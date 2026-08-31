"""pytest test suite for sentra.src.forecasts.witnessed.

Phase 1 Track 2a — L7 witnessed forecasting.
SPDX-License-Identifier: BSL-1.1

Tests cover:
  1. formula_witness field is present and equals 'madhava_bound'
  2. lean_theorem_ref is non-empty and matches expected Lean theorem
  3. lean_commit_sha is a 40-char hex string
  4. confidence_envelope.bound is non-negative
  5. prediction lies inside the confidence interval
  6. synthetic flag is forwarded correctly
  7. batch forecast populates all fields on every element
  8. k parameter affects the bound (more terms → tighter bound for |x| < 1)
  9. input clamping to [-1, 1]
  10. ValueError raised for k < 1
  11. bound == 0 when input_value == 0
  12. as_dict() is JSON-round-trippable with all required keys
"""
from __future__ import annotations

import json
import math
import pytest

from forecasts.witnessed import (
    WitnessedForecast,
    ConfidenceEnvelope,
    forecast_with_madhava_bound,
    forecast_batch,
    MADHAVA_FORMULA_ID,
    MADHAVA_THEOREM_REF,
    LUTAR_LEAN_HEAD_SHA,
    _madhava_remainder_bound,
    _madhava_arctan_partial,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def basic_forecast() -> WitnessedForecast:
    """A simple witnessed forecast at x=0.5, k=10 (synthetic: true)."""
    return forecast_with_madhava_bound(0.5, k=10, synthetic=True)


@pytest.fixture
def zero_input_forecast() -> WitnessedForecast:
    return forecast_with_madhava_bound(0.0, k=10, synthetic=True)


@pytest.fixture
def unit_input_forecast() -> WitnessedForecast:
    return forecast_with_madhava_bound(1.0, k=10, synthetic=True)


# ---------------------------------------------------------------------------
# 1. formula_witness field
# ---------------------------------------------------------------------------

def test_formula_witness_present(basic_forecast: WitnessedForecast) -> None:
    """formula_witness must be present and equal the anchor slug."""
    assert hasattr(basic_forecast, "formula_witness")
    assert basic_forecast.formula_witness == "madhava_bound"


def test_formula_witness_is_madhava_formula_id(basic_forecast: WitnessedForecast) -> None:
    assert basic_forecast.formula_witness == MADHAVA_FORMULA_ID


# ---------------------------------------------------------------------------
# 2. lean_theorem_ref
# ---------------------------------------------------------------------------

def test_lean_theorem_ref_non_empty(basic_forecast: WitnessedForecast) -> None:
    """lean_theorem_ref must be a non-empty string."""
    assert isinstance(basic_forecast.lean_theorem_ref, str)
    assert len(basic_forecast.lean_theorem_ref) > 0


def test_lean_theorem_ref_matches_madhava(basic_forecast: WitnessedForecast) -> None:
    """lean_theorem_ref must point to the Lutar.PACBayes.MadhavaBound theorem."""
    assert basic_forecast.lean_theorem_ref == (
        "Lutar.PACBayes.MadhavaBound.madhava_alt_series_bound"
    )


def test_lean_theorem_ref_is_constant(basic_forecast: WitnessedForecast) -> None:
    assert basic_forecast.lean_theorem_ref == MADHAVA_THEOREM_REF


# ---------------------------------------------------------------------------
# 3. lean_commit_sha
# ---------------------------------------------------------------------------

def test_lean_commit_sha_is_40_hex(basic_forecast: WitnessedForecast) -> None:
    """lean_commit_sha must be a 40-character hexadecimal string."""
    sha = basic_forecast.lean_commit_sha
    assert isinstance(sha, str)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha.lower())


def test_lean_commit_sha_default_matches_constant(basic_forecast: WitnessedForecast) -> None:
    assert basic_forecast.lean_commit_sha == LUTAR_LEAN_HEAD_SHA


def test_lean_commit_sha_custom() -> None:
    """Custom SHA is forwarded unchanged."""
    custom_sha = "a" * 40
    wf = forecast_with_madhava_bound(0.5, k=5, lean_commit_sha=custom_sha)
    assert wf.lean_commit_sha == custom_sha


# ---------------------------------------------------------------------------
# 4. confidence_envelope.bound is non-negative
# ---------------------------------------------------------------------------

def test_bound_non_negative(basic_forecast: WitnessedForecast) -> None:
    assert basic_forecast.confidence_envelope.bound >= 0.0


def test_bound_zero_for_zero_input(zero_input_forecast: WitnessedForecast) -> None:
    """When input is 0, the remainder bound is exactly 0 (|0|^(2k+1) = 0)."""
    assert zero_input_forecast.confidence_envelope.bound == 0.0


def test_bound_positive_for_unit_input(unit_input_forecast: WitnessedForecast) -> None:
    """When |x| = 1, the remainder bound is strictly positive: 1 / (2k+1)."""
    assert unit_input_forecast.confidence_envelope.bound > 0.0


# ---------------------------------------------------------------------------
# 5. prediction lies inside confidence interval
# ---------------------------------------------------------------------------

def test_prediction_inside_envelope(basic_forecast: WitnessedForecast) -> None:
    env = basic_forecast.confidence_envelope
    assert env.lower <= basic_forecast.prediction <= env.upper


def test_prediction_inside_envelope_unit_input(unit_input_forecast: WitnessedForecast) -> None:
    env = unit_input_forecast.confidence_envelope
    assert env.lower <= unit_input_forecast.prediction <= env.upper


def test_prediction_inside_envelope_negative_input() -> None:
    wf = forecast_with_madhava_bound(-0.75, k=8, synthetic=True)
    env = wf.confidence_envelope
    assert env.lower <= wf.prediction <= env.upper


# ---------------------------------------------------------------------------
# 6. synthetic flag
# ---------------------------------------------------------------------------

def test_synthetic_flag_true(basic_forecast: WitnessedForecast) -> None:
    assert basic_forecast.synthetic is True


def test_synthetic_flag_false_by_default() -> None:
    wf = forecast_with_madhava_bound(0.5, k=10)
    assert wf.synthetic is False


# ---------------------------------------------------------------------------
# 7. batch forecast
# ---------------------------------------------------------------------------

def test_batch_length() -> None:
    results = forecast_batch([0.0, 0.5, 1.0], k=10, synthetic=True)
    assert len(results) == 3


def test_batch_all_have_formula_witness() -> None:
    results = forecast_batch([0.1, 0.5, 0.9], k=10, synthetic=True)
    assert all(r.formula_witness == MADHAVA_FORMULA_ID for r in results)


def test_batch_all_have_valid_sha() -> None:
    results = forecast_batch([0.0, 0.5], k=5, synthetic=True)
    assert all(len(r.lean_commit_sha) == 40 for r in results)


def test_batch_all_predictions_inside_envelopes() -> None:
    results = forecast_batch([-1.0, -0.5, 0.0, 0.5, 1.0], k=10)
    for r in results:
        assert r.confidence_envelope.lower <= r.prediction <= r.confidence_envelope.upper


# ---------------------------------------------------------------------------
# 8. k parameter tightens bound
# ---------------------------------------------------------------------------

def test_more_terms_tighter_bound() -> None:
    """For |x| < 1, a higher k gives a strictly smaller bound."""
    x = 0.7
    wf_10 = forecast_with_madhava_bound(x, k=10)
    wf_20 = forecast_with_madhava_bound(x, k=20)
    assert wf_20.confidence_envelope.bound < wf_10.confidence_envelope.bound


# ---------------------------------------------------------------------------
# 9. input clamping
# ---------------------------------------------------------------------------

def test_input_clamped_above_one() -> None:
    """Values > 1 are clamped to 1; bound equals 1/(2k+1)."""
    wf = forecast_with_madhava_bound(5.0, k=10)
    assert wf.confidence_envelope.x_normalised == 1.0


def test_input_clamped_below_minus_one() -> None:
    wf = forecast_with_madhava_bound(-5.0, k=10)
    assert wf.confidence_envelope.x_normalised == -1.0


# ---------------------------------------------------------------------------
# 10. ValueError for k < 1
# ---------------------------------------------------------------------------

def test_k_zero_raises() -> None:
    with pytest.raises(ValueError, match="k must be ≥ 1"):
        forecast_with_madhava_bound(0.5, k=0)


def test_k_negative_raises() -> None:
    with pytest.raises(ValueError, match="k must be ≥ 1"):
        forecast_with_madhava_bound(0.5, k=-3)


# ---------------------------------------------------------------------------
# 11. bound == 0 when input_value == 0
# ---------------------------------------------------------------------------

def test_bound_zero_input_all_k() -> None:
    """|0|^(2k+1) / (2k+1) = 0 for all k."""
    for k in [1, 5, 10, 50]:
        wf = forecast_with_madhava_bound(0.0, k=k)
        assert wf.confidence_envelope.bound == 0.0


# ---------------------------------------------------------------------------
# 12. as_dict() JSON round-trip
# ---------------------------------------------------------------------------

def test_as_dict_json_serialisable(basic_forecast: WitnessedForecast) -> None:
    d = basic_forecast.as_dict()
    serialised = json.dumps(d)
    recovered = json.loads(serialised)
    assert recovered["formula_witness"] == "madhava_bound"
    assert recovered["lean_theorem_ref"] == MADHAVA_THEOREM_REF


def test_as_dict_required_keys(basic_forecast: WitnessedForecast) -> None:
    """as_dict() must contain all keys required by the anatomy-alive harness."""
    d = basic_forecast.as_dict()
    required = {
        "prediction",
        "formula_witness",
        "lean_theorem_ref",
        "lean_commit_sha",
        "confidence_envelope",
        "synthetic",
    }
    assert required.issubset(d.keys())


def test_as_dict_envelope_keys(basic_forecast: WitnessedForecast) -> None:
    d = basic_forecast.as_dict()
    env = d["confidence_envelope"]
    assert "lower" in env
    assert "upper" in env
    assert "bound" in env
    assert "k_terms" in env
    assert env["formula"] == MADHAVA_FORMULA_ID
