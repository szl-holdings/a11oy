# SPDX-License-Identifier: Apache-2.0
"""Exercise source-bound arithmetic, HTTP boundaries and emitted Finance proxy."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from .test_finance_release_boundaries import projection

analytics = importlib.import_module("verticals.puriq-markets.runtime.analytics")
routes = importlib.import_module("verticals.puriq-markets.runtime.routes")
transport = importlib.import_module("verticals.puriq-markets.runtime.transport")
REVISION = "1" * 40
PREFIX = routes.PREFIX + "/analytics/v2"


@pytest.fixture
def canonical(monkeypatch):
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION},
        fetch=lambda plan: pytest.fail("synthetic request attempted provider access"))
    monkeypatch.setattr(routes, "CLIENT", client)
    app = FastAPI()
    routes.register(app)
    return TestClient(app), client


def test_component_is_exact_immutable_reviewed_math():
    binding = analytics.COMPONENT
    assert binding["repository"] == "szl-holdings/vertical-services"
    assert binding["revision"] == "f487dc0fdc71af52841e3634bf7b9c6bf9fb6448"
    assert binding["path"] == "services/finance/engine.py"
    assert hashlib.sha256((analytics.ROOT / "engine.py").read_bytes()).hexdigest() == binding["engine_sha256"]
    assert binding["engine_sha256"] == "78816c492102ffb8b0ab958a18a89adb1e57eb77a93d1c89a7b6a92a20b691b6"


@pytest.mark.parametrize("operation", ["signals", "quote"])
def test_fixture_is_repeatable_modeled_unsigned_and_never_provider_access(canonical, operation):
    http, _ = canonical
    path = PREFIX + "/" + operation + "/AAPL?origin=fixture"
    first, second = http.get(path), http.get(path)
    assert first.status_code == 200 and first.json() == second.json()
    body = first.json()
    assert body["source_revision"] == REVISION
    assert body["truth_label"] == "MODELED" and body["inputs"]["asset"]["truth_label"] == "SYNTHETIC"
    assert body["execution_enabled"] is False
    assert body["receipt"]["signing"] == "UNSIGNED_HONEST"
    assert analytics.verify(body)
    assert '"MEASURED"' not in json.dumps(body)
    assert first.headers["cache-control"] == "private, no-store"


def test_math_has_independent_known_answers(canonical):
    http, _ = canonical
    result = http.post(PREFIX + "/portfolio", json={
        "holdings": {"TEST": [100, 110, 99]}, "periods_per_year": 252})
    assert result.status_code == 200
    body = result.json()
    asset = body["result"]["per_asset"]["TEST"]
    assert asset["volatility"] == pytest.approx((.02 * 252) ** .5)
    assert asset["sharpe"] == pytest.approx(0, abs=1e-12)
    assert asset["max_drawdown"] == pytest.approx(-.1)
    assert body["inputs"]["truth_label"] == "UNVERIFIED"
    assert body["result"]["truth_label"] == "MODELED" and analytics.verify(body)
    report = body["result"]
    assert report["report_digest"] == analytics.engine.canonical_digest(
        {key: value for key, value in report.items() if key != "report_digest"})


@pytest.mark.parametrize("holdings,annual", [({},252), ({"a":[1,2,3]},252),
    ({"A":[1,2]},252), ({"A":[True,2,3]},252), ({"A":[0,2,3]},252),
    ({"A":[1,2,-3]},252), ({"A":[1,2,3]},True), ({"A":[1,2,3]},999),
    ({"A":[1] * 301},252), ({str(i):[1,2,3] for i in range(17)},252)])
def test_portfolio_validation_is_bounded_and_strict(canonical, holdings, annual):
    http, _ = canonical
    reply = http.post(PREFIX + "/portfolio", json={"holdings":holdings,"periods_per_year":annual})
    assert reply.status_code == 422 and reply.json()["ok"] is False


@pytest.mark.parametrize("raw", [b'{"holdings":{},"holdings":{}}', b'{"x":NaN}', b'{"x":Infinity}',
                                b'{"x":1e9999}', b'[' * 2000, b' ' * 160001],
                         ids=["duplicate", "nan", "infinity", "overflow", "depth", "oversize"])
def test_malformed_or_excessive_post_never_computes(canonical, raw):
    http, _ = canonical
    assert http.post(PREFIX + "/portfolio", content=raw).status_code == 422


def test_receipt_verification_is_stateless_integrity_only(canonical):
    http, _ = canonical
    body = http.get(PREFIX + "/signals/AAPL?origin=fixture").json()
    checked = http.post(PREFIX + "/receipts/verify", json=body).json()
    assert checked["result"]["verified"] is True
    assert checked["result"]["state"] == "INTEGRITY_VALID"
    assert checked["result"]["authenticity_established"] is False
    body["result"]["verdict"] = "TAMPERED"
    invalid = http.post(PREFIX + "/receipts/verify", json=body).json()["result"]
    assert invalid["verified"] is False and invalid["state"] == "INVALID"
    assert http.get(PREFIX + "/receipts").json()["result"]["entries"] == []
    assert http.get(PREFIX + "/receipts/verify").json()["result"]["verified"] is False
    assert http.get(PREFIX + "/receipts/verify").json()["result"]["state"] == "INPUT_REQUIRED"


def test_fractional_prices_are_accepted_and_roundtrip_receipts(canonical):
    http, _ = canonical
    result = http.post(PREFIX + "/portfolio", json={"holdings":{"A":[1.25,1.75,1.50]},"periods_per_year":252})
    assert result.status_code == 200
    assert http.post(PREFIX + "/receipts/verify", json=result.json()).json()["result"]["verified"] is True


@pytest.mark.parametrize("path", ["/signals/AAPL?origin=fixture", "/receipts", "/receipts/verify"])
def test_unbound_source_fails_closed(canonical, path):
    http, client = canonical
    client.environ.clear()
    result = http.get(PREFIX + path)
    assert result.status_code == 503 and result.json()["error"] == "CANONICAL_SOURCE_UNBOUND"


def test_coinbase_complete_daily_window_and_timestamp_alignment(monkeypatch):
    captured = []
    tick = [100.0]
    monkeypatch.setattr(analytics.time, "sleep", lambda delay: tick.__setitem__(0, tick[0] + delay))
    def fetch(plan):
        captured.append(plan)
        return json.dumps([[plan.parameters["start"] + i * 86400, 50, 200, 100,
                            100 + i * .1 + (i % 5), 1] for i in range(260)][::-1]).encode()
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION},
        fetch=fetch, clock=lambda: 1789430400, monotonic=lambda: tick[0])
    result = analytics.compute(client, "quote", "BTC-USD", "coinbase", "ETH-USD")
    assert result["inputs"]["periods_per_year"] == 365
    assert result["result"]["stats"]["beta"] == pytest.approx(1)
    assert len(captured) == 2 and captured[0].parameters["end"] == captured[1].parameters["end"]
    assert 100.3 < tick[0] < 100.35
    assert result["inputs"]["asset"]["observation"]["provenance"]["source_bytes_sha256"]


def test_missing_provider_intervals_are_not_interpolated():
    def fetch(plan):
        return json.dumps([[plan.parameters["start"] + i * 86400, 50, 200, 100, 100+i*.1, 1]
                           for i in range(259)]).encode()
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION}, fetch=fetch)
    with pytest.raises(transport.FinanceError, match="INCOMPLETE_HISTORY"):
        analytics.compute(client, "signals", "BTC-USD", "coinbase")


def test_default_input_lane_never_substitutes_fixture(canonical):
    http, client = canonical
    client.fetch = lambda plan: (_ for _ in ()).throw(transport.FinanceError("UPSTREAM_HTTP_503"))
    result = http.get(PREFIX + "/signals/BTC-USD")
    assert result.status_code == 503 and "result" not in result.json()


def test_emitted_proxy_accepts_exact_computation_and_rejects_tampering(projection):
    http, state = projection
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION})
    state.update(body=analytics.compute(client, "signals", "AAPL", "fixture"), status=200)
    result = http.get("/api/finance/v2/signals/AAPL?origin=fixture")
    assert result.status_code == 200 and result.json() == state["body"]
    assert state["calls"][0][0].endswith("/analytics/v2/signals/AAPL?origin=fixture")
    state["body"]["result"]["verdict"] = "TAMPERED"
    result = http.get("/api/finance/v2/signals/AAPL?origin=fixture")
    assert result.status_code == 503 and result.json()["error"] == "CANONICAL_RECEIPT_INVALID"


@pytest.mark.parametrize("change", ["revision", "component", "authority", "advisory", "operation", "origin", "symbol"])
def test_projection_rejects_misbound_even_if_self_consistent(projection, change):
    http, state = projection
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION})
    body = analytics.compute(client, "signals", "AAPL", "fixture")
    if change == "revision": body["source_revision"] = "2" * 40
    elif change == "component": body["component"] = {**body["component"], "engine_sha256": "0" * 64}
    elif change == "authority": body["receipt"]["authority"] = "TRADING"
    elif change == "advisory": body["advisory_only"] = False
    elif change == "operation": body["operation"] = "quote"
    elif change == "origin": body["inputs"]["asset"]["origin"] = "coinbase"
    else: body["result"]["symbol"] = "WRONG"
    body["receipt"]["payload_sha256"] = transport.digest({key:value for key,value in body.items() if key != "receipt"})
    body["receipt"]["receipt_sha256"] = transport.digest({key:value for key,value in body["receipt"].items() if key != "receipt_sha256"})
    state.update(body=body, status=200)
    assert http.get("/api/finance/v2/signals/AAPL?origin=fixture").status_code == 503


def test_projection_post_drops_caller_credentials_and_limits_body(projection):
    http, state = projection
    client = transport.FinanceClient(environ={"SZL_SOURCE_REVISION": REVISION})
    payload = {"holdings":{"A":[100,110,99]},"periods_per_year":252}
    state.update(body=analytics.portfolio(client,payload), status=200)
    original = state["namespace"]["httpx"].Client
    class Client(original):
        def stream(self, method, target, headers, content=None):
            assert method == "POST" and json.loads(content) == payload
            assert not any(key.lower() in ("authorization", "cookie", "x-szl-finance-read-token") for key in headers)
            return super().stream("GET", target, headers)
    state["namespace"]["httpx"] = SimpleNamespace(Client=Client)
    result = http.post("/api/finance/v2/portfolio",json=payload,headers={"Authorization":"secret-fixture","Cookie":"fixture=value"})
    assert result.status_code == 200
    state["calls"].clear()
    assert http.post("/api/finance/v2/portfolio",content=b' ' * 160001).status_code == 422
    assert state["calls"] == []
