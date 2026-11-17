# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Worker-thread read paths must retain one cache and one refresh per observation."""
import ast
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

import szl_backend_hardening as bh
import szl_frontier_manifest as manifest


class ObservedLock:
    """Signal callers before they wait, without changing lock ownership semantics."""
    def __init__(self, expected):
        self.lock = threading.Lock()
        self.count_lock = threading.Lock()
        self.expected = expected
        self.attempts = 0
        self.joined = threading.Event()

    def __enter__(self):
        with self.count_lock:
            self.attempts += 1
            if self.attempts == self.expected:
                self.joined.set()
        self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


@pytest.mark.parametrize("failed", [False, True])
def test_sovereign_rollup_coalesces_misses_and_keeps_expiry_and_errors(monkeypatch, failed):
    clock = [100.0]
    lock = ObservedLock(expected=3)
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def rollup():
        calls.append("probe")
        entered.set()
        assert release.wait(5)
        if failed:
            raise RuntimeError("synthetic probe failure")
        return {"reachable": False, "label": "UNAVAILABLE"}

    monkeypatch.setitem(sys.modules, "szl_sovereign_panel", SimpleNamespace(rollup_signal=rollup))
    source = Path(__file__).resolve().parents[1] / "serve.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_sovereign_health_signal")
    scope = {"_SOVEREIGN_HZ_CACHE": {}, "_SOVEREIGN_HZ_LOCK": lock,
             "_hz_time": SimpleNamespace(time=lambda: clock[0])}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
    signal = scope["_sovereign_health_signal"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        leader = pool.submit(signal)
        try:
            assert entered.wait(2)
            followers = [pool.submit(signal) for _ in range(2)]
            assert lock.joined.wait(2)
        finally:
            release.set()
        results = [f.result(timeout=2) for f in [leader, *followers]]
    assert calls == ["probe"]
    assert all(value is results[0] for value in results)
    assert results[0]["reachable"] is False
    assert results[0]["label"] == "UNAVAILABLE"
    if failed:
        assert results[0]["error"] == "RuntimeError"
    clock[0] = 129.0
    assert signal() is results[0]
    assert len(calls) == 1
    clock[0] = 130.0
    signal()
    assert len(calls) == 2


def test_concurrent_first_manifest_readers_share_one_per_app_cache(monkeypatch):
    app = FastAPI()
    lock = ObservedLock(expected=2)
    entered = threading.Event()
    release = threading.Event()
    real_cache = bh.TTLCache
    calls = []

    def create_cache(*args, **kwargs):
        calls.append("create")
        entered.set()
        assert release.wait(5)
        return real_cache(*args, **kwargs)

    monkeypatch.setattr(manifest, "_MANIFEST_CACHE_LOCK", lock)
    monkeypatch.setattr(bh, "TTLCache", create_cache)
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(manifest._manifest_cache, app)
        try:
            assert entered.wait(2)
            follower = pool.submit(manifest._manifest_cache, app)
            assert lock.joined.wait(2)
        finally:
            release.set()
        first, second = leader.result(timeout=2), follower.result(timeout=2)
    assert first is second is app.state.szl_frontier_manifest_cache
    assert calls == ["create"]
    assert manifest._manifest_cache(FastAPI()) is not first
