#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline loop evidence: orchestration and signatures do not prove completion."""

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODEL = "fixture-selected-model"
SUITE = "fixture-suite"


def engine_result():
    return {
        "decision": "ALLOW", "emitted": True, "answer": "Fixture answer",
        "gate": {"severity": "low"}, "lambda": 0.9,
        "inference": {"mode": "generative", "model": MODEL, "attempts": 1,
                      "rate_limited": False, "error": None},
        "backend": {"mode": "fixture-only"},
        "executed": False, "execution_status": "NOT_REQUESTED",
        "signed_receipt": {"signed": False, "signatures": [], "payload": "fixture"},
    }


def eval_result():
    return {
        "status_code": 200, "suite": {"id": SUITE, "sha256": "a" * 64},
        "model_id": MODEL, "execution_mode": "live", "honesty_label": "LIVE",
        "aggregate": {"n_cases": 1, "n_evaluated": 1, "n_passed": 1,
                      "n_unavailable": 0, "execution_complete": True,
                      "score_basis": "MODEL_RESPONSES_ONLY", "accuracy": 1.0,
                      "lambda": 0.9, "lambda_status": "CONJECTURE",
                      "model_qualified": False},
        "results": [{"id": "case-1", "evaluated": True, "passed": True,
                     "honesty_label": "LIVE", "answer": "Fixture answer",
                     "answer_sha256": "b" * 64, "error": None,
                     "generation": {"state": "COMPLETED", "answer": "Fixture answer",
                                    "source_binding": "MATCHED_BEFORE_AND_AFTER",
                                    "receipt": {"public_model": MODEL}},
                     "governance": {"decision": "allow"}}],
        "receipt": {"body": {"schema": "fixture.eval", "model_id": MODEL},
                    "dsse": {"signed": False, "signatures": [], "payload": "fixture"},
                    "signing": {"mode": "UNSIGNED-LOCAL"}},
        "forum_ingest": {"ingested": False},
    }


@pytest.fixture
def runtime():
    engine = SimpleNamespace(governed_turn=Mock(return_value=engine_result()))
    arena = SimpleNamespace(run_eval=Mock(return_value=eval_result()))
    planner = SimpleNamespace(plan=Mock(return_value={
        "run_id": "offline-fixture", "mode": "chat", "plan": [
            {"n": 1, "title": "Fixture step", "mode": "chat", "prompt": "Fixture task",
             "sandbox": False, "state_changing": False}]}))
    approval = Mock(return_value={"required": False, "granted": None})
    stubs = {
        "a11oy_code_engine": engine, "a11oy_code_runloop": planner,
        "szl_eval_arena": arena, "szl_model_harness": SimpleNamespace(),
        "szl_agentic_loop": SimpleNamespace(approval_interrupt=approval),
        "szl_sovereign_flywheel": SimpleNamespace(is_sovereign=lambda _: False),
        "szl_agentloop_brain": SimpleNamespace(),
        "szl_operator_auth": SimpleNamespace(),
    }
    spec = importlib.util.spec_from_file_location(
        "isolated_governed_loop_completion", ROOT / "szl_agent_loop_governed.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    module._BRAINFEED_OK = False
    module._ingest_forum = Mock(return_value={"ingested": False})
    signed = []

    def sign(payload):
        signed.append(copy.deepcopy(payload))
        return {"signed": False, "signatures": [], "payloadType": "application/test+json"}

    def run(**kwargs):
        options = {"mode": "chat", "model_id": MODEL, "eval_suite": SUITE,
                   "max_retries": 0, "sandbox": False,
                   "consult_brain": False, "allocate_energy": False}
        options.update(kwargs)
        return module.run_loop("Fixture task", sign, **options)

    return SimpleNamespace(module=module, engine=engine, arena=arena, planner=planner,
                           approval=approval, run=run, signed=signed)


def assert_not_complete(result):
    assert result["ok"] is False
    assert result["completion"]["state"] != "OBSERVED_COMPLETE"
    assert result["completion"]["complete"] is False
    assert not result["label"].startswith("LIVE")
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("inference", [
    None, {}, {"mode": "local-deterministic", "model": None},
    {"mode": "unavailable", "model": None, "error": "MODEL_UNAVAILABLE"},
    {"mode": "unknown", "model": MODEL},
    {"mode": "generative", "model": "different-model", "attempts": 1},
    {"mode": "generative", "model": MODEL, "attempts": True},
    {"mode": "generative", "model": MODEL, "attempts": float("inf")},
])
def test_unknown_local_unavailable_or_fallback_generation_cannot_pass(runtime, inference):
    runtime.engine.governed_turn.return_value["inference"] = inference
    assert_not_complete(runtime.run())


@pytest.mark.parametrize("field,value", [
    ("n_cases", 0), ("n_cases", True), ("n_cases", float("nan")),
    ("n_evaluated", 0), ("n_evaluated", True), ("n_evaluated", float("inf")),
    ("n_passed", True), ("n_passed", 2), ("n_unavailable", 1),
    ("execution_complete", False), ("execution_complete", 1),
    ("score_basis", "NO_MODEL_RESPONSES"), ("accuracy", float("nan")),
    ("accuracy", True), ("lambda", float("inf")), ("lambda", 10 ** 400),
])
def test_incomplete_or_malformed_eval_counts_cannot_pass(runtime, field, value):
    runtime.arena.run_eval.return_value["aggregate"][field] = value
    assert_not_complete(runtime.run())


@pytest.mark.parametrize("field,value", [
    ("honesty_label", "MODELED"), ("execution_mode", "modeled"),
    ("model_id", "other-model"), ("results", []),
    ("results", [{"id": "case-1", "evaluated": False}]),
    ("error", "MODEL_UNAVAILABLE"), ("status_code", 503),
])
def test_modeled_wrong_model_or_failed_eval_cannot_pass(runtime, field, value):
    runtime.arena.run_eval.return_value[field] = value
    assert_not_complete(runtime.run())


@pytest.mark.parametrize("mutation", ["deny", "hold", "rejected", "unknown", "engine-error",
                                      "eval-error", "no-emission", "empty-plan"])
def test_signed_orchestration_is_not_execution_success(runtime, mutation):
    if mutation == "deny":
        runtime.engine.governed_turn.return_value["decision"] = "DENY"
    elif mutation == "hold":
        runtime.approval.return_value = {"required": True, "granted": None}
    elif mutation == "rejected":
        runtime.approval.return_value = {"required": True, "granted": False}
    elif mutation == "unknown":
        runtime.approval.return_value = {"required": None, "granted": None}
    elif mutation == "engine-error":
        runtime.engine.governed_turn.side_effect = RuntimeError("sensitive-provider-error")
    elif mutation == "eval-error":
        runtime.arena.run_eval.side_effect = RuntimeError("sensitive-provider-error")
    elif mutation == "no-emission":
        runtime.engine.governed_turn.return_value["emitted"] = False
    else:
        runtime.planner.plan.return_value["plan"] = []
    assert_not_complete(runtime.run())


def test_reported_completion_preserves_evidence_without_qualification(runtime):
    result = runtime.run()
    assert result["ok"] is True
    assert result["orchestration_complete"] is True
    completion = result["completion"]
    assert completion["state"] == "OBSERVED_COMPLETE"
    assert completion["evidence_basis"] == "UPSTREAM_REPORTED_UNVERIFIED"
    assert completion["receipt_verification_asserted"] is False
    assert completion["model_qualified"] is False
    attempt = result["steps"][0]["final"]
    assert attempt["engine"]["inference"] == engine_result()["inference"]
    assert attempt["engine"]["signed_receipt"] == engine_result()["signed_receipt"]
    row = dict(attempt["eval"]["evidence"]["results"][0])
    assert row.pop("generation_source_sha256") == runtime.module._sha256(
        runtime.module._canon(eval_result()["results"][0]["generation"]))
    assert row == eval_result()["results"][0]
    assert attempt["eval"]["evidence"]["receipt"] == eval_result()["receipt"]
    assert runtime.signed[-1]["completion"] == completion
    assert result["retry_policy"]["engine_internal_retries_bounded"] is False
    assert result["retry_policy"]["budget_enforcement_asserted"] is False
    assert runtime.engine.governed_turn.call_count == 1
    assert runtime.arena.run_eval.call_count == 1


def test_low_quality_complete_evaluation_is_not_model_qualification(runtime):
    evidence = runtime.arena.run_eval.return_value
    evidence["results"][0]["passed"] = False
    evidence["aggregate"].update(n_passed=0, accuracy=0.0)
    result = runtime.run()
    assert result["completion"]["complete"] is True
    assert result["completion"]["model_qualified"] is False
    assert result["aggregate"]["mean_eval_accuracy"] == 0.0


def test_evidence_is_chained_and_independent_of_mutable_upstream_objects(runtime):
    result = runtime.run()
    step = result["steps"][0]
    body = {"n": step["n"], "title": step["title"], "mode": step["mode"],
            "sandbox": step["sandbox"], "state_changing": step["state_changing"],
            "suite_id": step["suite_id"], "attempts": len(step["attempts"]),
            "attempt_evidence_sha256": step["attempt_evidence_sha256"],
            "final": step["final"], "prev_digest": ""}
    assert runtime.module._sha256(runtime.module._canon(body)) == step["step_digest"]
    runtime.engine.governed_turn.return_value["inference"]["model"] = "changed-after-run"
    runtime.arena.run_eval.return_value["results"][0]["answer"] = "changed-after-run"
    assert step["final"]["engine"]["inference"]["model"] == MODEL
    assert step["final"]["eval"]["evidence"]["results"][0]["answer"] == "Fixture answer"


def test_errors_and_unrecognized_provider_fields_are_not_exported(runtime):
    raw = "Bearer sensitive-provider-secret"
    runtime.engine.governed_turn.return_value["inference"]["error"] = raw
    runtime.engine.governed_turn.return_value["inference"]["authorization"] = raw
    runtime.engine.governed_turn.return_value["error"] = raw
    runtime.arena.run_eval.return_value["error"] = raw
    runtime.arena.run_eval.return_value["authorization"] = raw
    runtime.arena.run_eval.return_value["results"][0]["error"] = raw
    result = runtime.run()
    assert_not_complete(result)
    assert raw not in json.dumps(result)
    assert result["steps"][0]["final"]["engine"]["error"] == "UPSTREAM_ERROR_REDACTED"


def test_engine_unavailable_has_same_failure_contract(runtime):
    runtime.module._ENGINE_OK = False
    runtime.module._ENGINE_ERR = "fixture import failure"
    result = runtime.run()
    assert_not_complete(result)
    assert result["orchestration_complete"] is False
    assert runtime.engine.governed_turn.call_count == 0
    assert runtime.arena.run_eval.call_count == 0


@pytest.mark.parametrize("model_id", ["", "   "])
def test_missing_explicit_model_cannot_be_reported_selected_completion(runtime, model_id):
    assert_not_complete(runtime.run(model_id=model_id))


def test_all_retry_evidence_is_bound_not_only_final_attempt(runtime):
    first_eval = eval_result()
    first_eval["aggregate"].update(accuracy=0.0, n_passed=0)
    first_eval["results"][0]["passed"] = False
    runtime.arena.run_eval.side_effect = [first_eval, eval_result()]
    first_engine = engine_result()
    first_engine["inference"]["model"] = "fallback-model"
    runtime.engine.governed_turn.side_effect = [first_engine, engine_result()]
    result = runtime.run(max_retries=1)
    step = result["steps"][0]
    assert len(step["attempts"]) == 2
    before = step["attempt_evidence_sha256"]
    assert before == runtime.module._sha256(runtime.module._canon(step["attempts"]))
    assert result["composite_receipt"]["body"]["step_chain"][0]["digest"] == step["step_digest"]
    step["attempts"][0]["engine"]["inference"]["model"] = "tampered-model"
    assert before != runtime.module._sha256(runtime.module._canon(step["attempts"]))


@pytest.mark.parametrize("field,value", [("answer", ""), ("answer", "   "), ("answer", None)])
def test_empty_engine_output_cannot_complete(runtime, field, value):
    runtime.engine.governed_turn.return_value[field] = value
    assert_not_complete(runtime.run())


@pytest.mark.parametrize("mutation", ["empty-answer", "different-answer", "unknown-generation",
                                      "wrong-generation-model", "duplicate-case", "nonboolean-pass",
                                      "malformed-generation-state"])
def test_missing_or_inconsistent_case_evidence_cannot_complete(runtime, mutation):
    evidence = runtime.arena.run_eval.return_value
    row = evidence["results"][0]
    if mutation == "empty-answer":
        row["answer"] = row["generation"]["answer"] = ""
    elif mutation == "different-answer":
        row["generation"]["answer"] = "Not the evaluated answer"
    elif mutation == "unknown-generation":
        row["generation"]["state"] = "UNKNOWN"
    elif mutation == "malformed-generation-state":
        row["generation"]["state"] = []
    elif mutation == "wrong-generation-model":
        row["generation"]["receipt"]["public_model"] = "other-model"
    elif mutation == "duplicate-case":
        evidence["results"].append(copy.deepcopy(row))
        evidence["aggregate"].update(n_cases=2, n_evaluated=2, n_passed=2)
    else:
        row["passed"] = 1
    assert_not_complete(runtime.run())


def test_observed_refusal_counts_as_execution_not_invented_answer(runtime):
    row = runtime.arena.run_eval.return_value["results"][0]
    row.update(refused=True, answer=None)
    row["generation"].update(state="REFUSED", answer=None, refusal=None)
    assert runtime.run()["completion"]["complete"] is True


@pytest.mark.parametrize("executed", ["false", "true", 1, None])
def test_sandbox_execution_requires_real_boolean_observation(runtime, executed):
    engine = runtime.engine.governed_turn.return_value
    engine.update(executed=executed, execution_status="EXECUTED")
    assert_not_complete(runtime.run(sandbox=True))


def test_nonfinite_evidence_returns_encodable_unavailable_http_response(runtime):
    from starlette.responses import JSONResponse
    runtime.arena.run_eval.return_value["aggregate"].update(n_evaluated=float("inf"), accuracy=float("nan"))
    result = runtime.run()
    assert_not_complete(result)
    assert JSONResponse(result).status_code == 200


# Assembled route controls exercise real gates and completion with a fixture provider.
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real ASGI admission + loop/engine/eval; only provider/signer/forum boundaries replaced."""
import copy
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_code_engine as strict_engine
import a11oy_vertical_feeds as strict_vertical
import szl_agent_loop_governed as strict_loop
import szl_eval_arena as strict_arena

STRICT_ORIGINAL_CLIENT = httpx.Client
STRICT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
STRICT_SUITE = "independent-review-suite"
STRICT_LIMITS = {"max_model_requests": 2, "max_output_tokens": 100, "max_elapsed_seconds": 5}
STRICT_HEADERS = {"Authorization": "Bearer review-fixture-operator", "X-A11oy-Tenant": "review-fixture-tenant"}
STRICT_LOOP_PATH = "/api/a11oy/v1/agentloop/run"
STRICT_EVAL_PATH = "/api/a11oy/v1/eval/run"
STRICT_BODY = {"task": "What is two plus two?", "mode": "chat", "model_id": STRICT_MODEL,
        "eval_suite": STRICT_SUITE, "max_retries": 0, "sandbox": False,
        "consult_brain": False, "allocate_energy": False, "execution_limits": STRICT_LIMITS}


@pytest.fixture
def strict_app_boundary(monkeypatch):
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "review-fixture-operator")
    monkeypatch.setenv("A11OY_CODE_TENANT", "review-fixture-tenant")
    monkeypatch.delenv("A11OY_APPROVAL_INTERRUPT", raising=False)
    monkeypatch.setattr(strict_engine, "_MODEL_BASE_URL", "https://fixed.example/v1")
    monkeypatch.setattr(strict_engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.setattr(strict_engine, "_HF_TOKEN", "review-fixture-provider")
    monkeypatch.setattr(strict_engine, "_retrieve_with_identity", lambda *a, **k: ([], {}))
    monkeypatch.setattr(strict_vertical, "_HAS_KHIPU", False)
    monkeypatch.setattr(strict_vertical, "_HAS_DSSE", False)
    monkeypatch.setitem(strict_arena._SUITES, STRICT_SUITE, {"title": "Independent review", "version": "1",
        "description": "Fixture, not model qualification", "cases": [
            {"id": "sum", "input": "What is two plus two?", "expected": "4",
             "category": "correctness", "scorer": "exact"}]})
    state = {"calls": [], "signed": [], "eval_signed": [], "forums": [], "status": 200, "usage": 1}
    def sign(value):
        if state.get("sign_hook"):
            state["sign_hook"](value)
        state["signed"].append(copy.deepcopy(value))
        return {"signed": False, "signatures": [], "payload": "isolated-review"}
    def eval_sign(value):
        state["eval_signed"].append(copy.deepcopy(value))
        return ({"signed": False, "signatures": []}, {"mode": "UNSIGNED-LOCAL"})
    def forum(*args):
        state["forums"].append(args)
        return {"ingested": False}
    monkeypatch.setattr(strict_arena, "_sign", eval_sign)
    monkeypatch.setattr(strict_arena, "_ingest_forum", forum)
    monkeypatch.setattr(strict_loop, "_ingest_forum", forum)
    app = FastAPI()
    strict_arena.register(app)
    strict_loop.register(app, sign_fn=sign)
    api = TestClient(app)
    def provider(request):
        assert request.url.host == "fixed.example"
        state["calls"].append(request)
        selected = json.loads(request.content)["model"]
        return httpx.Response(state["status"], headers={"content-type": "application/json"},
            json={"model": selected, "choices": [{"message": {"role": "assistant", "content": "4"},
                   "finish_reason": "stop"}], "usage": state.get("usage_fields", {"completion_tokens": state["usage"]})})
    monkeypatch.setattr(httpx, "Client", lambda **kw: STRICT_ORIGINAL_CLIENT(
        **{**kw, "transport": httpx.MockTransport(provider)}))
    yield api, state
    api.close()


def test_strict_integration_real_single_step_and_eval_share_exact_client_budget(strict_app_boundary):
    api, state = strict_app_boundary
    response = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=STRICT_BODY)
    result = response.json()
    assert response.status_code == 200, result
    assert result["ok"] is True, result
    assert result["completion"]["complete"] is True
    assert len(result["steps"]) == 1
    assert len(state["calls"]) == 2
    sent = [json.loads(req.content) for req in state["calls"]]
    assert all(body["model"] == STRICT_MODEL for body in sent)
    assert sum(body["max_tokens"] for body in sent) == 100
    assert result["completion"]["evidence_basis"] == "UPSTREAM_REPORTED_UNVERIFIED"
    assert result["completion"]["model_qualified"] is False
    assert result["retry_policy"]["execution_limits"]["model_requests"] == 2
    assert result["retry_policy"]["execution_limits"]["usage_complete"] is True


@pytest.mark.parametrize("first_failure", ["http_error", "unknown_usage", "excess_usage"])
def test_strict_integration_actual_failed_chat_never_calls_self_eval(strict_app_boundary, first_failure):
    api, state = strict_app_boundary
    if first_failure == "http_error":
        state["status"] = 503
    elif first_failure == "unknown_usage":
        state["usage"] = None
    else:
        state["usage"] = 51
    result = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=STRICT_BODY).json()
    assert result["ok"] is False
    assert result["completion"]["complete"] is False
    assert len(state["calls"]) == 1
    assert state["eval_signed"] == []


@pytest.mark.parametrize("mutation", [
    lambda b: b.update(execution_limits=None),
    lambda b: b.update(consult_brain="false"),
    lambda b: b.update(max_retries=False),
    lambda b: b.update(model=STRICT_MODEL),
    lambda b: b.update(approval={"approved": True}),
    lambda b: b.update(sandbox=True),
    lambda b: b.update(mode="research"),
])
def test_strict_integration_real_route_rejects_unsafe_scope_before_any_effect(strict_app_boundary, mutation):
    api, state = strict_app_boundary
    body = copy.deepcopy(STRICT_BODY)
    mutation(body)
    response = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=body)
    assert response.status_code == 422
    assert state["calls"] == [] and state["signed"] == [] and state["eval_signed"] == []
    assert state["forums"] == []


@pytest.mark.parametrize("path,body", [(STRICT_LOOP_PATH, STRICT_BODY), (STRICT_EVAL_PATH,
    {"suite": STRICT_SUITE, "model_id": STRICT_MODEL, "execution_mode": "live", "execution_limits": STRICT_LIMITS})])
def test_strict_integration_real_routes_still_require_operator_admission(strict_app_boundary, path, body):
    api, state = strict_app_boundary
    response = api.post(path, json=body)
    assert response.status_code == 401
    assert state["calls"] == [] and state["signed"] == [] and state["eval_signed"] == []


def test_strict_integration_real_route_short_budget_refuses_entire_loop_before_any_effect(strict_app_boundary):
    api, state = strict_app_boundary
    body = copy.deepcopy(STRICT_BODY)
    body["execution_limits"]["max_model_requests"] = 1
    response = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=body)
    assert response.status_code == 422
    assert state["calls"] == [] and state["signed"] == [] and state["eval_signed"] == []


def test_strict_integration_real_eval_preflight_refuses_restricted_case_without_effect(strict_app_boundary, monkeypatch):
    api, state = strict_app_boundary
    monkeypatch.setitem(strict_arena._SUITES[STRICT_SUITE]["cases"][0], "input", "Explain patient care methods.")
    response = api.post(STRICT_EVAL_PATH, headers=STRICT_HEADERS, json={"suite": STRICT_SUITE,
        "model_id": STRICT_MODEL, "execution_mode": "live", "execution_limits": STRICT_LIMITS})
    assert response.status_code == 422, response.text
    assert state["calls"] == [] and state["signed"] == [] and state["eval_signed"] == []
    assert state["forums"] == []


@pytest.mark.parametrize("usage", [
    {"completion_tokens": 1, "prompt_tokens": -1, "total_tokens": 0},
    {"completion_tokens": 1, "prompt_tokens": 2, "total_tokens": 4},
    {"completion_tokens": 1, "prompt_tokens": True, "total_tokens": 2},
    {"completion_tokens": 1, "total_tokens": 2},
])
def test_strict_integration_inconsistent_usage_burns_attempt(strict_app_boundary, usage):
    api, state = strict_app_boundary
    state["usage_fields"] = usage
    result = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=STRICT_BODY).json()
    assert result["ok"] is False
    assert result["retry_policy"]["execution_limits"]["terminal"] is True
    assert len(state["calls"]) == 1
    assert state["eval_signed"] == []


def test_strict_integration_approval_rejection_does_not_create_checkpoint(strict_app_boundary, monkeypatch):
    api, state = strict_app_boundary
    monkeypatch.setenv("A11OY_APPROVAL_INTERRUPT", "1")
    interrupt = Mock(side_effect=AssertionError("checkpoint must not be created"))
    monkeypatch.setattr(strict_loop, "_approval_interrupt", interrupt)
    body = copy.deepcopy(STRICT_BODY)
    body["task"] = "Please delete a file."
    response = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "STRICT_APPROVAL_SCOPE_UNSUPPORTED"
    interrupt.assert_not_called()
    assert state["calls"] == [] and state["signed"] == [] and state["forums"] == []


def test_strict_integration_invalid_internal_budget_is_blocked():
    result = strict_loop.run_loop("What is two plus two?", lambda _: {}, execution_budget=object())
    assert result["status_code"] == 422
    assert result["status"] == "BLOCKED"
    assert result["execution_limits"] is None
    transport = strict_engine._hf_chat([], want_model=STRICT_MODEL, execution_budget=object())
    assert transport["ok"] is False and transport["attempts"] == 0
    assert transport["error"] == "INVALID_EXECUTION_BUDGET"
    turn = strict_engine.governed_turn("chat", "What is two plus two?", lambda _: {},
                                     "a11oy", execution_budget=object())
    assert turn["decision"] == "DENY" and turn["emitted"] is False


def test_strict_integration_duplicate_body_field_is_rejected(strict_app_boundary):
    api, state = strict_app_boundary
    raw = json.dumps(STRICT_BODY)
    raw = raw[:-1] + ', "sandbox": false}'
    response = api.post(STRICT_LOOP_PATH,
                        headers={**STRICT_HEADERS, "Content-Type": "application/json"}, content=raw)
    assert response.status_code == 422
    assert state["calls"] == [] and state["signed"] == [] and state["forums"] == []


def test_strict_integration_late_composite_sign_preserves_receipt_but_withholds_forum(strict_app_boundary, monkeypatch):
    import szl_router_client

    api, state = strict_app_boundary
    clock = [0.0]
    monkeypatch.setattr(szl_router_client, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    def late_composite(payload):
        if payload.get("schema") == strict_loop.SCHEMA:
            clock[0] = 6.0

    state["sign_hook"] = late_composite
    result = api.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=STRICT_BODY).json()
    assert result["ok"] is False
    assert result["completion"]["complete"] is False
    assert result["retry_policy"]["execution_limits"]["error"] == "EXECUTION_DEADLINE_EXCEEDED"
    assert result["composite_receipt"]["body"]["completion"]["complete"] is True
    assert state["signed"][-1] == result["composite_receipt"]["body"]
    assert result["forum_ingest"]["ingested"] is False
    assert len(state["forums"]) == 1  # Only the earlier native evaluation receipt.


def test_strict_integration_cancelled_request_does_not_dispatch_next_case(strict_app_boundary, monkeypatch):
    import asyncio
    import threading
    api, state = strict_app_boundary
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    original_run = strict_loop.run_loop
    def observed_run(*args, **kwargs):
        try:
            result = original_run(*args, **kwargs)
            state["worker_result"] = result
            return result
        finally:
            finished.set()
    monkeypatch.setattr(strict_loop, "run_loop", observed_run)
    def provider(request):
        state["calls"].append(request)
        entered.set()
        assert release.wait(3)
        return httpx.Response(200, headers={"content-type": "application/json"}, json={
            "model": STRICT_MODEL, "choices": [{"message": {"role": "assistant", "content": "4"},
            "finish_reason": "stop"}], "usage": {"completion_tokens": 1}})
    monkeypatch.setattr(httpx, "Client", lambda **kw: STRICT_ORIGINAL_CLIENT(
        **{**kw, "transport": httpx.MockTransport(provider)}))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://testserver") as ac:
            request = asyncio.create_task(ac.post(STRICT_LOOP_PATH, headers=STRICT_HEADERS, json=STRICT_BODY))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                request.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await request
            finally:
                release.set()
            assert await asyncio.to_thread(finished.wait, 2)
    asyncio.run(scenario())
    assert len(state["calls"]) == 1
    assert state["worker_result"]["completion"]["complete"] is False
    assert state["worker_result"]["composite_receipt"]["dsse"]["signed"] is False
    assert state["signed"] == []
    assert state["eval_signed"] == []
    assert state["forums"] == []
