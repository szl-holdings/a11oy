# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 unchanged · Λ remains Conjecture 1
# Lives in Lutar/Innovations/round4/ namespace — OUTSIDE locked kernel.
#
# szl_ancient_r4_crt.py — CRT Receipt Shard instillation for amaru (Khipu DAG)
#
# Source citations (primary academic):
#   CRT-RECEIPT-SHARD:
#     Needham, Science and Civilisation in China Vol. 3 (Cambridge UP, 1959) — Sunzi
#     Sunzi Suanjing (Sun Tzu's Mathematical Manual), ~3rd-5th century CE
#     Lean stub: https://github.com/szl-holdings/lutar-lean/blob/feat/innovations-round4/Lutar/Innovations/round4/CRTReceiptShard.lean
#     Lake receipt: https://github.com/szl-holdings/szl-lake/blob/main/attestations/innovations/round4/crt-receipt-shard.json
#
#   COPPER-SCROLL-DAG-HEIGHT (bonus — same plug-in target):
#     Milik & Cross, Les Grottes de Murabba'ât (1961) — Copper Scroll 3Q15
#     Lean stub: https://github.com/szl-holdings/lutar-lean/blob/feat/innovations-round4/Lutar/Innovations/round4/CopperScrollDAGHeight.lean
#     Lake receipt: https://github.com/szl-holdings/szl-lake/blob/main/attestations/innovations/round4/copper-scroll-dag-height.json
#
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

"""
Ancient Decode Round 4 — CRT Receipt Shard + Copper Scroll DAG Height
instillation for amaru (Khipu DAG memory).

F-09: CRT-RECEIPT-SHARD
  Given receipt ID r and pairwise coprime shards (m1, m2, m3), the triple
  (r % m1, r % m2, r % m3) uniquely reconstructs r mod (m1*m2*m3).
  Lean: crt_unique_reconstruction (closes by omega + Nat.chineseRemainder)
  Lean: sunzi_original_problem (closes by decide — 23%3=2, 23%5=3, 23%7=2)

F-05: COPPER-SCROLL-DAG-HEIGHT (bonus instillation)
  appendOnlyInvariant: height(e) = height(prev(e)) + 1
  Lean: copper_scroll_height_monotone (closes by omega)
"""

from math import gcd
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# F-09: CRT-RECEIPT-SHARD
# ---------------------------------------------------------------------------

# Default coprime shard moduli (pairwise coprime: gcd(7,11)=1, gcd(7,13)=1, gcd(11,13)=1)
DEFAULT_SHARDS = (7, 11, 13)
assert gcd(7, 11) == 1 and gcd(7, 13) == 1 and gcd(11, 13) == 1, "Shards must be pairwise coprime"
assert 7 * 11 * 13 == 1001, "CRT modulus = 1001"

# Sunzi's original problem: x ≡ 2 (mod 3), x ≡ 3 (mod 5), x ≡ 2 (mod 7) → x = 23
# Lean: sunzi_original_problem : 23 % 3 = 2 ∧ 23 % 5 = 3 ∧ 23 % 7 = 2
assert 23 % 3 == 2 and 23 % 5 == 3 and 23 % 7 == 2, "Lean: sunzi_original_problem"


def _ext_gcd(a: int, b: int) -> Tuple[int, int, int]:
    """Extended Euclidean algorithm: returns (gcd, s, t) with a*s + b*t = gcd."""
    if b == 0:
        return a, 1, 0
    g, s, t = _ext_gcd(b, a % b)
    return g, t, s - (a // b) * t


def crt_shard_split(receipt_id: int,
                    moduli: Tuple[int, ...] = DEFAULT_SHARDS) -> Tuple[int, ...]:
    """
    Split receipt_id into CRT shards.
    Each shard: receipt_id % moduli[i].
    Lean: crt_shard_bounds — shard_i < moduli[i] (by Nat.mod_lt).
    """
    shards = tuple(receipt_id % m for m in moduli)
    # Verify bounds (Lean: crt_shard_bounds)
    for i, (s, m) in enumerate(zip(shards, moduli)):
        assert 0 <= s < m, f"Shard {i}: {s} not in [0, {m})"
    return shards


def crt_shard_reconstruct(shards: Tuple[int, ...],
                           moduli: Tuple[int, ...] = DEFAULT_SHARDS) -> int:
    """
    Reconstruct receipt_id mod (product of moduli) from CRT shards.
    Uses the constructive CRT formula: x = Σ a_i * M_i * y_i (mod N)
    where N = Π m_i, M_i = N / m_i, y_i = M_i^{-1} mod m_i.
    Lean: crt_unique_reconstruction — agreement on each shard implies agreement mod product.
    """
    N = 1
    for m in moduli:
        N *= m

    result = 0
    for a_i, m_i in zip(shards, moduli):
        M_i = N // m_i
        _, y_i, _ = _ext_gcd(M_i, m_i)
        result += a_i * M_i * y_i

    return result % N


def crt_verify_round_trip(receipt_id: int,
                           moduli: Tuple[int, ...] = DEFAULT_SHARDS) -> bool:
    """
    Verify CRT round-trip: split then reconstruct recovers receipt_id mod N.
    This is the operational check of the Lean theorem.
    """
    shards = crt_shard_split(receipt_id, moduli)
    recovered = crt_shard_reconstruct(shards, moduli)
    N = 1
    for m in moduli:
        N *= m
    return recovered == receipt_id % N


# ---------------------------------------------------------------------------
# F-05: COPPER-SCROLL-DAG-HEIGHT (bonus — same plug-in target: amaru Khipu DAG)
# ---------------------------------------------------------------------------

def khipu_dag_height_invariant(height: int, prev_height: Optional[int]) -> bool:
    """
    Verify the Copper Scroll append-only invariant:
      if prev is None: height == 0  (genesis)
      if prev is Some(h): height == h + 1
    Lean: copper_scroll_height_monotone (closes by omega)
    Source: Copper Scroll 3Q15, ~50 CE; Milik & Cross (1961)
    """
    if prev_height is None:
        return height == 0
    return height == prev_height + 1


def khipu_append_entry(chain: List[dict], payload: dict) -> dict:
    """
    Append an entry to the Khipu DAG, enforcing the Copper Scroll height invariant.
    New entry: height = prev.height + 1 (or 0 if genesis).
    Lean: copper_scroll_height_monotone — prev_height < height
    """
    if not chain:
        prev_height = None
        new_height = 0
    else:
        prev_height = chain[-1]["height"]
        new_height = prev_height + 1

    assert khipu_dag_height_invariant(new_height, prev_height), \
        "Copper Scroll DAG height invariant violated"

    entry = {
        "height": new_height,
        "prev_height": prev_height,
        "payload": payload,
        "lean_ref": "Lutar/Innovations/round4/CopperScrollDAGHeight.lean",
        "doctrine": "v11 LOCKED 749/14/163",
    }
    chain.append(entry)
    return entry


# ---------------------------------------------------------------------------
# Combined amaru Khipu API with CRT receipt fingerprinting
# ---------------------------------------------------------------------------

def amaru_receipt_shard_fingerprint(receipt_id: int,
                                     chain_height: int,
                                     moduli: Tuple[int, ...] = DEFAULT_SHARDS) -> dict:
    """
    Create a CRT-sharded fingerprint for a Khipu DAG receipt.
    Combines:
      - CRT shards for multi-validator reconstruction (F-09)
      - Chain height for append-only audit (F-05)

    Doctrine: v11 LOCKED 749/14/163 · Λ = Conjecture 1
    Lean stubs: CRTReceiptShard.lean, CopperScrollDAGHeight.lean (round4)
    """
    shards = crt_shard_split(receipt_id, moduli)
    N = 1
    for m in moduli:
        N *= m

    return {
        "receipt_id": receipt_id,
        "receipt_id_mod_N": receipt_id % N,
        "crt_shards": dict(zip([f"m{m}" for m in moduli], shards)),
        "crt_modulus": N,
        "chain_height": chain_height,
        "verify_round_trip": crt_verify_round_trip(receipt_id, moduli),
        "lean_refs": [
            "Lutar/Innovations/round4/CRTReceiptShard.lean",
            "Lutar/Innovations/round4/CopperScrollDAGHeight.lean",
        ],
        "doctrine": "v11 LOCKED 749/14/163",
        "lambda": "Conjecture 1 — NOT theorem",
        "academic_sources": [
            "Needham, Science and Civilisation in China Vol. 3 (Cambridge UP, 1959)",
            "Milik & Cross, Les Grottes de Murabba'ât (1961)",
        ],
    }
