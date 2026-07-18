# SPDX-License-Identifier: Apache-2.0
"""Regression contract for the AYNI dark-surface dual mount."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from szl_dark_surfaces_register import register


def test_ayni_routes_exist_at_documented_and_legacy_prefixes() -> None:
    app = FastAPI()
    register(app, ns="a11oy")
    client = TestClient(app)

    # Current FastAPI represents include_router() with an internal wrapper, so
    # assert the public behavior instead of depending on router internals.
    for suffix in ("/v1/ayni", "/v1/ayni/healthz", "/v1/replay", "/v1/tinkuy"):
        params = {"at": "0"} if suffix == "/v1/replay" else None
        legacy = client.get(suffix, params=params)
        documented = client.get(f"/api/a11oy{suffix}", params=params)
        assert legacy.status_code == 200
        assert documented.status_code == 200
        assert legacy.headers["content-type"].startswith("application/json")
        assert documented.headers["content-type"].startswith("application/json")
