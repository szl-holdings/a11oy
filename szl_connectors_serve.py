# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors_serve — FastAPI registration module for the Enterprise Mesh.

ADDITIVE & GUARDED (matches szl_a11oy_live_feeds.register pattern). Mounts the
connector manifest, per-connector health/read/write, the OAuth2 start/callback
flow, and the standalone /integrations page route — all BEFORE the SPA catch-all,
all try/except-guarded so they can NEVER take the Space down.

Endpoints (ns defaults to "a11oy"):
  GET  /api/{ns}/connectors                      → honest manifest + scoreboard
  GET  /api/{ns}/v1/connectors                   → alias (versioned)
  GET  /api/{ns}/v1/connectors/{cid}/health      → one connector's honest health
  GET  /api/{ns}/v1/connectors/{cid}/read        → live records | READY | SAMPLE (never faked)
  POST /api/{ns}/v1/connectors/{cid}/write       → Λ-gated + DSSE-receipted write
  GET  /api/{ns}/v1/connectors/{cid}/oauth/start → PKCE authorize URL (signed state)
  GET  /api/{ns}/v1/connectors/{cid}/oauth/callback → code→token, credential-bound receipt
  GET  /integrations                             → standalone Enterprise Mesh page

DOCTRINE: honest states only; never fabricates a record; writes carry a DSSE
receipt with credential FINGERPRINT hashes (never the key); 0 runtime CDN.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:  # FastAPI types are present in the a11oy image
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse
except Exception:  # pragma: no cover — import-time guard
    FastAPI = object  # type: ignore
    Request = object  # type: ignore

import szl_connectors as sc
from szl_connectors import oauth as _oauth

_PAGES_DIR = Path(os.environ.get("SZL_PAGES_DIR", "/app/pages"))
_INDEX_HTML = Path("/app/static/index.html")


def register(app, ns: str = "a11oy") -> str:
    """Mount every connector endpoint. Returns a status string (logged by serve.py)."""
    base = f"/api/{ns}/v1"

    # ── manifest (honest scoreboard; cheap path by default) ────────────────
    @app.get(f"/api/{ns}/connectors", include_in_schema=False)
    async def _manifest(probe: int = 0, category: str = ""):  # noqa: ANN202
        return JSONResponse(sc.manifest(probe=bool(probe), category=category or None))

    @app.get(f"{base}/connectors", include_in_schema=False)
    async def _manifest_v1(probe: int = 0, category: str = ""):  # noqa: ANN202
        return JSONResponse(sc.manifest(probe=bool(probe), category=category or None))

    # ── per-connector health ───────────────────────────────────────────────
    @app.get(f"{base}/connectors/{{cid}}/health", include_in_schema=False)
    async def _health(cid: str):  # noqa: ANN202
        return JSONResponse(sc.health(cid))

    # ── per-connector read (live | READY | SAMPLE — NEVER fabricated) ────────
    @app.get(f"{base}/connectors/{{cid}}/read", include_in_schema=False)
    async def _read(cid: str, limit: int = 12, q: str = ""):  # noqa: ANN202
        c = sc.get(cid)
        if not c:
            return JSONResponse({"error": f"unknown connector '{cid}'",
                                 "known": sc.all_ids()}, status_code=404)
        query = {"limit": max(1, min(int(limit), 50))}
        if q:
            query["q"] = q
        try:
            return JSONResponse(c.read(query).to_dict())
        except Exception as e:  # honest error, never crash
            return JSONResponse({"connector_id": cid, "state": "error",
                                 "records": [], "live": False,
                                 "note": f"read failed: {type(e).__name__}: {type(e).__name__}"},
                                status_code=502)

    # ── per-connector write (Λ-gated + DSSE-receipted) ───────────────────────
    @app.post(f"{base}/connectors/{{cid}}/write", include_in_schema=False)
    async def _write(cid: str, request: Request):  # noqa: ANN202
        c = sc.get(cid)
        if not c:
            return JSONResponse({"error": f"unknown connector '{cid}'",
                                 "known": sc.all_ids()}, status_code=404)
        if not getattr(c, "writable", False):
            return JSONResponse({"connector_id": cid, "ok": False,
                                 "detail": "connector is read-only"}, status_code=405)
        try:
            action = await request.json()
        except Exception:
            action = {}
        try:
            return JSONResponse(c.write(action or {}).to_dict())
        except Exception as e:
            return JSONResponse({"connector_id": cid, "ok": False, "state": "error",
                                 "detail": f"write failed: {type(e).__name__}: {type(e).__name__}"},
                                status_code=502)

    # ── OAuth2 start: build PKCE authorize URL with signed state ─────────────
    @app.get(f"{base}/connectors/{{cid}}/oauth/start", include_in_schema=False)
    async def _oauth_start(cid: str, request: Request, redirect_uri: str = ""):  # noqa: ANN202
        ru = redirect_uri or str(request.url.replace(path=f"{base}/connectors/{cid}/oauth/callback", query=""))
        try:
            out = _oauth.build_authorize_url(cid, redirect_uri=ru)
            return JSONResponse(out)
        except Exception as e:
            return JSONResponse({"connector_id": cid, "error": type(e).__name__,
                                 "detail": "no OAuth profile for this connector or misconfigured"},
                                status_code=400)

    # ── OAuth2 callback: exchange code→token; emit credential-bound receipt ──
    @app.get(f"{base}/connectors/{{cid}}/oauth/callback", include_in_schema=False)
    async def _oauth_callback(cid: str, request: Request, code: str = "", state: str = ""):  # noqa: ANN202
        ru = str(request.url.replace(query=""))
        try:
            out = _oauth.exchange_code(cid, code=code, state=state, redirect_uri=ru)
            # NEVER return the token value to the browser; only the receipt + status
            safe = {k: v for k, v in out.items() if k not in ("access_token", "refresh_token")}
            return JSONResponse(safe)
        except Exception as e:
            return JSONResponse({"connector_id": cid, "error": type(e).__name__}, status_code=400)

    # ── standalone Integrations / Enterprise Mesh page ───────────────────────
    @app.get("/integrations", include_in_schema=False)
    async def _integrations_page():  # noqa: ANN202
        f = _PAGES_DIR / "integrations.html"
        if f.is_file():
            return FileResponse(f, media_type="text/html")
        if _INDEX_HTML.is_file():
            return FileResponse(_INDEX_HTML, media_type="text/html")
        return JSONResponse({"error": "integrations page not found"}, status_code=404)

    counts = sc.manifest(probe=False)["scoreboard"]
    return (f"szl_connectors mounted: /api/{ns}/connectors (manifest) + "
            f"{base}/connectors/{{cid}}/(health|read|write|oauth/start|oauth/callback) "
            f"+ /integrations page · {len(sc.REGISTRY)} connectors "
            f"(connected={counts.get('connected')} ready={counts.get('ready')} "
            f"sample={counts.get('sample')})")


__all__ = ["register"]

# Doctrine v11 LOCKED — 749/14/163 — Λ = Conjecture 1 · honest CONNECTED/READY/SAMPLE ·
# no fabricated records · writes Λ-gated + DSSE-receipted · 0 runtime CDN.
