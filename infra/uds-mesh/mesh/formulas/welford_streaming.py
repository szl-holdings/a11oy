#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""welford_streaming.py — online running statistics on the OTLP trace fan-out.

The mesh OTLP broker fans out each cross-organ trace to N organ collectors. The fan-out
latency / span-count per trace is a stream; the broker folds each observation into a
Welford accumulator (O(1) memory, one pass, numerically stable) to maintain a running
mean/variance and a z-score gate that FLAGS (never silently drops) anomalous fan-outs.

Welford recurrence (thesis_v22.pdf §2 "Welford"):
    count += 1; delta = x-mean; mean += delta/count; M2 += delta*(x-mean); var = M2/(count-1)

B. P. Welford, Technometrics 4(3):419–420 (1962).

Lean: ``Lutar/Innovations/round11/FrontierWelfordVariance.lean :: welford_mean_exact``
(L89, sorry-free: the online recurrence equals the exact mean, no accumulated drift).
Permalink pinned at round11 commit f3153a68.

CITATION: thesis_v22.pdf §2  ·  LEAN: FrontierWelfordVariance.lean::welford_mean_exact
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/Innovations/round11/FrontierWelfordVariance.lean::welford_mean_exact"
LEAN_PERMALINK = (
    "https://github.com/szl-holdings/lutar-lean/blob/"
    "f3153a684e7d9b77462d58185bd1eae0aeacd1bc/"
    "Lutar/Innovations/round11/FrontierWelfordVariance.lean#L89")


@dataclass
class StreamingStats:
    """Welford online mean/variance for trace fan-out, with a z-score anomaly gate."""

    count: int = 0
    mean: float = 0.0
    _m2: float = field(default=0.0, repr=False)
    z_threshold: float = 3.0

    def update(self, x: float) -> None:
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        self._m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self._m2 / (self.count - 1) if self.count >= 2 else 0.0

    @property
    def stddev(self) -> float:
        return math.sqrt(self.variance)

    def zscore(self, x: float) -> float:
        sd = self.stddev
        return 0.0 if sd == 0.0 else (x - self.mean) / sd

    def observe(self, x: float) -> dict:
        """Classify against prior stats THEN fold in (honest order)."""
        z = self.zscore(x)
        anomaly = self.count >= 2 and abs(z) > self.z_threshold
        self.update(x)
        return {
            "value": round(self.mean, 6),
            "running_mean": round(self.mean, 6),
            "running_variance": round(self.variance, 6),
            "running_stddev": round(self.stddev, 6),
            "zscore": round(z, 4),
            "anomaly": bool(anomaly),
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


__all__ = ["StreamingStats", "CITATION", "LEAN_THEOREM", "LEAN_PERMALINK"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
