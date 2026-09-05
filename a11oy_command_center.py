#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Serve the canonical A11oy Command Center on the product origin.

Product host: a-11-oy.com  (this surface)
Proof host:   a11oy.net    (do not serve this surface there)

Additive routes:
  GET+HEAD /command
  GET+HEAD /command-v2
  GET+HEAD /command/constellation
  GET+HEAD /command/brain
  GET+HEAD /command/ops
  GET+HEAD /operator-pane
  GET+HEAD /constellation
  GET+HEAD /command/{rest}

The additive router does not steal /console or the host-root /brain route.
/command remains on elite_console.html; /command-v2 is an independently
reviewable skin until an explicit, evidence-backed promotion changes that.
"""
from pathlib import Path
from typing import List

MOUNTS = ("/command",)
SPECIFIC = (
    ("/command-v2", "command-v2.html"),
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
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return here / "web" / "elite_console.html"


def _page(name: str) -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here / "pages" / name, Path("/app/pages") / name):
        if candidate.is_file():
            return candidate
    return here / "pages" / name


def _existing_paths(app) -> set:
    try:
        router = getattr(app, "router", app)
        return {getattr(route, "path", None) for route in getattr(router, "routes", [])}
    except Exception:
        return set()


def _drop_paths(app, paths: set) -> None:
    """Remove exact path registrations so reviewed pages replace SPA stubs."""
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    routes[:] = [route for route in list(routes) if getattr(route, "path", None) not in paths]


def _front_move(app, paths: list) -> None:
    """Park exact routes at the front, in the requested order."""
    router = getattr(app, "router", app)
    routes = getattr(router, "routes", None)
    if not routes:
        return
    wanted = set(paths)
    chosen = [route for route in routes if getattr(route, "path", None) in wanted]
    order = {path: index for index, path in enumerate(paths)}
    for route in chosen:
        try:
            routes.remove(route)
        except ValueError:
            pass
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

    def _file(name: str):
        async def _handler(_request=None):
            page = _page(name)
            if page.is_file():
                return FileResponse(page, media_type="text/html; charset=utf-8")
            return JSONResponse(
                {
                    "status": "NOT_FOUND",
                    "reason": f"{name} missing from image",
                    "page": name,
                },
                status_code=404,
            )

        return _handler

    specific_paths = {path for path, _name in SPECIFIC}
    _drop_paths(app, specific_paths)
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
    for path, name in SPECIFIC:
        _add(path, _file(name), ["GET", "HEAD"])
    _add(CATCHALL, _spa, ["GET", "HEAD"])
    _front_move(app, [path for path, _name in SPECIFIC] + list(MOUNTS))
    registered.append(
        "command-center on /command; /command-v2 additive; "
        "constellation/brain/ops beat catch-all; /console and host-root /brain untouched"
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

    async def _console(_request):
        return HTMLResponse("<html><body>operator console</body></html>")

    async def _hickok(_request):
        return HTMLResponse("<html><body>Hickok dual-stream</body></html>")

    app = Starlette(routes=[Route("/console", _console), Route("/brain", _hickok)])
    output = register(app, ns="a11oy")
    assert any("/command" in row for row in output), output
    assert any("/command-v2" in row for row in output), output
    client = TestClient(app)

    for path in ("/command", "/command/anatomy", "/command/honest"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)

    command_v2 = _page("command-v2.html")
    if command_v2.is_file():
        response = client.get("/command-v2")
        assert response.status_code == 200
        assert "A11oy Command" in response.text
        assert "Conjecture 1" in response.text
        assert "cdnjs" not in response.text
        assert "googleapis" not in response.text
        assert "jsdelivr" not in response.text

    if _page("constellation.html").is_file():
        for path in ("/command/constellation", "/constellation"):
            body = client.get(path).text
            assert "Constellation" in body, path
            assert "Control before capability" not in body

    if _page("second-brain.html").is_file():
        response = client.get("/command/brain")
        assert response.status_code == 200
        assert "Second Brain" in response.text
        assert "F1" in response.text

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
        "(v2 additive; exact pages beat catch-all; /console and /brain untouched)"
    )


if __name__ == "__main__":
    _selftest()
