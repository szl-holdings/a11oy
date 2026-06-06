#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. -- SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# receipt_bloom.py -- SENTRA receipt-bus: false-negative-free Bloom filter for the
# cache-bypass fast path.
#
# Frontier formula F2 (round11): Bloom filter membership + optimal sizing.
#   B. H. Bloom, "Space/time trade-offs in hash coding with allowable errors",
#   CACM 13(7):422-426 (1970). https://en.wikipedia.org/wiki/Bloom_filter
#   Optimal hashes k = (m/n) ln 2 ; FP p ~ (1 - e^{-kn/m})^k ; m/n = -log2(p)/ln2.
#
# Lean proof of the SAFETY invariant (no false negatives -> fail-closed safe):
#   szl-holdings/lutar-lean
#   Lutar/Innovations/round11/FrontierBloomCacheBypass.lean :: query_after_insert,
#   absent_false_after_insert, absent_implies_not_all_set
#
# Why this helps the running software:
#   The receipt-bus hot path can SKIP an expensive verify/store lookup when this filter
#   reports a receipt-hash as `definitely_absent`. Because a Bloom filter has ZERO false
#   negatives (proved in Lean), a receipt we have actually recorded is NEVER wrongly
#   bypassed -- so the fail-closed safety contract is preserved while cold-miss latency
#   drops (no round-trip for keys we provably never inserted).
#
# Stdlib only (hashlib) -- zero install, matches immune_server.py's no-dep posture.

from __future__ import annotations

import hashlib
import math


class ReceiptBloom:
    """Bloom filter over receipt-hash strings, sized from (expected_n, target_fp).

    Guarantees (see Lean F2):
      * NO false negatives: if `add(x)` was called, `definitely_absent(x)` is False.
      * `definitely_absent(x) == True`  ==>  x was never added  ==> safe to bypass.
    """

    def __init__(self, expected_n: int = 100_000, target_fp: float = 1e-4) -> None:
        if expected_n < 1:
            expected_n = 1
        if not (0.0 < target_fp < 1.0):
            raise ValueError("target_fp must be in (0,1)")
        self.expected_n = expected_n
        self.target_fp = target_fp
        # m = -n ln p / (ln 2)^2 ; k = (m/n) ln 2  (textbook optimal sizing).
        m = math.ceil(-(expected_n * math.log(target_fp)) / (math.log(2) ** 2))
        k = max(1, round((m / expected_n) * math.log(2)))
        self.m = int(m)
        self.k = int(k)
        self._bits = bytearray((self.m + 7) // 8)
        self._count = 0

    # --- bit helpers -------------------------------------------------------
    def _positions(self, key: str):
        """k probe positions via double hashing (Kirsch-Mitzenmacher)."""
        h = hashlib.sha256(key.encode("utf-8")).digest()
        h1 = int.from_bytes(h[:16], "big")
        h2 = int.from_bytes(h[16:], "big") | 1  # ensure odd so steps cover the array
        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def _get(self, pos: int) -> bool:
        return bool(self._bits[pos >> 3] & (1 << (pos & 7)))

    def _set(self, pos: int) -> None:
        self._bits[pos >> 3] |= (1 << (pos & 7))

    # --- public API --------------------------------------------------------
    def add(self, key: str) -> None:
        """Record a receipt-hash (set all probe bits). Mirrors Lean `insert`."""
        for p in self._positions(key):
            self._set(p)
        self._count += 1

    def probably_present(self, key: str) -> bool:
        """All probe bits set => 'probably present' (could be a false positive)."""
        return all(self._get(p) for p in self._positions(key))

    def definitely_absent(self, key: str) -> bool:
        """Some probe bit clear => DEFINITELY absent. SAFE to bypass the lookup.

        False-negative-free by construction (Lean: query_after_insert).
        """
        return not self.probably_present(key)

    def current_fp_rate(self) -> float:
        """Empirical FP rate estimate at the current fill: (1 - e^{-k n / m})^k."""
        if self._count == 0:
            return 0.0
        return (1.0 - math.exp(-self.k * self._count / self.m)) ** self.k

    @staticmethod
    def bits_per_element(target_fp: float) -> float:
        """m/n needed for a target FP rate: -log2(p)/ln2 (~1.44 * -log2 p)."""
        return -math.log2(target_fp) / math.log(2)

    def stats(self) -> dict:
        return {
            "m_bits": self.m,
            "k_hashes": self.k,
            "count": self._count,
            "expected_fp_rate": round(self.current_fp_rate(), 8),
            "formula": "bloom-filter-cache-bypass",
            "lean_ref": "Lutar/Innovations/round11/FrontierBloomCacheBypass.lean",
        }


__all__ = ["ReceiptBloom"]
