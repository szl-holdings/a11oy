#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real route/middleware boundary with deterministic inference data."""
import copy
import json
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_governed_cortex as cortex
import vsp_otel.middleware as otel


REVISION = "a" * 40
TRACE = "00-" + "1" * 32 + "-" + "2" * 16 + "-00"


@pytest.fixture
def proposal(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", REVISION)
    body = {
        "source_revision": REVISION,
        "model": {"sha256": cortex.MODEL_SHA256},
        "output_sha256": "b" * 64,
        "decision": "REVIEW_PROPOSAL_ONLY",
        "executed": False,
        "tool_execution": False,
        "authority_state": "NO_ACTION_AUTHORITY",
    }
    return {
        "state": "PROPOSAL",
        "output": "private-output-marker",
        "source_revision": REVISION,
        "model": {"sha256": cortex.MODEL_SHA256},
        "executed": False,
        "tool_execution": False,
        "authority_state": "NO_ACTION_AUTHORITY",
        "nemo": [
            {"stage": stage, "decision": "ALLOW"}
            for stage in ("PRE_GENERATION", "TEXT_R1_R5", "POST_GENERATION")
        ],
        "receipt": {
            "payload": body,
            "receipt_sha256": cortex.canonical_sha256(body),
            "signature": {"status": "UNSIGNED_RUNTIME"},
            "persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
        },
    }


def client_for(proposal, *, middleware=True):
    app = FastAPI()
    if middleware:
        otel.install(app, service_name="trace-contract-test", endpoint=None)
    cortex.register(app)
    return TestClient(app)


def test_route_observes_actual_server_span_without_changing_receipt(proposal):
    before = cortex.canonical_bytes(proposal["receipt"])
    with mock.patch.object(cortex, "infer_payload", side_effect=lambda request: copy.deepcopy(proposal)):
        with client_for(proposal) as client:
            response = client.post(
                "/api/v2/governed-infer",
                json={"prompt": "private-request-marker"},
                headers={"traceparent": TRACE},
            )
            repeated = client.post("/api/v2/governed-infer", json={"prompt": "private-request-marker"})
    assert response.status_code == repeated.status_code == 200
    body = response.json()
    event = body["trace_observation"]
    current = otel.parse_traceparent(response.headers["traceparent"])
    assert event["state"] == "OBSERVED"
    assert event["trace_id"] == "1" * 32 == current["trace_id"]
    assert event["span_id"] == current["parent_id"] != "2" * 16
    assert event["trace_flags"] == "00"
    assert repeated.json()["trace_observation"]["trace_id"] != event["trace_id"]
    assert cortex.canonical_bytes(body["receipt"]) == before
    assert body["authority_state"] == "NO_ACTION_AUTHORITY"
    assert body["executed"] is body["tool_execution"] is False
    assert "private-" not in json.dumps(event, allow_nan=False)
    assert event["collector_delivery"] == "UNVERIFIED"


@pytest.mark.parametrize("fault", ["missing_context", "constructor_error", "receipt_drift"])
def test_diagnostic_failure_preserves_success_and_hides_exception(proposal, fault):
    if fault == "receipt_drift":
        proposal["receipt"]["receipt_sha256"] = "c" * 64
    with mock.patch.object(cortex, "infer_payload", return_value=copy.deepcopy(proposal)):
        with mock.patch.object(cortex.trace_ir, "receipt_observation", wraps=cortex.trace_ir.receipt_observation) as observe:
            if fault == "constructor_error":
                observe.side_effect = RuntimeError("private-error-marker")
            with client_for(proposal, middleware=fault != "missing_context") as client:
                response = client.post("/api/v2/governed-infer", json={"prompt": "status"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "PROPOSAL"
    assert body["trace_observation"]["state"] == "UNAVAILABLE"
    assert "private-error-marker" not in json.dumps(body["trace_observation"], allow_nan=False)
    assert body["receipt"] == proposal["receipt"]


@pytest.mark.parametrize("mutation", ["missing_witness", "duplicate_witness", "blocked_witness", "authority", "model", "source", "signature"])
def test_inconsistent_metadata_cannot_claim_observed(proposal, mutation):
    if mutation == "missing_witness":
        proposal["nemo"].pop()
    elif mutation == "duplicate_witness":
        proposal["nemo"][2] = proposal["nemo"][0]
    elif mutation == "blocked_witness":
        proposal["nemo"][1]["decision"] = "BLOCK"
    elif mutation == "authority":
        proposal["executed"] = True
    elif mutation == "model":
        proposal["model"]["sha256"] = "c" * 64
    elif mutation == "source":
        proposal["source_revision"] = "c" * 40
    elif mutation == "signature":
        proposal["receipt"]["signature"]["status"] = "SIGNED"
    result = cortex._receipt_trace_observation(proposal, TRACE)
    assert result["state"] == "UNAVAILABLE"
    assert result["diagnostic"]["decision"] == "HOLD"
    assert "private-" not in json.dumps(result, allow_nan=False)


def test_existing_nemo_denial_never_observes_success(proposal):
    with (
        mock.patch.object(cortex, "infer_payload", side_effect=cortex.CortexBoundaryError("nemo_text_witness_blocked", 422)),
        mock.patch.object(cortex, "_receipt_trace_observation") as observe,
        client_for(proposal) as client,
    ):
        response = client.post("/api/v2/governed-infer", json={"prompt": "status"})
    assert response.status_code == 422
    assert "trace_observation" not in response.json()
    observe.assert_not_called()


def test_discovery_reads_do_not_create_observations(proposal):
    with mock.patch.object(cortex, "_receipt_trace_observation") as observe, client_for(proposal) as client:
        response = client.get("/api/v2/governed-contract")
        last = client.get("/api/v2/anatomy/last")
    assert response.status_code == last.status_code == 200
    assert response.json()["trace_observation"]["authority"] == "NONE"
    assert "observation_sha256" not in response.text
    observe.assert_not_called()


def test_receipt_authority_drift_cannot_hide_behind_response_flags(proposal):
    proposal["receipt"]["payload"]["executed"] = True
    proposal["receipt"]["receipt_sha256"] = cortex.canonical_sha256(proposal["receipt"]["payload"])
    result = cortex._receipt_trace_observation(proposal, TRACE)
    assert result["state"] == "UNAVAILABLE"
    assert result["diagnostic"]["decision"] == "HOLD"


def install_actual_wire_d_middleware(app):
    """Run the production Wire D middleware and pure helpers, without signing/storage."""
    import ast
    import os
    import re
    import threading
    from collections import deque
    from datetime import datetime, timezone
    from pathlib import Path
    from typing import Any
    from starlette.requests import Request

    source = Path(cortex.__file__).with_name("szl_provenance.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {
        "_rand_hex", "new_trace_id", "new_span_id", "parse_traceparent",
        "parse_tracestate", "mutate_tracestate", "_TraceState",
    }
    helpers = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names
    ]
    assert {node.name for node in helpers} == names
    registration = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "register_provenance"
    )
    middleware = next(
        node for node in registration.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_wire_d_mw"
    )
    namespace = {
        "os": os, "re": re, "threading": threading, "deque": deque,
        "datetime": datetime, "timezone": timezone, "Any": Any, "Request": Request,
    }
    exec(compile(ast.Module(body=helpers, type_ignores=[]), str(source), "exec"), namespace)
    state = namespace["_TraceState"]()
    namespace.update(app=app, space="a11oy", tstate=state)
    exec(compile(ast.Module(body=[middleware], type_ignores=[]), str(source), "exec"), namespace)
    return state


@pytest.mark.parametrize("incoming", [TRACE, TRACE[:-2] + "01", TRACE[:-2] + "03", None, "invalid-traceparent"])
@pytest.mark.parametrize("configured_provider", [False, True])
def test_production_wire_d_and_vsp_share_server_context(proposal, monkeypatch, incoming, configured_provider):
    from contextlib import contextmanager
    from types import SimpleNamespace

    calls = []
    if configured_provider:
        real_tracer = otel._Tracer

        class ControlledTracer(real_tracer):
            def __init__(self, service, endpoint):
                super().__init__(service, None)

            @contextmanager
            def server_span(self, name, parent, attrs, **options):
                calls.append({"parent": parent, **options})
                parsed = otel.parse_traceparent(parent)
                context = SimpleNamespace(
                    trace_id=int(parsed["trace_id"], 16) if parsed else int("9" * 32, 16),
                    span_id=int("e" * 16, 16),
                    trace_flags=0,
                )
                yield SimpleNamespace(get_span_context=lambda: context, set_attribute=lambda *args: None)

        monkeypatch.setattr(otel, "_Tracer", ControlledTracer)

    app = FastAPI()
    # This is the actual serve.py installation order: Wire D wraps VSP.
    otel.install(app, service_name="trace-coexistence-test", endpoint=None)
    wire = install_actual_wire_d_middleware(app)
    cortex.register(app)
    headers = {"traceparent": incoming} if incoming is not None else {}
    with mock.patch.object(cortex, "infer_payload", side_effect=lambda request: copy.deepcopy(proposal)):
        with TestClient(app) as client:
            response = client.post("/api/v2/governed-infer", json={"prompt": "context-test"}, headers=headers)
    assert response.status_code == 200
    event = response.json()["trace_observation"]
    returned = otel.parse_traceparent(response.headers["traceparent"])
    recorded = wire.snapshot()["recent"][-1]
    if incoming == TRACE[:-2] + "03":
        # The existing strict VSP v00 profile rejects this Wire D context.
        assert returned is None
        assert event["state"] == "UNAVAILABLE"
        assert event["reason_codes"] == ["TRACE_CONTEXT_UNAVAILABLE"]
        assert response.json()["receipt"] == proposal["receipt"]
        assert response.headers["traceparent"].split("-")[2] == recorded["span_id"]
        assert calls == []
        return
    assert event["state"] == "OBSERVED"
    assert event["trace_id"] == returned["trace_id"] == recorded["trace_id"]
    assert event["span_id"] == returned["parent_id"] == recorded["span_id"]
    assert event["trace_flags"] == returned["flags"]
    assert wire.snapshot()["active_span_count"] == 0
    if otel.parse_traceparent(incoming):
        supplied = otel.parse_traceparent(incoming)
        assert returned["trace_id"] == supplied["trace_id"]
        assert returned["parent_id"] != supplied["parent_id"]
    if configured_provider:
        assert calls == [{"parent": response.headers["traceparent"], "inherited_server": True}]
        assert event["span_id"] != "e" * 16


@pytest.mark.parametrize("attribute,value,remove", [
    ("trace_id", "9" * 32, False),
    ("span_id", "9" * 16, False),
    ("traceparent", "invalid-host-context", False),
    ("traceparent", "", False),
    ("traceparent", None, False),
    ("traceparent", None, True),
    ("span_id", None, True),
    ("trace_id", None, True),
])
def test_inconsistent_host_context_cannot_claim_observed(proposal, attribute, value, remove):
    app = FastAPI()
    otel.install(app, service_name="trace-corrupt-host-test", endpoint=None)

    @app.middleware("http")
    async def corrupt_context(request, call_next):
        if remove:
            delattr(request.state, attribute)
        else:
            setattr(request.state, attribute, value)
        return await call_next(request)

    install_actual_wire_d_middleware(app)
    cortex.register(app)
    with mock.patch.object(cortex, "infer_payload", side_effect=lambda request: copy.deepcopy(proposal)):
        with TestClient(app) as client:
            response = client.post("/api/v2/governed-infer", json={"prompt": "context-test"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "PROPOSAL"
    assert body["receipt"] == proposal["receipt"]
    assert body["trace_observation"]["state"] == "UNAVAILABLE"
    assert body["trace_observation"]["reason_codes"] == ["TRACE_CONTEXT_UNAVAILABLE"]
    assert otel.parse_traceparent(response.headers["traceparent"]) is not None


def test_production_middleware_installation_matches_coexistence_fixture():
    import ast
    from pathlib import Path

    tree = ast.parse(Path(cortex.__file__).with_name("serve.py").read_text(encoding="utf-8"))
    def calls(owner, method):
        return [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == owner and node.func.attr == method
        ]
    vsp = calls("_vsp_otel", "install")
    wire = calls("_prov", "register_provenance")
    assert len(vsp) == len(wire) == 1
    assert vsp[0] < wire[0], "Reconcile fixture and canonical context before changing middleware order"
