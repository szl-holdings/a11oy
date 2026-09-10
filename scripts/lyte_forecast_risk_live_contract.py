# SPDX-License-Identifier: Apache-2.0
"""Independent, advisory-only risk-window checks for the canonical publisher.

No producer imports, model downloads, credentials, or provider writes. A healthy
old forecast endpoint that ignores ``risk`` must fail this additional contract.
The bounded fixtures are synthetic; passing is not production calibration.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from typing import Any, Callable

PREFIX = "/api/lyte/v2"
QUANTILES = (0.1, 0.5, 0.9)
KEYS = ("q10", "q50", "q90")
PAYLOAD = {
    "signal_id": "qualification.risk-window-publisher",
    "values": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    "horizon": 3,
    "quantiles": list(QUANTILES),
    "provider": "baseline",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def finite_number(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))


def risk_response_matches(body: Any, payload: dict[str, Any]) -> bool:
    """Recompute the fixed probe's request, forecast, risk, and receipt bindings.

    The checker intentionally supports only the canonical probe's three
    quantiles. It independently derives conservative marginal event bounds,
    rather than trusting a producer's self-reported hash or a copied model.
    """
    try:
        if not isinstance(body, dict) or body.get("execution_authority") != "NONE":
            return False
        receipt, points, risk = body["receipt"], body["points"], body["risk_window"]
        rule = payload["risk"]
        if not all(isinstance(x, dict) for x in (receipt, risk, rule)):
            return False
        if payload.get("quantiles") != list(QUANTILES) or payload.get("provider") != "baseline":
            return False
        if (rule.get("direction") not in {"above", "below"}
                or not finite_number(rule.get("threshold"))
                or not finite_number(rule.get("alert_level"))
                or not 0 < rule["alert_level"] <= 1):
            return False
        horizon = payload["horizon"]
        if type(horizon) is not int or not 1 <= horizon <= 1024:
            return False
        values = payload["values"]
        if not isinstance(values, list) or not values or len(values) > 8192:
            return False
        if not all(finite_number(v) for v in values):
            return False
        basis = {
            "contract": "szl.lyte.forecast-loom/v1",
            "signal_id": payload["signal_id"],
            "values": [float(v) for v in values],
            "horizon": horizon, "quantiles": list(QUANTILES),
        }
        for name, expected in {
            "contract": basis["contract"], "signal_id": basis["signal_id"],
            "provider": "szl.robust-drift/v1", "horizon": horizon,
            "quantiles": list(QUANTILES), "context_points": len(values),
            "original_context_points": len(values), "truncated_points": 0,
            "imputed_points": 0, "input_sha256": digest(basis),
            "raw_input_sha256": digest(basis), "output_sha256": digest(points),
        }.items():
            if receipt.get(name) != expected:
                return False
        if not isinstance(points, list) or len(points) != horizon:
            return False
        expected_rows = []
        for step, point in enumerate(points, 1):
            row = point["quantiles"]
            if type(point["step"]) is not int or point["step"] != step or set(row) != set(KEYS):
                return False
            predicted = [row[key] for key in KEYS]
            if not all(finite_number(v) for v in predicted) or predicted != sorted(predicted):
                return False
            lower, upper = 0.0, 1.0
            for q, prediction in zip(QUANTILES, predicted, strict=True):
                if rule["direction"] == "above":
                    tail = float(Decimal(1) - Decimal(str(q)))
                    if prediction <= rule["threshold"]:
                        upper = min(upper, tail)
                    else:
                        lower = max(lower, tail)
                elif prediction < rule["threshold"]:
                    lower = max(lower, q)
                else:
                    upper = min(upper, q)
            crosses = (row["q50"] > rule["threshold"] if rule["direction"] == "above"
                       else row["q50"] < rule["threshold"])
            expected_rows.append({
                "step": step, "model_implied_breach_lower": lower,
                "model_implied_breach_upper": upper, "median_crosses": crosses,
            })
        expected_fields = {
            "contract": "szl.lyte.forecast-risk-window/v1",
            "signal_id": payload["signal_id"], "provider": receipt["provider"],
            "rule": rule,
            "event_semantics": ("STRICT_GREATER_THAN" if rule["direction"] == "above"
                                else "STRICT_LESS_THAN"),
            "time_unit": "FORECAST_STEPS_NOT_WALL_CLOCK",
            "steps": expected_rows,
            "earliest_possible_alert_step": next((r["step"] for r in expected_rows
                if r["model_implied_breach_upper"] >= rule["alert_level"]), None),
            "earliest_supported_alert_step": next((r["step"] for r in expected_rows
                if r["model_implied_breach_lower"] >= rule["alert_level"]), None),
            "first_median_crossing_step": next((r["step"] for r in expected_rows
                if r["median_crosses"]), None),
            "any_breach_over_horizon": {
                "lower": max(r["model_implied_breach_lower"] for r in expected_rows),
                "upper": min(1.0, math.fsum(r["model_implied_breach_upper"] for r in expected_rows)),
                "method": "MARGINAL_MAX_LOWER_UNION_SUM_UPPER_NO_INDEPENDENCE_ASSUMPTION",
            },
            "forecast_receipt_sha256": digest(receipt),
            "forecast_output_sha256": receipt["output_sha256"],
            "calibration_status": "NOT_ESTABLISHED", "production_admitted": False,
            "execution_authority": "NONE",
        }
        # Canonical JSON distinguishes booleans from numbers (True is not step 1).
        if any(digest(risk.get(k)) != digest(v) for k, v in expected_fields.items()):
            return False
        limitations = risk.get("limitations")
        if not isinstance(limitations, list) or not limitations or not all(
            isinstance(value, str) and value for value in limitations
        ):
            return False
        return risk.get("report_sha256") == digest({k: v for k, v in risk.items()
                                                   if k != "report_sha256"})
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return False


def verify_risk_contract(request_json: Callable[..., tuple[int, Any]]) -> dict[str, Any]:
    """Exercise actual advisory POSTs and preserve all failed observations."""
    checks: dict[str, bool] = {}
    observations: dict[str, Any] = {}

    def observe(name: str, path: str, payload: dict[str, Any] | None = None,
                expected: int = 200) -> dict[str, Any]:
        try:
            status, body = (request_json(path) if payload is None else request_json(
                path, method="POST", payload=payload, expected_statuses=(expected,),
            ))
            checks[name + " status"] = status == expected and isinstance(body, dict)
            observations[name] = {"http_status": status, "body": body}
            return body if isinstance(body, dict) else {}
        except Exception as exc:
            checks[name + " status"] = False
            observations[name] = {"http_status": None, "error_type": type(exc).__name__}
            return {}

    before = observe("receipts before risk", f"{PREFIX}/receipts")
    responses = {}
    for name, direction, threshold in (("above", "above", 10.0), ("repeat", "above", 10.0),
                                       ("below", "below", 10.0), ("changed policy", "above", 20.0)):
        payload = {**PAYLOAD, "risk": {
            "threshold": threshold, "direction": direction, "alert_level": 0.8,
        }}
        body = observe(name, f"{PREFIX}/forecast", payload)
        checks[name + " independent risk binding"] = risk_response_matches(body, payload)
        responses[name] = body
    checks["risk deterministic repeat"] = (
        checks["above independent risk binding"] and responses["above"] == responses["repeat"]
    )
    checks["policy changes risk not forecast"] = bool(
        checks["above independent risk binding"] and checks["changed policy independent risk binding"]
        and responses["above"].get("receipt") == responses["changed policy"].get("receipt")
        and responses["above"].get("risk_window", {}).get("report_sha256")
        != responses["changed policy"].get("risk_window", {}).get("report_sha256")
    )
    for name, rule in (
        ("nonfinite threshold rejected", {"threshold": "NaN"}),
        ("unknown risk authority rejected", {"threshold": 10, "execute": True}),
    ):
        body = observe(name, f"{PREFIX}/forecast", {**PAYLOAD, "risk": rule}, 422)
        checks[name + " validation detail"] = isinstance(body.get("detail"), list) and bool(body["detail"])
    after = observe("receipts after risk", f"{PREFIX}/receipts")
    checks["risk advisory calls do not persist receipts"] = (
        type(before.get("count")) is int and type(after.get("count")) is int
        and before["count"] == after["count"]
    )
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "szl.lyte-risk-live-contract/v1", "complete": not failed,
        "checks": checks, "failed_checks": failed, "observations": observations,
        "data_mode": "SYNTHETIC_PROBE", "production_telemetry_verified": False,
        "production_granite_admitted": False, "calibration_status": "NOT_ESTABLISHED",
        "execution_authority": "NONE", "credentials_used": False,
    }
