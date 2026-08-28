# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""Fail-closed unit tests for the investor smoke gate (no live HTTP).

S7 against live genome.json (25 vs 8) lives in test_investor_smoke_bind.py so
this file can stay green while INTI's count is still RED.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import investor_smoke_gate as gate  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "investor_smoke"


def test_skip_as_green_is_rejected():
    empty = gate.Matrix()
    errors = gate.validate_matrix(empty, required=("S7", "S1"))
    assert any("missing probe S7" in err for err in errors)
    assert any("missing probe S1" in err for err in errors)
    assert any("skip-as-green" in err for err in errors)


def test_snapshot_without_date_is_rejected():
    with pytest.raises(ValueError, match="SNAPSHOT requires a date"):
        gate.Verdict(id="L1", status="SNAPSHOT", detail="stress", evidence="none")


def test_snapshot_with_date_is_accepted():
    item = gate.Verdict(
        id="L1",
        status="SNAPSHOT",
        detail="not run",
        evidence="SNAPSHOT 2026-08-28",
        snapshot_date="2026-08-28",
    )
    matrix = gate.Matrix()
    matrix.add(item)
    errors = gate.validate_matrix(matrix, required=("L1",))
    assert errors == []


def test_unavailable_only_for_listed_ids():
    matrix = gate.Matrix()
    matrix.add(
        gate.Verdict(id="S1", status="UNAVAILABLE", detail="network", evidence="none")
    )
    errors = gate.validate_matrix(matrix, required=("S1",))
    assert any("UNAVAILABLE not allowed" in err for err in errors)


def test_s4_s6_s9_unavailable_is_honest():
    matrix = gate.Matrix()
    for item in gate.unavailable_placeholders():
        matrix.add(item)
    errors = gate.validate_matrix(matrix, required=("S4", "S6", "S9"))
    assert errors == []


def test_post_is_forbidden():
    with pytest.raises(ValueError, match="forbids POST"):
        gate.http_request("https://example.invalid/", method="POST")


def test_s7_equality_fails_when_genome_is_25():
    verdict = gate.s7_count_agreement(25, 8)
    assert verdict.status == "FAIL"
    assert verdict.owner == "INTI"
    assert "LOCKED-PROVEN=25" in verdict.evidence


def test_s7_equality_passes_when_counts_agree_at_eight():
    verdict = gate.s7_count_agreement(8, 8)
    assert verdict.status == "PASS"


def test_s7_fails_if_honest_is_not_eight():
    verdict = gate.s7_count_agreement(8, 7)
    assert verdict.status == "FAIL"


def test_bind_detector_records_genome_into_kernel_slot():
    text = (FIXTURES / "kernel_slot_genome_bind.html").read_text(encoding="utf-8")
    failures = gate.kernel_slot_bind_failures(text, source_name="fixture-genome")
    assert failures
    blob = " ".join(failures)
    assert "cnt-locked" in blob
    assert "setTiers.locked" in blob or "LOCKED-PROVEN" in blob


def test_bind_detector_silent_when_kernel_slot_not_genome():
    text = (FIXTURES / "kernel_slot_honest_bind.html").read_text(encoding="utf-8")
    failures = gate.kernel_slot_bind_failures(text, source_name="fixture-honest")
    assert failures == []


def test_d5_labels_catalog_size_not_tag_agreement():
    counts = gate.genome_catalog_counts(ROOT / "data" / "genome.json")
    assert counts["entry_count"] == 144
    verdict = gate.evaluate_genome_vs_kernel(counts, kernel=gate.LOCKED_KERNEL_COUNT)
    assert verdict.status == "PASS"
    assert verdict.id == "D5"
    assert "S7" in verdict.detail


def test_s12_readme_yaml_parses():
    verdict = gate.s12_verdict(ROOT)
    assert verdict.status == "PASS", verdict.detail


def test_l_rows_are_snapshot_2026_08_28():
    rows = {item.id: item for item in gate.snapshot_l_verdicts()}
    assert set(rows) == set(gate.SNAPSHOT_IDS)
    for item in rows.values():
        assert item.status == "SNAPSHOT"
        assert item.snapshot_date == "2026-08-28"


def test_unlabeled_iss_coords_are_red():
    payload = {
        "source": "Where-the-ISS-at",
        "mode": "live",
        "data": {"latitude": 27.4, "longitude": -91.3, "altitude": 417.7},
    }
    hits = gate.unlabeled_numeric_coords(payload)
    assert hits, "bare ISS digits must be unlabeled FAIL"


def test_measured_without_method_is_not_enough():
    payload = {
        "data": {"latitude": {"value": 27.4, "label": "MEASURED"}},
    }
    assert gate.unlabeled_numeric_coords(payload), "MEASURED without method is unlabeled"


def test_measured_with_method_and_unavailable_are_ok():
    measured = {
        "data": {
            "latitude": {"value": 27.4, "label": "MEASURED", "method": "where-the-iss-at"},
            "longitude": {"value": -91.3, "label": "MEASURED", "method": "where-the-iss-at"},
        },
    }
    assert gate.unlabeled_numeric_coords(measured) == []
    unavailable = {
        "data": {"latitude": {"value": None, "label": "UNAVAILABLE"}},
    }
    # no numeric coord — also a numeric UNAVAILABLE:
    unavailable_num = {
        "data": {"latitude": {"value": 0.0, "label": "UNAVAILABLE"}},
    }
    assert gate.unlabeled_numeric_coords(unavailable) == []
    assert gate.unlabeled_numeric_coords(unavailable_num) == []


def test_first_viewport_rejects_bare_latitude():
    html = "<section id='hero'><p>latitude 27.3999 longitude -91.32</p></section>"
    hits = gate.first_viewport_unlabeled_latitude(html)
    assert hits
    labelled = (
        "<section id='hero'><p>latitude UNAVAILABLE</p></section>"
    )
    assert gate.first_viewport_unlabeled_latitude(labelled) == []
    measured = (
        "<section id='hero'><p>latitude 27.4 MEASURED method=where-the-iss-at</p></section>"
    )
    assert gate.first_viewport_unlabeled_latitude(measured) == []


def test_landing_first_viewport_has_no_raw_latitude():
    html = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    assert gate.first_viewport_unlabeled_latitude(html) == []


def test_signer_enum_extract():
    assert (
        gate.extract_signer_status({"rollup": {"signer": {"status": "DSSE-LIVE"}}})
        == "DSSE-LIVE"
    )
    assert gate.extract_signer_status({"lean_sha": "c7c0ba17", "status": "ok"}) is None


def test_locked_formula_count_nested_or_top_level():
    assert gate.locked_formula_count_from_honest({"locked_formula_count": 8}) == 8
    assert (
        gate.locked_formula_count_from_honest({"doctrine_lock": {"locked_formula_count": 8}})
        == 8
    )
    assert gate.locked_formula_count_from_honest({"kernel_commit": "c7c0ba17"}) is None


def test_static_debug_rows_are_honest():
    rows = {item.id: item for item in gate.static_debug_verdicts(ROOT)}
    for key in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"):
        assert rows[key].status == "PASS", (key, rows[key].detail, rows[key].evidence)
    assert rows["D10"].status == "SNAPSHOT"
    assert rows["wire-D"].status == "UNCONFIGURED"
