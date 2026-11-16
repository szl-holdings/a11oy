#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline ASGI payment-boundary tests; fixture keys have no production authority."""
import hashlib
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import a11oy_x402_admission as admission
import szl_trust_x402_payment_context as trust

PATH = "/v1/acoustic/burgers"
NOW = 1_700_000_000
BASE = "https://paid.example"
PUBLIC_HEADERS = {
    "cache-control": "public, max-age=3600",
    "cdn-cache-control": "public, max-age=86400",
    "cloudflare-cdn-cache-control": "public, max-age=86400",
    "surrogate-control": "max-age=86400",
    "payment-settlement": "fixture-must-not-escape",
    "payment-response": "fixture-must-not-escape",
    "x-fixture-preserved": "yes",
}


@pytest.fixture
def client(monkeypatch):
    for key in ("PUBLIC_BASE", "SCHEME", "ACOUSTIC_AMOUNT_ATOMIC", "DATA_AMOUNT_ATOMIC",
                "EXPERIMENTAL_AMOUNT_ATOMIC", "LEEWAY_SECONDS"):
        monkeypatch.delenv("A11OY_X402_" + key, raising=False)
    private = Ed25519PrivateKey.generate()
    calls = []

    async def paid(_request):
        calls.append("paid")
        return JSONResponse({"fixture": True}, headers=PUBLIC_HEADERS)

    async def health(_request):
        return JSONResponse({"status": "fixture"}, headers={"cache-control": "public, max-age=60"})

    app = Starlette(routes=[Route(PATH, paid), Route("/healthz", health)])
    app.add_middleware(BaseHTTPMiddleware, dispatch=admission.payment_gate)
    app.state.x402_now = lambda: NOW
    app.state.x402_keys = {"fixture": private.public_key()}

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("offline contract test attempted JWKS network access")

    monkeypatch.setattr(trust, "fetch_pinned_jwks", forbidden_network)
    with TestClient(app) as c:
        yield c, private, calls


def configure(monkeypatch, amount="50000"):
    monkeypatch.setenv("A11OY_X402_PUBLIC_BASE", BASE)
    monkeypatch.setenv("A11OY_X402_SCHEME", "exact")
    monkeypatch.setenv("A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC", amount)


def token(private):
    return jwt.encode({"iat": NOW, "nbf": NOW, "exp": NOW + 60,
                       "aud": BASE + PATH, "scheme": "exact", "amount": "50000"},
                      private, algorithm="EdDSA", headers={"kid": "fixture"})


def assert_uncacheable(response):
    assert response.headers["cache-control"] == "private, no-store"
    for header in ("cdn-cache-control", "cloudflare-cdn-cache-control", "surrogate-control"):
        assert header not in response.headers
    for header in ("payment-settlement", "payment-response"):
        assert header not in response.headers
    assert response.headers["x-a11oy-settlement-evidence"] == "false"


def test_verified_paid_body_cannot_inherit_public_cache_directives(client, monkeypatch):
    c, private, calls = client
    configure(monkeypatch)
    response = c.get(PATH, headers={"payment-context": token(private)})
    assert response.status_code == 200
    assert response.json() == {"fixture": True}
    assert calls == ["paid"]
    assert response.headers["x-a11oy-payment-enforcement"] == "context-verified"
    assert response.headers["x-fixture-preserved"] == "yes"
    assert_uncacheable(response)


def test_unconfigured_paid_family_is_not_reused_after_future_activation(client):
    c, _private, calls = client
    response = c.get(PATH)
    assert response.status_code == 200
    assert calls == ["paid"]
    assert response.headers["x-a11oy-payment-enforcement"] == "unconfigured"
    assert_uncacheable(response)


@pytest.mark.parametrize("mode,status,reason", [
    ("absent", 403, "ABSENT"),
    ("malformed", 403, "MALFORMED_TOKEN"),
    ("incomplete", 503, "CONFIGURATION_INCOMPLETE"),
    ("head", 405, "METHOD_NOT_ALLOWED"),
    ("upto", 503, "UPTO_NOT_SUPPORTED"),
])
def test_rejections_are_noncacheable_without_handler_execution(client, monkeypatch, mode, status, reason):
    c, _private, calls = client
    configure(monkeypatch)
    headers = {}
    if mode == "malformed":
        headers["payment-context"] = "invalid-fixture"
    elif mode == "incomplete":
        monkeypatch.delenv("A11OY_X402_PUBLIC_BASE")
    elif mode == "upto":
        monkeypatch.setenv("A11OY_X402_SCHEME", "upto")
    response = c.request("HEAD" if mode == "head" else "GET", PATH, headers=headers)
    assert response.status_code == status
    if mode != "head":
        assert response.json()["reason"] == reason
    assert calls == []
    assert_uncacheable(response)


@pytest.mark.parametrize("amount", ["9" * 5000, "9" * 10000, "1" + "0" * 100, "100000001"])
def test_oversized_configured_amount_fails_closed_not_as_an_exception(client, monkeypatch, amount):
    c, _private, calls = client
    configure(monkeypatch, amount)
    response = c.get(PATH)
    assert response.status_code == 503
    assert response.json()["reason"] == "CONFIGURATION_INCOMPLETE"
    assert calls == []
    assert_uncacheable(response)


def test_free_health_route_retains_its_cache_policy_and_has_no_payment_labels(client, monkeypatch):
    c, _private, calls = client
    configure(monkeypatch)
    response = c.get("/healthz", headers={"payment-context": "invalid-fixture"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=60"
    assert "x-a11oy-payment-enforcement" not in response.headers
    assert calls == []


def test_pinned_estate_signature_validator_is_not_replaced():
    assert hashlib.sha256(Path(trust.__file__).read_bytes()).hexdigest() == (
        "c5d22596c582e2e93b21c40496969f39da3c725a267c3064881941f9a1e07ade")
