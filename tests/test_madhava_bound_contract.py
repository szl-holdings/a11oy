"""Contract for the classical Madhava first-omitted-term comparison.

The allow bit is a log-space comparison with an absolute threshold.
Lean madhavaRemainderBound_nonneg is nonnegativity only.
accuracyClaim stays NOT_ASSERTED. No network and no file mutation.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from a11oy_v4_formulas import GateError, eval_madhava_bound  # noqa: E402


def test_corpus_duplicate_matches_root_bytes() -> None:
    root = (ROOT / "a11oy_v4_formulas.py").read_bytes()
    corpus = (ROOT / "corpus" / "formulas" / "a11oy__a11oy_v4_formulas.py").read_bytes()
    assert root == corpus


def test_finite_half_five_allows_without_an_accuracy_claim() -> None:
    result = eval_madhava_bound({"x": 0.5, "N": 5})
    expected = math.exp(11 * math.log(0.5) - math.log(11))
    assert result["allow"] is True
    assert result["remainderBoundState"] == "FINITE"
    assert result["remainderBound"] == pytest.approx(expected)
    assert result["lambdaScore"] == pytest.approx(max(0.0, min(1.0, 1.0 - expected)))
    assert result["accuracyClaim"] == "NOT_ASSERTED"
    assert result["leanScope"] == "nonnegativity_only"
    assert result["floatTruncationError"] == "NOT_BOUNDED"
    assert result["comparison"] == "log_space_first_omitted_term"
    assert "nonnegativity only" in result["rationale"]
    assert "sufficiently converged" not in result["rationale"]
    assert "Lean:" in result["rationale"]


def test_unit_interval_endpoints_use_exact_reciprocal() -> None:
    one = eval_madhava_bound({"x": 1, "N": 1})
    assert one["allow"] is False
    assert one["remainderBound"] == pytest.approx(1 / 3)
    assert one["remainderBoundState"] == "FINITE"
    two = eval_madhava_bound({"x": -1, "N": 2})
    assert two["remainderBound"] == pytest.approx(1 / 5)
    assert two["allow"] is False


def test_zero_is_finite_zero() -> None:
    result = eval_madhava_bound({"x": 0, "N": 1})
    assert result["allow"] is True
    assert result["remainderBound"] == 0.0
    assert result["remainderBoundState"] == "FINITE"
    assert result["lambdaScore"] == 1.0


def test_underflow_does_not_report_a_perfect_lambda() -> None:
    result = eval_madhava_bound({"x": 0.5, "N": 600}, {"threshold": 0.01})
    assert result["remainderBoundState"] == "SUBNORMAL_OR_UNDERFLOW"
    assert result["remainderBound"] == 0.0
    assert result["allow"] is True
    assert result["lambdaScore"] is None
    assert result["accuracyClaim"] == "NOT_ASSERTED"
    assert "sufficiently converged" not in result["rationale"]


def test_rejects_bools_strings_and_domain_edges() -> None:
    with pytest.raises(GateError):
        eval_madhava_bound({"x": True, "N": 1})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 0.5, "N": True})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 0.5, "N": 0})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 0.5, "N": 10001})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 1.2, "N": 2})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 0.5, "N": 5}, {"threshold": "0.01"})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 0.5, "N": 5}, {"threshold": True})
    with pytest.raises(GateError):
        eval_madhava_bound({"x": 0.5, "N": 5}, {"threshold": 0})
