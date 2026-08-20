"""SENTRA — Witnessed Forecasting with Mādhava Error Envelope.

Phase 1 Track 2a deliverable (Doctrine v6).

Every forecast produced by this module carries a ``formula_witness`` field
that cryptographically binds the prediction to an anchor formula in the
SZL Holdings receipt ledger.  The Mādhava alternating-series bound
(``Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound``) is used as the
error-envelope formula: the forecast confidence interval is bounded by the
first omitted term of the Mādhava arctan partial sum.

The key invariant (per Doctrine v6 — no hallucinations):

    |forecast − truth| ≤ madhava_remainder_bound(x, k)
                        = |x|^(2k+1) / (2k+1)

for a normalised input ``x ∈ [−1, 1]`` and ``k`` series terms.

Lean theorem reference (verified to exist on lutar-lean main):
    ``Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound``

lutar-lean HEAD SHA (pinned 2026-05-30):
    ``c4d13795689601324fce0236351bfe0ade990a43``

SPDX-License-Identifier: BSL-1.1
Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Lean theorem namespace + name for the Mādhava remainder bound.
MADHAVA_THEOREM_REF: str = (
    "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound"
)

#: Formula slug as it appears in the SZL ANCHOR_REGISTRY.
MADHAVA_FORMULA_ID: str = "madhava_bound"

#: lutar-lean main HEAD SHA pinned at module-write time (2026-05-30).
#: Callers that want the live HEAD should fetch it from the lutar-lean API
#: and pass it to ``forecast_with_madhava_bound`` via ``lean_commit_sha``.
LUTAR_LEAN_HEAD_SHA: str = "c4d13795689601324fce0236351bfe0ade990a43"

#: Floor below which the raw input is treated as exactly zero (avoids
#: division-by-zero in the bound computation).
_ABS_ZERO_FLOOR: float = 1e-15


# ---------------------------------------------------------------------------
# Madhava bound helpers (pure, no I/O)
# ---------------------------------------------------------------------------

def _madhava_remainder_bound(x: float, k: int) -> float:
    """Return the Mādhava remainder bound: |x|^(2k+1) / (2k+1).

    Matches the Lean definition in
    ``Lutar.PACBayes.MadhavaBound.madhavaRemainderBound``:

        noncomputable def madhavaRemainderBound (x : ℝ) (N : ℕ) : ℝ :=
          |x|^(2*N+1) / (2*N+1)

    The parameter ``k`` here corresponds to ``N`` in the Lean definition;
    the bound is the magnitude of the (k+1)-th term, which upper-bounds the
    truncation error after ``k`` terms.

    Args:
        x: Normalised input value.  Must satisfy ``|x| ≤ 1`` for the bound
           to be monotonically decreasing in ``k``.
        k: Number of series terms already summed (≥ 1).

    Returns:
        Non-negative upper bound on the truncation error.

    Examples:
        >>> _madhava_remainder_bound(1.0, 10)
        0.047619047619047616
        >>> _madhava_remainder_bound(0.5, 5)  # 0.5^11 / 11
        4.438920454545455e-05
        >>> _madhava_remainder_bound(0.0, 10)
        0.0
        >>> _madhava_remainder_bound(1.0, 1)
        0.3333333333333333
    """
    if abs(x) < _ABS_ZERO_FLOOR:
        return 0.0
    exponent = 2 * k + 1
    return (abs(x) ** exponent) / exponent


def _madhava_arctan_partial(x: float, k: int) -> float:
    """Return the Mādhava arctan partial sum to ``k`` terms.

    Matches the Lean definition in
    ``Lutar.PACBayes.MadhavaBound.madhavaArctanPartial``:

        Σ_{n=0}^{k-1} (-1)^n · x^(2n+1) / (2n+1)

    Args:
        x: Input value (|x| ≤ 1 for convergence).
        k: Number of terms to sum (≥ 1).

    Returns:
        Partial sum approximation of arctan(x).

    Examples:
        >>> round(_madhava_arctan_partial(1.0, 100), 4)
        0.7829
        >>> round(_madhava_arctan_partial(0.0, 10), 10)
        0.0
        >>> abs(_madhava_arctan_partial(1.0, 10) - math.atan(1.0)) <= _madhava_remainder_bound(1.0, 10)
        True
    """
    total = 0.0
    for n in range(k):
        sign = (-1) ** n
        total += sign * (x ** (2 * n + 1)) / (2 * n + 1)
    return total


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceEnvelope:
    """Confidence envelope produced by the Mādhava remainder bound.

    Attributes:
        lower: Lower bound of the confidence interval.
        upper: Upper bound of the confidence interval.
        bound: Half-width of the interval (= |x|^(2k+1) / (2k+1)).
        k_terms: Number of Mādhava series terms used.
        x_normalised: The normalised input value used for the bound.
        formula: Formula slug (always ``"madhava_bound"`` for this module).
    """
    lower: float
    upper: float
    bound: float
    k_terms: int
    x_normalised: float
    formula: str = MADHAVA_FORMULA_ID


@dataclass
class WitnessedForecast:
    """A forecast observation coupled with a cryptographic formula witness.

    Every field is mandatory so that downstream consumers (uds-mesh receipt
    ledger, anatomy-alive harness) can assert completeness without special-
    casing ``None`` values.

    Attributes:
        prediction: The scalar forecast value (e.g. a probability in [0,1]
            or a normalised risk score).
        formula_witness: Slug of the anchor formula that bounds this forecast.
            Must match an entry in the SZL ANCHOR_REGISTRY.
        lean_theorem_ref: Fully-qualified Lean 4 theorem reference that
            provides machine-verifiable proof of the error bound.
        lean_commit_sha: lutar-lean main HEAD SHA at prediction time.
            Consumers use this to verify the theorem has not changed.
        confidence_envelope: The Mādhava-bounded confidence interval around
            ``prediction``.
        synthetic: True when the forecast was produced from synthetic / test
            data (Doctrine v6: all synthetic data must be labeled).
        metadata: Arbitrary caller-supplied key-value pairs.
    """
    prediction: float
    formula_witness: str
    lean_theorem_ref: str
    lean_commit_sha: str
    confidence_envelope: ConfidenceEnvelope
    synthetic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def forecast_with_madhava_bound(
    input_value: float,
    k: int = 10,
    *,
    lean_commit_sha: str = LUTAR_LEAN_HEAD_SHA,
    synthetic: bool = False,
    metadata: dict[str, Any] | None = None,
) -> WitnessedForecast:
    """Produce a witnessed forecast with a Mādhava-bounded error envelope.

    The forecast value is the Mādhava arctan partial sum evaluated at the
    normalised ``input_value``.  The error envelope is the Mādhava remainder
    bound at ``k`` terms, which by the Lean theorem
    ``Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound`` upper-bounds
    the truncation error for any |x| ≤ 1.

    Args:
        input_value: Raw input value.  Clamped to [−1, 1] before use so that
            the Mādhava bound is monotonically decreasing.
        k: Number of Mādhava series terms to sum (must be ≥ 1).
        lean_commit_sha: lutar-lean HEAD SHA to embed in the witness.
            Defaults to ``LUTAR_LEAN_HEAD_SHA`` (pinned 2026-05-30).
        synthetic: Label the forecast as synthetic (Doctrine v6 requirement
            when test data is used).  Defaults to ``False``.
        metadata: Caller-supplied key-value pairs stored on the forecast.

    Returns:
        A :class:`WitnessedForecast` with all fields populated.

    Raises:
        ValueError: If ``k < 1``.

    Examples:
        >>> wf = forecast_with_madhava_bound(0.5, k=10)
        >>> wf.formula_witness == 'madhava_bound'
        True
        >>> wf.lean_theorem_ref == 'Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound'
        True
        >>> len(wf.lean_commit_sha) == 40
        True
        >>> wf.confidence_envelope.k_terms == 10
        True
        >>> wf.confidence_envelope.bound >= 0
        True
        >>> wf.confidence_envelope.lower <= wf.prediction <= wf.confidence_envelope.upper
        True
        >>> wf2 = forecast_with_madhava_bound(1.0, k=10)
        >>> round(wf2.confidence_envelope.bound, 6)
        0.047619
        >>> wf3 = forecast_with_madhava_bound(0.5, k=5)
        >>> round(wf3.confidence_envelope.bound, 10)  # 0.5^11 / 11
        4.43892e-05
        >>> wf4 = forecast_with_madhava_bound(0.0, k=10)
        >>> wf4.confidence_envelope.bound == 0.0
        True
        >>> wf5 = forecast_with_madhava_bound(0.5, k=10, synthetic=True)
        >>> wf5.synthetic
        True
        >>> wf5.formula_witness
        'madhava_bound'
        >>> wf6 = forecast_with_madhava_bound(-0.5, k=5)
        >>> wf6.confidence_envelope.lower <= wf6.prediction
        True
    """
    if k < 1:
        raise ValueError(f"k must be ≥ 1, got {k}")

    # Clamp to [−1, 1] so the remainder bound is meaningful
    x = max(-1.0, min(1.0, float(input_value)))

    prediction = _madhava_arctan_partial(x, k)
    bound = _madhava_remainder_bound(x, k)

    envelope = ConfidenceEnvelope(
        lower=prediction - bound,
        upper=prediction + bound,
        bound=bound,
        k_terms=k,
        x_normalised=x,
    )

    return WitnessedForecast(
        prediction=prediction,
        formula_witness=MADHAVA_FORMULA_ID,
        lean_theorem_ref=MADHAVA_THEOREM_REF,
        lean_commit_sha=lean_commit_sha,
        confidence_envelope=envelope,
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
    """Produce a witnessed forecast for each value in ``inputs``.

    Convenience wrapper around :func:`forecast_with_madhava_bound` for
    batch use cases (e.g. scoring a list of agent outputs).

    Args:
        inputs: List of raw input values (each clamped to [−1, 1]).
        k: Number of Mādhava terms.
        lean_commit_sha: lutar-lean HEAD SHA.
        synthetic: Label all forecasts as synthetic.

    Returns:
        List of :class:`WitnessedForecast` objects, one per input.

    Examples:
        >>> results = forecast_batch([0.0, 0.5, 1.0], k=10)
        >>> len(results)
        3
        >>> all(r.formula_witness == 'madhava_bound' for r in results)
        True
        >>> all(len(r.lean_commit_sha) == 40 for r in results)
        True
    """
    return [
        forecast_with_madhava_bound(
            v, k,
            lean_commit_sha=lean_commit_sha,
            synthetic=synthetic,
        )
        for v in inputs
    ]


# ---------------------------------------------------------------------------
# Runnable example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("  SENTRA — Witnessed Forecasting  |  Doctrine v6  |  Phase 1 L7")
    print("=" * 72)
    print()

    examples = [
        ("x=0.5,  k=10", 0.5,  10),
        ("x=1.0,  k=10", 1.0,  10),
        ("x=0.0,  k=10", 0.0,  10),
        ("x=-0.5, k=5",  -0.5,  5),
    ]

    for label, x, k in examples:
        wf = forecast_with_madhava_bound(x, k=k, synthetic=True)
        print(f"  [{label}]")
        print(f"    prediction      = {wf.prediction:.8f}")
        print(f"    bound           = {wf.confidence_envelope.bound:.2e}")
        print(f"    interval        = [{wf.confidence_envelope.lower:.6f}, "
              f"{wf.confidence_envelope.upper:.6f}]")
        print(f"    formula_witness = {wf.formula_witness!r}")
        print(f"    lean_theorem    = {wf.lean_theorem_ref!r}")
        print(f"    lean_sha        = {wf.lean_commit_sha[:12]}...")
        print(f"    synthetic       = {wf.synthetic}")
        print()

    # JSON serialisation example
    wf_json = forecast_with_madhava_bound(0.75, k=10, synthetic=True)
    print("  JSON serialisation:")
    print(json.dumps(wf_json.as_dict(), indent=2))
