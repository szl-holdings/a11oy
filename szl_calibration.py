# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_calibration.py — LIVE calibration tracking: ECE + Brier per model / agent-type
(Lane B / Dev B), plus the automated-response gate.

Why
---
Overconfident predictions from a self-hosted model are indistinguishable from
well-calibrated ones WITHOUT measurement. This module tracks, per (model,
agent_type), a rolling window of (predicted_confidence, was_correct, full
distribution) and computes:

  * Expected Calibration Error (ECE), equal-width binning:
        ECE = Σ_b (|B_b| / N) · | acc(B_b) − conf(B_b) |
  * Brier Score (multiclass, strictly-proper):
        BS = (1/N) Σ_i Σ_k (p_ik − y_ik)^2

Source formulas: ECE/Brier arXiv:2605.21566 (and arXiv:2505.15437). Pure-Python,
no numpy — ships byte-identical into both images.

The GATE
--------
Doctrine: an automated killinchu response is only permitted when the model that
produced it is well calibrated. We expose:

    automated_response_gate(model, agent_type) ->
        {allow: bool, ece: float|None, threshold: 0.05, reason: str, ...}

Threshold ECE < 0.05 (coordinate the exact value with Dev D via
RESULT_DEVB_AGENTIC.md; tunable via env A11OY_ECE_GATE_THRESHOLD). When ECE is
not yet measured (too few samples) the gate FAILS CLOSED (allow=False,
reason="not_measured") — we never auto-respond on an unmeasured calibration.

Honesty: every number is computed from logged outcomes; with <MIN_SAMPLES points
ECE/Brier are reported as None ("not yet measured"), never zero-filled.

DCO: Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import os
import threading
from collections import deque
from typing import Any, Optional, Sequence

DEFAULT_ECE_GATE = 0.05      # ECE strictly below this required for auto-response
MIN_SAMPLES = 20             # below this, calibration is "not_measured"
DEFAULT_BINS = 10
WINDOW = 500                 # rolling window per (model, agent_type)


def _gate_threshold() -> float:
    try:
        return float(os.environ.get("A11OY_ECE_GATE_THRESHOLD", str(DEFAULT_ECE_GATE)))
    except (TypeError, ValueError):
        return DEFAULT_ECE_GATE


def expected_calibration_error(confidences: Sequence[float],
                               correct: Sequence[bool],
                               n_bins: int = DEFAULT_BINS) -> Optional[float]:
    """Equal-width-bin ECE over predicted confidences and correctness flags.
    Returns None if there are no samples. Never raises."""
    conf = [min(1.0, max(0.0, float(c))) for c in confidences]
    cor = [1.0 if bool(b) else 0.0 for b in correct]
    n = min(len(conf), len(cor))
    if n == 0:
        return None
    conf, cor = conf[:n], cor[:n]
    bins = max(1, int(n_bins))
    ece = 0.0
    for b in range(bins):
        lo = b / bins
        hi = (b + 1) / bins
        # last bin is inclusive of 1.0
        idx = [i for i in range(n)
               if (conf[i] > lo or (b == 0 and conf[i] >= lo))
               and (conf[i] <= hi or (b == bins - 1 and conf[i] <= 1.0))]
        if not idx:
            continue
        acc = sum(cor[i] for i in idx) / len(idx)
        avg_conf = sum(conf[i] for i in idx) / len(idx)
        ece += (len(idx) / n) * abs(acc - avg_conf)
    return round(ece, 6)


def brier_score(prob_vectors: Sequence[Sequence[float]],
                true_indices: Sequence[int]) -> Optional[float]:
    """Multiclass Brier score. prob_vectors[i] is the full distribution for
    sample i; true_indices[i] is the index of the true class. None if empty."""
    n = min(len(prob_vectors), len(true_indices))
    if n == 0:
        return None
    total = 0.0
    for i in range(n):
        p = [max(0.0, min(1.0, float(v))) for v in prob_vectors[i]]
        s = sum(p)
        if s > 0:
            p = [v / s for v in p]
        ti = int(true_indices[i])
        acc = 0.0
        for k in range(len(p)):
            y = 1.0 if k == ti else 0.0
            acc += (p[k] - y) ** 2
        total += acc
    return round(total / n, 6)


def brier_binary(confidences: Sequence[float], correct: Sequence[bool]) -> Optional[float]:
    """Binary Brier from a top-class confidence + correctness flag:
       BS = mean( (conf − correct)^2 ). None if empty."""
    conf = [min(1.0, max(0.0, float(c))) for c in confidences]
    cor = [1.0 if bool(b) else 0.0 for b in correct]
    n = min(len(conf), len(cor))
    if n == 0:
        return None
    return round(sum((conf[i] - cor[i]) ** 2 for i in range(n)) / n, 6)


def reliability_bins(confidences: Sequence[float], correct: Sequence[bool],
                     n_bins: int = DEFAULT_BINS) -> list[dict]:
    """Reliability-diagram data: per equal-width bin, return count, mean
    confidence, and accuracy. Drives the dashboard's calibration curve."""
    conf = [min(1.0, max(0.0, float(c))) for c in confidences]
    cor = [1.0 if bool(b) else 0.0 for b in correct]
    n = min(len(conf), len(cor))
    bins = max(1, int(n_bins))
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i in range(n)
               if (conf[i] > lo or (b == 0 and conf[i] >= lo))
               and (conf[i] <= hi or (b == bins - 1 and conf[i] <= 1.0))]
        out.append({
            "bin": b, "lo": round(lo, 3), "hi": round(hi, 3),
            "count": len(idx),
            "mean_conf": round(sum(conf[i] for i in idx) / len(idx), 6) if idx else None,
            "accuracy": round(sum(cor[i] for i in idx) / len(idx), 6) if idx else None,
        })
    return out


class CalibrationTracker:
    """Thread-safe rolling calibration tracker keyed by (model, agent_type).
    Log each prediction whose ground truth is later known; query ECE/Brier and
    the automated-response gate live."""

    def __init__(self, window: int = WINDOW, n_bins: int = DEFAULT_BINS) -> None:
        self.window = int(window) if window and window > 0 else WINDOW
        self.n_bins = int(n_bins) if n_bins and n_bins > 0 else DEFAULT_BINS
        self._lock = threading.Lock()
        # key -> deque of {conf, correct, probs, true_idx}
        self._store: dict[tuple, deque] = {}

    @staticmethod
    def _key(model: str, agent_type: str) -> tuple:
        return (str(model or "unknown"), str(agent_type or "default"))

    def log(self, model: str, agent_type: str, confidence: float, correct: bool,
            probs: Optional[Sequence[float]] = None,
            true_index: Optional[int] = None) -> None:
        k = self._key(model, agent_type)
        rec = {"conf": float(confidence), "correct": bool(correct),
               "probs": list(probs) if probs is not None else None,
               "true_idx": (int(true_index) if true_index is not None else None)}
        with self._lock:
            dq = self._store.get(k)
            if dq is None:
                dq = deque(maxlen=self.window)
                self._store[k] = dq
            dq.append(rec)

    def metrics(self, model: str, agent_type: str) -> dict:
        k = self._key(model, agent_type)
        with self._lock:
            recs = list(self._store.get(k, []))
        n = len(recs)
        threshold = _gate_threshold()
        if n < MIN_SAMPLES:
            return {"model": k[0], "agent_type": k[1], "n": n,
                    "status": "not_measured", "ece": None, "brier": None,
                    "ece_gate_threshold": threshold,
                    "min_samples": MIN_SAMPLES,
                    "honesty": ("Calibration not yet measured for this "
                                "(model, agent-type): %d/%d samples. ECE/Brier "
                                "reported as null, never zero-filled." % (n, MIN_SAMPLES))}
        conf = [r["conf"] for r in recs]
        cor = [r["correct"] for r in recs]
        ece = expected_calibration_error(conf, cor, self.n_bins)
        # multiclass Brier when full distributions are present; else binary
        pv = [r["probs"] for r in recs if r["probs"] is not None and r["true_idx"] is not None]
        ti = [r["true_idx"] for r in recs if r["probs"] is not None and r["true_idx"] is not None]
        if len(pv) >= MIN_SAMPLES:
            brier = brier_score(pv, ti)
            brier_kind = "multiclass"
        else:
            brier = brier_binary(conf, cor)
            brier_kind = "binary(top-class)"
        return {
            "model": k[0], "agent_type": k[1], "n": n,
            "status": "measured",
            "ece": ece, "brier": brier, "brier_kind": brier_kind,
            "accuracy": round(sum(1 for c in cor if c) / n, 6),
            "mean_confidence": round(sum(conf) / n, 6),
            "ece_gate_threshold": threshold,
            "reliability": reliability_bins(conf, cor, self.n_bins),
            "honesty": ("LIVE ECE (equal-width %d-bin) + Brier over the last %d "
                        "verified predictions. ECE/Brier per arXiv:2605.21566. "
                        "Lower is better; ECE<%.2f gates automated responses."
                        % (self.n_bins, n, threshold)),
        }

    def automated_response_gate(self, model: str, agent_type: str) -> dict:
        """The doctrine gate: allow an automated (no-human) response ONLY when
        the (model, agent-type) is measured AND ECE < threshold. Fails CLOSED on
        unmeasured calibration. Coordinate threshold with Dev D."""
        m = self.metrics(model, agent_type)
        threshold = _gate_threshold()
        if m["status"] != "measured" or m.get("ece") is None:
            return {"allow": False, "model": m["model"], "agent_type": m["agent_type"],
                    "ece": None, "threshold": threshold, "n": m["n"],
                    "reason": "not_measured",
                    "honesty": ("Gate FAILS CLOSED: calibration not yet measured "
                                "(%d/%d samples). No automated response permitted "
                                "until ECE is measured below %.2f." % (m["n"], MIN_SAMPLES, threshold))}
        allow = m["ece"] < threshold
        return {"allow": bool(allow), "model": m["model"], "agent_type": m["agent_type"],
                "ece": m["ece"], "threshold": threshold, "n": m["n"],
                "reason": ("ece_below_threshold" if allow else "ece_above_threshold"),
                "honesty": ("Automated-response gate: ECE=%.4f %s threshold %.2f -> %s. "
                            "When the gate denies, the response must route to a human "
                            "(human-on-loop)." % (m["ece"], "<" if allow else ">=",
                                                  threshold, "ALLOW" if allow else "DENY"))}

    def summary(self) -> dict:
        with self._lock:
            keys = list(self._store.keys())
        rows = [self.metrics(k[0], k[1]) for k in keys]
        measured = [r for r in rows if r["status"] == "measured"]
        return {
            "tracked": len(keys),
            "measured": len(measured),
            "not_measured": len(keys) - len(measured),
            "ece_gate_threshold": _gate_threshold(),
            "rows": rows,
            "honesty": ("Per (model, agent-type) live calibration. A row shows "
                        "'not_measured' until it has >=%d verified predictions; "
                        "we never zero-fill an unmeasured ECE." % MIN_SAMPLES),
        }


if __name__ == "__main__":  # pragma: no cover
    import random
    random.seed(11)
    t = CalibrationTracker()
    # well-calibrated model: confidence ~ P(correct)
    for _ in range(400):
        c = random.uniform(0.5, 0.99)
        correct = random.random() < c
        t.log("qwen2.5-coder-32b", "threat-classify", c, correct)
    # overconfident model: always claims 0.95 but only 0.7 correct
    for _ in range(400):
        correct = random.random() < 0.70
        t.log("overconfident-stub", "threat-classify", 0.95, correct)
    mm = t.metrics("qwen2.5-coder-32b", "threat-classify")
    print("calibrated  ECE=%.4f Brier=%.4f acc=%.3f -> gate %s"
          % (mm["ece"], mm["brier"], mm["accuracy"],
             t.automated_response_gate("qwen2.5-coder-32b", "threat-classify")["allow"]))
    oo = t.metrics("overconfident-stub", "threat-classify")
    print("overconfident ECE=%.4f Brier=%.4f acc=%.3f -> gate %s"
          % (oo["ece"], oo["brier"], oo["accuracy"],
             t.automated_response_gate("overconfident-stub", "threat-classify")["allow"]))
    print("unmeasured gate:", t.automated_response_gate("brand-new", "x")["reason"])
    print("OK")
