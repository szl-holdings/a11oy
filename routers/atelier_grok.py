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
from urllib.parse import urlsplit
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
LOCAL_URL_ENV = "A11OY_ATELIER_LOCAL_URL"
LOCAL_MODEL_ENV = "A11OY_ATELIER_LOCAL_MODEL"
LOCAL_MODEL_DIGEST_ENV = "A11OY_ATELIER_LOCAL_MODEL_DIGEST"
LOCAL_PROVIDER = "local_ollama"
LOCAL_MODE = "NO_KEY_LOCAL"
LOCAL_TAGS_TIMEOUT_S = 10.0
CPU_LAB_PROVIDER = "szl_cpu_lab"
CPU_LAB_MODE = "NO_PROVIDER_KEY_PUBLIC_CPU_LAB"
CPU_LAB_ORIGIN = "https://szlholdings-szl-model-inference-lab.hf.space"
CPU_LAB_IDENTITY_URL = f"{CPU_LAB_ORIGIN}/api/v1/identity"
CPU_LAB_CHAT_URL = f"{CPU_LAB_ORIGIN}/v1/chat/completions"
CPU_LAB_SPACE = "SZLHOLDINGS/szl-model-inference-lab"
CPU_LAB_MODEL_REPO = "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
CPU_LAB_MODEL_REVISION = "67d60ec577730747055491640cfb91fc4a4b5d25"
CPU_LAB_MODEL = f"{CPU_LAB_MODEL_REPO}@{CPU_LAB_MODEL_REVISION}"
CPU_LAB_MODEL_FILE = "SZL-Khipu-1.5B-Q4_K_M.gguf"
CPU_LAB_MODEL_SHA256 = "13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a"
CPU_LAB_RELEASE_ID = "brain13-1d3960c-controller-9f227f6"
CPU_LAB_RELEASE_MANIFEST_SHA256 = "a2b488cc635e86e395218c78a7562a6b5f5879463d2e2d988c879e0cf98ae849"
CPU_LAB_MAX_BODY_BYTES = 8192
CPU_LAB_MAX_INPUT_CHARS = 1200
CPU_LAB_MAX_OUTPUT_TOKENS = 32
CPU_LAB_RESERVED_TOKENS = ("<|im_start|>", "<|im_end|>", "<|endoftext|>")
# Defense in depth for familiar credential shapes, not comprehensive DLP.
CPU_LAB_KNOWN_SECRET_PATTERNS = (
    re.compile(r"\b(?:xai-[A-Za-z0-9_-]{16,}|hf_[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9_-]{16,})\b", re.I),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.I),
    re.compile(r"\bAuthorization\s*:?\s*Bearer\b", re.I),
)
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


class LocalTurnRequest(BaseModel):
    """Local inference has no xAI model or reasoning-effort override."""

    model_config = ConfigDict(extra="forbid", strict=True)
    prompt: str = Field(min_length=1, max_length=32_768)
    declared: Literal["PUBLIC", "INTERNAL", "RESTRICTED", "SECRET"] = "PUBLIC"
    max_output_tokens: int = Field(default=4096, ge=1, le=4096)

    @field_validator("prompt")
    @classmethod
    def nonblank_prompt(cls, value):
        if not value.strip():
            raise ValueError("prompt is empty")
        return value


class CpuLabTurnRequest(BaseModel):
    """Public-only, exact-text subset of the pinned CPU lab's chat contract."""

    model_config = ConfigDict(extra="forbid", strict=True)
    prompt: str = Field(min_length=1, max_length=CPU_LAB_MAX_INPUT_CHARS)
    declared: Literal["PUBLIC"] = "PUBLIC"
    max_output_tokens: int = Field(default=24, ge=1, le=CPU_LAB_MAX_OUTPUT_TOKENS)
    public_share_acknowledged: Literal[True]

    @field_validator("public_share_acknowledged", mode="before")
    @classmethod
    def exact_public_acknowledgement(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("public disclosure acknowledgement is required")
        return value

    @field_validator("prompt")
    @classmethod
    def exact_public_prompt(cls, value):
        # The lab strips each message. Reject input it would silently change.
        if (not value.strip() or value != value.strip() or "\x00" in value
                or any(token in value for token in CPU_LAB_RESERVED_TOKENS)
                or any(pattern.search(value) for pattern in CPU_LAB_KNOWN_SECRET_PATTERNS)):
            raise ValueError("prompt is not accepted unchanged by CPU lab")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("prompt is not UTF-8 encodable") from None
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


def _local_url():
    """Accept only an explicit loopback Ollama chat endpoint."""
    raw = os.environ.get(LOCAL_URL_ENV, "").strip()
    try:
        parts = urlsplit(raw)
        valid = (parts.scheme == "http" and parts.hostname in {"127.0.0.1", "::1"}
                 and parts.port is not None and 1 <= parts.port <= 65535
                 and parts.path == "/api/chat" and "?" not in raw and "#" not in raw
                 and not parts.query
                 and not parts.fragment and parts.username is None and parts.password is None
                 and not any(ord(ch) < 33 or ord(ch) == 127 for ch in raw))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise AtelierFailure("LOCAL_ENDPOINT_UNAVAILABLE")
    return raw


def _local_model():
    model = os.environ.get(LOCAL_MODEL_ENV, "").strip()
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}", model)
            or "grok" in model.lower()):
        raise AtelierFailure("LOCAL_MODEL_UNAVAILABLE")
    return model


def _local_model_digest():
    digest = os.environ.get(LOCAL_MODEL_DIGEST_ENV, "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise AtelierFailure("LOCAL_MODEL_DIGEST_UNAVAILABLE")
    return digest


def _ledger_path():
    raw = os.environ.get("A11OY_ATELIER_LEDGER_PATH", "").strip()
    path = Path(raw)
    if (not raw or not path.is_absolute() or path == Path(path.anchor)
            or path.is_dir() or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)):
        raise AtelierFailure("LEDGER_UNAVAILABLE")
    required = os.environ.get("A11OY_ATELIER_REQUIRED_MOUNT", "").strip()
    if required:
        mount = Path(required)
        if (not mount.is_absolute() or mount == Path(mount.anchor)
                or mount.is_symlink() or not os.path.ismount(str(mount))):
            raise AtelierFailure("LEDGER_UNAVAILABLE")
        try:
            path.resolve(strict=False).relative_to(mount.resolve(strict=True))
        except (OSError, ValueError):
            raise AtelierFailure("LEDGER_UNAVAILABLE") from None
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


def local_health():
    """Configuration only: a GET cannot prove a model call or mint a receipt."""
    blockers = []
    configured = {"credentials": False, "endpoint": False, "model": False,
                  "model_digest": False,
                  "signer": False, "ledger": False}
    try:
        registry = _registry()
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
        _local_url()
        configured["endpoint"] = True
    except AtelierFailure:
        pass
    try:
        model = _local_model()
        configured["model"] = True
    except AtelierFailure:
        model = None
    try:
        _local_model_digest()
        configured["model_digest"] = True
    except AtelierFailure:
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
                      ("endpoint", "LOCAL_ENDPOINT_UNAVAILABLE"),
                      ("model", "LOCAL_MODEL_UNAVAILABLE"),
                      ("model_digest", "LOCAL_MODEL_DIGEST_UNAVAILABLE"),
                      ("signer", "SIGNER_UNAVAILABLE"), ("ledger", "LEDGER_UNAVAILABLE")):
        if not configured[key]:
            blockers.append(code)
    revision = os.environ.get("SZL_GIT_SHA", "")
    revision = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None
    return {"ready": not blockers, "model": model, "inference_verified": False,
            "blockers": blockers, "configured": configured, "source_revision": revision,
            "continuity": CONTINUITY, "provider": LOCAL_PROVIDER, "mode": LOCAL_MODE,
            "chain_scope": CHAIN_SCOPE, "energy": {"label": "UNAVAILABLE", "joules": None}}


def cpu_lab_health():
    """Local prerequisites only; no remote probe, receipt, or durability claim."""
    configured = {"credentials": False, "signer": False,
                  "ledger_path_configured": False}
    try:
        registry = _registry()
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
        configured["ledger_path_configured"] = True
    except (AtelierFailure, OSError, ValueError):
        pass
    blockers = [code for key, code in (
        ("credentials", "CREDENTIALS_UNAVAILABLE"),
        ("signer", "SIGNER_UNAVAILABLE"),
        ("ledger_path_configured", "LEDGER_UNAVAILABLE"),
    ) if not configured[key]]
    revision = os.environ.get("SZL_GIT_SHA", "")
    revision = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None
    return {"ready": not blockers,
            "ready_scope": "LOCAL_PREREQUISITES_ONLY",
            "model": CPU_LAB_MODEL if not blockers else None,
            "inference_verified": False, "blockers": blockers,
            "configured": configured, "source_revision": revision,
            "continuity": CONTINUITY, "provider": CPU_LAB_PROVIDER,
            "mode": CPU_LAB_MODE, "chain_scope": CHAIN_SCOPE,
            "provider_identity_verified": False,
            "ledger_durability_verified": False,
            "output_signature_status": "UNSIGNED",
            "energy": {"label": "UNAVAILABLE", "joules": None}}


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


def _local_output(document, model):
    """Read one final assistant message; never expose model-private fields."""
    if (not isinstance(document, dict) or document.get("model") != model
            or document.get("done") is not True
            or document.get("done_reason") != "stop"):
        raise AtelierFailure("LOCAL_INVALID_RESPONSE", 502)
    message = document.get("message")
    if (not isinstance(message, dict) or message.get("role") != "assistant"
            or message.get("tool_calls") or not isinstance(message.get("content"), str)):
        raise AtelierFailure("LOCAL_INVALID_RESPONSE", 502)
    answer = message["content"]
    if not answer.strip() or len(answer) > 32_768:
        raise AtelierFailure("LOCAL_INVALID_RESPONSE", 502)
    usage = {key: value for key in ("prompt_eval_count", "eval_count")
             if type(value := document.get(key)) is int and 0 <= value <= 10_000_000}
    return answer, usage


def _local_failure(code):
    return AtelierFailure("LOCAL_TIMEOUT" if code == "TIMEOUT" else "LOCAL_UNAVAILABLE",
                          504 if code == "TIMEOUT" else 502)


def _local_observed_digest(url, model):
    """Read the exact tag's current digest; this does not pin execution bytes."""
    tags_url = url[: -len("/api/chat")] + "/api/tags"
    try:
        document, code = szl_provider_http.http_json(
            tags_url, method="GET", timeout=LOCAL_TAGS_TIMEOUT_S, max_response_bytes=1_048_576,
            max_redirects=0, allow_private=True,
        )
    except Exception:
        raise AtelierFailure("LOCAL_MODEL_DIGEST_UNAVAILABLE") from None
    if code or not isinstance(document, dict) or not isinstance(document.get("models"), list):
        raise AtelierFailure("LOCAL_MODEL_DIGEST_UNAVAILABLE")
    matches = [row for row in document["models"]
               if isinstance(row, dict) and row.get("name") == model]
    if len(matches) != 1:
        raise AtelierFailure("LOCAL_MODEL_DIGEST_UNAVAILABLE")
    observed = matches[0].get("digest")
    if not isinstance(observed, str) or not re.fullmatch(r"[0-9a-f]{64}", observed):
        raise AtelierFailure("LOCAL_MODEL_DIGEST_UNAVAILABLE")
    return observed


def _cpu_lab_identity():
    """Observe the pinned public lab release; this is not remote attestation."""
    try:
        document, code = szl_provider_http.http_json(
            CPU_LAB_IDENTITY_URL, method="GET", timeout=4.0,
            max_response_bytes=16_384, max_redirects=0, allow_private=False,
        )
    except Exception:
        raise AtelierFailure("CPU_LAB_IDENTITY_UNAVAILABLE") from None
    if code or not isinstance(document, dict):
        raise AtelierFailure("CPU_LAB_IDENTITY_UNAVAILABLE")
    space, model, runtime = (document.get(key) for key in ("space", "model", "runtime"))
    if not all(isinstance(value, dict) for value in (space, model, runtime)):
        raise AtelierFailure("CPU_LAB_IDENTITY_MISMATCH")
    contract = runtime.get("openai_compatible_subset")
    if (document.get("status") != "READY"
            or space.get("id") != CPU_LAB_SPACE
            or space.get("release_id") != CPU_LAB_RELEASE_ID
            or space.get("release_manifest_sha256") != CPU_LAB_RELEASE_MANIFEST_SHA256
            or space.get("source_integrity") is not True
            or model.get("repo") != CPU_LAB_MODEL_REPO
            or model.get("revision") != CPU_LAB_MODEL_REVISION
            or model.get("file") != CPU_LAB_MODEL_FILE
            or model.get("sha256_expected") != CPU_LAB_MODEL_SHA256
            or model.get("sha256_loaded") != CPU_LAB_MODEL_SHA256
            or runtime.get("max_input_chars") != CPU_LAB_MAX_INPUT_CHARS
            or runtime.get("max_formatted_prompt_tokens") != 800
            or runtime.get("max_new_tokens") != CPU_LAB_MAX_OUTPUT_TOKENS
            or runtime.get("max_request_body_bytes") != CPU_LAB_MAX_BODY_BYTES
            or not isinstance(contract, dict)
            or contract.get("chat_completions") != "POST /v1/chat/completions"
            or contract.get("model_id") != CPU_LAB_MODEL
            or contract.get("streaming") is not False):
        raise AtelierFailure("CPU_LAB_IDENTITY_MISMATCH")
    return {"model_digest_observed_before_call": model["sha256_loaded"],
            "release_id_observed_before_call": space["release_id"],
            "release_manifest_observed_before_call": space["release_manifest_sha256"]}


def _cpu_lab_json_digest(value):
    """The lab's documented canonical JSON is UTF-8, sorted and compact."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _cpu_lab_request(turn):
    messages = [{"role": "user", "content": turn.prompt}]
    body = _canonical({"model": CPU_LAB_MODEL, "messages": messages,
                       "max_completion_tokens": turn.max_output_tokens,
                       "temperature": 0.0, "top_p": 1.0, "n": 1, "stream": False})
    canonical_request = {"schema": "szl.openai-chat-request/v1",
                         "model": CPU_LAB_MODEL, "messages": messages,
                         "max_completion_tokens": turn.max_output_tokens,
                         "temperature": 0.0, "top_p": 1.0, "n": 1,
                         "stream": False, "tools": None}
    return body, _cpu_lab_json_digest(canonical_request)


def _cpu_lab_output(document, expected_request_hash):
    """Validate the exact unsigned lab subset and return only public answer text."""
    if (not isinstance(document, dict) or document.get("object") != "chat.completion"
            or document.get("model") != CPU_LAB_MODEL
            or not isinstance(document.get("id"), str)
            or not _SAFE_PROVIDER_ID.fullmatch(document["id"])
            or type(document.get("created")) is not int or document["created"] < 0):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    choices = document.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    choice = choices[0]
    if (not isinstance(choice, dict) or type(choice.get("index")) is not int
            or choice["index"] != 0 or choice.get("finish_reason") != "stop"):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    message = choice.get("message")
    if (not isinstance(message, dict) or message.get("role") != "assistant"
            or message.get("tool_calls") or not isinstance(message.get("content"), str)):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    answer = message["content"]
    if not answer.strip() or len(answer) > 4096:
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    usage = document.get("usage")
    if not isinstance(usage, dict):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    prompt_tokens, completion_tokens, total_tokens = (
        usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    if (type(prompt_tokens) is not int or not 0 <= prompt_tokens <= 800
            or type(completion_tokens) is not int
            or not 1 <= completion_tokens <= CPU_LAB_MAX_OUTPUT_TOKENS
            or type(total_tokens) is not int
            or total_tokens != prompt_tokens + completion_tokens):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    provenance = document.get("szl_provenance")
    if not isinstance(provenance, dict):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    model, runtime, receipts, output = (
        provenance.get(key) for key in ("model", "runtime", "receipts", "output"))
    expected_model = {"repo": CPU_LAB_MODEL_REPO,
                      "revision": CPU_LAB_MODEL_REVISION,
                      "file": CPU_LAB_MODEL_FILE, "sha256": CPU_LAB_MODEL_SHA256}
    if (provenance.get("schema") != "szl.openai-compat-provenance/v1"
            or model != expected_model or not isinstance(runtime, dict)
            or runtime.get("space") != CPU_LAB_SPACE
            or runtime.get("release_id") != CPU_LAB_RELEASE_ID
            or runtime.get("service_level") != "BEST_EFFORT_NO_SLA"
            or not isinstance(receipts, dict)
            or receipts.get("covers_this_output") is not False
            or not isinstance(output, dict)
            or output.get("signature_status") != "UNSIGNED"
            or output.get("signature") is not None
            or output.get("termination_reason") != "stop"):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    record = provenance.get("execution_record")
    if not isinstance(record, dict):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    record_model = {"id": CPU_LAB_MODEL, **expected_model}
    source, termination = record.get("source"), record.get("termination")
    record_hash = record.get("record_sha256")
    if (record.get("schema") != "szl.unsigned-execution-record/v1"
            or record.get("request_id") != document["id"]
            or record.get("created_unix") != document["created"]
            or record.get("canonical_request_sha256") != expected_request_hash
            or record.get("output_sha256") != hashlib.sha256(answer.encode()).hexdigest()
            or record.get("model") != record_model
            or not isinstance(source, dict)
            or source.get("space_id") != CPU_LAB_SPACE
            or source.get("release_id") != CPU_LAB_RELEASE_ID
            or source.get("release_manifest_sha256") != CPU_LAB_RELEASE_MANIFEST_SHA256
            or record.get("usage") != {"prompt_tokens": prompt_tokens,
                                       "completion_tokens": completion_tokens,
                                       "total_tokens": total_tokens}
            or not isinstance(termination, dict)
            or termination.get("reason") != "stop"
            or termination.get("time_budget_reached") is not False
            or record.get("signature_status") != "UNSIGNED"
            or record.get("signature") is not None
            or record.get("authenticity_not_established") is not True
            or not isinstance(record_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", record_hash)
            or record_hash != _cpu_lab_json_digest({key: value for key, value in record.items()
                                                     if key != "record_sha256"})):
        raise AtelierFailure("CPU_LAB_INVALID_RESPONSE", 502)
    return answer, {"prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens}, document["id"], record_hash


def _cpu_lab_failure(code):
    if code == "TIMEOUT":
        return AtelierFailure("CPU_LAB_TIMEOUT", 504)
    return AtelierFailure("CPU_LAB_UNAVAILABLE", 502)


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


def _execute_local(principal, turn):
    url = _local_url()
    model = _local_model()
    expected_digest = _local_model_digest()
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
        metadata = {"request_id": request_id, "provider": LOCAL_PROVIDER,
                    "mode": LOCAL_MODE, "model": model,
                    "model_digest_expected": expected_digest,
                    "prompt_sha256": hashlib.sha256(turn.prompt.encode()).hexdigest(),
                    "classification": classification.get("class"),
                    "max_output_tokens": turn.max_output_tokens,
                    "source_revision": local_health()["source_revision"],
                    "continuity": CONTINUITY, "retry_safe": False}
        decision_receipt, decision_dsse = _append(
            store, principal, {**metadata, "phase": "DECISION",
                               "decision": "ALLOW" if allowed else "DENY",
                               "policy_decision": policy.get("decision")})
        if not allowed:
            return _error(AtelierFailure("POLICY_DENIED", 403, "DENIED"),
                          request_id=request_id, receipt=decision_receipt, dsse=decision_dsse)
        observed_digest = None
        try:
            observed_digest = _local_observed_digest(url, model)
            if observed_digest != expected_digest:
                raise AtelierFailure("LOCAL_MODEL_DIGEST_MISMATCH")
        except AtelierFailure as failure:
            observed = ({"model_digest_observed_before_call": observed_digest}
                        if observed_digest is not None else {})
            receipt, dsse = _append(store, principal, {**metadata, **observed,
                "phase": "OUTCOME", "decision_receipt_hash": decision_receipt["digest"],
                "state": "UNAVAILABLE", "code": failure.code,
                "provider_outcome_uncertain": False})
            return _error(failure, request_id=request_id, receipt=receipt, dsse=dsse)
        body = _canonical({"model": model,
                           "messages": [{"role": "user", "content": turn.prompt}],
                           "stream": False, "truncate": False,
                           "options": {"num_predict": turn.max_output_tokens}})
        started = time.monotonic()
        try:
            document, code = szl_provider_http.http_json(
                url, method="POST", body=body,
                headers={"Content-Type": "application/json"},
                timeout=120.0, max_response_bytes=1_048_576, max_redirects=0,
                allow_private=True,
            )
            if code:
                raise _local_failure(code)
            answer, usage = _local_output(document, model)
        except AtelierFailure as failure:
            receipt, dsse = _append(store, principal, {**metadata,
                "model_digest_observed_before_call": observed_digest, "phase": "OUTCOME",
                "decision_receipt_hash": decision_receipt["digest"], "state": "UNAVAILABLE",
                "code": failure.code, "provider_outcome_uncertain": True})
            return _error(failure, request_id=request_id, receipt=receipt, dsse=dsse)
        except Exception:
            receipt, dsse = _append(store, principal, {**metadata,
                "model_digest_observed_before_call": observed_digest, "phase": "OUTCOME",
                "decision_receipt_hash": decision_receipt["digest"], "state": "UNAVAILABLE",
                "code": "LOCAL_UNAVAILABLE", "provider_outcome_uncertain": True})
            return _error(AtelierFailure("LOCAL_UNAVAILABLE", 502),
                          request_id=request_id, receipt=receipt, dsse=dsse)
        receipt, dsse = _append(store, principal, {**metadata,
            "model_digest_observed_before_call": observed_digest, "phase": "OUTCOME",
            "decision_receipt_hash": decision_receipt["digest"], "state": "COMPLETED",
            "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "usage": usage,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "energy": {"label": "UNAVAILABLE", "joules": None}})
        return JSONResponse({"state": "COMPLETED", "answer": answer, "model": model,
            "provider": LOCAL_PROVIDER, "mode": LOCAL_MODE, "request_id": request_id,
            "receipt": receipt, "dsse": dsse,
            "energy": {"label": "UNAVAILABLE", "joules": None}, "retry_safe": False},
            headers={"Cache-Control": "no-store"})


def _execute_cpu_lab(principal, turn):
    body, canonical_request_hash = _cpu_lab_request(turn)
    if len(body) > CPU_LAB_MAX_BODY_BYTES:
        raise AtelierFailure("REQUEST_TOO_LARGE", 413, "DENIED")
    if szl_dsse.signing_available() is not True:
        raise AtelierFailure("SIGNER_UNAVAILABLE")
    path = _ledger_path()
    revision = os.environ.get("SZL_GIT_SHA", "")
    revision = revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None
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
        allowed = (classification.get("class") == "PUBLIC"
                   and policy.get("decision") == "allow")
        metadata = {"request_id": request_id, "provider": CPU_LAB_PROVIDER,
                    "mode": CPU_LAB_MODE, "model": CPU_LAB_MODEL,
                    "model_digest_expected": CPU_LAB_MODEL_SHA256,
                    "release_id_expected": CPU_LAB_RELEASE_ID,
                    "release_manifest_expected": CPU_LAB_RELEASE_MANIFEST_SHA256,
                    "prompt_sha256": hashlib.sha256(turn.prompt.encode()).hexdigest(),
                    "outbound_request_sha256": hashlib.sha256(body).hexdigest(),
                    "classification": classification.get("class"),
                    "public_share_acknowledged": turn.public_share_acknowledged,
                    "max_output_tokens": turn.max_output_tokens,
                    "source_revision": revision, "continuity": CONTINUITY,
                    "provider_output_signature_status": "UNSIGNED",
                    "retry_safe": False}
        decision_receipt, decision_dsse = _append(
            store, principal, {**metadata, "phase": "DECISION",
                               "decision": "ALLOW" if allowed else "DENY",
                               "policy_decision": policy.get("decision")})
        if not allowed:
            return _error(AtelierFailure("POLICY_DENIED", 403, "DENIED"),
                          request_id=request_id, receipt=decision_receipt, dsse=decision_dsse)
        try:
            observed = _cpu_lab_identity()
        except AtelierFailure as failure:
            receipt, dsse = _append(store, principal, {**metadata,
                "phase": "OUTCOME", "decision_receipt_hash": decision_receipt["digest"],
                "state": "UNAVAILABLE", "code": failure.code,
                "provider_outcome_uncertain": False})
            return _error(failure, request_id=request_id, receipt=receipt, dsse=dsse)
        started = time.monotonic()
        try:
            document, code = szl_provider_http.http_json(
                CPU_LAB_CHAT_URL, method="POST", body=body,
                headers={"Content-Type": "application/json"}, timeout=60.0,
                max_response_bytes=65_536, max_redirects=0, allow_private=False,
            )
            if code:
                raise _cpu_lab_failure(code)
            answer, usage, provider_id, record_hash = _cpu_lab_output(
                document, canonical_request_hash)
        except AtelierFailure as failure:
            receipt, dsse = _append(store, principal, {**metadata, **observed,
                "phase": "OUTCOME", "decision_receipt_hash": decision_receipt["digest"],
                "state": "UNAVAILABLE", "code": failure.code,
                "provider_outcome_uncertain": True})
            return _error(failure, request_id=request_id, receipt=receipt, dsse=dsse)
        except Exception:
            receipt, dsse = _append(store, principal, {**metadata, **observed,
                "phase": "OUTCOME", "decision_receipt_hash": decision_receipt["digest"],
                "state": "UNAVAILABLE", "code": "CPU_LAB_UNAVAILABLE",
                "provider_outcome_uncertain": True})
            return _error(AtelierFailure("CPU_LAB_UNAVAILABLE", 502),
                          request_id=request_id, receipt=receipt, dsse=dsse)
        receipt, dsse = _append(store, principal, {**metadata, **observed,
            "phase": "OUTCOME", "decision_receipt_hash": decision_receipt["digest"],
            "state": "COMPLETED", "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "usage": usage, "provider_response_id": provider_id,
            "provider_unsigned_execution_record_sha256": record_hash,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "energy": {"label": "UNAVAILABLE", "joules": None}})
        return JSONResponse({"state": "COMPLETED", "answer": answer,
            "model": CPU_LAB_MODEL, "provider": CPU_LAB_PROVIDER, "mode": CPU_LAB_MODE,
            "provider_output_signature_status": "UNSIGNED",
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
    paths = {f"{PREFIX}/health", f"{PREFIX}/turn",
             f"{PREFIX}/local/health", f"{PREFIX}/local/turn",
             f"{PREFIX}/cpu-lab/health", f"{PREFIX}/cpu-lab/turn"}
    existing = [route for route in app.router.routes if getattr(route, "path", None) in paths]
    if existing:
        if (len(existing) == len(paths) and {route.path for route in existing} == paths
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

    @app.api_route(f"{PREFIX}/local/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def atelier_local_health(request: Request):
        result = local_health()
        if request.method == "HEAD":
            return Response(status_code=200, headers={"Cache-Control": "no-store"})
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.post(f"{PREFIX}/local/turn", include_in_schema=False)
    async def atelier_local_turn(request: Request):
        try:
            principal = _authenticate(request)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > MAX_BODY_BYTES:
                    raise AtelierFailure("REQUEST_TOO_LARGE", 413, "DENIED")
            try:
                data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
                turn = LocalTurnRequest.model_validate(data)
            except (UnicodeDecodeError, ValueError, ValidationError):
                raise AtelierFailure("INVALID_REQUEST", 422, "DENIED") from None
            return await anyio.to_thread.run_sync(_execute_local, principal, turn)
        except AtelierFailure as failure:
            return _error(failure)
        except Exception:
            return _error(AtelierFailure("ATELIER_UNAVAILABLE"))

    @app.api_route(f"{PREFIX}/cpu-lab/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def atelier_cpu_lab_health(request: Request):
        result = await anyio.to_thread.run_sync(cpu_lab_health)
        if request.method == "HEAD":
            return Response(status_code=200, headers={"Cache-Control": "no-store"})
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.post(f"{PREFIX}/cpu-lab/turn", include_in_schema=False)
    async def atelier_cpu_lab_turn(request: Request):
        try:
            principal = _authenticate(request)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > CPU_LAB_MAX_BODY_BYTES:
                    raise AtelierFailure("REQUEST_TOO_LARGE", 413, "DENIED")
            try:
                data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
                turn = CpuLabTurnRequest.model_validate(data)
            except (UnicodeDecodeError, ValueError, ValidationError):
                raise AtelierFailure("INVALID_REQUEST", 422, "DENIED") from None
            return await anyio.to_thread.run_sync(_execute_cpu_lab, principal, turn)
        except AtelierFailure as failure:
            return _error(failure)
        except Exception:
            return _error(AtelierFailure("ATELIER_UNAVAILABLE"))

    added = app.router.routes[before:]
    del app.router.routes[before:]
    app.router.routes[0:0] = added
    return {"state": "REGISTERED", "routes": sorted(paths)}
