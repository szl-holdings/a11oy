# SPDX-License-Identifier: Apache-2.0
"""Receipt conservation is derived from the submitted decision and emitted node."""

from __future__ import annotations

from pathlib import Path

from szl_provenance import derive_receipt_conservation


ROOT = Path(__file__).resolve().parents[1]
DIGEST = "ab" * 32


def _submitted() -> dict:
    return {
        "schema": "szl.a11oy.policy_decision/v1",
        "op": "policy/evaluate",
        "action_id": "functest-decision-1",
        "severity": "critical",
        "decision": "deny",
        "gate": "thresholdPolicySeverity",
        "lambda_score": None,
    }


def _node(receipt: dict, digest: object = DIGEST) -> dict:
    return {"digest": digest, "receipt": receipt, "signed": False}


def test_matching_emit_conserves_and_labels_the_derivation() -> None:
    submitted = _submitted()
    result = derive_receipt_conservation(
        submitted, _node({**submitted, "space": "a11oy", "traceparent": "00-aa"})
    )
    assert result["receipts_in_eq_out"] is True
    assert result["receipts_in"] == 1
    assert result["receipts_out"] == 1
    assert result["measurement"] == "derived"
    assert result["receipts_in_eq_out_basis"] == (
        "derived_from_submitted_decision_and_emitted_node"
    )


def test_missing_or_malformed_digest_does_not_conserve() -> None:
    submitted = _submitted()
    for digest in ("", "AB" * 32, "ab" * 31, None, True, 1):
        result = derive_receipt_conservation(submitted, _node(submitted, digest))
        assert result["receipts_in_eq_out"] is False
        assert result["receipts_out"] == 0


def test_changed_decision_field_does_not_conserve() -> None:
    submitted = _submitted()
    stored = {**submitted, "decision": "allow"}
    result = derive_receipt_conservation(submitted, _node(stored))
    assert result["receipts_in_eq_out"] is False
    assert result["receipts_in"] == 1
    assert result["receipts_out"] == 0


def test_field_membership_rejects_a_missing_null_and_keeps_python_equality() -> None:
    """Missing keys are not stored nulls. True == 1 stays Python equality."""
    cases = (
        ({}, {"digest": None}, False),
        ({"digest": None}, {"digest": None}, True),
        ({"digest": "abc"}, {"digest": "abc"}, True),
        ({"digest": "abc"}, {"digest": "def"}, False),
        ({"digest": "abc"}, {"digest": "abc", "revision": None}, False),
        ({"digest": "abc", "revision": "r1"}, {"digest": "abc"}, True),
        ({"enabled": False, "count": 0}, {"enabled": False, "count": 0}, True),
        ({}, {}, True),
        ({"value": True}, {"value": 1}, True),
    )
    for stored, expected, want in cases:
        result = derive_receipt_conservation(expected, _node(stored))
        assert result["receipts_in"] == 1
        assert result["receipts_in_eq_out"] is want
        assert result["receipts_out"] == (1 if want else 0)


def test_policy_and_frontier_sources_do_not_assign_the_flag() -> None:
    serve = (ROOT / "serve.py").read_text(encoding="utf-8")
    frontier = (ROOT / "routers" / "gdw_frontier.py").read_text(encoding="utf-8")
    assert 'decision["receipts_in_eq_out"] = True' not in serve
    assert '"receipts_in_eq_out": True' not in frontier
