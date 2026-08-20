# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
"""
a11oy VERTICAL PACKS — server-side live feeds + governed loop + typed receipts.

ADDITIVE module (Dev2). Mounts under /api/a11oy/v1/vert/* BEFORE the SPA catch-all.
Owns the 5 vertical packs:
  - defense   (Defense / Gov):   live CISA KEV + NVD CVE + UDS mesh bridge
  - finance   (Finance):         live markets (Yahoo v8 + Coinbase) + fraud/risk governance + CVE-for-fintech
  - legal     (Legal):           live Federal Register + CourtListener (consolidates 'Counsel')
  - cyber     (Enterprise/Cyber):live CISA KEV + NVD CVE + GitHub/HF activity (consolidates 'Sentra')
  - realestate(Real Estate):     live NYC distress (HPD litigations + DOB violations) + Treasury rates (consolidates 'Terra')

Each pack: pulls REAL data SERVER-SIDE (0 client CDN), caches warm with honest 'cached'/'stale'
degrade labels, runs the GOVERNED LOOP (classify -> gate -> Λ floor -> route), and emits typed
RECEIPTS (signed only when signing machinery succeeds) reusing the EXISTING machinery:
  - szl_khipu.get_dag(<organ>).emit(action, payload)   -> append-only hash-chained receipt
  - szl_dsse.sign_khipu_receipt(receipt)               -> real ECDSA-P256 DSSE envelope (cosign.pub verifiable)
  - szl_governance_gateway.classify/route              -> sensitivity + model-route decision

DOCTRINE: locked=8 {F1,F4,F7,F11,F12,F18,F19,F22}; Λ = Conjecture 1 (advisory floor 0.90, NOT a theorem);
SLSA L1 honest; no fabricated data — any synthetic enrichment is SIMULATED-labeled; 0 runtime CDN.
All live sources verified in team/LIVE_SOURCES_VERIFIED.md (all HTTP 200).
"""

from __future__ import annotations

import base64
import copy
import functools
import hashlib
import json
import math
import os
import random
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Annotated, Any, Callable, Optional
from urllib.parse import urljoin

import anyio
import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Optional governance machinery (reused, never re-implemented). try/except so a
# missing dep can NEVER take down the route — honest degrade instead.
# ---------------------------------------------------------------------------
try:
    import szl_khipu  # append-only hash-chained receipt DAG
    _HAS_KHIPU = True
except Exception:  # pragma: no cover
    szl_khipu = None  # type: ignore
    _HAS_KHIPU = False

# POC (szl-substrate extraction): prefer the shared package as the single source
# of truth; fall back to the local vendored copy so nothing breaks if the package
# is not installed in this runtime. See szl-holdings/szl-substrate MIGRATION.md.
try:
    from szl_substrate import szl_dsse  # single source of truth (cosign.pub verifiable)
    _HAS_DSSE = True
except Exception:  # pragma: no cover
    try:
        import szl_dsse  # fall back to local vendored copy
        _HAS_DSSE = True
    except Exception:
        szl_dsse = None  # type: ignore
        _HAS_DSSE = False

try:
    import szl_governance_gateway as _gw  # classify() + route()
    _HAS_GW = True
except Exception:  # pragma: no cover
    _gw = None  # type: ignore
    _HAS_GW = False

NS = "a11oy"
DOCTRINE = {
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "lambda": "Conjecture 1 (advisory floor 0.90; unconditional uniqueness machine-checked FALSE; conditional axiom-free proven)",
    "slsa": "L1 only; this runtime surface makes no SLSA L2 or L3 claim",
    "lambda_floor": 0.90,
}
UA = {"User-Agent": "a11oy-mesh/2.0 (+https://huggingface.co/spaces/SZLHOLDINGS/a11oy) governed-feed"}

_SOURCE_HTTP_TIMEOUT_ENV = "A11OY_SOURCE_HTTP_TIMEOUT_S"
_SOURCE_HTTP_TIMEOUT_DEFAULT_S = 4.0
_SOURCE_HTTP_TIMEOUT_MIN_S = 0.25
_SOURCE_HTTP_TIMEOUT_MAX_S = 15.0


def _source_http_timeout_s() -> float:
    """Return the one bounded transport budget used by every live source."""
    raw = os.environ.get(_SOURCE_HTTP_TIMEOUT_ENV, str(_SOURCE_HTTP_TIMEOUT_DEFAULT_S))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = _SOURCE_HTTP_TIMEOUT_DEFAULT_S
    if not math.isfinite(value):
        value = _SOURCE_HTTP_TIMEOUT_DEFAULT_S
    return max(_SOURCE_HTTP_TIMEOUT_MIN_S, min(_SOURCE_HTTP_TIMEOUT_MAX_S, value))


def _source_url_allowed(url: str) -> bool:
    """Require TLS for external feeds; permit HTTP only for local loopback."""
    try:
        parsed = httpx.URL(url)
    except Exception:
        return False
    host = (parsed.host or "").lower().strip("[]")
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}


def _courtlistener_public_url(value: Any) -> str:
    """Return a CourtListener-owned public URL from an API path."""
    path = str(value or "").strip()
    if not path.startswith("/") or path.startswith("//"):
        return "https://www.courtlistener.com/"
    return urljoin("https://www.courtlistener.com/", path)


def _variant_cache_key(source: str, **parameters: Any) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, default=str).encode("utf-8")
    return f"{source}|{hashlib.sha256(canonical).hexdigest()[:20]}"


def _bounded_limit(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    return max(1, min(maximum, parsed))


def _bounded_text(value: Any, default: str, maximum: int) -> str:
    text = str(value if value is not None else default).strip()
    return (text or default)[:maximum]


_GOVERN_SCOPE = "vertical:govern"
_GOVERN_BODY_KEYS = frozenset({
    "text", "severity", "context", "classification", "action_kind",
})
_GOVERN_ACTION_ALIASES = {
    "decision": "decision",
    "review": "review",
    "assessment": "assessment",
    "triage": "triage",
    "incident-response": "incident-response",
    "forecast": "forecast",
}
_GOVERN_CLASSIFICATIONS = frozenset({
    "PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "PRIVILEGED", "SECRET",
})
_GOVERN_AUTH_LOCK = threading.Lock()
_GOVERN_AUTH_REGISTRY = None
_GOVERN_AUTH_FINGERPRINT: Optional[str] = None
_GOVERN_RATE_LOCK = threading.Lock()
_GOVERN_LAST: dict[tuple[str, str], float] = {}
_GOVERN_PENDING: set[tuple[str, str]] = set()


class _GovernValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class _GovernPayloadTooLarge(ValueError):
    """Raised before JSON decode when a govern body exceeds its byte budget."""


def _govern_body_limit_bytes() -> int:
    try:
        configured = int(os.environ.get("A11OY_GOVERN_BODY_MAX_BYTES", "16384"))
    except (TypeError, ValueError, OverflowError):
        configured = 16384
    return max(1024, min(65536, configured))


async def _read_govern_json(req: Request) -> Any:
    """Read a bounded request stream and only then decode its JSON document."""
    maximum = _govern_body_limit_bytes()
    headers = getattr(req, "headers", {})
    content_length = headers.get("content-length") if hasattr(headers, "get") else None
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except (TypeError, ValueError, OverflowError):
            raise _GovernValidationError("body", "Content-Length must be a non-negative integer")
        if declared_length < 0:
            raise _GovernValidationError("body", "Content-Length must be a non-negative integer")
        if declared_length > maximum:
            raise _GovernPayloadTooLarge

    stream = getattr(req, "stream", None)
    if callable(stream):
        encoded = bytearray()
        async for chunk in stream():
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                raise _GovernValidationError("body", "request body stream is invalid")
            encoded.extend(chunk)
            if len(encoded) > maximum:
                raise _GovernPayloadTooLarge
        raw = bytes(encoded)
        if not raw:
            raise _GovernValidationError("body", "request body must contain valid JSON")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise _GovernValidationError("body", "request body must contain valid UTF-8 JSON")

    # Test doubles and legacy standalone adapters may expose only json(). Re-encode
    # and enforce the identical byte budget before accepting their parsed value.
    try:
        body = await req.json()
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
    except Exception:
        raise _GovernValidationError("body", "request body must contain valid JSON")
    if len(encoded) > maximum:
        raise _GovernPayloadTooLarge
    return body


def _govern_credential_registry():
    """Load the immutable operator registry; absent/malformed config fails closed."""
    from gdw_auth import load_credential_registry

    global _GOVERN_AUTH_REGISTRY, _GOVERN_AUTH_FINGERPRINT
    registry_json = os.environ.get("A11OY_GOVERN_CREDENTIALS_JSON")
    principal_json = os.environ.get("A11OY_GOVERN_PRINCIPALS_JSON")
    if registry_json is None and principal_json is None:
        registry_json = os.environ.get("GDW_CREDENTIALS_JSON")
        principal_json = os.environ.get("GDW_PRINCIPALS_JSON")
    namespace = (
        os.environ.get("A11OY_GOVERN_NAMESPACE")
        or os.environ.get("GDW_NAMESPACE")
        or "a11oy"
    )
    fingerprint = hashlib.sha256(json.dumps({
        "registry": registry_json,
        "principals": principal_json,
        "namespace": namespace,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    with _GOVERN_AUTH_LOCK:
        if (_GOVERN_AUTH_REGISTRY is not None
                and _GOVERN_AUTH_FINGERPRINT == fingerprint):
            return _GOVERN_AUTH_REGISTRY, namespace
        registry = load_credential_registry(
            registry_json,
            principal_registry_json=principal_json,
            principal_registry_namespace=namespace,
        )
        _GOVERN_AUTH_REGISTRY = registry
        _GOVERN_AUTH_FINGERPRINT = fingerprint
        return registry, namespace


def _govern_authorise(authorization: Optional[str]):
    """Authenticate a constant-time bearer credential with the mutation scope."""
    from gdw_auth import AuthConfigurationError, AuthenticationError, authenticate_bearer

    try:
        registry, namespace = _govern_credential_registry()
        principal = authenticate_bearer(
            authorization,
            registry,
            namespace=namespace,
            required_scopes=(_GOVERN_SCOPE,),
        )
        return principal, None
    except AuthConfigurationError:
        return None, JSONResponse({
            "state": "unavailable",
            "error": "governance operator credential registry is unavailable",
        }, status_code=503)
    except AuthenticationError as error:
        status = 403 if error.code in {
            "credential_revoked", "foreign_namespace", "missing_scopes",
        } else 401
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return None, JSONResponse(
            {"state": "denied", "error": error.code},
            status_code=status,
            headers=headers,
        )


def _govern_interval_s() -> int:
    try:
        configured = int(os.environ.get("A11OY_GOVERN_MIN_INTERVAL_SEC", "2"))
    except (TypeError, ValueError, OverflowError):
        configured = 2
    return max(1, min(3600, configured))


def _govern_claim(principal):
    """Allow one queued/running mutation and cool down each credential key."""
    identity = (principal.owner_id, principal.key_id)
    interval = _govern_interval_s()
    now = time.monotonic()
    with _GOVERN_RATE_LOCK:
        last = _GOVERN_LAST.get(identity)
        if _GOVERN_PENDING:
            return None, max(1, interval)
        if last is not None and now - last < interval:
            return None, max(1, int(interval - (now - last) + 0.999))
        _GOVERN_LAST[identity] = now
        _GOVERN_PENDING.add(identity)
        return identity, None


def _govern_release(identity: tuple[str, str]) -> None:
    with _GOVERN_RATE_LOCK:
        _GOVERN_PENDING.discard(identity)


def _govern_actor(principal) -> dict[str, str]:
    return {
        "actor_type": "credential",
        "owner_id": principal.owner_id,
        "namespace": principal.namespace,
        "key_id": principal.key_id,
        "scope": _GOVERN_SCOPE,
    }


def _canonical_govern_action(surface: str, requested: Any) -> str:
    if not isinstance(requested, str) or requested not in _GOVERN_ACTION_ALIASES:
        raise _GovernValidationError(
            "action_kind",
            "action_kind must be one of: " + ", ".join(sorted(_GOVERN_ACTION_ALIASES)),
        )
    if not re.fullmatch(r"[a-z0-9-]{1,64}", surface):
        raise _GovernValidationError("action_kind", "governance surface is invalid")
    return f"a11oy.{surface}.govern.{_GOVERN_ACTION_ALIASES[requested]}"


def _bounded_json_value(value: Any, depth: int = 0) -> bool:
    if depth > 8:
        return False
    if value is None or isinstance(value, (bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        return len(value) <= 2000
    if isinstance(value, list):
        return len(value) <= 128 and all(
            _bounded_json_value(item, depth + 1) for item in value
        )
    if isinstance(value, dict):
        return len(value) <= 32 and all(
            isinstance(key, str) and len(key) <= 64
            and _bounded_json_value(item, depth + 1)
            for key, item in value.items()
        )
    return False


def _validate_govern_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise _GovernValidationError("body", "request body must be a JSON object")
    unknown = sorted(set(body) - _GOVERN_BODY_KEYS)
    if unknown:
        raise _GovernValidationError(
            unknown[0], "unknown request field; supported fields are: "
            + ", ".join(sorted(_GOVERN_BODY_KEYS)),
        )
    text = body.get("text", "")
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        raise _GovernValidationError("text", "text must be a non-empty string of at most 8000 characters")
    severity = body.get("severity", 0.0)
    if isinstance(severity, bool) or not isinstance(severity, (int, float)):
        raise _GovernValidationError("severity", "severity must be a finite number from 0 to 10")
    severity = float(severity)
    if not math.isfinite(severity) or not 0.0 <= severity <= 10.0:
        raise _GovernValidationError("severity", "severity must be a finite number from 0 to 10")
    context = body.get("context", {})
    if not isinstance(context, dict) or not _bounded_json_value(context):
        raise _GovernValidationError("context", "context must be a bounded JSON object")
    try:
        encoded_context = json.dumps(context, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError):
        raise _GovernValidationError("context", "context must contain finite JSON values")
    if len(encoded_context.encode("utf-8")) > 8192:
        raise _GovernValidationError("context", "context must be at most 8192 UTF-8 bytes")
    classification = body.get("classification")
    if classification is not None:
        if not isinstance(classification, str) or classification.upper() not in _GOVERN_CLASSIFICATIONS:
            raise _GovernValidationError(
                "classification",
                "classification must be one of: " + ", ".join(sorted(_GOVERN_CLASSIFICATIONS)),
            )
        classification = classification.upper()
    action_kind = body.get("action_kind", "decision")
    if not isinstance(action_kind, str) or action_kind not in _GOVERN_ACTION_ALIASES:
        raise _GovernValidationError(
            "action_kind",
            "action_kind must be one of: " + ", ".join(sorted(_GOVERN_ACTION_ALIASES)),
        )
    return {
        "text": text,
        "severity": severity,
        "context": context,
        "classification": classification,
        "action_kind": action_kind,
    }


def _govern_validation_response(error: _GovernValidationError) -> JSONResponse:
    return JSONResponse({"detail": [{
        "type": "value_error", "loc": ["body", error.field],
        "msg": error.message,
    }]}, status_code=422)


class _RefreshFlight:
    """One in-process refresh shared by every caller for the same cache key."""

    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Optional[dict[str, Any]] = None
        self.waiters = 0


# Blocking upstream clients remain synchronous so the existing feed/parser/cache
# contracts stay stable.  Every async route must cross this one bounded adapter;
# otherwise a slow upstream monopolizes the ASGI event loop and even local
# health endpoints stop responding.  DEV-A and DEV-B reuse this limiter.
try:
    _UPSTREAM_MAX_CONCURRENCY = max(
        1, min(16, int(os.environ.get("A11OY_UPSTREAM_CONCURRENCY", "8")))
    )
except (TypeError, ValueError):
    _UPSTREAM_MAX_CONCURRENCY = 8
_UPSTREAM_LIMITER = anyio.CapacityLimiter(_UPSTREAM_MAX_CONCURRENCY)


async def _run_blocking(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run one synchronous feed operation without blocking the ASGI loop.

    The default ``abandon_on_cancel=False`` is intentional: a cancelled request
    does not orphan a still-running socket worker.  The synchronous HTTP helper
    remains responsible for its bounded transport timeout.
    """
    call = functools.partial(func, *args, **kwargs)
    return await anyio.to_thread.run_sync(call, limiter=_UPSTREAM_LIMITER)


async def _gather_blocking(
    calls: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
) -> list[Any]:
    """Run independent feed operations concurrently, preserving call order."""
    results: list[Any] = [None] * len(calls)

    async def _one(index: int, func: Callable[..., Any], args: tuple[Any, ...],
                   kwargs: dict[str, Any]) -> None:
        results[index] = await _run_blocking(func, *args, **kwargs)

    async with anyio.create_task_group() as task_group:
        for index, (func, args, kwargs) in enumerate(calls):
            task_group.start_soon(_one, index, func, args, kwargs)
    return results

# ---------------------------------------------------------------------------
# Warm cache with honest freshness labels. Each source has its own TTL.
# Background-safe: a poll failure keeps the last-good value and marks it 'stale'.
# ---------------------------------------------------------------------------
def _cache_max_entries() -> int:
    try:
        configured = int(os.environ.get("A11OY_FEED_CACHE_MAX_ENTRIES", "256"))
    except (TypeError, ValueError, OverflowError):
        configured = 256
    return max(16, min(2048, configured))


class _Cache:
    def __init__(self, max_entries: Optional[int] = None) -> None:
        self._d: dict[str, dict[str, Any]] = {}
        self._inflight: dict[str, _RefreshFlight] = {}
        self._lock = threading.Lock()
        self._max_entries = max(1, max_entries or _cache_max_entries())

    def _evict_locked(self, protected_key: str) -> None:
        while len(self._d) > self._max_entries:
            candidates = [
                key for key in self._d
                if key != protected_key and key not in self._inflight
            ]
            if not candidates:
                candidates = [key for key in self._d if key != protected_key]
            if not candidates:
                candidates = list(self._d)
            victim = min(
                candidates,
                key=lambda key: (float(self._d[key].get("fetched_at", 0.0)), key),
            )
            del self._d[victim]

    def get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            v = self._d.get(key)
            return dict(v) if v else None

    def put(self, key: str, value: Any, ttl: float, status: str = "live") -> dict[str, Any]:
        rec = {"value": value, "fetched_at": time.time(), "ttl": ttl, "status": status}
        with self._lock:
            self._d[key] = rec
            self._evict_locked(key)
        return rec

    def claim_refresh(self, key: str) -> tuple[_RefreshFlight, bool]:
        with self._lock:
            flight = self._inflight.get(key)
            if flight is not None:
                flight.waiters += 1
                return flight, False
            flight = _RefreshFlight()
            self._inflight[key] = flight
            return flight, True

    def finish_refresh(self, key: str, flight: _RefreshFlight,
                       result: dict[str, Any]) -> None:
        with self._lock:
            if self._inflight.get(key) is flight:
                flight.result = result
                flight.event.set()
                del self._inflight[key]

    def mark_stale_if_same(self, key: str, fetched_at: float) -> None:
        with self._lock:
            current = self._d.get(key)
            if current and current.get("fetched_at") == fetched_at:
                current["status"] = "stale"

    def freshness(self, key: str) -> dict[str, Any]:
        rec = self.get(key)
        if not rec:
            return {"status": "empty", "age_s": None}
        age = time.time() - rec["fetched_at"]
        status = rec.get("status", "live")
        if status == "live" and age > rec["ttl"] * 4:
            status = "stale"
        elif status == "live" and age > rec["ttl"]:
            status = "cached"
        return {"status": status, "age_s": round(age, 1), "fetched_at": rec["fetched_at"]}

    def freshness_latest(self, source: str) -> dict[str, Any]:
        with self._lock:
            candidates = [dict(rec) for key, rec in self._d.items()
                          if key == source or key.startswith(source + "|")]
        if not candidates:
            return {"status": "empty", "age_s": None}
        rec = max(candidates, key=lambda item: item.get("fetched_at", 0.0))
        age = time.time() - rec["fetched_at"]
        status = rec.get("status", "live")
        if status == "live" and age > rec["ttl"] * 4:
            status = "stale"
        elif status == "live" and age > rec["ttl"]:
            status = "cached"
        return {"status": status, "age_s": round(age, 1),
                "fetched_at": rec["fetched_at"]}


_CACHE = _Cache()


def _client() -> httpx.Client:
    # Redirect following is disabled so an HTTPS source cannot downgrade to an
    # attacker-controlled HTTP Location after the initial URL policy check.
    return httpx.Client(timeout=_source_http_timeout_s(), headers=UA, follow_redirects=False)


def _flight_wait_failure(rec: Optional[dict[str, Any]]) -> dict[str, Any]:
    error = f"single-flight wait exceeded {_source_http_timeout_s():g}s source budget"
    if rec:
        return {"value": rec["value"], "freshness": {
            "status": "stale",
            "age_s": round(max(0.0, time.time() - rec["fetched_at"]), 1),
            "fetched_at": rec["fetched_at"],
            "error": error,
        }}
    return {"value": None, "freshness": {"status": "unavailable", "error": error}}


def _refresh_failure(rec: Optional[dict[str, Any]], exc: BaseException) -> dict[str, Any]:
    error = f"{type(exc).__name__}: {str(exc)[:160]}"
    if rec:
        return {"value": rec["value"], "freshness": {
            "status": "stale",
            "age_s": round(max(0.0, time.time() - rec["fetched_at"]), 1),
            "fetched_at": rec["fetched_at"],
            "error": error[:160],
        }}
    return {"value": None, "freshness": {"status": "unavailable", "error": error}}


def _cached_fetch(key: str, url: str, ttl: float, parser=None, label="live", headers=None) -> dict[str, Any]:
    """Return {value, freshness}. Serve warm cache if within TTL; else refetch.
    On error keep last-good and mark 'stale' — never fabricate. Concurrent
    refreshes for one key are coalesced into exactly one upstream operation."""
    if not _source_url_allowed(url):
        return {"value": None, "freshness": {
            "status": "unavailable", "error": "external feed URL requires HTTPS",
        }}
    rec = _CACHE.get(key)
    now = time.time()
    if rec and (now - rec["fetched_at"]) < rec["ttl"] and rec.get("status") == "live":
        return {"value": rec["value"], "freshness": _CACHE.freshness(key)}

    flight, is_leader = _CACHE.claim_refresh(key)
    if not is_leader:
        if not flight.event.wait(_source_http_timeout_s() + 1.0):
            return _flight_wait_failure(rec)
        return flight.result if flight.result is not None else _flight_wait_failure(rec)

    # A caller can read an expired record, lose the scheduler, and claim just
    # after the preceding leader publishes and retires. Recheck after claiming
    # so that late arrival consumes the new cache entry instead of opening a
    # duplicate transport.
    current = _CACHE.get(key)
    current_now = time.time()
    if (current and current.get("status") == "live"
            and (current_now - current["fetched_at"]) < current["ttl"]):
        result = {"value": current["value"], "freshness": _CACHE.freshness(key)}
        _CACHE.finish_refresh(key, flight, result)
        return result

    result: Optional[dict[str, Any]] = None
    try:
        with _client() as cl:
            r = cl.get(url, headers=headers) if headers else cl.get(url)
            r.raise_for_status()
            data = r.json()
        val = parser(data) if parser else data
        _CACHE.put(key, val, ttl, status="live")
        result = {"value": val, "freshness": _CACHE.freshness(key)}
    except BaseException as exc:
        if rec:
            _CACHE.mark_stale_if_same(key, rec["fetched_at"])
        result = _refresh_failure(rec, exc)
        if not isinstance(exc, Exception):
            raise
    finally:
        if result is None:
            result = _refresh_failure(rec, RuntimeError("refresh aborted before publication"))
        _CACHE.finish_refresh(key, flight, result)
    return result


# Bare vertical summaries report only child source state that this process has
# actually observed.  A cold cache is UNAVAILABLE, not evidence of a live feed.
_VERTICAL_FEED_CACHE_KEYS: dict[str, tuple[str, ...]] = {
    "defense": ("cisa_kev", "nvd"),
    "finance": (
        "yh_SPY", "yh_AAPL", "yh_MSFT", "yh_NVDA", "yh_^VIX",
        "poly_SPY", "poly_AAPL", "poly_MSFT", "poly_NVDA",
        "cb_BTC-USD", "cb_ETH-USD", "cb_SOL-USD", "nvd_financial", "fx_USD",
    ),
    "legal": ("fedreg", "courtlistener_artificial_intelligence"),
    "cyber": (
        "cisa_kev", "nvd", "gh_huggingface_transformers", "gh_openai_gpt-2",
        "gh_pytorch_pytorch", "ghev_huggingface_transformers", "hf_models",
    ),
    "realestate": ("nyc_hpd", "nyc_dob", "treasury"),
}


def _vertical_feed_state(vertical: str) -> dict[str, Any]:
    """Aggregate the latest observed cache state without performing I/O."""
    child_states = []
    for source_id in _VERTICAL_FEED_CACHE_KEYS.get(vertical, ()):
        freshness = _CACHE.freshness_latest(source_id)
        status = freshness.get("status", "unavailable")
        if status == "empty":
            status = "unavailable"
        child_states.append({"source_id": source_id, "status": status,
                             "freshness": freshness})

    statuses = [child["status"] for child in child_states]
    if statuses and all(status == "live" for status in statuses):
        aggregate = "live"
    elif statuses and all(status == "cached" for status in statuses):
        aggregate = "cached"
    elif statuses and all(status == "stale" for status in statuses):
        aggregate = "stale"
    elif not statuses or all(status == "unavailable" for status in statuses):
        aggregate = "unavailable"
    else:
        aggregate = "degraded"

    return {
        "status": aggregate,
        "live": aggregate == "live",
        "basis": "latest observed in-process child source cache state",
        "children_total": len(child_states),
        "children_live": sum(child["status"] == "live" for child in child_states),
        "children": child_states,
    }


# ===========================================================================
# GOVERNED LOOP — reuses szl_governance_gateway + a small deny-by-default gate.
# Honest: Λ is an advisory floor (Conjecture 1), NOT a pass/fail oracle.
# ===========================================================================
_THREAT_RX = re.compile(r"(?i)(drop\s+table|rm\s+-rf|<script|;\s*delete\s+from|exec\(|/etc/passwd|--\s*$|union\s+select|0x[0-9a-f]{8})")
_PII_RX = re.compile(r"(?i)(ssn|social security|\b\d{3}-\d{2}-\d{4}\b|credit card|\b\d{16}\b|routing number)")
_SIGNED_ENVELOPE_LOCK = threading.Lock()
_SIGNED_ENVELOPES: dict[tuple[str, str], dict[str, Any]] = {}
try:
    _SIGNED_ENVELOPE_MAX = max(16, min(4096, int(os.environ.get(
        "A11OY_SIGNER_EVIDENCE_MAX_ENTRIES", "512",
    ))))
except (TypeError, ValueError, OverflowError):
    _SIGNED_ENVELOPE_MAX = 512
_SIGNED_ENVELOPE_EVICTIONS = 0
_ROI_LOCK = threading.Lock()
_ROI_COUNTS: dict[str, dict[str, int]] = {}


def _governance_statement(*, organ: str, chain_receipt: dict[str, Any],
                          action_kind: str, actor: dict[str, str], decision: str,
                          sensitivity: Any, lam: float, lam_floor: float,
                          gates: list[dict[str, Any]], text: str,
                          context: dict[str, Any]) -> dict[str, Any]:
    """Build the privacy-safe semantics the signer actually attests.

    Raw input, input previews, and context values are intentionally excluded.
    Their canonical SHA-256 digests preserve equality checks without turning the
    public ledger into a content or secret store.
    """
    context_bytes = json.dumps(
        context, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False, default=str,
    ).encode("utf-8")
    return {
        "statement_type": "A11OY_GOVERNANCE_STATEMENT_V1",
        "schema_version": 1,
        "chain": {
            "organ": organ,
            "namespace": chain_receipt.get("ns"),
            "digest": chain_receipt.get("digest"),
            "payload_digest": chain_receipt.get("payload_digest"),
            "action": chain_receipt.get("action"),
        },
        "actor": {
            key: actor.get(key)
            for key in ("actor_type", "owner_id", "namespace", "key_id", "scope")
        },
        "policy": {
            "policy_id": "a11oy.vertical-govern.v1",
            "server_action": action_kind,
            "decision": decision,
            "sensitivity": sensitivity,
            "lambda": lam,
            "lambda_floor": lam_floor,
            "gates": [{
                "gate": gate.get("gate"),
                "fired": gate.get("fired") is True,
                "decision": gate.get("decision"),
            } for gate in gates],
        },
        "content_digests": {
            "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "context_sha256": hashlib.sha256(context_bytes).hexdigest(),
        },
        "privacy": "NO_RAW_INPUT_OR_CONTEXT",
    }


def _remember_signed_envelope(organ: str, chain_digest: Any,
                              statement: dict[str, Any], dsse: dict[str, Any]) -> None:
    """Keep bounded, evictable signer evidence addressable by chain digest."""
    global _SIGNED_ENVELOPE_EVICTIONS
    if not isinstance(chain_digest, str) or not re.fullmatch(r"[0-9a-fA-F]{32,128}", chain_digest):
        return
    record = {
        "chain_digest": chain_digest,
        "statement": copy.deepcopy(statement),
        "statement_sha256": hashlib.sha256(json.dumps(
            statement, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")).hexdigest(),
        "dsse": copy.deepcopy(dsse),
        "stored_at": time.time(),
        "durability": "IN_PROCESS_BOUNDED_EVICTABLE",
        "durable_across_restart": False,
    }
    key = (organ, chain_digest)
    with _SIGNED_ENVELOPE_LOCK:
        _SIGNED_ENVELOPES[key] = record
        while len(_SIGNED_ENVELOPES) > _SIGNED_ENVELOPE_MAX:
            victim = min(
                _SIGNED_ENVELOPES,
                key=lambda item: (
                    float(_SIGNED_ENVELOPES[item].get("stored_at", 0.0)), item,
                ),
            )
            del _SIGNED_ENVELOPES[victim]
            _SIGNED_ENVELOPE_EVICTIONS += 1


def _signature_evidence(organ: str, chain_receipt: dict[str, Any]) -> Optional[dict[str, Any]]:
    digest = chain_receipt.get("digest")
    if not isinstance(digest, str):
        return None
    with _SIGNED_ENVELOPE_LOCK:
        record = copy.deepcopy(_SIGNED_ENVELOPES.get((organ, digest)))
    if not record:
        return None
    statement = record.get("statement") if isinstance(record.get("statement"), dict) else {}
    chain = statement.get("chain") if isinstance(statement.get("chain"), dict) else {}
    dsse = record.get("dsse") if isinstance(record.get("dsse"), dict) else {}
    decoded = None
    try:
        decoded = json.loads(base64.b64decode(dsse.get("payload", ""), validate=True))
    except Exception:
        decoded = None
    statement_sha256 = hashlib.sha256(json.dumps(
        statement, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest() if statement else None
    content_digests = statement.get("content_digests") or {}
    digest_fields_valid = set(content_digests) == {
        "input_sha256", "context_sha256",
    } and all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in content_digests.values()
    )
    actor = statement.get("actor") if isinstance(statement.get("actor"), dict) else {}
    policy = statement.get("policy") if isinstance(statement.get("policy"), dict) else {}
    actor_valid = (
        set(actor) == {"actor_type", "owner_id", "namespace", "key_id", "scope"}
        and actor.get("actor_type") == "credential"
        and actor.get("scope") == _GOVERN_SCOPE
        and actor.get("namespace") == chain.get("namespace")
        and all(isinstance(actor.get(key), str) and actor.get(key)
                for key in ("owner_id", "namespace", "key_id"))
    )
    policy_valid = (
        policy.get("policy_id") == "a11oy.vertical-govern.v1"
        and policy.get("server_action") == chain_receipt.get("action")
        and policy.get("decision") in {"allow", "review", "deny"}
        and policy.get("sensitivity") in _GOVERN_CLASSIFICATIONS
        and isinstance(policy.get("gates"), list)
        and len(policy["gates"]) <= 16
    )
    top_level_valid = set(statement) in ({
        "statement_type", "schema_version", "chain", "actor", "policy",
        "content_digests", "privacy",
    }, {
        "statement_type", "schema_version", "chain", "actor", "policy",
        "content_digests", "privacy", "neuro_citations",
    })
    checks = {
        "retention_key_matches_chain_digest": record.get("chain_digest") == digest,
        "statement_chain_digest_matches": chain.get("digest") == digest,
        "statement_payload_digest_matches": (
            chain.get("payload_digest") == chain_receipt.get("payload_digest")
        ),
        "statement_action_matches": chain.get("action") == chain_receipt.get("action"),
        "statement_organ_matches": chain.get("organ") == organ,
        "statement_namespace_matches": chain.get("namespace") == chain_receipt.get("ns"),
        "statement_schema_valid": (
            top_level_valid
            and statement.get("statement_type") == "A11OY_GOVERNANCE_STATEMENT_V1"
            and statement.get("schema_version") == 1
            and statement.get("privacy") == "NO_RAW_INPUT_OR_CONTEXT"
            and digest_fields_valid and actor_valid and policy_valid
        ),
        "statement_digest_matches": record.get("statement_sha256") == statement_sha256,
        "envelope_payload_matches_statement": decoded == statement,
    }
    record["binding_checks"] = checks
    record["binding_verified"] = all(checks.values())
    record["envelope_payload_matches_statement"] = decoded == statement
    if _HAS_DSSE and hasattr(szl_dsse, "verify_envelope"):
        try:
            record["cryptographic_verification"] = szl_dsse.verify_envelope(dsse)
        except Exception:
            record["cryptographic_verification"] = {
                "verified": False, "reason": "verifier error",
            }
    else:
        record["cryptographic_verification"] = {
            "verified": False, "reason": "verifier unavailable",
        }
    record["verification_scope"] = (
        "binding_verified proves the retained DSSE payload matches the typed statement "
        "and exact Khipu chain receipt; cryptographic_verification is reported separately"
    )
    return record


def _signer_evidence_retention() -> dict[str, Any]:
    with _SIGNED_ENVELOPE_LOCK:
        return {
            "durability": "IN_PROCESS_BOUNDED_EVICTABLE",
            "durable_across_restart": False,
            "current_entries": len(_SIGNED_ENVELOPES),
            "max_entries": _SIGNED_ENVELOPE_MAX,
            "evictions": _SIGNED_ENVELOPE_EVICTIONS,
            "eviction_policy": "oldest-stored-at-then-organ-and-chain-digest",
        }


def _record_roi_decision(vertical: str, decision: str) -> None:
    if decision not in {"allow", "review", "deny"}:
        return
    with _ROI_LOCK:
        counts = _ROI_COUNTS.setdefault(
            vertical, {"allow": 0, "review": 0, "deny": 0},
        )
        counts[decision] = min(9_223_372_036_854_775_807, counts[decision] + 1)


def _roi_snapshot(vertical: str) -> dict[str, int]:
    with _ROI_LOCK:
        return dict(_ROI_COUNTS.get(
            vertical, {"allow": 0, "review": 0, "deny": 0},
        ))


def _lambda_estimate(text: str, severity: float, signals: list[str]) -> float:
    """Advisory Λ in [0,1]: starts at 0.97, penalised by detected risk signals.
    DETERMINISTIC, transparent (no fabricated AI confidence). Λ = Conjecture 1."""
    lam = 0.97
    if _THREAT_RX.search(text or ""):
        lam -= 0.55
    if _PII_RX.search(text or ""):
        lam -= 0.25
    lam -= 0.05 * len([s for s in signals if s.startswith("secret") or s.startswith("restricted")])
    lam -= min(0.30, max(0.0, (severity - 5.0) / 10.0) * 0.30)  # CVSS-like severity drag
    return round(max(0.0, min(1.0, lam)), 3)


def governed_turn(vertical: str, text: str, *, declared: str | None = None,
                  severity: float = 0.0, action_kind: str = "decision",
                  context: dict | None = None, actor: dict[str, str] | None = None,
                  emit_receipt: bool = True) -> dict[str, Any]:
    """Run the P1..P6-style governed turn over an input and emit an honest receipt.

    A Khipu receipt may be signed when the signing machinery is available. The
    dependency-free fallback is a content digest only: it is neither a chain
    proof nor a signature and must never be promoted to one by demo signing.

    Returns {decision, lambda, gates, route, receipt, dsse, doctrine}."""
    text = text or ""
    context = context or {}
    signals: list[str] = []

    # P1 classify (sensitivity) — reuse gateway when available
    if _HAS_GW:
        cls = _gw.classify(text, declared)
    else:
        cls = {"class": (declared or "PUBLIC").upper(), "rank": 1, "signals": []}
    signals += list(cls.get("signals", []))

    # P2 deny-by-default safety gates (genuine signature scan)
    gates = []
    threat_hit = bool(_THREAT_RX.search(text))
    pii_hit = bool(_PII_RX.search(text))
    gates.append({"gate": "threat-signature-scan", "fired": threat_hit,
                  "decision": "deny" if threat_hit else "allow"})
    gates.append({"gate": "pii-egress-guard", "fired": pii_hit,
                  "decision": "deny" if pii_hit else "allow"})
    if threat_hit:
        signals.append("threat-signature")
    if pii_hit:
        signals.append("pii-detected")

    # P3 Λ advisory floor (non-interference: a low Λ flags for human review, never silently passes)
    lam = _lambda_estimate(text, severity, signals)
    lam_floor = DOCTRINE["lambda_floor"]
    lam_pass = lam >= lam_floor and not threat_hit and not pii_hit

    # P4 route (cost-aware, sensitivity-first) — reuse gateway
    if _HAS_GW:
        route = _gw.route(text[:400] or "governed decision", classification=cls.get("class"),
                          min_tier=context.get("min_tier", "T1"), task=context.get("task", vertical))
    else:
        route = {"chosen": {"id": "local-policy-engine"}, "policy": "fallback"}

    decision = "deny" if (threat_hit or pii_hit) else ("allow" if lam_pass else "review")
    reason = ("immune gate denied: " + ",".join([g["gate"] for g in gates if g["fired"]])) if decision == "deny" \
        else ("Λ below advisory floor — flagged for human review" if decision == "review"
              else "passed safety gates; Λ above advisory floor")

    # P5/P6 emit a hash-chained receipt when Khipu is available. Otherwise the
    # fallback is explicitly digest-only, unsigned, and unverified.
    organ = f"vertical-{vertical}"
    payload = {
        "vertical": vertical,
        "action_kind": action_kind,
        "input_preview": text[:160],
        "sensitivity": cls.get("class"),
        "lambda": lam,
        "lambda_floor": lam_floor,
        "decision": decision,
        "signals": signals,
        "chosen_model": (route.get("chosen") or {}).get("id") if isinstance(route, dict) else None,
        "context": {k: v for k, v in context.items() if k != "min_tier"},
        "actor": dict(actor) if actor is not None else None,
    }
    receipt = None
    dsse = None
    chain_digest = None
    governance_statement = None
    if not emit_receipt:
        receipt = {
            "receipt_type": "NOT_EMITTED",
            "signature_state": "UNSIGNED",
            "signed": False,
            "signature": None,
            "chain_verified": False,
            "note": "read-only evaluation; no ledger append or signer call",
        }
        dsse = {
            "signed": False,
            "signature_state": "UNSIGNED",
            "honesty": "read-only evaluation; no signature requested",
        }
    elif _HAS_KHIPU:
        try:
            dag = szl_khipu.get_dag(organ, ns=NS)
            receipt = dag.emit(action_kind, payload)
            chain_digest = receipt.get("digest") if isinstance(receipt, dict) else None
            if actor is not None and isinstance(receipt, dict):
                governance_statement = _governance_statement(
                    organ=organ,
                    chain_receipt=receipt,
                    action_kind=action_kind,
                    actor=actor,
                    decision=decision,
                    sensitivity=cls.get("class"),
                    lam=lam,
                    lam_floor=lam_floor,
                    gates=gates,
                    text=text,
                    context=context,
                )
        except Exception as e:
            receipt = {"error": f"khipu-unavailable: {e}", "chain_verified": False}
    else:
        # Honest deterministic content digest only; not a chain or signature.
        import hashlib
        body = json.dumps(payload, sort_keys=True).encode()
        receipt = {"organ": organ, "ns": NS, "action": action_kind,
                   "digest": hashlib.sha256(body).hexdigest(),
                   "receipt_type": "DIGEST_ONLY", "signature_state": "UNSIGNED",
                   "signed": False, "signature": None, "chain_verified": False,
                   "note": "khipu module absent; deterministic sha256 content digest only"}
        dsse = {"signed": False, "signature_state": "UNSIGNED",
                "honesty": "DIGEST_ONLY: khipu module absent; no DSSE signature or chain proof"}
    if (emit_receipt and _HAS_DSSE and isinstance(governance_statement, dict)
            and isinstance(receipt, dict) and "error" not in receipt
            and receipt.get("receipt_type") != "DIGEST_ONLY"):
        try:
            signed = szl_dsse.sign_khipu_receipt(copy.deepcopy(governance_statement))
            dsse = signed.get("dsse")
            governance_statement = signed.get("receipt", governance_statement)
        except Exception as e:
            dsse = {"signed": False, "honesty": f"sign-unavailable: {e}"}
        # ADDITIVE demo-signing fallback (Option B): when the production cosign key
        # is founder-gated/absent (dsse unsigned), sign with the clearly-labelled
        # DEMO key so /verify can show a REAL in-browser ECDSA-P256 verification.
        # keyid="demo-signing-key" — NEVER mislabelled as the production signature.
        # Fully guarded: any failure keeps the honest UNSIGNED behavior
        # and never breaks the infer path.
        if (isinstance(dsse, dict) and not dsse.get("signed")
                and isinstance(governance_statement, dict)):
            try:
                import szl_demo_sign
                _demo = szl_demo_sign.demo_sign_receipt(governance_statement)
                if _demo is not None:
                    dsse = _demo["dsse"]
                    # demo_sign_receipt stamps its returned display receipt only
                    # after signing the original payload. Retain the exact signed
                    # statement so envelope-payload binding remains verifiable.
                    governance_statement = copy.deepcopy(governance_statement)
            except Exception as e:
                import sys as _dsys
                print(f"[demo-sign] non-fatal, staying UNSIGNED: {e!r}", file=_dsys.stderr)

    if (emit_receipt and isinstance(governance_statement, dict) and isinstance(dsse, dict)
            and dsse.get("signed") is True):
        _remember_signed_envelope(organ, chain_digest, governance_statement, dsse)
    if emit_receipt and actor is not None:
        _record_roi_decision(vertical, decision)

    return {
        "vertical": vertical,
        "decision": decision,
        "reason": reason,
        "lambda": lam,
        "lambda_floor": lam_floor,
        "lambda_pass": lam_pass,
        "sensitivity": cls,
        "gates": gates,
        "route": route,
        "receipt": receipt,
        "dsse": dsse,
        "governance_statement": governance_statement,
        "authorization": dict(actor) if actor is not None else None,
        "mutation": "ledger_append" if emit_receipt else "none",
        "doctrine": DOCTRINE,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _ledger(vertical: str, n: int = 25) -> dict[str, Any]:
    organ = f"vertical-{vertical}"
    if _HAS_KHIPU:
        try:
            dag = szl_khipu.get_dag(organ, ns=NS)
            receipts = []
            for item in reversed(dag.tail(n)):
                receipt = dict(item)
                evidence = _signature_evidence(organ, receipt)
                receipt["signature_evidence"] = evidence
                receipts.append(receipt)
            return {
                "organ": organ,
                "depth": dag.depth(),
                "head": dag.head(),
                "verify": dag.verify_chain(),
                "receipts": receipts,
                "ledger_scope": "HASH_CHAIN_WITH_TYPED_GOVERNANCE_STATEMENT_EVIDENCE",
                "signer_evidence_retention": _signer_evidence_retention(),
                "note": (
                    "The Khipu tail stores payload digests, not governance semantics. "
                    "A successful signer therefore attests a privacy-safe typed statement "
                    "joined by the exact chain digest. Evidence is bounded and evictable, "
                    "does not survive restart, and reports binding and cryptographic "
                    "verification as separate verdicts."
                ),
            }
        except Exception as e:
            return {"organ": organ, "error": str(e), "receipts": []}
    return {"organ": organ, "depth": 0, "receipts": [], "note": "khipu module absent"}


# ===========================================================================
# LIVE FEED PARSERS — all SERVER-SIDE, all real sources (see LIVE_SOURCES_VERIFIED.md)
# ===========================================================================
def feed_cisa_kev(limit: int = 40) -> dict[str, Any]:
    limit = _bounded_limit(limit, 40, 2000)
    # CISA's own host 403s datacenter/Hetzner egress IPs; the cisagov GitHub mirror
    # carries the identical authoritative catalog (same schema) and is reachable
    # server-side, so the KEV feed reports genuinely LIVE instead of DEGRADED.
    url = "https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
    def parse(d):
        vulns = d.get("vulnerabilities", [])
        vulns_sorted = sorted(vulns, key=lambda v: v.get("dateAdded", ""), reverse=True)
        return {
            "catalogVersion": d.get("catalogVersion"),
            "dateReleased": d.get("dateReleased"),
            "count": d.get("count", len(vulns)),
            "ransomware": sum(1 for v in vulns if str(v.get("knownRansomwareCampaignUse", "")).lower() == "known"),
            "items": [{
                "cveID": v.get("cveID"), "vendor": v.get("vendorProject"), "product": v.get("product"),
                "name": v.get("vulnerabilityName"), "dateAdded": v.get("dateAdded"),
                "dueDate": v.get("dueDate"), "action": v.get("requiredAction"),
                "ransomware": v.get("knownRansomwareCampaignUse"),
            } for v in vulns_sorted],
        }
    observed = _cached_fetch("cisa_kev", url, ttl=900, parser=parse)
    if not isinstance(observed.get("value"), dict):
        return observed
    result = dict(observed)
    value = dict(observed["value"])
    value["items"] = list(value.get("items") or [])[:limit]
    value["returned"] = len(value["items"])
    result["value"] = value
    return result


def feed_nvd(limit: int = 25, keyword: str | None = None) -> dict[str, Any]:
    limit = _bounded_limit(limit, 25, 100)
    keyword = _bounded_text(keyword, "", 120) or None
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=14)
    fmt = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.000")
    url = ("https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=" + str(limit)
           + "&pubStartDate=" + fmt(start) + "&pubEndDate=" + fmt(end))
    if keyword:
        url += "&" + str(httpx.QueryParams({"keywordSearch": keyword}))
    source = "nvd" + ("_" + re.sub(r"\W+", "_", keyword).strip("_")[:40] if keyword else "")
    key = _variant_cache_key(source, limit=limit, keyword=keyword or "")
    def parse(d):
        vs = d.get("vulnerabilities", [])
        def sev(v):
            m = v["cve"].get("metrics", {})
            arr = m.get("cvssMetricV31") or m.get("cvssMetricV30") or m.get("cvssMetricV2") or []
            if arr:
                cd = arr[0].get("cvssData", {})
                return cd.get("baseSeverity") or arr[0].get("baseSeverity") or "NONE", cd.get("baseScore", 0.0)
            return "NONE", 0.0
        out = []
        for v in vs:
            c = v["cve"]
            s, score = sev(v)
            desc = next((x["value"] for x in c.get("descriptions", []) if x.get("lang") == "en"), "")
            out.append({"id": c.get("id"), "severity": str(s).upper(), "score": score,
                        "published": (c.get("published") or "")[:10], "desc": desc[:200]})
        out.sort(key=lambda x: x["published"], reverse=True)
        sevcount = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "NONE": 0}
        for o in out:
            sevcount[o["severity"]] = sevcount.get(o["severity"], 0) + 1
        return {"totalResults": d.get("totalResults", 0), "items": out, "sevcount": sevcount}
    return _cached_fetch(key, url, ttl=240, parser=parse)


def feed_fedregister(limit: int = 20, term: str | None = None) -> dict[str, Any]:
    limit = _bounded_limit(limit, 20, 100)
    term = _bounded_text(term, "", 160) or None
    url = ("https://www.federalregister.gov/api/v1/documents.json?per_page=" + str(limit)
           + "&order=newest")
    if term:
        url += "&" + str(httpx.QueryParams({"conditions[term]": term}))
    key = _variant_cache_key("fedreg", limit=limit, term=term or "")
    def parse(d):
        res = d.get("results", [])
        return {"count": d.get("count"), "items": [{
            "title": r.get("title"), "type": r.get("type"), "agency": ", ".join(a.get("name", "") for a in (r.get("agencies") or [])[:2]),
            "abstract": (r.get("abstract") or "")[:240], "date": r.get("publication_date"),
            "url": r.get("html_url"), "doc": r.get("document_number"),
        } for r in res]}
    return _cached_fetch(key, url, ttl=600, parser=parse)


def feed_courtlistener(term: str = "artificial intelligence", limit: int = 20) -> dict[str, Any]:
    term = _bounded_text(term, "artificial intelligence", 160)
    limit = _bounded_limit(limit, 20, 100)
    source = "courtlistener_" + re.sub(r"\W+", "_", term).strip("_")[:40]
    url = "https://www.courtlistener.com/api/rest/v4/search/?" + str(httpx.QueryParams({
        "q": term, "type": "o", "order_by": "dateFiled desc", "page_size": limit,
    }))
    key = _variant_cache_key(source, term=term, limit=limit, kind="o")
    def parse(d):
        res = d.get("results", [])[:limit]
        return {"count": d.get("count"), "items": [{
            "caseName": r.get("caseName"), "court": r.get("court"), "dateFiled": r.get("dateFiled"),
            "url": _courtlistener_public_url(r.get("absolute_url")),
            "citeCount": r.get("citeCount", 0), "status": r.get("status"),
        } for r in res]}
    return _cached_fetch(key, url, ttl=900, parser=parse)


def feed_yahoo(symbol: str) -> dict[str, Any]:
    symbol = _bounded_text(symbol, "SPY", 24).upper()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    def parse(d):
        res = (d.get("chart", {}).get("result") or [{}])[0]
        m = res.get("meta", {})
        quotes = (res.get("indicators", {}).get("quote") or [{}])[0]
        closes = [c for c in (quotes.get("close") or []) if c is not None]
        return {"symbol": symbol, "price": m.get("regularMarketPrice"), "prevClose": m.get("chartPreviousClose") or m.get("previousClose"),
                "currency": m.get("currency"), "spark": closes[-30:], "ts": m.get("regularMarketTime"),
                "source": "Yahoo Finance (unofficial v8 endpoint — fallback)", "official": False,
                "data_kind": "unofficial-fallback"}
    return _cached_fetch(_variant_cache_key("yh_" + symbol, symbol=symbol,
                                            interval="1d", range="5d"),
                         url, ttl=30, parser=parse)


def feed_coinbase(pair: str) -> dict[str, Any]:
    pair = _bounded_text(pair, "BTC-USD", 24).upper()
    url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
    def parse(d):
        return {"pair": pair, "amount": float(d.get("data", {}).get("amount", 0)),
                "currency": d.get("data", {}).get("currency"),
                "source": "Coinbase spot price", "leader": "Coinbase", "data_kind": "live"}
    return _cached_fetch(_variant_cache_key("cb_" + pair, pair=pair),
                         url, ttl=20, parser=parse)


def feed_fx(base: str = "USD", symbols: str = "EUR,GBP,JPY,CAD,CHF") -> dict[str, Any]:
    base = _bounded_text(base, "USD", 8).upper()
    symbols = _bounded_text(symbols, "EUR,GBP,JPY,CAD,CHF", 80).upper()
    url = f"https://api.frankfurter.dev/v1/latest?base={base}&symbols={symbols}"
    def parse(d):
        return {"base": d.get("base"), "date": d.get("date"),
                "rates": d.get("rates", {}),
                "source": "ECB euro reference rates (via Frankfurter)",
                "leader": "European Central Bank (ECB)", "data_kind": "live"}
    return _cached_fetch(_variant_cache_key("fx_" + base, base=base, symbols=symbols),
                         url, ttl=600, parser=parse)


def feed_polygon(symbol: str) -> dict[str, Any]:
    """Official Polygon.io market data (key-gated). The API key is sent via an
    Authorization header (never in the URL) so it cannot leak into cached error
    strings. When POLYGON_API_KEY is unset we return an honest 'disabled'
    payload — never a fabricated price. Live tick streaming (WebSocket) is a
    roadmap item; this REST path serves the official previous-session OHLC."""
    symbol = _bounded_text(symbol, "SPY", 24).upper()
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        return {"value": {"symbol": symbol, "source": "polygon.io", "official": True,
                          "status": "disabled", "reason": "POLYGON_API_KEY not set",
                          "live_ticks": "websocket roadmap"},
                "freshness": {"status": "unavailable", "error": "POLYGON_API_KEY not set"}}
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?adjusted=true"
    def parse(d):
        r = (d.get("results") or [{}])[0]
        return {"symbol": symbol, "source": "polygon.io", "official": True, "status": "live",
                "open": r.get("o"), "high": r.get("h"), "low": r.get("l"),
                "close": r.get("c"), "volume": r.get("v"), "ts": r.get("t")}
    return _cached_fetch(_variant_cache_key("poly_" + symbol, symbol=symbol,
                                            adjusted=True), url, ttl=30, parser=parse,
                         headers={"Authorization": f"Bearer {key}"})


def feed_gh_events(repo: str = "huggingface/transformers", limit: int = 12) -> dict[str, Any]:
    repo = _bounded_text(repo, "huggingface/transformers", 160)
    limit = _bounded_limit(limit, 12, 100)
    url = f"https://api.github.com/repos/{repo}/events?per_page={limit}"
    def parse(d):
        return {"repo": repo, "items": [{
            "type": e.get("type"), "actor": (e.get("actor") or {}).get("login"),
            "created": e.get("created_at"),
            "ref": (e.get("payload") or {}).get("ref") or (e.get("payload") or {}).get("action"),
        } for e in (d if isinstance(d, list) else [])[:limit]]}
    source = "ghev_" + re.sub(r"\W+", "_", repo).strip("_")[:48]
    return _cached_fetch(_variant_cache_key(source, repo=repo, limit=limit),
                         url, ttl=180, parser=parse)


def feed_treasury(limit: int = 6) -> dict[str, Any]:
    limit = _bounded_limit(limit, 6, 100)
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/"
           "avg_interest_rates?sort=-record_date&page%5Bsize%5D=" + str(limit))
    def parse(d):
        return {"items": [{"date": r.get("record_date"), "security": r.get("security_desc"),
                           "type": r.get("security_type_desc"), "rate": float(r.get("avg_interest_rate_amt", 0) or 0)}
                          for r in d.get("data", [])]}
    return _cached_fetch(_variant_cache_key("treasury", limit=limit),
                         url, ttl=3600, parser=parse)


def feed_github(repo: str) -> dict[str, Any]:
    repo = _bounded_text(repo, "huggingface/transformers", 160)
    url = f"https://api.github.com/repos/{repo}"
    def parse(d):
        return {"repo": repo, "stars": d.get("stargazers_count"), "forks": d.get("forks_count"),
                "issues": d.get("open_issues_count"), "pushed_at": d.get("pushed_at"),
                "lang": d.get("language")}
    source = "gh_" + re.sub(r"\W+", "_", repo).strip("_")[:48]
    return _cached_fetch(_variant_cache_key(source, repo=repo),
                         url, ttl=300, parser=parse)


def feed_hf(limit: int = 8) -> dict[str, Any]:
    limit = _bounded_limit(limit, 8, 100)
    url = "https://huggingface.co/api/models?limit=" + str(limit) + "&sort=trendingScore"
    def parse(d):
        return {"items": [{"id": m.get("id"), "likes": m.get("likes"), "downloads": m.get("downloads"),
                           "trending": m.get("trendingScore")} for m in (d if isinstance(d, list) else [])]}
    return _cached_fetch(_variant_cache_key("hf_models", limit=limit,
                                            sort="trendingScore"),
                         url, ttl=300, parser=parse)


def feed_nyc_hpd(limit: int = 40) -> dict[str, Any]:
    limit = _bounded_limit(limit, 40, 1000)
    url = ("https://data.cityofnewyork.us/resource/59kj-x8nc.json?%24limit=" + str(limit)
           + "&%24order=caseopendate%20DESC")
    def parse(d):
        items = []
        for r in (d if isinstance(d, list) else []):
            try:
                lat = float(r.get("latitude")) if r.get("latitude") else None
                lng = float(r.get("longitude")) if r.get("longitude") else None
            except Exception:
                lat = lng = None
            items.append({"id": r.get("litigationid"), "casetype": r.get("casetype"),
                          "status": r.get("casestatus"), "respondent": (r.get("respondent") or "")[:80],
                          "address": f"{r.get('housenumber','')} {r.get('streetname','')}".strip(),
                          "zip": r.get("zip"), "nta": r.get("nta"), "bbl": r.get("bbl"),
                          "lat": lat, "lng": lng, "opened": r.get("caseopendate")})
        return {"items": items}
    return _cached_fetch(_variant_cache_key("nyc_hpd", limit=limit,
                                            order="caseopendate DESC"),
                         url, ttl=900, parser=parse)


def feed_nyc_dob(limit: int = 30) -> dict[str, Any]:
    limit = _bounded_limit(limit, 30, 1000)
    url = "https://data.cityofnewyork.us/resource/3h2n-5cm9.json?%24limit=" + str(limit)
    def parse(d):
        return {"items": [{"id": r.get("isn_dob_bis_viol"), "type": r.get("violation_type"),
                           "street": (str(r.get("house_number", "")) + " " + str(r.get("street", ""))).strip(),
                           "boro": r.get("boro"), "issued": r.get("issue_date")}
                          for r in (d if isinstance(d, list) else [])]}
    return _cached_fetch(_variant_cache_key("nyc_dob", limit=limit),
                         url, ttl=1800, parser=parse)


# ===========================================================================
# ROI / cost-of-failure — honest, LABELED assumptions (no fabricated outcomes).
# ===========================================================================
_ROI_ASSUMPTIONS = {
    "defense": {"unit": "exploited-CVE incident", "avoided_per_unit_usd": 1_200_000,
                "basis": "IBM Cost of a Data Breach 2024 avg ($4.88M) scaled to a single contained KEV exploitation; LABELED assumption."},
    "finance": {"unit": "fraud/poisoned-decision caught", "avoided_per_unit_usd": 350_000,
                "basis": "Nilson/ACFE median occupational+payment fraud loss band; LABELED assumption."},
    "legal": {"unit": "missed obligation / adverse filing", "avoided_per_unit_usd": 500_000,
              "basis": "Median commercial-contract dispute exposure band; LABELED assumption."},
    "cyber": {"unit": "AI incident contained", "avoided_per_unit_usd": 1_500_000,
              "basis": "IBM 2024 breach avg incl. detection-time savings; LABELED assumption."},
    "realestate": {"unit": "distressed-asset mispricing avoided", "avoided_per_unit_usd": 800_000,
                   "basis": "Avg NYC multifamily distressed-deal write-down band; LABELED assumption."},
}


def roi(vertical: str, governed_count: int, caught_count: int,
        outcome_counts: Optional[dict[str, int]] = None) -> dict[str, Any]:
    a = _ROI_ASSUMPTIONS.get(vertical, {"avoided_per_unit_usd": 0, "unit": "decision", "basis": "n/a"})
    return {
        "vertical": vertical,
        "governed_decisions": governed_count,
        "risks_caught": caught_count,
        "decision_outcomes": dict(outcome_counts or {}),
        "count_evidence": (
            "privacy-safe in-process aggregate of authenticated govern mutations; "
            "resets on process restart; never inferred from ledger depth"
        ),
        "liability_avoided_usd": caught_count * a["avoided_per_unit_usd"],
        "per_unit_usd": a["avoided_per_unit_usd"],
        "unit": a["unit"],
        "basis": a["basis"],
        "label": "MODELED — honest assumptions, not realised P&L",
    }


# ===========================================================================
# CITED LEADER SOURCES — every vertical carries ≥1 real, NAMED leader/standard
# with a resolvable URL (mirrors the killinchu real-data + citation upgrade,
# T-K4). These are the authoritative bodies behind each live feed; data_kind is
# honest: 'live' = a real HTTP-200 feed we pull, 'unofficial-fallback' = Yahoo
# v8 (yfinance-equivalent, not an official quote source), 'reference' = a cited
# standard/leader we ground against but do not poll in this endpoint.
# ===========================================================================
CITED_LEADERS: dict[str, list[dict[str, str]]] = {
    "defense": [
        {"source": "Known Exploited Vulnerabilities (KEV) Catalog",
         "leader": "CISA — Cybersecurity & Infrastructure Security Agency",
         "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
         "data_kind": "live"},
        {"source": "National Vulnerability Database (NVD 2.0)",
         "leader": "NIST — National Institute of Standards and Technology",
         "url": "https://nvd.nist.gov/", "data_kind": "live"},
        {"source": "ATT&CK adversary technique corpus",
         "leader": "MITRE", "url": "https://attack.mitre.org/", "data_kind": "reference"},
    ],
    "finance": [
        {"source": "Euro foreign-exchange reference rates (served via Frankfurter)",
         "leader": "European Central Bank (ECB)",
         "url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html",
         "data_kind": "live"},
        {"source": "Spot crypto prices",
         "leader": "Coinbase", "url": "https://docs.cdp.coinbase.com/", "data_kind": "live"},
        {"source": "v8 chart endpoint (yfinance-equivalent)",
         "leader": "Yahoo Finance", "url": "https://finance.yahoo.com/",
         "data_kind": "unofficial-fallback"},
        {"source": "Fintech CVE prioritisation",
         "leader": "NIST NVD", "url": "https://nvd.nist.gov/", "data_kind": "live"},
        {"source": "Official OHLC market data (key-gated)",
         "leader": "Polygon.io", "url": "https://polygon.io/docs", "data_kind": "reference"},
    ],
    "legal": [
        {"source": "Federal Register API",
         "leader": "Office of the Federal Register — U.S. National Archives (NARA)",
         "url": "https://www.federalregister.gov/developers/documentation/api/v1",
         "data_kind": "live"},
        {"source": "U.S. case law search API",
         "leader": "Free Law Project — CourtListener",
         "url": "https://www.courtlistener.com/help/api/rest/", "data_kind": "live"},
    ],
    "cyber": [
        {"source": "Known Exploited Vulnerabilities (KEV) Catalog",
         "leader": "CISA — Cybersecurity & Infrastructure Security Agency",
         "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
         "data_kind": "live"},
        {"source": "National Vulnerability Database (NVD 2.0)",
         "leader": "NIST", "url": "https://nvd.nist.gov/", "data_kind": "live"},
        {"source": "ATT&CK adversary technique corpus",
         "leader": "MITRE", "url": "https://attack.mitre.org/", "data_kind": "reference"},
    ],
    "realestate": [
        {"source": "HPD housing litigations + DOB violations (Socrata)",
         "leader": "NYC Open Data — City of New York",
         "url": "https://opendata.cityofnewyork.us/", "data_kind": "live"},
        {"source": "Average interest rates on U.S. Treasury securities (Fiscal Data API)",
         "leader": "U.S. Department of the Treasury — Bureau of the Fiscal Service",
         "url": "https://fiscaldata.treasury.gov/datasets/average-interest-rates-treasury-securities/",
         "data_kind": "live"},
        {"source": "Housing & rate macro series (cited standard)",
         "leader": "Federal Reserve Bank of St. Louis (FRED)",
         "url": "https://fred.stlouisfed.org/", "data_kind": "reference"},
    ],
}


def cited_leaders(vertical: str) -> list[dict[str, str]]:
    """≥1 real, named leader source per vertical (honest data_kind labels)."""
    return CITED_LEADERS.get(vertical, [])


# ===========================================================================
# REGISTER — additive routes BEFORE SPA catch-all.
# ===========================================================================
def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    base = f"/api/{ns}/v1/vert"
    # Snapshot route count so we can move our new routes to the FRONT of the
    # router after registration. serve.py's /api/a11oy/{path:path} Node proxy
    # and the /{full_path:path} SPA catch-all are registered EARLIER; plain
    # @app.get decorators APPEND, so without this reorder our /v1/vert/* routes
    # would be SHADOWED (proxied to Node -> 404). Mirrors the dev1 WOW pattern.
    _n_before = len(app.router.routes)

    # ---- DEFENSE / GOV ----
    @app.get(base + "/defense/feed", include_in_schema=False)
    async def _def_feed(limit: Annotated[int, Query(ge=1, le=100)] = 30):
        kev, nvd = await _gather_blocking([
            (feed_cisa_kev, (limit,), {}),
            (feed_nvd, (min(limit, 20),), {}),
        ])
        return JSONResponse({"vertical": "defense", "kev": kev, "nvd": nvd,
                             "sources_cited": cited_leaders("defense"), "doctrine": DOCTRINE})

    @app.get(base + "/defense/kpi", include_in_schema=False)
    async def _def_kpi():
        kev = await _run_blocking(feed_cisa_kev, 2000)
        v = kev.get("value") or {}
        return JSONResponse({"catalog_count": v.get("count"), "ransomware": v.get("ransomware"),
                             "catalogVersion": v.get("catalogVersion"), "freshness": kev.get("freshness")})

    # ---- FINANCE ----
    @app.get(base + "/finance/feed", include_in_schema=False)
    async def _fin_feed():
        syms = ["SPY", "AAPL", "MSFT", "NVDA", "^VIX"]
        official_syms = ["SPY", "AAPL", "MSFT", "NVDA"]
        crypto_pairs = ["BTC-USD", "ETH-USD", "SOL-USD"]
        calls = (
            [(feed_yahoo, (symbol,), {}) for symbol in syms]
            + [(feed_polygon, (symbol,), {}) for symbol in official_syms]
            + [(feed_coinbase, (pair,), {}) for pair in crypto_pairs]
            + [(feed_nvd, (12,), {"keyword": "financial"}),
               (feed_fx, ("USD", "EUR,GBP,JPY,CAD,CHF"), {})]
        )
        values = await _gather_blocking(calls)
        cursor = 0
        eq = dict(zip(syms, values[cursor:cursor + len(syms)]))
        cursor += len(syms)
        # Official source: Polygon.io (key-gated). ^VIX is an index, not a Polygon stock ticker.
        official = dict(zip(
            official_syms, values[cursor:cursor + len(official_syms)]
        ))
        cursor += len(official_syms)
        crypto = dict(zip(
            crypto_pairs, values[cursor:cursor + len(crypto_pairs)]
        ))
        cursor += len(crypto_pairs)
        cve, fx = values[cursor:cursor + 2]
        return JSONResponse({"vertical": "finance",
                             "equities_official": official,
                             "equities": eq,
                             "equities_note": ("equities_official = Polygon.io (official, key-gated); "
                                               "equities = Yahoo v8 (unofficial fallback)"),
                             "crypto": crypto,
                             "fx": fx, "fintech_cve": cve,
                             "sources_cited": cited_leaders("finance"), "doctrine": DOCTRINE})

    # ---- LEGAL ----
    @app.get(base + "/legal/feed", include_in_schema=False)
    async def _legal_feed(limit: Annotated[int, Query(ge=1, le=100)] = 18):
        fr, cl = await _gather_blocking([
            (feed_fedregister, (limit,), {}),
            (feed_courtlistener, ("artificial intelligence", limit), {}),
        ])
        return JSONResponse({"vertical": "legal", "federal_register": fr, "court_filings": cl,
                             "sources_cited": cited_leaders("legal"), "doctrine": DOCTRINE})

    # ---- ENTERPRISE / CYBER ----
    @app.get(base + "/cyber/feed", include_in_schema=False)
    async def _cyber_feed(limit: Annotated[int, Query(ge=1, le=100)] = 30):
        repos = ["huggingface/transformers", "openai/gpt-2", "pytorch/pytorch"]
        values = await _gather_blocking(
            [(feed_cisa_kev, (limit,), {}),
             (feed_nvd, (min(limit, 20),), {})]
            + [(feed_github, (repo,), {}) for repo in repos]
            + [(feed_gh_events, ("huggingface/transformers", 12), {}),
               (feed_hf, (8,), {})]
        )
        kev, nvd = values[:2]
        gh = dict(zip(repos, values[2:2 + len(repos)]))
        ghev, hf = values[2 + len(repos):2 + len(repos) + 2]
        return JSONResponse({"vertical": "cyber", "kev": kev, "nvd": nvd, "github": gh,
                             "gh_events": ghev, "hf": hf,
                             "sources_cited": cited_leaders("cyber"), "doctrine": DOCTRINE})

    # ---- REAL ESTATE ----
    @app.get(base + "/realestate/feed", include_in_schema=False)
    async def _re_feed(limit: Annotated[int, Query(ge=1, le=1000)] = 40):
        hpd, dob, rates = await _gather_blocking([
            (feed_nyc_hpd, (limit,), {}),
            (feed_nyc_dob, (30,), {}),
            (feed_treasury, (6,), {}),
        ])
        return JSONResponse({"vertical": "realestate", "hpd_litigations": hpd,
                             "dob_violations": dob, "rates": rates,
                             "sources_cited": cited_leaders("realestate"), "doctrine": DOCTRINE})

    # ---- SHARED: governed turn, ledger, roi ----
    @app.post(base + "/{vertical}/govern", include_in_schema=False)
    async def _govern(vertical: str, req: Request):
        if vertical not in ("defense", "finance", "legal", "cyber", "realestate"):
            return JSONResponse({"error": "unknown vertical"}, status_code=404)
        principal, denial = _govern_authorise(req.headers.get("authorization"))
        if denial is not None:
            return denial
        try:
            body = await _read_govern_json(req)
        except _GovernPayloadTooLarge:
            return JSONResponse({
                "detail": "governance request body exceeds the configured byte limit",
            }, status_code=413)
        except _GovernValidationError as error:
            return _govern_validation_response(error)
        try:
            clean = _validate_govern_body(body)
            action_kind = _canonical_govern_action("vertical-" + vertical, clean["action_kind"])
        except _GovernValidationError as error:
            return _govern_validation_response(error)
        identity, retry_after = _govern_claim(principal)
        if identity is None:
            return JSONResponse({
                "state": "rate_limited",
                "error": "a governance mutation is already active or this credential is inside its cooldown",
                "retry_after_s": retry_after,
            }, status_code=429, headers={"Retry-After": str(retry_after)})
        actor = _govern_actor(principal)
        try:
            result = await _run_blocking(
                governed_turn, vertical, clean["text"],
                declared=clean["classification"], severity=clean["severity"],
                action_kind=action_kind, context=clean["context"], actor=actor,
            )
            return JSONResponse(result)
        finally:
            _govern_release(identity)

    @app.get(base + "/{vertical}/ledger", include_in_schema=False)
    async def _ledger_ep(
        vertical: str, n: Annotated[int, Query(ge=1, le=1000)] = 25,
    ):
        if vertical not in ("defense", "finance", "legal", "cyber", "realestate"):
            return JSONResponse({"error": "unknown vertical"}, status_code=404)
        return JSONResponse(await _run_blocking(_ledger, vertical, n))

    @app.get(base + "/{vertical}/roi", include_in_schema=False)
    async def _roi_ep(vertical: str):
        if vertical not in ("defense", "finance", "legal", "cyber", "realestate"):
            return JSONResponse({"error": "unknown vertical"}, status_code=404)
        outcomes = _roi_snapshot(vertical)
        governed = sum(outcomes.values())
        caught = outcomes["review"] + outcomes["deny"]
        return JSONResponse(roi(vertical, governed, caught, outcomes))

    @app.get(base + "/healthz", include_in_schema=False)
    async def _vh():
        return JSONResponse({"ok": True, "verticals": ["defense", "finance", "legal", "cyber", "realestate"],
                             "khipu": _HAS_KHIPU, "dsse": _HAS_DSSE, "gateway": _HAS_GW,
                             "doctrine": DOCTRINE})

    # ---- BARE-PATH VERTICAL INDEX (consolidation map) ----
    # GET /api/a11oy/v1/vert/{vertical} -> honest summary of the consolidated
    # vertical: which legacy organ it absorbed, its observed feed state, and the
    # doctrine. This makes the bare path genuinely meaningful (not a stub) and
    # lets readiness probes confirm consolidation at the canonical vertical URL.
    _VERT_CONSOLIDATION = {
        "defense":    {"label": "Defense / Gov",     "absorbed": None,
                       "sources": ["CISA KEV", "NVD CVE", "UDS mesh bridge"],
                       "routes": ["/feed", "/kpi", "/govern", "/ledger", "/roi"]},
        "finance":    {"label": "Finance",           "absorbed": None,
                       "sources": ["Polygon.io (official, key-gated)", "Yahoo v8 (unofficial fallback)", "Coinbase", "Frankfurter ECB FX", "fintech CVE"],
                       "routes": ["/feed", "/govern", "/ledger", "/roi"]},
        "legal":      {"label": "Legal",             "absorbed": "Counsel",
                       "sources": ["Federal Register", "CourtListener"],
                       "routes": ["/feed", "/govern", "/ledger", "/roi"]},
        "cyber":      {"label": "Enterprise / Cyber", "absorbed": "Sentra",
                       "sources": ["CISA KEV", "NVD CVE", "GitHub/HF activity"],
                       "routes": ["/feed", "/govern", "/ledger", "/roi"]},
        "realestate": {"label": "Real Estate",       "absorbed": "Terra",
                       "sources": ["NYC HPD litigations", "NYC DOB violations", "Treasury rates"],
                       "routes": ["/feed", "/govern", "/ledger", "/roi"]},
    }

    @app.get(base + "/{vertical}", include_in_schema=False)
    async def _vert_index(vertical: str):
        meta = _VERT_CONSOLIDATION.get(vertical)
        if meta is None:
            return JSONResponse({"error": "unknown vertical",
                                 "verticals": list(_VERT_CONSOLIDATION.keys())}, status_code=404)
        absorbed = meta["absorbed"]
        feed_state = _vertical_feed_state(vertical)
        return JSONResponse({
            "vertical": vertical,
            "label": meta["label"],
            "live": feed_state["live"],
            "feed_state": feed_state,
            "consolidated_from": absorbed,
            "consolidation_note": (f"Legacy '{absorbed}' organ consolidated into a11oy vertical '{vertical}'."
                                   if absorbed else f"Native a11oy vertical '{vertical}'."),
            "sources": meta["sources"],
            "sources_cited": cited_leaders(vertical),
            "routes": [base + "/" + vertical + r for r in meta["routes"]],
            "doctrine": DOCTRINE,
        })

    # Move the routes we just appended to the FRONT so they win ordered matching
    # ahead of the proxy + SPA catch-all. Different path namespace (/v1/vert)
    # from dev1 (/v1/wow), so order between the two blocks does not matter.
    _moved = -1
    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        _moved = len(_new)
    except Exception as _re_e:  # never break the Space
        import sys as _vsys
        print(f"[a11oy] dev2 vertical route reorder failed (non-fatal): {_re_e!r}", file=_vsys.stderr)
    return {"mounted": base, "verticals": 5, "khipu": _HAS_KHIPU, "dsse": _HAS_DSSE,
            "gateway": _HAS_GW, "moved": _moved}
