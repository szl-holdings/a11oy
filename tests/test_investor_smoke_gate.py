# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem).
"""Fail-closed unit tests for the investor smoke gate (no live HTTP).

S7 against live surfaces (kernel chips still bound to genome 25) lives in
test_investor_smoke_bind.py so this file can stay green while the bind is RED.
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


def test_s7_does_not_demand_genome_catalog_equal_eight():
    counts = gate.genome_catalog_counts(ROOT / "data" / "genome.json")
    assert counts["locked_proven_tags"] == 25
    assert counts["locked_proven_tags"] != gate.LOCKED_KERNEL_COUNT
    verdict = gate.s7_kernel_chip_bind(
        failures=[],
        catalog_locked_proven=25,
        honest_count=8,
    )
    assert verdict.status == "PASS"
    assert "catalog" in verdict.evidence


def test_s7_fails_if_live_honest_is_not_eight():
    verdict = gate.s7_kernel_chip_bind(failures=[], honest_count=7)
    assert verdict.status == "FAIL"


def test_bind_detector_records_genome_into_kernel_slot():
    text = (FIXTURES / "kernel_slot_genome_bind.html").read_text(encoding="utf-8")
    landing = gate.kernel_slot_bind_failures(
        text, source_name="fixture-genome", role="landing"
    )
    trust = gate.kernel_slot_bind_failures(
        text, source_name="fixture-genome", role="trust"
    )
    console = gate.kernel_slot_bind_failures(
        text, source_name="fixture-genome", role="console"
    )
    assert landing and trust and console
    blob = " ".join(landing + trust + console)
    assert "cnt-locked" in blob
    assert "loadLockedKernel" in blob or "pt-locked" in blob
    assert "LOCKED-PROVEN" in blob or "setTiers" in blob or "proof_tiers" in blob


def test_bind_detector_silent_when_kernel_chips_bind_honest():
    text = (FIXTURES / "kernel_slot_honest_bind.html").read_text(encoding="utf-8")
    for role in ("landing", "trust", "console"):
        failures = gate.kernel_slot_bind_failures(
            text, source_name="fixture-honest", role=role
        )
        assert failures == [], (role, failures)


def test_load_kernel_locked_alias_binds_landing_pt_locked():
    text = """
async function loadKernelLocked(){
  const h = await getJSON("/api/a11oy/v1/honest");
  const n = num(h && h.locked_formula_count);
  $("pt-locked").textContent = (n === null) ? "N/A" : n;
}
function setTiers(t){ $("pt-semantic").textContent = t.semantic; }
"""
    failures = gate.kernel_slot_bind_failures(
        text, source_name="fixture-1394-landing", role="landing"
    )
    assert failures == [], failures


def test_labelled_catalog_chip_is_not_the_kernel_slot():
    text = (FIXTURES / "kernel_slot_honest_bind.html").read_text(encoding="utf-8")
    assert "cnt-genome-locked-proven" in text
    assert "LOCKED-PROVEN" in text
    failures = gate.kernel_slot_bind_failures(
        text, source_name="fixture-honest", role="trust"
    )
    assert failures == []


def test_d5_labels_catalog_size_not_kernel_bind():
    counts = gate.genome_catalog_counts(ROOT / "data" / "genome.json")
    assert counts["entry_count"] == 144
    assert counts["locked_proven_tags"] == 25
    verdict = gate.evaluate_genome_vs_kernel(counts, kernel=gate.LOCKED_KERNEL_COUNT)
    assert verdict.status == "PASS"
    assert verdict.id == "D5"
    assert "S7" in verdict.detail
    assert "catalog" in verdict.detail.lower()


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


def test_unit_labeled_iss_coords_are_ok():
    payload = {
        "source": "Where-the-ISS-at",
        "mode": "live",
        "data": {
            "latitude": 27.4,
            "longitude": -91.3,
            "altitude": 417.7,
            "units": {"latitude": "degrees", "longitude": "degrees", "altitude": "km"},
        },
    }
    assert gate.unlabeled_numeric_coords(payload) == []


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
    assert gate.extract_signer_status({"signer": {"status": "ABSENT"}}) == "ABSENT"
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
