# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
szl_code_proxy — /api/<space>/v1/code-proxy forwarder (Doctrine v11 §14).

ADDITIVE module for the 6 sibling Spaces (amaru, sentra, vessels, killinchu, rosie,
uds-demo). Forwards a code-route request to the a11oy.code router and returns its
response verbatim, annotated with the forwarding hop. Honest degrade: if a11oy is
unreachable, returns {"proxied": False, "reason": ...} (ZERO BANDAID).
"""
from __future__ import annotations

import os
from typing import Any, Dict

# Import Request/JSONResponse at MODULE level: FastAPI resolves a route handler's
# annotations against the ENCLOSING MODULE'S globals. If `Request` is only imported
# inside register_code_proxy(), FastAPI cannot resolve the annotation and mis-treats
# `request` as a required query param (HTTP 422). Module-level import fixes this.
from starlette.requests import Request
from fastapi.responses import JSONResponse

A11OY_CODE_URL = os.environ.get(
    "A11OY_CODE_URL", "https://szlholdings-a11oy.hf.space/api/a11oy/v1/code/route"
)


def register_code_proxy(app, space: str, path_override: str | None = None):
    """Attach POST /api/<space>/v1/code-proxy that forwards to a11oy.code. ADDITIVE.

    If the target app is a sub-app mounted at /api/<space> (e.g. amaru's amaru_app),
    pass path_override="/v1/code-proxy" so the route resolves correctly behind the mount.
    """
    _path = path_override if path_override is not None else f"/api/{space}/v1/code-proxy"

    @app.post(_path)
    async def _code_proxy(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        # propagate organ_context = this space's organ by default
        body.setdefault("organ_context", space)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(A11OY_CODE_URL, json=body)
                data = r.json()
            return JSONResponse({
                "proxied": True,
                "via": f"{space} → a11oy.code",
                "upstream_status": r.status_code,
                "result": data,
                "doctrine": "v11",
            })
        except Exception as e:
            return JSONResponse({
                "proxied": False,
                "via": f"{space} → a11oy.code",
                "reason": f"{type(e).__name__}: {e}",
                "upstream": A11OY_CODE_URL,
                "doctrine": "v11",
            }, status_code=502)

    return app
