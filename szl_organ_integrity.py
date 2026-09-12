#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
# Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
"""Fail-closed five-organ integrity kernel for a-11-oy.com.

GET/POST /api/a11oy/v1/organs/integrity
GET/POST /api/a11oy/v1/kernel/probe
HTML     /organs/integrity

Empty JSON bind is UNKNOWN — never locked-8, never LIVE, never ADMIT.
Silhouette demo requires an explicit silhouette=true or tamper flag.

Stdlib SHA-256. Energy UNAVAILABLE. Λ = Conjecture 1 OPEN. proven_trust false.
The 3D atlas is the map; this is the body. Additive FastAPI register() that
moves routes to the front so they beat the SPA catch-all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from organ_integrity import (
    anatomy_kwargs,
    envelope,
    evaluate_anatomy,
    selftest,
    unknown_bind,
    wants_silhouette,
)

_PAGES = Path(__file__).resolve().parent / "pages"
_PAGE = _PAGES / "organs-integrity.html"

API_PATHS = (
    "/api/{ns}/v1/organs/integrity",
    "/api/organs/integrity",
    "/v1/organs/integrity",
)
PROBE_PATHS = (
    "/api/{ns}/v1/kernel/probe",
    "/api/kernel/probe",
    "/kernel/probe",
)


def _request_map(request: Any, body: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(body, dict) and body:
        return body
    try:
        return dict(request.query_params)
    except Exception:
        return {}


def register(app: Any, ns: str = "a11oy") -> str:
    """Mount kernel API + Evidence Bay ahead of SPA fallbacks."""
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from starlette.routing import Route

    paths = tuple(p.format(ns=ns) for p in API_PATHS)
    probes = tuple(p.format(ns=ns) for p in PROBE_PATHS)

    async def _body(request: Any) -> dict[str, Any]:
        if request.method != "POST":
            return {}
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    async def _integrity(request: Any) -> JSONResponse:
        data = await _body(request)
        src = _request_map(request, data)
        if not wants_silhouette(src):
            return JSONResponse(unknown_bind("szl-organ-integrity"))
        ev = evaluate_anatomy(**anatomy_kwargs(src))
        return JSONResponse(envelope(ev))

    async def _probe(request: Any) -> JSONResponse:
        data = await _body(request)
        src = _request_map(request, data)
        if wants_silhouette(src):
            ev = evaluate_anatomy(**anatomy_kwargs(src))
            packed = envelope(ev)
            packed["surface"] = "szl-kernel-probe"
            packed["decision"] = ev.get("verdict")
            packed["honesty"] = "SILHOUETTE"
            packed["certified_production_ready"] = False
            packed["halt_drone"] = "BLOCKED"
            return JSONResponse(packed)
        return JSONResponse(unknown_bind("szl-kernel-probe"))

    async def _page(request: Any = None) -> Any:
        if _PAGE.is_file():
            return FileResponse(_PAGE, media_type="text/html")
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>organ integrity</title>"
            "<p>kernel probe. POST /api/a11oy/v1/kernel/probe {} → UNKNOWN</p>"
        )

    routes = [Route(path, _integrity, methods=["GET", "HEAD", "POST"]) for path in paths]
    routes.extend(Route(path, _probe, methods=["GET", "HEAD", "POST"]) for path in probes)
    routes.append(Route("/organs/integrity", _page, methods=["GET", "HEAD"]))
    app.router.routes[0:0] = routes
    print(
        f"[a11oy] organ-integrity kernel registered: {paths[0]} + {probes[0]} + /organs/integrity "
        f"[moved {len(routes)} routes to front]",
        file=sys.stderr,
    )
    return f"organ-integrity-ok routes={len(routes)}"


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2))
