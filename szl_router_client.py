#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services-layer client for the opt-in router_control hash-receipt contract.

SHA-256 binds request, result and routing provenance. It is not a signature,
DSSE envelope, model-weight attestation, or independent execution witness.
"""
import hashlib
import hmac
import json
import os
import re
import uuid
from urllib.parse import urlsplit, urlunsplit

import httpx

MAX_RESPONSE_BYTES = 2_000_000
_HEX = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")


class RouterContractError(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _origin(value):
    parsed = urlsplit(value)
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port or (
        443 if parsed.scheme.lower() == "https" else 80)


def _configuration(request_origin=""):
    base = os.getenv("SZL_ROUTER_BASE_URL", "").strip()
    token = os.getenv("SZL_ROUTER_TOKEN", "").strip()
    revision = os.getenv("SZL_ROUTER_SOURCE_REVISION", "").strip()
    model = os.getenv("SZL_ROUTER_MODEL", "").strip()
    if not base or not token or not _REVISION.fullmatch(revision) or not _IDENTIFIER.fullmatch(model):
        raise RouterContractError("ROUTER_CONFIGURATION_REQUIRED")
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/v1"}
            or parsed.port not in {None, 443}):
        raise RouterContractError("INVALID_ROUTER_BASE_URL")
    if any(char in token for char in "\r\n"):
        raise RouterContractError("INVALID_ROUTER_TOKEN")
    base = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    existing = [request_origin, "https://a-11-oy.com", "https://szlholdings-a11oy.hf.space"]
    existing += [os.getenv(name, "") for name in (
        "A11OY_MODEL_BASE_URL", "A11OY_BRAIN_URL", "SZL_LOCAL_LLM_URL", "SZL_SOVEREIGN_GATEWAY")]
    if any(value and _origin(value) == _origin(base) for value in existing):
        raise RouterContractError("ROUTER_RECURSION_FORBIDDEN")
    return base, token, revision, model


def configuration_status():
    """Local configuration admission; never probes or reports live inference."""
    try:
        _configuration()
    except (ValueError, TypeError):
        return {"state": "UNAVAILABLE", "basis": "LOCAL_CONFIGURATION_ONLY"}
    return {"state": "CONFIGURED_UNVERIFIED", "basis": "LOCAL_CONFIGURATION_ONLY"}


def _read(client, method, url, *, headers, payload=None):
    with client.stream(method, url, headers=headers, json=payload) as response:
        if "no-store" not in {item.strip().lower() for item in response.headers.get("cache-control", "").split(",")}:
            raise RouterContractError("ROUTER_NO_STORE_REQUIRED")
        chunks = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise RouterContractError("ROUTER_RESPONSE_TOO_LARGE")
            chunks.append(chunk)
        if "application/json" not in response.headers.get("content-type", "").lower():
            raise RouterContractError("ROUTER_JSON_REQUIRED")
        try:
            value = json.loads(b"".join(chunks).decode("utf-8"), object_pairs_hook=_unique_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RouterContractError("INVALID_ROUTER_JSON") from exc
        if not isinstance(value, dict):
            raise RouterContractError("ROUTER_OBJECT_REQUIRED")
        return response.status_code, value, response.headers


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _safe_failure(detail):
    """Only known diagnostic enums and HTTP codes; no arbitrary gateway text."""
    result = {"evidence": "UNVERIFIED_FAILURE_DIAGNOSTICS"}
    if not isinstance(detail, dict):
        return result
    codes = {"INVALID_ROUTER_CONFIGURATION", "EGRESS_DISABLED", "NO_ELIGIBLE_PROVIDER",
             "CALLER_AUTH_NOT_CONFIGURED", "INVALID_ROUTER_CREDENTIAL"}
    if detail.get("code") in codes:
        result["code"] = detail["code"]
    if detail.get("state") == "ALL_ELIGIBLE_PROVIDERS_FAILED":
        result["state"] = detail["state"]
    attempts = detail.get("attempts")
    states = {"SKIPPED_CREDENTIAL_UNAVAILABLE", "UPSTREAM_HTTP_ERROR", "TRANSPORT_OR_CONTRACT_ERROR"}
    if isinstance(attempts, list):
        result["attempts"] = []
        for attempt in attempts[:16]:
            if not isinstance(attempt, dict):
                continue
            row = {}
            if attempt.get("state") in states:
                row["state"] = attempt["state"]
            status = attempt.get("status_code")
            if type(status) is int and 400 <= status <= 599:
                row["status_code"] = status
            if row:
                result["attempts"].append(row)
    return result


def _source(client, base, revision, headers):
    status, value, _ = _read(client, "GET", base + "/api/source", headers=headers)
    receipt = value.get("receipt")
    body = {key: item for key, item in value.items() if key != "receipt"}
    files = value.get("controlled_files")
    expected_files = {"router_control/app.py", "router_control/static/index.html",
                      "router_control/static/app.js", "router_control/static/styles.css"}
    if (status != 200 or value.get("schema") != "szl.router-source/v1"
            or value.get("repository") != "szl-holdings/szl-router"
            or value.get("revision") != revision or not isinstance(receipt, dict)
            or not isinstance(files, dict) or set(files) != expected_files
            or any(not isinstance(item, str) or not _HEX.fullmatch(item)
                   for item in files.values())
            or any(value.get(key) is not False for key in
                   ("default_egress", "secret_output", "arbitrary_url_routing"))
            or receipt.get("algorithm") != "sha256"
            or receipt.get("digest") != _digest(body)):
        raise RouterContractError("ROUTER_SOURCE_BINDING_INVALID")
    return receipt["digest"]


def _verify_completion(value, headers, request):
    receipt = value.get("szl_receipt")
    if not isinstance(receipt, dict):
        raise RouterContractError("ROUTER_RECEIPT_REQUIRED")
    body = {key: item for key, item in receipt.items() if key not in {"digest", "algorithm"}}
    digest = receipt.get("digest")
    if (receipt.get("schema") != "szl.router-receipt/v1"
            or receipt.get("algorithm") != "sha256" or not isinstance(digest, str)
            or not _HEX.fullmatch(digest) or not hmac.compare_digest(digest, _digest(body))
            or headers.get("x-szl-receipt") != digest):
        raise RouterContractError("ROUTER_RECEIPT_DIGEST_INVALID")
    completion = {key: item for key, item in value.items() if key != "szl_receipt"}
    if (receipt.get("request_digest") != _digest(request)
            or receipt.get("response_digest") != _digest(completion)
            or receipt.get("public_model") != request["model"]
            or receipt.get("classification") != request["data_classification"]
            or receipt.get("secret_material_recorded") is not False
            or not isinstance(receipt.get("provider_id"), str)
            or not _IDENTIFIER.fullmatch(receipt["provider_id"])
            or not isinstance(receipt.get("plan_digest"), str)
            or not _HEX.fullmatch(receipt["plan_digest"])
            or not isinstance(receipt.get("upstream_model"), str)
            or not _IDENTIFIER.fullmatch(receipt["upstream_model"])
            or completion.get("model") != receipt["upstream_model"]):
        raise RouterContractError("ROUTER_PROVENANCE_INVALID")
    attempts = receipt.get("attempts")
    if (not isinstance(attempts, list) or not attempts
            or not isinstance(attempts[-1], dict)
            or attempts[-1].get("provider_id") != receipt["provider_id"]
            or attempts[-1].get("state") != "SUCCESS"
            or attempts[-1].get("status_code") != 200):
        raise RouterContractError("ROUTER_ATTEMPT_INVALID")
    choices = completion.get("choices")
    if completion.get("error") is not None or not isinstance(choices, list) or not choices:
        raise RouterContractError("ROUTER_COMPLETION_INVALID")
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise RouterContractError("ROUTER_COMPLETION_INVALID")
        if (choice.get("finish_reason") != "content_filter"
                and not any(message.get(key) for key in ("content", "refusal", "tool_calls"))):
            raise RouterContractError("ROUTER_COMPLETION_EMPTY")
        if any(message.get(key) is not None and not isinstance(message[key], str)
               for key in ("content", "refusal")):
            raise RouterContractError("ROUTER_COMPLETION_INVALID")
    return completion, receipt


def complete(prompt, *, classification, request_id=None, request_origin=""):
    """Execute once after the caller's governance allow; no provider fallback."""
    evidence = {"state": "UNAVAILABLE", "answer": None, "signature_state": "UNSIGNED",
                "receipt_kind": "HASH_INTEGRITY_ONLY", "http_status": 503}
    try:
        base, token, revision, model = _configuration(request_origin)
        if classification not in {"PUBLIC", "INTERNAL"}:
            raise RouterContractError("ROUTER_CLASSIFICATION_DENIED")
        if not isinstance(prompt, str) or not 0 < len(prompt) <= 32_000:
            raise RouterContractError("INVALID_ROUTER_PROMPT")
        request_id = request_id or uuid.uuid4().hex
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,96}", request_id):
            raise RouterContractError("INVALID_REQUEST_ID")
        request = {
            "model": model, "messages": [{"role": "user", "content": prompt, "name": None}],
            "temperature": None, "top_p": None, "max_tokens": 1200, "stream": False,
            "stop": None, "user": request_id, "data_classification": classification.lower(),
            "max_cost_tier": 0,
        }
        # Source probes carry no bearer credential. Credentials go only to the pinned gateway.
        headers = {"Accept": "application/json", "Cache-Control": "no-store", "X-Request-ID": request_id}
        with httpx.Client(timeout=httpx.Timeout(45, connect=10), follow_redirects=False,
                          trust_env=False) as client:
            source_digest = _source(client, base, revision, headers)
            status, admission, _ = _read(client, "GET", base + "/readyz/inference", headers=headers)
            if (status != 200 or admission.get("ready_for_requests") is not True
                    or admission.get("basis") != "LOCAL_CONFIGURATION_ONLY"):
                raise RouterContractError("ROUTER_NOT_ADMITTED")
            status, value, response_headers = _read(
                client, "POST", base + "/v1/chat/completions",
                headers={**headers, "Authorization": f"Bearer {token}", "X-SZL-Router-Hop": "1"},
                payload=request,
            )
            if status != 200:
                # Preserve the status and provider attempt trail; never fall through to another backend.
                return {**evidence, "http_status": status if 400 <= status <= 599 else 502,
                        "error": "ROUTER_REQUEST_FAILED", "failure": _safe_failure(value.get("detail")),
                        "request_id": request_id}
            completion, receipt = _verify_completion(value, response_headers, request)
            if _source(client, base, revision, headers) != source_digest:
                raise RouterContractError("ROUTER_SOURCE_CHANGED_DURING_REQUEST")
        message = completion["choices"][0]["message"]
        refused = bool(message.get("refusal") or completion["choices"][0].get("finish_reason") == "content_filter")
        return {**evidence, "state": "REFUSED" if refused else "COMPLETED",
                "http_status": 200, "answer": None if refused else message.get("content"),
                "completion": completion, "receipt": receipt, "source_revision": revision,
                "request_id": request_id, "refusal": message.get("refusal"),
                "source_binding": "MATCHED_BEFORE_AND_AFTER", "energy": "UNAVAILABLE"}
    except (RouterContractError, httpx.HTTPError, ValueError, TypeError) as exc:
        code = str(exc) if isinstance(exc, RouterContractError) else "ROUTER_TRANSPORT_OR_CONTRACT_ERROR"
        return {**evidence, "error": code}
