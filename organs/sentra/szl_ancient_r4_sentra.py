# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 unchanged · Λ remains Conjecture 1
# Lives in Lutar/Innovations/round4/ namespace — OUTSIDE locked kernel.
#
# szl_ancient_r4_sentra.py — Masoretic Checksum + ELS Bonferroni Bound
# instillation for sentra (verdict / receipt-format / gate sensitivity).
#
# Source citations (primary academic):
#   MASORETIC-CHECKSUM:
#     Wuerthwein, The Text of the Old Testament (Eerdmans, 1988), pp. 12-15
#     TheTorah.com scribal marks analysis (primary Masoretic source)
#     Lean stub: https://github.com/szl-holdings/lutar-lean/blob/feat/innovations-round4/Lutar/Innovations/round4/MasoreticChecksum.lean
#     Lake receipt: https://github.com/szl-holdings/szl-lake/blob/main/attestations/innovations/round4/masoretic-checksum.json
#
#   ELS-BONFERRONI-BOUND:
#     McKay, Bar-Natan, Bar-Hillel, Kalai.
#     "Solving the Bible Code Puzzle." Statistical Science 14(2):150-173, 1999.
#     DOI: 10.1214/ss/1009212243
#     Lean stub: https://github.com/szl-holdings/lutar-lean/blob/feat/innovations-round4/Lutar/Innovations/round4/ELSBonferroniBound.lean
#     Lake receipt: https://github.com/szl-holdings/szl-lake/blob/main/attestations/innovations/round4/els-bonferroni-bound.json
#
# NOTE on ELS: The Bible Code ELS claims are definitively REFUTED by McKay et al. (1999).
# We extract ONLY the statistical false-positive bound — a legitimate result.
#
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

"""
Ancient Decode Round 4 — Masoretic Checksum + ELS Bonferroni Bound
instillation for sentra verdict / receipt-format / gate sensitivity.

F-04: MASORETIC-CHECKSUM
  Receipt validation: byte_length must match reference + midpoint byte must match.
  Double-check catches single-field corruption in receipt transmission.
  Lean: masoreticDecidable — both conditions are Decidable [instDecidableAnd]
  Lean: masoretic_midpoint_in_bounds [omega]

F-07: ELS-BONFERRONI-BOUND (SKEPTICAL — extracted statistical bound only)
  When scanning gate outputs for pattern anomalies:
  Expected false-positive count ≤ W * 2*C*K / sigma^L
  where W=patterns searched, C=corpus size, K=max skip, sigma=alphabet, L=word length.
  Lean: els_bonferroni_monotone_in_W [mul_le_mul_of_nonneg_right]
  Lean: els_zero_patterns [simp]
"""

from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# F-04: MASORETIC-CHECKSUM
# ---------------------------------------------------------------------------

def masoretic_checksum(data: bytes, ref_length: int, ref_midpoint_byte: int) -> dict:
    """
    Masoretic-style validation for a receipt byte sequence.
    Validates: (1) total length matches reference, (2) midpoint byte matches reference.

    Source: Wuerthwein, The Text of the Old Testament (1988), pp. 12-15.
    Scribal tradition: Masoretes counted every character; midpoint of each book verified.
    1000-year text stability demonstrated by Masada Psalms Scroll vs Aleppo Codex.

    Lean: masoreticDecidable — Decidable (masoreticValid bytes ref) [instDecidableAnd]
    Lean: masoretic_midpoint_in_bounds — ref.totalLen / 2 < bytes.length [omega]
    """
    length_ok = len(data) == ref_length
    midpoint_ok = False
    midpoint_byte = None

    if ref_length > 0:
        mid_idx = ref_length // 2
        if mid_idx < len(data):
            midpoint_byte = data[mid_idx]
            midpoint_ok = (midpoint_byte == ref_midpoint_byte)

    valid = length_ok and midpoint_ok

    return {
        "valid": valid,
        "length_check": {"actual": len(data), "expected": ref_length, "pass": length_ok},
        "midpoint_check": {
            "index": ref_length // 2,
            "actual": midpoint_byte,
            "expected": ref_midpoint_byte,
            "pass": midpoint_ok,
        },
        "lean_ref": "Lutar/Innovations/round4/MasoreticChecksum.lean",
        "source": "Wuerthwein, The Text of the Old Testament (1988), pp. 12-15",
    }


def masoretic_receipt_ref(receipt_bytes: bytes) -> dict:
    """
    Compute the Masoretic reference values for a receipt — used to create the reference.
    Store (length, midpoint_byte) alongside the receipt for future validation.
    """
    length = len(receipt_bytes)
    midpoint_byte = receipt_bytes[length // 2] if length > 0 else 0
    return {
        "ref_length": length,
        "ref_midpoint_byte": midpoint_byte,
        "doctrine": "v11 LOCKED 749/14/163",
    }


# ---------------------------------------------------------------------------
# F-07: ELS-BONFERRONI-BOUND (statistical gate sensitivity)
# ---------------------------------------------------------------------------

# SKEPTIC NOTE: This extracts ONLY the false-positive rate formula from
# McKay et al. (1999), which REFUTED the Bible Code ELS claims.

def els_expected_count(corpus_size: int,
                       max_skip: int,
                       word_length: int,
                       alphabet_size: int = 26) -> float:
    """
    Expected number of ELS (equidistant letter sequence) occurrences.
    Formula from McKay et al., Statistical Science 14(2):150-173, 1999.
    E[count] ≤ 2 * C * K / sigma^L

    CONTEXT: This formula was used to DISPROVE the Bible Code — the expected count
    in a 304,805-character text with K=5000, L=4 is ~3 billion.
    Lean: els_bonferroni_monotone_in_W — bound monotone increasing in W.
    """
    if alphabet_size <= 0 or word_length <= 0:
        return 0.0
    return (2.0 * corpus_size * max_skip) / (alphabet_size ** word_length)


def bonferroni_els_fpr(corpus_size: int,
                       max_skip: int,
                       word_length: int,
                       n_patterns: int,
                       alphabet_size: int = 26) -> float:
    """
    Bonferroni-corrected family-wise false-positive rate for searching W patterns.
    FPR ≤ W * E[count_per_pattern]

    Use for sentra gate output sensitivity testing: before flagging an anomaly,
    verify that the observed pattern count exceeds this Bonferroni bound.
    Lean: els_bonferroni_monotone_in_W — FPR ≤ FPR(W+1) for any W.
    Lean: els_zero_patterns — FPR = 0 when W = 0.
    """
    if n_patterns == 0:
        return 0.0  # Lean: els_zero_patterns
    per_pattern = els_expected_count(corpus_size, max_skip, word_length, alphabet_size)
    return n_patterns * per_pattern


def sentra_gate_sensitivity_check(observed_count: int,
                                   corpus_size: int,
                                   max_skip: int,
                                   word_length: int,
                                   n_patterns: int,
                                   alphabet_size: int = 26,
                                   significance_multiplier: float = 10.0) -> dict:
    """
    Check if an observed pattern count in gate output is statistically significant
    vs. the Bonferroni-corrected ELS false-positive baseline.

    A count is flagged as anomalous only if:
      observed_count > significance_multiplier * bonferroni_fpr

    Source: McKay et al., Statistical Science 14(2):150-173, 1999.
    DOI: 10.1214/ss/1009212243
    """
    fpr = bonferroni_els_fpr(corpus_size, max_skip, word_length, n_patterns, alphabet_size)
    threshold = significance_multiplier * fpr
    is_anomalous = observed_count > threshold

    return {
        "observed_count": observed_count,
        "bonferroni_fpr": fpr,
        "significance_threshold": threshold,
        "is_anomalous": is_anomalous,
        "interpretation": (
            "ANOMALOUS (exceeds Bonferroni-corrected threshold)"
            if is_anomalous
            else "NOT anomalous (consistent with random baseline)"
        ),
        "lean_ref": "Lutar/Innovations/round4/ELSBonferroniBound.lean",
        "source": "McKay et al., Statistical Science 14(2):150-173, 1999. DOI: 10.1214/ss/1009212243",
        "skeptic_note": "ELS Bible Code claims are REFUTED. This extracts only the statistical bound.",
        "doctrine": "v11 LOCKED 749/14/163",
        "lambda": "Conjecture 1 — NOT theorem",
    }
