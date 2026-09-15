# SPDX-License-Identifier: Apache-2.0
"""Network-free finance contracts: semantics, source boundary, cache, HTTP and wiring."""
import concurrent.futures
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
import pytest

sources = importlib.import_module("verticals.puriq-markets.runtime.sources")
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
routes = importlib.import_module("verticals.puriq-markets.runtime.routes")

NOW = 1_789_430_400
TOKEN = "read-fixture-" * 4
ENV = {"SZL_SEC_USER_AGENT": "SZL contract test test@example.invalid",
       "SZL_FINANCE_PRIVATE_READ_TOKEN": TOKEN, "SZL_FRED_API_KEY": "a" * 32,
       "APCA_API_KEY_ID": "fixture-id", "APCA_API_SECRET_KEY": "fixture-secret",
       "SZL_SOURCE_REVISION": "1" * 40}
PARAMS = {"polymarket-book": {"token_id": "123"}, "polymarket-history": {"token_id": "123"},
          "kalshi-book": {"ticker": "KXTEST-26-A"},
          "coinbase-candles": {"count": "3", "granularity": "900"}}


def fixture(source, p):
    if source == "polymarket-markets":
        return [{"id": "1", "conditionId": "0xcondition", "question": "Synthetic fixture",
            "outcomes": '["No","Yes"]', "outcomePrices": '["0.3","0.7"]',
            "clobTokenIds": '["123","456"]', "active": True, "closed": False,
            "enableOrderBook": True, "volume24hr": 0, "volume": "1000"}]
    if source == "polymarket-book":
        return {"asset_id": p["token_id"], "timestamp": str(NOW * 1000),
                "bids": [{"price": ".2", "size": "5"}, {"price": ".4", "size": "4"}],
                "asks": [{"price": ".8", "size": "6"}, {"price": ".6", "size": "7"}]}
    if source == "polymarket-history":
        return {"history": [{"t": NOW - 60, "p": .7}, {"t": NOW - 120, "p": .6}]}
    if source == "kalshi-markets":
        return {"markets": [{"ticker": "KXTEST-26-A", "event_ticker": "KXTEST-26",
            "title": "Synthetic fixture", "yes_bid_dollars": "0.4200", "yes_ask_dollars": "0.4400",
            "volume_24h_fp": "0.00", "volume_fp": "123.00", "rules_primary": "Fixture only"}], "cursor": "next_fixture"}
    if source == "kalshi-book":
        return {"orderbook_fp": {"yes_dollars": [["0.4200", "13.25"]], "no_dollars": [["0.5600", "17.50"]]}}
    if source == "coinbase-products":
        return [{"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD", "status": "online", "trading_disabled": False}]
    if source == "coinbase-ticker":
        return {"price": "100", "bid": "99", "ask": "101", "time": "2026-09-15T00:00:00Z", "volume": "0"}
    if source == "coinbase-candles":
        return [[p["start"] + i * p["granularity"], 98, 102, 99, 101, 0] for i in range(p["count"])][::-1]
    if source == "sec-submissions":
        return {"cik": int(p["cik"]), "name": "Fixture issuer", "filings": {"files": [], "recent": {
            "accessionNumber": ["0000000000-26-000001"], "filingDate": ["2026-01-01"],
            "reportDate": ["2025-12-31"], "acceptanceDateTime": ["2026-01-01T00:00:00Z"],
            "form": ["10-K"], "primaryDocument": ["fixture.htm"]}}}
    if source == "sec-companyfacts":
        return {"cik": int(p["cik"]), "entityName": "Fixture issuer", "facts": {"us-gaap": {"Assets": {
            "units": {"USD": [{"val": 123, "end": "2025-12-31", "filed": "2026-01-01", "form": "10-K", "fp": "FY"}]}}}}}
    if source.startswith("treasury-"):
        return {"data": [{"record_date": "2026-08-31", "security_type_desc": "Marketable", "security_desc": "Bills",
            "avg_interest_rate_amt": "4.200", "tot_pub_debt_out_amt": "12345678901234.56"}], "meta": {"total-pages": 10}}
    if source == "bls-series":
        return {"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"seriesID": p["series_id"],
            "data": [{"year": "2025", "period": "M13", "periodName": "Annual", "value": "123", "footnotes": [{}]}]}]}}
    if source == "fred-series":
        return {"realtime_start": p["as_of"], "realtime_end": p["as_of"], "observations": [
            {"date": "2025-01-01", "value": ".", "realtime_start": p["as_of"], "realtime_end": p["as_of"]}]}
    if source == "alpaca-quote":
        return {"symbol": p["symbol"], "quote": {"t": "2026-09-15T00:00:00Z", "bp": 100, "ap": 101, "bs": 1, "as": 2, "bx": "V", "ax": "V"}}
    if source == "alpaca-bars":
        return {"symbol": p["symbol"], "bars": [{"t": p["start"], "o": 99, "h": 102, "l": 98, "c": 101, "v": 50}], "next_page_token": "next_fixture"}
    raise AssertionError(source)


def plan(source):
    return sources.build_plan(source, PARAMS.get(source, {}), ENV, NOW)


def network_fixture(p):
    return json.dumps(fixture(p.source, p.parameters)).encode()


def client(fetch=network_fixture, env=None, clock=None, capacity=128):
    clock = clock or (lambda: NOW)
    return transport.FinanceClient(fetch=fetch, environ=ENV if env is None else env,
                                   clock=clock, monotonic=clock, capacity=capacity)


@pytest.mark.parametrize("source", sources.SOURCES)
def test_each_adapter_observation_is_source_bound_and_read_only(source):
    body = client().observe(source, PARAMS.get(source, {}), access_token=TOKEN)
    assert body["ok"] is True, body
    assert body["state"] == "SNAPSHOT"
    assert body["execution_enabled"] is False
    assert body["provenance"]["signed"] is False
    assert body["provenance"]["runtime_reported_source_revision"] == "1" * 40
    assert body["provenance"]["normalized_data_sha256"] == transport.digest(body["data"])
    json.dumps(body, allow_nan=False)


@pytest.mark.parametrize("source", sources.SOURCES)
def test_each_adapter_rejects_arbitrary_url_parameters(source):
    with pytest.raises(transport.FinanceError, match="INVALID_PARAMETERS"):
        sources.build_plan(source, {"url": "https://127.0.0.1/admin"}, ENV, NOW)


@pytest.mark.parametrize("value", [True, False, "NaN", "Infinity", "-Infinity", "1e999999", "1e-999999", [], {}, "invalid"])
def test_numbers_reject_nonfinite_bool_unbounded_and_non_numeric(value):
    with pytest.raises(transport.FinanceError):
        sources.number(value)


def test_polymarket_outcome_position_zero_volume_and_token_identity():
    p = plan("polymarket-markets")
    raw = fixture(p.source, p.parameters)
    raw[0]["outcomePrices"] = '["bad","0.7"]'
    data = sources.normalize(p.source, raw, p.parameters, NOW)["items"][0]
    assert data["outcomes"][0] == {"index": 0, "label": "No", "price": None, "token_id": "123"}
    assert data["outcomes"][1]["label"] == "Yes"
    assert data["outcomes"][1]["price"] == "0.7"
    assert data["volume_24h_usd"] == "0"
    assert data["volume_lifetime_usd"] == "1000"
    assert data["cross_venue_equivalence"] == "NOT_ESTABLISHED"


def test_polymarket_mismatched_arrays_are_not_zipped_or_shifted():
    p = plan("polymarket-markets")
    raw = fixture(p.source, p.parameters)
    raw[0]["clobTokenIds"] = '["123"]'
    data = sources.normalize(p.source, raw, p.parameters, NOW)["items"][0]
    assert all(o["token_id"] is None for o in data["outcomes"])
    assert "OUTCOME_ARRAY_LENGTH_MISMATCH" in data["quality_flags"]


def test_books_sort_find_best_prices_and_detect_crossing():
    p = plan("polymarket-book")
    raw = fixture(p.source, p.parameters)
    data = sources.normalize(p.source, raw, p.parameters, NOW)
    assert data["best_bid"] == "0.4" and data["best_ask"] == "0.6"
    assert data["spread"] == "0.2"
    raw["asks"][1]["price"] = ".3"
    data = sources.normalize(p.source, raw, p.parameters, NOW)
    assert data["spread"] is None and data["quality"] == "INVALID_CROSSED"


def test_wrong_polymarket_token_response_is_denied():
    p = plan("polymarket-book")
    raw = fixture(p.source, p.parameters)
    raw["asset_id"] = "999"
    with pytest.raises(transport.FinanceError, match="IDENTITY_MISMATCH"):
        sources.normalize(p.source, raw, p.parameters, NOW)


def test_kalshi_fractional_units_and_complement_are_exact():
    p = plan("kalshi-book")
    data = sources.normalize(p.source, fixture(p.source, p.parameters), p.parameters, NOW)
    assert data["best_bid"] == "0.4200"
    assert Decimal(data["best_ask"]) == Decimal("0.4400")
    assert Decimal(data["spread"]) == Decimal("0.0200")
    assert data["asks"][0]["quantity"] == "17.50"
    assert data["asks_kind"] == "DERIVED_COMPLEMENT_OF_NO_BIDS"
    assert data["provider_age_seconds"] is None


def test_kalshi_legacy_integer_cents_stay_separate_from_dollars():
    p = plan("kalshi-book")
    data = sources.normalize(p.source, {"orderbook": {"yes": [[42, 2]], "no": [[56, 3]]}}, p.parameters, NOW)
    assert data["best_bid"] == "0.42"
    assert Decimal(data["spread"]) == Decimal(".02")


def test_empty_one_sided_book_does_not_invent_zero_spread():
    p = plan("kalshi-book")
    data = sources.normalize(p.source, {"orderbook_fp": {"yes_dollars": [[".4", "1"]], "no_dollars": []}}, p.parameters, NOW)
    assert data["best_ask"] is None and data["spread"] is None
    assert data["quality"] == "INCOMPLETE"


def test_duplicate_book_levels_fail_closed():
    with pytest.raises(transport.FinanceError, match="DUPLICATE_BOOK_LEVEL"):
        sources.levels([[".4", "1"], ["0.40", "2"]])


def test_coinbase_completed_bars_are_sorted_and_boundary_gaps_reported():
    p = plan("coinbase-candles")
    raw = fixture(p.source, p.parameters)
    raw.pop()
    raw.append([p.parameters["end"], 98, 102, 99, 101, 1])
    data = sources.normalize(p.source, raw, p.parameters, NOW)
    assert data["missing_intervals"] == [p.parameters["start"]]
    assert data["window_complete"] is False
    assert data["excluded_outside_window"] == 1
    assert data["interpolation"] == "NONE"
    assert data["items"][0]["time"] < data["items"][1]["time"]


def test_coinbase_duplicate_and_invalid_ohlc_are_denied():
    p = plan("coinbase-candles")
    raw = fixture(p.source, p.parameters)
    with pytest.raises(transport.FinanceError, match="TIMESTAMP"):
        sources.normalize(p.source, [raw[0], raw[0]], p.parameters, NOW)
    raw[0][1] = 999
    with pytest.raises(transport.FinanceError, match="OHLC"):
        sources.normalize(p.source, raw, p.parameters, NOW)


def test_empty_history_is_empty_not_fabricated_data():
    p = plan("polymarket-history")
    data = sources.normalize(p.source, {"history": []}, p.parameters, NOW)
    assert data["count"] == 0 and data["data_state"] == "EMPTY"


def test_history_duplicate_and_future_timestamps_fail_closed():
    p = plan("polymarket-history")
    for history in [[{"t": NOW + 60, "p": .5}], [{"t": NOW, "p": .5}, {"t": NOW, "p": .6}]]:
        with pytest.raises(transport.FinanceError, match="HISTORY_TIMESTAMP"):
            sources.normalize(p.source, {"history": history}, p.parameters, NOW)


def test_sec_recent_columns_do_not_shift_and_cik_is_bound():
    p = plan("sec-submissions")
    raw = fixture(p.source, p.parameters)
    raw["filings"]["recent"]["form"] = []
    with pytest.raises(transport.FinanceError, match="COLUMN_LENGTH"):
        sources.normalize(p.source, raw, p.parameters, NOW)
    raw["cik"] = 999
    with pytest.raises(transport.FinanceError, match="CIK_IDENTITY"):
        sources.normalize(p.source, raw, p.parameters, NOW)


def test_bls_annual_average_is_not_a_thirteenth_month():
    p = plan("bls-series")
    data = sources.normalize(p.source, fixture(p.source, p.parameters), p.parameters, NOW)
    assert data["items"][0]["is_annual_average"] is True
    assert "vintage not established" in data["vintage"]


def test_fred_missing_values_preserved_and_asof_mismatch_fails():
    p = plan("fred-series")
    raw = fixture(p.source, p.parameters)
    data = sources.normalize(p.source, raw, p.parameters, NOW)
    assert data["items"][0]["value"] is None
    raw["realtime_start"] = "2020-01-01"
    with pytest.raises(transport.FinanceError, match="VINTAGE_MISMATCH"):
        sources.normalize(p.source, raw, p.parameters, NOW)


def test_fred_key_is_never_in_public_plan_repr_or_observation():
    p = plan("fred-series")
    assert ENV["SZL_FRED_API_KEY"] in p.url
    assert ENV["SZL_FRED_API_KEY"] not in p.public_url
    assert ENV["SZL_FRED_API_KEY"] not in repr(p)
    body = client().observe("fred-series", access_token=TOKEN)
    assert ENV["SZL_FRED_API_KEY"] not in json.dumps(body)
    assert "api_key" not in body["provenance"]["source_url"]


def test_alpaca_feed_identity_and_no_replay_claim():
    p = plan("alpaca-bars")
    data = sources.normalize(p.source, fixture(p.source, p.parameters), p.parameters, NOW)
    assert data["feed"] == "iex" and data["adjustment"] == "raw"
    assert data["session_completeness_verified"] is False and data["replay_eligible"] is False


def test_private_sources_require_independent_read_auth_even_if_api_key_exists():
    c = client()
    for source in ("fred-series", "alpaca-quote", "alpaca-bars"):
        with pytest.raises(transport.FinanceError, match="PRIVATE_SOURCE_ACCESS"):
            c.observe(source)


def test_unknown_source_and_invalid_query_rejected_before_network():
    calls = []
    c = client(fetch=lambda p: calls.append(p))
    for source, query in [("unknown", {}), ("coinbase-ticker", {"product": "../../accounts"}),
                          ("polymarket-book", {"token_id": "123&url=https://example.com"})]:
        with pytest.raises(transport.FinanceError):
            c.observe(source, query)
    assert not calls


def test_missing_sec_configuration_is_unavailable_without_network():
    c = client(env={})
    body = c.observe("sec-submissions")
    assert not body["ok"] and body["error"] == "NEEDS_SEC_USER_AGENT"


def test_cache_failure_preserves_old_provenance_and_timestamp():
    t = [NOW]
    calls = []
    def fetch(p):
        calls.append(p)
        if len(calls) > 1:
            raise transport.FinanceError("UPSTREAM_HTTP_429", 60)
        return network_fixture(p)
    c = client(fetch, clock=lambda: t[0])
    a = c.observe("coinbase-ticker")
    t[0] += 11
    b = c.observe("coinbase-ticker")
    assert b["state"] == "STALE" and not b["ok"]
    assert b["retrieved_at"] == a["retrieved_at"]
    assert b["provenance"] == a["provenance"]
    t[0] += 1
    other = c.observe("coinbase-ticker", {"product": "ETH-USD"})
    assert other["error"] == "PROVIDER_COOLDOWN" and len(calls) == 2


def test_cache_returns_deep_copies_and_cannot_be_poisoned_by_caller():
    c = client()
    a = c.observe("coinbase-ticker")
    a["data"]["price"] = "999999"
    b = c.observe("coinbase-ticker")
    assert b["state"] == "CACHED" and b["data"]["price"] == "100"


def test_singleflight_under_concurrent_reads():
    calls = []
    def fetch(p):
        calls.append(p)
        return network_fixture(p)
    c = client(fetch)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(lambda _: c.observe("coinbase-ticker"), range(16)))
    assert len(calls) == 1 and all(r["ok"] for r in result)


def test_bounded_cache_and_distinct_parameter_identity():
    t = [NOW]
    c = client(clock=lambda: t[0], capacity=2)
    seen = []
    for product in ("BTC-USD", "ETH-USD", "SOL-USD"):
        seen.append(c.observe("coinbase-ticker", {"product": product})["provenance"]["observation_id"])
        t[0] += 1
    assert len(c._cache) == 2 and len(set(seen)) == 3


def test_malformed_provider_json_returns_unavailable_not_html_or_green():
    for raw in (b"<html>denied</html>", b'{"price": NaN}', b'{"price":1,"price":2}'):
        body = client(fetch=lambda p: raw).observe("coinbase-ticker")
        assert not body["ok"] and body["data"] is None
        assert body["state"] == "UNAVAILABLE"


def test_registry_is_configuration_not_connectivity():
    body = client().registry()
    assert len(body["sources"]) == 16
    assert all(s["observed_connection"] == "NOT_PROBED" for s in body["sources"])
    assert all(s["last_attempt"] is None for s in body["sources"])


def test_route_assembly_ahead_of_spa_and_no_write_routes(monkeypatch):
    monkeypatch.setattr(routes, "CLIENT", client())
    app = FastAPI()
    @app.get("/{path:path}")
    def spa(path):
        return HTMLResponse("SPA fallback")
    import a11oy_markets
    a11oy_markets.register(app)
    http = TestClient(app)
    prefix = routes.PREFIX
    assert http.get(prefix + "/providers").json()["schema"] == "szl.finance.providers/v1"
    result = http.get(prefix + "/observations/coinbase-ticker")
    assert result.status_code == 200 and result.json()["source"] == "coinbase-ticker"
    assert http.get(prefix + "/observations/coinbase-ticker?product=BTC-USD&product=ETH-USD").status_code == 422
    assert http.get(prefix + "/observations/coinbase-ticker?url=https://127.0.0.1/").status_code == 422
    assert http.get(prefix + "/observations/alpaca-quote").status_code == 403
    assert http.post(prefix + "/observations/coinbase-ticker").status_code == 405
    assert all(route.methods <= {"GET"} for route in app.routes if getattr(route, "path", "").startswith(prefix))
    assert result.headers["cache-control"] == "private, no-store"


def test_overview_reports_partial_failure_without_declaring_all_connected(monkeypatch):
    def fetch(p):
        if p.source == "kalshi-markets":
            raise transport.FinanceError("UPSTREAM_HTTP_503")
        return network_fixture(p)
    monkeypatch.setattr(routes, "CLIENT", client(fetch))
    body = json.loads(routes.finance_overview().body)
    assert body["state"] == "DEGRADED" and body["ok"] is False
    assert body["sources_available"] == 3 and body["sources_requested"] == 4
    assert body["event_equivalence"] == "NOT_ESTABLISHED"


class Response:
    def __init__(self, body=b'{}', status=200, headers=None):
        self.body, self.status, self.offset = body, status, 0
        self.headers = {"Content-Type": "application/json", **(headers or {})}
    def getheader(self, name):
        return self.headers.get(name)
    def read(self, n):
        piece = self.body[self.offset:self.offset+n]
        self.offset += len(piece)
        return piece


class Connection:
    response = None
    calls = []
    sock = None
    def __init__(self, host, **kwargs):
        self.host = host
    def set_debuglevel(self, level):
        assert level == 0
    def request(self, method, target, headers):
        self.calls.append((method, self.host, target, dict(headers)))
    def getresponse(self):
        return self.response
    def close(self):
        pass


@pytest.mark.parametrize("url", ["http://clob.polymarket.com/book", "https://evil.example/book",
    "https://user@clob.polymarket.com/book", "https://clob.polymarket.com:444/book", "https://127.0.0.1/book"])
def test_transport_rejects_unapproved_destinations(url):
    with pytest.raises(transport.FinanceError, match="DESTINATION_DENIED"):
        transport.fetch_bytes(transport.Plan("x", "x", url, "redacted"))


@pytest.mark.parametrize("response,code", [
    (Response(status=302, headers={"Location": "https://evil.example"}), "UPSTREAM_HTTP_302"),
    (Response(headers={"Content-Type": "text/html"}), "NON_JSON_RESPONSE"),
    (Response(headers={"Content-Encoding": "gzip"}), "ENCODED_RESPONSE_DENIED"),
    (Response(headers={"Content-Length": "99999999"}), "RESPONSE_TOO_LARGE"),
    (Response(b"x" * 21), "RESPONSE_TOO_LARGE"),
])
def test_transport_blocks_redirects_wrong_types_and_oversize(response, code):
    Connection.response, Connection.calls = response, []
    p = transport.Plan("x", "polymarket", "https://clob.polymarket.com/book?token_id=123", "public", max_bytes=20)
    with patch.object(transport.http.client, "HTTPSConnection", Connection):
        with pytest.raises(transport.FinanceError, match=code):
            transport.fetch_bytes(p)
    assert len(Connection.calls) == 1 and Connection.calls[0][0] == "GET"


def test_transport_honors_retry_after_and_does_not_leak_error_body():
    Connection.response, Connection.calls = Response(b"sensitive provider body", status=429, headers={"Retry-After": "120"}), []
    with patch.object(transport.http.client, "HTTPSConnection", Connection):
        with pytest.raises(transport.FinanceError) as error:
            transport.fetch_bytes(plan("coinbase-ticker"))
    assert error.value.retry_after == 120
    assert str(error.value) == "UPSTREAM_HTTP_429"


def test_docker_has_complete_new_runtime_copy_closure():
    docker = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    assert "COPY verticals/puriq-markets ./verticals/puriq-markets" in docker
    root = Path(__file__).resolve().parents[1] / "verticals/puriq-markets/runtime"
    assert {"__init__.py", "transport.py", "sources.py", "routes.py"} <= {p.name for p in root.iterdir()}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_finance_projection_preserves_canonical_data_and_no_secret_forwarding(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    proxy = load_module("finance_projection_test", root / "scripts/hf_finance_read_proxy.py")
    # Exercise the actual generated application code, not a copied proxy.
    generator = load_module("flagship_base_test", root / "scripts/_hf_publish_vertical_flagships_v4_impl_base.py")
    cfg = {"slug": "finance", "title": "PURIQ", "upstream": "unused", "hf_repository": "SZLHOLDINGS/finance", "source_revision": "1" * 40}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "index.html").write_text("<main>fixture</main>")
    (tmp_path / "panels.html").write_text("<main>fixture</main>")
    monkeypatch.chdir(tmp_path)
    namespace = {"__name__": "generated_finance_projection"}
    exec(compile(proxy.augment(generator.APP), "generated_app", "exec"), namespace)
    called = []
    payload = client().observe("coinbase-ticker")
    class ProxyResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_bytes(self): yield json.dumps(payload).encode()
    class ProxyClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, target, headers):
            called.append((method, target, headers))
            return ProxyResponse()
    # Patch only the projection's outbound client, not TestClient's own transport.
    from types import SimpleNamespace
    namespace["httpx"] = SimpleNamespace(Client=ProxyClient)
    http = TestClient(namespace["app"])
    reply = http.get("/api/finance/observations/coinbase-ticker?product=BTC-USD", headers={"Authorization": "private-fixture"})
    assert reply.status_code == 200 and reply.json() == payload
    assert "Authorization" not in called[0][2]
    assert called[0][1].startswith("https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/")
    assert http.get("/api/finance/observations/alpaca-quote").status_code == 403
    assert len(called) == 1
    assert http.get("/api/finance/observations/coinbase-ticker?product=X&product=Y").status_code == 422
    assert http.post("/api/finance/overview").status_code == 405
    payload = {"schema": "szl.finance.overview/v1", "ok": False, "state": "DEGRADED", "execution_enabled": False, "source_revision": "1" * 40}
    result = http.get("/api/live").json()
    assert result["status"] == "UNAVAILABLE" and result["data"]["state"] == "DEGRADED"
    payload["source_revision"] = "2" * 40
    assert http.get("/api/finance/overview").json()["error"] == "CANONICAL_REVISION_MISMATCH"
    assert http.get("/api/finance/observations/coinbase-ticker?api_key=private").status_code == 422


def test_publisher_overlay_keeps_finance_on_existing_writer_and_base_unchanged():
    root = Path(__file__).resolve().parents[1]
    overlay = load_module("flagship_overlay_test", root / "scripts/hf_publish_vertical_flagships_v4_impl.py")
    row = next(r for r in overlay.FLAGSHIPS if r["slug"] == "finance")
    assert row["upstream"] == "https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/overview"
    assert row["source"].endswith("a11oy/tree/main/verticals/puriq-markets")
    assert "Public finance projection" in overlay.APP
    assert overlay.TERRA_FORGE_GENERATOR == "szl-vertical-forge/0.2.2"


def test_oversized_identifiers_are_rejected_not_truncated_to_another_asset():
    p = plan("polymarket-markets")
    raw = fixture(p.source, p.parameters)
    raw[0]["clobTokenIds"] = json.dumps(["1" * 81, "456"])
    with pytest.raises(transport.FinanceError, match="INVALID_SOURCE_IDENTIFIER"):
        sources.normalize(p.source, raw, p.parameters, NOW)


def test_polymarket_old_source_timestamp_is_not_fresh_just_because_retrieved_now():
    p = plan("polymarket-book")
    raw = fixture(p.source, p.parameters)
    raw["timestamp"] = str((NOW - 60) * 1000)
    data = sources.normalize(p.source, raw, p.parameters, NOW)
    assert data["source_freshness"] == "STALE"
    raw["timestamp"] = str((NOW + 60) * 1000)
    with pytest.raises(transport.FinanceError, match="PROVIDER_CLOCK_AHEAD"):
        sources.normalize(p.source, raw, p.parameters, NOW)
