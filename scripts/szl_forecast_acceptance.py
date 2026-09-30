"""Independent additive public Forecast Loom/risk/workbench HTTP verification.

Use together with A11oy's EXISTING complete live contract and image attestor.
This is not a replacement for tenant, browser, metrics, production, or model
qualification. It never imports the producer forecasting implementation.
Public requests use fixed origins, no tokens, no redirects, and bounded bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from szl_release_guard import ContractError, canonical, digest, immutable_json, sha, strict_json, utc_now

ORIGIN = "https://szlholdings-lyte.hf.space"
PREFIX = "/api/lyte/v2/forecast"
INPUT = {"signal_id": "qualification.upgrade-v2", "values": [10.0, 11.0, None, 13.0, 14.0],
         "horizon": 3, "quantiles": [0.1, 0.5, 0.9], "provider": "baseline",
         "risk": {"threshold": 14.0, "direction": "above", "alert_level": 0.5}}
PAYLOAD_CAP = 2_000_000


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ContractError(reason)


def finite(value: Any) -> float:
    require(type(value) in (int, float) and math.isfinite(value), "INVALID_FINITE_NUMBER")
    return float(value)


def quantile_label(value: float) -> str:
    text = format(Decimal(str(value)) * 100, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    whole, dot, fraction = text.partition(".")
    return "q" + whole.zfill(2) + dot + fraction


def validate_forecast(body: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    require(isinstance(body, Mapping), "FORECAST_NOT_OBJECT")
    require(body.get("execution_authority") == "NONE", "AUTHORITY_ESCALATION")
    points, receipt = body.get("points"), body.get("receipt")
    require(isinstance(points, list) and isinstance(receipt, dict), "FORECAST_SHAPE")
    horizon = request["horizon"]
    require(type(horizon) is int and 1 <= horizon <= 1024 and len(points) == horizon, "HORIZON")
    require(receipt.get("provider") == "szl.robust-drift/v1", "BASELINE_NOT_OBSERVED")
    require(receipt.get("contract") == "szl.lyte.forecast-loom/v1", "FORECAST_SCHEMA")
    qs = request["quantiles"]
    require(receipt.get("quantiles") == qs and receipt.get("signal_id") == request["signal_id"]
            and type(receipt.get("horizon")) is int and receipt["horizon"] == horizon, "REQUEST_BINDING")
    for step, point in enumerate(points, 1):
        require(type(point.get("step")) is int and point["step"] == step, "STEP_IDENTITY")
        row = point.get("quantiles")
        require(isinstance(row, dict) and set(row) == {quantile_label(q) for q in qs}, "QUANTILE_KEYS")
        values = [finite(row[quantile_label(q)]) for q in qs]
        require(values == sorted(values), "QUANTILE_CROSSING")
    require(receipt.get("output_sha256") == digest(points), "OUTPUT_DIGEST")
    # This verifier's fixture has one forward-filled missing observation.
    require(request["values"] in ([10.0, 11.0, None, 13.0, 14.0],
                                  [10.0, 11.0, 11.0, 13.0, 14.0]), "UNSUPPORTED_WITNESS_FIXTURE")
    filled = [10.0, 11.0, 11.0, 13.0, 14.0]
    basis = {"contract": "szl.lyte.forecast-loom/v1", "signal_id": request["signal_id"],
             "values": filled, "horizon": horizon, "quantiles": qs}
    require(receipt.get("input_sha256") == digest(basis), "PROCESSED_INPUT_DIGEST")
    require(receipt.get("raw_input_sha256") == digest({**basis, "values": request["values"]}),
            "RAW_INPUT_DIGEST")
    for key, expected in (("context_points", 5), ("original_context_points", 5),
                          ("truncated_points", 0), ("imputed_points", request["values"].count(None))):
        require(type(receipt.get(key)) is int and receipt[key] == expected, "CONTEXT_PROVENANCE")


def expected_risk(points: Sequence[Mapping[str, Any]], quantiles: Sequence[float],
                  rule: Mapping[str, Any]) -> dict[str, Any]:
    """Independent marginal brackets, preserving strict ties and dependence limits."""
    threshold, level = finite(rule["threshold"]), finite(rule["alert_level"])
    direction = rule["direction"]
    require(direction in ("above", "below") and 0 < level <= 1, "INVALID_RISK_RULE")
    rows = []
    for point in points:
        lower, upper = Decimal(0), Decimal(1)
        for q in quantiles:
            value = finite(point["quantiles"][quantile_label(q)])
            prob = Decimal(str(q))
            if direction == "above":
                if value > threshold:
                    lower = max(lower, 1 - prob)
                else:
                    upper = min(upper, 1 - prob)
            else:
                if value < threshold:
                    lower = max(lower, prob)
                else:
                    upper = min(upper, prob)
        median = point["quantiles"][quantile_label(0.5)]
        crosses = median > threshold if direction == "above" else median < threshold
        rows.append({"step": point["step"], "model_implied_breach_lower": float(lower),
                     "model_implied_breach_upper": float(upper), "median_crosses": crosses})

    def first(key):
        return next((r["step"] for r in rows if r[key] >= level), None)

    return {"steps": rows, "earliest_possible_alert_step": first("model_implied_breach_upper"),
            "earliest_supported_alert_step": first("model_implied_breach_lower"),
            "first_median_crossing_step": next((r["step"] for r in rows if r["median_crosses"]), None),
            "any_breach_over_horizon": {
                "lower": max(r["model_implied_breach_lower"] for r in rows),
                "upper": min(1.0, math.fsum(r["model_implied_breach_upper"] for r in rows)),
                "method": "MARGINAL_MAX_LOWER_UNION_SUM_UPPER_NO_INDEPENDENCE_ASSUMPTION"}}


def validate_risk(body: Mapping[str, Any], request: Mapping[str, Any]) -> None:
    validate_forecast(body, request)
    risk = body.get("risk_window")
    require(isinstance(risk, dict), "RISK_WINDOW_MISSING")
    require(risk.get("contract") == "szl.lyte.forecast-risk-window/v1", "RISK_SCHEMA")
    require(risk.get("execution_authority") == "NONE" and risk.get("production_admitted") is False
            and risk.get("calibration_status") == "NOT_ESTABLISHED", "RISK_AUTHORITY")
    require(canonical(risk.get("rule")) == canonical(request["risk"]), "RULE_BINDING")
    require(risk.get("time_unit") == "FORECAST_STEPS_NOT_WALL_CLOCK", "TIME_SEMANTICS")
    semantics = "STRICT_GREATER_THAN" if request["risk"]["direction"] == "above" else "STRICT_LESS_THAN"
    require(risk.get("event_semantics") == semantics, "STRICT_EVENT_SEMANTICS")
    for key, value in expected_risk(body["points"], request["quantiles"], request["risk"]).items():
        require(canonical(risk.get(key)) == canonical(value), "INDEPENDENT_RISK_MISMATCH")
    require(risk.get("signal_id") == body["receipt"]["signal_id"]
            and risk.get("provider") == body["receipt"]["provider"], "RISK_PROVIDER_BINDING")
    require(risk.get("forecast_output_sha256") == digest(body["points"]), "RISK_OUTPUT_BINDING")
    require(risk.get("forecast_receipt_sha256") == digest(body["receipt"]), "RISK_RECEIPT_BINDING")
    unsigned = {k: v for k, v in risk.items() if k != "report_sha256"}
    require(risk.get("report_sha256") == digest(unsigned), "RISK_REPORT_DIGEST")


def validate_envelope(envelope: Mapping[str, Any], request: Mapping[str, Any], source: str) -> None:
    sha(source)
    require(isinstance(envelope, Mapping), "ENVELOPE_NOT_OBJECT")
    require(envelope.get("schema") == "szl.lyte.forecast-inspection-envelope/v1", "ENVELOPE_SCHEMA")
    raw = envelope.get("canonical_json")
    require(isinstance(raw, str) and len(raw.encode()) <= PAYLOAD_CAP, "ENVELOPE_BYTES")
    require(envelope.get("sha256") == hashlib.sha256(raw.encode("utf-8")).hexdigest(), "ENVELOPE_DIGEST")
    require(envelope.get("hash_semantics") == "CONTENT_INTEGRITY_NOT_SIGNATURE_OR_ACCURACY", "HASH_SEMANTICS")
    body = strict_json(raw)
    require(body.get("schema") == "szl.lyte.forecast-inspection/v1", "INSPECTION_SCHEMA")
    require(body.get("source") == {"repository": "szl-holdings/lyte-services", "revision": source},
            "INSPECTION_SOURCE")
    require(canonical(body.get("request")) == canonical(request), "INSPECTION_REQUEST")
    require(body.get("execution_authority") == "NONE" and body.get("persisted") is False
            and body.get("input_provenance") == "CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED",
            "INSPECTION_AUTHORITY")
    validate_risk(body["forecast"], request)


def verify_extended_contract(request_json: Callable[..., tuple[int, Any]],
                             request_text: Callable[..., tuple[int, str]],
                             *, source: str) -> dict[str, Any]:
    """Do not import producer code to validate its own output."""
    sha(source)
    checks, observations = {}, {}

    def check(name, action):
        try:
            observation = action()
            checks[name] = True
            observations[name] = observation
        except Exception as exc:
            checks[name] = False
            # Do not echo upstream exception bodies or caller values.
            observations[name] = {"error_type": type(exc).__name__}

    def identity():
        status, obj = request_json("/api/build-info")
        require(status == 200 and isinstance(obj, dict), "BUILD_INFO_HTTP")
        require(obj.get("source_revision") == source and obj.get("runtime_source_revision") == source,
                "SOURCE_MISMATCH")
        require(obj.get("effectors_enabled") is False, "EFFECTORS_ENABLED")
        return {"http_status": status, "body_sha256": digest(obj), "source_revision": source}

    def capabilities():
        status, obj = request_json(PREFIX)
        require(status == 200 and isinstance(obj, dict), "CAPABILITIES_HTTP")
        require(obj.get("schema") == "szl.lyte.forecast-workbench/v1"
                and obj.get("workbench") == PREFIX + "/workbench"
                and obj.get("inspection") == PREFIX + "/inspect"
                and obj.get("inspection_provider") == "baseline"
                and obj.get("execution_authority") == "NONE", "CAPABILITIES_CONTRACT")
        return {"http_status": status, "body_sha256": digest(obj)}

    def workbench():
        status, text = request_text(PREFIX + "/workbench")
        require(status == 200 and isinstance(text, str) and "Forecast Loom" in text
                and "/static/lyte/forecast.mjs" in text, "WORKBENCH_HTTP")
        return {"http_status": status, "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "browser_interaction_verified": False}

    def forecast(direction):
        payload = {**INPUT, "risk": {**INPUT["risk"], "direction": direction}}
        code, obj = request_json(PREFIX, method="POST", payload=payload)
        require(code == 200, "FORECAST_HTTP")
        validate_risk(obj, payload)
        repeat_code, repeated = request_json(PREFIX, method="POST", payload=payload)
        require(repeat_code == 200 and canonical(repeated) == canonical(obj), "FORECAST_NOT_REPEATABLE")
        return {"http_status": code, "body_sha256": digest(obj), "repeat_matched": True}

    def inspection():
        code, obj = request_json(PREFIX + "/inspect", method="POST", payload=INPUT)
        require(code == 200, "INSPECTION_HTTP")
        validate_envelope(obj, INPUT, source)
        return {"http_status": code, "envelope_sha256": digest(obj)}

    def denial(path, payload, status, detail=None):
        code, obj = request_json(path, method="POST", payload=payload, expected_statuses=(status,))
        require(code == status and isinstance(obj, dict), "DENIAL_HTTP")
        if detail is not None:
            require(obj.get("detail") == detail, "DENIAL_SEMANTICS")
        return {"http_status": code, "body_sha256": digest(obj)}

    check("source-before", identity)
    check("capabilities", capabilities)
    check("workbench-document", workbench)
    check("risk-above-and-repeat", lambda: forecast("above"))
    check("risk-below-and-repeat", lambda: forecast("below"))
    check("inspection-envelope", inspection)
    check("reject-inspection-granite", lambda: denial(PREFIX + "/inspect", {**INPUT, "provider": "granite"}, 422))
    check("reject-inspection-no-risk", lambda: denial(PREFIX + "/inspect", {**INPUT, "risk": None}, 422))
    check("granite-production-withheld", lambda: denial(PREFIX, {**INPUT, "provider": "granite"}, 503,
           "Granite provider is not admitted in this deployment"))
    check("reject-zero-horizon", lambda: denial(PREFIX, {**INPUT, "horizon": 0}, 422))
    check("source-after", identity)
    return {"schema": "szl.lyte.extended-http-contract/v1", "source_revision": source,
            "observed_at": utc_now(), "checks": checks, "observations": observations,
            "http_contract_pass": all(checks.values()),
            "scope": "ADDITIVE_BASELINE_RISK_WORKBENCH_HTTP_ONLY",
            "browser_verified": False, "production_qualified": False,
            "provider_admitted": False, "execution_authority": "NONE"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicTransport:
    """Fixed public host. No cookie jar, bearer token, or implicit HF credential."""
    def __init__(self, *, seconds: float = 180):
        self.deadline = time.monotonic() + seconds
        self.opener = urllib.request.build_opener(NoRedirect())

    def fetch(self, path, *, method="GET", payload=None):
        require(isinstance(path, str) and path.startswith("/") and not path.startswith("//")
                and "?" not in path and "#" not in path and "\\" not in path, "UNSAFE_PUBLIC_PATH")
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "OBSERVATION_DEADLINE")
        headers = {"User-Agent": "SZL-Upgrade-V2-Public-Witness/1", "Cache-Control": "no-cache",
                   "Accept": "application/json,text/html;q=0.8"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(ORIGIN + path + "?szl_witness=" + str(time.time_ns()),
                                     headers=headers, method=method,
                                     data=None if payload is None else canonical(payload))
        try:
            response = self.opener.open(req, timeout=min(20, remaining))
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read(PAYLOAD_CAP + 1)
            require(len(raw) <= PAYLOAD_CAP, "PUBLIC_RESPONSE_TOO_LARGE")
            require(time.monotonic() <= self.deadline, "OBSERVATION_DEADLINE")
            return response.code, response.headers.get("Content-Type", ""), raw

    def json(self, path, *, method="GET", payload=None, **_):
        status, media, raw = self.fetch(path, method=method, payload=payload)
        require("application/json" in media.lower(), "JSON_MEDIA_TYPE_REQUIRED")
        return status, strict_json(raw)

    def text(self, path):
        status, media, raw = self.fetch(path)
        require("text/html" in media.lower(), "HTML_MEDIA_TYPE_REQUIRED")
        return status, raw.decode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    transport = PublicTransport()
    report = verify_extended_contract(transport.json, transport.text, source=args.source)
    file = immutable_json(args.output, report)
    print(json.dumps({"report": str(file), "http_contract_pass": report["http_contract_pass"],
                      "failed_checks": [k for k, v in report["checks"].items() if not v],
                      "production_qualified": False}, sort_keys=True))
    return 0 if report["http_contract_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
