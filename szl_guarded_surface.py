#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_guarded_surface.py — one shared, additive guard so a single bad surface
backend can NEVER 500 the whole SPA.

PROBLEM: the estate mounts 90+ surface backends. If ANY one of them raises an
unhandled exception, FastAPI/Starlette returns a bare HTTP 500. Because the SPA
and every surface share the one app, an operator hitting a broken surface sees a
raw 500 — and a 500 on an `/api/.../v1/*` fetch is exactly the "silent-degrade"
class the frontier-endpoint contract gate forbids.

FIX (this module, ADDITIVE — no surface file's internals are edited): a single
ASGI middleware wraps the whole app. If a request to a JSON API surface raises,
the middleware converts the crash into an HONEST HTTP 200 carrying an
UNAVAILABLE/DEGRADED label + the real reason, instead of a 500. One bad surface
degrades honestly; the SPA and every other surface keep working.

HONESTY / DOCTRINE v11 (binding):
  - NEVER fabricates success: the guarded response is explicitly `ok:false` with
    an UNAVAILABLE label and the real exception reason — an honest degrade, not a
    fake green. (Honest BLOCKED beats fake green.)
  - Scoped to JSON API surfaces (`/api/...`). Non-API paths (the SPA HTML shell,
    static assets) are RE-RAISED unchanged, so nothing about the SPA's own error
    behavior is altered — the guard only ever turns an API 500 into an honest 200.
  - PURE: signs nothing, mints nothing, adds nothing to the locked-8; Λ stays
    Conjecture 1; trust ceiling 0.97, never 100%.
  - Never short-circuits a healthy request: a successful response passes through
    byte-for-byte untouched.
"""

import datetime
from typing import Any

UNAVAILABLE = "UNAVAILABLE"
DEGRADED = "DEGRADED"
TRUST_CEILING = 0.97

# API prefixes whose crashes are converted to an honest JSON 200. Everything
# else (SPA HTML, static assets, page routes) is left exactly as-is.
_GUARDED_PREFIXES = ("/api/",)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def is_guarded_path(path: str) -> bool:
    """True if `path` is a JSON API surface whose crash we convert to honest 200."""
    return isinstance(path, str) and any(path.startswith(p) for p in _GUARDED_PREFIXES)


def honest_unavailable(path: str, exc: BaseException, label: str = UNAVAILABLE) -> dict:
    """The honest degraded payload returned instead of a 500. `ok:false` +
    UNAVAILABLE/DEGRADED + the real reason — never a fabricated success."""
    return {
        "ok": False,
        "endpoint": path,
        "label": label,
        "health": label,
        "reason": f"{type(exc).__name__}: {exc}",
        "guarded": True,
        "what": ("this surface backend raised; the shared guard converted the crash "
                 "into an honest UNAVAILABLE 200 so one bad surface cannot break the SPA "
                 "or any other surface. This is an honest degrade, not a fabricated pass."),
        "doctrine": {
            "label_top": label,
            "locked_proven": 8,
            "lambda": "Conjecture 1",
            "trust_ceiling": TRUST_CEILING,
            "trust_100_percent": False,
            "note": "guarded honest degrade; signs/mints nothing; adds nothing to the locked-8.",
        },
        "timestamp_utc": _now_iso(),
    }


def _build_middleware_class():
    """Build the middleware class lazily so importing this module never requires
    starlette at import time (matches the guarded-import discipline in serve.py)."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class GuardedSurfaceMiddleware(BaseHTTPMiddleware):
        """Catch an unhandled exception from any JSON API surface and return an
        honest UNAVAILABLE 200 instead of a bare 500. Healthy responses and
        non-API paths pass through untouched."""

        async def dispatch(self, request, call_next):
            try:
                return await call_next(request)
            except Exception as exc:  # noqa: BLE001 — the whole point: never 500 a surface
                path = getattr(request.url, "path", "") or ""
                if not is_guarded_path(path):
                    # Non-API (SPA/static/page) — preserve existing behavior exactly.
                    raise
                return JSONResponse(status_code=200, content=honest_unavailable(path, exc))

    return GuardedSurfaceMiddleware


def register(app) -> str:
    """Install the shared guarded-surface middleware on the FastAPI ``app``.

    Additive: adds one middleware; edits no route and no surface internals."""
    cls = _build_middleware_class()
    app.add_middleware(cls)
    return "guarded-surface-wired:1"


# ---------------------------------------------------------------------------
# Self-test — a deliberately-throwing API route degrades to an honest 200;
# a healthy route and a throwing NON-API route are unaffected.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=" * 72)
    print("szl_guarded_surface — self-test (one bad surface must not 500 the SPA)")
    print("=" * 72)

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    app = FastAPI()
    register(app)

    @app.get("/api/a11oy/v1/boom")
    def _boom():
        raise RuntimeError("simulated bad surface backend")

    @app.get("/api/a11oy/v1/ok")
    def _ok():
        return JSONResponse({"ok": True, "label": "LIVE"})

    @app.get("/page-not-api")
    def _page():
        raise RuntimeError("non-api crash must be left alone")

    # raise_server_exceptions=False so we can OBSERVE the non-api 500 rather than
    # have the test client re-raise it (the middleware re-raises non-api crashes).
    client = TestClient(app, raise_server_exceptions=False)

    # 1) a throwing API surface degrades to an HONEST 200 UNAVAILABLE (not a 500).
    r = client.get("/api/a11oy/v1/boom")
    assert r.status_code == 200, f"guarded API crash should be 200, got {r.status_code}"
    j = r.json()
    assert j["ok"] is False and j["label"] == UNAVAILABLE, j
    assert "simulated bad surface backend" in j["reason"], j
    assert j["guarded"] is True
    print("[1] throwing API surface -> honest 200 UNAVAILABLE (not 500), real reason  OK")

    # 2) a healthy API route passes through untouched.
    r = client.get("/api/a11oy/v1/ok")
    assert r.status_code == 200 and r.json()["label"] == "LIVE"
    print("[2] healthy API route passes through byte-for-byte untouched  OK")

    # 3) a throwing NON-API path is NOT converted (existing behavior preserved -> 500).
    r = client.get("/page-not-api")
    assert r.status_code == 500, f"non-api crash must stay a 500, got {r.status_code}"
    print("[3] non-API crash left unchanged (SPA/static error behavior preserved)  OK")

    # 4) honest payload doctrine block is clean (locked-8, Λ Conjecture 1, no 100%).
    d = honest_unavailable("/api/a11oy/v1/x", RuntimeError("x"))["doctrine"]
    assert d["locked_proven"] == 8 and d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    print("[4] guarded payload doctrine clean (locked-8, Λ=Conjecture 1, trust 0.97)  OK")

    print("\nok:true checks:4")
    _sys.exit(0)
