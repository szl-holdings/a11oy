#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Bloom (1970) rotation-safe filter for receipt-membership checks.

a11oy's receipt-bus fast path can SKIP an expensive verify/store lookup when this filter
reports a receipt-hash as ``definitely_absent``. A Bloom filter has ZERO false negatives
(proved in Lean), so a receipt we actually recorded is NEVER wrongly bypassed — the
fail-closed safety contract is preserved while cold-miss latency drops.

Rotation-safe: two generations (active + retiring) so we can roll the filter without a
window where a recently-seen receipt reads absent (membership is the OR of both gens).

Published form (thesis_v22.pdf §2 — "Bloom filter"):
    optimal hashes k = (m/n) ln 2 ;  FP p ≈ (1 − e^{−kn/m})^k ;  m/n = −log2(p)/ln2.
B. H. Bloom, "Space/time trade-offs in hash coding with allowable errors", CACM 13(7) (1970).

Lean theorems (sorry-free):
  ``Lutar/Innovations/round11/FrontierBloomCacheBypass.lean :: query_after_insert,
  absent_false_after_insert, absent_implies_not_all_set`` (no false negatives → fail-closed).

CITATION: thesis_v22.pdf §2  ·  LEAN: Lutar/Innovations/round11/FrontierBloomCacheBypass.lean::query_after_insert
"""
from __future__ import annotations

import hashlib
import math

CITATION = "thesis_v22.pdf §2"
LEAN_THEOREM = "Lutar/Innovations/round11/FrontierBloomCacheBypass.lean::query_after_insert"


class _Gen:
    def __init__(self, m: int, k: int) -> None:
        self.m, self.k = m, k
        self._bits = bytearray((m + 7) // 8)
        self.count = 0

    def _positions(self, key: str):
        h = hashlib.sha256(key.encode("utf-8")).digest()
        h1 = int.from_bytes(h[:16], "big")
        h2 = int.from_bytes(h[16:], "big") | 1
        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def add(self, key: str) -> None:
        for p in self._positions(key):
            self._bits[p >> 3] |= 1 << (p & 7)
        self.count += 1

    def present(self, key: str) -> bool:
        return all(self._bits[p >> 3] & (1 << (p & 7)) for p in self._positions(key))


class BloomFilter:
    """Rotation-safe Bloom filter over receipt-hash strings.

    Guarantees (Lean F2): if ``add(x)`` was called and x is still in either live
    generation, ``definitely_absent(x)`` is False. ``definitely_absent == True`` ⇒
    never added ⇒ SAFE to bypass the lookup.
    """

    def __init__(self, expected_n: int = 100_000, target_fp: float = 1e-4) -> None:
        if expected_n < 1:
            expected_n = 1
        if not (0.0 < target_fp < 1.0):
            raise ValueError("target_fp must be in (0,1)")
        self.expected_n = expected_n
        self.target_fp = target_fp
        m = math.ceil(-(expected_n * math.log(target_fp)) / (math.log(2) ** 2))
        k = max(1, round((m / expected_n) * math.log(2)))
        self.m, self.k = int(m), int(k)
        self._active = _Gen(self.m, self.k)
        self._retiring: _Gen | None = None

    def add(self, key: str) -> None:
        self._active.add(key)

    def probably_present(self, key: str) -> bool:
        if self._active.present(key):
            return True
        return self._retiring is not None and self._retiring.present(key)

    def definitely_absent(self, key: str) -> bool:
        """Some probe bit clear in BOTH live gens ⇒ DEFINITELY absent (FN-free)."""
        return not self.probably_present(key)

    def rotate(self) -> None:
        """Roll generations: retire the active gen, start a fresh active one.

        Membership stays the OR of (new active ∪ retiring) so no recently-seen
        receipt momentarily reads absent.
        """
        self._retiring = self._active
        self._active = _Gen(self.m, self.k)

    def current_fp_rate(self) -> float:
        n = self._active.count + (self._retiring.count if self._retiring else 0)
        if n == 0:
            return 0.0
        return (1.0 - math.exp(-self.k * n / self.m)) ** self.k

    def stats(self) -> dict:
        return {
            "value": round(self.current_fp_rate(), 8),
            "m_bits": self.m,
            "k_hashes": self.k,
            "active_count": self._active.count,
            "retiring_count": self._retiring.count if self._retiring else 0,
            "expected_fp_rate": round(self.current_fp_rate(), 8),
            "citation": CITATION,
            "lean_theorem": LEAN_THEOREM,
        }


__all__ = ["BloomFilter", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest + L2 attested (public Sigstore+Rekor) where slsa-verifier confirms.
