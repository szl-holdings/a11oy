# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Recommendation routes must report observed health and capability blockers.

Execute the production handlers and their helper dependencies in isolation from
unrelated app startup. All health observations below are simulated test inputs;
none are production readiness evidence or permission to execute an action.
"""
import ast
import asyncio
import copy
import datetime
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, Response


SOURCE = Path(__file__).resolve().parents[1] / "serve.py"
ROUTES = {
    "/api/a11oy/v1/companion/recommend": "_sc_rosie_recommend",
    "/api/a11oy/v1/operator/recommend": "_sc_cap_recommend",
}


@pytest.fixture
def runtime():
    """Load actual source, including future helpers, but never boot integrations."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    reads = []
    writes = []

    async def no_observation():
        raise RuntimeError("simulated health source unavailable")

    def forbidden_write(*args, **kwargs):
        writes.append((args, kwargs))
        raise AssertionError("recommendation GET attempted to create execution evidence")

    scope = {
        "_SCJSON": JSONResponse, "JSONResponse": JSONResponse,
        "_sc_json": json, "json": json, "_sc_datetime": datetime,
        "healthz": no_observation,
        "_sc_receipt": forbidden_write, "_sc_act": forbidden_write,
        "_sc_build_verdict": forbidden_write, "_sc_log_verdict": forbidden_write,
    }
    # Keep the pre-fix literal available: regressions must fail the behavioral
    # contract, not fail because the harness omitted the old global constant.
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_SC_RECOMMEND"
                        for t in node.targets)):
            try:
                scope["_SC_RECOMMEND"] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass

    needed = set(ROUTES.values())
    pending = list(needed)
    while pending:
        node = functions[pending.pop()]
        for name in {part.id for part in ast.walk(node) if isinstance(part, ast.Name)}:
            if (name in functions and name not in scope and name not in needed
                    and (name.startswith(("_sc_", "_gov_")) or name == "gov_envelope")):
                needed.add(name)
                pending.append(name)
    selected = []
    for name in sorted(needed):
        node = copy.deepcopy(functions[name])
        node.decorator_list = []
        selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), scope)
    app = FastAPI()
    for path, name in ROUTES.items():
        app.add_api_route(path, scope[name], methods=["GET"])

    def observe(value, status_code=200):
        original = copy.deepcopy(value)

        async def health():
            reads.append("healthz")
            return JSONResponse(copy.deepcopy(value), status_code=status_code)

        scope["healthz"] = health
        return original

    yield TestClient(app), scope, observe, reads
    assert writes == [], "read-only recommendations must not mint receipts or decisions"


def health(*, service_status="ok", ready=False, blocked=True):
    blockers = ([{"name": "Energy operator", "ready": False,
                  "reasons": ["operator_stopped", "no_gpu_reachable"]}]
                if blocked else [])
    service_blockers = ["storage-unavailable"] if service_status == "degraded" else []
    return {
        "service": "a11oy", "status": service_status,
        "scope": "SERVICE_HEALTH", "degraded_reasons": service_blockers,
        "operational_readiness": {
            "scope": "FRONTIER_CAPABILITIES_AND_SERVICE_HEALTH",
            "ready": ready, "status": "READY" if ready else "NOT_READY",
            "service_blockers": service_blockers,
            "frontier": {"state": "READY" if not blocked else "NOT_READY",
                         "ready": not blocked,
                         "ready_tiles": ["Tamper-evident energy ledger"],
                         "blocked_tiles": blockers},
        },
    }


def checked_get(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] in {"REAL", "DEGRADED"}
    assert isinstance(body["recommendations"], list) and body["recommendations"]
    actual = Counter(row["severity"] for row in body["recommendations"])
    assert body["counts"] == {severity: actual[severity]
                              for severity in ("critical", "warn", "info", "ok")}
    assert isinstance(body["citations"], list)
    assert body["citations"][0]["endpoint"] == "/api/a11oy/healthz"
    return body


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("service_status,http_status", [("ok", 200), ("degraded", 200),
                                                      ("degraded", 503)])
def test_observed_blockers_prevent_nominal_recommendations(runtime, path, service_status, http_status):
    client, _, observe, reads = runtime
    report = health(service_status=service_status)
    observe(report, status_code=http_status)
    body = checked_get(client, path)
    assert reads == ["healthz"]
    assert body["status"] == "DEGRADED"
    assert body["grounded"] is True
    assert body["counts"]["ok"] == 0
    evidence = body["citations"][0]["data"]
    assert evidence["service"] == "a11oy"
    assert evidence["status"] == service_status
    assert evidence["operational_readiness"] == report["operational_readiness"]
    findings = json.dumps(body["recommendations"])
    assert "operator_stopped" in findings
    assert "no_gpu_reachable" in findings
    if service_status == "degraded":
        assert "storage-unavailable" in findings


@pytest.mark.parametrize("path", ROUTES)
def test_consistent_ready_observation_can_report_nominal(runtime, path):
    client, _, observe, reads = runtime
    report = health(ready=True, blocked=False)
    observe(report)
    body = checked_get(client, path)
    assert reads == ["healthz"]
    assert body["status"] == "REAL"
    assert body["grounded"] is True
    assert body["counts"]["ok"] == 1
    assert body["counts"]["critical"] == body["counts"]["warn"] == 0
    assert body["citations"][0]["data"]["operational_readiness"] == report["operational_readiness"]


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("mutation", [
    lambda value: value.pop("operational_readiness"),
    lambda value: value.update(operational_readiness=[]),
    lambda value: value["operational_readiness"].update(ready="true"),
    lambda value: value["operational_readiness"].update(status="NOT_READY"),
    lambda value: value["operational_readiness"].update(service_blockers=["storage-unavailable"]),
    lambda value: value["operational_readiness"].update(frontier=None),
    lambda value: value["operational_readiness"].update(service_blockers="none"),
    lambda value: value["operational_readiness"]["frontier"].pop("state"),
    lambda value: value["operational_readiness"]["frontier"].update(state="NOT_READY"),
    lambda value: value["operational_readiness"]["frontier"].update(ready="true"),
    lambda value: value["operational_readiness"]["frontier"].update(ready_tiles="all"),
    lambda value: value["operational_readiness"]["frontier"].update(blocked_tiles={}),
    lambda value: value["operational_readiness"]["frontier"].update(blocked_tiles=[{
        "name": "Energy operator", "reasons": ["operator_stopped"]}]),
])
def test_missing_or_inconsistent_readiness_never_reports_nominal(runtime, path, mutation):
    client, _, observe, _ = runtime
    report = health(ready=True, blocked=False)
    mutation(report)
    observe(report)
    body = checked_get(client, path)
    assert body["status"] == "DEGRADED"
    assert body["counts"]["ok"] == 0


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("failure", ["exception", "wrong-service", "non-object", "invalid-json"])
def test_unavailable_health_is_not_replaced_with_static_success(runtime, path, failure):
    client, scope, _, reads = runtime

    async def unavailable():
        reads.append("healthz")
        if failure == "exception":
            raise RuntimeError("simulated unavailable probe")
        if failure == "wrong-service":
            return JSONResponse({"service": "other", "status": "ok"})
        if failure == "non-object":
            return JSONResponse(["ok"])
        return Response("not valid JSON", media_type="application/json")

    scope["healthz"] = unavailable
    body = checked_get(client, path)
    assert reads == ["healthz"]
    assert body["status"] == "DEGRADED"
    assert body["grounded"] is False
    assert body["counts"]["ok"] == 0
    assert body["citations"][0]["data"]["state"] == "UNAVAILABLE"


def test_plain_and_governed_routes_share_the_same_observation(runtime):
    client, _, observe, reads = runtime
    observe(health())
    plain = checked_get(client, "/api/a11oy/v1/companion/recommend")
    governed = checked_get(client, "/api/a11oy/v1/operator/recommend")
    assert reads == ["healthz", "healthz"]
    for key in ("status", "grounded", "recommendations", "counts", "citations"):
        assert plain[key] == governed[key]


def compile_into(scope, *names):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    nodes = []
    for name in names:
        node = copy.deepcopy(next(node for node in ast.walk(tree)
                                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                  and node.name == name))
        node.decorator_list = []
        nodes.append(node)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), scope)


@pytest.mark.parametrize("observed", [False, True])
def test_command_recommendation_stage_retains_evidence_or_is_unavailable(runtime, observed):
    _, scope, _, reads = runtime
    # Command policy/receipt effects are separately covered by integration tests.
    # Here their explicit test doubles let us inspect only recommendation adoption.
    scope.update(
        _sc_classify=lambda _command: "health",
        _sc_build_verdict=lambda _value: {"decision": "allow"},
        _sc_secrets=SimpleNamespace(token_hex=lambda _size: "simulated"),
        _sc_receipt=lambda *_args: {"receipt": {"receipt_sha256": "simulated"}, "signed": False},
    )
    compile_into(scope, "_sc_command_loop")
    body = {"command": "inspect health", "approved": False}
    if observed:
        evidence = scope["_sc_recommend"](health(), http_status=200)
        result = scope["_sc_command_loop"](body, recommendation_report=evidence)
    else:
        result = scope["_sc_command_loop"](body)
    stage = next(stage for stage in result["stages"] if stage["stage"] == "Recommend")
    assert stage["status"] == "DEGRADED"
    assert stage["evidence"]["grounded"] is observed
    assert stage["evidence"]["counts"]["ok"] == 0
    assert stage["data"] == stage["evidence"]["recommendations"]
    assert result["outcome"] == "HELD_FOR_APPROVAL"
    assert reads == []  # the synchronous loop never performs a hidden health probe


def test_command_route_observes_health_before_passing_recommendations(runtime):
    _, scope, observe, reads = runtime
    observe(health())
    passed = []

    def command_loop(body, recommendation_report=None):
        passed.append((body, recommendation_report))
        return {"stages": [{"status": "REAL"}], "outcome": "SIMULATED"}

    class Request:
        async def json(self):
            return {"command": "inspect health", "approved": False}

    scope.update(_sc_command_loop=command_loop, _SCRequest=Request)
    compile_into(scope, "_sc_body", "_sc_rejected", "_sc_cap_command")
    response = asyncio.run(scope["_sc_cap_command"](Request()))
    assert response.status_code == 200
    assert reads == ["healthz"]
    assert len(passed) == 1
    assert passed[0][1]["grounded"] is True
    assert passed[0][1]["status"] == "DEGRADED"
    assert passed[0][1]["counts"]["ok"] == 0
