#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Compose the actual trace middleware without keys, storage or a live model."""

import ast
import copy
import importlib.util
import json
import sys
import threading
import types
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_governed_cortex as cortex
import vsp_otel.middleware as otel


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
TRACE_ID = "1" * 32
PARENT_ID = "2" * 16
SDK_SPAN_ID = "3" * 16
TRACESTATE = "vendor=one,szl=prior,other=two"
ROUTE = "/api/v2/governed-infer"


def _traceparent(flags="01"):
    return f"00-{TRACE_ID}-{PARENT_ID}-{flags}"


def _serve_registration_order():
    """Use the host's real registration order, not a hand-picked passing order."""
    tree = ast.parse((ROOT / "serve.py").read_text(encoding="utf-8"))
    targets = {
        ("_be_harden", "harden"): "be",
        ("_prov", "register_provenance"): "wire",
        ("_vsp_otel", "install"): "vsp",
    }
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        key = (node.func.value.id, node.func.attr)
        if key in targets:
            found.append((node.lineno, targets[key]))
    assert sorted(name for _, name in found) == ["be", "vsp", "wire"]
    return [name for _, name in sorted(found)]


def _load_source(monkeypatch, name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _forbidden_boundary(*args, **kwargs):
    raise AssertionError("this composition test must not sign or access managed storage")


class _CaptureStore:
    backend = "memory"

    def __init__(self, *args, **kwargs):
        pass


class _CaptureDAG:
    """Capture arguments before signing; never produce a signature or durable receipt."""

    def __init__(self, space):
        self.space = space
        self.lock = threading.Lock()
        self.nodes = []
        self.captured = []

    def by_schema(self, schema):
        return []

    def append_signed(self, receipt, *, confirm=False):
        frozen = json.loads(json.dumps(receipt, allow_nan=False))
        self.captured.append({"receipt": frozen, "confirm": confirm})
        return {"receipt": frozen, "signed": False, "capture_only": True}


class _CaptureLogger:
    def __init__(self):
        self.events = []

    def _record(self, message, **kwargs):
        self.events.append({"message": message, **kwargs.get("extra", {})})

    info = _record
    warning = _record
    error = _record


def _proposal():
    body = {
        "schema": cortex.RECEIPT_SCHEMA,
        "source_revision": REVISION,
        "model": {"sha256": cortex.MODEL_SHA256},
        "decision": "REVIEW_PROPOSAL_ONLY",
        "executed": False,
        "tool_execution": False,
        "authority_state": "NO_ACTION_AUTHORITY",
    }
    return {
        "schema": cortex.RESPONSE_SCHEMA,
        "state": "PROPOSAL",
        "output": "synthetic composition fixture",
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


@pytest.fixture
def stack_factory(monkeypatch):
    # These imports are intercepted before provenance executes. In particular,
    # importing the real DSSE module must not discover or initialize a signer.
    dsse = types.ModuleType("szl_dsse")
    dsse.signing_available = lambda: False
    dsse.sign_payload = _forbidden_boundary
    dsse.verify_envelope = _forbidden_boundary
    dsse.KEYID = "capture-only"
    dsse.KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"
    dsse.PUB_KEY_URL = "https://invalid.example/capture-only"
    owner = types.ModuleType("a11oy_state_store")
    owner.enabled = lambda: False
    owner.active = _forbidden_boundary
    owner.local_dir = _forbidden_boundary
    with monkeypatch.context() as imports:
        imports.setitem(sys.modules, "szl_dsse", dsse)
        imports.setitem(sys.modules, "a11oy_state_store", owner)
        provenance = _load_source(
            monkeypatch, "_canonical_context_provenance", "szl_provenance.py"
        )
    hardening = _load_source(
        monkeypatch, "_canonical_context_hardening", "szl_be_hardening.py"
    )
    monkeypatch.setattr(provenance, "_KhipuDAG", _CaptureDAG)
    monkeypatch.setattr(hardening, "DurableKhipu", _CaptureStore)
    # Do not inspect the operator's configured targets or authorization digest.
    monkeypatch.setattr(provenance, "_wire_d_targets_from_env", lambda: ({}, []))
    monkeypatch.setattr(
        provenance, "os", types.SimpleNamespace(environ={}, urandom=__import__("os").urandom)
    )
    monkeypatch.setenv("SZL_GIT_SHA", REVISION)
    proposal = _proposal()
    monkeypatch.setattr(cortex, "infer_payload", lambda request: copy.deepcopy(proposal))

    def build(*, vsp=True, wire=True, poison_aliases=False):
        app = FastAPI()
        logger = _CaptureLogger()
        monkeypatch.setattr(hardening, "_make_logger", lambda organ: logger)
        captured = []
        # Installed first, this observer runs inside the production middleware.
        # Its receipt boundary is capture-only, and is exercised only by this
        # synthetic local POST, never by a discovery/read request.
        @app.middleware("http")
        async def capture_context(request, call_next):
            if request.method == "POST" and request.url.path == ROUTE:
                current = {
                    key: getattr(request.state, key, None)
                    for key in (
                        "traceparent", "trace_id", "span_id", "trace_flags",
                        "inbound_parent", "tracestate",
                    )
                }
                if poison_aliases:
                    request.state.traceparent = "00-" + "e" * 32 + "-" + "f" * 16 + "-00"
                    request.state.trace_id = "e" * 32
                    request.state.span_id = "f" * 16
                    request.state.trace_flags = "00"
                    request.state.tracestate = "untrusted=alias"
                item = {"context": current}
                if wire:
                    item["outgoing"] = app.state.szl_outgoing_headers(request, "test-peer")
                    node = app.state.szl_emit_signed_receipt(
                        {"schema": "szl.test.trace-context-capture/v1"}, request
                    )
                    item["receipt"] = node["receipt"]
                captured.append(item)
            return await call_next(request)

        cortex.register(app)
        for name in _serve_registration_order():
            if name == "be":
                assert hardening.harden(app, organ="trace-context-test")["ok"] is True
            elif name == "wire" and wire:
                provenance.register_provenance(app, "trace-context-test")
            elif name == "vsp" and vsp:
                otel.install(app, service_name="trace-context-test", endpoint=None)
        return types.SimpleNamespace(
            app=app, captured=captured, logger=logger, provenance=provenance,
            proposal=proposal,
        )

    return build


def _post(client, incoming=None, *, log_alias="unrelated-client-log-id"):
    headers = {"tracestate": TRACESTATE, "x-trace-id": log_alias}
    if incoming is not None:
        headers["traceparent"] = incoming
    return client.post(ROUTE, json={"prompt": "synthetic trace fixture"}, headers=headers)


def _assert_one_context(stack, response, *, observed=True, index=0):
    assert response.status_code == 200
    body = response.json()
    context = stack.provenance.parse_traceparent(response.headers["traceparent"])
    assert context["valid"] is True
    expected_trace = context["trace_id"]
    expected_span = context["parent_id"]
    assert response.headers["x-trace-id"] == expected_trace
    assert response.headers["x-span-id"] == expected_span
    item = stack.captured[index]
    assert item["context"]["traceparent"] == response.headers["traceparent"]
    assert item["context"]["trace_id"] == expected_trace
    assert item["context"]["span_id"] == expected_span
    assert item["receipt"]["traceparent"] == response.headers["traceparent"]
    assert item["receipt"]["trace_id"] == expected_trace
    assert item["receipt"]["span_id"] == expected_span
    assert item["receipt"]["wire_d"] == "LIVE"
    assert body["receipt"] == stack.proposal["receipt"]
    assert body["authority_state"] == "NO_ACTION_AUTHORITY"
    assert body["executed"] is body["tool_execution"] is False

    diagnostic = body["trace_observation"]
    if observed:
        assert diagnostic["state"] == "OBSERVED"
        assert diagnostic["trace_id"] == expected_trace
        assert diagnostic["span_id"] == expected_span
        assert diagnostic["trace_flags"] == context["flags"]
        assert diagnostic["authority"] == "NONE"
        assert diagnostic["collector_delivery"] == "UNVERIFIED"
    else:
        assert diagnostic["state"] == "UNAVAILABLE"

    outgoing = stack.provenance.parse_traceparent(item["outgoing"]["traceparent"])
    assert outgoing["valid"] is True
    assert outgoing["trace_id"] == expected_trace
    assert outgoing["parent_id"] != expected_span
    assert outgoing["flags"] == context["flags"]
    assert item["outgoing"]["tracestate"].split(",")[0] == "szl=" + outgoing["parent_id"]
    assert response.headers["tracestate"].split(",")[0] == "szl=" + expected_span
    logs = list(stack.app.state.szl_trace.log)
    inbound = [row for row in logs if row["dir"] == "in" and row["span_id"] == expected_span]
    assert len(inbound) == 1
    assert inbound[0]["trace_id"] == expected_trace
    outbound = [row for row in logs if row["dir"] == "out" and row["span_id"] == outgoing["parent_id"]]
    assert len(outbound) == 1
    assert outbound[0]["trace_id"] == expected_trace
    assert outbound[0]["parent"] == expected_span
    assert stack.app.state.szl_trace.active_spans == {}
    request_logs = [row for row in stack.logger.events if row.get("path") == ROUTE]
    assert request_logs[index]["trace_id"] == expected_trace
    assert request_logs[index]["span_id"] == expected_span
    return context, item


def test_serve_selects_local_provenance_and_orders_the_context_owner_first():
    tree = ast.parse((ROOT / "serve.py").read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.Import)
        and any(alias.name == "szl_provenance" and alias.asname == "_prov" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.ImportFrom)
        and any(alias.asname == "_prov" for alias in node.names)
        for node in ast.walk(tree)
    ), "a preferred external provenance module bypasses the reviewed middleware repair"
    assert _serve_registration_order() == ["be", "wire", "vsp"]


@pytest.mark.parametrize("incoming", [
    None, _traceparent("01"), _traceparent("00"), "invalid", _traceparent("03"),
], ids=["new-root", "sampled", "unsampled", "invalid", "reserved-flags"])
def test_full_host_chain_has_one_server_context(stack_factory, incoming):
    stack = stack_factory()
    with TestClient(stack.app) as client:
        response = _post(client, incoming)
    context, item = _assert_one_context(stack, response)
    accepted = otel.parse_traceparent(incoming)
    inbound = [
        row for row in stack.app.state.szl_trace.log
        if row["dir"] == "in" and row["span_id"] == context["parent_id"]
    ][0]
    if accepted is not None:
        assert context["trace_id"] == TRACE_ID
        assert context["parent_id"] != PARENT_ID
        assert context["flags"] == accepted["flags"]
        assert inbound["parent"] == PARENT_ID
        assert response.headers["tracestate"].split(",")[1:] == ["vendor=one", "other=two"]
        assert item["outgoing"]["tracestate"].split(",")[1:] == ["vendor=one", "other=two"]
    else:
        assert inbound["parent"] is None
        assert context["trace_id"] != TRACE_ID
        assert context["flags"] == "01"
        assert response.headers["tracestate"].split(",")[1:] == []


@pytest.mark.parametrize("flags", ["03", "ff"])
def test_standalone_wire_d_and_be_preserve_their_flag_policy(stack_factory, flags):
    stack = stack_factory(vsp=False)
    with TestClient(stack.app) as client:
        response = _post(client, _traceparent(flags))
    context, item = _assert_one_context(stack, response, observed=False)
    assert context["trace_id"] == TRACE_ID
    assert context["flags"] == flags
    assert item["outgoing"]["traceparent"].endswith("-" + flags)
    assert response.headers["tracestate"].split(",")[1:] == ["vendor=one", "other=two"]


def test_be_only_keeps_its_standalone_logging_fallback(stack_factory):
    stack = stack_factory(vsp=False, wire=False)
    with TestClient(stack.app) as client:
        response = _post(client)
    assert response.status_code == 200
    assert "traceparent" not in response.headers
    assert response.headers["x-trace-id"] == "unrelated-client-log-id"
    assert len(response.headers["x-span-id"]) == 16
    assert stack.captured[0]["context"]["trace_id"] == response.headers["x-trace-id"]
    assert response.json()["trace_observation"]["state"] == "UNAVAILABLE"


@pytest.mark.parametrize("flags", ["00", "01"])
def test_full_chain_uses_the_sdk_span_context_not_a_second_span(
    stack_factory, monkeypatch, flags
):
    sdk_context = types.SimpleNamespace(
        trace_id=int(TRACE_ID, 16), span_id=int(SDK_SPAN_ID, 16), trace_flags=int(flags, 16)
    )
    calls = []

    class Span:
        def get_span_context(self):
            return sdk_context

        def set_attribute(self, key, value):
            pass

    @contextmanager
    def sdk_span(self, name, incoming_traceparent, attrs):
        calls.append(incoming_traceparent)
        yield Span()

    monkeypatch.setattr(otel._Tracer, "server_span", sdk_span)
    stack = stack_factory()
    with TestClient(stack.app) as client:
        response = _post(client, _traceparent(flags))
    context, _ = _assert_one_context(stack, response)
    assert calls == [_traceparent(flags)]
    assert context["trace_id"] == TRACE_ID
    assert context["parent_id"] == SDK_SPAN_ID
    assert context["flags"] == flags


def test_mutated_state_aliases_cannot_retarget_receipts_or_the_cortex_sidecar(stack_factory):
    stack = stack_factory(poison_aliases=True)
    with TestClient(stack.app) as client:
        response = _post(client, _traceparent())
    context, _ = _assert_one_context(stack, response)
    assert context["trace_id"] == TRACE_ID
    assert context["parent_id"] != "f" * 16
    assert response.headers["tracestate"].split(",")[1:] == ["vendor=one", "other=two"]


def test_same_parent_gets_distinct_server_contexts_per_request(stack_factory):
    stack = stack_factory()
    with TestClient(stack.app) as client:
        first = _post(client, _traceparent())
        second = _post(client, _traceparent())
    left, _ = _assert_one_context(stack, first, index=0)
    right, _ = _assert_one_context(stack, second, index=1)
    assert left["trace_id"] == right["trace_id"] == TRACE_ID
    assert left["parent_id"] != right["parent_id"]


def test_valid_looking_x_trace_id_cannot_override_server_context(stack_factory):
    stack = stack_factory()
    with TestClient(stack.app) as client:
        response = _post(client, _traceparent(), log_alias="e" * 32)
    context, _ = _assert_one_context(stack, response)
    assert context["trace_id"] == TRACE_ID
    assert context["trace_id"] != "e" * 32


@pytest.mark.parametrize("fault", [
    "none", "zero-trace", "zero-span", "string-trace", "bool-span",
    "oversized-trace", "oversized-span", "invalid-flags", "raises",
])
def test_malformed_sdk_context_preserves_request_without_observation(
    stack_factory, monkeypatch, fault
):
    sdk_context = types.SimpleNamespace(
        trace_id=int(TRACE_ID, 16), span_id=int(SDK_SPAN_ID, 16), trace_flags=1
    )
    if fault == "zero-trace":
        sdk_context.trace_id = 0
    elif fault == "zero-span":
        sdk_context.span_id = 0
    elif fault == "string-trace":
        sdk_context.trace_id = TRACE_ID
    elif fault == "bool-span":
        sdk_context.span_id = True
    elif fault == "oversized-trace":
        sdk_context.trace_id = 1 << 128
    elif fault == "oversized-span":
        sdk_context.span_id = 1 << 64
    elif fault == "invalid-flags":
        sdk_context.trace_flags = "private-sdk-error-marker"

    class Span:
        def get_span_context(self):
            if fault == "raises":
                raise RuntimeError("private-sdk-error-marker")
            return None if fault == "none" else sdk_context

        def set_attribute(self, key, value):
            pass

    @contextmanager
    def sdk_span(self, name, incoming_traceparent, attrs):
        yield Span()

    monkeypatch.setattr(otel._Tracer, "server_span", sdk_span)
    stack = stack_factory()
    flags = "00" if fault == "none" else "01"
    with TestClient(stack.app) as client:
        response = _post(client, _traceparent(flags))
    context, _ = _assert_one_context(stack, response, observed=False)
    assert context["trace_id"] == TRACE_ID
    assert context["parent_id"] not in (PARENT_ID, "0" * 16)
    assert context["flags"] == flags
    assert "private-sdk-error-marker" not in response.text
    assert "observation_sha256" not in response.json()["trace_observation"]


def test_sdk_new_root_does_not_claim_the_incoming_parent_or_tracestate(
    stack_factory, monkeypatch
):
    sdk_trace_id = "4" * 32
    sdk_context = types.SimpleNamespace(
        trace_id=int(sdk_trace_id, 16), span_id=int(SDK_SPAN_ID, 16), trace_flags=1
    )
    span_attributes = {}
    offered_parents = []

    class Span:
        def get_span_context(self):
            return sdk_context

        def set_attribute(self, key, value):
            span_attributes[key] = value

    @contextmanager
    def sdk_span(self, name, incoming_traceparent, attrs):
        # Mirror the real span wrapper's initial diagnostic attributes. The
        # middleware must correct parent diagnostics after reading the actual
        # SDK context when its propagator did not continue the offered trace.
        offered_parents.append(incoming_traceparent)
        span = Span()
        for key, value in attrs.items():
            span.set_attribute(key, str(value))
        yield span

    monkeypatch.setattr(otel._Tracer, "server_span", sdk_span)
    stack = stack_factory()
    with TestClient(stack.app) as client:
        response = _post(client, _traceparent())
    context, item = _assert_one_context(stack, response)
    assert offered_parents == [_traceparent()]
    assert context["trace_id"] == sdk_trace_id
    assert context["parent_id"] == SDK_SPAN_ID
    assert item["context"]["inbound_parent"] is None
    inbound = [
        row for row in stack.app.state.szl_trace.log
        if row["dir"] == "in" and row["span_id"] == SDK_SPAN_ID
    ]
    assert len(inbound) == 1
    assert inbound[0]["parent"] is None
    assert response.headers["tracestate"] == "szl=" + SDK_SPAN_ID
    outgoing = stack.provenance.parse_traceparent(item["outgoing"]["traceparent"])
    assert item["outgoing"]["tracestate"] == "szl=" + outgoing["parent_id"]
    assert span_attributes["szl.parent_trace_id"] == "(root)"
