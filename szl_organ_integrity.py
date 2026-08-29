#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
# Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
"""Fail-closed five-organ integrity kernel for a-11-oy.com.

GET/POST /api/a11oy/v1/organs/integrity
HTML     /organs/integrity

Stdlib SHA-256. Energy UNAVAILABLE. Λ = Conjecture 1 OPEN. proven_trust false.
The 3D atlas is the map; this is the body. Additive FastAPI register() that
moves routes to the front so they beat the SPA catch-all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from organ_integrity import envelope, evaluate_anatomy, parse_flags, selftest

_PAGES = Path(__file__).resolve().parent / "pages"
_PAGE = _PAGES / "organs-integrity.html"

API_PATHS = (
    "/api/{ns}/v1/organs/integrity",
    "/api/organs/integrity",
    "/v1/organs/integrity",
)


def _flags_from_request(request: Any, body: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(body, dict) and body:
        return parse_flags(body)
    try:
        params = dict(request.query_params)
    except Exception:
        params = {}
    return parse_flags(params)


def register(app: Any, ns: str = "a11oy") -> str:
    """Mount kernel API + Evidence Bay ahead of SPA fallbacks."""
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from starlette.routing import Route

    paths = tuple(p.format(ns=ns) for p in API_PATHS)

    async def _integrity(request: Any) -> JSONResponse:
        data: dict[str, Any] | None = None
        if request.method == "POST":
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            data = payload if isinstance(payload, dict) else {}
        flags = _flags_from_request(request, data)
        ev = evaluate_anatomy(**flags)
        return JSONResponse(envelope(ev))

    async def _page(request: Any = None) -> Any:
        if _PAGE.is_file():
            return FileResponse(_PAGE, media_type="text/html")
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>organ integrity</title>"
            "<p>kernel live. GET /api/a11oy/v1/organs/integrity</p>"
        )

    routes = [Route(path, _integrity, methods=["GET", "HEAD", "POST"]) for path in paths]
    routes.append(Route("/organs/integrity", _page, methods=["GET", "HEAD"]))
    app.router.routes[0:0] = routes
    print(
        f"[a11oy] organ-integrity kernel registered: {paths[0]} + /organs/integrity "
        f"[moved {len(routes)} routes to front]",
        file=sys.stderr,
    )
    try:
        import szl_n25_organs as _n25
        n25 = _n25.register(app, ns)
    except Exception as _n25_e:  # pragma: no cover
        n25 = f"n25-skip {_n25_e!r}"
        print(f"[a11oy] N1–N25 organs NOT registered: {_n25_e!r}", file=sys.stderr)
    return f"organ-integrity-ok routes={len(routes)} n25={n25}"


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2))
