#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Staged fixed-route observations and public-only offline native validation.

No endpoint is installed by importing this module. This is not a receipt store.
Native hooks must read records already persisted by the owner of each receipt.
"""
import asyncio
import copy
import inspect
import json
import math
import os
import re
from dataclasses import dataclass

from tools import execution_acceptance as a

NATIVE_TYPE = "application/vnd.szl.khipu+json"
HOST_TYPE = "application/vnd.szl.receipt+json"
HOOK_SCHEMA = "szl.native-execution-readbacks/v1"
READBACK_SCHEMA = "szl.native-execution-readback/v1"
LOCKED = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
QUESTION = "Which eight formula identifiers are locked under Doctrine v11?"
FORMULA_SOURCE = "serve._SC_PROVED_FORMULAS"
FEED = "/api/a11oy/v1/policy/decisions/feed"
ENDPOINTS = {"policy-decide": "_sc_cap_decide", "policy-compliance": "_sc_cap_compliance",
             "operator-ask": "_sc_cap_ask", "eval-run": "eval_run", "agentloop-run": "_run"}


class AdapterBlocked(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise AdapterBlocked(code)


def h(value):
    return a.digest(a.canonical(value))


def loop_hash(value):
    # The existing agent composite uses ASCII-escaped JSON, unlike the eval arena.
    return a.digest(json.dumps(value, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode())


def object_(value, code):
    require(type(value) is dict, code)
    return value


def limits(value):
    require(type(value) is dict and set(value) == {
        "max_model_requests", "max_output_tokens", "max_elapsed_seconds"}, "LIMITS_REQUIRED")
    for name, cap in (("max_model_requests", 32), ("max_output_tokens", 32768),
                      ("max_elapsed_seconds", 300)):
        require(type(value[name]) is int and 1 <= value[name] <= cap, "LIMITS_INVALID")


def validate_fixed_plan(plan):
    """Pure effect-scope validation, supplementary to independent plan signatures."""
    object_(plan, "PLAN_REQUIRED")
    nonce = plan.get("run_nonce")
    require(type(nonce) is str and a.HEX64.fullmatch(nonce), "RUN_NONCE_REQUIRED")
    cases = plan.get("cases")
    require(type(cases) is list and len(cases) == 5, "COMPLETE_PLAN_REQUIRED")
    seen = {}
    for case in cases:
        object_(case, "CASE_REQUIRED")
        case_id = case.get("id")
        require(type(case_id) is str and case_id in a.CONTRACTS and case_id not in seen,
                "FIXED_CASE_SET_REQUIRED")
        require(case.get("method") == "POST" and case.get("path") == a.CONTRACTS[case_id]
                and type(case.get("expected_status")) is int and case["expected_status"] == 200,
                "FIXED_ROUTE_REQUIRED")
        body = object_(case.get("body"), "BODY_REQUIRED")
        require(len(a.canonical(body)) <= a.MAX_BODY, "BODY_TOO_LARGE")
        if case_id == "policy-decide":
            require(body == {"agent": "execution-acceptance", "request_id": nonce + ":policy-decide",
                             "action": {"operation": "inspect-synthetic-record", "record_id": "acceptance-only"}},
                    "SYNTHETIC_POLICY_SCOPE_REQUIRED")
        elif case_id == "policy-compliance":
            require(set(body) == {"framework"} and body["framework"] in ("NIST", "STIG", "ISO27001"),
                    "EXPLICIT_COMPLIANCE_FRAMEWORK_REQUIRED")
        elif case_id == "operator-ask":
            require(body == {"question": QUESTION}, "DECLARED_FORMULA_QUESTION_REQUIRED")
        else:
            limits(body.get("execution_limits"))
            require(type(body.get("model_id")) is str and
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,191}", body["model_id"]),
                    "EXPLICIT_MODEL_REQUIRED")
            if case_id == "eval-run":
                require(set(body) == {"model_id", "suite", "execution_mode", "execution_limits"}
                        and body["execution_mode"] == "live" and type(body["suite"]) is str
                        and bool(body["suite"]), "STRICT_EVAL_SCOPE_REQUIRED")
            else:
                require(set(body) == {"model_id", "task", "eval_suite", "mode", "sandbox", "max_retries",
                                      "consult_brain", "allocate_energy", "execution_limits"}
                        and body["mode"] == "chat" and body["sandbox"] is False
                        and type(body["max_retries"]) is int and body["max_retries"] == 0
                        and body["consult_brain"] is False and body["allocate_energy"] is False
                        and type(body["task"]) is str and 0 < len(body["task"]) <= 256
                        and body["task"] == body["task"].strip()
                        and type(body["eval_suite"]) is str and bool(body["eval_suite"]),
                        "STRICT_AGENT_SCOPE_REQUIRED")
        seen[case_id] = body
    require(seen["eval-run"]["model_id"] == seen["agentloop-run"]["model_id"]
            and seen["eval-run"]["suite"] == seen["agentloop-run"]["eval_suite"],
            "SAME_EXPLICIT_MODEL_AND_SUITE_REQUIRED")


def budget(value, expected, requests=None):
    object_(value, "BUDGET_EVIDENCE_REQUIRED")
    limits(expected)
    require(value.get("limits") == expected and value.get("terminal") is False
            and value.get("usage_complete") is True and value.get("request_pending") is False
            and value.get("ambiguous") is False and value.get("error") is None
            and value.get("enforcement_scope") == "CLIENT_REQUESTS_ONLY", "BUDGET_NOT_COMPLETE")
    for field in ("model_requests", "output_tokens_reserved", "output_tokens_reported", "elapsed_ms"):
        require(type(value.get(field)) is int and value[field] >= 0, "INVALID_BUDGET_COUNTER")
    require(1 <= value["model_requests"] <= expected["max_model_requests"]
            and 0 <= value["output_tokens_reported"] <= value["output_tokens_reserved"] <= expected["max_output_tokens"]
            and value["elapsed_ms"] <= expected["max_elapsed_seconds"] * 1000, "BUDGET_EXCEEDED")
    if requests is not None:
        require(value["model_requests"] == requests, "REQUEST_COUNT_MISMATCH")


def governance(value):
    object_(value, "GOVERNANCE_REQUIRED")
    route = object_(value.get("route"), "GOVERNANCE_ROUTE_REQUIRED")
    sensitivity = object_(route.get("sensitivity"), "GOVERNANCE_SENSITIVITY_REQUIRED")
    require(value.get("decision") == "allow" and route.get("airgap_required") is False
            and sensitivity.get("class") in ("PUBLIC", "INTERNAL"), "EGRESS_NOT_ADMITTED")


def native(envelope, key, key_id, *, payload_type=HOST_TYPE):
    object_(envelope, "NATIVE_SIGNATURE_REQUIRED")
    require(envelope.get("signed") is True, "NATIVE_SIGNATURE_REQUIRED")
    core = {name: envelope.get(name) for name in ("payloadType", "payload", "signatures")}
    payload = a.verify(core, payload_type, key, key_id)
    raw = a.decode(core["payload"], a.MAX_BYTES)
    kind = payload_type.encode()
    pae = b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(raw)).encode() + b" " + raw
    require(envelope.get("_pae_sha256") == a.digest(pae), "NATIVE_PAE_MISMATCH")
    if payload_type == HOST_TYPE:
        identity = payload.get("_signing_identity")
        require(type(identity) is dict and set(identity) == {"keyid", "verify_key_url", "key_scope",
                "key_lifetime", "key_source", "key_fingerprint_sha256"}, "HOST_SIGNING_IDENTITY_REQUIRED")
        require(identity["keyid"] == identity["key_fingerprint_sha256"] == key_id
                and identity["verify_key_url"] == "/api/a11oy/cosign.pub"
                and identity["key_scope"] == "DEPLOYMENT_PERSISTENT"
                and identity["key_lifetime"] == "UNTIL_SECRET_ROTATION"
                and type(identity["key_source"]) is str and identity["key_source"].startswith("persistent:"),
                "HOST_SIGNING_IDENTITY_MISMATCH")
    return payload, a.digest(raw)


def native_receipt(receipt, key, key_id):
    object_(receipt, "NATIVE_RECEIPT_REQUIRED")
    body = object_(receipt.get("body"), "NATIVE_BODY_REQUIRED")
    schema = body.get("schema")
    require(schema in ("szl.eval_arena.receipt/v1", "szl.agentloop.receipt/v1"), "NATIVE_RECEIPT_SCHEMA_MISMATCH")
    payload_type = NATIVE_TYPE if schema == "szl.eval_arena.receipt/v1" else HOST_TYPE
    payload, payload_hash = native(receipt.get("dsse"), key, key_id, payload_type=payload_type)
    declared = ({k: v for k, v in payload.items() if k != "_signing_identity"}
                if payload_type == HOST_TYPE else payload)
    require(declared == body, "NATIVE_BODY_MISMATCH")
    return payload, payload_hash


def verify_readback(value, case_id, receipt, payload_hash, key, key_id):
    require(type(value) is dict and set(value) == {"schema", "case_id", "payload_sha256", "receipt"},
            "EXACT_NATIVE_READBACK_REQUIRED")
    require(value["schema"] == READBACK_SCHEMA and value["case_id"] == case_id
            and value["payload_sha256"] == payload_hash, "NATIVE_READBACK_BINDING_MISMATCH")
    stored, stored_hash = native_receipt(value["receipt"], key, key_id)
    require(stored_hash == payload_hash and value["receipt"] == receipt,
            "NATIVE_READBACK_RECEIPT_MISMATCH")
    return stored


def validate_eval(result, body, key, key_id, *, nested=False):
    object_(result, "EVAL_RESULT_REQUIRED")
    require(result.get("status_code", 200 if not nested else None) == 200 and result.get("error") is None
            and result.get("model_id") == body["model_id"] and result.get("execution_mode") == "live"
            and result.get("honesty_label") == "LIVE" and result.get("execution_complete") is True
            and (nested or result.get("state") == "COMPLETED"),
            "EVAL_NOT_COMPLETED")
    suite = object_(result.get("suite"), "SUITE_EVIDENCE_REQUIRED")
    require(suite.get("id") == body["suite"], "EVAL_SUITE_MISMATCH")
    receipt = object_(result.get("receipt"), "EVAL_RECEIPT_REQUIRED")
    signed, payload_hash = native_receipt(receipt, key, key_id)
    require(signed.get("schema") == "szl.eval_arena.receipt/v1"
            and signed.get("model_id") == body["model_id"] and signed.get("suite_id") == body["suite"]
            and signed.get("suite_sha256") == suite.get("sha256") and signed.get("execution_mode") == "live"
            and signed.get("honesty_label") == "LIVE" and signed.get("harness_profile_id") is None,
            "EVAL_SIGNED_BINDING_MISMATCH")
    slug = signed.get("selected_model_slug")
    require(type(slug) is str and bool(slug) and
            (nested or result.get("selected_model_slug") == slug), "SELECTED_MODEL_MISMATCH")
    aggregate = object_(result.get("aggregate"), "EVAL_AGGREGATE_REQUIRED")
    rows = result.get("results")
    require(aggregate == signed.get("aggregate") and type(rows) is list and bool(rows), "EVAL_AGGREGATE_MISMATCH")
    n = len(rows)
    for name in ("n_cases", "n_evaluated", "n_passed", "n_unavailable"):
        require(type(aggregate.get(name)) is int, "EVAL_COUNTS_INVALID")
    require(aggregate["n_cases"] == n and aggregate["n_evaluated"] == n
            and aggregate["n_unavailable"] == 0 and 0 <= aggregate["n_passed"] <= n
            and aggregate.get("execution_complete") is True
            and aggregate.get("score_basis") == "MODEL_RESPONSES_ONLY"
            and aggregate.get("model_qualified") is False, "EVAL_COUNTS_INCOMPLETE")
    accuracy = aggregate.get("accuracy")
    require(type(accuracy) in (int, float) and math.isfinite(accuracy)
            and accuracy == round(aggregate["n_passed"] / n, 4), "EVAL_ACCURACY_MISMATCH")
    budget(result.get("execution_budget"), body["execution_limits"], n + int(nested))
    budget(signed.get("execution_budget"), body["execution_limits"], n + int(nested))
    final_budget, signed_budget = result["execution_budget"], signed["execution_budget"]
    require({k: v for k, v in final_budget.items() if k != "elapsed_ms"}
            == {k: v for k, v in signed_budget.items() if k != "elapsed_ms"}
            and final_budget["elapsed_ms"] >= signed_budget["elapsed_ms"], "FINAL_BUDGET_MISMATCH")
    digests, ids = [], set()
    for index, row in enumerate(rows):
        object_(row, "EVAL_CASE_REQUIRED")
        case_id = row.get("id")
        require(type(case_id) is str and case_id and case_id not in ids, "EVAL_CASE_ID_INVALID")
        ids.add(case_id)
        require(row.get("evaluated") is True and type(row.get("passed")) is bool
                and type(row.get("refused")) is bool and row.get("honesty_label") == "LIVE"
                and row.get("error") is None, "EVAL_CASE_INCOMPLETE")
        answer = row.get("answer")
        require(type(answer) is str and bool(answer.strip())
                and row.get("answer_sha256") == a.digest(answer.encode()), "ANSWER_HASH_MISMATCH")
        generation = object_(row.get("generation"), "GENERATION_REQUIRED")
        require(generation.get("state") == ("CLIENT_REFUSED" if row["refused"] else "CLIENT_COMPLETED")
                and generation.get("requested") == body["model_id"] and generation.get("model_slug") == slug
                and generation.get("signature_state") == "UNSIGNED"
                and generation.get("receipt_kind") == "CLIENT_OBSERVATION_ONLY"
                and type(generation.get("attempts")) is int and generation["attempts"] == 1
                and generation.get("error") is None
                and generation.get("refusal" if row["refused"] else "answer") == answer,
                "GENERATION_BINDING_MISMATCH")
        budget(generation.get("execution_budget"), body["execution_limits"], index + 1 + int(nested))
        governance(row.get("governance"))
        generation_hash = h(generation)
        if nested:
            # Strict client generation has no omitted extension fields. Refuse an
            # uncheckable source hash instead of trusting a caller's hash string.
            require(row.get("generation_source_sha256") == loop_hash(generation), "GENERATION_PROJECTION_MISMATCH")
        digests.append({"id": case_id, "passed": row["passed"], "answer_sha256": row["answer_sha256"],
                        "label": "LIVE", "evaluated": True, "refused": row["refused"],
                        "generation_sha256": generation_hash, "governance_sha256": h(row["governance"])})
    require(sum(row["passed"] for row in rows) == aggregate["n_passed"]
            and signed.get("per_case_digests") == digests, "EVAL_CASE_DIGEST_MISMATCH")
    return signed, payload_hash, slug


def validate_agent(result, body, key, key_id):
    object_(result, "AGENT_RESULT_REQUIRED")
    completion = object_(result.get("completion"), "AGENT_COMPLETION_REQUIRED")
    require(result.get("ok") is True and result.get("status_code") == 200
            and result.get("error") is None and completion.get("complete") is True
            and completion.get("state") == "OBSERVED_COMPLETE" and completion.get("reasons") == []
            and type(completion.get("n_steps")) is int and completion["n_steps"] == 1
            and type(completion.get("n_complete_steps")) is int and completion["n_complete_steps"] == 1
            and completion.get("requested_model_id") == body["model_id"]
            and completion.get("model_qualified") is False
            and completion.get("evidence_basis") == "UPSTREAM_REPORTED_UNVERIFIED"
            and completion.get("receipt_verification_asserted") is False
            and result.get("orchestration_complete") is True,
            "AGENT_NOT_COMPLETED")
    signed, payload_hash = native_receipt(result.get("composite_receipt"), key, key_id)
    require(signed.get("schema") == "szl.agentloop.receipt/v1" and signed.get("run_id") == result.get("run_id")
            and type(result.get("run_id")) is str and bool(result["run_id"])
            and signed.get("task") == result.get("task") == body["task"]
            and signed.get("mode") == result.get("mode") == "chat"
            and signed.get("model_id") == body["model_id"] and signed.get("eval_suite_default") == body["eval_suite"]
            and signed.get("completion") == completion and type(signed.get("max_retries")) is int
            and signed["max_retries"] == 0
            and signed.get("harness_profile_id") is None, "AGENT_SIGNED_BINDING_MISMATCH")
    for value in (signed, result):
        require(value.get("brain_consulted") is False and value.get("brain_context") is None
                and value.get("energy_allocated") is False and value.get("energy_allocation") is None,
                "AGENT_EFFECT_SCOPE_MISMATCH")
    policy = object_(result.get("retry_policy"), "RETRY_POLICY_REQUIRED")
    signed_policy = object_(signed.get("retry_policy"), "SIGNED_RETRY_POLICY_REQUIRED")
    require({k: v for k, v in policy.items() if k != "execution_limits"}
            == {k: v for k, v in signed_policy.items() if k != "execution_limits"}
            and type(policy.get("outer_max_retries")) is int and policy["outer_max_retries"] == 0
            and policy.get("engine_internal_retries_bounded") is True
            and policy.get("engine_model_fallback_disabled") is True, "RETRY_POLICY_MISMATCH")
    steps = result.get("steps")
    require(type(steps) is list and type(signed.get("n_steps")) is int
            and len(steps) == signed["n_steps"] == 1, "ONE_AGENT_STEP_REQUIRED")
    step = object_(steps[0], "AGENT_STEP_REQUIRED")
    attempts = step.get("attempts")
    require(type(attempts) is list and len(attempts) == 1 and type(step.get("retries")) is int
            and step["retries"] == 0
            and step.get("final") == attempts[0] and step.get("mode") == "chat"
            and step.get("sandbox") is False and step.get("state_changing") is False
            and step.get("suite_id") == body["eval_suite"], "AGENT_STEP_SCOPE_MISMATCH")
    attempt = object_(attempts[0], "AGENT_ATTEMPT_REQUIRED")
    approval = object_(attempt.get("approval"), "APPROVAL_EVIDENCE_REQUIRED")
    require(approval.get("required") is False and attempt.get("harness_profile") is None,
            "AGENT_APPROVAL_SCOPE_MISMATCH")
    engine = object_(attempt.get("engine"), "ENGINE_EVIDENCE_REQUIRED")
    require((engine.get("ok") is None or engine.get("ok") is True) and engine.get("emitted") is True
            and engine.get("output_present") is True and engine.get("error") is None
            and engine.get("decision") == "ALLOW" and engine.get("mode") == "chat"
            and engine.get("sandbox") is False and engine.get("executed") is False
            and engine.get("signed") is True, "ENGINE_NOT_COMPLETED")
    engine_body, _ = native(engine.get("signed_receipt"), key, key_id)
    ev = object_(attempt.get("eval"), "SELF_EVAL_REQUIRED")
    eval_request = {"model_id": body["model_id"], "suite": body["eval_suite"],
                    "execution_mode": "live", "execution_limits": body["execution_limits"]}
    eval_signed, eval_hash, slug = validate_eval(ev.get("evidence"), eval_request, key, key_id, nested=True)
    inference = object_(engine.get("inference"), "INFERENCE_REQUIRED")
    require(inference.get("mode") == "generative" and inference.get("model") == body["model_id"]
            and inference.get("upstream_model") == slug and type(inference.get("attempts")) is int
            and inference["attempts"] == 1
            and inference.get("rate_limited") is False and inference.get("error") is None,
            "ENGINE_MODEL_MISMATCH")
    require(engine_body.get("mode") == "chat" and engine_body.get("decision") == "ALLOW"
            and engine_body.get("emitted") is True and engine_body.get("executed") is False
            and engine_body.get("sandbox_execution_attempted") is None
            and engine_body.get("selected_model") == {"model_id": body["model_id"], "upstream_model": slug},
            "ENGINE_SIGNED_BINDING_MISMATCH")
    governance(engine_body.get("pre_inference_governance"))
    budget(engine_body.get("execution_limits"), body["execution_limits"], 1)
    budget(policy.get("execution_limits"), body["execution_limits"], len(ev["evidence"]["results"]) + 1)
    budget(signed_policy.get("execution_limits"), body["execution_limits"], len(ev["evidence"]["results"]) + 1)
    final_budget, signed_budget = policy["execution_limits"], signed_policy["execution_limits"]
    require({k: v for k, v in final_budget.items() if k != "elapsed_ms"}
            == {k: v for k, v in signed_budget.items() if k != "elapsed_ms"}
            and final_budget["elapsed_ms"] >= signed_budget["elapsed_ms"], "FINAL_BUDGET_MISMATCH")
    engine_pae = engine["signed_receipt"]["_pae_sha256"]
    eval_pae = ev["evidence"]["receipt"]["dsse"]["_pae_sha256"]
    require(engine.get("signed_pae_sha256") == engine_pae and ev.get("receipt_pae_sha256") == eval_pae
            and ev.get("receipt_signed") is True, "NATIVE_CHAIN_LINK_MISMATCH")
    attempt_hash = loop_hash(attempts)
    require(step.get("attempt_evidence_sha256") == attempt_hash, "ATTEMPT_HASH_MISMATCH")
    step_body = {k: step.get(k) for k in ("n", "title", "mode", "sandbox", "state_changing", "suite_id", "final")}
    step_body.update(attempts=1, attempt_evidence_sha256=attempt_hash, prev_digest="")
    step_hash = loop_hash(step_body)
    chain = signed.get("step_chain")
    require(step.get("step_digest") == step_hash and type(chain) is list and len(chain) == 1
            and chain[0].get("n") == step.get("n") and chain[0].get("digest") == step_hash
            and chain[0].get("decision") == "ALLOW" and chain[0].get("step_receipt_pae_sha256") == engine_pae
            and chain[0].get("eval_receipt_pae_sha256") == eval_pae
            and signed.get("run_chain_digest") == loop_hash([step_hash])
            and signed.get("chain_order") == ["steps(profile+act+eval)"], "COMPOSITE_CHAIN_MISMATCH")
    return signed, payload_hash, ev["evidence"]["receipt"], eval_hash


def validate_native_observation(case, status, response_bytes, readback_bytes,
                                runtime_public_key, runtime_key_id):
    """Offline fixed predicates; no network, signing or private-key discovery."""
    require(type(status) is int and status == case.get("expected_status") == 200, "HTTP_SUCCESS_REQUIRED")
    require(type(response_bytes) is bytes and len(response_bytes) <= a.MAX_BODY
            and type(readback_bytes) is bytes and len(readback_bytes) <= a.MAX_BODY, "BODY_TOO_LARGE")
    response = object_(a.strict_json(response_bytes), "JSON_RESPONSE_REQUIRED")
    rb = object_(a.strict_json(readback_bytes), "JSON_READBACK_REQUIRED")
    case_id, body = case["id"], case["body"]
    require(case.get("method") == "POST" and case.get("path") == a.CONTRACTS.get(case_id), "FIXED_ROUTE_REQUIRED")
    key = a.public_key(runtime_public_key, runtime_key_id)
    if case_id in ("policy-decide", "policy-compliance", "operator-ask"):
        require(rb.get("schema") == READBACK_SCHEMA and rb.get("case_id") == case_id
                and response.get("status") == "REAL", "DETERMINISTIC_READBACK_REQUIRED")
        record = object_(rb.get("record"), "NATIVE_RECORD_REQUIRED")
        if case_id == "policy-decide":
            require(rb.get("source") == FEED and record.get("request_id") == body.get("request_id")
                    and response.get("actionId") == body.get("request_id")
                    and record.get("agent") == body.get("agent")
                    and record.get("action_preview") == str(body.get("action"))[:120]
                    and type(record.get("id")) is str and bool(record["id"])
                    and response.get("decision") in ("allow", "deny")
                    and type(response.get("receipt_hash")) is str
                    and re.fullmatch(r"[0-9a-f]{16}", response["receipt_hash"]), "POLICY_REQUEST_BINDING_MISMATCH")
            for field in ("decision", "signals", "lambda_value", "receipt_hash"):
                require(field in response and record.get(field) == response[field], "POLICY_AUDIT_MISMATCH")
        elif case_id == "policy-compliance":
            require(rb.get("source") == "serve._SC_BUNDLE.compliance." + body["framework"]
                    and rb.get("evidence_scope") == "DECLARED_LOCAL_RECORD_ONLY"
                    and record.get("framework") == body["framework"]
                    and all(response.get(k) == v for k, v in record.items()),
                    "COMPLIANCE_RECORD_MISMATCH")
        else:
            require(rb.get("source") == FORMULA_SOURCE and rb.get("evidence_scope") == "DECLARED_LOCAL_TABLE_ONLY"
                    and rb.get("lean_verified") is False and record == {"proved": LOCKED, "count": 8, "doctrine": "v11"},
                    "FORMULA_DECLARATION_MISMATCH")
            require(response.get("question") == body.get("question") == QUESTION
                    and response.get("topic") == "formulas" and response.get("grounded") is True
                    and type(response.get("answer")) is str
                    and set(re.findall(r"\bF\d+\b", response["answer"])) == set(LOCKED), "FORMULA_ANSWER_MISMATCH")
            citations = response.get("citations")
            require(type(citations) is list and len(citations) == 1
                    and citations[0].get("endpoint") == FORMULA_SOURCE
                    and all(citations[0].get("data", {}).get(k) == v for k, v in record.items()),
                    "FORMULA_CITATION_SOURCE_MISMATCH")
            unsigned = object_(response.get("receipt"), "OPERATOR_RECEIPT_REQUIRED")
            require(unsigned.get("signed") is False and (unsigned.get("dsse") or {}).get("signed") is False,
                    "OPERATOR_PLACEHOLDER_NOT_SIGNATURE")
    elif case_id == "eval-run":
        _, payload_hash, _ = validate_eval(response, body, key, runtime_key_id)
        verify_readback(rb, case_id, response["receipt"], payload_hash, key, runtime_key_id)
    elif case_id == "agentloop-run":
        _, payload_hash, eval_receipt, eval_hash = validate_agent(response, body, key, runtime_key_id)
        require(set(rb) == {"record", "eval_record"}, "AGENT_NATIVE_READBACKS_REQUIRED")
        verify_readback(rb["record"], case_id, response["composite_receipt"], payload_hash, key, runtime_key_id)
        verify_readback(rb["eval_record"], "eval-run", eval_receipt, eval_hash, key, runtime_key_id)
    else:
        raise AdapterBlocked("FIXED_CASE_SET_REQUIRED")


@dataclass(frozen=True)
class CapturedObservation:
    response_status: int
    response_bytes: bytes
    readback_bytes: bytes


class FixedAdapters:
    def __init__(self, app, runtime_public_key, runtime_key_id):
        self.app, self.public_key, self.key_id = app, runtime_public_key, runtime_key_id
        self.key = a.public_key(runtime_public_key, runtime_key_id)
        self._cases, self._used, self._globals = {}, set(), {}
        self._hooks = None

    def _endpoint(self, method, path):
        from starlette.routing import Match
        scope = {"type": "http", "method": method, "path": path, "root_path": ""}
        for route in self.app.routes:
            match, child = route.matches(scope)
            if match == Match.FULL:
                endpoint = child.get("endpoint")
                require(callable(endpoint), "ORIGINAL_ROUTE_REQUIRED")
                return endpoint
        raise AdapterBlocked("ORIGINAL_ROUTE_UNAVAILABLE")

    def preflight(self, plan):
        require(not self._used, "ADAPTER_ALREADY_USED")
        self._cases = {}
        validate_fixed_plan(plan)
        hooks = getattr(self.app.state, "execution_native_readbacks", None)
        require(hooks is not None and getattr(hooks, "schema", None) == HOOK_SCHEMA
                and callable(getattr(hooks, "read_eval", None))
                and callable(getattr(hooks, "read_agentloop", None)), "NATIVE_EXACT_READBACK_HOOKS_UNAVAILABLE")
        case_map = {case["id"]: copy.deepcopy(case) for case in plan["cases"]}
        globals_ = {}
        for case_id, case in case_map.items():
            endpoint = self._endpoint("POST", case["path"])
            require(endpoint.__name__ == ENDPOINTS[case_id], "ORIGINAL_ROUTE_MISMATCH")
            if case_id in ("eval-run", "agentloop-run"):
                require(getattr(endpoint, "execution_native_readbacks_schema", None) == HOOK_SCHEMA,
                        "NATIVE_RECEIPT_WRITER_NOT_INSTALLED")
            globals_[case_id] = endpoint.__globals__
        require(self._endpoint("GET", FEED).__name__ == "_sc_cap_feed", "NATIVE_FEED_UNAVAILABLE")
        # The shared loader can create an ephemeral fallback when configuration
        # disappears. Inspect existing configuration before asking it for signing
        # availability; admission must never create a replacement identity.
        from a11oy_signing_key import _configured_request
        signing_request = _configured_request()
        configured_persistent = (type(signing_request[2]) is str
            and signing_request[2].startswith("persistent:") and not signing_request[3])
        del signing_request  # Never retain or serialize the configured private bytes.
        require(configured_persistent, "NATIVE_PERSISTENT_SIGNER_CONFIGURATION_REQUIRED")
        import szl_dsse
        require(szl_dsse.signing_available() is True, "NATIVE_EVAL_SIGNER_UNAVAILABLE")
        a.public_key(szl_dsse.active_public_key_pem().encode(), self.key_id)
        host_endpoint = self._endpoint("POST", case_map["agentloop-run"]["path"])
        closure = dict(zip(host_endpoint.__code__.co_freevars,
                           (cell.cell_contents for cell in (host_endpoint.__closure__ or ()))))
        host_signer = closure.get("sign_fn")
        require(callable(host_signer) and getattr(host_signer, "__name__", None) == "_a11oy_sign_receipt",
                "NATIVE_HOST_SIGNER_UNAVAILABLE")
        host_globals = host_signer.__globals__
        require(host_globals.get("_A11OY_PRIV") is not None
                and type(host_globals.get("_A11OY_KEY_SOURCE")) is str
                and host_globals["_A11OY_KEY_SOURCE"].startswith("persistent:")
                and host_globals.get("_A11OY_KEYID") == self.key_id
                and host_globals.get("_A11OY_PAYLOAD_TYPE") == HOST_TYPE, "NATIVE_HOST_SIGNER_UNAVAILABLE")
        a.public_key(host_globals.get("_A11OY_PUB_PEM", "").encode(), self.key_id)
        policy = globals_["policy-decide"]
        lock, ring = policy.get("_SC_AUDIT_LOCK"), policy.get("_SC_AUDIT")
        require(lock is not None and ring is not None, "NATIVE_POLICY_AUDIT_UNAVAILABLE")
        with lock:
            require(not any(row.get("request_id") == case_map["policy-decide"]["body"]["request_id"] for row in ring),
                    "POLICY_REQUEST_ID_ALREADY_OBSERVED")
        compliance = globals_["policy-compliance"].get("_SC_BUNDLE", {}).get("compliance", {})
        framework = case_map["policy-compliance"]["body"]["framework"]
        require(type(compliance.get(framework)) is dict and bool(compliance[framework]), "NATIVE_COMPLIANCE_UNAVAILABLE")
        self._compliance = copy.deepcopy(compliance[framework])
        operator = globals_["operator-ask"]
        require(operator.get("_SC_PROVED_FORMULAS") == LOCKED, "LOCKED_FORMULA_TABLE_MISMATCH")
        # The fixed formula branch is a pure local lookup. No health, model or
        # signing call belongs in this branch. Existing misattribution is denied.
        ask = operator.get("_sc_ask")
        require(callable(ask), "FORMULA_SOURCE_UNAVAILABLE")
        preview = ask(QUESTION)
        cites = preview.get("citations") if type(preview) is dict else None
        require(type(cites) is list and len(cites) == 1 and cites[0].get("endpoint") == FORMULA_SOURCE,
                "FORMULA_CITATION_SOURCE_MISMATCH")
        from szl_eval_arena import prepare_strict_eval
        from szl_router_client import ExecutionBudget, strict_governance_admission
        import szl_agent_loop_governed as loop
        eval_body = case_map["eval-run"]["body"]
        self._eval_plan = prepare_strict_eval(eval_body["suite"], eval_body["model_id"], ExecutionBudget(eval_body["execution_limits"]))
        agent_body = case_map["agentloop-run"]["body"]
        agent_budget = ExecutionBudget(agent_body["execution_limits"])
        agent_plan = prepare_strict_eval(agent_body["eval_suite"], agent_body["model_id"], agent_budget)
        agent_budget.preflight(agent_plan["n_cases"] + 1, agent_plan["n_cases"] + 1)
        # Same native pre-inference governance used by the strict engine.
        from a11oy_vertical_feeds import governed_turn as strict_gate
        require(loop._ENGINE_OK and loop._ARENA_OK and loop._APPROVAL_OK,
                "AGENT_COMPONENT_PREFLIGHT_UNAVAILABLE")
        if os.environ.get("A11OY_APPROVAL_INTERRUPT") == "1":
            state_changing = getattr(loop._loop, "_is_state_changing", None)
            require(callable(state_changing) and not state_changing(agent_body["task"], True),
                    "AGENT_APPROVAL_SCOPE_UNSUPPORTED")
        gate = strict_gate("agentloop", agent_body["task"], declared="PUBLIC",
                           action_kind="bounded-model-inference", emit_receipt=False)
        strict_governance_admission(gate)
        require(agent_plan["model_slug"] == self._eval_plan["model_slug"], "MODEL_CATALOG_CHANGED")
        self._agent_plan = agent_plan
        self._globals, self._hooks, self._cases = globals_, hooks, case_map

    async def _hook(self, method, payload_hash):
        callback = getattr(self._hooks, method)
        if inspect.iscoroutinefunction(callback):
            raw = await callback(payload_hash)
        else:
            raw = await asyncio.to_thread(callback, payload_hash)
        require(type(raw) is bytes and len(raw) <= a.MAX_BODY, "NATIVE_READBACK_BYTES_REQUIRED")
        return object_(a.strict_json(raw), "NATIVE_READBACK_OBJECT_REQUIRED")

    async def capture(self, case, credentials):
        case_id = case.get("id") if type(case) is dict else None
        require(case_id in self._cases and case == self._cases[case_id] and case_id not in self._used,
                "PREFLIGHTED_UNUSED_CASE_REQUIRED")
        case = copy.deepcopy(self._cases[case_id])
        require(type(credentials) is dict, "CREDENTIAL_HEADERS_REQUIRED")
        headers = {}
        for name, value in credentials.items():
            require(type(name) is str and name.lower() in ("authorization", "x-a11oy-tenant")
                    and name.lower() not in headers and type(value) is str
                    and value and "\n" not in value and "\r" not in value, "CREDENTIAL_HEADERS_INVALID")
            headers[name.lower()] = value
        require("authorization" in headers, "OPERATOR_AUTHORIZATION_REQUIRED")
        require(getattr(self.app.state, "execution_native_readbacks", None) is self._hooks,
                "NATIVE_READBACK_OWNER_CHANGED")
        self._used.add(case_id)  # No retry after ambiguous dispatch or readback.
        if case_id in ("eval-run", "agentloop-run"):
            from szl_eval_arena import prepare_strict_eval
            from szl_router_client import ExecutionBudget
            body = case["body"]
            admitted = self._eval_plan if case_id == "eval-run" else self._agent_plan
            current = await asyncio.to_thread(prepare_strict_eval,
                body["suite"] if case_id == "eval-run" else body["eval_suite"],
                body["model_id"], ExecutionBudget(body["execution_limits"]))
            require(current["model_slug"] == admitted["model_slug"]
                    and h(current["suite"]) == h(admitted["suite"]),
                    "EVAL_PREFLIGHT_DRIFT" if case_id == "eval-run" else "AGENT_PREFLIGHT_DRIFT")
        import httpx
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=a.ORIGIN,
                                     follow_redirects=False) as client:
            response = await client.post(case["path"], headers={**headers, "content-type": "application/json"},
                                         content=a.canonical(case["body"]))
            require(response.headers.get("content-type", "").split(";", 1)[0] == "application/json", "JSON_RESPONSE_REQUIRED")
            raw = response.content
            require(len(raw) <= a.MAX_BODY, "BODY_TOO_LARGE")
            result = object_(a.strict_json(raw), "JSON_RESPONSE_REQUIRED")
            require(response.status_code == 200, "ORIGINAL_ROUTE_NOT_SUCCESSFUL")
            body = case["body"]
            if case_id == "policy-decide":
                feed = await client.get(FEED, params={"limit": 200}, headers=headers)
                require(feed.status_code == 200 and len(feed.content) <= a.MAX_BODY, "NATIVE_FEED_UNAVAILABLE")
                rows = object_(a.strict_json(feed.content), "NATIVE_FEED_INVALID").get("verdicts")
                require(type(rows) is list, "NATIVE_FEED_INVALID")
                matches = [row for row in rows if type(row) is dict and row.get("request_id") == body["request_id"]]
                require(len(matches) == 1, "NATIVE_AUDIT_AMBIGUOUS")
                rb = {"schema": READBACK_SCHEMA, "case_id": case_id, "source": FEED, "record": matches[0]}
            elif case_id == "policy-compliance":
                current = self._globals[case_id]["_SC_BUNDLE"]["compliance"][body["framework"]]
                require(current == self._compliance, "COMPLIANCE_RECORD_CHANGED")
                rb = {"schema": READBACK_SCHEMA, "case_id": case_id,
                      "source": "serve._SC_BUNDLE.compliance." + body["framework"],
                      "record": copy.deepcopy(current), "evidence_scope": "DECLARED_LOCAL_RECORD_ONLY"}
            elif case_id == "operator-ask":
                require(self._globals[case_id]["_SC_PROVED_FORMULAS"] == LOCKED, "LOCKED_FORMULA_TABLE_CHANGED")
                rb = {"schema": READBACK_SCHEMA, "case_id": case_id, "source": FORMULA_SOURCE,
                      "record": {"proved": list(LOCKED), "count": 8, "doctrine": "v11"},
                      "evidence_scope": "DECLARED_LOCAL_TABLE_ONLY", "lean_verified": False}
            elif case_id == "eval-run":
                _, payload_hash, slug = validate_eval(result, body, self.key, self.key_id)
                require(slug == self._eval_plan["model_slug"] and
                        result["suite"]["sha256"] == h(self._eval_plan["suite"]["cases"]), "EVAL_PREFLIGHT_DRIFT")
                rb = await self._hook("read_eval", payload_hash)
            else:
                _, payload_hash, eval_receipt, eval_hash = validate_agent(result, body, self.key, self.key_id)
                require(eval_receipt["body"]["selected_model_slug"] == self._agent_plan["model_slug"]
                        and eval_receipt["body"]["suite_sha256"] == h(self._agent_plan["suite"]["cases"]),
                        "AGENT_PREFLIGHT_DRIFT")
                rb = {"record": await self._hook("read_agentloop", payload_hash),
                      "eval_record": await self._hook("read_eval", eval_hash)}
        readback = a.canonical(rb)
        validate_native_observation(case, response.status_code, raw, readback, self.public_key, self.key_id)
        return CapturedObservation(response.status_code, raw, readback)
