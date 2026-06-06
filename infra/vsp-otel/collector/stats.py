"""
collector/stats.py — online statistics for the vsp-otel collector.

  * Welford   — online mean/variance of span latency. Models the sorry-free Lean
                theorem Lutar.Round11.Welford.welford_mean_exact / weightedMean_increment
                (lutar-lean open PR #180). Runtime coordinate:
                szl-holdings/sentra/runtime/welford_gate.py.
  * HyperLogLog — unique-trace cardinality estimation (Flajolet et al. 2007),
                constant-memory distinct-count over trace ids.

Pure stdlib; no deps.

SPDX-License-Identifier: Apache-2.0
Author: Yachay (CTO authority) · Built by Perplexity Computer Agent · SZL Holdings
Doctrine v11 LOCKED — 749 / 14 / 163.
"""
from __future__ import annotations

import hashlib
import math


class Welford:
    """Welford's online algorithm for streaming mean + sample variance.

    welford_mean_exact: the online mean after n updates equals total/n exactly.
    weightedMean_increment: each update is O(1) and exact in the rationals.
    """

    __slots__ = ("n", "mean", "_m2")

    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self._m2 = 0.0

    def update(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n          # weightedMean_increment
        self._m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self._m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def stddev(self) -> float:
        return math.sqrt(self.variance)

    def snapshot(self) -> dict:
        return {"count": self.n, "mean": round(self.mean, 4),
                "variance": round(self.variance, 4), "stddev": round(self.stddev, 4)}


class HyperLogLog:
    """HyperLogLog distinct-count estimator (Flajolet, Fusy, Gandouet, Meunier 2007).

    p register bits -> m = 2^p registers. Standard-error ≈ 1.04/sqrt(m).
    p=14 -> 16384 registers, ~0.81% error, ~16 KiB. Used for unique-trace cardinality.
    """

    __slots__ = ("p", "m", "alpha", "reg")

    def __init__(self, p: int = 14) -> None:
        if not (4 <= p <= 18):
            raise ValueError("p must be in [4, 18]")
        self.p = p
        self.m = 1 << p
        self.alpha = self._alpha(self.m)
        self.reg = bytearray(self.m)

    @staticmethod
    def _alpha(m: int) -> float:
        if m == 16:
            return 0.673
        if m == 32:
            return 0.697
        if m == 64:
            return 0.709
        return 0.7213 / (1 + 1.079 / m)

    def add(self, item: str) -> None:
        h = int.from_bytes(hashlib.sha1(item.encode()).digest()[:8], "big")
        idx = h & (self.m - 1)
        w = h >> self.p
        rank = self._rho(w, 64 - self.p)
        if rank > self.reg[idx]:
            self.reg[idx] = rank

    @staticmethod
    def _rho(w: int, maxbits: int) -> int:
        # position of leftmost 1-bit (1-indexed); maxbits if w == 0.
        if w == 0:
            return maxbits + 1
        rank = 1
        while (w & 1) == 0 and rank <= maxbits:
            rank += 1
            w >>= 1
        return rank

    def count(self) -> int:
        z = sum(2.0 ** -r for r in self.reg)
        est = self.alpha * self.m * self.m / z
        # small-range correction (linear counting)
        if est <= 2.5 * self.m:
            zeros = self.reg.count(0)
            if zeros:
                est = self.m * math.log(self.m / zeros)
        return int(est)
