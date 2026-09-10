# SPDX-License-Identifier: Apache-2.0
"""Read-only verification of the source-owned Lyte 4 runtime and forecast API.

Transport functions are injected so every positive condition can be challenged
without a network. Advisory POSTs calculate results; authenticated ingest is
never attempted with credentials. This verifies the public SAMPLE deployment,
not a production telemetry installation, calibrated uncertainty, or an SLO.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable

PREFIX = "/api/lyte/v2"
IDENTITY_PATHS = (
    "/healthz", "/readyz", "/api/build-info", "/api/source",
    "/.well-known/szl-source.json",
)
CATALOG_PATHS = ("catalog", "capabilities", "anatomy", "formulas", "sources")
ENTITY_PATHS = (
    "services", "journeys", "outcomes", "agents", "incidents", "decisions",
    "playback", "second-brain", "evidence", "receipts",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_METRICS_BYTES = 2_000_000
_METRIC_NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"


def digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def identity_matches(body: Any, revision: str, version: str) -> bool:
    return bool(
        isinstance(body, dict)
        and body.get("source_repository") == "szl-holdings/lyte-services"
        and body.get("runtime_repository") == "szl-holdings/lyte-services"
        and body.get("source_revision") == revision
        and body.get("runtime_source_revision") == revision
        and body.get("version") == version
        and body.get("effectors_enabled") is False
        and body.get("human_approval_required") is True
    )


def metrics_identity_matches(body: Any, *, revision: str, version: str) -> bool:
    """Require the two source-owned gauges, not merely a nonempty HTTP 200.

    This is deliberately a bounded critical-gauge contract, not a general
    Prometheus parser or validation of every exported series. Other families
    are preserved. Required gauges may not be duplicated, timestamped, renamed,
    relabelled, replaced with comments, or populated with non-finite values.
    Run after readiness, which performs the actual database health probe.
    """
    if not isinstance(body, str) or not body.endswith("\n"):
        return False
    if len(body) > MAX_METRICS_BYTES or len(body.encode("utf-8")) > MAX_METRICS_BYTES:
        return False
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        return False
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,63}", version) is None:
        return False
    lines = [line.strip() for line in body.splitlines()]
    if len(lines) > 20_000 or any(len(line) > 4_096 for line in lines):
        return False
    rv, vv = re.escape(revision), re.escape(version)
    labels = rf'(?:revision="{rv}",version="{vv}"|version="{vv}",revision="{rv}")'
    patterns = {
        "lyte_build_info": rf'lyte_build_info\{{{labels}\}}[ \t]+({_METRIC_NUMBER})',
        "lyte_db_pool_healthy": rf'lyte_db_pool_healthy[ \t]+({_METRIC_NUMBER})',
    }
    for name, pattern in patterns.items():
        declarations = [line for line in lines if re.match(rf"# TYPE[ \t]+{name}(?:[ \t]|$)", line)]
        if declarations != [f"# TYPE {name} gauge"]:
            return False
        samples = [line for line in lines if re.match(rf"{name}(?:[{{ \t]|$)", line)]
        if len(samples) != 1:
            return False
        match = re.fullmatch(pattern, samples[0])
        if match is None or not math.isfinite(float(match[1])) or float(match[1]) != 1.0:
            return False
    return True


def forecast_matches(body: Any, *, keys: set[str], horizon: int) -> bool:
    """Check actual values and independently recompute the returned output hash."""
    if not isinstance(body, dict) or body.get("execution_authority") != "NONE":
        return False
    points, receipt = body.get("points"), body.get("receipt")
    if not isinstance(points, list) or len(points) != horizon or not isinstance(receipt, dict):
        return False
    if receipt.get("contract") != "szl.lyte.forecast-loom/v1":
        return False
    if receipt.get("provider") != "szl.robust-drift/v1" or receipt.get("horizon") != horizon:
        return False
    if any(SHA256.fullmatch(str(receipt.get(key, ""))) is None for key in (
        "input_sha256", "raw_input_sha256", "output_sha256",
    )):
        return False
    try:
        if receipt["output_sha256"] != digest(points):
            return False
        for step, point in enumerate(points, start=1):
            row = point["quantiles"]
            if point["step"] != step or set(row) != keys:
                return False
            values = [row[key] for key in sorted(keys, key=lambda key: float(key[1:]))]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                return False
            if values != sorted(values):
                return False
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return True


def verify_current_contract(
    request_json: Callable[..., tuple[int, Any]],
    request_text: Callable[..., tuple[int, str]],
    *,
    revision: str,
    version: str,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    observations: dict[str, Any] = {}

    def get(path: str) -> dict[str, Any]:
        status, body = request_json(path)
        checks[f"GET {path}"] = status == 200 and isinstance(body, dict)
        observations[path] = {"http_status": status, "body": body}
        return body if isinstance(body, dict) else {}

    def post(name: str, path: str, payload: dict[str, Any], expected: tuple[int, ...] = (200,)) -> dict[str, Any]:
        status, body = request_json(path, method="POST", payload=payload, expected_statuses=expected)
        checks[name + " status"] = status in expected and isinstance(body, dict)
        observations[name] = {"http_status": status, "body": body}
        return body if isinstance(body, dict) else {}

    def observe_metrics(phase: str) -> None:
        # Keep failed transport observable without recording arbitrary error bodies.
        try:
            status, body = request_text("/metrics")
        except Exception as exc:
            checks[f"metrics {phase} source and readiness"] = False
            observations[f"metrics_{phase}"] = {"http_status": None, "error_type": type(exc).__name__}
            return
        encoded = body.encode("utf-8") if isinstance(body, str) else b""
        checks[f"metrics {phase} source and readiness"] = (
            status == 200 and metrics_identity_matches(body, revision=revision, version=version)
        )
        observations[f"metrics_{phase}"] = {
            "http_status": status, "bytes": len(encoded),
            "response_sha256": hashlib.sha256(encoded).hexdigest(),
            "critical_gauges_match": checks[f"metrics {phase} source and readiness"],
            "all_metric_families_validated": False,
        }

    identities = {path: get(path) for path in IDENTITY_PATHS}
    for path, body in identities.items():
        checks[path + " exact identity"] = identity_matches(body, revision, version)
    health, ready, build = (identities[p] for p in IDENTITY_PATHS[:3])
    checks["health"] = health.get("ok") is True and health.get("service") == "lyte-signal-lattice"
    checks["readiness"] = bool(
        ready.get("ready") is True
        and ready.get("checks", {}).get("database") == "READY"
        and ready.get("source_binding", {}).get("bindings_agree") is True
        and ready.get("build", {}).get("state") == "OBSERVED"
        and ready.get("build", {}).get("revision") == revision
    )
    checks["build schema and binding"] = bool(
        build.get("schema") == "szl.lyte-build/v2"
        and build.get("build", {}).get("revision") == revision
        and build.get("build", {}).get("state") == "OBSERVED"
        and build.get("source_binding", {}).get("bindings_agree") is True
        and build.get("persistence", {}).get("state") == "READY"
        and build.get("persistence", {}).get("tenant_workspace_scoped") is True
        and build.get("data_mode") == "SAMPLE"
    )
    observe_metrics("initial")

    catalogs = {name: get(f"{PREFIX}/{name}") for name in CATALOG_PATHS}
    lenses = catalogs["catalog"].get("lenses", [])
    checks["six observability lenses"] = bool(
        len(lenses) == 6
        and {row.get("id") for row in lenses}
        == {"service", "journey", "business", "agent", "delivery", "decision"}
        and catalogs["catalog"].get("effectors_enabled") is False
        and catalogs["catalog"].get("data_mode") == "SAMPLE"
    )
    checks["operational capabilities"] = bool(
        {"living_anatomy", "second_brain", "hatun_review", "deterministic_ask_lyte", "tenant_workspace_isolation"}
        <= set(catalogs["capabilities"].get("operational", []))
        and catalogs["capabilities"].get("effectors_enabled") is False
    )
    checks["anatomy"] = bool(
        len(catalogs["anatomy"].get("stages", [])) == 9
        and catalogs["anatomy"].get("machine_enforced") is True
        and catalogs["anatomy"].get("effectors_enabled") is False
    )
    formulas = catalogs["formulas"].get("formulas", [])
    checks["formula non-authority"] = bool(
        formulas and catalogs["formulas"].get("lambda_status") == "CONJECTURE_1_ADVISORY"
        and catalogs["formulas"].get("formula_output_can_authorize") is False
        and all(row.get("can_authorize") is False and row.get("can_be_sole_allow_basis") is False for row in formulas)
    )
    checks["allowlisted sources"] = catalogs["sources"].get("arbitrary_url_fetch") is False
    entities = {name: get(f"{PREFIX}/{name}") for name in ENTITY_PATHS}
    memory = entities["second-brain"]
    checks["scoped second brain"] = bool(
        memory.get("count", 0) >= 1 and memory.get("items")
        and memory.get("raw_session_token_recorded") is False
        and memory.get("scope_digest_exposed") is False
        and all(row.get("receipt_hash") for row in memory.get("items", []))
    )
    answer = post("ask", f"{PREFIX}/ask", {"question": "Why is checkout revenue at risk?"})
    evidence_ids = answer.get("evidence_receipt_ids", [])
    checks["ask evidence and non-causality"] = bool(
        answer.get("truth_label") == "MODELED"
        and answer.get("confidence_basis") == "DETERMINISTIC_QUERY_MATCH"
        and evidence_ids and all(SHA256.fullmatch(str(value)) for value in evidence_ids)
        and answer.get("causality_claimed") is False and answer.get("can_execute") is False
    )
    review = post("hatun review", f"{PREFIX}/hatun/evaluate", {
        "action_type": "investigate-checkout", "evidence_labels": ["SAMPLE", "MODELED"],
        "evidence_receipt_ids": evidence_ids, "formula_ids": answer.get("formula_ids", []),
    })
    denied = post("hatun deny", f"{PREFIX}/hatun/evaluate", {
        "action_type": "rollback", "evidence_labels": ["MEASURED"], "requests_execution": True,
    })
    checks["hatun review cannot authorize"] = bool(
        review.get("decision") == "REVIEW" and review.get("can_authorize") is False
        and review.get("can_execute") is False and review.get("effectors_enabled") is False
    )
    checks["hatun execution denied"] = bool(
        denied.get("decision") == "DENY" and denied.get("can_execute") is False
        and denied.get("can_authorize") is False and denied.get("effectors_enabled") is False
    )
    rejected = post("anonymous mutation denied", f"{PREFIX}/analyze", {}, (401, 503))
    checks["authentication denial is explicit"] = bool(
        isinstance(rejected.get("detail"), str)
        and ("denied" in rejected["detail"] or "authentication failed" in rejected["detail"])
    )
    source = get(f"{PREFIX}/github/szl-holdings/lyte-services")
    checks["github observation is read-only"] = bool(
        source.get("read_only") is True and source.get("receipt_persisted") is False
        and source.get("persistence_requires_authenticated_ingest") is True
        and source.get("arbitrary_url_fetch") is False
        and source.get("truth_label") == "REPORTED"
    )

    payload = {"signal_id": "qualification.canonical-publisher", "values": [10.0, 11.0, None, 13.0, 14.0],
               "horizon": 3, "quantiles": [0.1, 0.5, 0.9]}
    filled_values = [10.0, 11.0, 11.0, 13.0, 14.0]
    forecast = post("forecast", f"{PREFIX}/forecast", payload)
    repeat = post("forecast repeat", f"{PREFIX}/forecast", payload)
    filled = post("forecast observed", f"{PREFIX}/forecast", {**payload, "values": filled_values})
    fractional = post("forecast fractional", f"{PREFIX}/forecast", {**payload, "quantiles": [0.101, 0.104, 0.5, 0.9]})
    checks["forecast values and output digest"] = forecast_matches(forecast, keys={"q10", "q50", "q90"}, horizon=3)
    checks["forecast deterministic repeat"] = forecast == repeat
    checks["fractional quantiles preserved"] = forecast_matches(fractional, keys={"q10.1", "q10.4", "q50", "q90"}, horizon=3)
    receipt, observed_receipt = forecast.get("receipt", {}), filled.get("receipt", {})
    raw_basis = {"contract": "szl.lyte.forecast-loom/v1", **payload}
    checks["forecast request independently bound"] = bool(
        receipt.get("signal_id") == payload["signal_id"]
        and receipt.get("quantiles") == payload["quantiles"]
        and receipt.get("input_sha256") == digest({**raw_basis, "values": filled_values})
        and receipt.get("raw_input_sha256") == digest(raw_basis)
    )
    checks["raw missingness provenance"] = bool(
        receipt.get("context_points") == 5 and receipt.get("original_context_points") == 5
        and receipt.get("truncated_points") == 0 and receipt.get("imputed_points") == 1
        and receipt.get("input_sha256") == observed_receipt.get("input_sha256")
        and receipt.get("raw_input_sha256") != observed_receipt.get("raw_input_sha256")
        and receipt.get("output_sha256") == observed_receipt.get("output_sha256")
    )
    granite = post("granite withheld", f"{PREFIX}/forecast", {**payload, "provider": "granite"}, (503,))
    checks["granite disabled explicitly"] = granite.get("detail") == "Granite provider is not admitted in this deployment"
    post("invalid horizon rejected", f"{PREFIX}/forecast", {**payload, "horizon": 0}, (422,))
    post("missing context rejected", f"{PREFIX}/forecast", {**payload, "values": [None, None]}, (422,))
    post("quantile workload bounded", f"{PREFIX}/forecast", {**payload, "quantiles": [i / 200 for i in range(1, 200)]}, (422,))
    after = get(f"{PREFIX}/receipts")
    checks["read and advisory calls do not mint persisted receipts"] = (
        isinstance(after.get("count"), int) and after["count"] == entities["receipts"].get("count")
    )
    root_status, root = request_text("/")
    css_status, css = request_text("/static/lyte/styles.css")
    js_status, js = request_text("/static/lyte/app.js")
    checks["product shell"] = bool(
        root_status == 200 and "Business Observability Command" in root
        and 'id="ask-open"' in root and 'id="main-content"' in root
        and 'href="/static/lyte/styles.css"' in root
        and 'src="/static/lyte/app.js"' in root and "viewport-fit=cover" in root
    )
    checks["external responsive assets"] = bool(
        css_status == 200 and js_status == 200 and len(js) > 100
        and "prefers-reduced-motion" in css and "forced-colors" in css and "focus-visible" in css
    )
    observations["frontend"] = {"root_http": root_status, "css_http": css_status, "js_http": js_status,
        "root_sha256": hashlib.sha256(root.encode()).hexdigest(),
        "css_sha256": hashlib.sha256(css.encode()).hexdigest(),
        "js_sha256": hashlib.sha256(js.encode()).hexdigest()}
    observe_metrics("final")
    failed = [name for name, passed in checks.items() if not passed]
    return {"schema": "szl.lyte-live-contract/v4", "complete": not failed,
        "checks": checks, "failed_checks": failed, "observations": observations,
        "source_revision": revision, "expected_version": version, "data_mode": "SAMPLE",
        "production_telemetry_verified": False, "production_granite_admitted": False,
        "execution_authority": "NONE", "secret_values_recorded": False,
        "limitations": ["Content hashes are not signatures.", "This is public SAMPLE runtime verification, not production telemetry or SLO qualification.", "CSS contract checks are not a substitute for browser accessibility testing.", "Metrics checks validate two critical gauges, not every exported series."]}
