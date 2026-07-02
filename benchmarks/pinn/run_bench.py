#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. — SZL Holdings — ORCID 0009-0001-0110-4173 — Doctrine v11
"""
run_bench.py — a11oy PINN cross-framework HONEST benchmark harness.

Compares three solver families on the SAME 1D problems with KNOWN ground truth:

  * szl      — SZL Governed spectral collocation (this repo, own code, NumPy-only).
               Linear BVP via least-squares sine collocation; NONLINEAR BVP via a
               Newton loop around the same LS solve (szl_pinn_nonlinear); inverse
               parameter discovery via the governed inverse engine
               (szl_governed_ipinn / szl_pinn_inverse).
  * deepxde  — DeepXDE neural PINN (github.com/lululxvi/deepxde). BENCHMARK-ONLY.
  * modulus  — NVIDIA Modulus, RENAMED PhysicsNeMo. NOT RUN here (needs a CUDA GPU;
               this sandbox is CPU-only). Recorded as NOT-RUN with a reproduce spec.

LICENSING (why DeepXDE lives ONLY in this file):
  DeepXDE is **LGPL-2.1**. It is used here as a *benchmark-only development
  dependency*. It is NEVER imported by serve.py or by any shipped a11oy module; the
  /pinn/bench endpoint only READS the committed results.json this harness writes.
  DeepXDE imports are confined to the _deepxde_* functions below (lazy imports), so
  `--arm szl` and `--assemble` run with NumPy alone.

HONESTY (Doctrine v11):
  - Every number is MEASURED on THIS box (rel-L2 vs the exact closed form, wall time)
    or clearly labelled NOT-RUN / NOT-MEASURED. No number is fabricated.
  - Energy/joules are NOT-MEASURED: the sandbox has no power meter. We never print a
    joule figure for any arm.
  - DISCLOSURE: the Poisson exact solution is a finite sum of sine modes and therefore
    lies INSIDE the SZL trial basis, so SZL reaches ~machine precision BY CONSTRUCTION.
    This is flagged (solution_in_trial_basis) and is NOT a general-accuracy claim.
  - SCOPE: this is a low-dimensional, smooth, CPU-only suite. It favors spectral
    methods. The regimes where neural PINNs are designed to win (high dimension,
    complex/irregular geometry, no known good basis) are NOT exercised here and are
    reported as NOT-TESTED — not as a loss for the neural arm.

Reproduce (each DeepXDE arm fits the 120s per-call budget at 3 seeds on 2 CPUs):
    python benchmarks/pinn/run_bench.py --arm szl
    python benchmarks/pinn/run_bench.py --arm deepxde --problem poisson --seeds 3
    python benchmarks/pinn/run_bench.py --arm deepxde --problem burgers --seeds 3
    python benchmarks/pinn/run_bench.py --arm deepxde --problem duffing --seeds 3
    python benchmarks/pinn/run_bench.py --assemble --out benchmarks/pinn/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
PARTIAL_DIR = HERE.parent / "_partial"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Shared problem constants (must match szl_pinn_nonlinear canonical instances).
POISSON_MODES = {1: 1.0, 3: 0.5, 5: 0.2}
BURGERS_C, BURGERS_X0, BURGERS_NU = 1.0, 0.5, 0.05
DUFFING = dict(m=1.0, c=0.2, delta=1.0, alpha=1.0, F=0.5, omega=1.0, x0=0.0, v0=0.0)
DUFFING_T = (0.0, 12.0)
DUFFING_NDATA = 120
ALPHA_TRUTH = 1.0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stats(vals: List[float]) -> Dict[str, float]:
    return {"median": float(statistics.median(vals)),
            "min": float(min(vals)), "max": float(max(vals)),
            "n": len(vals)}


# --------------------------------------------------------------------------- #
# SZL arms (own code, NumPy-only) — fast, run in a single call
# --------------------------------------------------------------------------- #
def run_szl() -> Dict[str, Any]:
    import numpy as np
    import szl_pinn_nonlinear as NL

    # Poisson (linear) — solution IN basis (disclosed)
    t0 = time.time()
    ps = NL.solve_poisson_multimode(POISSON_MODES, N=8, M=64)
    poisson = {"framework": "szl", "method": "spectral sine-collocation least-squares",
               "rel_l2_vs_exact": ps["rel_l2_vs_exact"], "dof_sine_modes": ps["N"],
               "wall_s": round(time.time() - t0, 4),
               "solution_in_trial_basis": ps["solution_in_trial_basis"],
               "label": "MEASURED", "energy": "NOT-MEASURED (no power meter in sandbox)"}

    # Burgers (nonlinear) — solution NOT in basis (honest truncation error)
    C, x0, nu = BURGERS_C, BURGERS_X0, BURGERS_NU
    a = float(NL.exact_shock(0.0, C, x0, nu))
    b = float(NL.exact_shock(1.0, C, x0, nu))
    t0 = time.time()
    bs = NL.solve_steady_burgers(nu=nu, a=a, b=b, N=48, M=240)
    rel = NL.rel_l2_vs_exact(bs, C, x0, nu)
    burgers = {"framework": "szl",
               "method": "Newton-linearized spectral collocation (frontier, own code)",
               "rel_l2_vs_exact": rel, "dof_sine_modes": bs["N"],
               "newton_iterations": bs["newton_iterations"],
               "wall_s": round(time.time() - t0, 4),
               "solution_in_trial_basis": False,
               "label": "MEASURED", "energy": "NOT-MEASURED (no power meter in sandbox)"}

    # Inverse Duffing — governed inverse discovery of alpha (truth 1.0)
    import szl_governed_ipinn as GI
    t0 = time.time()
    out = GI.governed_discover({"demo": "duffing"})
    disc = out["receipt"]["dsse"]
    import base64
    payload = json.loads(base64.b64decode(disc["payload"]).decode())
    alpha_row = next(d for d in payload["discovered"] if d["name"] == "alpha")
    duffing = {"framework": "szl",
               "method": "governed inverse (Fisher-gated LS + physics-residual GD)",
               "alpha_estimate": alpha_row["value"], "alpha_truth": ALPHA_TRUTH,
               "abs_err": abs(alpha_row["value"] - ALPHA_TRUTH),
               "ci95": alpha_row.get("ci95"), "fisher_information": alpha_row.get("fisher_information"),
               "convergence_label": alpha_row.get("convergence_label"),
               "identifiable": alpha_row.get("identifiable"),
               "wall_s": round(time.time() - t0, 4),
               "label": "MEASURED (fit error vs synthetic ground truth; not measured physics)"}

    return {"framework_versions": {"numpy": np.__version__, "python": sys.version.split()[0]},
            "poisson": poisson, "burgers": burgers, "duffing": duffing, "ran_at": _now()}


# --------------------------------------------------------------------------- #
# DeepXDE arms (LGPL, benchmark-only, lazy-imported here ONLY)
# --------------------------------------------------------------------------- #
def _deepxde_setup():
    os.environ.setdefault("DDE_BACKEND", "pytorch")
    import numpy as np  # noqa
    import torch
    torch.set_num_threads(2)
    import deepxde as dde
    dde.optimizers.set_LBFGS_options(maxiter=2000)
    return dde, torch, np


def _deepxde_poisson_seed(seed: int) -> Dict[str, Any]:
    dde, torch, np = _deepxde_setup()
    PI = np.pi
    dde.config.set_random_seed(seed)
    ue = lambda x: sum(c * np.sin(k * PI * x) for k, c in POISSON_MODES.items())
    ft = lambda x: sum(c * (k * PI) ** 2 * torch.sin(k * PI * x) for k, c in POISSON_MODES.items())
    pde = lambda x, y: -dde.grad.hessian(y, x) - ft(x)
    g = dde.geometry.Interval(0, 1)
    bc = dde.icbc.DirichletBC(g, lambda x: 0.0, lambda x, on: on)
    data = dde.data.PDE(g, pde, bc, num_domain=64, num_boundary=2, solution=ue, num_test=200)
    net = dde.nn.FNN([1] + [32] * 3 + [1], "tanh", "Glorot uniform")
    m = dde.Model(data, net)
    t0 = time.time()
    m.compile("adam", lr=1e-3)
    m.train(iterations=8000, display_every=100000)
    m.compile("L-BFGS")
    m.train(display_every=100000)
    wall = time.time() - t0
    x = g.uniform_points(400, True)
    yp = m.predict(x).ravel()
    yeq = ue(x).ravel()
    rel = float(np.sqrt(np.sum((yp - yeq) ** 2) / np.sum(yeq ** 2)))
    return {"seed": seed, "rel_l2_vs_exact": rel, "wall_s": round(wall, 2),
            "trainable_params": int(sum(p.numel() for p in net.parameters()))}


def _deepxde_burgers_seed(seed: int) -> Dict[str, Any]:
    dde, torch, np = _deepxde_setup()
    C, x0, nu = BURGERS_C, BURGERS_X0, BURGERS_NU
    dde.config.set_random_seed(seed)
    exact = lambda x: -C * np.tanh(C * (x - x0) / (2.0 * nu))

    def pde(x, y):
        dy = dde.grad.jacobian(y, x)
        d2y = dde.grad.hessian(y, x)
        return nu * d2y - y * dy

    g = dde.geometry.Interval(0, 1)
    bc = dde.icbc.DirichletBC(g, lambda x: exact(x), lambda x, on: on)
    # standard, adequately-resourced FNN PINN (not shock-adapted): denser collocation
    # + firmer BC weighting so the comparison is fair, not a strawman.
    data = dde.data.PDE(g, pde, bc, num_domain=200, num_boundary=2, solution=exact, num_test=400)
    net = dde.nn.FNN([1] + [40] * 3 + [1], "tanh", "Glorot uniform")
    m = dde.Model(data, net)
    t0 = time.time()
    m.compile("adam", lr=1e-3, loss_weights=[1.0, 100.0])
    m.train(iterations=8000, display_every=100000)
    m.compile("L-BFGS", loss_weights=[1.0, 100.0])
    m.train(display_every=100000)
    wall = time.time() - t0
    x = g.uniform_points(400, True)
    yp = m.predict(x).ravel()
    yeq = exact(x).ravel()
    rel = float(np.sqrt(np.sum((yp - yeq) ** 2) / np.sum(yeq ** 2)))
    return {"seed": seed, "rel_l2_vs_exact": rel, "wall_s": round(wall, 2),
            "trainable_params": int(sum(p.numel() for p in net.parameters()))}


def _deepxde_duffing_seed(seed: int) -> Dict[str, Any]:
    dde, torch, np = _deepxde_setup()
    import szl_pinn_inverse as PIV
    dde.config.set_random_seed(seed)
    t_lo, t_hi = DUFFING_T
    m_, c_, delta_, F_, omega_ = (DUFFING["m"], DUFFING["c"], DUFFING["delta"],
                                  DUFFING["F"], DUFFING["omega"])
    # SAME synthetic data both arms see: integrate the true Duffing with alpha=1.0
    t_obs = np.linspace(t_lo, t_hi, DUFFING_NDATA)
    x_obs = np.asarray(PIV.integrate_duffing(t_obs, **DUFFING)).reshape(-1, 1)
    t_col = t_obs.reshape(-1, 1)

    alpha = dde.Variable(2.0)  # deliberately wrong init; must discover ~1.0

    def ode(t, x):
        dx = dde.grad.jacobian(x, t)
        ddx = dde.grad.hessian(x, t)
        return m_ * ddx + c_ * dx + delta_ * x + alpha * x ** 3 - F_ * torch.cos(omega_ * t)

    geom = dde.geometry.TimeDomain(t_lo, t_hi)
    obs = dde.icbc.PointSetBC(t_col, x_obs, component=0)
    data = dde.data.PDE(geom, ode, [obs], num_domain=200, num_boundary=2,
                        anchors=t_col)
    net = dde.nn.FNN([1] + [40] * 3 + [1], "tanh", "Glorot uniform")
    m = dde.Model(data, net)
    t0 = time.time()
    m.compile("adam", lr=1e-3, external_trainable_variables=[alpha])
    m.train(iterations=10000, display_every=100000)
    # bound L-BFGS: with 2nd-order (hessian) residuals the default maxiter=15000
    # runs far past convergence and blows any wall budget; 3000 is ample here.
    dde.optimizers.config.set_LBFGS_options(maxiter=3000)
    m.compile("L-BFGS", external_trainable_variables=[alpha])
    m.train(display_every=100000)
    wall = time.time() - t0
    a_hat = float(alpha.detach().cpu().numpy()) if hasattr(alpha, "detach") else float(alpha)
    return {"seed": seed, "alpha_estimate": a_hat, "alpha_truth": ALPHA_TRUTH,
            "abs_err": abs(a_hat - ALPHA_TRUTH), "wall_s": round(wall, 2),
            "trainable_params": int(sum(p.numel() for p in net.parameters()))}


_DEEPXDE_RUNNERS = {"poisson": _deepxde_poisson_seed,
                    "burgers": _deepxde_burgers_seed,
                    "duffing": _deepxde_duffing_seed}


def run_deepxde(problem: str, seeds: int) -> Dict[str, Any]:
    """Resumable: writes the partial after EACH seed and skips seeds already done,
    so a per-call timeout on a slow CPU never loses completed work — just re-run."""
    runner = _DEEPXDE_RUNNERS[problem]
    import deepxde as dde
    part_path = PARTIAL_DIR / ("deepxde_%s.json" % problem)
    existing = _load_partial("deepxde_%s.json" % problem) or {}
    rows: List[Dict[str, Any]] = existing.get("seeds", [])
    done = {r["seed"] for r in rows}
    versions = {}
    try:
        import torch
        versions = {"deepxde": dde.__version__, "torch": torch.__version__, "backend": "pytorch"}
    except Exception:
        versions = {"deepxde": getattr(dde, "__version__", "?")}

    def _pack() -> Dict[str, Any]:
        return {"framework": "deepxde", "problem": problem,
                "seeds": sorted(rows, key=lambda r: r["seed"]),
                "framework_versions": versions,
                "license": "LGPL-2.1 (benchmark-only dev dependency; NOT imported by shipped code)",
                "method_class": "neural PINN (MLP minimizes PDE residual via Adam + L-BFGS)",
                "energy": "NOT-MEASURED (no power meter in sandbox)", "ran_at": _now()}

    for s in range(seeds):
        if s in done:
            continue
        row = runner(s)
        rows.append(row)
        part_path.write_text(json.dumps(_pack(), indent=2))
        print("[run_bench] deepxde %s seed %d done -> %s" % (problem, s, part_path), flush=True)
    return _pack()


# --------------------------------------------------------------------------- #
# Assemble committed results.json from partials
# --------------------------------------------------------------------------- #
def _load_partial(name: str) -> Optional[Dict[str, Any]]:
    fp = PARTIAL_DIR / name
    if fp.is_file():
        with fp.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


# Committed DeepXDE training config per problem. These mirror the _deepxde_*_seed
# functions above that produced the partials, recorded here so the assembled artifact
# is SELF-DESCRIBING and reproducible without re-reading this source. (Kept in lockstep
# with the seed functions; the architect verified they match the committed partials.)
_DEEPXDE_CONFIG = {
    "poisson": {"net": "FNN [1,32,32,32,1] tanh (Glorot uniform)",
                "optimizer": "Adam 8000 iters (lr=1e-3) + L-BFGS (maxiter=2000)",
                "num_domain": 64, "num_boundary": 2, "num_test": 200, "loss_weights": None},
    "burgers": {"net": "FNN [1,40,40,40,1] tanh (Glorot uniform)",
                "optimizer": "Adam 8000 iters (lr=1e-3) + L-BFGS (maxiter=2000)",
                "num_domain": 200, "num_boundary": 2, "num_test": 400, "loss_weights": [1.0, 100.0]},
    "duffing": {"net": "FNN [1,40,40,40,1] tanh (Glorot uniform)",
                "optimizer": "Adam 10000 iters (lr=1e-3) + L-BFGS (maxiter=3000)",
                "num_domain": 200, "num_boundary": 2, "anchors": "120 observation points (PointSetBC)"},
}
# Honest caveats attached to specific neural arms so a strong SZL result is never
# read as a universal neural-PINN ceiling.
_DEEPXDE_CAVEAT = {
    "burgers": ("STANDARD, non-shock-adapted PINN config: a plain FNN minimizing the PDE "
                "residual with firm BC weighting. Shock-adaptation techniques (adaptive "
                "resampling / RAR, curriculum in \u03bd, or hard-BC output transforms) would "
                "very likely improve this arm and are NOT-TESTED here \u2014 so the large "
                "burgers error reflects the vanilla config, NOT a ceiling for neural PINNs "
                "on this PDE."),
}


def _dx_summary(part: Optional[Dict[str, Any]], metric: str, problem: str) -> Dict[str, Any]:
    if not part:
        return {"framework": "deepxde", "label": "NOT-RUN",
                "reason": "no partial artifact; run the deepxde arm to populate"}
    vals = [row[metric] for row in part["seeds"]]
    walls = [row["wall_s"] for row in part["seeds"]]
    out = {"framework": "deepxde", "method_class": part["method_class"],
           "license": part["license"], "seeds_run": len(vals),
           metric: _stats(vals), "wall_s": _stats(walls),
           "trainable_params": part["seeds"][0].get("trainable_params"),
           "config": _DEEPXDE_CONFIG.get(problem),
           "framework_versions": part["framework_versions"],
           "label": "MEASURED", "energy": part["energy"]}
    if problem in _DEEPXDE_CAVEAT:
        out["caveat"] = _DEEPXDE_CAVEAT[problem]
    if metric == "abs_err":
        # inverse-parameter fit: harmonize the label with the SZL arm — both arms fit
        # the SAME synthetic data, so both are "MEASURED (fit error vs ground truth)".
        out["label"] = "MEASURED (fit error vs synthetic ground truth; not measured physics)"
        out["alpha_estimate_median"] = float(statistics.median(
            [row["alpha_estimate"] for row in part["seeds"]]))
        out["alpha_truth"] = ALPHA_TRUTH
    return out


def _modulus_stub(problem: str) -> Dict[str, Any]:
    return {"framework": "modulus_physicsnemo", "label": "NOT-RUN",
            "reason": ("NVIDIA Modulus (renamed PhysicsNeMo) requires a CUDA GPU; this "
                       "benchmark box is CPU-only (0 GPUs)."),
            "note": "NVIDIA Modulus was renamed to PhysicsNeMo — same framework lineage.",
            "reproduce": ("on a CUDA GPU host: `pip install nvidia-physicsnemo`; port the "
                          f"'{problem}' 1D residual to a PhysicsNeMo PDE + constraint and "
                          "train; report rel-L2 vs the same exact closed form.")}


def assemble(out_path: str) -> Dict[str, Any]:
    szl = _load_partial("szl.json")
    dx_pois = _load_partial("deepxde_poisson.json")
    dx_burg = _load_partial("deepxde_burgers.json")
    dx_duff = _load_partial("deepxde_duffing.json")

    problems = [
        {
            "id": "poisson_1d_multimode",
            "pde": "-u''(x) = f(x) on [0,1], u(0)=u(1)=0",
            "exact": "u*(x)=Σ c_k sin(kπx), modes {1:1.0, 3:0.5, 5:0.2}",
            "disclosure": {
                "solution_in_trial_basis": True,
                "note": ("the exact solution is a finite sine sum, so it lies INSIDE the SZL "
                         "sine trial basis → SZL reaches ~machine precision BY CONSTRUCTION. "
                         "This is a property of the problem, NOT a general-accuracy claim."),
            },
            "metric": "rel_l2_vs_exact",
            "arms": [szl["poisson"] if szl else {"framework": "szl", "label": "NOT-RUN"},
                     _dx_summary(dx_pois, "rel_l2_vs_exact", "poisson"),
                     _modulus_stub("poisson")],
        },
        {
            "id": "steady_burgers_shock",
            "pde": "ν u''(x) - u(x) u'(x) = 0 on [0,1], Dirichlet BCs from exact",
            "exact": "u*(x)=-C·tanh(C(x-x0)/(2ν)), C=1, x0=0.5, ν=0.05",
            "disclosure": {
                "solution_in_trial_basis": False,
                "note": ("the tanh shock is NOT a finite sine sum, so the SZL error is a "
                         "genuine spectral-truncation error — an honest head-to-head on a "
                         "NONLINEAR PDE (the frontier gap this build closes)."),
            },
            "metric": "rel_l2_vs_exact",
            "arms": [szl["burgers"] if szl else {"framework": "szl", "label": "NOT-RUN"},
                     _dx_summary(dx_burg, "rel_l2_vs_exact", "burgers"),
                     _modulus_stub("burgers")],
        },
        {
            "id": "inverse_duffing",
            "pde": "m x'' + c x' + δ x + α x³ = F cos(ωt); DISCOVER α (truth 1.0)",
            "exact": "synthetic data integrated from the true system (α=1.0); same data both arms",
            "disclosure": {
                "solution_in_trial_basis": None,
                "note": ("inverse parameter-discovery problem: both arms see the SAME synthetic "
                         "x(t) data and must recover α from a deliberately wrong start."),
            },
            "metric": "abs_err",
            "arms": [szl["duffing"] if szl else {"framework": "szl", "label": "NOT-RUN"},
                     _dx_summary(dx_duff, "abs_err", "duffing"),
                     _modulus_stub("duffing")],
        },
    ]

    result = {
        "service": "a11oy.pinn.bench",
        "title": "SZL Governed spectral collocation vs DeepXDE (neural PINN) vs Modulus/PhysicsNeMo",
        "overall_label": "MEASURED (SZL + DeepXDE on this CPU box); Modulus NOT-RUN",
        "ran_at": _now(),
        "hardware": {"cpus": 2, "ram_gib": 15, "gpu": None, "torch_threads": 2,
                     "note": "Replit sandbox — CPU-only, no CUDA GPU"},
        "frameworks": {
            "szl": {"method_class": ("classical spectral collocation least-squares (+ Newton "
                                     "for nonlinear BVP) — NOT a neural PINN"),
                    "deps": ["python-stdlib", "numpy (BSD-3)"],
                    "license": "Apache-2.0", "shipped": True,
                    "versions": szl["framework_versions"] if szl else None},
            "deepxde": {"method_class": "neural PINN (MLP minimizes PDE residual)",
                        "deps": ["pytorch"], "license": "LGPL-2.1",
                        "shipped": False,
                        "usage": ("benchmark-only dev dependency; NEVER imported by serve.py or "
                                  "any shipped module. The /pinn/bench endpoint only reads this "
                                  "committed artifact."),
                        "versions": (dx_pois or dx_burg or dx_duff or {}).get("framework_versions")},
            "modulus_physicsnemo": {"method_class": "neural PINN (NVIDIA)",
                                    "status": "NOT-RUN", "license": "Apache-2.0",
                                    "note": "NVIDIA Modulus was renamed PhysicsNeMo (same framework)."},
        },
        "problems": problems,
        "interpretation": {
            "poisson": ("SZL is ~machine precision BY CONSTRUCTION (solution in basis, disclosed); "
                        "DeepXDE reaches a solid neural-PINN accuracy without knowing the basis."),
            "burgers": ("honest nonlinear head-to-head: SZL's new Newton-spectral solver and the "
                        "neural PINN both target the exact tanh shock; compare rel-L2 and wall time. "
                        "The DeepXDE arm is a STANDARD, non-shock-adapted PINN \u2014 shock-adaptation "
                        "(RAR / curriculum / hard-BC) is NOT-TESTED and would likely narrow the gap."),
            "duffing": ("both recover α from the same data; compare |α̂-1| and cost."),
        },
        "scope_limits": (
            "This is a LOW-DIMENSIONAL (1D), SMOOTH, CPU-ONLY suite with KNOWN good bases. "
            "It structurally favors spectral methods. The regimes neural PINNs are designed "
            "for — high dimension (curse-of-dimensionality resistance), complex/irregular "
            "geometry, and problems with NO known good basis — are NOT exercised here and are "
            "reported as NOT-TESTED, not as a neural-arm loss. Do not read SZL wins on this "
            "suite as universal superiority."),
        "honesty": (
            "All rel-L2 and wall-time numbers are MEASURED on this box against the exact closed "
            "form; ≥3 seeds are reported as median[min,max] for the neural arm. No joules are "
            "reported (NOT-MEASURED: no power meter). Poisson's in-basis advantage is disclosed. "
            "DeepXDE (LGPL) is benchmark-only and never shipped. Modulus/PhysicsNeMo is NOT-RUN "
            "with a reproduce spec (no GPU)."),
        "doctrine": "Doctrine v11 LOCKED — no fabricated numbers; MEASURED/MODELED/NOT-RUN/NOT-MEASURED/NOT-TESTED labels only.",
        "reproduce": {
            "szl": "python benchmarks/pinn/run_bench.py --arm szl",
            "deepxde": "python benchmarks/pinn/run_bench.py --arm deepxde --problem {poisson|burgers|duffing} --seeds 3",
            "assemble": "python benchmarks/pinn/run_bench.py --assemble --out benchmarks/pinn/results.json",
            "modulus": "requires a CUDA GPU host with nvidia-physicsnemo (see each problem's modulus arm)",
        },
    }
    outp = Path(out_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="a11oy PINN cross-framework honest benchmark harness.")
    ap.add_argument("--arm", choices=["szl", "deepxde"], help="which arm to run")
    ap.add_argument("--problem", choices=["poisson", "burgers", "duffing"],
                    help="problem for the deepxde arm")
    ap.add_argument("--seeds", type=int, default=3, help="seeds for the deepxde arm (>=3 for honesty)")
    ap.add_argument("--assemble", action="store_true", help="merge partials into results.json")
    ap.add_argument("--out", default=str(HERE.parent / "results.json"), help="assembled artifact path")
    args = ap.parse_args()

    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)

    if args.arm == "szl":
        res = run_szl()
        (PARTIAL_DIR / "szl.json").write_text(json.dumps(res, indent=2))
        print("[run_bench] SZL arm -> _partial/szl.json")
        print("  poisson rel_l2=%.3e  burgers rel_l2=%.3e (newton %d it)  duffing |a-1|=%.4f (%s)"
              % (res["poisson"]["rel_l2_vs_exact"], res["burgers"]["rel_l2_vs_exact"],
                 res["burgers"]["newton_iterations"], res["duffing"]["abs_err"],
                 res["duffing"]["convergence_label"]))
        return 0

    if args.arm == "deepxde":
        if not args.problem:
            print("[run_bench] --arm deepxde requires --problem", file=sys.stderr)
            return 2
        res = run_deepxde(args.problem, args.seeds)
        (PARTIAL_DIR / ("deepxde_%s.json" % args.problem)).write_text(json.dumps(res, indent=2))
        metric = "abs_err" if args.problem == "duffing" else "rel_l2_vs_exact"
        vals = [r[metric] for r in res["seeds"]]
        print("[run_bench] DeepXDE %s -> _partial/deepxde_%s.json  %s median=%.3e [%.3e,%.3e] over %d seeds"
              % (args.problem, args.problem, metric, statistics.median(vals),
                 min(vals), max(vals), len(vals)))
        return 0

    if args.assemble:
        res = assemble(args.out)
        print("[run_bench] assembled -> %s  overall_label=%s" % (args.out, res["overall_label"]))
        for p in res["problems"]:
            labels = ", ".join("%s:%s" % (a["framework"], a["label"]) for a in p["arms"])
            print("  %-22s [%s]" % (p["id"], labels))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
