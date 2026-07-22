from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_serve_source_registers_holographic_transport_immediately_after_app() -> None:
    source = (ROOT / "serve.py").read_text(encoding="utf-8")
    app_marker = "app = FastAPI("
    import_marker = "import szl3d_holographic as _szl3d_holographic"
    register_marker = (
        "_SZL3D_HOLOGRAPHIC_STATUS = "
        '_szl3d_holographic.register(app, ns="a11oy")'
    )
    first_api_marker = '@app.get("/api/a11oy/v1/waqay/security-loop/manifest")'

    assert source.count(import_marker) == 1
    assert source.count(register_marker) == 1
    assert source.index(app_marker) < source.index(import_marker)
    assert source.index(import_marker) < source.index(first_api_marker)
    assert "_SZL3D_HOLOGRAPHIC_STATUS" in source
    assert "registered": False


def test_assembled_app_serves_holographic_get_and_bodyless_head() -> None:
    import serve

    static_path = "/static/3d/{path:path}"
    matching = [
        route
        for route in serve.app.routes
        if getattr(route, "path", None) == static_path
    ]
    methods = {
        method
        for route in matching
        for method in getattr(route, "methods", set())
    }
    assert {"GET", "HEAD"}.issubset(methods)

    catchall_indexes = [
        index
        for index, route in enumerate(serve.app.routes)
        if getattr(route, "path", None) == "/{full_path:path}"
    ]
    static_indexes = [
        index
        for index, route in enumerate(serve.app.routes)
        if getattr(route, "path", None) == static_path
    ]
    if catchall_indexes:
        assert max(static_indexes) < min(catchall_indexes)

    client = TestClient(serve.app)
    get_response = client.get("/static/3d/holographic.html")
    head_response = client.head("/static/3d/holographic.html")

    assert get_response.status_code == 200
    assert "Holographic Estate" in get_response.text
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert get_response.headers["cache-control"] == "public, max-age=300"
    assert head_response.headers["cache-control"] == "public, max-age=300"
