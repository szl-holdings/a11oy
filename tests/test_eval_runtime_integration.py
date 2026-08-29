"""Real-ASGI integration coverage for the eval-history operator lifecycle.

The service module is intentionally imported once for this file.  The tests run
the canonical FastAPI lifespan and real routes, while replacing only external
startup boundaries (Node and energy/network probes).  This catches lifecycle and
event-loop regressions that the lightweight AST contracts cannot see.
"""

from __future__ import annotations

import asyncio
import collections
import json
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

import serve


@pytest.fixture
def isolated_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Keep the real app lifecycle but make every external startup edge inert."""

    monkeypatch.setenv("A11OY_EVAL_AUTORUN_INTERVAL_SEC", "3600")
    monkeypatch.setenv("A11OY_EVAL_AUTORUN_INITIAL_DELAY_SEC", "3600")
    monkeypatch.setenv("A11OY_SERIES_A_STARTUP_REFRESH", "0")
    monkeypatch.setenv("A11OY_EVAL_RERUN_MIN_INTERVAL_SEC", "60")
    monkeypatch.setenv(
        "A11OY_EVAL_CREDENTIALS_JSON",
        json.dumps(
            {
                "version": 1,
                "credentials": [
                    {
                        "owner_id": "eval-operator",
                        "namespace": "a11oy",
                        "key_id": "eval-key-1",
                        "token": "eval-test-token",
                        "scopes": ["eval:run"],
                    }
                ],
            }
        ),
    )
    monkeypatch.delenv("A11OY_EVAL_PRINCIPALS_JSON", raising=False)

    # A missing script exercises the application's honest Node-unavailable path.
    # Popen is also guarded so a future refactor cannot silently launch a process.
    monkeypatch.setattr(serve, "A11OY_SERVE_SCRIPT", tmp_path / "missing-serve.ts")
    popen_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def forbidden_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        raise AssertionError("Node subprocess must be mocked in runtime tests")

    monkeypatch.setattr(subprocess, "Popen", forbidden_popen)

    # Energy autostart is the only startup hook that can probe remote lungs.
    # Replace that boundary with an explicit, observable unavailable receipt.
    import szl_energy_operator

    energy_calls: list[float] = []

    def mocked_energy_autostart():
        energy_calls.append(time.perf_counter())
        return {
            "running": False,
            "state": "UNAVAILABLE_TEST_BOUNDARY",
            "reachable_lungs": 0,
        }

    monkeypatch.setattr(
        szl_energy_operator,
        "autostart_if_lung_reachable",
        mocked_energy_autostart,
    )

    # No scheduler may leak between contexts or tests.  Snapshot history because
    # the real history route below intentionally mutates the in-memory ring.
    serve._a11oy_eval_autorun_stop()
    with serve._A11OY_EVAL_HIST_LOCK:
        original_history = list(serve._A11OY_EVAL_HIST)
        serve._A11OY_EVAL_HIST.clear()
    with serve._A11OY_EVAL_AUTORUN_LOCK:
        serve._A11OY_EVAL_AUTORUN_THREAD = None
        serve._A11OY_EVAL_AUTORUN_STARTED = False
        serve._A11OY_EVAL_AUTORUN_STOP = threading.Event()
    with serve._A11OY_EVAL_AUTH_LOCK:
        serve._A11OY_EVAL_AUTH_REGISTRY = None
        serve._A11OY_EVAL_AUTH_FINGERPRINT = None
    with serve._A11OY_EVAL_RERUN_RATE_LOCK:
        serve._A11OY_EVAL_RERUN_LAST.clear()
        serve._A11OY_EVAL_RERUN_PENDING.clear()
    serve._node_proc = None

    yield {"popen_calls": popen_calls, "energy_calls": energy_calls}

    serve._a11oy_eval_autorun_stop()
    with serve._A11OY_EVAL_HIST_LOCK:
        serve._A11OY_EVAL_HIST = collections.deque(
            original_history,
            maxlen=serve._A11OY_EVAL_HIST_MAX,
        )
    with serve._A11OY_EVAL_RERUN_RATE_LOCK:
        serve._A11OY_EVAL_RERUN_LAST.clear()
        serve._A11OY_EVAL_RERUN_PENDING.clear()
    with serve._A11OY_EVAL_AUTH_LOCK:
        serve._A11OY_EVAL_AUTH_REGISTRY = None
        serve._A11OY_EVAL_AUTH_FINGERPRINT = None
    serve._node_proc = None


def test_real_lifespan_restarts_eval_scheduler_generation(isolated_runtime):
    async def scenario():
        generations = []
        durations = []
        for _ in range(2):
            started_at = time.perf_counter()
            async with serve.app.router.lifespan_context(serve.app):
                durations.append(time.perf_counter() - started_at)
                thread = serve._A11OY_EVAL_AUTORUN_THREAD
                stop_event = serve._A11OY_EVAL_AUTORUN_STOP
                assert serve._A11OY_EVAL_AUTORUN_STARTED is True
                assert thread is not None and thread.is_alive()
                assert not stop_event.is_set()
                generations.append((thread, stop_event))

            assert stop_event.is_set()
            assert not thread.is_alive()
            assert serve._A11OY_EVAL_AUTORUN_STARTED is False

        assert generations[1][0] is not generations[0][0]
        assert generations[1][1] is not generations[0][1]
        return durations

    durations = asyncio.run(scenario())
    assert isolated_runtime["popen_calls"] == []
    assert len(isolated_runtime["energy_calls"]) == 2
    # Boundary mocks should leave lifecycle execution small; this makes a future
    # accidental live probe visible without treating a specific CPU speed as truth.
    assert max(durations) < 5.0


def test_operator_routes_fail_closed_and_rerun_keeps_health_responsive(
    isolated_runtime,
    monkeypatch: pytest.MonkeyPatch,
):
    worker_started = threading.Event()
    worker_release = threading.Event()

    def blocked_live_run(triggered_by=None):
        worker_started.set()
        if not worker_release.wait(5):
            raise TimeoutError("test did not release blocked live evaluation")
        return {
            "run_id": "runtime-integration-live-run",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "live",
            "triggered_by": triggered_by,
        }

    monkeypatch.setattr(
        serve,
        "_a11oy_eval_run_live_serialized",
        blocked_live_run,
    )

    async def scenario():
        async with serve.app.router.lifespan_context(serve.app):
            transport = httpx.ASGITransport(app=serve.app, raise_app_exceptions=True)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://a11oy-runtime.test",
            ) as client:
                # Required ledger/export surfaces are operational live-empty,
                # never the deterministic SAMPLE chain. Repeated export GETs
                # stay byte-for-byte equivalent and never mint a receipt.
                sample_ledger = (await client.get("/api/a11oy/v1/ledger")).json()
                export_one = (await client.get("/api/a11oy/v1/receipt/export")).json()
                export_two = (await client.get("/api/a11oy/v1/receipt/export")).json()
                assert sample_ledger["data_kind"] == "live"
                assert sample_ledger["operational"] is True
                assert sample_ledger["count"] == 0
                assert sample_ledger["receipts"] == []
                assert sample_ledger["structure_verified"] is True
                assert export_one == export_two
                assert export_one["state"] == "live"
                assert export_one["data_kind"] == "live"
                assert export_one["operational"] is True
                assert export_one["receipt_minted"] is False

                # Method safety is enforced by the actual router, not a source check.
                with serve._A11OY_EVAL_HIST_LOCK:
                    history_before_get = list(serve._A11OY_EVAL_HIST)
                get_rerun = await client.get("/api/a11oy/v1/eval-arena/rerun")
                assert get_rerun.status_code == 405
                assert get_rerun.headers["allow"] == "POST"
                assert worker_started.is_set() is False
                with serve._A11OY_EVAL_HIST_LOCK:
                    assert list(serve._A11OY_EVAL_HIST) == history_before_get

                denied = await client.post("/api/a11oy/v1/eval-arena/rerun")
                assert denied.status_code == 401
                assert denied.headers["www-authenticate"] == "Bearer"
                assert worker_started.is_set() is False

                # Missing, stale, and future-dated evidence all fail closed through
                # the production history endpoint.
                with serve._A11OY_EVAL_HIST_LOCK:
                    serve._A11OY_EVAL_HIST.clear()
                missing = (
                    await client.get("/api/a11oy/v1/eval-arena/history")
                ).json()
                assert missing["freshness"]["status"] == "unavailable"
                assert missing["latest_run_at"] is None

                now = datetime.now(timezone.utc)
                with serve._A11OY_EVAL_HIST_LOCK:
                    serve._A11OY_EVAL_HIST.append(
                        {
                            "timestamp": (now - timedelta(hours=25)).isoformat(),
                            "mode": "live",
                        }
                    )
                stale = (
                    await client.get("/api/a11oy/v1/eval-arena/history")
                ).json()
                assert stale["freshness"]["status"] == "stale"
                assert stale["latest_run_age_s"] >= 25 * 3600

                with serve._A11OY_EVAL_HIST_LOCK:
                    serve._A11OY_EVAL_HIST.clear()
                    serve._A11OY_EVAL_HIST.append(
                        {
                            "timestamp": (now + timedelta(minutes=10)).isoformat(),
                            "mode": "live",
                        }
                    )
                future = (
                    await client.get("/api/a11oy/v1/eval-arena/history")
                ).json()
                assert future["freshness"]["status"] == "unavailable"
                assert "future clock skew" in future["freshness"]["reason"]

                # Block the synchronous evaluator after it enters AnyIO's worker
                # pool, then prove the application event loop can still serve health.
                rerun_task = asyncio.create_task(
                    client.post(
                        "/api/a11oy/v1/eval-arena/rerun",
                        headers={"Authorization": "Bearer eval-test-token"},
                    )
                )
                for _ in range(200):
                    if worker_started.is_set():
                        break
                    await asyncio.sleep(0.01)
                assert worker_started.is_set(), "rerun never entered worker thread"

                health_started = time.perf_counter()
                try:
                    health = await asyncio.wait_for(
                        client.get("/health/live"),
                        timeout=1.0,
                    )
                finally:
                    worker_release.set()
                health_elapsed = time.perf_counter() - health_started
                rerun = await asyncio.wait_for(rerun_task, timeout=2.0)

                assert health.status_code == 200
                assert health_elapsed < 1.0
                assert rerun.status_code == 200
                assert rerun.json()["run_id"] == "runtime-integration-live-run"
                assert rerun.json()["triggered_by"] == {
                    "actor_type": "credential",
                    "owner_id": "eval-operator",
                    "namespace": "a11oy",
                    "key_id": "eval-key-1",
                }

                rate_limited = await client.post(
                    "/api/a11oy/v1/eval-arena/rerun",
                    headers={"Authorization": "Bearer eval-test-token"},
                )
                assert rate_limited.status_code == 429
                assert int(rate_limited.headers["retry-after"]) >= 1

                with serve._A11OY_EVAL_RERUN_RATE_LOCK:
                    serve._A11OY_EVAL_RERUN_LAST.clear()

                def failed_live_run(triggered_by=None):
                    raise RuntimeError("bounded test evaluator failure")

                monkeypatch.setattr(
                    serve,
                    "_a11oy_eval_run_live_serialized",
                    failed_live_run,
                )
                failed = await client.post(
                    "/api/a11oy/v1/eval-arena/rerun",
                    headers={"Authorization": "Bearer eval-test-token"},
                )
                assert failed.status_code == 503
                assert failed.json()["mode"] == "recorded"
                assert failed.json()["state"] == "unavailable"

    try:
        asyncio.run(scenario())
    finally:
        worker_release.set()

    assert isolated_runtime["popen_calls"] == []
    assert len(isolated_runtime["energy_calls"]) == 1
