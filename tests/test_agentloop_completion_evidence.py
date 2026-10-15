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
