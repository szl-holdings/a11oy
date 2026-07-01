# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Cognitive drift guard: an additive, default-OFF governed-reasoning step that
scores current-step-intent vs stated-objective divergence (lexical Jaccard).

Honesty / additivity invariants asserted here:
  - OFF by default -> honest no-op {measured:false}, chain byte-identical to today
  - when A11OY_DRIFT_GUARD=1 it scores, folds a `drift_check` link INTO the hash
    chain, and the run still re-verifies (chain_intact stays true)
  - it NEVER alters the gate/kernel verdict (advisory only); score is a real
    lexical measurement, never fabricated
"""
import hashlib
import json

import szl_agentic_loop as L


def _fake_sign(payload: dict) -> dict:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"signed": True,
            "payloadType": "application/vnd.szl.receipt+json",
            "payload": hashlib.sha256(body).hexdigest(),
            "signatures": [{"sig": hashlib.sha256(b"k" + body).hexdigest()}]}


def _client():
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    app = Starlette()
    L.register(app, "a11oy", _fake_sign, signer_label="test in-image key")
    return TestClient(app)


def test_drift_off_by_default(monkeypatch):
    monkeypatch.delenv("A11OY_DRIFT_GUARD", raising=False)
    d = L.drift_check("deploy the reversible config change", "deploy config")
    assert d["measured"] is False
    assert d["score"] is None
    assert d["action"] == "none"


def test_drift_aligned_scores_low(monkeypatch):
    monkeypatch.setenv("A11OY_DRIFT_GUARD", "1")
    d = L.drift_check("deploy the reversible database migration",
                      "deploy reversible database migration")
    assert d["measured"] is True
    assert 0.0 <= d["score"] <= 1.0
    assert d["score"] < d["threshold"]
    assert d["action"] == "none"


def test_drift_diverged_flags_reflect(monkeypatch):
    monkeypatch.setenv("A11OY_DRIFT_GUARD", "1")
    d = L.drift_check("summarize the quarterly finance report",
                      "delete production kubernetes cluster")
    assert d["measured"] is True
    assert d["score"] >= d["threshold"]
    assert d["action"] == "reflect"


def test_drift_unscoreable_is_honest_noop(monkeypatch):
    monkeypatch.setenv("A11OY_DRIFT_GUARD", "1")
    d = L.drift_check("", "do something")
    assert d["measured"] is False
    assert d["score"] is None


def test_default_run_chain_unchanged_when_drift_off(monkeypatch):
    """Drift guard OFF (default) adds NO chain link: the six governed hops remain
    and the run re-verifies byte-identically to today."""
    monkeypatch.delenv("A11OY_DRIFT_GUARD", raising=False)
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run", json={"action": "x"}).json()
    assert run["drift"]["measured"] is False
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "drift_check" not in kinds
    assert kinds == ["retrieve", "quarantine_untrusted", "tool_call",
                     "policy_check", "kernel_check", "emit"]


def test_drift_enabled_folds_into_chain_and_verifies(monkeypatch):
    monkeypatch.setenv("A11OY_DRIFT_GUARD", "1")
    client = _client()
    # An action lexically unrelated to the query -> measurable drift.
    run = client.post("/api/a11oy/v1/agent/run",
                      json={"query": "summarize the finance report",
                            "action": "deploy reversible change", "severity": "low",
                            "confidence": 0.9, "reversible": True}).json()
    drift = run["drift"]
    assert drift["measured"] is True
    assert 0.0 <= drift["score"] <= 1.0
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "drift_check" in kinds
    # Folded into the SAME chain, before the emit seal, and still verifies.
    assert kinds.index("drift_check") < kinds.index("emit")
    # The advisory drift flag did NOT change the verdict: a low-severity,
    # high-confidence, reversible action is still ALLOWed.
    assert run["decision"] == "ALLOW"
    v = client.post("/api/a11oy/v1/agent/verify-chain", json={"run": run}).json()
    assert v["chain_intact"] is True
    assert v["chain_break_at_seq"] is None
