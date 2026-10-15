#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded operator HTTP observations; never a release or model-execution gate.

Taxonomy: supply-chain tooling. Default mode performs GET preflight only.
An explicit execution flag admits three fixed non-model contracts. Evaluation
and agent-loop execution remain blocked until their native trust and provider
budgets have a reviewed runtime adapter. No credential is read or transmitted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

import operator_acceptance_verify as verifier

ROOT = Path(__file__).resolve().parents[1]
BUILD = "/api/build-info"
FEED = "/api/a11oy/v1/policy/decisions/feed?limit=200"
MAX_RESPONSE = 512 * 1024
ADMITTED_CASES = ("policy-decide", "operator-ask", "policy-compliance")
POST_PATHS = frozenset(verifier.CONTRACTS[name] for name in ADMITTED_CASES)
GET_PATHS = frozenset((BUILD, FEED))


class ObservationError(ValueError):
    """Allowlisted diagnostic only; never include arbitrary HTTP output."""


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_new(path, value):
    raw = verifier.canonical(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


class Journal:
    """Persist invocation intent before any POST; do not silently resume runs."""
    def __init__(self, path):
        self.stream = path.open("x", encoding="utf-8")
        self.previous = "0" * 64

    def append(self, event, **values):
        record = {"event": event, "at": stamp(), "previous_sha256": self.previous,
                  **values}
        raw = verifier.canonical(record)
        self.stream.write(raw.decode("utf-8") + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.previous = digest(raw)

    def close(self):
        self.stream.close()


class CurlClient:
    """HTTPS only, no redirects/retries/proxy/config, strict time/byte bounds."""
    def __init__(self):
        self.executable = shutil.which("curl.exe" if os.name == "nt" else "curl")
        if not self.executable:
            raise ObservationError("CURL_UNAVAILABLE")
        result = subprocess.run([self.executable, "--disable", "--version"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=10, check=False)
        match = re.match(rb"curl (\d+)\.(\d+)\.(\d+)", result.stdout)
        # 8.4 introduced streaming --max-filesize enforcement, including bodies
        # without Content-Length. Do not run unbounded capture on older curl.
        if result.returncode or not match or tuple(map(int, match.groups())) < (8, 4, 0):
            raise ObservationError("CURL_8_4_OR_NEWER_REQUIRED")

    def request(self, method, path, payload=None):
        if ((method == "GET" and path not in GET_PATHS)
                or (method == "POST" and path not in POST_PATHS)
                or method not in ("GET", "POST")):
            raise ObservationError("REQUEST_NOT_ADMITTED")
        if (method == "GET" and payload is not None) or (method == "POST" and type(payload) is not dict):
            raise ObservationError("REQUEST_BODY_INVALID")
        with tempfile.TemporaryDirectory(prefix="a11oy-operator-http-") as directory:
            output = Path(directory) / "response"
            command = [self.executable, "--disable", "--silent", "--http1.1", "--proto", "=https",
                       "--noproxy", "*", "--connect-timeout", "10", "--max-time", "30",
                       "--max-redirs", "0", "--retry", "0", "--max-filesize", str(MAX_RESPONSE),
                       "--request", method, "--header", "Accept: application/json",
                       "--header", "Cache-Control: no-cache", "--output", str(output),
                       "--write-out", "%{http_code}", "--url", verifier.ORIGIN + path]
            raw_request = None
            if method == "POST":
                command += ["--header", "Content-Type: application/json", "--data-binary", "@-"]
                raw_request = verifier.canonical(payload)
            try:
                result = subprocess.run(command, input=raw_request, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, timeout=40, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ObservationError("HTTP_OUTCOME_UNAVAILABLE") from exc
            if result.returncode or not re.fullmatch(rb"[1-5][0-9]{2}", result.stdout):
                raise ObservationError("HTTP_OUTCOME_UNAVAILABLE")
            if not output.is_file() or output.stat().st_size > MAX_RESPONSE:
                raise ObservationError("HTTP_RESPONSE_LIMIT_EXCEEDED")
            status = int(result.stdout)
            with output.open("rb") as stream:
                raw = stream.read(MAX_RESPONSE + 1)
            body = verifier.strict_json(raw)
            if type(body) is not dict:
                raise ObservationError("HTTP_JSON_OBJECT_REQUIRED")
            return status, body


def _get(client, path):
    status, body = client.request("GET", path)
    if status != 200:
        raise ObservationError("READBACK_HTTP_UNAVAILABLE")
    return body


def collect(output, expected_source, *, execute=False, client=None):
    """Persist a fresh capture. Return receipt; incomplete acceptance exits 2."""
    if not verifier.SHA40.fullmatch(expected_source or ""):
        raise ObservationError("EXACT_SOURCE_REQUIRED")
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ObservationError("OUTPUT_MUST_BE_OUTSIDE_CHECKOUT")
    output.mkdir(parents=False, exist_ok=False)
    nonce = secrets.token_hex(16)
    cases = [{**plan, "status_code": None, "response": None,
              "readback_before": None, "readback_after": None,
              "state": "NOT_ATTEMPTED", "reason": "PREFLIGHT_ONLY"}
             for plan in verifier.planned_cases(nonce)]
    bundle = {"schema": verifier.SCHEMA, "evidence_class": "REPORTED",
              "expected_source_revision": expected_source, "origin": verifier.ORIGIN,
              "run_nonce": nonce, "started_at": stamp(), "finished_at": None,
              "build_before": None, "build_after": None, "cases": cases}
    journal = Journal(output / "journal.jsonl")
    current = None
    try:
        journal.append("prepared", source_revision=expected_source, run_nonce=nonce,
                       origin=verifier.ORIGIN, maximum_posts=3 if execute else 0,
                       evidence_class="REPORTED", publication_eligible=False,
                       effect_scope="one_noop_decision_and_two_static_lookups")
        client = CurlClient() if client is None else client
        bundle["build_before"] = _get(client, BUILD)
        verifier.validate_build_identity(bundle["build_before"], expected_source)
        if execute:
            for case in cases[:3]:
                if case["id"] not in ADMITTED_CASES:
                    raise ObservationError("REQUEST_NOT_ADMITTED")
                current = case
                case["reason"] = "PRE_POST_CHECK_FAILED"
                bundle["build_after"] = None
                bundle["build_after"] = _get(client, BUILD)
                verifier.validate_build_identity(bundle["build_after"], expected_source)
                if case["id"] == "policy-decide":
                    case["readback_before"] = _get(client, FEED)
                    verifier.validate_policy_baseline(case["readback_before"], nonce)
                journal.append("post_intent", case_id=case["id"], path=case["path"],
                               request_sha256=digest(verifier.canonical(case["request"])))
                # The journal records possible occurrence before dispatch. Any
                # exception from now until verified readback is UNKNOWN, never
                # zero attempts. No restart/resume or POST retry exists.
                case.update(state="UNKNOWN", reason="EFFECT_UNKNOWN")
                case["status_code"], case["response"] = client.request("POST", case["path"], case["request"])
                if case["id"] == "policy-decide":
                    case["readback_after"] = _get(client, FEED)
                bundle["build_after"] = None
                bundle["build_after"] = _get(client, BUILD)
                verifier.validate_build_identity(bundle["build_after"], expected_source)
                candidate = {**case, "state": "OBSERVED", "reason": "SCOPED_HTTP_OBSERVATION"}
                checked = verifier.verify_case(candidate, run_nonce=nonce)
                if checked["semantic_checks_passed"] is not True:
                    raise ObservationError("EFFECT_CONTRACT_MISMATCH")
                case.update(candidate)
                journal.append("observed", case_id=case["id"],
                               observation_sha256=digest(verifier.canonical(case)))
                current = None
        bundle["build_after"] = None
        bundle["build_after"] = _get(client, BUILD)
        verifier.validate_build_identity(bundle["build_after"], expected_source)
    except (ObservationError, verifier.VerificationError, OSError) as exc:
        reason = str(exc) if isinstance(exc, (ObservationError, verifier.VerificationError)) else "LOCAL_IO_UNAVAILABLE"
        if current is not None:
            current["reason"] = reason
        for case in cases:
            if case is not current and case["state"] == "NOT_ATTEMPTED":
                case["reason"] = "STOPPED_AFTER_PREFLIGHT_OR_EFFECT_FAILURE"
        journal.append("stopped", reason=reason,
                       effect_state=current["state"] if current else "NOT_ATTEMPTED")
    finally:
        journal.close()
    for case in cases[3:]:
        case["reason"] = "NATIVE_RECEIPT_TRUST_AND_BOUNDED_MODEL_EXECUTION_NOT_ADMITTED"
    bundle["finished_at"] = stamp()
    bundle_hash = write_new(output / "observation.json", bundle)
    try:
        checked = verifier.verify_bytes((output / "observation.json").read_bytes(),
                                        expected_sha256=bundle_hash, expected_source_revision=expected_source,
                                        expected_run_nonce=nonce)
    except verifier.VerificationError as exc:
        checked = {"status": "BLOCKED", "reason": str(exc), "publication_eligible": False,
                   "execution_authorized": False, "reported_semantic_contracts": 0,
                   "required_contracts": 5}
    verification_hash = write_new(output / "verification.json", checked)
    receipt = {"schema": "szl.operator-http-run/v1", "status": "BLOCKED",
               "evidence_class": "REPORTED", "origin": verifier.ORIGIN,
               "source_revision": expected_source, "run_nonce": nonce,
               "reported_semantic_contracts": checked["reported_semantic_contracts"],
               "required_contracts": 5, "publication_eligible": False,
               "execution_authorized": False, "signing": "UNSIGNED",
               "files": {"observation.json": bundle_hash,
                         "verification.json": verification_hash,
                         "journal.jsonl": digest((output / "journal.jsonl").read_bytes())}}
    write_new(output / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", required=True, help="Independently read exact deployed GitHub SHA")
    parser.add_argument("--out", required=True, help="New directory outside the source checkout")
    parser.add_argument("--execute-observational-cases", action="store_true",
                        help="Admit the fixed no-op policy decision and two static lookups (maximum 3 POSTs)")
    args = parser.parse_args()
    try:
        receipt = collect(args.out, args.expected_source, execute=args.execute_observational_cases)
    except (ObservationError, verifier.VerificationError, OSError, subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, (ObservationError, verifier.VerificationError)) else "RUN_UNAVAILABLE"
        print(json.dumps({"status": "BLOCKED", "reason": reason, "publication_eligible": False}))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 2  # All five execution contracts are required; scoped captures cannot clear them.


if __name__ == "__main__":
    raise SystemExit(main())
