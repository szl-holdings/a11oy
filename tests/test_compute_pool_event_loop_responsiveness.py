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
