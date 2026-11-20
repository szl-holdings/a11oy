"""Regression: slow pool refresh must not starve the ASGI event loop.

Source-only fixture. Never calls live GPUs, caches, cloud billing, or other services.
"""

from __future__ import annotations

import asyncio
import threading

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import szl_compute_pool_contract as pool_contract


def test_health_remains_responsive_during_stalled_pool_refresh(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    response = {"fixture": "bounded-unavailable", "ready": False}

    def blocked_probe():
        entered.set()
        # A finite wait makes the original event-loop regression fail, not hang.
        release.wait(timeout=3)
        return response

    monkeypatch.setattr(pool_contract, "build_compute_pool_contract", blocked_probe)
    app = FastAPI()
    assert pool_contract.register(app) == ["/api/a11oy/v1/compute-pool/v1"]

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    async def exercise():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://fixture.local"
        ) as client:
            pending = asyncio.create_task(client.get("/api/a11oy/v1/compute-pool/v1"))
            try:
                assert await asyncio.to_thread(entered.wait, 1), "probe never entered"
                health = await asyncio.wait_for(client.get("/healthz"), timeout=1)
                assert health.status_code == 200
                assert health.json() == {"ok": True}
                assert not pending.done(), "pool request blocked health event loop"
            finally:
                release.set()
            pool = await asyncio.wait_for(pending, timeout=2)
            assert pool.status_code == 200
            assert pool.json() == response
            assert pool.headers["cache-control"] == "no-store"

    asyncio.run(exercise())


def test_sync_health_is_not_starved_by_saturated_pool_probes(monkeypatch):
    """A bounded pool probe lane must leave the shared sync-health lane usable."""
    import anyio

    started = threading.Event()
    release = threading.Event()
    count_lock = threading.Lock()
    calls = []

    def blocked_probe():
        with count_lock:
            calls.append("probe")
            if len(calls) == 2:
                started.set()
        # The finite timeout keeps failures bounded even if the test tears down.
        assert release.wait(timeout=4), "fixture blocked beyond its timeout"
        return {"ready": False, "fixture": "two-stalled-probes"}

    monkeypatch.setattr(pool_contract, "build_compute_pool_contract", blocked_probe)
    app = FastAPI()
    pool_contract.register(app)

    @app.get("/sync-healthz")
    def sync_healthz():
        return {"ok": True}

    async def exercise():
        # Shrink the shared default pool in this isolated event loop only.
        default_limiter = anyio.to_thread.current_default_thread_limiter()
        original_limit = default_limiter.total_tokens
        default_limiter.total_tokens = 2
        tasks = []
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fixture.local"
            ) as client:
                tasks = [
                    asyncio.create_task(client.get("/api/a11oy/v1/compute-pool/v1"))
                    for _ in range(3)
                ]
                assert await asyncio.to_thread(started.wait, 1.5)
                assert len(calls) == 2
                health_task = asyncio.create_task(client.get("/sync-healthz"))
                health = await asyncio.wait_for(
                    asyncio.shield(health_task), timeout=0.4
                )
                assert health.status_code == 200
                assert health.json() == {"ok": True}
                assert not tasks[0].done()
                assert not tasks[1].done()
        finally:
            release.set()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            default_limiter.total_tokens = original_limit

    asyncio.run(exercise())
