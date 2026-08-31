#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v11
"""
run_modulus.py — PhysicsNeMo (NVIDIA Modulus) neural-PINN arm for the a11oy PINN
benchmark. Companion to run_bench.py's DeepXDE arms.

It mirrors the DeepXDE arms EXACTLY — same 1D problems, same constants, same exact
closed-form solutions, same network architecture / optimizer budget, same metric —
but builds the network with PhysicsNeMo's FullyConnected model and trains a manual
PINN residual loop (Adam + L-BFGS) on CUDA. This makes it an apples-to-apples
neural-PINN-vs-neural-PINN comparison (DeepXDE vs PhysicsNeMo) on the SAME GPU.

HONESTY (Doctrine v11):
  * Every number is MEASURED on the GPU vs the exact closed form (rel-L2 / |a-1|).
  * This uses the PhysicsNeMo *core* model layer
    (physicsnemo.models.mlp.FullyConnected), NOT the PhysicsNeMo-Sym PDE DSL —
    labelled precisely so the arm is neither overclaimed nor understated.
  * Energy/joules NOT-MEASURED (no power meter).
  * The Duffing arm uses the SAME synthetic data the DeepXDE arm saw, via the shared
    szl_pinn_inverse.integrate_duffing integrator.

Reproduce (on a CUDA GPU host with `pip install nvidia-physicsnemo`):
    python run_modulus.py --problem poisson --seeds 3 --out modulus_partial
    python run_modulus.py --problem burgers --seeds 3 --out modulus_partial
    python run_modulus.py --problem duffing --seeds 3 --out modulus_partial
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

# szl source path (for the SAME synthetic Duffing data the DeepXDE arm integrates)
for _p in ("/home/rosie/pinnbench", str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
import torch
from physicsnemo.models.mlp.fully_connected import FullyConnected

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PI = np.pi

# --- constants: MUST match run_bench.py ---
POISSON_MODES = {1: 1.0, 3: 0.5, 5: 0.2}
BURGERS_C, BURGERS_X0, BURGERS_NU = 1.0, 0.5, 0.05
DUFFING = dict(m=1.0, c=0.2, delta=1.0, alpha=1.0, F=0.5, omega=1.0, x0=0.0, v0=0.0)
DUFFING_T = (0.0, 12.0)
DUFFING_NDATA = 120
ALPHA_TRUTH = 1.0

METRIC = {"poisson": "rel_l2_vs_exact", "burgers": "rel_l2_vs_exact", "duffing": "abs_err"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seed_all(s: int) -> None:
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)


def _net(hidden_layers: int, width: int) -> torch.nn.Module:
    # FullyConnected(num_layers=H) => H hidden layers of `width`; matches DeepXDE's
    # FNN [1, width*H, 1] tanh.
    return FullyConnected(in_features=1, out_features=1, num_layers=hidden_layers,
                          layer_size=width, activation_fn="tanh").to(DEVICE)


def _d(y: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
    return torch.autograd.grad(y, x, grad_outputs=torch.ones_like(y), create_graph=True)[0]


def _adam_then_lbfgs(params, loss_fn, adam_iters, adam_lr, lbfgs_iters):
    opt = torch.optim.Adam(params, lr=adam_lr)
    for _ in range(adam_iters):
        opt.zero_grad()
        loss = loss_fn()
        loss.backward()
        opt.step()
    if lbfgs_iters > 0:
        lb = torch.optim.LBFGS(params, max_iter=lbfgs_iters, line_search_fn="strong_wolfe",
                               tolerance_grad=1e-12, tolerance_change=1e-12)

        def closure():
            lb.zero_grad()
            l = loss_fn()
            l.backward()
            return l

        lb.step(closure)
    return float(loss_fn().detach())


def _params_count(net) -> int:
    return int(sum(p.numel() for p in net.parameters()))


def run_poisson(seed: int) -> dict:
    _seed_all(seed)
    net = _net(3, 32)  # FNN [1,32,32,32,1] tanh
    xd = torch.linspace(0, 1, 66, device=DEVICE)[1:-1].reshape(-1, 1).requires_grad_(True)  # 64 interior
    xb = torch.tensor([[0.0], [1.0]], device=DEVICE)

    def f(x):
        return sum(c * (k * PI) ** 2 * torch.sin(k * PI * x) for k, c in POISSON_MODES.items())

    def loss_fn():
        u = net(xd)
        u_xx = _d(_d(u, xd), xd)
        res = -u_xx - f(xd)
        ub = net(xb)
        return torch.mean(res ** 2) + torch.mean(ub ** 2)

    t0 = time.time()
    _adam_then_lbfgs(list(net.parameters()), loss_fn, 8000, 1e-3, 2000)
    wall = time.time() - t0

    xe = torch.linspace(0, 1, 400, device=DEVICE).reshape(-1, 1)
    with torch.no_grad():
        yp = net(xe).cpu().numpy().ravel()
    xen = xe.cpu().numpy().ravel()
    ye = sum(c * np.sin(k * PI * xen) for k, c in POISSON_MODES.items())
    rel = float(np.sqrt(np.sum((yp - ye) ** 2) / np.sum(ye ** 2)))
    return {"seed": seed, "rel_l2_vs_exact": rel, "wall_s": round(wall, 2),
            "trainable_params": _params_count(net)}


def run_burgers(seed: int) -> dict:
    _seed_all(seed)
    net = _net(3, 40)  # FNN [1,40,40,40,1] tanh
    C, x0, nu = BURGERS_C, BURGERS_X0, BURGERS_NU
    exact = lambda x: -C * np.tanh(C * (x - x0) / (2.0 * nu))
    xd = torch.linspace(0, 1, 202, device=DEVICE)[1:-1].reshape(-1, 1).requires_grad_(True)  # 200 interior
    xb = torch.tensor([[0.0], [1.0]], device=DEVICE)
    ub_t = torch.tensor([[float(exact(0.0))], [float(exact(1.0))]], dtype=torch.float32, device=DEVICE)

    def loss_fn():
        u = net(xd)
        u_x = _d(u, xd)
        u_xx = _d(u_x, xd)
        res = nu * u_xx - u * u_x
        ub = net(xb)
        return torch.mean(res ** 2) + 100.0 * torch.mean((ub - ub_t) ** 2)

    t0 = time.time()
    _adam_then_lbfgs(list(net.parameters()), loss_fn, 8000, 1e-3, 2000)
    wall = time.time() - t0

    xe = torch.linspace(0, 1, 400, device=DEVICE).reshape(-1, 1)
    with torch.no_grad():
        yp = net(xe).cpu().numpy().ravel()
    xen = xe.cpu().numpy().ravel()
    ye = exact(xen)
    rel = float(np.sqrt(np.sum((yp - ye) ** 2) / np.sum(ye ** 2)))
    return {"seed": seed, "rel_l2_vs_exact": rel, "wall_s": round(wall, 2),
            "trainable_params": _params_count(net)}


def run_duffing(seed: int) -> dict:
    _seed_all(seed)
    import szl_pinn_inverse as PIV  # shared integrator -> SAME data the DeepXDE arm saw
    t_lo, t_hi = DUFFING_T
    m_, c_, delta_, F_, omega_ = (DUFFING["m"], DUFFING["c"], DUFFING["delta"],
                                  DUFFING["F"], DUFFING["omega"])
    t_obs = np.linspace(t_lo, t_hi, DUFFING_NDATA)
    x_obs = np.asarray(PIV.integrate_duffing(t_obs, **DUFFING)).reshape(-1, 1)

    net = _net(3, 40)
    alpha = torch.nn.Parameter(torch.tensor(2.0, device=DEVICE))  # wrong init; must discover ~1.0
    t_d = torch.linspace(t_lo, t_hi, 200, device=DEVICE).reshape(-1, 1).requires_grad_(True)
    t_data = torch.tensor(t_obs, dtype=torch.float32, device=DEVICE).reshape(-1, 1)
    x_data = torch.tensor(x_obs, dtype=torch.float32, device=DEVICE)

    def loss_fn():
        x = net(t_d)
        x_t = _d(x, t_d)
        x_tt = _d(x_t, t_d)
        res = m_ * x_tt + c_ * x_t + delta_ * x + alpha * x ** 3 - F_ * torch.cos(omega_ * t_d)
        x_pred = net(t_data)
        return torch.mean(res ** 2) + torch.mean((x_pred - x_data) ** 2)

    t0 = time.time()
    _adam_then_lbfgs(list(net.parameters()) + [alpha], loss_fn, 10000, 1e-3, 3000)
    wall = time.time() - t0

    a_hat = float(alpha.detach().cpu())
    return {"seed": seed, "alpha_estimate": a_hat, "alpha_truth": ALPHA_TRUTH,
            "abs_err": abs(a_hat - ALPHA_TRUTH), "wall_s": round(wall, 2),
            "trainable_params": _params_count(net)}


RUNNERS = {"poisson": run_poisson, "burgers": run_burgers, "duffing": run_duffing}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", required=True, choices=list(RUNNERS))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default="modulus_partial")
    a = ap.parse_args()

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    pf = outdir / ("modulus_%s.json" % a.problem)
    existing = json.loads(pf.read_text()) if pf.is_file() else {}
    rows = existing.get("seeds", [])
    done = {r["seed"] for r in rows}

    import physicsnemo
    versions = {"physicsnemo": getattr(physicsnemo, "__version__", "?"),
                "torch": torch.__version__,
                "backend": "pytorch-cuda" if DEVICE == "cuda" else "pytorch-cpu"}

    def pack():
        return {"framework": "modulus_physicsnemo", "problem": a.problem,
                "seeds": sorted(rows, key=lambda r: r["seed"]),
                "framework_versions": versions,
                "license": "Apache-2.0 (NVIDIA PhysicsNeMo; benchmark-only dev dependency, NOT shipped)",
                "method_class": ("neural PINN (PhysicsNeMo FullyConnected MLP; manual PDE-residual "
                                 "loop, Adam + L-BFGS)"),
                "device": (torch.cuda.get_device_name(0) if DEVICE == "cuda" else "cpu"),
                "note": ("Uses PhysicsNeMo core model layer (physicsnemo.models.mlp.FullyConnected), "
                         "NOT the PhysicsNeMo-Sym PDE DSL. Same net/optimizer budget and same exact "
                         "solutions as the DeepXDE arm for an apples-to-apples neural comparison."),
                "energy": "NOT-MEASURED (no power meter)", "ran_at": _now()}

    print("[modulus] device=%s problem=%s seeds=%d torch=%s pn=%s"
          % (DEVICE, a.problem, a.seeds, torch.__version__, versions["physicsnemo"]), flush=True)
    for s in range(a.seeds):
        if s in done:
            print("[modulus] skip seed %d (already done)" % s, flush=True)
            continue
        row = RUNNERS[a.problem](s)
        rows.append(row)
        pf.write_text(json.dumps(pack(), indent=2))
        mk = METRIC[a.problem]
        print("[modulus] %s seed %d done: %s=%s wall=%ss -> %s"
              % (a.problem, s, mk, row[mk], row["wall_s"], pf), flush=True)
    print("[modulus] DONE %s" % a.problem, flush=True)


if __name__ == "__main__":
    main()
