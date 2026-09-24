#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Provenance layer: read-only ledger and advisory policy inspection in A11oy."""

import asyncio
import importlib.util
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

BASE = Path(__file__).resolve().parent
PREFIX = "/api/a11oy/v1/anatomy-ledger"
MAX_BODY = 256 * 1024


def load_service():
    spec = importlib.util.spec_from_file_location(
        "a11oy_anatomy_ledger_service", BASE / "anatomy-ledger/server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register(app):
    if getattr(app.state, "anatomy_ledger_registered", False):
        return {"registered": True, "evaluationOnly": True}
    service = load_service()
    router = APIRouter()

    def json_response(value, status=200):
        return JSONResponse(value, status_code=status, headers=service.SECURITY_HEADERS)

    @router.get(PREFIX + "/status")
    @router.get(PREFIX + "/healthz")
    def status():
        return json_response(service.status_snapshot())

    @router.get(PREFIX + "/ledger")
    def ledger():
        code, value = service.ledger_snapshot()
        return json_response(value, code)

    @router.get(PREFIX + "/prove")
    def prove():
        return json_response(service.prove_matrix())

    async def collect_body(request):
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BODY:
                raise OverflowError("request body exceeds 256 KiB")
            chunks.append(chunk)
        return b"".join(chunks)

    @router.post(PREFIX + "/{operation}")
    async def inspect_policy(operation: str, request: Request):
        if operation not in {"authorize", "evaluate", "bind"}:
            return json_response({"error": "unknown operation"}, 404)
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip()
            != "application/json"
        ):
            return json_response({"error": "application/json required"}, 415)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return json_response({"error": "cross-origin inspection rejected"}, 403)
        try:
            raw = await asyncio.wait_for(collect_body(request), timeout=5)
            payload = service.decode_json(raw)
        except OverflowError as exc:
            return json_response({"error": str(exc)}, 413)
        except asyncio.TimeoutError:
            return json_response({"error": "request body timeout"}, 408)
        except (ValueError, UnicodeError, RecursionError):
            return json_response({"error": "invalid JSON object"}, 400)
        code, value = service.evaluate_request(operation, payload)
        return json_response(value, code)

    @router.get("/anatomy-ledger", include_in_schema=False)
    def redirect():
        return RedirectResponse("/anatomy-ledger/", status_code=307)

    @router.get("/anatomy-ledger/", include_in_schema=False)
    @router.get("/anatomy-ledger/{asset}", include_in_schema=False)
    def dashboard(asset: str = "index.html"):
        if "/" + asset not in service.STATIC_ROUTES:
            return json_response({"error": "unknown asset"}, 404)
        try:
            body, content_type = service.read_static("/" + asset)
        except (OSError, ValueError):
            return json_response({"error": "dashboard asset unavailable"}, 503)
        return Response(body, media_type=content_type, headers=service.SECURITY_HEADERS)

    # Include then front-move only this registrar's routes ahead of the existing SPA.
    existing = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[existing:]
    del app.router.routes[existing:]
    app.router.routes[0:0] = added
    app.state.anatomy_ledger_registered = True
    return {"registered": True, "evaluationOnly": True, "routeCount": len(added)}
