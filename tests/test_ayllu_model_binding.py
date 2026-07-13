import asyncio
import base64
import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_ayllu
import a11oy_code_orchestrator as orchestrator
import szl_yupaq_compute
from ayllu.model_binding import family_binding, persona_binding
from ayllu.personas import ROSTER


ROOT = Path(__file__).resolve().parents[1]


def _client(namespace: str = "a11oy") -> TestClient:
    app = FastAPI()
    a11oy_ayllu.register(app, ns=namespace)
    return TestClient(app)


def _payload(envelope: dict) -> dict:
    return json.loads(base64.b64decode(envelope["payload"]).decode("utf-8"))


def test_all_personas_map_once_to_declared_forge_profiles():
    family = json.loads((ROOT / "model_release/szl-forge-family.json").read_text())
    release_binding = json.loads((
        ROOT / "model_release/szl-ayllu-binding.json").read_text())
    declared = {profile["profile_id"] for profile in family["profiles"]}
    profile_states = {
        profile["profile_id"]: profile["state"] for profile in family["profiles"]
    }
    binding = family_binding()
    mappings = binding["personas"]
    assert {item["persona"] for item in mappings} == {p.name for p in ROSTER}
    assert len(mappings) == len(ROSTER) == 11
    assert {item["primary_profile"] for item in mappings} <= declared
    assert {
        profile
        for item in mappings
        for profile in item["supporting_profiles"]
    } <= declared
    assert all(
        item["profile_state"] == profile_states[item["primary_profile"]]
        for item in mappings
    )
    assert binding["runtime_backend_is_profile_pinned"] is False
    assert binding["hard_boundaries"]["personas_are_separate_weights"] is False
    assert release_binding["schema_version"] == binding["schema"]
    assert release_binding["profile_mappings"] == {
        item["persona"]: item["primary_profile"] for item in mappings
    }
    ayllu_surface = next(
        item for item in family["interface_surfaces"]
        if item["surface_id"] == "A11oy-Ayllu")
    assert ayllu_surface["state"] == "COUNCIL_RUNTIME_NOT_MODEL"


def test_ayllu_compute_authority_is_proposal_only_and_allowlisted():
    binding = family_binding(namespace="union")
    assert binding["family_id"] == "SZL-Forge-1.5B"
    assert binding["binding_state"] == "ROUTER_INTEGRATED_FORGE_PROFILE_NOT_PINNED"
    assert binding["compute"]["capabilities_endpoint"].startswith(
        "/api/union/v1/compute/")
    assert set(binding["compute"]["allowed_operations"]) == set(
        szl_yupaq_compute.OPERATIONS)
    hard = binding["hard_boundaries"]
    assert hard["tool_dispatch_active"] is False
    assert hard["can_execute_external_actions"] is False
    assert hard["can_approve_own_proposal"] is False
    assert hard["can_sign_own_evidence"] is False
    assert hard["can_self_certify_correctness"] is False
    yupaq = persona_binding("Yupaq")
    assert yupaq["authority"] == "PROPOSAL_ONLY"
    assert set(yupaq["compute_operations"]) == set(szl_yupaq_compute.OPERATIONS)


def test_roster_manifest_and_binding_endpoint_expose_same_family_contract():
    client = _client("bindingtest")
    roster = client.get("/api/bindingtest/v1/ayllu/roster").json()
    endpoint = client.get("/api/bindingtest/v1/ayllu/model-binding").json()
    manifest = client.get("/api/bindingtest/v1/ayllu/council/manifest").json()
    assert roster["model_family"]["family_id"] == endpoint["family_id"]
    assert manifest["model_family"]["family_id"] == endpoint["family_id"]
    for value in (roster["model_family"], endpoint, manifest["model_family"]):
        assert value["compute"]["capabilities_endpoint"].startswith(
            "/api/bindingtest/v1/compute/")
        assert value["runtime_backend_is_profile_pinned"] is False


def test_ask_receipt_binds_profile_intent_without_relabeling_actual_model(monkeypatch):
    async def fake_complete(*_args, **kwargs):
        return {
            "text": "bounded proposal",
            "model": "router-observed-model",
            "stub": False,
            "timeout": False,
            "token_budget": kwargs["max_tokens"],
            "timeout_s": kwargs["timeout_s"],
        }

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", fake_complete)
    a11oy_ayllu._ASK_BUCKET._hits.clear()
    a11oy_ayllu._LOUNGE.feed.clear()
    response = _client().post("/api/a11oy/v1/ayllu/ask", json={
        "persona": "Yupaq",
        "prompt": "Draft a typed inventory proposal",
    })
    assert response.status_code == 200
    body = response.json()
    turn = body["turn"]
    assert turn["model"] == "router-observed-model"
    assert turn["loop"]["tool_dispatch"] is False
    assert turn["model_binding"]["primary_profile"] == "ReceiptAgent-v1"
    assert turn["model_binding"]["actual_model"] == "router-observed-model"
    receipt = _payload(body["receipt"])
    digest = hashlib.sha256(json.dumps(
        turn["model_binding"], sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    assert receipt["model_binding_sha256"] == digest
    assert receipt["profile_intent"] == "ReceiptAgent-v1"
    assert receipt["model"] == "router-observed-model"
    assert receipt["output_sha256"] == hashlib.sha256(
        turn["answer"].encode("utf-8")).hexdigest()
    assert a11oy_ayllu._LOUNGE.feed == []


def test_local_fallback_receipt_uses_effective_served_model_identity(monkeypatch):
    async def fake_call(_client, _model, _payload):
        return {"choices": [{"message": {"content": "local"}}]}

    monkeypatch.setattr(orchestrator, "_call_model", fake_call)
    monkeypatch.setattr(
        orchestrator, "_serving_base", lambda: ("http://127.0.0.1:11434/v1", True))
    monkeypatch.setattr(
        orchestrator, "_map_model_for_local", lambda _model: "szl-forge-loaded:1.5b")
    _data, model_used = asyncio.run(orchestrator._call_model_resilient(
        object(), ["router-candidate"], {"messages": []}))
    assert model_used == "szl-forge-loaded:1.5b"


def test_reachable_no_key_local_backend_is_not_forced_to_stub(monkeypatch):
    monkeypatch.setattr(orchestrator, "has_inference_credential", lambda: False)
    monkeypatch.setattr(
        orchestrator, "_serving_base", lambda: ("http://127.0.0.1:11434/v1", True))
    monkeypatch.setattr(orchestrator, "_get_client", lambda: object())
    monkeypatch.setattr(orchestrator, "route", lambda *_args, **_kwargs: {
        "model": "router-model", "fallbacks": [], "tier": "T2"})
    monkeypatch.setattr(orchestrator, "_emit_turn_receipt", lambda *_args, **_kwargs: None)

    async def fake_call(_client, _candidates, _payload):
        return ({"choices": [{"message": {"content": "local answer"}}]},
                "szl-forge-local")

    monkeypatch.setattr(orchestrator, "_call_model_resilient", fake_call)
    assert orchestrator.inference_backend_ready() is True
    result = asyncio.run(orchestrator.agent_model_complete(
        [{"role": "user", "content": "local test"}], max_tokens=32))
    assert result["stub"] is False
    assert result["model"] == "szl-forge-local"
    assert result["text"] == "local answer"


def test_paid_inference_routes_reject_oversized_bodies_before_model_call(monkeypatch):
    called = {"value": False}

    async def should_not_run(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("oversized request reached the model backend")

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", should_not_run)
    client = _client()
    oversized = "x" * (a11oy_ayllu.MAX_BODY_BYTES + 1)
    for path, body in (
        ("ask", {"persona": "Yupaq", "prompt": oversized}),
        ("council", {"prompt": oversized}),
    ):
        response = client.post(
            f"/api/a11oy/v1/ayllu/{path}",
            content=json.dumps(body),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413
    assert called["value"] is False
