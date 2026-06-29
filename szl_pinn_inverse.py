#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
#
# szl_pinn_inverse.py — SZL Governed Inverse-PINN engine (a11oy frontier).
# Taxonomy home: services (frontier discovery surface) + provenance (signed receipt).
#
# Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Lambda = Conjecture 1 (advisory only).
#
# WHAT THIS IS
#   A self-contained INVERSE physics-informed solver that discovers unknown
#   PHYSICAL PARAMETERS of an ODE/PDE from data, with an HONEST self-doubt gate:
#   a parameter the data cannot identify is labelled RED / UNIDENTIFIABLE and the
#   engine REFUSES to assert a value for it (Fisher-information gate, below).
#
# OWN CODE / PERMISSIVE DEPS ONLY (NumPy BSD-3)
#   No torch, no DeepXDE (LGPL), nothing proprietary. Every equation is
#   RE-IMPLEMENTED from the public literature (per-equation citation map in
#   team/frontier/PINN_BACKEND.md), not copied from any GPL/LGPL package.
#
#   The surrogate that represents x(t) is a LINEAR spectral basis (Fourier modes
#   + a low-order polynomial trend). A linear basis is the pragmatic, robust
#   choice for an autograd-free NumPy build: its first/second time-derivatives
#   are EXACT and analytic (no fragile finite differencing, no second-order
#   backprop), the data fit is a single regularised least-squares solve (fast,
#   CPU-only, seconds), and the physics residual is then well-conditioned. A
#   tanh-MLP surrogate (SZLPinnNet) with exact analytic input-derivatives is also
#   provided for callers who prefer it, but the governed endpoint defaults to the
#   spectral basis because it is the one that converges reliably on a cpu-basic
#   Space without a heavy autodiff dependency.
#
#   Parameters that enter the residual LINEARLY (e.g. Duffing alpha) are solved by
#   exact least squares; any others are refined by gradient descent on the
#   physics residual. Identifiability is then checked via the Fisher Information
#   Matrix BEFORE any value is asserted.
#
# HONEST LABELS: every numeric result here is MODELED (a fit to data), never
#   MEASURED. The convergence label is GREEN / YELLOW / RED with the EXACT numeric
#   criteria from team/frontier/ARXIV_LEADERS.md — see _classify_convergence().
#   The half-state ("looks done but isn't") is unacceptable.

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# EXACT convergence thresholds — from ARXIV_LEADERS.md (three-state GREEN/YELLOW/
# RED rules). These are the contract the front-end + receipt rely on; do NOT
# loosen them without updating the spec.
# ---------------------------------------------------------------------------
CAUSAL_GREEN = 0.99          # min(w_causal) > 0.99  -> temporally converged
CAUSAL_RED = 0.50            # min(w_causal) <= 0.50 -> diverged
GRAD_GREEN = 1e-5            # ||grad L_A (params)|| < 1e-5 -> stationary
KAPPA_IDENT = 1e6            # kappa(FIM) < 1e6  -> identifiable
KAPPA_RED = 1e8              # kappa(FIM) >= 1e8 -> non-identifiable (RED)
FISHER_FLOOR = 1e-8          # per-param Fisher information floor (self-doubt gate)
EPSILON_CAUSAL = 0.01        # epsilon in w_causal = exp(-eps * cumsum r^2)
MIN_DATA_POINTS = 10         # below this the engine refuses to assert anything

__all__ = [
    "SZLSpectralSurrogate",
    "SZLPinnNet",
    "SZLInversePINN",
    "SZLInversePINNTrainer",
    "ConvergenceRecord",
    "ParamResult",
    "duffing_residual",
    "integrate_duffing",
]


# ===========================================================================
# 1a. Spectral-basis surrogate (DEFAULT) — exact analytic time-derivatives.
# ===========================================================================
class SZLSpectralSurrogate:
    """x(t) ~ sum_p a_p t^p  +  sum_k [ b_k sin(w_k tau) + c_k cos(w_k tau) ],
    tau = t - t0, w_k = 2*pi*k / span. A LINEAR-in-coefficients model: the
    design matrices for x, dx/dt, d2x/dt2 are exact and analytic, so the physics
    residual needs no finite differencing of the surrogate. Re-implemented from
    standard Fourier/Chebyshev collocation theory (own code)."""

    def __init__(self, n_modes: int = 24, poly_deg: int = 3, ridge: float = 1e-6):
        self.K = int(n_modes)
        self.D = int(poly_deg)
        self.ridge = float(ridge)
        self.coef: Optional[np.ndarray] = None
        self.t0 = 0.0
        self.span = 1.0

    def n_features(self) -> int:
        return (self.D + 1) + 2 * self.K

    def design(self, t: np.ndarray, order: int = 0) -> np.ndarray:
        t = np.asarray(t, float).reshape(-1)
        tau = t - self.t0
        cols: List[np.ndarray] = []
        for p in range(self.D + 1):
            if order == 0:
                cols.append(t ** p)
            elif order == 1:
                cols.append(p * t ** (p - 1) if p >= 1 else np.zeros_like(t))
            else:
                cols.append(p * (p - 1) * t ** (p - 2) if p >= 2 else np.zeros_like(t))
        for k in range(1, self.K + 1):
            w = 2.0 * math.pi * k / self.span
            if order == 0:
                cols += [np.sin(w * tau), np.cos(w * tau)]
            elif order == 1:
                cols += [w * np.cos(w * tau), -w * np.sin(w * tau)]
            else:
                cols += [-w * w * np.sin(w * tau), -w * w * np.cos(w * tau)]
        return np.stack(cols, axis=1)

    def fit(self, t: np.ndarray, y: np.ndarray):
        t = np.asarray(t, float).reshape(-1)
        y = np.asarray(y, float).reshape(-1)
        self.t0 = float(t.min())
        self.span = float(t.max() - t.min()) or 1.0
        A = self.design(t, 0)
        G = A.T @ A + self.ridge * np.eye(A.shape[1])
        self.coef = np.linalg.solve(G, A.T @ y)
        return self

    def derivatives(self, t: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.coef is None:
            raise RuntimeError("surrogate not fitted")
        x = self.design(t, 0) @ self.coef
        dx = self.design(t, 1) @ self.coef
        ddx = self.design(t, 2) @ self.coef
        return x, dx, ddx

    def predict(self, t: np.ndarray) -> np.ndarray:
        return self.design(t, 0) @ self.coef


# ===========================================================================
# 1b. Optional tanh-MLP surrogate — exact analytic input-derivatives.
#     Provided for spec-completeness/generality; the governed endpoint defaults
#     to SZLSpectralSurrogate (more robust autograd-free convergence on CPU).
# ===========================================================================
class SZLPinnNet:
    """1-D -> 1-D tanh MLP with EXACT first/second analytic derivatives of the
    output w.r.t. the scalar input, plus manual reverse-mode backprop of the data
    MSE. Re-implemented from first principles (chain rule for tanh layers;
    Rumelhart et al. backprop). NumPy only."""

    def __init__(self, layers: Sequence[int] = (1, 32, 32, 1), seed: int = 0):
        self.layers = list(layers)
        rng = np.random.default_rng(seed)
        self.W: List[np.ndarray] = []
        self.b: List[np.ndarray] = []
        for nin, nout in zip(self.layers[:-1], self.layers[1:]):
            self.W.append(rng.normal(0.0, math.sqrt(1.0 / nin), size=(nin, nout)))
            self.b.append(np.zeros((1, nout)))
        self.in_mean = 0.0
        self.in_scale = 1.0
        self.out_mean = 0.0
        self.out_scale = 1.0
        self._cache: dict = {}

    def set_norm(self, t, y):
        self.in_mean = float(np.mean(t)); self.in_scale = float(np.std(t)) or 1.0
        self.out_mean = float(np.mean(y)); self.out_scale = float(np.std(y)) or 1.0

    def _raw_forward(self, tn: np.ndarray) -> np.ndarray:
        a = tn.reshape(-1, 1)
        zs, acts = [], [a]
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            z = a @ W + b
            zs.append(z)
            a = np.tanh(z) if i < len(self.W) - 1 else z
            acts.append(a)
        self._cache = {"zs": zs, "acts": acts}
        return a.reshape(-1)

    def predict(self, t: np.ndarray) -> np.ndarray:
        tn = (np.asarray(t, float) - self.in_mean) / self.in_scale
        return self.out_mean + self.out_scale * self._raw_forward(tn)

    def derivatives(self, t: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        tn = (np.asarray(t, float) - self.in_mean) / self.in_scale
        a = tn.reshape(-1, 1)
        da = np.ones_like(a)
        dda = np.zeros_like(a)
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            z = a @ W + b
            dz = da @ W
            ddz = dda @ W
            if i < len(self.W) - 1:
                th = np.tanh(z)
                tp = 1.0 - th * th
                tpp = -2.0 * th * tp
                a = th
                dda = tpp * dz * dz + tp * ddz
                da = tp * dz
            else:
                a = z; da = dz; dda = ddz
        s = self.out_scale
        x = self.out_mean + s * a.reshape(-1)
        dx = s * da.reshape(-1) / self.in_scale
        ddx = s * dda.reshape(-1) / (self.in_scale ** 2)
        return x, dx, ddx

    def data_grads(self, t, y):
        tn = (np.asarray(t, float) - self.in_mean) / self.in_scale
        yn = (np.asarray(y, float) - self.out_mean) / self.out_scale
        x = self._raw_forward(tn)
        n = x.shape[0]
        resid = (x - yn)
        loss = float(0.5 * np.mean(resid * resid))
        g = (resid / n).reshape(-1, 1)
        acts = self._cache["acts"]; zs = self._cache["zs"]
        gW = [None] * len(self.W); gb = [None] * len(self.b)
        delta = g
        for i in reversed(range(len(self.W))):
            gW[i] = acts[i].T @ delta
            gb[i] = delta.sum(axis=0, keepdims=True)
            if i > 0:
                delta = (delta @ self.W[i].T) * (1.0 - np.tanh(zs[i - 1]) ** 2)
        return gW, gb, loss

    def fit(self, t, y, epochs: int = 1500, lr: float = 5e-3):
        self.set_norm(t, y)
        mW = [np.zeros_like(w) for w in self.W]; vW = [np.zeros_like(w) for w in self.W]
        mb = [np.zeros_like(b) for b in self.b]; vb = [np.zeros_like(b) for b in self.b]
        b1, b2, e = 0.9, 0.999, 1e-8
        for it in range(int(epochs)):
            gW, gb, _ = self.data_grads(t, y)
            i1 = it + 1
            for j in range(len(self.W)):
                mW[j] = b1 * mW[j] + (1 - b1) * gW[j]; vW[j] = b2 * vW[j] + (1 - b2) * gW[j] ** 2
                self.W[j] -= lr * (mW[j] / (1 - b1 ** i1)) / (np.sqrt(vW[j] / (1 - b2 ** i1)) + e)
                mb[j] = b1 * mb[j] + (1 - b1) * gb[j]; vb[j] = b2 * vb[j] + (1 - b2) * gb[j] ** 2
                self.b[j] -= lr * (mb[j] / (1 - b1 ** i1)) / (np.sqrt(vb[j] / (1 - b2 ** i1)) + e)
        return self


# ===========================================================================
# 2. The inverse model — surrogate + learnable physical parameters + residual.
# ===========================================================================
class SZLInversePINN:
    """Bundles a surrogate (spectral by default), a dict of learnable physical
    parameters, and a user-supplied residual callable r = f(t,x,dx,ddx,params)."""

    def __init__(self, residual_fn: Callable[..., np.ndarray],
                 param_inits: Dict[str, float],
                 surrogate=None,
                 param_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
                 linear_params: Optional[Sequence[str]] = None):
        self.surrogate = surrogate if surrogate is not None else SZLSpectralSurrogate()
        self.residual_fn = residual_fn
        self.params: Dict[str, float] = dict(param_inits)
        self.param_bounds = dict(param_bounds or {})
        self.linear_params = list(linear_params or [])

    def param_values(self) -> Dict[str, float]:
        return dict(self.params)

    def derivatives(self, t: np.ndarray):
        return self.surrogate.derivatives(t)

    def residual(self, t: np.ndarray) -> np.ndarray:
        x, dx, ddx = self.surrogate.derivatives(t)
        return np.asarray(self.residual_fn(t, x, dx, ddx, self.params), dtype=float)


# ===========================================================================
# 3. Records.
# ===========================================================================
@dataclass
class ParamResult:
    name: str
    value: float
    ci_low: float
    ci_high: float
    std: float
    fisher: float
    identifiable: bool
    asserted: bool          # False -> engine REFUSES (RED / UNIDENTIFIABLE)


@dataclass
class ConvergenceRecord:
    label: str                      # GREEN | YELLOW | RED
    min_causal_weight: float
    grad_norm: float
    kappa_fim: float
    delta_param_rel: float
    residual_rms: float
    data_rms: float
    epochs_run: int
    criteria: Dict[str, str] = field(default_factory=dict)
    note: str = ""


# ===========================================================================
# 4. The trainer — surrogate fit + param solve (LS for linear, GD for nonlinear)
#    + SA-PINN weights + causal weights + FIM self-doubt gate + ensemble CI.
# ===========================================================================
class SZLInversePINNTrainer:
    def __init__(self, model: SZLInversePINN,
                 t_data: np.ndarray, y_data: np.ndarray,
                 t_colloc: Optional[np.ndarray] = None,
                 w_phys: float = 1.0,
                 lr_param: float = 5e-2,
                 noise_sigma: Optional[float] = None,
                 seed: int = 0):
        self.m = model
        self.t_data = np.asarray(t_data, float).reshape(-1)
        self.y_data = np.asarray(y_data, float).reshape(-1)
        self.t_colloc = (np.asarray(t_colloc, float).reshape(-1)
                         if t_colloc is not None else self.t_data.copy())
        self.w_phys = float(w_phys)
        self.lr_param = float(lr_param)
        self.noise_sigma = noise_sigma
        self.rng = np.random.default_rng(seed)
        self.sa = np.ones_like(self.t_colloc)       # SA-PINN self-adaptive weights
        self.param_history: List[Dict[str, float]] = []

    # ---- residual on the collocation grid ----
    def _phys_residual(self) -> np.ndarray:
        return self.m.residual(self.t_colloc)

    # ---- exact least squares for params that enter r LINEARLY ----
    def _ls_solve_linear(self):
        names = list(self.m.linear_params)
        if not names:
            return
        x, dx, ddx = self.m.derivatives(self.t_colloc)
        base = dict(self.m.params)
        G = np.zeros((self.t_colloc.shape[0], len(names)))
        for j, nm in enumerate(names):
            p = dict(base); p[nm] = base[nm] + 1.0
            r1 = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p), float)
            p[nm] = base[nm]
            r0 = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p), float)
            G[:, j] = r1 - r0
        p0 = dict(base)
        for nm in names:
            p0[nm] = 0.0
        r_at_zero = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p0), float)
        w = np.sqrt(self.sa)
        try:
            sol, *_ = np.linalg.lstsq(G * w[:, None], -r_at_zero * w, rcond=None)
            for j, nm in enumerate(names):
                v = float(sol[j])
                lo, hi = self.m.param_bounds.get(nm, (-np.inf, np.inf))
                self.m.params[nm] = float(min(max(v, lo), hi))
        except np.linalg.LinAlgError:
            pass

    # ---- gradient descent for NONLINEAR params (Adam on physics residual) ----
    def _gd_nonlinear(self, epochs: int):
        names = [k for k in self.m.params if k not in self.m.linear_params]
        if not names:
            return
        mom = {k: 0.0 for k in names}; vel = {k: 0.0 for k in names}
        b1, b2, e = 0.9, 0.999, 1e-8
        for it in range(int(epochs)):
            r = self._phys_residual()
            self.sa = np.clip(self.sa + 0.01 * np.abs(r), 1.0, 50.0)
            x, dx, ddx = self.m.derivatives(self.t_colloc)
            i1 = it + 1
            for nm in names:
                d = max(1e-6, 1e-4 * (abs(self.m.params[nm]) + 1.0))
                p = dict(self.m.params); p[nm] += d
                rp = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p), float)
                grad = float(np.mean(self.sa * r * (rp - r) / d)) * self.w_phys
                mom[nm] = b1 * mom[nm] + (1 - b1) * grad
                vel[nm] = b2 * vel[nm] + (1 - b2) * grad * grad
                step = self.lr_param * (mom[nm] / (1 - b1 ** i1)) / (math.sqrt(vel[nm] / (1 - b2 ** i1)) + e)
                v = self.m.params[nm] - step
                lo, hi = self.m.param_bounds.get(nm, (-np.inf, np.inf))
                self.m.params[nm] = float(min(max(v, lo), hi))
            self.param_history.append(dict(self.m.params))

    # ---- causal temporal weights: w_i = exp(-eps * sum_{k<i} r_k^2) ----
    def _causal_weights(self) -> np.ndarray:
        order = np.argsort(self.t_colloc)
        r2 = self._phys_residual()[order] ** 2
        cum = np.concatenate([[0.0], np.cumsum(r2)[:-1]])   # strictly earlier pts
        w = np.exp(-EPSILON_CAUSAL * cum)
        out = np.empty_like(w)
        out[order] = w
        return out

    # ---- parameter gradient norm of the physics loss ----
    def _param_grad_norm(self) -> float:
        r = self._phys_residual()
        x, dx, ddx = self.m.derivatives(self.t_colloc)
        gs = []
        for nm in self.m.params:
            d = max(1e-6, 1e-4 * (abs(self.m.params[nm]) + 1.0))
            p = dict(self.m.params); p[nm] += d
            rp = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p), float)
            gs.append(float(np.mean(r * (rp - r) / d)) * self.w_phys)
        return float(np.linalg.norm(gs))

    # ---- FIM identifiability — the SELF-DOUBT GATE ----
    def fisher_information(self) -> Tuple[np.ndarray, np.ndarray, float]:
        """FIM = J^T J / (Nc * sigma^2), J_{i,j} = d r_i / d eta_j at the solution.
        A near-zero column => the data carries no information about that parameter
        => UNIDENTIFIABLE. Returns (FIM, per-param Fisher diag, kappa(FIM))."""
        x, dx, ddx = self.m.derivatives(self.t_colloc)
        names = list(self.m.params)
        nc = self.t_colloc.shape[0]
        J = np.zeros((nc, len(names)))
        for j, nm in enumerate(names):
            d = max(1e-6, 1e-4 * (abs(self.m.params[nm]) + 1.0))
            p = dict(self.m.params); p[nm] += d
            rp = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p), float)
            p[nm] = self.m.params[nm] - d
            rm = np.asarray(self.m.residual_fn(self.t_colloc, x, dx, ddx, p), float)
            J[:, j] = (rp - rm) / (2 * d)
        sig2 = (self.noise_sigma ** 2) if self.noise_sigma else max(
            float(np.var(self.m.surrogate.predict(self.t_data) - self.y_data)), 1e-8)
        fim = (J.T @ J) / (nc * sig2)
        diag = np.diag(fim).copy()
        try:
            s = np.linalg.svd(fim, compute_uv=False)
            smax = float(s[0]); smin = float(s[-1])
            kappa = (smax / smin) if smin > 0 else float("inf")
        except np.linalg.LinAlgError:
            kappa = float("inf")
        return fim, diag, kappa

    # ---- full fit ----
    def fit(self, epochs: int = 600) -> ConvergenceRecord:
        if self.t_data.shape[0] < MIN_DATA_POINTS:
            raise ValueError(
                f"need >= {MIN_DATA_POINTS} data points to assert anything "
                f"(got {self.t_data.shape[0]})")
        self.m.surrogate.fit(self.t_data, self.y_data)
        # nonlinear params first (uses fixed surrogate derivatives), then exact LS
        self._gd_nonlinear(epochs)
        self._ls_solve_linear()
        return self._build_record(epochs)

    def _delta_param_rel(self, window: int = 20) -> float:
        if len(self.param_history) < window + 1:
            return 0.0 if self.m.linear_params else float("inf")
        recent = self.param_history[-window:]
        rels = []
        for k in self.m.params:
            if k in self.m.linear_params:
                continue
            vals = np.array([h[k] for h in recent])
            denom = max(abs(np.mean(vals)), 1e-9)
            rels.append(float(np.max(np.abs(np.diff(vals))) / denom))
        return float(max(rels)) if rels else 0.0

    def _build_record(self, epochs: int) -> ConvergenceRecord:
        wc = self._causal_weights()
        min_wc = float(np.min(wc)) if wc.size else 0.0
        gnorm = self._param_grad_norm()
        _, diag, kappa = self.fisher_information()
        dpr = self._delta_param_rel()
        r = self._phys_residual()
        rms = float(np.sqrt(np.mean(r * r)))
        d_rms = float(np.sqrt(np.mean((self.m.surrogate.predict(self.t_data) - self.y_data) ** 2)))
        # self-doubt: any per-param Fisher below the floor forces RED.
        min_fisher = float(np.min(diag)) if diag.size else 0.0
        label, crit = _classify_convergence(min_wc, gnorm, kappa, dpr, min_fisher)
        return ConvergenceRecord(
            label=label, min_causal_weight=min_wc, grad_norm=gnorm,
            kappa_fim=kappa, delta_param_rel=dpr, residual_rms=rms,
            data_rms=d_rms, epochs_run=int(epochs), criteria=crit)

    # ---- per-parameter governed results (value, CI, identifiability, assert) ----
    def param_results(self, n_restarts: int = 6, epochs: int = 400) -> List[ParamResult]:
        ci = self.ensemble_ci(n_restarts=n_restarts, epochs=epochs)
        _, diag, kappa = self.fisher_information()
        names = list(self.m.params)
        out: List[ParamResult] = []
        for j, nm in enumerate(names):
            mean, std, lo, hi = ci[nm]
            fisher = float(diag[j])
            identifiable = (fisher >= FISHER_FLOOR) and (kappa < KAPPA_RED) and math.isfinite(kappa)
            out.append(ParamResult(
                name=nm, value=float(self.m.params[nm]),
                ci_low=lo, ci_high=hi, std=std, fisher=fisher,
                identifiable=identifiable, asserted=identifiable))
        return out

    # ---- ensemble CI (E-PINN): bootstrap-resample data -> refit -> resolve ----
    def ensemble_ci(self, n_restarts: int = 6, epochs: int = 400
                    ) -> Dict[str, Tuple[float, float, float, float]]:
        names = list(self.m.params)
        samples: Dict[str, List[float]] = {k: [self.m.params[k]] for k in names}
        n = self.t_data.shape[0]
        for s in range(1, max(1, n_restarts)):
            idx = self.rng.integers(0, n, size=n)         # bootstrap resample
            mdl = SZLInversePINN(
                self.m.residual_fn,
                {k: (self.m.params[k] if k in self.m.linear_params
                     else self.rng.normal(self.m.params[k], 0.25 * abs(self.m.params[k]) + 0.1))
                 for k in names},
                surrogate=type(self.m.surrogate)(
                    getattr(self.m.surrogate, "K", 24), getattr(self.m.surrogate, "D", 3),
                    getattr(self.m.surrogate, "ridge", 1e-6))
                if isinstance(self.m.surrogate, SZLSpectralSurrogate) else SZLSpectralSurrogate(),
                param_bounds=self.m.param_bounds, linear_params=self.m.linear_params)
            tr = SZLInversePINNTrainer(
                mdl, self.t_data[idx], self.y_data[idx], self.t_colloc,
                self.w_phys, self.lr_param, self.noise_sigma, seed=s + 13)
            try:
                tr.fit(epochs=epochs)
                for k in names:
                    samples[k].append(mdl.params[k])
            except Exception:
                pass
        out: Dict[str, Tuple[float, float, float, float]] = {}
        for k in names:
            arr = np.array(samples[k], float)
            mean = float(np.mean(arr))
            std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
            out[k] = (mean, std, mean - 1.96 * std, mean + 1.96 * std)
        return out


# ===========================================================================
# 5. Three-state convergence classifier — EXACT criteria from ARXIV_LEADERS.
# ===========================================================================
def _classify_convergence(min_wc: float, grad_norm: float, kappa: float,
                          delta_param_rel: float, min_fisher: float
                          ) -> Tuple[str, Dict[str, str]]:
    crit = {
        "min_causal_weight": f"{min_wc:.4f} (GREEN>{CAUSAL_GREEN}, RED<={CAUSAL_RED})",
        "grad_norm": f"{grad_norm:.2e} (GREEN<{GRAD_GREEN:.0e})",
        "kappa_fim": f"{kappa:.2e} (IDENT<{KAPPA_IDENT:.0e}, RED>={KAPPA_RED:.0e})",
        "min_fisher": f"{min_fisher:.2e} (floor {FISHER_FLOOR:.0e}; below=UNIDENTIFIABLE)",
        "delta_param_rel": f"{delta_param_rel:.2e}",
    }
    # RED dominates: divergence, non-identifiability, or a below-floor Fisher.
    if (min_wc <= CAUSAL_RED) or (kappa >= KAPPA_RED) or (not math.isfinite(kappa)) \
            or (min_fisher < FISHER_FLOOR):
        return "RED", crit
    # GREEN requires ALL exact gates.
    if (min_wc > CAUSAL_GREEN) and (grad_norm < GRAD_GREEN) and (kappa < KAPPA_IDENT):
        return "GREEN", crit
    return "YELLOW", crit


# ===========================================================================
# 6. Built-in Duffing system — the runnable demo physics.
#    m x'' + c x' + delta x + alpha x^3 = F cos(omega t); alpha is the unknown.
# ===========================================================================
def duffing_residual(t, x, dx, ddx, params,
                     m=1.0, c=0.2, delta=1.0, F=0.5, omega=1.0):
    alpha = params.get("alpha", 0.0)
    ghost = params.get("ghost", 0.0)   # enters with coefficient 0 -> UNIDENTIFIABLE
    return (m * ddx + c * dx + delta * x + alpha * (x ** 3)
            - F * np.cos(omega * t) + 0.0 * ghost)


def integrate_duffing(t, m=1.0, c=0.2, delta=1.0, alpha=1.0, F=0.5, omega=1.0,
                      x0=0.0, v0=0.0):
    """RK4 integration of the Duffing oscillator (own NumPy integrator; no scipy
    dependency). Returns x(t) on the given grid."""
    t = np.asarray(t, float)
    def deriv(state, tt):
        x, v = state
        a = (F * math.cos(omega * tt) - c * v - delta * x - alpha * x ** 3) / m
        return np.array([v, a])
    xs = np.empty_like(t)
    state = np.array([x0, v0], float)
    xs[0] = state[0]
    for i in range(1, len(t)):
        h = t[i] - t[i - 1]
        k1 = deriv(state, t[i - 1])
        k2 = deriv(state + 0.5 * h * k1, t[i - 1] + 0.5 * h)
        k3 = deriv(state + 0.5 * h * k2, t[i - 1] + 0.5 * h)
        k4 = deriv(state + h * k3, t[i])
        state = state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        xs[i] = state[0]
    return xs
