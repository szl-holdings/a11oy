"""Tests for the verifiable-ai core.

Crucially, the good-path tests run the honesty gate against the REAL a11oy PINN
artifacts (results.json / results_gpu.json), not toy fixtures — so the core is
proven against our own flagship output. The bad-path tests mutate that real
artifact into each overclaim shape and assert the gate catches it.
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from verifiable_ai import Claim, Label, honesty_gate  # noqa: E402

HERE = os.path.dirname(__file__)
PINN = os.path.join(HERE, "..", "..", "benchmarks", "pinn")
REAL = os.path.join(PINN, "results.json")
REAL_GPU = os.path.join(PINN, "results_gpu.json")


def _load(path):
    with open(path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------- Claim level
def test_measured_needs_value_and_evidence():
    assert not Claim("x", Label.MEASURED, value=1.0, evidence={"seeds": 3}).violations()
    assert Claim("x", Label.MEASURED, value=1.0).violations()  # no evidence
    assert Claim("x", Label.MEASURED, evidence={"seeds": 3}).violations()  # no value


def test_abstention_must_not_carry_value():
    assert not Claim("x", Label.NOT_RUN).violations()
    bad = Claim("x", Label.NOT_RUN, value=0.5).violations()
    assert bad and "fabrication" in bad[0]


def test_label_parse_tolerates_caveat():
    assert Label.parse("MEASURED (fit error vs synthetic ground truth)") is Label.MEASURED
    assert Label.parse("NOT-RUN") is Label.NOT_RUN
    with pytest.raises(ValueError):
        Label.parse("PROBABLY-FINE")


# ------------------------------------------------------------- Artifact gate
def test_real_artifact_passes():
    res = honesty_gate(_load(REAL))
    assert res.ok, res.violations
    assert res.arms_checked == 9  # 3 problems x 3 arms


@pytest.mark.skipif(
    not os.path.exists(REAL_GPU),
    reason="results_gpu.json is a local raw GPU artifact, not shipped to main",
)
def test_real_gpu_artifact_passes():
    assert honesty_gate(_load(REAL_GPU)).ok


def test_measured_arm_without_value_is_overclaim():
    art = _load(REAL)
    art["problems"][0]["arms"].append({"framework": "ghost", "label": "MEASURED"})
    res = honesty_gate(art)
    assert not res.ok and any("overclaim" in x for x in res.violations)


def test_notrun_arm_with_value_is_fabrication():
    art = _load(REAL)
    arm = art["problems"][0]["arms"][0]
    arm["label"] = "NOT-RUN"  # but it still carries its measured rel_l2
    res = honesty_gate(art)
    assert not res.ok and any("fabrication" in x for x in res.violations)


def test_unknown_label_is_rejected():
    art = _load(REAL)
    art["problems"][0]["arms"][0]["label"] = "PROBABLY-FINE"
    res = honesty_gate(art)
    assert not res.ok and any("unrecognized" in x for x in res.violations)


def test_overall_label_overclaim_is_caught():
    art = _load(REAL)
    # Honestly demote one framework's arms to NOT-RUN (stripping their measured
    # values) while overall_label still claims MEASURED 3-way -> the label lies.
    metric_keys = ("rel_l2_vs_exact", "abs_err", "wall_s", "energy", "alpha_estimate_median")
    for pb in art["problems"]:
        for arm in pb["arms"]:
            if arm.get("framework") == "modulus_physicsnemo":
                arm["label"] = "NOT-RUN"
                for k in metric_keys:
                    arm.pop(k, None)
    res = honesty_gate(art)
    assert not res.ok and any("overall_label claims" in x for x in res.violations)


def test_missing_honesty_disclosure_is_caught():
    art = _load(REAL)
    art["honesty"] = ""
    assert not honesty_gate(art).ok
