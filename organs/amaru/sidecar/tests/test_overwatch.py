"""Tests for R0513 OVERWATCH panel."""

from __future__ import annotations

import math

import pytest

from amaru import overwatch
from amaru.chakana_wiring import wiring_snapshot
from amaru.receipts import ReceiptChain


def test_panel_has_six_innovations_with_reserved_slot():
    snap = overwatch.evaluate_panel()
    assert len(snap.invariants) == 6
    ids = [i.id for i in snap.invariants]
    assert ids == ["I1", "I2", "I3", "I4", "I5", "I6"]
    i4 = next(i for i in snap.invariants if i.id == "I4")
    assert i4.status == "reserved"


def test_panel_is_read_only_marker():
    snap = overwatch.evaluate_panel()
    assert snap.read_only is True
    assert snap.thesis_kernel_hash == "01f6c9b6"
    assert snap.thesis_brain_hash == "df4e9741"


def test_i1_kl_drift_pass_warn_trip():
    base = [0.5, 0.5]
    same = overwatch.invariant_i1_kl_drift(baseline=base, observed=base)
    assert same.status == "pass"
    skew = overwatch.invariant_i1_kl_drift(baseline=base, observed=[0.2, 0.8])
    assert skew.status in {"warn", "trip"}
    assert skew.value is not None and skew.value > 0


def test_i1_kl_vacuous_with_no_input():
    r = overwatch.invariant_i1_kl_drift(baseline=None, observed=None)
    assert r.status == "pass"


def test_kl_divergence_self_is_zero():
    assert overwatch.kl_divergence([0.4, 0.6], [0.4, 0.6]) == pytest.approx(0.0, abs=1e-9)


def test_i2_joint_margin_envelope():
    r = overwatch.invariant_i2_joint_margin({"a": 0.20, "b": 0.08, "c": 0.50})
    assert r.status == "pass"
    r2 = overwatch.invariant_i2_joint_margin({"a": 0.20, "b": 0.01})
    assert r2.status == "warn"
    r3 = overwatch.invariant_i2_joint_margin({"a": 0.20, "b": -0.01})
    assert r3.status == "trip"


def test_i3_tukuy_regate_ratio():
    assert overwatch.invariant_i3_tukuy_regate(in_flight=0, regated=0).status == "pass"
    assert overwatch.invariant_i3_tukuy_regate(in_flight=10, regated=1).status == "pass"
    assert overwatch.invariant_i3_tukuy_regate(in_flight=10, regated=4).status == "warn"
    assert overwatch.invariant_i3_tukuy_regate(in_flight=10, regated=8).status == "trip"


def test_i4_is_reserved_by_doctrine():
    r = overwatch.invariant_i4_reserved()
    assert r.status == "reserved"
    assert "doctrine" in r.detail.lower()


def test_i5_maxwell_rigidity_against_real_chakana():
    snap = wiring_snapshot()
    r = overwatch.invariant_i5_maxwell_rigidity(
        vertices=len(snap["chakras"]),
        edges=len(snap["edges"]),
    )
    # Real wiring is 7 vertices / 7 edges (ascent + ouroboros), not 21 —
    # so this should report deficit and trip. That's the honest reading.
    assert r.status == "trip"
    assert r.value == overwatch.CHAKANA_EDGES_REQUIRED - len(snap["edges"])


def test_i5_pass_at_doctrinal_21_edges():
    r = overwatch.invariant_i5_maxwell_rigidity(vertices=7, edges=21)
    assert r.status == "pass"
    assert r.value == 0


def test_i6_chain_integrity_on_real_receipt_chain():
    chain = ReceiptChain(operator_id="test-overwatch")
    chain.append(endpoint="/test/a", method="POST", params={"x": 1}, result={"ok": True})
    chain.append(endpoint="/test/b", method="POST", params={"x": 2}, result={"ok": True})
    chain.append(endpoint="/test/c", method="POST", params={"x": 3}, result={"ok": True})
    receipts = [r.to_dict() for r in chain.all()]
    r = overwatch.invariant_i6_chain_integrity(receipts)
    assert r.status == "pass"
    assert r.value == 0


def test_i6_chain_integrity_detects_break():
    chain = ReceiptChain(operator_id="test-overwatch-break")
    chain.append(endpoint="/a", method="POST", params={}, result={})
    chain.append(endpoint="/b", method="POST", params={}, result={})
    receipts = [r.to_dict() for r in chain.all()]
    # Tamper with the second receipt's prev_hash.
    receipts[1]["prev_hash"] = "f" * 64
    r = overwatch.invariant_i6_chain_integrity(receipts)
    assert r.status == "trip"
    assert r.value == 1


def test_i6_chain_integrity_empty_is_vacuous_pass():
    r = overwatch.invariant_i6_chain_integrity([])
    assert r.status == "pass"


def test_full_panel_with_real_chain_and_wiring():
    chain = ReceiptChain(operator_id="full-panel")
    chain.append(endpoint="/x", method="POST", params={}, result={"o": 1})
    snap = overwatch.evaluate_panel(
        receipts=[r.to_dict() for r in chain.all()],
        wiring=wiring_snapshot(),
        baseline_axes=[0.5, 0.5],
        observed_axes=[0.5, 0.5],
        margins={"a": 0.30, "b": 0.20},
        in_flight=4,
        regated=0,
    )
    d = snap.to_dict()
    assert d["read_only"] is True
    assert d["panel_version"] == "r0513.v1"
    # Summary counts add to 6.
    assert sum(d["summary"].values()) == 6


def test_overwatch_does_not_mutate_inputs():
    receipts = [
        {"seq": 1, "prev_hash": "0" * 64, "self_hash": "aa"},
        {"seq": 2, "prev_hash": "aa", "self_hash": "bb"},
    ]
    margins = {"a": 0.1, "b": 0.2}
    snap_before = (list(receipts), dict(margins))
    overwatch.evaluate_panel(
        receipts=receipts,
        margins=margins,
        baseline_axes=[0.5, 0.5],
        observed_axes=[0.4, 0.6],
    )
    assert receipts == snap_before[0]
    assert margins == snap_before[1]
