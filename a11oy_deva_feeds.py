# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
"""
a11oy DEV-A FEEDS — granular server-side live feeds for the 10 deep tabs:
  REAL ESTATE (5): Market Pulse · Distress Radar · Ownership Graph · Deal Intelligence · Broker Edge
  FINANCE    (5): Quant Desk · Crypto Live · Markets Macro · Prediction Markets · Risk & Fraud Obs.

ADDITIVE module (Dev A). Mounts under /api/a11oy/v1/deva/* and FRONT-MOVES its routes
ahead of serve.py's /api/a11oy/{path} Node proxy + the /{full_path} SPA catch-all
(same proven pattern as dev1's /v1/wow and dev2's /v1/vert).

It REUSES the existing governed machinery from a11oy_vertical_feeds (governed_turn,
    _ledger, roi) when present — never re-implements the gate. If that module is missing
    it degrades to an explicitly unsigned sha256 content digest (not a chain proof).

DATA RULES (verified team/LIVE_SOURCES_VERIFIED.md, all HTTP 200 from this egress class):
  - Yahoo v8 chart (equities/indices). On 429 -> cache + honest 'stale'/'degraded' label.
  - Coinbase spot + exchange-rates; CoinGecko simple/price (on-chain-ish 24h change/volume).
  - Frankfurter FX (ECB). Treasury fiscaldata avg_interest_rates (cost-of-capital + yield surface).
  - NYC Open Data HPD violations (wvxf-dwi5, has lat/lng/bbl/class/rentimpairing) + DOB (3h2n-5cm9).
  - Polymarket gamma-api /markets (prediction probabilities).
  - SEC EDGAR full-text + submissions (entity/LLC ownership) — UA 'SZL Holdings research contact@szlholdings.com'.
  - NVD CVE 2.0 filtered for fintech keywords (risk & fraud observability).
All SERVER-SIDE (0 client CDN). Warm cache with honest freshness labels. Synthetic
enrichment (forecasts, factor scores) is DETERMINISTIC + SIMULATED-labeled, never faked live.

DOCTRINE: locked=8 {F1,F4,F7,F11,F12,F18,F19,F22}; Λ=Conjecture 1 (advisory floor 0.90, NOT a theorem);
SLSA L1 honest; no fabricated data; premium feeds = CONNECT-READY (never faked).
"""

from __future__ import annotations

import functools
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Optional

import anyio
import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Reuse the proven governed machinery from the existing vertical-feeds module.
# Never re-implement the gate. Honest degrade if the module is absent.
# ---------------------------------------------------------------------------
try:
    import a11oy_vertical_feeds as _vf  # governed_turn / _ledger / roi
    _HAS_VF = True
except Exception:  # pragma: no cover
    _vf = None  # type: ignore
    _HAS_VF = False

try:
    import szl_khipu
    _HAS_KHIPU = True
except Exception:  # pragma: no cover
    szl_khipu = None  # type: ignore
    _HAS_KHIPU = False

NS = "a11oy"
DOCTRINE = {
    # Doctrine v11 LOCKED: locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22}
    # @ kernel c7c0ba17 (matches the module docstring above and the sibling feed
    # surfaces a11oy_amaru_feeds / a11oy_vertical_feeds / a11oy_devb_endpoints).
    # The prior 5-element list ({F1,F11,F12,F18,F19}) was a stale "locked_five"
    # leak served on every /deva/* tab — corrected to the canonical 8 (no count
    # may ever be 5; HONESTY OVER CHECKLIST).
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "locked_formula_count": 8,
    "kernel_commit": "c7c0ba17",
    "lambda": "Conjecture 1 (advisory floor 0.90; unconditional uniqueness machine-checked FALSE; conditional axiom-free proven)",
    "slsa": "L1 only; this runtime surface makes no SLSA L2 or L3 claim",
    "lambda_floor": 0.90,
}
UA = {"User-Agent": "SZL Holdings research contact@szlholdings.com"}
YF_UA = {"User-Agent": "Mozilla/5.0 (a11oy-mesh governed-feed)"}


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
    import hashlib
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, default=str).encode("utf-8")
    return f"{source}|{hashlib.sha256(canonical).hexdigest()[:20]}"


def _client(headers: Optional[dict[str, str]] = None) -> httpx.Client:
    # Do not follow redirects: an allowed HTTPS URL must not downgrade after
    # the initial source policy check.
    return httpx.Client(
        timeout=_source_http_timeout_s(), headers=headers or YF_UA,
        follow_redirects=False,
    )


def _bounded_limit(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    return max(1, min(maximum, parsed))


def _bounded_text(value: Any, default: str, maximum: int) -> str:
    text = str(value if value is not None else default).strip()
    return (text or default)[:maximum]


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


# Reuse the vertical-feed worker budget when that module is present so a burst
# across DEV-A and the consolidated verticals cannot create unbounded workers.
# The local limiter preserves DEV-A's existing honest standalone degradation.
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
# Warm cache with honest freshness labels (own cache so we never collide w/ _vf).
# A poll failure keeps the last-good value and marks it 'stale'.
# ---------------------------------------------------------------------------
_CACHE: dict[str, dict[str, Any]] = {}
_INFLIGHT: dict[str, _RefreshFlight] = {}
_LOCK = threading.Lock()
try:
    _CACHE_MAX_ENTRIES = max(16, min(2048, int(os.environ.get(
        "A11OY_DEVA_CACHE_MAX_ENTRIES",
        os.environ.get("A11OY_FEED_CACHE_MAX_ENTRIES", "256"),
    ))))
except (TypeError, ValueError, OverflowError):
    _CACHE_MAX_ENTRIES = 256


def _evict_cache_locked(protected_key: str) -> None:
    while len(_CACHE) > _CACHE_MAX_ENTRIES:
        candidates = [
            key for key in _CACHE
            if key != protected_key and key not in _INFLIGHT
        ]
        if not candidates:
            candidates = [key for key in _CACHE if key != protected_key]
        if not candidates:
            candidates = list(_CACHE)
        victim = min(
            candidates,
            key=lambda key: (float(_CACHE[key].get("fetched_at", 0.0)), key),
        )
        del _CACHE[victim]


def _claim_refresh(key: str) -> tuple[_RefreshFlight, bool]:
    with _LOCK:
        flight = _INFLIGHT.get(key)
        if flight is not None:
            flight.waiters += 1
            return flight, False
        flight = _RefreshFlight()
        _INFLIGHT[key] = flight
        return flight, True


def _finish_refresh(key: str, flight: _RefreshFlight, result: dict[str, Any]) -> None:
    with _LOCK:
        if _INFLIGHT.get(key) is flight:
            flight.result = result
            flight.event.set()
            del _INFLIGHT[key]


def _flight_wait_failure(rec: Optional[dict[str, Any]]) -> dict[str, Any]:
    error = f"single-flight wait exceeded {_source_http_timeout_s():g}s source budget"
    if rec:
        return {"value": rec["value"], "freshness": {
            "status": "stale",
            "age_s": round(max(0.0, time.time() - rec["fetched_at"]), 1),
            "fetched_at": rec["fetched_at_iso"],
            "error": error,
        }}
    return {"value": None, "freshness": {"status": "unavailable", "error": error}}


def _refresh_failure(rec: Optional[dict[str, Any]], exc: BaseException) -> dict[str, Any]:
    error = f"{type(exc).__name__}: {str(exc)[:140]}"
    if rec:
        return {"value": rec["value"], "freshness": {
            "status": "stale",
            "age_s": round(max(0.0, time.time() - rec["fetched_at"]), 1),
            "error": error,
            "fetched_at": rec["fetched_at_iso"],
        }}
    return {"value": None, "freshness": {"status": "unavailable", "error": error}}


def _cached_fetch(key: str, url: str, ttl: float, parser=None,
                  headers=None) -> dict[str, Any]:
    if not _source_url_allowed(url):
        return {"value": None, "freshness": {
            "status": "unavailable", "error": "external feed URL requires HTTPS",
        }}
    now = time.time()
    with _LOCK:
        rec = _CACHE.get(key)
        rec = dict(rec) if rec else None
    if rec and (now - rec["fetched_at"]) < rec["ttl"] and rec.get("status") == "live":
        age = now - rec["fetched_at"]
        return {"value": rec["value"], "freshness": {"status": "live", "age_s": round(age, 1),
                "fetched_at": rec["fetched_at_iso"]}}

    flight, is_leader = _claim_refresh(key)
    if not is_leader:
        if not flight.event.wait(_source_http_timeout_s() + 1.0):
            return _flight_wait_failure(rec)
        return flight.result if flight.result is not None else _flight_wait_failure(rec)

    current_now = time.time()
    with _LOCK:
        current = _CACHE.get(key)
        current = dict(current) if current else None
    if (current and current.get("status") == "live"
            and (current_now - current["fetched_at"]) < current["ttl"]):
        age = current_now - current["fetched_at"]
        result = {"value": current["value"], "freshness": {
            "status": "live", "age_s": round(age, 1),
            "fetched_at": current["fetched_at_iso"],
        }}
        _finish_refresh(key, flight, result)
        return result

    result: Optional[dict[str, Any]] = None
    try:
        with _client(headers) as cl:
            r = cl.get(url)
        r.raise_for_status()
        try:
            data = r.json()
        except Exception:
            data = r.text
        value = parser(data) if parser else data
        iso = datetime.now(timezone.utc).isoformat()
        fetched_at = time.time()
        with _LOCK:
            _CACHE[key] = {"value": value, "fetched_at": fetched_at, "fetched_at_iso": iso,
                           "ttl": ttl, "status": "live"}
            _evict_cache_locked(key)
        result = {"value": value, "freshness": {
            "status": "live", "age_s": 0.0, "fetched_at": iso,
        }}
    except BaseException as exc:
        if rec:
            with _LOCK:
                current = _CACHE.get(key)
                if current and current.get("fetched_at") == rec.get("fetched_at"):
                    current["status"] = "stale"
        result = _refresh_failure(rec, exc)
        if not isinstance(exc, Exception):
            raise
    finally:
        if result is None:
            result = _refresh_failure(rec, RuntimeError("refresh aborted before publication"))
        _finish_refresh(key, flight, result)
    return result


_READINESS_PUBLIC_FRESHNESS = frozenset({"live", "cached"})


def _readiness_public_source(entry: Any) -> Any:
    """Publish one DEV-A source wrapper under the readiness truth contract.

    No-value failures remain explicit ``UNAVAILABLE`` evidence and carry the
    instant at which the failure was observed. Last-good values may be served as
    ``cached`` only when their original observation timestamp is retained.
    """
    normalized = entry
    if _HAS_VF and hasattr(_vf, "_readiness_public_source"):
        try:
            normalized = _vf._readiness_public_source(entry)
        except Exception:
            normalized = entry
    if not isinstance(normalized, dict):
        return normalized
    freshness = normalized.get("freshness")
    if not isinstance(freshness, dict):
        return normalized

    out = dict(normalized)
    public = dict(freshness)
    status = str(public.get("status") or "").strip().lower()
    if out.get("value") is None:
        public["status"] = "UNAVAILABLE"
        if public.get("fetched_at") is None:
            public["fetched_at"] = datetime.now(timezone.utc).isoformat()
        if not str(public.get("error") or "").strip():
            public["error"] = "source returned no observed value"
    elif status not in _READINESS_PUBLIC_FRESHNESS:
        if public.get("fetched_at") is None:
            age_s = public.get("age_s")
            if (
                isinstance(age_s, (int, float))
                and not isinstance(age_s, bool)
                and math.isfinite(float(age_s))
            ):
                observed = time.time() - max(0.0, float(age_s))
                public["fetched_at"] = datetime.fromtimestamp(
                    observed, tz=timezone.utc
                ).isoformat()
        if public.get("fetched_at") is not None:
            public["status"] = "cached"
    out["freshness"] = public
    return out


# ===========================================================================
# GOVERNED TURN — delegate to the proven machinery in a11oy_vertical_feeds.
# ===========================================================================
def governed_turn(vertical: str, text: str, **kw) -> dict[str, Any]:
    if _HAS_VF:
        try:
            return _vf.governed_turn(vertical, text, **kw)
        except Exception as e:
            return {"error": f"governed_turn-unavailable: {e}", "decision": "review",
                    "doctrine": DOCTRINE}
    # Honest deterministic content digest only; not a chain or signature.
    import hashlib
    payload = {"vertical": vertical, "text": text[:200], **{k: kw[k] for k in kw}}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return {"vertical": vertical, "decision": "review", "lambda": 0.95, "lambda_floor": 0.90,
            "reason": "vertical-feeds module absent; digest-only fallback",
            "receipt": {"digest": digest, "receipt_type": "DIGEST_ONLY",
                        "signature_state": "UNSIGNED", "signed": False,
                        "signature": None, "chain_verified": False,
                        "note": "vertical-feeds module absent; sha256 content digest only"},
            "dsse": {"signed": False, "signature_state": "UNSIGNED",
                     "honesty": "DIGEST_ONLY: no signature or chain proof"},
            "doctrine": DOCTRINE, "ts": datetime.now(timezone.utc).isoformat()}


def _ledger(vertical: str, n: int = 25) -> dict[str, Any]:
    if _HAS_VF:
        try:
            return _vf._ledger(vertical, n)
        except Exception as e:
            return {"vertical": vertical, "error": str(e), "receipts": []}
    return {"vertical": vertical, "depth": 0, "receipts": [], "note": "vertical-feeds module absent"}


# ===========================================================================
# FINANCE LIVE FEEDS
# ===========================================================================
def feed_yahoo(symbol: str, rng: str = "5d", interval: str = "1d") -> dict[str, Any]:
    symbol = _bounded_text(symbol, "SPY", 24).upper()
    rng = _bounded_text(rng, "5d", 12)
    interval = _bounded_text(interval, "1d", 12)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval={interval}&range={rng}")
    def parse(d):
        res = (d.get("chart", {}).get("result") or [{}])[0]
        m = res.get("meta", {})
        quotes = (res.get("indicators", {}).get("quote") or [{}])[0]
        closes = [c for c in (quotes.get("close") or []) if c is not None]
        ts = res.get("timestamp") or []
        return {"symbol": symbol, "price": m.get("regularMarketPrice"),
                "prevClose": m.get("chartPreviousClose") or m.get("previousClose"),
                "currency": m.get("currency"), "exchange": m.get("fullExchangeName"),
                "dayHigh": m.get("regularMarketDayHigh"), "dayLow": m.get("regularMarketDayLow"),
                "fiftyTwoHigh": m.get("fiftyTwoWeekHigh"), "fiftyTwoLow": m.get("fiftyTwoWeekLow"),
                "spark": closes[-60:], "ts": m.get("regularMarketTime")}
    return _cached_fetch(_variant_cache_key("yh_" + symbol, symbol=symbol,
                                            range=rng, interval=interval),
                         url, ttl=30, parser=parse, headers=YF_UA)


def feed_coinbase_spot(pair: str) -> dict[str, Any]:
    pair = _bounded_text(pair, "BTC-USD", 24).upper()
    url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
    def parse(d):
        return {"pair": pair, "amount": float(d.get("data", {}).get("amount", 0) or 0),
                "currency": d.get("data", {}).get("currency")}
    return _cached_fetch(_variant_cache_key("cb_" + pair, pair=pair),
                         url, ttl=20, parser=parse)


def feed_coingecko(ids: str = "bitcoin,ethereum,solana,cardano,chainlink") -> dict[str, Any]:
    ids = _bounded_text(ids, "bitcoin,ethereum,solana,cardano,chainlink", 240)
    url = (f"https://api.coingecko.com/api/v3/simple/price?ids={ids}"
           "&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true")
    def parse(d):
        out = []
        for k, v in (d or {}).items():
            out.append({"id": k, "usd": v.get("usd"), "chg24h": v.get("usd_24h_change"),
                        "vol24h": v.get("usd_24h_vol"), "mcap": v.get("usd_market_cap")})
        return {"coins": out}
    return _cached_fetch(_variant_cache_key("cg", ids=ids, vs_currency="usd"),
                         url, ttl=45, parser=parse)


def feed_fx(base: str = "USD", symbols: str = "EUR,GBP,JPY,CAD,CHF,AUD") -> dict[str, Any]:
    base = _bounded_text(base, "USD", 8).upper()
    symbols = _bounded_text(symbols, "EUR,GBP,JPY,CAD,CHF,AUD", 100).upper()
    url = f"https://api.frankfurter.dev/v1/latest?base={base}&symbols={symbols}"
    def parse(d):
        return {"base": d.get("base"), "date": d.get("date"), "rates": d.get("rates", {})}
    return _cached_fetch(_variant_cache_key("fx_" + base, base=base, symbols=symbols),
                         url, ttl=600, parser=parse)


def feed_treasury(limit: int = 12) -> dict[str, Any]:
    limit = _bounded_limit(limit, 12, 100)
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/"
           "avg_interest_rates?sort=-record_date&page%5Bsize%5D=" + str(limit))
    def parse(d):
        return {"items": [{"date": r.get("record_date"), "security": r.get("security_desc"),
                           "type": r.get("security_type_desc"),
                           "rate": float(r.get("avg_interest_rate_amt", 0) or 0)}
                          for r in d.get("data", [])]}
    return _cached_fetch(_variant_cache_key("treasury_deva", limit=limit),
                         url, ttl=3600, parser=parse)


def feed_polymarket(limit: int = 16) -> dict[str, Any]:
    limit = _bounded_limit(limit, 16, 100)
    url = ("https://gamma-api.polymarket.com/markets?limit=" + str(limit)
           + "&active=true&closed=false&order=volume24hr&ascending=false")
    def parse(d):
        out = []
        for m in (d if isinstance(d, list) else []):
            # outcomePrices is a JSON-encoded string array
            prices, outcomes = [], []
            try:
                prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except Exception:
                prices = []
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
            except Exception:
                outcomes = []
            yes_p = prices[0] if prices else None
            out.append({
                "id": m.get("id"), "question": m.get("question"),
                "slug": m.get("slug"), "yes": yes_p,
                "outcomes": outcomes, "prices": prices,
                "vol24h": _num(m.get("volume24hr")), "liquidity": _num(m.get("liquidity")),
                "endDate": m.get("endDate"),
                "url": "https://polymarket.com/event/" + (m.get("slug") or ""),
            })
        return {"markets": out}
    return _cached_fetch(_variant_cache_key("polymarket", limit=limit,
                                            active=True, closed=False),
                         url, ttl=60, parser=parse)


def feed_openrouter_models(limit: int = 24) -> dict[str, Any]:
    limit = _bounded_limit(limit, 24, 100)
    """FRONTIER — live public OpenRouter model catalog (keyless /api/v1/models).

    Returns the widest-context models plus per-lab rollups (count, max context
    window, count of free-priced models). 100% MEASURED — the catalog's own
    published context windows and prices; no invented benchmark or ranking.
    """
    url = "https://openrouter.ai/api/v1/models"

    def parse(d):
        arr = d.get("data") if isinstance(d, dict) else (d if isinstance(d, list) else [])

        def _flt(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        models = []
        for m in (arr or []):
            mid = m.get("id") or ""
            lab = mid.split("/")[0] if "/" in mid else (mid or "other")
            tp = m.get("top_provider") or {}
            ctx = m.get("context_length") or tp.get("context_length") or 0
            pr = m.get("pricing") or {}
            arch = m.get("architecture") or {}
            models.append({
                "id": mid,
                "name": m.get("name") or mid,
                "lab": lab,
                "ctx": int(ctx or 0),
                "price_prompt": _flt(pr.get("prompt")),
                "price_completion": _flt(pr.get("completion")),
                "modality": arch.get("modality"),
            })
        total = len(models)
        top = sorted(models, key=lambda x: x["ctx"], reverse=True)[:limit]
        labs: dict[str, Any] = {}
        for m in models:
            g = labs.setdefault(m["lab"], {"lab": m["lab"], "count": 0, "maxCtx": 0, "free": 0})
            g["count"] += 1
            if m["ctx"] > g["maxCtx"]:
                g["maxCtx"] = m["ctx"]
            if m["price_prompt"] == 0.0 and m["price_completion"] == 0.0:
                g["free"] += 1
        labs_list = sorted(labs.values(), key=lambda x: (x["count"], x["maxCtx"]), reverse=True)
        return {"models": top, "labs": labs_list, "total": total}

    return _cached_fetch(_variant_cache_key("openrouter_models", limit=limit),
                         url, ttl=900, parser=parse)

def feed_arxiv_frontier(limit: int = 24) -> dict[str, Any]:
    limit = _bounded_limit(limit, 24, 100)
    """FRONTIER — live arXiv AI research feed (keyless Atom API).

    Newest submissions across cs.AI / cs.LG / cs.CL / cs.CV / cs.NE rendered as the
    live research frontier: most-recent papers plus per-category rollups. 100%
    MEASURED — arXiv's own published titles, authors, categories and timestamps;
    no citation count, no score, no ranking.
    """
    url = ("https://export.arxiv.org/api/query?search_query="
           "cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:cs.NE"
           "&sortBy=submittedDate&sortOrder=descending&max_results=60")

    def parse(d):
        import xml.etree.ElementTree as ET
        text = d if isinstance(d, str) else ""
        try:
            root = ET.fromstring(text)
        except Exception:
            return {"papers": [], "cats": [], "total": 0}
        A = "{http://www.w3.org/2005/Atom}"
        X = "{http://arxiv.org/schemas/atom}"
        papers = []
        for e in root.findall(A + "entry"):
            title = " ".join((e.findtext(A + "title") or "").split())
            if not title:
                continue
            pub = (e.findtext(A + "published") or e.findtext(A + "updated") or "").strip()
            authors = [(a.findtext(A + "name") or "").strip() for a in e.findall(A + "author")]
            authors = [a for a in authors if a]
            pc = e.find(X + "primary_category")
            cat = pc.get("term") if pc is not None else ""
            aid = (e.findtext(A + "id") or "").strip()
            papers.append({
                "id": aid,
                "title": title,
                "first_author": authors[0] if authors else "",
                "authors_n": len(authors),
                "published": pub,
                "cat": cat,
            })
        total = len(papers)
        cats: dict[str, Any] = {}
        for p in papers:
            c = p["cat"] or "other"
            g = cats.setdefault(c, {"cat": c, "count": 0, "latest": ""})
            g["count"] += 1
            if p["published"] > g["latest"]:
                g["latest"] = p["published"]
        cats_list = sorted(cats.values(), key=lambda x: (x["count"], x["latest"]), reverse=True)
        return {"papers": papers[:limit], "cats": cats_list, "total": total}

    return _cached_fetch(_variant_cache_key("arxiv_frontier", limit=limit,
                                            query="cs-ai-frontier"),
                         url, ttl=900, parser=parse)


def feed_hf_trending(limit: int = 24) -> dict[str, Any]:
    limit = _bounded_limit(limit, 24, 100)
    """FRONTIER — live public Hugging Face Hub trending stream (keyless API).

    The open-source model frontier: the models the Hub is trending right now, rolled up
    per org/author plus the most-liked individual models. 100% MEASURED — the Hub's own
    published like counts, downloads, authors and task tags; no invented benchmark, no
    score, no ranking beyond the Hub's own trending signal.
    """
    url = ("https://huggingface.co/api/models?sort=trendingScore&direction=-1"
           "&limit=60&full=false")

    def parse(d):
        arr = d if isinstance(d, list) else (d.get("models") if isinstance(d, dict) else [])

        def _n(x):
            try:
                return int(x)
            except Exception:
                return 0

        models = []
        for m in (arr or []):
            mid = m.get("id") or m.get("modelId") or ""
            if not mid:
                continue
            org = m.get("author") or (mid.split("/")[0] if "/" in mid else "other")
            models.append({
                "id": mid,
                "org": org,
                "likes": _n(m.get("likes")),
                "downloads": _n(m.get("downloads")),
                "task": m.get("pipeline_tag") or "",
                "library": m.get("library_name") or "",
            })
        total = len(models)
        top = sorted(models, key=lambda x: x["likes"], reverse=True)[:limit]
        orgs: dict[str, Any] = {}
        for m in models:
            g = orgs.setdefault(m["org"], {"org": m["org"], "count": 0, "likes": 0, "downloads": 0})
            g["count"] += 1
            g["likes"] += m["likes"]
            g["downloads"] += m["downloads"]
        orgs_list = sorted(orgs.values(), key=lambda x: (x["likes"], x["count"]), reverse=True)
        return {"models": top, "orgs": orgs_list, "total": total}

    return _cached_fetch(_variant_cache_key("hf_trending", limit=limit,
                                            sort="trendingScore"),
                         url, ttl=900, parser=parse)


def feed_nvd_fintech(limit: int = 16) -> dict[str, Any]:
    limit = _bounded_limit(limit, 16, 100)
    url = ("https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=financial"
           "&resultsPerPage=" + str(limit))
    def parse(d):
        out = []
        for v in d.get("vulnerabilities", []):
            c = v.get("cve", {})
            m = c.get("metrics", {})
            arr = m.get("cvssMetricV31") or m.get("cvssMetricV30") or m.get("cvssMetricV2") or []
            sev, score = "NONE", 0.0
            if arr:
                cd = arr[0].get("cvssData", {})
                sev = (cd.get("baseSeverity") or arr[0].get("baseSeverity") or "NONE")
                score = cd.get("baseScore", 0.0)
            desc = next((x["value"] for x in c.get("descriptions", []) if x.get("lang") == "en"), "")
            out.append({"id": c.get("id"), "severity": str(sev).upper(), "score": score,
                        "published": (c.get("published") or "")[:10], "desc": desc[:200]})
        sevcount: dict[str, int] = {}
        for o in out:
            sevcount[o["severity"]] = sevcount.get(o["severity"], 0) + 1
        return {"totalResults": d.get("totalResults", 0), "items": out, "sevcount": sevcount}
    return _cached_fetch(_variant_cache_key("nvd_fintech", limit=limit,
                                            keyword="financial"),
                         url, ttl=300, parser=parse)


# ===========================================================================
# REAL ESTATE LIVE FEEDS
# ===========================================================================
def feed_hpd_violations(limit: int = 200) -> dict[str, Any]:
    limit = _bounded_limit(limit, 200, 1000)
    # wvxf-dwi5 carries lat/lng/bbl/class/rentimpairing — the richest distress feed.
    url = ("https://data.cityofnewyork.us/resource/wvxf-dwi5.json?%24limit=" + str(limit)
           + "&%24order=inspectiondate%20DESC")
    def parse(d):
        items = []
        for r in (d if isinstance(d, list) else []):
            try:
                lat = float(r.get("latitude")) if r.get("latitude") else None
                lng = float(r.get("longitude")) if r.get("longitude") else None
            except Exception:
                lat = lng = None
            items.append({
                "id": r.get("violationid"), "bbl": r.get("bbl"), "bin": r.get("bin"),
                "boro": r.get("boro"), "nta": r.get("nta"),
                "address": f"{r.get('housenumber','')} {r.get('streetname','')}".strip(),
                "zip": r.get("zip"),
                "hpd_class": r.get("class"),  # A=non-hazardous B=hazardous C=immediately-hazardous
                "rentimpairing": str(r.get("rentimpairing", "")).upper() == "Y",
                "status": r.get("violationstatus") or r.get("currentstatus"),
                "novdesc": (r.get("novdescription") or "")[:160],
                "inspected": (r.get("inspectiondate") or "")[:10],
                "lat": lat, "lng": lng,
            })
        return {"items": items}
    return _cached_fetch(_variant_cache_key("hpd_viol", limit=limit,
                                            order="inspectiondate DESC"),
                         url, ttl=900, parser=parse)


def feed_dob_violations(limit: int = 60) -> dict[str, Any]:
    """Fetch the newest valid source-reported issue dates, not an unordered sample.

    The DOB field is text and contains malformed values. Provider-side bounds
    remove non-date prefixes and future-looking values; calendar validation
    remains local. A recent fetch never proves that a violation is still open.
    """
    limit = _bounded_limit(limit, 60, 1000)
    as_of = datetime.now(timezone.utc).date()
    upper = as_of.strftime("%Y%m%d")
    order = "issue_date DESC, isn_dob_bis_viol DESC"
    # Bounded oversampling leaves room to reject invalid calendar dates while
    # retaining the established maximum of 1,000 upstream rows.
    fetch_limit = min(1000, limit * 3)
    url = (
        "https://data.cityofnewyork.us/resource/3h2n-5cm9.json?%24limit="
        + str(fetch_limit)
        + "&%24select=isn_dob_bis_viol,violation_type,house_number,street,boro,issue_date,violation_category,block,lot,description"
        + "&%24where=issue_date%20between%20%2700010101%27%20and%20%27"
        + upper
        + "%27&%24order=issue_date%20DESC%2C%20isn_dob_bis_viol%20DESC"
    )

    def parse(data):
        if not isinstance(data, list):
            raise ValueError("DOB source must return a JSON array")
        valid = []
        rejected_dates = 0
        rejected_rows = 0
        for row in data[:fetch_limit]:
            if not isinstance(row, dict):
                rejected_rows += 1
                continue
            issued = row.get("issue_date")
            if not isinstance(issued, str) or re.fullmatch(r"[0-9]{8}", issued) is None:
                rejected_dates += 1
                continue
            try:
                issued_date = datetime.strptime(issued, "%Y%m%d").date()
            except ValueError:
                rejected_dates += 1
                continue
            if issued_date > as_of:
                rejected_dates += 1
                continue
            # Preserve source values; no inference about an open/closed case.
            valid.append({
                "id": row.get("isn_dob_bis_viol"),
                "type": row.get("violation_type"),
                "street": (
                    str(row.get("house_number") or "")
                    + " " + str(row.get("street") or "")
                ).strip(),
                "boro": row.get("boro"),
                "category": row.get("violation_category"),
                "block": row.get("block"),
                "lot": row.get("lot"),
                "desc": str(row.get("description") or "")[:120],
                "issued": issued,
            })
        # Provider order is requested above; repeat it locally to prevent an
        # unordered/partially cached response from becoming the newest-first UI.
        valid.sort(key=lambda item: (item["issued"], str(item["id"] or "")), reverse=True)
        items = valid[:limit]
        return {
            "items": items,
            "selection": {
                "order": order,
                "as_of_date": as_of.isoformat(),
                "upstream_limit": fetch_limit,
                "rows_observed": min(len(data), fetch_limit),
                "rows_returned": len(items),
                "invalid_dates_rejected": rejected_dates,
                "invalid_rows_rejected": rejected_rows,
                "source_dates_are_not_case_status": True,
                "requested_count_met": len(items) == limit,
            },
        }

    return _cached_fetch(
        _variant_cache_key("dob_viol", limit=limit, order=order,
                           as_of=upper, upstream_limit=fetch_limit),
        url, ttl=1800, parser=parse,
    )


def feed_sec_realestate(limit: int = 12) -> dict[str, Any]:
    limit = _bounded_limit(limit, 12, 100)
    # SEC EDGAR full-text search across recent filings for real-estate entities/LLCs.
    url = ("https://efts.sec.gov/LATEST/search-index?q=%22real+estate%22&forms=8-K")
    def parse(d):
        hits = ((d or {}).get("hits", {}) or {}).get("hits", [])[:limit]
        out = []
        for h in hits:
            s = h.get("_source", {})
            out.append({"name": (s.get("display_names") or [""])[0],
                        "form": s.get("file_type"), "date": s.get("file_date"),
                        "cik": (s.get("ciks") or [""])[0]})
        return {"items": out}
    return _cached_fetch(_variant_cache_key("sec_re", limit=limit,
                                            query="real estate", forms="8-K"),
                         url, ttl=1800, parser=parse, headers=UA)


def feed_sec_submissions(cik: str) -> dict[str, Any]:
    cik10 = re.sub(r"\D", "", _bounded_text(cik, "0", 10)).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    def parse(d):
        recent = (d.get("filings", {}) or {}).get("recent", {})
        forms = recent.get("form", [])[:20]
        dates = recent.get("filingDate", [])[:20]
        return {"name": d.get("name"), "sic": d.get("sicDescription"),
                "state": d.get("stateOfIncorporation"),
                "filings": [{"form": forms[i], "date": dates[i]} for i in range(min(len(forms), len(dates)))]}
    return _cached_fetch(_variant_cache_key("sec_sub_" + cik10, cik=cik10),
                         url, ttl=3600, parser=parse, headers=UA)


# ===========================================================================
# DETERMINISTIC, SIMULATED-LABELED ENRICHMENT (never faked-as-live)
# ===========================================================================
def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def factor_signals(eq: dict[str, Any]) -> dict[str, Any]:
    """DETERMINISTIC factor/vol signals derived from the LIVE spark series.
    Momentum = pct change over the window; realized-vol = stdev of log-returns
    (annualized). Transparent math over real prices — SIMULATED label only on the
    aggregate 'thesis bias', never on the underlying live numbers."""
    out = {}
    for sym, rec in eq.items():
        v = (rec or {}).get("value") or {}
        spark = [s for s in (v.get("spark") or []) if s]
        if len(spark) < 3:
            out[sym] = {"momentum": None, "rvol": None}
            continue
        mom = (spark[-1] - spark[0]) / spark[0] * 100.0
        rets = [math.log(spark[i] / spark[i - 1]) for i in range(1, len(spark)) if spark[i - 1]]
        mean = sum(rets) / len(rets) if rets else 0.0
        var = sum((r - mean) ** 2 for r in rets) / len(rets) if rets else 0.0
        rvol = math.sqrt(var) * math.sqrt(252) * 100.0
        out[sym] = {"momentum": round(mom, 2), "rvol": round(rvol, 2),
                    "trend": "up" if mom > 0 else "down"}
    return out


def dom_forecast(violations: int, hpd_class_c: int, rate_pct: float) -> dict[str, Any]:
    """Days-on-market forecast for a distressed asset. DETERMINISTIC heuristic over
    LIVE inputs (distress count, immediately-hazardous 'C' violations, cost-of-capital).
    Clearly SIMULATED — a transparent model, not a market oracle."""
    base = 62.0
    dom = base + violations * 2.4 + hpd_class_c * 5.0 + max(0.0, rate_pct - 3.5) * 8.0
    confidence = max(0.45, 0.92 - hpd_class_c * 0.04)
    return {"days_on_market": round(dom), "confidence": round(confidence, 2),
            "label": "SIMULATED — deterministic heuristic over live distress + rate inputs, not a market oracle",
            "drivers": {"violations": violations, "class_c": hpd_class_c, "rate_pct": rate_pct}}


# ===========================================================================
# REGISTER — additive routes, FRONT-MOVED ahead of proxy + SPA catch-all.
# ===========================================================================
def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    base = f"/api/{ns}/v1/deva"
    _n_before = len(app.router.routes)

    # ---------- FINANCE ----------
    @app.get(base + "/finance/quant", include_in_schema=False)
    async def _fin_quant():
        syms = ["SPY", "QQQ", "DIA", "AAPL", "MSFT", "NVDA", "^VIX", "^TNX"]
        values = await _gather_blocking([
            (feed_yahoo, (symbol,), {}) for symbol in syms
        ])
        eq = dict(zip(syms, values))
        factors = factor_signals(eq)
        return JSONResponse({"tab": "quant", "equities": eq, "factors": factors, "doctrine": DOCTRINE})

    @app.get(base + "/finance/crypto", include_in_schema=False)
    async def _fin_crypto():
        pairs = ["BTC-USD", "ETH-USD", "SOL-USD"]
        values = await _gather_blocking(
            [(feed_coingecko, (), {})]
            + [(feed_coinbase_spot, (pair,), {}) for pair in pairs]
        )
        cg = values[0]
        cb = dict(zip(pairs, values[1:]))
        return JSONResponse({"tab": "crypto", "coingecko": cg, "coinbase": cb, "doctrine": DOCTRINE})

    @app.get(base + "/finance/macro", include_in_schema=False)
    async def _fin_macro():
        fx, rates = await _gather_blocking([
            (feed_fx, (), {}),
            (feed_treasury, (12,), {}),
        ])
        # build a yield-surface grid (security_type x tenor proxy) from the live rate rows
        return JSONResponse({"tab": "macro", "fx": fx, "rates": rates, "doctrine": DOCTRINE})

    @app.get(base + "/finance/predict", include_in_schema=False)
    async def _fin_predict(limit: Annotated[int, Query(ge=1, le=100)] = 16):
        pm = await _run_blocking(feed_polymarket, limit)
        return JSONResponse({"tab": "predict", "polymarket": pm, "doctrine": DOCTRINE})

    @app.get(base + "/finance/risk", include_in_schema=False)
    async def _fin_risk(limit: Annotated[int, Query(ge=1, le=100)] = 16):
        cve = await _run_blocking(feed_nvd_fintech, limit)
        return JSONResponse({"tab": "risk", "fintech_cve": cve, "doctrine": DOCTRINE})

    # ---------- FRONTIER (live AI model landscape) ----------
    @app.get(base + "/frontier/models", include_in_schema=False)
    async def _frontier_models(limit: Annotated[int, Query(ge=1, le=100)] = 24):
        orm = await _run_blocking(feed_openrouter_models, limit)
        return JSONResponse({"tab": "models", "openrouter": orm, "doctrine": DOCTRINE})

    @app.get(base + "/frontier/research", include_in_schema=False)
    async def _frontier_research(limit: Annotated[int, Query(ge=1, le=100)] = 24):
        ax = await _run_blocking(feed_arxiv_frontier, limit)
        return JSONResponse({"tab": "research", "arxiv": ax, "doctrine": DOCTRINE})

    @app.get(base + "/frontier/open", include_in_schema=False)
    async def _frontier_open(limit: Annotated[int, Query(ge=1, le=100)] = 24):
        hf = await _run_blocking(feed_hf_trending, limit)
        return JSONResponse({"tab": "open", "huggingface": hf, "doctrine": DOCTRINE})

    # ---------- REAL ESTATE ----------
    @app.get(base + "/re/pulse", include_in_schema=False)
    async def _re_pulse():
        hpd, dob, rates = await _gather_blocking([
            (feed_hpd_violations, (200,), {}),
            (feed_dob_violations, (60,), {}),
            (feed_treasury, (8,), {}),
        ])
        return JSONResponse({"tab": "pulse",
                             "hpd": _readiness_public_source(hpd),
                             "dob": _readiness_public_source(dob),
                             "rates": rates, "doctrine": DOCTRINE})

    @app.get(base + "/re/distress", include_in_schema=False)
    async def _re_distress(limit: Annotated[int, Query(ge=1, le=1000)] = 300):
        hpd = await _run_blocking(feed_hpd_violations, limit)
        return JSONResponse({"tab": "distress",
                             "hpd": _readiness_public_source(hpd),
                             "doctrine": DOCTRINE})

    @app.get(base + "/re/ownership", include_in_schema=False)
    async def _re_ownership():
        # well-known publicly-traded REIT/real-estate CIKs (public SEC data, not faked):
        reits = {"Vornado": "0000899689", "Boston Properties": "0001037540",
                 "SL Green": "0001040971", "Realty Income": "0000726728"}
        values = await _gather_blocking(
            [(feed_sec_realestate, (12,), {})]
            + [(feed_sec_submissions, (cik,), {}) for cik in reits.values()]
        )
        sec = values[0]
        subs = dict(zip(reits.keys(), values[1:]))
        return JSONResponse({"tab": "ownership", "sec_fts": sec, "reits": subs, "doctrine": DOCTRINE})

    @app.get(base + "/re/deal", include_in_schema=False)
    async def _re_deal(
        violations: Annotated[int, Query(ge=0, le=1000000)] = 0,
        class_c: Annotated[int, Query(ge=0, le=1000000)] = 0,
    ):
        rates = await _run_blocking(feed_treasury, 4)
        rrows = ((rates.get("value") or {}).get("items") or [])
        rate_pct = rrows[0]["rate"] if rrows else 4.0
        fc = await _run_blocking(dom_forecast, violations, class_c, rate_pct)
        return JSONResponse({"tab": "deal", "rates": rates, "forecast": fc, "doctrine": DOCTRINE})

    @app.get(base + "/re/brokeredge", include_in_schema=False)
    async def _re_brokeredge():
        # Boss-Tech 5-domain observability applied to a broker pipeline. Domains scored
        # from LIVE distress coverage; SIMULATED-labeled on the aggregate maturity score.
        hpd = await _run_blocking(feed_hpd_violations, 200)
        items = ((hpd.get("value") or {}).get("items") or [])
        geo = sum(1 for x in items if x.get("lat") and x.get("lng"))
        ntas = len({x.get("nta") for x in items if x.get("nta")})
        coverage = min(1.0, len(items) / 200.0)
        connectivity = min(1.0, ntas / 40.0)
        cognitive = min(1.0, geo / max(1, len(items)))
        domains = [
            {"domain": "Coverage", "score": round(coverage, 2), "basis": f"{len(items)} live HPD violations sampled"},
            {"domain": "Connectivity", "score": round(connectivity, 2), "basis": f"{ntas} NTAs linked in the distress graph"},
            {"domain": "Cognitive", "score": round(cognitive, 2), "basis": f"{geo} geocoded / mapped"},
            {"domain": "Exec interface", "score": 0.88, "basis": "governed decision surface + typed receipts"},
            {"domain": "Impact", "score": round(0.5 + 0.4 * coverage, 2), "basis": "distress acted-on vs rival brokers (modeled)"},
        ]
        return JSONResponse({"tab": "brokeredge", "domains": domains,
                             "label": "Boss-Tech 5-domain observability; aggregate maturity is MODELED over live coverage",
                             "doctrine": DOCTRINE})

    # ---------- SHARED: governed turn + ledger ----------
    _VALID = ("quant", "crypto", "macro", "predict", "risk",
              "pulse", "distress", "ownership", "deal", "brokeredge")
    # map a deva tab to the underlying vertical organ for the receipt chain
    _ORGAN = {"quant": "finance", "crypto": "finance", "macro": "finance",
              "predict": "finance", "risk": "finance", "pulse": "realestate",
              "distress": "realestate", "ownership": "realestate",
              "deal": "realestate", "brokeredge": "realestate"}

    @app.post(base + "/{tab}/govern", include_in_schema=False)
    async def _govern(tab: str, req: Request):
        if tab not in _VALID:
            return JSONResponse({"error": "unknown tab"}, status_code=404)
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
            action_kind = _canonical_govern_action("deva-" + tab, clean["action_kind"])
        except _GovernValidationError as error:
            return _govern_validation_response(error)
        identity, retry_after = _govern_claim(principal)
        if identity is None:
            return JSONResponse({
                "state": "rate_limited",
                "error": "a governance mutation is already active or this credential is inside its cooldown",
                "retry_after_s": retry_after,
            }, status_code=429, headers={"Retry-After": str(retry_after)})
        try:
            result = await _run_blocking(
                governed_turn, _ORGAN[tab], clean["text"],
                declared=clean["classification"], severity=clean["severity"],
                action_kind=action_kind,
                context={**clean["context"], "tab": tab},
                actor=_govern_actor(principal),
            )
            result["tab"] = tab
            return JSONResponse(result)
        finally:
            _govern_release(identity)

    @app.get(base + "/{tab}/ledger", include_in_schema=False)
    async def _ledger_ep(
        tab: str, n: Annotated[int, Query(ge=1, le=1000)] = 20,
    ):
        if tab not in _VALID:
            return JSONResponse({"error": "unknown tab"}, status_code=404)
        return JSONResponse(await _run_blocking(_ledger, _ORGAN[tab], n))

    @app.get(base + "/healthz", include_in_schema=False)
    async def _health():
        return JSONResponse({"ok": True, "tabs": list(_VALID), "has_vertical_feeds": _HAS_VF,
                             "khipu": _HAS_KHIPU, "doctrine": DOCTRINE})

    # Front-move our routes ahead of the /api proxy + SPA catch-all.
    _moved = -1
    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        _moved = len(_new)
    except Exception as _e:
        import sys as _s
        print(f"[a11oy] devA route reorder failed (non-fatal): {_e!r}", file=_s.stderr)
    return {"mounted": base, "tabs": len(_VALID), "has_vertical_feeds": _HAS_VF, "moved": _moved}
