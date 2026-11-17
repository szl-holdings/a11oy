# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Concurrent probe readers share one refresh and never republish invalidated evidence."""
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

import szl_backend_hardening as bh


def watch_waiters(monkeypatch, expected):
    joined = threading.Event()
    lock = threading.Lock()
    count = 0

    class ObservedFuture(Future):
        def result(self, timeout=None):
            nonlocal count
            with lock:
                count += 1
                if count == expected:
                    joined.set()
            return super().result(timeout)

    monkeypatch.setattr(bh, "Future", ObservedFuture, raising=False)
    return joined


@pytest.mark.parametrize("expired", [False, True])
def test_same_key_shares_refresh_while_other_keys_remain_available(monkeypatch, expired):
    cache = bh.TTLCache(ttl=30)
    if expired:
        cache._store["blocked"] = ({"generation": "old"}, time.monotonic() - 60)
    entered = threading.Event()
    release = threading.Event()
    joined = watch_waiters(monkeypatch, expected=3)
    calls = []

    def produce():
        calls.append("probe")
        entered.set()
        assert release.wait(5), "test did not release probe"
        return {"generation": "fresh", "reachable": False}

    with ThreadPoolExecutor(max_workers=5) as pool:
        leader = pool.submit(cache.get_or_compute, produce, "blocked")
        try:
            assert entered.wait(2)
            followers = [pool.submit(cache.get_or_compute, produce, "blocked") for _ in range(3)]
            all_joined = joined.wait(2)
            other = pool.submit(cache.get_or_compute, lambda: {"key": "other"}, "other")
            assert other.result(timeout=2)["key"] == "other"
            assert cache.peek("blocked") is None
        finally:
            release.set()
        results = [future.result(timeout=2) for future in [leader, *followers]]
    assert all_joined, "concurrent misses did not join the existing refresh"
    assert calls == ["probe"]
    assert all(value is results[0] for value in results)
    assert results[0]["generation"] == "fresh"
    assert results[0]["reachable"] is False
    assert "cached_at" in results[0]


def test_failed_refresh_releases_every_waiter_and_allows_retry(monkeypatch):
    cache = bh.TTLCache(ttl=30)
    entered = threading.Event()
    release = threading.Event()
    joined = watch_waiters(monkeypatch, expected=1)
    failure = RuntimeError("synthetic probe failure")
    calls = []

    def fail():
        calls.append("probe")
        entered.set()
        assert release.wait(5)
        raise failure

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(cache.get_or_compute, fail)
        try:
            assert entered.wait(2)
            follower = pool.submit(cache.get_or_compute, fail)
            all_joined = joined.wait(2)
        finally:
            release.set()
        for future in (leader, follower):
            with pytest.raises(RuntimeError, match="synthetic probe failure") as caught:
                future.result(timeout=2)
            assert caught.value is failure
    assert all_joined
    assert calls == ["probe"]
    assert cache.peek() is None
    assert cache.get_or_compute(lambda: "recovered") == "recovered"


def test_invalidation_during_refresh_discards_old_evidence_before_retry(monkeypatch):
    cache = bh.TTLCache(ttl=30)
    entered = threading.Event()
    release = threading.Event()
    joined = watch_waiters(monkeypatch, expected=1)
    calls = []

    def produce():
        calls.append("probe")
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
            return {"generation": "invalidated", "ready": True}
        return {"generation": "current", "ready": False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(cache.get_or_compute, produce)
        try:
            assert entered.wait(2)
            follower = pool.submit(cache.get_or_compute, produce)
            assert joined.wait(2)
            cache.invalidate()
            assert cache.peek() is None
        finally:
            release.set()
        values = [future.result(timeout=2) for future in (leader, follower)]
    assert len(calls) == 2
    assert all(value["generation"] == "current" and value["ready"] is False for value in values)
    assert cache.peek() == values[0]


@pytest.mark.parametrize("change", ["invalidate", "expire"])
def test_delayed_waiter_rechecks_freshness_before_returning(monkeypatch, change):
    from types import SimpleNamespace

    clock = [100.0]
    monkeypatch.setattr(bh, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    waiting = threading.Event()
    obtained = threading.Event()
    resume = threading.Event()
    entered = threading.Event()
    release = threading.Event()

    class DelayedFuture(Future):
        def result(self, timeout=None):
            waiting.set()
            result = super().result(timeout)
            obtained.set()
            assert resume.wait(5)
            return result

    monkeypatch.setattr(bh, "Future", DelayedFuture)
    cache = bh.TTLCache(ttl=30)

    def old_probe():
        entered.set()
        assert release.wait(5)
        return {"generation": "old"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(cache.get_or_compute, old_probe)
        try:
            assert entered.wait(2)
            follower = pool.submit(cache.get_or_compute, old_probe)
            assert waiting.wait(2)
            release.set()
            assert leader.result(timeout=2)["generation"] == "old"
            assert obtained.wait(2)
            if change == "invalidate":
                cache.invalidate()
            else:
                clock[0] = 131.0
            fresh = cache.get_or_compute(lambda: {"generation": "fresh"})
        finally:
            release.set()
            resume.set()
        assert follower.result(timeout=2) is fresh
