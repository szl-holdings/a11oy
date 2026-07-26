# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the bounded live-feed readiness endpoint."""

from __future__ import annotations

import asyncio
import json
import threading
import time

import a11oy_live_feeds
import serve


def test_feed_pulse_is_concurrent_bounded_and_honest_about_timeout(monkeypatch):
    active = 0
    active_lock = threading.Lock()
    all_workers_done = threading.Event()

    def fake_get_feed(feed, timeout_s=None):
        nonlocal active
        assert timeout_s == 0.15
        with active_lock:
            active += 1
        try:
            if feed == "celestrak":
                time.sleep(0.05)
                raise TimeoutError("cooperative test deadline")
            time.sleep(0.02)
            source, source_url = serve._kl_live._SOURCE[feed]
            return {
                "source": source,
                "source_url": source_url,
                "mode": "live",
                "fetched_at": serve._kl_live._now_iso(),
                "ttl_s": 60,
                "data": {"feed": feed},
            }
        finally:
            with active_lock:
                active -= 1
                if active == 0:
                    all_workers_done.set()

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    started = time.monotonic()
    response = asyncio.run(serve._feeds_pulse())
    elapsed = time.monotonic() - started
    payload = json.loads(response.body)

    assert elapsed < 0.75
    # The endpoint deadline can win the race against a cooperative worker by a
    # few scheduler ticks.  Require that such a worker exits promptly without
    # making the request wait for the abandoned thread.
    assert all_workers_done.wait(0.25)
    assert active == 0
    assert payload["feed_count"] == 7
    assert payload["live_count"] == 6
    assert payload["live_count"] + payload["cached_count"] + payload["down_count"] == 7
    assert payload["down_count"] == 1
    assert [item["feed"] for item in payload["items"]] == [
        "kev", "osv", "rekor", "iss", "celestrak", "prometheus", "fhir"
    ]
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "unavailable"
    assert timed_out["source_url"].startswith("https://")
    assert timed_out["fetched_at"] is None
    assert timed_out["payload_bytes"] == 0
    assert timed_out["error"] == "probe timeout after 0.15s"


def test_live_feed_budget_is_propagated_and_decreases_between_requests(monkeypatch):
    observed_timeouts = []

    def fake_http_get(_url, timeout=20, **_kwargs):
        observed_timeouts.append(timeout)
        time.sleep(0.01)
        return {"vulns": []}

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {})
    monkeypatch.setattr(a11oy_live_feeds, "_http_get", fake_http_get)

    payload = a11oy_live_feeds.get_feed("osv", timeout_s=0.20)

    assert payload["mode"] == "live"
    assert len(observed_timeouts) == 5
    assert 0 < observed_timeouts[-1] < observed_timeouts[0] <= 0.20 + 1e-6


def test_feed_pulse_counts_internally_caught_timeout_without_cache_as_down(monkeypatch):
    def timeout_fetch(_feed, deadline=None):
        raise TimeoutError("cooperative test deadline")

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {})
    monkeypatch.setattr(a11oy_live_feeds, "_fetch", timeout_fetch)
    monkeypatch.setattr(a11oy_live_feeds, "_load_snapshot", lambda _feed: None)
    unavailable = a11oy_live_feeds.get_feed("celestrak", timeout_s=0.15)

    assert unavailable["mode"] == "unavailable"
    assert unavailable["data"] is None
    assert "TimeoutError" in unavailable["error"]
    assert "cooperative test deadline" in unavailable["error"]

    def fake_get_feed(feed, timeout_s=None):
        assert timeout_s == 0.15
        if feed == "celestrak":
            return unavailable
        source, source_url = serve._kl_live._SOURCE[feed]
        return {
            "source": source,
            "source_url": source_url,
            "mode": "live",
            "fetched_at": serve._kl_live._now_iso(),
            "ttl_s": 60,
            "data": {"feed": feed},
        }

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    response = asyncio.run(serve._feeds_pulse())
    payload = json.loads(response.body)

    assert payload["live_count"] == 6
    assert payload["cached_count"] == 0
    assert payload["down_count"] == 1
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "unavailable"
    assert timed_out["payload_bytes"] == 0
    assert "cooperative test deadline" in timed_out["error"]


def test_feed_pulse_propagates_internal_timeout_cache_evidence(monkeypatch):
    def timeout_fetch(_feed, deadline=None):
        raise TimeoutError("cooperative test deadline")

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {})
    monkeypatch.setattr(a11oy_live_feeds, "_fetch", timeout_fetch)
    monkeypatch.setattr(
        a11oy_live_feeds,
        "_load_snapshot",
        lambda feed: {"snapshot": feed},
    )
    cached = a11oy_live_feeds.get_feed("celestrak", timeout_s=0.15)

    assert cached["mode"] == "cached"
    assert "TimeoutError" in cached["cache_note"]

    def fake_get_feed(feed, timeout_s=None):
        assert timeout_s == 0.15
        if feed == "celestrak":
            return cached
        source, source_url = serve._kl_live._SOURCE[feed]
        return {
            "source": source,
            "source_url": source_url,
            "mode": "live",
            "fetched_at": serve._kl_live._now_iso(),
            "ttl_s": 60,
            "data": {"feed": feed},
        }

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    response = asyncio.run(serve._feeds_pulse())
    payload = json.loads(response.body)

    assert payload["live_count"] == 6
    assert payload["cached_count"] == 1
    assert payload["down_count"] == 0
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "cached"
    assert timed_out["payload_bytes"] > 0
    assert "TimeoutError" in timed_out["cache_note"]


def test_feed_pulse_preserves_cache_when_worker_propagates_timeout(monkeypatch):
    stale = {
        "data": {"snapshot": "real-stale-celestrak"},
        "ts": time.time() - a11oy_live_feeds._TTL["celestrak"] - 1,
        "mode": "live",
        "iso": "2026-07-25T00:00:00+00:00",
    }

    def fake_get_feed(feed, timeout_s=None):
        assert timeout_s == 0.05
        if feed == "celestrak":
            raise TimeoutError("transport deadline exhausted")
        source, source_url = serve._kl_live._SOURCE[feed]
        return {
            "source": source,
            "source_url": source_url,
            "mode": "live",
            "fetched_at": serve._kl_live._now_iso(),
            "ttl_s": 60,
            "data": {"feed": feed},
        }

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {"celestrak": stale})
    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.05)

    payload = json.loads(asyncio.run(serve._feeds_pulse()).body)

    assert payload["live_count"] == 6
    assert payload["cached_count"] == 1
    assert payload["down_count"] == 0
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "cached"
    assert timed_out["fetched_at"] == stale["iso"]
    assert timed_out["payload_bytes"] > 0
    assert timed_out["error"] is None
    assert "TimeoutError" in timed_out["cache_note"]


def test_feed_pulse_joins_trickling_worker_and_preserves_cached_evidence(monkeypatch):
    active_streams = 0
    max_active_streams = 0
    stream_calls = 0

    class TricklingResponse:
        headers = {}

        def __enter__(self):
            nonlocal active_streams, max_active_streams
            active_streams += 1
            max_active_streams = max(max_active_streams, active_streams)
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            nonlocal active_streams
            active_streams -= 1

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            while True:
                # Each byte arrives before a per-read timeout would fire. The
                # absolute body deadline must still terminate the stream.
                time.sleep(0.01)
                yield b" "

    def fake_stream(method, url, **kwargs):
        nonlocal stream_calls
        assert method == "GET"
        assert url == "https://example.test/trickle"
        assert kwargs["follow_redirects"] is True
        stream_calls += 1
        return TricklingResponse()

    original_http_get = a11oy_live_feeds._http_get

    def fake_fetch(feed, deadline=None):
        if feed == "celestrak":
            return original_http_get(
                "https://example.test/trickle",
                timeout=a11oy_live_feeds._remaining_timeout(deadline, 1),
                deadline=deadline,
            )
        return {"feed": feed}

    stale = {
        "data": {"snapshot": "real-stale-celestrak"},
        "ts": time.time() - a11oy_live_feeds._TTL["celestrak"] - 1,
        "mode": "live",
        "iso": "2026-07-25T00:00:00+00:00",
    }
    monkeypatch.setattr(a11oy_live_feeds.httpx, "stream", fake_stream)
    monkeypatch.setattr(a11oy_live_feeds, "_fetch", fake_fetch)
    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {"celestrak": stale})
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.05)

    started = time.monotonic()
    payloads = [
        json.loads(asyncio.run(serve._feeds_pulse()).body)
        for _ in range(4)
    ]
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert stream_calls == 4
    assert max_active_streams == 1
    assert active_streams == 0
    for payload in payloads:
        assert payload["live_count"] == 6
        assert payload["cached_count"] == 1
        assert payload["down_count"] == 0
        timed_out = payload["items"][4]
        assert timed_out["mode"] == "cached"
        assert timed_out["fetched_at"] == stale["iso"]
        assert timed_out["payload_bytes"] > 0
        assert timed_out["error"] is None
        assert "TimeoutError" in timed_out["cache_note"]
