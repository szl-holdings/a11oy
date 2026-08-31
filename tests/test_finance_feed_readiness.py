# SPDX-License-Identifier: Apache-2.0
"""Post-deploy finance-feed honesty: omit unofficial Yahoo misses.

hf-sync run 33227751977 left exactly one doctrine lie:

  /api/a11oy/v1/vert/finance/feed
  schema invalid (vert_finance_feed)
  freshness timestamp missing: equities.SPY.freshness.fetched_at
  evidence label not allowed: freshness.status="unavailable"

Do not expand probe allowLabels. Official Polygon SPY stays required.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI

import a11oy_vertical_feeds as vertical


def _live(symbol: str, official: bool = False) -> dict:
    kind = "live" if official else "unofficial-fallback"
    return {
        "value": {
            "symbol": symbol,
            "price": 1.0,
            "data_kind": kind,
            "official": official,
        },
        "freshness": {"status": "live", "fetched_at": 1786449600},
    }


def _unavailable(error: str = "TimeoutError: yahoo") -> dict:
    return {"value": None, "freshness": {"status": "unavailable", "error": error}}


def _stale_last_good(symbol: str) -> dict:
    return {
        "value": {"symbol": symbol, "price": 2.0, "data_kind": "unofficial-fallback"},
        "freshness": {
            "status": "stale",
            "age_s": 90.0,
            "fetched_at": 1786449500,
            "error": "HTTPStatusError: 429",
        },
    }


def _payload(response) -> dict:
    return json.loads(response.body)


def _endpoint(app: FastAPI, path: str):
    for route in app.router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"route not registered: {path}")


def test_refresh_failure_without_cache_stamps_fetched_at() -> None:
    payload = vertical._refresh_failure(None, TimeoutError("yahoo"))
    assert payload["value"] is None
    assert payload["freshness"]["status"] == "unavailable"
    assert isinstance(payload["freshness"]["fetched_at"], float)
    assert payload["freshness"]["fetched_at"] > 0


def test_finance_public_series_omits_unavailable_and_promotes_stale_cache() -> None:
    public = vertical._finance_public_series({
        "SPY": _unavailable(),
        "AAPL": _live("AAPL"),
        "MSFT": _stale_last_good("MSFT"),
        "^VIX": {"value": None, "freshness": {"status": "unavailable"}},
    })
    assert "SPY" not in public
    assert "^VIX" not in public
    assert public["AAPL"]["freshness"]["status"] == "live"
    assert public["MSFT"]["freshness"]["status"] == "cached"
    assert public["MSFT"]["freshness"]["fetched_at"] == 1786449500
    assert public["MSFT"]["value"]["price"] == 2.0


def test_finance_feed_omits_yahoo_misses_and_keeps_official_spy(monkeypatch) -> None:
    def fake_yahoo(symbol: str):
        if symbol in {"SPY", "AAPL", "^VIX"}:
            return _unavailable(symbol)
        return _live(symbol)

    def fake_polygon(symbol: str):
        return _live(symbol, official=True)

    monkeypatch.setattr(vertical, "feed_yahoo", fake_yahoo)
    monkeypatch.setattr(vertical, "feed_polygon", fake_polygon)
    monkeypatch.setattr(vertical, "feed_coinbase", lambda pair: _live(pair, official=True))
    monkeypatch.setattr(vertical, "feed_nvd", lambda *a, **k: _live("CVE"))
    monkeypatch.setattr(vertical, "feed_fx", lambda *a, **k: _live("USD", official=True))

    app = FastAPI()
    vertical.register(app)
    finance_feed = _endpoint(app, "/api/a11oy/v1/vert/finance/feed")
    body = _payload(asyncio.run(finance_feed()))
    assert set(body["equities_official"]) == {"SPY", "AAPL", "MSFT", "NVDA"}
    assert "SPY" not in body["equities"]
    assert "AAPL" not in body["equities"]
    assert "^VIX" not in body["equities"]
    assert body["equities"]["MSFT"]["freshness"]["status"] == "live"
    assert "unavailable" not in json.dumps(body["equities"])
    for row in body["equities"].values():
        assert row["freshness"]["fetched_at"]
    assert body["equities_official"]["SPY"]["freshness"]["status"] == "live"
    assert body["equities_official"]["SPY"]["freshness"]["fetched_at"]
    assert "omitted" in body["equities_note"]
