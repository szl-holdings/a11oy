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
import threading
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import httpx

MAX_RESPONSE_BYTES = 2_000_000
_HEX = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")


class RouterContractError(ValueError):
    pass


class ExecutionBudgetError(ValueError):
    """A local request bound failed; never contains provider or credential text."""


class ExecutionBudget:
    """Opt-in bounds on client requests, requested output and observed elapsed time.

    These are not a billing ceiling or an assertion about a remote provider's
    internal retries. Reservations are consumed before dispatch and never refunded.
    A failed or ambiguous request closes the budget instead of authorizing a retry.
    """

    _CAPS = {"max_model_requests": 32, "max_output_tokens": 32768,
             "max_elapsed_seconds": 300}

    def __init__(self, limits):
        if (not isinstance(limits, dict) or set(limits) != set(self._CAPS)
                or any(type(limits[key]) is not int or not 1 <= limits[key] <= cap
                       for key, cap in self._CAPS.items())):
            raise ExecutionBudgetError("INVALID_EXECUTION_LIMITS")
        self._limits = dict(limits)
        self._started = time.monotonic()
        self._deadline = self._started + limits["max_elapsed_seconds"]
        self._lock = threading.RLock()
        self._requests = 0
        self._reserved = 0
        self._reported = 0
        self._unknown_usage = 0
        self._pending = None
        self._error = None
        self._ambiguous = False

    @property
    def max_output_tokens(self):
        return self._limits["max_output_tokens"]

    @property
    def remaining_output_tokens(self):
        with self._lock:
            return self.max_output_tokens - self._reserved

    @property
    def remaining_attempts(self):
        with self._lock:
            return self._limits["max_model_requests"] - self._requests

    def check(self):
        with self._lock:
            if self._error:
                raise ExecutionBudgetError(self._error)
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self.fail("EXECUTION_DEADLINE_EXCEEDED", ambiguous=self._pending is not None)
                raise ExecutionBudgetError(self._error)
            return remaining

    def preflight(self, attempts, output_tokens):
        with self._lock:
            self.check()
            if (type(attempts) is not int or attempts < 1
                    or type(output_tokens) is not int or output_tokens < attempts):
                raise ExecutionBudgetError("INVALID_EXECUTION_PREFLIGHT")
            if self._pending is not None:
                raise ExecutionBudgetError("EXECUTION_REQUEST_ALREADY_PENDING")
            if attempts > self.remaining_attempts:
                raise ExecutionBudgetError("EXECUTION_REQUEST_BUDGET_INSUFFICIENT")
            if output_tokens > self.remaining_output_tokens:
                raise ExecutionBudgetError("EXECUTION_OUTPUT_BUDGET_INSUFFICIENT")

    def claim_attempt(self, output_tokens):
        with self._lock:
            self.preflight(1, output_tokens)
            self._requests += 1
            self._reserved += output_tokens
            self._pending = output_tokens
            return self.check()

    def record_output(self, output_tokens):
        with self._lock:
            self.check()
            if (self._pending is None or (output_tokens is not None and (
                    type(output_tokens) is not int or not 0 <= output_tokens <= self._pending))):
                self.fail("EXECUTION_OUTPUT_USAGE_INVALID", ambiguous=True)
                raise ExecutionBudgetError(self._error)
            if output_tokens is None:
                self.fail("EXECUTION_OUTPUT_USAGE_UNAVAILABLE", ambiguous=True)
                raise ExecutionBudgetError(self._error)
            self._reported += output_tokens
            self._pending = None

    def fail(self, code, ambiguous=False):
        with self._lock:
            if not self._error:
                self._error = (code if isinstance(code, str)
                               and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
                               else "EXECUTION_FAILED")
            self._ambiguous = self._ambiguous or bool(ambiguous)
            if self._pending is not None:
                self._unknown_usage += 1
            self._pending = None

    def snapshot(self):
        with self._lock:
            return {"limits": dict(self._limits), "model_requests": self._requests,
                    "output_tokens_reserved": self._reserved,
                    "output_tokens_reported": self._reported,
                    "usage_complete": self._unknown_usage == 0 and self._pending is None,
                    "request_pending": self._pending is not None,
                    "terminal": self._error is not None, "error": self._error,
                    "ambiguous": self._ambiguous,
                    "elapsed_ms": max(0, round((time.monotonic() - self._started) * 1000)),
                    "enforcement_scope": "CLIENT_REQUESTS_ONLY"}


def strict_model_slug(model_id):
    """Resolve one declared open-weight model; never select a runtime fallback."""
    if (not isinstance(model_id, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,191}", model_id)):
        raise ExecutionBudgetError("STRICT_MODEL_ID_REQUIRED")
    try:
        import a11oy_code_engine as engine
        try:
            from szl_substrate import szl_llm_registry as registry
        except ImportError:
            import szl_llm_registry as registry
        entries = [entry for entry in registry.MODEL_REGISTRY
                   if isinstance(entry, dict) and entry.get("model_id") == model_id]
        # This catalog is a static source of explicit model identities, not the
        # legacy transport's automatic fallback sequence.
        entries += [{**entry, "model_slug": entry["id"]}
                    for entry in engine._FALLBACK_ROSTER
                    if isinstance(entry, dict) and entry.get("id") == model_id]
    except (AttributeError, ImportError, TypeError) as exc:
        raise ExecutionBudgetError("STRICT_MODEL_REGISTRY_UNAVAILABLE") from exc
    if len(entries) != 1:
        raise ExecutionBudgetError("STRICT_MODEL_NOT_REGISTERED")
    if not engine._is_open_weight(entries[0]):
        raise ExecutionBudgetError("STRICT_OPEN_WEIGHT_MODEL_REQUIRED")
    slug = entries[0].get("model_slug")
    if (not isinstance(slug, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,191}", slug)
            or any(part.lower() in {"auto", "automatic", "default", "best", "fastest", "cheapest"}
                   for part in slug.split("/"))):
        raise ExecutionBudgetError("STRICT_MODEL_SLUG_INVALID")
    return slug


def strict_governance_admission(governance):
    """A governance allow alone cannot waive a classified route's egress rule."""
    route = governance.get("route") if isinstance(governance, dict) else None
    sensitivity = route.get("sensitivity") if isinstance(route, dict) else None
    if (not isinstance(governance, dict) or governance.get("decision") != "allow"
            or not isinstance(sensitivity, dict)
            or not isinstance(sensitivity.get("class"), str)
            or sensitivity.get("class") not in {"PUBLIC", "INTERNAL"}
            or route.get("airgap_required") is not False):
        raise ExecutionBudgetError("STRICT_GOVERNANCE_EGRESS_DENIED")
    return sensitivity["class"]


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
    # Exact router-source/v1 closure; additions or omissions require review.
    expected_files = {
        "router_control/app.py", "router_control/local_store.py",
        "router_control/verification.py", "router_control/free_tier.py",
        "router_control/static/index.html", "router_control/static/app.js",
        "router_control/static/styles.css", "router_control/static/free-options.js",
        "router_control/static/free-options.css", "router_control/static/szl/szl-tokens.css",
        "router_control/static/szl/szl-icon-32.svg", "router_control/static/szl/SOURCE.json",
        "router_control/static/szl/PROJECTION.json",
    }
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


def _model_plan(client, base, headers, request, expected_upstream_model):
    payload = {key: request[key] for key in ("model", "data_classification", "max_cost_tier")}
    status, value, _ = _read(client, "POST", base + "/api/plan", headers=headers, payload=payload)
    receipt = value.get("receipt")
    body = {key: item for key, item in value.items() if key != "receipt"}
    candidates = value.get("candidates")
    if (status != 200 or value.get("schema") != "szl.router-plan/v1"
            or value.get("model") != request["model"]
            or value.get("classification") != request["data_classification"]
            or value.get("max_cost_tier") != request["max_cost_tier"]
            or value.get("registry_state") != "VALIDATED"
            or value.get("egress_enabled") is not True
            or not isinstance(receipt, dict) or receipt.get("algorithm") != "sha256"
            or receipt.get("digest") != _digest(body)
            or not isinstance(candidates, list) or not candidates):
        raise RouterContractError("ROUTER_MODEL_PLAN_INVALID")
    # Every fallback candidate must serve the same selected model, before any generation.
    for candidate in candidates:
        if (not isinstance(candidate, dict)
                or candidate.get("public_model") != request["model"]
                or candidate.get("upstream_model") != expected_upstream_model
                or candidate.get("classification") != request["data_classification"]
                or type(candidate.get("cost_tier")) is not int
                or not 0 <= candidate["cost_tier"] <= request["max_cost_tier"]
                or not isinstance(candidate.get("provider_id"), str)
                or not _IDENTIFIER.fullmatch(candidate["provider_id"])):
            raise RouterContractError("ROUTER_SELECTED_MODEL_MISMATCH")
    return receipt["digest"], {candidate["provider_id"] for candidate in candidates}


def complete(prompt, *, classification, request_id=None, request_origin="",
             model=None, expected_upstream_model=None, execution_budget=None):
    """One gateway request after governance; the gateway may try provider candidates."""
    evidence = {"state": "UNAVAILABLE", "answer": None, "signature_state": "UNSIGNED",
                "receipt_kind": "HASH_INTEGRITY_ONLY", "http_status": 503}
    if execution_budget is not None:
        # The gateway contract cannot prohibit its provider retries or fallback.
        # A post-response attempt trail cannot establish pre-dispatch admission.
        return {**evidence, "error": "STRICT_ROUTER_TRANSPORT_UNSUPPORTED"}
    try:
        base, token, revision, configured_model = _configuration(request_origin)
        model = configured_model if model is None else model
        if not isinstance(model, str) or not _IDENTIFIER.fullmatch(model):
            raise RouterContractError("INVALID_ROUTER_MODEL")
        if expected_upstream_model is not None and (
                not isinstance(expected_upstream_model, str)
                or not _IDENTIFIER.fullmatch(expected_upstream_model)):
            raise RouterContractError("INVALID_ROUTER_EXPECTED_MODEL")
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
            # Match ChatRequest's normalized default while hashing the exact request.
            "max_cost_tier": 0, "required_provider_id": None,
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
            plan_digest, plan_providers = None, set()
            if expected_upstream_model is not None:
                plan_digest, plan_providers = _model_plan(client, base, headers, request, expected_upstream_model)
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
            if expected_upstream_model is not None and (
                    receipt.get("upstream_model") != expected_upstream_model
                    or receipt.get("provider_id") not in plan_providers
                    or receipt.get("plan_digest") != plan_digest):
                raise RouterContractError("ROUTER_SELECTED_MODEL_MISMATCH")
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
