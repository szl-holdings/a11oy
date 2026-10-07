#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Governance contract for the materials-property predictor (szl_materials_predict).

Doctrine v11: receipt-on-WRITE, never on read; honest BLOCKED beats fake green.
Every signer / ledger / Khipu module the predictor imports lazily is replaced by a
COUNTING double installed in sys.modules before the module under test is
(re)loaded, so nothing in this file signs, writes a ledger, emits a receipt, fits
on a read path or touches the network. Lambda = Conjecture 1 and the
locked-proven count is 8; this file asserts both and changes neither.

Both mounted prefixes are exercised: /api/a11oy/v1/materials and /v1/materials.
"""
import importlib
import json
import math
import sys
import types

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

PREFIXES = ("/api/a11oy/v1/materials", "/v1/materials")
JSON_HDR = {"content-type": "application/json"}

MALFORMED_COUNTS = {
    "nan": '{"composition":{"Mg":NaN,"O":1}}',
    "inf": '{"composition":{"Mg":Infinity,"O":1}}',
    "neg_inf": '{"composition":{"Mg":-Infinity,"O":1}}',
    "bool": '{"composition":{"Mg":true,"O":true}}',
    "negative": '{"composition":{"Mg":1,"O":1,"Fe":-5}}',
    "overflow_10_pow_400": '{"composition":{"Mg":1' + "0" * 400 + ',"O":1}}',
    "zero_total": '{"composition":{"Mg":0,"O":0}}',
    "string_count": '{"composition":{"Mg":"one","O":1}}',
    "list_count": '{"composition":{"Mg":[1],"O":1}}',
    "empty_composition": '{"composition":{}}',
    "composition_not_object": '{"composition":[["Mg",1]]}',
}

MALFORMED_SPECS = {
    "property_band_gap": {"composition": {"Mg": 1, "O": 1}, "property": "band_gap"},
    "property_not_string": {"composition": {"Mg": 1, "O": 1}, "property": 5},
    "sign_not_bool": {"composition": {"Mg": 1, "O": 1}, "options": {"sign": "yes"}},
    "radius_negative": {"composition": {"Mg": 1, "O": 1}, "options": {"radius_m": -1}},
    "radius_zero": {"composition": {"Mg": 1, "O": 1}, "options": {"radius_m": 0}},
    "radius_bool": {"composition": {"Mg": 1, "O": 1}, "options": {"radius_m": True}},
    "energy_string": {"composition": {"Mg": 1, "O": 1}, "options": {"energy_j": "big"}},
    "options_not_object": {"composition": {"Mg": 1, "O": 1}, "options": "sign"},
    "unknown_demo": {"demo": "nope"},
    "demo_not_string": {"demo": {"x": 1}},
}


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
        real_matrices = self.mp._build_matrices

        def counting_matrices():
            # _build_matrices runs exactly once per real fit (inside _build's
            # uncached branch), so it is the honest "a fit happened" counter.
            self.counts["fit"] += 1
            return real_matrices()

        monkeypatch.setattr(self.mp, "_build_matrices", counting_matrices)
        self.app = FastAPI()
        self.routes = self.mp.register(self.app, ns="a11oy")
        self.client = TestClient(self.app)

    def _install_fakes(self, monkeypatch):
        counts = self.counts
        dsse = types.ModuleType("szl_dsse")

        def sign_payload(payload, payload_type=None):
            counts["sign"] += 1
            json.dumps(payload, allow_nan=False)  # a real signer canonicalizes JSON
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

    def post_raw(self, prefix, raw):
        return self.client.post(prefix + "/predict", content=raw, headers=JSON_HDR)


@pytest.fixture
def h(monkeypatch):
    return Harness(monkeypatch)


def _assert_400_shape(resp):
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert isinstance(body["error"], str) and body["error"]
    assert body["honesty"]["locked_proven_count"] == 8
    assert "Conjecture 1" in body["honesty"]["lambda"]
    assert "receipt" not in body and "ledger" not in body


# ---------------------------------------------------------------------------
# Malformed input: HTTP 400, no fit, no sign, no ledger, no emit (MAT-F05).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("case", sorted(MALFORMED_COUNTS))
def test_malformed_counts_are_400_and_inert(h, prefix, case):
    resp = h.post_raw(prefix, MALFORMED_COUNTS[case])
    _assert_400_shape(resp)
    h.assert_inert()


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("case", sorted(MALFORMED_SPECS))
def test_malformed_property_options_demo_are_400_and_inert(h, prefix, case):
    resp = h.client.post(prefix + "/predict", json=MALFORMED_SPECS[case])
    _assert_400_shape(resp)
    h.assert_inert()


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("raw", ["{}", "null", "[1,2]", "this is not json", "", '"demo"'])
def test_empty_or_non_object_body_is_400_not_a_demo(h, prefix, raw):
    resp = h.post_raw(prefix, raw)
    _assert_400_shape(resp)
    assert resp.json()["error"] == "supply {composition} or {demo}"
    h.assert_inert()


# ---------------------------------------------------------------------------
# Read paths are inert (MAT-F07): GET /predict is 405, GET /health never fits.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", PREFIXES)
def test_get_predict_is_405_with_allow_post_and_no_side_effects(h, prefix):
    resp = h.client.get(prefix + "/predict")
    assert resp.status_code == 405
    assert resp.headers.get("allow") == "POST"
    body = resp.json()
    assert body["ok"] is False
    assert body["usage"]["method"] == "POST"
    assert "verdict" not in body and "receipt" not in body
    h.assert_inert()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_get_health_never_fits_and_reports_not_built(h, prefix):
    resp = h.client.get(prefix + "/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True  # szl_engine_status 'skeleton' probe stays reachable
    assert body["calibration"] == {
        "state": "NOT_BUILT",
        "note": "health never fits; built on first POST /predict",
    }
    assert body["honesty"]["locked_proven_count"] == 8
    assert "measured_coverage" not in body["honesty"]
    h.assert_inert()
    # a second poll is still inert
    h.client.get(prefix + "/health")
    h.assert_inert()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_health_after_a_real_post_reports_the_calibration(h, prefix):
    assert h.client.post(prefix + "/predict", json={"demo": "green"}).status_code == 200
    assert h.built is True and h.counts["fit"] == 1
    body = h.client.get(prefix + "/health").json()
    cal = body["calibration"]
    assert "state" not in cal
    assert cal["measured_coverage_n"] == 420
    assert cal["measured_coverage"] == pytest.approx(0.9619, abs=1e-4)
    assert h.counts["fit"] == 1  # health reads the cached state, it does not refit


# ---------------------------------------------------------------------------
# Valid writes still work and side effects are exactly accounted for.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", PREFIXES)
def test_valid_post_signs_once_ledgers_once_and_carries_sanitized_counts(h, prefix):
    resp = h.client.post(prefix + "/predict", json={"composition": {"Mg": 1, "O": 1, "Fe": 0}})
    assert resp.status_code == 200
    assert resp.headers.get("x-szl-materials-verdict") == "GREEN"
    body = resp.json()
    assert body["ok"] is True and body["verdict"] == "GREEN"
    # exact-zero count = absent species; response and receipt carry the sanitized counts
    assert body["composition"] == {"Mg": 1.0, "O": 1.0}
    assert body["receipt"]["payload"]["composition"] == {"Mg": 1.0, "O": 1.0}
    assert body["receipt"]["signed"] is True
    assert body["ledger"]["recorded"] is True
    assert body["receipt"]["payload"]["doctrine"]["locked_proven_count"] == 8
    assert body["receipt"]["payload"]["doctrine"]["lambda"] == "Conjecture 1"
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}
    assert h.built is True
    json.dumps(body, allow_nan=False)  # strict JSON all the way down


@pytest.mark.parametrize("prefix", PREFIXES)
def test_sign_false_skips_the_signer_but_the_ledger_write_stays(h, prefix):
    # Current, documented behaviour: options.sign=false drops the DSSE envelope
    # only; the governed state change (the ledger write) still happens once.
    resp = h.client.post(prefix + "/predict",
                         json={"composition": {"Mg": 1, "O": 1}, "options": {"sign": False}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt"]["signed"] is False
    assert "dsse" not in body["receipt"]
    assert body["ledger"]["recorded"] is True
    assert h.counts == {"sign": 0, "ledger": 1, "emit": 0, "fit": 1}


@pytest.mark.parametrize("prefix", PREFIXES)
def test_unknown_element_refusal_is_still_red_with_a_receipt(h, prefix):
    resp = h.client.post(prefix + "/predict", json={"composition": {"Xx": 1, "O": 1}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["verdict"] == "RED"
    assert body["refusal"].startswith("OUT-OF-DISTRIBUTION: element 'Xx' is outside")
    assert body["value"] is None and body["interval95"] is None
    assert body["composition"] == {"Xx": 1.0, "O": 1.0}
    assert body["receipt"]["payload"]["verdict"] == "RED"
    assert body["receipt"]["signed"] is True
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}


@pytest.mark.parametrize("prefix", PREFIXES)
def test_non_finite_internal_value_fails_closed_without_signing(h, monkeypatch, prefix):
    # Defence in depth behind _validate_spec: inject a NaN downstream of validation
    # and check that nothing is signed or ledgered and the response says why.
    real = h.mp.compute_lambda

    def poisoned(*a, **k):
        out = real(*a, **k)
        out["value"] = float("nan")
        return out

    monkeypatch.setattr(h.mp, "compute_lambda", poisoned)
    resp = h.client.post(prefix + "/predict", json={"composition": {"Mg": 1, "O": 1}})
    assert resp.status_code == 500
    body = resp.json()
    assert body["ok"] is False and body["fail_closed"] is True
    assert "refusing to sign or ledger" in body["error"]
    assert h.counts["sign"] == 0 and h.counts["ledger"] == 0 and h.counts["emit"] == 0


# ---------------------------------------------------------------------------
# Regression vectors: the current demo outputs, observed with the fakes installed
# (MODELED + SAMPLE surrogate values; pinned so the governance work changes none).
# ---------------------------------------------------------------------------
def test_demo_green_regression_vector(h):
    body = h.client.post(PREFIXES[0] + "/predict", json={"demo": "green"}).json()
    assert body["verdict"] == "GREEN"
    assert body["composition"] == {"Mg": 1.0, "O": 1.0}
    assert body["value_eV_atom"] == pytest.approx(-2.39825, abs=2e-4)
    lo, hi = body["interval95_eV_atom"]
    assert lo == pytest.approx(-3.79417, abs=2e-4)
    assert hi == pytest.approx(-1.00232, abs=2e-4)
    assert body["ensemble_sigma_eV_atom"] == pytest.approx(0.11165, abs=2e-4)
    assert body["ood_score"] == pytest.approx(0.0, abs=1e-6)
    assert body["lambda_advisory"]["value"] == pytest.approx(0.8972, abs=2e-4)
    assert body["lambda_advisory"]["status"] == "ADVISORY"
    assert body["convex_hull_gate"]["delta_hull_eV_atom"] == pytest.approx(-2.39825, abs=2e-4)
    cal = body["calibration"]
    assert cal["measured_coverage_n"] == 420 and cal["dataset_n"] == 52
    assert cal["target_coverage"] == pytest.approx(0.95)
    assert cal["measured_coverage"] == pytest.approx(0.9619, abs=1e-4)
    assert cal["uncalibrated_coverage"] == pytest.approx(0.631, abs=1e-4)
    assert body["honesty"]["locked_proven"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]


def test_demo_ood_regression_vector(h):
    body = h.client.post(PREFIXES[1] + "/predict", json={"demo": "ood"}).json()
    assert body["verdict"] == "RED"
    assert body["value_eV_atom"] is None and body["interval95_eV_atom"] is None
    assert body["ood_score"] == pytest.approx(2.3853, abs=2e-4)
    assert body["refusal"].startswith("descriptor is OUT-OF-DISTRIBUTION")
    assert h.counts == {"sign": 1, "ledger": 1, "emit": 0, "fit": 1}


def test_fe2o3_regression_vector(h):
    body = h.client.post(PREFIXES[0] + "/predict", json={"composition": {"Fe": 2, "O": 3}}).json()
    assert body["verdict"] == "GREEN"
    assert body["value_eV_atom"] == pytest.approx(-1.76008, abs=2e-4)
    assert body["convex_hull_gate"]["delta_hull_eV_atom"] == pytest.approx(-0.21075, abs=2e-4)


# ---------------------------------------------------------------------------
# Pure helpers: the validation layer is side-effect free and tells the two
# refusal kinds apart.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("comp", [
    {"Mg": float("nan"), "O": 1},
    {"Mg": float("inf"), "O": 1},
    {"Mg": True, "O": True},
    {"Mg": 1, "O": 1, "Fe": -5},
    {"Mg": 10 ** 400, "O": 1},
    {"Mg": 0, "O": 0},
    {"Mg": 1e308, "O": 1e308},  # finite counts, non-finite total
    {},
    [("Mg", 1)],
])
def test_normalize_comp_raises_invalid_composition_error(h, comp):
    exc = getattr(h.mp, "InvalidCompositionError", None)
    assert exc is not None and issubclass(exc, ValueError)
    with pytest.raises(exc):
        h.mp._normalize_comp(comp)
    h.assert_inert()


def test_normalize_comp_unknown_element_is_a_plain_value_error(h):
    exc = getattr(h.mp, "InvalidCompositionError", None)
    with pytest.raises(ValueError) as ei:
        h.mp._normalize_comp({"Xx": 1, "O": 1})
    assert exc is not None and not isinstance(ei.value, exc)
    assert "outside the embedded SAMPLE element table" in str(ei.value)


def test_normalize_comp_drops_exact_zero_and_keeps_fractions(h):
    frac = h.mp._normalize_comp({"Mg": 1, "O": 1, "Fe": 0, "Al": -0.0})
    assert frac == {"Mg": 0.5, "O": 0.5}
    assert h.mp._normalize_comp({"Al": 2, "O": 3}) == pytest.approx({"Al": 0.4, "O": 0.6})


def test_validate_spec_is_pure_and_normalizes(h):
    validate = getattr(h.mp, "_validate_spec", None)
    assert validate is not None
    out = validate({"demo": "green"})
    assert out == {"property": "formation_energy", "composition": {"Mg": 1.0, "O": 1.0},
                   "options": {"sign": True, "radius_m": 1.0, "energy_j": 1.0}}
    out = validate({"composition": {"Xx": 2, "O": 0}, "options": {"sign": False, "radius_m": 2}})
    assert out["composition"] == {"Xx": 2.0}  # unknown element passes through to the RED path
    assert out["options"] == {"sign": False, "radius_m": 2.0, "energy_j": 1.0}
    for bad in ({}, None, [], {"composition": None}, {"property": "formation_energy"}):
        with pytest.raises(ValueError):
            validate(bad)
    assert math.isfinite(out["options"]["radius_m"])
    h.assert_inert()


def test_predict_property_direct_call_rejects_before_building(h):
    out = h.mp.predict_property({"composition": {"Mg": float("nan"), "O": 1}})
    assert out["ok"] is False and "receipt" not in out
    out = h.mp.predict_property(None)
    assert out["ok"] is False and out["error"] == "supply {composition} or {demo}"
    h.assert_inert()
