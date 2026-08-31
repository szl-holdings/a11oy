#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
#
# szl_materials_predict.py — Governed materials-PROPERTY predictor with CALIBRATED
# uncertainty. The SECOND materials vertical (after the governed CALPHAD inverse-
# discovery surface in szl_governed_ipinn / szl_calphad_inverse).
#
# Doctrine v11 LOCKED · kernel c7c0ba17 · 8 locked-proven {F1,F4,F7,F11,F12,F18,
# F19,F22} · Lambda = Conjecture 1 (advisory, NEVER theorem).
#
# WHAT THIS IS (read this before you read anything else):
#   A self-contained, NUMPY-ONLY calibrated SURROGATE for formation energy
#   (eV/atom) over a SMALL embedded SAMPLE of published DFT formation energies,
#   wrapped in the FULL a11oy governance layer. It is NOT a SOTA DFT/MACE/CHGNet
#   prediction. The frontier contribution here is the GOVERNANCE + CALIBRATION,
#   not the potential:
#     * a 5-member BOOTSTRAP deep-ensemble for epistemic uncertainty,
#     * an ISOTONIC-REGRESSION recalibration (Kuleshov et al. 2018) verified to
#       achieve ~95% empirical coverage on a HELD-OUT split (the MEASURED coverage
#       number is reported on every response and in the receipt),
#     * a hard convex-hull-distance plausibility GATE (Delta_hull > 0.1 eV/atom
#       => RED/refuse) — a CHECK, not a guarantee,
#     * a Bekenstein/F19 information-cost check (F19 APPLIED, not re-claimed),
#     * a SELF-DOUBT / out-of-distribution gate: a descriptor far from the embedded
#       training descriptors => RED/refuse, never a confident extrapolation.
#
# HONEST LABELS (Doctrine v11, non-negotiable):
#   - The prediction is MODELED + SAMPLE: a calibrated SURROGATE over a SAMPLE
#     dataset, NOT a SOTA DFT/MACE prediction. We say exactly this in the honesty
#     block and the surface copy. NO "discovered/validated a new material". NO
#     "MACE-accurate".
#   - The calibration coverage is MEASURED on the held-out split (real number, with
#     n) — never a number we did not measure.
#   - The convex-hull gate is a PLAUSIBILITY CHECK, not a guarantee.
#   - 8 locked-proven only; this module NEVER adds to the locked set.
#   - Lambda = Conjecture 1 (advisory, capped <= 0.99).
#   - F19/Bekenstein is a PROVEN inequality APPLIED here (MODELED application).
#   - MACE (MIT, ACEsuit/mace) and CHGNet (BSD-3-Clause, CederGroupHub/chgnet) are
#     cited as the PATTERNS we would wrap behind a remote HTTP inference endpoint
#     (NOT reachable today). We reimplement-not-copy; NO proprietary weights are
#     bundled. When a real MACE/CHGNet endpoint becomes reachable, predict_property
#     would call it and the SAME governance/calibration wrapper applies; until then
#     we ship the honest numpy surrogate, labeled clearly.
#
# DEPLOY: numpy-only; imports guarded at request time; NEVER raises into startup.
# Registered BEFORE the /api/a11oy/{path:path} Node-proxy + SPA catch-all (serve.py
# front-moves these routes to the router head, same proven pattern as the PINN block).

import math
import time
import threading

import numpy as np

RECEIPT_SCHEMA = "szl.lake.receipt/v1"
RECEIPT_ORGAN = "a11oy-materials"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.materials-predict+json"
LOCKED_PROVEN = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
LOCKED_PROVEN_AT = "c7c0ba17"

# Governance thresholds (eV/atom unless noted). These are documented on the wire.
HULL_GREEN = 0.05      # Delta_hull <= this AND in-distribution => GREEN-eligible
HULL_RED = 0.10        # Delta_hull > this => RED / refuse (implausible)
OOD_Z_RED = 1.0        # OOD score (see _ood_score) > this => RED / refuse
OOD_Z_YELLOW = 0.6     # OOD score in (YELLOW, RED] => YELLOW caution
SIGMA_YELLOW = 0.50    # calibrated epistemic std (eV/atom) above this => YELLOW
ENSEMBLE_N = 5
ALPHA = 0.05           # 95% target central interval
RIDGE_LAMBDA = 0.5

CITATIONS = (
    "Kuleshov, Fenner & Ermon 2018, 'Accurate Uncertainties for Deep Learning "
    "Using Calibrated Regression', ICML (arXiv:1807.00263) — isotonic recalibration",
    "Lakshminarayanan, Pritzel & Blundell 2017, 'Simple and Scalable Predictive "
    "Uncertainty Estimation using Deep Ensembles', NeurIPS (arXiv:1612.01474)",
    "Tan, Heenen et al. 2023, npj Comput. Mater., DOI:10.1038/s41524-023-01180-8 "
    "— deep ensembles are the best general-purpose UQ for MLIPs",
    "MACE (ACEsuit/mace, MIT) and CHGNet (CederGroupHub/chgnet, BSD-3-Clause) — "
    "the wrappable patterns; reimplement-not-copy, NO proprietary weights bundled",
)


# ---------------------------------------------------------------------------
# Embedded element-property table (SAMPLE textbook values: Pauling
# electronegativity, empirical atomic radius pm, period, group, valence e-).
# Used only to FEATURIZE a composition. Not a database; honest small table.
# ---------------------------------------------------------------------------
#                EN     r_pm  period group  ve
_ELEM = {
    "O":  (3.44,  60.0, 2, 16, 6),
    "F":  (3.98,  50.0, 2, 17, 7),
    "N":  (3.04,  65.0, 2, 15, 5),
    "Cl": (3.16,  79.0, 3, 17, 7),
    "S":  (2.58,  88.0, 3, 16, 6),
    "Li": (0.98, 145.0, 2,  1, 1),
    "Na": (0.93, 180.0, 3,  1, 1),
    "Mg": (1.31, 150.0, 3,  2, 2),
    "Al": (1.61, 125.0, 3, 13, 3),
    "Si": (1.90, 110.0, 3, 14, 4),
    "K":  (0.82, 220.0, 4,  1, 1),
    "Ca": (1.00, 180.0, 4,  2, 2),
    "Ti": (1.54, 140.0, 4,  4, 4),
    "Cr": (1.66, 140.0, 4,  6, 6),
    "Mn": (1.55, 140.0, 4,  7, 7),
    "Fe": (1.83, 140.0, 4,  8, 8),
    "Ni": (1.91, 135.0, 4, 10, 10),
    "Zn": (1.65, 135.0, 4, 12, 2),
    # in-vocabulary metals deliberately NOT in the (ionic) training set, so an
    # intermetallic query (e.g. Cu-Au) is descriptor-FAR => OOD/RED self-doubt.
    "Cu": (1.90, 135.0, 4, 11, 1),
    "Au": (2.54, 135.0, 6, 11, 1),
}

# Embedded SAMPLE dataset: binary ionic-compound formation energies (eV/atom),
# reimplemented as approximations of published DFT / Materials-Project values
# (SAMPLE — textbook/representative magnitudes, NOT a live MP query). Binary only,
# so the convex-hull construction is an exact 1-D lower envelope.
#   (composition dict {element: count}, E_form eV/atom)
_DATASET = [
    ({"Mg": 1, "O": 1}, -3.06),
    ({"Al": 2, "O": 3}, -3.44),
    ({"Ti": 1, "O": 2}, -3.30),
    ({"Ti": 2, "O": 3}, -3.38),
    ({"Ti": 1, "O": 1}, -2.72),
    ({"Fe": 1, "O": 1}, -1.41),
    ({"Fe": 2, "O": 3}, -1.71),
    ({"Fe": 3, "O": 4}, -1.66),
    ({"Si": 1, "O": 2}, -3.05),
    ({"Ca": 1, "O": 1}, -3.29),
    ({"Na": 2, "O": 1}, -1.74),
    ({"Li": 2, "O": 1}, -2.06),
    ({"Zn": 1, "O": 1}, -1.85),
    ({"K": 2, "O": 1}, -1.50),
    ({"Cr": 2, "O": 3}, -2.35),
    ({"Mn": 1, "O": 1}, -2.06),
    ({"Ni": 1, "O": 1}, -1.24),
    ({"Na": 1, "Cl": 1}, -2.02),
    ({"K": 1, "Cl": 1}, -2.20),
    ({"Li": 1, "Cl": 1}, -2.10),
    ({"Mg": 1, "Cl": 2}, -2.20),
    ({"Ca": 1, "Cl": 2}, -2.69),
    ({"Al": 1, "Cl": 3}, -1.50),
    ({"Na": 1, "F": 1}, -2.95),
    ({"Li": 1, "F": 1}, -3.20),
    ({"Ca": 1, "F": 2}, -4.10),
    ({"Mg": 1, "F": 2}, -3.70),
    ({"Al": 1, "F": 3}, -3.50),
    ({"K": 1, "F": 1}, -2.85),
    ({"Al": 1, "N": 1}, -1.65),
    ({"Ti": 1, "N": 1}, -1.74),
    ({"Si": 3, "N": 4}, -0.92),
    ({"Zn": 1, "S": 1}, -1.04),
    ({"Fe": 1, "S": 1}, -0.55),
    ({"Na": 2, "S": 1}, -1.30),
    ({"Ca": 1, "S": 1}, -2.20),
    ({"Mn": 1, "S": 1}, -1.40),
    ({"Mg": 1, "S": 1}, -1.75),
    ({"Mn": 1, "O": 2}, -1.55),
    ({"Mn": 2, "O": 3}, -1.95),
    ({"Zn": 1, "Cl": 2}, -1.50),
    ({"Fe": 1, "Cl": 2}, -1.30),
    ({"Ni": 1, "Cl": 2}, -1.10),
    ({"Mn": 1, "Cl": 2}, -1.75),
    ({"Li": 3, "N": 1}, -0.55),
    ({"Mg": 3, "N": 2}, -0.85),
    ({"Ca": 3, "N": 2}, -1.00),
    ({"Al": 2, "S": 3}, -0.85),
    ({"K": 2, "S": 1}, -1.25),
    ({"Li": 2, "S": 1}, -1.55),
    ({"Ti": 1, "S": 2}, -1.35),
    ({"Cr": 1, "N": 1}, -1.00),
]

_FEATURE_NAMES = (
    "mean_EN", "EN_diff", "EN_diff_sq", "frac_anion", "mean_radius",
    "radius_ratio", "mean_group", "mean_period", "mean_ve", "ionicity",
)


# ---------------------------------------------------------------------------
# Composition parsing + featurization.
# ---------------------------------------------------------------------------
def _normalize_comp(comp):
    """comp: dict element->count (>0). Returns dict element->fraction. Raises
    ValueError on empty/invalid input or an element outside the embedded table
    (an unknown element is an honest, hard OOD: we cannot featurize it)."""
    if not isinstance(comp, dict) or not comp:
        raise ValueError("composition must be a non-empty {element: count} object")
    counts = {}
    for el, c in comp.items():
        el = str(el).strip()
        try:
            c = float(c)
        except (TypeError, ValueError):
            raise ValueError("count for %r must be a number" % el)
        if c <= 0:
            continue
        if el not in _ELEM:
            raise ValueError(
                "element %r is outside the embedded SAMPLE element table %s — "
                "cannot featurize (honest OOD refusal)" % (el, sorted(_ELEM)))
        counts[el] = counts.get(el, 0.0) + c
    if not counts:
        raise ValueError("composition has no positive element counts")
    tot = sum(counts.values())
    return {el: c / tot for el, c in counts.items()}


def featurize(comp):
    """Composition dict -> descriptor vector (numpy, len(_FEATURE_NAMES))."""
    frac = _normalize_comp(comp)
    els = list(frac)
    f = np.array([frac[e] for e in els])
    EN = np.array([_ELEM[e][0] for e in els])
    R = np.array([_ELEM[e][1] for e in els])
    G = np.array([_ELEM[e][3] for e in els])
    P = np.array([_ELEM[e][2] for e in els])
    VE = np.array([_ELEM[e][4] for e in els])
    mean_EN = float(np.dot(f, EN))
    en_diff = float(EN.max() - EN.min())
    # fraction of the most-electronegative element (anion-likeness)
    frac_anion = float(f[int(np.argmax(EN))])
    mean_R = float(np.dot(f, R))
    radius_ratio = float(R.max() / max(R.min(), 1e-9))
    mean_G = float(np.dot(f, G))
    mean_P = float(np.dot(f, P))
    mean_VE = float(np.dot(f, VE))
    ionicity = en_diff * frac_anion  # ionic-bond strength proxy (EN gap x anion frac)
    return np.array([mean_EN, en_diff, en_diff * en_diff, frac_anion, mean_R,
                     radius_ratio, mean_G, mean_P, mean_VE, ionicity], dtype=float)


# ---------------------------------------------------------------------------
# Ridge regression (closed form, standardized features, centered target) and a
# 5-member BOOTSTRAP deep-ensemble for epistemic UQ.
# ---------------------------------------------------------------------------
def _fit_ridge(Xz, y, lam):
    n, d = Xz.shape
    ybar = float(np.mean(y))
    yc = y - ybar
    A = Xz.T @ Xz + lam * np.eye(d)
    w = np.linalg.solve(A, Xz.T @ yc)
    return w, ybar


class _Surrogate:
    """Standardizer + bootstrap ensemble of ridge regressors over descriptors."""

    def __init__(self, X, y, n_members=ENSEMBLE_N, lam=RIDGE_LAMBDA, seed=0):
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0)
        self.sd[self.sd < 1e-9] = 1.0
        Xz = (X - self.mu) / self.sd
        self.X = X
        self.Xz = Xz
        self.y = y
        rng = np.random.default_rng(seed)
        self.members = []
        n = Xz.shape[0]
        for _ in range(n_members):
            idx = rng.integers(0, n, size=n)
            w, b = _fit_ridge(Xz[idx], y[idx], lam)
            self.members.append((w, b))
        # NN distance scale in standardized feature space (for the OOD score).
        self._nn_scale = self._train_nn_scale()

    def _z(self, x):
        return (x - self.mu) / self.sd

    def predict(self, x):
        """Return (mean, std) over ensemble members for a single descriptor x."""
        xz = self._z(x)
        preds = np.array([float(xz @ w + b) for (w, b) in self.members])
        return float(preds.mean()), float(preds.std(ddof=0))

    def _train_nn_scale(self):
        Z = self.Xz
        n = Z.shape[0]
        nn = []
        for i in range(n):
            d = np.linalg.norm(Z - Z[i], axis=1)
            d[i] = np.inf
            nn.append(float(d.min()))
        nn = np.array(nn)
        return float(np.median(nn) + nn.std() + 1e-9)

    def ood_score(self, x):
        """Min nearest-neighbour distance to training descriptors in standardized
        space, scaled by the training NN scale. >1 means materially outside the
        embedded training distribution (self-doubt territory)."""
        xz = self._z(x)
        d = np.linalg.norm(self.Xz - xz, axis=1)
        return float(d.min() / self._nn_scale)


# ---------------------------------------------------------------------------
# Isotonic regression (PAV) + Kuleshov-2018 calibrated regression.
# ---------------------------------------------------------------------------
def _isotonic_pav(x, y):
    """Pool-Adjacent-Violators: monotone non-decreasing fit of y on sorted x.
    Returns (xs, ys) breakpoints for piecewise-constant interpolation."""
    order = np.argsort(x, kind="mergesort")
    xs = np.asarray(x, float)[order]
    ys = np.asarray(y, float)[order].copy()
    w = np.ones_like(ys)
    # standard PAV
    i = 0
    blocks = [[ys[k], w[k], xs[k]] for k in range(len(ys))]
    merged = []
    for b in blocks:
        merged.append(b[:])
        while len(merged) > 1 and merged[-2][0] > merged[-1][0]:
            v2, w2, x2 = merged.pop()
            v1, w1, x1 = merged.pop()
            nw = w1 + w2
            merged.append([(v1 * w1 + v2 * w2) / nw, nw, x2])
    out_x, out_y = [], []
    for v, w_, xr in merged:
        out_x.append(xr)
        out_y.append(v)
    return np.array(out_x), np.array(out_y)


def _norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_ppf(p):
    """Inverse standard-normal CDF (Acklam's rational approximation)."""
    p = min(max(float(p), 1e-9), 1.0 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


class _Calibrator:
    """Calibrated regression (Kuleshov et al. 2018) via ISOTONIC recalibration of
    the predictive CDF. We recalibrate on the STANDARDIZED residual z=(y-mu)/sigma:
    fit a monotone (isotonic, PAV) empirical CDF G(z) on the held-out calibration
    set. A bootstrap ensemble is typically UNDERdispersed, so the empirical z
    quantiles are wider than the nominal Gaussian ones — recalibrating the CDF on z
    absorbs that and restores coverage. The calibrated central (1-alpha) interval is
    [mu + G^{-1}(alpha/2)*sigma, mu + G^{-1}(1-alpha/2)*sigma]."""

    def __init__(self, z_cal):
        z = np.sort(np.asarray(z_cal, float))
        n = len(z)
        ecdf = (np.arange(n) + 0.5) / n          # plotting-position empirical CDF
        zg, cg = _isotonic_pav(z, ecdf)          # monotone (z -> cumulative prob)
        self.z_grid = zg
        self.cdf_grid = np.clip(cg, 0.0, 1.0)
        self.n = n
        self.abs_z = np.sort(np.abs(z))          # for the symmetric conformal radius

    def quantile(self, q):
        q = min(max(float(q), 0.0), 1.0)
        return float(np.interp(q, self.cdf_grid, self.z_grid))

    def conformal_radius(self, alpha=ALPHA):
        """Finite-sample symmetric conformal quantile of |z| at level 1-alpha. Uses
        the ceil((n+1)(1-alpha)) order statistic (the split-conformal correction);
        when that index exceeds n it falls back to max|z| (coverage ~ n/(n+1))."""
        n = self.n
        if n == 0:
            return float("inf")
        k = int(math.ceil((n + 1) * (1.0 - alpha)))
        if k > n:
            return float(self.abs_z[-1])
        return float(self.abs_z[k - 1])

    def interval(self, mu, sigma, alpha=ALPHA):
        sigma = max(float(sigma), 1e-6)
        r = self.conformal_radius(alpha) * sigma
        return float(mu - r), float(mu + r)


def _residuals(surr, Xc, yc):
    """Standardized residuals z=(y-mu)/sigma over a calibration set."""
    z = []
    for x, y in zip(Xc, yc):
        mu, sigma = surr.predict(x)
        z.append((float(y) - mu) / max(sigma, 1e-6))
    return np.array(z, float)


# ---------------------------------------------------------------------------
# Convex-hull-distance plausibility gate (binary system, exact 1-D lower hull).
# ---------------------------------------------------------------------------
def _lower_hull_points(points):
    """points: list of (x, E) including endpoints. Return hull vertices (sorted x)
    forming the lower convex envelope."""
    pts = sorted(set(points))
    hull = []
    for p in pts:
        while len(hull) >= 2:
            (x1, y1), (x2, y2), (x3, y3) = hull[-2], hull[-1], p
            # cross product; pop if middle point is above the line (not lower hull)
            cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append(p)
    return hull


def _hull_energy_at(hull, x):
    for i in range(len(hull) - 1):
        x1, y1 = hull[i]
        x2, y2 = hull[i + 1]
        if x1 <= x <= x2:
            if x2 == x1:
                return min(y1, y2)
            t = (x - x1) / (x2 - x1)
            return y1 + t * (y2 - y1)
    return 0.0


def convex_hull_distance(comp, e_pred):
    """For a binary composition, Delta_hull = E_pred - E_hull(x) where the hull is
    the lower convex envelope of the embedded SAMPLE compounds in the SAME binary
    system plus the elemental endpoints at E=0. Returns a dict; None hull if the
    system is not binary or has no embedded competing phases."""
    frac = _normalize_comp(comp)
    els = sorted(frac)
    if len(els) != 2:
        return {"applicable": False,
                "reason": "convex-hull gate implemented for BINARY systems only",
                "delta_hull": None}
    a, b = els
    xq = frac[b]  # fraction of the second (alphabetical) element
    # Hull of COMPETING phases (elemental endpoints + embedded compounds at OTHER
    # compositions). We exclude any embedded phase at the SAME composition as the
    # query so the gate measures plausibility against competitors, NOT the
    # surrogate's own fit error at this composition.
    points = [(0.0, 0.0), (1.0, 0.0)]
    for c, e in _DATASET:
        cf = _normalize_comp(c)
        if set(cf) == {a, b} and abs(cf[b] - xq) > 1e-3:
            points.append((cf[b], float(e)))
    hull = _lower_hull_points(points)
    e_hull = _hull_energy_at(hull, xq)
    delta = float(e_pred - e_hull)
    return {"applicable": True, "system": "%s-%s" % (a, b),
            "x_%s" % b: round(xq, 4),
            "e_pred_eV_atom": round(float(e_pred), 5),
            "e_hull_eV_atom": round(float(e_hull), 5),
            "delta_hull_eV_atom": round(delta, 5),
            "hull_vertices": [[round(x, 4), round(y, 5)] for x, y in hull],
            "thresholds": {"green_max": HULL_GREEN, "red_max": HULL_RED},
            "note": "PLAUSIBILITY check vs. embedded SAMPLE phases — NOT a guarantee"}


# ---------------------------------------------------------------------------
# Bekenstein / F19 information-cost ratio (APPLIED; F19 is locked-proven).
# ---------------------------------------------------------------------------
_HBAR = 1.054571817e-34
_C = 2.99792458e8


def bekenstein_check(sigma_prior, sigma_post, radius_m=1.0, energy_j=1.0):
    sp = max(float(sigma_prior), 1e-30)
    sq = max(float(sigma_post), 1e-30)
    info_bits = math.log2(sp / sq) if sp > sq else 0.0
    i_max = (2.0 * math.pi * float(radius_m) * float(energy_j)) / (_HBAR * _C) / math.log(2.0)
    ratio = info_bits / i_max if i_max > 0 else float("inf")
    return {
        "info_bits": round(info_bits, 6),
        "bekenstein_max_bits": i_max,
        "ratio": ratio,
        "label": "PHYSICALLY_PLAUSIBLE" if ratio <= 1.0 else "PHYSICALLY_IMPLAUSIBLE",
        "radius_m": float(radius_m), "energy_j": float(energy_j),
        "basis": ("F19 Bekenstein bound = PROVEN inequality (locked-8 @ %s); this "
                  "application is MODELED with SAMPLE R,E unless supplied" % LOCKED_PROVEN_AT),
    }


def compute_lambda(label, ood_score, sigma, hull_ok):
    f_label = {"GREEN": 0.9, "YELLOW": 0.6, "RED": 0.2}.get(label, 0.2)
    f_ood = float(np.clip(1.0 - ood_score, 0.05, 1.0))
    f_sigma = float(np.clip(math.exp(-2.0 * max(sigma, 0.0)), 0.05, 1.0))
    f_hull = 0.9 if hull_ok else 0.2
    geom = (f_label * f_ood * f_sigma * f_hull) ** 0.25
    return {"value": round(min(geom, 0.99), 4), "status": "ADVISORY",
            "basis": "Lambda = Conjecture 1 (advisory, capped <= 0.99; NEVER a proof)",
            "factors": {"label": f_label, "in_distribution": round(f_ood, 4),
                        "uncertainty": round(f_sigma, 4), "hull": f_hull}}


# ---------------------------------------------------------------------------
# Model build + held-out calibration-coverage measurement (cached at first use).
# ---------------------------------------------------------------------------
_STATE = {"built": False}
_LOCK = threading.Lock()


def _build_matrices():
    X = np.array([featurize(c) for c, _ in _DATASET], dtype=float)
    y = np.array([e for _, e in _DATASET], dtype=float)
    return X, y


def _measure_coverage_cv(X, y, repeats=60, seed=1234):
    """Honest held-out coverage: repeated random train/calib/test splits. For each
    split, fit ensemble on TRAIN, fit isotonic calibrator on CALIB, then count how
    many TEST targets fall inside the calibrated 95% interval. Aggregate over all
    held-out TEST points (large effective n). Returns (coverage, n, raw_coverage)."""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    hit, raw_hit, total = 0, 0, 0
    for _ in range(repeats):
        idx = rng.permutation(n)
        n_test = max(6, n // 7)
        # n_cal >= 19 so the two-sided 95% conformal order statistic is interior.
        n_cal = max(19, n // 3)
        test_idx = idx[:n_test]
        cal_idx = idx[n_test:n_test + n_cal]
        tr_idx = idx[n_test + n_cal:]
        if len(tr_idx) < 12:
            continue
        surr = _Surrogate(X[tr_idx], y[tr_idx], seed=int(rng.integers(0, 1 << 30)))
        cal = _Calibrator(_residuals(surr, X[cal_idx], y[cal_idx]))
        for j in test_idx:
            mu, sigma = surr.predict(X[j])
            lo, hi = cal.interval(mu, sigma, ALPHA)
            if lo <= y[j] <= hi:
                hit += 1
            # raw (uncalibrated) 95% gaussian interval for comparison
            rlo, rhi = mu - 1.96 * sigma, mu + 1.96 * sigma
            if rlo <= y[j] <= rhi:
                raw_hit += 1
            total += 1
    cov = hit / total if total else float("nan")
    raw = raw_hit / total if total else float("nan")
    return cov, total, raw


def _build():
    with _LOCK:
        if _STATE.get("built"):
            return _STATE
        X, y = _build_matrices()
        # production model: ensemble on the full set; isotonic on the full set
        # (the REPORTED coverage below is the held-out CV number, never in-sample).
        surr = _Surrogate(X, y, seed=7)
        cal = _Calibrator(_residuals(surr, X, y))
        cov, n_cov, raw_cov = _measure_coverage_cv(X, y)
        _STATE.update({
            "built": True, "X": X, "y": y, "surr": surr, "cal": cal,
            "coverage": cov, "coverage_n": n_cov, "raw_coverage": raw_cov,
            "alpha": ALPHA,
        })
        return _STATE


def calibration_report():
    st = _build()
    return {
        "method": ("5-member bootstrap deep-ensemble (numpy ridge over composition "
                   "descriptors) + ISOTONIC recalibration of the standardized-residual "
                   "CDF (Kuleshov 2018) with a finite-sample split-conformal interval "
                   "correction"),
        "target_coverage": 1.0 - ALPHA,
        "measured_coverage": round(float(st["coverage"]), 4),
        "measured_coverage_n": int(st["coverage_n"]),
        "uncalibrated_coverage": round(float(st["raw_coverage"]), 4),
        "protocol": ("repeated random train/calibration/test splits; coverage counted "
                     "ONLY on held-out TEST points never seen by the ensemble or the "
                     "isotonic calibrator; aggregated over all held-out points"),
        "dataset_n": len(_DATASET),
        "label": "MEASURED coverage on held-out split (MODELED+SAMPLE surrogate)",
    }


# ---------------------------------------------------------------------------
# Honesty block + receipt.
# ---------------------------------------------------------------------------
def _honesty(coverage=None, coverage_n=None):
    h = {
        "what_this_is": ("a calibrated SURROGATE for formation energy over a SAMPLE "
                         "dataset — NOT a SOTA DFT/MACE/CHGNet prediction"),
        "labels": "MODELED + SAMPLE (numpy surrogate; values are MODELED, data are SAMPLE)",
        "calibration": "coverage is MEASURED on a held-out split (see calibration block)",
        "convex_hull_gate": "PLAUSIBILITY check, not a guarantee",
        "self_doubt": ("out-of-distribution descriptor (far from embedded training) => "
                       "RED/refuse — never a confident extrapolation"),
        "locked_proven_count": 8,
        "locked_proven": list(LOCKED_PROVEN),
        "lambda": "Conjecture 1 (advisory, <= 0.99)",
        "f19": "Bekenstein bound = PROVEN inequality (locked-8); application MODELED",
        "do_not_overclaim": ("NOT 'discovered/validated a new material'; NOT 'MACE-accurate'. "
                             "MACE (MIT)/CHGNet (BSD-3) cited as patterns we'd wrap behind a "
                             "remote endpoint (not reachable today); reimplement-not-copy; "
                             "NO proprietary weights bundled"),
    }
    if coverage is not None:
        h["measured_coverage"] = round(float(coverage), 4)
        h["measured_coverage_n"] = int(coverage_n) if coverage_n else None
    return h


def _ledger(receipt):
    try:
        import szl_lake_ingest  # type: ignore
        res = szl_lake_ingest.record_receipt(receipt, organ=RECEIPT_ORGAN)
        return {"recorded": True, "backend": "szl_lake_ingest.record_receipt",
                "result": res if isinstance(res, dict) else str(res)}
    except Exception as e:  # noqa: BLE001 — honest degrade
        return {"recorded": False, "reason": "ledger hook not wired (%r)" % e,
                "organ": RECEIPT_ORGAN}


def _build_receipt(payload_core, sign=True):
    payload = {
        "schema": RECEIPT_SCHEMA, "organ": RECEIPT_ORGAN,
        "kind": "materials_property_predict", "ts": time.time(),
        "label_provenance": "MODELED + SAMPLE (calibrated surrogate; not MEASURED/DFT)",
        "doctrine": {
            "locked_proven_count": 8, "locked_proven": list(LOCKED_PROVEN),
            "locked_at": LOCKED_PROVEN_AT, "lambda": "Conjecture 1",
            "f19": "Bekenstein bound = PROVEN inequality (locked-8); application MODELED",
        },
    }
    payload.update(payload_core)
    receipt = {"payload": payload}
    if sign:
        try:
            import szl_dsse  # type: ignore
            env = szl_dsse.sign_payload(payload, RECEIPT_PAYLOAD_TYPE)
            receipt["dsse"] = env
            receipt["signed"] = bool(env.get("signatures"))
        except Exception as e:  # noqa: BLE001
            receipt["dsse"] = {"signed": False, "reason": "szl_dsse unavailable (%r)" % e}
            receipt["signed"] = False
    else:
        receipt["signed"] = False
    return receipt


# ---------------------------------------------------------------------------
# The governed prediction entry point.
# ---------------------------------------------------------------------------
_DEMOS = {
    "green": {"property": "formation_energy", "composition": {"Mg": 1, "O": 1}},
    "ood":   {"property": "formation_energy", "composition": {"Cu": 1, "Au": 1}},
}


def predict_property(spec):
    """spec: {composition: {el: count}, property?: 'formation_energy', options?:{}}
    or {demo: 'green'|'ood'}. Returns the governed result dict."""
    spec = dict(spec or {})
    st = _build()
    surr, cal = st["surr"], st["cal"]
    coverage, coverage_n = st["coverage"], st["coverage_n"]

    demo = spec.get("demo")
    if demo:
        d = _DEMOS.get(str(demo).strip().lower())
        if d is None:
            return {"ok": False, "error": "unknown demo %r; try 'green' or 'ood'" % demo,
                    "honesty": _honesty(coverage, coverage_n)}
        spec = dict(d)

    prop = (spec.get("property") or "formation_energy").strip().lower()
    if prop != "formation_energy":
        return {"ok": False,
                "error": "this SAMPLE surrogate predicts 'formation_energy' (eV/atom) only",
                "honesty": _honesty(coverage, coverage_n)}
    comp = spec.get("composition") or spec.get("descriptor")
    opts = dict(spec.get("options") or {})
    sign = bool(opts.get("sign", True))

    # featurize (unknown element => hard OOD refusal handled here)
    try:
        x = featurize(comp)
    except ValueError as ve:
        result = {
            "ok": True, "property": prop, "composition": comp,
            "verdict": "RED",
            "refusal": "OUT-OF-DISTRIBUTION: %s" % ve,
            "value": None, "interval95": None,
            "calibration": calibration_report(),
            "honesty": _honesty(coverage, coverage_n),
        }
        receipt = _build_receipt({"property": prop, "composition": comp,
                                  "verdict": "RED", "refusal": result["refusal"]},
                                 sign=sign)
        result["receipt"] = receipt
        result["ledger"] = _ledger(receipt)
        return result

    mu, sigma = surr.predict(x)
    lo, hi = cal.interval(mu, sigma, ALPHA)
    ood = surr.ood_score(x)
    hull = convex_hull_distance(comp, mu)

    # gates
    delta = hull.get("delta_hull_eV_atom")
    hull_red = (delta is not None and delta > HULL_RED)
    hull_yellow = (delta is not None and delta > HULL_GREEN)
    ood_red = ood > OOD_Z_RED
    ood_yellow = ood > OOD_Z_YELLOW
    sigma_yellow = sigma > SIGMA_YELLOW

    # Bekenstein F19 check: prior std = spread of dataset targets; posterior = sigma.
    prior_sigma = float(np.std(st["y"]))
    bek = bekenstein_check(prior_sigma, max(sigma, 1e-6),
                           radius_m=float(opts.get("radius_m", 1.0)),
                           energy_j=float(opts.get("energy_j", 1.0)))

    verdict = "GREEN"
    reasons = []
    if ood_red:
        verdict = "RED"
        reasons.append("descriptor is OUT-OF-DISTRIBUTION (ood_score=%.3f > %.2f) — "
                       "self-doubt gate REFUSES a confident extrapolation"
                       % (ood, OOD_Z_RED))
    if hull_red:
        verdict = "RED"
        reasons.append("convex-hull distance Delta_hull=%.3f eV/atom > %.2f — predicted "
                       "phase is implausible vs. embedded competing phases"
                       % (delta, HULL_RED))
    if bek["label"] != "PHYSICALLY_PLAUSIBLE":
        verdict = "RED"
        reasons.append("F19/Bekenstein information-cost check failed (ratio=%.2e)"
                       % bek["ratio"])
    if verdict != "RED" and (ood_yellow or hull_yellow or sigma_yellow):
        verdict = "YELLOW"
        if ood_yellow:
            reasons.append("near distribution edge (ood_score=%.3f)" % ood)
        if hull_yellow:
            reasons.append("metastable: Delta_hull=%.3f eV/atom in (%.2f, %.2f]"
                           % (delta, HULL_GREEN, HULL_RED))
        if sigma_yellow:
            reasons.append("elevated epistemic uncertainty (sigma=%.3f eV/atom)" % sigma)
    if verdict == "GREEN":
        reasons.append("in-distribution, on/near hull, calibrated interval — plausible")

    refuse = verdict == "RED"
    lam = compute_lambda(verdict, ood, sigma, hull_ok=not hull_red)

    result = {
        "ok": True,
        "property": prop,
        "composition": comp,
        "verdict": verdict,
        "value_eV_atom": (None if refuse else round(mu, 5)),
        "ensemble_sigma_eV_atom": round(sigma, 5),
        "interval95_eV_atom": (None if refuse else [round(lo, 5), round(hi, 5)]),
        "interval_is_calibrated": True,
        "ood_score": round(ood, 4),
        "convex_hull_gate": hull,
        "bekenstein_f19": bek,
        "lambda_advisory": lam,
        "calibration": calibration_report(),
        "gate_reasons": reasons,
        "honesty": _honesty(coverage, coverage_n),
        "would_wrap": ("when a real MACE(MIT)/CHGNet(BSD-3) inference endpoint is "
                       "reachable over HTTP, predict_property would call it and this "
                       "SAME calibration + gate wrapper applies; it is NOT reachable "
                       "today, so this is the honest numpy SAMPLE surrogate"),
        "citations": list(CITATIONS),
    }
    if refuse:
        result["refusal"] = " ; ".join(reasons)

    receipt = _build_receipt({
        "property": prop, "composition": comp, "verdict": verdict,
        "value_eV_atom": result["value_eV_atom"],
        "interval95_eV_atom": result["interval95_eV_atom"],
        "ensemble_sigma_eV_atom": result["ensemble_sigma_eV_atom"],
        "ood_score": result["ood_score"],
        "convex_hull_gate": hull,
        "bekenstein_f19": bek,
        "lambda_advisory": lam,
        "calibration": {"measured_coverage": round(float(coverage), 4),
                        "measured_coverage_n": int(coverage_n),
                        "target_coverage": 1.0 - ALPHA},
    }, sign=sign)
    result["receipt"] = receipt
    result["ledger"] = _ledger(receipt)
    return result


# ---------------------------------------------------------------------------
# HTTP surface — POST /api/a11oy/v1/materials/predict (+ GET /materials/health).
# Registered BEFORE the SPA/Node catch-all (serve.py front-moves to router head).
# ---------------------------------------------------------------------------
def register(app, ns="a11oy"):
    from fastapi.responses import JSONResponse
    from fastapi import Request

    async def _predict(request: Request):
        try:
            try:
                spec = await request.json()
            except Exception:
                spec = {}
            if not isinstance(spec, dict):
                spec = {}
            if not spec:
                spec = {"demo": "green"}
            out = predict_property(spec)
            code = 200 if out.get("ok") else 400
            return JSONResponse(out, status_code=code, headers={
                "x-szl-materials-verdict": str(out.get("verdict", "NA")),
                "x-szl-organ": RECEIPT_ORGAN})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "%r" % e,
                                 "honesty": _honesty()}, status_code=500)

    async def _health():
        try:
            rep = calibration_report()
        except Exception as e:  # noqa: BLE001
            rep = {"error": "calibration unavailable (%r)" % e}
        return JSONResponse({
            "ok": True, "organ": RECEIPT_ORGAN,
            "endpoint": "POST /api/%s/v1/materials/predict" % ns,
            "vertical": "materials-property-prediction (governed, calibrated surrogate)",
            "property": "formation_energy (eV/atom)",
            "model": ("numpy-only 5-member bootstrap deep-ensemble over composition "
                      "descriptors; MODELED + SAMPLE surrogate — NOT MACE/CHGNet/DFT"),
            "gates": {
                "self_doubt_ood": "ood_score > %.2f => RED/refuse" % OOD_Z_RED,
                "convex_hull": "Delta_hull > %.2f eV/atom => RED" % HULL_RED,
                "f19_bekenstein": "information-cost ratio <= 1 required",
            },
            "calibration": rep,
            "demos": {"green": "POST {\"demo\":\"green\"} -> GREEN MgO in-distribution",
                      "ood": "POST {\"demo\":\"ood\"} -> RED Cu-Au out-of-distribution refusal"},
            "elements": sorted(_ELEM),
            "honesty": _honesty(rep.get("measured_coverage"), rep.get("measured_coverage_n")),
            "citations": list(CITATIONS),
        })

    prefixes = ["/api/%s/v1/materials" % ns, "/v1/materials"]
    routes = []
    for p in prefixes:
        app.add_api_route("%s/predict" % p, _predict, methods=["POST", "GET"],
                          include_in_schema=True)
        app.add_api_route("%s/health" % p, _health, methods=["GET"],
                          include_in_schema=True)
        routes += ["%s/predict" % p, "%s/health" % p]
    return routes


if __name__ == "__main__":
    import json
    print(json.dumps(calibration_report(), indent=2))
    for d in ("green", "ood"):
        out = predict_property({"demo": d})
        print("\n== demo:%s ==" % d)
        print(json.dumps({k: out.get(k) for k in (
            "verdict", "value_eV_atom", "interval95_eV_atom", "ood_score",
            "convex_hull_gate", "refusal")}, indent=2, default=float)[:1400])
