# SPDX-License-Identifier: Apache-2.0
"""Older market aliases cannot bypass canonical FRED access or SPA ordering."""
import importlib
import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
import pytest

import a11oy_markets as legacy
routes = importlib.import_module("verticals.puriq-markets.runtime.routes")
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
TOKEN = "synthetic-owner-fixture-" * 3


@pytest.fixture
def setup(monkeypatch):
    calls = []
    def fetch(plan):
        calls.append(plan.source)
        assert plan.source == "fred-series"
        return json.dumps({"realtime_start": plan.parameters["as_of"],
            "realtime_end": plan.parameters["as_of"], "observations": [
            {"date": "2026-01-01", "value": "0", "realtime_start": plan.parameters["as_of"],
             "realtime_end": plan.parameters["as_of"]}]}).encode()
    client = transport.FinanceClient(fetch=fetch, clock=lambda: 1789430400,
        environ={"SZL_FINANCE_PRIVATE_READ_TOKEN": TOKEN, "SZL_FRED_API_KEY": "a" * 32,
                 "SZL_SOURCE_REVISION": "1" * 40})
    monkeypatch.setattr(routes, "CLIENT", client)
    monkeypatch.setattr(legacy, "_company", lambda cik: {"ok": True, "metrics": {}})
    monkeypatch.setattr(legacy, "_debt", lambda: {"ok": True})
    monkeypatch.setattr(legacy, "http_json", lambda *a, **k: pytest.fail("legacy FRED HTTP path used"))
    app = FastAPI()
    @app.get("/{path:path}")
    def spa(path): return HTMLResponse("SPA fallback")
    legacy.register(app)
    return TestClient(app), app, calls


@pytest.mark.parametrize("prefix", ["/v1/markets", "/api/a11oy/v1/markets"])
def test_public_legacy_macro_is_denied_even_with_provider_key_present(setup, prefix):
    http, app, calls = setup
    result = http.get(prefix + "/macro")
    assert result.status_code == 403 and result.json()["error"] == "PRIVATE_SOURCE_ACCESS_REQUIRED"
    assert calls == []


@pytest.mark.parametrize("prefix", ["/v1/markets", "/api/a11oy/v1/markets"])
def test_legacy_summary_preserves_partial_failure_and_never_reads_private_fred(setup, prefix):
    http, app, calls = setup
    result = http.get(prefix + "/summary")
    assert result.status_code == 200
    assert result.json()["ok"] is False and result.json()["state"] == "DEGRADED"
    assert result.json()["macro"]["observations"] == [] and calls == []
    assert result.headers["cache-control"] == "private, no-store"


def test_authorized_alias_reuses_canonical_cache_without_later_public_leak(setup):
    http, app, calls = setup
    canonical = http.get(routes.PREFIX + "/observations/fred-series", headers={"X-SZL-Finance-Read-Token": TOKEN})
    assert canonical.status_code == 200
    result = http.get("/v1/markets/macro", headers={"X-SZL-Finance-Read-Token": TOKEN})
    assert result.status_code == 200 and result.json()["state"] == "CACHED"
    assert result.json()["observations"][0]["value"] == "0"
    assert result.json()["provenance"] == canonical.json()["provenance"]
    assert calls == ["fred-series"]
    assert http.get("/v1/markets/macro").status_code == 403
    assert len(calls) == 1


def test_token_in_query_does_not_grant_access(setup):
    http, app, calls = setup
    assert http.get("/v1/markets/macro", params={"token": TOKEN}).status_code == 403
    assert calls == []


def test_repeated_registration_keeps_both_route_families_before_spa(setup):
    http, app, calls = setup
    original_count = len(app.router.routes)
    legacy.register(app)
    assert len(app.router.routes) == original_count
    for prefix in ("/v1/markets", "/api/a11oy/v1/markets"):
        assert http.get(prefix + "/company").json()["ok"] is True
        assert http.get(prefix + "/debt").json()["ok"] is True
    assert http.get(routes.PREFIX + "/providers").status_code == 200
    assert http.post("/v1/markets/macro").status_code == 405


def test_authorized_summary_remains_nostore_and_reports_same_asof(setup):
    http, app, calls = setup
    result = http.get("/v1/markets/summary", headers={"X-SZL-Finance-Read-Token": TOKEN})
    assert result.json()["ok"] is True
    assert result.json()["macro"]["as_of"] == "2026-09-15"
    assert result.headers["cache-control"] == "private, no-store"
    assert result.json()["execution_enabled"] is False
