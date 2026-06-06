"""
szl_hm_lambda_score.py — Harmonic-mean Lambda aggregator for Sentra

EMERALD CODEX ROUND 5 INSTILLATION: F-06 TETRACTYS-HM-BOUND + F-07 TETRACTYS-HM-BOTTLENECK
Primary source: G.H. Hardy, J.E. Littlewood, G. Pólya, Inequalities,
    Cambridge University Press, 1934 (2nd ed. 1952), Section 2.5. ISBN 0-521-35880-9.
Lean stub: https://github.com/szl-holdings/lutar-lean/blob/feat/innovations-round5/Lutar/Innovations/round5/TetractysHMBound.lean
Lake receipt: https://github.com/szl-holdings/szl-lake/blob/main/attestations/innovations/round5/TetractysHMBound.json
Doctrine: v11 LOCKED 749/14/163 · Λ = Conjecture 1 · lives in Innovations/round5/ outside locked kernel
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

Mathematical guarantee (Hardy-Littlewood-Pólya 1934, §2.5):
    HM(x) ≤ GM(x) ≤ AM(x)   with equality iff all x_i are equal.

Consequence for Λ scoring:
    If HM-score < threshold, there EXISTS at least one axis below threshold.
    (TETRACTYS-HM-BOTTLENECK corollary — formal proof in TetractysHMBottleneck.lean)
"""

from typing import Sequence
import math
import logging

logger = logging.getLogger(__name__)


def harmonic_mean(scores: Sequence[float]) -> float:
    """
    Compute harmonic mean of a sequence of positive scores.
    HM = n / sum(1/x_i).
    Source: Hardy, Littlewood, Pólya (1934), §2.5.
    """
    if not scores:
        raise ValueError("Cannot compute harmonic mean of empty sequence")
    if any(s <= 0 for s in scores):
        raise ValueError("Harmonic mean requires strictly positive values")
    return len(scores) / sum(1.0 / s for s in scores)


def lambda_hm_aggregate(axis_scores: dict[str, float], threshold: float = 0.5) -> dict:
    """
    Aggregate multi-axis Lambda score using harmonic mean.

    Returns dict with:
    - hm_score: harmonic mean (formal lower bound on axis quality)
    - am_score: arithmetic mean (for comparison)
    - bottleneck_axes: axes below threshold (if HM < threshold)
    - bottleneck_detected: True if HM < threshold (theorem guarantee)

    Theorem (HLP 1934): HM < threshold => exists i: score_i < threshold.
    """
    scores = list(axis_scores.values())
    hm = harmonic_mean(scores)
    am = sum(scores) / len(scores)
    bottleneck_axes = [k for k, v in axis_scores.items() if v < threshold]
    bottleneck_detected = hm < threshold

    if bottleneck_detected and not bottleneck_axes:
        logger.warning(
            "[HM-BOTTLENECK] HM < threshold but no axis below threshold found — "
            "verify score precision (HLP 1934 guarantees existence)."
        )

    return {
        "hm_score": hm,
        "am_score": am,
        "hm_le_am": hm <= am + 1e-12,  # invariant check
        "bottleneck_detected": bottleneck_detected,
        "bottleneck_axes": bottleneck_axes,
        "axis_count": len(scores),
    }
