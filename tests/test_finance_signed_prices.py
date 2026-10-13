# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic signed transport, canonical routes and emitted projection boundaries."""
from copy import deepcopy
import importlib
import json
import hashlib
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from .test_finance_signed_verifier import signed
from .test_finance_release_boundaries import projection

prices = importlib.import_module("verticals.puriq-markets.runtime.signed_prices")
routes = importlib.import_module("verticals.puriq-markets.runtime.routes")
REVISION = "1" * 40
ENV = {"SZL_SOURCE_REVISION": REVISION}


def sample(signed, change=None):
    _, data, ring, now = signed
    data = deepcopy(data)
    if change:
        change(data)
    calls = []
    def respond(request):
        calls.append(request)
        assert "authorization" not in request.headers
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, json=ring if request.url.path.endswith("pubkey") else data)
    client = prices.SignedPriceClient(httpx.MockTransport(respond), clock=lambda: now)
    return client, calls


def signed_envelope(signed):
    client, _ = sample(signed)
    return prices.envelope(ENV, client.observe("BTC"))


def test_pinned_components():
    assert prices.COMPONENT["revision"] == "2ea8ea4bb9de2ca432f40c0c55ea5a5ed02786bf"
    for path, digest in prices.COMPONENT["files"].items():
        assert hashlib.sha256((prices.ROOT / path).read_bytes()).hexdigest() == digest


def test_real_crypto_through_canonical_and_public_projection(signed, projection, monkeypatch):
    client, calls = sample(signed)
    monkeypatch.setattr(prices, "CLIENT", client)
    monkeypatch.setattr(routes.CLIENT, "environ", ENV)
    app = FastAPI(); routes.register(app)
    body = TestClient(app).get(routes.PREFIX + "/signed-prices/BTC").json()
    assert body["state"] == "REVIEW"
    assert body["result"]["verification"]["record_valid"] is True
    assert len(calls) == 2
    http, state = projection; state.update(body=body, status=200)
    response = http.get("/api/finance/signed-prices/BTC")
    assert response.status_code == 200 and response.json() == body
    assert "no-store" in response.headers["cache-control"]
    assert state["calls"][-1][0].endswith("/api/a11oy/v1/finance/signed-prices/BTC")


@pytest.mark.parametrize("change", [lambda p: p.update(sources=999), lambda p: p.pop("v2"),
    lambda p: p.update(signature="invalid"), lambda p: p.update(priceText="1")])
def test_tampered_or_partial_record_abstains_without_display_price(signed, projection, change):
    client, _ = sample(signed, change)
    body = prices.envelope(ENV, client.observe("BTC"))
    assert body["state"] == "ABSTAIN" and body["result"]["price_text"] is None
    http, state = projection; state.update(body=body, status=200)
    assert http.get("/api/finance/signed-prices/BTC").json() == body


@pytest.mark.parametrize("change", [lambda b: b.update(source_revision="2" * 40),
    lambda b: b["result"].update(price_text="1"),
    lambda b: b["component"].update(revision="2" * 40),
    lambda b: b["result"].update(can_authorize=True)])
def test_proxy_rejects_misbound_or_modified_result(signed, projection, change):
    body = deepcopy(signed_envelope(signed)); change(body)
    http, state = projection; state.update(body=body, status=200)
    result = http.get("/api/finance/signed-prices/BTC")
    assert result.status_code == 503 and "result" not in result.json()


def test_symbol_replay_and_query_injection_are_denied(signed, projection):
    http, state = projection; state.update(body=signed_envelope(signed), status=200)
    assert http.get("/api/finance/signed-prices/ETH").status_code == 503
    for suffix in ("BTC?url=https://example.com", "BTC?origin=fixture", "DOGE"):
        assert http.get("/api/finance/signed-prices/" + suffix).status_code in (404, 422)


def test_stateless_synthetic_model_and_existing_page(projection, monkeypatch):
    monkeypatch.setattr(routes.CLIENT, "environ", ENV)
    app = FastAPI(); routes.register(app)
    body = TestClient(app).get(routes.PREFIX + "/signed-prices/model").json()
    result = body["result"]["cases"]["correlated_venue_cluster"]
    assert result["venue_median_usd"] == "1000"
    assert result["reference_price_usd"] == "100.5"
    http, state = projection; state.update(body=body, status=200)
    assert http.get("/api/finance/signed-prices/model").json() == body
    assert http.get("/signed-prices").status_code == 200


@pytest.mark.parametrize("reply", [httpx.Response(302, headers={"location":"https://example.com"}),
    httpx.Response(200, text="<html>private</html>"),
    httpx.Response(200, content=b'{"a":1,"a":2}', headers={"content-type":"application/json"}),
    httpx.Response(200, content=b'{"n":1e999}', headers={"content-type":"application/json"}),
    httpx.Response(200, content=b' ' * 70000, headers={"content-type":"application/json"})])
def test_upstream_errors_never_leak_or_return_price(reply, monkeypatch):
    client = prices.SignedPriceClient(httpx.MockTransport(lambda _: reply))
    monkeypatch.setattr(prices, "CLIENT", client); monkeypatch.setattr(routes.CLIENT, "environ", ENV)
    app = FastAPI(); routes.register(app)
    response = TestClient(app).get(routes.PREFIX + "/signed-prices/BTC")
    assert response.status_code == 503 and response.json()["error"] == "SIGNED_PRICE_SOURCE_UNAVAILABLE"
    assert "private" not in response.text and "result" not in response.json()


def test_unbound_runtime_never_fetches(monkeypatch):
    monkeypatch.setattr(routes.CLIENT, "environ", {})
    monkeypatch.setattr(prices.CLIENT, "observe", lambda *_: pytest.fail("unbound provider fetch"))
    app = FastAPI(); routes.register(app)
    assert TestClient(app).get(routes.PREFIX + "/signed-prices/BTC").status_code == 503
