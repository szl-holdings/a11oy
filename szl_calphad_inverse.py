#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
#
# szl_calphad_inverse.py — Governed CALPHAD inverse-discovery system for the SZL
# Inverse-PINN engine. Taxonomy: services (frontier discovery surface) + provenance.
#
# Doctrine v11 LOCKED · Lambda = Conjecture 1 (advisory). 8 locked-proven.
#
# WHAT THIS IS
#   The FIRST materials-by-design vertical: a governed inverse-discovery of the
#   Redlich-Kister BINARY interaction parameters L0, L1, L2 of the excess Gibbs
#   energy of a solution phase, recovered from sparse synthetic mixing-enthalpy
#   data. It is the same HONEST self-doubt engine as the Duffing demo, applied to
#   thermodynamics: a parameter the data cannot identify is labelled
#   RED/UNIDENTIFIABLE and the engine REFUSES to assert it (Fisher-information +
#   FIM-conditioning gate). Plus a convex-hull thermodynamic-stability PLAUSIBILITY
#   check (not a guarantee).
#
# THE MATH (RE-IMPLEMENTED from public equations, OWN CODE — NumPy BSD-3 only):
#   Excess Gibbs energy via the Redlich-Kister polynomial (Redlich & Kister 1948):
#       G_xs(x) = x (1-x) * sum_k  L_k * (1 - 2x)^k
#   For temperature-independent L_k the excess entropy is zero, so the molar
#   enthalpy of mixing equals the excess Gibbs energy:  H_mix(x) = G_xs(x).
#   This is LINEAR in the unknowns L_k, so the inverse problem is a single
#   regularised least-squares solve with an EXACT parameter covariance
#   sigma^2 (Phi^T Phi)^{-1} -> per-parameter 95% confidence interval, and an
#   EXACT Fisher Information Matrix FIM = (Phi^T Phi)/sigma^2 for the self-doubt
#   identifiability gate. The full molar Gibbs energy of mixing
#       G_mix(x) = R T [x ln x + (1-x) ln(1-x)] + G_xs(x)
#   feeds the convex-hull stability plausibility check (common-tangent / lower
#   convex hull -> single-phase vs miscibility-gap).
#
#   LICENSES: the Redlich-Kister math is public (Redlich & Kister 1948; Honarmandi
#   et al. 2019 Bayesian CALPHAD UQ, DOI:10.1088/1361-651X/ab08c3; Kattner
#   PMC4912057). OpenCalphad is GPL-v3 and Thermo-Calc is proprietary — REFERENCE
#   ONLY; nothing here is imported or linked from them. Every equation above is
#   reimplemented from the peer-reviewed equations.
#
# HONEST LABELS: every numeric result here is MODELED — a fit to SYNTHETIC data
#   in a governed-discovery DEMO. It is NOT a validated materials prediction and
#   NOT the discovery of a real new alloy. The convex-hull check is a PLAUSIBILITY
#   check, not a thermodynamic guarantee. The 8 locked-proven inequalities are not
#   touched; F19 (Bekenstein) is APPLIED, not re-claimed; Lambda stays Conjecture 1.

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Reuse the EXACT honest thresholds from the bare engine — the CALPHAD system
# rides the same self-doubt contract as Duffing (no per-system loosening).
from szl_pinn_inverse import (
    KAPPA_IDENT, KAPPA_RED, FISHER_FLOOR, MIN_DATA_POINTS,
)

R_GAS = 8.314462618          # J/(mol*K) — molar gas constant (CODATA)

__all__ = [
    "rk_excess_gibbs",
    "rk_design",
    "gibbs_of_mixing",
    "convex_hull_stability",
    "RKResult",
    "solve_redlich_kister",
    "ensemble_ci_rk",
    "classify_calphad",
    "make_calphad_data",
    "param_results_rk",
    "RK_SYSTEMS",
    "CALPHAD_CITATIONS",
]

# Synthetic ground-truth binaries (J/mol). These are illustrative, physically
# reasonable RK magnitudes (CALPHAD L_k are typically 1e3-1e5 J/mol); they are
# NOT assessed values for any real alloy — purely for the governed DEMO.
RK_SYSTEMS = {
    "redlich_kister": {
        "desc": ("Synthetic Ni-Al-like binary excess Gibbs energy "
                 "G_xs = x(1-x) sum_k L_k (1-2x)^k (Redlich-Kister 1948)"),
        "truth": [-40000.0, 8000.0, -5000.0],   # L0, L1, L2 (J/mol)
        "T": 1000.0,                             # K (isothermal demo)
        "order": 2,
        "components": ["A(~Ni)", "B(~Al)"],
    },
}

CALPHAD_CITATIONS = [
    "Redlich & Kister 1948, Ind. Eng. Chem. 40(2):345 (algebraic representation "
    "of thermodynamic properties / the RK polynomial)",
    "Honarmandi et al. 2019, Modelling Simul. Mater. Sci. Eng. — Bayesian CALPHAD "
    "uncertainty quantification, DOI:10.1088/1361-651X/ab08c3",
    "Kattner 2016, JOM / PMC4912057 — the CALPHAD method review",
    "OpenCalphad (sundmanbo) GPL-v3 — REFERENCE ONLY, not imported or linked; "
    "math reimplemented from the equations above (Thermo-Calc not used).",
]


# ---------------------------------------------------------------------------
# 1. Redlich-Kister algebra (own code).
# ---------------------------------------------------------------------------
def rk_excess_gibbs(x, L: Sequence[float]) -> np.ndarray:
    """G_xs(x) = x(1-x) * sum_k L_k (1-2x)^k. Pure RK polynomial."""
    x = np.asarray(x, float)
    s = np.zeros_like(x, dtype=float)
    for k, Lk in enumerate(L):
        s = s + float(Lk) * (1.0 - 2.0 * x) ** k
    return x * (1.0 - x) * s


def rk_design(x, order: int) -> np.ndarray:
    """Design matrix Phi[i,k] = x_i(1-x_i)(1-2x_i)^k for k=0..order. The inverse
    problem H_mix = Phi @ L is LINEAR in L, so the columns ARE the per-parameter
    sensitivities used by the Fisher-information self-doubt gate."""
    x = np.asarray(x, float).reshape(-1)
    cols = [x * (1.0 - x) * (1.0 - 2.0 * x) ** k for k in range(int(order) + 1)]
    return np.stack(cols, axis=1)


def gibbs_of_mixing(x, L: Sequence[float], T: float) -> np.ndarray:
    """Full molar Gibbs energy of mixing G_mix = RT[x ln x + (1-x)ln(1-x)] + G_xs.
    Ideal configurational entropy + RK excess term."""
    x = np.clip(np.asarray(x, float), 1e-12, 1.0 - 1e-12)
    ideal = R_GAS * float(T) * (x * np.log(x) + (1.0 - x) * np.log(1.0 - x))
    return ideal + rk_excess_gibbs(x, L)


# ---------------------------------------------------------------------------
# 2. Convex-hull thermodynamic-stability PLAUSIBILITY check (not a guarantee).
#    Lower convex hull of G_mix(x): points strictly above the hull lie inside a
#    common-tangent (two-phase) region -> miscibility gap. A purely convex G_mix
#    -> single-phase stable. This is a sanity CHECK on the recovered parameters.
# ---------------------------------------------------------------------------
def convex_hull_stability(L: Sequence[float], T: float, n_grid: int = 201) -> Dict:
    x = np.linspace(1e-3, 1.0 - 1e-3, int(n_grid))
    g = gibbs_of_mixing(x, L, T)
    # monotone-chain lower hull (own code; no scipy).
    hull: List[Tuple[float, float]] = []
    for px, pg in zip(x, g):
        while len(hull) >= 2:
            (x1, g1), (x2, g2) = hull[-2], hull[-1]
            cross = (x2 - x1) * (pg - g1) - (g2 - g1) * (px - x1)
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append((float(px), float(pg)))
    hx = np.array([p[0] for p in hull])
    hg = np.array([p[1] for p in hull])
    g_hull = np.interp(x, hx, hg)
    above = g - g_hull
    gap_frac = float(np.mean(above > 1.0))            # >1 J/mol above the hull
    d2 = np.gradient(np.gradient(g, x), x)
    min_d2 = float(np.min(d2[5:-5]))                  # interior curvature
    gap = gap_frac > 0.01
    return {
        "stable": (not gap),
        "verdict": "single_phase_stable" if not gap else "miscibility_gap_predicted",
        "miscibility_gap_fraction": round(gap_frac, 4),
        "min_d2G_dx2": min_d2,
        "convex_everywhere": bool(min_d2 > 0.0),
        "hull_vertices": int(len(hull)),
        "T_kelvin": float(T),
        "basis": ("lower convex hull / common-tangent of G_mix(x); this is a "
                  "PLAUSIBILITY check, NOT a thermodynamic guarantee"),
        "label": "MODELED",
    }


# ---------------------------------------------------------------------------
# 3. The linear inverse solve (exact LS) + exact covariance + exact FIM.
# ---------------------------------------------------------------------------
@dataclass
class RKResult:
    order: int
    L: np.ndarray                 # recovered L_k
    std: np.ndarray               # per-param standard error
    ci_low: np.ndarray
    ci_high: np.ndarray
    fisher_diag: np.ndarray       # per-param Fisher information (FIM diagonal)
    kappa_fim: float              # condition number of the FIM
    sigma: float                  # noise sigma used
    normal_eq_resid: float        # ||Phi^T(Phi L - h)|| — LS stationarity proof
    data_rms: float               # RMS data misfit (J/mol)
    data_scale: float             # RMS of |h| (for normalised misfit)


def solve_redlich_kister(x, h, order: int = 2,
                         noise_sigma: Optional[float] = None,
                         ridge: float = 0.0) -> RKResult:
    """Recover L_0..L_order from (composition x, mixing enthalpy h) by exact
    regularised least squares, with the EXACT parameter covariance and Fisher
    information used by the self-doubt gate. No fitting tricks; the normal
    equations are solved exactly so the LS objective is stationary by
    construction (reported as normal_eq_resid)."""
    x = np.asarray(x, float).reshape(-1)
    h = np.asarray(h, float).reshape(-1)
    if x.shape[0] != h.shape[0]:
        raise ValueError("x and h must have equal length")
    p = int(order) + 1
    Phi = rk_design(x, order)
    G = Phi.T @ Phi + float(ridge) * np.eye(p)
    L = np.linalg.solve(G, Phi.T @ h)
    resid = h - Phi @ L
    n = x.shape[0]
    dof = max(1, n - p)
    if noise_sigma and noise_sigma > 0:
        sigma = float(noise_sigma)
    else:
        sigma = math.sqrt(max(float(np.sum(resid ** 2)) / dof, 1e-12))
    sig2 = max(sigma ** 2, 1e-12)
    # exact parameter covariance for a linear model: sigma^2 (Phi^T Phi)^{-1}
    GtG = Phi.T @ Phi
    try:
        cov = sig2 * np.linalg.inv(GtG)
        std = np.sqrt(np.clip(np.diag(cov), 0.0, np.inf))
    except np.linalg.LinAlgError:
        std = np.full(p, np.inf)
    fim = GtG / sig2
    fisher_diag = np.diag(fim).copy()
    try:
        sv = np.linalg.svd(fim, compute_uv=False)
        smax, smin = float(sv[0]), float(sv[-1])
        kappa = (smax / smin) if smin > 0 else float("inf")
    except np.linalg.LinAlgError:
        kappa = float("inf")
    neq = float(np.linalg.norm(Phi.T @ (Phi @ L - h)))
    data_rms = float(np.sqrt(np.mean(resid ** 2)))
    data_scale = float(np.sqrt(np.mean(h ** 2))) or 1.0
    return RKResult(
        order=int(order), L=L, std=std,
        ci_low=L - 1.96 * std, ci_high=L + 1.96 * std,
        fisher_diag=fisher_diag, kappa_fim=kappa, sigma=sigma,
        normal_eq_resid=neq, data_rms=data_rms, data_scale=data_scale)


def ensemble_ci_rk(x, h, order: int = 2, noise_sigma: Optional[float] = None,
                   n_restarts: int = 24, seed: int = 1
                   ) -> Dict[int, Tuple[float, float, float, float]]:
    """Bootstrap-resample (x,h) -> refit -> collect L_k, giving an empirical
    95% credible interval per parameter that AGREES with the analytic covariance
    when the problem is well-posed and BLOWS UP when it is not."""
    x = np.asarray(x, float).reshape(-1)
    h = np.asarray(h, float).reshape(-1)
    n = x.shape[0]
    rng = np.random.default_rng(seed)
    base = solve_redlich_kister(x, h, order, noise_sigma)
    samples: Dict[int, List[float]] = {k: [float(base.L[k])] for k in range(order + 1)}
    for _ in range(max(1, n_restarts) - 1):
        idx = rng.integers(0, n, size=n)
        try:
            r = solve_redlich_kister(x[idx], h[idx], order, noise_sigma)
            for k in range(order + 1):
                samples[k].append(float(r.L[k]))
        except Exception:
            pass
    out: Dict[int, Tuple[float, float, float, float]] = {}
    for k in range(order + 1):
        arr = np.asarray(samples[k], float)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
        out[k] = (mean, std, mean - 1.96 * std, mean + 1.96 * std)
    return out


# ---------------------------------------------------------------------------
# 4. Three-state classifier — reuses the EXACT engine thresholds (no loosening).
# ---------------------------------------------------------------------------
def classify_calphad(kappa: float, min_fisher: float, norm_resid: float
                     ) -> Tuple[str, Dict[str, str]]:
    crit = {
        "kappa_fim": f"{kappa:.2e} (IDENT<{KAPPA_IDENT:.0e}, RED>={KAPPA_RED:.0e})",
        "min_fisher": f"{min_fisher:.2e} (floor {FISHER_FLOOR:.0e}; below=UNIDENTIFIABLE)",
        "normalised_data_rms": f"{norm_resid:.3e} (GREEN<0.05)",
    }
    if (kappa >= KAPPA_RED) or (not math.isfinite(kappa)) or (min_fisher < FISHER_FLOOR):
        return "RED", crit
    if (kappa < KAPPA_IDENT) and (min_fisher >= FISHER_FLOOR) and (norm_resid < 0.05):
        return "GREEN", crit
    return "YELLOW", crit


# ---------------------------------------------------------------------------
# 5. Per-parameter governed results — value, CI, identifiability, REFUSAL.
#    Same self-doubt gate as Duffing: Fisher >= floor AND kappa < KAPPA_RED.
# ---------------------------------------------------------------------------
def param_results_rk(res: RKResult, ci: Dict[int, Tuple[float, float, float, float]],
                     truth: Optional[Sequence[float]] = None) -> List[Dict]:
    out: List[Dict] = []
    for k in range(res.order + 1):
        fisher = float(res.fisher_diag[k])
        identifiable = (fisher >= FISHER_FLOOR) and (res.kappa_fim < KAPPA_RED) \
            and math.isfinite(res.kappa_fim)
        _, e_std, e_lo, e_hi = ci.get(k, (float(res.L[k]), float(res.std[k]),
                                          float(res.ci_low[k]), float(res.ci_high[k])))
        name = "L%d" % k
        block = {
            "name": name,
            "asserted": identifiable,
            "value": (round(float(res.L[k]), 4) if identifiable else None),
            "ci95": ([round(float(res.ci_low[k]), 4), round(float(res.ci_high[k]), 4)]
                     if identifiable else None),
            "ci95_bootstrap": ([round(e_lo, 4), round(e_hi, 4)] if identifiable else None),
            "std": round(float(res.std[k]), 6),
            "fisher_information": fisher,
            "identifiable": identifiable,
            "units": "J/mol",
            "label": "MODELED",
        }
        if truth is not None and k < len(truth):
            block["ground_truth"] = float(truth[k])
            if identifiable:
                block["recovery_abs_err"] = round(abs(float(res.L[k]) - float(truth[k])), 4)
        if not identifiable:
            if fisher < FISHER_FLOOR:
                why = ("Fisher information %.2e is below the floor %.0e — the data "
                       "carry no information about this RK parameter (composition "
                       "range too narrow to excite the (1-2x)^%d term)"
                       % (fisher, FISHER_FLOOR, k))
            else:
                why = ("the FIM is ill-conditioned (kappa=%.2e >= %.0e) — the L_k are "
                       "jointly non-identifiable from these data"
                       % (res.kappa_fim, KAPPA_RED))
            block["refusal"] = ("UNIDENTIFIABLE: %s. The engine REFUSES to assert this "
                                "parameter." % why)
        out.append(block)
    return out


# ---------------------------------------------------------------------------
# 6. Synthetic data generator — a clean GREEN case and a deliberately ill-posed
#    RED case (composition clustered near x=0.5 so high-order L_k vanish).
# ---------------------------------------------------------------------------
def make_calphad_data(case: str = "identifiable", options: Optional[Dict] = None):
    """Return (x, h, sigma, truth, T, order, desc, used_demo, data_label, case).
    case='identifiable' -> well-spread compositions -> GREEN recovery.
    case='ill_posed'    -> compositions clustered near x=0.5 -> RED/REFUSE."""
    opts = dict(options or {})
    sysdef = RK_SYSTEMS["redlich_kister"]
    truth = list(opts.get("truth", sysdef["truth"]))
    T = float(opts.get("T", sysdef["T"]))
    order = int(opts.get("order", sysdef["order"]))
    seed = int(opts.get("seed", 0))
    rng = np.random.default_rng(seed)
    case = (case or "identifiable").strip().lower()
    if case in ("ill_posed", "ill-posed", "illposed", "red", "unidentifiable"):
        sigma = float(opts.get("noise", 300.0))       # J/mol synthetic noise
        n = int(opts.get("n_points", 14))
        n = max(MIN_DATA_POINTS, min(n, 600))
        win = float(opts.get("x_window", 0.05))       # half-width around x=0.5
        x = np.linspace(0.5 - win, 0.5 + win, n)
        case = "ill_posed"
    else:
        sigma = float(opts.get("noise", 150.0))       # J/mol synthetic noise
        n = int(opts.get("n_points", 30))
        n = max(MIN_DATA_POINTS, min(n, 600))
        x = np.linspace(0.05, 0.95, n)
        case = "identifiable"
    h = rk_excess_gibbs(x, truth) + rng.normal(0.0, sigma, size=x.shape)
    return x, h, max(sigma, 1e-6), truth, T, order, sysdef["desc"], True, \
        "MODELED synthetic (demo)", case
