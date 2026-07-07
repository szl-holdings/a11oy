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
    assert h["model"] == MODEL_TAG
    assert h["provider"] == PROVIDER
    assert h["url"].endswith("/v1")


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
    assert "UNAVAILABLE" in g["note"]
