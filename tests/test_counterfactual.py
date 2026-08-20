# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Counterfactual check: an additive, default-OFF governed-reasoning step that,
before finalizing a HIGH-CONSEQUENCE decision, asks a wired reasoning brain
"what would make this wrong?" and folds the reply into the VERIFY receipt.

Honesty / additivity invariants asserted here:
  - OFF by default -> honest no-op {ran:false}, chain byte-identical to today
  - no real brain wired -> honest {ran:false} (NEVER fabricates a counterfactual;
    the in-image szl_brain.route stub is intentionally NOT used)
  - low/medium reversible action -> not high-consequence -> {ran:false}
  - when enabled + high-consequence + a real brain is injected, it runs, folds a
    `counterfactual` link INTO the hash chain, the verdict is unchanged, and the
    run still re-verifies (chain_intact stays true)
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


def test_counterfactual_off_by_default(monkeypatch):
    monkeypatch.delenv("A11OY_COUNTERFACTUAL", raising=False)
    c = L.counterfactual_check("delete prod database", "critical", 0.9, False, "DENY")
    assert c["ran"] is False
    assert c["note"] is None


def test_counterfactual_no_brain_is_honest_noop(monkeypatch):
    monkeypatch.setenv("A11OY_COUNTERFACTUAL", "1")
    monkeypatch.setattr(L, "_CF_GENERATOR", None, raising=False)
    c = L.counterfactual_check("delete prod database", "critical", 0.9, False, "DENY")
    # High-consequence + enabled, but no real brain -> honest no-op, never faked.
    assert c["ran"] is False
    assert c["note"] is None
    assert "brain" in c["reason"].lower()


def test_counterfactual_low_consequence_skipped(monkeypatch):
    monkeypatch.setenv("A11OY_COUNTERFACTUAL", "1")
    monkeypatch.setattr(L, "_CF_GENERATOR", lambda p: "fake", raising=False)
    c = L.counterfactual_check("tweak a label", "low", 0.9, True, "ALLOW")
    assert c["ran"] is False
    assert "not high-consequence" in c["reason"]


def test_counterfactual_runs_with_wired_brain(monkeypatch):
    monkeypatch.setenv("A11OY_COUNTERFACTUAL", "1")
    seen = {}

    def _brain(prompt):
        seen["prompt"] = prompt
        return "If the track were mis-identified the engage would be wrong; detect via a second sensor."

    monkeypatch.setattr(L, "_CF_GENERATOR", _brain, raising=False)
    c = L.counterfactual_check("engage the track", "critical", 0.9, False, "ALLOW")
    assert c["ran"] is True
    assert c["note"] and "mis-identified" in c["note"]
    # The brain was asked a real "what would make this wrong" question.
    assert "opposite were true" in seen["prompt"]


def test_default_run_chain_unchanged_when_counterfactual_off(monkeypatch):
    """Counterfactual OFF (default) adds NO chain link: the six governed hops
    remain and the run re-verifies byte-identically to today."""
    monkeypatch.delenv("A11OY_COUNTERFACTUAL", raising=False)
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run",
                      json={"action": "engage the track", "severity": "critical",
                            "confidence": 0.9, "reversible": False}).json()
    assert run["counterfactual"]["ran"] is False
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "counterfactual" not in kinds
    assert kinds == ["retrieve", "quarantine_untrusted", "tool_call",
                     "policy_check", "kernel_check", "emit"]


def test_counterfactual_enabled_folds_into_chain_and_verifies(monkeypatch):
    monkeypatch.setenv("A11OY_COUNTERFACTUAL", "1")
    monkeypatch.setattr(L, "_CF_GENERATOR",
                        lambda p: "A single mis-identification would make this wrong.",
                        raising=False)
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run",
                      json={"query": "engage the hostile track",
                            "action": "engage the hostile track", "severity": "critical",
                            "confidence": 0.9, "reversible": False}).json()
    cf = run["counterfactual"]
    assert cf["ran"] is True
    assert cf["note"]
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "counterfactual" in kinds
    # Folded into the SAME chain, before the emit seal, and still verifies.
    assert kinds.index("counterfactual") < kinds.index("emit")
    v = client.post("/api/a11oy/v1/agent/verify-chain", json={"run": run}).json()
    assert v["chain_intact"] is True
    assert v["chain_break_at_seq"] is None
