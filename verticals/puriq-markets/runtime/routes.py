# SPDX-License-Identifier: Apache-2.0
"""Canonical finance reads and stateless calculations; no orders or ledger writes."""
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .sources import SOURCES
from .transport import FinanceClient, FinanceError, source_revision
from . import analytics

router = APIRouter()
CLIENT = FinanceClient()
PREFIX = "/api/a11oy/v1/finance"


def analytics_failure(code, status=422):
    return reply({"ok": False, "state": "BLOCKED", "error": code,
                  "execution_enabled": False}, status)


def finance_analytics(operation: str, symbol_name: str, request: Request):
    if operation not in ("signals", "quote"):
        return analytics_failure("UNKNOWN_SOURCE", 404)
    pairs = list(request.query_params.multi_items())
    params = dict(pairs)
    if (len(pairs) != len(params) or set(params) - {"origin", "benchmark"}
            or operation == "signals" and "benchmark" in params):
        return analytics_failure("INVALID_PARAMETERS")
    try:
        return reply(analytics.compute(CLIENT, operation, symbol_name,
            params.get("origin", "coinbase"), params.get("benchmark")))
    except FinanceError as exc:
        return analytics_failure(exc.code, 422 if exc.code == "INVALID_PARAMETERS" else 503)
    except (analytics.engine.EngineBlocked, ValueError, OverflowError, ZeroDivisionError):
        return analytics_failure("COMPUTATION_BLOCKED", 503)


@router.get(PREFIX + "/analytics/v2/signals/{symbol_name}")
def finance_signals(symbol_name: str, request: Request):
    return finance_analytics("signals", symbol_name, request)


@router.get(PREFIX + "/analytics/v2/quote/{symbol_name}")
def finance_quote(symbol_name: str, request: Request):
    return finance_analytics("quote", symbol_name, request)


async def bounded_json(request):
    from .transport import strict_json
    from decimal import Decimal
    import math
    def floats(value):
        if isinstance(value, Decimal):
            number = float(value)
            if not math.isfinite(number):
                raise FinanceError("INVALID_PARAMETERS")
            return number
        if isinstance(value, list):
            return [floats(item) for item in value]
        if isinstance(value, dict):
            return {key: floats(item) for key, item in value.items()}
        return value
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 160_000:
            raise FinanceError("INVALID_PARAMETERS")
    try:
        return floats(strict_json(bytes(raw)))
    except (FinanceError, OverflowError, RecursionError):
        raise FinanceError("INVALID_PARAMETERS") from None


@router.post(PREFIX + "/analytics/v2/portfolio")
async def finance_portfolio(request: Request):
    if request.query_params:
        return analytics_failure("INVALID_PARAMETERS")
    try:
        return reply(analytics.portfolio(CLIENT, await bounded_json(request)))
    except FinanceError as exc:
        return analytics_failure(exc.code)
    except (analytics.engine.EngineBlocked, ValueError, OverflowError, ZeroDivisionError):
        return analytics_failure("COMPUTATION_BLOCKED", 503)


@router.get(PREFIX + "/analytics/v2/receipts")
def finance_receipt_contract():
    return capability("receipts", {
        "signing": "UNSIGNED_HONEST", "persistence": "CALLER_HELD",
        "ledger": "NONE", "entries": [], "execution_authority": "NONE",
        "verification": "POST a computation envelope to receipts/verify; GET is capability only."})


@router.get(PREFIX + "/analytics/v2/receipts/verify")
def finance_verification_contract():
    return capability("receipt-verification-contract", {
        "state": "INPUT_REQUIRED", "verified": False, "signing": "UNSIGNED_HONEST",
        "authenticity_established": False, "method": "POST"})


def capability(operation, payload):
    try:
        return reply(analytics.envelope(CLIENT, operation, payload, {}))
    except FinanceError as exc:
        return analytics_failure(exc.code, 503)


@router.post(PREFIX + "/analytics/v2/receipts/verify")
async def finance_verify_receipt(request: Request):
    if request.query_params:
        return analytics_failure("INVALID_PARAMETERS")
    try:
        valid = analytics.verify(await bounded_json(request))
        return reply(analytics.envelope(CLIENT, "receipt-verification", {
            "state": "INTEGRITY_VALID" if valid else "INVALID", "verified": valid,
            "signing": "UNSIGNED_HONEST", "authenticity_established": False}, {}))
    except (FinanceError, ValueError, OverflowError):
        return analytics_failure("INVALID_PARAMETERS")


def reply(body, status=200):
    return JSONResponse(body, status_code=status,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get(PREFIX + "/providers")
def finance_providers():
    return reply(CLIENT.registry())


@router.get(PREFIX + "/observations/{source}")
def finance_observation(source: str, request: Request):
    if source not in SOURCES:
        return reply({"ok": False, "state": "UNAVAILABLE", "error": "UNKNOWN_SOURCE"}, 404)
    pairs = list(request.query_params.multi_items())
    if len(pairs) != len({key for key, _ in pairs}):
        return reply({"ok": False, "state": "UNAVAILABLE", "error": "DUPLICATE_QUERY_PARAMETER"}, 422)
    try:
        body = CLIENT.observe(source, dict(pairs), access_token=request.headers.get("X-SZL-Finance-Read-Token"))
    except FinanceError as exc:
        code = 403 if exc.code == "PRIVATE_SOURCE_ACCESS_REQUIRED" else 422
        return reply({"ok": False, "state": "UNAVAILABLE", "error": exc.code}, code)
    return reply(body, 200 if body["ok"] else 503)


@router.get(PREFIX + "/overview")
def finance_overview():
    """Bounded public snapshots, not a cross-venue join or total market census."""
    requests = (
        ("polymarket-markets", {"limit": "12"}),
        ("kalshi-markets", {"limit": "12"}),
        ("coinbase-ticker", {"product": "BTC-USD"}),
        ("treasury-rates", {"limit": "12"}),
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda task: CLIENT.observe(*task), requests))
    successful = sum(item["ok"] for item in results)
    return reply({"schema": "szl.finance.overview/v1", "ok": successful == len(results),
        "state": "SNAPSHOTS_AVAILABLE" if successful == len(results) else "DEGRADED",
        "source_revision": source_revision(CLIENT.environ),
        "sources_requested": len(results), "sources_available": successful,
        "data": {item["source"]: item for item in results},
        "event_equivalence": "NOT_ESTABLISHED", "execution_enabled": False,
        "scope": "Four explicitly requested public snapshots; other adapters are not implicitly verified."})


def register(app):
    """Register once, preserving include-router dependencies and route ordering.

    Newer FastAPI versions store included routers as grouped route objects with
    no ``path`` attribute. Identify only the objects added by this include call,
    rather than assuming FastAPI flattens every APIRoute into the parent list.
    """
    if getattr(app.state, "szl_finance_routes_registered", False):
        return "finance source adapters already mounted (read-only)"
    before = {id(route) for route in app.router.routes}
    app.include_router(router)
    added = [route for route in app.router.routes if id(route) not in before]
    if not added:
        raise RuntimeError("finance router registration produced no route objects")
    app.router.routes[:] = added + [route for route in app.router.routes if id(route) in before]
    app.state.szl_finance_routes_registered = True
    return "finance source adapters mounted (read-only)"
