# SPDX-License-Identifier: Apache-2.0
"""A11oy same-origin adapter for the Living Anatomy v7 Brain/quant instrument.

Only five fixed, public, read-only Anatomy routes are admitted. No caller can
supply an origin or path. Redirects across hosts are rejected, responses are
bounded and content fields are refused, and failures remain explicitly
UNAVAILABLE. This module provides observability, not model, merge, execution,
training, provider, or consequential-action authority.
"""
from __future__ import annotations

import copy
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse

ANATOMY_ORIGIN = "https://betterwithage-anatomy.hf.space"
ROUTES = {
    "health": "/api/anatomy/v1/frontier-health",
    "frontier": "/api/anatomy/v1/brain/frontier?limit=48",
    "formulas": "/api/anatomy/v1/brain/formulas?limit=48",
    "quant": "/api/anatomy/v1/brain/quant?limit=48",
    "ouroboros": "/api/anatomy/v1/brain/ouroboros?limit=48",
}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CACHE_SECONDS = 45.0
USER_AGENT = "a11oy-holographic-brain-v7/1.0"
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_PUBLIC_KEYS = frozenset({"content", "text", "documents"})

AUTHORITY = {
    "content_access": "HANDLES_ONLY",
    "private_memory_access": "NONE",
    "training": "NONE",
    "weight_update": "NONE",
    "promotion": "NONE",
    "merge": "NONE",
    "execution": "NONE",
    "provider_mutation": "NONE",
    "consequential_action": "HUMAN_REVIEW_REQUIRED",
}


class BrainV7ProxyError(RuntimeError):
    """The fixed upstream or returned payload violated the proxy contract."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise BrainV7ProxyError("upstream redirect rejected")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _walk(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _walk(item)
        return
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        if str(key).lower() in FORBIDDEN_PUBLIC_KEYS:
            raise BrainV7ProxyError("upstream exposed candidate content")
        _walk(child)


def validate_payload(name: str, payload: Any) -> dict[str, Any]:
    if name not in ROUTES:
        raise BrainV7ProxyError("unknown fixed route")
    if not isinstance(payload, dict):
        raise BrainV7ProxyError("upstream payload is not an object")
    _walk(payload)
    state = str(payload.get("state") or "UNAVAILABLE")
    if state not in {"REVIEW_REQUIRED", "UNAVAILABLE", "BLOCKED"}:
        raise BrainV7ProxyError("upstream state is outside the review boundary")
    if payload.get("content_access") != "HANDLES_ONLY":
        raise BrainV7ProxyError("upstream is not handles-only")
    for field in ("training_authority", "promotion_authority", "execution_authority"):
        if payload.get(field) != "NONE":
            raise BrainV7ProxyError(f"upstream grants {field}")

    handles = payload.get("handles", [])
    if not isinstance(handles, list) or len(handles) > 48:
        raise BrainV7ProxyError("upstream handle count is invalid")
    for handle in handles:
        if not isinstance(handle, dict):
            raise BrainV7ProxyError("upstream handle is not an object")
        if handle.get("contentAccess") != "HANDLES_ONLY":
            raise BrainV7ProxyError("handle content boundary drifted")
        if handle.get("candidateState") != "DISCOVERED_REVIEW_REQUIRED":
            raise BrainV7ProxyError("candidate state was promoted")
        if not re.fullmatch(r"frontier:[0-9a-f]{32}", str(handle.get("nodeId") or "")):
            raise BrainV7ProxyError("invalid candidate handle")
        if not HEX_40.fullmatch(str(handle.get("revision") or "")):
            raise BrainV7ProxyError("candidate revision is not exact")
        if not HEX_64.fullmatch(str(handle.get("sha256") or "")):
            raise BrainV7ProxyError("candidate digest is malformed")
    return payload


def fetch_fixed_json(name: str) -> dict[str, Any]:
    try:
        path = ROUTES[name]
    except KeyError as exc:
        raise BrainV7ProxyError("unknown fixed route") from exc
    target = ANATOMY_ORIGIN + path
    parsed = urllib.parse.urlsplit(target)
    if parsed.scheme != "https" or parsed.hostname != "betterwithage-anatomy.hf.space":
        raise BrainV7ProxyError("fixed origin contract drifted")
    request = urllib.request.Request(
        target,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != parsed.hostname:
                raise BrainV7ProxyError("upstream host changed")
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "application/json" not in content_type:
                raise BrainV7ProxyError("upstream did not return JSON")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except BrainV7ProxyError:
        raise
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise BrainV7ProxyError(type(exc).__name__) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise BrainV7ProxyError("upstream response exceeded limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BrainV7ProxyError("upstream returned malformed JSON") from exc
    return validate_payload(name, payload)


Fetcher = Callable[[str], dict[str, Any]]


@dataclass
class _CacheEntry:
    stored_at: float
    payload: dict[str, Any]


class FixedBrainV7Proxy:
    """Small in-memory cache over the immutable fixed-route fetcher."""

    def __init__(
        self,
        fetcher: Fetcher = fetch_fixed_json,
        *,
        ttl_seconds: float = CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._ttl = max(0.0, float(ttl_seconds))
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, _CacheEntry] = {}

    def get(self, name: str) -> dict[str, Any]:
        if name not in ROUTES:
            raise BrainV7ProxyError("unknown fixed route")
        now = self._clock()
        with self._lock:
            cached = self._cache.get(name)
            if cached and now - cached.stored_at <= self._ttl:
                return copy.deepcopy(cached.payload)
        payload = validate_payload(name, self._fetcher(name))
        envelope = {
            "schema": "szl.a11oy.holographic-brain-v7/v1",
            "state": payload.get("state"),
            "ready": payload.get("ready", False),
            "plane": name,
            "source_origin": ANATOMY_ORIGIN,
            "source_schema": payload.get("schema"),
            "payload": payload,
            "payload_sha256": __import__("hashlib").sha256(
                canonical_bytes(payload)
            ).hexdigest(),
            "authority": dict(AUTHORITY),
        }
        with self._lock:
            self._cache[name] = _CacheEntry(now, envelope)
        return copy.deepcopy(envelope)


_PROXY: FixedBrainV7Proxy | None = None
_PROXY_LOCK = threading.Lock()


def get_proxy() -> FixedBrainV7Proxy:
    global _PROXY
    if _PROXY is None:
        with _PROXY_LOCK:
            if _PROXY is None:
                _PROXY = FixedBrainV7Proxy()
    return _PROXY


def create_brain_v7_router(proxy: FixedBrainV7Proxy | None = None) -> APIRouter:
    source = proxy or get_proxy()
    router = APIRouter(tags=["Holographic Brain v7"])

    @router.get("/api/a11oy/v1/holographic/brain-v7/contract")
    def contract() -> JSONResponse:
        return JSONResponse(
            {
                "schema": "szl.a11oy.holographic-brain-v7-contract/v1",
                "state": "SOURCE_BOUND_OBSERVABILITY",
                "upstream_origin": ANATOMY_ORIGIN,
                "fixed_planes": dict(ROUTES),
                "cache_seconds": CACHE_SECONDS,
                "max_response_bytes": MAX_RESPONSE_BYTES,
                "redirect_policy": "REJECT",
                "public_content_access": "HANDLES_ONLY",
                "authority": dict(AUTHORITY),
                "locked_proven_count": 8,
                "f_number_mapping": "UNKNOWN_NOT_INFERRED",
                "lambda": "CONJECTURE_1",
            }
        )

    for plane in ROUTES:
        def endpoint(plane_name: str = plane) -> JSONResponse:
            try:
                return JSONResponse(source.get(plane_name))
            except BrainV7ProxyError as exc:
                return JSONResponse(
                    {
                        "schema": "szl.a11oy.holographic-brain-v7/v1",
                        "state": "UNAVAILABLE",
                        "ready": False,
                        "plane": plane_name,
                        "source_origin": ANATOMY_ORIGIN,
                        "reason": type(exc).__name__,
                        "payload": {
                            "state": "UNAVAILABLE",
                            "ready": False,
                            "content_access": "HANDLES_ONLY",
                            "handles": [],
                            "training_authority": "NONE",
                            "promotion_authority": "NONE",
                            "execution_authority": "NONE",
                        },
                        "authority": dict(AUTHORITY),
                    },
                    status_code=503,
                )

        endpoint.__name__ = f"brain_v7_{plane}"
        router.add_api_route(
            f"/api/a11oy/v1/holographic/brain-v7/{plane}",
            endpoint,
            methods=["GET"],
        )

    return router


def install_brain_v7_holographic_routes(app: Any) -> None:
    marker = "_szl_brain_v7_holographic_installed"
    state = getattr(app, "state", None)
    if state is not None and getattr(state, marker, False):
        return
    app.include_router(create_brain_v7_router())
    if state is not None:
        setattr(state, marker, True)
