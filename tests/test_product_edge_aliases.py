"""Exact /spectral and /controller aliases beat the SPA soft-404 guard."""

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import a11oy_nav_wireup


def _app():
    async def holographic(_request):
        return HTMLResponse("<html><body>holo</body></html>")

    async def honest(_request):
        return JSONResponse({"organ": "a11oy", "ok": True})

    async def spa(_request):
        return HTMLResponse(
            "<html><body>spa</body></html>",
            headers={"X-SZL-Route-State": "SPA_FALLBACK"},
        )

    app = Starlette(
        routes=[
            Route("/static/3d/holographic.html", holographic, methods=["GET", "HEAD"]),
            Route("/api/a11oy/v1/honest", honest, methods=["GET", "HEAD"]),
            Route("/{full_path:path}", spa, methods=["GET", "HEAD"]),
        ]
    )
    registered = a11oy_nav_wireup._register_public_page_aliases(app)
    assert any("/spectral" in row for row in registered), registered
    assert any("/controller" in row for row in registered), registered
    return app


def test_spectral_redirects_to_holographic():
    client = TestClient(_app())
    response = client.get("/spectral", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/static/3d/holographic.html"


def test_controller_redirects_to_honest():
    client = TestClient(_app())
    response = client.get("/controller", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/api/a11oy/v1/honest"


def test_aliases_reach_live_targets():
    client = TestClient(_app())
    spectral = client.get("/spectral", follow_redirects=True)
    assert spectral.status_code == 200
    assert "holo" in spectral.text
    controller = client.get("/controller", follow_redirects=True)
    assert controller.status_code == 200
    assert controller.json()["organ"] == "a11oy"


def test_assembled_app_aliases_beat_soft_404_guard():
    # The synthetic app above has no soft-404 guard; the Space serves serve.app, which does.
    import serve

    client = TestClient(serve.app, follow_redirects=False)
    for alias, target in (
        ("/spectral", "/static/3d/holographic.html"),
        ("/spectral/", "/static/3d/holographic.html"),
        ("/controller", "/api/a11oy/v1/honest"),
        ("/controller/", "/api/a11oy/v1/honest"),
    ):
        for method in ("GET", "HEAD"):
            response = client.request(method, alias)
            assert response.status_code == 302, (method, alias, response.status_code, response.text[:200])
            assert response.headers["location"] == target, (method, alias)
    assert client.get("/static/3d/holographic.html").status_code == 200
    assert client.get("/api/a11oy/v1/honest").status_code == 200
