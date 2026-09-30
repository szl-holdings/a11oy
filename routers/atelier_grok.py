#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Authenticated single-turn inference; services/governance/provenance taxonomy.

The canonical doctrine gate evaluates text without emitting its preview receipt.
This route retains signed metadata only. Its process lock serializes a bounded,
rotating receipt chain; it supplies neither conversation replay nor distributed
coordination. Provider reasoning ciphertext is never returned or stored. Content
hashes are integrity metadata, not anonymization or a prompt-privacy guarantee.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

import a11oy_vertical_feeds
import gdw_auth
import szl_dsse
import szl_governance_gateway
import szl_provider_http
from szl_durable_ledger import DurableStore, OK, PRESSURE


PREFIX = "/api/a11oy/v1/atelier"
DEFAULT_MODEL = "grok-4.7"
ALLOWED_MODELS = (DEFAULT_MODEL, "grok-4.6")
PROVIDER_URL = "https://api.x.ai/v1/responses"
MAX_BODY_BYTES = 140_000
RECEIPT_SCHEMA = "a11oy.atelier.single-turn.receipt/v1"
PAYLOAD_TYPE = "application/vnd.szl.atelier-turn+json"
CHAIN_SCOPE = "SINGLE_PROCESS_RETAINED_METADATA_CHAIN"
CONTINUITY = "SINGLE_TURN_NO_SERVER_TEXT_HISTORY"
_TURN_LOCK = threading.Lock()
_SAFE_PROVIDER_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    prompt: str = Field(min_length=1, max_length=32_768)
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "high"
    model: Optional[str] = Field(default=None, max_length=80)
    declared: Literal["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"] = "PUBLIC"
    max_output_tokens: int = Field(default=4096, ge=1, le=4096)

    @field_validator("prompt")
    @classmethod
    def nonblank_prompt(cls, value):
        if not value.strip():
            raise ValueError("prompt is empty")
        return value


class AtelierFailure(Exception):
    def __init__(self, code, status=503, state="UNAVAILABLE"):
        self.code, self.status, self.state = code, status, state
        super().__init__(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _error(failure, **extra):
    return JSONResponse(
        {"state": failure.state, "code": failure.code, "retry_safe": False, **extra},
        status_code=failure.status,
        headers={"Cache-Control": "no-store"},
    )


def _namespace():
    return os.environ.get("A11OY_ATELIER_NAMESPACE", "a11oy").strip()


def _registry():
    raw = os.environ.get("A11OY_ATELIER_CREDENTIALS_JSON")
    try:
        return gdw_auth.load_credential_registry(raw)
    except gdw_auth.AuthConfigurationError:
        raise AtelierFailure("CREDENTIALS_UNAVAILABLE") from None


def _authenticate(request):
    registry = _registry()
    try:
        return gdw_auth.authenticate_bearer(
            request.headers.get("authorization"), registry,
            namespace=_namespace(), required_scopes=("atelier:write",),
        )
    except gdw_auth.AuthConfigurationError:
        raise AtelierFailure("CREDENTIALS_UNAVAILABLE") from None
    except gdw_auth.AuthenticationError as exc:
        forbidden = exc.code in {"credential_revoked", "foreign_namespace", "missing_scopes"}
        raise AtelierFailure("AUTH_FORBIDDEN" if forbidden else "AUTH_REQUIRED",
                             403 if forbidden else 401, "DENIED") from None


def _selected_model(request_model=None):
    if request_model is not None:
        selected = request_model.strip()
    else:
        selected = (os.environ.get("SZL_GROK_MODEL", "").strip()
                    or os.environ.get("A11OY_ATELIER_MODEL", "").strip()
                    or DEFAULT_MODEL)
    if selected not in ALLOWED_MODELS:
        raise AtelierFailure("MODEL_NOT_ALLOWED", 400, "DENIED")
    return selected


def _provider_key():
    return (os.environ.get("A11OY_ATELIER_XAI_API_KEY", "").strip()
            or os.environ.get("XAI_API_KEY", "").strip())


def _ledger_path():
    raw = os.environ.get("A11OY_ATELIER_LEDGER_PATH", "").strip()
    path = Path(raw)
    if (not raw or not path.is_absolute() or path == Path(path.anchor)
            or path.is_dir() or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)):
        raise AtelierFailure("LEDGER_UNAVAILABLE")
    return str(path)


def health():
    blockers = []
    configured = {"credentials": False, "provider": bool(_provider_key()),
                  "signer": False, "ledger": False}
    try:
        registry = _registry()
        # The public helper validates namespace before rejecting the absent header.
        # It performs no credential scan, provider call, signing or ledger write.
        try:
            gdw_auth.authenticate_bearer(None, registry, namespace=_namespace())
        except gdw_auth.AuthenticationError:
            parsed = json.loads(os.environ["A11OY_ATELIER_CREDENTIALS_JSON"])
            configured["credentials"] = any(
                row["namespace"] == _namespace() and not row.get("revoked", False)
                and "atelier:write" in row["scopes"] for row in parsed["credentials"])
    except (AtelierFailure, gdw_auth.AuthConfigurationError, KeyError):
        pass
    try:
        configured["signer"] = szl_dsse.signing_available() is True
    except Exception:
        pass
    try:
        _ledger_path()
        configured["ledger"] = True
    except (AtelierFailure, OSError, ValueError):
        pass
    for key, code in (("credentials", "CREDENTIALS_UNAVAILABLE"),
                      ("provider", "PROVIDER_UNAVAILABLE"),
                      ("signer", "SIGNER_UNAVAILABLE"), ("ledger", "LEDGER_UNAVAILABLE")):
        if not configured[key]:
            blockers.append(code)
    try:
        model = _selected_model()
    except AtelierFailure:
        model = None
        blockers.append("MODEL_NOT_ALLOWED")
    revision = os.environ.get("SZL_GIT_SHA", "")
    revision = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None
    return {"ready": not blockers, "model": model, "inference_verified": False,
            "blockers": blockers, "configured": configured, "source_revision": revision,
            "continuity": CONTINUITY, "provider": "xai",
            "chain_scope": CHAIN_SCOPE, "energy": {"label": "UNAVAILABLE", "joules": None}}


def _validated_envelope(payload, envelope):
    try:
        embedded = json.loads(base64.b64decode(envelope["payload"], validate=True))
        return (envelope.get("signed") is True and embedded == payload
                and envelope.get("payloadType") == PAYLOAD_TYPE
                and szl_dsse.verify_envelope(envelope).get("verified") is True)
    except Exception:
        return False


def _retained_records(store):
    # DurableStore.iter_records intentionally skips unreadable segments. A signed
    # decision chain must fail closed rather than silently append a new genesis.
    try:
        for number in range(store.backup_count, -1, -1):
            segment = Path(store.path if number == 0 else f"{store.path}.{number}")
            if segment.is_symlink():
                raise AtelierFailure("LEDGER_INTEGRITY_UNAVAILABLE")
            if not segment.exists():
                continue
            with segment.open("r", encoding="utf-8") as retained:
                for line in retained:
                    if line.strip():
                        yield json.loads(line)
    except (OSError, UnicodeError, ValueError):
        raise AtelierFailure("LEDGER_INTEGRITY_UNAVAILABLE") from None


def _retained_head(store, principal):
    latest = None
    for record in _retained_records(store):
        if not isinstance(record, dict) or record.get("schema") != RECEIPT_SCHEMA:
            raise AtelierFailure("LEDGER_INTEGRITY_UNAVAILABLE")
        payload = record.get("payload", {})
        if (not isinstance(payload, dict) or type(payload.get("sequence")) is not int
                or payload["sequence"] < 1 or record.get("digest") != _digest(payload)
                or not _validated_envelope(payload, record.get("dsse", {}))):
            raise AtelierFailure("LEDGER_INTEGRITY_UNAVAILABLE")
        if payload.get("owner_id") != principal.owner_id or payload.get("namespace") != principal.namespace:
            continue
        if latest and (payload.get("prior_hash") != latest["digest"]
                       or payload.get("sequence") != latest["payload"]["sequence"] + 1):
            raise AtelierFailure("LEDGER_INTEGRITY_UNAVAILABLE")
        latest = record
    return latest


@contextmanager
def _exclusive_turn():
    if not _TURN_LOCK.acquire(blocking=False):
        raise AtelierFailure("ATELIER_BUSY", 409)
    try:
        yield
    finally:
        _TURN_LOCK.release()


def _append(store, principal, metadata):
    previous = _retained_head(store, principal)
    payload = {"schema": RECEIPT_SCHEMA, "owner_id": principal.owner_id,
               "namespace": principal.namespace, "key_id": principal.key_id,
               "prior_hash": previous["digest"] if previous else None,
               "sequence": previous["payload"]["sequence"] + 1 if previous else 1,
               "at_utc": datetime.now(timezone.utc).isoformat(), **metadata}
    envelope = szl_dsse.sign_payload(payload, payload_type=PAYLOAD_TYPE)
    if not _validated_envelope(payload, envelope):
        raise AtelierFailure("SIGNATURE_UNAVAILABLE")
    digest = _digest(payload)
    record = {"schema": RECEIPT_SCHEMA, "payload": payload, "digest": digest, "dsse": envelope}
    if store.append(record).ok is not True:
        raise AtelierFailure("LEDGER_WRITE_FAILED")
    return {"payload": payload, "digest": digest, "persisted": True,
            "signature_verified": True, "chain_scope": CHAIN_SCOPE}, envelope


def _final_output(document, model):
    if not isinstance(document, dict) or document.get("model") != model or document.get("status") != "completed":
        raise AtelierFailure("PROVIDER_INVALID_RESPONSE", 502)
    output = document.get("output")
    if not isinstance(output, list):
        raise AtelierFailure("PROVIDER_INVALID_RESPONSE", 502)
    parts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message" or item.get("role") != "assistant":
            continue
        if item.get("status", "completed") != "completed":
            raise AtelierFailure("PROVIDER_INVALID_RESPONSE", 502)
        contents = item.get("content")
        if not isinstance(contents, list):
            raise AtelierFailure("PROVIDER_INVALID_RESPONSE", 502)
        for content in contents:
            if isinstance(content, dict) and content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    answer = "\n".join(parts)
    if not answer.strip() or len(answer) > 32_768:
        raise AtelierFailure("PROVIDER_INVALID_RESPONSE", 502)
    usage = document.get("usage") or {}
    usage = {key: value for key in ("input_tokens", "output_tokens", "total_tokens")
             if isinstance(usage, dict) and type(value := usage.get(key)) is int and 0 <= value <= 10_000_000}
    provider_id = document.get("id")
    provider_id = provider_id if isinstance(provider_id, str) and _SAFE_PROVIDER_ID.fullmatch(provider_id) else None
    return answer, usage, provider_id


def _provider_failure(code):
    if isinstance(code, str) and re.fullmatch(r"HTTP_STATUS:[1-5][0-9]{2}", code):
        status = int(code.split(":")[1])
        return AtelierFailure(f"PROVIDER_HTTP_{status}", status if status in {401, 402, 403, 429} else 502)
    return AtelierFailure("PROVIDER_TIMEOUT" if code == "TIMEOUT" else "PROVIDER_UNAVAILABLE",
                          504 if code == "TIMEOUT" else 502)


def _execute(principal, turn):
    model = _selected_model(turn.model)
    api_key = _provider_key()
    if not api_key:
        raise AtelierFailure("PROVIDER_UNAVAILABLE")
    if szl_dsse.signing_available() is not True:
        raise AtelierFailure("SIGNER_UNAVAILABLE")
    path = _ledger_path()
    request_id = str(uuid4())
    with _exclusive_turn():
        store = DurableStore(path, fsync=True)
        if store.status().get("status") not in {OK, PRESSURE}:
            raise AtelierFailure("LEDGER_UNAVAILABLE")
        classification = szl_governance_gateway.classify(turn.prompt, turn.declared)
        policy = a11oy_vertical_feeds.governed_turn(
            "atelier", turn.prompt, declared=turn.declared, action_kind="inference",
            actor={"owner_id": principal.owner_id, "namespace": principal.namespace,
                   "key_id": principal.key_id}, emit_receipt=False,
        )
        allowed = (classification.get("class") in {"PUBLIC", "INTERNAL"}
                   and policy.get("decision") == "allow")
        metadata = {"request_id": request_id, "provider": "xai", "model": model,
                    "prompt_sha256": hashlib.sha256(turn.prompt.encode()).hexdigest(),
                    "classification": classification.get("class"),
                    "reasoning_effort": turn.reasoning_effort,
                    "max_output_tokens": turn.max_output_tokens,
                    "source_revision": health()["source_revision"],
                    "continuity": CONTINUITY, "retry_safe": False}
        decision_receipt, decision_dsse = _append(
            store, principal, {**metadata, "phase": "DECISION",
                               "decision": "ALLOW" if allowed else "DENY",
                               "policy_decision": policy.get("decision")})
        if not allowed:
            return _error(AtelierFailure("POLICY_DENIED", 403, "DENIED"),
                          request_id=request_id, receipt=decision_receipt, dsse=decision_dsse)
        body = _canonical({"model": model, "input": [{"role": "user", "content": turn.prompt}],
                           "reasoning": {"effort": turn.reasoning_effort}, "store": False,
                           "max_output_tokens": turn.max_output_tokens, "tools": []})
        started = time.monotonic()
        try:
            document, code = szl_provider_http.http_json(
                PROVIDER_URL, method="POST", body=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=120.0, max_response_bytes=1_048_576, max_redirects=0, allow_private=False,
            )
            if code:
                raise _provider_failure(code)
            answer, usage, provider_id = _final_output(document, model)
        except AtelierFailure as failure:
            receipt, dsse = _append(store, principal, {**metadata, "phase": "OUTCOME",
                "decision_receipt_hash": decision_receipt["digest"], "state": "UNAVAILABLE",
                "code": failure.code, "provider_outcome_uncertain": failure.code not in {
                    "PROVIDER_HTTP_401", "PROVIDER_HTTP_402", "PROVIDER_HTTP_403", "PROVIDER_HTTP_429"}})
            return _error(failure, request_id=request_id, receipt=receipt, dsse=dsse)
        except Exception:
            receipt, dsse = _append(store, principal, {**metadata, "phase": "OUTCOME",
                "decision_receipt_hash": decision_receipt["digest"], "state": "UNAVAILABLE",
                "code": "PROVIDER_UNAVAILABLE", "provider_outcome_uncertain": True})
            return _error(AtelierFailure("PROVIDER_UNAVAILABLE", 502),
                          request_id=request_id, receipt=receipt, dsse=dsse)
        receipt, dsse = _append(store, principal, {**metadata, "phase": "OUTCOME",
            "decision_receipt_hash": decision_receipt["digest"], "state": "COMPLETED",
            "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "provider_request_id": provider_id, "usage": usage,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "energy": {"label": "UNAVAILABLE", "joules": None}})
        return JSONResponse({"state": "COMPLETED", "answer": answer, "model": model,
            "request_id": request_id, "receipt": receipt, "dsse": dsse,
            "energy": {"label": "UNAVAILABLE", "joules": None}, "retry_safe": False},
            headers={"Cache-Control": "no-store"})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def register(app: FastAPI):
    paths = {f"{PREFIX}/health", f"{PREFIX}/turn"}
    existing = [route for route in app.router.routes if getattr(route, "path", None) in paths]
    if existing:
        if (len(existing) == 2 and {route.path for route in existing} == paths
                and all(getattr(route.endpoint, "__module__", None) == __name__ for route in existing)):
            return {"state": "ALREADY_REGISTERED", "routes": sorted(paths)}
        raise RuntimeError("ATELIER_ROUTE_COLLISION")
    before = len(app.router.routes)

    @app.api_route(f"{PREFIX}/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def atelier_health(request: Request):
        result = health()
        if request.method == "HEAD":
            return Response(status_code=200, headers={"Cache-Control": "no-store"})
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.post(f"{PREFIX}/turn", include_in_schema=False)
    async def atelier_turn(request: Request):
        try:
            principal = _authenticate(request)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > MAX_BODY_BYTES:
                    raise AtelierFailure("REQUEST_TOO_LARGE", 413, "DENIED")
            try:
                data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
                turn = TurnRequest.model_validate(data)
            except (UnicodeDecodeError, ValueError, ValidationError):
                raise AtelierFailure("INVALID_REQUEST", 422, "DENIED") from None
            return await anyio.to_thread.run_sync(_execute, principal, turn)
        except AtelierFailure as failure:
            return _error(failure)
        except Exception:
            return _error(AtelierFailure("ATELIER_UNAVAILABLE"))

    added = app.router.routes[before:]
    del app.router.routes[before:]
    app.router.routes[0:0] = added
    return {"state": "REGISTERED", "routes": sorted(paths)}
