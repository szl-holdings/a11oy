# SPDX-License-Identifier: Apache-2.0
"""Runtime contract for visualization assets served by the real FastAPI app."""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import serve  # noqa: E402


client = TestClient(serve.app)


@pytest.mark.parametrize("prefix", ["/viz", "/static/viz"])
@pytest.mark.parametrize(
    ("asset", "content_type", "marker"),
    [
        ("style.css", "text/css", "--bg:#06101d"),
        ("app.js", "javascript", "const STATS_EP"),
    ],
)
def test_router_assets_are_files_not_spa_html(prefix, asset, content_type, marker):
    response = client.get(f"{prefix}/router/{asset}")

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert "text/html" not in response.headers["content-type"]
    assert marker in response.text
    assert "<!doctype html>" not in response.text.lower()


@pytest.mark.parametrize(
    "path",
    [
        "/viz/router/missing.css",
        "/static/viz/router/missing.js",
        "/viz/not-a-scene/style.css",
    ],
)
def test_missing_or_unknown_viz_assets_return_real_404(path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"error": "visualization asset not found"}
