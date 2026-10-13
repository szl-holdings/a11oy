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
#     * a 5-member bootstrap ridge (linear) ensemble over ten composition
#       descriptors; its member spread is the "epistemic" sigma. The deep ensemble
#       UQ pattern (Lakshminarayanan et al. 2017) is cited as prior art, NOT
#       claimed: these are closed-form ridge regressors, not neural networks,
#     * a symmetric split-conformal |z| radius (z = standardized residual) from an
#       IN-SAMPLE calibrator — that radius is what the served interval uses. The
#       coverage numbers on the wire are MEASURED in memory at build time under two
#       LABELLED protocols (split models; the serving recipe on random holdouts),
#       each with its n, trial count and unique-material count,
#     * a convex-hull-distance plausibility GATE (Delta_hull > 0.1 eV/atom =>
#       RED/refuse) — a CHECK, not a guarantee. An unknown or unverifiable hull is
#       NEVER favorable: GREEN requires an applicable hull with >= 1 embedded
#       competing phase, otherwise the verdict is YELLOW,
#     * a CALIBRATION ARTIFACT binding the calibrator to the served predictor
#       (sha256 over fitted coefficients + config, data hash, alpha, n, rank k,
#       unbounded flag, evaluation provenance); a stale predictor hash fails closed,
#     * a Bekenstein/F19 information-cost check (F19 APPLIED, not re-claimed),
#     * a SELF-DOUBT / out-of-distribution gate: a descriptor far from the embedded
#       training descriptors => RED/refuse, never a confident extrapolation.
#
# HONEST LABELS (Doctrine v11, non-negotiable):
#   - The prediction is MODELED + SAMPLE: a calibrated SURROGATE over a SAMPLE
#     dataset, NOT a SOTA DFT/MACE prediction. We say exactly this in the honesty
#     block and the surface copy. NO "discovered/validated a new material". NO
#     "MACE-accurate".
#   - Coverage numbers are MEASURED in memory at build time (deterministic seeds,
#     ephemeral, never persisted) — never a number we did not measure — and each
#     carries its protocol label and n. The CV number evaluates SPLIT models, not
#     the served pair, and says so; the serving-protocol number is reported beside it.
#   - The split-conformal radius is UNBOUNDED when ceil((n+1)(1-alpha)) > n; the
#     predictor then ABSTAINS (RED, interval None) instead of serving max|z|.
#   - The convex-hull gate is a PLAUSIBILITY CHECK, not a guarantee, and a missing
#     or inapplicable hull can never earn GREEN.
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
# INPUT CONTRACT (receipt-on-WRITE, never on read — AGENTS.md):
#   - _validate_spec is PURE and runs before the first-use fit: counts must be
#     finite, non-negative, non-boolean numbers with a finite positive total (an
#     exact zero means "absent species"); options.sign is a bool; radius_m and
#     energy_j are finite and > 0. Malformed input => {ok:false} / HTTP 400 with no
#     fit, no signature, no ledger write. Responses and receipts carry the
#     SANITIZED counts, never the raw request object.
#   - /materials/predict is POST-only (GET => 405 + Allow: POST + usage body); an
#     empty or non-object body is a 400, never a silent demo. /materials/health is
#     a read: it never fits and reports NOT_BUILT until the first POST.
#   - An element outside the embedded table is NOT malformed input: it is the honest
#     hard-OOD refusal (RED verdict WITH a receipt), unchanged.
#
# DEPLOY: numpy-only; imports guarded at request time; NEVER raises into startup.
# Registered BEFORE the /api/a11oy/{path:path} Node-proxy + SPA catch-all (serve.py
# front-moves these routes to the router head, same proven pattern as the PINN block).

import hashlib
import json
import math
import struct
import time
import threading

import numpy as np

RECEIPT_SCHEMA = "szl.lake.receipt/v1"
RECEIPT_ORGAN = "a11oy-materials"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.materials-predict+json"
CALIBRATION_ARTIFACT_SCHEMA = "szl.materials.calibration_artifact/v1"
LOCKED_PROVEN = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
LOCKED_PROVEN_AT = "c7c0ba17"
ABSTAIN_UNBOUNDED = "calibration set too small for a finite split-conformal interval"
HULL_NOT_APPLICABLE = "hull gate not applicable - plausibility unverified"

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
    "Vovk, Gammerman & Shafer 2005, 'Algorithmic Learning in a Random World' / "
    "Lei et al. 2018 JASA (arXiv:1604.04173) — split-conformal prediction; the "
    "served interval is the symmetric ceil((n+1)(1-alpha)) order statistic of |z|",
    "Kuleshov, Fenner & Ermon 2018, 'Accurate Uncertainties for Deep Learning "
    "Using Calibrated Regression', ICML (arXiv:1807.00263) — isotonic CDF "
    "recalibration; fitted here as a DIAGNOSTIC only, NOT on the served interval path",
    "Lakshminarayanan, Pritzel & Blundell 2017, 'Simple and Scalable Predictive "
    "Uncertainty Estimation using Deep Ensembles', NeurIPS (arXiv:1612.01474) — "
    "prior art for ensemble-spread UQ; this module's 5 members are closed-form ridge "
    "regressors, NOT a deep ensemble",
    "Tan, Heenen et al. 2023, npj Comput. Mater., DOI:10.1038/s41524-023-01180-8 "
    "— ensemble UQ for MLIPs (prior art; says nothing about this surrogate)",
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
class InvalidCompositionError(ValueError):
    """Malformed composition NUMERICS: a boolean, non-finite, negative or
    overflowing count, a non-object/empty composition, or a non-positive total.
    Deliberately distinct from the unknown-element refusal (a plain ValueError):
    that one is an honest scientific RED verdict and keeps its receipt, whereas
    this one is a client error that must never reach the fit, signer or ledger."""


def _sanitize_counts(comp):
    """Numeric contract only (NO element-table check). Returns {element: count}
    with finite, strictly positive float counts. Exact zeros are dropped — a zero
    count means the species is absent (contract decision, see CHANGELOG). Raises
    InvalidCompositionError for everything else."""
    if not isinstance(comp, dict) or not comp:
        raise InvalidCompositionError(
            "composition must be a non-empty {element: count} object")
    counts = {}
    for el, c in comp.items():
        el = str(el).strip()
        if isinstance(c, (bool, np.bool_)):
            raise InvalidCompositionError(
                "count for %r must be a number, not a boolean" % el)
        try:
            c = float(c)
        except OverflowError:
            raise InvalidCompositionError(
                "count for %r is too large for a finite float" % el)
        except (TypeError, ValueError):
            raise InvalidCompositionError("count for %r must be a number" % el)
        if not math.isfinite(c):
            raise InvalidCompositionError("count for %r must be finite" % el)
        if c < 0:
            raise InvalidCompositionError("count for %r must not be negative" % el)
        if c == 0.0:
            continue
        counts[el] = counts.get(el, 0.0) + c
    if not counts:
        raise InvalidCompositionError("composition has no positive element counts")
    tot = sum(counts.values())
    if not (math.isfinite(tot) and tot > 0):
        raise InvalidCompositionError(
            "composition total count must be finite and positive")
    return counts


def _normalize_comp(comp):
    """comp: dict element->count. Returns dict element->fraction. Raises
    InvalidCompositionError on malformed numerics (see _sanitize_counts) and a
    plain ValueError for an element outside the embedded table (an unknown
    element is an honest, hard OOD: we cannot featurize it)."""
    counts = _sanitize_counts(comp)
    for el in counts:
        if el not in _ELEM:
            raise ValueError(
                "element %r is outside the embedded SAMPLE element table %s — "
                "cannot featurize (honest OOD refusal)" % (el, sorted(_ELEM)))
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
# 5-member bootstrap ridge (linear) ensemble whose member spread is the
# "epistemic" sigma (ensemble-spread UQ; deep ensembles are the cited prior art).
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
        self.lam = float(lam)
        self.seed = int(seed)
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
# Split-conformal calibrator over standardized residuals. An isotonic (PAV) CDF
# fit (Kuleshov 2018) is kept as a DIAGNOSTIC (quantile()); the served interval
# uses only the symmetric split-conformal |z| radius.
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


def _check_alpha(alpha):
    """alpha must be a real NUMBER strictly inside (0, 1) — not a bool, not a
    string; anything else is a caller error, never a silently clamped level."""
    if isinstance(alpha, (bool, np.bool_)) or \
            not isinstance(alpha, (int, float, np.integer, np.floating)):
        raise ValueError("alpha must be a number in (0, 1), got %r" % (alpha,))
    a = float(alpha)
    if not (math.isfinite(a) and 0.0 < a < 1.0):
        raise ValueError("alpha must be a finite number in (0, 1), got %r" % (alpha,))
    return a


class _Calibrator:
    """Split-conformal calibrator over the STANDARDIZED residual z=(y-mu)/sigma of a
    calibration set. The served central (1-alpha) interval is

        [mu - q*sigma, mu + q*sigma],  q = the ceil((n+1)(1-alpha))-th smallest |z|

    (symmetric split-conformal radius; Vovk et al. 2005, Lei et al. 2018). When
    ceil((n+1)(1-alpha)) > n no finite order statistic carries the guarantee and
    the radius is UNBOUNDED (math.inf); the caller must abstain, never serve max|z|.

    An isotonic (PAV) empirical CDF of z (Kuleshov et al. 2018) is also fitted and
    exposed through quantile() as a DIAGNOSTIC of the residual distribution. It is
    NOT on the served interval path and no coverage claim is made for it."""

    def __init__(self, z_cal):
        z = np.sort(np.asarray(z_cal, float))
        n = len(z)
        ecdf = (np.arange(n) + 0.5) / n          # plotting-position empirical CDF
        zg, cg = _isotonic_pav(z, ecdf)          # monotone (z -> cumulative prob)
        self.z_grid = zg
        self.cdf_grid = np.clip(cg, 0.0, 1.0)
        self.n = n
        self.abs_z = np.sort(np.abs(z))          # the conformity scores, sorted

    def quantile(self, q):
        """DIAGNOSTIC isotonic-CDF quantile of z. Not used by interval()."""
        q = min(max(float(q), 0.0), 1.0)
        return float(np.interp(q, self.cdf_grid, self.z_grid))

    def conformal_rank(self, alpha=ALPHA):
        """Split-conformal order statistic k = ceil((n+1)(1-alpha)) and whether it
        is unbounded (k > n, including n == 0). Pure."""
        a = _check_alpha(alpha)
        n = self.n
        k = int(math.ceil((n + 1) * (1.0 - a)))
        return {"n_calibration": n, "rank_k": k, "unbounded": k > n}

    def conformal_radius(self, alpha=ALPHA):
        """Finite-sample symmetric split-conformal quantile of |z| at level 1-alpha:
        the ceil((n+1)(1-alpha))-th smallest |z|. Returns math.inf when that rank
        exceeds n (the guarantee then needs an unbounded interval); it never
        substitutes max|z| for it."""
        rk = self.conformal_rank(alpha)
        if rk["unbounded"]:
            return math.inf
        return float(self.abs_z[rk["rank_k"] - 1])

    def interval(self, mu, sigma, alpha=ALPHA):
        """(lo, hi) = mu -/+ radius*sigma. An unbounded radius yields (-inf, inf);
        predict_property abstains before serving that."""
        sigma = max(float(sigma), 1e-6)
        r = self.conformal_radius(alpha)
        if not math.isfinite(r):
            return -math.inf, math.inf
        r *= sigma
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


_HULL_NOTE = ("PLAUSIBILITY check vs. embedded SAMPLE phases — NOT a guarantee; "
              "applicable:false is UNKNOWN evidence, never favorable")


def convex_hull_distance(comp, e_pred):
    """For a binary composition, Delta_hull = E_pred - E_hull(x) where the hull is
    the lower convex envelope of the embedded SAMPLE compounds in the SAME binary
    system plus the elemental endpoints at E=0.

    The dict always carries `applicable`, `delta_hull_eV_atom` (None unless
    applicable) and `competing_phases` (embedded phases in the same system at a
    composition OTHER than the query). The gate is applicable only for a binary
    query with >= 1 competing phase: with the elemental endpoints alone there is
    nothing to compete against, so the number E_pred - 0 is reported separately as
    `delta_vs_elements_eV_atom` (informational) and the gate says so. Embedded
    phases at the query composition are excluded (counted in
    `same_composition_phases_excluded`) so the gate measures plausibility against
    competitors, not the surrogate's own fit error; polymorph competition at the
    query composition is therefore NOT assessed."""
    frac = _normalize_comp(comp)
    els = sorted(frac)
    thresholds = {"green_max": HULL_GREEN, "red_max": HULL_RED}
    if len(els) != 2:
        return {"applicable": False,
                "reason": ("convex-hull gate implemented for BINARY systems only "
                           "(%d-element query)" % len(els)),
                "system": "-".join(els), "competing_phases": 0,
                "delta_hull_eV_atom": None,
                "e_pred_eV_atom": round(float(e_pred), 5),
                "thresholds": thresholds, "note": _HULL_NOTE}
    a, b = els
    xq = frac[b]  # fraction of the second (alphabetical) element
    points = [(0.0, 0.0), (1.0, 0.0)]
    competing, same_comp = 0, 0
    for c, e in _DATASET:
        cf = _normalize_comp(c)
        if set(cf) != {a, b}:
            continue
        if abs(cf[b] - xq) > 1e-3:
            points.append((cf[b], float(e)))
            competing += 1
        else:
            same_comp += 1
    hull = _lower_hull_points(points)
    e_hull = _hull_energy_at(hull, xq)
    delta = float(e_pred - e_hull)
    out = {"system": "%s-%s" % (a, b), "x_%s" % b: round(xq, 4),
           "competing_phases": competing,
           "same_composition_phases_excluded": same_comp,
           "e_pred_eV_atom": round(float(e_pred), 5),
           "hull_vertices": [[round(x, 4), round(y, 5)] for x, y in hull],
           "thresholds": thresholds, "note": _HULL_NOTE}
    if competing == 0:
        out.update({
            "applicable": False,
            "reason": ("no embedded competing phase in the %s-%s system: only the "
                       "elemental endpoints are known, so plausibility is unverified"
                       % (a, b)),
            "delta_hull_eV_atom": None,
            "delta_vs_elements_eV_atom": round(delta, 5),
        })
        return out
    out.update({"applicable": True,
                "e_hull_eV_atom": round(float(e_hull), 5),
                "delta_hull_eV_atom": round(delta, 5)})
    return out


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


CV_REPEATS, CV_SEED = 60, 1234
SERVING_REPEATS, SERVING_SEED = 60, 4321


def _measure_coverage_cv(X, y, repeats=CV_REPEATS, seed=CV_SEED):
    """Held-out coverage of SPLIT models: repeated random train/calib/test splits.
    For each split, fit the ensemble on TRAIN, the conformal calibrator on CALIB,
    then count how many TEST targets fall inside the (1-alpha) interval.
    Aggregated over all held-out TEST predictions: n counts predictions (the same
    material recurs across trials), NOT independent materials. This evaluates the
    split protocol, not the served full-sample pair (see
    _measure_coverage_serving). Returns (coverage, n, raw_coverage, trials);
    coverage is None when no trial could run."""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    hit, raw_hit, total, trials = 0, 0, 0, 0
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
        trials += 1
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
    cov = hit / total if total else None
    raw = raw_hit / total if total else None
    return cov, total, raw, trials


def _measure_coverage_serving(X, y, repeats=SERVING_REPEATS, seed=SERVING_SEED):
    """Held-out coverage of the SERVING recipe: on each trial hold out a random
    block, fit the ensemble on the kept records AND calibrate on the kept records'
    own (in-sample) residuals — exactly how the served pair is built — then count
    held-out targets inside the interval. Trials whose calibrator is unbounded are
    counted in `unbounded_trials` and excluded (an infinite interval always covers
    and would inflate the number). Deterministic (seeded), in-memory, ephemeral.
    Returns a dict; coverage is None when no bounded trial could run."""
    rng = np.random.default_rng(seed)
    n = X.shape[0]
    hit, total, trials, unbounded = 0, 0, 0, 0
    n_hold = max(6, n // 7)
    for _ in range(repeats):
        idx = rng.permutation(n)
        hold, keep = idx[:n_hold], idx[n_hold:]
        if len(keep) < 12:
            continue
        surr = _Surrogate(X[keep], y[keep], seed=int(rng.integers(0, 1 << 30)))
        cal = _Calibrator(_residuals(surr, X[keep], y[keep]))
        if not math.isfinite(cal.conformal_radius(ALPHA)):
            unbounded += 1
            continue
        trials += 1
        for j in hold:
            mu, sigma = surr.predict(X[j])
            lo, hi = cal.interval(mu, sigma, ALPHA)
            if lo <= y[j] <= hi:
                hit += 1
            total += 1
    return {"coverage": (hit / total if total else None), "n": total,
            "trials": trials, "unbounded_trials": unbounded, "holdout_per_trial": n_hold,
            "seed": seed}


def _r4(v, nd=4):
    """round() that passes None / non-finite through as None (strict-JSON safe)."""
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if math.isfinite(v) else None


def _predictor_hash(surr):
    """sha256 over the fitted coefficients (standardizer + every member's (w, b))
    and the fitting config. Any refit, reseed or config change yields a new hash,
    so a calibration artifact carrying the old hash is detectably stale."""
    h = hashlib.sha256()
    cfg = {"ensemble_n": len(surr.members), "ridge_lambda": surr.lam, "seed": surr.seed,
           "features": list(_FEATURE_NAMES), "n_train": int(surr.Xz.shape[0])}
    h.update(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    h.update(np.ascontiguousarray(surr.mu, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(surr.sd, dtype=np.float64).tobytes())
    for w, b in surr.members:
        h.update(np.ascontiguousarray(w, dtype=np.float64).tobytes())
        h.update(struct.pack("<d", float(b)))
    return h.hexdigest()


def _data_hash(dataset=None):
    """sha256 over the canonical JSON of the embedded SAMPLE dataset."""
    rows = [[dict(sorted(c.items())), float(e)] for c, e in (dataset or _DATASET)]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"))
                           .encode("utf-8")).hexdigest()


def _calibration_state(cal, alpha):
    """Validate and fingerprint the actual scores and diagnostic CDF in memory."""
    a = _check_alpha(alpha)
    if not isinstance(cal, _Calibrator) or type(cal.n) is not int or cal.n < 0:
        raise ValueError("invalid calibrator or calibration count")
    h = hashlib.sha256(b"szl.materials.calibrator/v1")
    h.update(struct.pack("<Qd", cal.n, a))
    arrays = {}
    for name in ("abs_z", "z_grid", "cdf_grid"):
        values = np.asarray(getattr(cal, name))
        if (values.ndim != 1 or values.size != cal.n or values.dtype.kind != "f"
                or not np.all(np.isfinite(values))
                or np.any(values[1:] < values[:-1])):
            raise ValueError("invalid calibrator %s" % name)
        arrays[name] = values
        h.update(name.encode("ascii"))
        h.update(np.ascontiguousarray(values, dtype="<f8").tobytes())
    if np.any(arrays["abs_z"] < 0):
        raise ValueError("negative calibration score")
    if np.any((arrays["cdf_grid"] < 0) | (arrays["cdf_grid"] > 1)):
        raise ValueError("calibrator CDF is outside [0,1]")
    k = int(math.ceil((cal.n + 1) * (1.0 - a)))
    unbounded = k > cal.n
    return {"calibration_state_hash": h.hexdigest(), "alpha": a,
            "n_calibration": cal.n, "rank_k": k, "unbounded": unbounded,
            "radius_abs_z": (None if unbounded else round(float(arrays["abs_z"][k - 1]), 5))}


def build_calibration_artifact(surr, cal, alpha, data_hash, evaluation):
    """PURE: the artifact binding `cal` to `surr`. Nothing here fits or signs."""
    state = _calibration_state(cal, alpha)
    n_train = int(surr.Xz.shape[0])
    return {
        "schema": CALIBRATION_ARTIFACT_SCHEMA,
        "predictor_hash": _predictor_hash(surr),
        "data_hash": data_hash,
        "protocol": "serving",
        "protocol_description": ("full-sample fit (n_train=%d) + IN-SAMPLE calibrator on the "
                                 "same records (n_calibration=%d); no disjoint calibration "
                                  "split is held back for the served pair" % (n_train, state["n_calibration"])),
        "split_ids": {"train": "embedded:all", "calibration": "embedded:all (in-sample)",
                      "test": None},
        "score_definition": ("|z| with z = (y - mu) / max(sigma, 1e-6); symmetric split-conformal "
                             "radius = the ceil((n+1)(1-alpha))-th smallest |z|"),
        **state,
        "evaluation_provenance": evaluation,
    }


def validate_calibration_artifact(artifact, predictor_hash, data_hash=None,
                                  *, calibrator=None, alpha=ALPHA):
    """PURE: check predictor/data binding and the actual calibration state.

    Hash equality alone cannot prove this binding: the served calibrator and
    level are required, and its count/rank/radius metadata must agree as well.
    This checks internal consistency, not statistical validity or authenticity.
    """
    if not isinstance(artifact, dict):
        return {"valid": False, "reason": "calibration artifact missing"}
    try:
        json.dumps(artifact, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return {"valid": False, "reason": "calibration artifact is not strict JSON"}
    if artifact.get("schema") != CALIBRATION_ARTIFACT_SCHEMA:
        return {"valid": False, "reason": "unknown calibration artifact schema %r"
                % (artifact.get("schema"),)}
    if artifact.get("predictor_hash") != predictor_hash:
        return {"valid": False,
                "reason": "stale predictor_hash: the calibration was fitted for a different "
                          "predictor (artifact %s..., served %s...)"
                          % (str(artifact.get("predictor_hash"))[:12], str(predictor_hash)[:12])}
    if data_hash is not None and artifact.get("data_hash") != data_hash:
        return {"valid": False, "reason": "stale data_hash: the embedded dataset changed"}
    try:
        state = _calibration_state(calibrator, alpha)
    except (AttributeError, TypeError, ValueError, OverflowError, struct.error) as exc:
        return {"valid": False, "reason": "invalid calibration state: %s" % type(exc).__name__}
    if artifact.get("protocol") != "serving":
        return {"valid": False, "reason": "invalid calibration protocol"}
    for key, expected in state.items():
        value = artifact.get(key)
        # bool == 1 in Python; the count, rank and boundedness types are part of
        # the contract. Missing radius must also fail for an unbounded artifact.
        if (key not in artifact or type(value) is not type(expected) or value != expected):
            return {"valid": False, "reason": "calibration %s does not match served state" % key}
    return {"valid": True, "reason": "predictor, data and calibration state match"}


def _build():
    with _LOCK:
        if _STATE.get("built"):
            return _STATE
        X, y = _build_matrices()
        # Served pair: ensemble on the full sample; conformal calibrator on that same
        # sample's residuals (IN-SAMPLE). Both coverage numbers below are measured on
        # held-out records at build time and labelled by protocol; neither is the
        # served pair's own guarantee.
        surr = _Surrogate(X, y, seed=7)
        cal = _Calibrator(_residuals(surr, X, y))
        cov, n_cov, raw_cov, cv_trials = _measure_coverage_cv(X, y)
        serving = _measure_coverage_serving(X, y)
        data_hash = _data_hash()
        evaluation = {
            "measured_at": "build time, in-memory, deterministic seeds, ephemeral (not persisted)",
            "unique_materials": int(X.shape[0]),
            "cv_split_models": {"coverage": _r4(cov), "n_predictions": int(n_cov),
                                "trials": int(cv_trials), "seed": CV_SEED,
                                "label": "MEASURED on held-out TEST records of SPLIT models; "
                                         "not the served pair"},
            "serving_protocol_holdout": {"coverage": _r4(serving["coverage"]),
                                         "n_predictions": int(serving["n"]),
                                         "trials": int(serving["trials"]),
                                         "unbounded_trials": int(serving["unbounded_trials"]),
                                         "seed": serving["seed"],
                                         "label": "MEASURED on held-out records with the serving "
                                                  "recipe (fit + in-sample calibrate on the kept "
                                                  "records)"},
        }
        artifact = build_calibration_artifact(surr, cal, ALPHA, data_hash, evaluation)
        _STATE.update({
            "built": True, "X": X, "y": y, "surr": surr, "cal": cal,
            "coverage": cov, "coverage_n": n_cov, "raw_coverage": raw_cov,
            "cv_trials": cv_trials, "serving": serving, "alpha": ALPHA,
            "data_hash": data_hash, "artifact": artifact,
        })
        return _STATE


def calibration_report():
    st = _build()
    n_unique = int(st["X"].shape[0])
    serving = st["serving"]
    art = st["artifact"]
    return {
        "method": ("5-member bootstrap ridge (linear) ensemble over composition descriptors "
                   "(member spread = sigma) + symmetric split-conformal |z| radius from an "
                   "IN-SAMPLE calibrator (n=%d, rank k=%d of ceil((n+1)(1-alpha))); the "
                   "isotonic CDF fit is a diagnostic only"
                   % (art["n_calibration"], art["rank_k"])),
        "interval_method": ("served interval = mu -/+ radius*sigma with radius = the %d-th "
                            "smallest |z| of the in-sample calibration residuals%s"
                            % (art["rank_k"], "" if not art["unbounded"]
                               else " — UNBOUNDED at this n/alpha, predictor abstains")),
        "target_coverage": 1.0 - ALPHA,
        # CV number (kept, now labelled): split models, 60 trials, 420 predictions.
        "measured_coverage": _r4(st["coverage"]),
        "measured_coverage_n": int(st["coverage_n"]),
        "measured_coverage_protocol": (
            "cv_split_models: %d repeated random train/calibration/test splits of the %d "
            "embedded materials; n counts %d held-out TEST predictions, not independent "
            "materials (each material recurs across trials); evaluates SPLIT models, NOT "
            "the served full-sample pair" % (st["cv_trials"], n_unique, st["coverage_n"])),
        "uncalibrated_coverage": _r4(st["raw_coverage"]),
        "uncalibrated_coverage_protocol": ("same cv_split_models protocol; raw mu -/+ 1.96*sigma "
                                           "Gaussian interval, no conformal radius"),
        # Serving-protocol number (new): the recipe that is actually served.
        "serving_protocol_coverage": _r4(serving["coverage"]),
        "serving_protocol_coverage_n": int(serving["n"]),
        "serving_protocol_coverage_protocol": (
            "serving_protocol_holdout: %d trials holding out %d of %d materials; fit on the "
            "kept records and calibrate on their IN-SAMPLE residuals (the served recipe), "
            "count held-out hits; %d unbounded trial(s) excluded; n counts held-out "
            "predictions" % (serving["trials"], serving["holdout_per_trial"], n_unique,
                             serving["unbounded_trials"])),
        "coverage_measurement": ("MEASURED in memory at build time with deterministic seeds "
                                 "(cv %d, serving %d); ephemeral, not persisted; a SAMPLE "
                                 "dataset of %d unique materials"
                                 % (CV_SEED, serving["seed"], n_unique)),
        "coverage_note": (None if st["coverage"] is not None else
                          "NOT_RUN: too few records for the split protocol (coverage None)"),
        "unique_materials": n_unique,
        "dataset_n": len(_DATASET),
        "label": ("MEASURED held-out coverage, protocol-labelled (MODELED+SAMPLE surrogate); "
                  "the served pair itself is full-sample + in-sample calibrated"),
    }


# ---------------------------------------------------------------------------
# Honesty block + receipt.
# ---------------------------------------------------------------------------
def _honesty(coverage=None, coverage_n=None):
    h = {
        "what_this_is": ("a calibrated SURROGATE for formation energy over a SAMPLE "
                         "dataset — NOT a SOTA DFT/MACE/CHGNet prediction"),
        "labels": "MODELED + SAMPLE (numpy surrogate; values are MODELED, data are SAMPLE)",
        "calibration": ("served interval = symmetric split-conformal |z| radius from an "
                        "IN-SAMPLE calibrator; coverage numbers are MEASURED in memory at "
                        "build time and each carries its protocol label and n (the CV number "
                        "evaluates split models, not the served pair; see calibration block); "
                        "an unbounded radius => abstain"),
        "convex_hull_gate": ("PLAUSIBILITY check, not a guarantee; GREEN requires an "
                             "applicable hull with >= 1 embedded competing phase — unknown "
                             "hull evidence is never favorable"),
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
        h["measured_coverage"] = _r4(coverage)
        h["measured_coverage_n"] = int(coverage_n) if coverage_n else None
        h["measured_coverage_protocol"] = "cv_split_models (see calibration block)"
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
# "green" is Fe2O3: in-distribution AND its Fe-O hull has embedded competing phases
# (FeO, Fe3O4), so the hull gate is applicable and the verdict is honestly GREEN.
# MgO (the previous preset) is the only embedded Mg-O phase: with no competitor the
# hull is unverifiable, so MgO now answers YELLOW and stays reachable explicitly.
_DEMOS = {
    "green": {"property": "formation_energy", "composition": {"Fe": 2, "O": 3}},
    "ood":   {"property": "formation_energy", "composition": {"Cu": 1, "Au": 1}},
}


_USAGE_ERROR = "supply {composition} or {demo}"


def _validate_spec(spec):
    """PURE request validation — no fit, no sign, no ledger, no I/O, no _STATE.
    Resolves a demo, checks the property, sanitizes the composition counts and
    the options. Returns the normalized spec
      {"property": str, "composition": {el: finite positive float},
       "options": {"sign": bool, "radius_m": float > 0, "energy_j": float > 0}}
    and raises ValueError (InvalidCompositionError for numeric composition faults)
    carrying a client-facing message. An element OUTSIDE the embedded table is not
    an error here: the counts pass through so predict_property can refuse it the
    honest way (RED verdict WITH a receipt), exactly as before. As before, a demo
    replaces the whole spec, so a demo request ignores caller options."""
    if not isinstance(spec, dict) or not spec:
        raise ValueError(_USAGE_ERROR)
    demo = spec.get("demo")
    if demo:
        if not isinstance(demo, str):
            raise ValueError("demo must be a string: 'green' or 'ood'")
        d = _DEMOS.get(demo.strip().lower())
        if d is None:
            raise ValueError("unknown demo %r; try 'green' or 'ood'" % demo)
        spec = dict(d)

    prop = spec.get("property") or "formation_energy"
    if not isinstance(prop, str):
        raise ValueError("property must be a string")
    prop = prop.strip().lower()
    if prop != "formation_energy":
        raise ValueError(
            "this SAMPLE surrogate predicts 'formation_energy' (eV/atom) only")

    comp = spec.get("composition") or spec.get("descriptor")
    if comp is None:
        raise ValueError(_USAGE_ERROR)
    counts = _sanitize_counts(comp)

    raw_opts = spec.get("options")
    if raw_opts is None:
        raw_opts = {}
    if not isinstance(raw_opts, dict):
        raise ValueError("options must be an object")
    sign = raw_opts.get("sign", True)
    if not isinstance(sign, bool):
        raise ValueError("options.sign must be a boolean")
    opts = {"sign": sign}
    for key in ("radius_m", "energy_j"):
        v = raw_opts.get(key, 1.0)
        bad = "options.%s must be a finite number > 0" % key
        if isinstance(v, (bool, np.bool_)):
            raise ValueError(bad)
        try:
            v = float(v)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(bad)
        if not (math.isfinite(v) and v > 0):
            raise ValueError(bad)
        opts[key] = v
    return {"property": prop, "composition": counts, "options": opts}


def _honesty_from_state():
    """Honesty block WITHOUT triggering a fit: coverage only once built."""
    if _STATE.get("built"):
        return _honesty(_STATE.get("coverage"), _STATE.get("coverage_n"))
    return _honesty()


def _seal(result, payload_core, sign):
    """Attach receipt + ledger to a FINISHED result. Defence in depth behind
    _validate_spec: if the response or the receipt payload is not strict JSON
    (NaN/inf/odd types), fail CLOSED — nothing signed, nothing ledgered — rather
    than mint a receipt whose bytes could never be re-verified."""
    try:
        json.dumps({"response": result, "receipt_payload": payload_core},
                   allow_nan=False)
    except (ValueError, TypeError) as e:
        return {"ok": False, "fail_closed": True,
                "error": "refusing to sign or ledger: payload is not strict JSON (%s)" % e,
                "property": result.get("property"),
                "composition": result.get("composition"),
                "honesty": _honesty_from_state()}
    receipt = _build_receipt(payload_core, sign=sign)
    result["receipt"] = receipt
    result["ledger"] = _ledger(receipt)
    return result


def predict_property(spec):
    """spec: {composition: {el: count}, property?: 'formation_energy', options?:{}}
    or {demo: 'green'|'ood'}. Returns the governed result dict.

    Order is load-bearing (doctrine: receipt-on-WRITE, never on a malformed
    request): _validate_spec runs FIRST and is pure, so only a well-formed
    request reaches the first-use fit (_build), the signer and the ledger.
    Malformed input returns {ok:false, error, honesty} with none of those side
    effects; responses and receipts carry the SANITIZED counts, never the raw
    composition object."""
    try:
        v = _validate_spec(spec)
    except ValueError as ve:
        return {"ok": False, "error": str(ve), "honesty": _honesty_from_state()}
    prop, counts, opts = v["property"], v["composition"], v["options"]
    sign = opts["sign"]

    st = _build()
    surr, cal, artifact = st["surr"], st.get("cal"), st.get("artifact")
    coverage, coverage_n = st["coverage"], st["coverage_n"]

    # The calibrator must be the one fitted for THIS predictor. A stale binding is a
    # server-side integrity fault: fail closed (HTTP 500), sign and ledger nothing.
    binding = validate_calibration_artifact(artifact, _predictor_hash(surr), _data_hash(),
                                            calibrator=cal, alpha=ALPHA)
    if not binding["valid"]:
        return {"ok": False, "fail_closed": True,
                "error": "calibration artifact does not bind to the served predictor: %s"
                         % binding["reason"],
                "property": prop, "composition": counts,
                "honesty": _honesty(coverage, coverage_n)}
    art_compact = {k: artifact[k] for k in ("schema", "predictor_hash", "data_hash", "protocol",
                                            "calibration_state_hash", "alpha", "n_calibration",
                                            "rank_k", "unbounded", "radius_abs_z")}

    # featurize: the numeric contract already held in _validate_spec, so the only
    # ValueError left is the element-table refusal (hard OOD, honest RED + receipt)
    try:
        x = featurize(counts)
    except InvalidCompositionError as ve:  # unreachable after validation; fail closed
        return {"ok": False, "error": str(ve), "honesty": _honesty(coverage, coverage_n)}
    except ValueError as ve:
        result = {
            "ok": True, "property": prop, "composition": counts,
            "verdict": "RED",
            "refusal": "OUT-OF-DISTRIBUTION: %s" % ve,
            "value": None, "interval95": None,
            "calibration": calibration_report(),
            "calibration_artifact": artifact,
            "honesty": _honesty(coverage, coverage_n),
        }
        return _seal(result, {"property": prop, "composition": counts,
                              "verdict": "RED", "refusal": result["refusal"],
                              "calibration_artifact": art_compact}, sign)

    mu, sigma = surr.predict(x)
    radius = cal.conformal_radius(ALPHA)
    if not math.isfinite(radius):
        # ceil((n+1)(1-alpha)) > n: no finite order statistic carries the guarantee.
        # Abstain honestly instead of serving max|z| as if it were the quantile.
        result = {
            "ok": True, "property": prop, "composition": counts,
            "verdict": "RED",
            "refusal": "%s (n_calibration=%d, rank_k=%d, alpha=%g)"
                       % (ABSTAIN_UNBOUNDED, artifact["n_calibration"], artifact["rank_k"], ALPHA),
            "value": None, "interval95": None,
            "value_eV_atom": None, "interval95_eV_atom": None,
            "interval_is_calibrated": False,
            "ensemble_sigma_eV_atom": round(sigma, 5),
            "calibration": calibration_report(),
            "calibration_artifact": artifact,
            "honesty": _honesty(coverage, coverage_n),
        }
        return _seal(result, {"property": prop, "composition": counts,
                              "verdict": "RED", "refusal": result["refusal"],
                              "calibration_artifact": art_compact}, sign)
    lo, hi = cal.interval(mu, sigma, ALPHA)
    ood = surr.ood_score(x)
    hull = convex_hull_distance(counts, mu)

    # gates. The hull is CHECKED only when applicable with a finite delta; an
    # unchecked hull is unknown evidence and can never be favorable (no GREEN).
    delta = hull.get("delta_hull_eV_atom")
    hull_checked = bool(hull.get("applicable")) and delta is not None and math.isfinite(delta)
    hull_red = hull_checked and delta > HULL_RED
    hull_yellow = hull_checked and delta > HULL_GREEN
    ood_red = ood > OOD_Z_RED
    ood_yellow = ood > OOD_Z_YELLOW
    sigma_yellow = sigma > SIGMA_YELLOW

    # Bekenstein F19 check: prior std = spread of dataset targets; posterior = sigma.
    prior_sigma = float(np.std(st["y"]))
    bek = bekenstein_check(prior_sigma, max(sigma, 1e-6),
                           radius_m=opts["radius_m"], energy_j=opts["energy_j"])

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
    if verdict != "RED" and (ood_yellow or hull_yellow or sigma_yellow or not hull_checked):
        verdict = "YELLOW"
        if ood_yellow:
            reasons.append("near distribution edge (ood_score=%.3f)" % ood)
        if hull_yellow:
            reasons.append("metastable: Delta_hull=%.3f eV/atom in (%.2f, %.2f]"
                           % (delta, HULL_GREEN, HULL_RED))
        if not hull_checked:
            reasons.append("%s (%s)" % (HULL_NOT_APPLICABLE, hull.get("reason", "no hull evidence")))
        if sigma_yellow:
            reasons.append("elevated epistemic uncertainty (sigma=%.3f eV/atom)" % sigma)
    if verdict == "GREEN":
        reasons.append("in-distribution, on/near hull vs %d embedded competing phase(s), "
                       "calibrated interval — plausible" % hull.get("competing_phases", 0))

    refuse = verdict == "RED"
    lam = compute_lambda(verdict, ood, sigma, hull_ok=hull_checked and not hull_red)

    result = {
        "ok": True,
        "property": prop,
        "composition": counts,
        "verdict": verdict,
        "value_eV_atom": (None if refuse else round(mu, 5)),
        "ensemble_sigma_eV_atom": round(sigma, 5),
        "interval95_eV_atom": (None if refuse else [round(lo, 5), round(hi, 5)]),
        "interval_is_calibrated": True,
        "interval_method": ("symmetric split-conformal |z| radius (rank %d of n=%d, in-sample "
                            "calibrator) times ensemble sigma"
                            % (artifact["rank_k"], artifact["n_calibration"])),
        "ood_score": round(ood, 4),
        "convex_hull_gate": hull,
        "hull_checked": hull_checked,
        "bekenstein_f19": bek,
        "lambda_advisory": lam,
        "calibration": calibration_report(),
        "calibration_artifact": artifact,
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

    return _seal(result, {
        "property": prop, "composition": counts, "verdict": verdict,
        "value_eV_atom": result["value_eV_atom"],
        "interval95_eV_atom": result["interval95_eV_atom"],
        "ensemble_sigma_eV_atom": result["ensemble_sigma_eV_atom"],
        "ood_score": result["ood_score"],
        "convex_hull_gate": hull,
        "hull_checked": hull_checked,
        "bekenstein_f19": bek,
        "lambda_advisory": lam,
        "calibration": {"measured_coverage": _r4(coverage),
                        "measured_coverage_n": int(coverage_n),
                        "measured_coverage_protocol": "cv_split_models",
                        "serving_protocol_coverage": _r4(st["serving"]["coverage"]),
                        "serving_protocol_coverage_n": int(st["serving"]["n"]),
                        "target_coverage": 1.0 - ALPHA},
        "calibration_artifact": art_compact,
    }, sign)


# ---------------------------------------------------------------------------
# HTTP surface — POST /api/a11oy/v1/materials/predict (+ GET /materials/health).
# Registered BEFORE the SPA/Node catch-all (serve.py front-moves to router head).
# ---------------------------------------------------------------------------
def register(app, ns="a11oy"):
    from fastapi.responses import JSONResponse
    from fastapi import Request

    # /predict is a governed WRITE (fit, sign, ledger). GET must stay inert, so it
    # answers 405 + Allow: POST with a usage body instead of running a demo.
    get_not_allowed = {
        "ok": False,
        "error": "GET is not allowed on /materials/predict: predicting fits the "
                 "surrogate, signs a receipt and writes the ledger, and signing "
                 "belongs on writes, never on reads. Use POST.",
        "usage": {
            "method": "POST",
            "body": {"composition": {"Fe": 2, "O": 3}, "property": "formation_energy",
                     "options": {"sign": True, "radius_m": 1.0, "energy_j": 1.0}},
            "or": {"demo": "green | ood"},
            "verdicts": ("GREEN needs an applicable hull with >= 1 embedded competing "
                         "phase; a binary with elemental endpoints only (e.g. MgO) or a "
                         "non-binary query is YELLOW: %s" % HULL_NOT_APPLICABLE),
        },
        "read_only": "GET /api/%s/v1/materials/health (never fits, never signs)" % ns,
        "honesty": _honesty(),
    }

    def _status(out):
        if out.get("fail_closed"):
            return 500
        return 200 if out.get("ok") else 400

    async def _predict(request: Request):
        try:
            try:
                spec = await request.json()
            except Exception:  # noqa: BLE001 — malformed body is a client error, not a demo
                spec = None
            if not isinstance(spec, dict) or not spec:
                return JSONResponse({"ok": False, "error": _USAGE_ERROR,
                                     "honesty": _honesty_from_state()},
                                    status_code=400,
                                    headers={"x-szl-organ": RECEIPT_ORGAN})
            out = predict_property(spec)
            return JSONResponse(out, status_code=_status(out), headers={
                "x-szl-materials-verdict": str(out.get("verdict", "NA")),
                "x-szl-organ": RECEIPT_ORGAN})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "%r" % e,
                                 "honesty": _honesty_from_state()}, status_code=500)

    async def _predict_get():
        return JSONResponse(get_not_allowed, status_code=405,
                            headers={"Allow": "POST", "x-szl-organ": RECEIPT_ORGAN})

    async def _health():
        # Health is a READ: it never fits. Until the first POST /predict builds the
        # surrogate it says so, keeping ok:true/200 so szl_engine_status stays reachable.
        artifact = None
        if _STATE.get("built"):
            try:
                rep = calibration_report()
                artifact = _STATE.get("artifact")
            except Exception as e:  # noqa: BLE001
                rep = {"error": "calibration unavailable (%r)" % e}
        else:
            rep = {"state": "NOT_BUILT",
                   "note": "health never fits; built on first POST /predict"}
        return JSONResponse({
            "ok": True, "organ": RECEIPT_ORGAN,
            "endpoint": "POST /api/%s/v1/materials/predict" % ns,
            "vertical": "materials-property-prediction (governed, calibrated surrogate)",
            "property": "formation_energy (eV/atom)",
            "model": ("numpy-only 5-member bootstrap ridge (linear) ensemble over "
                      "composition descriptors with a symmetric split-conformal |z| interval "
                      "from an in-sample calibrator; MODELED + SAMPLE surrogate — NOT "
                      "MACE/CHGNet/DFT and NOT a deep ensemble (that pattern is cited prior art)"),
            "gates": {
                "self_doubt_ood": "ood_score > %.2f => RED/refuse" % OOD_Z_RED,
                "convex_hull": ("Delta_hull > %.2f eV/atom => RED; hull not applicable "
                                "(non-binary, or no embedded competing phase) => YELLOW, "
                                "never GREEN" % HULL_RED),
                "f19_bekenstein": "information-cost ratio <= 1 required",
                "calibration": ("unbounded split-conformal radius (ceil((n+1)(1-alpha)) > n) "
                                "=> RED abstain; stale calibration artifact => fail closed"),
            },
            "calibration": rep,
            "calibration_artifact": artifact,
            "demos": {"green": ("POST {\"demo\":\"green\"} -> GREEN Fe2O3: in-distribution, "
                                "hull applicable vs embedded Fe-O competing phases"),
                      "ood": "POST {\"demo\":\"ood\"} -> RED Cu-Au out-of-distribution refusal",
                      "note": ("MgO is reachable as an explicit composition and answers "
                               "YELLOW: it is the only embedded Mg-O phase, so its hull is "
                               "unverifiable")},
            "elements": sorted(_ELEM),
            "honesty": _honesty(rep.get("measured_coverage"), rep.get("measured_coverage_n")),
            "citations": list(CITATIONS),
        })

    prefixes = ["/api/%s/v1/materials" % ns, "/v1/materials"]
    routes = []
    for p in prefixes:
        app.add_api_route("%s/predict" % p, _predict, methods=["POST"],
                          include_in_schema=True)
        # Same path, GET only: an explicit 405 + Allow: POST + usage body, so a
        # browser or a curl without -X POST can never trigger a fit or a signature.
        app.add_api_route("%s/predict" % p, _predict_get, methods=["GET"],
                          include_in_schema=False)
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
