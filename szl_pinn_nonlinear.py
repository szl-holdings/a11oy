#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. — SZL Holdings — ORCID 0009-0001-0110-4173
#
# szl_pinn_nonlinear.py — SZL Governed NONLINEAR spectral-collocation solver +
# honest cross-framework benchmark surface (a11oy frontier).
#
# Closes the "linear-only" gap in the SZL PINN/bounds mesh: the existing spectral
# solver (run_measured_pinn.py) handles the LINEAR Poisson BVP -u''=f; this module
# adds a NONLINEAR BVP solver via a Newton loop around the SAME least-squares
# spectral collocation, validated on the STEADY VISCOUS BURGERS equation, which has
# an EXACT closed-form traveling-shock solution. It also carries the shipped Poisson
# solver used as the SZL arm of the cross-framework benchmark, and serves the
# committed benchmark artifact at /pinn/bench (read-only).
#
# Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory only).
#
# OWN CODE / PERMISSIVE DEPS ONLY (NumPy BSD-3). No torch, no DeepXDE (LGPL),
# nothing proprietary is imported here. The benchmark HARNESS (benchmarks/pinn/
# run_bench.py) is the ONLY place DeepXDE is used, and it is a benchmark-only dev
# dependency — never imported by this module or serve.py. This endpoint only READS
# the committed results.json produced by that harness.
#
# THE NONLINEAR PDE (steady viscous Burgers, 1D BVP on [0,1]):
#       ν u''(x) − u(x) u'(x) = 0 ,   u(0)=a, u(1)=b
#   EXACT solution family (Cole-Hopf / Taylor viscous shock):
#       u*(x) = −C · tanh( C (x − x0) / (2ν) )
#   so a benchmark with a KNOWN ground truth is available: pick (C, x0, ν),
#   set a=u*(0), b=u*(1), and the exact field is known by construction.
#
# METHOD (Newton-linearized spectral collocation):
#   Trial u(x) = T(x) + Σ_{k=1..N} c_k sin(kπx),  T(x)=a+(b−a)x  (satisfies BCs;
#   the sine modes vanish at x=0,1 so the Dirichlet data is exact for any c).
#   Residual R = ν u'' − u u'. Newton step δ = Σ d_k sin(kπx) solves the LINEARISED
#   system  ν δ'' − (u δ' + δ u') = −R  at M interior collocation points by the SAME
#   least-squares solve used for the linear engine; update c += d until ‖R‖ → 0.
#
# HONEST LABELS: every returned field is MODELED (a numerical solution), never
# MEASURED. `rel_l2_vs_exact` is a REAL computed error against the closed form — it
# certifies the solver, it is not a physical measurement.

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:  # only needed when served under a Starlette/FastAPI app
    from starlette.requests import Request
    from starlette.responses import JSONResponse
except Exception:  # pragma: no cover - keep this module standalone-importable
    Request = object  # type: ignore
    JSONResponse = None  # type: ignore

try:  # reuse the shared doctrine strings for a consistent honesty envelope
    from szl_pinn_bounds import DOCTRINE, LAMBDA_NOTE  # type: ignore
except Exception:  # pragma: no cover
    DOCTRINE = ("No free energy. Every certified quantity is DERIVED from measured "
                "inputs or a closed-form model; nothing is fabricated.")
    LAMBDA_NOTE = ("Λ = Conjecture 1 — advisory only, NOT 'proven trust'.")

PI = math.pi

_RESULTS_PATHS = [
    "benchmarks/pinn/results.json",
    "/app/benchmarks/pinn/results.json",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmarks", "pinn", "results.json"),
]


# --------------------------------------------------------------------------- #
# Sine design matrix shared by both solvers
# --------------------------------------------------------------------------- #
def _design(xs: np.ndarray, N: int):
    """Return (S, Sp, Spp): the sine basis and its 1st/2nd derivatives at xs.
    S[j,k]=sin(kπx_j), Sp=kπcos(kπx_j), Spp=−(kπ)²sin(kπx_j)  (k=1..N)."""
    k = np.arange(1, N + 1, dtype=float)
    kp = k * PI
    arg = np.outer(xs, kp)
    S = np.sin(arg)
    Sp = np.cos(arg) * kp
    Spp = -S * (kp * kp)
    return S, Sp, Spp


# --------------------------------------------------------------------------- #
# LINEAR arm — Poisson multimode (SZL's shipped spectral method; same math as
# run_measured_pinn.py). NOTE (honest disclosure): when the exact solution is a
# finite sum of sine modes it lies INSIDE this trial basis, so the solver hits
# near machine precision BY CONSTRUCTION. That is a property of the problem, not a
# general accuracy claim — the benchmark artifact flags solution_in_trial_basis.
# --------------------------------------------------------------------------- #
def exact_poisson(x, modes: Dict[int, float]):
    x = np.asarray(x, dtype=float)
    return sum(c * np.sin(k * PI * x) for k, c in modes.items())


def solve_poisson_multimode(modes: Dict[int, float], N: int = 8, M: int = 64) -> Dict:
    """Solve -u''(x)=f(x) on [0,1], u(0)=u(1)=0 by sine-basis LS collocation,
    where f = Σ c_k (kπ)² sin(kπx) for the given modes {k: c_k}."""
    xs = np.array([(j + 1) / (M + 1) for j in range(M)], dtype=float)
    S, _, Spp = _design(xs, N)
    f = sum(c * (k * PI) ** 2 * np.sin(k * PI * xs) for k, c in modes.items())
    A = -Spp  # -u'' operator on the sine coefficients
    c, *_ = np.linalg.lstsq(A, f, rcond=None)
    xt = np.linspace(0.0, 1.0, 400)
    St, _, _ = _design(xt, N)
    u = St @ c
    ue = exact_poisson(xt, modes)
    rel = float(np.sqrt(np.sum((u - ue) ** 2) / np.sum(ue ** 2)))
    max_mode = max(modes)
    return {"coeffs": c, "N": N, "M": M, "modes": modes,
            "rel_l2_vs_exact": rel, "solution_in_trial_basis": bool(N >= max_mode)}


# --------------------------------------------------------------------------- #
# Exact reference for the NONLINEAR arm (closed form ground truth)
# --------------------------------------------------------------------------- #
def exact_shock(x, C: float, x0: float, nu: float):
    """u*(x) = −C·tanh(C(x−x0)/(2ν)) — exact steady viscous-Burgers shock."""
    x = np.asarray(x, dtype=float)
    return -C * np.tanh(C * (x - x0) / (2.0 * nu))


def exact_shock_deriv(x, C: float, x0: float, nu: float):
    x = np.asarray(x, dtype=float)
    th = np.tanh(C * (x - x0) / (2.0 * nu))
    return -(C * C) / (2.0 * nu) * (1.0 - th * th)


# --------------------------------------------------------------------------- #
# NONLINEAR arm — Newton-linearized spectral-collocation solver (own code)
# --------------------------------------------------------------------------- #
def solve_steady_burgers(nu: float, a: float, b: float,
                         N: int = 48, M: int = 240,
                         newton_iters: int = 40, tol: float = 1e-12) -> Dict:
    """Solve ν u'' − u u' = 0 on [0,1], u(0)=a, u(1)=b by Newton + spectral LS."""
    if not (nu > 0):
        raise ValueError("viscosity nu must be > 0")
    xs = np.array([(j + 1) / (M + 1) for j in range(M)], dtype=float)
    S, Sp, Spp = _design(xs, N)
    slope = (b - a)
    T = a + slope * xs
    Tp = np.full_like(xs, slope)

    c = np.zeros(N, dtype=float)
    res_hist: List[float] = []
    for _ in range(newton_iters):
        u = T + S @ c
        up = Tp + Sp @ c
        upp = Spp @ c
        R = nu * upp - u * up
        res_hist.append(float(np.max(np.abs(R))))
        A = nu * Spp - (u[:, None] * Sp + S * up[:, None])
        d, *_ = np.linalg.lstsq(A, -R, rcond=None)
        c = c + d
        if float(np.max(np.abs(d))) < tol:
            break
    xt = np.linspace(0.02, 0.98, 400)
    St, Spt, Sppt = _design(xt, N)
    ut = a + slope * xt + St @ c
    upt = slope + Spt @ c
    uppt = Sppt @ c
    Rt = nu * uppt - ut * upt
    max_res = float(np.max(np.abs(Rt)))
    rel_l2_res = float(np.sqrt(np.mean(Rt ** 2)) / (np.sqrt(np.mean(ut ** 2)) + 1e-30))
    return {"coeffs": c, "N": N, "M": M, "nu": nu, "a": a, "b": b, "slope": slope,
            "newton_residual_history": res_hist, "newton_iterations": len(res_hist),
            "max_pde_residual_on_test": max_res, "rel_l2_pde_residual_on_test": rel_l2_res}


def eval_solution(sol: Dict, x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    S, _, _ = _design(x, sol["N"])
    return sol["a"] + sol["slope"] * x + S @ sol["coeffs"]


def rel_l2_vs_exact(sol: Dict, C: float, x0: float, nu: float, npts: int = 400) -> float:
    x = np.linspace(0.0, 1.0, npts)
    u = eval_solution(sol, x)
    ue = exact_shock(x, C, x0, nu)
    return float(np.sqrt(np.sum((u - ue) ** 2) / np.sum(ue ** 2)))


# --------------------------------------------------------------------------- #
# Canonical benchmark instances (deterministic; used by endpoint + tests + bench)
# --------------------------------------------------------------------------- #
POISSON_MODES = {1: 1.0, 3: 0.5, 5: 0.2}
BURGERS_C, BURGERS_X0, BURGERS_NU = 1.0, 0.5, 0.05


def canonical_poisson() -> Dict:
    sol = solve_poisson_multimode(POISSON_MODES, N=8, M=64)
    return {"modes": POISSON_MODES, "sol": sol, "rel_l2_vs_exact": sol["rel_l2_vs_exact"]}


def canonical_instance() -> Dict:
    """Fixed, reproducible steady viscous-Burgers shock; BCs set from exact."""
    C, x0, nu = BURGERS_C, BURGERS_X0, BURGERS_NU
    a = float(exact_shock(0.0, C, x0, nu))
    b = float(exact_shock(1.0, C, x0, nu))
    sol = solve_steady_burgers(nu=nu, a=a, b=b, N=48, M=240)
    err = rel_l2_vs_exact(sol, C, x0, nu)
    return {"C": C, "x0": x0, "nu": nu, "a": a, "b": b, "sol": sol, "rel_l2_vs_exact": err}


# --------------------------------------------------------------------------- #
# HTTP surface
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _burgers_payload(nu: float, a: float, b: float, N: int,
                     ref: Optional[Dict] = None) -> Dict:
    sol = solve_steady_burgers(nu=nu, a=a, b=b, N=N)
    x = [i / 128.0 for i in range(129)]
    u = eval_solution(sol, np.array(x)).tolist()
    body = {
        "service": "a11oy.pinn.nonlinear.burgers",
        "status": "MODELED (numerical solution) — NOT MEASURED",
        "modeled_not_measured": True,
        "pde": "nu*u''(x) - u(x)*u'(x) = 0 on [0,1] (steady viscous Burgers)",
        "method_class": ("Newton-linearized spectral collocation (own code, NumPy) — "
                         "a NONLINEAR BVP solver; NOT a neural PINN"),
        "boundary_conditions": {"u(0)": a, "u(1)": b},
        "viscosity_nu": nu, "dof_sine_modes": N,
        "newton_iterations": sol["newton_iterations"],
        "newton_residual_history": [round(v, 12) for v in sol["newton_residual_history"]],
        "max_pde_residual_on_test": sol["max_pde_residual_on_test"],
        "rel_l2_pde_residual_on_test": sol["rel_l2_pde_residual_on_test"],
        "solution": {"x": x, "u": u},
        "doctrine": DOCTRINE, "lambda_note": LAMBDA_NOTE,
        "honesty": ("MODELED numerical field; no free-energy claim, no measured joule. "
                    "rel_l2_vs_exact (when a closed form exists) is a solver-verification "
                    "error, not a physical measurement."),
        "ts": _now_iso(),
    }
    if ref is not None:
        body["exact_reference"] = {
            "form": "-C*tanh(C(x-x0)/(2*nu))", "C": ref["C"], "x0": ref["x0"], "nu": ref["nu"],
            "rel_l2_vs_exact": rel_l2_vs_exact(sol, ref["C"], ref["x0"], ref["nu"]),
            "solution_in_trial_basis": False,
            "note": ("the tanh shock is NOT in the finite sine basis, so this error is a "
                     "genuine spectral-truncation error (not a by-construction win)"),
        }
    return body


def _h_burgers(req: Request):
    """MODELED nonlinear steady-Burgers solution. Defaults to the canonical shock
    instance (with exact-reference error); accepts ?nu=&a=&b=&N= for exploration."""
    qp = getattr(req, "query_params", {}) or {}

    def _q(name, default):
        try:
            return type(default)(qp.get(name)) if qp.get(name) not in (None, "") else default
        except Exception:
            return default

    if not any(k in qp for k in ("nu", "a", "b")):
        ci = canonical_instance()
        ref = {"C": ci["C"], "x0": ci["x0"], "nu": ci["nu"]}
        return JSONResponse(_burgers_payload(ci["nu"], ci["a"], ci["b"], N=48, ref=ref))
    nu = _q("nu", BURGERS_NU)
    a = _q("a", 0.9)
    b = _q("b", -0.9)
    N = int(_q("N", 48))
    if not (nu > 0):
        return JSONResponse({"error": "REFUSED", "reason": "viscosity nu must be > 0",
                             "honesty": "the solver refuses degenerate inputs; it never fabricates a field"},
                            status_code=400)
    N = max(4, min(N, 128))
    return JSONResponse(_burgers_payload(nu, a, b, N))


def _read_results() -> Optional[Dict]:
    for p in _RESULTS_PATHS:
        try:
            fp = Path(p)
            if fp.is_file():
                with fp.open("r", encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception:
            continue
    return None


def _h_bench(req: Request):
    """Serve the committed honest PINN cross-framework benchmark artifact.

    Read-only: this endpoint NEVER runs DeepXDE/Modulus in the request path (DeepXDE
    is LGPL and is a benchmark-only dev dependency). It serves benchmarks/pinn/
    results.json produced by run_bench.py; if the artifact is absent it returns an
    honest NOT-RUN roadmap with the exact reproduce command."""
    data = _read_results()
    if data is not None:
        data.setdefault("served_at", _now_iso())
        data.setdefault("source", "committed benchmarks/pinn/results.json (read-only)")
        return JSONResponse(data)
    return JSONResponse({
        "service": "a11oy.pinn.bench",
        "overall_label": "NOT-RUN",
        "reason": "no committed benchmarks/pinn/results.json found in this deployment",
        "reproduce": "python benchmarks/pinn/run_bench.py --assemble  (see harness --help)",
        "doctrine": DOCTRINE, "lambda_note": LAMBDA_NOTE,
        "ts": _now_iso(),
    })


def register(app, ns: str = "a11oy"):
    """Wire the nonlinear-PINN + benchmark surface under /api/<ns>/v1/pinn/*.
    Additive; mirrors szl_pinn_bounds.register()."""
    base = f"/api/{ns}/v1/pinn"
    handlers = [(f"{base}/burgers", _h_burgers), (f"{base}/bench", _h_bench)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


# --------------------------------------------------------------------------- #
# Self-test (no server): proves solver convergence + honesty
# --------------------------------------------------------------------------- #
def _selftest() -> Dict:
    out: Dict[str, object] = {}
    # Poisson (linear) — must hit the near-machine-precision floor (solution in basis)
    cp = canonical_poisson()
    out["poisson_solution_in_trial_basis"] = bool(cp["sol"]["solution_in_trial_basis"])
    out["poisson_near_exact"] = bool(cp["rel_l2_vs_exact"] < 1e-9)
    # Burgers (nonlinear) — honest spectral-truncation error vs exact tanh
    ci = canonical_instance()
    hist = ci["sol"]["newton_residual_history"]
    out["newton_converged"] = bool(ci["sol"]["newton_iterations"] < 40
                                   and hist[-1] < hist[0] * 0.05)
    out["matches_exact_closed_form"] = bool(ci["rel_l2_vs_exact"] < 1e-5)
    out["small_pde_residual"] = bool(ci["sol"]["rel_l2_pde_residual_on_test"] < 1e-3)
    refused = False
    try:
        solve_steady_burgers(nu=0.0, a=1.0, b=-1.0)
    except ValueError:
        refused = True
    out["refuses_degenerate_viscosity"] = refused
    out["poisson_rel_l2_vs_exact"] = cp["rel_l2_vs_exact"]
    out["burgers_rel_l2_vs_exact"] = ci["rel_l2_vs_exact"]
    out["burgers_newton_iterations"] = ci["sol"]["newton_iterations"]
    out["ok"] = all(out[k] is True for k in (
        "poisson_solution_in_trial_basis", "poisson_near_exact", "newton_converged",
        "matches_exact_closed_form", "small_pde_residual", "refuses_degenerate_viscosity"))
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
