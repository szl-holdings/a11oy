# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the bounded live-feed readiness endpoint."""

from __future__ import annotations

import asyncio
import json
import time

import serve


def test_feed_pulse_is_concurrent_bounded_and_honest_about_timeout(monkeypatch):
    def fake_get_feed(feed):
        time.sleep(1.00 if feed == "celestrak" else 0.02)
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

    started = time.monotonic()
    response = asyncio.run(serve._feeds_pulse())
    elapsed = time.monotonic() - started
    payload = json.loads(response.body)

    assert elapsed < 0.75
    assert payload["feed_count"] == 7
    assert payload["live_count"] >= 1
    assert payload["live_count"] + payload["cached_count"] + payload["down_count"] == 7
    assert payload["down_count"] >= 1
    assert [item["feed"] for item in payload["items"]] == [
        "kev", "osv", "rekor", "iss", "celestrak", "prometheus", "fhir"
    ]
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "unavailable"
    assert timed_out["source_url"].startswith("https://")
    assert timed_out["fetched_at"] is None
    assert timed_out["payload_bytes"] == 0
    assert timed_out["error"] == "probe timeout after 0.15s"
