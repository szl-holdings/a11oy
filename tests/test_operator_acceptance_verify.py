#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic captured-response fixtures only; no provider request or production proof."""
import ast
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

PATH = Path(__file__).resolve().parents[1] / "tools" / "operator_acceptance_verify.py"
SPEC = importlib.util.spec_from_file_location("operator_acceptance_verify", PATH)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
NOW = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
SOURCE = "a" * 40
NONCE = "b" * 32


@pytest.fixture
def bundle():
    cases = []
    for plan in v.planned_cases(NONCE):
        cases.append({**plan, "status_code": None, "response": None,
                      "readback_before": None, "readback_after": None,
                      "state": "NOT_ATTEMPTED", "reason": "fixture_not_executed"})
    policy, ask, compliance = cases[:3]
    policy.update(state="OBSERVED", status_code=200,
                  response={"decision": "allow", "actionId": NONCE + ":policy-decide",
                            "receipt_hash": "c" * 16, "lambda_value": 0.97,
                            "signals": [], "gates_fired": []},
                  readback_before={"total_buffered": 0, "verdicts": []},
                  readback_after={"total_buffered": 1, "verdicts": [
                      {"request_id": NONCE + ":policy-decide", "decision": "allow",
                       "receipt_hash": "c" * 16, "agent": "operator-acceptance",
                       "lambda_value": 0.97, "signals": []}]})
    ask.update(state="OBSERVED", status_code=200,
               response={"topic": "formulas", "question": ask["request"]["question"],
                         "answer": ", ".join(v.LOCKED), "grounded": True,
                         "citations": [{"endpoint": v.FORMULA_CITATION_ENDPOINT,
                                        "data": {"count": 8, "proved": v.LOCKED}}]})
    receipt = {"schema": "szl.a11oy.operator/v1", "kind": "ask", "organ": "a11oy",
               "ts_utc": "2026-10-15T13:59:15+00:00", "doctrine": "v11",
               "lambda_status": "Conjecture 1 (NOT a theorem)",
               "body": {"question": ask["request"]["question"], "topic": "formulas", "grounded": True}}
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True,
                                              separators=(",", ":")).encode()).hexdigest()
    ask["response"]["receipt"] = {"receipt": receipt, "signed": False,
                                  "signing_available": False, "dsse": {"signed": False}}
    compliance.update(state="OBSERVED", status_code=200,
                      response={"status": "REAL", "framework": "NIST", "covered": 8, "total": 8})
    build = {"service": "a11oy", "status": "OBSERVED", "build": {"state": "OBSERVED",
             "revision": SOURCE, "revision_source": "env:SZL_GIT_SHA",
             "field_evidence": {"revision": "OBSERVED"}}, "receipt_minted": False}
    return {"schema": v.SCHEMA, "evidence_class": "REPORTED", "origin": v.ORIGIN,
            "expected_source_revision": SOURCE, "run_nonce": NONCE,
            "started_at": "2026-10-15T13:59:00Z", "finished_at": "2026-10-15T13:59:30Z",
            "build_before": copy.deepcopy(build), "build_after": copy.deepcopy(build), "cases": cases}


def verify(bundle, **overrides):
    return v.verify_bundle(bundle, **{"expected_source_revision": SOURCE,
                                    "expected_run_nonce": NONCE, "now": NOW, **overrides})


def test_three_scoped_observations_never_qualify_five_contracts(bundle):
    result = verify(bundle)
    assert result["status"] == "REPORTED"
    assert result["reported_semantic_contracts"] == 3
    assert result["all_five_semantics_verified"] is False
    assert result["publication_eligible"] is False
    assert result["execution_authorized"] is False
    assert result["passive_probe_modified"] is False
    assert all(row["native_receipt_verified"] is False for row in result["cases"])


@pytest.mark.parametrize("server_time", ["2026-10-15T14:00:04Z", "2026-10-15T13:58:55+00:00"])
def test_remote_clock_is_not_assumed_synchronized(bundle, server_time):
    record = bundle["cases"][1]["response"]["receipt"]["receipt"]
    record["ts_utc"] = server_time
    unsigned = {key: value for key, value in record.items() if key != "receipt_sha256"}
    record["receipt_sha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True,
                                                       separators=(",", ":")).encode()).hexdigest()
    result = verify(bundle)
    assert result["reported_semantic_contracts"] == 3
    assert result["freshness_basis"] == "LOCAL_CAPTURE_CLOCK_REPORTED"
    assert result["cases"][1]["receipt_time_comparison"] == "UNAVAILABLE"
    assert result["publication_eligible"] is False
    assert result["cases"][1]["execution_qualified"] is False


@pytest.mark.parametrize("question", ["Which eight formula identifiers are locked under Doctrine v11?",
    "Which eight formula identifiers are locked under Doctrine v11? Acceptance run " + "c" * 32 + "."])
def test_ask_response_from_a_different_run_is_rejected(bundle, question):
    body = bundle["cases"][1]["response"]
    body["question"] = question
    body["receipt"]["receipt"]["body"]["question"] = question
    with pytest.raises(v.VerificationError, match="OBSERVATION_AFTER_STOP"):
        verify(bundle)


@pytest.mark.parametrize("server_time", ["2026-10-15", "2026-10-15 13:59:15Z",
    "2026-10-15T13:59:15", "2026-10-15T13:59:15+01:00", "2026-10-99T13:59:15Z"])
def test_server_timestamp_requires_strict_utc_syntax(bundle, server_time):
    body = bundle["cases"][1]["response"]
    body["receipt"]["receipt"]["ts_utc"] = server_time
    result = v.verify_case(bundle["cases"][1], run_nonce=NONCE)
    assert result["semantic_checks_passed"] is False
    assert result["reason"] == "ASK_RECEIPT_TIME_INVALID"


def test_v1_capture_cannot_be_reinterpreted_under_v2_rules(bundle):
    bundle["schema"] = "szl.operator-http-observation/v1"
    with pytest.raises(v.VerificationError, match="SCHEMA_OR_CLASS_MISMATCH"):
        verify(bundle)


@pytest.mark.parametrize("field,value", [("origin", "https://attacker.invalid"),
    ("run_nonce", "c" * 32), ("expected_source_revision", "c" * 40),
    ("evidence_class", "MEASURED"), ("schema", "other"),
    ("started_at", "2026-10-15T13:40:00Z"), ("finished_at", "2026-10-15T14:01:00Z"),
    ("finished_at", "2026-10-15T13:58:00Z"), ("started_at", "2026-10-15 13:59:00Z")])
def test_wrong_source_origin_nonce_class_or_time_rejects(bundle, field, value):
    bundle[field] = value
    with pytest.raises(v.VerificationError):
        verify(bundle)


@pytest.mark.parametrize("where", ["build_before", "build_after"])
def test_a_redeploy_between_reads_invalidates_capture(bundle, where):
    bundle[where]["build"]["revision"] = "d" * 40
    with pytest.raises(v.VerificationError, match="BUILD_IDENTITY_MISMATCH"):
        verify(bundle)


@pytest.mark.parametrize("field,value", [("state", "UNKNOWN"),
    ("revision_source", "env:GITHUB_SHA"), ("field_evidence", {"revision": "UNKNOWN"})])
def test_build_identity_requires_observed_canonical_binding(bundle, field, value):
    bundle["build_after"]["build"][field] = value
    with pytest.raises(v.VerificationError, match="BUILD_IDENTITY_MISMATCH"):
        verify(bundle)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "self_authorized", "wrong_route", "bool_status"])
def test_incomplete_or_self_asserted_evidence_rejects(bundle, mutation):
    if mutation == "missing": bundle["cases"].pop()
    elif mutation == "duplicate": bundle["cases"][-1] = copy.deepcopy(bundle["cases"][0])
    elif mutation == "extra": bundle["cases"].append(copy.deepcopy(bundle["cases"][0]))
    elif mutation == "self_authorized": bundle["execution_authorized"] = True
    elif mutation == "wrong_route": bundle["cases"][0]["path"] = "/api/other"
    elif mutation == "bool_status": bundle["cases"][0]["status_code"] = True
    with pytest.raises(v.VerificationError):
        verify(bundle)


@pytest.mark.parametrize("mutation", ["wrong_request", "wrong_receipt", "old_request", "count_only", "overclaim_lambda", "gates", "incomplete_feed", "feed_lambda", "feed_signals"])
def test_policy_requires_exact_new_identity_and_effect_readback(bundle, mutation):
    case = bundle["cases"][0]
    if mutation == "wrong_request": case["request"]["action"]["value"] = "other"
    elif mutation == "wrong_receipt": case["readback_after"]["verdicts"][0]["receipt_hash"] = "d" * 16
    elif mutation == "old_request": case["readback_before"] = copy.deepcopy(case["readback_after"])
    elif mutation == "count_only": case["readback_after"]["verdicts"][0]["request_id"] = "someone-else"
    elif mutation == "overclaim_lambda": case["response"]["lambda_value"] = 1.0
    elif mutation == "gates": case["response"]["gates_fired"] = ["gate"]
    elif mutation == "incomplete_feed": case["readback_before"]["total_buffered"] = 1
    elif mutation == "feed_lambda": case["readback_after"]["verdicts"][0]["lambda_value"] = 1.0
    elif mutation == "feed_signals": case["readback_after"]["verdicts"][0]["signals"] = ["gate"]
    assert v.verify_case(case, run_nonce=NONCE)["status"] == "BLOCKED"


@pytest.mark.parametrize("mutation", ["wrong_citation", "inflated_count", "extra_formula", "false_answer", "ungrounded"])
def test_formula_answer_requires_canonical_eight_not_a_label(bundle, mutation):
    body = bundle["cases"][1]["response"]
    if mutation == "wrong_citation": body["citations"][0]["endpoint"] = "untrusted"
    elif mutation == "inflated_count": body["citations"][0]["data"]["count"] = 9
    elif mutation == "extra_formula": body["citations"][0]["data"]["proved"] = v.LOCKED + ["F99"]
    elif mutation == "false_answer": body["answer"] += ", F99"
    elif mutation == "ungrounded": body["grounded"] = False
    assert v.verify_case(bundle["cases"][1], run_nonce=NONCE)["status"] == "BLOCKED"


def test_compliance_is_only_bounded_declared_lookup(bundle):
    bundle["cases"][2]["response"]["covered"] = True
    assert verify(bundle)["cases"][2]["status"] == "BLOCKED"


@pytest.mark.parametrize("case_index", [3, 4])
@pytest.mark.parametrize("label", ["MODELED", "LIVE"])
def test_native_signed_flags_or_live_labels_do_not_admit_execution(bundle, case_index, label):
    case = bundle["cases"][case_index]
    case.update(state="OBSERVED", status_code=200, request={"model_id": "fixture"},
                response={"honesty_label": label, "signed": True, "execution_complete": True,
                          "receipt": {"signed": True}}, readback_after={"total_events": 10})
    with pytest.raises(v.VerificationError, match="MODEL_EXECUTION_OUTSIDE_CAPTURE_SCOPE"):
        v.verify_case(case, run_nonce=NONCE)
    with pytest.raises(v.VerificationError):
        verify(bundle)


def test_policy_baseline_rejects_hidden_or_repeated_nonce(bundle):
    v.validate_policy_baseline(bundle["cases"][0]["readback_before"], NONCE)
    with pytest.raises(v.VerificationError, match="POLICY_REQUEST_ALREADY_PRESENT"):
        v.validate_policy_baseline(bundle["cases"][0]["readback_after"], NONCE)
    with pytest.raises(v.VerificationError, match="POLICY_READBACK_UNAVAILABLE"):
        v.validate_policy_baseline({"total_buffered": 2, "verdicts": []}, NONCE)


@pytest.mark.parametrize("mutation", ["payload", "hash", "signed"])
def test_ask_unsigned_digest_is_recomputed_not_trusted(bundle, mutation):
    case = bundle["cases"][1]
    receipt = case["response"]["receipt"]
    if mutation == "payload": receipt["receipt"]["body"]["question"] = "other"
    elif mutation == "hash": receipt["receipt"]["receipt_sha256"] = "e" * 64
    elif mutation == "signed": receipt["signed"] = True
    assert v.verify_case(case, run_nonce=NONCE)["status"] == "BLOCKED"


def test_case_order_and_continue_after_ambiguous_effect_rejected(bundle):
    swapped = copy.deepcopy(bundle)
    swapped["cases"][0], swapped["cases"][1] = swapped["cases"][1], swapped["cases"][0]
    with pytest.raises(v.VerificationError, match="CASE_ORDER_MISMATCH"):
        verify(swapped)
    bundle["cases"][0]["state"] = "UNKNOWN"
    with pytest.raises(v.VerificationError, match="OBSERVATION_AFTER_STOP"):
        verify(bundle)


def test_not_attempted_prefix_cannot_hide_a_later_post(bundle):
    bundle["cases"][0].update(state="NOT_ATTEMPTED", status_code=None, response=None,
                              readback_after=None)
    with pytest.raises(v.VerificationError, match="OBSERVATION_AFTER_STOP"):
        verify(bundle)


def test_unrelated_citation_stays_allowed_beside_one_live_formula_source(bundle):
    body = bundle["cases"][1]["response"]
    body["citations"].append({"endpoint": "/api/a11oy/v1/lambda", "data": {"lambda": "Conjecture 1"}})
    result = v.verify_case(bundle["cases"][1], run_nonce=NONCE)
    assert result["status"] == "REPORTED"
    assert result["semantic_checks_passed"] is True
    assert result["execution_qualified"] is False
    assert result["native_receipt_verified"] is False


@pytest.mark.parametrize("mutation", ["retired", "absent", "duplicate"])
def test_retired_absent_or_duplicate_formula_citations_are_rejected(bundle, mutation):
    body = bundle["cases"][1]["response"]
    if mutation == "retired":
        body["citations"][0]["endpoint"] = "szl_brain.CANONICAL"
    elif mutation == "absent":
        body["citations"] = [{"endpoint": "/api/other", "data": {"count": 8, "proved": v.LOCKED}}]
    elif mutation == "duplicate":
        body["citations"].append(copy.deepcopy(body["citations"][0]))
    result = v.verify_case(bundle["cases"][1], run_nonce=NONCE)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "FORMULA_CITATION_MISMATCH"
    assert result["execution_qualified"] is False


def test_serve_formula_citation_is_bound_to_the_live_literal_without_import():
    tree = ast.parse((PATH.parents[1] / "serve.py").read_text(encoding="utf-8"))
    proved_lists = []
    endpoints = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_SC_PROVED_FORMULAS"
            for target in node.targets
        ):
            proved_lists.append(ast.literal_eval(node.value))
        if isinstance(node, ast.Constant) and node.value == v.FORMULA_CITATION_ENDPOINT:
            endpoints.append(node.value)
    assert proved_lists == [list(v.LOCKED)]
    assert endpoints == [v.FORMULA_CITATION_ENDPOINT]


def test_changed_local_artifact_bytes_rejected_by_independent_digest(bundle):
    raw = v.canonical(bundle)
    digest = hashlib.sha256(raw).hexdigest()
    result = v.verify_bytes(raw, expected_sha256=digest, expected_source_revision=SOURCE,
                            expected_run_nonce=NONCE, now=NOW)
    assert result["artifact_digest_verified"] is True
    with pytest.raises(v.VerificationError, match="ARTIFACT_HASH_MISMATCH"):
        v.verify_bytes(raw + b" ", expected_sha256=digest, expected_source_revision=SOURCE,
                       expected_run_nonce=NONCE, now=NOW)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'])
def test_ambiguous_or_nonfinite_json_rejected(raw):
    with pytest.raises(v.VerificationError): v.strict_json(raw)


def test_cli_help_needs_no_runtime_environment():
    result = subprocess.run([sys.executable, "-I", "-B", str(PATH), "--help"],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert "--expected-sha256" in result.stdout


def test_cli_error_does_not_echo_private_paths(tmp_path):
    secret_path = tmp_path / "private-operator-input"
    result = subprocess.run([sys.executable, "-I", "-B", str(PATH), str(secret_path),
                             "--expected-source", SOURCE, "--expected-nonce", NONCE,
                             "--expected-sha256", "f" * 64], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert "private-operator-input" not in result.stdout + result.stderr
    assert "ARTIFACT_UNAVAILABLE" in result.stdout


def test_cli_partial_capture_returns_two_not_release_success(bundle, tmp_path):
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    bundle.update(started_at=stamp, finished_at=stamp)
    for case in bundle["cases"]:
        case.update(state="NOT_ATTEMPTED", status_code=None, response=None,
                    readback_before=None, readback_after=None)
    raw = v.canonical(bundle)
    path = tmp_path / "synthetic-capture.json"
    path.write_bytes(raw)
    result = subprocess.run([sys.executable, "-I", "-B", str(PATH), str(path),
                             "--expected-source", SOURCE, "--expected-nonce", NONCE,
                             "--expected-sha256", hashlib.sha256(raw).hexdigest()],
                             capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["reported_semantic_contracts"] == 0
    assert report["publication_eligible"] is False
