"""Independent risk-publication regression controls, with no provider access."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "risk_publication_test", ROOT / "scripts" / "lyte_forecast_risk_live_contract.py",
)
assert SPEC is not None and SPEC.loader is not None
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


def fixture(direction="above", threshold=10.0):
    """Normative finite quantiles and explicit expected bounds, not a model."""
    payload = {**CONTRACT.PAYLOAD, "risk": {
        "threshold": threshold, "direction": direction, "alert_level": 0.8,
    }}
    points = [
        {"step": i, "quantiles": dict(zip(CONTRACT.KEYS, values, strict=True))}
        for i, values in enumerate(((5.0, 9.0, 13.0), (4.0, 10.0, 15.0),
                                    (4.0, 11.0, 18.0)), 1)
    ]
    basis = {"contract": "szl.lyte.forecast-loom/v1", **{
        k: payload[k] for k in ("signal_id", "values", "horizon", "quantiles")
    }}
    receipt = {
        "contract": basis["contract"], "signal_id": payload["signal_id"],
        "provider": "szl.robust-drift/v1", "horizon": 3, "context_points": 8,
        "original_context_points": 8, "truncated_points": 0, "imputed_points": 0,
        "quantiles": list(CONTRACT.QUANTILES), "input_sha256": CONTRACT.digest(basis),
        "raw_input_sha256": CONTRACT.digest(basis), "output_sha256": CONTRACT.digest(points),
        "confidence": 0.2305, "limitations": ["This is a test fixture."],
    }
    if threshold == 20.0:
        bounds = ((0.0, 0.1, False),) * 3
        possible, median, lower, upper = None, None, 0.0, 0.30000000000000004
    elif direction == "below":
        bounds = ((0.5, 0.9, True), (0.1, 0.5, False), (0.1, 0.5, False))
        possible, median, lower, upper = 1, 1, 0.5, 1.0
    else:
        bounds = ((0.1, 0.5, False), (0.1, 0.5, False), (0.5, 0.9, True))
        possible, median, lower, upper = 3, 3, 0.5, 1.0
    risk = {
        "contract": "szl.lyte.forecast-risk-window/v1", "signal_id": receipt["signal_id"],
        "provider": receipt["provider"], "rule": payload["risk"],
        "event_semantics": "STRICT_GREATER_THAN" if direction == "above" else "STRICT_LESS_THAN",
        "time_unit": "FORECAST_STEPS_NOT_WALL_CLOCK",
        "steps": [{"step": i, "model_implied_breach_lower": lo,
                   "model_implied_breach_upper": hi, "median_crosses": crosses}
                  for i, (lo, hi, crosses) in enumerate(bounds, 1)],
        "earliest_possible_alert_step": possible, "earliest_supported_alert_step": None,
        "first_median_crossing_step": median,
        "any_breach_over_horizon": {"lower": lower, "upper": upper,
            "method": "MARGINAL_MAX_LOWER_UNION_SUM_UPPER_NO_INDEPENDENCE_ASSUMPTION"},
        "forecast_receipt_sha256": CONTRACT.digest(receipt),
        "forecast_output_sha256": receipt["output_sha256"],
        "calibration_status": "NOT_ESTABLISHED", "production_admitted": False,
        "execution_authority": "NONE", "limitations": ["Conditional model bounds only."],
    }
    risk["report_sha256"] = CONTRACT.digest(risk)
    return {"points": points, "receipt": receipt, "risk_window": risk,
            "execution_authority": "NONE"}, payload


@pytest.mark.parametrize("direction,threshold", [("above", 10.0), ("below", 10.0), ("above", 20.0)])
def test_known_strict_bounds_and_policy_binding(direction, threshold):
    body, payload = fixture(direction, threshold)
    assert CONTRACT.risk_response_matches(body, payload)


@pytest.mark.parametrize("key,value", [
    ("calibration_status", "CALIBRATED"), ("production_admitted", True),
    ("production_admitted", 0), ("execution_authority", "EXECUTE"),
    ("time_unit", "HOURS"), ("event_semantics", "GREATER_OR_EQUAL"),
    ("earliest_supported_alert_step", 1), ("earliest_possible_alert_step", 2),
    ("first_median_crossing_step", 2), ("forecast_receipt_sha256", "a" * 64),
    ("forecast_output_sha256", "b" * 64), ("signal_id", "other"),
    ("provider", "granite"), ("contract", "unknown"), ("limitations", []),
])
def test_self_rehashed_false_claims_are_rejected(key, value):
    body, payload = fixture()
    body["risk_window"][key] = value
    risk = body["risk_window"]
    risk["report_sha256"] = CONTRACT.digest({k: v for k, v in risk.items() if k != "report_sha256"})
    assert not CONTRACT.risk_response_matches(body, payload)


@pytest.mark.parametrize("part", ["receipt", "risk_window", "points"])
def test_missing_response_component_fails(part):
    body, payload = fixture()
    del body[part]
    assert not CONTRACT.risk_response_matches(body, payload)


def test_altered_quantiles_fail_even_with_fresh_forecast_hash():
    body, payload = fixture()
    body["points"][0]["quantiles"]["q50"] = 100.0
    body["receipt"]["output_sha256"] = CONTRACT.digest(body["points"])
    assert not CONTRACT.risk_response_matches(body, payload)


def test_numeric_boolean_alert_step_is_not_an_integer():
    body, payload = fixture("below")
    risk = body["risk_window"]
    risk["earliest_possible_alert_step"] = True
    risk["report_sha256"] = CONTRACT.digest({k: v for k, v in risk.items() if k != "report_sha256"})
    assert not CONTRACT.risk_response_matches(body, payload)


def test_changed_request_cannot_reuse_valid_report():
    body, payload = fixture()
    payload = copy.deepcopy(payload)
    payload["values"][0] = 99.0
    assert not CONTRACT.risk_response_matches(body, payload)


class Transport:
    def __init__(self, *, legacy=False, persist=False, fail=False):
        self.calls = []
        self.legacy, self.persist, self.fail = legacy, persist, fail

    def __call__(self, path, *, method="GET", payload=None, expected_statuses=(200,)):
        self.calls.append((path, method, payload))
        if self.fail:
            raise TimeoutError("Transport detail must not be copied into evidence")
        if path.endswith("/receipts"):
            return 200, {"count": 2 if self.persist and len(self.calls) > 1 else 1}
        assert path == "/api/lyte/v2/forecast" and method == "POST"
        rule = payload["risk"]
        if rule.get("threshold") == "NaN" or "execute" in rule:
            return 422, {"detail": [{"type": "validation_error"}]}
        body, _ = fixture(rule["direction"], rule["threshold"])
        if self.legacy:
            del body["risk_window"]
        return 200, body


def test_complete_probe_uses_only_bounded_advisory_requests():
    transport = Transport()
    result = CONTRACT.verify_risk_contract(transport)
    assert result["complete"] is True and result["failed_checks"] == []
    assert len(transport.calls) == 8
    assert result["calibration_status"] == "NOT_ESTABLISHED"
    assert result["production_granite_admitted"] is False
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("options", [{"legacy": True}, {"persist": True}, {"fail": True}])
def test_old_runtime_persistence_or_transport_failure_never_passes(options):
    result = CONTRACT.verify_risk_contract(Transport(**options))
    assert result["complete"] is False and result["failed_checks"]
    assert "Transport detail" not in str(result)
