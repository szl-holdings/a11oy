"""Wave-R Dev 2 — shared guarded-surface wrapper contract guard.

One bad surface backend must NEVER 500 the whole SPA. szl_guarded_surface
installs one additive ASGI middleware that converts an unhandled exception from
any JSON API surface (/api/…) into an HONEST 200 (ok:false, UNAVAILABLE + the
real reason), while leaving non-API paths (SPA HTML / static) unchanged.

This guard proves, in-process with no network:

  1. On a deterministic FRESH app: a throwing /api route degrades to an honest
     200 UNAVAILABLE (never a 500), a healthy route passes through untouched, and
     a throwing NON-api route is left as a 500 (existing behavior preserved).
  2. On the REAL serve.app: the middleware is installed, and a deliberately-
     throwing /api surface (front-inserted, then removed) degrades to an honest
     200 UNAVAILABLE inside the FULL middleware stack — not a bare 500.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
import pytest

pytest.importorskip("starlette.testclient")
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.routing import Route  # noqa: E402

import szl_guarded_surface as guard  # noqa: E402


def _fresh_app():
    app = FastAPI()
    guard.register(app)

    @app.get("/api/a11oy/v1/boom")
    def _boom():
        raise RuntimeError("simulated bad surface backend")

    @app.get("/api/a11oy/v1/ok")
    def _ok():
        return JSONResponse({"ok": True, "label": "LIVE"})

    @app.get("/page-not-api")
    def _page():
        raise RuntimeError("non-api crash must be left alone")

    return app


def test_throwing_api_surface_degrades_to_honest_200():
    c = TestClient(_fresh_app(), raise_server_exceptions=False)
    r = c.get("/api/a11oy/v1/boom")
    assert r.status_code == 200, f"guarded API crash should be 200, got {r.status_code}"
    j = r.json()
    assert j["ok"] is False and j["label"] == "UNAVAILABLE" and j["guarded"] is True
    assert "simulated bad surface backend" in j["reason"]
    d = j["doctrine"]
    assert d["locked_proven"] == 8 and d["lambda"] == "Conjecture 1"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False


def test_healthy_api_route_passes_through():
    c = TestClient(_fresh_app(), raise_server_exceptions=False)
    r = c.get("/api/a11oy/v1/ok")
    assert r.status_code == 200 and r.json()["label"] == "LIVE"


def test_non_api_crash_is_unchanged():
    c = TestClient(_fresh_app(), raise_server_exceptions=False)
    r = c.get("/page-not-api")
    assert r.status_code == 500, "non-api crash must stay a 500 (SPA/static unchanged)"


def test_guard_installed_and_works_on_real_serve_app():
    import serve
    names = [type(m).__name__ if hasattr(m, "__name__") is False else getattr(m, "cls", m)
             for m in getattr(serve.app, "user_middleware", [])]
    # The middleware class name should appear in the stack.
    stack = " ".join(str(getattr(m, "cls", m)) for m in serve.app.user_middleware)
    assert "GuardedSurfaceMiddleware" in stack, f"guard not installed: {stack}"

    async def _boom(request):
        raise RuntimeError("waver guard real-app probe")

    path = "/api/a11oy/v1/__waver_guard_probe__"
    route = Route(path, _boom, methods=["GET"])
    serve.app.router.routes.insert(0, route)
    try:
        with TestClient(serve.app) as c:  # default raises if anything escapes the guard
            r = c.get(path)
        assert r.status_code == 200, f"real-app guarded crash should be 200, got {r.status_code}"
        j = r.json()
        assert j["ok"] is False and j["label"] == "UNAVAILABLE"
        assert "waver guard real-app probe" in j["reason"]
    finally:
        serve.app.router.routes.remove(route)
