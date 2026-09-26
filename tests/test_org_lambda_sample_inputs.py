#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Default-constant Λ postures are SAMPLE, never a computed pass (audit S6)."""

import json
from pathlib import Path

import a11oy_grc_data as grc
import szl_org_lambda as org

ROOT = Path(__file__).resolve().parents[1]


def test_default_inputs_are_sample_with_null_pass():
    d = org.org_lambda()
    assert d["pass"] is None
    assert d["inputs"]["class"] == "SAMPLE"
    assert d["inputs"]["method"] is None
    assert d["inputs"]["measured_at"] is None
    assert d["inputs"]["n"] is None
    assert set(d["verticals_source"].values()) == {"DEFAULT_CONSTANT"}
    by_name = {a["name"]: a["source"] for a in d["axes"]}
    for name in ("calibration", "reversibility", "transparency", "fairness",
                 "containment", "authority"):
        assert by_name[name] == "DEFAULT_CONSTANT"
    assert "SUPPLIED" not in by_name.values()


def test_partial_supply_stays_sample():
    d = org.org_lambda(vertical_scores={"defense": 0.95})
    assert d["verticals_source"]["defense"] == "SUPPLIED"
    assert d["verticals_source"]["core"] == "DEFAULT_CONSTANT"
    assert d["pass"] is None
    assert d["inputs"]["class"] == "SAMPLE"


def test_fully_supplied_inputs_compute_pass():
    d = org.org_lambda(
        vertical_scores={k: 0.95 for k in org.DEFAULT_VERTICAL_POSTURES},
        axis_scores={n: 0.95 for n in org.ORG_AXIS_NAMES},
    )
    assert d["inputs"]["class"] == "SUPPLIED"
    assert d["pass"] is True
    low = org.org_lambda(
        vertical_scores={k: 0.5 for k in org.DEFAULT_VERTICAL_POSTURES},
        axis_scores={n: 0.5 for n in org.ORG_AXIS_NAMES},
    )
    assert low["pass"] is False


def test_overview_never_marks_default_vertical_as_pass():
    ov = org.org_overview()
    for row in ov["verticals"]:
        assert row["source"] == "DEFAULT_CONSTANT"
        assert row["status"] == "NOT MEASURED"


def test_landing_cards_render_na_for_default_constants():
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
    body = landing.split("function setVerticals(v, src){", 1)[1].split("\n  }\n", 1)[0]
    assert 'src[k] !== "SUPPLIED"' in body
    assert 'el.textContent = "N/A"' in body
    assert "NOT MEASURED · DEFAULT CONSTANT" in body
    assert "d.verticals_source" in landing
    assert "setVerticals({}, null);" in landing  # unreachable endpoint stays a down N/A


def test_grc_lambda_rows_are_partial_and_oscal_artifact_agrees():
    rows = {r["control"]: r for r in grc.COVERAGE_MATRIX}
    for control in ("A.5.4", "RA-3"):
        assert rows[control]["coverage"] == "PARTIAL"
        assert "per-inference risk assessment" not in rows[control]["mechanism"]
        # Every Λ source is named as what it is: none of them is a measurement.
        for source in ("keyword checks", "caller-declared", "0.97 default",
                       "SHA-256-derived", "0.97 minus", "regex", "severity",
                       "default constants"):
            assert source in rows[control]["mechanism"], (control, source)
    live = grc.build_oscal()["component-definition"]["components"][0][
        "control-implementations"][0]["implemented-requirements"]
    committed = json.loads(
        (ROOT / "compliance" / "oscal" / "a11oy-component-definition.json").read_text(encoding="utf-8")
    )["component-definition"]["components"][0]["control-implementations"][0]["implemented-requirements"]
    assert committed == live
