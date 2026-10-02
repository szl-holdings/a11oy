# SPDX-License-Identifier: Apache-2.0
"""Reserved GET-only API and verified static surface for the canonical host."""
import mimetypes
import os
import re
import threading
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from .core import API_PREFIX, API_OPERATIONS, Observatory, BusyError, ContractError

_ROOT = Path(__file__).resolve().parent
_LOCK = threading.Lock()
_SERVICE = None
_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"]
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-SZL-Civilian-Scope": "read-only-public-observations",
    "Cache-Control": "no-store",
}


def service():
    global _SERVICE
    with _LOCK:
        if _SERVICE is None:
            default = Path(os.environ.get("XDG_CACHE_HOME", "/tmp")) / "szl-civilian-observatory" / "public-cache.sqlite3"
            _SERVICE = Observatory(_ROOT, Path(os.environ.get("A11OY_CIVILIAN_CACHE", str(default))))
        return _SERVICE


def error(message, status):
    return JSONResponse(
        {"error": message, "scope": "EXPERIMENTAL_SOFTWARE", "external_effectors": [], "model_loaded": False},
        status_code=status, headers=_HEADERS,
    )


def create_handlers(service_factory=service):
    async def api(request: Request):
        if request.method != "GET":
            return JSONResponse({"error": "This namespace accepts GET observations only; no action or state-write API."},
                                status_code=405, headers={**_HEADERS, "Allow": "GET"})
        if request.headers.get("content-length", "0") != "0" or request.headers.get("transfer-encoding"):
            return error("Request bodies are not accepted in this observation namespace", 400)
        operation = request.path_params.get("operation") or request.url.path.removeprefix(API_PREFIX + "/")
        if operation not in API_OPERATIONS:
            return error("Unknown observation operation", 404)
        raw = request.scope.get("query_string", b"")
        if len(raw) > 2500:
            return error("Query exceeds the bounded request limit", 414)
        pairs = list(request.query_params.multi_items())
        if len({k for k, _ in pairs}) != len(pairs):
            return error("Duplicate query fields are not allowed", 400)
        try:
            owner = await run_in_threadpool(service_factory)
        except Exception:
            return error("Civilian payload or cache integrity is unavailable", 503)
        try:
            value = await run_in_threadpool(owner.handle, operation, dict(pairs))
            return JSONResponse(value, headers=_HEADERS)
        except ContractError:
            return error("Observation request contract rejected", 400)
        except BusyError:
            return JSONResponse({"error": "Public observation budget is busy; retry later."}, status_code=429,
                                headers={**_HEADERS, "Retry-After": "60"})
        except Exception:
            return error("Civilian evidence service unavailable; no observation is fabricated", 503)

    async def surface(request: Request):
        if request.method not in ("GET", "HEAD"):
            return JSONResponse({"error": "This surface is read-only."}, status_code=405,
                                headers={**_HEADERS, "Allow": "GET, HEAD"})
        if request.url.path == "/civilian":
            return RedirectResponse("/civilian/", status_code=307, headers=_HEADERS)
        asset = request.path_params.get("asset", "")
        relative = "static/" + (asset or "index.html")
        if "\\" in relative or ".." in Path(relative).parts or len(relative) > 250:
            return error("Unknown static asset", 404)
        try:
            owner = await run_in_threadpool(service_factory)
            # Only exact build-manifest entries are web-addressable.
            if relative not in owner.manifest["files"] or not relative.startswith("static/"):
                return error("Unknown static asset", 404)
            target = owner.root / relative
            if target.is_symlink() or not target.resolve().is_relative_to(owner.root):
                return error("Unadmitted static path", 404)
            body = await run_in_threadpool(target.read_bytes)
            import hashlib
            if hashlib.sha256(body).hexdigest() != owner.manifest["files"][relative]:
                return error("Static asset integrity check failed", 503)
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".js":
                mime = "application/javascript"
            headers = {**_HEADERS, "Content-Length": str(len(body))}
            if target.suffix == ".html":
                headers["Content-Security-Policy"] = (
                    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
                    "base-uri 'none'; form-action 'none'; object-src 'none'; "
                    "frame-ancestors 'self' https://huggingface.co"
                )
            else:
                headers["Cache-Control"] = "public, max-age=3600"
            return Response(content=b"" if request.method == "HEAD" else body, media_type=mime, headers=headers)
        except Exception:
            return error("Civilian static payload unavailable; no SPA fallback", 503)
    return api, surface


def register(app, service_factory=service):
    """Front-insert the complete namespace before both existing fallback routers."""
    existing = [getattr(route, "path", "") for route in app.router.routes]
    if API_PREFIX + "/{operation:path}" in existing:
        return {"registered": True, "state": "EXPERIMENTAL_SOFTWARE", "effectors": 0, "already_registered": True}
    api, surface = create_handlers(service_factory)
    before = len(app.router.routes)
    app.add_api_route(API_PREFIX + "/health", api, methods=_METHODS, include_in_schema=False)
    app.add_api_route(API_PREFIX + "/overview", api, methods=_METHODS, include_in_schema=False)
    app.add_api_route(API_PREFIX, api, methods=_METHODS, include_in_schema=False)
    app.add_api_route(API_PREFIX + "/{operation:path}", api, methods=_METHODS, include_in_schema=False)
    app.add_api_route("/civilian", surface, methods=_METHODS, include_in_schema=False)
    app.add_api_route("/civilian/{asset:path}", surface, methods=_METHODS, include_in_schema=False)
    additions = app.router.routes[before:]
    app.router.routes[:] = additions + app.router.routes[:before]
    return {
        "registered": True, "state": "EXPERIMENTAL_SOFTWARE", "api_policy": "GET_ONLY",
        "routes": [API_PREFIX + "/health", API_PREFIX + "/overview", "/civilian/"],
        "model_loaded": False, "effectors": 0, "signature_status": "UNSIGNED_SELF_ASSERTED",
    }
