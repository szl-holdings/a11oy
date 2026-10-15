#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline, public-key-only binding checks for five execution observations.

This does not execute requests, discover keys, grant credentials or admit a release.
DSSE PAE and ECDSA-P256/SHA256 match szl_dsse.py; its ambient/private-key discovery
is deliberately not used. Pins and expected identities come from the caller's
independent admission context, never from the submitted evidence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ORIGIN = "https://szlholdings-a11oy.hf.space"
PLAN_TYPE = "application/vnd.szl.execution-acceptance-plan.v1+json"
RECEIPT_TYPE = "application/vnd.szl.execution-observation.v1+json"
CONTRACTS = {
    "policy-decide": "/api/a11oy/v1/policy/decide",
    "policy-compliance": "/api/a11oy/v1/policy/compliance",
    "operator-ask": "/api/a11oy/v1/operator/ask",
    "eval-run": "/api/a11oy/v1/eval/run",
    "agentloop-run": "/api/a11oy/v1/agentloop/run",
}
MAX_BYTES = 2 * 1024 * 1024
MAX_BODY = 128 * 1024
MAX_AGE = timedelta(minutes=15)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class EvidenceError(ValueError):
    """The supplied artifact cannot establish the requested binding."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceError(code)


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("INVALID_JSON_VALUE") from exc


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw: bytes) -> Any:
    require(len(raw) <= MAX_BYTES, "INPUT_TOO_LARGE")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(_):
        raise EvidenceError("NONFINITE_JSON")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
        canonical(value)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("INVALID_JSON") from exc


def fields(value: Any, expected: str, code: str) -> dict:
    require(type(value) is dict and set(value) == set(expected.split()), code)
    return value


def text(value: Any, code: str) -> str:
    require(type(value) is str and 0 < len(value) <= 256 and value == value.strip(), code)
    return value


def decode(value: Any, limit: int = MAX_BODY) -> bytes:
    require(type(value) is str and len(value) <= 4 * ((limit + 2) // 3), "INVALID_BASE64")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise EvidenceError("INVALID_BASE64") from exc
    require(len(raw) <= limit, "BODY_TOO_LARGE")
    return raw


def moment(value: Any) -> datetime:
    require(type(value) is str and value.endswith("Z"), "UTC_TIME_REQUIRED")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError("INVALID_TIME") from exc
    require(result.utcoffset() == timedelta(0), "UTC_TIME_REQUIRED")
    return result


def public_key(pem: bytes, expected_pin: str):
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    require(type(expected_pin) is str and HEX64.fullmatch(expected_pin) is not None,
            "PUBLIC_KEY_PIN_REQUIRED")
    require(type(pem) is bytes and len(pem) <= 4096, "INVALID_PUBLIC_KEY")
    try:
        key = serialization.load_pem_public_key(pem)
        require(isinstance(key, ec.EllipticCurvePublicKey)
                and isinstance(key.curve, ec.SECP256R1), "P256_KEY_REQUIRED")
        normalized = key.public_bytes(serialization.Encoding.PEM,
                                      serialization.PublicFormat.SubjectPublicKeyInfo)
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise EvidenceError("INVALID_PUBLIC_KEY") from exc
    require(digest(normalized.strip()) == expected_pin, "PUBLIC_KEY_PIN_MISMATCH")
    return key


def verify(envelope: Any, payload_type: str, key, key_id: str) -> dict:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    fields(envelope, "payloadType payload signatures", "INVALID_ENVELOPE")
    require(envelope["payloadType"] == payload_type, "PAYLOAD_TYPE_MISMATCH")
    signatures = envelope["signatures"]
    require(type(signatures) is list and len(signatures) == 1, "ONE_SIGNATURE_REQUIRED")
    signature = fields(signatures[0], "keyid sig", "INVALID_SIGNATURE_RECORD")
    require(signature["keyid"] == key_id, "SIGNER_MISMATCH")
    body = decode(envelope["payload"], MAX_BYTES)
    kind = payload_type.encode("utf-8")
    pae = b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(body)).encode() + b" " + body
    try:
        key.verify(decode(signature["sig"], 128), pae, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError) as exc:
        raise EvidenceError("SIGNATURE_INVALID") from exc
    payload = strict_json(body)
    require(type(payload) is dict, "PAYLOAD_OBJECT_REQUIRED")
    return payload


@dataclass(frozen=True)
class AdmissionContext:
    """Out-of-band caller inputs. Never construct this from bundle contents."""

    source_revision: str
    runtime_revision: str
    runtime_boot_id: str
    run_nonce: str
    authority_public_key: bytes
    authority_key_id: str
    runtime_public_key: bytes
    runtime_key_id: str


def validate_plan(envelope: Any, context: AdmissionContext, *, now: datetime | None = None) -> dict:
    """Verify the complete plan against independent context; grants no authority.

    Runtime callers still need their own credential, scope, storage and effect
    admission. Sharing this parser does not turn five planned requests into five
    observed requests.
    """
    now = datetime.now(timezone.utc) if now is None else now
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() == timedelta(0), "UTC_NOW_REQUIRED")
    require(type(context.source_revision) is str and type(context.runtime_revision) is str
            and SHA40.fullmatch(context.source_revision) is not None
            and SHA40.fullmatch(context.runtime_revision) is not None, "EXACT_REVISIONS_REQUIRED")
    text(context.runtime_boot_id, "BOOT_ID_REQUIRED")
    require(type(context.run_nonce) is str and HEX64.fullmatch(context.run_nonce) is not None,
            "RUN_NONCE_REQUIRED")
    require(len(canonical(envelope)) <= MAX_BYTES, "INPUT_TOO_LARGE")
    require(context.authority_key_id != context.runtime_key_id, "SEPARATE_AUTHORITY_REQUIRED")
    authority = public_key(context.authority_public_key, context.authority_key_id)
    public_key(context.runtime_public_key, context.runtime_key_id)
    plan = verify(envelope, PLAN_TYPE, authority, context.authority_key_id)
    fields(plan, "schema origin source_revision runtime_revision runtime_boot_id run_nonce issued_at expires_at operator_reference max_requests retries cases", "INVALID_PLAN")
    require(plan["schema"] == "szl.execution-acceptance-plan/v1", "PLAN_SCHEMA_MISMATCH")
    bindings = {"origin": ORIGIN, "source_revision": context.source_revision,
                "runtime_revision": context.runtime_revision,
                "runtime_boot_id": context.runtime_boot_id, "run_nonce": context.run_nonce}
    require(all(plan[k] == v for k, v in bindings.items()), "PLAN_BINDING_MISMATCH")
    text(plan["operator_reference"], "OPERATOR_REFERENCE_REQUIRED")
    start, end = moment(plan["issued_at"]), moment(plan["expires_at"])
    require(start <= now <= end and timedelta(0) < end - start <= MAX_AGE, "PLAN_EXPIRED_OR_INVALID")
    require(type(plan["max_requests"]) is int and plan["max_requests"] == 5
            and type(plan["retries"]) is int and plan["retries"] == 0, "REQUEST_BUDGET_INVALID")
    cases = plan["cases"]
    require(type(cases) is list and len(cases) == 5, "COMPLETE_PLAN_REQUIRED")
    planned = {}
    for case in cases:
        fields(case, "id method path body expected_status response_assertions readback_assertions", "INVALID_CASE")
        case_id = case["id"]
        require(type(case_id) is str and case_id in CONTRACTS and case_id not in planned, "CASE_SET_MISMATCH")
        require(case["method"] == "POST" and case["path"] == CONTRACTS[case_id], "ROUTE_MISMATCH")
        require(type(case["body"]) is dict and bool(case["body"])
                and len(canonical(case["body"])) <= MAX_BODY, "EXPLICIT_BODY_REQUIRED")
        body = case["body"]
        if case_id in ("eval-run", "agentloop-run"):
            text(body.get("model_id"), "EXPLICIT_MODEL_REQUIRED")
        if case_id == "eval-run":
            text(body.get("suite"), "EXPLICIT_SUITE_REQUIRED")
            require(body.get("execution_mode") == "live", "MODELED_IS_NOT_LIVE_ACCEPTANCE")
        if case_id == "agentloop-run":
            text(body.get("task"), "EXPLICIT_TASK_REQUIRED")
            text(body.get("eval_suite"), "EXPLICIT_SUITE_REQUIRED")
            require(body.get("mode") == "chat" and body.get("sandbox") is False
                    and type(body.get("max_retries")) is int and body["max_retries"] == 0
                    and body.get("consult_brain") is False and body.get("allocate_energy") is False
                    and "approval" not in body, "AGENT_EFFECT_SCOPE_UNSUPPORTED")
        require(type(case["expected_status"]) is int and 200 <= case["expected_status"] < 300,
                "SUCCESS_STATUS_REQUIRED")
        for name in ("response_assertions", "readback_assertions"):
            require(type(case[name]) is dict and 0 < len(case[name]) <= 16, "ASSERTIONS_REQUIRED")
            for pointer in case[name]:
                require(type(pointer) is str and pointer.startswith("/") and len(pointer) <= 256,
                        "JSON_POINTER_REQUIRED")
                require(re.search(r"~(?![01])", pointer) is None, "INVALID_POINTER_ESCAPE")
        planned[case_id] = case
    return plan


def validate(bundle: Any, context: AdmissionContext, *, now: datetime | None = None) -> dict:
    """Check signatures/bindings; return no execution or publication authorization."""
    now = datetime.now(timezone.utc) if now is None else now
    require(len(canonical(bundle)) <= MAX_BYTES, "INPUT_TOO_LARGE")
    fields(bundle, "schema plan observations", "INVALID_BUNDLE")
    require(bundle["schema"] == "szl.execution-acceptance-bundle/v1", "BUNDLE_SCHEMA_MISMATCH")
    plan = validate_plan(bundle["plan"], context, now=now)
    runtime = public_key(context.runtime_public_key, context.runtime_key_id)
    bindings = {"origin": ORIGIN, "source_revision": context.source_revision,
                "runtime_revision": context.runtime_revision,
                "runtime_boot_id": context.runtime_boot_id, "run_nonce": context.run_nonce}
    start, end = moment(plan["issued_at"]), moment(plan["expires_at"])
    planned = {case["id"]: case for case in plan["cases"]}
    rows = bundle["observations"]
    require(type(rows) is list and len(rows) == 5, "COMPLETE_EVIDENCE_REQUIRED")
    seen, receipt_ids = set(), set()
    plan_hash = digest(canonical(plan))
    for row in rows:
        fields(row, "receipt response_b64 readback_b64", "INVALID_OBSERVATION")
        receipt = verify(row["receipt"], RECEIPT_TYPE, runtime, context.runtime_key_id)
        fields(receipt, "schema receipt_id case_id plan_sha256 origin source_revision runtime_revision runtime_boot_id run_nonce operator_reference request_sha256 response_sha256 readback_sha256 response_status started_at completed_at", "INVALID_RECEIPT")
        require(receipt["schema"] == "szl.execution-observation/v1", "RECEIPT_SCHEMA_MISMATCH")
        case_id = receipt["case_id"]
        require(type(case_id) is str and case_id in planned and case_id not in seen, "CASE_SET_MISMATCH")
        receipt_id = text(receipt["receipt_id"], "RECEIPT_ID_REQUIRED")
        require(receipt_id not in receipt_ids, "DUPLICATE_RECEIPT")
        seen.add(case_id)
        receipt_ids.add(receipt_id)
        require(all(receipt[k] == v for k, v in bindings.items()), "RECEIPT_BINDING_MISMATCH")
        require(receipt["plan_sha256"] == plan_hash
                and receipt["operator_reference"] == plan["operator_reference"], "AUTHORITY_BINDING_MISMATCH")
        begun, done = moment(receipt["started_at"]), moment(receipt["completed_at"])
        require(start <= begun <= done <= min(now, end) and now - done <= MAX_AGE,
                "OBSERVATION_TIME_INVALID")
        case = planned[case_id]
        request = {k: case[k] for k in ("method", "path", "body")}
        require(receipt["request_sha256"] == digest(canonical(request)), "REQUEST_HASH_MISMATCH")
        require(type(receipt["response_status"]) is int
                and receipt["response_status"] == case["expected_status"], "RESPONSE_STATUS_MISMATCH")
        for label in ("response", "readback"):
            raw = decode(row[label + "_b64"])
            require(receipt[label + "_sha256"] == digest(raw), label.upper() + "_HASH_MISMATCH")
            payload = strict_json(raw)
            for pointer, expected in case[label + "_assertions"].items():
                value = payload
                try:
                    for part in pointer[1:].split("/"):
                        key = part.replace("~1", "/").replace("~0", "~")
                        require(type(value) is dict and key in value, "ASSERTION_PATH_MISSING")
                        value = value[key]
                except (KeyError, TypeError) as exc:
                    raise EvidenceError("ASSERTION_PATH_MISSING") from exc
                require(canonical(value) == canonical(expected), "ASSERTION_MISMATCH")
    return {"schema": "szl.execution-acceptance-validation/v1", "status": "REPORTED",
            "binding_checks_passed": True, "plan_sha256": plan_hash,
            "cases": sorted(seen), "receipt_ids": sorted(receipt_ids),
            "source_revision": context.source_revision, "runtime_revision": context.runtime_revision,
            "publication_eligible": False, "execution_authorized": False,
            "passive_probe_modified": False,
            "limitation": "Signed observations checked offline; producer execution, key trust admission, "
                          "endpoint semantics and release integration require separate review."}


def read_file(path: str, limit: int = MAX_BYTES) -> bytes:
    with Path(path).open("rb") as handle:
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, "INPUT_TOO_LARGE")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle")
    for name in ("source-revision", "runtime-revision", "runtime-boot-id", "run-nonce",
                 "authority-key", "authority-key-id", "runtime-key", "runtime-key-id"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        context = AdmissionContext(args.source_revision, args.runtime_revision,
                                   args.runtime_boot_id, args.run_nonce,
                                   read_file(args.authority_key, 4096), args.authority_key_id,
                                   read_file(args.runtime_key, 4096), args.runtime_key_id)
        result = validate(strict_json(read_file(args.bundle)), context)
    except (EvidenceError, OSError, ImportError) as exc:
        code = str(exc) if isinstance(exc, EvidenceError) else type(exc).__name__
        print(json.dumps({"status": "BLOCKED", "reason": code, "publication_eligible": False,
                          "execution_authorized": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
