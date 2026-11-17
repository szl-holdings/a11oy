#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""One fixed operator-authorized restraint receipt, with independent public pins.

This is not the five-case execution producer or a release qualification. No
private-key discovery, model request, GPU dispatch, deployment or configuration
write is provided. A timeout after POST reservation is ambiguous and never retried.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import execution_acceptance as evidence

ORIGIN = "https://szlholdings-a11oy.hf.space"
HF_INFO = "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy"
BUILD = ORIGIN + "/api/build-info"
STATUS = ORIGIN + "/api/a11oy/v1/series-a/status"
INFO = ORIGIN + "/api/a11oy/v1/restraint/info"
EVALUATE = ORIGIN + "/api/a11oy/v1/restraint/evaluate"
PAYLOAD_TYPE = "application/vnd.szl.receipt+json"
TASK = "Add a cache for these API responses while preserving validation and error handling."
BODY = {"task": TASK, "intensity": "full", "lang": "py"}
MAX_BYTES = 128 * 1024
MAX_REQUESTS = 9
TOTAL_SECONDS = 60.0
IO_SECONDS = 5.0


class CanaryBlocked(ValueError):
    pass


def require(condition, code):
    if condition is not True:
        raise CanaryBlocked(code)


@dataclass(frozen=True)
class Context:
    source: str
    runtime: str
    boot: str
    key_id: str
    public_key: object


def context_from_environment(source, env):
    runtime = env.get("A11OY_EXECUTION_HF_REVISION", "")
    boot = env.get("A11OY_EXECUTION_BOOT_ID", "")
    require(all(isinstance(v, str) and evidence.SHA40.fullmatch(v) is not None
                for v in (source, runtime)), "EXACT_EXPECTED_REVISIONS_REQUIRED")
    require(isinstance(boot, str) and re.fullmatch(r"boot_[0-9a-f]{32}", boot) is not None,
            "EXPECTED_BOOT_REQUIRED")
    raw = env.get("A11OY_EXECUTION_AUTHORITY_PINS_JSON", "").encode("utf-8")
    require(0 < len(raw) <= 16384, "INDEPENDENT_PUBLIC_PINS_REQUIRED")
    pins = evidence.strict_json(raw)
    evidence.fields(pins, "schema approval_public_pem approval_key_id runtime_public_pem runtime_key_id",
                    "INVALID_AUTHORITY_CONFIGURATION")
    require(pins["schema"] == "szl.execution-authority-pins/v1", "AUTHORITY_SCHEMA_MISMATCH")
    require(pins["runtime_key_id"] != pins["approval_key_id"], "SEPARATE_AUTHORITY_REQUIRED")
    # Validate the existing configuration; the approval key grants no authority here.
    evidence.public_key(pins["approval_public_pem"].encode(), pins["approval_key_id"])
    key = evidence.public_key(pins["runtime_public_pem"].encode(), pins["runtime_key_id"])
    return Context(source, runtime, boot, pins["runtime_key_id"], key)


class BoundedClient:
    def __init__(self, client, token, *, clock=time.monotonic):
        require(isinstance(token, str) and 0 < len(token) <= 4096
                and token == token.strip() and "\r" not in token and "\n" not in token,
                "OPERATOR_CREDENTIAL_REQUIRED")
        self.client, self.token, self.clock = client, token, clock
        self.deadline = clock() + TOTAL_SECONDS
        self.requests = 0
        self.post_attempts = 0
        self.verified_receipt = None

    def fetch(self, method, url):
        require((method == "GET" and url in {HF_INFO, BUILD, STATUS, INFO})
                or (method == "POST" and url == EVALUATE), "FIXED_ROUTE_REQUIRED")
        require(self.requests < MAX_REQUESTS, "REQUEST_BUDGET_EXHAUSTED")
        remaining = self.deadline - self.clock()
        require(remaining > 0, "DEADLINE_EXCEEDED")
        headers = {"Accept": "application/json", "Accept-Encoding": "identity",
                   "Cache-Control": "no-store"}
        content = None
        if method == "POST":
            require(self.post_attempts == 0, "POST_ALREADY_ATTEMPTED")
            self.post_attempts += 1  # Reserve before I/O, including ambiguous failure.
            headers.update(Authorization="Bearer " + self.token, **{"Content-Type": "application/json"})
            content = evidence.canonical(BODY)
            require(len(content) <= 1024, "REQUEST_BODY_TOO_LARGE")
        self.requests += 1
        try:
            with self.client.stream(method, url, headers=headers, content=content,
                                    follow_redirects=False,
                                    timeout=httpx.Timeout(min(IO_SECONDS, remaining))) as response:
                require(response.status_code == 200 and str(response.url) == url,
                        "HTTP_RESPONSE_REJECTED")
                require(response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        == "application/json", "JSON_RESPONSE_REQUIRED")
                require(response.headers.get("content-encoding", "identity").lower() == "identity",
                        "ENCODED_RESPONSE_REJECTED")
                length = response.headers.get("content-length")
                require(length is None or (length.isdigit() and 0 < int(length) <= MAX_BYTES),
                        "RESPONSE_SIZE_INVALID")
                body = bytearray()
                for chunk in response.iter_raw():
                    require(self.clock() <= self.deadline, "DEADLINE_EXCEEDED")
                    body.extend(chunk)
                    require(len(body) <= MAX_BYTES, "RESPONSE_TOO_LARGE")
                require(self.clock() <= self.deadline, "DEADLINE_EXCEEDED")
                require(length is None or len(body) == int(length), "RESPONSE_SIZE_MISMATCH")
            require(self.token.encode() not in body, "CREDENTIAL_REFLECTION_REJECTED")
            value = evidence.strict_json(bytes(body))
            require(type(value) is dict, "JSON_OBJECT_REQUIRED")
            return value
        except (CanaryBlocked, evidence.EvidenceError):
            raise
        except httpx.TimeoutException:
            raise CanaryBlocked("HTTP_TIMEOUT_NO_RETRY") from None
        except Exception:
            raise CanaryBlocked("HTTP_TRANSPORT_UNAVAILABLE_NO_RETRY") from None


def bracket(transport, context):
    hf = transport.fetch("GET", HF_INFO)
    runtime = hf.get("runtime") or {}
    require(hf.get("id") == "SZLHOLDINGS/a11oy" and hf.get("sdk") == "docker"
            and hf.get("private") is False and runtime.get("stage") == "RUNNING"
            and hf.get("sha") == runtime.get("sha") == context.runtime,
            "HF_IDENTITY_MISMATCH")
    build = transport.fetch("GET", BUILD)
    require((build.get("build") or {}).get("revision") == context.source,
            "SOURCE_IDENTITY_MISMATCH")
    status = transport.fetch("GET", STATUS)
    require(status.get("schema") == "szl.series-a-status/v1"
            and status.get("source_revision") == context.source
            and status.get("runtime_boot_id") == context.boot
            and status.get("signing_key_source") == "persistent:env:SZL_COSIGN_PRIVATE_PEM",
            "PROCESS_IDENTITY_MISMATCH")
    return {"source_revision": context.source, "hf_revision": context.runtime,
            "runtime_boot_id": context.boot}


def verify_response(response, context, token):
    envelope = response.get("signed_receipt")
    payload = response.get("receipt_payload")
    require(type(envelope) is dict and envelope.get("signed") is True
            and envelope.get("_dsse") == "DSSEv1", "SIGNED_DSSE_REQUIRED")
    core = {k: envelope.get(k) for k in ("payloadType", "payload", "signatures")}
    verified = evidence.verify(core, PAYLOAD_TYPE, context.public_key, context.key_id)
    require(token.encode() not in evidence.canonical(verified), "CREDENTIAL_REFLECTION_REJECTED")
    identity = verified.pop("_signing_identity", None)
    require(type(identity) is dict and identity.get("keyid") == context.key_id,
            "SIGNING_IDENTITY_MISMATCH")
    require(type(payload) is dict and verified == payload, "RECEIPT_PAYLOAD_MISMATCH")
    require(payload.get("kind") == "restraint.decision"
            and payload.get("task_digest") == hashlib.sha256(TASK.encode()).hexdigest()
            and payload.get("intensity") == BODY["intensity"]
            and payload.get("doctrine") == "v11", "FIXED_TASK_BINDING_MISMATCH")
    # Retain only signed DSSE fields, never arbitrary unsigned server metadata.
    return core, evidence.digest(evidence.canonical(envelope))


def run_canary(transport, context):
    before = bracket(transport, context)
    prior = transport.fetch("GET", INFO)
    require((prior.get("signer_health") or {}).get("identity") == context.key_id
            and (prior.get("signer_health") or {}).get("identity_checked") is True,
            "RUNTIME_KEY_IDENTITY_MISMATCH")
    response = transport.fetch("POST", EVALUATE)
    envelope, digest = verify_response(response, context, transport.token)
    transport.verified_receipt = {"signed_receipt": envelope, "native_receipt_sha256": digest,
                                  "signature_verified": True, "qualified": False}
    observed = transport.fetch("GET", INFO)
    signer = observed.get("signer_health") or {}
    receipt = observed.get("receipt_verification") or {}
    require(signer.get("observed_this_process") is True and signer.get("ready") is True
            and signer.get("identity_checked") is True
            and signer.get("identity") == signer.get("last_verified_identity") == context.key_id,
            "SIGNER_READBACK_MISMATCH")
    require(receipt.get("observed_this_process") is True
            and receipt.get("cryptographically_verified") is True
            and type(receipt.get("signature_count")) is int and receipt["signature_count"] == 1
            and receipt.get("method") == "ECDSA-P256-SHA256 DSSE PAE"
            and receipt.get("receipt_sha256") == digest, "RECEIPT_READBACK_MISMATCH")
    require((prior.get("receipt_verification") or {}).get("receipt_sha256") != digest,
            "OBSERVATION_NOT_ADVANCED")
    after = bracket(transport, context)
    require(before == after, "SOURCE_OR_BOOT_CHANGED")
    require(transport.requests == MAX_REQUESTS and transport.post_attempts == 1,
            "REQUEST_ACCOUNTING_MISMATCH")
    return {"schema": "szl.restraint-receipt-canary/v1", "state": "VERIFIED",
            "checked_at": datetime.now(timezone.utc).isoformat(), "identity": after,
            "key_id": context.key_id, "native_receipt_sha256": digest, "signed_receipt": envelope,
            "dsse_sha256": evidence.digest(evidence.canonical(envelope)),
            "request_sha256": evidence.digest(evidence.canonical(BODY)),
            "requests": transport.requests, "post_attempts": transport.post_attempts,
            "source_boot_binding": "BRACKETED_READBACK_NOT_SIGNED_IN_NATIVE_RECEIPT",
            "execution_authorized": False, "release_qualified": False,
            "full_readiness_claimed": False, "model_requests": 0, "gpu_dispatches": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    token = os.environ.get("A11OY_CODE_ADMIN_KEY", "")
    transport = None
    result = {"schema": "szl.restraint-receipt-canary/v1", "state": "BLOCKED",
              "execution_authorized": False, "release_qualified": False,
              "full_readiness_claimed": False}
    # Refuse an existing artifact before any network effect.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        try:
            require(args.execute, "EXPLICIT_EXECUTION_REQUIRED")
            context = context_from_environment(args.source_sha, os.environ)
            # HTTPX's normal transport has zero retries and preserves configured
            # proxy routing and CA trust. Do not substitute a direct-egress transport.
            with httpx.Client(follow_redirects=False, trust_env=True) as client:
                transport = BoundedClient(client, token)
                result = run_canary(transport, context)
            code = 0
        except Exception as exc:
            reason = str(exc) if isinstance(exc, (CanaryBlocked, evidence.EvidenceError)) else "CANARY_UNAVAILABLE"
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason) or (token and token in reason):
                reason = "CANARY_UNAVAILABLE"
            attempts = transport.post_attempts if transport else 0
            result.update(error=reason, requests=transport.requests if transport else 0,
                          post_attempts=attempts,
                          post_effect="UNKNOWN_NO_RETRY" if attempts else "NOT_DISPATCHED")
            if transport and transport.verified_receipt is not None:
                result["verified_but_unqualified_receipt"] = transport.verified_receipt
            code = 2
        output.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items()
                      if k in {"state", "error", "requests", "post_attempts", "post_effect",
                               "native_receipt_sha256", "execution_authorized", "release_qualified"}}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
