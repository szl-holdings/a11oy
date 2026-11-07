#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Configured origin admission rejects before the handler. Unconfigured does not pretend."""

import base64
import hashlib
import json
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.testclient import TestClient

import a11oy_x402_admission as admission
import serve
import szl_trust_x402_payment_context as trust_x402

NOW = 1_700_000_000
BASE = "https://pay.example"
AMOUNT = "50000"
PATH = "/v1/acoustic/burgers"
PIN = "c5d22596c582e2e93b21c40496969f39da3c725a267c3064881941f9a1e07ade"


def test_validator_copy_matches_the_trust_pin_and_bounds():
    raw = Path(trust_x402.__file__).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PIN
    assert admission.MIN_ATOMIC == trust_x402.MIN_ATOMIC
    assert admission.MAX_ATOMIC == trust_x402.MAX_ATOMIC
    assert trust_x402.production_charging_enabled() is False


def _jwks(public):
    raw = public.public_bytes_raw()
    return {"keys": [{
        "kty": "OKP", "crv": "Ed25519", "kid": "fixture",
        "x": base64.urlsafe_b64encode(raw).decode().rstrip("="),
        "alg": "EdDSA", "use": "sig",
    }]}


def _token(private, *, amount=AMOUNT, scheme="exact", aud=BASE + PATH,
           exp=NOW + 60, nbf=NOW, alg="EdDSA", kid="fixture"):
    claims = {"iat": NOW, "nbf": nbf, "exp": exp, "aud": aud, "scheme": scheme, "amount": amount}
    headers = {"kid": kid} if kid else None
    return jwt.encode(claims, private, algorithm=alg, headers=headers)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("A11OY_X402_PUBLIC_BASE", raising=False)
    monkeypatch.delenv("A11OY_X402_SCHEME", raising=False)
    monkeypatch.delenv("A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC", raising=False)
    monkeypatch.delenv("A11OY_X402_DATA_AMOUNT_ATOMIC", raising=False)
    monkeypatch.delenv("A11OY_X402_EXPERIMENTAL_AMOUNT_ATOMIC", raising=False)
    monkeypatch.delenv("A11OY_X402_LEEWAY_SECONDS", raising=False)
    serve.app.state.x402_now = lambda: NOW
    private = Ed25519PrivateKey.generate()
    serve.app.state.x402_keys = trust_x402.StaticKeySet(_jwks(private.public_key()))
    calls = {"burgers": 0}
    real = serve._acoustic_burgers_check

    def counted():
        calls["burgers"] += 1
        return real()

    monkeypatch.setattr(serve, "_acoustic_burgers_check", counted)
    with TestClient(serve.app) as test_client:
        yield test_client, private, calls


def _configure(monkeypatch):
    monkeypatch.setenv("A11OY_X402_PUBLIC_BASE", BASE)
    monkeypatch.setenv("A11OY_X402_SCHEME", "exact")
    monkeypatch.setenv("A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC", AMOUNT)


def test_unconfigured_ignores_spoofed_headers_and_mints_nothing(client):
    test_client, _private, calls = client
    response = test_client.get(PATH, headers={
        "x-payment-verified": "true",
        "payment-signature": "not-a-payment",
        "x-forwarded-host": "attacker.example",
        "host": "attacker.example",
    })
    assert response.status_code == 200
    assert calls["burgers"] == 1
    assert response.json()["label"] == "MEASURED"
    assert "receipt" not in response.json()
    assert response.headers["x-a11oy-payment-enforcement"] == "unconfigured"
    assert response.headers["x-a11oy-settlement-evidence"] == "false"
    assert "payment-settlement" not in response.headers


def test_partial_configuration_rejects_before_the_handler(client, monkeypatch):
    test_client, _private, calls = client
    monkeypatch.setenv("A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC", AMOUNT)
    response = test_client.get(PATH)
    assert response.status_code == 503
    assert response.json()["reason"] == "CONFIGURATION_INCOMPLETE"
    assert calls["burgers"] == 0


@pytest.mark.parametrize("mutate", ["absent", "alg", "key", "expired", "early",
                                    "audience", "scheme", "amount"])
def test_bad_contexts_reject_before_burgers(client, monkeypatch, mutate):
    test_client, private, calls = client
    _configure(monkeypatch)
    headers = {"x-forwarded-host": "attacker.example", "x-payment-verified": "true"}
    if mutate == "alg":
        headers["payment-context"] = (
            "eyJhbGciOiJIUzI1NiIsImtpZCI6ImZpeHR1cmUifQ.eyJhdWQiOiJ4In0.sig")
    elif mutate != "absent":
        other = Ed25519PrivateKey.generate()
        signer = other if mutate == "key" else private
        headers["payment-context"] = _token(
            signer,
            exp=NOW - 60 if mutate == "expired" else NOW + 60,
            nbf=NOW + 120 if mutate == "early" else NOW,
            aud="https://attacker.example/v1/acoustic/burgers" if mutate == "audience" else BASE + PATH,
            scheme="upto" if mutate == "scheme" else "exact",
            amount="1000" if mutate == "amount" else AMOUNT,
        )
    response = test_client.get(PATH, headers=headers)
    assert response.status_code == 403
    assert response.json()["settlement_evidence"] is False
    assert calls["burgers"] == 0
    assert "payment-settlement" not in response.headers


def test_valid_context_reaches_burgers_without_a_settlement_receipt(client, monkeypatch):
    test_client, private, calls = client
    _configure(monkeypatch)
    response = test_client.get(PATH, headers={
        "payment-context": _token(private),
        "host": "attacker.example",
        "x-forwarded-host": "attacker.example",
        "x-payment-verified": "true",
    })
    body = response.json()
    assert response.status_code == 200
    assert calls["burgers"] == 1
    assert body["result"]["refinement_holds"] is True
    assert "receipt" not in body and "signature" not in body
    assert response.headers["x-a11oy-payment-enforcement"] == "context-verified"
    assert response.headers["x-a11oy-settlement-evidence"] == "false"
    assert "payment-settlement" not in response.headers
    assert "payment-response" not in response.headers


def test_upto_verification_still_emits_no_settlement(client, monkeypatch):
    test_client, private, calls = client
    _configure(monkeypatch)
    monkeypatch.setenv("A11OY_X402_SCHEME", "upto")
    response = test_client.get(PATH, headers={"payment-context": _token(private, scheme="upto")})
    assert response.status_code == 200
    assert calls["burgers"] == 1
    assert "payment-settlement" not in response.headers


def test_one_configured_family_does_not_gate_another(client, monkeypatch):
    test_client, _private, _calls = client
    _configure(monkeypatch)
    response = test_client.get("/v1/data/")
    assert response.status_code == 200
    assert response.headers["x-a11oy-payment-enforcement"] == "unconfigured"


def test_health_stays_outside_the_payment_gate(client, monkeypatch):
    test_client, _private, _calls = client
    _configure(monkeypatch)
    response = test_client.get("/healthz", headers={
        "payment-context": "not-a-token",
        "x-payment-verified": "true",
        "x-forwarded-host": "attacker.example",
    })
    assert response.status_code != 403
    assert "x-a11oy-payment-enforcement" not in response.headers


def test_two_contexts_are_ambiguous_before_the_handler():
    class Headers:
        def getlist(self, name):
            assert name == "payment-context"
            return ["one", "two"]

    class Url:
        path = PATH

    class State:
        x402_keys = None
        x402_now = lambda: NOW

    class App:
        state = State()

    class Request:
        method = "GET"
        url = Url()
        headers = Headers()
        app = App()

    import os
    os.environ["A11OY_X402_PUBLIC_BASE"] = BASE
    os.environ["A11OY_X402_SCHEME"] = "exact"
    os.environ["A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC"] = AMOUNT
    try:
        outcome = admission.evaluate(Request())
    finally:
        os.environ.pop("A11OY_X402_PUBLIC_BASE")
        os.environ.pop("A11OY_X402_SCHEME")
        os.environ.pop("A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC")
    assert outcome.status == 403 and outcome.reason == "AMBIGUOUS_CONTEXT"
