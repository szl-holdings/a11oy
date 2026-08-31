# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED 749/14/163
# Authored by Yachay (CTO) — Co-Authored-By: Perplexity Computer Agent.
"""
tests/test_hickok_ingest.py — pytest suite for the Hickok cognitive-neuroscience
ingest (Lutar Anchors A36/A37/A38).

Required tests (Task G):
  (1) dorsal routes an imperative intent
  (2) ventral routes an interrogative intent
  (3) Spt delta ≤ ε for matched inputs
  (4) WHEN returns the phase mechanism string ("low_freq_phase_Heschl")
  (5) WHAT returns the gamma mechanism string ("gamma_planum_temporale")

Plus additive coverage: ambiguous → dual gate-fail (A36), neuro_citations present
on every receipt (Task E), and the dual-stream router middleware classification.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import a11oy_v4_hickok as H

EPSILON = 1e-3


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()

    # Routes the dual-stream router middleware watches (stubbed so we can assert
    # the middleware classification headers without standing up the real agent).
    @app.post("/api/a11oy/v4/agent/ask")
    async def _ask(request: Request):  # noqa: ANN202
        body = await request.json()
        return JSONResponse({"echo": body})

    @app.post("/api/a11oy/v4/predict")
    async def _predict(request: Request):  # noqa: ANN202
        body = await request.json()
        return JSONResponse({"echo": body})

    status = H.register(app, "a11oy")
    assert status["registered"] is True
    return TestClient(app)


# ---------------------------------------------------------------------------
# (1) dorsal routes an imperative intent
# ---------------------------------------------------------------------------
def test_dorsal_routes_imperative(client: TestClient) -> None:
    r = client.post("/api/a11oy/v4/dorsal", json={"intent": "sign the receipt"})
    assert r.status_code == 200
    data = r.json()
    assert data["lutar_anchor"] == "A36"
    assert "motor_pathway" in data
    assert data["classification"]["stream"] == "dorsal"
    assert data["classification"]["gate_pass"] is True
    # neuro_citations present with the dual-stream DOI (Task E)
    assert {"doi": "10.1038/nrn2113"} in data["neuro_citations"]
    assert data["signed_receipt_id"]


# ---------------------------------------------------------------------------
# (2) ventral routes an interrogative intent
# ---------------------------------------------------------------------------
def test_ventral_routes_interrogative(client: TestClient) -> None:
    r = client.post("/api/a11oy/v4/ventral", json={"intent": "what does this mean?"})
    assert r.status_code == 200
    data = r.json()
    assert data["lutar_anchor"] == "A36"
    assert "meaning" in data
    assert data["classification"]["stream"] == "ventral"
    assert data["classification"]["gate_pass"] is True
    assert {"doi": "10.1038/nrn2113"} in data["neuro_citations"]


# ---------------------------------------------------------------------------
# (3) Spt delta ≤ ε for matched inputs
# ---------------------------------------------------------------------------
def test_spt_delta_within_epsilon_for_matched(client: TestClient) -> None:
    r = client.post("/api/a11oy/v4/spt",
                    json={"sensory_target": 1.0, "motor_plan": 1.0})
    assert r.status_code == 200
    data = r.json()
    assert data["delta"] <= EPSILON
    assert {"doi": "10.1152/jn.91344.2008"} in data["neuro_citations"]
    # A mismatched pair must produce a strictly larger delta.
    r2 = client.post("/api/a11oy/v4/spt",
                     json={"sensory_target": 1.0, "motor_plan": 9.0})
    assert r2.json()["delta"] > EPSILON


# ---------------------------------------------------------------------------
# (4) WHEN returns the phase mechanism string
# ---------------------------------------------------------------------------
def test_when_returns_phase_mechanism(client: TestClient) -> None:
    r = client.post("/api/a11oy/v4/when", json={"stream": "left-Heschl"})
    assert r.status_code == 200
    data = r.json()
    assert data["mechanism"] == "low_freq_phase_Heschl"
    assert "phase_prediction" in data
    assert {"doi": "10.1101/474718"} in data["neuro_citations"]


# ---------------------------------------------------------------------------
# (5) WHAT returns the gamma mechanism string
# ---------------------------------------------------------------------------
def test_what_returns_gamma_mechanism(client: TestClient) -> None:
    r = client.post("/api/a11oy/v4/what", json={"stream": "planum-temporale"})
    assert r.status_code == 200
    data = r.json()
    assert data["mechanism"] == "gamma_planum_temporale"
    assert "semantic_prediction" in data
    assert {"doi": "10.1101/474718"} in data["neuro_citations"]


# ---------------------------------------------------------------------------
# Additive coverage
# ---------------------------------------------------------------------------
def test_ambiguous_intent_is_dual_gate_fail() -> None:
    """A36 says EXACTLY one stream — an ambiguous intent is `dual` and fails."""
    cls = H.classify_stream("banana table widget")
    assert cls["stream"] == "dual"
    assert cls["gate_pass"] is False
    assert cls["lutar_anchor"] == "A36"


def test_dual_stream_router_middleware_headers(client: TestClient) -> None:
    """The middleware classifies /agent/ask + /predict and writes A36 headers,
    while preserving the request body for the downstream handler."""
    r = client.post("/api/a11oy/v4/agent/ask", json={"intent": "deploy the build"})
    assert r.json()["echo"] == {"intent": "deploy the build"}  # body preserved
    assert r.headers.get("X-A11oy-Stream") == "dorsal"
    assert r.headers.get("X-A11oy-Stream-Gate") == "pass"
    assert r.headers.get("X-A11oy-Stream-Anchor") == "A36"

    r2 = client.post("/api/a11oy/v4/predict", json={"intent": "why does this fail?"})
    assert r2.headers.get("X-A11oy-Stream") == "ventral"

    r3 = client.post("/api/a11oy/v4/agent/ask", json={"intent": "xyzzy plugh"})
    assert r3.headers.get("X-A11oy-Stream") == "dual"
    assert r3.headers.get("X-A11oy-Stream-Gate") == "fail"


def test_every_receipt_carries_neuro_citations() -> None:
    """Task E: sign_khipu_receipt injects neuro_citations (default []) on the receipt."""
    signed = H._sign("probe", {"x": 1}, [H.CITE_DUAL_STREAM], stream="dorsal")
    assert "neuro_citations" in signed["receipt"]
    cites = signed["receipt"]["neuro_citations"]
    assert isinstance(cites, list) and len(cites) >= 1
    assert all("doi" in c and "label" in c for c in cites)


def test_dsse_default_empty_neuro_citations() -> None:
    """Task E: a receipt signed with no citations gets an empty list, not an error."""
    import szl_dsse as dsse
    out = dsse.sign_khipu_receipt({"organ": "test", "action": "noop"})
    assert out["receipt"]["neuro_citations"] == []
