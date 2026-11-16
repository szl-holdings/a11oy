# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Prove network denial and bounded real route probes without replacing backends."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / ".github/scripts/frontier_index_honesty_check.py"


def _checker():
    spec = importlib.util.spec_from_file_location("frontier_honesty_test", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Audit hooks last for the process. Exercise real stdlib calls in fresh children
# so the pytest runner retains its own unrelated transport policy.
_PRELUDE = r"""
import importlib.util, json, socket, sys, urllib.request
spec = importlib.util.spec_from_file_location('frontier_honesty_child', sys.argv[1])
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
"""


def _child(code):
    result = subprocess.run(
        [sys.executable, "-I", "-c", _PRELUDE + code, str(CHECKER)],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("operation", [
    "socket.getaddrinfo('example.invalid', 443)",
    "socket.gethostbyname('example.invalid')",
    "socket.gethostbyaddr('192.0.2.1')",
    "socket.getnameinfo(('192.0.2.1', 443), 0)",
    "socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
    "socket.socket(socket.AF_INET6, socket.SOCK_STREAM)",
    "socket.socket(socket.AF_INET, socket.SOCK_DGRAM)",
    "urllib.request.urlopen('https://example.invalid/', timeout=1)",
])
def test_real_dns_and_internet_clients_are_denied(operation):
    result = _child("""
guard._install_no_network_guard()
guard._install_no_network_guard()
try:
    """ + operation + """
except OSError as exc:
    assert 'frontier contract denies outbound network' in str(exc), repr(exc)
else:
    raise AssertionError('Internet operation was not denied')
assert guard._BLOCKED_NETWORK_ATTEMPTS
print(json.dumps({'blocked': True}))
""")
    assert result == {"blocked": True}


@pytest.mark.parametrize("operation,socket_kind", [
    ("sock.connect(('192.0.2.1', 443))", "SOCK_STREAM"),
    ("sock.connect_ex(('192.0.2.1', 443))", "SOCK_STREAM"),
    ("sock.sendto(b'probe', ('192.0.2.1', 443))", "SOCK_DGRAM"),
    ("sock.sendmsg([b'probe'], [], 0, ('192.0.2.1', 443))", "SOCK_DGRAM"),
])
def test_preexisting_socket_cannot_escape_the_boundary(operation, socket_kind):
    result = _child("\nsock = socket.socket(socket.AF_INET, socket." + socket_kind + ")\n" + """
guard._install_no_network_guard()
try:
    """ + operation + """
except PermissionError as exc:
    assert 'frontier contract denies outbound network' in str(exc)
else:
    raise AssertionError('preexisting socket escaped the boundary')
finally:
    sock.close()
print(json.dumps({'blocked': True}))
""")
    assert result == {"blocked": True}


def test_threads_are_denied_but_real_local_asgi_and_socketpairs_work():
    result = _child("""
import concurrent.futures
from fastapi import FastAPI
from starlette.testclient import TestClient
guard._install_no_network_guard()
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(socket.getaddrinfo, 'example.invalid', 443)
    try:
        future.result(timeout=2)
    except PermissionError:
        pass
    else:
        raise AssertionError('worker thread escaped the boundary')
left, right = socket.socketpair()
try:
    left.sendall(b'local')
    assert right.recv(5) == b'local'
finally:
    left.close()
    right.close()
app = FastAPI()
@app.get('/probe')
def route():
    return {'label': 'MODELED', 'citations': ['arXiv:2401.00001']}
with TestClient(app) as client:
    assert guard.probe_backend(app, client, '/probe') == route()
print(json.dumps({'thread_denied': True, 'real_asgi': True, 'socketpair': True}))
""")
    assert result == {"thread_denied": True, "real_asgi": True, "socketpair": True}


@pytest.mark.parametrize("claimed,emitted", [("LIVE", "SAMPLE"), ("SAMPLE", "LIVE")])
def test_network_policy_never_excuses_independently_observed_label_drift(claimed, emitted):
    guard = _checker()
    catalog = {
        "ok": True, "label": "MODELED", "surfaces": [{
            "id": "anatomy", "backend": "a11oy-native", "label": claimed,
            "endpoint": "/api/a11oy/v1/ecosystem/anatomy", "citations": [],
        }],
    }
    actual = {"label": emitted}
    violations = guard.find_violations(catalog, lambda _path: actual)
    assert len(violations) == 1
    assert "LABEL DRIFT" in violations[0]


def test_all_existing_and_new_negative_controls_still_pass():
    assert _checker()._selftest() == 0


def test_route_probe_timeout_returns_before_the_handler_finishes():
    import threading
    import time
    from types import SimpleNamespace
    import szl_frontier_index as frontier
    __import__("starlette.requests")

    release = threading.Event()
    workers = []
    def blocked():
        workers.append(threading.current_thread())
        release.wait(1)
        return {"label": "SAMPLE"}
    try:
        started = time.monotonic()
        result = frontier._invoke_route(object(), SimpleNamespace(endpoint=blocked), "/probe", 0.03)
        elapsed = time.monotonic() - started
        assert result is None
        assert elapsed < 0.4, "caller waited for the abandoned handler to finish"
        assert workers and workers[0].is_alive()
    finally:
        release.set()
        for worker in workers:
            worker.join(timeout=2)


import asyncio
import threading
import time
from types import SimpleNamespace

import szl_frontier_index as frontier


@pytest.fixture
def route_probes(monkeypatch):
    registry = frontier._RouteProbeRegistry()
    monkeypatch.setattr(frontier, "_ROUTE_PROBES", registry)
    __import__("starlette.requests")
    return registry


def _release_probes(release, workers):
    release.set()
    for worker in tuple(workers):
        worker.join(timeout=2)
        assert not worker.is_alive(), "released read-probe worker did not finish"


def test_route_probe_capacity_covers_timed_out_work_and_recovers(route_probes):
    release, workers = threading.Event(), []
    def blocked():
        workers.append(threading.current_thread())
        release.wait(3)
        return {"label": "SAMPLE"}
    app, other_app = object(), object()
    route = SimpleNamespace(endpoint=blocked)
    other_route = SimpleNamespace(endpoint=blocked)
    keys = [(app, route, "/one"), (other_app, route, "/one"),
            (app, other_route, "/one"), (app, route, "/two")]
    available_calls = []
    def available():
        available_calls.append(True)
        return {"label": "MODELED"}
    available_route = SimpleNamespace(endpoint=available)
    try:
        for owner, selected, path in keys:
            assert frontier._invoke_route(owner, selected, path, 0.1) is None
        assert len(workers) == 4
        assert all(worker.daemon and worker.is_alive() for worker in workers)
        started = time.monotonic()
        assert frontier._invoke_route(app, available_route, "/available", 1) is None
        assert time.monotonic() - started < 0.2
        assert available_calls == []
        assert len(workers) == 4
    finally:
        _release_probes(release, workers)
    assert frontier._invoke_route(app, available_route, "/available", 1) == {"label": "MODELED"}
    assert available_calls == [True]


def test_route_probe_duplicate_after_timeout_refuses_late_result_and_retries_fresh(route_probes):
    release, workers, calls = threading.Event(), [], []
    def endpoint():
        calls.append(True)
        workers.append(threading.current_thread())
        if len(calls) == 1:
            release.wait(3)
            return {"label": "SAMPLE"}
        return {"label": "MODELED"}
    app, route = object(), SimpleNamespace(endpoint=endpoint)
    try:
        assert frontier._invoke_route(app, route, "/probe", 0.1) is None
        started = time.monotonic()
        for _ in range(5):
            assert frontier._invoke_route(app, route, "/probe", 1) is None
        assert time.monotonic() - started < 0.2
        assert calls == [True]
    finally:
        _release_probes(release, workers)
    assert frontier._invoke_route(app, route, "/probe", 1) == {"label": "MODELED"}
    assert len(calls) == 2


def test_route_probe_changed_callable_cannot_reuse_an_old_invocation(route_probes):
    release, workers, calls = threading.Event(), [], []
    def old():
        calls.append("old")
        workers.append(threading.current_thread())
        release.wait(3)
        return {"label": "SAMPLE"}
    def replacement():
        calls.append("replacement")
        return {"label": "MODELED"}
    app, route = object(), SimpleNamespace(endpoint=old)
    try:
        assert frontier._invoke_route(app, route, "/probe", 0.1) is None
        route.endpoint = replacement
        assert frontier._invoke_route(app, route, "/probe", 1) == {"label": "MODELED"}
        assert calls == ["old", "replacement"]
    finally:
        _release_probes(release, workers)


def test_route_probe_decode_holds_capacity_until_completion(route_probes):
    route_probes.capacity = 1
    release, workers = threading.Event(), []
    class SlowBody:
        @property
        def body(self):
            workers.append(threading.current_thread())
            release.wait(3)
            return b'{"label":"SAMPLE"}'
    app = object()
    route = SimpleNamespace(endpoint=lambda: SlowBody())
    other_calls = []
    def other():
        other_calls.append(True)
        return {"label": "MODELED"}
    other_route = SimpleNamespace(endpoint=other)
    try:
        started = time.monotonic()
        assert frontier._invoke_route(app, route, "/decode", 0.1) is None
        assert time.monotonic() - started < 0.4
        assert workers and workers[0].is_alive()
        assert frontier._invoke_route(app, route, "/decode", 1) is None
        assert frontier._invoke_route(app, other_route, "/other", 1) is None
        assert other_calls == []
    finally:
        _release_probes(release, workers)
    assert frontier._invoke_route(app, other_route, "/other", 1) == {"label": "MODELED"}


@pytest.mark.parametrize("failure", ["handler", "start"])
def test_route_probe_failure_releases_capacity(route_probes, monkeypatch, failure):
    route_probes.capacity = 1
    app = object()
    def broken():
        raise RuntimeError("private provider exception")
    if failure == "handler":
        assert frontier._invoke_route(app, SimpleNamespace(endpoint=broken), "/broken", 1) is None
    else:
        class FailedThread:
            def __init__(self, **kwargs):
                pass
            def start(self):
                raise RuntimeError("thread cannot start")
        with monkeypatch.context() as scoped:
            scoped.setattr(frontier.threading, "Thread", FailedThread)
            assert frontier._invoke_route(app, SimpleNamespace(endpoint=broken), "/broken", 1) is None
    route = SimpleNamespace(endpoint=lambda: {"label": "SAMPLE"})
    assert frontier._invoke_route(app, route, "/recovered", 1) == {"label": "SAMPLE"}


def test_route_probe_reentrant_same_route_refuses_without_deadlock(route_probes):
    app, calls = object(), []
    def endpoint():
        calls.append(True)
        assert frontier._invoke_route(app, route, "/recursive", 1) is None
        return {"label": "SAMPLE"}
    route = SimpleNamespace(endpoint=endpoint)
    assert frontier._invoke_route(app, route, "/recursive", 0.3) == {"label": "SAMPLE"}
    assert calls == [True]


def test_route_probe_async_handler_keeps_request_and_label_contract(route_probes):
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    app = object()
    async def endpoint(request: Request):
        await asyncio.sleep(0)
        assert request.app is app and request.url.path == "/async"
        return JSONResponse({"evidence": {"data_label": "SAMPLE"}, "label": "LIVE"})
    route = SimpleNamespace(endpoint=endpoint)
    payload = frontier._invoke_route(app, route, "/async", 1)
    assert payload == {"evidence": {"data_label": "SAMPLE"}, "label": "LIVE"}
    assert frontier._extract_label(payload) == "SAMPLE"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), 1e300, "invalid"])
def test_route_probe_invalid_deadline_does_not_start_work(route_probes, timeout):
    calls = []
    def endpoint():
        calls.append(True)
        return {"label": "SAMPLE"}
    assert frontier._invoke_route(object(), SimpleNamespace(endpoint=endpoint), "/probe", timeout) is None
    assert calls == []
