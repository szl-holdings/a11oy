#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Calibration lifecycle and hull decision boundary of szl_materials_predict
(MAT-F01..F04; DBG-M01/M02).

What is pinned here:
  * split-conformal rank/radius: k = ceil((n+1)(1-alpha)); k > n is UNBOUNDED
    (math.inf) and the predictor ABSTAINS instead of serving max|z|;
  * the calibration artifact binds the calibrator to the served predictor by a
    sha256 over its fitted coefficients; a stale hash fails closed;
  * the convex-hull gate: unknown or inapplicable hull evidence is never
    favorable (no GREEN for a ternary, an endpoints-only binary, or a None delta);
  * honest wording: no deep-ensemble or isotonic coverage claim; every coverage
    number on the wire carries its protocol label;
  * a demo regression table (option A: served numbers are unchanged, MgO's
    verdict is YELLOW, the green demo is Fe2O3).

Signer / ledger / Khipu modules are COUNTING test doubles installed in
sys.modules before the module under test is reloaded; nothing signs, writes a
ledger, emits a receipt or touches the network. Lambda = Conjecture 1 and the
locked-proven count is 8; this file asserts both and changes neither.
"""
import importlib
import copy
import inspect
import json
import math
import re
import sys
import types

import numpy as np
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

PREFIXES = ("/api/a11oy/v1/materials", "/v1/materials")
HULL_NA = "hull gate not applicable - plausibility unverified"
ABSTAIN = "calibration set too small for a finite split-conformal interval"
ALPHA = 0.05


class Harness:
    """Fresh module + fresh app per test, with side-effect counters."""

    def __init__(self, monkeypatch):
        self.counts = {"sign": 0, "ledger": 0, "emit": 0, "fit": 0}
        self._install_fakes(monkeypatch)
        if "szl_materials_predict" in sys.modules:
            self.mp = importlib.reload(sys.modules["szl_materials_predict"])
        else:
            self.mp = importlib.import_module("szl_materials_predict")
        assert self.mp._STATE.get("built") is False
        self.real_matrices = self.mp._build_matrices

        def counting_matrices():
            self.counts["fit"] += 1
            return self.real_matrices()

        monkeypatch.setattr(self.mp, "_build_matrices", counting_matrices)
        self.monkeypatch = monkeypatch
        self.app = FastAPI()
        self.routes = self.mp.register(self.app, ns="a11oy")
        self.client = TestClient(self.app)

    def _install_fakes(self, monkeypatch):
        counts = self.counts
        dsse = types.ModuleType("szl_dsse")

        def sign_payload(payload, payload_type=None):
            counts["sign"] += 1
            json.dumps(payload, allow_nan=False)
            return {"payloadType": payload_type, "payload": "FAKE",
                    "signatures": [{"sig": "FAKE-TEST-DOUBLE-NOT-A-SIGNATURE"}]}

        dsse.sign_payload = sign_payload
        lake = types.ModuleType("szl_lake_ingest")

        def record_receipt(receipt, organ="a11oy"):
            counts["ledger"] += 1
            return {"accepted": True, "test_double": True}

        lake.record_receipt = record_receipt
        khipu = types.ModuleType("szl_khipu")

        class _Dag:
            def emit(self, action, payload=None):
                counts["emit"] += 1
                return {"digest": "FAKE", "seq": 0}

        khipu.get_dag = lambda organ, ns="a11oy": _Dag()
        monkeypatch.setitem(sys.modules, "szl_dsse", dsse)
        monkeypatch.setitem(sys.modules, "szl_lake_ingest", lake)
        monkeypatch.setitem(sys.modules, "szl_khipu", khipu)

    @property
    def built(self):
        return bool(self.mp._STATE.get("built"))

    def assert_inert(self):
        assert self.counts == {"sign": 0, "ledger": 0, "emit": 0, "fit": 0}, self.counts
        assert self.built is False

    def post(self, body, prefix=PREFIXES[0]):
        return self.client.post(prefix + "/predict", json=body)

    def shrink_dataset(self, n_rows):
        """Make the next build fit on the first n_rows embedded records only."""
        real = self.real_matrices

        def small():
            self.counts["fit"] += 1
            X, y = real()
            return X[:n_rows], y[:n_rows]

        self.monkeypatch.setattr(self.mp, "_build_matrices", small)


@pytest.fixture
def h(monkeypatch):
    return Harness(monkeypatch)


def _hull_reason(body):
    return [r for r in body.get("gate_reasons", []) if r.startswith(HULL_NA)]


# ---------------------------------------------------------------------------
# Split-conformal fixtures on sorted scores (pure _Calibrator; MAT-F03).
# ---------------------------------------------------------------------------
def test_n18_alpha05_is_unbounded_and_n19_is_rank_19(h):
    cal18 = h.mp._Calibrator(np.arange(1, 19, dtype=float))  # |z| = 1..18
    assert cal18.conformal_rank(ALPHA) == {"n_calibration": 18, "rank_k": 19, "unbounded": True}
    assert cal18.conformal_radius(ALPHA) == math.inf
    assert cal18.interval(0.0, 1.0, ALPHA) == (-math.inf, math.inf)
    cal19 = h.mp._Calibrator(np.arange(1, 20, dtype=float))  # |z| = 1..19
    assert cal19.conformal_rank(ALPHA) == {"n_calibration": 19, "rank_k": 19, "unbounded": False}
    assert cal19.conformal_radius(ALPHA) == 19.0  # the 19th smallest |z|
    assert cal19.interval(0.5, 2.0, ALPHA) == (0.5 - 38.0, 0.5 + 38.0)
    h.assert_inert()


def test_small_sample_returns_inf_not_max_abs_z(h):
    # The exact MAT-F03 probe: n=5, alpha=0.05 -> k=6 > 5. Before the fix this
    # returned max|z| = 1.0 and the served interval looked finite and calibrated.
    cal = h.mp._Calibrator(np.linspace(-1.0, 1.0, 5))
    assert cal.conformal_radius(ALPHA) == math.inf
    assert cal.conformal_rank(ALPHA)["unbounded"] is True
    assert float(np.max(cal.abs_z)) == 1.0
    assert h.mp._Calibrator([]).conformal_radius(ALPHA) == math.inf
    assert h.mp._Calibrator([]).conformal_rank(ALPHA) == {"n_calibration": 0, "rank_k": 1,
                                                          "unbounded": True}


@pytest.mark.parametrize("alpha", [0.05, 0.1, 0.2, 0.5])
def test_rank_matches_ceil_formula_over_a_sweep(h, alpha):
    rng = np.random.default_rng(99)
    for n in range(1, 61):
        z = rng.normal(size=n) * 3.0
        cal = h.mp._Calibrator(z)
        k = int(math.ceil((n + 1) * (1.0 - alpha)))
        rk = cal.conformal_rank(alpha)
        assert rk["rank_k"] == k and rk["unbounded"] is (k > n)
        r = cal.conformal_radius(alpha)
        if k > n:
            assert r == math.inf
        else:
            assert r == float(np.sort(np.abs(z))[k - 1])


def test_tied_scores_and_zero_scale(h):
    tied = h.mp._Calibrator(np.full(19, 0.7))
    assert tied.conformal_radius(ALPHA) == 0.7
    two_level = h.mp._Calibrator(np.array([0.3] * 20 + [-0.9] * 20))  # n=40 -> k=39
    assert two_level.conformal_rank(ALPHA)["rank_k"] == 39
    assert two_level.conformal_radius(ALPHA) == 0.9
    zero = h.mp._Calibrator(np.zeros(25))  # zero scale: every score is 0
    assert zero.conformal_radius(ALPHA) == 0.0
    assert zero.interval(-2.5, 0.4, ALPHA) == (-2.5, -2.5)
    # sigma is clamped to 1e-6, never 0, so a degenerate interval still has a width
    lo, hi = tied.interval(1.0, 0.0, ALPHA)
    assert hi - lo == pytest.approx(2 * 0.7 * 1e-6)


@pytest.mark.parametrize("alpha", [0, 1, -0.1, 1.5, float("nan"), float("inf"), True, "0.05",
                                   None])
def test_invalid_alpha_raises(h, alpha):
    cal = h.mp._Calibrator(np.arange(1, 30, dtype=float))
    with pytest.raises(ValueError):
        cal.conformal_rank(alpha)
    with pytest.raises(ValueError):
        cal.conformal_radius(alpha)
    with pytest.raises(ValueError):
        cal.interval(0.0, 1.0, alpha)


# ---------------------------------------------------------------------------
# Abstain end-to-end: an unbounded radius is RED with interval None (MAT-F03).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", PREFIXES)
def test_predict_abstains_when_the_calibration_set_is_too_small(h, prefix):
    h.shrink_dataset(18)  # n=18, alpha=0.05 -> k=19 > 18
    resp = h.post({"composition": {"Fe": 2, "O": 3}}, prefix)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["verdict"] == "RED"
    assert body["refusal"].startswith(ABSTAIN)
    assert body["value_eV_atom"] is None and body["interval95_eV_atom"] is None
    assert body["interval_is_calibrated"] is False
    art = body["calibration_artifact"]
    assert art["n_calibration"] == 18 and art["rank_k"] == 19 and art["unbounded"] is True
    assert art["radius_abs_z"] is None
    cal = body["calibration"]
    assert cal["measured_coverage"] is None and cal["measured_coverage_n"] == 0
    assert cal["coverage_note"].startswith("NOT_RUN")
    assert cal["serving_protocol_coverage"] is None
    assert "UNBOUNDED" in cal["interval_method"]
    assert "measured_coverage" not in body["honesty"]  # no number we did not measure
    # a governed RED verdict still carries exactly one receipt, like the OOD refusal
    assert body["receipt"]["payload"]["refusal"].startswith(ABSTAIN)
    assert body["receipt"]["payload"]["calibration_artifact"]["unbounded"] is True
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}
    json.dumps(body, allow_nan=False)
    health = h.client.get(prefix + "/health").json()
    assert health["calibration_artifact"]["unbounded"] is True
    assert h.counts["fit"] == 1


# ---------------------------------------------------------------------------
# Calibration artifact: pure helpers and the end-to-end binding (MAT-F01).
# ---------------------------------------------------------------------------
def test_validate_calibration_artifact_is_pure_and_rejects_a_stale_hash(h):
    X, y = h.real_matrices()
    surr = h.mp._Surrogate(X[:20], y[:20], seed=3)
    cal = h.mp._Calibrator(h.mp._residuals(surr, X[:20], y[:20]))
    art = h.mp.build_calibration_artifact(surr, cal, ALPHA, "data-hash", {"note": "test"})
    own = h.mp._predictor_hash(surr)
    def validate(artifact, predictor_hash, data_hash=None):
        return h.mp.validate_calibration_artifact(
            artifact, predictor_hash, data_hash, calibrator=cal, alpha=ALPHA)
    assert art["predictor_hash"] == own and art["data_hash"] == "data-hash"
    assert art["n_calibration"] == 20 and art["rank_k"] == 20 and art["unbounded"] is False
    assert validate(art, own)["valid"] is True
    assert validate(art, own, "data-hash")["valid"] is True
    assert h.mp.validate_calibration_artifact(art, own)["valid"] is False
    refit = h.mp._Surrogate(X[:20], y[:20], seed=4)
    stale = validate(art, h.mp._predictor_hash(refit))
    assert stale["valid"] is False and "stale predictor_hash" in stale["reason"]
    assert validate(art, own, "other-data")["valid"] is False
    assert validate(None, own)["valid"] is False
    assert validate(dict(art, schema="x"), own)["valid"] is False
    broken = dict(art)
    del broken["rank_k"]
    assert validate(broken, own)["valid"] is False
    # the hash is a function of the fitted coefficients + config, nothing else
    assert h.mp._predictor_hash(h.mp._Surrogate(X[:20], y[:20], seed=3)) == own
    assert h.mp._predictor_hash(refit) != own
    assert re.fullmatch(r"[0-9a-f]{64}", own)
    assert re.fullmatch(r"[0-9a-f]{64}", h.mp._data_hash())
    assert h.mp._data_hash() == h.mp._data_hash(h.mp._DATASET)
    h.assert_inert()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_artifact_fields_present_and_bound_to_the_served_predictor(h, prefix):
    body = h.post({"demo": "green"}, prefix).json()
    art = body["calibration_artifact"]
    for key in ("schema", "predictor_hash", "data_hash", "protocol", "protocol_description",
                "split_ids", "score_definition", "alpha", "n_calibration", "rank_k",
                "unbounded", "radius_abs_z", "evaluation_provenance", "calibration_state_hash"):
        assert key in art, key
    assert art["schema"] == "szl.materials.calibration_artifact/v1"
    assert art["predictor_hash"] == h.mp._predictor_hash(h.mp._STATE["surr"])
    assert art["data_hash"] == h.mp._data_hash()
    assert art["protocol"] == "serving"
    assert art["split_ids"] == {"train": "embedded:all", "calibration": "embedded:all (in-sample)",
                                "test": None}
    assert "ceil((n+1)(1-alpha))" in art["score_definition"]
    # P4 regression: the served calibrator is n=52 -> k=51, bounded, radius unchanged
    assert art["alpha"] == ALPHA and art["n_calibration"] == 52 and art["rank_k"] == 51
    assert art["unbounded"] is False
    assert art["radius_abs_z"] == pytest.approx(12.50311, abs=2e-4)
    prov = art["evaluation_provenance"]
    assert prov["unique_materials"] == 52
    assert prov["cv_split_models"]["trials"] == 60 and prov["cv_split_models"]["n_predictions"] == 420
    assert "not the served pair" in prov["cv_split_models"]["label"]
    assert prov["serving_protocol_holdout"]["unbounded_trials"] == 0
    # the same artifact is on health and (compact) in the receipt
    health = h.client.get(prefix + "/health").json()
    assert health["calibration_artifact"] == art
    compact = body["receipt"]["payload"]["calibration_artifact"]
    assert compact["predictor_hash"] == art["predictor_hash"]
    assert compact["data_hash"] == art["data_hash"]
    assert compact["calibration_state_hash"] == art["calibration_state_hash"]
    assert compact["radius_abs_z"] == art["radius_abs_z"]
    assert compact["rank_k"] == 51 and compact["unbounded"] is False
    assert h.counts["fit"] == 1


@pytest.mark.parametrize("prefix", PREFIXES)
def test_stale_predictor_fails_closed_without_signing(h, prefix):
    assert h.post({"demo": "green"}, prefix).status_code == 200
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}
    st = h.mp._STATE
    st["surr"] = h.mp._Surrogate(st["X"], st["y"], seed=8)  # a refit without recalibration
    resp = h.post({"composition": {"Fe": 2, "O": 3}}, prefix)
    assert resp.status_code == 500
    body = resp.json()
    assert body["ok"] is False and body["fail_closed"] is True
    assert "stale predictor_hash" in body["error"]
    assert "verdict" not in body and "receipt" not in body and "ledger" not in body
    assert "calibration_artifact" not in body  # unvalidated state is never echoed
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}  # nothing new signed


@pytest.mark.parametrize("prefix", PREFIXES)
def test_changed_calibration_metadata_fails_closed_before_receipt(h, prefix):
    assert h.post({"demo": "green"}, prefix).status_code == 200
    st = h.mp._STATE
    original = copy.deepcopy(st["artifact"])
    counts = dict(h.counts)
    changes = {"alpha": 0.9, "n_calibration": -1, "rank_k": -1,
               "unbounded": True, "radius_abs_z": 999999.0,
               "calibration_state_hash": "0" * 64, "protocol": "other"}
    for key, value in changes.items():
        st["artifact"] = dict(original, **{key: value})
        response = h.post({"demo": "green"}, prefix)
        assert response.status_code == 500, key
        body = response.json()
        assert body["fail_closed"] is True, key
        assert "receipt" not in body and "calibration_artifact" not in body
        assert h.counts == counts
    for key in ("alpha", "n_calibration", "rank_k", "unbounded", "radius_abs_z"):
        st["artifact"] = dict(original)
        del st["artifact"][key]
        response = h.post({"demo": "green"}, prefix)
        assert response.status_code == 500 and response.json()["fail_closed"] is True
        assert h.counts == counts
    for artifact in (None, [], dict(original, radius_abs_z=float("nan")),
                     dict(original, rank_k=True), dict(original, unbounded=0)):
        st["artifact"] = artifact
        response = h.post({"demo": "green"}, prefix)
        assert response.status_code == 500 and response.json()["fail_closed"] is True
        assert h.counts == counts


@pytest.mark.parametrize("prefix", PREFIXES)
def test_changed_calibrator_scores_and_level_fail_closed(h, prefix):
    assert h.post({"demo": "green"}, prefix).status_code == 200
    st = h.mp._STATE
    original = copy.deepcopy(st["cal"])
    counts = dict(h.counts)
    # A one-ulp change leaves the rounded radius unchanged. It must still be
    # detected, as must replacing every score or the diagnostic CDF.
    for kind in ("replace", "one_ulp", "cdf", "bad_count", "missing", "nonfinite", "unsorted"):
        cal = copy.deepcopy(original)
        if kind == "replace":
            cal.abs_z[:] = 0.0
        elif kind == "one_ulp":
            cal.abs_z[-1] = np.nextafter(cal.abs_z[-1], math.inf)
        elif kind == "cdf":
            cal.cdf_grid[:] = 0.0
        elif kind == "bad_count":
            cal.n = 1
        elif kind == "nonfinite":
            cal.abs_z[-1] = math.inf
        elif kind == "unsorted":
            cal.abs_z = cal.abs_z[::-1]
        st["cal"] = None if kind == "missing" else cal
        response = h.post({"demo": "green"}, prefix)
        assert response.status_code == 500 and response.json()["fail_closed"] is True, kind
        assert h.counts == counts
    st["cal"] = original
    h.monkeypatch.setattr(h.mp, "ALPHA", 0.1)
    response = h.post({"demo": "green"}, prefix)
    assert response.status_code == 500 and response.json()["fail_closed"] is True
    assert h.counts == counts


def test_changed_embedded_data_does_not_reuse_cached_hash(h):
    assert h.post({"demo": "green"}).status_code == 200
    counts = dict(h.counts)
    rows = list(h.mp._DATASET)
    comp, energy = rows[0]
    rows[0] = (comp, energy + 0.1)
    h.monkeypatch.setattr(h.mp, "_DATASET", rows)
    response = h.post({"demo": "green"})
    assert response.status_code == 500 and response.json()["fail_closed"] is True
    assert "stale data_hash" in response.json()["error"]
    assert h.counts == counts


def test_health_before_any_post_has_no_artifact_and_is_inert(h):
    body = h.client.get(PREFIXES[1] + "/health").json()
    assert body["ok"] is True
    assert body["calibration"]["state"] == "NOT_BUILT"
    assert body["calibration_artifact"] is None
    assert "deep-ensemble" not in body["model"] and "split-conformal" in body["model"]
    assert "never GREEN" in body["gates"]["convex_hull"]
    assert "abstain" in body["gates"]["calibration"]
    assert "Fe2O3" in body["demos"]["green"] and "YELLOW" in body["demos"]["note"]
    h.assert_inert()


# ---------------------------------------------------------------------------
# Hull decision boundary: unknown hull evidence is never favorable (MAT-F04).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("comp", [{"Mg": 1, "Al": 1, "O": 2}, {"Ca": 1, "Al": 1, "F": 3},
                                  {"Li": 1, "Na": 1, "Cl": 2}, {"Fe": 1, "Mn": 1, "O": 2}])
def test_ternary_is_never_green(h, prefix, comp):
    body = h.post({"composition": comp}, prefix).json()
    assert body["ok"] is True and body["verdict"] != "GREEN"
    hull = body["convex_hull_gate"]
    assert hull["applicable"] is False and hull["delta_hull_eV_atom"] is None
    assert hull["competing_phases"] == 0 and "BINARY" in hull["reason"]
    assert "delta_hull" not in hull  # the legacy mismatched key is gone
    assert body["hull_checked"] is False
    assert body["lambda_advisory"]["factors"]["hull"] == 0.2
    if body["verdict"] == "YELLOW":
        assert _hull_reason(body)


def test_endpoints_only_binary_is_never_green(h):
    mp = h.mp
    endpoints_only = []
    for c, _ in mp._DATASET:
        frac = mp._normalize_comp(c)
        a, b = sorted(frac)
        competing = sum(1 for c2, _ in mp._DATASET
                        if set(mp._normalize_comp(c2)) == {a, b}
                        and abs(mp._normalize_comp(c2)[b] - frac[b]) > 1e-3)
        if competing == 0:
            endpoints_only.append(c)
    assert {"Mg": 1, "O": 1} in endpoints_only and {"Al": 2, "O": 3} in endpoints_only
    assert len(endpoints_only) >= 30
    for c in endpoints_only:
        body = h.post({"composition": c}).json()
        hull = body["convex_hull_gate"]
        assert body["verdict"] != "GREEN", c
        assert hull["applicable"] is False and hull["delta_hull_eV_atom"] is None
        assert hull["competing_phases"] == 0 and hull["same_composition_phases_excluded"] == 1
        assert math.isfinite(hull["delta_vs_elements_eV_atom"])  # informational only
        assert "no embedded competing phase" in hull["reason"]
        assert hull["hull_vertices"] == [[0.0, 0.0], [1.0, 0.0]]
        assert body["hull_checked"] is False
        assert body["lambda_advisory"]["factors"]["hull"] == 0.2
        if body["verdict"] == "YELLOW":
            assert _hull_reason(body), c


@pytest.mark.parametrize("prefix", PREFIXES)
def test_mgo_is_yellow_with_the_reason_and_unchanged_numbers(h, prefix):
    resp = h.post({"composition": {"Mg": 1, "O": 1}}, prefix)
    assert resp.headers.get("x-szl-materials-verdict") == "YELLOW"
    body = resp.json()
    assert body["verdict"] == "YELLOW"
    reasons = _hull_reason(body)
    assert len(reasons) == 1 and "Mg-O" in reasons[0]
    # option A: the served numbers did not move, only the verdict did
    assert body["value_eV_atom"] == pytest.approx(-2.39825, abs=2e-4)
    lo, hi = body["interval95_eV_atom"]
    assert lo == pytest.approx(-3.79417, abs=2e-4) and hi == pytest.approx(-1.00232, abs=2e-4)
    hull = body["convex_hull_gate"]
    assert hull["applicable"] is False and hull["competing_phases"] == 0
    assert hull["delta_vs_elements_eV_atom"] == pytest.approx(-2.39825, abs=2e-4)
    assert body["lambda_advisory"]["factors"] == {"label": 0.6, "in_distribution": 1.0,
                                                  "uncertainty": pytest.approx(0.7999, abs=2e-4),
                                                  "hull": 0.2}
    assert body["receipt"]["payload"]["verdict"] == "YELLOW"
    assert body["receipt"]["payload"]["hull_checked"] is False


@pytest.mark.parametrize("prefix", PREFIXES)
def test_demo_green_is_fe2o3_green_with_competing_phases(h, prefix):
    body = h.post({"demo": "green"}, prefix).json()
    assert body["verdict"] == "GREEN" and body["composition"] == {"Fe": 2.0, "O": 3.0}
    hull = body["convex_hull_gate"]
    assert hull["applicable"] is True and hull["competing_phases"] == 2
    assert hull["system"] == "Fe-O" and hull["same_composition_phases_excluded"] == 1
    assert hull["delta_hull_eV_atom"] == pytest.approx(-0.21075, abs=2e-4)
    assert hull["e_hull_eV_atom"] == pytest.approx(-1.54933, abs=2e-4)
    assert body["hull_checked"] is True
    assert body["lambda_advisory"]["factors"]["hull"] == 0.9
    assert body["gate_reasons"] == ["in-distribution, on/near hull vs 2 embedded competing "
                                    "phase(s), calibrated interval — plausible"]
    assert not _hull_reason(body)
    assert h.mp._DEMOS["green"]["composition"] == {"Fe": 2, "O": 3}


def test_every_green_dataset_composition_has_a_checked_hull(h):
    greens = []
    for c, _ in h.mp._DATASET:
        body = h.post({"composition": c}).json()
        if body["verdict"] == "GREEN":
            hull = body["convex_hull_gate"]
            assert body["hull_checked"] is True and hull["applicable"] is True
            assert hull["competing_phases"] >= 1
            assert hull["delta_hull_eV_atom"] <= h.mp.HULL_GREEN
            greens.append(json.dumps(c, sort_keys=True))
    assert sorted(greens) == sorted(json.dumps(c, sort_keys=True) for c in (
        {"Ti": 1, "O": 2}, {"Fe": 2, "O": 3}, {"Fe": 3, "O": 4},
        {"Mn": 1, "O": 1}, {"Mn": 1, "O": 2}, {"Mn": 2, "O": 3}))


@pytest.mark.parametrize("delta", [None, float("nan"), float("inf")])
def test_a_missing_or_non_finite_delta_is_never_favorable(h, monkeypatch, delta):
    real = h.mp.convex_hull_distance

    def poisoned(comp, e_pred):
        out = real(comp, e_pred)
        out["applicable"] = True  # claims applicability but carries no usable delta
        out["delta_hull_eV_atom"] = delta
        return out

    monkeypatch.setattr(h.mp, "convex_hull_distance", poisoned)
    body = h.post({"composition": {"Fe": 2, "O": 3}}).json()
    if delta is None:
        assert body["ok"] is True and body["verdict"] == "YELLOW"
        assert body["hull_checked"] is False
        assert body["lambda_advisory"]["factors"]["hull"] == 0.2
        assert _hull_reason(body)
    else:
        # a non-finite number cannot be sealed: fail closed, nothing signed
        assert body["ok"] is False and body["fail_closed"] is True
        assert h.counts["sign"] == 0 and h.counts["ledger"] == 0


def test_convex_hull_distance_pure_helper(h):
    fe = h.mp.convex_hull_distance({"Fe": 2, "O": 3}, -1.76)
    assert fe["applicable"] is True and fe["competing_phases"] == 2
    assert fe["delta_hull_eV_atom"] == pytest.approx(-1.76 - fe["e_hull_eV_atom"], abs=1e-5)
    assert "delta_vs_elements_eV_atom" not in fe and "delta_hull" not in fe
    mg = h.mp.convex_hull_distance({"Mg": 1, "O": 1}, -2.4)
    assert mg["applicable"] is False and mg["delta_hull_eV_atom"] is None
    assert mg["competing_phases"] == 0 and mg["delta_vs_elements_eV_atom"] == -2.4
    assert "e_hull_eV_atom" not in mg
    tern = h.mp.convex_hull_distance({"Mg": 1, "Al": 1, "O": 2}, -2.2)
    assert tern["applicable"] is False and tern["delta_hull_eV_atom"] is None
    assert tern["competing_phases"] == 0 and tern["system"] == "Al-Mg-O"
    assert "3-element" in tern["reason"]
    for d in (fe, mg, tern):
        assert d["thresholds"] == {"green_max": 0.05, "red_max": 0.10}
        assert "never favorable" in d["note"]
    h.assert_inert()


def test_synthetic_lower_envelope_exact_endpoints_and_interpolation(h):
    hull_of = h.mp._lower_hull_points
    e_at = h.mp._hull_energy_at
    base = [(0.0, 0.0), (1.0, 0.0), (0.5, -2.0)]
    hull = hull_of(base)
    assert hull == [(0.0, 0.0), (0.5, -2.0), (1.0, 0.0)]
    assert e_at(hull, 0.0) == 0.0 and e_at(hull, 1.0) == 0.0  # exact endpoints
    assert e_at(hull, 0.5) == -2.0                            # exact vertex
    assert e_at(hull, 0.25) == pytest.approx(-1.0)             # linear interpolation
    assert e_at(hull, 0.75) == pytest.approx(-1.0)
    # a phase above the envelope is not a vertex; one below it is
    assert hull_of(base + [(0.25, -0.5)]) == hull
    assert hull_of(base + [(0.75, -1.5)]) == [(0.0, 0.0), (0.5, -2.0), (0.75, -1.5), (1.0, 0.0)]
    # exact duplicates collapse; two phases at one composition keep the lower one
    assert hull_of(base + [(0.5, -2.0)]) == hull
    poly = hull_of(base + [(0.5, -1.0)])
    assert e_at(poly, 0.5) == -2.0
    # a positive-energy "phase" never lowers the envelope below the endpoints
    assert hull_of([(0.0, 0.0), (1.0, 0.0), (0.5, 0.3)]) == [(0.0, 0.0), (1.0, 0.0)]
    assert e_at([(0.0, 0.0), (1.0, 0.0)], 0.37) == 0.0


# ---------------------------------------------------------------------------
# Honest wording (MAT-F02) and protocol-labelled coverage (MAT-F01, option A).
# ---------------------------------------------------------------------------
def test_module_strings_make_no_deep_ensemble_or_isotonic_coverage_claim(h):
    src = inspect.getsource(h.mp)
    assert "deep-ensemble" not in src
    assert "ISOTONIC" not in src
    assert "~95%" not in src
    lines = src.splitlines()
    markers = ("prior art", "Lakshminarayanan", "NOT a deep", "Deep Ensembles'")
    for i, line in enumerate(lines):
        if re.search(r"deep ensemble", line, re.IGNORECASE):
            window = " ".join(lines[max(0, i - 1):i + 2])
            assert any(m in window for m in markers), line
    for i, line in enumerate(lines):
        if "isotonic" in line.lower() and "def _isotonic_pav" not in line \
                and "_isotonic_pav(" not in line:
            window = " ".join(lines[max(0, i - 2):i + 3]).lower()
            assert "diagnostic" in window or "pool-adjacent" in window \
                or "monotone" in window or "pav" in window, line
    assert "bootstrap ridge (linear) ensemble" in src
    assert "split-conformal" in src
    assert h.mp.LOCKED_PROVEN == ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
    assert any("Lakshminarayanan" in c and "prior art" in c for c in h.mp.CITATIONS)
    assert any("Kuleshov" in c and "DIAGNOSTIC" in c for c in h.mp.CITATIONS)
    h.assert_inert()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_every_coverage_number_on_the_wire_carries_a_protocol_label(h, prefix):
    body = h.post({"demo": "green"}, prefix).json()
    cal = body["calibration"]
    coverage_keys = [k for k in cal if k.endswith("_coverage") and k != "target_coverage"]
    assert sorted(coverage_keys) == ["measured_coverage", "serving_protocol_coverage",
                                     "uncalibrated_coverage"]
    for k in coverage_keys:
        assert isinstance(cal[k + "_protocol"], str) and len(cal[k + "_protocol"]) > 40, k
    assert cal["measured_coverage_n"] == 420 and cal["serving_protocol_coverage_n"] == 420
    assert cal["unique_materials"] == 52 and cal["dataset_n"] == 52
    proto = cal["measured_coverage_protocol"]
    assert "60 repeated" in proto and "SPLIT models" in proto
    assert "not independent materials" in proto and "NOT the served" in proto
    sproto = cal["serving_protocol_coverage_protocol"]
    assert "60 trials holding out 7 of 52" in sproto and "IN-SAMPLE" in sproto
    assert "0 unbounded trial(s) excluded" in sproto
    meas = cal["coverage_measurement"]
    assert "in memory at build time" in meas and "ephemeral" in meas
    assert "cv 1234" in meas and "serving 4321" in meas
    assert "ridge (linear) ensemble" in cal["method"] and "diagnostic only" in cal["method"]
    assert "51-th smallest |z|" in cal["interval_method"]
    assert "split-conformal" in body["interval_method"] and "in-sample" in body["interval_method"]
    assert body["honesty"]["measured_coverage_protocol"] == "cv_split_models (see calibration block)"
    assert "in-sample" in body["honesty"]["calibration"].lower()
    assert "never favorable" in body["honesty"]["convex_hull_gate"]
    assert body["honesty"]["locked_proven_count"] == 8
    assert "Conjecture 1" in body["honesty"]["lambda"]
    rc = body["receipt"]["payload"]["calibration"]
    assert rc["measured_coverage_protocol"] == "cv_split_models"
    assert rc["serving_protocol_coverage_n"] == 420


def test_serving_protocol_coverage_is_measured_at_build_and_deterministic(h):
    body = h.post({"demo": "green"}).json()
    cal = body["calibration"]
    # MEASURED in this process at build time with a fixed seed; the CV number is
    # the existing one, the serving-protocol number is new and lower.
    assert cal["measured_coverage"] == pytest.approx(0.9619, abs=1e-4)
    assert cal["serving_protocol_coverage"] == pytest.approx(0.9333, abs=1e-4)
    assert cal["serving_protocol_coverage"] < cal["measured_coverage"]
    assert cal["uncalibrated_coverage"] == pytest.approx(0.631, abs=1e-4)
    assert cal["coverage_note"] is None
    st = h.mp._STATE
    again = h.mp._measure_coverage_serving(st["X"], st["y"])
    assert again == st["serving"]
    assert again["trials"] == 60 and again["unbounded_trials"] == 0 and again["n"] == 420
    assert again["holdout_per_trial"] == 7 and again["seed"] == 4321
    cv = h.mp._measure_coverage_cv(st["X"], st["y"])
    assert cv[0] == st["coverage"] and cv[1] == 420 and cv[3] == 60
    assert h.counts["fit"] == 1  # the direct calls above fit in memory but never rebuild
    assert h.mp._r4(None) is None and h.mp._r4(float("nan")) is None
    assert h.mp._r4(0.96191) == 0.9619


# ---------------------------------------------------------------------------
# Demo regression table (MODELED + SAMPLE values; option A: numbers unchanged).
# ---------------------------------------------------------------------------
TABLE = [
    # (request, verdict, value, interval, hull applicable, delta_hull, competing)
    ({"demo": "green"}, "GREEN", -1.76008, [-3.65398, 0.13382], True, -0.21075, 2),
    ({"composition": {"Fe": 2, "O": 3}}, "GREEN", -1.76008, [-3.65398, 0.13382], True, -0.21075, 2),
    ({"composition": {"Mg": 1, "O": 1}}, "YELLOW", -2.39825, [-3.79417, -1.00232], False, None, 0),
    ({"composition": {"Al": 2, "O": 3}}, "YELLOW", -2.21503, [-6.45378, 2.02371], False, None, 0),
    ({"composition": {"Ca": 1, "O": 1}}, "YELLOW", -2.60752, None, False, None, 0),
    ({"composition": {"Ti": 1, "O": 2}}, "GREEN", -2.77638, [-4.392, -1.16077], True, 0.04028, 2),
    ({"composition": {"Fe": 3, "O": 4}}, "GREEN", -1.65028, [-3.18322, -0.11733], True, -0.02171, 2),
    ({"composition": {"Mn": 1, "O": 1}}, "GREEN", -1.77704, [-2.58117, -0.97292], True, -0.15204, 2),
    ({"composition": {"Mg": 1, "Al": 1, "O": 2}}, "YELLOW", -2.25333, [-4.42207, -0.0846], False, None, 0),
    ({"demo": "ood"}, "RED", None, None, False, None, 0),
]


@pytest.mark.parametrize("req,verdict,value,interval,applicable,delta,competing", TABLE)
def test_demo_regression_table(h, req, verdict, value, interval, applicable, delta, competing):
    resp = h.post(req)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == verdict
    if value is None:
        assert body["value_eV_atom"] is None and body["interval95_eV_atom"] is None
    else:
        assert body["value_eV_atom"] == pytest.approx(value, abs=2e-4)
        if interval is not None:
            assert body["interval95_eV_atom"] == pytest.approx(interval, abs=2e-4)
    hull = body["convex_hull_gate"]
    assert hull["applicable"] is applicable and hull["competing_phases"] == competing
    if delta is None:
        assert hull["delta_hull_eV_atom"] is None
    else:
        assert hull["delta_hull_eV_atom"] == pytest.approx(delta, abs=2e-4)
    assert body["hull_checked"] is (applicable and delta is not None)
    assert (verdict == "GREEN") <= body["hull_checked"]  # GREEN implies a checked hull
    assert body["calibration_artifact"]["rank_k"] == 51
    assert body["honesty"]["locked_proven"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}
    json.dumps(body, allow_nan=False)


def test_unknown_element_refusal_keeps_its_receipt_and_carries_the_artifact(h):
    body = h.post({"composition": {"Xx": 1, "O": 1}}).json()
    assert body["verdict"] == "RED" and body["refusal"].startswith("OUT-OF-DISTRIBUTION")
    assert body["calibration_artifact"]["rank_k"] == 51
    assert body["receipt"]["payload"]["calibration_artifact"]["predictor_hash"] == \
        body["calibration_artifact"]["predictor_hash"]
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}


@pytest.mark.parametrize("prefix", PREFIXES)
def test_malformed_input_still_answers_400_without_an_artifact(h, prefix):
    resp = h.client.post(prefix + "/predict", content='{"composition":{"Mg":NaN,"O":1}}',
                         headers={"content-type": "application/json"})
    assert resp.status_code == 400
    assert "calibration_artifact" not in resp.json()
    h.assert_inert()
