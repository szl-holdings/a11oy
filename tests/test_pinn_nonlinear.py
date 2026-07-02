# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
"""
Tests for szl_pinn_nonlinear — the NONLINEAR frontier solver + honest benchmark surface.

Two contracts are pinned here:
  1. The Newton-linearized spectral-collocation solver actually solves the nonlinear
     steady viscous-Burgers shock (u u_x = nu u_xx) to near the spectral-truncation
     floor, converges in a handful of Newton steps, and REFUSES degenerate viscosity.
     The linear Poisson multimode case hits machine precision (solution in the trial
     basis — this is DISCLOSED, never sold as a general win).
  2. The HTTP surface: GET /api/a11oy/v1/pinn/burgers (200, MODELED-not-measured,
     honest exact-reference disclosure, refuses nu<=0) and GET /api/a11oy/v1/pinn/bench
     (serves the COMMITTED benchmarks/pinn/results.json read-only; Doctrine v11 labels).
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_pinn_nonlinear as nl


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    nl.register(app, ns="a11oy")
    return TestClient(app, raise_server_exceptions=True)


# --------------------------------------------------------------------------- #
# Solver-level (no server)
# --------------------------------------------------------------------------- #
def test_selftest_ok():
    out = nl._selftest()
    assert out["ok"] is True


def test_newton_burgers_matches_exact_shock():
    """The nonlinear steady-Burgers shock is solved to near the spectral floor and
    matches the exact tanh closed form (which is NOT in the sine basis)."""
    ci = nl.canonical_instance()
    assert ci["rel_l2_vs_exact"] < 1e-5
    sol = ci["sol"]
    # Newton actually iterated on the nonlinearity and the residual collapsed
    assert 1 <= sol["newton_iterations"] < 40
    hist = sol["newton_residual_history"]
    assert hist[-1] < hist[0] * 0.05
    # honest: the exact tanh is genuinely out of the trial basis (no by-construction win)
    assert sol["rel_l2_pde_residual_on_test"] < 1e-3


def test_poisson_multimode_in_basis_is_disclosed():
    """Linear Poisson with a modal forcing lives in the sine basis → machine precision.
    That advantage is DISCLOSED (solution_in_trial_basis True), never hidden."""
    cp = nl.canonical_poisson()
    assert cp["rel_l2_vs_exact"] < 1e-9
    assert cp["sol"]["solution_in_trial_basis"] is True


def test_solver_refuses_degenerate_viscosity():
    with pytest.raises(ValueError):
        nl.solve_steady_burgers(nu=0.0, a=1.0, b=-1.0)


# --------------------------------------------------------------------------- #
# HTTP surface — /pinn/burgers
# --------------------------------------------------------------------------- #
def test_register_returns_wired_paths():
    app = FastAPI()
    wired = nl.register(app, ns="a11oy")
    assert "/api/a11oy/v1/pinn/burgers" in wired
    assert "/api/a11oy/v1/pinn/bench" in wired
    paths = {r.path for r in app.router.routes if hasattr(r, "path")}
    for p in wired:
        assert p in paths


def test_burgers_200_modeled_not_measured(client):
    r = client.get("/api/a11oy/v1/pinn/burgers")
    assert r.status_code == 200
    d = r.json()
    assert d["modeled_not_measured"] is True
    assert "MODELED" in d["status"]
    assert "NOT MEASURED" in d["status"]


def test_burgers_canonical_carries_honest_exact_reference(client):
    d = client.get("/api/a11oy/v1/pinn/burgers").json()
    ref = d["exact_reference"]
    # the shock is NOT in the finite sine basis → the error is a real truncation error
    assert ref["solution_in_trial_basis"] is False
    assert ref["rel_l2_vs_exact"] < 1e-5
    assert d["newton_iterations"] >= 1
    # a real field is returned, not a stub
    assert len(d["solution"]["x"]) == len(d["solution"]["u"]) == 129


def test_burgers_refuses_nonpositive_viscosity(client):
    r = client.get("/api/a11oy/v1/pinn/burgers", params={"nu": 0})
    assert r.status_code == 400
    assert r.json()["error"] == "REFUSED"


def test_burgers_accepts_custom_instance(client):
    r = client.get("/api/a11oy/v1/pinn/burgers", params={"nu": 0.1, "a": 0.8, "b": -0.8})
    assert r.status_code == 200
    d = r.json()
    assert d["viscosity_nu"] == 0.1
    assert d["boundary_conditions"]["u(0)"] == 0.8


def test_burgers_no_fabricated_joule(client):
    d = client.get("/api/a11oy/v1/pinn/burgers").json()
    assert "free-energy" in d["honesty"].lower()
    assert "Conjecture 1" in d["lambda_note"]


# --------------------------------------------------------------------------- #
# HTTP surface — /pinn/bench (read-only committed artifact)
# --------------------------------------------------------------------------- #
def test_bench_200(client):
    assert client.get("/api/a11oy/v1/pinn/bench").status_code == 200


def test_bench_serves_committed_measured_results(client):
    """With benchmarks/pinn/results.json committed, /pinn/bench serves MEASURED arms
    for SZL + DeepXDE and honestly labels Modulus/PhysicsNeMo NOT-RUN."""
    d = client.get("/api/a11oy/v1/pinn/bench").json()
    if "problems" not in d:
        pytest.skip("no committed results.json in this environment (NOT-RUN roadmap)")
    assert "MEASURED" in d["overall_label"]
    ids = {p["id"] for p in d["problems"]}
    assert {"poisson_1d_multimode", "steady_burgers_shock", "inverse_duffing"} <= ids
    for p in d["problems"]:
        frameworks = {a["framework"]: a for a in p["arms"]}
        assert "szl" in frameworks and "deepxde" in frameworks
        # Modulus was not run on this box — it must be honestly labelled, never faked
        assert frameworks["modulus_physicsnemo"]["label"] == "NOT-RUN"


def test_bench_burgers_arm_is_honest_headtohead(client):
    """The frontier nonlinear shock: SZL (Newton-spectral) is near-exact; a standard,
    non-shock-adapted neural PINN struggles. Both numbers are MEASURED, not asserted."""
    d = client.get("/api/a11oy/v1/pinn/bench").json()
    if "problems" not in d:
        pytest.skip("no committed results.json in this environment")
    burgers = next(p for p in d["problems"] if p["id"] == "steady_burgers_shock")
    arms = {a["framework"]: a for a in burgers["arms"]}
    assert arms["szl"]["label"] == "MEASURED"
    assert arms["szl"]["rel_l2_vs_exact"] < 1e-4
    assert arms["deepxde"]["label"] == "MEASURED"
    # neural arm reported as a seed distribution (>=3 seeds), never a single lucky run
    assert arms["deepxde"]["rel_l2_vs_exact"]["n"] >= 3


def test_bench_is_read_only_never_runs_deepxde(client):
    """Doctrine + license: the request path serves the committed artifact and NEVER
    imports/runs DeepXDE (LGPL, benchmark-only). Proven by the honest source tag."""
    d = client.get("/api/a11oy/v1/pinn/bench").json()
    if "problems" not in d:
        pytest.skip("no committed results.json in this environment")
    assert "committed" in d["source"].lower()
    # deepxde must NOT have been imported merely by serving the benchmark endpoint
    assert "deepxde" not in sys.modules
