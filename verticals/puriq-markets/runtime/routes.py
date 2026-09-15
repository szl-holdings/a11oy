# SPDX-License-Identifier: Apache-2.0
"""Canonical finance data routes. GET-only; no source URL or order parameters."""
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .sources import SOURCES
from .transport import FinanceClient, FinanceError, source_revision

router = APIRouter()
CLIENT = FinanceClient()
PREFIX = "/api/a11oy/v1/finance"


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
