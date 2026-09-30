# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for state-changing runtime transport boundaries."""
from __future__ import annotations

import asyncio
import json
import threading

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import serve
import szl_agentic_loop as runtime_loop
import szl_immune as immune


_TOKEN = "test-main-runtime-token"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}


def _registry(scopes: list[str]) -> str:
    return json.dumps({
        "version": 1,
        "credentials": [{
            "owner_id": "operator:test",
            "namespace": "a11oy",
            "key_id": "main-runtime-test-key",
            "token": _TOKEN,
            "scopes": scopes,
            "revoked": False,
        }],
    })


@pytest.fixture(autouse=True)
def _operator_state(monkeypatch):
    monkeypatch.setenv(
        "A11OY_OPERATOR_CREDENTIALS_JSON",
        _registry(["agent:cycle", "ouroboros:run", "immune:lorenz"]),
    )
    monkeypatch.setenv("A11OY_OPERATOR_NAMESPACE", "a11oy")
    monkeypatch.setenv("A11OY_OPERATOR_MIN_INTERVAL_SEC", "0")
    monkeypatch.delenv("A11OY_OPERATOR_PRINCIPALS_JSON", raising=False)
    with runtime_loop._OPERATOR_ACTION_LOCK:
        runtime_loop._OPERATOR_ACTION_PENDING.clear()
        runtime_loop._OPERATOR_ACTION_LAST.clear()
    yield
    with runtime_loop._OPERATOR_ACTION_LOCK:
        runtime_loop._OPERATOR_ACTION_PENDING.clear()
        runtime_loop._OPERATOR_ACTION_LAST.clear()


def _loop_app() -> FastAPI:
    app = FastAPI()
    runtime_loop.register(
        app,
        ns="a11oy",
        sign_fn=lambda payload: {
            "payloadType": "application/json",
            "payload": payload,
            "signatures": [],
            "signed": False,
            "honesty": "test structural envelope",
        },
    )
    return app


def test_mcp_notification_is_an_empty_202_and_requests_still_reply() -> None:
    with TestClient(_loop_app()) as client:
        notification = client.post("/mcp/", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        request = client.post("/mcp/", json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "ping",
        })

    assert notification.status_code == 202
    assert notification.content == b""
    assert request.status_code == 200
    assert request.json() == {"jsonrpc": "2.0", "id": 7, "result": {}}


def test_agent_cycle_requires_strict_opt_in_and_operator_capability(monkeypatch) -> None:
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    with TestClient(_loop_app()) as client:
        string_false = client.post(
            "/api/a11oy/v1/agent/cycle", json={"loop": "false"}
        )
        unauthenticated = client.post(
            "/api/a11oy/v1/agent/cycle", json={"loop": True}
        )

    assert string_false.status_code == 200
    assert string_false.json()["cycle"] is False
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"] == "missing_authorization"


def test_agent_cycle_rejects_a_valid_token_without_the_cycle_scope(monkeypatch) -> None:
    monkeypatch.setenv("A11OY_OUROBOROS", "1")
    monkeypatch.setenv("A11OY_OPERATOR_CREDENTIALS_JSON", _registry(["immune:lorenz"]))
    with TestClient(_loop_app()) as client:
        response = client.post(
            "/api/a11oy/v1/agent/cycle",
            json={"loop": True},
            headers=_HEADERS,
        )
    assert response.status_code == 403
    assert response.json()["error"] == "missing_scopes"


def test_ouroboros_status_does_not_disclose_an_absolute_runner_path() -> None:
    response = asyncio.run(serve.ouroboros_status())
    payload = json.loads(response.body)
    assert response.status_code == 200
    assert "runner_path" not in payload
    assert payload["runner_id"] in {None, "OUROBOROS_RUN_ALL.py"}


def test_ouroboros_run_requires_deployment_enablement_and_authentication(monkeypatch) -> None:
    async def post() -> httpx.Response:
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/a11oy/v1/ouroboros/run-all")

    monkeypatch.delenv("A11OY_OUROBOROS_RUN_ALL", raising=False)
    disabled = asyncio.run(post())
    assert disabled.status_code == 503
    assert "disabled by deployment policy" in disabled.json()["error"]

    monkeypatch.setenv("A11OY_OUROBOROS_RUN_ALL", "1")
    unauthenticated = asyncio.run(post())
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"] == "missing_authorization"


def test_ouroboros_run_is_authorized_single_flight_and_off_loop(monkeypatch) -> None:
    monkeypatch.setenv("A11OY_OUROBOROS_RUN_ALL", "1")
    started = threading.Event()
    release = threading.Event()

    def blocked_run() -> dict:
        started.set()
        if not release.wait(3.0):
            raise TimeoutError("test release deadline exhausted")
        return {"verdict": "BLOCKED", "tests_run": 0}

    monkeypatch.setattr(serve, "_ouroboros_run_all_sync", blocked_run)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = asyncio.create_task(client.post(
                "/api/a11oy/v1/ouroboros/run-all", headers=_HEADERS
            ))
            assert await asyncio.to_thread(started.wait, 1.5)
            health = await client.get("/api/a11oy/healthz")
            second = await client.post(
                "/api/a11oy/v1/ouroboros/run-all", headers=_HEADERS
            )
            assert health.status_code == 200
            assert not first.done(), "blocking suite starved or completed on the event loop"
            assert second.status_code == 429
            release.set()
            assert (await first).status_code == 200

    try:
        asyncio.run(exercise())
    finally:
        release.set()


def test_lorenz_get_and_head_are_side_effect_free(monkeypatch) -> None:
    calls = {"n": 0}

    def forbidden_action() -> dict:
        calls["n"] += 1
        raise AssertionError("safe method executed Lorenz")

    monkeypatch.setattr(immune, "_nexus_lorenz", forbidden_action)

    async def exercise():
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return (
                await client.get("/api/a11oy/v1/immune/nexus/lorenz"),
                await client.head("/api/a11oy/v1/immune/nexus/lorenz"),
            )

    get_response, head_response = asyncio.run(exercise())

    assert get_response.status_code == 200
    assert get_response.json()["state"] == "POST_ONLY"
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert calls["n"] == 0


def test_lorenz_post_is_authorized_and_single_flight(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocked_action() -> dict:
        started.set()
        if not release.wait(3.0):
            raise TimeoutError("test release deadline exhausted")
        return {
            "ok": False,
            "sealed": False,
            "reachability": "UNAVAILABLE",
            "error": "test unverified receipt",
        }

    monkeypatch.setattr(immune, "_nexus_lorenz", blocked_action)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=serve.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            denied = await client.post("/api/a11oy/v1/immune/nexus/lorenz")
            assert denied.status_code == 401

            first = asyncio.create_task(client.post(
                "/api/a11oy/v1/immune/nexus/lorenz", headers=_HEADERS
            ))
            assert await asyncio.to_thread(started.wait, 1.5)
            second = await client.post(
                "/api/a11oy/v1/immune/nexus/lorenz", headers=_HEADERS
            )
            assert second.status_code == 429
            release.set()
            result = await first
            assert result.status_code == 503
            assert result.json()["sealed"] is False

    try:
        asyncio.run(exercise())
    finally:
        release.set()
