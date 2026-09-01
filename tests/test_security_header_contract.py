# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the response-header contract enforced in production."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import szl_be_hardening as hardening


def test_hardened_landing_page_emits_complete_security_baseline(tmp_path):
    app = FastAPI()

    @app.get("/")
    async def landing() -> HTMLResponse:
        return HTMLResponse("<html><body>a11oy</body></html>")

    report = hardening.harden(
        app,
        organ="a11oy",
        khipu_path=str(tmp_path / "security-header-contract.sqlite3"),
    )
    assert report.get("ok") is True

    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"

    csp = response.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in csp
    assert "https://huggingface.co" in csp
    assert "https://*.hf.space" in csp
    assert "https://*.huggingface.co" in csp


def test_existing_route_csp_is_preserved(tmp_path):
    app = FastAPI()
    route_csp = "default-src 'none'; frame-ancestors 'none';"

    @app.get("/strict")
    async def strict() -> HTMLResponse:
        return HTMLResponse(
            "<html><body>strict</body></html>",
            headers={"Content-Security-Policy": route_csp},
        )

    hardening.harden(
        app,
        organ="a11oy",
        khipu_path=str(tmp_path / "security-header-preserve.sqlite3"),
    )
    response = TestClient(app).get("/strict")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == route_csp
