#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. -- SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# welford_gate.py -- SENTRA immune organ: O(1)-memory online latency anomaly gate.
#
# Frontier formula F1 (round11): Welford's online mean/variance.
#   B. P. Welford, "Note on a method for calculating corrected sums of squares and
#   products", Technometrics 4(3):419-420 (1962).
#   https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
#
# Lean proof of the underlying invariant (online mean == exact mean, no accumulated
# drift): szl-holdings/lutar-lean
#   Lutar/Innovations/round11/FrontierWelfordVariance.lean :: welford_mean_exact
#
# Why this helps the running software:
#   sentra must watch /verdict latency for drift. The naive estimator
#   var = (SumSq - Sum^2/n)/(n-1) suffers catastrophic cancellation on large-magnitude
#   latency streams (can yield NEGATIVE variance). Welford's recurrence is one-pass,
#   O(1) memory, numerically stable. This gives the immune server a cheap, correct
#   z-score gate to FLAG (never silently change) latency outliers.
#
# HONESTY: this module ADDS an observation/`anomaly` annotation. It does NOT change any
# allow/deny verdict. Default behaviour is unchanged unless explicitly read.

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class WelfordGate:
    """Online mean/variance + z-score outlier gate (Welford 1962).

    Maintains count, mean, and M2 (sum of squared deviations) in O(1) memory.
    `z(x)` is the number of standard deviations `x` sits from the running mean.
    """

    count: int = 0
    mean: float = 0.0
    _m2: float = field(default=0.0, repr=False)
    # z-score threshold above which a sample is flagged anomalous (3-sigma default).
    z_threshold: float = 3.0

    def update(self, x: float) -> None:
        """Fold one latency sample into the running statistics (Welford step).

        Mirrors the Lean `step`/`fold`: count += 1; mean += (x - mean)/count;
        M2 += (x - mean_prev)*(x - mean_new).
        """
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self._m2 += delta * delta2

    @property
    def variance(self) -> float:
        """Sample variance (Bessel-corrected). 0.0 until >= 2 samples seen."""
        if self.count < 2:
            return 0.0
        return self._m2 / (self.count - 1)

    @property
    def stddev(self) -> float:
        return math.sqrt(self.variance)

    def zscore(self, x: float) -> float:
        """Signed z-score of `x` against the running mean. 0.0 if no spread yet."""
        sd = self.stddev
        if sd == 0.0:
            return 0.0
        return (x - self.mean) / sd

    def is_anomaly(self, x: float) -> bool:
        """True iff `x` is beyond `z_threshold` sigma. Needs >= 2 prior samples."""
        if self.count < 2:
            return False
        return abs(self.zscore(x)) > self.z_threshold

    def observe(self, x: float) -> dict:
        """Convenience: classify a sample THEN fold it in. Returns an annotation dict.

        Note: classification uses statistics from PRIOR samples (the sample being
        observed is not yet in the window), so a spike is flagged before it skews
        the baseline.
        """
        anomaly = self.is_anomaly(x)
        z = self.zscore(x)
        self.update(x)
        return {
            "sample": x,
            "anomaly": anomaly,
            "zscore": round(z, 4),
            "running_mean": round(self.mean, 6),
            "running_stddev": round(self.stddev, 6),
            "count": self.count,
            "formula": "welford-online-variance",
            "lean_ref": "Lutar/Innovations/round11/FrontierWelfordVariance.lean",
        }


__all__ = ["WelfordGate"]
