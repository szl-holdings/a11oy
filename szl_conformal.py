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
