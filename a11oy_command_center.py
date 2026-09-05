#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Serve the canonical A11oy Command Center on the product origin.

Product host: a-11-oy.com  (this surface)
Proof host:   a11oy.net    (do not serve this surface there)

Additive tabs:
  GET+HEAD /command
  GET+HEAD /command-v2
  GET+HEAD /command/constellation
  GET+HEAD /command/brain
  GET+HEAD /constellation   (host-root; declared so SPA fallback cannot 404 it)
  GET+HEAD /command/ops
  GET+HEAD /operator-pane
  GET+HEAD /command/{rest}

Host-root /brain is Hickok dual-stream. Do not steal it.
/command stays on elite_console.html until an explicit reviewed promotion.
"""
from pathlib import Path
from typing import List

MOUNTS = ("/command",)
V2_MOUNTS = ("/command-v2",)
SPECIFIC = (
    ("/command/constellation", "constellation.html"),
    ("/command/brain", "second-brain.html"),
    ("/command/ops", "operator-pane.html"),
    ("/operator-pane", "operator-pane.html"),
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


def _v2_path() -> Path:
    here = Path(__file__).resolve().parent
    candidates = (
        here / "pages" / "command-v2.html",
        Path("/app/pages/command-v2.html"),
    )
    for cand in candidates:
        if cand.is_file():
            return cand
    return here / "pages" / "command-v2.html"


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
    """Remove exact path registrations so reviewed pages replace SPA stubs."""
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    routes[:] = [r for r in list(routes) if getattr(r, "path", None) not in paths]


def _front_move(app, paths: list) -> None:
    """Park exact routes at the front, in given order. Never include catch-all."""
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    wanted = set(paths)
    chosen = [r for r in routes if getattr(r, "path", None) in wanted]
    if not chosen:
        return
    for route in chosen:
        try:
            routes.remove(route)
        except ValueError:
            pass
    order = {path: index for index, path in enumerate(paths)}
    chosen.sort(key=lambda route: order.get(getattr(route, "path", ""), 99))
    for route in reversed(chosen):
        routes.insert(0, route)


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

    async def _v2(_request=None):
        page = _v2_path()
        if page.is_file():
            return FileResponse(page, media_type="text/html; charset=utf-8")
        return JSONResponse(
            {
                "status": "UNAVAILABLE",
                "reason": "command-v2.html missing from the deployed pages closure",
                "page": "pages/command-v2.html",
            },
            status_code=503,
        )

    def _file(name: str):
        async def _handler(_request=None):
            page = _page(name)
            if page.is_file():
                return FileResponse(page, media_type="text/html; charset=utf-8")
            return JSONResponse(
                {
                    "status": "NOT_FOUND",
                    "reason": "command page missing from image",
                    "page": name,
                },
                status_code=404,
            )

        return _handler

    specific_paths = {path for path, _name in SPECIFIC}
    _drop_paths(app, specific_paths | set(V2_MOUNTS))
    existing = _existing_paths(app)
    router = getattr(app, "router", app)

    def _add(path: str, handler, methods: List[str]) -> None:
        if path in existing and path != CATCHALL:
            registered.append(f"{path} already registered (skipped)")
            return
        try:
            router.routes.insert(0, Route(path, handler, methods=methods))
        except Exception:
            app.add_api_route(path, handler, methods=methods, include_in_schema=False)
        existing.add(path)
        registered.append(f"GET+HEAD {path}")

    for path in MOUNTS:
        _add(path, _spa, ["GET", "HEAD"])
    for path in V2_MOUNTS:
        _add(path, _v2, ["GET", "HEAD"])
    for path, name in SPECIFIC:
        _add(path, _file(name), ["GET", "HEAD"])
    _add(CATCHALL, _spa, ["GET", "HEAD"])
    _front_move(
        app,
        list(V2_MOUNTS) + [path for path, _name in SPECIFIC] + list(MOUNTS),
    )
    registered.append(
        "command-center on /command; /command-v2 additive; "
        "constellation/brain/ops beat catch-all; /brain and /console untouched"
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

    v2_page = _v2_path()
    assert v2_page.is_file(), v2_page
    v2_html = v2_page.read_text(encoding="utf-8")
    assert "<main" in v2_html
    assert 'name="viewport"' in v2_html
    assert "prefers-reduced-motion" in v2_html
    assert "Conjecture 1" in v2_html
    assert "cdnjs" not in v2_html and "googleapis" not in v2_html
    assert "jsdelivr" not in v2_html

    async def _console(_req):
        return HTMLResponse("<html><body>operator console</body></html>")

    async def _hickok(_req):
        return HTMLResponse("<html><body>Hickok dual-stream</body></html>")

    app = Starlette(routes=[Route("/console", _console), Route("/brain", _hickok)])
    out = register(app, ns="a11oy")
    assert any("/command" in row for row in out), out
    assert any("/command-v2" in row for row in out), out
    client = TestClient(app)
    for path in ("/command", "/command/anatomy", "/command/honest"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
    v2 = client.get("/command-v2")
    assert v2.status_code == 200
    assert v2.headers["content-type"].startswith("text/html")
    assert "A11oy Command" in v2.text
    if _page("constellation.html").is_file():
        for path in ("/command/constellation", "/constellation"):
            body = client.get(path).text
            assert "Constellation" in body, path
            assert "Control before capability" not in body
    if _page("second-brain.html").is_file():
        brain = client.get("/command/brain")
        assert brain.status_code == 200
        assert "Second Brain" in brain.text
        assert "F1" in brain.text
    pane = _page("operator-pane.html")
    if pane.is_file():
        for path in ("/command/ops", "/operator-pane"):
            body = client.get(path).text
            assert "operator pane" in body.lower(), path
            assert "Conjecture 1" in body
            assert "cdnjs" not in body and "googleapis" not in body
    assert "Hickok" in client.get("/brain").text
    assert client.get("/console").status_code == 200
    print(
        "a11oy_command_center: ALL OK "
        "(v2 additive; exact pages beat catch-all; host roots untouched)"
    )


if __name__ == "__main__":
    _selftest()
