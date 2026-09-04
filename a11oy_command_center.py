#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Serve the canonical A11oy Command Center on the product origin.

Product host: a-11-oy.com  (this surface)
Proof host:   a11oy.net    (do not serve this surface there)

Additive tabs:
  GET+HEAD /command
  GET+HEAD /command/constellation
  GET+HEAD /command/brain
  GET+HEAD /constellation   (host-root; declared so SPA fallback cannot 404 it)
  GET+HEAD /command/{rest}

Host-root /brain is Hickok dual-stream. Do not steal it.
"""
from pathlib import Path
from typing import List

MOUNTS = ("/command",)
SPECIFIC = (
    ("/command/constellation", "constellation.html"),
    ("/command/brain", "second-brain.html"),
    ("/constellation", "constellation.html"),
)
CATCHALL = "/command/{rest:path}"


def _spa_path() -> Path:
    here = Path(__file__).resolve().parent
    candidates = (
        here / "web" / "elite_console.html",
        Path("/app/web/elite_console.html"),
        here / "pages" / "command-center.html",
        Path("/app/pages/command-center.html"),
        here / "command-center.html",
    )
    for cand in candidates:
        if cand.is_file():
            return cand
    return here / "web" / "elite_console.html"


def _page(name: str) -> Path:
    here = Path(__file__).resolve().parent
    for cand in (here / "pages" / name, Path("/app/pages") / name):
        if cand.is_file():
            return cand
    return here / "pages" / name


def _existing_paths(app) -> set:
    try:
        router = getattr(app, "router", app)
        return {getattr(r, "path", None) for r in getattr(router, "routes", [])}
    except Exception:
        return set()


def _drop_paths(app, paths: set) -> None:
    """Remove exact path registrations so we can replace SPA stubs."""
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    keep = [r for r in list(routes) if getattr(r, "path", None) not in paths]
    routes[:] = keep


def _front_move(app, paths: list) -> None:
    """Park exact routes at the front, in given order. Never include the catch-all."""
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    wanted = set(paths)
    chosen = [r for r in routes if getattr(r, "path", None) in wanted]
    if not chosen:
        return
    for r in chosen:
        try:
            routes.remove(r)
        except ValueError:
            pass
    order = {p: i for i, p in enumerate(paths)}
    chosen.sort(key=lambda r: order.get(getattr(r, "path", ""), 99))
    for r in reversed(chosen):
        routes.insert(0, r)


def register(app, ns: str = "a11oy") -> List[str]:
    del ns
    spa = _spa_path()
    registered: List[str] = []
    if not spa.is_file():
        return [f"command-center SPA missing at {spa}"]

    from starlette.responses import FileResponse, JSONResponse
    from starlette.routing import Route

    async def _spa(_request=None, rest: str = ""):
        del rest
        return FileResponse(spa, media_type="text/html; charset=utf-8")

    def _file(name: str):
        async def _handler(_request=None):
            page = _page(name)
            if page.is_file():
                return FileResponse(page, media_type="text/html; charset=utf-8")
            return JSONResponse(
                {
                    "status": "NOT_FOUND",
                    "reason": "constellation page missing from image",
                    "page": name,
                },
                status_code=404,
            )
        return _handler

    specific_paths = {path for path, _name in SPECIFIC}
    _drop_paths(app, specific_paths)
    existing = _existing_paths(app)
    mounted: set = set()
    router = getattr(app, "router", app)

    def _add(path: str, handler, methods: List[str]) -> None:
        if path in existing and path != CATCHALL:
            registered.append("%s already registered (skipped)" % path)
            return
        try:
            router.routes.insert(0, Route(path, handler, methods=methods))
        except Exception:
            app.add_api_route(path, handler, methods=methods, include_in_schema=False)
        existing.add(path)
        mounted.add(path)
        registered.append("GET+HEAD %s" % path)

    for path in MOUNTS:
        _add(path, _spa, ["GET", "HEAD"])
    for path, name in SPECIFIC:
        _add(path, _file(name), ["GET", "HEAD"])
    _add(CATCHALL, _spa, ["GET", "HEAD"])
    _front_move(app, [path for path, _name in SPECIFIC] + list(MOUNTS))
    registered.append("command-center on /command (constellation/brain beat catch-all; /brain host-root untouched)")
    return registered


def _selftest() -> None:
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    spa = _spa_path()
    assert spa.is_file(), spa
    html = spa.read_text(encoding="utf-8")
    assert ("Elite Console" in html) or ("a11oy Command Center" in html)
    if spa.name == "elite_console.html":
        assert "20 fully-functional tabs" in html
        assert "/api/a11oy/" in html
        assert "zero mocks" in html.lower()
    assert "cdnjs" not in html and "googleapis" not in html and "jsdelivr" not in html
    assert "Conjecture 1" in html

    async def _console(_req):
        return HTMLResponse("<html><body>operator console</body></html>")

    async def _hickok(_req):
        return HTMLResponse("<html><body>Hickok dual-stream</body></html>")

    app = Starlette(routes=[Route("/console", _console), Route("/brain", _hickok)])
    out = register(app, ns="a11oy")
    assert any("/command" in row for row in out), out
    c = TestClient(app)
    for path in ("/command", "/command/anatomy", "/command/honest"):
        r = c.get(path)
        assert r.status_code == 200, (path, r.status_code)
    if _page("constellation.html").is_file():
        for path in ("/command/constellation", "/constellation"):
            body = c.get(path).text
            assert "Constellation" in body, path
            assert "Control before capability" not in body
    if _page("second-brain.html").is_file():
        br = c.get("/command/brain")
        assert br.status_code == 200
        assert "Second Brain" in br.text
        assert "F1" in br.text
    assert "Hickok" in c.get("/brain").text
    assert c.get("/console").status_code == 200
    print("a11oy_command_center: ALL OK (constellation beats catch-all; /brain host-root untouched)")


if __name__ == "__main__":
    _selftest()
