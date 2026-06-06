"""amaru.src.cortex.entropy_budget — Shannon entropy as cortex attention budget.

Doctrine v6 | SPDX-License-Identifier: BSL-1.1
Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings

Implements the ``Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits``
theorem as a hard attention-budget gate for the amaru cortex.

The doctrine-label alphabet has exactly 4 classes:
  { Bot, L1, L2, Top }

By Shannon's entropy theorem, the maximum entropy of any distribution
over an alphabet of size 4 is log₂(4) = 2 bits, achieved uniquely at
the uniform distribution. This bounds the attention budget per inference
call: attending to more than 2 bits of doctrine signal is
information-theoretically redundant.

Lean theorem: Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits
Lean file:    Lutar/Shannon/DoctrineEntropy.lean
Lean line:    ~60
Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
Status:       STAGED-ADVISORY (DoctrineEntropy.lean repair pending PR #98–#102)

Reference:
  Shannon, C.E. (1948) "A Mathematical Theory of Communication,"
  Bell System Technical Journal, 27(3):379–423.
  DOI: 10.1002/j.1538-7305.1948.tb01338.x
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LUTAR_LEAN_HEAD_SHA: str = "c4d13795689601324fce0236351bfe0ade990a43"

ENTROPY_THEOREM: str = (
    "Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits"
)
ENTROPY_LEAN_FILE: str = "Lutar/Shannon/DoctrineEntropy.lean"
ENTROPY_LEAN_LINE: int = 60
ENTROPY_STATUS: str = "STAGED-ADVISORY"

#: Doctrine-label alphabet size. log₂(4) = 2 bits exactly.
DOCTRINE_ALPHABET_SIZE: int = 4

#: Maximum Shannon entropy for the doctrine alphabet (bits).
MAX_DOCTRINE_ENTROPY_BITS: float = math.log2(DOCTRINE_ALPHABET_SIZE)  # = 2.0

#: Tolerance for floating-point entropy bound checks.
_ENTROPY_EPS: float = 1e-9

#: Minimum probability below which a class is treated as zero (avoids log(0)).
_PROB_FLOOR: float = 1e-15


# ---------------------------------------------------------------------------
# Doctrine-label enum
# ---------------------------------------------------------------------------

class DoctrineLabel(str, Enum):
    """Four-class doctrine-label alphabet (TH_V18_02_DoctrineLabelFintype).

    Lean obligation: ``TH_V18_02_DoctrineLabelFintype.lean``
    File: ``Lutar/Doctrine/DoctrineLabelFintype.lean``
    Status: TRACKED
    """
    BOT = "Bot"
    L1 = "L1"
    L2 = "L2"
    TOP = "Top"


# Canonical ordering for probability vectors (must match Lean Fintype instance).
_DOCTRINE_LABEL_ORDER: tuple[DoctrineLabel, ...] = (
    DoctrineLabel.BOT,
    DoctrineLabel.L1,
    DoctrineLabel.L2,
    DoctrineLabel.TOP,
)


# ---------------------------------------------------------------------------
# DSSE receipt helpers
# ---------------------------------------------------------------------------

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _inputs_hash(inputs: dict[str, Any]) -> str:
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return _sha256_hex(canonical)


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dsse_receipt(
    inputs: dict[str, Any],
    output: dict[str, Any],
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> dict[str, Any]:
    """Build DSSE receipt for one entropy budget evaluation.

    Lean theorem: Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits
    Lean file:    Lutar/Shannon/DoctrineEntropy.lean:60
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       STAGED-ADVISORY
    """
    return {
        "theorem": ENTROPY_THEOREM,
        "lean_file": ENTROPY_LEAN_FILE,
        "lean_line": ENTROPY_LEAN_LINE,
        "lean_status": ENTROPY_STATUS,
        "lean_commit_sha": lean_commit_sha,
        "inputs_hash": _inputs_hash(inputs),
        "output": output,
        "ts": _iso_now(),
    }


# ---------------------------------------------------------------------------
# Shannon entropy computation
# ---------------------------------------------------------------------------

def shannon_entropy_bits(probs: list[float]) -> float:
    """Compute Shannon entropy of a probability distribution in bits.

    Formula: H(X) = −Σ pᵢ log₂(pᵢ)  (with 0·log₂(0) := 0)

    Lean theorem: Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits
    Lean file:    Lutar/Shannon/DoctrineEntropy.lean:60
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       STAGED-ADVISORY

    Args:
        probs: Probability distribution. Need not sum to exactly 1.0 but
               all values must be ≥ 0.

    Returns:
        Entropy in bits (≥ 0).

    Raises:
        ValueError: If any probability is negative.
    """
    for i, p in enumerate(probs):
        if p < 0:
            raise ValueError(f"Negative probability at index {i}: {p!r}")
    entropy = 0.0
    for p in probs:
        if p > _PROB_FLOOR:
            entropy -= p * math.log2(p)
    return entropy


def validate_doctrine_probs(probs: list[float]) -> list[float]:
    """Normalise and validate a doctrine probability vector of length 4.

    Args:
        probs: Raw probability vector. Must have length 4 and non-negative entries.

    Returns:
        Normalised probability vector summing to 1.

    Raises:
        ValueError: If length ≠ 4, all-zero, or negative entry.
    """
    if len(probs) != DOCTRINE_ALPHABET_SIZE:
        raise ValueError(
            f"Doctrine alphabet requires exactly {DOCTRINE_ALPHABET_SIZE} probabilities, "
            f"got {len(probs)}."
        )
    for i, p in enumerate(probs):
        if p < 0:
            raise ValueError(f"Probability at index {i} is negative: {p!r}")
    total = sum(probs)
    if total < _PROB_FLOOR:
        raise ValueError("All-zero probability vector — cannot normalise.")
    return [p / total for p in probs]


# ---------------------------------------------------------------------------
# Entropy budget gate
# ---------------------------------------------------------------------------

@dataclass
class EntropyBudgetResult:
    """Result of a single doctrine entropy budget evaluation.

    Attributes:
        entropy_bits:   Shannon entropy of the doctrine distribution (bits).
        max_bits:       Maximum possible entropy = log₂(4) = 2.0 bits.
        within_budget:  True if entropy ≤ max_bits + ε (always true for
                        well-formed doctrine distributions).
        normalised_load: entropy / max_bits in [0, 1] — the fraction of the
                        2-bit budget consumed.
        label_probs:    Dict mapping DoctrineLabel → probability.
        dsse_receipt:   DSSE receipt for this evaluation.
    """
    entropy_bits: float
    max_bits: float
    within_budget: bool
    normalised_load: float
    label_probs: dict[str, float]
    dsse_receipt: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def doctrine_entropy_budget(
    probs: list[float],
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> EntropyBudgetResult:
    """Evaluate the doctrine entropy budget gate.

    Computes the Shannon entropy of a doctrine-label probability distribution
    and checks that it does not exceed log₂(4) = 2 bits. The theorem
    ``doctrine_max_entropy_2_bits`` guarantees this bound is tight (achieved
    at uniform) and that any valid probability distribution over the 4-class
    alphabet satisfies it.

    This function is the runtime gate: it RAISES RuntimeError if the entropy
    exceeds 2 bits (which can only happen due to floating-point mis-normalisation
    or a bug in the probability computation).

    Lean theorem: Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits
    Lean file:    Lutar/Shannon/DoctrineEntropy.lean:60
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       STAGED-ADVISORY

    Args:
        probs:           Probability vector over [Bot, L1, L2, Top] (length 4).
        lean_commit_sha: lutar-lean HEAD SHA.

    Returns:
        :class:`EntropyBudgetResult` with full audit trail.

    Raises:
        ValueError:   If probs is malformed (wrong length, negative, all-zero).
        RuntimeError: If entropy exceeds 2 bits (theorem violation — indicates bug).
    """
    normalised = validate_doctrine_probs(probs)
    entropy = shannon_entropy_bits(normalised)
    within_budget = entropy <= MAX_DOCTRINE_ENTROPY_BITS + _ENTROPY_EPS

    if not within_budget:
        raise RuntimeError(
            f"Doctrine entropy budget violation: {entropy:.6f} bits > "
            f"{MAX_DOCTRINE_ENTROPY_BITS} bits max "
            f"(Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits). "
            "This indicates a bug in probability normalisation."
        )

    label_probs = {
        label.value: round(normalised[i], 12)
        for i, label in enumerate(_DOCTRINE_LABEL_ORDER)
    }
    normalised_load = entropy / MAX_DOCTRINE_ENTROPY_BITS

    inp = {"probs": probs, "doctrine_alphabet_size": DOCTRINE_ALPHABET_SIZE}
    out = {
        "entropy_bits": entropy,
        "max_bits": MAX_DOCTRINE_ENTROPY_BITS,
        "within_budget": within_budget,
        "normalised_load": normalised_load,
    }

    return EntropyBudgetResult(
        entropy_bits=entropy,
        max_bits=MAX_DOCTRINE_ENTROPY_BITS,
        within_budget=within_budget,
        normalised_load=normalised_load,
        label_probs=label_probs,
        dsse_receipt=_dsse_receipt(inp, out, lean_commit_sha=lean_commit_sha),
    )


def entropy_budget_from_labels(
    label_counts: dict[str, int],
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> EntropyBudgetResult:
    """Compute entropy budget from raw doctrine-label frequency counts.

    Converts raw counts (e.g. from an inference batch) to a probability
    distribution and evaluates the entropy budget gate.

    Lean theorem: Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits
    Lean file:    Lutar/Shannon/DoctrineEntropy.lean:60
    Status:       STAGED-ADVISORY

    Args:
        label_counts: Dict mapping label name → count. Missing labels default to 0.
        lean_commit_sha: lutar-lean HEAD SHA.

    Returns:
        :class:`EntropyBudgetResult`.

    Raises:
        ValueError: If all counts are zero.
    """
    counts = [
        label_counts.get(label.value, 0) for label in _DOCTRINE_LABEL_ORDER
    ]
    total = sum(counts)
    if total == 0:
        raise ValueError("All label counts are zero — cannot compute entropy.")
    probs = [c / total for c in counts]
    return doctrine_entropy_budget(probs, lean_commit_sha=lean_commit_sha)


def rate_limit_inference(
    probs: list[float],
    load_threshold: float = 1.0,
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
) -> dict[str, Any]:
    """Gate an inference call based on the doctrine entropy budget.

    If the normalised entropy load exceeds ``load_threshold`` (default: 1.0 =
    full 2-bit budget), the call is rate-limited (rejected). This implements
    the amaru cortex's formal attention-budget enforcement.

    Lean theorem: Lutar.Shannon.DoctrineEntropy.doctrine_max_entropy_2_bits
    Lean file:    Lutar/Shannon/DoctrineEntropy.lean:60
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       STAGED-ADVISORY

    Args:
        probs:           Doctrine probability vector (length 4).
        load_threshold:  Fraction of 2-bit budget above which to rate-limit
                         (0 < threshold ≤ 1.0).
        lean_commit_sha: lutar-lean HEAD SHA.

    Returns:
        Dict with keys:
            allowed         — bool: True if inference may proceed
            entropy_bits    — Shannon entropy of probs
            normalised_load — fraction of 2-bit budget used
            dsse_receipt    — DSSE receipt
    """
    result = doctrine_entropy_budget(probs, lean_commit_sha=lean_commit_sha)
    allowed = result.normalised_load <= load_threshold + _ENTROPY_EPS
    return {
        "allowed": allowed,
        "entropy_bits": result.entropy_bits,
        "normalised_load": result.normalised_load,
        "dsse_receipt": result.dsse_receipt,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("  amaru — Doctrine Entropy Budget | Doctrine v6 | STAGED-ADVISORY")
    print("=" * 72)

    examples = [
        ("Uniform (max entropy = 2 bits)", [0.25, 0.25, 0.25, 0.25]),
        ("Degenerate Bot (0 bits)", [1.0, 0.0, 0.0, 0.0]),
        ("Skewed toward L2/Top", [0.05, 0.1, 0.4, 0.45]),
        ("Near-uniform", [0.24, 0.26, 0.25, 0.25]),
    ]
    for name, probs in examples:
        r = doctrine_entropy_budget(probs)
        print(f"\n  {name}")
        print(f"    entropy        = {r.entropy_bits:.8f} bits")
        print(f"    max            = {r.max_bits} bits")
        print(f"    load           = {r.normalised_load:.4f}")
        print(f"    within_budget  = {r.within_budget}")
        print(f"    label_probs    = {r.label_probs}")
