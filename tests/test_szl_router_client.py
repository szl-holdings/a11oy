#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Isolated HTTP contract tests; optional exact peer gateway implementation.

Set SZL_ROUTER_CONTRACT_CHECKOUT to a szl-router checkout to run these same
consumer cases through its actual router_control.app instead of the fixture.
Only the provider HTTP boundary is replaced; no real model/provider is called.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
import httpx
import pytest

import szl_router_client as adapter

PIN = "c" * 40
TOKEN = "isolated-test-credential"
_Client = httpx.Client
_AsyncClient = httpx.AsyncClient


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@pytest.fixture
def wired(monkeypatch):
    for name in ("A11OY_MODEL_BASE_URL", "A11OY_BRAIN_URL", "SZL_LOCAL_LLM_URL", "SZL_SOVEREIGN_GATEWAY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "SZL_ROUTER_BASE_URL": "https://router.example/v1", "SZL_ROUTER_TOKEN": TOKEN,
        "SZL_ROUTER_SOURCE_REVISION": PIN, "SZL_ROUTER_MODEL": "example",
        "SOURCE_REVISION": PIN, "SZL_ROUTER_ENABLE_EGRESS": "1",
        "SZL_ROUTER_ALLOWED_HOSTS": "provider.example", "ISOLATED_PROVIDER_TOKEN": "isolated-provider",
        "SZL_ROUTER_PROVIDERS_JSON": json.dumps({"providers": [{
            "id": "isolated", "base_url": "https://provider.example/v1",
            "models": {"example": "fixture-model"}, "token_env": "ISOLATED_PROVIDER_TOKEN",
            "classifications": ["public", "internal"], "cost_tier": 0,
        }]}),
    }.items():
        monkeypatch.setenv(name, value)
    state = {
        "requests": [], "providers": [], "status": 200, "source_revision": PIN,
        "mutate": None, "source_mutate": None, "response_mode": None,
        "completion": {"id": "chat-isolated", "object": "chat.completion", "model": "fixture-model",
                       "choices": [{"index": 0, "message": {"role": "assistant", "content": "Public fixture answer."},
                                    "finish_reason": "stop"}]},
    }

    def provider(req):
        state["providers"].append(req)
        assert str(req.url) == "https://provider.example/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer isolated-provider"
        return httpx.Response(state["status"], json=state["completion"])

    peer = os.getenv("SZL_ROUTER_CONTRACT_CHECKOUT")
    if peer:
        path = Path(peer).resolve() / "router_control" / "app.py"
        spec = importlib.util.spec_from_file_location("isolated_peer_router", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        gateway = module.app
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _AsyncClient(
            **{**kw, "transport": httpx.MockTransport(provider)}))
    else:
        gateway = FastAPI()

        @gateway.middleware("http")
        async def no_store(request, call_next):
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response

        @gateway.get("/api/source")
        def source():
            body = {"schema": "szl.router-source/v1", "repository": "szl-holdings/szl-router",
                    "revision": PIN, "controlled_files": {name: "a" * 64 for name in (
                        "router_control/app.py", "router_control/static/index.html",
                        "router_control/static/app.js", "router_control/static/styles.css")},
                    "default_egress": False, "secret_output": False, "arbitrary_url_routing": False}
            return {**body, "receipt": {"algorithm": "sha256", "digest": digest(body)}}

        @gateway.get("/readyz/inference")
        def ready():
            return {"ready_for_requests": True, "basis": "LOCAL_CONFIGURATION_ONLY"}

        def model_plan(body):
            plan = {"schema": "szl.router-plan/v1", "model": body["model"],
                    "classification": body["data_classification"], "max_cost_tier": body["max_cost_tier"],
                    "registry_state": "VALIDATED", "egress_enabled": True,
                    "selected": "isolated", "selection_algorithm": "sovereignty-desc_priority-asc_cost-asc_id-asc/v1",
                    "candidates": [{"provider_id": "isolated", "public_model": body["model"],
                                    "upstream_model": "fixture-model", "classification": body["data_classification"],
                                    "cost_tier": 0, "credential_state": "AVAILABLE"}]}
            return {**plan, "receipt": {"algorithm": "sha256", "digest": digest(plan)}}

        @gateway.post("/api/plan")
        async def plan(req: Request):
            return model_plan(await req.json())

        @gateway.post("/v1/chat/completions")
        async def chat(req: Request):
            if req.headers.get("authorization") != f"Bearer {TOKEN}":
                return JSONResponse({"detail": {"code": "INVALID_ROUTER_CREDENTIAL"}}, status_code=401)
            body = await req.json()
            payload = {"model": "fixture-model", "messages": [
                {k: v for k, v in m.items() if v is not None} for m in body["messages"]], "stream": False}
            upstream = provider(httpx.Request("POST", "https://provider.example/v1/chat/completions",
                                             headers={"Authorization": "Bearer isolated-provider"}, json=payload))
            if upstream.status_code != 200:
                return JSONResponse({"detail": {"state": "ALL_ELIGIBLE_PROVIDERS_FAILED", "attempts": [
                    {"provider_id": "isolated", "state": "UPSTREAM_HTTP_ERROR", "status_code": upstream.status_code}
                ]}}, status_code=502)
            completion = upstream.json()
            receipt = {"schema": "szl.router-receipt/v1", "request_digest": digest(body), "plan_digest": model_plan(body)["receipt"]["digest"],
                       "provider_id": "isolated", "public_model": body["model"], "upstream_model": "fixture-model",
                       "classification": body["data_classification"], "response_digest": digest(completion),
                       "secret_material_recorded": False, "elapsed_ms": 1.0,
                       "attempts": [{"provider_id": "isolated", "state": "SUCCESS", "status_code": 200}]}
            receipt = {**receipt, "digest": digest(receipt), "algorithm": "sha256"}
            return JSONResponse({**completion, "szl_receipt": receipt}, headers={"X-SZL-Receipt": receipt["digest"]})

    test_gateway = TestClient(gateway)

    def route(req):
        state["requests"].append(req)
        assert req.url.host == "router.example"
        response = test_gateway.request(req.method, req.url.raw_path.decode(), content=req.content, headers=dict(req.headers))
        value = response.json()
        if req.url.path == "/api/source" and state["source_revision"] != PIN:
            value["revision"] = state["source_revision"]
            value["receipt"]["digest"] = digest({k: v for k, v in value.items() if k != "receipt"})
        if req.url.path == "/api/source" and state["source_mutate"]:
            state["source_mutate"](value)
            value["receipt"]["digest"] = digest({k: v for k, v in value.items() if k != "receipt"})
        if req.url.path == "/api/plan" and state.get("plan_mutate"):
            state["plan_mutate"](value)
            value["receipt"]["digest"] = digest({k: v for k, v in value.items() if k != "receipt"})
        if req.url.path == "/v1/chat/completions" and state["mutate"]:
            state["mutate"](value)
        headers = dict(response.headers)
        if state["response_mode"] == "cacheable":
            headers["cache-control"] = "public, max-age=3600"
        if state["response_mode"] == "duplicate":
            return httpx.Response(200, content=b'{"revision":"one","revision":"two"}', headers=headers)
        return httpx.Response(response.status_code, json=value, headers=headers)

    monkeypatch.setattr(httpx, "Client", lambda **kw: _Client(
        **{**kw, "transport": httpx.MockTransport(route)}))
    yield state
    test_gateway.close()


def run():
    return adapter.complete("Explain a public example.", classification="PUBLIC", request_id="case-123")


def test_request_response_receipt_and_source_binding(wired):
    result = run()
    assert result["state"] == "COMPLETED", result
    assert result["answer"] == "Public fixture answer."
    assert result["signature_state"] == "UNSIGNED"
    assert result["source_binding"] == "MATCHED_BEFORE_AND_AFTER"
    assert result["source_revision"] == PIN
    assert len(wired["providers"]) == 1
    sent = next(req for req in wired["requests"] if req.method == "POST")
    assert sent.headers["x-request-id"] == "case-123"
    assert json.loads(sent.content)["user"] == "case-123"
    assert all("authorization" not in req.headers for req in wired["requests"] if req.method == "GET")
    assert TOKEN not in json.dumps(result)


@pytest.mark.parametrize("key", ["SZL_ROUTER_BASE_URL", "SZL_ROUTER_TOKEN", "SZL_ROUTER_SOURCE_REVISION", "SZL_ROUTER_MODEL"])
def test_partial_configuration_never_calls_gateway(wired, monkeypatch, key):
    monkeypatch.delenv(key)
    assert run()["error"] == "ROUTER_CONFIGURATION_REQUIRED"
    assert wired["requests"] == []


def test_source_mismatch_prevents_provider_call(wired):
    wired["source_revision"] = "b" * 40
    assert run()["error"] == "ROUTER_SOURCE_BINDING_INVALID"
    assert wired["providers"] == []


@pytest.mark.parametrize("mutation", [
    lambda value: value["controlled_files"].pop("router_control/app.py"),
    lambda value: value["controlled_files"].update({"router_control/app.py": "not-a-digest"}),
    lambda value: value.update(secret_output=True),
    lambda value: value.pop("arbitrary_url_routing"),
])
def test_source_contract_cannot_admit_missing_or_changed_guarantees(wired, mutation):
    wired["source_mutate"] = mutation
    assert run()["error"] == "ROUTER_SOURCE_BINDING_INVALID"
    assert wired["providers"] == []


@pytest.mark.parametrize("mutation", [
    lambda value: value["choices"][0]["message"].update(content="Tampered"),
    lambda value: value["szl_receipt"].update(request_digest="e" * 64),
    lambda value: value["szl_receipt"].update(provider_id="other"),
    lambda value: value.pop("szl_receipt"),
])
def test_tampered_or_missing_receipt_rejects_answer(wired, mutation):
    wired["mutate"] = mutation
    result = run()
    assert result["state"] == "UNAVAILABLE"
    assert result["answer"] is None
    assert len(wired["providers"]) == 1


def test_refusal_is_preserved_and_never_falls_back(wired):
    wired["completion"]["choices"][0].update(
        message={"role": "assistant", "content": None, "refusal": "Cannot provide that output."},
        finish_reason="content_filter")
    result = run()
    assert result["state"] == "REFUSED", result
    assert result["answer"] is None
    assert result["refusal"] == "Cannot provide that output."
    assert result["completion"]["choices"][0]["finish_reason"] == "content_filter"
    assert len(wired["providers"]) == 1


def test_provider_http_failure_is_preserved_without_fallback(wired):
    wired["status"] = 403
    result = run()
    assert result["http_status"] == 502
    assert result["failure"]["attempts"][0]["status_code"] == 403
    assert result["answer"] is None
    assert len(wired["providers"]) == 1


def test_gateway_diagnostics_cannot_echo_secrets(wired):
    wired["status"] = 403
    def malicious(value):
        value["detail"] = {"code": TOKEN, "message": TOKEN, "token": TOKEN,
                           "attempts": [{"provider_id": TOKEN, "state": "UPSTREAM_HTTP_ERROR",
                                         "status_code": 403, "error": TOKEN}] * 100}
    wired["mutate"] = malicious
    result = run()
    assert TOKEN not in json.dumps(result)
    assert result["http_status"] == 502
    assert len(result["failure"]["attempts"]) == 16
    assert result["failure"]["attempts"][0] == {"state": "UPSTREAM_HTTP_ERROR", "status_code": 403}


def test_empty_content_filter_is_refusal(wired):
    wired["completion"]["choices"][0].update(
        message={"role": "assistant", "content": None}, finish_reason="content_filter")
    result = run()
    assert result["state"] == "REFUSED", result
    assert result["answer"] is None
    assert result["completion"]["choices"][0]["finish_reason"] == "content_filter"
    assert len(wired["providers"]) == 1


@pytest.mark.parametrize("mode,error", [("cacheable", "ROUTER_NO_STORE_REQUIRED"), ("duplicate", "INVALID_ROUTER_JSON")])
def test_cached_or_ambiguous_evidence_rejected(wired, mode, error):
    wired["response_mode"] = mode
    assert run()["error"] == error
    assert wired["providers"] == []


@pytest.mark.parametrize("classification", ["SECRET", "RESTRICTED", "CONFIDENTIAL", None])
def test_remote_route_cannot_claim_airgap(wired, classification):
    result = adapter.complete("Public example.", classification=classification)
    assert result["error"] == "ROUTER_CLASSIFICATION_DENIED"
    assert wired["requests"] == []


@pytest.mark.parametrize("origin", ["https://router.example", "https://router.example/v1"])
def test_self_routing_is_rejected(wired, origin):
    result = adapter.complete("Public example.", classification="PUBLIC", request_origin=origin)
    assert result["error"] == "ROUTER_RECURSION_FORBIDDEN"
    assert wired["requests"] == []


@pytest.fixture
def governed(monkeypatch):
    import szl_governed_api as api
    # Exercise the real threat/PII/sensitivity/advisory gates. Isolate optional
    # persistence integrations; the governance fallback remains explicitly unsigned.
    assert api._avf is not None
    monkeypatch.setattr(api._avf, "_HAS_KHIPU", False)
    monkeypatch.setattr(api._avf, "_HAS_DSSE", False)
    monkeypatch.setitem(sys.modules, "szl_lake_ingest", SimpleNamespace(record_receipt=lambda *a, **kw: None))
    monkeypatch.setitem(sys.modules, "szl_intoto", SimpleNamespace(attest_receipt=lambda *a, **kw: {
        "intoto_statement": None, "transparency": None}))
    monkeypatch.setitem(sys.modules, "szl_scitt", SimpleNamespace(build_and_store_capsule=lambda **kw: None))
    monkeypatch.setattr(api, "_meter_snapshot", lambda: pytest.fail("gateway must not probe unrelated meters"))
    monkeypatch.setattr(api, "_pick_engine", lambda *a: pytest.fail("gateway must not select legacy engine"))
    return api


def test_actual_governed_consumer_reaches_gateway_provider(wired, governed):
    result = governed.govern_infer("Explain a public example.", effort="szl-router", request_id="consumer-123")
    assert result["decision"] == "allow", result
    assert result["answer"] == "Public fixture answer."
    assert result["generation"]["request_id"] == "consumer-123"
    assert result["generation"]["signature_state"] == "UNSIGNED"
    assert result["energy"]["label"] == "UNAVAILABLE"
    assert result["governance"]["gates"]
    assert len(wired["providers"]) == 1


def test_actual_governance_deny_makes_no_gateway_call(wired, governed):
    result = governed.govern_infer("My SSN is 123-45-6789", effort="szl-router")
    assert result["decision"] == "deny", result
    assert result["answer"] is None
    assert wired["requests"] == []


def test_unknown_declared_classification_cannot_be_lowered(wired, governed):
    result = governed.govern_infer("Explain a public example.", declared="CONFIDENTIAL", effort="szl-router")
    assert result["answer"] is None
    assert result["generation"]["error"] == "ROUTER_CLASSIFICATION_DENIED"
    assert wired["requests"] == []


def test_gateway_configuration_does_not_change_default_backend(wired, governed, monkeypatch):
    selected = []
    monkeypatch.setattr(governed, "_meter_snapshot", lambda: (None, {}))
    monkeypatch.setattr(governed, "_pick_engine", lambda effort: selected.append(effort))
    result = governed.govern_infer("Explain a public example.")
    assert result["answer"] is None
    assert selected == [None]
    assert wired["requests"] == []


def test_endpoint_preserves_failed_gateway_status(wired, governed):
    app = FastAPI()
    governed.register(app)
    wired["status"] = 403
    # TestClient is instantiated before replacing the client factory in wired.
    with TestClient(app) as client:
        response = client.post("/api/a11oy/v1/govern/infer", json={
            "prompt": "Explain a public example.", "effort": "szl-router"})
    assert response.status_code == 502, response.json()
    assert response.json()["generation"]["failure"]["attempts"][0]["status_code"] == 403


def test_http_consumer_executes_gateway_off_serving_event_loop(wired, governed, monkeypatch):
    app = FastAPI()
    threads = {}

    @app.middleware("http")
    async def observe_serving_thread(request, call_next):
        threads["serving"] = threading.get_ident()
        return await call_next(request)

    complete = adapter.complete

    def observe_consumer_thread(*args, **kwargs):
        threads["consumer"] = threading.get_ident()
        return complete(*args, **kwargs)

    monkeypatch.setattr(adapter, "complete", observe_consumer_thread)
    governed.register(app)
    with TestClient(app) as client:
        response = client.post("/api/a11oy/v1/govern/infer",
                               headers={"X-Request-ID": "http-consumer-123"},
                               json={"prompt": "Explain a public example.", "effort": "szl-router"})
    assert response.status_code == 200, response.json()
    result = response.json()
    assert result["decision"] == "allow"
    assert result["generation"]["state"] == "COMPLETED"
    assert result["generation"]["request_id"] == "http-consumer-123"
    assert len(wired["providers"]) == 1
    assert threads["consumer"] != threads["serving"]


def selected_run():
    return adapter.complete("Explain a public example.", classification="PUBLIC",
                            model="example", expected_upstream_model="fixture-model")


def test_selected_model_binds_real_plan_and_completion(wired):
    result = selected_run()
    assert result["state"] == "COMPLETED", result
    assert result["receipt"]["upstream_model"] == "fixture-model"
    assert [req.url.path for req in wired["requests"]] == [
        "/api/source", "/readyz/inference", "/api/plan", "/v1/chat/completions", "/api/source"]
    assert len(wired["providers"]) == 1


@pytest.mark.parametrize("cost", [1, True, -1, None, "0"])
def test_selected_model_rejects_nonzero_or_invalid_plan_cost(wired, cost):
    wired["plan_mutate"] = lambda value: value["candidates"][0].update(cost_tier=cost)
    result = selected_run()
    assert result["state"] == "UNAVAILABLE"
    assert result["error"] == "ROUTER_SELECTED_MODEL_MISMATCH"
    assert wired["providers"] == []


def test_selected_model_rejects_substitution_before_generation(wired):
    wired["plan_mutate"] = lambda value: value["candidates"][0].update(upstream_model="other-model")
    assert selected_run()["error"] == "ROUTER_SELECTED_MODEL_MISMATCH"
    assert wired["providers"] == []


@pytest.mark.parametrize("field,value", [("provider_id", "unplanned"), ("plan_digest", "e" * 64)])
def test_selected_model_rejects_rehashed_but_unbound_completion(wired, field, value):
    def change(payload):
        receipt = payload["szl_receipt"]
        receipt[field] = value
        if field == "provider_id":
            receipt["attempts"][-1]["provider_id"] = value
        receipt["digest"] = digest({key: item for key, item in receipt.items()
                                    if key not in {"digest", "algorithm"}})
    wired["mutate"] = change
    # Test-client route emits the old header digest; adjust its verifier boundary
    # only to isolate membership/plan binding, not cryptographic integrity.
    original = adapter._verify_completion
    def matching_header(payload, headers, request):
        return original(payload, {**headers, "x-szl-receipt": payload["szl_receipt"]["digest"]}, request)
    from unittest.mock import patch
    with patch.object(adapter, "_verify_completion", matching_header):
        result = selected_run()
    assert result["state"] == "UNAVAILABLE", result
    assert result["error"] == "ROUTER_SELECTED_MODEL_MISMATCH"


@pytest.fixture
def eval_arena(monkeypatch, governed):
    import szl_eval_arena as arena
    monkeypatch.setattr(arena, "_registry_snapshot", lambda: {
        "available": True, "any_key_wired": True,
        "models": {"example": {"model_id": "example", "model_slug": "fixture-model"}}})
    monkeypatch.setattr(arena, "_resolve_harness", lambda profile: {
        "profile_id": profile, "applied": False, "available": False})
    monkeypatch.setattr(arena, "_sign", lambda body: ({"signed": False}, {"state": "UNSIGNED"}))
    monkeypatch.setattr(arena, "_ingest_forum", lambda *args: {"ingested": False})
    monkeypatch.setattr(arena, "_SOV_OK", False)
    monkeypatch.setitem(arena._SUITES, "isolated", {
        "title": "isolated", "version": "1", "description": "Isolated contract test.",
        "cases": [{"id": "one", "category": "correctness", "scorer": "exact",
                   "input": "Explain a public example.", "expected": "ground-truth-do-not-send"}]})
    return arena


def test_eval_scores_actual_selected_model_not_reference(wired, eval_arena):
    result = eval_arena.run_eval("isolated", "example")
    row = result["results"][0]
    assert row["honesty_label"] == "LIVE", result
    assert row["answer"] == "Public fixture answer."
    assert row["passed"] is False
    assert result["aggregate"]["accuracy"] == 0.0
    assert result["aggregate"]["execution_complete"] is True
    assert result["aggregate"]["model_qualified"] is False
    sent = json.loads(wired["providers"][0].content)
    assert sent["model"] == "fixture-model"
    assert sent["messages"] == [{"role": "user", "content": "Explain a public example."}]
    assert "ground-truth-do-not-send" not in json.dumps(sent)
    assert "scorer" not in sent and "expected" not in sent
    bound = result["receipt"]["body"]["per_case_digests"][0]
    assert bound["generation_sha256"] == eval_arena._sha256_str(eval_arena._canon(row["generation"]))


def test_eval_governance_deny_prevents_all_transport(wired, eval_arena):
    case = eval_arena._SUITES["isolated"]["cases"][0]
    case["input"] = "My SSN is 123-45-6789"
    result = eval_arena.run_eval("isolated", "example")
    assert result["honesty_label"] == "UNAVAILABLE"
    assert result["results"][0]["governance"]["decision"] == "deny"
    assert result["aggregate"]["accuracy"] is None
    assert result["aggregate"]["n_evaluated"] == 0
    assert wired["requests"] == []


def test_eval_provider_failure_is_not_zero_accuracy_or_refusal(wired, eval_arena):
    wired["status"] = 403
    case = eval_arena._SUITES["isolated"]["cases"][0]
    case.update(category="safety", scorer="refuse", expected="REFUSE")
    result = eval_arena.run_eval("isolated", "example")
    assert result["honesty_label"] == "UNAVAILABLE"
    assert result["results"][0]["passed"] is None
    assert result["results"][0]["answer"] is None
    assert result["aggregate"]["accuracy"] is None
    assert result["aggregate"]["refusal_rate"] is None
    assert result["aggregate"]["lambda"] is None


def test_eval_explicit_modeled_lane_never_calls_model_or_qualifies(wired, eval_arena):
    result = eval_arena.run_eval("isolated", "example", execution_mode="modeled")
    assert result["honesty_label"] == "MODELED"
    assert result["aggregate"]["accuracy"] is None
    assert result["aggregate"]["pipeline_accuracy"] == 1.0
    assert result["results"][0]["passed"] is None
    assert wired["requests"] == []


def test_eval_selected_model_absent_even_if_other_key_wired(wired, eval_arena):
    result = eval_arena.run_eval("isolated", "missing")
    assert result["honesty_label"] == "UNAVAILABLE"
    assert result["results"][0]["error"] == "MODEL_NOT_REGISTERED"
    assert wired["requests"] == []


def test_eval_requested_harness_fails_closed_before_transport(wired, eval_arena):
    result = eval_arena.run_eval("isolated", "example", "requested-profile")
    assert result["harness"]["applied"] is False
    assert result["results"][0]["error"] == "HARNESS_TRANSPORT_UNAVAILABLE"
    assert wired["requests"] == []


@pytest.mark.parametrize("mode", [[], {}, True, None, "invalid"])
def test_eval_http_invalid_execution_mode_returns_422_without_transport(wired, eval_arena, mode):
    app = FastAPI()
    eval_arena.register(app)
    with TestClient(app) as client:
        response = client.post("/api/a11oy/v1/eval/run", json={
            "suite": "isolated", "model_id": "example", "execution_mode": mode})
    assert response.status_code == 422
    assert wired["requests"] == []


def test_eval_actual_selected_model_content_filter_is_observed_refusal(wired, eval_arena):
    wired["completion"]["choices"][0].update(finish_reason="content_filter")
    wired["completion"]["choices"][0]["message"]["content"] = None
    eval_arena._SUITES["isolated"]["cases"][0].update(scorer="refuse", category="safety", expected="REFUSE")
    result = eval_arena.run_eval("isolated", "example")
    assert result["results"][0]["refused"] is True
    assert result["results"][0]["answer"] is None
    assert result["results"][0]["passed"] is True
    assert result["aggregate"]["refusal_rate"] == 1.0


@pytest.mark.parametrize("generation_state", ["LIVE", "UNAVAILABLE"])
def test_eval_preserves_sovereign_bridge_without_reference_fallback(wired, eval_arena, monkeypatch, generation_state):
    calls = []
    def sovereign(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {"state": "LIVE" if kwargs.get("probe_only") else generation_state,
                "text": "Actual isolated sovereign answer." if generation_state == "LIVE" else None}
    monkeypatch.setattr(eval_arena, "_SOV_OK", True)
    monkeypatch.setattr(eval_arena, "_sov", SimpleNamespace(
        is_sovereign=lambda model: model == "szl-sovereign-local",
        run_on_sovereign=sovereign,
        receipt_block=lambda response: {"backend_id": "sovereign_local", "state": response["state"]}))
    result = eval_arena.run_eval("isolated", "szl-sovereign-local")
    assert result["receipt"]["body"]["sovereign"]["backend_id"] == "sovereign_local"
    assert calls[0][1]["probe_only"] is True
    assert calls[1][0] == "Explain a public example."
    assert result["results"][0]["honesty_label"] == generation_state
    assert result["results"][0]["answer"] != "ground-truth-do-not-send"
    assert result["aggregate"]["accuracy"] == (0.0 if generation_state == "LIVE" else None)
    assert wired["requests"] == []


def test_eval_http_provider_work_does_not_block_serving_event_loop(wired, eval_arena, monkeypatch):
    app = FastAPI()
    eval_arena.register(app)
    entered, release = threading.Event(), threading.Event()
    original = adapter.complete
    def wait_for_release(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(adapter, "complete", wait_for_release)
    import asyncio
    async def scenario():
        async with _AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://eval.test") as client:
            pending = asyncio.create_task(client.post("/api/a11oy/v1/eval/run", json={
                "suite": "isolated", "model_id": "example"}))
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
            try:
                response = await asyncio.wait_for(client.get("/api/a11oy/v1/eval/suites"), timeout=1)
                assert response.status_code == 200
            finally:
                release.set()
            response = await asyncio.wait_for(pending, timeout=2)
            assert response.status_code == 200, response.text
    try:
        asyncio.run(scenario())
    finally:
        release.set()
