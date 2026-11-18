# SPDX-License-Identifier: Apache-2.0
"""Source-backed but uncalibrated radical-pair simulation invariants."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_flavin_spin_research as spin


def test_spin_basis_and_projectors_are_valid():
    np = pytest.importorskip("numpy")
    _, _, _, ps, pt, _, _, eye = spin._spin_operators()
    assert np.allclose(ps @ ps, ps, atol=1e-12)
    assert np.allclose(pt @ pt, pt, atol=1e-12)
    assert np.allclose(ps @ pt, np.zeros((8, 8)), atol=1e-12)
    assert np.allclose(ps + pt, eye, atol=1e-12)
    assert np.isclose(np.trace(ps), 2)
    assert np.isclose(np.trace(pt), 6)


def test_default_is_modeled_only_with_explicit_parameters_and_sources():
    result = spin.simulate()
    assert result["schema"] == spin.SCHEMA
    assert result["state"] == "MODELED"
    assert result["claims_verified"] is False
    assert result["execution_authorized"] is False
    assert result["verification_scope"] == "NUMERICAL_INVARIANTS_ONLY"
    assert result["inputs"]["parameter_origin"] == "ILLUSTRATIVE_NOT_EXPERIMENTALLY_FITTED"
    assert result["sources"]["review"].endswith("10.0044249")
    assert "not an instrument measurement" not in result["boundaries"]  # no fabricated instrument claim
    assert "no measured flavin rates" in result["boundaries"]
    assert "no quantum advantage" in result["boundaries"]
    assert len(result["results"]) == 3
    assert result["conservation_max_absolute_residual"] < 1e-9
    assert result["singlet_yield_angular_contrast"] > 0


def test_geomagnetic_larmor_period_is_from_electron_gyromagnetic_ratio():
    result = spin.simulate(B_uT=50.0, steps=70, dt_us=0.01)
    period = result["earth_field_electron_larmor_period_ns"]
    assert 700 < period < 730  # condition in review, not a measured SCRP lifetime
    zero = spin.simulate(B_uT=0, steps=70, dt_us=0.01)
    assert zero["earth_field_electron_larmor_period_ns"] is None


@pytest.mark.parametrize("field", [0.0, 25.0, 50.0, 75.0])
@pytest.mark.parametrize("gamma_st", [0.0, 0.2, 3.0])
def test_positivity_and_product_plus_survival_conservation(field, gamma_st):
    result = spin.simulate(
        B_uT=field, angles_deg=(0, 45, 90),
        gamma_st_per_us=gamma_st, steps=100, dt_us=0.02,
    )
    assert result["conservation_max_absolute_residual"] < 1e-9
    for row in result["results"]:
        assert row["minimum_surviving_density_eigenvalue"] >= -1e-10
        assert all(0 <= row[key] <= 1.0 + 1e-8 for key in (
            "singlet_product_probability",
            "triplet_product_probability",
            "surviving_pair_probability",
        ))
        assert abs(
            row["singlet_product_probability"]
            + row["triplet_product_probability"]
            + row["surviving_pair_probability"] - 1.0
        ) < 1e-9


def test_no_hyperfine_no_flip_preserves_initial_electron_singlet():
    result = spin.simulate(
        B_uT=90, angles_deg=(0, 30, 90, 180),
        hyperfine_xy_MHz=0, hyperfine_z_MHz=0,
        gamma_st_per_us=0, gamma_flip_per_us=0,
        k_s_per_us=1, k_t_per_us=2,
        dt_us=0.01, steps=300,
    )
    target = -math.expm1(-3)
    for row in result["results"]:
        assert abs(row["singlet_product_probability"] - target) < 1e-9
        assert abs(row["triplet_product_probability"]) < 1e-10
    assert result["singlet_yield_angular_contrast"] < 1e-9


def test_isotropic_hyperfine_cannot_create_angular_compass():
    result = spin.simulate(
        hyperfine_xy_MHz=1, hyperfine_z_MHz=1,
        angles_deg=(0, 45, 90, 180), steps=220, dt_us=0.02,
    )
    assert result["singlet_yield_angular_contrast"] < 1e-9


def test_zero_field_cannot_create_an_orientation_effect():
    result = spin.simulate(B_uT=0, angles_deg=(0, 15, 90, 180),
                           steps=200, dt_us=0.02)
    assert result["singlet_yield_angular_contrast"] < 1e-9


def test_strong_phase_dephasing_reduces_contrast_for_this_declared_fixture():
    free = spin.simulate(gamma_st_per_us=0, steps=320, dt_us=0.02)
    noisy = spin.simulate(gamma_st_per_us=5, steps=320, dt_us=0.02)
    assert free["singlet_yield_angular_contrast"] > noisy["singlet_yield_angular_contrast"]
    assert all(row["probability_mass_residual"] < 1e-9 for row in noisy["results"])


def test_flip_noise_is_distinct_from_singlet_triplet_dephasing():
    a = spin.simulate(gamma_flip_per_us=0, steps=300, dt_us=0.02)
    b = spin.simulate(gamma_flip_per_us=2, steps=300, dt_us=0.02)
    assert abs(a["results"][0]["singlet_product_probability"]
               - b["results"][0]["singlet_product_probability"]) > .01


def test_step_refinement_yields_same_model_with_convergence():
    coarse = spin.simulate(dt_us=0.02, steps=500)
    fine = spin.simulate(dt_us=0.01, steps=1000)
    assert coarse["inputs"]["time_window_us"] == fine["inputs"]["time_window_us"]
    for left, right in zip(coarse["results"], fine["results"]):
        assert abs(left["singlet_product_probability"]
                   - right["singlet_product_probability"]) < 1e-4


@pytest.mark.parametrize("inputs", [
    {"B_uT": -1}, {"B_uT": 1e99},
    {"B_uT": float("nan")}, {"B_uT": True},
    {"angles_deg": ""}, {"angles_deg": "0,,90"},
    {"angles_deg": (0, 210)}, {"angles_deg": (0,)*8},
    {"angles_deg": [[1]]}, {"hyperfine_z_MHz": -1},
    {"hyperfine_xy_MHz": float("inf")},
    {"exchange_MHz": 3}, {"k_s_per_us": 0}, {"k_t_per_us": -1},
    {"gamma_st_per_us": -0.2}, {"gamma_flip_per_us": float("inf")},
    {"steps": -1}, {"steps": 1201}, {"steps": True}, {"steps": "500"},
    {"dt_us": -1}, {"dt_us": 0.1}, {"dt_us": float("nan")},
    {"steps": 1200, "angles_deg": (0,30,45,60,90,120)},
    {"steps": 100, "dt_us": .05, "k_s_per_us": 20},
    {"steps": 200, "dt_us": .05, "hyperfine_z_MHz": 5},
])
def test_out_of_scope_model_inputs_fail_closed(inputs):
    with pytest.raises(spin.InputHold):
        spin.simulate(**inputs)


def test_missing_numpy_is_unavailable_not_a_fake_reduced_model(monkeypatch):
    monkeypatch.setattr(spin, "np", None)
    with pytest.raises(spin.InputHold, match="NUMPY_UNAVAILABLE"):
        spin.simulate()


def test_http_registration_live_shape_and_no_read_side_effects():
    app = FastAPI()
    path = spin.register(app)
    with TestClient(app) as client:
        routes = client.get("/openapi.json").json()["paths"]
        assert path in routes and "get" in routes[path]
        a = client.get(path)
        b = client.get(path)
        assert a.status_code == b.status_code == 200
        assert a.headers["cache-control"] == "no-store"
        payload = a.json()
        assert payload == b.json()  # no runtime counters/timestamps or mutation
        assert payload["state"] == "MODELED"
        assert not payload["claims_verified"]
        assert "signature" not in payload
        assert "receipt_id" not in payload
        assert client.post(path).status_code == 405


@pytest.mark.parametrize("query", [
    "?angles=",
    "?angles=0,,90",
    "?angles=0,NaN",
    "?angles=0,45,200",
    "?B_uT=-1",
    "?B_uT=nan",
    "?dt_us=0.03&k_s_per_us=20",
    "?steps=999999999999",
    "?steps=12.5",
    "?B_uT=50&B_uT=70",
    "?arbitrary_input=sensor_verified",
])
def test_http_rejects_bad_queries_without_leaking_internal_details(query):
    app = FastAPI()
    path = spin.register(app)
    with TestClient(app) as client:
        response = client.get(path + query)
        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
        item = response.json()
        assert item["state"] == "UNAVAILABLE"
        assert item["execution_authorized"] is False
        assert "traceback" not in response.text.lower()
        assert "MODEL" not in item.get("status", "")


def test_http_missing_numpy_reports_explicit_503(monkeypatch):
    app = FastAPI()
    path = spin.register(app)
    monkeypatch.setattr(spin, "np", None)
    with TestClient(app) as client:
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["reason"] == "NUMPY_UNAVAILABLE"


def test_docker_and_source_registration_are_bound_before_spa_catchall():
    root = Path(__file__).resolve().parents[1]
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    serve = (root / "serve.py").read_text(encoding="utf-8")
    page = (root / "pages/command-v2.html").read_text(encoding="utf-8")
    assert " szl_flavin_spin_research.py " in docker
    assert "import szl_flavin_spin_research as" in serve
    assert serve.index("import szl_flavin_spin_research as") < serve.index("SPA catch-all", serve.index("import szl_flavin_spin_research as"))
    assert '/api/a11oy/v1/qbio/flavin-spin-research' in page
    assert 'Flavin spin research' in page


def test_content_digest_covers_exact_model_parameters_but_is_not_a_signature():
    first = spin.simulate(steps=65, dt_us=0.01)
    same = spin.simulate(steps=65, dt_us=0.01)
    different = spin.simulate(steps=65, dt_us=0.01, B_uT=60)
    assert first == same
    assert first["digest_sha256"] != different["digest_sha256"]
    assert first["digest_semantics"] == "UNSIGNED_CONTENT_HASH_ONLY"
    data = {k: v for k, v in first.items() if k not in ("digest_sha256", "digest_semantics")}
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == first["digest_sha256"]
    assert "signature" not in first


def test_http_oversized_query_is_rejected_before_parsing():
    app = FastAPI()
    path = spin.register(app)
    with TestClient(app) as client:
        result = client.get(path + "?angles=" + "0," * 500)
        assert result.status_code == 422
        assert result.json()["reason"] == "QUERY_TOO_LARGE"
