#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Configured origin admission rejects before the handler. Unconfigured does not pretend."""

import asyncio
import base64
import email.utils
import hashlib
import json
import time
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


def test_upto_authorization_does_not_run_the_handler(client, monkeypatch):
    test_client, private, calls = client
    _configure(monkeypatch)
    monkeypatch.setenv("A11OY_X402_SCHEME", "upto")
    underfunded = test_client.get(PATH, headers={
        "payment-context": _token(private, amount="1000", scheme="upto")})
    covered = test_client.get(PATH, headers={
        "payment-context": _token(private, amount="100000", scheme="upto")})
    assert underfunded.status_code == 503
    assert underfunded.json()["reason"] == "UPTO_NOT_SUPPORTED"
    assert covered.status_code == 503
    assert calls["burgers"] == 0
    assert "payment-settlement" not in underfunded.headers
    assert "payment-settlement" not in covered.headers


def test_head_does_not_run_the_paid_handler(client, monkeypatch):
    test_client, private, calls = client
    _configure(monkeypatch)
    response = test_client.head(PATH, headers={"payment-context": _token(private)})
    assert response.status_code == 405
    assert response.headers["x-a11oy-payment-enforcement"] == "rejected"
    assert calls["burgers"] == 0
    assert "payment-settlement" not in response.headers


def test_case_and_slash_variants_do_not_serve_the_paid_body(client, monkeypatch):
    test_client, private, calls = client
    _configure(monkeypatch)
    token = _token(private)
    for variant in ("/v1/acoustic/Burgers", "/v1/acoustic/burgers/", "/V1/acoustic/burgers"):
        response = test_client.get(variant, headers={"payment-context": token}, follow_redirects=False)
        assert "szl.acoustic.burgers/v1" not in response.text
    assert calls["burgers"] == 0


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


def _resolver_response(private):
    body = json.dumps(_jwks(private.public_key())).encode("utf-8")
    return trust_x402.KeyFetchResponse(
        status=200,
        headers={
            "content-type": "application/json",
            "cache-control": "max-age=120",
            "age": "0",
            "date": email.utils.formatdate(time.time(), usegmt=True),
        },
        body=body,
        url=trust_x402.PINNED_JWKS_URL,
        redirected=False,
    )


def test_shared_key_resolution_fails_closed_without_blocking_health(monkeypatch):
    import httpx

    calls = {"fetch": 0, "burgers": 0}
    real = serve._acoustic_burgers_check

    def counted():
        calls["burgers"] += 1
        return real()

    def fetch(url, *, timeout, max_bytes):
        assert url == trust_x402.PINNED_JWKS_URL
        calls["fetch"] += 1
        time.sleep(0.8)
        raise trust_x402.PaymentHold("KEYS_UNAVAILABLE", "PAYMENT_KEYS_FETCH_FAILED")

    monkeypatch.setattr(serve, "_acoustic_burgers_check", counted)
    _configure(monkeypatch)
    previous = getattr(serve.app.state, "x402_keys", None)
    serve.app.state.x402_keys = None
    monkeypatch.setattr(admission, "_SHARED_RESOLVER", trust_x402.PaymentKeyResolver(fetch=fetch))
    headers = {"payment-context": _token(Ed25519PrivateKey.generate())}

    async def scenario():
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/healthz")
            started = time.monotonic()

            async def health():
                mark = time.monotonic()
                response = await client.get("/healthz")
                return response.status_code, time.monotonic() - mark

            paid_a = asyncio.create_task(client.get(PATH, headers=headers))
            paid_b = asyncio.create_task(client.get(PATH, headers=headers))
            await asyncio.sleep(0.05)
            health_status, health_elapsed = await health()
            first, second = await asyncio.gather(paid_a, paid_b)
            return health_status, health_elapsed, first.status_code, second.status_code, time.monotonic() - started

    try:
        health_status, health_elapsed, first, second, total = asyncio.run(scenario())
    finally:
        serve.app.state.x402_keys = previous
    assert calls["fetch"] == 1
    assert first == 503 and second == 503
    assert calls["burgers"] == 0
    assert health_status != 403
    assert health_elapsed < 0.4
    assert total >= 0.8


def test_health_stays_responsive_when_the_default_executor_is_saturated(monkeypatch):
    """Two key waits must not occupy the process default executor."""
    import httpx
    from concurrent.futures import ThreadPoolExecutor

    calls = {"fetch": 0}
    def fetch(url, *, timeout, max_bytes):
        assert url == trust_x402.PINNED_JWKS_URL
        calls["fetch"] += 1
        time.sleep(0.8)
        raise trust_x402.PaymentHold("KEYS_UNAVAILABLE", "PAYMENT_KEYS_FETCH_FAILED")

    _configure(monkeypatch)
    previous = getattr(serve.app.state, "x402_keys", None)
    serve.app.state.x402_keys = None
    monkeypatch.setattr(admission, "_SHARED_RESOLVER", trust_x402.PaymentKeyResolver(fetch=fetch))
    headers = {"payment-context": _token(Ed25519PrivateKey.generate())}

    async def scenario():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=2))
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/healthz")
            paid_a = asyncio.create_task(client.get(PATH, headers=headers))
            paid_b = asyncio.create_task(client.get(PATH, headers=headers))
            await asyncio.sleep(0.05)
            mark = time.monotonic()
            health = await client.get("/healthz")
            elapsed = time.monotonic() - mark
            first, second = await asyncio.gather(paid_a, paid_b)
            return health.status_code, elapsed, first.status_code, second.status_code

    try:
        health_status, elapsed, first, second = asyncio.run(scenario())
    finally:
        serve.app.state.x402_keys = previous
    assert calls["fetch"] == 1
    assert first == 503 and second == 503
    assert health_status == 200
    assert elapsed < 0.5


def test_verification_queue_fails_closed_when_full():
    import threading
    release = threading.Event()

    def block():
        release.wait(timeout=5)
        return "done"

    futures = []
    try:
        for _ in range(admission._VERIFY_WORKERS + admission._VERIFY_QUEUE):
            future = admission.submit_verification(block)
            assert future is not None
            futures.append(future)
        assert admission.submit_verification(block) is None
    finally:
        release.set()
        for future in futures:
            future.result(timeout=5)


def test_shared_key_resolution_reuses_a_fresh_set(monkeypatch):
    import httpx

    private = Ed25519PrivateKey.generate()
    calls = {"fetch": 0, "burgers": 0}
    real = serve._acoustic_burgers_check

    def counted():
        calls["burgers"] += 1
        return real()

    def fetch(url, *, timeout, max_bytes):
        assert url == trust_x402.PINNED_JWKS_URL
        calls["fetch"] += 1
        return _resolver_response(private)

    monkeypatch.setattr(serve, "_acoustic_burgers_check", counted)
    _configure(monkeypatch)
    previous_keys = getattr(serve.app.state, "x402_keys", None)
    previous_now = getattr(serve.app.state, "x402_now", None)
    serve.app.state.x402_keys = None
    serve.app.state.x402_now = lambda: NOW
    monkeypatch.setattr(admission, "_SHARED_RESOLVER", trust_x402.PaymentKeyResolver(fetch=fetch))
    headers = {"payment-context": _token(private)}

    async def scenario():
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get(PATH, headers=headers)
            second = await client.get(PATH, headers=headers)
            return first.status_code, second.status_code

    try:
        first, second = asyncio.run(scenario())
    finally:
        serve.app.state.x402_keys = previous_keys
        serve.app.state.x402_now = previous_now
    assert calls["fetch"] == 1
    assert first == 200 and second == 200
    assert calls["burgers"] == 2


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
        outcome = admission.classify(Request())
    finally:
        os.environ.pop("A11OY_X402_PUBLIC_BASE")
        os.environ.pop("A11OY_X402_SCHEME")
        os.environ.pop("A11OY_X402_ACOUSTIC_AMOUNT_ATOMIC")
    assert outcome.status == 403 and outcome.reason == "AMBIGUOUS_CONTEXT"
