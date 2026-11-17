# SPDX-License-Identifier: Apache-2.0
"""Read-only telemetry summary and holographic evidence-rail bindings."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import szl_runtime_contracts as runtime

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "static/3d/holographic.html"
ROUTE = "/api/a11oy/v1/telemetry/summary"


def _app():
    app = FastAPI()

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        return HTMLResponse("<html>SPA fallback</html>")

    runtime.register(app)
    return app


@pytest.mark.parametrize(
    "otel,expected",
    [
        ({"status": "LIVE", "in_process": {"state": "LIVE"},
          "collector": {"state": "REACHABLE"}}, "LIVE"),
        ({"status": "LIVE", "in_process": {"state": "LIVE"},
          "collector": {"state": "UNKNOWN"}}, "DEGRADED"),
        ({"status": "DEGRADED", "in_process": {"state": "LIVE"},
          "collector": {"state": "UNKNOWN"}}, "DEGRADED"),
        ({"status": "UNAVAILABLE", "in_process": {"state": "UNAVAILABLE"},
          "collector": {"state": "UNAVAILABLE"}}, "UNAVAILABLE"),
    ],
)
def test_summary_never_upgrades_unverified_exporter(monkeypatch, otel, expected):
    monkeypatch.setattr(runtime, "_otel_posture", lambda _: otel)
    monkeypatch.setattr(runtime, "_safe_env_sha", lambda: ("a" * 40, "env:SZL_GIT_SHA"))
    client = TestClient(_app())
    response = client.get(ROUTE)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    body = response.json()
    assert body["schema"] == "szl.telemetry-summary/v1"
    assert body["status"] == expected
    assert body["source_revision"] == "a" * 40
    assert body["otel"] == otel
    assert body["read_only"] is True
    assert body["receipt_minted"] is False
    assert body["production_authorization"] is False
    assert body["traces"]["state"] == "UNAVAILABLE"
    assert body["scope"] == "OTEL_POSTURE_ONLY"


def test_missing_revision_and_collector_are_not_made_live(monkeypatch):
    monkeypatch.setattr(runtime, "_safe_env_sha", lambda: (None, None))
    monkeypatch.setattr(runtime, "_otel_posture", lambda _: {
        "status": "LIVE", "in_process": {"state": "LIVE"}, "collector": {},
    })
    body = TestClient(_app()).get(ROUTE).json()
    assert body["status"] == "DEGRADED"
    assert body["source_revision"] is None
    assert body["source_revision_provenance"] == "UNAVAILABLE"


def test_holographic_client_binds_summary_without_overclaiming():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="evidence-rail-telemetry"' in html
    assert 'getJson("/api/a11oy/v1/telemetry/summary")' in html
    assert 'telemetry?.schema === "szl.telemetry-summary/v1"' in html
    assert 'telemetry?.source_revision === revision' in html
    assert 'telemetry?.otel?.collector?.state === "REACHABLE"' in html
    assert 'evidenceTelemetry.textContent = telemetryState' in html
    assert 'telemetry?.status === "LIVE"' in html


def test_registered_api_precedes_spa_fallback():
    app = _app()
    paths = [getattr(route, "path", "") for route in app.router.routes]
    assert ROUTE in paths
    assert paths.index(ROUTE) < paths.index("/{full_path:path}")
