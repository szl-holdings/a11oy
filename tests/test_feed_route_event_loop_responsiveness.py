# SPDX-License-Identifier: Apache-2.0
"""Regression tests for non-blocking, bounded live-feed route execution."""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from typing import Any, Callable

import httpx
import pytest
from fastapi import FastAPI

import a11oy_deva_feeds as deva
import a11oy_devb_endpoints as devb
import a11oy_vertical_feeds as vertical
import szl_khipu as real_khipu


_GOVERN_TOKEN = "test-govern-token"
_GOVERN_HEADERS = {"Authorization": f"Bearer {_GOVERN_TOKEN}"}


@pytest.fixture(autouse=True)
def _configured_governance_operator(monkeypatch):
    monkeypatch.setenv("A11OY_GOVERN_CREDENTIALS_JSON", json.dumps({
        "version": 1,
        "credentials": [{
            "owner_id": "operator:test",
            "namespace": "a11oy",
            "key_id": "test-govern-key",
            "token": _GOVERN_TOKEN,
            "scopes": ["vertical:govern"],
            "revoked": False,
        }],
    }))
    monkeypatch.delenv("A11OY_GOVERN_PRINCIPALS_JSON", raising=False)
    monkeypatch.setenv("A11OY_GOVERN_NAMESPACE", "a11oy")
    monkeypatch.setenv("A11OY_GOVERN_MIN_INTERVAL_SEC", "1")
    vertical._GOVERN_AUTH_REGISTRY = None
    vertical._GOVERN_AUTH_FINGERPRINT = None
    with vertical._GOVERN_RATE_LOCK:
        vertical._GOVERN_LAST.clear()
        vertical._GOVERN_PENDING.clear()
    yield
    vertical._GOVERN_AUTH_REGISTRY = None
    vertical._GOVERN_AUTH_FINGERPRINT = None
    with vertical._GOVERN_RATE_LOCK:
        vertical._GOVERN_LAST.clear()
        vertical._GOVERN_PENDING.clear()


def _endpoint(app: FastAPI, path: str) -> Callable[..., Any]:
    for route in app.router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"route not registered: {path}")


def _payload(response: Any) -> dict[str, Any]:
    return json.loads(response.body)


class _BlockingFeed:
    """A synchronous upstream that only an external test gate can release."""

    def __init__(self, saturation: int = 1) -> None:
        self.release = threading.Event()
        self.started = threading.Event()
        self.saturated = threading.Event()
        self._saturation = saturation
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def __call__(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started.set()
            if self.active >= self._saturation:
                self.saturated.set()
        try:
            if not self.release.wait(3.0):
                raise TimeoutError("test upstream release deadline exhausted")
            return {
                "value": None,
                "freshness": {"status": "unavailable", "error": "test upstream blocked"},
            }
        finally:
            with self._lock:
                self.active -= 1


async def _wait_event(event: threading.Event, timeout: float = 1.5) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if event.is_set():
            return True
        await asyncio.sleep(0.005)
    return event.is_set()


async def _assert_health_while_blocked(
    feed_endpoint: Callable[..., Any],
    health_endpoints: list[Callable[..., Any]],
    blocker: _BlockingFeed,
) -> Any:
    # The watchdog prevents the pre-fix implementation from deadlocking the
    # test process.  Correct code reaches the assertions while the gate remains
    # closed; old inline-sync code only resumes after the watchdog fires.
    watchdog = threading.Timer(2.5, blocker.release.set)
    watchdog.daemon = True
    watchdog.start()
    task = asyncio.create_task(feed_endpoint())
    try:
        assert await _wait_event(blocker.started)
        assert await _wait_event(blocker.saturated)
        assert not task.done(), "feed completed before the blocked upstream was released"

        started = time.monotonic()
        responses = [await endpoint() for endpoint in health_endpoints]
        elapsed = time.monotonic() - started

        assert elapsed < 0.5, "local health handlers were starved by upstream I/O"
        assert not task.done(), "feed did not remain pending while health handlers ran"
        assert all(_payload(response).get("ok") is True for response in responses)
    finally:
        blocker.release.set()
        watchdog.cancel()
    return await asyncio.wait_for(task, timeout=2.0)


def test_network_feed_routes_preserve_event_loop_responsiveness_and_schemas(monkeypatch):
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    deva.register(app, ns="a11oy")
    devb.register(app)

    deva_health = _endpoint(app, "/api/a11oy/v1/deva/healthz")
    devb_health = _endpoint(app, "/api/a11oy/v1/devb/healthz")

    finance_calls = 14
    finance_blocker = _BlockingFeed(
        saturation=min(vertical._UPSTREAM_MAX_CONCURRENCY, finance_calls)
    )
    for name in ("feed_yahoo", "feed_polygon", "feed_coinbase", "feed_nvd", "feed_fx"):
        monkeypatch.setattr(vertical, name, finance_blocker)

    deva_blocker = _BlockingFeed()
    monkeypatch.setattr(deva, "feed_yahoo", deva_blocker)

    devb_blocker = _BlockingFeed()
    monkeypatch.setattr(devb, "feed_courtlistener", devb_blocker)

    finance_feed = _endpoint(app, "/api/a11oy/v1/vert/finance/feed")
    deva_quant = _endpoint(app, "/api/a11oy/v1/deva/finance/quant")
    devb_matter = _endpoint(app, "/api/a11oy/v1/devb/legal/matter")

    async def _exercise() -> tuple[Any, Any, Any]:
        finance_response = await _assert_health_while_blocked(
            finance_feed, [deva_health, devb_health], finance_blocker
        )
        assert finance_blocker.max_active <= vertical._UPSTREAM_MAX_CONCURRENCY
        assert finance_blocker.max_active == min(
            vertical._UPSTREAM_MAX_CONCURRENCY, finance_calls
        )

        deva_response = await _assert_health_while_blocked(
            deva_quant, [deva_health, devb_health], deva_blocker
        )
        devb_response = await _assert_health_while_blocked(
            devb_matter, [deva_health, devb_health], devb_blocker
        )
        return finance_response, deva_response, devb_response

    finance_response, deva_response, devb_response = asyncio.run(_exercise())

    finance_payload = _payload(finance_response)
    assert set(finance_payload) == {
        "vertical", "equities_official", "equities", "equities_note", "crypto",
        "fx", "fintech_cve", "sources_cited", "doctrine",
    }
    assert list(finance_payload["equities"]) == ["SPY", "AAPL", "MSFT", "NVDA", "^VIX"]
    assert list(finance_payload["equities_official"]) == ["SPY", "AAPL", "MSFT", "NVDA"]
    assert list(finance_payload["crypto"]) == ["BTC-USD", "ETH-USD", "SOL-USD"]

    deva_payload = _payload(deva_response)
    assert set(deva_payload) == {"tab", "equities", "factors", "doctrine"}
    assert deva_payload["tab"] == "quant"

    devb_payload = _payload(devb_response)
    assert set(devb_payload) == {"surface", "term", "opinions", "doctrine"}
    assert devb_payload["surface"] == "matter"


def test_vertical_cache_distinguishes_cached_from_stale() -> None:
    cache = vertical._Cache()
    now = time.time()
    with cache._lock:
        cache._d["cached"] = {
            "value": {"real": True}, "fetched_at": now - 11.0,
            "ttl": 10.0, "status": "live",
        }
        cache._d["stale"] = {
            "value": {"real": True}, "fetched_at": now - 41.0,
            "ttl": 10.0, "status": "live",
        }

    assert cache.freshness("cached")["status"] == "cached"
    assert cache.freshness("stale")["status"] == "stale"


def test_digest_only_fallback_is_unsigned_and_unverified(monkeypatch) -> None:
    class _UnexpectedSigner:
        @staticmethod
        def sign_khipu_receipt(_receipt: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("digest-only fallback must never reach a signer")

    monkeypatch.setattr(vertical, "_HAS_KHIPU", False)
    monkeypatch.setattr(vertical, "_HAS_DSSE", True)
    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "szl_dsse", _UnexpectedSigner())

    result = vertical.governed_turn("finance", "review this transaction")
    receipt = result["receipt"]
    dsse = result["dsse"]

    assert receipt["receipt_type"] == "DIGEST_ONLY"
    assert receipt["signature_state"] == "UNSIGNED"
    assert receipt["signed"] is False
    assert receipt["signature"] is None
    assert receipt["chain_verified"] is False
    assert len(receipt["digest"]) == 64
    assert dsse["signed"] is False
    assert dsse["signature_state"] == "UNSIGNED"

    monkeypatch.setattr(deva, "_HAS_VF", False)
    monkeypatch.setattr(devb, "_HAS_VF", False)
    for fallback in (
        deva.governed_turn("finance", "review this transaction"),
        devb.governed_turn("leg-matter", "review this transaction"),
    ):
        fallback_receipt = fallback["receipt"]
        assert fallback_receipt["receipt_type"] == "DIGEST_ONLY"
        assert fallback_receipt["signature_state"] == "UNSIGNED"
        assert fallback_receipt["signed"] is False
        assert fallback_receipt["signature"] is None
        assert fallback_receipt["chain_verified"] is False
        assert fallback["dsse"]["signed"] is False
        assert fallback["dsse"]["signature_state"] == "UNSIGNED"


def test_bare_vertical_live_is_derived_from_observed_children(monkeypatch) -> None:
    cache = vertical._Cache()
    monkeypatch.setattr(vertical, "_CACHE", cache)
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    defense_summary = _endpoint(app, "/api/a11oy/v1/vert/{vertical}")

    async def _exercise() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        unavailable = _payload(await defense_summary("defense"))

        cache.put("cisa_kev", {"real": True}, ttl=10.0)
        cache.put("nvd", {"real": True}, ttl=10.0)
        live = _payload(await defense_summary("defense"))

        with cache._lock:
            cache._d["cisa_kev"]["fetched_at"] -= 41.0
            cache._d["nvd"]["fetched_at"] -= 41.0
        stale = _payload(await defense_summary("defense"))
        return unavailable, live, stale

    unavailable, live, stale = asyncio.run(_exercise())

    assert unavailable["live"] is False
    assert unavailable["feed_state"]["status"] == "unavailable"
    assert unavailable["feed_state"]["children_live"] == 0

    assert live["live"] is True
    assert live["feed_state"]["status"] == "live"
    assert live["feed_state"]["children_live"] == 2

    assert stale["live"] is False
    assert stale["feed_state"]["status"] == "stale"
    assert {child["status"] for child in stale["feed_state"]["children"]} == {"stale"}


def test_devb_singleflight_coalesces_refresh_and_preserves_fresh_success(monkeypatch) -> None:
    key = "race"
    old_record = {
        "value": {"generation": "old"},
        "fetched_at": time.time() - 20.0,
        "ttl": 1.0,
        "status": "live",
    }
    monkeypatch.setattr(devb, "_HAS_VF", False)
    monkeypatch.setattr(devb, "_LOCAL_CACHE", {key: old_record})
    monkeypatch.setattr(devb, "_LOCAL_INFLIGHT", {})

    refresh_started = threading.Event()
    release_refresh = threading.Event()
    client_calls = 0
    calls_lock = threading.Lock()

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"generation": "new"}

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str) -> _Response:
            nonlocal client_calls
            with calls_lock:
                client_calls += 1
            refresh_started.set()
            if not release_refresh.wait(2.0):
                raise TimeoutError("test refresh release deadline exhausted")
            return _Response()

    monkeypatch.setattr(devb.httpx, "Client", _Client)
    results: dict[str, dict[str, Any]] = {}

    def _fetch(label: str) -> None:
        results[label] = devb._cached(key, "https://invalid.example.test", 60.0)

    leader = threading.Thread(target=_fetch, args=("leader",), name="refresh-leader")
    follower = threading.Thread(target=_fetch, args=("follower",), name="refresh-follower")
    leader.start()
    assert refresh_started.wait(1.0)
    follower.start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        with devb._LOCAL_CACHE_LOCK:
            flight = devb._LOCAL_INFLIGHT.get(key)
            if flight is not None and flight.waiters == 1:
                break
        time.sleep(0.001)
    else:
        raise AssertionError("same-key follower never joined the in-flight refresh")

    release_refresh.set()
    leader.join(1.0)
    follower.join(1.0)
    assert not leader.is_alive()
    assert not follower.is_alive()

    with devb._LOCAL_CACHE_LOCK:
        final_record = dict(devb._LOCAL_CACHE[key])
        assert key not in devb._LOCAL_INFLIGHT
    assert client_calls == 1
    assert final_record["value"] == {"generation": "new"}
    assert final_record["status"] == "live"
    assert results["leader"] == results["follower"]
    assert results["leader"]["value"] == {"generation": "new"}
    assert results["leader"]["freshness"]["status"] == "live"


class _JsonRequest:
    def __init__(self, body: Any, authorization: str | None = _GOVERN_TOKEN) -> None:
        self.body = body
        self.headers = ({"authorization": f"Bearer {authorization}"}
                        if authorization is not None else {})

    async def json(self) -> Any:
        return self.body


def test_public_query_parameters_are_bounded_at_the_api_edge() -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    deva.register(app, ns="a11oy")
    devb.register(app)

    async def exercise() -> list[int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://a11oy.test",
        ) as client:
            responses = [
                await client.get("/api/a11oy/v1/vert/defense/feed?limit=0"),
                await client.get("/api/a11oy/v1/deva/frontier/models?limit=101"),
                await client.get(
                    "/api/a11oy/v1/devb/legal/matter", params={"term": "x" * 161},
                ),
                await client.get(
                    "/api/a11oy/v1/devb/ent/incident",
                    params={"repo": "not-a-repository"},
                ),
                await client.get(
                    "/api/a11oy/v1/devb/ent/forecast", params={"growth": "nan"},
                ),
            ]
            return [response.status_code for response in responses]

    assert asyncio.run(exercise()) == [422, 422, 422, 422, 422]


def test_govern_routes_reject_invalid_severity_and_context_with_422(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    deva.register(app, ns="a11oy")
    devb.register(app)

    monkeypatch.setattr(
        vertical, "governed_turn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid body must not reach governance")
        ),
    )
    monkeypatch.setattr(deva, "governed_turn", vertical.governed_turn)
    monkeypatch.setattr(devb, "governed_turn", vertical.governed_turn)

    vertical_govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    deva_govern = _endpoint(app, "/api/a11oy/v1/deva/{tab}/govern")
    devb_govern = _endpoint(app, "/api/a11oy/v1/devb/{label}/govern")

    async def exercise() -> list[Any]:
        return [
            await vertical_govern("finance", _JsonRequest({
                "text": "review", "severity": "not-a-number", "context": {},
            })),
            await deva_govern("quant", _JsonRequest({
                "text": "review", "severity": float("nan"), "context": {},
            })),
            await devb_govern("ent-exec", _JsonRequest({
                "text": "review", "severity": 4, "context": ["not", "a", "dict"],
            })),
        ]

    responses = asyncio.run(exercise())
    assert [response.status_code for response in responses] == [422, 422, 422]
    fields = [_payload(response)["detail"][0]["loc"][-1] for response in responses]
    assert fields == ["severity", "severity", "context"]


async def _health_while_task_blocked(
    task: asyncio.Task[Any], started: threading.Event,
    release: threading.Event, health_endpoint: Callable[..., Any],
) -> Any:
    watchdog = threading.Timer(2.5, release.set)
    watchdog.daemon = True
    watchdog.start()
    try:
        assert await _wait_event(started)
        assert not task.done()
        began = time.monotonic()
        health = await health_endpoint()
        elapsed = time.monotonic() - began
        assert elapsed < 0.5
        assert _payload(health)["ok"] is True
        assert not task.done()
    finally:
        release.set()
        watchdog.cancel()
    return await asyncio.wait_for(task, timeout=2.0)


def test_blocked_production_signer_does_not_starve_health(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    health = _endpoint(app, "/api/a11oy/v1/vert/healthz")
    signer_started = threading.Event()
    release_signer = threading.Event()

    class _Dag:
        def emit(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "organ": "vertical-finance", "ns": "a11oy", "action": action,
                "digest": "1" * 64, "payload_digest": "2" * 64,
                "chain_verified": True,
            }

    class _Khipu:
        @staticmethod
        def get_dag(_organ: str, ns: str) -> _Dag:
            assert ns == "a11oy"
            return _Dag()

    class _Signer:
        @staticmethod
        def sign_khipu_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
            signer_started.set()
            if not release_signer.wait(2.0):
                raise TimeoutError("signer release deadline exhausted")
            return {"receipt": receipt, "dsse": {"signed": True, "keyid": "test"}}

    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "_HAS_KHIPU", True)
    monkeypatch.setattr(vertical, "_HAS_DSSE", True)
    monkeypatch.setattr(vertical, "szl_khipu", _Khipu())
    monkeypatch.setattr(vertical, "szl_dsse", _Signer())

    async def exercise() -> Any:
        task = asyncio.create_task(govern("finance", _JsonRequest({
            "text": "review this transaction", "severity": 4.0,
            "context": {"task": "finance"},
        })))
        return await _health_while_task_blocked(
            task, signer_started, release_signer, health,
        )

    response = asyncio.run(exercise())
    assert _payload(response)["dsse"]["signed"] is True


def test_blocked_khipu_dag_does_not_starve_health(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    ledger = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/ledger")
    health = _endpoint(app, "/api/a11oy/v1/vert/healthz")
    dag_started = threading.Event()
    release_dag = threading.Event()

    class _Dag:
        def depth(self) -> int:
            dag_started.set()
            if not release_dag.wait(2.0):
                raise TimeoutError("DAG release deadline exhausted")
            return 2

        def head(self) -> str:
            return "head"

        def verify_chain(self) -> bool:
            return True

        def tail(self, _n: int) -> list[dict[str, Any]]:
            return []

    class _Khipu:
        @staticmethod
        def get_dag(_organ: str, ns: str) -> _Dag:
            assert ns == "a11oy"
            return _Dag()

    monkeypatch.setattr(vertical, "_HAS_KHIPU", True)
    monkeypatch.setattr(vertical, "szl_khipu", _Khipu())

    async def exercise() -> Any:
        task = asyncio.create_task(ledger("finance", 25))
        return await _health_while_task_blocked(task, dag_started, release_dag, health)

    response = asyncio.run(exercise())
    assert _payload(response)["depth"] == 2


def test_blocked_forecast_governance_does_not_starve_devb_health(monkeypatch) -> None:
    app = FastAPI()
    devb.register(app)
    forecast_endpoint = _endpoint(app, "/api/a11oy/v1/devb/ent/forecast")
    health = _endpoint(app, "/api/a11oy/v1/devb/healthz")
    govern_started = threading.Event()
    release_govern = threading.Event()

    def blocked_govern(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["emit_receipt"] is False
        govern_started.set()
        if not release_govern.wait(2.0):
            raise TimeoutError("forecast-govern release deadline exhausted")
        return {"decision": "review", "receipt": {"chain_verified": False}}

    monkeypatch.setattr(devb, "governed_turn", blocked_govern)

    async def exercise() -> Any:
        task = asyncio.create_task(forecast_endpoint())
        return await _health_while_task_blocked(
            task, govern_started, release_govern, health,
        )

    response = asyncio.run(exercise())
    assert _payload(response)["governed"]["decision"] == "review"


def test_govern_routes_fail_closed_before_body_or_mutation(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    deva.register(app, ns="a11oy")
    devb.register(app)

    def must_not_govern(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("unauthenticated request reached governance")

    monkeypatch.setattr(vertical, "governed_turn", must_not_govern)
    monkeypatch.setattr(deva, "governed_turn", must_not_govern)
    monkeypatch.setattr(devb, "governed_turn", must_not_govern)

    async def exercise() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://a11oy.test") as client:
            return [
                await client.post("/api/a11oy/v1/vert/finance/govern", content=b"not-json"),
                await client.post("/api/a11oy/v1/deva/quant/govern", content=b"not-json"),
                await client.post("/api/a11oy/v1/devb/ent-exec/govern", content=b"not-json"),
            ]

    responses = asyncio.run(exercise())
    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(response.json()["error"] == "missing_authorization" for response in responses)
    assert all(response.headers["www-authenticate"] == "Bearer" for response in responses)


def test_govern_registry_absence_and_scope_mismatch_fail_closed(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    monkeypatch.delenv("A11OY_GOVERN_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("A11OY_GOVERN_PRINCIPALS_JSON", raising=False)
    monkeypatch.delenv("GDW_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("GDW_PRINCIPALS_JSON", raising=False)

    unavailable = asyncio.run(govern("finance", _JsonRequest({"text": "review"})))
    assert unavailable.status_code == 503
    assert _payload(unavailable)["state"] == "unavailable"

    monkeypatch.setenv("A11OY_GOVERN_CREDENTIALS_JSON", json.dumps({
        "version": 1,
        "credentials": [{
            "owner_id": "operator:test", "namespace": "a11oy", "key_id": "read-only",
            "token": _GOVERN_TOKEN, "scopes": ["session:read"], "revoked": False,
        }],
    }))
    denied = asyncio.run(govern("finance", _JsonRequest({"text": "review"})))
    assert denied.status_code == 403
    assert _payload(denied)["error"] == "missing_scopes"


def test_govern_body_caps_unknown_keys_and_action_aliases_before_mutation(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    monkeypatch.setenv("A11OY_GOVERN_BODY_MAX_BYTES", "1024")
    monkeypatch.setattr(
        vertical, "governed_turn",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid request reached governance")
        ),
    )

    class _StreamRequest:
        headers = {
            "authorization": f"Bearer {_GOVERN_TOKEN}",
            "content-length": "1",
        }

        async def stream(self):
            yield b'{"text":"' + (b"x" * 1100) + b'"}'

    async def exercise() -> list[Any]:
        return [
            await govern("finance", _JsonRequest({"text": "review", "surprise": True})),
            await govern("finance", _JsonRequest({
                "text": "review", "action_kind": "operator.approve",
            })),
            await govern("finance", _StreamRequest()),
        ]

    responses = asyncio.run(exercise())
    assert [response.status_code for response in responses] == [422, 422, 413]
    assert _payload(responses[0])["detail"][0]["loc"][-1] == "surprise"
    assert _payload(responses[1])["detail"][0]["loc"][-1] == "action_kind"


def test_authorized_governance_binds_principal_and_server_owned_action(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    captured: dict[str, Any] = {}

    class _Dag:
        def emit(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
            captured["action"] = action
            captured["payload"] = payload
            return {
                "organ": "vertical-finance", "ns": "a11oy", "action": action,
                "digest": "1" * 64, "payload_digest": "2" * 64,
                "chain_verified": True,
            }

    class _Khipu:
        @staticmethod
        def get_dag(_organ: str, ns: str) -> _Dag:
            assert ns == "a11oy"
            return _Dag()

    class _Signer:
        @staticmethod
        def sign_khipu_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
            captured["signed_input"] = receipt
            return {"receipt": receipt, "dsse": {"signed": True, "keyid": "test"}}

    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "_HAS_KHIPU", True)
    monkeypatch.setattr(vertical, "_HAS_DSSE", True)
    monkeypatch.setattr(vertical, "szl_khipu", _Khipu())
    monkeypatch.setattr(vertical, "szl_dsse", _Signer())

    response = asyncio.run(govern("finance", _JsonRequest({
        "text": "review this transaction", "severity": 4,
        "classification": "restricted", "action_kind": "review",
    })))
    assert response.status_code == 200
    payload = _payload(response)
    assert captured["action"] == "a11oy.vertical-finance.govern.review"
    assert captured["payload"]["actor"] == {
        "actor_type": "credential", "owner_id": "operator:test",
        "namespace": "a11oy", "key_id": "test-govern-key",
        "scope": "vertical:govern",
    }
    assert payload["authorization"] == captured["payload"]["actor"]
    assert captured["signed_input"]["actor"]["key_id"] == "test-govern-key"
    assert captured["signed_input"]["policy"]["decision"] == payload["decision"]
    assert captured["signed_input"]["chain"]["digest"] == payload["receipt"]["digest"]
    assert "review this transaction" not in json.dumps(captured["signed_input"])


def test_all_three_authorized_govern_route_families_share_identity_and_action_contract(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    deva.register(app, ns="a11oy")
    devb.register(app)
    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "_HAS_KHIPU", False)
    monkeypatch.setattr(vertical, "_HAS_DSSE", False)
    endpoints = [
        (_endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern"), "finance",
         "a11oy.vertical-finance.govern.decision"),
        (_endpoint(app, "/api/a11oy/v1/deva/{tab}/govern"), "quant",
         "a11oy.deva-quant.govern.decision"),
        (_endpoint(app, "/api/a11oy/v1/devb/{label}/govern"), "ent-exec",
         "a11oy.devb-ent-exec.govern.decision"),
    ]

    async def exercise() -> list[dict[str, Any]]:
        results = []
        for endpoint, label, _expected in endpoints:
            response = await endpoint(label, _JsonRequest({"text": "review operation"}))
            assert response.status_code == 200
            results.append(_payload(response))
            with vertical._GOVERN_RATE_LOCK:
                vertical._GOVERN_LAST.clear()
        return results

    results = asyncio.run(exercise())
    for result, (_endpoint_fn, _label, expected_action) in zip(results, endpoints):
        assert result["receipt"]["action"] == expected_action
        assert result["authorization"]["owner_id"] == "operator:test"
        assert result["authorization"]["key_id"] == "test-govern-key"
        assert result["authorization"]["scope"] == "vertical:govern"


def test_govern_mutations_are_globally_serialized_and_principal_cooled_down() -> None:
    principal, denial = vertical._govern_authorise(f"Bearer {_GOVERN_TOKEN}")
    assert denial is None
    identity, retry = vertical._govern_claim(principal)
    assert identity == ("operator:test", "test-govern-key")
    assert retry is None
    blocked_identity, blocked_retry = vertical._govern_claim(principal)
    assert blocked_identity is None
    assert blocked_retry >= 1
    vertical._govern_release(identity)
    cooled_identity, cooled_retry = vertical._govern_claim(principal)
    assert cooled_identity is None
    assert cooled_retry >= 1


def test_anonymous_forecast_is_read_only_and_never_calls_ledger_or_signer(monkeypatch) -> None:
    class _ForbiddenKhipu:
        @staticmethod
        def get_dag(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("read-only forecast attempted a ledger mutation")

    class _ForbiddenSigner:
        @staticmethod
        def sign_khipu_receipt(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("read-only forecast attempted signing")

    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "_HAS_KHIPU", True)
    monkeypatch.setattr(vertical, "_HAS_DSSE", True)
    monkeypatch.setattr(vertical, "szl_khipu", _ForbiddenKhipu())
    monkeypatch.setattr(vertical, "szl_dsse", _ForbiddenSigner())
    result = devb.forecast("base", 4, 100.0, 0.08, 0.0)
    assert result["governed"]["mutation"] == "none"
    assert result["governed"]["receipt"]["receipt_type"] == "NOT_EMITTED"
    assert result["governed"]["dsse"]["signed"] is False


def test_parameterized_cache_cardinality_is_bounded_with_deterministic_eviction(monkeypatch) -> None:
    cache = vertical._Cache(max_entries=2)
    monkeypatch.setattr(vertical.time, "time", lambda: 1.0)
    cache.put("b", {"key": "b"}, 60)
    cache.put("a", {"key": "a"}, 60)
    cache.put("c", {"key": "c"}, 60)
    assert set(cache._d) == {"b", "c"}

    monkeypatch.setattr(deva, "_CACHE_MAX_ENTRIES", 2)
    with deva._LOCK:
        deva._CACHE.clear()
        deva._INFLIGHT.clear()
        deva._CACHE.update({
            "b": {"fetched_at": 1.0}, "a": {"fetched_at": 1.0},
            "c": {"fetched_at": 2.0},
        })
        deva._evict_cache_locked("c")
        assert set(deva._CACHE) == {"b", "c"}
        deva._CACHE.clear()

    monkeypatch.setattr(devb, "_LOCAL_CACHE_MAX_ENTRIES", 2)
    with devb._LOCAL_CACHE_LOCK:
        devb._LOCAL_CACHE.clear()
        devb._LOCAL_INFLIGHT.clear()
        devb._LOCAL_CACHE.update({
            "b": {"fetched_at": 1.0}, "a": {"fetched_at": 1.0},
            "c": {"fetched_at": 2.0},
        })
        devb._evict_local_cache_locked("c")
        assert set(devb._LOCAL_CACHE) == {"b", "c"}
        devb._LOCAL_CACHE.clear()


def test_external_redirect_following_is_disabled_and_plaintext_policy_is_fail_closed() -> None:
    clients = [vertical._client(), deva._client(), devb._client()]
    try:
        assert all(client.follow_redirects is False for client in clients)
    finally:
        for client in clients:
            client.close()
    for module in (vertical, deva, devb):
        assert module._source_url_allowed("https://example.test/feed") is True
        assert module._source_url_allowed("http://example.test/feed") is False
        assert module._source_url_allowed("http://127.0.0.1:7860/feed") is True


def test_feed_receipt_doctrine_claims_canonical_slsa_l1_only() -> None:
    for module in (vertical, deva, devb):
        claim = module.DOCTRINE["slsa"]
        assert claim.startswith("L1 only")
        assert "L2 build-attestation" not in claim


def test_roi_counts_authenticated_allow_review_and_deny_without_ledger_depth(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    roi_endpoint = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/roi")
    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "_HAS_KHIPU", False)
    monkeypatch.setattr(vertical, "_HAS_DSSE", False)
    with vertical._ROI_LOCK:
        vertical._ROI_COUNTS.clear()

    async def run(body: dict[str, Any]) -> dict[str, Any]:
        response = await govern("finance", _JsonRequest(body))
        assert response.status_code == 200
        with vertical._GOVERN_RATE_LOCK:
            vertical._GOVERN_LAST.clear()
        return _payload(response)

    async def exercise() -> tuple[list[dict[str, Any]], Any]:
        outcomes = [
            await run({"text": "ordinary portfolio review", "severity": 0}),
            await run({"text": "high severity portfolio review", "severity": 10}),
            await run({"text": "contains SSN sensitive data", "severity": 0}),
        ]
        return outcomes, await roi_endpoint("finance")

    governed, roi_response = asyncio.run(exercise())
    assert [item["decision"] for item in governed] == ["allow", "review", "deny"]
    result = _payload(roi_response)
    assert result["governed_decisions"] == 3
    assert result["risks_caught"] == 2
    assert result["decision_outcomes"] == {"allow": 1, "review": 1, "deny": 1}
    assert "never inferred from ledger depth" in result["count_evidence"]


def test_govern_ledger_binds_real_khipu_shape_to_typed_private_statement(monkeypatch) -> None:
    app = FastAPI()
    vertical.register(app, ns="a11oy")
    govern = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/govern")
    ledger = _endpoint(app, "/api/a11oy/v1/vert/{vertical}/ledger")
    dag = real_khipu.KhipuDAG("vertical-finance", ns="a11oy")

    class _Khipu:
        @staticmethod
        def get_dag(_organ: str, ns: str) -> real_khipu.KhipuDAG:
            assert ns == "a11oy"
            return dag

    class _Signer:
        @staticmethod
        def sign_khipu_receipt(statement: dict[str, Any]) -> dict[str, Any]:
            statement = dict(statement)
            statement["neuro_citations"] = []
            encoded = json.dumps(
                statement, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            return {
                "receipt": statement,
                "dsse": {
                    "signed": True,
                    "payload": base64.b64encode(encoded).decode("ascii"),
                    "payloadType": "application/vnd.szl.khipu+json",
                    "signatures": [{"keyid": "test-key", "sig": "test"}],
                },
            }

        @staticmethod
        def verify_envelope(_envelope: dict[str, Any]) -> dict[str, Any]:
            return {"verified": False, "reason": "deterministic test signer has no key"}

    monkeypatch.setattr(vertical, "_HAS_GW", False)
    monkeypatch.setattr(vertical, "_HAS_KHIPU", True)
    monkeypatch.setattr(vertical, "_HAS_DSSE", True)
    monkeypatch.setattr(vertical, "szl_khipu", _Khipu())
    monkeypatch.setattr(vertical, "szl_dsse", _Signer())
    with vertical._SIGNED_ENVELOPE_LOCK:
        vertical._SIGNED_ENVELOPES.clear()

    async def exercise() -> tuple[Any, Any]:
        governed = await govern("finance", _JsonRequest({
            "text": "review transaction secret-input-marker",
            "context": {"case": "secret-context-marker"},
            "severity": 10,
        }))
        observed_ledger = await ledger("finance", 25)
        return governed, observed_ledger

    governed_response, ledger_response = asyncio.run(exercise())
    governed = _payload(governed_response)
    observed = _payload(ledger_response)
    assert governed["dsse"]["signed"] is True
    assert observed["verify"]["ok"] is True
    assert "payload" not in observed["receipts"][0]
    evidence = observed["receipts"][0]["signature_evidence"]
    assert evidence["binding_verified"] is True
    assert evidence["envelope_payload_matches_statement"] is True
    assert evidence["chain_digest"] == governed["receipt"]["digest"]
    assert evidence["dsse"]["signed"] is True
    assert evidence["durability"] == "IN_PROCESS_BOUNDED_EVICTABLE"
    assert evidence["durable_across_restart"] is False
    assert evidence["statement"]["actor"]["owner_id"] == "operator:test"
    assert evidence["statement"]["policy"]["decision"] == "review"
    assert evidence["statement"]["chain"]["payload_digest"] == governed["receipt"]["payload_digest"]
    serialized = json.dumps(evidence["statement"], sort_keys=True)
    assert "secret-input-marker" not in serialized
    assert "secret-context-marker" not in serialized
    assert set(evidence["statement"]["content_digests"]) == {
        "input_sha256", "context_sha256",
    }
    assert evidence["cryptographic_verification"]["verified"] is False
    retention = observed["signer_evidence_retention"]
    assert retention["durability"] == "IN_PROCESS_BOUNDED_EVICTABLE"
    assert retention["current_entries"] == 1
    assert retention["max_entries"] == 512


def test_signer_evidence_retention_is_bounded_evictable_and_counted(monkeypatch) -> None:
    monkeypatch.setattr(vertical, "_SIGNED_ENVELOPE_MAX", 2)
    with vertical._SIGNED_ENVELOPE_LOCK:
        vertical._SIGNED_ENVELOPES.clear()
        vertical._SIGNED_ENVELOPE_EVICTIONS = 0

    def statement_for(digest: str) -> dict[str, Any]:
        return {
            "statement_type": "A11OY_GOVERNANCE_STATEMENT_V1",
            "schema_version": 1,
            "chain": {
                "organ": "vertical-finance", "namespace": "a11oy",
                "digest": digest, "payload_digest": "a" * 64,
                "action": "a11oy.vertical-finance.govern.decision",
            },
            "actor": {
                "actor_type": "credential", "owner_id": "operator:test",
                "namespace": "a11oy", "key_id": "test-govern-key",
                "scope": "vertical:govern",
            },
            "policy": {
                "policy_id": "a11oy.vertical-govern.v1",
                "server_action": "a11oy.vertical-finance.govern.decision",
                "decision": "allow", "sensitivity": "PUBLIC",
                "lambda": 0.97, "lambda_floor": 0.9, "gates": [],
            },
            "content_digests": {
                "input_sha256": "b" * 64, "context_sha256": "c" * 64,
            },
            "privacy": "NO_RAW_INPUT_OR_CONTEXT",
        }

    try:
        digests = [f"{number:064x}" for number in (1, 2, 3)]
        for digest in digests:
            statement = statement_for(digest)
            encoded = json.dumps(
                statement, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            vertical._remember_signed_envelope(
                "vertical-finance", digest, statement,
                {"signed": True, "payload": base64.b64encode(encoded).decode("ascii")},
            )

        empty_dag = real_khipu.KhipuDAG("vertical-finance", ns="a11oy")

        class _Khipu:
            @staticmethod
            def get_dag(_organ: str, ns: str) -> real_khipu.KhipuDAG:
                assert ns == "a11oy"
                return empty_dag

        monkeypatch.setattr(vertical, "_HAS_KHIPU", True)
        monkeypatch.setattr(vertical, "szl_khipu", _Khipu())
        ledger = vertical._ledger("finance", 25)
        retention = ledger["signer_evidence_retention"]
        assert retention == {
            "durability": "IN_PROCESS_BOUNDED_EVICTABLE",
            "durable_across_restart": False,
            "current_entries": 2,
            "max_entries": 2,
            "evictions": 1,
            "eviction_policy": "oldest-stored-at-then-organ-and-chain-digest",
        }
        with vertical._SIGNED_ENVELOPE_LOCK:
            assert ("vertical-finance", digests[0]) not in vertical._SIGNED_ENVELOPES
            assert set(vertical._SIGNED_ENVELOPES) == {
                ("vertical-finance", digests[1]),
                ("vertical-finance", digests[2]),
            }
    finally:
        with vertical._SIGNED_ENVELOPE_LOCK:
            vertical._SIGNED_ENVELOPES.clear()
            vertical._SIGNED_ENVELOPE_EVICTIONS = 0
