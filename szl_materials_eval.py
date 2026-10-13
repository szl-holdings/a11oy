#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only retrospective/OOD and discovery evaluator for sealed materials
prediction records (work package R09, MAT-U05).

Taxonomy home: governance/ (the evaluation-honesty contract of the materials
vertical).  The module serves no route, is not imported by serve.py and is not
copied into the image, so it needs no Dockerfile COPY line.  It is stdlib only.
It fits nothing, opens no file or socket, writes no ledger, mints no Khipu
receipt and signs nothing: every function is a pure computation over the
caller's in-memory records.

Functions
    validate_records     reject malformed sealed prediction records
    check_leakage        id, group, material and composition overlap across
                         splits
    regression_metrics   coverage, MAE, RMSE, per-group error and support
    discovery_metrics    stability classification under a declared
                         missing-prediction policy: precision, recall, F1,
                         prevalence and DAF
    acceleration_factor  random_budget / model_budget (budget_fraction is the
                         reciprocal, under its own name)
    budget_parity        candidate budget, input relaxation status and
                         training-overlap label across competitors
    evaluate             one bundle -> one status in
                         {UNVERIFIED, SAMPLE, UNKNOWN, BLOCKED}; never PASS
                         and never MEASURED

Limits
    Results describe the supplied records only.  They are not a benchmark run,
    not a reproduction of an official leaderboard, and not evidence of a
    prospective discovery, which retrospective replay cannot establish.
    Provenance hashes are checked for presence and format only; the evaluator
    does not read or re-hash the referenced artifacts.  That is why the best
    status it can give is UNVERIFIED: doctrine reserves MEASURED for a real,
    fresh measurement, and an unchecked digest is not one.  Preprocessing-fold
    and hyperparameter isolation cannot be observed from sealed records, so
    they are reported as NOT_RUN.  A ratio with a zero denominator is
    "UNDEFINED", never 0.

Prior art (ideas cited, no code copied; this is an original implementation)
    Dunn et al. 2020, Matbench, npj Comput. Mater. 6, 138 (code MIT):
        task contracts with per-task units; retrospective splits.
    Riebesell et al. 2023, Matbench Discovery, arXiv:2308.14920 (code MIT):
        stability against a fixed hull, missing predictions counted as
        unstable by default, DAF = precision / prevalence, relaxed-input
        leakage.
    Omee et al. 2024, structure-based OOD benchmark, npj Comput. Mater.:
        report per-group error and support, not one pooled OOD number.
    Borg et al. 2023, Digital Discovery, doi:10.1039/D2DD00113F:
        acceleration under finite budgets.  Defined here explicitly as
        random_budget / model_budget, so 10 versus 5 gives 2.
"""

import hashlib
import json
import math
import re
from fractions import Fraction

__all__ = [
    "SCHEMA",
    "UNDEFINED",
    "RecordValidationError",
    "composition_key",
    "validate_records",
    "check_leakage",
    "regression_metrics",
    "discovery_metrics",
    "acceleration_factor",
    "budget_fraction",
    "budget_parity",
    "evaluate",
]

SCHEMA = "szl.materials_eval/v1"
UNDEFINED = "UNDEFINED"

SPLITS = ("train", "calibration", "test")
DATA_ORIGINS = ("experimental", "dft", "sample")
MISSING_POLICIES = ("count_as_unstable", "exclude")
RELAXATION_STATES = ("unrelaxed", "relaxed", "unknown")
OVERLAP_STATES = ("none", "known", "unknown")
HULL_UNIT = "eV/atom"
HULL_TARGET = "e_above_hull"

REQUIRED_HASHES = (
    "task_sha256",
    "split_sha256",
    "hull_sha256",
    "model_sha256",
    "checkpoint_sha256",
)
REQUIRED_LICENSES = ("data_license", "code_license", "checkpoint_license")
NOT_RUN_CHECKS = (
    "preprocessing-fold-isolation",
    "hyperparameter-selection-isolation",
    "provenance-hash-recomputation",
    "group-bootstrap-intervals",
)
STATUSES = ("UNVERIFIED", "SAMPLE", "UNKNOWN", "BLOCKED")
# Labels evaluate() must never emit: PASS is not an evaluation outcome, and
# MEASURED needs artifacts that were re-hashed, which this module never does.
NEVER_EMITTED = ("PASS", "MEASURED")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_FORMULA_TOKEN = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")
_LICENSE_PLACEHOLDERS = frozenset(
    {"unknown", "unverified", "n/a", "na", "tbd", "none", "null"}
)
_DIGEST_FIELDS = (
    "id",
    "group",
    "split",
    "y_true",
    "y_pred",
    "unit",
    "data_origin",
    "functional",
    "composition",
    "material_id",
)
_NO_CLAIMS = {
    "model_fit": False,
    "benchmark_run": False,
    "discovery_claim": False,
    "prospective_evaluation": False,
    "provenance_verified": False,
}


class RecordValidationError(ValueError):
    """Input failed the record, task or competitor contract."""

    def __init__(self, errors):
        self.errors = list(errors)
        head = "; ".join(self.errors[:5])
        more = f" (+{len(self.errors) - 5} more)" if len(self.errors) > 5 else ""
        super().__init__(head + more)


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def _padded(value):
    return value != value.strip()


def _identity(value):
    # Group and material identities compare case-insensitively.  This can only
    # merge spellings, so a case variant across splits is reported as leakage
    # instead of slipping past the check.
    return value.casefold()


def _finite_real(value):
    # bool is an int subclass; True must never pass as 1.0.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _defined(value):
    return value != UNDEFINED


def _ratio(numerator, denominator):
    return UNDEFINED if denominator == 0 else numerator / denominator


def _finite_metric(name, value):
    if not math.isfinite(value):
        raise ValueError(f"{name} is not finite (value range overflow)")
    return value


def _ordered_splits(splits):
    return [s for s in SPLITS if s in splits]


def composition_key(formula):
    """Return a canonical reduced composition key for a simple formula.

    'Fe2O3' and 'O6Fe4' both map to 'Fe:2/5,O:3/5'.  Parentheses, hydrates,
    charges and lower-case symbols are rejected rather than guessed.
    """
    if not _nonempty_str(formula):
        raise ValueError("composition must be a non-empty formula string")
    text = formula.strip()
    counts = {}
    pos = 0
    while pos < len(text):
        match = _FORMULA_TOKEN.match(text, pos)
        if match is None:
            raise ValueError(
                f"composition {formula!r} is not a simple formula such as 'Fe2O3'"
            )
        amount = Fraction(match.group(2)) if match.group(2) else Fraction(1)
        if amount <= 0:
            raise ValueError(f"composition {formula!r} has a non-positive count")
        counts[match.group(1)] = counts.get(match.group(1), Fraction(0)) + amount
        pos = match.end()
    total = sum(counts.values())
    return ",".join(f"{el}:{counts[el] / total}" for el in sorted(counts))


def _task_errors(task):
    if not isinstance(task, dict):
        return ["task contract must be an object"]
    errors = []
    for key in ("task_id", "unit", "target"):
        if not _nonempty_str(task.get(key)):
            errors.append(f"task.{key} must be a non-empty string")
    discovery = task.get("discovery")
    if discovery is not None:
        if not isinstance(discovery, dict):
            errors.append("task.discovery must be an object")
        else:
            if task.get("unit") != HULL_UNIT:
                errors.append(
                    f"task.discovery requires task.unit == {HULL_UNIT!r} "
                    "(energy above hull)"
                )
            # Formation energy is also eV/atom; the unit alone cannot tell
            # them apart, and stability is defined against the hull.
            if task.get("target") != HULL_TARGET:
                errors.append(
                    f"task.discovery requires task.target == {HULL_TARGET!r} "
                    "(stability is classified from energy above hull)"
                )
            if not _finite_real(discovery.get("threshold", 0.0)):
                errors.append("task.discovery.threshold must be a finite real number")
            policy = discovery.get("missing_policy", MISSING_POLICIES[0])
            if policy not in MISSING_POLICIES:
                errors.append(
                    f"task.discovery.missing_policy must be one of {list(MISSING_POLICIES)}"
                )
    return errors


def validate_records(records, task=None):
    """Check sealed prediction records against the record and task contract.

    Returns {"ok", "errors", "n_records"}; it never raises for bad input.
    Each record needs: id, group (group, prototype or chemical-system id),
    split in {train, calibration, test}, finite real y_true, y_pred (finite
    real, or null for a missing prediction), unit (equal to the task unit when
    a task is given), data_origin in {experimental, dft, sample} and
    functional (null allowed unless the label is DFT).  Optional: composition
    (simple formula) and material_id (repeated trials of one material).
    id, group and material_id must not start or end with whitespace,
    so a padded copy cannot pass as a different identity.
    """
    errors = [] if task is None else _task_errors(task)
    if not isinstance(records, (list, tuple)):
        errors.append("records must be a list of objects")
        return {"ok": False, "errors": errors, "n_records": 0}
    task_unit = task.get("unit") if isinstance(task, dict) else None
    units = set()
    for index, rec in enumerate(records):
        where = f"records[{index}]"
        if not isinstance(rec, dict):
            errors.append(f"{where} must be an object")
            continue
        if _nonempty_str(rec.get("id")):
            where = f"{where} (id={rec['id']!r})"
            if _padded(rec["id"]):
                errors.append(f"{where}.id must not start or end with whitespace")
        else:
            errors.append(f"{where}.id must be a non-empty string")
        if not _nonempty_str(rec.get("group")):
            errors.append(
                f"{where}.group must be a non-empty string "
                "(group, prototype or chemical-system id)"
            )
        elif _padded(rec["group"]):
            errors.append(f"{where}.group must not start or end with whitespace")
        if rec.get("split") not in SPLITS:
            errors.append(f"{where}.split must be one of {list(SPLITS)}")
        if not _finite_real(rec.get("y_true")):
            errors.append(
                f"{where}.y_true must be a finite real number "
                "(bool, NaN and infinity are rejected)"
            )
        if "y_pred" not in rec:
            errors.append(f"{where}.y_pred must be present (null marks a missing prediction)")
        elif rec["y_pred"] is not None and not _finite_real(rec["y_pred"]):
            errors.append(
                f"{where}.y_pred must be null or a finite real number "
                "(bool, NaN and infinity are rejected)"
            )
        unit = rec.get("unit")
        if not _nonempty_str(unit):
            errors.append(f"{where}.unit must be a non-empty string")
        else:
            units.add(unit)
            if _nonempty_str(task_unit) and unit != task_unit:
                errors.append(
                    f"{where}.unit {unit!r} does not match the task contract unit "
                    f"{task_unit!r}"
                )
        origin = rec.get("data_origin")
        if origin not in DATA_ORIGINS:
            errors.append(f"{where}.data_origin must be one of {list(DATA_ORIGINS)}")
        if "functional" not in rec:
            errors.append(f"{where}.functional must be present (null when not a DFT label)")
        else:
            functional = rec["functional"]
            if functional is not None and not _nonempty_str(functional):
                errors.append(f"{where}.functional must be null or a non-empty string")
            elif origin == "dft" and functional is None:
                errors.append(f"{where}.functional is required for a DFT label")
        if rec.get("composition") is not None:
            try:
                composition_key(rec["composition"])
            except ValueError as exc:
                errors.append(f"{where}: {exc}")
        material = rec.get("material_id")
        if material is not None and not _nonempty_str(material):
            errors.append(f"{where}.material_id must be null or a non-empty string")
        elif material is not None and _padded(material):
            errors.append(
                f"{where}.material_id must not start or end with whitespace"
            )
    if len(units) > 1:
        errors.append(f"records mix units {sorted(units)}; one task has one unit")
    return {"ok": not errors, "errors": errors, "n_records": len(records)}


def _require_valid(records, task):
    report = validate_records(records, task)
    if not report["ok"]:
        raise RecordValidationError(report["errors"])


def _select(records, split):
    if split is not None and split not in SPLITS:
        raise ValueError(f"split must be one of {list(SPLITS)} or None")
    return [r for r in records if split is None or r["split"] == split]


def _identity_overlap(field, splits_by_key, spellings_by_key):
    overlap = []
    for key in sorted(splits_by_key):
        splits = splits_by_key[key]
        if len(splits) < 2:
            continue
        spellings = sorted(spellings_by_key[key])
        entry = {field: spellings[0], "splits": _ordered_splits(splits)}
        if len(spellings) > 1:
            entry["spellings"] = spellings
        overlap.append(entry)
    return overlap


def _coverage(n_records, n_without):
    if not n_records or n_without == n_records:
        return "NOT_RUN"
    return "PARTIAL" if n_without else "RUN"


def check_leakage(records, task=None):
    """Report duplicate ids and group, material or composition overlap.

    A group, material_id or reduced composition present in more than one split
    is leakage.  Groups and material ids compare case-insensitively.  Repeats
    inside one split are repeated trials, not leakage.  The status is
    "LEAKAGE" or "NO_LEAKAGE_DETECTED"; the second only covers the checks that
    ran (see composition_check and material_check).
    """
    _require_valid(records, task)
    id_counts = {}
    group_splits, group_spellings = {}, {}
    material_splits, material_spellings = {}, {}
    composition_splits = {}
    without_composition = without_material = 0
    for rec in records:
        id_counts[rec["id"]] = id_counts.get(rec["id"], 0) + 1
        key = _identity(rec["group"])
        group_splits.setdefault(key, set()).add(rec["split"])
        group_spellings.setdefault(key, set()).add(rec["group"])
        material = rec.get("material_id")
        if material is None:
            without_material += 1
        else:
            key = _identity(material)
            material_splits.setdefault(key, set()).add(rec["split"])
            material_spellings.setdefault(key, set()).add(material)
        if rec.get("composition") is None:
            without_composition += 1
        else:
            key = composition_key(rec["composition"])
            composition_splits.setdefault(key, set()).add(rec["split"])
    duplicate_ids = sorted(k for k, n in id_counts.items() if n > 1)
    group_overlap = _identity_overlap("group", group_splits, group_spellings)
    material_overlap = _identity_overlap("material_id", material_splits, material_spellings)
    composition_overlap = [
        {"composition": c, "splits": _ordered_splits(s)}
        for c, s in sorted(composition_splits.items())
        if len(s) > 1
    ]
    leaked = bool(duplicate_ids or group_overlap or material_overlap or composition_overlap)
    return {
        "status": "LEAKAGE" if leaked else "NO_LEAKAGE_DETECTED",
        "duplicate_ids": duplicate_ids,
        "group_overlap": group_overlap,
        "material_overlap": material_overlap,
        "composition_overlap": composition_overlap,
        "material_check": _coverage(len(records), without_material),
        "records_without_material_id": without_material,
        "composition_check": _coverage(len(records), without_composition),
        "records_without_composition": without_composition,
    }


def _mean(name, values):
    try:
        total = math.fsum(values)
    except OverflowError:
        total = math.inf
    return _finite_metric(name, total / len(values))


def _mae(rows):
    if not rows:
        return UNDEFINED
    return _mean("MAE", [abs(r["y_pred"] - r["y_true"]) for r in rows])


def _rmse(rows):
    if not rows:
        return UNDEFINED
    squared = [(r["y_pred"] - r["y_true"]) * (r["y_pred"] - r["y_true"]) for r in rows]
    return math.sqrt(_mean("RMSE", squared))


def regression_metrics(records, task=None, split="test"):
    """Coverage-aware MAE/RMSE over one split (split=None means all records).

    Missing predictions are never dropped silently: they stay in n_total, are
    counted in n_missing and listed in missing_ids, and lower coverage.  MAE
    and RMSE are over predicted records only and are UNDEFINED when nothing
    was predicted.  per_group gives error and support for every group.
    """
    _require_valid(records, task)
    rows = _select(records, split)
    predicted = [r for r in rows if r["y_pred"] is not None]
    missing_ids = sorted(r["id"] for r in rows if r["y_pred"] is None)
    by_group = {}
    for rec in rows:
        by_group.setdefault(rec["group"], []).append(rec)
    per_group = []
    for group in sorted(by_group):
        members = by_group[group]
        group_predicted = [r for r in members if r["y_pred"] is not None]
        per_group.append(
            {
                "group": group,
                "support": len(members),
                "n_predicted": len(group_predicted),
                "n_missing": len(members) - len(group_predicted),
                "mae": _mae(group_predicted),
            }
        )
    materials = {
        ("material", _identity(r["material_id"]))
        if r.get("material_id") is not None
        else ("record", r["id"])
        for r in rows
    }
    if rows:
        unit = rows[0]["unit"]
    elif isinstance(task, dict):
        unit = task.get("unit")
    else:
        unit = None
    return {
        "split": split if split is not None else "all",
        "unit": unit,
        "n_total": len(rows),
        "n_predicted": len(predicted),
        "n_missing": len(missing_ids),
        "missing_ids": missing_ids,
        "coverage": _ratio(len(predicted), len(rows)),
        "mae": _mae(predicted),
        "rmse": _rmse(predicted),
        "n_unique_materials": len(materials),
        "n_repeated_trials": len(rows) - len(materials),
        "n_groups": len(per_group),
        "per_group": per_group,
    }


def _discovery_setting(name, explicit, contract, default):
    declared = contract.get(name)
    if explicit is None:
        return default if declared is None else declared
    if declared is not None and explicit != declared:
        raise ValueError(
            f"{name} {explicit!r} conflicts with task.discovery.{name} {declared!r}"
        )
    return explicit


def discovery_metrics(
    records,
    threshold=None,
    missing_policy=None,
    task=None,
    split="test",
):
    """Stability classification from energy above hull (eV/atom).

    A record is stable when its value is <= threshold.  The missing-prediction
    policy is declared in the output: "count_as_unstable" (default) classifies
    a missing prediction as predicted-unstable; "exclude" leaves it out of the
    confusion matrix.  Either way the missing count is reported.  Prevalence
    is the reference stable fraction over every record in the split,
    independent of predictions.  DAF = precision / prevalence.  Every ratio
    with a zero denominator is UNDEFINED.

    With a task, the task must declare a discovery block; its threshold and
    missing_policy apply, and an explicit argument that contradicts them
    raises ValueError.  Without a task the defaults are 0.0 eV/atom and
    "count_as_unstable", and only the unit can be checked.
    """
    _require_valid(records, task)
    contract = {}
    if task is not None:
        contract = task.get("discovery")
        if contract is None:
            raise RecordValidationError(
                ["task declares no discovery block; discovery metrics do not apply"]
            )
    threshold = _discovery_setting("threshold", threshold, contract, 0.0)
    missing_policy = _discovery_setting(
        "missing_policy", missing_policy, contract, MISSING_POLICIES[0]
    )
    if not _finite_real(threshold):
        raise ValueError("threshold must be a finite real number (eV/atom)")
    if missing_policy not in MISSING_POLICIES:
        raise ValueError(f"missing_policy must be one of {list(MISSING_POLICIES)}")
    units = {r["unit"] for r in records}
    if units - {HULL_UNIT}:
        raise RecordValidationError(
            [f"discovery metrics need energy above hull in {HULL_UNIT!r}; got {sorted(units)}"]
        )
    rows = _select(records, split)
    tp = fp = fn = tn = 0
    missing_ids = []
    missing_as_fn = missing_as_tn = 0
    for rec in rows:
        truly_stable = rec["y_true"] <= threshold
        if rec["y_pred"] is None:
            missing_ids.append(rec["id"])
            if missing_policy == "exclude":
                continue
            if truly_stable:
                fn += 1
                missing_as_fn += 1
            else:
                tn += 1
                missing_as_tn += 1
            continue
        predicted_stable = rec["y_pred"] <= threshold
        if predicted_stable and truly_stable:
            tp += 1
        elif predicted_stable:
            fp += 1
        elif truly_stable:
            fn += 1
        else:
            tn += 1
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * tp, 2 * tp + fp + fn)
    prevalence = _ratio(sum(1 for r in rows if r["y_true"] <= threshold), len(rows))
    if _defined(precision) and _defined(prevalence) and prevalence > 0:
        daf = precision / prevalence
    else:
        daf = UNDEFINED
    return {
        "split": split if split is not None else "all",
        "unit": HULL_UNIT,
        "threshold": float(threshold),
        "missing_policy": missing_policy,
        "n_total": len(rows),
        "n_predicted": len(rows) - len(missing_ids),
        "n_missing": len(missing_ids),
        "missing_ids": sorted(missing_ids),
        "missing_counted_as_false_negative": missing_as_fn,
        "missing_counted_as_true_negative": missing_as_tn,
        "n_classified": tp + fp + fn + tn,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "prevalence": prevalence,
        "daf": daf,
    }


def _positive_budget(name, value):
    if not _finite_real(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number (bool is rejected)")
    return float(value)


def acceleration_factor(random_budget, model_budget):
    """random_budget / model_budget: 10 random versus 5 model gives 2.0."""
    ratio = _positive_budget("random_budget", random_budget) / _positive_budget(
        "model_budget", model_budget
    )
    return _finite_metric("acceleration_factor", ratio)


def budget_fraction(random_budget, model_budget):
    """model_budget / random_budget, the reciprocal of acceleration_factor."""
    ratio = _positive_budget("model_budget", model_budget) / _positive_budget(
        "random_budget", random_budget
    )
    return _finite_metric("budget_fraction", ratio)


def _held_out_label(overlap):
    if overlap == "none":
        return "held-out"
    if overlap == "known":
        return "overlap-known"
    return "overlap-unknown"


def budget_parity(entries):
    """Check that competitors were compared under the same conditions.

    Each entry: name, candidate_budget (positive int), relaxed_inputs in
    {unrelaxed, relaxed, unknown}, training_overlap in {none, known, unknown}.
    parity is EQUAL, UNEQUAL, UNKNOWN (a relaxation status is unknown) or
    NOT_APPLICABLE (fewer than two entries); conditions_equal is parity ==
    EQUAL.  Only training_overlap "none" earns the "held-out" label; "unknown"
    yields "overlap-unknown".  comparison_admissible needs both equal
    conditions and every competitor held out, because a competitor that saw
    (or may have seen) the test set is not comparable.
    """
    if not isinstance(entries, (list, tuple)) or not entries:
        raise RecordValidationError(["competitors must be a non-empty list"])
    errors = []
    names = set()
    rows = []
    for index, entry in enumerate(entries):
        where = f"competitors[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be an object")
            continue
        name = entry.get("name")
        if not _nonempty_str(name):
            errors.append(f"{where}.name must be a non-empty string")
        elif name in names:
            errors.append(f"{where}.name {name!r} is duplicated")
        else:
            names.add(name)
        budget = entry.get("candidate_budget")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            errors.append(f"{where}.candidate_budget must be a positive integer")
        if entry.get("relaxed_inputs") not in RELAXATION_STATES:
            errors.append(f"{where}.relaxed_inputs must be one of {list(RELAXATION_STATES)}")
        if entry.get("training_overlap") not in OVERLAP_STATES:
            errors.append(f"{where}.training_overlap must be one of {list(OVERLAP_STATES)}")
        rows.append(
            {
                "name": name,
                "candidate_budget": budget,
                "relaxed_inputs": entry.get("relaxed_inputs"),
                "training_overlap": entry.get("training_overlap"),
                "held_out_label": _held_out_label(entry.get("training_overlap")),
            }
        )
    if errors:
        raise RecordValidationError(errors)
    flags = []
    relaxation = {r["relaxed_inputs"] for r in rows}
    if len(rows) < 2:
        parity = "NOT_APPLICABLE"
    else:
        unequal = False
        if len({r["candidate_budget"] for r in rows}) > 1:
            flags.append("unequal-candidate-budget")
            unequal = True
        if len(relaxation - {"unknown"}) > 1:
            flags.append("relaxed-input-mismatch")
            unequal = True
        if "unknown" in relaxation:
            flags.append("relaxed-input-unknown")
        if unequal:
            parity = "UNEQUAL"
        elif "unknown" in relaxation:
            parity = "UNKNOWN"
        else:
            parity = "EQUAL"
    if "relaxed" in relaxation:
        flags.append("relaxed-inputs-used")
    for row in rows:
        if row["held_out_label"] != "held-out":
            flags.append(f"{row['held_out_label']}:{row['name']}")
    conditions_equal = parity == "EQUAL"
    all_held_out = all(r["held_out_label"] == "held-out" for r in rows)
    return {
        "parity": parity,
        "conditions_equal": conditions_equal,
        "all_held_out": all_held_out,
        "comparison_admissible": conditions_equal and all_held_out,
        "flags": flags,
        "entries": rows,
    }


def _placeholder_digest(value):
    # One repeated hex character ("0" * 64) or the digest of empty input is
    # what a stub writes, not what hashing a real artifact yields.
    return len(set(value)) == 1 or value == _EMPTY_SHA256


def _provenance_report(provenance):
    if not isinstance(provenance, dict):
        provenance = {}
    missing = []
    invalid = []
    placeholder = []
    fields = {}
    for key in REQUIRED_HASHES:
        value = provenance.get(key)
        if value is None or value == "":
            missing.append(key)
        elif not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            invalid.append(key)
        elif _placeholder_digest(value):
            placeholder.append(key)
        else:
            fields[key] = value
    for key in REQUIRED_LICENSES:
        value = provenance.get(key)
        if not _nonempty_str(value):
            missing.append(key)
        elif value.strip().lower() in _LICENSE_PLACEHOLDERS:
            placeholder.append(key)
        else:
            fields[key] = value
    overlap = provenance.get("training_overlap")
    if overlap is None:
        overlap = "unknown"
    elif overlap not in OVERLAP_STATES:
        invalid.append("training_overlap")
        overlap = "unknown"
    return {
        "complete": not missing and not invalid and not placeholder,
        "missing": missing,
        "invalid": invalid,
        "placeholder": placeholder,
        "training_overlap": overlap,
        "fields": fields,
    }


def _digest_value(key, value):
    # Bind numeric values, not their spelling: 0, 0.0 and -0.0 hash alike.
    if key in ("y_true", "y_pred") and value is not None:
        number = float(value)
        return 0.0 if number == 0 else number
    return value


def _records_digest(records):
    rows = [{key: _digest_value(key, rec.get(key)) for key in _DIGEST_FIELDS} for rec in records]
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def evaluate(bundle):
    """Evaluate one sealed bundle {task, records, provenance, competitors?}.

    Never raises for bad input and never returns PASS or MEASURED.  Status
    precedence: BLOCKED (invalid input, or split leakage; metrics withheld) >
    UNKNOWN (provenance missing, malformed or placeholder, or no test
    predictions) > SAMPLE (any record has data_origin "sample") > UNVERIFIED.
    UNVERIFIED means computed from the supplied records with well-formed
    provenance whose digests were not recomputed; it is not a measurement, a
    benchmark or a discovery claim.  Training overlap "none" earns
    held_out_label "held-out"; a missing or "unknown" overlap yields
    "overlap-unknown".
    """
    out = {
        "schema": SCHEMA,
        "status": None,
        "reasons": [],
        "notes": [],
        "held_out_label": None,
        "validation": None,
        "leakage": None,
        "provenance": None,
        "regression": None,
        "discovery": None,
        "budget_parity": None,
        "records_sha256": None,
        "not_run": list(NOT_RUN_CHECKS),
        "claims": dict(_NO_CLAIMS),
    }

    def blocked(reason):
        out["status"] = "BLOCKED"
        out["reasons"].append(reason)
        return out

    if not isinstance(bundle, dict):
        out["validation"] = {"ok": False, "errors": ["bundle must be an object"], "n_records": 0}
        return blocked("input validation failed")
    task = bundle.get("task")
    records = bundle.get("records")
    if isinstance(task, dict):
        report = validate_records(records, task)
        errors = list(report["errors"])
    else:
        report = validate_records(records)
        errors = ["task contract must be an object"] + report["errors"]
    parity = None
    competitors = bundle.get("competitors")
    if competitors is not None:
        try:
            parity = budget_parity(competitors)
        except RecordValidationError as exc:
            errors.extend(exc.errors)
    out["validation"] = {"ok": not errors, "errors": errors, "n_records": report["n_records"]}
    if errors:
        return blocked("input validation failed")

    out["records_sha256"] = _records_digest(records)
    leakage = check_leakage(records, task)
    out["leakage"] = leakage
    if leakage["status"] == "LEAKAGE":
        return blocked("split leakage detected; metrics withheld")
    if leakage["material_check"] != "RUN":
        out["notes"].append(
            f"material_id overlap check {leakage['material_check']}: "
            f"{leakage['records_without_material_id']} record(s) carry no material_id"
        )
    if leakage["composition_check"] != "RUN":
        out["notes"].append(
            f"composition overlap check {leakage['composition_check']}: "
            f"{leakage['records_without_composition']} record(s) carry no composition"
        )

    provenance = _provenance_report(bundle.get("provenance"))
    out["provenance"] = provenance
    out["held_out_label"] = _held_out_label(provenance["training_overlap"])
    if out["held_out_label"] != "held-out":
        out["notes"].append(
            f"training overlap label {out['held_out_label']!r}: "
            "not a held-out evaluation"
        )

    try:
        out["regression"] = regression_metrics(records, task, "test")
        if task.get("discovery") is not None:
            out["discovery"] = discovery_metrics(records, task=task, split="test")
    except ValueError as exc:
        out["regression"] = None
        out["discovery"] = None
        return blocked(f"metric computation refused: {exc}")

    if parity is not None:
        out["budget_parity"] = parity
        if not parity["conditions_equal"]:
            out["notes"].append(
                f"competitor comparison not admissible: parity {parity['parity']}"
            )
        if not parity["all_held_out"]:
            overlapping = [
                e["name"] for e in parity["entries"] if e["held_out_label"] != "held-out"
            ]
            out["notes"].append(
                "competitor comparison not admissible: training overlap is not "
                f"'none' for {overlapping}"
            )

    status = "UNVERIFIED"
    if not provenance["complete"]:
        status = "UNKNOWN"
        out["reasons"].append(
            "provenance incomplete: missing "
            f"{provenance['missing']}, invalid {provenance['invalid']}, "
            f"placeholder {provenance['placeholder']}"
        )
    if out["regression"]["n_predicted"] == 0:
        status = "UNKNOWN"
        out["reasons"].append("no test-split predictions; error metrics UNDEFINED")
    if status == "UNVERIFIED" and any(r["data_origin"] == "sample" for r in records):
        status = "SAMPLE"
        out["reasons"].append("records include data_origin 'sample'")
    if status == "UNVERIFIED":
        out["reasons"].append(
            "provenance digests are format-checked only and no referenced artifact "
            "was re-hashed, so the result is not MEASURED"
        )
    out["status"] = status
    return out
