# SPDX-License-Identifier: Apache-2.0
"""POST routing must not generate on opt-out or release unreceipted output."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import szl_governed_infer as governed
import szl_llm_registry as registry
import szl_operator_auth as operator_auth

_OPERATOR = "fixture-operator-secret-not-real"


@pytest.fixture(autouse=True)
def _operator_key(monkeypatch):
    monkeypatch.setenv(operator_auth.OPERATOR_KEY_ENV, _OPERATOR)


def _client(*, authorized=True) -> TestClient:
    app = FastAPI()
    registry.register(app)
    client = TestClient(app)
    if authorized:
        client.headers.update({"Authorization": "Bearer " + _OPERATOR})
    return client


def test_anonymous_route_is_blocked_before_harness_or_provider(monkeypatch):
    import szl_model_harness as harness

    def forbidden(*_args, **_kwargs):
        raise AssertionError("anonymous request reached an effect path")

    monkeypatch.setattr(harness, "apply", forbidden)
    monkeypatch.setattr(registry, "sovereign_mesh_matrix", forbidden)
    for body in ({"prompt": "no effect", "model_id": registry._SOVEREIGN_BACKEND_ID},
                 {"prompt": "no harness", "harness_profile_id": "szl-honest-operator"}):
        response = _client(authorized=False).post(
            "/api/a11oy/v1/llm/route", json=body)
        assert response.status_code == 401
        assert response.json()["status"] == "BLOCKED"


def test_requested_harness_exception_does_not_fall_back_to_plain_route(monkeypatch):
    import szl_model_harness as harness

    def broken_harness(*_args, **_kwargs):
        raise RuntimeError("private harness diagnostic")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("plain route ran after requested harness failure")

    monkeypatch.setattr(harness, "apply", broken_harness)
    monkeypatch.setattr(registry, "sovereign_mesh_matrix", forbidden)
    response = _client().post(
        "/api/a11oy/v1/llm/route",
        json={"prompt": "do not fall back", "harness_profile_id": "szl-honest-operator"},
    )
    assert response.status_code == 503
    assert response.json()["status"] == "UNAVAILABLE"
    assert "private harness diagnostic" not in response.text


def test_explicit_non_sovereign_opt_out_never_probes_or_generates(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("sovereign mesh touched after explicit opt-out")

    monkeypatch.setattr(registry, "sovereign_mesh_matrix", forbidden)
    monkeypatch.setattr(registry, "sovereign_mesh_generate", forbidden)
    response = _client().post(
        "/api/a11oy/v1/llm/route",
        json={"prompt": "use the selected cloud route",
              "model_id": "claude_sonnet_4_6", "prefer_local": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_selected"]["model_id"] == "claude_sonnet_4_6"
    assert "[HONEST STUB]" in body["response"] or "[CONFIGURED_UNVERIFIED]" in body["response"]


def test_conflicting_explicit_sovereign_and_opt_out_is_blocked(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("conflicting request touched the sovereign mesh")

    monkeypatch.setattr(registry, "sovereign_mesh_matrix", forbidden)
    monkeypatch.setattr(registry, "sovereign_mesh_generate", forbidden)
    response = _client().post(
        "/api/a11oy/v1/llm/route",
        json={"prompt": "contradiction", "model_id": registry._SOVEREIGN_BACKEND_ID,
              "prefer_local": False},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "BLOCKED"


@pytest.mark.parametrize("receipt_failure", ["returned", "raised", "inconsistent", "missing_hash"])
def test_generated_text_is_withheld_when_receipt_cannot_verify(
        monkeypatch, receipt_failure):
    private_text = "PRIVATE_PROVIDER_OUTPUT_SENTINEL"
    private_url = "https://private-tunnel.example.invalid/v1"
    private_token = "private-gateway-token-123456789"
    canonical = registry._SOVEREIGN_MODEL_TAG
    for name in ("A11OY_BRAIN_URL", "A11OY_MODEL_BASE_URL",
                 "A11OY_SOVEREIGN_GATEWAY_URL", "SZL_SOVEREIGN_NODES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", private_url)
    monkeypatch.setenv("SZL_LOCAL_LLM_MODEL", canonical)
    monkeypatch.setenv("A11OY_SOVEREIGN_GATEWAY_KEY", private_token)
    monkeypatch.setattr(registry, "_FORUM_LOG", [])
    calls = []

    def metadata_and_generation(url, *, method="GET", body=None, timeout=4.0):
        calls.append((method, url))
        if url.endswith("/api/tags"):
            return {"models": [{"name": canonical}]}, None
        if url.endswith("/api/generate"):
            return {"response": private_text, "eval_count": 1}, None
        return None, "unexpected fixture route"

    monkeypatch.setattr(registry, "_http_json", metadata_and_generation)
    receipt_calls = []

    def failed_receipt(*_args, **_kwargs):
        receipt_calls.append(True)
        if receipt_failure == "raised":
            raise OSError("fixture ledger unavailable " + private_token)
        if receipt_failure == "inconsistent":
            return {"ok": False, "inference_receipted": True,
                    "receipt_hash": "unverified-hash",
                    "reason": "fixture replay did not verify " + private_url}
        if receipt_failure == "missing_hash":
            return {"ok": True, "inference_receipted": True,
                    "reason": "fixture omitted receipt hash " + private_url}
        return {"ok": False, "inference_receipted": False,
                "reason": "fixture replay did not verify " + private_url}

    monkeypatch.setattr(governed, "record_provider_generation", failed_receipt)
    response = _client().post(
        "/api/a11oy/v1/llm/route",
        json={"prompt": "withhold if no receipt",
              "model_id": registry._SOVEREIGN_BACKEND_ID},
    )
    assert response.status_code == 503
    body = response.json()
    assert receipt_calls == [True]
    assert sum(url.endswith("/api/tags") for _method, url in calls) == 1
    assert sum(url.endswith("/api/generate") for _method, url in calls) == 1
    assert body["generated"] is True  # compute happened; never claim otherwise
    assert body["inference_receipted"] is False
    assert body["operational"] is False
    assert body["label"] == "REACHABLE_UNRECEIPTED"
    assert body["response"].startswith("[UNAVAILABLE]")
    assert "raw" not in body["local"]
    serialized = json.dumps(body)
    assert private_text not in serialized
    assert private_url not in serialized
    assert private_token not in serialized
    assert "private-tunnel.example.invalid" not in serialized
    assert private_text not in json.dumps(registry._FORUM_LOG[-1])
    assert private_url not in json.dumps(registry._FORUM_LOG[-1])
    assert private_token not in json.dumps(registry._FORUM_LOG[-1])
