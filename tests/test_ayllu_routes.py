"""Ayllu HTTP route-wiring regression guard.

REGRESSION THIS CATCHES: the ayllu handlers annotate `request: "Request"` as a
string forward-ref (because a11oy_ayllu.py uses `from __future__ import
annotations`). FastAPI resolves endpoint annotations with get_type_hints against
the handler's *module* globals. If `Request` is only imported *inside*
register() (function-local), FastAPI cannot resolve the forward-ref, fails to
recognise the special Request parameter, and mis-treats `request` as a REQUIRED
query param — so every GET route 422s with loc=["query","request"] and the POST
handlers never even parse their body. The module-level (guarded) `from fastapi
import Request` in a11oy_ayllu.py is what keeps these green.

A route-*presence* test (see test_demo_critical_routes.py) cannot catch this: the
route IS registered, it just returns 422 instead of running. So this guard boots
the ayllu routes on a bare app and exercises them for real (no mocks, no network).
"""
import asyncio
import hashlib
import sys
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import a11oy_ayllu  # noqa: E402
from ayllu import backend as ayllu_backend  # noqa: E402


def _client() -> TestClient:
    app = FastAPI()
    a11oy_ayllu.register(app, ns="a11oy")
    return TestClient(app)


def test_roster_returns_200_not_query_param_422():
    r = _client().get("/api/a11oy/v1/ayllu/roster")
    assert r.status_code == 200, (
        "roster GET must be 200. A 422 here is the forward-ref regression where "
        "FastAPI mis-binds `request` as a required query param — re-add the "
        "module-level `from fastapi import Request` in a11oy_ayllu.py. "
        f"Body: {r.text[:300]}"
    )
    d = r.json()
    assert d["count"] == len(a11oy_ayllu.ROSTER) == 11
    assert len(d["personas"]) == 11
    assert "mode" in d["backend"]


def test_second_brain_route_exposes_compound_runtime_boundary(monkeypatch):
    monkeypatch.setattr(
        a11oy_ayllu._backend,
        "backend_status",
        lambda: {
            "mode": "live",
            "forge_profiles": {
                "profiles": {
                    "BrainNavigator-v1": {
                        "expected_model": "khipu:latest",
                        "served_model": "khipu:latest",
                        "available": True,
                    }
                }
            },
        },
    )
    import a11oy_org_rag

    monkeypatch.setattr(
        a11oy_org_rag,
        "status",
        lambda: {
            "built": True,
            "document_count": 12,
            "chunk_count": 34,
            "brain_handle_count": 9464,
            "training_authority_rows": 0,
            "integrity_state": "VERIFIED_AT_PUBLISH",
        },
    )
    response = _client().get("/api/a11oy/v1/ayllu/second-brain")
    assert response.status_code == 200
    body = response.json()
    assert body["system_type"] == "COMPOUND_MODEL_WITH_EXTERNAL_EVIDENCE_MEMORY"
    assert body["ready_for_grounded_navigation"] is True
    assert body["profile"]["artifact_binding"] == "UNBOUND"
    assert body["memory"]["brain_handle_count"] == 9464
    assert body["memory"]["training_authority_rows"] == 0
    assert body["hard_boundaries"]["model_can_read_raw_node_content"] is False


def test_page_and_lounge_are_200():
    c = _client()
    page = c.get("/ayllu")
    assert page.status_code == 200
    # Upgrade guard: the standalone Ayllu space is a first-class surface that
    # offers a round-trip link back to the a11oy command centre (/console), so
    # it is reachable both ways — its own space, cleanly linked, not embedded.
    assert 'href="/console"' in page.text, (
        "The /ayllu page must link back to the command centre (/console).")
    assert "Â·" not in page.text, "Council output must not ship mojibake separators."
    assert "@media (max-width:720px)" in page.text
    assert "overflow-wrap:anywhere" in page.text
    assert 'aria-label="Ayllu sections"' in page.text
    assert "overflow-x:hidden" not in page.text
    assert 'id="councilout" class="out" aria-live="polite"' in page.text
    assert 'id="sb-out"' in page.text
    assert "/api/a11oy/v1/ayllu/second-brain" in page.text
    assert "gradient admission" in page.text
    assert "Brain handles" in page.text
    assert "data:{error:'request unavailable'}" in page.text
    lr = c.get("/api/a11oy/v1/ayllu/lounge")
    assert lr.status_code == 200
    assert "recent" in lr.json()


def test_ask_empty_body_hits_our_validation_not_fastapi_query_422():
    r = _client().post("/api/a11oy/v1/ayllu/ask", json={})
    assert r.status_code == 422
    err = r.json().get("error")
    assert isinstance(err, str) and ("persona" in err or "prompt" in err), (
        "empty-body ask must reach OUR validation ('persona' and 'prompt' are "
        "required), not FastAPI's query-param 422 (the forward-ref regression). "
        f"Got: {r.json()}"
    )


def test_ask_unknown_persona_is_404():
    r = _client().post(
        "/api/a11oy/v1/ayllu/ask", json={"persona": "nobody", "prompt": "hi"})
    assert r.status_code == 404


def test_ask_receipt_binds_an_empty_answer_exactly(monkeypatch):
    async def empty_answer(**_kwargs):
        return {
            "text": "",
            "model": "local-test-model",
            "stub": False,
            "honesty": "answer produced by the test backend",
        }

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", empty_answer)
    monkeypatch.setattr(
        a11oy_ayllu,
        "_make_receipt",
        lambda payload, sign_fn=None: payload,
    )
    a11oy_ayllu._ASK_BUCKET._hits.clear()
    response = _client().post(
        "/api/a11oy/v1/ayllu/ask",
        json={"persona": "Amaru", "prompt": "Return an empty answer"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["turn"]["answer"] == ""
    assert body["receipt"]["output_sha256"] == hashlib.sha256(b"").hexdigest()


def test_ask_receipt_binds_handles_and_exact_augmented_prompt(monkeypatch):
    async def grounded_answer(**_kwargs):
        return {
            "text": '{"decision":"PLAN","citedNodeIds":["node-1"]}',
            "model": "khipu:latest",
            "stub": False,
            "honesty": "bounded grounded plan",
            "model_attestation": {
                "served_model": "khipu:latest",
                "model_manifest_sha256": "a" * 64,
                "modelfile_sha256": "b" * 64,
                "modelfile_layer_sha256": ["c" * 64],
            },
            "grounding": {
                "schema": "szl.brain.navigator-context/v1",
                "state": "GROUNDED_HANDLES_READY",
                "evidence_set_sha256": "d" * 64,
                "handles_sha256": "e" * 64,
                "augmented_prompt_sha256": "f" * 64,
                "handle_evidence_set_equivalent": True,
                "grounded_count": 1,
                "citation_validation": {
                    "state": "CITATIONS_WITHIN_OFFERED_HANDLES",
                    "cited_node_ids": ["node-1"],
                },
            },
        }

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", grounded_answer)
    monkeypatch.setattr(
        a11oy_ayllu, "_make_receipt", lambda payload, sign_fn=None: payload)
    a11oy_ayllu._ASK_BUCKET._hits.clear()
    response = _client().post(
        "/api/a11oy/v1/ayllu/ask",
        json={"persona": "Maskaq", "prompt": "ground this"},
    )
    assert response.status_code == 200
    receipt = response.json()["receipt"]
    assert receipt["evidence_set_sha256"] == "d" * 64
    assert receipt["handles_sha256"] == "e" * 64
    assert receipt["augmented_prompt_sha256"] == "f" * 64
    assert len(receipt["citation_validation_sha256"]) == 64
    assert len(receipt["model_attestation_sha256"]) == 64


def test_council_contract_never_promotes_model_text_to_verified_truth():
    result = {
        "participants": ["Amaru"],
        "mode": "single-round",
        "rounds": [{
            "persona": "Amaru", "round": 1, "model": "szl-sovereign:latest",
            "stub": False, "answer": "a model claim", "energy_receipt": None,
        }],
    }
    contract = a11oy_ayllu._build_council_contract(
        "review this", result, {"state": "LIVE", "receipt": None})
    assert contract["decision_state"] == "PROPOSAL_ONLY"
    assert contract["correctness_state"] == "NOT_VERIFIED"
    assert contract["turn_evidence"][0]["correctness_state"] == "UNVERIFIED_MODEL_OUTPUT"
    assert contract["semantic_consensus"]["state"] == "NOT_MEASURED"


def test_council_fanout_uses_bounded_tokens_and_one_parallel_deadline(monkeypatch):
    calls = []

    async def fake_complete(*_args, **kwargs):
        calls.append({"kwargs": kwargs, "started": time.monotonic()})
        await asyncio.sleep(0.05)
        return {"text": "proposal", "model": "test", "stub": False,
                "timeout": False, "token_budget": kwargs["max_tokens"],
                "timeout_s": kwargs["timeout_s"]}

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", fake_complete)
    a11oy_ayllu._COUNCIL_BUCKET._hits.clear()
    response = _client().post("/api/a11oy/v1/ayllu/council", json={
        "prompt": "Bound this review",
        "personas": ["Amaru", "Kamachiq", "Qhatuq"],
        "debate": False,
    })
    assert response.status_code == 200
    assert response.json()["result"]["published_to_lounge"] is False
    assert len(calls) == 3
    assert {c["kwargs"]["max_tokens"] for c in calls} == {
        a11oy_ayllu.COUNCIL_MAX_TOKENS}
    assert {c["kwargs"]["timeout_s"] for c in calls} == {
        a11oy_ayllu.COUNCIL_TURN_TIMEOUT_S}
    started = [c["started"] for c in calls]
    assert max(started) - min(started) < 0.03, (
        "independent council turns should start as concurrent bounded fan-out")
    limits = response.json()["contract"]["limits"]
    assert limits["round_fanout"] == "CONCURRENT_BOUNDED"
    assert limits["tokens_per_turn_max"] == a11oy_ayllu.COUNCIL_MAX_TOKENS


def test_backend_timeout_cancels_turn_and_fabricates_no_answer(monkeypatch):
    cancelled = {"value": False}

    async def slow_complete(*_args, **_kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled["value"] = True
            raise

    monkeypatch.setitem(
        sys.modules, "a11oy_code_orchestrator",
        SimpleNamespace(agent_model_complete=slow_complete))
    result = asyncio.run(ayllu_backend.model_complete(
        "system", "prompt", max_tokens=77, timeout_s=0.02))
    assert cancelled["value"] is True
    assert result["timeout"] is True
    assert result["stub"] is True
    assert result["model"] == "timeout"
    assert result["text"] is None
    assert result["token_budget"] == 77
    assert "no answer was fabricated" in result["honesty"]


def test_council_khipu_survives_process_store_reopen(monkeypatch, tmp_path):
    """Council proposals append to the same verified SQLite chain after reopen.

    This proves local process-restart persistence only. The response must continue
    to label redeploy durability NOT_VERIFIED because no persistent production
    mount is demonstrated by this test.
    """
    db_path = tmp_path / "ayllu-council.sqlite3"
    monkeypatch.setenv("A11OY_AYLLU_KHIPU_PATH", str(db_path))

    async def fake_complete(*_args, **kwargs):
        return {"text": "bounded proposal", "model": "test", "stub": False,
                "timeout": False, "token_budget": kwargs["max_tokens"],
                "timeout_s": kwargs["timeout_s"]}

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", fake_complete)
    monkeypatch.setattr(
        a11oy_ayllu, "_nemo_council_route",
        lambda *_args, **_kwargs: {
            "state": "UNAVAILABLE", "receipt": None,
            "honesty": "test does not claim a Nemo model route",
        })

    def convene():
        app = FastAPI()
        a11oy_ayllu.register(app, ns="restarttest")
        a11oy_ayllu._COUNCIL_BUCKET._hits.clear()
        response = TestClient(app).post(
            "/api/restarttest/v1/ayllu/council",
            json={"prompt": "audit this", "personas": ["Amaru"]})
        assert response.status_code == 200
        return response.json()

    first = convene()
    second = convene()  # new app + newly-opened DurableKhipu over the same path

    first_chain = first["contract"]["chain"]
    second_chain = second["contract"]["chain"]
    assert first_chain["storage"]["backend"] == "sqlite"
    assert first_chain["storage"]["survives_process_restart"] is True
    assert first_chain["storage"]["survives_redeploy"] == "NOT_VERIFIED"
    assert first_chain["seq"] == 0
    assert second_chain["seq"] == 1
    assert second_chain["depth"] == 2
    assert second_chain["chain_verified"] is True
