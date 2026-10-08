# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""Wave M (DEV 1) — szl-sovereign-local backend contract tests (offline).

The founder's sovereign model runs on the Tower (Ollama, model tag
`llama3-szl-finetuned-q4`, Doctrine-v11 system prompt) served OpenAI-compatible
at SZL_LOCAL_LLM_URL. The Tower is NOT reachable from CI/cloud, so this suite
pins the CRITICAL honesty contract: when the endpoint is down the backend must
degrade to an honest UNAVAILABLE label — a 200 response with reachable=False and
NO fabricated model text — and must NEVER raise / 500.

Runs fully offline: we point SZL_LOCAL_LLM_URL at a dead localhost port so the
guarded probe/generate deterministically fail, and assert the honest path.
"""
import os
import json

# Dead port — nothing listens — deterministic UNAVAILABLE (before importing reg).
os.environ["SZL_LOCAL_LLM_URL"] = "http://127.0.0.1:59999/v1"
os.environ["SZL_LOCAL_LLM_PROBE_TIMEOUT"] = "0.4"
os.environ["SZL_LOCAL_LLM_GEN_TIMEOUT"] = "0.6"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_llm_registry as reg

BACKEND_ID = "szl-sovereign-local"
MODEL_TAG = "llama3-szl-finetuned-q4"
PROVIDER = "SZL sovereign (Ollama, local, Doctrine-v11 system prompt)"


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    reg.register(app)
    return TestClient(app)


def test_first_class_backend_registered():
    m = {x["model_id"]: x for x in reg.MODEL_REGISTRY}
    assert BACKEND_ID in m, "szl-sovereign-local must be a first-class backend"
    sov = m[BACKEND_ID]
    assert sov["model_slug"] == MODEL_TAG
    assert sov["provider"] == PROVIDER
    assert sov["api_base"] == "http://localhost:11434/v1"  # OpenAI-compat default
    assert sov.get("own_metal") is True and sov.get("route_first") is True


def test_health_honest_unavailable_when_down(client):
    r = client.get("/api/a11oy/v1/llm/sovereign/health")
    assert r.status_code == 200  # honest, not an error
    h = r.json()
    for k in ("reachable", "model", "url", "provider", "label"):
        assert k in h, f"health must return required key {k!r}"
    assert h["reachable"] is False
    assert h["label"] == "UNAVAILABLE"
    assert h["model"] is None
    assert h["canonical_model"] == MODEL_TAG
    assert h["model_ready"] is False
    assert h["inference_receipted"] is False
    assert h["operational"] is False
    assert h["provider"] == PROVIDER
    assert h["url"] is None  # public status never publishes a private origin


def test_public_health_and_router_status_withhold_private_mesh_details(client, monkeypatch):
    """Anonymous status preserves booleans but never serializes routing metadata."""
    private_url = "http://secret-tunnel.example.invalid:11434/v1"
    private_ip = "10.4.5.6"
    private_model = "private-model-inventory-sentinel"
    auth_error = "Bearer auth-error-private-detail"
    matrix = {
        "node_count": 1, "reachable_count": 1, "any_reachable": True,
        "primary_base_url": private_url,
        "selected": {"index": 0, "role": "primary", "base_url": private_url,
                     "served_models": [MODEL_TAG, private_model]},
        "nodes": [{"index": 0, "role": "primary", "reachable": True,
                   "base_url": private_url, "served_models": [MODEL_TAG, private_model],
                   "probed": [{"url": f"http://{private_ip}/api/tags",
                               "error": auth_error}], "error": auth_error,
                   "note": private_url}],
        "note": private_url,
    }
    monkeypatch.setattr(reg, "sovereign_mesh_matrix", lambda: matrix)
    monkeypatch.setattr(reg, "_sovereign_base", lambda: private_url)
    monkeypatch.setattr(reg, "_sovereign_env_present", lambda: True)
    monkeypatch.setattr(reg, "_sovereign_model_slug", lambda: MODEL_TAG)
    monkeypatch.setattr(reg, "sovereign_probe", lambda _base: {
        "live": True, "models": [MODEL_TAG, private_model],
        "base_url": private_url, "env_present": True, "api_style": "ollama /api",
        "probed": [{"url": f"http://{private_ip}/api/tags", "error": auth_error}],
        "note": private_url,
    })
    monkeypatch.setattr(reg, "_inference_receipt_state", lambda _model: {
        "inference_receipted": False, "successful_receipt_count": 0,
        "total_receipt_count": 0, "chain_ok": True, "latest_receipt_hash": None,
    })
    monkeypatch.setattr(reg, "resolve_code_llm_key", lambda: {
        "wired": True, "provider": "fixture", "env_used": "A11OY_CODE_LLM_KEY",
        "base_url": private_url, "honest_note": "fixture configured",
    })
    health = client.get("/api/a11oy/v1/llm/sovereign/health")
    router = client.get("/api/a11oy/v1/llm/router/status?probe=1")
    for response in (health, router):
        assert response.status_code == 200
        serialized = json.dumps(response.json())
        for forbidden in (private_url, "secret-tunnel", private_ip,
                          private_model, auth_error):
            assert forbidden not in serialized
    assert health.json()["reachable"] is True
    assert health.json()["endpoint_reachable"] is True
    assert health.json()["label"] == "UNKNOWN"
    assert health.json()["gpu_verified"] is False
    assert health.json()["weights_verified"] is False
    assert health.json()["ownership_proof"] == "UNAVAILABLE"
    assert health.json()["model_ready"] is True
    assert health.json()["state"] == "UNKNOWN"
    assert health.json()["operational"] is False
    assert health.json()["wired"] is False
    assert health.json()["live"] is False
    assert health.json()["mesh"]["reachable_count"] == 1
    assert router.json()["local_nodes"][0]["reachable"] is True
    assert router.json()["local_nodes"][0]["endpoint_reachable"] is True
    assert router.json()["local_nodes"][0]["label"] == "UNKNOWN"
    assert router.json()["local_nodes"][0]["ownership_proof"] == "UNAVAILABLE"
    assert router.json()["local_nodes"][0]["model_ready"] is True
    assert router.json()["local_nodes"][0]["operational"] is False
    assert router.json()["local_nodes"][0]["wired"] is False
    assert matrix["selected"]["base_url"] == private_url  # internal routing unchanged


def test_route_sovereign_honest_unavailable_not_error(client):
    r = client.post("/api/a11oy/v1/llm/route",
                    json={"model_id": BACKEND_ID, "prompt": "State your doctrine."})
    assert r.status_code == 200
    d = r.json()
    assert d["reachable"] is False
    assert d["label"] == "UNAVAILABLE"
    # No fabricated model text — the response is an explicit UNAVAILABLE marker.
    assert "[UNAVAILABLE]" in d["response"]
    # Receipt still records the intended sovereign backend (no fabrication).
    assert d["lambda_receipt"]["model_id"] == BACKEND_ID
    assert d["lambda_receipt"]["reachable"] is False
    assert "Conjecture 1" in d["conjecture_note"]  # Λ = Conjecture 1


def test_unreachable_sovereign_does_not_hijack_default_routing(client):
    # Own-metal-first must only fire when the node is reachable. Down => fall
    # through to the normal Λ-gated free/paid tiers.
    r = client.post("/api/a11oy/v1/llm/route", json={"prompt": "explain gravity"})
    assert r.status_code == 200
    assert r.json()["lambda_receipt"]["model_id"] != BACKEND_ID


def test_registry_snapshot_reflects_sovereign(client):
    r = client.get("/api/a11oy/v1/llm/registry?probe=1")
    assert r.status_code == 200
    sv = r.json()["sovereign"]
    assert sv["backend_id"] == BACKEND_ID
    assert sv["reachable"] is False
    assert sv["label"] == "UNAVAILABLE"
    assert "own-metal" in sv["route_order"]


def test_probe_never_raises_and_reports_unavailable():
    # Direct unit-level guard: the probe returns a dict (never raises) with live=False.
    p = reg.sovereign_probe("http://127.0.0.1:59999/v1", timeout=0.4)
    assert p["live"] is False
    assert "UNAVAILABLE" in p["note"]
    g = reg.sovereign_generate("hi", base="http://127.0.0.1:59999/v1", timeout=0.4)
    assert g["live"] is False and g["text"] is None  # never fabricated text
    assert g["model_ready"] is False
    assert "no executable model" in g["note"]
