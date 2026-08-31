#!/usr/bin/env python3
"""tests/contract_tests.py — contract tests for the a11oy core.

Runnable two ways:
  python3 -m pytest tests/contract_tests.py -q      (if pytest is installed)
  python3 tests/contract_tests.py                   (plain runner, zero deps)

Every adversarial claim has a named test. Zero-Bandaid Law: the test IS
the claim — no doc paragraph without a test that survives it.
"""
from __future__ import annotations

import copy
import base64
import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11oy.policy_engine import TypedPolicyEngine, PolicyRule, execution_gate, most_restrictive
from a11oy.flight_recorder import SegmentedFlightRecorder
from a11oy.receipts import Signer, build_predicate, sign_envelope, HonestyViolation
from a11oy.verifier import OfflineVerifier
from a11oy.yaml_emit import scalar

KS = Path(tempfile.mkdtemp(prefix="a11oy-test-keys-"))
SIGNER = Signer(KS)
VERIFIER = OfflineVerifier(SIGNER)
HUMAN = {"id": "stephen.lutar", "role": "founder", "is_service_account": False}


def _env_for(action_type, side_effect, obligations, approval=None, outcome="ALLOW"):
    pred = build_predicate(
        action={"id": "t", "type": action_type, "side_effect_class": side_effect},
        actor={"id": "agent", "type": "agent", "is_service_account": True},
        authority={"outcome": outcome, "evaluated_before_execution": True},
        evidence={"completeness": "COMPLETE" if all(o["satisfied"] for o in obligations) else "INCOMPLETE",
                  "obligations": obligations},
        approval=approval,
    )
    return sign_envelope(pred, SIGNER)


# ---------------------------------------------------------------- tests ----

def test_default_deny_on_ungoverned_action():
    d = TypedPolicyEngine().evaluate("exfiltrate.dataset")
    assert d.outcome == "DENY", d.outcome
    assert d.deciding_rule is None


def test_first_match_wins_for_decision():
    rules = [PolicyRule("r1", ("merge.*",), "ALLOW", (), "WORKSPACE_WRITE"),
             PolicyRule("r2", ("merge.*",), "DENY", (), "WORKSPACE_WRITE")]
    d = TypedPolicyEngine(rules).evaluate("merge.pr", "WORKSPACE_WRITE")
    assert d.deciding_rule == "r1" and d.outcome == "ALLOW"


def test_obligations_accumulate_across_all_matches():
    rules = [PolicyRule("r1", ("merge.*",), "ALLOW", ("tests_pass",), "WORKSPACE_WRITE"),
             PolicyRule("r2", ("merge.*",), "ALLOW", ("ci_green",), "WORKSPACE_WRITE")]
    d = TypedPolicyEngine(rules).evaluate("merge.pr", "WORKSPACE_WRITE")
    assert set(d.obligations) == {"tests_pass", "ci_green"}, d.obligations


def test_most_restrictive_side_effect_wins():
    assert most_restrictive("READ_ONLY", "IRREVERSIBLE", "WORKSPACE_WRITE") == "IRREVERSIBLE"


def test_irreversible_allow_overridden_to_require_approval():
    rules = [PolicyRule("r1", ("deploy.*",), "ALLOW", (), "IRREVERSIBLE")]
    d = TypedPolicyEngine(rules).evaluate("deploy.prod", "IRREVERSIBLE")
    assert d.outcome == "REQUIRE_APPROVAL", d.outcome


def test_unknown_side_effect_class_treated_as_worst_case():
    assert most_restrictive("READ_ONLY", "NOT_A_REAL_CLASS") == "IRREVERSIBLE"


def test_service_account_cannot_claim_human():
    # Construction-level: build_predicate refuses a service-account principal.
    try:
        _env_for("deploy.prod", "IRREVERSIBLE", [],
                 approval={"principal": {"id": "svc-bot", "is_service_account": True}})
        raise AssertionError("build_predicate should have raised HonestyViolation")
    except HonestyViolation:
        pass
    # Verifier-level: an attacker who hand-crafts the envelope is still caught.
    evil = {"action": {"id": "x", "type": "deploy.prod", "side_effect_class": "IRREVERSIBLE"},
            "actor": {"id": "svc-bot", "is_service_account": True},
            "authority": {"outcome": "ALLOW", "evaluated_before_execution": True},
            "evidence": {"completeness": "COMPLETE", "obligations": []},
            "approval": {"principal": {"id": "svc-bot", "is_service_account": True}},
            "limitations": [], "context": {},
            "timestamp": {"utc": "2026-08-31T00:00:00+00:00", "ntp_synced": None}}
    env = sign_envelope(evil, SIGNER)
    v = VERIFIER.verify(env)
    assert v.status == "FAIL_POLICY", v.status


def test_irreversible_without_approval_fails_policy():
    env = _env_for("deploy.prod", "IRREVERSIBLE", [], approval=None, outcome="ALLOW")
    v = VERIFIER.verify(env)
    assert v.status == "FAIL_POLICY", v.status


def test_tampered_payload_fails_signature():
    env = _env_for("merge.pr", "WORKSPACE_WRITE",
                   [{"id": "tests_pass", "satisfied": True},
                    {"id": "diff_bounded", "satisfied": True},
                    {"id": "security_scan_clean", "satisfied": True}],
                   approval={"principal": HUMAN})
    raw = bytearray(base64.b64decode(env["payload"]))
    raw[len(raw) // 2] ^= 0x01
    env2 = copy.deepcopy(env)
    env2["payload"] = base64.b64encode(bytes(raw)).decode()
    v = VERIFIER.verify(env2)
    assert v.status == "FAIL_SIGNATURE", v.status


def test_missing_evidence_is_incomplete_never_pass():
    env = _env_for("merge.pr", "WORKSPACE_WRITE",
                   [{"id": "tests_pass", "satisfied": False},
                    {"id": "diff_bounded", "satisfied": True},
                    {"id": "security_scan_clean", "satisfied": True}],
                   approval={"principal": HUMAN})
    v = VERIFIER.verify(env)
    assert v.status == "INCOMPLETE", v.status
    assert not v.ok


def test_complete_with_unsatisfied_obligation_raises():
    try:
        build_predicate(
            action={"id": "t", "type": "merge.pr", "side_effect_class": "WORKSPACE_WRITE"},
            actor={"id": "a"}, authority={"outcome": "ALLOW", "evaluated_before_execution": True},
            evidence={"completeness": "COMPLETE",
                      "obligations": [{"id": "tests_pass", "satisfied": False}]},
        )
        raise AssertionError("should have raised HonestyViolation")
    except HonestyViolation:
        pass


def test_posthoc_authority_raises():
    try:
        build_predicate(
            action={"id": "t", "type": "merge.pr", "side_effect_class": "READ_ONLY"},
            actor={"id": "a"}, authority={"outcome": "ALLOW", "evaluated_before_execution": False},
            evidence={"completeness": "COMPLETE", "obligations": []},
        )
        raise AssertionError("post-hoc logs are not governance")
    except HonestyViolation:
        pass


def test_flight_recorder_integrity_and_chain():
    p = Path(tempfile.mkdtemp()) / "seg.fr"
    fr = SegmentedFlightRecorder(p)
    fr.append({"a": 1}, idempotency_key="k1")
    fr.append({"a": 2}, upstream_ack=True, idempotency_key="k2")
    integ = fr.verify_integrity()
    assert integ["ok"] and integ["records"] == 2 and integ["chain_ok"], integ
    assert integ["pending_sync"] == [1], integ


def test_flight_recorder_idempotency_no_duplicate():
    p = Path(tempfile.mkdtemp()) / "seg.fr"
    fr = SegmentedFlightRecorder(p)
    fr.append({"action": "merge"}, idempotency_key="idem-1")
    assert fr.find_by_idempotency_key("idem-1") is not None
    assert fr.find_by_idempotency_key("idem-absent") is None


def test_flight_recorder_detects_truncated_tail():
    p = Path(tempfile.mkdtemp()) / "seg.fr"
    fr = SegmentedFlightRecorder(p)
    fr.append({"a": 1}, idempotency_key="k1")
    fr.append({"a": 2}, idempotency_key="k2")
    with open(p, "r+b") as f:
        f.truncate(p.stat().st_size - 7)   # simulate crash mid-write
    integ = fr.verify_integrity()
    assert not integ["ok"] and integ["corruptions"], integ


def test_execution_gate_refuses_unapproved_irreversible():
    d = TypedPolicyEngine().evaluate("merge.pr", "IRREVERSIBLE")
    gate, _ = execution_gate(d, approval=None)
    assert gate == "REFUSE"
    gate2, _ = execution_gate(d, approval={"principal": {"id": "svc", "is_service_account": True}})
    assert gate2 == "REFUSE"


def test_yaml_emit_unknown_for_none():
    assert scalar(None) == "UNKNOWN"
    assert scalar(True) == "true"
    assert scalar("plain") == "plain"


def test_article12_profile_exists_with_180_day_floor():
    import yaml
    prof = yaml.safe_load((ROOT / "conformance" / "ARTICLE12_PROFILE.yaml").read_text())
    assert prof["retention_minimum_days"] >= 180
    assert any(f["id"] == "A12-04" for f in prof["fields"])  # natural-person verification


# ---------------------------------------------------------------- runner ---

def _all_tests():
    return [(n, f) for n, f in sorted(globals().items())
            if n.startswith("test_") and callable(f)]


def main() -> int:
    tests = _all_tests()
    passed, failed = 0, []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception:
            failed.append(name)
            print(f"  FAIL  {name}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} contract tests passed")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
