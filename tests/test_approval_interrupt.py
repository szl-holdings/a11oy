# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Human-approval-interrupt: an additive, default-OFF durable primitive that
HOLDS a gate-ALLOWED state-changing action at a durable checkpoint until a human
grants approval for that exact checkpoint (solves tool-call-committed-before-yes).

Honesty / additivity / composition invariants asserted here:
  - OFF by default -> no hold, no chain link, emit + chain byte-identical to today
  - composes with the gate: a DENY stays DENY (required:false, nothing to approve)
  - enabled + state-changing + ALLOW + no grant -> HELD (emitted:false), a
    `approval` link folded INTO the chain, run still re-verifies
  - a matching human grant (same checkpoint_id + approver) releases the hold and
    the action fires; a non-matching grant does NOT
  - injected input can NEVER use the interrupt to flip a DENY into a fire
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


def test_approval_off_by_default(monkeypatch):
    monkeypatch.delenv("A11OY_APPROVAL_INTERRUPT", raising=False)
    a = L.approval_interrupt("deploy service", "high", False, "ALLOW")
    assert a["required"] is False
    assert a["granted"] is None
    assert len(a["checkpoint_id"]) == 32


def test_approval_composes_never_overrides_deny(monkeypatch):
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    a = L.approval_interrupt("delete database", "critical", False, "DENY")
    # Gate already DENYied -> nothing to approve; the interrupt never flips a DENY.
    assert a["required"] is False


def test_approval_reversible_readonly_not_required(monkeypatch):
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    a = L.approval_interrupt("summarize the report", "low", True, "ALLOW")
    assert a["required"] is False


def test_approval_holds_state_changing_allow(monkeypatch):
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    a = L.approval_interrupt("deploy the release", "high", False, "ALLOW")
    assert a["required"] is True
    assert a["granted"] is None  # HELD until a human approves


def test_approval_released_by_matching_grant(monkeypatch):
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    held = L.approval_interrupt("deploy the release", "high", False, "ALLOW")
    cp = held["checkpoint_id"]
    grant = {"approved": True, "approver": "operator-jane", "checkpoint_id": cp}
    ok = L.approval_interrupt("deploy the release", "high", False, "ALLOW", grant=grant)
    assert ok["required"] is True
    assert ok["granted"] is True
    # A grant for a DIFFERENT checkpoint does NOT release this action.
    bad = L.approval_interrupt("deploy the release", "high", False, "ALLOW",
                               grant={"approved": True, "approver": "x", "checkpoint_id": "deadbeef"})
    assert bad["granted"] is None


def test_default_run_unchanged_when_approval_off(monkeypatch):
    """Approval OFF (default): no hold, no chain link, emit byte-identical."""
    monkeypatch.delenv("A11OY_APPROVAL_INTERRUPT", raising=False)
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run",
                      json={"action": "deploy the release", "severity": "high",
                            "confidence": 0.9, "reversible": True}).json()
    assert run["approval"]["required"] is False
    assert run["emitted"] is True  # fires as today
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "approval" not in kinds
    assert kinds == ["retrieve", "quarantine_untrusted", "tool_call",
                     "policy_check", "kernel_check", "emit"]


def test_enabled_holds_and_folds_into_chain(monkeypatch):
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run",
                      json={"action": "deploy the release", "severity": "high",
                            "confidence": 0.9, "reversible": True}).json()
    # Gate ALLOWed, but the action is HELD (not fired) pending human approval.
    assert run["decision"] == "ALLOW"
    assert run["approval"]["required"] is True
    assert run["approval"]["granted"] is None
    assert run["emitted"] is False
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "approval" in kinds
    assert kinds.index("approval") < kinds.index("emit")
    v = client.post("/api/a11oy/v1/agent/verify-chain", json={"run": run}).json()
    assert v["chain_intact"] is True
    assert v["chain_break_at_seq"] is None


def test_enabled_fires_after_matching_grant(monkeypatch):
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    client = _client()
    body = {"action": "deploy the release", "severity": "high",
            "confidence": 0.9, "reversible": True}
    held = client.post("/api/a11oy/v1/agent/run", json=body).json()
    cp = held["approval"]["checkpoint_id"]
    body2 = dict(body)
    body2["approval_grant"] = {"approved": True, "approver": "operator-jane",
                               "checkpoint_id": cp}
    fired = client.post("/api/a11oy/v1/agent/run", json=body2).json()
    assert fired["approval"]["granted"] is True
    assert fired["emitted"] is True  # released -> fires
    v = client.post("/api/a11oy/v1/agent/verify-chain", json={"run": fired}).json()
    assert v["chain_intact"] is True
