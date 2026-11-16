#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Isolated fixture contracts, not a deployed five-service or collector receipt."""
import asyncio
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_build_env_fanout as fanout

INCOMING = "00-" + "1" * 32 + "-" + "2" * 16 + "-01"
CURRENT = "00-" + "1" * 32 + "-" + "3" * 16 + "-01"
ECHO = "00-" + "1" * 32 + "-" + "4" * 16 + "-01"
QUERY = "/route?fanout=sentra,amaru,killinchu,rosie"
ORIGINAL_CLIENT = httpx.AsyncClient


def peer_response(status=200, data=b'{"status":"fixture"}', headers=None):
    values = {"content-type": "application/json", "traceparent": ECHO}
    values.update(headers or {})
    return httpx.Response(status, headers=values, stream=httpx.ByteStream(data))


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setenv("A11OY_BUILD_ENV_FANOUT", "1")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "a11oy")
    app = FastAPI()
    app._vsp_otel_installed = True
    app._vsp_otel_service = "a11oy"
    app._vsp_otel_exporter = "otlp-grpc:configured:fixture-only"
    state = SimpleNamespace(app=app, calls=[], client_options=[], continuing=CURRENT,
                            exporter="otlp-grpc:configured:fixture-only", handler=None)

    @app.middleware("http")
    async def fixture_context(request, call_next):
        request.state.traceparent = state.continuing
        request.state.vsp_otel_exporter = state.exporter
        return await call_next(request)

    fanout.register(app)

    async def dispatch(request):
        state.calls.append(request)
        return await state.handler(request) if state.handler else peer_response()

    def client_factory(**kwargs):
        state.client_options.append(kwargs)
        return ORIGINAL_CLIENT(transport=httpx.MockTransport(dispatch), **kwargs)

    monkeypatch.setattr(fanout.httpx, "AsyncClient", client_factory)
    with TestClient(app) as client:
        state.client = client
        yield state


def get(rig, path=QUERY, headers=None):
    return rig.client.get(path, headers={"traceparent": INCOMING} if headers is None else headers,
                          follow_redirects=False)


def test_exact_acknowledgement_and_fixed_network_contract(rig):
    result = get(rig, headers={"traceparent": INCOMING, "authorization": "Bearer private-fixture",
                              "cookie": "private=fixture", "baggage": "private=value",
                              "tracestate": "private=value", "host": "attacker.invalid"})
    assert result.status_code == 200
    assert result.json() == {"schema": fanout.SCHEMA, "accepted": True,
                             "traceparent": INCOMING, "fanout": list(fanout.FANOUT)}
    assert result.headers["cache-control"] == "private, no-store"
    assert result.headers["x-szl-collector-delivery"] == "unverified"
    assert result.headers["x-szl-execution-authority"] == "none"
    assert sorted(str(r.url) for r in rig.calls) == sorted(url for _, url in fanout.TARGETS)
    assert len(rig.calls) == 4
    for request in rig.calls:
        assert request.method == "GET" and request.content == b""
        assert request.headers["traceparent"] == CURRENT
        assert request.headers["accept-encoding"] == "identity"
        for private in ("authorization", "cookie", "baggage", "tracestate", "x-forwarded-host"):
            assert private not in request.headers
        assert request.url.host != "attacker.invalid"
    for options in rig.client_options:
        assert options["trust_env"] is False
        assert options["follow_redirects"] is False
        assert options["limits"].max_connections == len(fanout.TARGETS)


@pytest.mark.parametrize("value", [None, "", "0", "true", "yes", " 1"])
def test_disabled_unless_exact_opt_in(rig, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("A11OY_BUILD_ENV_FANOUT")
    else:
        monkeypatch.setenv("A11OY_BUILD_ENV_FANOUT", value)
    response = get(rig)
    assert response.status_code == 503 and response.json()["reason"] == "FANOUT_DISABLED"
    assert not rig.calls and not rig.client_options


@pytest.mark.parametrize("fault", ["service", "installed", "exporter", "state_exporter", "same_span", "other_trace", "unsampled", "missing"])
def test_missing_native_trace_context_cannot_call_peers(rig, monkeypatch, fault):
    if fault == "service": monkeypatch.setenv("OTEL_SERVICE_NAME", "other")
    elif fault == "installed": rig.app._vsp_otel_installed = False
    elif fault == "exporter": rig.app._vsp_otel_exporter = "in-process-only"
    elif fault == "state_exporter": rig.exporter = "in-process-only"
    elif fault == "same_span": rig.continuing = INCOMING
    elif fault == "other_trace": rig.continuing = CURRENT.replace("1" * 32, "8" * 32)
    elif fault == "unsampled": rig.continuing = CURRENT[:-2] + "00"
    else: rig.continuing = None
    response = get(rig)
    assert response.status_code == 503 and response.json()["accepted"] is False
    assert not rig.calls and not rig.client_options


@pytest.mark.parametrize("path", ["/route", "/route?fanout=sentra", QUERY + "&url=http://169.254.169.254/",
    QUERY + "&fanout=sentra,amaru,killinchu,rosie", "/route?fanout=rosie,amaru,killinchu,sentra",
    "/route?fanout=sentra%2Camaru%2Ckillinchu%2Crosie", "/route?fanout=http://127.0.0.1/"])
def test_request_cannot_choose_targets_or_reorder_scope(rig, path):
    response = get(rig, path)
    assert response.status_code == 400 and response.json()["reason"] == "EXACT_FANOUT_REQUIRED"
    assert not rig.calls


@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_non_get_methods_have_no_peer_effect(rig, method):
    response = rig.client.request(method, QUERY, headers={"traceparent": INCOMING})
    assert response.status_code == 405 and response.headers["allow"] == "GET"
    assert not rig.calls


@pytest.mark.parametrize("headers", [{}, {"traceparent": "invalid"}, {"traceparent": INCOMING[:-2] + "00"},
    {"traceparent": INCOMING.replace("1" * 32, "0" * 32)},
    {"traceparent": INCOMING.replace("2" * 16, "0" * 16)},
    {"traceparent": " " + INCOMING}, [("traceparent", INCOMING), ("traceparent", INCOMING)]])
def test_absent_invalid_or_duplicate_traceparent_never_calls_network(rig, headers):
    response = get(rig, headers=headers)
    assert response.status_code == 400
    assert response.json()["reason"] == "TRACEPARENT_REQUIRED"
    assert not rig.calls


@pytest.mark.parametrize("status", [201, 301, 302, 307, 401, 403, 429, 500, 503])
def test_any_peer_non_200_prevents_acceptance_without_retry(rig, status):
    async def handler(request):
        return peer_response(status if request.url.host.startswith("amaru.") else 200,
                             headers={"location": "http://169.254.169.254/private"})
    rig.handler = handler
    response = get(rig)
    assert response.status_code == 503 and response.json()["reason"] == "PEER_STATUS_UNAVAILABLE"
    assert len(rig.calls) == 4
    assert not any(r.url.host == "169.254.169.254" for r in rig.calls)


@pytest.mark.parametrize("data,headers,reason", [
    (b'<html>private-fixture</html>', {"content-type": "text/html"}, "PEER_JSON_REQUIRED"),
    (b'{"value":1,"value":2}', {}, "PEER_JSON_REQUIRED"),
    (b'{"value":NaN}', {}, "PEER_JSON_REQUIRED"),
    (b'[]', {}, "PEER_JSON_REQUIRED"), (b'{}', {}, "PEER_JSON_REQUIRED"),
    (b'', {}, "PEER_JSON_REQUIRED"), (b'\xff', {}, "PEER_JSON_REQUIRED"),
    (b'{"ok":true}', {"content-encoding": "gzip"}, "PEER_JSON_REQUIRED"),
    (b'x' * (fanout.MAX_RESPONSE_BYTES + 1), {}, "PEER_BODY_LIMIT"),
    (b'{"ok":true}', {"content-length": "999999999999999"}, "PEER_BODY_LIMIT"),
    (b'{"ok":true}', {"content-length": "0"}, "PEER_BODY_LIMIT"),
    (b'{"ok":true}', {"content-length": "1, 11"}, "PEER_BODY_LIMIT"),
    (b'{"ok":true}', {"content-length": "12"}, "PEER_BODY_LIMIT"),
    (b'{"ok":true}', {"traceparent": "invalid"}, "PEER_TRACE_UNAVAILABLE"),
    (b'{"ok":true}', {"traceparent": CURRENT}, "PEER_TRACE_UNAVAILABLE"),
    (b'{"ok":true}', {"traceparent": ECHO[:-2] + "00"}, "PEER_TRACE_UNAVAILABLE"),
    (b'{"ok":true}', {"traceparent": ECHO.replace("1" * 32, "9" * 32)}, "PEER_TRACE_UNAVAILABLE"),
])
def test_peer_body_and_trace_fail_closed(rig, data, headers, reason):
    async def handler(_request): return peer_response(data=data, headers=headers)
    rig.handler = handler
    response = get(rig)
    assert response.status_code == 503 and response.json()["reason"] == reason
    assert "private-fixture" not in response.text
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("exception,reason", [(httpx.ConnectError("private-fixture"), "PEER_UNAVAILABLE"),
    (httpx.ReadTimeout("private-fixture"), "PEER_TIMEOUT"), (RuntimeError("private-fixture"), "PEER_UNAVAILABLE")])
def test_transport_errors_do_not_leak_or_retry(rig, exception, reason):
    async def handler(_request): raise exception
    rig.handler = handler
    response = get(rig)
    assert response.status_code == 503 and response.json()["reason"] == reason
    assert len(rig.calls) == 4 and "private-fixture" not in response.text


def test_peer_cookies_cannot_cross_target_boundaries(rig):
    async def handler(_request):
        return peer_response(headers={"set-cookie": "secret=fixture; Domain=.szl.svc; Path=/"})
    rig.handler = handler
    assert get(rig).status_code == 200
    assert all("cookie" not in request.headers for request in rig.calls)


def test_saturation_is_bounded_and_slots_recover(rig):
    async def scenario():
        release, started = asyncio.Event(), asyncio.Event()
        count = 0
        async def handler(_request):
            nonlocal count
            count += 1
            if count == 8: started.set()
            await release.wait()
            return peer_response()
        rig.handler = handler
        async with ORIGINAL_CLIENT(transport=httpx.ASGITransport(app=rig.app), base_url="http://test") as client:
            first = asyncio.create_task(client.get(QUERY, headers={"traceparent": INCOMING}))
            second = asyncio.create_task(client.get(QUERY, headers={"traceparent": INCOMING}))
            await asyncio.wait_for(started.wait(), 2)
            third = await client.get(QUERY, headers={"traceparent": INCOMING})
            assert third.status_code == 429 and count == 8
            release.set()
            assert all(r.status_code == 200 for r in await asyncio.gather(first, second))
            fourth = await client.get(QUERY, headers={"traceparent": INCOMING})
            assert fourth.status_code == 200
    asyncio.run(scenario())


def test_deadline_cancels_outstanding_reads_and_releases_capacity(rig, monkeypatch):
    monkeypatch.setattr(fanout, "TOTAL_TIMEOUT_SECONDS", 0.04)
    cancelled = []
    async def handler(_request):
        try: await asyncio.sleep(2)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return peer_response()
    rig.handler = handler
    response = get(rig)
    assert response.status_code == 504 and response.json()["reason"] == "FANOUT_DEADLINE"
    assert len(cancelled) == 4
    rig.handler = None
    assert get(rig).status_code == 200


def test_registration_is_idempotent(rig):
    fanout.register(rig.app)
    assert sum(getattr(r, "path", None) == "/route" for r in rig.app.routes) == 1


def test_runtime_registration_and_container_copy_are_present():
    root = Path(__file__).resolve().parents[1]
    source = (root / "serve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    registrations = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == "register"
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == "_a11oy_build_env_fanout"]
    assert len(registrations) == 1
    catchalls = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
                and n.args[0].value.startswith("/{") and n.args[0].value.endswith(":path}")]
    assert catchalls and registrations[0].lineno < min(catchalls)
    copies = [line for line in (root / "Dockerfile").read_text().splitlines() if line.startswith("COPY ")]
    assert any("a11oy_build_env_fanout.py" in line.split()[1:-1] for line in copies)
