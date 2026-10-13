#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed checks for the R09 materials retrospective/OOD evaluator.

Every fixture here is synthetic (data_origin "sample" unless a test needs a
non-sample path).  These are software checks of evaluator arithmetic and
contracts; no model is fit and no benchmark is run.  Stdlib + pytest only.
"""

import ast
import copy
import hashlib
import math
import pathlib

import pytest

import szl_materials_eval as ev

ROOT = pathlib.Path(__file__).resolve().parents[1]
UNIT = "eV/atom"


def _rec(rid, group, split, y_true, y_pred, composition=None, **extra):
    rec = {
        "id": rid,
        "group": group,
        "split": split,
        "y_true": y_true,
        "y_pred": y_pred,
        "unit": UNIT,
        "data_origin": "sample",
        "functional": None,
    }
    if composition is not None:
        rec["composition"] = composition
    rec.update(extra)
    return rec


def _records():
    # Binary-exact values so MAE and the confusion matrix are exact.
    return [
        _rec("tr-1", "Fe-O", "train", 0.0, 0.125, "Fe2O3"),
        _rec("tr-2", "Fe-O", "train", 0.25, 0.25, "Fe3O4"),
        _rec("tr-3", "Mn-O", "train", 0.5, None, "MnO2"),
        _rec("ca-1", "Ti-O", "calibration", 0.125, 0.25, "TiO2"),
        _rec("te-1", "Al-N", "test", -0.25, -0.125, "AlN"),  # TP, |e| 0.125
        _rec("te-2", "Al-N", "test", 0.5, -0.25, "Al2N3"),  # FP, |e| 0.75
        _rec("te-3", "Ga-N", "test", 0.0, 0.25, "GaN"),  # FN, |e| 0.25
        _rec("te-4", "Ga-N", "test", 0.75, 0.5, "Ga2N"),  # TN, |e| 0.25
    ]


def _task(**discovery):
    task = {"task_id": "synthetic-ehull-r09", "unit": UNIT, "target": "e_above_hull"}
    task["discovery"] = {"threshold": 0.0, "missing_policy": "count_as_unstable", **discovery}
    return task


def _digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _provenance(**overrides):
    prov = {
        "task_sha256": _digest("synthetic task contract"),
        "split_sha256": _digest("synthetic split manifest"),
        "hull_sha256": _digest("synthetic convex hull"),
        "model_sha256": _digest("synthetic model"),
        "checkpoint_sha256": _digest("synthetic checkpoint"),
        "data_license": "CC-BY-4.0",
        "code_license": "Apache-2.0",
        "checkpoint_license": "Apache-2.0",
        "training_overlap": "none",
    }
    prov.update(overrides)
    return prov


def _bundle(records=None, provenance=None, **extra):
    bundle = {
        "task": _task(),
        "records": _records() if records is None else records,
        "provenance": _provenance() if provenance is None else provenance,
    }
    bundle.update(extra)
    return bundle


def _as_dft(records):
    for rec in records:
        rec["data_origin"] = "dft"
        rec["functional"] = "PBE"
    return records


# --- validation ------------------------------------------------------------


def test_clean_fixture_validates():
    report = ev.validate_records(_records(), _task())
    assert report == {"ok": True, "errors": [], "n_records": 8}


@pytest.mark.parametrize(
    "field,value",
    [
        ("y_true", float("nan")),
        ("y_true", float("inf")),
        ("y_true", float("-inf")),
        ("y_true", True),
        ("y_true", 10**400),
        ("y_true", "0.5"),
        ("y_true", None),
        ("y_true", 2**53 + 1),
        ("y_pred", float("nan")),
        ("y_pred", float("inf")),
        ("y_pred", False),
        ("y_pred", -(2**53) - 1),
    ],
)
def test_nan_inf_and_bool_are_rejected(field, value):
    records = _records()
    records[4][field] = value
    report = ev.validate_records(records, _task())
    assert report["ok"] is False
    assert any(f".{field} must be" in e and "te-1" in e for e in report["errors"])
    with pytest.raises(ev.RecordValidationError):
        ev.regression_metrics(records, _task())
    result = ev.evaluate(_bundle(records))
    assert result["status"] == "BLOCKED"
    assert result["regression"] is None and result["discovery"] is None


def test_integers_up_to_two_to_the_53_are_accepted_and_bound_exactly():
    # The digest is built from float(value); beyond 2**53 an int has no exact
    # float, so digest and metrics could bind different values.
    records = _as_dft(_records())
    records[4].update(y_true=2**53, y_pred=-(2**53))
    assert ev.validate_records(records, _task())["ok"] is True
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "SAMPLE"
    moved = _as_dft(_records())
    moved[4].update(y_true=2**53, y_pred=-(2**53) + 2)
    assert ev.evaluate(_bundle(records=moved))["records_sha256"] != result["records_sha256"]


def test_unit_mismatch_against_task_contract_is_rejected():
    records = _records()
    records[5]["unit"] = "meV/atom"
    report = ev.validate_records(records, _task())
    assert report["ok"] is False
    assert any("does not match the task contract unit" in e for e in report["errors"])
    assert any("records mix units" in e for e in report["errors"])
    assert ev.evaluate(_bundle(records))["status"] == "BLOCKED"


def test_mixed_units_rejected_without_a_task():
    records = _records()
    records[0]["unit"] = "eV"
    report = ev.validate_records(records)
    assert report["ok"] is False
    assert any("records mix units" in e for e in report["errors"])


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda r: r.update(split="validation"), ".split must be one of"),
        (lambda r: r.update(group=""), ".group must be a non-empty string"),
        (lambda r: r.update(id=7), ".id must be a non-empty string"),
        (lambda r: r.update(data_origin="DFT"), ".data_origin must be one of"),
        (lambda r: r.update(data_origin="dft"), ".functional is required for a DFT label"),
        (lambda r: r.pop("y_pred"), ".y_pred must be present"),
        (lambda r: r.pop("functional"), ".functional must be present"),
        (lambda r: r.update(composition="fe2o3"), "is not a simple formula"),
        (lambda r: r.update(composition="Fe0O1"), "non-positive count"),
        (lambda r: r.update(material_id=""), ".material_id must be null"),
        (lambda r: r.update(id="te-3 "), ".id must not start or end with whitespace"),
        (lambda r: r.update(group=" Ga-N"), ".group must not start or end with whitespace"),
        (
            lambda r: r.update(material_id="mp-1\t"),
            ".material_id must not start or end with whitespace",
        ),
    ],
)
def test_record_contract_violations_are_named(mutate, needle):
    records = _records()
    mutate(records[6])
    report = ev.validate_records(records, _task())
    assert report["ok"] is False
    assert any(needle in e for e in report["errors"]), report["errors"]


def test_task_contract_violations_block_evaluation():
    bad = _bundle()
    bad["task"]["unit"] = "eV"
    for rec in bad["records"]:
        rec["unit"] = "eV"
    result = ev.evaluate(bad)
    assert result["status"] == "BLOCKED"
    assert any("task.discovery requires task.unit" in e for e in result["validation"]["errors"])
    bad = _bundle()
    bad["task"]["discovery"]["missing_policy"] = "drop"
    assert ev.evaluate(bad)["status"] == "BLOCKED"
    for threshold in (True, 2**53 + 1, -(2**53) - 1):
        bad = _bundle()
        bad["task"]["discovery"]["threshold"] = threshold
        result = ev.evaluate(bad)
        assert result["status"] == "BLOCKED"
        # Refused by the task contract, not only later by discovery_metrics.
        assert any(
            "task.discovery.threshold must be a finite real number" in e
            for e in result["validation"]["errors"]
        ), threshold


def test_discovery_on_a_non_hull_target_is_blocked():
    # Formation energy shares the eV/atom unit; stability needs the hull.
    bad = _bundle(records=_as_dft(_records()))
    bad["task"]["target"] = "formation_energy_per_atom"
    result = ev.evaluate(bad)
    assert result["status"] == "BLOCKED"
    assert result["discovery"] is None
    assert any("task.discovery requires task.target" in e for e in result["validation"]["errors"])


@pytest.mark.parametrize("bundle", [None, [], "x", {"records": "x"}, {"task": _task()}])
def test_evaluate_never_raises_on_garbage(bundle):
    result = ev.evaluate(bundle)
    assert result["status"] == "BLOCKED"
    assert result["validation"]["ok"] is False


# --- leakage ---------------------------------------------------------------


def test_clean_fixture_has_no_detected_leakage():
    report = ev.check_leakage(_records())
    assert report["status"] == "NO_LEAKAGE_DETECTED"
    assert report["splits_present"] == ["train", "calibration", "test"]
    assert report["cross_split_check"] == "RUN"
    assert report["composition_check"] == "RUN"
    assert report["material_check"] == "NOT_RUN"
    assert report["records_without_material_id"] == 8
    assert report["group_overlap"] == []
    assert report["duplicate_ids"] == []
    assert report["material_overlap"] == []
    assert report["composition_overlap"] == []
    notes = ev.evaluate(_bundle())["notes"]
    assert "material_id overlap check NOT_RUN: 8 record(s) carry no material_id" in notes


def _dft_records_in(*splits):
    return [r for r in _as_dft(_records()) if r["split"] in splits]


_NO_TRAIN_REASON = (
    "split leakage not observable: no ['train'] records, so train and test were not compared"
)


def test_test_only_bundle_cannot_observe_leakage_and_is_unknown():
    records = _dft_records_in("test")
    report = ev.check_leakage(records)
    assert report["status"] == "UNKNOWN"
    assert report["splits_present"] == ["test"]
    assert report["cross_split_check"] == "NOT_RUN"
    assert report["group_overlap"] == [] and report["composition_overlap"] == []
    # Nothing to compare against, so the field checks did not run either.
    assert report["composition_check"] == "NOT_RUN"
    assert report["material_check"] == "NOT_RUN"
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "UNKNOWN"
    assert result["leakage"]["status"] == "UNKNOWN"
    assert result["reasons"] == [_NO_TRAIN_REASON]
    assert result["notes"] == [
        "cross-split leakage check NOT_RUN: splits supplied ['test'], so group, "
        "material_id and composition overlap between train and test is not observable"
    ]
    # The metrics are still reported; the status says what could not be seen.
    assert result["regression"]["mae"] == 0.34375
    assert result["held_out_label"] == "held-out"


def test_calibration_and_test_without_train_is_partial_and_unknown():
    records = _dft_records_in("calibration", "test")
    report = ev.check_leakage(records)
    assert report["status"] == "UNKNOWN"
    assert report["splits_present"] == ["calibration", "test"]
    assert report["cross_split_check"] == "PARTIAL"
    assert report["composition_check"] == "RUN"
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "UNKNOWN"
    assert result["reasons"] == [_NO_TRAIN_REASON]
    assert any(n.startswith("cross-split leakage check PARTIAL") for n in result["notes"])
    # The splits that are present are still compared against each other.
    records.append(_rec("te-5", "Ti-O", "test", 0.0, 0.0, "TiO2"))
    leaked = ev.check_leakage(records)
    assert leaked["status"] == "LEAKAGE"
    assert leaked["group_overlap"] == [{"group": "Ti-O", "splits": ["calibration", "test"]}]
    assert ev.evaluate(_bundle(records=records))["status"] == "BLOCKED"


def test_train_and_test_without_calibration_is_a_full_cross_split_check():
    records = _dft_records_in("train", "test")
    report = ev.check_leakage(records)
    assert report["cross_split_check"] == "RUN"
    assert report["status"] == "NO_LEAKAGE_DETECTED"
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "SAMPLE"
    assert not any(n.startswith("cross-split leakage check") for n in result["notes"])


def test_train_only_and_empty_bundles_are_unknown_not_clean():
    records = _dft_records_in("train")
    assert ev.check_leakage(records)["status"] == "UNKNOWN"
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "UNKNOWN"
    assert (
        "split leakage not observable: no ['test'] records, so train and test were not compared"
        in result["reasons"]
    )
    empty = ev.check_leakage([])
    assert empty["status"] == "UNKNOWN" and empty["cross_split_check"] == "NOT_RUN"


def test_single_split_still_reports_duplicate_ids_as_leakage():
    records = _dft_records_in("test")
    records.append(dict(records[0]))
    report = ev.check_leakage(records)
    assert report["cross_split_check"] == "NOT_RUN"
    assert report["status"] == "LEAKAGE" and report["duplicate_ids"] == ["te-1"]
    assert ev.evaluate(_bundle(records=records))["status"] == "BLOCKED"


def test_group_leakage_across_splits_blocks_and_withholds_metrics():
    records = _records()
    records.append(_rec("te-5", "Fe-O", "test", 0.0, 0.0, "FeO"))
    report = ev.check_leakage(records)
    assert report["status"] == "LEAKAGE"
    assert report["group_overlap"] == [{"group": "Fe-O", "splits": ["train", "test"]}]
    result = ev.evaluate(_bundle(records))
    assert result["status"] == "BLOCKED"
    assert "split leakage detected; metrics withheld" in result["reasons"]
    assert result["regression"] is None and result["discovery"] is None
    assert result["held_out_label"] is None


def test_group_shared_by_train_and_calibration_only_is_leakage():
    records = _records()
    records.append(_rec("ca-2", "Fe-O", "calibration", 0.0, 0.0, "FeO"))
    report = ev.check_leakage(records)
    assert report["status"] == "LEAKAGE"
    assert report["group_overlap"] == [{"group": "Fe-O", "splits": ["train", "calibration"]}]
    result = ev.evaluate(_bundle(records))
    assert result["status"] == "BLOCKED"
    assert result["regression"] is None


def test_group_case_variant_across_splits_is_leakage():
    records = _records()
    records.append(_rec("te-5", "fe-o", "test", 0.0, 0.0, "FeO"))
    report = ev.check_leakage(records)
    assert report["status"] == "LEAKAGE"
    assert report["group_overlap"] == [
        {"group": "Fe-O", "splits": ["train", "test"], "spellings": ["Fe-O", "fe-o"]}
    ]
    assert ev.evaluate(_bundle(records))["status"] == "BLOCKED"


def test_shared_material_id_across_splits_is_leakage_without_composition():
    records = _as_dft(_records())
    for rec in records:
        del rec["composition"]
    records[0]["material_id"] = "mp-19770"  # train
    records[4]["material_id"] = "MP-19770"  # test, case variant of the same id
    report = ev.check_leakage(records)
    assert report["status"] == "LEAKAGE"
    assert report["composition_check"] == "NOT_RUN"
    assert report["material_check"] == "PARTIAL"
    assert report["material_overlap"] == [
        {
            "material_id": "MP-19770",
            "splits": ["train", "test"],
            "spellings": ["MP-19770", "mp-19770"],
        }
    ]
    result = ev.evaluate(_bundle(records))
    assert result["status"] == "BLOCKED"
    assert "split leakage detected; metrics withheld" in result["reasons"]
    assert result["regression"] is None and result["discovery"] is None


def test_duplicate_ids_are_leakage():
    records = _records()
    records.append(_rec("te-1", "In-N", "test", 0.0, 0.0, "InN"))
    report = ev.check_leakage(records)
    assert report["status"] == "LEAKAGE"
    assert report["duplicate_ids"] == ["te-1"]


def test_reduced_composition_overlap_across_splits_is_leakage():
    records = _records()
    # Same reduced composition as tr-1 (Fe2O3) under a different group label.
    records.append(_rec("te-5", "Fe-O-poly", "test", 0.0, 0.0, "O6Fe4"))
    report = ev.check_leakage(records)
    assert report["status"] == "LEAKAGE"
    assert report["group_overlap"] == []
    assert report["composition_overlap"] == [
        {"composition": "Fe:2/5,O:3/5", "splits": ["train", "test"]}
    ]


def test_repeats_inside_one_split_are_trials_not_leakage():
    records = _records()
    records.append(_rec("te-5", "Ga-N", "test", 0.0, 0.25, "GaN", material_id="mat-GaN"))
    records[6]["material_id"] = "mat-GaN"
    report = ev.check_leakage(records)
    assert report["status"] == "NO_LEAKAGE_DETECTED"
    assert report["material_check"] == "PARTIAL" and report["material_overlap"] == []
    metrics = ev.regression_metrics(records)
    assert metrics["n_total"] == 5
    assert metrics["n_unique_materials"] == 4
    assert metrics["n_repeated_trials"] == 1


def test_case_variants_of_one_material_id_count_as_one_material():
    records = _records()
    records.append(_rec("te-5", "Ga-N", "test", 0.0, 0.25, "GaN", material_id="MAT-GaN"))
    records[6]["material_id"] = "mat-GaN"
    assert ev.check_leakage(records)["status"] == "NO_LEAKAGE_DETECTED"
    metrics = ev.regression_metrics(records)
    assert metrics["n_total"] == 5
    assert metrics["n_unique_materials"] == 4
    assert metrics["n_repeated_trials"] == 1


def test_missing_composition_is_reported_not_assumed_clean():
    records = _records()
    del records[0]["composition"]
    report = ev.check_leakage(records)
    assert report["composition_check"] == "PARTIAL"
    assert report["records_without_composition"] == 1
    result = ev.evaluate(_bundle(records))
    assert any("composition overlap check PARTIAL" in n for n in result["notes"])
    for rec in records:
        rec.pop("composition", None)
    assert ev.check_leakage(records)["composition_check"] == "NOT_RUN"


def test_composition_key_is_canonical_and_reduced():
    assert ev.composition_key("Fe2O3") == ev.composition_key("O6Fe4") == "Fe:2/5,O:3/5"
    assert ev.composition_key("Li0.5CoO2") == ev.composition_key("LiCo2O4")
    assert ev.composition_key("CO") != ev.composition_key("Co")
    for bad in ("", "Fe2(O3)", "Fe2 O3", "Fe2O3+", "fe"):
        with pytest.raises(ValueError):
            ev.composition_key(bad)


# --- regression metrics ----------------------------------------------------


def test_regression_metrics_exact_values_and_per_group_support():
    m = ev.regression_metrics(_records(), _task())
    assert m["split"] == "test" and m["unit"] == UNIT
    assert (m["n_total"], m["n_predicted"], m["n_missing"]) == (4, 4, 0)
    assert m["coverage"] == 1.0
    assert m["mae"] == 0.34375
    assert m["rmse"] == pytest.approx(math.sqrt(0.703125 / 4))
    assert m["per_group"] == [
        {"group": "Al-N", "support": 2, "n_predicted": 2, "n_missing": 0, "mae": 0.4375},
        {"group": "Ga-N", "support": 2, "n_predicted": 2, "n_missing": 0, "mae": 0.25},
    ]


def test_per_group_support_merges_case_variants_like_the_leakage_check():
    records = _as_dft(_records())
    records[6]["group"] = "al-n"  # te-3, was Ga-N
    records[7]["group"] = "al-n"  # te-4, was Ga-N
    assert ev.check_leakage(records)["status"] == "NO_LEAKAGE_DETECTED"
    m = ev.regression_metrics(records, _task())
    assert m["n_groups"] == 1
    assert m["per_group"] == [
        {
            "group": "Al-N",
            "spellings": ["Al-N", "al-n"],
            "support": 4,
            "n_predicted": 4,
            "n_missing": 0,
            "mae": 0.34375,
        }
    ]
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "SAMPLE"
    assert result["regression"]["n_groups"] == 1


def test_missing_predictions_are_counted_not_dropped():
    records = _records()
    records.append(_rec("te-5", "In-N", "test", -0.125, None, "InN"))
    m = ev.regression_metrics(records, _task())
    assert (m["n_total"], m["n_predicted"], m["n_missing"]) == (5, 4, 1)
    assert m["missing_ids"] == ["te-5"]
    assert m["coverage"] == 0.8
    assert m["mae"] == 0.34375
    assert m["per_group"][-1] == {
        "group": "In-N",
        "support": 1,
        "n_predicted": 0,
        "n_missing": 1,
        "mae": ev.UNDEFINED,
    }


def test_zero_predictions_give_undefined_errors_and_unknown_status():
    records = _records()
    for rec in records:
        if rec["split"] == "test":
            rec["y_pred"] = None
    m = ev.regression_metrics(records, _task())
    assert m["n_predicted"] == 0 and m["n_missing"] == 4
    assert m["mae"] == ev.UNDEFINED and m["rmse"] == ev.UNDEFINED
    assert m["coverage"] == 0.0
    result = ev.evaluate(_bundle(records))
    assert result["status"] == "UNKNOWN"
    assert "no test-split predictions; error metrics UNDEFINED" in result["reasons"]


def test_empty_split_coverage_is_undefined_not_zero():
    records = [r for r in _records() if r["split"] != "calibration"]
    m = ev.regression_metrics(records, _task(), split="calibration")
    assert m["n_total"] == 0
    assert m["coverage"] == ev.UNDEFINED
    assert m["mae"] == ev.UNDEFINED
    with pytest.raises(ValueError):
        ev.regression_metrics(records, _task(), split="holdout")


def test_overflowing_error_is_refused_not_reported_as_inf():
    records = _records()
    records[4]["y_true"] = -1.7e308
    records[4]["y_pred"] = 1.7e308
    with pytest.raises(ValueError):
        ev.regression_metrics(records)
    result = ev.evaluate(_bundle(records))
    assert result["status"] == "BLOCKED"
    assert result["reasons"][0].startswith("metric computation refused")


@pytest.mark.parametrize("magnitude", [1e200, 1e308])
def test_representable_large_mean_and_rmse_do_not_overflow(magnitude):
    records = [_rec("a", "a", "test", magnitude, 0.0),
               _rec("b", "b", "test", magnitude, 0.0)]
    metrics = ev.regression_metrics(records)
    assert metrics["mae"] == magnitude
    assert metrics["rmse"] == magnitude


@pytest.mark.parametrize("formula", ["Xx2O3", "Q2Zz", "Uuo", "D2O"])
def test_unknown_element_symbols_are_rejected(formula):
    with pytest.raises(ValueError):
        ev.composition_key(formula)
    records = _records()
    records[0]["composition"] = formula
    assert ev.validate_records(records)["ok"] is False


def test_named_elements_and_decimal_compositions_remain_supported():
    assert len(ev._ELEMENT_SYMBOLS) == 118
    for element in ev._ELEMENT_SYMBOLS:
        assert ev.composition_key(element) == element + ":1"
    assert ev.composition_key("Li0.5CoO2") == ev.composition_key("LiCo2O4")


def test_competitor_budgets_preserve_exact_json_integer_range():
    assert ev.budget_parity([_competitor("a", budget=2**53),
                             _competitor("b", budget=2**53)])["parity"] == "EQUAL"
    with pytest.raises(ev.RecordValidationError):
        ev.budget_parity([_competitor("a", budget=2**53),
                          _competitor("b", budget=2**53 + 1)])


# --- discovery metrics -----------------------------------------------------


def test_discovery_metrics_exact_confusion_and_daf():
    d = ev.discovery_metrics(_records())
    assert d["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert (d["precision"], d["recall"], d["f1"]) == (0.5, 0.5, 0.5)
    assert d["prevalence"] == 0.5
    assert d["daf"] == 1.0
    assert d["missing_policy"] == "count_as_unstable" and d["n_missing"] == 0


def test_default_policy_counts_missing_as_predicted_unstable_and_reports_it():
    records = _records()
    records.append(_rec("te-5", "In-N", "test", -0.125, None, "InN"))
    d = ev.discovery_metrics(records)
    assert d["missing_policy"] == "count_as_unstable"
    assert d["n_missing"] == 1 and d["missing_ids"] == ["te-5"]
    assert d["missing_counted_as_false_negative"] == 1
    assert d["confusion"] == {"tp": 1, "fp": 1, "fn": 2, "tn": 1}
    assert d["n_classified"] == 5
    assert d["precision"] == 0.5
    assert d["recall"] == pytest.approx(1 / 3)
    assert d["f1"] == 0.4
    assert d["prevalence"] == 0.6
    assert d["daf"] == pytest.approx(0.5 / 0.6)


def test_exclude_policy_still_reports_missing_count():
    records = _records()
    records.append(_rec("te-5", "In-N", "test", -0.125, None, "InN"))
    d = ev.discovery_metrics(records, missing_policy="exclude")
    assert d["n_missing"] == 1 and d["n_classified"] == 4
    assert d["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert d["missing_counted_as_false_negative"] == 0
    assert d["prevalence"] == 0.6  # reference prevalence over every test record
    with pytest.raises(ValueError):
        ev.discovery_metrics(records, missing_policy="drop")


def test_prediction_exactly_at_threshold_counts_as_predicted_stable():
    records = [
        _rec("te-1", "A", "test", -0.25, 0.0),  # predicted stable at the boundary: TP
        _rec("te-2", "B", "test", 0.5, 0.0),  # predicted stable at the boundary: FP
        _rec("te-3", "C", "test", 0.0, 0.5),  # truly stable at the boundary: FN
    ]
    d = ev.discovery_metrics(records)
    assert d["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 0}
    assert d["prevalence"] == pytest.approx(2 / 3)


def test_missing_prediction_on_a_truly_unstable_record_is_a_true_negative():
    records = _records()
    records.append(_rec("te-5", "In-N", "test", 0.5, None, "InN"))
    d = ev.discovery_metrics(records)
    assert d["missing_counted_as_true_negative"] == 1
    assert d["missing_counted_as_false_negative"] == 0
    assert d["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 2}
    assert d["precision"] == 0.5
    assert d["prevalence"] == 0.4


def _task_threshold_and_exclude_records():
    records = _as_dft(_records())
    records.append(_rec("te-5", "In-N", "test", 0.125, None, "InN"))
    records[-1].update(data_origin="dft", functional="PBE")
    return records


def test_evaluate_applies_the_task_threshold_and_missing_policy():
    records = _task_threshold_and_exclude_records()
    result = ev.evaluate(
        _bundle(records=records, task=_task(threshold=0.3, missing_policy="exclude"))
    )
    assert result["status"] == "SAMPLE"
    d = result["discovery"]
    assert d["threshold"] == 0.3 and d["missing_policy"] == "exclude"
    # At 0.3 eV/atom te-3 (pred 0.25) is a TP; under exclude te-5 is not an FN.
    assert d["confusion"] == {"tp": 2, "fp": 1, "fn": 0, "tn": 1}
    assert (d["n_missing"], d["n_classified"]) == (1, 4)
    assert d["prevalence"] == 0.6
    assert d["precision"] == pytest.approx(2 / 3) and d["recall"] == 1.0


def test_direct_discovery_call_follows_the_task_contract():
    records = _task_threshold_and_exclude_records()
    task = _task(threshold=0.3, missing_policy="exclude")
    d = ev.discovery_metrics(records, task=task)
    assert d["threshold"] == 0.3 and d["missing_policy"] == "exclude"
    assert d["confusion"] == {"tp": 2, "fp": 1, "fn": 0, "tn": 1}
    assert ev.discovery_metrics(records, threshold=0.3, task=task)["threshold"] == 0.3
    with pytest.raises(ValueError, match="conflicts with task.discovery.threshold"):
        ev.discovery_metrics(records, threshold=0.0, task=task)
    with pytest.raises(ValueError, match="conflicts with task.discovery.missing_policy"):
        ev.discovery_metrics(records, missing_policy="count_as_unstable", task=task)
    regression_only = {"task_id": "t", "unit": UNIT, "target": "e_above_hull"}
    with pytest.raises(ev.RecordValidationError, match="no discovery block"):
        ev.discovery_metrics(records, task=regression_only)


def test_zero_denominators_are_undefined_not_zero():
    all_unstable = [
        _rec("te-1", "A", "test", 0.5, 0.25),
        _rec("te-2", "B", "test", 0.25, 0.5),
    ]
    d = ev.discovery_metrics(all_unstable)
    assert d["confusion"] == {"tp": 0, "fp": 0, "fn": 0, "tn": 2}
    assert d["precision"] == ev.UNDEFINED
    assert d["recall"] == ev.UNDEFINED
    assert d["f1"] == ev.UNDEFINED
    assert d["prevalence"] == 0.0
    assert d["daf"] == ev.UNDEFINED

    none_predicted_stable = [_rec("te-1", "A", "test", -0.25, 0.25)]
    d = ev.discovery_metrics(none_predicted_stable)
    assert d["precision"] == ev.UNDEFINED
    assert d["recall"] == 0.0
    assert d["daf"] == ev.UNDEFINED

    d = ev.discovery_metrics([_rec("tr-1", "A", "train", 0.0, 0.0)])
    assert d["n_total"] == 0
    assert d["prevalence"] == ev.UNDEFINED and d["daf"] == ev.UNDEFINED


def test_discovery_requires_energy_above_hull_unit_and_finite_threshold():
    records = _records()
    for rec in records:
        rec["unit"] = "eV"
    with pytest.raises(ev.RecordValidationError):
        ev.discovery_metrics(records)
    for bad in (float("nan"), True, "0"):
        with pytest.raises(ValueError):
            ev.discovery_metrics(_records(), threshold=bad)


# --- budgets and parity ----------------------------------------------------


def test_acceleration_factor_fixture_ten_versus_five_is_two():
    assert ev.acceleration_factor(10, 5) == 2.0
    assert ev.budget_fraction(10, 5) == 0.5
    rejected = (
        (0, 5),
        (10, 0),
        (-10, 5),
        (True, 5),
        (10, float("nan")),
        (2**53 + 1, 5),  # no exact float beyond 2**53
        (10, 2**53 + 1),
    )
    for random_budget, model_budget in rejected:
        with pytest.raises(ValueError):
            ev.acceleration_factor(random_budget, model_budget)
        with pytest.raises(ValueError):
            ev.budget_fraction(random_budget, model_budget)
    assert ev.acceleration_factor(2**53, 2**52) == 2.0
    with pytest.raises(ValueError):
        ev.acceleration_factor(1e308, 1e-308)


def _competitor(name, budget=100, relaxed="unrelaxed", overlap="none"):
    return {
        "name": name,
        "candidate_budget": budget,
        "relaxed_inputs": relaxed,
        "training_overlap": overlap,
    }


def test_equal_budgets_are_admissible():
    p = ev.budget_parity([_competitor("szl"), _competitor("baseline-mean")])
    assert p["parity"] == "EQUAL"
    assert p["conditions_equal"] is True
    assert p["comparison_admissible"] is True
    assert p["all_held_out"] is True
    assert p["flags"] == []


def test_unequal_budgets_are_flagged():
    p = ev.budget_parity([_competitor("szl", 100), _competitor("other", 50)])
    assert p["parity"] == "UNEQUAL"
    assert "unequal-candidate-budget" in p["flags"]
    assert p["comparison_admissible"] is False
    result = ev.evaluate(
        _bundle(competitors=[_competitor("szl", 100), _competitor("other", 50)])
    )
    assert result["budget_parity"]["parity"] == "UNEQUAL"
    assert any("competitor comparison not admissible" in n for n in result["notes"])


def test_relaxation_status_must_match_and_be_known():
    p = ev.budget_parity([_competitor("a", relaxed="relaxed"), _competitor("b")])
    assert p["parity"] == "UNEQUAL"
    assert "relaxed-input-mismatch" in p["flags"] and "relaxed-inputs-used" in p["flags"]
    p = ev.budget_parity([_competitor("a", relaxed="unknown"), _competitor("b")])
    assert p["parity"] == "UNKNOWN"
    assert p["comparison_admissible"] is False


def test_relaxed_inputs_keep_parity_but_evaluate_adds_a_note():
    # Equal conditions stay admissible (owner decision), but relaxed inputs
    # leak label information (Riebesell et al. 2023), so the output says so.
    entries = [_competitor("szl", relaxed="relaxed"), _competitor("base", relaxed="relaxed")]
    p = ev.budget_parity(entries)
    assert p["parity"] == "EQUAL" and p["comparison_admissible"] is True
    assert p["flags"] == ["relaxed-inputs-used"]
    result = ev.evaluate(_bundle(records=_as_dft(_records()), competitors=entries))
    assert result["status"] == "SAMPLE"
    assert (
        "relaxed inputs used by ['szl', 'base']: relaxed structures carry information "
        "from the label calculation, so the comparison describes a relaxed-input "
        "setting, not discovery from unrelaxed candidates"
    ) in result["notes"]
    plain = ev.evaluate(
        _bundle(records=_as_dft(_records()), competitors=[_competitor("a"), _competitor("b")])
    )
    assert not any(n.startswith("relaxed inputs used") for n in plain["notes"])


def test_overlap_unknown_blocks_held_out_label():
    p = ev.budget_parity([_competitor("szl"), _competitor("pretrained", overlap="unknown")])
    labels = {e["name"]: e["held_out_label"] for e in p["entries"]}
    assert labels == {"szl": "held-out", "pretrained": "overlap-unknown"}
    assert p["all_held_out"] is False
    assert "overlap-unknown:pretrained" in p["flags"]


@pytest.mark.parametrize("overlap", ["known", "unknown"])
def test_competitor_training_overlap_makes_comparison_inadmissible(overlap):
    entries = [_competitor("szl", overlap=overlap), _competitor("baseline")]
    p = ev.budget_parity(entries)
    assert p["parity"] == "EQUAL" and p["conditions_equal"] is True
    assert p["all_held_out"] is False
    assert p["comparison_admissible"] is False
    result = ev.evaluate(_bundle(records=_as_dft(_records()), competitors=entries))
    assert result["held_out_label"] == "held-out"
    assert result["budget_parity"]["comparison_admissible"] is False
    assert (
        "competitor comparison not admissible: training overlap is not 'none' for ['szl']"
        in result["notes"]
    )


def test_single_competitor_parity_is_not_applicable():
    p = ev.budget_parity([_competitor("szl")])
    assert p["parity"] == "NOT_APPLICABLE"
    assert p["comparison_admissible"] is False


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [_competitor("a", budget=True)],
        [_competitor("a", budget=10.0)],
        [_competitor("a", relaxed="yes")],
        [_competitor("a", overlap="maybe")],
        [_competitor("a"), _competitor("a")],
    ],
)
def test_invalid_competitors_fail_closed(entries):
    with pytest.raises(ev.RecordValidationError):
        ev.budget_parity(entries)
    if entries:
        assert ev.evaluate(_bundle(competitors=entries))["status"] == "BLOCKED"


# --- evaluate: status and provenance --------------------------------------


def test_synthetic_sample_bundle_is_labelled_sample():
    result = ev.evaluate(_bundle())
    assert result["status"] == "SAMPLE"
    assert result["held_out_label"] == "held-out"
    assert result["leakage"]["status"] == "NO_LEAKAGE_DETECTED"
    assert result["regression"]["mae"] == 0.34375
    assert result["discovery"]["daf"] == 1.0
    assert result["claims"] == {
        "model_fit": False,
        "benchmark_run": False,
        "discovery_claim": False,
        "prospective_evaluation": False,
        "provenance_verified": False,
    }
    assert "preprocessing-fold-isolation" in result["not_run"]
    assert "provenance-hash-recomputation" in result["not_run"]


def test_unverified_provenance_is_sample_never_measured():
    # Digests are format-checked, never recomputed, so synthetic records with
    # complete-looking provenance cannot earn the doctrine label MEASURED.
    result = ev.evaluate(_bundle(records=_as_dft(_records())))
    assert result["status"] == "SAMPLE"
    assert result["provenance"]["complete"] is True
    assert result["reasons"] == [
        "provenance digests are format-checked only and no referenced artifact "
        "was re-hashed, so the result is not MEASURED"
    ]
    assert result["claims"]["provenance_verified"] is False
    assert "MEASURED" not in ev.STATUSES and "MEASURED" in ev.NEVER_EMITTED


def test_one_sample_record_among_dft_records_makes_the_bundle_sample():
    records = _as_dft(_records())
    records[5].update(data_origin="sample", functional=None)
    result = ev.evaluate(_bundle(records=records))
    assert result["status"] == "SAMPLE"
    assert "records include data_origin 'sample'" in result["reasons"]


def test_regression_only_task_is_evaluated_without_discovery():
    records = _as_dft(_records())
    for rec in records:
        rec["unit"] = "eV"
    task = {"task_id": "synthetic-band-gap", "unit": "eV", "target": "band_gap"}
    result = ev.evaluate(_bundle(records=records, task=task))
    assert result["status"] == "SAMPLE"
    assert result["discovery"] is None
    assert result["regression"]["unit"] == "eV" and result["regression"]["mae"] == 0.34375


@pytest.mark.parametrize("key", ev.REQUIRED_HASHES + ev.REQUIRED_LICENSES)
def test_missing_provenance_is_unknown_never_pass(key):
    prov = _provenance()
    del prov[key]
    result = ev.evaluate(_bundle(records=_as_dft(_records()), provenance=prov))
    assert result["status"] == "UNKNOWN"
    assert result["provenance"]["missing"] == [key]
    assert any(key in r for r in result["reasons"])


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"model_sha256": "A" * 64}, "invalid"),
        ({"model_sha256": "4" * 63}, "invalid"),
        ({"model_sha256": "4" * 64 + "\n"}, "invalid"),
        ({"model_sha256": 4}, "invalid"),
        ({"training_overlap": "maybe"}, "invalid"),
        ({"code_license": "  "}, "missing"),
        ({"data_license": "UNKNOWN"}, "placeholder"),
        ({"checkpoint_license": "n/a"}, "placeholder"),
        ({"data_license": "Unverified"}, "placeholder"),
        ({"data_license": "NOASSERTION"}, "placeholder"),
        ({"data_license": "TODO"}, "placeholder"),
        ({"code_license": "TBA"}, "placeholder"),
        ({"checkpoint_license": "unspecified"}, "placeholder"),
        ({"data_license": "Not  Specified"}, "placeholder"),
        ({"data_license": "?"}, "placeholder"),
        ({"code_license": " - "}, "placeholder"),
        ({"task_sha256": "0" * 64}, "placeholder"),
        ({"hull_sha256": "f" * 64}, "placeholder"),
        ({"task_sha256": "0123456789abcdef" * 4}, "placeholder"),
        ({"split_sha256": "deadbeef" * 8}, "placeholder"),
        ({"hull_sha256": "ab" * 32}, "placeholder"),
        ({"model_sha256": ("abc" * 22)[:64]}, "placeholder"),
        ({"checkpoint_sha256": _digest("half")[:32] * 2}, "placeholder"),
        ({"checkpoint_sha256": hashlib.sha256(b"").hexdigest()}, "placeholder"),
        ({key: hashlib.sha256(b"x").hexdigest() for key in ev.REQUIRED_HASHES}, "placeholder"),
        ({"model_sha256": _digest("synthetic checkpoint")}, "placeholder"),
    ],
)
def test_malformed_or_placeholder_provenance_is_unknown(overrides, field):
    result = ev.evaluate(
        _bundle(records=_as_dft(_records()), provenance=_provenance(**overrides))
    )
    assert result["status"] == "UNKNOWN"
    assert result["provenance"][field]
    assert result["provenance"]["complete"] is False


@pytest.mark.parametrize("license_id", ["MIT", "CC0-1.0", "Unlicense", "LicenseRef-internal"])
def test_real_license_identifiers_are_not_placeholders(license_id):
    result = ev.evaluate(
        _bundle(records=_as_dft(_records()), provenance=_provenance(data_license=license_id))
    )
    assert result["status"] == "SAMPLE"
    assert result["provenance"]["placeholder"] == []


def test_real_digests_are_not_screened_as_placeholders():
    records = _as_dft(_records())
    for index in range(200):
        prov = _provenance(model_sha256=_digest(f"synthetic model {index}"))
        result = ev.evaluate(_bundle(records=records, provenance=prov))
        assert result["provenance"]["placeholder"] == [], index


def test_one_digest_reused_across_artifacts_names_every_field_that_shares_it():
    shared = _digest("synthetic checkpoint")
    result = ev.evaluate(
        _bundle(
            records=_as_dft(_records()),
            provenance=_provenance(model_sha256=shared, task_sha256="0" * 64),
        )
    )
    assert result["status"] == "UNKNOWN"
    assert result["provenance"]["placeholder"] == [
        "task_sha256",
        "model_sha256",
        "checkpoint_sha256",
    ]
    assert "model_sha256" not in result["provenance"]["fields"]
    assert result["provenance"]["fields"]["hull_sha256"] == _digest("synthetic convex hull")


def test_absent_provenance_object_is_unknown():
    bundle = _bundle(records=_as_dft(_records()))
    del bundle["provenance"]
    result = ev.evaluate(bundle)
    assert result["status"] == "UNKNOWN"
    assert result["held_out_label"] == "overlap-unknown"


@pytest.mark.parametrize(
    "overlap,label",
    [(None, "overlap-unknown"), ("unknown", "overlap-unknown"), ("known", "overlap-known")],
)
def test_training_overlap_controls_the_held_out_label(overlap, label):
    prov = _provenance()
    if overlap is None:
        del prov["training_overlap"]
    else:
        prov["training_overlap"] = overlap
    result = ev.evaluate(_bundle(records=_as_dft(_records()), provenance=prov))
    assert result["held_out_label"] == label
    assert result["status"] == "SAMPLE"
    assert f"training overlap label {label!r}: not a held-out evaluation" in result["notes"]


def test_status_vocabulary_never_contains_pass_or_measured():
    bundles = [
        _bundle(),
        _bundle(records=_as_dft(_records())),
        _bundle(provenance={}),
        _bundle(records=[]),
        None,
    ]
    statuses = {ev.evaluate(b)["status"] for b in bundles}
    assert statuses <= set(ev.STATUSES)
    assert not statuses & {"PASS", "MEASURED"}
    assert ev.evaluate(_bundle(records=[]))["status"] == "UNKNOWN"


def test_evaluate_does_not_mutate_its_input():
    bundle = _bundle(competitors=[_competitor("szl"), _competitor("other")])
    snapshot = copy.deepcopy(bundle)
    ev.evaluate(bundle)
    assert bundle == snapshot


def test_records_digest_binds_the_fields_read():
    first = ev.evaluate(_bundle())["records_sha256"]
    assert first == ev.evaluate(_bundle())["records_sha256"]
    assert len(first) == 64
    changed = _records()
    changed[4]["y_pred"] = -0.0625
    assert ev.evaluate(_bundle(records=changed))["records_sha256"] != first


def test_records_digest_binds_values_not_their_spelling():
    first = ev.evaluate(_bundle())["records_sha256"]
    respelled = _records()
    respelled[0]["y_true"] = 0  # int instead of 0.0
    respelled[6]["y_true"] = -0.0  # negative zero instead of 0.0
    assert ev.evaluate(_bundle(records=respelled))["records_sha256"] == first
    # Non-zero values too: 1 and 1.0 are the same number.
    as_float = _records()
    as_float[7]["y_true"], as_float[5]["y_pred"] = 1.0, -1.0
    as_int = _records()
    as_int[7]["y_true"], as_int[5]["y_pred"] = 1, -1
    digest = ev.evaluate(_bundle(records=as_float))["records_sha256"]
    assert digest == ev.evaluate(_bundle(records=as_int))["records_sha256"]
    assert digest != first


# --- module boundary -------------------------------------------------------


def test_module_is_stdlib_only_and_side_effect_free():
    source = (ROOT / "szl_materials_eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"hashlib", "json", "math", "re", "fractions"}, imported
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called & {"open", "exec", "eval", "__import__", "compile"}
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "register" not in defined
    assert source.startswith("#!/usr/bin/env python3\n# SPDX-License-Identifier: Apache-2.0\n")
    assert "Taxonomy home: governance/" in source
