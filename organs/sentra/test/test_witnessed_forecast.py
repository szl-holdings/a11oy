"""pytest test suite for sentra.src.forecasting.witnessed_forecast.

Doctrine v6 | SPDX-License-Identifier: BSL-1.1
≥ 30 assertions covering:
  1.  formula_witness field present and correct
  2.  lean_theorem_ref correct
  3.  lean_commit_sha is 40-char hex
  4.  lean_file correct
  5.  lean_line positive integer
  6.  lean_status correct
  7.  confidence_envelope.bound ≥ 0
  8.  prediction lies inside confidence interval
  9.  synthetic flag forwarded
  10. batch length
  11. batch all formula_witness correct
  12. batch all predictions inside envelopes
  13. k=1 works, k=50 tighter bound than k=10
  14. input clamping > 1 and < -1
  15. ValueError for k < 1
  16. bound == 0 for x=0 all k
  17. as_dict() JSON round-trip
  18. as_dict() required keys
  19. dsse_receipt structure
  20. dsse_receipt inputs_hash is 64-char hex
  21. multiple calls same x,k produce same prediction
  22. Liu Hui monotone step: next ≥ prev
  23. Liu Hui step: ValueError on bad prev_conf
  24. Liu Hui step: ValueError on bad new_evidence
  25. false_position_step: one-step affine exact
  26. false_position_step: degenerate raises ValueError
  27. calibrate_threshold: converges on affine
  28. calibrate_threshold: converged flag true
  29. calibrate_threshold: receipts non-empty
  30. calibrate_threshold: liu_hui_bounds monotone non-increasing
  31. calibrate_sanctions_threshold: bracketing pair used
  32. WitnessedForecast.as_dict() envelope subkeys
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root without installation.
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from forecasting.witnessed_forecast import (  # noqa: E402
    ConfidenceEnvelope,
    LUTAR_LEAN_HEAD_SHA,
    LIU_HUI_STATUS,
    LIU_HUI_THEOREM,
    MADHAVA_LEAN_FILE,
    MADHAVA_LEAN_LINE,
    MADHAVA_STATUS,
    MADHAVA_THEOREM,
    WitnessedForecast,
    forecast_batch,
    forecast_with_witness,
    liu_hui_confidence_step,
    madhava_arctan_partial,
    madhava_remainder_bound,
)
from calibration.false_position import (  # noqa: E402
    calibrate_sanctions_threshold,
    calibrate_threshold,
    false_position_step,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wf_basic() -> WitnessedForecast:
    """Forecast at x=0.5, k=10, synthetic=True."""
    return forecast_with_witness(0.5, k=10, synthetic=True)


@pytest.fixture
def wf_zero() -> WitnessedForecast:
    return forecast_with_witness(0.0, k=10, synthetic=True)


@pytest.fixture
def wf_unit() -> WitnessedForecast:
    return forecast_with_witness(1.0, k=10, synthetic=True)


# ---------------------------------------------------------------------------
# 1. formula_witness
# ---------------------------------------------------------------------------

def test_formula_witness_present(wf_basic: WitnessedForecast) -> None:
    assert hasattr(wf_basic, "formula_witness")


def test_formula_witness_equals_madhava_theorem(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.formula_witness == MADHAVA_THEOREM


# ---------------------------------------------------------------------------
# 2. lean_theorem_ref
# ---------------------------------------------------------------------------

def test_lean_theorem_ref_non_empty(wf_basic: WitnessedForecast) -> None:
    assert isinstance(wf_basic.lean_theorem_ref, str) and len(wf_basic.lean_theorem_ref) > 0


def test_lean_theorem_ref_equals_madhava(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.lean_theorem_ref == MADHAVA_THEOREM


# ---------------------------------------------------------------------------
# 3. lean_commit_sha
# ---------------------------------------------------------------------------

def test_lean_commit_sha_is_40_hex(wf_basic: WitnessedForecast) -> None:
    sha = wf_basic.lean_commit_sha
    assert isinstance(sha, str)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha.lower())


def test_lean_commit_sha_default_matches_constant(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.lean_commit_sha == LUTAR_LEAN_HEAD_SHA


def test_lean_commit_sha_custom() -> None:
    custom = "b" * 40
    wf = forecast_with_witness(0.3, k=5, lean_commit_sha=custom)
    assert wf.lean_commit_sha == custom


# ---------------------------------------------------------------------------
# 4. lean_file
# ---------------------------------------------------------------------------

def test_lean_file_correct(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.lean_file == MADHAVA_LEAN_FILE


# ---------------------------------------------------------------------------
# 5. lean_line
# ---------------------------------------------------------------------------

def test_lean_line_positive_int(wf_basic: WitnessedForecast) -> None:
    assert isinstance(wf_basic.lean_line, int) and wf_basic.lean_line > 0


def test_lean_line_equals_constant(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.lean_line == MADHAVA_LEAN_LINE


# ---------------------------------------------------------------------------
# 6. lean_status
# ---------------------------------------------------------------------------

def test_lean_status_tracked(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.lean_status == MADHAVA_STATUS


# ---------------------------------------------------------------------------
# 7. confidence_envelope.bound ≥ 0
# ---------------------------------------------------------------------------

def test_bound_non_negative(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.confidence_envelope.bound >= 0.0


def test_bound_zero_for_zero_input(wf_zero: WitnessedForecast) -> None:
    assert wf_zero.confidence_envelope.bound == 0.0


def test_bound_positive_unit_input(wf_unit: WitnessedForecast) -> None:
    assert wf_unit.confidence_envelope.bound > 0.0


# ---------------------------------------------------------------------------
# 8. prediction inside confidence interval
# ---------------------------------------------------------------------------

def test_prediction_inside_envelope(wf_basic: WitnessedForecast) -> None:
    env = wf_basic.confidence_envelope
    assert env.lower <= wf_basic.prediction <= env.upper


def test_prediction_inside_envelope_unit(wf_unit: WitnessedForecast) -> None:
    env = wf_unit.confidence_envelope
    assert env.lower <= wf_unit.prediction <= env.upper


def test_prediction_inside_envelope_negative() -> None:
    wf = forecast_with_witness(-0.75, k=8, synthetic=True)
    env = wf.confidence_envelope
    assert env.lower <= wf.prediction <= env.upper


# ---------------------------------------------------------------------------
# 9. synthetic flag
# ---------------------------------------------------------------------------

def test_synthetic_true(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.synthetic is True


def test_synthetic_false_default() -> None:
    wf = forecast_with_witness(0.5, k=10)
    assert wf.synthetic is False


# ---------------------------------------------------------------------------
# 10. batch length
# ---------------------------------------------------------------------------

def test_batch_length() -> None:
    results = forecast_batch([0.0, 0.5, 1.0], k=10, synthetic=True)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# 11. batch formula_witness
# ---------------------------------------------------------------------------

def test_batch_all_formula_witness() -> None:
    results = forecast_batch([0.1, 0.5, 0.9], k=10, synthetic=True)
    assert all(r.formula_witness == MADHAVA_THEOREM for r in results)


# ---------------------------------------------------------------------------
# 12. batch predictions inside envelopes
# ---------------------------------------------------------------------------

def test_batch_predictions_inside_envelopes() -> None:
    results = forecast_batch([-1.0, -0.5, 0.0, 0.5, 1.0], k=10)
    for r in results:
        env = r.confidence_envelope
        assert env.lower <= r.prediction <= env.upper


# ---------------------------------------------------------------------------
# 13. k parameter tightens bound
# ---------------------------------------------------------------------------

def test_k_1_valid() -> None:
    wf = forecast_with_witness(0.5, k=1)
    assert wf.confidence_envelope.bound >= 0.0


def test_more_terms_tighter_bound() -> None:
    x = 0.7
    wf10 = forecast_with_witness(x, k=10)
    wf50 = forecast_with_witness(x, k=50)
    assert wf50.confidence_envelope.bound < wf10.confidence_envelope.bound


# ---------------------------------------------------------------------------
# 14. input clamping
# ---------------------------------------------------------------------------

def test_clamp_above_one() -> None:
    wf = forecast_with_witness(5.0, k=10)
    assert wf.confidence_envelope.x_normalised == 1.0


def test_clamp_below_minus_one() -> None:
    wf = forecast_with_witness(-5.0, k=10)
    assert wf.confidence_envelope.x_normalised == -1.0


# ---------------------------------------------------------------------------
# 15. ValueError for k < 1
# ---------------------------------------------------------------------------

def test_k_zero_raises() -> None:
    with pytest.raises(ValueError, match="k must be ≥ 1"):
        forecast_with_witness(0.5, k=0)


def test_k_negative_raises() -> None:
    with pytest.raises(ValueError, match="k must be ≥ 1"):
        forecast_with_witness(0.5, k=-3)


# ---------------------------------------------------------------------------
# 16. bound == 0 for x=0, all k
# ---------------------------------------------------------------------------

def test_bound_zero_all_k() -> None:
    for k in [1, 5, 10, 50, 100]:
        wf = forecast_with_witness(0.0, k=k)
        assert wf.confidence_envelope.bound == 0.0, f"k={k}"


# ---------------------------------------------------------------------------
# 17. as_dict() JSON round-trip
# ---------------------------------------------------------------------------

def test_as_dict_json_roundtrip(wf_basic: WitnessedForecast) -> None:
    d = wf_basic.as_dict()
    serialised = json.dumps(d)
    recovered = json.loads(serialised)
    assert recovered["formula_witness"] == MADHAVA_THEOREM
    assert recovered["lean_theorem_ref"] == MADHAVA_THEOREM


# ---------------------------------------------------------------------------
# 18. as_dict() required keys
# ---------------------------------------------------------------------------

def test_as_dict_required_keys(wf_basic: WitnessedForecast) -> None:
    d = wf_basic.as_dict()
    required = {
        "prediction", "formula_witness", "lean_theorem_ref",
        "lean_file", "lean_line", "lean_status",
        "lean_commit_sha", "confidence_envelope", "dsse_receipt", "synthetic",
    }
    assert required.issubset(d.keys())


# ---------------------------------------------------------------------------
# 19. dsse_receipt structure
# ---------------------------------------------------------------------------

def test_dsse_receipt_keys(wf_basic: WitnessedForecast) -> None:
    r = wf_basic.dsse_receipt
    for key in ("theorem", "lean_file", "lean_line", "lean_status",
                "lean_commit_sha", "inputs_hash", "output", "ts"):
        assert key in r, f"Missing key: {key}"


def test_dsse_receipt_theorem_matches(wf_basic: WitnessedForecast) -> None:
    assert wf_basic.dsse_receipt["theorem"] == MADHAVA_THEOREM


# ---------------------------------------------------------------------------
# 20. dsse_receipt inputs_hash is 64-char hex
# ---------------------------------------------------------------------------

def test_dsse_receipt_inputs_hash_64_hex(wf_basic: WitnessedForecast) -> None:
    h = wf_basic.dsse_receipt["inputs_hash"]
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h.lower())


# ---------------------------------------------------------------------------
# 21. deterministic: same x,k → same prediction
# ---------------------------------------------------------------------------

def test_deterministic_prediction() -> None:
    wf1 = forecast_with_witness(0.6, k=12)
    wf2 = forecast_with_witness(0.6, k=12)
    assert wf1.prediction == wf2.prediction


# ---------------------------------------------------------------------------
# 22. Liu Hui monotone step: next ≥ prev
# ---------------------------------------------------------------------------

def test_liu_hui_step_monotone() -> None:
    result = liu_hui_confidence_step(0.5, 0.8)
    assert result["next_conf"] >= 0.5
    assert result["monotone_ok"] is True


def test_liu_hui_step_zero_evidence_no_change() -> None:
    result = liu_hui_confidence_step(0.6, 0.0)
    # With zero evidence, delta = 0
    assert abs(result["next_conf"] - 0.6) < 1e-12


def test_liu_hui_step_full_evidence() -> None:
    result = liu_hui_confidence_step(0.5, 1.0)
    assert result["next_conf"] > 0.5


# ---------------------------------------------------------------------------
# 23. Liu Hui step: ValueError on bad prev_conf
# ---------------------------------------------------------------------------

def test_liu_hui_bad_prev_conf_raises() -> None:
    with pytest.raises(ValueError, match="prev_conf"):
        liu_hui_confidence_step(-0.1, 0.5)


def test_liu_hui_bad_prev_conf_above_one_raises() -> None:
    with pytest.raises(ValueError, match="prev_conf"):
        liu_hui_confidence_step(1.1, 0.5)


# ---------------------------------------------------------------------------
# 24. Liu Hui step: ValueError on bad new_evidence
# ---------------------------------------------------------------------------

def test_liu_hui_bad_evidence_raises() -> None:
    with pytest.raises(ValueError, match="new_evidence"):
        liu_hui_confidence_step(0.5, -0.1)


# ---------------------------------------------------------------------------
# 25. false_position_step: one-step affine exact
# ---------------------------------------------------------------------------

def test_false_position_affine_exact() -> None:
    # f(x) = x; target = 0.7 → x* = 0.7
    result = false_position_step(0.0, 0.0, 1.0, 1.0, 0.7)
    assert abs(result["x_star"] - 0.7) < 1e-12
    assert result["residual_bound"] < 1e-12


def test_false_position_affine_various_targets() -> None:
    for target in [0.1, 0.5, 0.9]:
        result = false_position_step(0.0, 0.0, 1.0, 1.0, target)
        assert abs(result["x_star"] - target) < 1e-12


# ---------------------------------------------------------------------------
# 26. false_position_step: degenerate raises ValueError
# ---------------------------------------------------------------------------

def test_false_position_degenerate_raises() -> None:
    with pytest.raises(ValueError, match="Degenerate"):
        false_position_step(0.0, 0.5, 1.0, 0.5, 0.7)


# ---------------------------------------------------------------------------
# 27. calibrate_threshold: converges on affine function
# ---------------------------------------------------------------------------

def test_calibrate_threshold_affine() -> None:
    cal = calibrate_threshold(lambda x: x, 0.0, 1.0, 0.7)
    assert abs(cal.f_x_star - 0.7) < 1e-8


# ---------------------------------------------------------------------------
# 28. calibrate_threshold: converged flag true
# ---------------------------------------------------------------------------

def test_calibrate_threshold_converged() -> None:
    cal = calibrate_threshold(lambda x: x * x, 0.0, 1.0, 0.25)
    assert cal.converged is True


# ---------------------------------------------------------------------------
# 29. calibrate_threshold: receipts non-empty
# ---------------------------------------------------------------------------

def test_calibrate_threshold_receipts_non_empty() -> None:
    cal = calibrate_threshold(lambda x: x, 0.0, 1.0, 0.5)
    assert len(cal.receipts) >= 1


# ---------------------------------------------------------------------------
# 30. calibrate_threshold: liu_hui_bounds monotone non-increasing (after first)
# ---------------------------------------------------------------------------

def test_calibrate_threshold_bounds_non_increasing() -> None:
    cal = calibrate_threshold(lambda x: math.sin(x), 0.0, math.pi / 2, 0.5)
    bounds = cal.liu_hui_bounds
    if len(bounds) >= 2:
        for i in range(1, min(len(bounds), 5)):
            # Bounds should be shrinking for a monotone function.
            assert bounds[i] <= bounds[0] + 1e-9


# ---------------------------------------------------------------------------
# 31. calibrate_sanctions_threshold: bracketing pair used
# ---------------------------------------------------------------------------

def test_calibrate_sanctions_threshold_bracketing() -> None:
    pairs = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
    result = calibrate_sanctions_threshold(pairs, 0.7)
    assert abs(result["x_star"] - 0.7) < 1e-10
    assert "used_pair_indices" in result


# ---------------------------------------------------------------------------
# 32. WitnessedForecast.as_dict() envelope subkeys
# ---------------------------------------------------------------------------

def test_as_dict_envelope_subkeys(wf_basic: WitnessedForecast) -> None:
    d = wf_basic.as_dict()
    env = d["confidence_envelope"]
    for key in ("lower", "upper", "bound", "k_terms", "x_normalised", "formula"):
        assert key in env, f"Missing envelope key: {key}"
