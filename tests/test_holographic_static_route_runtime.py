from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import szl3d_holographic as holographic


def _app_with_preexisting_catchall(monkeypatch, tmp_path: Path) -> FastAPI:
    page = tmp_path / "holographic.html"
    page.write_text(
        "<!doctype html><title>A11oy Holographic Operations</title>"
        "<main>The estate, observed—not assumed.</main>",
        encoding="utf-8",
    )
    monkeypatch.setattr(holographic, "_base_dir", lambda: tmp_path)

    app = FastAPI()

    @app.get("/{full_path:path}")
    async def spa_catchall(full_path: str):
        return JSONResponse({"status": "NOT_FOUND", "path": full_path}, status_code=404)

    holographic.register(app, ns="a11oy")
    return app


def _route_indexes(app: FastAPI, path: str) -> list[int]:
    return [
        index
        for index, route in enumerate(app.routes)
        if getattr(route, "path", None) == path
    ]


def _methods(app: FastAPI, path: str) -> set[str]:
    return {
        method
        for route in app.routes
        if getattr(route, "path", None) == path
        for method in getattr(route, "methods", set())
    }


def test_static_get_and_head_beat_a_preexisting_spa_catchall(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_with_preexisting_catchall(monkeypatch, tmp_path)
    client = TestClient(app)

    static_path = "/static/3d/{path:path}"
    catchall_path = "/{full_path:path}"
    assert {"GET", "HEAD"}.issubset(_methods(app, static_path))
    assert max(_route_indexes(app, static_path)) < min(_route_indexes(app, catchall_path))

    get_response = client.get("/static/3d/holographic.html")
    head_response = client.head("/static/3d/holographic.html")
    assert get_response.status_code == 200
    assert "A11oy Holographic Operations" in get_response.text
    assert "The estate, observed—not assumed." in get_response.text
    assert get_response.headers["cache-control"] == "public, max-age=300"
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert head_response.headers["cache-control"] == "public, max-age=300"


def test_shell_and_info_routes_also_beat_the_spa_catchall(
    monkeypatch, tmp_path: Path
) -> None:
    app = _app_with_preexisting_catchall(monkeypatch, tmp_path)
    client = TestClient(app)

    shell = client.get("/holographic")
    alias = client.get("/a11oy/holographic")
    info = client.get("/api/a11oy/v1/holographic/info")
    assert shell.status_code == 200
    assert alias.status_code == 200
    assert "A11oy Holographic Operations" in shell.text
    assert "A11oy Holographic Operations" in alias.text
    assert info.status_code == 200
    assert info.json()["capability"] == "Shared szl3d 3D toolkit + holographic shell"


def test_missing_and_traversal_assets_remain_fail_closed(
    monkeypatch, tmp_path: Path
) -> None:
    client = TestClient(_app_with_preexisting_catchall(monkeypatch, tmp_path))
    for route in (
        "/static/3d/missing.js",
        "/static/3d/../serve.py",
        "/static/3d/not-allowlisted.bin",
    ):
        response = client.get(route)
        assert response.status_code == 404
