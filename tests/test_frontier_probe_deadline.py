#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Actual catalogue probes keep caller deadlines and bounded worker admission."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.requests import Request

import szl_frontier_index as frontier


@pytest.fixture
def pools(monkeypatch):
    created = []
    releases = []

    def make(workers=2, capacity=2):
        pool = frontier._RouteProbePool(workers, capacity)
        created.append(pool)
        monkeypatch.setattr(frontier, "_PROBE_POOL", pool)
        return pool

    def blocked():
        entered, release = threading.Event(), threading.Event()
        releases.append(release)

        def work():
            entered.set()
            assert release.wait(5), "synthetic worker was not released"
            return {"label": "SAMPLE"}

        return SimpleNamespace(endpoint=work), entered, release

    yield make, blocked
    for release in releases:
        release.set()
    for pool in created:
        assert pool.shutdown(timeout=2), "test leaked a synthetic probe worker"


def invoke(route, timeout=0.05, diagnostics=None):
    return frontier._invoke_route(None, route, "/api/a11oy/v1/fixture/health",
                                  timeout, diagnostics=diagnostics)


def wait_idle(pool):
    deadline = time.monotonic() + 2
    while pool._queue.unfinished_tasks and time.monotonic() < deadline:
        time.sleep(0.005)
    assert pool._queue.unfinished_tasks == 0


def test_caller_returns_at_deadline_while_running_work_keeps_its_slot(pools):
    make, blocked = pools
    pool = make(workers=1, capacity=1)
    route, entered, release = blocked()
    diagnostics = []
    start = time.monotonic()
    assert invoke(route, diagnostics=diagnostics) is None
    assert time.monotonic() - start < 0.6
    assert entered.wait(1)
    assert diagnostics == [{
        "endpoint": "/api/a11oy/v1/fixture/health", "state": "TIMEOUT",
        "cancelled_before_start": False, "worker_may_continue": True,
        "running_work_cancelled": False,
    }]
    assert pool._queue.unfinished_tasks == 1
    assert len(pool._threads) == 1 and pool._threads[0].is_alive()
    assert pool._threads[0].daemon is True
    # A timeout must not free capacity while this same worker is still running.
    other = []
    assert invoke(SimpleNamespace(endpoint=lambda: {"label": "LIVE"}), diagnostics=other) is None
    assert other[0]["state"] == "SATURATED"
    release.set()
    wait_idle(pool)
    assert invoke(SimpleNamespace(endpoint=lambda: {"label": "MODELED"})) == {"label": "MODELED"}


def test_response_access_is_covered_by_the_same_caller_deadline(pools):
    make, blocked = pools
    pool = make(workers=1, capacity=1)
    blocker, entered, release = blocked()

    class SlowResponse:
        @property
        def body(self):
            blocker.endpoint()
            return b'{"label":"SAMPLE"}'

    start = time.monotonic()
    diagnostics = []
    assert invoke(SimpleNamespace(endpoint=SlowResponse), diagnostics=diagnostics) is None
    assert time.monotonic() - start < 0.6
    assert entered.wait(1)
    assert diagnostics[0]["state"] == "TIMEOUT"
    release.set()
    wait_idle(pool)


def test_repeated_timeouts_and_saturation_do_not_create_more_workers_or_queue_entries(pools):
    make, blocked = pools
    pool = make(workers=2, capacity=2)
    for _ in range(2):
        route, entered, _ = blocked()
        assert invoke(route) is None
        assert entered.wait(1)
    thread_ids = {thread.ident for thread in pool._threads}
    called = []
    start = time.monotonic()
    for _ in range(100):
        diagnostics = []
        result = invoke(SimpleNamespace(endpoint=lambda: called.append(True)), diagnostics=diagnostics)
        assert result is None and diagnostics[0]["state"] == "SATURATED"
    assert time.monotonic() - start < 1
    assert called == []
    assert len(pool._threads) == 2
    assert {thread.ident for thread in pool._threads} == thread_ids
    assert pool._queue.unfinished_tasks == 2


def test_queued_timeout_cancels_before_start_and_capacity_recovers_after_drain(pools):
    make, blocked = pools
    pool = make(workers=1, capacity=2)
    route, entered, release = blocked()
    assert invoke(route) is None
    assert entered.wait(1)
    called = []
    diagnostics = []
    assert invoke(SimpleNamespace(endpoint=lambda: called.append(True)),
                  diagnostics=diagnostics) is None
    assert diagnostics[0]["state"] == "TIMEOUT"
    assert diagnostics[0]["cancelled_before_start"] is True
    assert diagnostics[0]["worker_may_continue"] is False
    assert pool._queue.unfinished_tasks == 2
    release.set()
    wait_idle(pool)
    assert called == []
    assert invoke(SimpleNamespace(endpoint=lambda: {"label": "SAMPLE"})) == {"label": "SAMPLE"}
    assert len(pool._threads) == 1


def test_worker_exception_releases_capacity_without_claiming_a_label(pools):
    make, _ = pools
    pool = make(workers=1, capacity=1)

    def fail():
        raise RuntimeError("synthetic failure")

    diagnostics = []
    assert invoke(SimpleNamespace(endpoint=fail), diagnostics=diagnostics) is None
    assert diagnostics[0]["state"] == "ERROR"
    assert diagnostics[0]["error_class"] == "RuntimeError"
    wait_idle(pool)
    assert invoke(SimpleNamespace(endpoint=lambda: {"label": "UNAVAILABLE"})) == {"label": "UNAVAILABLE"}
    assert len(pool._threads) == 1


def test_async_callable_and_synthetic_get_request_keep_existing_contract(pools):
    make, _ = pools
    make(workers=1, capacity=1)

    async def endpoint(request: Request):
        return {"label": "MODELED", "method": request.method,
                "path": request.url.path, "headers": dict(request.headers)}

    payload = invoke(SimpleNamespace(endpoint=endpoint))
    assert payload == {"label": "MODELED", "method": "GET",
                       "path": "/api/a11oy/v1/fixture/health", "headers": {}}


def test_missing_required_argument_is_declined_without_starting_a_worker(pools):
    make, _ = pools
    pool = make()

    def endpoint(required_model):
        raise AssertionError("required argument must not be invented")

    diagnostics = []
    assert invoke(SimpleNamespace(endpoint=endpoint), diagnostics=diagnostics) is None
    assert diagnostics[0]["state"] == "REQUIRED_ARGUMENT_UNAVAILABLE"
    assert pool._threads == []


def test_catalogue_preserves_route_selection_and_verbatim_labels(pools):
    make, _ = pools
    make()
    app = FastAPI()

    @app.get("/api/a11oy/v1/fixture/health")
    def get_fixture():
        return {"label": "SAMPLE"}

    @app.post("/api/a11oy/v1/fixture/write")
    def post_fixture():
        raise AssertionError("catalogue must not execute a write")

    paths = frontier._registered_get_paths(app, "a11oy")
    assert "/api/a11oy/v1/fixture/write" not in paths
    result = frontier._classify_surface(app, {"id": "fixture", "title": "Fixture"}, paths, "a11oy")
    assert result["backend"] == frontier.NATIVE
    assert result["label"] == "SAMPLE"
    assert result["endpoint"] == "/api/a11oy/v1/fixture/health"
    assert "probe_failures" not in result


def test_catalogue_saturation_is_unavailable_with_explicit_diagnostic(pools):
    make, blocked = pools
    make(workers=1, capacity=1)
    route, entered, _ = blocked()
    assert invoke(route) is None
    assert entered.wait(1)
    app = FastAPI()

    @app.get("/api/a11oy/v1/fixture/health")
    def fixture():
        raise AssertionError("saturated probe must not execute")

    paths = frontier._registered_get_paths(app, "a11oy")
    result = frontier._classify_surface(app, {"id": "fixture"}, paths, "a11oy")
    assert result["label"] == "UNAVAILABLE"
    assert result["backend"] == frontier.FALLBACK
    assert result["probe_failures"] == [
        {"endpoint": "/api/a11oy/v1/fixture/health", "state": "SATURATED"}]


def test_singleton_initialization_is_locked_and_starts_no_import_time_workers(monkeypatch):
    monkeypatch.setattr(frontier, "_PROBE_POOL", None)
    with ThreadPoolExecutor(max_workers=8) as callers:
        instances = list(callers.map(lambda _: frontier._get_probe_pool(), range(32)))
    pool = instances[0]
    try:
        assert all(instance is pool for instance in instances)
        assert pool._threads == []
    finally:
        assert pool.shutdown()


def test_closed_pool_declines_without_new_threads(pools):
    make, _ = pools
    pool = make(workers=1, capacity=1)
    assert pool.shutdown()
    diagnostics = []
    assert invoke(SimpleNamespace(endpoint=lambda: {"label": "LIVE"}), diagnostics=diagnostics) is None
    assert diagnostics[0]["state"] == "SATURATED"
    assert pool._threads == []


@pytest.mark.parametrize("timeout", [0, -1, True, "3", float("inf"), float("nan"), 1e100, 10 ** 1000])
def test_invalid_or_unrepresentable_timeout_never_starts_work(pools, timeout):
    make, _ = pools
    pool = make()
    diagnostics = []
    route = SimpleNamespace(endpoint=lambda: {"label": "LIVE"})
    assert invoke(route, timeout=timeout, diagnostics=diagnostics) is None
    assert diagnostics[0]["state"] == "INVALID_TIMEOUT"
    assert pool._threads == []
