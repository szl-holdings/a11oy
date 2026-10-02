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
from pathlib import Path
import shutil
import subprocess

from fastapi import FastAPI
import pytest

import a11oy_vertical_feeds as vertical


_ROOT = Path(__file__).resolve().parents[1]
_PROBE = """
import fs from 'node:fs';
import {validateSchema, evaluateEndpointLabels, evaluateFreshness}
  from './tools/readiness-harness/probe_runner.mjs';
const {path, body, nowMs} = JSON.parse(fs.readFileSync(0, 'utf8'));
const tabs = JSON.parse(fs.readFileSync('tools/readiness-harness/tabs.json', 'utf8'));
const spec = tabs.endpoints[path];
const schema = validateSchema(spec.schema, body);
const labels = evaluateEndpointLabels(200, spec, body);
const freshness = evaluateFreshness(path, spec, body, nowMs);
process.stdout.write(JSON.stringify({
  schemaOk: schema.ok, labelsOk: labels.ok, freshOk: freshness.freshOk,
}));
"""


def _probe(path: str, body: dict, now_s: int = 1786449600) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the shipped readiness evaluator")
    result = subprocess.run(
        [node, "--input-type=module", "-e", _PROBE],
        input=json.dumps({"path": path, "body": body, "nowMs": now_s * 1000}),
        text=True, capture_output=True, check=True, cwd=_ROOT, timeout=10,
    )
    return json.loads(result.stdout)


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


def _stale_source(value: dict) -> dict:
    return {
        "value": value,
        "freshness": {
            "status": "stale",
            "age_s": 90.0,
            "fetched_at": 1786449500,
            "error": "HTTPStatusError: 503",
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


def test_defense_and_finance_routes_preserve_last_good_source_evidence(monkeypatch) -> None:
    monkeypatch.setattr(vertical, "feed_cisa_kev", lambda *a: {
        "value": {"items": []},
        "freshness": {"status": "live", "fetched_at": 1786449600},
    })
    monkeypatch.setattr(vertical, "feed_nvd", lambda *a, **k: _stale_source({"items": []}))
    monkeypatch.setattr(vertical, "feed_yahoo", lambda symbol: _live(symbol))
    monkeypatch.setattr(vertical, "feed_polygon", lambda symbol: (
        _live(symbol, official=True) if symbol == "SPY"
        else _stale_source({"symbol": symbol, "price": 1.0})
    ))
    monkeypatch.setattr(vertical, "feed_coinbase", lambda pair: _live(pair, official=True))
    monkeypatch.setattr(vertical, "feed_fx", lambda *a: _stale_source({"rates": {"EUR": 0.8}}))

    app = FastAPI()
    vertical.register(app)
    defense = _payload(asyncio.run(_endpoint(app, "/api/a11oy/v1/vert/defense/feed")()))
    finance = _payload(asyncio.run(_endpoint(app, "/api/a11oy/v1/vert/finance/feed")()))

    for source in (
        defense["nvd"], finance["equities_official"]["AAPL"],
        finance["equities_official"]["MSFT"],
        finance["equities_official"]["NVDA"], finance["fintech_cve"],
        finance["fx"],
    ):
        assert source["value"] is not None
        assert source["freshness"]["status"] == "cached"
        assert source["freshness"]["fetched_at"] == 1786449500
        assert source["freshness"]["error"] == "HTTPStatusError: 503"

    defense_path = "/api/a11oy/v1/vert/defense/feed"
    finance_path = "/api/a11oy/v1/vert/finance/feed"
    assert _probe(defense_path, defense) == {
        "schemaOk": True, "labelsOk": True, "freshOk": True,
    }
    assert _probe(finance_path, finance) == {
        "schemaOk": True, "labelsOk": True, "freshOk": True,
    }
    old = copy.deepcopy(finance)
    old["fx"]["freshness"]["fetched_at"] = 1786440000
    assert _probe(finance_path, old)["freshOk"] is False
    for section, symbol in (("equities_official", "AAPL"), ("crypto", "ETH-USD")):
        aged = copy.deepcopy(finance)
        aged[section][symbol]["freshness"]["fetched_at"] = 1786440000
        assert _probe(finance_path, aged)["freshOk"] is False


def test_finance_route_marks_missing_fx_as_canonical_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(vertical, "feed_yahoo", lambda symbol: _live(symbol))
    monkeypatch.setattr(vertical, "feed_polygon", lambda symbol: _live(symbol, official=True))
    monkeypatch.setattr(vertical, "feed_coinbase", lambda pair: _live(pair, official=True))
    monkeypatch.setattr(vertical, "feed_nvd", lambda *a, **k: _live("CVE"))
    monkeypatch.setattr(vertical, "feed_fx", lambda *a: {
        "value": None,
        "freshness": {
            "status": "unavailable",
            "fetched_at": 1786449500,
            "error": "TimeoutError: upstream FX unavailable",
        },
    })

    app = FastAPI()
    vertical.register(app)
    finance = _payload(asyncio.run(_endpoint(app, "/api/a11oy/v1/vert/finance/feed")()))
    assert finance["fx"] == {
        "value": None,
        "freshness": {
            "status": "UNAVAILABLE",
            "fetched_at": 1786449500,
            "error": "TimeoutError: upstream FX unavailable",
        },
    }
    finance_path = "/api/a11oy/v1/vert/finance/feed"
    assert _probe(finance_path, finance) == {
        "schemaOk": True, "labelsOk": True, "freshOk": True,
    }
    for missing in ("fetched_at", "error"):
        malformed = copy.deepcopy(finance)
        del malformed["fx"]["freshness"][missing]
        assert _probe(finance_path, malformed)["labelsOk"] is False


def test_finance_route_does_not_launder_clockless_stale_equity(monkeypatch) -> None:
    monkeypatch.setattr(vertical, "feed_yahoo", lambda symbol: _live(symbol))

    def polygon(symbol: str) -> dict:
        if symbol != "AAPL":
            return _live(symbol, official=True)
        clockless = _stale_source({"symbol": symbol, "price": 1.0})
        del clockless["freshness"]["fetched_at"]
        return clockless

    monkeypatch.setattr(vertical, "feed_polygon", polygon)
    monkeypatch.setattr(vertical, "feed_coinbase", lambda pair: _live(pair, official=True))
    monkeypatch.setattr(vertical, "feed_nvd", lambda *a, **k: _live("CVE"))
    monkeypatch.setattr(vertical, "feed_fx", lambda *a: _live("USD", official=True))

    app = FastAPI()
    vertical.register(app)
    finance_path = "/api/a11oy/v1/vert/finance/feed"
    finance = _payload(asyncio.run(_endpoint(app, finance_path)()))
    assert finance["equities_official"]["AAPL"]["freshness"]["status"] == "stale"
    assert _probe(finance_path, finance)["labelsOk"] is False
