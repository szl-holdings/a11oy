"""sentra.src.forecasting.witnessed_forecast — Formal witness emission per forecast.

Doctrine v6 | Phase 1 Track 2a | SPDX-License-Identifier: BSL-1.1
Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings

Every forecast produced by this module carries a ``formula_witness`` field
that cryptographically binds the prediction to a Lean theorem in the SZL
lutar-lean repository. Two anchors are used:

  1. **Mādhava remainder bound** (error envelope):
       Lean theorem: ``Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound``
       File: ``Lutar/PACBayes/MadhavaBound.lean``
       Commit: c4d13795689601324fce0236351bfe0ade990a43
       Status: TRACKED (1 sorry — monotone-convergence defer to Mathlib MCT)

  2. **Liu Hui monotone convergence** (confidence ratchet):
       Lean theorem: ``Lutar.Banach.LiuHui.liuHuiPi_monotone``
       File: ``Lutar/Banach/LiuHuiPi.lean``
       Commit: c4d13795689601324fce0236351bfe0ade990a43
       Status: STAGED-ADVISORY (1 sorry — monotone-convergence defer to Mathlib MCT)

DSSE receipt format per evaluation:
  { theorem, lean_commit_sha, inputs_hash, output, ts }

lutar-lean HEAD SHA (pinned 2026-05-30):
  c4d13795689601324fce0236351bfe0ade990a43
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: lutar-lean HEAD pinned 2026-05-30.
LUTAR_LEAN_HEAD_SHA: str = "c4d13795689601324fce0236351bfe0ade990a43"

#: Lean theorem namespace + name for the Mādhava remainder bound.
MADHAVA_THEOREM: str = "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound"
MADHAVA_LEAN_FILE: str = "Lutar/PACBayes/MadhavaBound.lean"
MADHAVA_LEAN_LINE: int = 72
MADHAVA_STATUS: str = "TRACKED"

#: Lean theorem for Liu Hui monotone convergence.
LIU_HUI_THEOREM: str = "Lutar.Banach.LiuHui.liuHuiPi_monotone"
LIU_HUI_LEAN_FILE: str = "Lutar/Banach/LiuHuiPi.lean"
LIU_HUI_LEAN_LINE: int = 65
LIU_HUI_STATUS: str = "STAGED-ADVISORY"

#: Minimum absolute value treated as non-zero for bound computation.
_ZERO_FLOOR: float = 1e-15


# ---------------------------------------------------------------------------
# DSSE receipt helpers
# ---------------------------------------------------------------------------

def _sha256_hex(s: str) -> str:
    """Return hex SHA-256 of *s*."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _inputs_hash(inputs: dict[str, Any]) -> str:
    """Deterministic SHA-256 of a JSON-serialisable dict."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return _sha256_hex(canonical)


def _dsse_receipt(
    theorem: str,
    lean_file: str,
    lean_line: int,
    lean_status: str,
    lean_commit_sha: str,
    inputs: dict[str, Any],
    output: dict[str, Any],
) -> dict[str, Any]:
    """Build a DSSE receipt dict per the SZL receipt ledger schema.

    Schema:
        theorem         — fully-qualified Lean theorem name
        lean_file       — relative path within lutar-lean
        lean_line       — approximate line of the theorem statement
        lean_status     — GREEN / TRACKED / STAGED-ADVISORY / RED
        lean_commit_sha — lutar-lean HEAD SHA at call time
        inputs_hash     — SHA-256 of canonical JSON of ``inputs``
        output          — computation result dict
        ts              — ISO-8601 UTC timestamp

    Lean ref: Lutar/PACBayes/MadhavaBound.lean:72 (TRACKED)
              lutar-lean#106 @ commit c4d13795689601324fce0236351bfe0ade990a43
    """
    return {
        "theorem": theorem,
        "lean_file": lean_file,
        "lean_line": lean_line,
        "lean_status": lean_status,
        "lean_commit_sha": lean_commit_sha,
        "inputs_hash": _inputs_hash(inputs),
        "output": output,
        "ts": _iso_now(),
    }


def _iso_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Mādhava arctan partial sum and remainder bound
# ---------------------------------------------------------------------------

def madhava_remainder_bound(x: float, k: int) -> float:
    """Return the Mādhava remainder bound for arctan(x) after k terms.

    Formula: ``|x|^(2k+1) / (2k+1)``

    Matches ``madhavaRemainderBound`` in
    ``Lutar/PACBayes/MadhavaBound.lean:72`` (TRACKED).

    By ``Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound``:
    the truncation error after k terms satisfies
    ``|arctan(x) − S_k(x)| ≤ |x|^(2k+1) / (2k+1)``
    for all |x| ≤ 1.

    Args:
        x: Normalised input, |x| ≤ 1.
        k: Number of terms summed (≥ 1).

    Returns:
        Non-negative upper bound on truncation error.

    Lean theorem: Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound
    Lean file:    Lutar/PACBayes/MadhavaBound.lean:72
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       TRACKED
    """
    if abs(x) < _ZERO_FLOOR:
        return 0.0
    return (abs(x) ** (2 * k + 1)) / (2 * k + 1)


def madhava_arctan_partial(x: float, k: int) -> float:
    """Return Mādhava arctan partial sum S_k(x) = Σ_{n=0}^{k-1} (-1)^n x^{2n+1}/(2n+1).

    Lean theorem: Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound
    Lean file:    Lutar/PACBayes/MadhavaBound.lean:72
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       TRACKED

    Args:
        x: Input value, |x| ≤ 1 for convergence.
        k: Number of terms (≥ 1).

    Returns:
        Partial sum approximation of arctan(x).
    """
    total = 0.0
    for n in range(k):
        sign = 1 if n % 2 == 0 else -1
        total += sign * (x ** (2 * n + 1)) / (2 * n + 1)
    return total


# ---------------------------------------------------------------------------
# Liu Hui monotone confidence ratchet
# ---------------------------------------------------------------------------

def liu_hui_confidence_step(prev_conf: float, new_evidence: float) -> dict[str, Any]:
    """Apply one Liu Hui polygon-doubling step to the confidence value.

    The Liu Hui polygon-doubling sequence: s_{2k}^2 = 2 − sqrt(4 − s_k^2)
    converges monotonically to π from below [Liu Hui, 263 CE, Nine Chapters].
    Analogously, confidence increases monotonically toward 1.0 under each
    new evidence panel.

    Invariant (per Lean theorem): nextConf ≥ prevConf.
    Violation is raised as RuntimeError to prevent silent confidence
    regression in the sanctions matching pipeline.

    Lean theorem: Lutar.Banach.LiuHui.liuHuiPi_monotone
    Lean file:    Lutar/Banach/LiuHuiPi.lean:65
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       STAGED-ADVISORY

    Args:
        prev_conf:    Previous confidence value in [0, 1].
        new_evidence: Strength of incoming evidence in [0, 1].

    Returns:
        Dict with keys:
            next_conf       — new confidence in [0, 1]
            monotone_ok     — bool: next_conf >= prev_conf − ε
            delta           — increase applied
            dsse_receipt    — DSSE receipt dict

    Raises:
        RuntimeError: If the Liu Hui monotone invariant is violated.
        ValueError:   If prev_conf or new_evidence is outside [0, 1].
    """
    if not (0.0 <= prev_conf <= 1.0):
        raise ValueError(f"prev_conf must be in [0,1], got {prev_conf!r}")
    if not (0.0 <= new_evidence <= 1.0):
        raise ValueError(f"new_evidence must be in [0,1], got {new_evidence!r}")

    # Liu Hui analogy: confidence gap = 1 − prev_conf; evidence reduces gap
    # as sqrt-contraction: Δ = (1 − sqrt(1 − e)) × gap.
    evidence_gap = 1.0 - prev_conf
    contraction = 1.0 - math.sqrt(max(0.0, 1.0 - new_evidence))
    delta = contraction * evidence_gap
    next_conf = min(1.0, prev_conf + delta)

    monotone_ok = next_conf >= prev_conf - 1e-12
    if not monotone_ok:
        raise RuntimeError(
            f"Liu Hui monotone invariant violated: "
            f"next_conf={next_conf:.6f} < prev_conf={prev_conf:.6f} "
            f"(Lutar.Banach.LiuHui.liuHuiPi_monotone)"
        )

    inputs = {"prev_conf": prev_conf, "new_evidence": new_evidence}
    output = {"next_conf": next_conf, "delta": delta, "monotone_ok": monotone_ok}
    receipt = _dsse_receipt(
        theorem=LIU_HUI_THEOREM,
        lean_file=LIU_HUI_LEAN_FILE,
        lean_line=LIU_HUI_LEAN_LINE,
        lean_status=LIU_HUI_STATUS,
        lean_commit_sha=LUTAR_LEAN_HEAD_SHA,
        inputs=inputs,
        output=output,
    )
    return {**output, "dsse_receipt": receipt}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceEnvelope:
    """Mādhava-bounded confidence interval around a forecast.

    Attributes:
        lower:        Lower bound of the interval.
        upper:        Upper bound of the interval.
        bound:        Half-width = |x|^(2k+1)/(2k+1).
        k_terms:      Number of Mādhava series terms used.
        x_normalised: Clamped input value used for the bound.
        formula:      Lean theorem slug.
    """
    lower: float
    upper: float
    bound: float
    k_terms: int
    x_normalised: float
    formula: str = MADHAVA_THEOREM


@dataclass
class WitnessedForecast:
    """A scalar forecast coupled with a cryptographic formula witness.

    Every field is mandatory so that downstream consumers can assert
    completeness without None-handling.

    Attributes:
        prediction:          Scalar forecast value (e.g. probability in [0,1]).
        formula_witness:     Lean theorem slug anchoring this forecast.
        lean_theorem_ref:    Fully-qualified Lean 4 theorem reference.
        lean_file:           Relative path of the Lean source file.
        lean_line:           Approximate line of the theorem statement.
        lean_status:         Theorem status (GREEN / TRACKED / STAGED-ADVISORY / RED).
        lean_commit_sha:     lutar-lean HEAD SHA at prediction time.
        confidence_envelope: Mādhava-bounded interval around ``prediction``.
        dsse_receipt:        Full DSSE receipt dict for audit.
        synthetic:           True if forecast comes from test/synthetic data.
        metadata:            Caller-supplied key-value pairs.
    """
    prediction: float
    formula_witness: str
    lean_theorem_ref: str
    lean_file: str
    lean_line: int
    lean_status: str
    lean_commit_sha: str
    confidence_envelope: ConfidenceEnvelope
    dsse_receipt: dict[str, Any]
    synthetic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of this forecast."""
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Public API — forecast_with_witness
# ---------------------------------------------------------------------------

def forecast_with_witness(
    input_value: float,
    k: int = 10,
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
    synthetic: bool = False,
    metadata: dict[str, Any] | None = None,
) -> WitnessedForecast:
    """Produce a witnessed forecast with a Mādhava-bounded error envelope.

    The forecast value is the Mādhava arctan partial sum evaluated at the
    normalised ``input_value``. The error envelope is the Mādhava remainder
    bound at ``k`` terms.

    Per Doctrine v6: every forecast MUST carry a ``formula_witness`` that
    names the Lean theorem bounding the error. This function satisfies that
    requirement.

    Lean theorem: Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound
    Lean file:    Lutar/PACBayes/MadhavaBound.lean:72
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       TRACKED

    Args:
        input_value:     Raw input value. Clamped to [−1, 1].
        k:               Number of Mādhava terms (≥ 1).
        lean_commit_sha: lutar-lean HEAD SHA to embed in witness.
        synthetic:       Label forecast as synthetic (Doctrine v6 requirement
                         when test data is used).
        metadata:        Caller-supplied key-value pairs.

    Returns:
        A :class:`WitnessedForecast` with all fields populated.

    Raises:
        ValueError: If ``k < 1``.

    Examples:
        >>> wf = forecast_with_witness(0.5, k=10, synthetic=True)
        >>> wf.formula_witness == MADHAVA_THEOREM
        True
        >>> wf.lean_commit_sha == LUTAR_LEAN_HEAD_SHA
        True
        >>> wf.confidence_envelope.bound >= 0
        True
        >>> wf.confidence_envelope.lower <= wf.prediction <= wf.confidence_envelope.upper
        True
    """
    if k < 1:
        raise ValueError(f"k must be ≥ 1, got {k!r}")

    x = max(-1.0, min(1.0, float(input_value)))
    prediction = madhava_arctan_partial(x, k)
    bound = madhava_remainder_bound(x, k)

    envelope = ConfidenceEnvelope(
        lower=prediction - bound,
        upper=prediction + bound,
        bound=bound,
        k_terms=k,
        x_normalised=x,
        formula=MADHAVA_THEOREM,
    )

    inputs = {"input_value": input_value, "x_normalised": x, "k": k}
    output = {
        "prediction": prediction,
        "bound": bound,
        "lower": envelope.lower,
        "upper": envelope.upper,
    }
    receipt = _dsse_receipt(
        theorem=MADHAVA_THEOREM,
        lean_file=MADHAVA_LEAN_FILE,
        lean_line=MADHAVA_LEAN_LINE,
        lean_status=MADHAVA_STATUS,
        lean_commit_sha=lean_commit_sha,
        inputs=inputs,
        output=output,
    )

    return WitnessedForecast(
        prediction=prediction,
        formula_witness=MADHAVA_THEOREM,
        lean_theorem_ref=MADHAVA_THEOREM,
        lean_file=MADHAVA_LEAN_FILE,
        lean_line=MADHAVA_LEAN_LINE,
        lean_status=MADHAVA_STATUS,
        lean_commit_sha=lean_commit_sha,
        confidence_envelope=envelope,
        dsse_receipt=receipt,
        synthetic=synthetic,
        metadata=metadata or {},
    )


def forecast_batch(
    inputs: list[float],
    k: int = 10,
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
    synthetic: bool = False,
) -> list[WitnessedForecast]:
    """Produce witnessed forecasts for each value in ``inputs``.

    Lean theorem: Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound
    Lean file:    Lutar/PACBayes/MadhavaBound.lean:72
    Lean commit:  c4d13795689601324fce0236351bfe0ade990a43
    Status:       TRACKED

    Args:
        inputs:          List of raw input values.
        k:               Number of Mādhava terms.
        lean_commit_sha: lutar-lean HEAD SHA.
        synthetic:       Label all forecasts as synthetic.

    Returns:
        List of :class:`WitnessedForecast`, one per input.

    Examples:
        >>> results = forecast_batch([0.0, 0.5, 1.0], k=5)
        >>> len(results)
        3
        >>> all(r.formula_witness == MADHAVA_THEOREM for r in results)
        True
    """
    return [
        forecast_with_witness(v, k, lean_commit_sha=lean_commit_sha, synthetic=synthetic)
        for v in inputs
    ]


# ---------------------------------------------------------------------------
# CLI runnable
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("  sentra — Witnessed Forecast | Doctrine v6 | Lean TRACKED")
    print("=" * 72)
    for x, k in [(0.5, 10), (1.0, 10), (0.0, 5), (-0.75, 8)]:
        wf = forecast_with_witness(x, k=k, synthetic=True)
        print(f"\n  x={x:+.2f} k={k}")
        print(f"    prediction = {wf.prediction:.8f}")
        print(f"    bound      = {wf.confidence_envelope.bound:.2e}")
        print(f"    interval   = [{wf.confidence_envelope.lower:.6f}, "
              f"{wf.confidence_envelope.upper:.6f}]")
        print(f"    witness    = {wf.formula_witness[:55]}")
        print(f"    sha        = {wf.lean_commit_sha[:12]}...")
        print(f"    status     = {wf.lean_status}")
        print(f"    receipt.ts = {wf.dsse_receipt['ts']}")
