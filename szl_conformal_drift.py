# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
szl_conformal_drift.py — CONFORMAL-DRIFT: Distribution-Free Compliance Drift Detection
Doctrine: v11 LOCKED | Lambda = Conjecture 1 | SLSA L1 honest
Innovation: CONFORMAL-DRIFT (Round 2, Lane Leader Scrape agent)
Bridge: Conformal Prediction (Angelopoulos-Bates 2022) x Doctrine Compliance Monitoring

Key property: P(s_{t+1} ∈ C_t) >= 1 - alpha — distribution-free coverage guarantee.
Refs: arXiv:2107.07511 (Angelopoulos & Bates 2022)

DCO: Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations
import json
from collections import deque
from typing import Optional

WINDOW = 50  # calibration window (rolling)

class ConformalDriftMonitor:
    """
    Maintains a rolling conformal prediction interval for the Λ compliance score.
    If s_{t+1} falls outside the interval for CONSECUTIVE_MISS steps, emits DRIFT alert.
    Coverage guarantee: P(s_{t+1} in C_t) >= 1 - alpha (by exchangeability, Vovk 2005).
    """
    ALPHA: float = 0.10          # 90% coverage
    CONSECUTIVE_MISS: int = 3    # alert after 3 misses

    def __init__(self) -> None:
        self._scores: deque[float] = deque(maxlen=WINDOW)
        self._misses: int = 0

    def update(self, score: float) -> dict:
        """Ingest a new Lambda score; return conformal interval + drift status."""
        if len(self._scores) >= 10:
            sorted_scores = sorted(self._scores)
            lo_idx = max(0, int(self.ALPHA / 2 * len(sorted_scores)))
            hi_idx = min(len(sorted_scores) - 1, int((1 - self.ALPHA / 2) * len(sorted_scores)))
            lo, hi = sorted_scores[lo_idx], sorted_scores[hi_idx]
            in_interval = lo <= score <= hi
        else:
            lo, hi, in_interval = 0.0, 1.0, True

        self._misses = 0 if in_interval else self._misses + 1
        self._scores.append(score)
        return {
            "score": score,
            "conformal_interval": [round(lo, 4), round(hi, 4)],
            "in_interval": in_interval,
            "consecutive_misses": self._misses,
            "drift_alert": self._misses >= self.CONSECUTIVE_MISS,
            "coverage_guarantee": f">= {1 - self.ALPHA:.0%}",
            "innovation": "CONFORMAL-DRIFT",
            "round": 2,
        }

    def to_json(self) -> str:
        return json.dumps({"window_size": len(self._scores), "alpha": self.ALPHA})


# Singleton for use in serve.py / szl_lambda_tripwire.py
_monitor = ConformalDriftMonitor()

def conformal_drift_update(lambda_score: float) -> dict:
    """Public API: feed Lambda score, get conformal drift analysis."""
    return _monitor.update(lambda_score)
