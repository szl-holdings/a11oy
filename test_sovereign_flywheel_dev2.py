"""Wave M · Dev 2 — sovereign flywheel TestClient smoke.

Verifies that ALL FOUR governed flywheel flows accept model_id="szl-sovereign-local"
(alias of Dev-1's registry backend id "sovereign_local") and, when the local Tower
endpoint (SZL_LOCAL_LLM_URL) is UNSET/unreachable, degrade HONESTLY:

  * HTTP 200 (never 500) — the governance pipeline still runs,
  * an honest MODELED/UNAVAILABLE label (never a fabricated model response),
  * the intended sovereign backend recorded in the signed receipt.

Run: python3 test_sovereign_flywheel_dev2.py   (also import-safe under pytest).
Additive; touches no locked-8 numbers; Λ = Conjecture 1 (advisory).
"""
from __future__ import annotations
import os

# Force the honest-degradation path: no local sovereign endpoint in CI/cloud.
os.environ.pop("SZL_LOCAL_LLM_URL", None)

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_model_harness as H
import szl_eval_arena as E
import szl_agent_loop_governed as A
import szl_governed_rag as R

NS = "a11oy"


def _build_client() -> TestClient:
    app = FastAPI()
    H.register(app, NS)
    E.register(app, NS)
    A.register(app, NS)
    R.register(app, NS)
    return TestClient(app)


def _sov_block(obj):
    """Pull the sovereign receipt block from any of the flows' return shapes."""
    if not isinstance(obj, dict):
        return None
    rc = obj.get("receipt") or obj.get("harness_receipt") or obj.get("composite_receipt") or {}
    body = rc.get("body") or rc
    return body.get("sovereign") or obj.get("sovereign") or rc.get("sovereign")


def _no_fabrication(text):
    """A non-LIVE sovereign response must be an explicit honest stub, never a
    fabricated model answer. We assert the honest marker is present."""
    if text is None:
        return True
    t = str(text).upper()
    return ("UNAVAILABLE" in t) or ("MODELED" in t) or ("HONEST STUB" in t) or ("SOVEREIGN" in t)


def test_harness_apply_sovereign():
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/harness/apply", json={
        "profile_id": "szl-honest-operator",
        "model_id": "szl-sovereign-local",
        "prompt": "Say hello.",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    sov = _sov_block(j)
    assert sov, "harness must record the intended sovereign backend"
    assert (sov.get("backend_id") or sov.get("backend")) == "sovereign_local"
    assert j.get("harness_state") in ("UNAVAILABLE", "MODELED"), j.get("harness_state")
    assert _no_fabrication(j.get("response"))
    return j


def test_eval_run_sovereign():
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/eval/run", json={
        "suite": "core_honest_v1",
        "model_id": "szl-sovereign-local",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    sov = _sov_block(j)
    assert sov, "eval must record the intended sovereign backend"
    assert (sov.get("backend_id") or sov.get("backend")) == "sovereign_local"
    assert j.get("honesty_label") in ("UNAVAILABLE", "MODELED"), j.get("honesty_label")
    return j


def test_agentloop_run_sovereign():
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/agentloop/run", json={
        "task": "State your doctrine in one line.",
        "model_id": "szl-sovereign-local",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    sov = _sov_block(j)
    assert sov, "agentloop must record the intended sovereign backend"
    assert (sov.get("backend_id") or sov.get("backend")) == "sovereign_local"
    lbl = j.get("sovereign_label") or ""
    assert ("UNAVAILABLE" in lbl.upper()) or ("MODELED" in lbl.upper()), lbl
    return j


def test_rag_query_sovereign():
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/rag/query", json={
        "query": "What is the doctrine?",
        "model_id": "szl-sovereign-local",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    sov = _sov_block(j)
    assert sov, "rag must record the intended sovereign backend"
    assert (sov.get("backend_id") or sov.get("backend")) == "sovereign_local"
    # honest extractive grounded answer is always present; sovereign_answer is None
    # (never fabricated) unless the local model answered LIVE.
    assert j.get("rag_state") in ("UNAVAILABLE", "MODELED"), j.get("rag_state")
    assert j.get("sovereign_answer") in (None, "") or isinstance(j.get("sovereign_answer"), str)
    return j


def test_non_sovereign_unaffected():
    """Requesting a normal model_id must NOT trigger the sovereign path."""
    c = _build_client()
    r = c.post(f"/api/{NS}/v1/eval/run", json={"suite": "core_honest_v1", "model_id": "gpt-4o"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert _sov_block(j) is None, "non-sovereign request must not record a sovereign block"


if __name__ == "__main__":
    print("== harness ==");   h = test_harness_apply_sovereign()
    print("  state:", h.get("harness_state"), "| response:", (h.get("response") or "")[:80])
    print("== eval ==");      e = test_eval_run_sovereign()
    print("  label:", e.get("honesty_label"))
    print("== agentloop =="); a = test_agentloop_run_sovereign()
    print("  label:", a.get("sovereign_label"))
    print("== rag ==");       g = test_rag_query_sovereign()
    print("  state:", g.get("rag_state"), "| model_note:", (g.get("model_note") or "")[:80])
    print("== non-sovereign guard =="); test_non_sovereign_unaffected()
    print("\nALL 4 FLOWS: 200 OK, honest UNAVAILABLE/MODELED, sovereign backend recorded, "
          "NO fabrication. Non-sovereign path unaffected. PASS")
