#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local health must remain available while fleet peer I/O is blocked."""

import ast
import asyncio
import io
from pathlib import Path
import threading
import urllib.error
import urllib.request

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import pytest


@pytest.mark.parametrize("handler", [
    "api_a11oy_v4_fleet_early", "api_a11oy_v4_fleet",
])
@pytest.mark.parametrize("path", ["/api/a11oy/v4/fleet", "/v4/fleet"])
def test_fleet_peer_io_does_not_block_local_health(monkeypatch, handler, path):
    # Load the actual route and decorators without booting unrelated services.
    source = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(node for node in tree.body if getattr(node, "name", None) == handler)
    app = FastAPI()
    namespace = {"app": app, "JSONResponse": JSONResponse}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)

    @app.get("/api/build-info")
    async def build_info():
        return {"service": "a11oy"}

    entered = threading.Event()
    release = threading.Event()
    requested = []

    def blocked_urlopen(request, timeout):
        requested.append((request.full_url, timeout))
        entered.set()
        assert release.wait(3), "test watchdog failed to release peer I/O"
        if "szlholdings-killinchu" in request.full_url:
            raise urllib.error.URLError("peer unavailable")
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    # Old async handlers resume the test only when this watchdog releases I/O.
    watchdog = threading.Timer(2, release.set)
    watchdog.daemon = True

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            pending = asyncio.create_task(client.get(path))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                response = await asyncio.wait_for(client.get("/api/build-info"), 0.5)
                assert response.status_code == 200
                assert response.json() == {"service": "a11oy"}
                assert not release.is_set(), "fleet I/O starved local health until watchdog release"
                assert not pending.done(), "fleet completed before the blocked peer was released"
            finally:
                release.set()
                watchdog.cancel()
                fleet_response = await asyncio.wait_for(pending, 2)
            assert fleet_response.status_code == 200
            peers = fleet_response.json()["peers"]
            assert [peer["status"] for peer in peers] == ["ok", "ok", "ok", "unreachable"]
            assert "peer unavailable" in peers[-1]["error"]
            assert len(requested) == 4
            assert all(timeout == 5 for _, timeout in requested)

    watchdog.start()
    asyncio.run(exercise())
