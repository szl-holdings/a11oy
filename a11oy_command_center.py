#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Serve the public Command Center SPA on the product origin.

Product host: a-11-oy.com  (this surface)
Proof host:   a11oy.net    (do not serve this surface there)

Does not steal existing /console (Python operator runtime). Mounts:

  /command  /origin  /zk  /invest  /build  /census
  /command/{rest}  (same SPA; client reads pathname)

Catch-all under /command/{path} returns the same document. Read-path only.
"""
from pathlib import Path
from typing import List

SPA_NAME = "command-center.html"
MOUNTS = (
    "/command",
    "/origin",
    "/zk",
    "/invest",
    "/build",
    "/census",
)


def _spa_path() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (
        here / "pages" / SPA_NAME,
        Path("/app/pages") / SPA_NAME,
        here / SPA_NAME,
    ):
        if cand.is_file():
            return cand
    return here / "pages" / SPA_NAME


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
    """Mount the Command Center SPA. Additive; skips paths already registered."""
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
    registered.append(
        "command-center SPA on /command /origin /zk /invest /build /census "
        "(does not steal /console or a11oy.net)"
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
    assert "a11oy Command Center" in html
    assert "https://a-11-oy.com/command" in html
    assert "/console" in html, "must keep a link to the operator console"
    assert "cdnjs" not in html and "googleapis" not in html and "jsdelivr" not in html
    assert "fonts.gstatic" not in html
    assert "Conjecture 1" in html
    assert "a11oy.net" in html

    async def _console(_req):
        return HTMLResponse("<html><body>operator console</body></html>")

    app = Starlette(routes=[Route("/console", _console)])
    out = register(app, ns="a11oy")
    assert any("/command" in row for row in out), out
    c = TestClient(app)
    for path in ("/command", "/zk", "/invest", "/build", "/census", "/origin", "/command/console"):
        r = c.get(path)
        assert r.status_code == 200, (path, r.status_code)
        assert "a11oy Command Center" in r.text
        h = c.head(path)
        assert h.status_code == 200, (path, h.status_code)
    op = c.get("/console")
    assert op.status_code == 200 and "operator console" in op.text
    print("a11oy_command_center: ALL OK (SPA mounts; /console untouched; 0 CDN)")


if __name__ == "__main__":
    _selftest()
