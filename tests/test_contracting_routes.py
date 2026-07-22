"""Regression coverage for literal contracting routes shadowed by area routes."""

from __future__ import annotations

import os

os.environ["SZL_CONTRACTING_WARM"] = "0"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import szl_contracting  # noqa: E402


def test_sources_live_is_a_real_literal_route() -> None:
    app = FastAPI()
    original_timeout = szl_contracting._LIVENESS_TIMEOUT
    szl_contracting._LIVENESS_TIMEOUT = 0.25
    try:
        szl_contracting.register(app, ns="a11oy")

        routes = [getattr(route, "path", None) for route in app.router.routes]
        literal = "/api/a11oy/v1/contracting/sources/live"
        parameterized = "/api/a11oy/v1/contracting/{area_id}/live"
        assert routes.index(literal) < routes.index(parameterized)

        response = TestClient(app).get(literal)
    finally:
        szl_contracting._LIVENESS_TIMEOUT = original_timeout

    assert response.status_code == 200
    payload = response.json()
    assert payload["layer"] == "a11oy contracting source reachability"
    assert payload["sources_total"] == len(szl_contracting.SOURCES)
    assert payload["sources_reachable"] <= payload["sources_total"]
    assert set(payload["sources"]) == set(szl_contracting.SOURCES)
    assert "error" not in payload

    openapi = app.openapi()
    assert "get" in openapi["paths"][literal]
