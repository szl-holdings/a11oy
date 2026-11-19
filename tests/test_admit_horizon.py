#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Admit-horizon acceptance suite (pytest, offline, stdlib only).

Every closed form is checked by plugging its answer back into the locked
geometric mean from szl_verify_nine, never by trusting the formula.
"""

import copy
import json
import math
import random

import pytest

import szl_admit_horizon as h
import szl_verify_nine as nine

NOMINAL = [0.95, 0.92, 0.88, 0.90]
HIDDEN_WEAK = [0.95, 0.95, 0.95, 0.40]


def _decision(report):
    (claim,) = report["claims"]
    return claim


def _gm(scores, weights=None):
    return nine.weighted_gm(scores, weights)


# --- the locked verdicts are unchanged -------------------------------------------------------

@pytest.mark.parametrize("name,axes,expect_admit,expect_dang", nine.DEMO_VECTORS)
def test_flat_vectors_keep_the_locked_verdict(name, axes, expect_admit, expect_dang):
    claim = _decision(h.vector_horizon(list(axes)))
    assert claim["admit"] is expect_admit, name
    assert claim["dang"] is expect_dang, name
    assert claim["status"] == (nine.ADMITTED if expect_admit else nine.DENY)


def test_hidden_weak_repair_point_matches_the_closed_form():
    claim = _decision(h.vector_horizon(HIDDEN_WEAK))
    assert claim["status"] == nine.DENY and claim["dang"] is True
    rows = {row["evidence"]: row for row in claim["floors"]}
    assert rows["x4"]["single_input_repair_feasible"] is True
    assert rows["x4"]["repair_needs"] == pytest.approx(0.477737, abs=1e-6)
    for weak_axis in ("x1", "x2", "x3"):  # would need 1.1346 > 1
        assert rows[weak_axis]["single_input_repair_feasible"] is False
        assert rows[weak_axis]["repair_needs"] is None
    repaired = HIDDEN_WEAK[:3] + [rows["x4"]["repair_needs"] + 1e-6]
    assert nine.admit(repaired)["admit"] is True
    assert nine.admit(HIDDEN_WEAK[:3] + [rows["x4"]["repair_needs"] - 1e-4])["admit"] is False


@pytest.mark.parametrize("weights", [None, [3.0, 1.0, 1.0, 1.0], [0.5, 2.0, 1.0, 4.0]])
def test_admit_floors_are_exact_break_points(weights):
    claim = _decision(h.vector_horizon(NOMINAL, weights))
    assert claim["admit"] is True
    for row in claim["floors"]:
        i = int(row["evidence"][1:]) - 1
        at_floor = list(NOMINAL)
        at_floor[i] = row["admit_floor_exact"]
        assert _gm(at_floor, weights) == pytest.approx(nine.POLICY_TAU, rel=1e-12)
        below = list(NOMINAL)
        below[i] = row["admit_floor_exact"] * (1 - 1e-6)
        assert nine.admit(below, weights=weights)["admit"] is False


def test_heaviest_weight_has_the_smallest_relative_allowance():
    claim = _decision(h.vector_horizon(NOMINAL, [4.0, 1.0, 1.0, 1.0]))
    allowance = {row["evidence"]: row["relative_drop_allowed"] for row in claim["floors"]}
    assert min(allowance, key=allowance.get) == "x1"


# --- horizons --------------------------------------------------------------------------------

def test_decay_horizon_is_the_exact_threshold_crossing():
    halves = [3600.0, 600.0, 86400.0, 7200.0]
    weights = [1.0, 2.0, 1.0, 1.0]
    claim = _decision(h.vector_horizon(NOMINAL, weights, [{"half_life_s": t} for t in halves]))
    horizon = claim["horizon"]
    assert horizon["state"] == h.MODELED and horizon["cause"] == "decay"
    assert horizon["evidence"][0] == "x2"  # largest w * lambda drives the lapse
    t = horizon["seconds"]

    def at(seconds):
        return [x * math.exp(-math.log(2) / hl * seconds) for x, hl in zip(NOMINAL, halves)]

    assert _gm(at(t), weights) == pytest.approx(nine.POLICY_TAU, rel=1e-6)
    assert nine.admit(at(t * 0.999), weights=weights)["admit"] is True
    assert nine.admit(at(t * 1.001), weights=weights)["admit"] is False


def test_hard_expiry_wins_when_it_comes_first():
    decay = [{"half_life_s": 1e6}, {"expires_in_s": 42.0}, {"static": True}, {"static": True}]
    horizon = _decision(h.vector_horizon(NOMINAL, None, decay))["horizon"]
    assert horizon == {"state": h.MODELED, "seconds": 42.0, "cause": "expiry", "evidence": ["x2"]}


def test_undeclared_freshness_is_unknown_never_infinite():
    decay = [{"expires_in_s": 300.0}, {}, {"static": True}, {"half_life_s": 1e9}]
    horizon = _decision(h.vector_horizon(NOMINAL, None, decay))["horizon"]
    assert horizon["state"] == h.UNKNOWN
    assert horizon["seconds"] is None
    assert horizon["undeclared"] == ["x2"]
    assert horizon["upper_bound_s"] == 300.0


def test_unknown_without_any_declared_bound_has_no_upper_bound():
    horizon = _decision(h.vector_horizon(NOMINAL))["horizon"]
    assert horizon["state"] == h.UNKNOWN and horizon["upper_bound_s"] is None


def test_all_static_evidence_declares_no_lapse():
    horizon = _decision(h.vector_horizon(NOMINAL, None, [{"static": True}] * 4))["horizon"]
    assert horizon["state"] == h.NO_DECLARED_LAPSE and horizon["seconds"] is None


def test_zero_evidence_is_already_denied():
    claim = _decision(h.vector_horizon([0.95, 0.0, 0.9, 0.9]))
    assert claim["status"] == nine.DENY
    assert claim["horizon"] == {"state": h.ALREADY_DENIED, "seconds": 0.0,
                                "cause": "zero_evidence", "evidence": ["x2"]}


# --- DAG: linearity, gating and counterfactuals -----------------------------------------------

def _random_dag(seed):
    rng = random.Random(seed)
    leaves = [f"e{i}" for i in range(8)]
    evidence = {e: {"score": rng.uniform(0.6, 1.0), "half_life_s": rng.uniform(600, 86400)} for e in leaves}
    claims, nodes = {}, list(leaves)
    for i in range(6):
        kids = rng.sample(nodes, rng.randint(2, 4))
        claims[f"c{i}"] = {"children": {k: rng.uniform(0.5, 3.0) for k in kids}, "tau": 0.6}
        nodes.append(f"c{i}")
    return {"evidence": evidence, "claims": claims}


@pytest.mark.parametrize("seed", range(12))
def test_dag_scores_match_the_recursive_gm_and_coefficients_sum_to_one(seed):
    graph = _random_dag(seed)
    ev, cl = h._parse(graph)
    coef = h._coefficients(ev, cl)
    scores = h._scores(ev, cl)
    for node, row in coef.items():
        assert sum(row.values()) == pytest.approx(1.0, abs=1e-12)
        direct = math.exp(sum(a * math.log(ev[j]["score"]) for j, a in row.items()))
        assert direct == pytest.approx(scores[node], rel=1e-12)
    h.analyze(graph)  # internal linear-vs-direct assertion must hold


@pytest.mark.parametrize("seed", range(12))
def test_dag_floors_and_horizons_are_exact_for_admitted_claims(seed):
    graph = _random_dag(seed)
    for claim in h.analyze(graph)["claims"]:
        if not claim["admit"]:
            continue
        for row in claim["floors"]:
            changed = copy.deepcopy(graph)
            changed["evidence"][row["evidence"]]["score"] = row["admit_floor_exact"] * (1 + 1e-9)
            assert _status(changed, claim["claim"]) == nine.ADMITTED
            changed["evidence"][row["evidence"]]["score"] = row["admit_floor_exact"] * (1 - 1e-6)
            assert _status(changed, claim["claim"]) == nine.DENY
        t = claim["horizon"]["seconds"]
        assert _status(_decayed(graph, t * 0.999), claim["claim"]) == nine.ADMITTED
        assert _status(_decayed(graph, t * 1.001), claim["claim"]) == nine.DENY


def _status(graph, node):
    return next(c["status"] for c in h.analyze(graph)["claims"] if c["claim"] == node)


def _decayed(graph, seconds):
    out = copy.deepcopy(graph)
    for spec in out["evidence"].values():
        spec["score"] *= math.exp(-math.log(2) / spec["half_life_s"] * seconds)
    return out


GATED = {
    "evidence": {
        "build": {"score": 0.99, "static": True},
        "tests": {"score": 0.97, "static": True},
        "scan": {"score": 0.62, "expires_in_s": 900.0},
        "review": {"score": 0.99, "half_life_s": 86400.0},
    },
    "claims": {
        "supply_chain": {"children": {"build": 1.0, "scan": 1.0}},
        "release": {"children": {"supply_chain": 1.0, "tests": 3.0, "review": 3.0}},
    },
}


def test_parent_is_denied_when_a_child_claim_is_denied_even_if_its_own_gm_admits():
    by_id = {c["claim"]: c for c in h.analyze(GATED)["claims"]}
    assert by_id["supply_chain"]["status"] == nine.DENY  # GM(0.99, 0.62) = 0.783 < 0.80
    release = by_id["release"]
    assert release["gate"] == {"own_rule_admits": True, "denied_child_claims": ["supply_chain"]}
    assert release["status"] == nine.DENY
    assert release["horizon"]["cause"] == "child_claim_denied"


def test_gated_horizon_is_the_earliest_lapse_along_the_chain():
    graph = copy.deepcopy(GATED)
    graph["evidence"]["scan"]["score"] = 0.9
    by_id = {c["claim"]: c for c in h.analyze(graph)["claims"]}
    assert by_id["supply_chain"]["horizon"]["seconds"] == 900.0
    release = by_id["release"]
    assert release["status"] == nine.ADMITTED
    assert release["horizon"]["seconds"] <= 900.0
    assert release["horizon"]["evidence"]


def test_withdrawal_is_a_veto_and_reports_every_admitted_ancestor():
    graph = copy.deepcopy(GATED)
    graph["evidence"]["scan"]["score"] = 0.9
    result = h.counterfactual(graph, {"scan": 0.0})
    assert result["lost_support"] == ["release", "supply_chain"]
    assert result["regained_support"] == []
    assert h.counterfactual(graph, {"review": 0.98})["lost_support"] == []
    assert result["receipt_minted"] is False


# --- fail closed, read path, determinism ----------------------------------------------------

@pytest.mark.parametrize("graph", [
    {"evidence": {"a": {"score": 0.9}}, "claims": {"c": {"children": {"c": 1.0}}}},
    {"evidence": {"a": {"score": 0.9}}, "claims": {"c": {"children": {"d": 1.0}}, "d": {"children": {"c": 1.0}}}},
    {"evidence": {"a": {"score": 0.9}}, "claims": {"c": {"children": {"ghost": 1.0}}}},
    {"evidence": {"a": {"score": 1.2}}, "claims": {"c": {"children": {"a": 1.0}}}},
    {"evidence": {"a": {"score": float("nan")}}, "claims": {"c": {"children": {"a": 1.0}}}},
    {"evidence": {"a": {"score": True}}, "claims": {"c": {"children": {"a": 1.0}}}},
    {"evidence": {"a": {"score": 0.9}}, "claims": {"c": {"children": {"a": -1.0}}}},
    {"evidence": {"a": {"score": 0.9}}, "claims": {"c": {"children": {"a": 1.0}, "tau": 0}}},
    {"evidence": {"a": {"score": 0.9, "static": True, "half_life_s": 60}}, "claims": {"c": {"children": {"a": 1}}}},
    {"evidence": {"a": {"score": 0.9, "half_life_s": 0}}, "claims": {"c": {"children": {"a": 1}}}},
    {"evidence": {"a": {"score": 0.9, "expires_in_s": -1}}, "claims": {"c": {"children": {"a": 1}}}},
    {"evidence": {"a": {"score": 0.9, "trust": 1.0}}, "claims": {"c": {"children": {"a": 1}}}},
    {"evidence": {"a": {"score": 0.9}}, "claims": {"a": {"children": {"a": 1}}}},
    {"evidence": {}, "claims": {"c": {"children": {"a": 1}}}},
    {"evidence": {"a": {"score": 0.9}}, "claims": {}, "admit": True},
])
def test_unanalysable_input_fails_closed(graph):
    with pytest.raises(h.HorizonContractError):
        h.analyze(graph)


def test_counterfactual_rejects_unknown_or_invalid_changes():
    with pytest.raises(h.HorizonContractError):
        h.counterfactual(GATED, {"ghost": 0.0})
    with pytest.raises(h.HorizonContractError):
        h.counterfactual(GATED, {"scan": 1.5})


def test_read_path_never_signs_or_grants():
    report = h.analyze(GATED)
    assert report["receipt_minted"] is False and report["label"] == h.MODELED
    text = json.dumps(report)
    for token in ('"ALLOW"', '"LIVE"', "VERIFIED", "signature"):
        assert token not in text


def test_input_digest_is_stable_under_key_order():
    shuffled = {"claims": dict(reversed(list(GATED["claims"].items()))),
                "evidence": dict(reversed(list(GATED["evidence"].items())))}
    assert h.analyze(shuffled)["input_sha256"] == h.analyze(GATED)["input_sha256"]


# --- live storage-status binding -----------------------------------------------------------

# Shape and values from GET https://a-11-oy.com/api/a11oy/v1/storage/status, 2026-11-19 05:3x UTC.
STORAGE_STATUS = {
    "schema": "szl.a11oy-storage-status/v2", "mode": "FENCED", "role": "WRITER", "writable": True,
    "lease": {"state": "ACTIVE", "sequence": 23664, "heartbeat_age_s": 24.5},
    "stores": {
        "gdw": {"health": "OK", "last_snapshot_age_s": 390.0, "unsnapshotted_change_age_s": 353.0},
        "series_a": {"health": "OK", "last_snapshot_age_s": 27.5, "unsnapshotted_change_age_s": None},
        "khipu": {"health": "OK", "last_snapshot_age_s": 62.1, "unsnapshotted_change_age_s": None},
        "khipu_council": {"health": "OK", "last_snapshot_age_s": 321.5, "unsnapshotted_change_age_s": None},
    },
    "alert": False, "alert_after_s": 900.0,
}


def test_storage_status_horizon_is_unknown_because_the_lease_bound_is_unpublished():
    claim = _decision(h.analyze(h.evidence_from_storage_status(STORAGE_STATUS)))
    assert claim["status"] == nine.ADMITTED
    horizon = claim["horizon"]
    assert horizon["state"] == h.UNKNOWN
    assert horizon["undeclared"] == ["lease:heartbeat"]
    assert horizon["upper_bound_s"] == 510.0  # 900 - 390: the server's own alert deadline for gdw
    assert horizon["cause"] == "expiry" and horizon["evidence"] == ["store:gdw"]


def test_storage_status_ignores_snapshot_age_when_not_writable():
    status = copy.deepcopy(STORAGE_STATUS)
    status["writable"] = False
    graph = h.evidence_from_storage_status(status)
    assert graph["evidence"]["store:gdw"]["expires_in_s"] == 900.0 - 353.0
    assert graph["evidence"]["store:series_a"]["expires_in_s"] == 900.0


def test_storage_status_unhealthy_store_denies():
    status = copy.deepcopy(STORAGE_STATUS)
    status["stores"]["khipu"]["health"] = "BLOCKED"
    claim = _decision(h.analyze(h.evidence_from_storage_status(status)))
    assert claim["status"] == nine.DENY
    assert claim["horizon"]["evidence"] == ["store:khipu"]


def test_storage_status_rejects_other_schemas():
    with pytest.raises(h.HorizonContractError):
        h.evidence_from_storage_status({"schema": "szl.a11oy-storage-status/v1", "alert_after_s": 900, "stores": {}})
