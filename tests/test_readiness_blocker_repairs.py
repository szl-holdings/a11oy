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

    def fake_get_feed(feed, timeout_s=None):
        nonlocal active
        assert timeout_s == 0.15
        with active_lock:
            active += 1
        try:
            delay = 1.00 if feed == "celestrak" else 0.02
            if delay > timeout_s:
                time.sleep(timeout_s)
                raise TimeoutError("cooperative test deadline")
            time.sleep(delay)
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

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    started = time.monotonic()
    response = asyncio.run(serve._feeds_pulse())
    elapsed = time.monotonic() - started
    payload = json.loads(response.body)

    assert elapsed < 0.75
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
