"""Existing Brain/Mesh links must resolve to their intended product routes."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_governed_loops_and_upgrades_are_not_spa_fallbacks():
    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    alias = client.get("/governed-loops", follow_redirects=False)
    assert alias.status_code == 307
    assert alias.headers["location"] == "/agent-loop"
    assert alias.headers.get("x-szl-route-state") != "SPA_FALLBACK"
    assert client.head("/governed-loops", follow_redirects=False).status_code == 307

    upgrades = client.get("/upgrades")
    assert upgrades.status_code == 200
    assert upgrades.headers["content-type"].startswith("text/html")
    assert upgrades.headers.get("x-szl-route-state") != "SPA_FALLBACK"
    assert "<title" in upgrades.text.lower()
    assert client.head("/upgrades").status_code == 200
