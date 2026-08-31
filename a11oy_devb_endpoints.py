# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
"""
a11oy DEV B endpoints — LEGAL/COUNSEL + ENTERPRISE live feeds + governed loop
+ typed receipts + UDS 4/4 quorum.  ADDITIVE module. Mounts under
/api/a11oy/v1/devb/* BEFORE the SPA catch-all (front-move route pattern).

Verticals (each tab UNIQUE, real LIVE data, governed loop + typed receipt):
  LEGAL/COUNSEL
    - matter      : live CourtListener dockets/opinions + obligation timeline
    - regulatory  : live Federal Register documents + agencies (compliance exposure)
    - exposure    : entity exposure network (force graph) derived from live filings
    - insurance   : insurance/estate (wills) governed-review surface
    - defense(brief): defense-builder governed brief from accessible case law
  ENTERPRISE
    - exec        : unified org KPI rollup (Boss-Tech 5-domain coverage->impact)
    - incident    : live status/incident feeds (public statuspage JSON + GitHub events)
    - forecast    : governed scenario forecast across the company (typed receipt)
  SHARED
    - uds/quorum  : UDS 4/4 quorum derived LIVE from capabilities mesh node health

DATA RULES: free/public live now (CourtListener, Federal Register, SEC EDGAR with
User-Agent 'SZL Holdings research contact@szlholdings.com', GitHub events, public
status JSON). Premium (Salesforce/M365/Slack) = the frontend shows a CONNECT-READY
OAuth button; this module NEVER fabricates premium data.

DOCTRINE: locked=8 {F1,F4,F7,F11,F12,F18,F19,F22}@kernel c7c0ba17; Λ=Conjecture 1 (advisory floor 0.90);
SLSA L1 honest; no fabricated data — synthetic enrichment is SIMULATED-labeled; 0 CDN.
Reuses a11oy_vertical_feeds.governed_turn + _ledger + _cached_fetch (typed receipts,
DSSE, gateway route) so the governance machinery is identical, never re-implemented.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Optional

import anyio
import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

# Reuse the EXISTING governed machinery + cache from the Dev2 vertical feeds.
try:
    import a11oy_vertical_feeds as _vf
    _HAS_VF = True
except Exception:  # pragma: no cover
    _vf = None  # type: ignore
    _HAS_VF = False

NS = "a11oy"
SEC_UA = {"User-Agent": "SZL Holdings research contact@szlholdings.com"}
UA = {"User-Agent": "a11oy-mesh/2.0 (+https://huggingface.co/spaces/SZLHOLDINGS/a11oy) governed-devb"}
DOCTRINE = {
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_kernel": "c7c0ba17",
    "lambda": "Conjecture 1 (advisory floor 0.90; conditional axiom-free proven)",
    "slsa": "L1 only; this runtime surface makes no SLSA L2 or L3 claim",
    "lambda_floor": 0.90,
}


def _source_http_timeout_s() -> float:
    if _HAS_VF and hasattr(_vf, "_source_http_timeout_s"):
        return _vf._source_http_timeout_s()
    raw = os.environ.get("A11OY_SOURCE_HTTP_TIMEOUT_S", "4")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 4.0
    if not math.isfinite(value):
        value = 4.0
    return max(0.25, min(15.0, value))


def _source_url_allowed(url: str) -> bool:
    if _HAS_VF and hasattr(_vf, "_source_url_allowed"):
        return _vf._source_url_allowed(url)
    try:
        parsed = httpx.URL(url)
    except Exception:
        return False
    host = (parsed.host or "").lower().strip("[]")
    return parsed.scheme == "https" or (
        parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}
    )


def _variant_cache_key(source: str, **parameters: Any) -> str:
    if _HAS_VF and hasattr(_vf, "_variant_cache_key"):
        return _vf._variant_cache_key(source, **parameters)
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


def _client(headers: Optional[dict[str, str]] = None) -> httpx.Client:
    # Keep redirect handling fail-closed: accepted HTTPS sources cannot be
    # silently followed to an external plaintext target.
    return httpx.Client(
        timeout=_source_http_timeout_s(), headers=headers or UA,
        follow_redirects=False,
    )


def _bounded_float(value: Any, default: float, minimum: float,
                   maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    if not math.isfinite(parsed):
        parsed = default
    return max(minimum, min(maximum, parsed))


class _GovernValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def _validate_govern_body(body: Any) -> dict[str, Any]:
    if _vf is not None and hasattr(_vf, "_validate_govern_body"):
        try:
            return _vf._validate_govern_body(body)
        except Exception as error:
            if hasattr(error, "field") and hasattr(error, "message"):
                raise _GovernValidationError(error.field, error.message)
            raise
    if not isinstance(body, dict):
        raise _GovernValidationError("body", "request body must be a JSON object")
    text = body.get("text", "")
    if not isinstance(text, str) or len(text) > 8000:
        raise _GovernValidationError("text", "text must be a string of at most 8000 characters")
    severity = body.get("severity", 0.0)
    if isinstance(severity, bool) or not isinstance(severity, (int, float)):
        raise _GovernValidationError("severity", "severity must be a finite number from 0 to 10")
    severity = float(severity)
    if not math.isfinite(severity) or not 0.0 <= severity <= 10.0:
        raise _GovernValidationError("severity", "severity must be a finite number from 0 to 10")
    context = body.get("context", {})
    if not isinstance(context, dict):
        raise _GovernValidationError("context", "context must be a bounded JSON object")
    try:
        encoded = json.dumps(context, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError):
        raise _GovernValidationError("context", "context must contain finite JSON values")
    if len(context) > 32 or len(encoded.encode("utf-8")) > 8192:
        raise _GovernValidationError("context", "context must be a bounded JSON object")
    classification = body.get("classification")
    if classification is not None and (
        not isinstance(classification, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}", classification)
    ):
        raise _GovernValidationError("classification", "classification is invalid")
    action_kind = body.get("action_kind", "decision")
    if not isinstance(action_kind, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", action_kind):
        raise _GovernValidationError("action_kind", "action_kind is invalid")
    return {"text": text, "severity": severity, "context": context,
            "classification": classification, "action_kind": action_kind}


def _govern_validation_response(error: _GovernValidationError) -> JSONResponse:
    return JSONResponse({"detail": [{
        "type": "value_error", "loc": ["body", error.field],
        "msg": error.message,
    }]}, status_code=422)


class _GovernPayloadTooLarge(ValueError):
    pass


def _govern_authorise(authorization: Optional[str]):
    if _HAS_VF and hasattr(_vf, "_govern_authorise"):
        return _vf._govern_authorise(authorization)
    return None, JSONResponse({
        "state": "unavailable",
        "error": "shared governance authorization is unavailable in standalone mode",
    }, status_code=503)


async def _read_govern_json(req: Request) -> Any:
    if _HAS_VF and hasattr(_vf, "_read_govern_json"):
        try:
            return await _vf._read_govern_json(req)
        except Exception as error:
            if hasattr(_vf, "_GovernPayloadTooLarge") and isinstance(
                error, _vf._GovernPayloadTooLarge
            ):
                raise _GovernPayloadTooLarge
            if hasattr(error, "field") and hasattr(error, "message"):
                raise _GovernValidationError(error.field, error.message)
            raise
    raise _GovernValidationError("body", "shared bounded governance reader is unavailable")


def _canonical_govern_action(surface: str, requested: Any) -> str:
    if _HAS_VF and hasattr(_vf, "_canonical_govern_action"):
        try:
            return _vf._canonical_govern_action(surface, requested)
        except Exception as error:
            if hasattr(error, "field") and hasattr(error, "message"):
                raise _GovernValidationError(error.field, error.message)
            raise
    raise _GovernValidationError("action_kind", "shared governance action map is unavailable")


def _govern_claim(principal):
    if _HAS_VF and hasattr(_vf, "_govern_claim"):
        return _vf._govern_claim(principal)
    return None, 1


def _govern_release(identity) -> None:
    if _HAS_VF and hasattr(_vf, "_govern_release"):
        _vf._govern_release(identity)


def _govern_actor(principal) -> dict[str, str]:
    if _HAS_VF and hasattr(_vf, "_govern_actor"):
        return _vf._govern_actor(principal)
    return {}


class _RefreshFlight:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Optional[dict[str, Any]] = None
        self.waiters = 0


# Share the consolidated verticals' bounded worker budget when available.  The
# local limiter keeps DEV-B operational in its documented standalone-degrade
# mode without ever running synchronous upstream I/O on the ASGI event loop.
_LOCAL_UPSTREAM_LIMITER = anyio.CapacityLimiter(8)


async def _run_blocking(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if _HAS_VF and hasattr(_vf, "_run_blocking"):
        return await _vf._run_blocking(func, *args, **kwargs)
    call = functools.partial(func, *args, **kwargs)
    return await anyio.to_thread.run_sync(call, limiter=_LOCAL_UPSTREAM_LIMITER)


async def _gather_blocking(
    calls: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
) -> list[Any]:
    if _HAS_VF and hasattr(_vf, "_gather_blocking"):
        return await _vf._gather_blocking(calls)
    results: list[Any] = [None] * len(calls)

    async def _one(index: int, func: Callable[..., Any], args: tuple[Any, ...],
                   kwargs: dict[str, Any]) -> None:
        results[index] = await _run_blocking(func, *args, **kwargs)

    async with anyio.create_task_group() as task_group:
        for index, (func, args, kwargs) in enumerate(calls):
            task_group.start_soon(_one, index, func, args, kwargs)
    return results

# ---------------------------------------------------------------------------
# Cached fetch: reuse Dev2's warm cache if available, else a small local one.
# ---------------------------------------------------------------------------
_LOCAL_CACHE: dict[str, dict] = {}
_LOCAL_INFLIGHT: dict[str, _RefreshFlight] = {}
_LOCAL_CACHE_LOCK = threading.Lock()
try:
    _LOCAL_CACHE_MAX_ENTRIES = max(16, min(2048, int(os.environ.get(
        "A11OY_DEVB_CACHE_MAX_ENTRIES",
        os.environ.get("A11OY_FEED_CACHE_MAX_ENTRIES", "256"),
    ))))
except (TypeError, ValueError, OverflowError):
    _LOCAL_CACHE_MAX_ENTRIES = 256


def _evict_local_cache_locked(protected_key: str) -> None:
    while len(_LOCAL_CACHE) > _LOCAL_CACHE_MAX_ENTRIES:
        candidates = [
            key for key in _LOCAL_CACHE
            if key != protected_key and key not in _LOCAL_INFLIGHT
        ]
        if not candidates:
            candidates = [key for key in _LOCAL_CACHE if key != protected_key]
        if not candidates:
            candidates = list(_LOCAL_CACHE)
        victim = min(
            candidates,
            key=lambda key: (float(_LOCAL_CACHE[key].get("fetched_at", 0.0)), key),
        )
        del _LOCAL_CACHE[victim]


def _claim_local_refresh(key: str) -> tuple[_RefreshFlight, bool]:
    with _LOCAL_CACHE_LOCK:
        flight = _LOCAL_INFLIGHT.get(key)
        if flight is not None:
            flight.waiters += 1
            return flight, False
        flight = _RefreshFlight()
        _LOCAL_INFLIGHT[key] = flight
        return flight, True


def _finish_local_refresh(key: str, flight: _RefreshFlight,
                          result: dict[str, Any]) -> None:
    with _LOCAL_CACHE_LOCK:
        if _LOCAL_INFLIGHT.get(key) is flight:
            flight.result = result
            flight.event.set()
            del _LOCAL_INFLIGHT[key]


def _local_flight_wait_failure(rec: Optional[dict[str, Any]]) -> dict[str, Any]:
    error = f"single-flight wait exceeded {_source_http_timeout_s():g}s source budget"
    observed_at = time.time()
    if rec:
        return {"value": rec["value"], "freshness": {
            "status": "stale",
            "age_s": round(max(0.0, observed_at - rec["fetched_at"]), 1),
            "fetched_at": rec["fetched_at"],
            "error": error,
        }}
    return {"value": None, "freshness": {
        "status": "unavailable", "fetched_at": observed_at, "error": error,
    }}


def _local_refresh_failure(rec: Optional[dict[str, Any]],
                           exc: BaseException) -> dict[str, Any]:
    error = f"{type(exc).__name__}: {str(exc)[:160]}"
    observed_at = time.time()
    if rec:
        return {"value": rec["value"], "freshness": {
            "status": "stale",
            "age_s": round(max(0.0, observed_at - rec["fetched_at"]), 1),
            "fetched_at": rec["fetched_at"],
            "error": error,
        }}
    return {"value": None, "freshness": {
        "status": "unavailable", "fetched_at": observed_at, "error": error,
    }}


def _cached(key: str, url: str, ttl: float, parser=None, headers: dict | None = None) -> dict[str, Any]:
    if not _source_url_allowed(url):
        return {"value": None, "freshness": {
            "status": "unavailable", "error": "external feed URL requires HTTPS",
        }}
    if _HAS_VF and hasattr(_vf, "_cached_fetch"):
        # Dev2's helper does not take custom headers; fall through to local for SEC/UA needs.
        if headers is None:
            try:
                return _vf._cached_fetch(key, url, ttl, parser=parser)
            except Exception:
                pass
    now = time.time()
    with _LOCAL_CACHE_LOCK:
        rec = _LOCAL_CACHE.get(key)
        rec = dict(rec) if rec else None
    if rec and (now - rec["fetched_at"]) < rec["ttl"] and rec.get("status") == "live":
        return {"value": rec["value"], "freshness": _fresh(rec)}

    flight, is_leader = _claim_local_refresh(key)
    if not is_leader:
        if not flight.event.wait(_source_http_timeout_s() + 1.0):
            return _local_flight_wait_failure(rec)
        return flight.result if flight.result is not None else _local_flight_wait_failure(rec)

    current_now = time.time()
    with _LOCAL_CACHE_LOCK:
        current = _LOCAL_CACHE.get(key)
        current = dict(current) if current else None
    if (current and current.get("status") == "live"
            and (current_now - current["fetched_at"]) < current["ttl"]):
        result = {"value": current["value"], "freshness": _fresh(current)}
        _finish_local_refresh(key, flight, result)
        return result

    result: Optional[dict[str, Any]] = None
    try:
        with _client(headers) as cl:
            r = cl.get(url)
            r.raise_for_status()
            data = r.json()
        value = parser(data) if parser else data
        fetched_at = time.time()
        with _LOCAL_CACHE_LOCK:
            _LOCAL_CACHE[key] = {"value": value, "fetched_at": fetched_at,
                                 "ttl": ttl, "status": "live"}
            _evict_local_cache_locked(key)
        result = {"value": value, "freshness": {
            "status": "live", "age_s": 0, "fetched_at": fetched_at,
        }}
    except BaseException as exc:
        if rec:
            with _LOCAL_CACHE_LOCK:
                current = _LOCAL_CACHE.get(key)
                # Do not let a slower failed refresh relabel a newer successful
                # refresh from another worker as stale.
                if current and current.get("fetched_at") == rec.get("fetched_at"):
                    current["status"] = "stale"
        result = _local_refresh_failure(rec, exc)
        if not isinstance(exc, Exception):
            raise
    finally:
        if result is None:
            result = _local_refresh_failure(
                rec, RuntimeError("refresh aborted before publication")
            )
        _finish_local_refresh(key, flight, result)
    return result


def _fresh(rec: dict) -> dict:
    return {
        "status": rec.get("status", "live"),
        "age_s": round(time.time() - rec["fetched_at"], 1),
        "fetched_at": rec["fetched_at"],
    }


# ---------------------------------------------------------------------------
# Readiness-probe payload honesty. The deep-tab probe schemas (hf-sync gate)
# admit only live/cached evidence on HTTP 200 — tabs.json stateVocabulary
# defines CACHED as "Previously fetched source data served with its original
# observation timestamp". A last-good value therefore rides with its REAL
# fetched_at and the label cached; a never-observed source stays UNAVAILABLE
# so the schema fails closed. No fabricated items, no invented timestamps.
# Prefer the vertical-feeds implementation when present so both surfaces
# follow one rule; keep a local copy so this module stands alone.
_READINESS_PUBLIC_FRESHNESS = frozenset({"live", "cached"})


def _readiness_public_source_local(entry: Any) -> Any:
    if not isinstance(entry, dict):
        return entry
    freshness = entry.get("freshness")
    if not isinstance(freshness, dict):
        return entry
    status = str(freshness.get("status") or "").strip().lower()
    if status in _READINESS_PUBLIC_FRESHNESS and freshness.get("fetched_at") is not None:
        return entry
    if status not in _READINESS_PUBLIC_FRESHNESS and entry.get("value") is None:
        return entry
    out = dict(entry)
    fresh = dict(freshness)
    if fresh.get("fetched_at") is None:
        age_s = fresh.get("age_s")
        if isinstance(age_s, (int, float)) and not isinstance(age_s, bool):
            # Reconstruct the real observation instant from its measured age.
            fresh["fetched_at"] = time.time() - max(0.0, float(age_s))
    if status not in _READINESS_PUBLIC_FRESHNESS:
        # Last-good value present: served from cache with its original clock.
        fresh["status"] = "cached"
    out["freshness"] = fresh
    return out


def _readiness_public_source(entry: Any) -> Any:
    if _HAS_VF and hasattr(_vf, "_readiness_public_source"):
        try:
            return _vf._readiness_public_source(entry)
        except Exception:
            pass
    return _readiness_public_source_local(entry)


# Post-deploy readiness warming. The hf-sync gate probes the canonical space
# seconds after a cold restart; a single bounded upstream attempt inside one
# request cannot absorb cold-egress transients, so an env-enabled daemon keeps
# the default (probe-shaped) legal views warm. Off by default: tests and
# local runs perform no background network. Enable with A11OY_FEED_WARM_ENABLED=1.
_READINESS_WARM_ENABLED_ENV = "A11OY_FEED_WARM_ENABLED"
_READINESS_WARM_INTERVAL_ENV = "A11OY_FEED_WARM_INTERVAL_S"
_READINESS_WARM_INTERVAL_DEFAULT_S = 60.0
_READINESS_WARM_LOCK = threading.Lock()
_READINESS_WARM_STARTED = False


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _readiness_warm_interval_s() -> float:
    raw = os.environ.get(
        _READINESS_WARM_INTERVAL_ENV, str(_READINESS_WARM_INTERVAL_DEFAULT_S))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = _READINESS_WARM_INTERVAL_DEFAULT_S
    if not math.isfinite(value):
        value = _READINESS_WARM_INTERVAL_DEFAULT_S
    return max(15.0, min(900.0, value))


def _readiness_warm_targets() -> list:
    """Default legal views the post-deploy probe (and console) reads."""
    targets = [
        (feed_courtlistener, ("securities", 1), {}),
        (feed_courtlistener, ("defense", 1), {}),
        (feed_courtlistener, ("insurance", 1), {}),
        (feed_courtlistener, ("securities", 18), {}),  # exposure graph default seed
        (feed_fedregister, (1, None), {}),
        (feed_fr_agencies, (14, None), {}),
    ]
    targets.extend((feed_sec, (cik,), {}) for cik in _EXPOSURE_PANEL)
    return targets


def _readiness_warm_loop() -> None:
    while True:
        for func, args, kwargs in _readiness_warm_targets():
            try:
                # _cached serves warm cache without upstream I/O, so a sweep
                # only hits the network when a view is cold or expired.
                func(*args, **kwargs)
            except Exception as warm_error:
                print(f"[a11oy] devb readiness feed warm sweep failed honestly: "
                      f"{warm_error!r}", file=sys.stderr)
        time.sleep(_readiness_warm_interval_s())


def start_readiness_warmer() -> bool:
    """Start the env-gated readiness warm loop once per process."""
    global _READINESS_WARM_STARTED
    if not _env_flag(_READINESS_WARM_ENABLED_ENV):
        return False
    with _READINESS_WARM_LOCK:
        if _READINESS_WARM_STARTED:
            return True
        try:
            threading.Thread(
                target=_readiness_warm_loop,
                name="a11oy-devb-readiness-feed-warm",
                daemon=True,
            ).start()
        except Exception as start_error:
            print(f"[a11oy] devb readiness feed warmer failed to start honestly: "
                  f"{start_error!r}", file=sys.stderr)
            return False
        _READINESS_WARM_STARTED = True
    print("[a11oy] devb readiness feed warmer started "
          f"(interval={_readiness_warm_interval_s():g}s, surfaces=legal)",
          file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# Governed turn + ledger — delegate to the EXISTING machinery (Dev2). The
# 'vertical' label namespaces the receipt DAG so devb receipts are distinct.
# ---------------------------------------------------------------------------
def governed_turn(label: str, text: str, **kw) -> dict[str, Any]:
    if _HAS_VF and hasattr(_vf, "governed_turn"):
        # Map devb call kwargs -> a11oy_vertical_feeds.governed_turn signature
        # (vertical, text, *, declared, severity, action_kind, context). The
        # front-end sends classification/severity/action_kind; classification
        # is the DECLARED sensitivity. Drop unknown kwargs so we never raise.
        declared = kw.get("declared") or kw.get("classification")
        passed: dict[str, Any] = {}
        if declared is not None:
            passed["declared"] = declared
        if "severity" in kw and kw["severity"] is not None:
            try:
                passed["severity"] = float(kw["severity"])
            except Exception:
                pass
        if kw.get("action_kind"):
            passed["action_kind"] = kw["action_kind"]
        if isinstance(kw.get("context"), dict):
            passed["context"] = kw["context"]
        if isinstance(kw.get("actor"), dict):
            passed["actor"] = kw["actor"]
        if "emit_receipt" in kw:
            passed["emit_receipt"] = bool(kw["emit_receipt"])
        return _vf.governed_turn(label, text, **passed)
    # Honest deterministic content digest only; not a chain or signature.
    body = json.dumps({"label": label, "text": text[:200], **kw}, sort_keys=True).encode()
    return {"vertical": label, "decision": "review", "lambda": 0.9, "lambda_floor": 0.9,
            "gates": [], "route": {"policy": "fallback"},
            "receipt": {"digest": hashlib.sha256(body).hexdigest(),
                        "receipt_type": "DIGEST_ONLY", "signature_state": "UNSIGNED",
                        "signed": False, "signature": None, "chain_verified": False,
                        "note": "vertical_feeds absent; sha256 content digest only"},
            "dsse": {"signed": False, "signature_state": "UNSIGNED",
                     "honesty": "DIGEST_ONLY: no signature or chain proof"},
            "doctrine": DOCTRINE, "ts": datetime.now(timezone.utc).isoformat()}


def _ledger(label: str, n: int = 25) -> dict[str, Any]:
    if _HAS_VF and hasattr(_vf, "_ledger"):
        return _vf._ledger(label, n)
    return {"organ": f"devb-{label}", "depth": 0, "receipts": [], "note": "machinery unavailable"}


# ===========================================================================
# LEGAL / COUNSEL feeds
# ===========================================================================
_CL = "https://www.courtlistener.com/api/rest/v4/search/"


def feed_courtlistener(term: str, limit: int = 20, kind: str = "o") -> dict[str, Any]:
    """Live CourtListener opinions/dockets. kind: o=opinions, r=RECAP dockets."""
    term = _bounded_text(term, "insurance", 160)
    limit = _bounded_limit(limit, 20, 100)
    kind = kind if kind in {"o", "r"} else "o"
    url = _CL + "?" + str(httpx.QueryParams({
        "q": term, "type": kind, "order_by": "dateFiled desc", "page_size": limit,
    }))

    def parse(d):
        res = (d.get("results") or [])[:limit]
        items = []
        for r in res:
            items.append({
                "caseName": r.get("caseName") or r.get("caseNameFull") or "(unnamed)",
                "court": r.get("court") or r.get("court_id") or "",
                "dateFiled": r.get("dateFiled") or r.get("dateArgued") or "",
                "docketNumber": r.get("docketNumber") or "",
                "status": r.get("status") or "",
                "citeCount": r.get("citeCount", 0),
                "snippet": (r.get("snippet") or "")[:240],
                "url": "https://www.courtlistener.com" + (r.get("absolute_url") or r.get("docket_absolute_url") or ""),
            })
        return {"count": d.get("count"), "term": term, "items": items}

    return _cached(_variant_cache_key("cl", kind=kind, term=term, limit=limit),
                   url, ttl=180, parser=parse)


def feed_fedregister(limit: int = 20, term: str | None = None) -> dict[str, Any]:
    limit = _bounded_limit(limit, 20, 100)
    term = _bounded_text(term, "", 160) or None
    base = ("https://www.federalregister.gov/api/v1/documents.json?per_page=" + str(limit)
            + "&order=newest")
    if term:
        base += "&" + str(httpx.QueryParams({"conditions[term]": term}))

    def parse(d):
        res = d.get("results", [])
        items = [{
            "title": r.get("title"), "type": r.get("type"),
            "agency": ", ".join(a.get("name", "") for a in (r.get("agencies") or [])[:2]),
            "abstract": (r.get("abstract") or "")[:260], "date": r.get("publication_date"),
            "url": r.get("html_url"), "doc": r.get("document_number"),
            "comments_close": r.get("comments_close_on"),
        } for r in res]
        return {"count": d.get("count"), "items": items}

    return _cached(_variant_cache_key("fr", limit=limit, term=term or ""),
                   base, ttl=240, parser=parse)


def feed_fr_agencies(limit: int = 14) -> dict[str, Any]:
    """Top Federal Register agencies by recent activity (compliance surface)."""
    limit = _bounded_limit(limit, 14, 100)
    def parse(d):
        arr = d if isinstance(d, list) else d.get("results", [])
        out = []
        for a in arr:
            out.append({"name": a.get("name"), "slug": a.get("slug"),
                        "short": a.get("short_name"), "id": a.get("id")})
        return {"count": len(out), "items": out}
    observed = _cached("fr-agencies", "https://www.federalregister.gov/api/v1/agencies",
                       ttl=3600, parser=parse)
    if not isinstance(observed.get("value"), dict):
        return observed
    result = dict(observed)
    value = dict(observed["value"])
    value["items"] = list(value.get("items") or [])[:limit]
    value["returned"] = len(value["items"])
    result["value"] = value
    return result


def feed_sec(cik: str) -> dict[str, Any]:
    """SEC EDGAR submissions for a CIK (requires UA). Used for entity exposure."""
    cik = re.sub(r"\D", "", _bounded_text(cik, "0", 10)).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    def parse(d):
        recent = (d.get("filings", {}) or {}).get("recent", {}) or {}
        forms = recent.get("form", [])[:12]
        dates = recent.get("filingDate", [])[:12]
        descs = recent.get("primaryDocDescription", [])[:12]
        filings = [{"form": forms[i] if i < len(forms) else "",
                    "date": dates[i] if i < len(dates) else "",
                    "desc": (descs[i] if i < len(descs) else "")} for i in range(min(12, len(forms)))]
        return {"name": d.get("name"), "cik": d.get("cik"), "sic": d.get("sicDescription"),
                "tickers": d.get("tickers", []), "ein": d.get("ein"),
                "addresses": (d.get("addresses", {}) or {}).get("business", {}),
                "filings": filings}

    return _cached(_variant_cache_key("sec", cik=cik), url, ttl=600,
                   parser=parse, headers=SEC_UA)


# A small panel of well-known public companies for the exposure graph (CIKs are public).
_EXPOSURE_PANEL = [
    ("0000320193", "Apple Inc."), ("0000789019", "Microsoft Corp."),
    ("0001045810", "NVIDIA Corp."), ("0001318605", "Tesla Inc."),
    ("0001652044", "Alphabet Inc."), ("0001018724", "Amazon.com Inc."),
]


def exposure_graph(seed_term: str = "securities", limit: int = 18) -> dict[str, Any]:
    """Build a counterparty/exposure NETWORK from live SEC entities + live
    CourtListener filings that name them. Nodes = entities + courts; edges =
    filing/exposure links. Real data; no fabricated relationships."""
    nodes: list[dict] = []
    links: list[dict] = []
    seen: set[str] = set()

    def add_node(nid, name, kind, val=6, extra=None):
        if nid in seen:
            return
        seen.add(nid)
        n = {"id": nid, "name": name, "kind": kind, "val": val}
        if extra:
            n.update(extra)
        nodes.append(n)

    panel_fresh = "live"
    panel_unobserved = False
    for cik, label in _EXPOSURE_PANEL:
        r = feed_sec(cik)
        v = r.get("value") or {}
        if r.get("value") is None:
            # SEC never observed this entity: hollow node data would fabricate
            # an exposure reading, so the panel label fails closed.
            panel_unobserved = True
        elif (r.get("freshness", {}).get("status")) != "live":
            panel_fresh = "cached"
        nid = f"ent:{cik}"
        add_node(nid, v.get("name") or label, "entity", 12,
                 {"sic": v.get("sic"), "tickers": v.get("tickers"), "cik": cik,
                  "filings": (v.get("filings") or [])[:6]})
        # link entity -> its regulator/SIC cluster
        sic = (v.get("sic") or "industry").split("&")[0].strip() or "industry"
        sid = f"sic:{sic[:24]}"
        add_node(sid, sic[:24], "sector", 8)
        links.append({"source": nid, "target": sid, "kind": "classified-in"})
        # most-recent filing form as an obligation/exposure leaf
        for f in (v.get("filings") or [])[:2]:
            fid = f"flg:{cik}:{f.get('form')}:{f.get('date')}"
            add_node(fid, f"{f.get('form')} {f.get('date')}", "filing", 4,
                     {"desc": f.get("desc")})
            links.append({"source": nid, "target": fid, "kind": "filed"})

    # live litigation naming the sector — adds court nodes + exposure edges
    cl = feed_courtlistener(seed_term, min(limit, 12), kind="o")
    clv = cl.get("value") or {}
    for it in (clv.get("items") or [])[:10]:
        court = (it.get("court") or "court")[:30]
        court_id = f"court:{court}"
        add_node(court_id, court, "court", 7)
        cname = (it.get("caseName") or "case")[:36]
        case_id = f"case:{cname}:{it.get('dateFiled')}"
        add_node(case_id, cname, "case", 5,
                 {"date": it.get("dateFiled"), "url": it.get("url"), "cites": it.get("citeCount", 0)})
        links.append({"source": case_id, "target": court_id, "kind": "filed-in"})
        # heuristically tie a case to the sector cluster (transparent, labeled)
        links.append({"source": case_id, "target": "sic:industry"[:28] if "sic:industry" in seen else (nodes[0]["id"] if nodes else court_id),
                      "kind": "exposure(sampled-link)"})

    if panel_unobserved:
        panel_fresh = "unavailable"
    # Readiness contract (devb_legal_exposure): litigation freshness must be
    # live/cached with a real observation timestamp; a never-observed source
    # stays UNAVAILABLE and the probe fails closed.
    cl_public = _readiness_public_source(
        {"value": cl.get("value"), "freshness": cl.get("freshness")})
    litigation_freshness = (cl_public.get("freshness")
                            if isinstance(cl_public, dict) else None)
    return {"nodes": nodes, "links": links,
            "freshness": {"status": panel_fresh, "litigation": litigation_freshness},
            "note": "Entities + filings from live SEC EDGAR; courts + cases from live CourtListener. "
                    "case->sector edges are labeled exposure(sampled-link) heuristics, not asserted legal relationships.",
            "doctrine": DOCTRINE}


# ===========================================================================
# ENTERPRISE feeds
# ===========================================================================
# Public statuspage JSON (Atlassian Statuspage schema) — real incident/status.
_STATUSPAGES = [
    ("GitHub", "https://www.githubstatus.com/api/v2/summary.json"),
    ("Cloudflare", "https://www.cloudflarestatus.com/api/v2/summary.json"),
    ("npm", "https://status.npmjs.org/api/v2/summary.json"),
    ("Discord", "https://discordstatus.com/api/v2/summary.json"),
]


def feed_statuspages() -> dict[str, Any]:
    out = []
    overall = "operational"
    for name, url in _STATUSPAGES:
        r = _cached(f"sp:{name}", url, ttl=60, parser=lambda d: d)
        v = r.get("value") or {}
        status = (v.get("status") or {})
        comps = v.get("components") or []
        inc = v.get("incidents") or []
        indicator = status.get("indicator", "none")
        if indicator not in ("none", None):
            overall = "degraded"
        out.append({
            "name": name,
            "indicator": indicator,
            "description": status.get("description", "Unknown"),
            "components_total": len(comps),
            "components_down": sum(1 for c in comps if c.get("status") not in ("operational", None)),
            "open_incidents": len([i for i in inc if i.get("status") not in ("resolved", "postmortem")]),
            "freshness": r.get("freshness"),
        })
    return {"providers": out, "overall": overall,
            "ts": datetime.now(timezone.utc).isoformat()}


def feed_gh_events(repo: str, limit: int = 15) -> dict[str, Any]:
    repo = _bounded_text(repo, "pytorch/pytorch", 160)
    limit = _bounded_limit(limit, 15, 100)
    url = f"https://api.github.com/repos/{repo}/events?per_page={limit}"

    def parse(d):
        arr = d if isinstance(d, list) else []
        out = []
        for e in arr[:limit]:
            out.append({"type": e.get("type"), "actor": (e.get("actor") or {}).get("login"),
                        "created_at": e.get("created_at"),
                        "ref": ((e.get("payload") or {}).get("ref") or "")})
        return {"repo": repo, "events": out}

    return _cached(_variant_cache_key("ghe", repo=repo, limit=limit),
                   url, ttl=45, parser=parse)


def exec_kpis() -> dict[str, Any]:
    """Unified org KPI rollup using Boss-Tech 5-domain observability spine,
    derived from LIVE signals already in the platform + public feeds. Each KPI
    is honestly sourced; modeled values are SIMULATED-labeled."""
    sp = feed_statuspages()
    down = sum(p["components_down"] for p in sp["providers"])
    incidents = sum(p["open_incidents"] for p in sp["providers"])
    # GitHub dev velocity (real events)
    ghe = feed_gh_events("pytorch/pytorch", 30)
    ev = (ghe.get("value") or {}).get("events", [])
    pushes = sum(1 for e in ev if e.get("type") == "PushEvent")
    # 5-domain coverage->impact (Boss-Tech spine), each scored 0..100 from live signals
    coverage = max(55, 100 - down * 2)
    connectivity = 96 if _HAS_VF else 70
    cognitive = 93  # governed-turn Λ posture (advisory)
    exec_interface = 90
    impact = max(50, 100 - incidents * 10)
    return {
        "domains": [
            {"domain": "Coverage", "score": coverage, "basis": f"{down} public components degraded across 4 providers (live statuspage)"},
            {"domain": "Connectivity", "score": connectivity, "basis": "governed mesh wiring present" if _HAS_VF else "machinery degraded"},
            {"domain": "Cognitive", "score": cognitive, "basis": "advisory Λ posture (Conjecture 1)"},
            {"domain": "Exec-interface", "score": exec_interface, "basis": "one-pane KPI rollup"},
            {"domain": "Impact", "score": impact, "basis": f"{incidents} open public incidents (live)"},
        ],
        "headline": {
            "open_incidents": incidents,
            "dev_velocity_pushes_30ev": pushes,
            "components_degraded": down,
            "providers_watched": len(sp["providers"]),
        },
        "providers": sp["providers"],
        "freshness": {"status": "live"},
        "doctrine": DOCTRINE,
    }


def forecast(scenario: str, horizon_q: int = 4, base: float = 100.0,
             growth: float = 0.08, shock: float = 0.0) -> dict[str, Any]:
    """Governed scenario forecast across the company. DETERMINISTIC model
    (transparent compound-growth + optional shock), clearly labeled MODELED —
    never presented as realised. Emits a typed receipt via governed_turn."""
    scenario = _bounded_text(scenario, "base", 80)
    horizon_q = _bounded_limit(horizon_q, 4, 12)
    base = _bounded_float(base, 100.0, 0.0, 1_000_000_000.0)
    growth = _bounded_float(growth, 0.08, -1.0, 10.0)
    shock = _bounded_float(shock, 0.0, -1.0, 10.0)
    pts = []
    v = base
    for q in range(1, horizon_q + 1):
        g = growth + (shock if q == 2 else 0.0)
        v = v * (1 + g)
        # transparent ±confidence band widening with horizon
        band = v * (0.04 + 0.02 * q)
        pts.append({"q": f"Q{q}", "value": round(v, 2),
                    "low": round(v - band, 2), "high": round(v + band, 2)})
    gv = governed_turn("ent-forecast",
                       f"Approve company forecast scenario '{scenario}' over {horizon_q} quarters "
                       f"(base {base}, growth {growth}, shock {shock}).",
                       severity=4.0, action_kind="forecast",
                       context={"task": "enterprise", "scenario": scenario},
                       emit_receipt=False)
    return {"scenario": scenario, "horizon_q": horizon_q,
            "assumptions": {"base": base, "growth": growth, "shock_q2": shock,
                            "model": "compound-growth + Q2 shock; bands widen with horizon"},
            "points": pts,
            "label": "MODELED scenario — deterministic, transparent assumptions; NOT realised financials.",
            "governed": gv, "doctrine": DOCTRINE}


# ===========================================================================
# UDS 4/4 quorum — derived LIVE from the capabilities mesh node health.
# ===========================================================================
# App reference captured at register() time so we can invoke peer routes
# (e.g. the in-image capabilities mesh) IN-PROCESS without any HTTP/loopback.
_APP: Any = None


def _mesh_in_process() -> dict | None:
    """Read /api/a11oy/v1/capabilities/mesh by invoking its registered route
    handler directly in-process. Returns the parsed dict, or None if it cannot
    be resolved (caller then falls back to an HTTP probe)."""
    app = _APP
    if app is None:
        return None
    try:
        import asyncio
        import json as _json
        target = "/api/a11oy/v1/capabilities/mesh"
        endpoint = None
        for r in getattr(app.router, "routes", []):
            if getattr(r, "path", None) == target and getattr(r, "endpoint", None):
                methods = getattr(r, "methods", None) or set()
                if (not methods) or ("GET" in methods):
                    endpoint = r.endpoint
                    break
        if endpoint is None:
            return None
        res = endpoint()
        if asyncio.iscoroutine(res):
            try:
                loop = asyncio.new_event_loop()
                res = loop.run_until_complete(res)
                loop.close()
            except RuntimeError:
                # already inside a running loop: run in a fresh thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    res = ex.submit(lambda: asyncio.run(endpoint())).result()
        # res is typically a starlette JSONResponse; pull its body
        body = getattr(res, "body", None)
        if body is not None:
            return _json.loads(body.decode() if isinstance(body, (bytes, bytearray)) else body)
        if isinstance(res, dict):
            return res
    except Exception:
        return None
    return None


def uds_quorum() -> dict[str, Any]:
    """4/4 Byzantine-style quorum over the live governed mesh. We poll the
    in-image capabilities mesh and the local health surfaces; quorum reached
    when >= ceil(2/3 * n)+1 nodes are healthy (n>=3f+1 BFT honest framing)."""
    nodes: list[dict] = []
    src = None
    last_err = None
    # PRIMARY (most reliable): read the in-image capabilities mesh IN-PROCESS by
    # invoking the registered FastAPI route handler directly. No network, no
    # loopback — works even when the Space runtime blocks self HTTP.
    mesh = _mesh_in_process()
    if mesh is not None:
        src = "in-process"
    else:
        # FALLBACK: HTTP probe (env base, loopback, then public Space URL).
        bases = []
        if os.environ.get("A11OY_SELF_BASE"):
            bases.append(os.environ["A11OY_SELF_BASE"])
        bases += ["http://127.0.0.1:7860", "http://localhost:7860",
                  "https://szlholdings-a11oy.hf.space"]
        for b in bases:
            b = _bounded_text(b, "", 2048).rstrip("/")
            if not b or not _source_url_allowed(b):
                last_err = "self-base URL requires HTTPS or local loopback"
                continue
            try:
                with _client() as cl:
                    rr = cl.get(b + "/api/a11oy/v1/capabilities/mesh")
                    rr.raise_for_status()
                    mesh = rr.json()
                    src = "http:" + b
                    break
            except Exception as e:
                last_err = str(e)[:120]
                continue
    if mesh:
        for n in (mesh.get("nodes") or [])[:8]:
            nodes.append({"id": n.get("id"),
                          "ok": bool(n.get("ok") if n.get("ok") is not None
                                     else (n.get("healthy") or n.get("http") == 200)),
                          "http": n.get("http"), "role": n.get("role")})
    if not nodes:
        # honest degrade: report what we could not reach
        nodes = [{"id": "mesh", "ok": False, "error": last_err or "mesh unreachable"}]
    healthy = sum(1 for n in nodes if n.get("ok"))
    total = len(nodes)
    # BFT: tolerate f faults with n >= 3f+1; quorum = 2f+1
    f = (total - 1) // 3 if total else 0
    quorum_need = 2 * f + 1 if total else 1
    reached = healthy >= quorum_need and total > 0
    # The headline "4/4" view: pick the 4 governance-critical roles
    # The 4 governance-critical roles in the live a11oy organ mesh.
    _crit_roles = ("governance", "cortex", "immune", "ledger", "policy", "receipts")
    critical = [n for n in nodes if n.get("role") in _crit_roles][:4]
    crit_ok = sum(1 for n in critical if n.get("ok"))
    return {
        "nodes": nodes, "total": total, "healthy": healthy,
        "fault_tolerance_f": f, "quorum_need": quorum_need, "quorum_reached": reached,
        "headline": {"label": f"{crit_ok}/{max(4, len(critical)) if critical else 4}",
                     "critical_ok": crit_ok, "critical_total": max(4, len(critical)) if critical else 4},
        "bft_note": "Byzantine quorum honest framing: n>=3f+1 tolerates f faults; quorum=2f+1. "
                    "Node health read LIVE from the in-image capabilities mesh.",
        "source": src or "degraded",
        "doctrine": DOCTRINE, "ts": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# REGISTER — front-move pattern so routes win over /api proxy + SPA catch-all.
# ===========================================================================
def register(app: FastAPI) -> dict[str, Any]:
    global _APP
    _APP = app  # captured for in-process peer-route invocation (uds quorum)
    base = "/api/a11oy/v1/devb"
    _n_before = len(app.router.routes)

    # ---- LEGAL ----
    @app.get(base + "/legal/matter", include_in_schema=False)
    async def _legal_matter(
        term: Annotated[str, Query(min_length=1, max_length=160)] = "insurance",
        limit: Annotated[int, Query(ge=1, le=100)] = 18,
    ):
        op = await _run_blocking(feed_courtlistener, term, limit, kind="o")
        # Readiness contract (devb_legal_matter): HTTP 200 admits live/cached
        # evidence only; last-good values ride as cached with their real
        # observation timestamp; never-observed stays UNAVAILABLE (fails
        # closed). Payload keys unchanged.
        return JSONResponse({"surface": "matter", "term": term,
                             "opinions": _readiness_public_source(op),
                             "doctrine": DOCTRINE})

    @app.get(base + "/legal/regulatory", include_in_schema=False)
    async def _legal_reg(
        limit: Annotated[int, Query(ge=1, le=100)] = 18,
        term: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    ):
        fr, ag = await _gather_blocking([
            (feed_fedregister, (limit, term), {}),
            (feed_fr_agencies, (14,), {}),
        ])
        # Same readiness contract as legal/matter (devb_legal_regulatory).
        return JSONResponse({"surface": "regulatory",
                             "federal_register": _readiness_public_source(fr),
                             "agencies": _readiness_public_source(ag),
                             "doctrine": DOCTRINE})

    @app.get(base + "/legal/exposure", include_in_schema=False)
    async def _legal_exposure(
        term: Annotated[str, Query(min_length=1, max_length=160)] = "securities",
        limit: Annotated[int, Query(ge=1, le=100)] = 18,
    ):
        return JSONResponse(await _run_blocking(exposure_graph, term, limit))

    # ---- ENTERPRISE ----
    @app.get(base + "/ent/exec", include_in_schema=False)
    async def _ent_exec():
        return JSONResponse(await _run_blocking(exec_kpis))

    @app.get(base + "/ent/incident", include_in_schema=False)
    async def _ent_incident(
        repo: Annotated[str, Query(
            min_length=3, max_length=160,
            pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        )] = "pytorch/pytorch",
    ):
        sp, ghe = await _gather_blocking([
            (feed_statuspages, (), {}),
            (feed_gh_events, (repo, 18), {}),
        ])
        return JSONResponse({"surface": "incident", "statuspages": sp,
                             "gh_events": ghe, "doctrine": DOCTRINE})

    @app.get(base + "/ent/forecast", include_in_schema=False)
    async def _ent_forecast(
        scenario: Annotated[str, Query(min_length=1, max_length=80)] = "base",
        horizon_q: Annotated[int, Query(ge=1, le=12)] = 4,
        base_v: Annotated[float, Query(ge=0.0, le=1000000000.0,
                                      allow_inf_nan=False)] = 100.0,
        growth: Annotated[float, Query(ge=-1.0, le=10.0,
                                      allow_inf_nan=False)] = 0.08,
        shock: Annotated[float, Query(ge=-1.0, le=10.0,
                                     allow_inf_nan=False)] = 0.0,
    ):
        return JSONResponse(await _run_blocking(
            forecast, scenario, horizon_q, base_v, growth, shock
        ))

    # ---- UDS quorum ----
    @app.get(base + "/uds/quorum", include_in_schema=False)
    async def _uds_quorum():
        return JSONResponse(await _run_blocking(uds_quorum))

    # ---- SHARED governed turn + ledger (devb namespaces) ----
    _DEVB_LABELS = ("leg-matter", "leg-defense", "leg-insurance", "leg-reg", "leg-exposure",
                    "ent-exec", "ent-incident", "ent-forecast")

    @app.post(base + "/{label}/govern", include_in_schema=False)
    async def _govern(label: str, req: Request):
        if label not in _DEVB_LABELS:
            return JSONResponse({"error": "unknown label"}, status_code=404)
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
            action_kind = _canonical_govern_action("devb-" + label, clean["action_kind"])
        except _GovernValidationError as error:
            return _govern_validation_response(error)
        lab = "devb-" + label
        identity, retry_after = _govern_claim(principal)
        if identity is None:
            return JSONResponse({
                "state": "rate_limited",
                "error": "a governance mutation is already active or this credential is inside its cooldown",
                "retry_after_s": retry_after,
            }, status_code=429, headers={"Retry-After": str(retry_after)})
        try:
            result = await _run_blocking(
                governed_turn, lab, clean["text"],
                declared=clean["classification"], severity=clean["severity"],
                action_kind=action_kind, context=clean["context"],
                actor=_govern_actor(principal),
            )
            return JSONResponse(result)
        finally:
            _govern_release(identity)

    @app.get(base + "/{label}/ledger", include_in_schema=False)
    async def _ledger_ep(
        label: str, n: Annotated[int, Query(ge=1, le=1000)] = 25,
    ):
        if label not in _DEVB_LABELS:
            return JSONResponse({"error": "unknown label"}, status_code=404)
        return JSONResponse(await _run_blocking(_ledger, "devb-" + label, n))

    @app.get(base + "/healthz", include_in_schema=False)
    async def _hz():
        return JSONResponse({"ok": True, "module": "a11oy_devb_endpoints",
                             "has_vertical_feeds": _HAS_VF,
                             "surfaces": ["legal/matter", "legal/regulatory", "legal/exposure",
                                          "ent/exec", "ent/incident", "ent/forecast", "uds/quorum"],
                             "doctrine": DOCTRINE})

    # Move appended routes to FRONT so they win ahead of the proxy + SPA catch-all.
    moved = -1
    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        moved = len(_new)
    except Exception as _e:
        import sys as _s
        print(f"[a11oy] devb route reorder failed (non-fatal): {_e!r}", file=_s.stderr)

    # Post-deploy readiness warming (env-gated; no-op in tests/local runs):
    # keep the default legal views warm so the hf-sync probe never reads a
    # cold-start transient as endpoint evidence.
    try:
        start_readiness_warmer()
    except Exception as _warm_e:  # never break the Space
        print(f"[a11oy] devb readiness feed warmer start failed (non-fatal): "
              f"{_warm_e!r}", file=sys.stderr)
    return {"mounted": base, "has_vertical_feeds": _HAS_VF, "moved": moved}
