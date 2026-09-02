#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Serve the canonical A11oy Command Center on the product origin.

Product host: a-11-oy.com  (this surface)
Proof host:   a11oy.net    (do not serve this surface there)

The canonical /command surface now prefers the existing 20-tab Elite Console,
which is backed by real /api/a11oy/... endpoints through szl_elite_console.py.
The older public command-center SPA remains an explicit fallback only if the
Elite Console asset is absent from a constrained build.

Bound path only. Does not edit the landing door and does not steal /console,
which remains the operator runtime. Mounts:

  GET+HEAD /command
  GET+HEAD /command/{rest}

/command-center is 307'd onto /command by serve.py.
"""
from pathlib import Path
from typing import List

MOUNTS = ("/command",)


def _spa_path() -> Path:
    """Resolve the richest shipped Command Center, fail-soft to legacy UI."""
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
    """Mount the canonical Command Center. Additive; skips existing paths."""
    del ns  # surface is host-level, not namespaced
    spa = _spa_path()
    registered: List[str] = []
    if not spa.is_file():
        return [f"command-center SPA missing at {spa}"]

    from starlette.responses import FileResponse
    from starlette.routing import Route

    async def _spa(_request=None, rest: str = ""):
        del rest
        return FileResponse(spa, media_type="text/html; charset=utf-8")

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
    _add("/command/{rest:path}", _spa, ["GET", "HEAD"])
    _front_move(app, mounted | set(MOUNTS) | {"/command/{rest:path}"})
    flavor = "elite-20-tab" if spa.name == "elite_console.html" else "legacy-fallback"
    registered.append(
        f"command-center {flavor} on /command (does not steal /console; not a landing door)"
    )
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
    for path in (
        "/command",
        "/command/overview",
        "/command/gates",
        "/command/alerts",
        "/command/anatomy",
        "/command/honest",
    ):
        r = c.get(path)
        assert r.status_code == 200, (path, r.status_code)
        assert ("Elite Console" in r.text) or ("a11oy Command Center" in r.text)
        h = c.head(path)
        assert h.status_code == 200, (path, h.status_code)
    op = c.get("/console")
    assert op.status_code == 200 and "operator console" in op.text
    print(
        "a11oy_command_center: ALL OK "
        f"({spa.name} on /command; /console untouched; 0 runtime CDN)"
    )


if __name__ == "__main__":
    _selftest()
