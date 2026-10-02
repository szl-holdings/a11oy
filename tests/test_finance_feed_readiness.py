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
import copy
import json
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
import pytest

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


def _ecb_fx_fixture() -> dict:
    today = datetime.now(timezone.utc).date()
    currencies = ["CHF", "USD", "CAD", "GBP", "JPY"]
    eur_rates = [1.0, 1.25, 1.5, 0.875, 150.0]
    return {
        "header": {"sender": {"id": "ECB"}},
        "structure": {"dimensions": {
            "series": [
                {"id": "FREQ", "values": [{"id": "D"}]},
                {"id": "CURRENCY", "values": [{"id": code} for code in currencies]},
                {"id": "CURRENCY_DENOM", "values": [{"id": "EUR"}]},
                {"id": "EXR_TYPE", "values": [{"id": "SP00"}]},
                {"id": "EXR_SUFFIX", "values": [{"id": "A"}]},
            ],
            "observation": [{"id": "TIME_PERIOD", "values": [
                {"id": today.isoformat()},
            ]}],
        }},
        "dataSets": [{"series": {
            f"0:{index}:0:0:0": {"observations": {"0": [eur_rates[index]]}}
            for index in range(len(currencies))
        }}],
    }


def test_finance_fx_uses_attributed_same_date_ecb_rates_when_primary_fails(monkeypatch) -> None:
    data = _ecb_fx_fixture()
    calls = []

    def fake_fetch(key, url, ttl, parser=None, timeout_s=None):
        calls.append((url, timeout_s))
        if "frankfurter.dev" in url:
            return _unavailable("Frankfurter timeout")
        return {"value": parser(data),
                "freshness": {"status": "live", "fetched_at": 1786449600}}

    monkeypatch.setattr(vertical, "_cached_fetch", fake_fetch)
    result = vertical.feed_fx()
    assert len(calls) == 2
    assert calls[1][0] == vertical._ECB_USD_FX_URL
    assert [budget for _, budget in calls] == [vertical._FX_SOURCE_TIMEOUT_S] * 2
    assert result["freshness"]["status"] == "reference"
    assert result["freshness"]["observation_date"] == result["value"]["date"]
    assert result["value"]["date"] == datetime.now(timezone.utc).date().isoformat()
    assert result["value"]["observation_age_days"] == 0
    assert result["value"]["rates"] == pytest.approx({
        "EUR": 0.8, "GBP": 0.7, "JPY": 120.0, "CAD": 1.2, "CHF": 0.8,
    })
    assert result["value"]["leader"] == "European Central Bank (ECB)"
    assert result["value"]["data_kind"] == "reference"
    assert "calculated from EUR reference rates" in result["value"]["source"]


def test_finance_fx_validates_primary_reference_before_accepting_it(monkeypatch) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    response = {"base": "USD", "date": today,
                "rates": {"EUR": 0.8, "GBP": 0.7, "JPY": 120.0,
                          "CAD": 1.2, "CHF": 0.8}}
    calls = []

    def fake_fetch(key, url, ttl, parser=None, timeout_s=None):
        calls.append(url)
        return {"value": parser(response),
                "freshness": {"status": "live", "fetched_at": 1786449600}}

    monkeypatch.setattr(vertical, "_cached_fetch", fake_fetch)
    result = vertical.feed_fx()
    assert len(calls) == 1
    assert result["freshness"]["status"] == "reference"
    assert result["value"]["rates"] == response["rates"]
    assert result["value"]["data_kind"] == "reference"


def test_finance_aggregate_selects_ecb_cache_when_frankfurter_is_stale(monkeypatch) -> None:
    cache = vertical._Cache()
    monkeypatch.setattr(vertical, "_CACHE", cache)
    primary_key = vertical._variant_cache_key(
        "fx_USD", base="USD", symbols="EUR,GBP,JPY,CAD,CHF")
    cache.put(primary_key, {"date": "old"}, ttl=600, status="stale")
    cache.put("fx_ecb_usd_reference", {"date": "today"}, ttl=600)
    finance = vertical._vertical_feed_state("finance")
    fx = [child for child in finance["children"]
          if child["source_id"] in {"fx_USD", "fx_ecb_usd_reference"}]
    assert len(fx) == 1
    assert fx[0]["source_id"] == "fx_ecb_usd_reference"
    assert fx[0]["status"] == "live"


def test_finance_aggregate_ignores_successful_adhoc_fx_variant(monkeypatch) -> None:
    cache = vertical._Cache()
    monkeypatch.setattr(vertical, "_CACHE", cache)
    adhoc_key = vertical._variant_cache_key(
        "fx_USD", base="USD", symbols="EUR,JPY")
    cache.put(adhoc_key, {"date": "today"}, ttl=600)
    finance = vertical._vertical_feed_state("finance")
    fx = next(child for child in finance["children"]
              if child["source_id"] == "fx_USD")
    assert fx["status"] == "unavailable"


def test_finance_cached_reference_expires_at_day_boundary() -> None:
    old = (datetime.now(timezone.utc).date() - timedelta(days=8)).isoformat()
    result = vertical._fx_reference_result({
        "value": {"date": old, "observation_age_days": 7, "rates": {"EUR": 0.8}},
        "freshness": {"status": "cached", "fetched_at": 1786449600},
    })
    assert result["freshness"]["status"] == "stale"
    assert result["value"]["observation_age_days"] == 8
    assert "too old" in result["freshness"]["error"]


def test_finance_fx_preserves_both_errors_when_sources_fail(monkeypatch) -> None:
    def fake_fetch(key, url, ttl, parser=None, timeout_s=None):
        if "frankfurter.dev" in url:
            return _unavailable("Frankfurter timeout")
        return _unavailable("ECB egress blocked")

    monkeypatch.setattr(vertical, "_cached_fetch", fake_fetch)
    result = vertical.feed_fx()
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert result["freshness"]["error"] == "Frankfurter timeout"
    assert result["freshness"]["fallback_source"] == "ECB direct"
    assert result["freshness"]["fallback_status"] == "unavailable"
    assert result["freshness"]["fallback_error"] == "ECB egress blocked"


def test_finance_fx_falls_back_when_cached_primary_observation_ages_out(monkeypatch) -> None:
    old = (datetime.now(timezone.utc).date() - timedelta(days=8)).isoformat()
    calls = []

    def fake_fetch(key, url, ttl, parser=None, timeout_s=None):
        calls.append(url)
        if "frankfurter.dev" in url:
            return {"value": {"date": old, "rates": {"EUR": 0.8}},
                    "freshness": {"status": "cached", "fetched_at": 1786449600}}
        return {"value": parser(_ecb_fx_fixture()),
                "freshness": {"status": "live", "fetched_at": 1786449600}}

    monkeypatch.setattr(vertical, "_cached_fetch", fake_fetch)
    result = vertical.feed_fx()
    assert len(calls) == 2
    assert result["freshness"]["status"] == "reference"
    assert result["value"]["source_url"] == vertical._ECB_USD_FX_URL


@pytest.mark.parametrize("primary", [
    {},
    {"base": "USD", "date": "2020-01-01", "rates": {
        "EUR": 0.8, "GBP": 0.7, "JPY": 120.0, "CAD": 1.2, "CHF": 0.8}},
    {"base": "USD", "date": datetime.now(timezone.utc).date().isoformat(),
     "rates": {"EUR": 0.8}},
    {"base": "USD", "date": datetime.now(timezone.utc).date().isoformat(),
     "rates": {"EUR": float("inf"), "GBP": 0.7, "JPY": 120.0,
               "CAD": 1.2, "CHF": 0.8}},
])
def test_finance_fx_rejects_bad_primary_and_uses_ecb(monkeypatch, primary: dict) -> None:
    calls = []

    def fake_fetch(key, url, ttl, parser=None, timeout_s=None):
        calls.append(url)
        if "frankfurter.dev" in url:
            try:
                parser(primary)
            except (KeyError, TypeError, ValueError):
                return _unavailable("Frankfurter payload rejected")
            raise AssertionError("invalid primary passed validation")
        return {"value": parser(_ecb_fx_fixture()),
                "freshness": {"status": "live", "fetched_at": 1786449600}}

    monkeypatch.setattr(vertical, "_cached_fetch", fake_fetch)
    result = vertical.feed_fx()
    assert len(calls) == 2
    assert result["freshness"]["status"] == "reference"
    assert result["value"]["source_url"] == vertical._ECB_USD_FX_URL


@pytest.mark.parametrize("invalid", [
    "missing_chf", "mixed_dates", "zero_usd", "nonfinite_usd",
    "wrong_dimensions", "too_old", "negative_index", "cross_overflow",
])
def test_finance_fx_rejects_invalid_ecb_fallback_without_inventing_rates(
    monkeypatch, invalid: str,
) -> None:
    data = copy.deepcopy(_ecb_fx_fixture())
    series = data["dataSets"][0]["series"]
    if invalid == "missing_chf":
        del series["0:0:0:0:0"]
    elif invalid == "mixed_dates":
        values = data["structure"]["dimensions"]["observation"][0]["values"]
        values.append({"id": (datetime.now(timezone.utc).date()
                              - timedelta(days=1)).isoformat()})
        series["0:0:0:0:0"]["observations"] = {"1": [1.0]}
    elif invalid == "zero_usd":
        series["0:1:0:0:0"]["observations"]["0"][0] = 0.0
    elif invalid == "nonfinite_usd":
        series["0:1:0:0:0"]["observations"]["0"][0] = float("nan")
    elif invalid == "wrong_dimensions":
        data["structure"]["dimensions"]["series"][2]["id"] = "CURRENCY_SOURCE"
    elif invalid == "too_old":
        old = datetime.now(timezone.utc).date() - timedelta(days=8)
        data["structure"]["dimensions"]["observation"][0]["values"][0]["id"] = old.isoformat()
    elif invalid == "negative_index":
        series["0:-1:0:0:0"] = series.pop("0:0:0:0:0")
    elif invalid == "cross_overflow":
        series["0:1:0:0:0"]["observations"]["0"][0] = 5e-324

    primary = _unavailable("Frankfurter timeout")

    def fake_fetch(key, url, ttl, parser=None, timeout_s=None):
        if "frankfurter.dev" in url:
            return primary
        try:
            return {"value": parser(data),
                    "freshness": {"status": "live", "fetched_at": 1786449600}}
        except Exception:
            return _unavailable("ECB payload rejected")

    monkeypatch.setattr(vertical, "_cached_fetch", fake_fetch)
    result = vertical.feed_fx()
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert result["freshness"]["error"] == primary["freshness"]["error"]
    assert result["freshness"]["fallback_error"] == "ECB payload rejected"
