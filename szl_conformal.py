# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_conformal.py — SHARED split-conformal prediction helper (Lane B / Dev B).

Purpose
-------
Convert a bare model confidence / softmax distribution into a PREDICTION SET S
that carries a finite-sample marginal coverage guarantee:

    Pr( y_true ∈ S(x) )  >=  1 - alpha     (under exchangeability)

This is the doctrine's anti-overclaiming primitive: it replaces "confidence 87%"
with "true class in {A, B} with >=95% coverage guarantee". Everywhere a11oy (and,
via the shared API below, killinchu / Dev D's threat classifier) shows a confidence
number for a classification/decision, it should instead show a conformal set.

Method — Split / Inductive Conformal Prediction (Vovk 2005; Angelopoulos & Bates,
"A Gentle Introduction to Conformal Prediction", arXiv:2107.07511; LLM application
Kumar et al. arXiv:2305.18404). Pure-Python, NO numpy/scipy dependency so it ships
byte-identical into both the a11oy and killinchu images.

Nonconformity score (softmax / 1-p form):
    s_i = 1 - p_hat(y_i | x_i)
Threshold (finite-sample corrected quantile):
    q_hat = Quantile( {s_i}, ceil((n+1)(1-alpha)) / n )
Prediction set for a new x:
    C(x) = { y : 1 - p_hat(y | x) <= q_hat }

Honesty rules (doctrine):
  * Coverage is MARGINAL and assumes exchangeability of the calibration data with
    the test point. We label this explicitly; it is NOT a per-instance guarantee.
  * With too few calibration points (n such that ceil((n+1)(1-alpha)) > n) the
    finite-sample quantile is undefined -> q_hat = 1.0 -> the set is the FULL label
    space (maximally honest: "cannot exclude any class at this coverage yet").
    We never fabricate a tight set from insufficient calibration.
  * trust < 100%: coverage is reported as the requested 1-alpha, never "100%".

PUBLIC API (stable — Dev D imports this; see RESULT_DEVB_AGENTIC.md):
    conformal_quantile(scores, alpha)                  -> float
    prediction_set(probs, q_hat, labels=None)          -> dict
    conformal_set(probs, calib_scores, alpha, labels)  -> dict   (one-shot convenience)
    ConformalClassifier(labels, alpha).calibrate(...).predict_set(probs) -> dict
    bare_pct_to_set(probs, ...)                         -> dict   (drop-in "replace bare %")

DCO: Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

__all__ = [
    "conformal_quantile",
    "prediction_set",
    "conformal_set",
    "bare_pct_to_set",
    "ConformalClassifier",
    "DEFAULT_ALPHA",
    "HELPER_VERSION",
    # --- governed-inference Λ layer (GAP 1 / GAP 2; NumPy-only, lazy) ---
    "classify_bucket",
    "LambdaConformalGovernor",
    "get_lambda_governor",
    "lambda_conformal_blocks",
    "LAMBDA_BUCKETS",
    "CP_MIN_MEASURED_N",
]

HELPER_VERSION = "szl_conformal/1.0.0"
DEFAULT_ALPHA = 0.05  # 95% coverage target (doctrine default for decisions)

_REF = ("Split/inductive conformal prediction (Vovk 2005; Angelopoulos & Bates "
        "arXiv:2107.07511; LLM sets Kumar et al. arXiv:2305.18404).")


def _as_float_list(xs: Sequence[Any]) -> list[float]:
    out: list[float] = []
    for x in xs:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _normalize(probs: Sequence[float]) -> list[float]:
    """Clamp to [0,1] and L1-normalize so the vector is a proper distribution.
    If the input does not sum to a positive value, fall back to uniform (honest:
    no information -> every class equally plausible)."""
    p = [max(0.0, min(1.0, float(v))) for v in probs]
    s = sum(p)
    if s <= 0:
        n = len(p) or 1
        return [1.0 / n] * len(p)
    return [v / s for v in p]


def conformal_quantile(scores: Sequence[float], alpha: float = DEFAULT_ALPHA) -> float:
    """Finite-sample corrected conformal threshold q_hat over calibration
    nonconformity scores.

        q_hat = the ceil((n+1)(1-alpha))/n empirical quantile of {scores}.

    Returns 1.0 (=> full-label-space set, maximally honest) when there are too
    few calibration points for the requested coverage, or on bad input. Never
    raises."""
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        a = DEFAULT_ALPHA
    a = min(0.999, max(1e-6, a))
    s = sorted(_as_float_list(scores))
    n = len(s)
    if n == 0:
        return 1.0
    # rank for the (1-alpha) quantile with finite-sample (n+1) correction
    rank = math.ceil((n + 1) * (1.0 - a))
    if rank > n:
        # insufficient calibration data for this coverage at this n
        return 1.0
    if rank < 1:
        rank = 1
    return float(s[rank - 1])


def prediction_set(probs: Sequence[float], q_hat: float,
                   labels: Optional[Sequence[Any]] = None) -> dict:
    """Build the conformal prediction set C(x) = { y : 1 - p(y|x) <= q_hat }.

    Always returns a non-empty set: if no class satisfies the threshold (can
    happen with a very tight q_hat), the single argmax class is included so the
    decision surface never shows an empty set. Pure, never raises."""
    p = _normalize(probs)
    k = len(p)
    lbls = list(labels) if labels is not None and len(list(labels)) == k else list(range(k))
    try:
        q = float(q_hat)
    except (TypeError, ValueError):
        q = 1.0
    members: list[dict] = []
    for i, pi in enumerate(p):
        if (1.0 - pi) <= q + 1e-12:
            members.append({"label": lbls[i], "p": round(pi, 6)})
    if not members and k:
        j = max(range(k), key=lambda i: p[i])
        members.append({"label": lbls[j], "p": round(p[j], 6)})
    members.sort(key=lambda m: m["p"], reverse=True)
    argmax_i = max(range(k), key=lambda i: p[i]) if k else None
    return {
        "set": [m["label"] for m in members],
        "members": members,
        "set_size": len(members),
        "argmax": (lbls[argmax_i] if argmax_i is not None else None),
        "argmax_p": (round(p[argmax_i], 6) if argmax_i is not None else None),
        "q_hat": round(q, 6),
        "singleton": len(members) == 1,
    }


def conformal_set(probs: Sequence[float], calib_scores: Sequence[float],
                 alpha: float = DEFAULT_ALPHA,
                 labels: Optional[Sequence[Any]] = None) -> dict:
    """One-shot convenience: compute q_hat from calibration scores then build the
    set for `probs`. Returns the prediction-set dict enriched with the coverage
    target and an honesty string. This is the primary entry point for surfaces
    that already hold a calibration pool. Never raises."""
    q = conformal_quantile(calib_scores, alpha)
    out = prediction_set(probs, q, labels)
    cov = round(1.0 - min(0.999, max(1e-6, float(alpha))), 4)
    out.update({
        "alpha": round(float(alpha), 6),
        "coverage_target": cov,
        "coverage_pct": round(cov * 100.0, 2),
        "calibration_n": len(list(calib_scores)),
        "guarantee": ("true class in set with >= %.0f%% marginal coverage "
                      "(exchangeability assumed; NOT a per-instance or 100%% "
                      "guarantee)" % (cov * 100.0)),
        "method": _REF,
        "helper": HELPER_VERSION,
        "full_label_space": (out["q_hat"] >= 1.0),
    })
    return out


def bare_pct_to_set(probs: Sequence[float], calib_scores: Sequence[float],
                   alpha: float = DEFAULT_ALPHA,
                   labels: Optional[Sequence[Any]] = None) -> dict:
    """Doctrine helper: take what would have been a bare "confidence X%" softmax
    and return both the honest conformal set AND a human-readable replacement
    string for the bare percentage. Use this anywhere a UI used to print a single
    confidence number."""
    cs = conformal_set(probs, calib_scores, alpha, labels)
    if cs["singleton"]:
        disp = "{%s} — true class in this singleton set with >=%.0f%% coverage" % (
            str(cs["set"][0]), cs["coverage_pct"])
    else:
        disp = "{%s} — true class in this set with >=%.0f%% coverage" % (
            ", ".join(str(s) for s in cs["set"]), cs["coverage_pct"])
    cs["display"] = disp
    cs["replaces_bare_pct"] = ("conf %.1f%% (argmax)" % (
        (cs["argmax_p"] or 0.0) * 100.0))
    return cs


class ConformalClassifier:
    """Stateful split-conformal wrapper. Maintain a rolling calibration pool of
    nonconformity scores s_i = 1 - p_hat(y_i | x_i) from VERIFIED outcomes, then
    wrap any new softmax in a coverage-guaranteed prediction set.

    Usage (Dev D threat-classify shape):
        cc = ConformalClassifier(labels=["BENIGN","SUSPECT","HOSTILE"], alpha=0.05)
        cc.calibrate(true_label, probs)        # on every ground-truth-known case
        out = cc.predict_set(probs_for_new_x)  # {set, coverage_target, ...}
    """

    def __init__(self, labels: Sequence[Any], alpha: float = DEFAULT_ALPHA,
                 window: int = 200) -> None:
        self.labels = list(labels)
        self.alpha = float(alpha)
        self.window = int(window) if window and window > 0 else 200
        self._scores: list[float] = []

    def _label_index(self, label: Any) -> Optional[int]:
        try:
            return self.labels.index(label)
        except ValueError:
            return None

    def calibrate(self, true_label: Any, probs: Sequence[float]) -> "ConformalClassifier":
        """Add one calibration point from a case whose TRUE label is now known."""
        p = _normalize(probs)
        i = self._label_index(true_label)
        if i is None and isinstance(true_label, int) and 0 <= true_label < len(p):
            i = true_label
        if i is None or i >= len(p):
            return self
        self._scores.append(1.0 - p[i])
        if len(self._scores) > self.window:
            self._scores = self._scores[-self.window:]
        return self

    def calibrate_many(self, pairs: Sequence[tuple]) -> "ConformalClassifier":
        for true_label, probs in pairs:
            self.calibrate(true_label, probs)
        return self

    @property
    def n_calibration(self) -> int:
        return len(self._scores)

    def q_hat(self) -> float:
        return conformal_quantile(self._scores, self.alpha)

    def predict_set(self, probs: Sequence[float]) -> dict:
        out = conformal_set(probs, self._scores, self.alpha, self.labels)
        out["classifier_window"] = self.window
        return out

    def predict_display(self, probs: Sequence[float]) -> dict:
        return bare_pct_to_set(probs, self._scores, self.alpha, self.labels)


# ════════════════════════════════════════════════════════════════════════════
# GOVERNED-INFERENCE Λ LAYER  —  Split-Conformal interval + Mondrian buckets + ECE
# (GAP_ML.md GAP 1/GAP 2, RANK 1).  NumPy-only, NO MAPIE/crepes/torch dependency —
# the math is reimplemented here (public domain: Vovk 1999; Angelopoulos & Bates
# 2021 arXiv:2107.07511; Guo et al. 2017 arXiv:1706.04599). numpy is imported
# LAZILY inside this layer so the pure-Python helper above stays dependency-free and
# byte-identical across images; if numpy is somehow absent the governor degrades to
# UNAVAILABLE and the caller falls back to the existing MODELED Λ behaviour.
#
# DOCTRINE (non-negotiable): Λ stays Conjecture 1, advisory, ≤0.99, NEVER a theorem,
# NEVER 1.0. The conformal block is labelled MEASURED **only** when computed against a
# real held-out calibration split of n ≥ CP_MIN_MEASURED_N with the achieved coverage
# actually measured. Seed/bootstrap data is labelled SAMPLE. Cold start (no data) is
# UNAVAILABLE. ECE is never reported as 0 — the measured value is always emitted. The
# half-state (claiming more than is real) is the only unacceptable outcome.
# ════════════════════════════════════════════════════════════════════════════

LAMBDA_BUCKETS = ("code-gen", "factual-QA", "math", "other")
CP_MIN_MEASURED_N = 500     # real held-out points required before MEASURED is allowed
ECE_MIN_MEASURED_N = 100    # real validation points required before TEMP-SCALED MEASURED
_LAMBDA_CP_VERSION = "szl_conformal.lambda/1.0.0"


def _np():
    """Lazy numpy import. Returns the module or None (never raises)."""
    try:
        import numpy as _n
        return _n
    except Exception:
        return None


# --- query-type bucketing for Mondrian (bucketed) conditional validity --------
import re as _re

_RX_CODE = _re.compile(
    r"```|\b(def |class |import |function|public |private |const |return\b|"
    r"npm |pip install|SELECT |CREATE TABLE|stack ?trace|compile|refactor|"
    r"unit test|regex|API|JSON|YAML|bug\b|exception)\b", _re.I)
_RX_MATH = _re.compile(
    r"\b(prove|proof|theorem|integral|derivative|matrix|eigen|probability|"
    r"equation|solve for|factorial|polynomial|\\frac|\\sum|\\int)\b|"
    r"[0-9]\s*[\+\-\*/\^=]\s*[0-9]|\b\d+\s*[x-z]\b", _re.I)
_RX_FACT = _re.compile(
    r"^\s*(who|what|when|where|which|whom|whose|how many|how much|"
    r"is |are |was |were |did |does |list the|name the|define)\b", _re.I)


def classify_bucket(prompt: str) -> str:
    """Map a prompt to a Mondrian query-type bucket for per-bucket (conditional)
    conformal validity. Heuristic, deterministic, transparent — buckets are
    {code-gen, factual-QA, math, other}. Never raises."""
    t = (prompt or "").strip()
    if not t:
        return "other"
    if _RX_CODE.search(t):
        return "code-gen"
    if _RX_MATH.search(t):
        return "math"
    if _RX_FACT.search(t):
        return "factual-QA"
    return "other"


# --- the 8–15 line NumPy core (reimplemented; public-domain math) -------------
def _cp_quantile_np(scores, alpha):
    """Split-conformal threshold q̂ = the ceil((n+1)(1-α))/n empirical quantile of
    the nonconformity scores (Vovk; Angelopoulos & Bates 2021). Finite-sample,
    distribution-free. Returns (q_hat, n)."""
    np = _np()
    s = np.sort(np.asarray(scores, dtype=float))
    n = int(s.size)
    if n == 0:
        return float("inf"), 0
    rank = int(np.ceil((n + 1) * (1.0 - alpha)))
    if rank > n:            # too few points for this coverage → no finite threshold
        return float("inf"), n
    return float(s[max(1, rank) - 1]), n


def _measured_coverage_np(scores, alpha):
    """Honest *achieved* empirical coverage on a held-out split: fit q̂ on one half
    of the calibration scores, then measure the fraction of the OTHER half whose
    nonconformity ≤ q̂. This is the real finite-sample coverage number, not the
    nominal target. Returns (coverage_achieved, q_hat_full, n_fit, n_val)."""
    np = _np()
    s = np.asarray(scores, dtype=float)
    n = int(s.size)
    if n < 4:
        q, _ = _cp_quantile_np(s, alpha)
        return None, q, 0, 0
    rng = np.random.default_rng(1999)              # Vovk 1999; deterministic split
    idx = rng.permutation(n)
    cut = n // 2
    fit, val = s[idx[:cut]], s[idx[cut:]]
    q_fit, _ = _cp_quantile_np(fit, alpha)
    cov = float(np.mean(val <= q_fit)) if np.isfinite(q_fit) else None
    q_full, _ = _cp_quantile_np(s, alpha)
    return cov, q_full, int(fit.size), int(val.size)


def _temperature_scale_np(logits, labels):
    """Temperature scaling T* = argmin NLL of σ(z/T) on a validation set (Guo et al.
    2017). Binary trust head: y∈{0,1}, z=logit. 1-D search (coarse log grid + local
    refine) — no scipy. Returns T* > 0."""
    np = _np()
    z = np.asarray(logits, dtype=float)
    y = np.asarray(labels, dtype=float)
    if z.size == 0:
        return 1.0

    def nll(T):
        p = 1.0 / (1.0 + np.exp(-z / T))
        p = np.clip(p, 1e-7, 1 - 1e-7)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    grid = np.geomspace(0.05, 20.0, 64)
    best = min(grid, key=nll)
    lo, hi = best / 1.5, best * 1.5            # local golden-ish refine
    for _ in range(40):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if nll(m1) < nll(m2):
            hi = m2
        else:
            lo = m1
    return float(max(1e-3, (lo + hi) / 2))


def _ece_np(probs, labels, n_bins=15):
    """Expected Calibration Error: Σ_m (|B_m|/n) |acc(B_m) − conf(B_m)| over n_bins
    equal-width confidence bins (Guo et al. 2017). Returns ECE ≥ 0."""
    np = _np()
    p = np.clip(np.asarray(probs, dtype=float), 0.0, 1.0)
    y = np.asarray(labels, dtype=float)
    if p.size == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece, n = 0.0, p.size
    for m in range(n_bins):
        lo, hi = edges[m], edges[m + 1]
        sel = (p > lo) & (p <= hi) if m > 0 else (p >= lo) & (p <= hi)
        cnt = int(np.sum(sel))
        if cnt == 0:
            continue
        ece += (cnt / n) * abs(float(np.mean(y[sel])) - float(np.mean(p[sel])))
    return float(ece)


class LambdaConformalGovernor:
    """Per-bucket (Mondrian) calibration store for the governed-inference Λ.

    Holds, per query-type bucket:
      * real nonconformity scores  s_i = |Λ_i − y_i|  (from delayed ground-truth
        feedback via record_outcome) — these and ONLY these can yield MEASURED;
      * SAMPLE seed scores (synthetic bootstrap) — yield at most SAMPLE;
      * a validation set (logit, y∈{0,1}) for temperature scaling + ECE.

    conformal_block()/calibration_block() emit the EXACT receipt schema from
    GAP_ML.md §(b). All math is via the NumPy core above; every method is guarded
    and never raises into the infer path."""

    def __init__(self, alpha: float = 0.10, window: int = 5000) -> None:
        self.alpha = float(alpha)
        self.window = int(window) if window and window > 0 else 5000
        self._real: dict[str, list] = {b: [] for b in LAMBDA_BUCKETS}
        self._seed: dict[str, list] = {b: [] for b in LAMBDA_BUCKETS}
        self._val:  dict[str, list] = {b: [] for b in LAMBDA_BUCKETS}   # (logit, y)
        self._seeded = False

    # -- ingestion -----------------------------------------------------------
    def _bucket(self, bucket):
        return bucket if bucket in self._real else "other"

    def record_outcome(self, bucket: str, lam: float, y: float) -> "LambdaConformalGovernor":
        """Record a REAL (Λ, realized-outcome) pair → nonconformity |Λ−y|. This is
        the live-traffic feedback hook that upgrades a bucket SAMPLE→MEASURED once
        n_real ≥ CP_MIN_MEASURED_N."""
        try:
            b = self._bucket(bucket)
            self._real[b].append(abs(float(lam) - float(y)))
            if len(self._real[b]) > self.window:
                self._real[b] = self._real[b][-self.window:]
        except Exception:
            pass
        return self

    def record_validation(self, bucket: str, logit: float, y: float) -> "LambdaConformalGovernor":
        try:
            b = self._bucket(bucket)
            self._val[b].append((float(logit), float(y)))
            if len(self._val[b]) > self.window:
                self._val[b] = self._val[b][-self.window:]
        except Exception:
            pass
        return self

    def seed_bucket(self, bucket: str, scores, val=None) -> "LambdaConformalGovernor":
        """Bootstrap a bucket with SAMPLE-labelled synthetic scores (and optional
        validation (logit,y) pairs). Never counts toward MEASURED."""
        try:
            b = self._bucket(bucket)
            self._seed[b].extend(float(s) for s in scores)
            if val:
                self._val[b].extend((float(z), float(y)) for z, y in val)
            self._seeded = True
        except Exception:
            pass
        return self

    def n_real(self, bucket: str) -> int:
        return len(self._real[self._bucket(bucket)])

    # -- the product: receipt blocks ----------------------------------------
    def conformal_block(self, lam: float, bucket: str = "other",
                        alpha: float | None = None) -> dict:
        """Build the GAP_ML.md §(b) "conformal" block for a Λ point estimate.

        Honest label ladder (doctrine):
          n_real ≥ CP_MIN_MEASURED_N        → "CP-NN MEASURED"  (coverage measured)
          seed present / 0 < n < min        → "CP-NN SAMPLE"    (bootstrap)
          nothing                           → "CP-NN UNAVAILABLE" (Λ stays MODELED)
        Returns a dict that ALWAYS includes a `label` and never raises."""
        a = float(alpha if alpha is not None else self.alpha)
        a = min(0.999, max(1e-6, a))
        cov_target = round(1.0 - a, 4)
        tag = "CP-%d" % round(cov_target * 100)
        b = self._bucket(bucket)
        out = {
            "coverage_target": cov_target,
            "coverage_achieved": None,
            "n": 0,
            "alpha": round(a, 6),
            "q_hat": None,
            "bucket": b,
            "interval": None,
            "score_fn": "abs_residual |Λ−y|",
            "method": ("split-conformal finite-sample quantile (Vovk 1999; "
                       "Angelopoulos & Bates 2021 arXiv:2107.07511); Mondrian "
                       "per-bucket q̂_b for conditional validity"),
            "label": tag + " UNAVAILABLE",
            "honesty": ("marginal coverage only (exchangeability assumed); NOT a "
                        "confidence interval on Λ and NOT 100%% coverage"),
        }
        np = _np()
        if np is None:
            out["honesty"] = "numpy unavailable — conformal degraded; Λ stays MODELED"
            return out
        try:
            lam = float(lam)
            real = self._real[b]
            seed = self._seed[b]
            n_real = len(real)
            if n_real >= CP_MIN_MEASURED_N:
                scores, src = real, "MEASURED"
            elif (n_real + len(seed)) > 0:
                scores, src = (real + seed), "SAMPLE"
            else:
                return out  # UNAVAILABLE

            cov, q_full, n_fit, n_val = _measured_coverage_np(scores, a)
            if not np.isfinite(q_full):
                # insufficient calibration for this coverage → honest, no MEASURED
                out["n"] = len(scores)
                out["label"] = tag + " UNAVAILABLE"
                out["honesty"] = ("calibration too small for finite-sample q̂ at this "
                                  "coverage; Λ stays MODELED")
                return out
            lo = round(max(0.0, lam - q_full), 4)
            hi = round(min(1.0, lam + q_full), 4)
            out["q_hat"] = round(q_full, 6)
            out["interval"] = [lo, hi]
            out["n"] = len(scores)
            out["coverage_achieved"] = (round(cov, 4) if cov is not None else None)
            out["n_holdout_fit"] = n_fit
            out["n_holdout_val"] = n_val
            out["label"] = tag + " " + src
            if src == "SAMPLE":
                out["honesty"] = ("SAMPLE bootstrap calibration (synthetic seed) — "
                                  "upgrades to MEASURED once n_real ≥ %d real "
                                  "outcomes; marginal coverage only" % CP_MIN_MEASURED_N)
        except Exception as e:  # pragma: no cover
            out["label"] = tag + " UNAVAILABLE"
            out["honesty"] = "conformal computation failed (%r); Λ stays MODELED" % e
        return out

    def calibration_block(self, bucket: str = "other", n_bins: int = 15) -> dict:
        """Build the GAP_ML.md §(b) "calibration" block (temperature scaling + ECE).
        ECE is never reported as 0 by fiat — the measured value is emitted. Returns
        a dict that ALWAYS includes a `label` and never raises."""
        b = self._bucket(bucket)
        out = {
            "method": "TEMP-SCALED",
            "T": None,
            "ECE_pre": None,
            "ECE_post": None,
            "n_validation": 0,
            "bucket": b,
            "ref": "Guo et al. 2017 arXiv:1706.04599",
            "label": "TEMP-SCALED UNAVAILABLE",
            "honesty": ("post-hoc, approximate — never 'perfectly calibrated'; "
                        "ECE→0 but never 0; calibration is per-bucket, not OOD"),
        }
        np = _np()
        if np is None:
            return out
        try:
            val = self._val[b]
            n = len(val)
            if n == 0:
                return out
            z = np.asarray([p[0] for p in val], dtype=float)
            y = np.asarray([p[1] for p in val], dtype=float)
            T = _temperature_scale_np(z, y)
            p_pre = 1.0 / (1.0 + np.exp(-z))
            p_post = 1.0 / (1.0 + np.exp(-z / T))
            ece_pre = _ece_np(p_pre, y, n_bins)
            ece_post = _ece_np(p_post, y, n_bins)
            src = "MEASURED" if n >= ECE_MIN_MEASURED_N and not self._seed[b] else "SAMPLE"
            out.update({
                "T": round(T, 4),
                "ECE_pre": round(ece_pre, 5),
                "ECE_post": round(ece_post, 5),
                "n_validation": n,
                "label": "TEMP-SCALED " + src,
            })
            if src == "SAMPLE":
                out["honesty"] = ("SAMPLE bootstrap validation set — ECE/T measured "
                                  "on synthetic seed; " + out["honesty"])
        except Exception as e:  # pragma: no cover
            out["label"] = "TEMP-SCALED UNAVAILABLE"
            out["honesty"] = "calibration computation failed (%r)" % e
        return out

    @staticmethod
    def human_label(lam: float, conformal: dict) -> str:
        """The EXACT honest one-line label from GAP_ML.md / the task spec, e.g.:
        `Λ=0.71 [CP-90:(0.63,0.79)] MEASURED | coverage=0.903 | n=847 | α=0.10 | bucket=code-gen`
        Falls back to a MODELED label when the conformal block is not MEASURED/SAMPLE."""
        try:
            tag = conformal.get("label", "")
            iv = conformal.get("interval")
            parts = ["Λ=%s" % round(float(lam), 3)]
            if iv and len(iv) == 2:
                cp = tag.split()[0]   # "CP-90"
                parts.append("[%s:(%.2f,%.2f)]" % (cp, iv[0], iv[1]))
            state = tag.split()[-1] if tag else "MODELED"
            parts.append(state)
            cov = conformal.get("coverage_achieved")
            if cov is not None:
                parts.append("| coverage=%.3f" % cov)
            parts.append("| n=%d" % int(conformal.get("n", 0)))
            parts.append("| α=%.2f" % float(conformal.get("alpha", 0.10)))
            parts.append("| bucket=%s" % conformal.get("bucket", "other"))
            return " ".join(parts)
        except Exception:
            return "Λ=%s MODELED" % round(float(lam), 3)


# --- module-level singleton + SAMPLE seed bootstrap --------------------------
_LAMBDA_GOVERNOR: "LambdaConformalGovernor | None" = None


def _seed_governor(gov: "LambdaConformalGovernor") -> None:
    """Bootstrap every bucket with a SMALL, clearly-SAMPLE-labelled synthetic seed
    so a cold-start governed turn emits an honest SAMPLE conformal block (never
    MEASURED, never empty/over-claimed) until real feedback fills the buffer. The
    seed is generated deterministically; it carries NO MEASURED authority."""
    np = _np()
    if np is None:
        return
    rng = np.random.default_rng(2107)  # arXiv:2107.07511
    for b in LAMBDA_BUCKETS:
        # plausible small residuals |Λ−y| around 0.05–0.12 (advisory Λ near 0.9+)
        scores = np.clip(np.abs(rng.normal(0.0, 0.07, size=64)), 0.0, 1.0)
        # synthetic, mildly-overconfident logits for ECE seed (post-RLHF style)
        z = rng.normal(1.4, 1.1, size=64)
        py = 1.0 / (1.0 + np.exp(-z * 0.7))         # true prob below stated
        y = (rng.random(64) < py).astype(float)
        gov.seed_bucket(b, scores.tolist(), val=list(zip(z.tolist(), y.tolist())))


def get_lambda_governor() -> "LambdaConformalGovernor":
    """Process-wide singleton governor, SAMPLE-seeded on first use. Never raises."""
    global _LAMBDA_GOVERNOR
    if _LAMBDA_GOVERNOR is None:
        g = LambdaConformalGovernor(alpha=0.10)
        try:
            _seed_governor(g)
        except Exception:
            pass
        _LAMBDA_GOVERNOR = g
    return _LAMBDA_GOVERNOR


def lambda_conformal_blocks(lam: float, prompt: str = "",
                            alpha: float = 0.10) -> dict:
    """Top-level convenience for the infer/govern path: classify the bucket, then
    return {conformal, calibration, lambda_label, bucket}. Fully guarded — on ANY
    failure returns a MODELED-fallback dict so the caller never breaks. This is the
    single entry point szl_governed_api wires in."""
    try:
        gov = get_lambda_governor()
        bucket = classify_bucket(prompt)
        conformal = gov.conformal_block(lam, bucket=bucket, alpha=alpha)
        calibration = gov.calibration_block(bucket=bucket)
        return {
            "conformal": conformal,
            "calibration": calibration,
            "lambda_label": LambdaConformalGovernor.human_label(lam, conformal),
            "bucket": bucket,
            "helper": _LAMBDA_CP_VERSION,
        }
    except Exception as e:  # pragma: no cover
        return {
            "conformal": {"label": "CP UNAVAILABLE", "honesty":
                          "conformal layer failed (%r); Λ stays MODELED" % e},
            "calibration": {"label": "TEMP-SCALED UNAVAILABLE"},
            "lambda_label": "Λ=%s MODELED" % (round(float(lam), 3)
                                              if isinstance(lam, (int, float)) else lam),
            "bucket": "other",
        }


# Self-test (run: python3 szl_conformal.py). No external deps.
if __name__ == "__main__":  # pragma: no cover
    import random
    random.seed(7)
    labels = ["BENIGN", "SUSPECT", "HOSTILE"]
    cc = ConformalClassifier(labels, alpha=0.10, window=300)
    # synthesize a moderately-calibrated 3-class model and calibrate on 250 cases
    for _ in range(250):
        true = random.randrange(3)
        logits = [random.gauss(0, 1) for _ in range(3)]
        logits[true] += 1.6  # model is right-ish but not perfect
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        s = sum(exps)
        probs = [e / s for e in exps]
        cc.calibrate(true, probs)
    print("n_calibration:", cc.n_calibration, "q_hat:", round(cc.q_hat(), 4))
    # empirical coverage check on fresh test points
    covered = 0
    sizes = 0
    N = 2000
    for _ in range(N):
        true = random.randrange(3)
        logits = [random.gauss(0, 1) for _ in range(3)]
        logits[true] += 1.6
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        s = sum(exps)
        probs = [e / s for e in exps]
        out = cc.predict_set(probs)
        sizes += out["set_size"]
        if labels[true] in out["set"]:
            covered += 1
    print("target coverage:", 1 - cc.alpha,
          "empirical coverage:", round(covered / N, 4),
          "avg set size:", round(sizes / N, 3))
    demo = bare_pct_to_set([0.62, 0.30, 0.08], cc._scores, 0.10, labels)
    print("display:", demo["display"])
    print("replaces:", demo["replaces_bare_pct"])
    print("OK")
