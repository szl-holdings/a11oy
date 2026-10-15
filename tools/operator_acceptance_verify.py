#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline checks of captured operator HTTP observations, not release authority.

Taxonomy: provenance / supply-chain tooling. No network, key discovery, signing,
runtime import or write. Native receipt admission and the separate DSSE observation
contract remain prerequisites for execution qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ORIGIN = "https://szlholdings-a11oy.hf.space"
SCHEMA = "szl.operator-http-observation/v2"
MAX_BYTES = 2 * 1024 * 1024
MAX_AGE = timedelta(minutes=15)
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
LOCKED = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
CONTRACTS = {
    "policy-decide": "/api/a11oy/v1/policy/decide",
    "operator-ask": "/api/a11oy/v1/operator/ask",
    "policy-compliance": "/api/a11oy/v1/policy/compliance",
    "eval-run": "/api/a11oy/v1/eval/run",
    "agentloop-run": "/api/a11oy/v1/agentloop/run",
}


class VerificationError(ValueError):
    """A stable rejection code; never include captured/private response text."""


def require(condition, code):
    if not condition:
        raise VerificationError(code)


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise VerificationError("INVALID_JSON_VALUE") from exc


def strict_json(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, "INPUT_TOO_LARGE")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def nonfinite(_):
        raise VerificationError("NONFINITE_JSON")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=nonfinite)
        canonical(result)
        return result
    except VerificationError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise VerificationError("INVALID_JSON") from exc


def _fields(value, names, code):
    require(type(value) is dict and set(value) == set(names.split()), code)


def _moment(value):
    require(type(value) is str and UTC.fullmatch(value) is not None, "UTC_TIME_REQUIRED")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise VerificationError("INVALID_TIME") from exc


def planned_cases(nonce):
    """The fixed bounded requests; model-execution cases are not admitted here."""
    require(type(nonce) is str and HEX32.fullmatch(nonce) is not None, "RUN_NONCE_REQUIRED")
    bodies = {
        "policy-decide": {"agent": "operator-acceptance", "action": {"value": "noop"}, "axes": [0.97],
                          "request_id": nonce + ":policy-decide"},
        "operator-ask": {"question": "Which eight formula identifiers are locked under Doctrine v11? "
                                     + "Acceptance run " + nonce + "."},
        "policy-compliance": {"framework": "NIST"},
    }
    return [{"id": name, "path": path, "request": bodies.get(name)}
            for name, path in CONTRACTS.items()]


def validate_build_identity(build, expected_source_revision):
    """Check a captured reported identity; this does not attest deployed bytes."""
    require(type(expected_source_revision) is str
            and SHA40.fullmatch(expected_source_revision) is not None, "EXACT_SOURCE_REQUIRED")
    require(type(build) is dict and build.get("service") == "a11oy" and build.get("status") == "OBSERVED"
            and type(build.get("build")) is dict
            and build["build"].get("state") == "OBSERVED"
            and build["build"].get("revision") == expected_source_revision
            and build["build"].get("revision_source") in ("env:SZL_GIT_SHA", "env:A11OY_GIT_SHA")
            and type(build["build"].get("field_evidence")) is dict
            and build["build"]["field_evidence"].get("revision") == "OBSERVED"
            and build.get("receipt_minted") is False, "BUILD_IDENTITY_MISMATCH")


def _feed(value):
    require(type(value) is dict and type(value.get("total_buffered")) is int
            and 0 <= value["total_buffered"] <= 200
            and type(value.get("verdicts")) is list
            and len(value["verdicts"]) == value["total_buffered"]
            and all(type(row) is dict for row in value["verdicts"]),
            "POLICY_READBACK_UNAVAILABLE")
    return value["verdicts"]


def validate_policy_baseline(feed, nonce):
    """Require a complete bounded baseline with no occurrence of this request ID."""
    planned_cases(nonce)
    rows = _feed(feed)
    require(not any(row.get("request_id") == nonce + ":policy-decide" for row in rows),
            "POLICY_REQUEST_ALREADY_PRESENT")


def _policy(case):
    body, request = case["response"], case["request"]
    receipt = body.get("receipt_hash")
    require(body.get("decision") == "allow" and body.get("actionId") == request["request_id"]
            and canonical(body.get("lambda_value")) == canonical(0.97)
            and body.get("signals") == [] and body.get("gates_fired") == []
            and type(receipt) is str and re.fullmatch(r"[0-9a-f]{16}", receipt) is not None,
            "POLICY_RESPONSE_MISMATCH")
    before = _feed(case["readback_before"])
    after = _feed(case["readback_after"])
    rid = request["request_id"]
    require(not any(row.get("request_id") == rid for row in before), "POLICY_REQUEST_ALREADY_PRESENT")
    matches = [row for row in after if row.get("request_id") == rid]
    require(len(matches) == 1 and matches[0].get("receipt_hash") == receipt
            and matches[0].get("decision") == body["decision"]
            and canonical(matches[0].get("lambda_value")) == canonical(body["lambda_value"])
            and matches[0].get("signals") == body["signals"]
            and matches[0].get("agent") == request["agent"], "POLICY_IDENTITY_READBACK_MISMATCH")
    n_before = case["readback_before"]["total_buffered"]
    n_after = case["readback_after"]["total_buffered"]
    require(n_after >= min(n_before + 1, 200), "POLICY_COUNT_REGRESSED")
    return "REPORTED_POLICY_DECISION_AND_MATCHING_FEED_ENTRY"


def _answer(case):
    body = case["response"]
    require(case["readback_before"] is None and case["readback_after"] is None,
            "UNSUPPORTED_READBACK")
    citations = body.get("citations")
    require(body.get("topic") == "formulas" and body.get("grounded") is True
            and body.get("question") == case["request"]["question"]
            and type(body.get("answer")) is str and bool(body["answer"].strip())
            and type(citations) is list and bool(citations), "FORMULA_RESPONSE_MISMATCH")
    matched = [c for c in citations if type(c) is dict and c.get("endpoint") == "szl_brain.CANONICAL"]
    require(len(matched) == 1 and type(matched[0].get("data")) is dict,
            "FORMULA_CITATION_MISMATCH")
    data = matched[0]["data"]
    require(type(data.get("count")) is int and data["count"] == 8
            and canonical(data.get("proved")) == canonical(LOCKED), "LOCKED_FORMULAS_MISMATCH")
    require(set(re.findall(r"\bF\d+\b", body["answer"])) == set(LOCKED), "FORMULA_ANSWER_MISMATCH")
    _ask_receipt(body)
    return "REPORTED_GROUNDED_FORMULA_RESPONSE_ONLY"


def _ask_receipt(body):
    wrapper = body.get("receipt")
    require(type(wrapper) is dict and wrapper.get("signed") is False
            and wrapper.get("signing_available") is False and type(wrapper.get("dsse")) is dict
            and wrapper["dsse"].get("signed") is False, "ASK_UNSIGNED_RECEIPT_REQUIRED")
    receipt = wrapper.get("receipt")
    _fields(receipt, "schema kind organ ts_utc doctrine lambda_status body receipt_sha256", "ASK_RECEIPT_INVALID")
    require(receipt["schema"] == "szl.a11oy.operator/v1" and receipt["kind"] == "ask"
            and receipt["organ"] == "a11oy" and receipt["doctrine"] == "v11"
            and receipt["lambda_status"] == "Conjecture 1 (NOT a theorem)"
            and canonical(receipt["body"]) == canonical({"question": body["question"],
                    "topic": "formulas", "grounded": True}), "ASK_RECEIPT_BINDING_MISMATCH")
    stamp = receipt["ts_utc"]
    require(type(stamp) is str and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", stamp),
        "ASK_RECEIPT_TIME_INVALID")
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        require(observed.utcoffset() == timedelta(0), "ASK_RECEIPT_TIME_INVALID")
    except ValueError as exc:
        raise VerificationError("ASK_RECEIPT_TIME_INVALID") from exc
    # serve.py:_sc_sha uses default ensure_ascii=True; this is an unkeyed digest.
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    digest = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode("utf-8")).hexdigest()
    require(receipt["receipt_sha256"] == digest, "ASK_RECEIPT_DIGEST_MISMATCH")
    return observed


def _compliance(case):
    body = case["response"]
    require(case["readback_before"] is None and case["readback_after"] is None,
            "UNSUPPORTED_READBACK")
    require(body.get("framework") == "NIST" and body.get("status") == "REAL"
            and type(body.get("covered")) is int and type(body.get("total")) is int
            and 0 <= body["covered"] <= body["total"] and body["total"] > 0,
            "COMPLIANCE_RESPONSE_MISMATCH")
    return "REPORTED_DECLARED_COMPLIANCE_RESPONSE_ONLY"


def _case_result(case, plan):
    row = {"id": case["id"], "path": case["path"], "status": "BLOCKED",
           "semantic_checks_passed": False, "execution_qualified": False,
           "native_receipt_verified": False, "reason": "NOT_ATTEMPTED"}
    if case["id"] in ("eval-run", "agentloop-run"):
        row["reason"] = "NATIVE_RECEIPT_TRUST_NOT_ADMITTED"
        return row
    if case["state"] != "OBSERVED":
        row["reason"] = "EFFECT_UNKNOWN" if case["state"] == "UNKNOWN" else "NOT_ATTEMPTED"
        return row
    try:
        require(canonical(case["request"]) == canonical(plan["request"]), "REQUEST_CONTRACT_MISMATCH")
        require(case["status_code"] == 200 and type(case["response"]) is dict,
                "RESPONSE_UNAVAILABLE")
        reason = {"policy-decide": _policy, "operator-ask": _answer,
                  "policy-compliance": _compliance}[case["id"]](case)
        row.update(status="REPORTED", semantic_checks_passed=True, reason=reason)
        if case["id"] == "operator-ask":
            row["unsigned_payload_digest_verified"] = True
    except VerificationError as exc:
        row["reason"] = str(exc)
    return row


def verify_case(case, *, run_nonce):
    """Check one capture before a runner continues; never authorizes its next call."""
    plans = {plan["id"]: plan for plan in planned_cases(run_nonce)}
    _fields(case, "id path request status_code response readback_before readback_after state reason", "INVALID_CASE")
    name = case["id"]
    require(type(name) is str and name in plans, "CASE_SET_MISMATCH")
    require(case["path"] == CONTRACTS[name], "ROUTE_MISMATCH")
    require(case["state"] in ("OBSERVED", "NOT_ATTEMPTED", "UNKNOWN"), "INVALID_EFFECT_STATE")
    require(type(case["reason"]) is str and 0 < len(case["reason"]) <= 256, "REASON_REQUIRED")
    require(case["status_code"] is None or (type(case["status_code"]) is int
            and 100 <= case["status_code"] <= 599), "INVALID_HTTP_STATUS")
    for key in ("request", "response", "readback_before", "readback_after"):
        require(case[key] is None or type(case[key]) is dict, "INVALID_OBSERVATION_OBJECT")
    if name in ("eval-run", "agentloop-run"):
        require(case["state"] == "NOT_ATTEMPTED" and all(case[key] is None for key in
                ("request", "status_code", "response", "readback_before", "readback_after")),
                "MODEL_EXECUTION_OUTSIDE_CAPTURE_SCOPE")
    if case["state"] == "NOT_ATTEMPTED":
        require(case["status_code"] is None and case["response"] is None
                and case["readback_after"] is None, "NOT_ATTEMPTED_CONTRADICTION")
    return _case_result(case, plans[name])


def verify_bundle(bundle, *, expected_source_revision, expected_run_nonce, now=None):
    """Verify captured facts. Caller expectations must not come from the bundle."""
    require(len(canonical(bundle)) <= MAX_BYTES, "INPUT_TOO_LARGE")
    _fields(bundle, "schema evidence_class expected_source_revision origin run_nonce started_at finished_at build_before build_after cases", "INVALID_BUNDLE")
    require(bundle["schema"] == SCHEMA and bundle["evidence_class"] == "REPORTED", "SCHEMA_OR_CLASS_MISMATCH")
    plans = planned_cases(expected_run_nonce)
    require(bundle["origin"] == ORIGIN and bundle["run_nonce"] == expected_run_nonce
            and bundle["expected_source_revision"] == expected_source_revision, "INDEPENDENT_BINDING_MISMATCH")
    validate_build_identity(bundle["build_before"], expected_source_revision)
    validate_build_identity(bundle["build_after"], expected_source_revision)
    start, end = _moment(bundle["started_at"]), _moment(bundle["finished_at"])
    now = datetime.now(timezone.utc) if now is None else now
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() == timedelta(0), "UTC_NOW_REQUIRED")
    require(start <= end <= now and now - start <= MAX_AGE, "STALE_OR_INVALID_OBSERVATION")
    cases = bundle["cases"]
    require(type(cases) is list and len(cases) == len(plans), "COMPLETE_CASE_SET_REQUIRED")
    results = []
    seen = set()
    by_id = {plan["id"]: plan for plan in plans}
    stopped = False
    for index, case in enumerate(cases):
        _fields(case, "id path request status_code response readback_before readback_after state reason", "INVALID_CASE")
        name = case["id"]
        require(type(name) is str and name in by_id and name not in seen, "CASE_SET_MISMATCH")
        require(name == plans[index]["id"], "CASE_ORDER_MISMATCH")
        seen.add(name)
        require(not stopped or case["state"] != "OBSERVED", "OBSERVATION_AFTER_STOP")
        result = verify_case(case, run_nonce=expected_run_nonce)
        if name == "operator-ask":
            # Remote unsigned UTC and this host's UTC have no independently
            # verified offset. The exact nonce-bearing question binds this case;
            # local capture age remains checked above without any tolerance.
            result.update(receipt_time_comparison="UNAVAILABLE",
                          receipt_time_reason="NO_VERIFIED_CROSS_CLOCK_OFFSET")
        results.append(result)
        stopped = stopped or case["state"] != "OBSERVED" or (case["state"] == "OBSERVED"
                                                           and not result["semantic_checks_passed"])
    observed = sum(row["semantic_checks_passed"] for row in results)
    return {"schema": "szl.operator-http-verification/v2", "status": "REPORTED",
            "source_revision": expected_source_revision, "run_nonce": expected_run_nonce,
            "origin": ORIGIN, "capture_binding_checks_passed": True,
            "reported_semantic_contracts": observed, "required_contracts": len(plans),
            "all_five_semantics_verified": observed == len(plans), "cases": results,
            "artifact_digest_verified": False, "publication_eligible": False,
            "freshness_basis": "LOCAL_CAPTURE_CLOCK_REPORTED",
            "execution_authorized": False, "passive_probe_modified": False,
            "limitations": ["Captured JSON objects and reported build identity are not authenticated transport or image provenance.",
                            "Remote receipt time cannot be compared to the local capture clock without an independently verified offset.",
                            "Policy receipt_hash is a correlation value, not a verified DSSE receipt.",
                            "Native receipt trust, live model execution and the separate DSSE observation bridge are not admitted.",
                            "Reverification never executes or authorizes a request; passive required NOT_PROBED rows remain unchanged."]}


def verify_bytes(raw, *, expected_sha256, expected_source_revision, expected_run_nonce, now=None):
    require(type(expected_sha256) is str and HEX64.fullmatch(expected_sha256) is not None,
            "INDEPENDENT_ARTIFACT_HASH_REQUIRED")
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, "INPUT_TOO_LARGE")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "ARTIFACT_HASH_MISMATCH")
    result = verify_bundle(strict_json(raw), expected_source_revision=expected_source_revision,
                           expected_run_nonce=expected_run_nonce, now=now)
    result.update(artifact_digest_verified=True, artifact_sha256=expected_sha256)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--expected-nonce", required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        with Path(args.bundle).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        result = verify_bytes(raw, expected_sha256=args.expected_sha256,
                              expected_source_revision=args.expected_source,
                              expected_run_nonce=args.expected_nonce)
    except (VerificationError, OSError) as exc:
        reason = str(exc) if isinstance(exc, VerificationError) else "ARTIFACT_UNAVAILABLE"
        print(json.dumps({"status": "BLOCKED", "reason": reason,
                          "publication_eligible": False, "execution_authorized": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    # Distinct nonzero status prevents a valid partial capture becoming a green gate.
    return 0 if result["all_five_semantics_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
