#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Welford (1962) online mean / variance accumulator — called per request.

O(1)-memory, one-pass, numerically stable running mean & variance. a11oy folds each
request's verdict latency (and any streamed Λ samples) into this accumulator so a cheap
z-score outlier gate can FLAG (never silently change) anomalies.

Published form (thesis_v22.pdf §2, formula table — "Welford"):
    count += 1
    delta  = x - mean
    mean  += delta / count
    M2    += delta * (x - mean)
    var    = M2 / (count - 1)              (Bessel-corrected)

B. P. Welford, "Note on a method for calculating corrected sums of squares and products",
Technometrics 4(3):419–420 (1962).

Lean theorem: ``Lutar/Innovations/round11/FrontierWelfordVariance.lean :: welford_mean_exact``
(sorry-free: the online recurrence equals the exact mean, no accumulated drift).

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/Innovations/round11/FrontierWelfordVariance.lean::welford_mean_exact
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/Innovations/round11/FrontierWelfordVariance.lean::welford_mean_exact"


@dataclass
class Welford:
    """Online mean/variance + z-score gate (Welford 1962)."""

    count: int = 0
    mean: float = 0.0
    _m2: float = field(default=0.0, repr=False)
    z_threshold: float = 3.0

    def update(self, x: float) -> None:
        """Fold one sample in (Welford step)."""
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self._m2 += delta * delta2

    @property
    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return self._m2 / (self.count - 1)

    @property
    def stddev(self) -> float:
        return math.sqrt(self.variance)

    def zscore(self, x: float) -> float:
        sd = self.stddev
        return 0.0 if sd == 0.0 else (x - self.mean) / sd

    def is_anomaly(self, x: float) -> bool:
        if self.count < 2:
            return False
        return abs(self.zscore(x)) > self.z_threshold

    def observe(self, x: float) -> dict:
        """Classify against prior stats THEN fold in. Honest schema."""
        anomaly = self.is_anomaly(x)
        z = self.zscore(x)
        self.update(x)
        return {
            "value": round(self.mean, 6),
            "running_mean": round(self.mean, 6),
            "running_variance": round(self.variance, 6),
            "running_stddev": round(self.stddev, 6),
            "zscore": round(z, 4),
            "anomaly": anomaly,
            "count": self.count,
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }

    def snapshot(self) -> dict:
        return {
            "value": round(self.mean, 6),
            "running_mean": round(self.mean, 6),
            "running_variance": round(self.variance, 6),
            "running_stddev": round(self.stddev, 6),
            "count": self.count,
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }


__all__ = ["Welford", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
