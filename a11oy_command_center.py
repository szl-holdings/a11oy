#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Serve the canonical A11oy Command Center on the product origin.

Product host: a-11-oy.com  (this surface)
Proof host:   a11oy.net    (do not serve this surface there)

Additive tabs. Host-root mounts exist because /command/{rest} was swallowing
/command/constellation and /command/brain on the live image.

  GET+HEAD /command
  GET+HEAD /command/constellation
  GET+HEAD /command/brain
  GET+HEAD /constellation
  GET+HEAD /brain
  GET+HEAD /command/{rest}
"""
from pathlib import Path
from typing import List

MOUNTS = ("/command",)


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


def _front_move(app, paths: set) -> None:
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    chosen = [r for r in routes if getattr(r, "path", None) in paths]
    if not chosen:
        return
    for r in chosen:
        try:
            routes.remove(r)
        except ValueError:
            pass
    for r in reversed(chosen):
        routes.insert(0, r)


def register(app, ns: str = "a11oy") -> List[str]:
    del ns
    spa = _spa_path()
    registered: List[str] = []
    if not spa.is_file():
        return [f"command-center SPA missing at {spa}"]

    from starlette.responses import FileResponse
    from starlette.routing import Route

    async def _spa(_request=None, rest: str = ""):
        del rest
        return FileResponse(spa, media_type="text/html; charset=utf-8")

    def _file(name: str):
        async def _handler(_request=None):
            page = _page(name)
            if page.is_file():
                return FileResponse(page, media_type="text/html; charset=utf-8")
            return FileResponse(spa, media_type="text/html; charset=utf-8")
        return _handler

    existing = _existing_paths(app)
    mounted: set = set()
    router = getattr(app, "router", app)

    def _add(path: str, handler, methods: List[str]) -> None:
        if path in existing and path != "/command/{rest:path}":
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
    _add("/command/constellation", _file("constellation.html"), ["GET", "HEAD"])
    _add("/command/brain", _file("second-brain.html"), ["GET", "HEAD"])
    _add("/constellation", _file("constellation.html"), ["GET", "HEAD"])
    _add("/brain", _file("second-brain.html"), ["GET", "HEAD"])
    _add("/command/{rest:path}", _spa, ["GET", "HEAD"])
    extra = {
        "/command/constellation",
        "/command/brain",
        "/constellation",
        "/brain",
        "/command/{rest:path}",
    }
    _front_move(app, mounted | set(MOUNTS) | extra)
    registered.append("command-center on /command (does not steal /console; not a landing door)")
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

    app = Starlette(routes=[Route("/console", _console)])
    out = register(app, ns="a11oy")
    assert any("/command" in row for row in out), out
    c = TestClient(app)
    for path in ("/command", "/command/anatomy", "/command/honest"):
        r = c.get(path)
        assert r.status_code == 200, (path, r.status_code)
    if _page("constellation.html").is_file():
        assert "Constellation" in c.get("/command/constellation").text
        assert "Constellation" in c.get("/constellation").text
    if _page("second-brain.html").is_file():
        br = c.get("/command/brain")
        assert br.status_code == 200 and "Second Brain" in br.text
        assert "Second Brain" in c.get("/brain").text
    assert c.get("/console").status_code == 200
    print("a11oy_command_center: ALL OK (root /brain + /constellation; /console untouched)")


if __name__ == "__main__":
    _selftest()
