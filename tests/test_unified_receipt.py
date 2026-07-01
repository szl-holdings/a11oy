# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Unified per-turn receipt: the ONE receipt additively carries governed +
energy + (optional) multi-witness, and the hash chain stays intact.

Honesty invariants asserted here:
  - energy is labelled MEASURED / ROADMAP / UNAVAILABLE (never a fabricated joule)
  - multi-witness is OFF by default -> honest SKIPPED, chain byte-identical to today
  - when A11OY_MULTIWITNESS=1 the witness runs, is folded INTO the hash chain,
    and the run still re-verifies (chain_intact stays true)
"""
import hashlib
import json

import pytest

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


def test_energy_helper_is_honestly_labelled():
    e = L._energy_fields_for_receipt()
    assert e["energy_label"] in ("MEASURED", "ROADMAP", "UNAVAILABLE")
    # No fabricated joule: absent meter -> None, never a made-up number.
    if e["energy_label"] != "MEASURED":
        assert e.get("joules_consumed") is None


def test_multiwitness_off_by_default(monkeypatch):
    monkeypatch.delenv("A11OY_MULTIWITNESS", raising=False)
    c = L._multiwitness_fields("deadbeef", {"decision": "ALLOW"})
    assert c["consensus_status"] == "SKIPPED"


def test_run_carries_energy_and_consensus_and_verifies():
    client = _client()
    r = client.post("/api/a11oy/v1/agent/run",
                    json={"action": "deploy reversible change", "severity": "low",
                          "confidence": 0.9, "reversible": True})
    assert r.status_code == 200
    run = r.json()
    # Unified fields present and honestly labelled.
    assert run["energy"]["energy_label"] in ("MEASURED", "ROADMAP", "UNAVAILABLE")
    assert run["consensus"]["consensus_status"] in ("WITNESSED", "SKIPPED")
    # Same signed fields are inside the signed decision payload's chain, and the
    # run re-verifies end-to-end (chain intact + signature).
    v = client.post("/api/a11oy/v1/agent/verify-chain", json={"run": run})
    assert v.status_code == 200
    vr = v.json()
    assert vr["chain_intact"] is True
    assert vr["chain_break_at_seq"] is None


def test_default_run_chain_unchanged_depth():
    """Multi-witness OFF (default) adds NO chain link: the six governed hops
    (retrieve, quarantine, tool_call, policy_check, kernel_check, emit) remain."""
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run", json={"action": "x"}).json()
    assert run["consensus"]["consensus_status"] == "SKIPPED"
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "multiwitness" not in kinds
    assert kinds == ["retrieve", "quarantine_untrusted", "tool_call",
                     "policy_check", "kernel_check", "emit"]


def test_multiwitness_enabled_folds_into_chain(monkeypatch):
    monkeypatch.setenv("A11OY_MULTIWITNESS", "1")
    client = _client()
    run = client.post("/api/a11oy/v1/agent/run", json={"action": "x"}).json()
    cons = run["consensus"]
    if cons["consensus_status"] == "SKIPPED":
        pytest.skip("khipu consensus unavailable in this image — honest SKIPPED")
    assert cons["consensus_status"] == "WITNESSED"
    assert len(cons["consensus_receipt_hash"]) == 64
    kinds = [rec["kind"] for rec in run["receipt_chain"]]
    assert "multiwitness" in kinds
    # Folded into the SAME chain, before the emit seal, and still verifies.
    assert kinds.index("multiwitness") < kinds.index("emit")
    v = client.post("/api/a11oy/v1/agent/verify-chain", json={"run": run}).json()
    assert v["chain_intact"] is True
