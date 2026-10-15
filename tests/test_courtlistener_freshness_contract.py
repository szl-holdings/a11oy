# SPDX-License-Identifier: Apache-2.0
"""Synthetic-clock, network-free legal freshness and provider-budget contracts."""

from collections import deque
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import a11oy_devb_endpoints as devb
import a11oy_vertical_feeds as vertical


@pytest.fixture
def source(monkeypatch):
    state = {"now": 100_000.0, "calls": [], "status": 200}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url, **_kwargs):
            state["calls"].append(url)
            return httpx.Response(
                state["status"], request=httpx.Request("GET", url),
                json={"count": 1, "results": [{
                    "caseName": "SIMULATED fixture", "absolute_url": "/opinion/1/",
                }]},
            )

    monkeypatch.setattr(vertical, "_client", lambda: Client())
    monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())
    monkeypatch.setattr(vertical, "_COURTLISTENER_REQUEST_TIMES", deque())
    monkeypatch.setattr(vertical, "_COURTLISTENER_NEXT_REQUEST_AT", 0.0)
    monkeypatch.setattr(vertical, "_COURTLISTENER_COOLDOWN_UNTIL", 0.0)
    monkeypatch.delenv("A11OY_COURTLISTENER_MIN_INTERVAL_S", raising=False)
    monkeypatch.setattr(vertical.time, "time", lambda: state["now"])
    monkeypatch.setattr(vertical.time, "monotonic", lambda: state["now"])
    monkeypatch.setattr(devb, "_HAS_VF", True)
    monkeypatch.setattr(devb, "_vf", vertical)
    monkeypatch.setattr(devb, "_LOCAL_CACHE", {})
    monkeypatch.setattr(devb, "_LOCAL_INFLIGHT", {})
    return state


def read(lane):
    return (vertical if lane == "vertical" else devb).feed_courtlistener(
        "insurance", 1,
    )


def test_legal_cache_does_not_outlive_published_freshness_sla():
    matrix = json.loads((Path(__file__).resolve().parents[1]
                         / "tools/readiness-harness/tabs.json").read_text())
    endpoints = (
        "/api/a11oy/v1/vert/legal/feed",
        "/api/a11oy/v1/devb/legal/matter?limit=1",
        "/api/a11oy/v1/devb/legal/matter?term=defense&limit=1",
        "/api/a11oy/v1/devb/legal/matter?term=insurance&limit=1",
        "/api/a11oy/v1/devb/legal/exposure?limit=1",
    )
    for endpoint in endpoints:
        assert 0 < vertical._COURTLISTENER_CACHE_TTL_S <= matrix["endpoints"][endpoint]["freshnessSLA"]
    assert devb._courtlistener_cache_ttl_s() == vertical._COURTLISTENER_CACHE_TTL_S


@pytest.mark.parametrize("lane", ["vertical", "devb"])
@pytest.mark.parametrize("age,requests", [(3599.0, 1), (3600.0, 2), (3601.0, 2)])
def test_one_hour_boundary_refreshes_without_relabelling_old_observation(source, lane, age, requests):
    first = read(lane)
    original = first["freshness"]["fetched_at"]
    source["now"] += age
    result = read(lane)
    assert len(source["calls"]) == requests
    assert result["freshness"]["status"] == "live"
    assert result["freshness"]["fetched_at"] == (original if requests == 1 else source["now"])
    assert result["freshness"]["age_s"] == (age if requests == 1 else 0.0)


def test_vertical_and_devb_share_the_renewed_observation(source):
    read("vertical")
    source["now"] += 3600.0
    renewed = read("devb")
    shared = read("vertical")
    assert len(source["calls"]) == 2
    assert shared == renewed


@pytest.mark.parametrize("lane", ["vertical", "devb"])
def test_old_day_ttl_cannot_override_current_one_hour_contract(source, lane):
    key = vertical._courtlistener_cache_key("insurance", 1)
    vertical._CACHE.put(key, {"items": []}, ttl=86400.0)
    source["now"] += 3601.0
    result = read(lane)
    assert len(source["calls"]) == 1
    assert result["freshness"]["fetched_at"] == source["now"]
    assert vertical._CACHE.get(key)["ttl"] == 3600.0


@pytest.mark.parametrize("lane", ["vertical", "devb"])
@pytest.mark.parametrize("blocker", ["daily-budget", "cooldown", "upstream-failure"])
def test_blocked_renewal_keeps_original_data_and_clock(source, monkeypatch, lane, blocker):
    first = read(lane)
    source["now"] += 3601.0
    if blocker == "daily-budget":
        # Exhaust only the daily window, not the minute/hour windows.
        monkeypatch.setattr(vertical, "_COURTLISTENER_REQUEST_TIMES", deque(
            source["now"] - 85_000.0 + index * 800.0 for index in range(100)
        ))
    elif blocker == "cooldown":
        monkeypatch.setattr(vertical, "_COURTLISTENER_COOLDOWN_UNTIL", source["now"] + 60.0)
    else:
        source["status"] = 503
    result = read(lane)
    assert result["value"] == first["value"]
    assert result["freshness"]["status"] == "stale"
    assert result["freshness"]["fetched_at"] == first["freshness"]["fetched_at"]
    assert result["freshness"]["age_s"] == 3601.0
    assert len(source["calls"]) == (2 if blocker == "upstream-failure" else 1)
    if blocker == "daily-budget":
        assert len(vertical._COURTLISTENER_REQUEST_TIMES) == 100
    public = vertical._readiness_public_source(result)
    assert public["freshness"]["status"] == "cached"
    assert public["freshness"]["fetched_at"] == first["freshness"]["fetched_at"]
    assert public["freshness"]["age_s"] > 3600.0


@pytest.mark.parametrize("failure", ["missing", "missing-helper", "raises"])
@pytest.mark.parametrize("has_old", [False, True])
def test_devb_never_falls_back_to_an_unscheduled_courtlistener_request(source, monkeypatch, failure, has_old):
    old = {"items": [{"caseName": "SIMULATED old observation"}]}
    observed_at = source["now"] - 3601.0
    if has_old:
        key = devb._courtlistener_cache_key("insurance", 1, "o")
        devb._LOCAL_CACHE[key] = {
            "value": old, "fetched_at": observed_at, "ttl": 86400.0, "status": "live",
        }
    if failure == "missing":
        monkeypatch.setattr(devb, "_HAS_VF", False)
    elif failure == "missing-helper":
        monkeypatch.setattr(devb, "_vf", SimpleNamespace())
    else:
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("shared helper failed")
        monkeypatch.setattr(vertical, "_cached_fetch", unavailable)

    def forbidden(*_args, **_kwargs):
        pytest.fail("CourtListener must not use the unscheduled standalone transport")
    monkeypatch.setattr(devb, "_client", forbidden)
    result = read("devb")
    assert result["freshness"]["status"] == ("stale" if has_old else "unavailable")
    assert result["value"] == (old if has_old else None)
    if has_old:
        assert result["freshness"]["fetched_at"] == observed_at
    assert source["calls"] == []


def test_renewal_preserves_the_existing_provider_budgets():
    assert vertical._COURTLISTENER_RATE_WINDOWS == (
        (60.0, 4), (3600.0, 40), (86400.0, 100),
    )


def test_hourly_warmers_and_extra_queries_cannot_exceed_daily_budget(source):
    started_at = source["now"]
    warmers = (("artificial intelligence", 18), ("securities", 1),
               ("defense", 1), ("insurance", 1))
    for hour in range(24):
        for index, (term, limit) in enumerate(warmers):
            source["now"] = started_at + hour * 3600.0 + index * 13.0
            result = devb.feed_courtlistener(term, limit)
            assert result["freshness"]["status"] == "live"
    assert len(source["calls"]) == 96
    for index in range(4):
        source["now"] = started_at + 23 * 3600.0 + 200.0 + index * 13.0
        result = devb.feed_courtlistener(f"SIMULATED extra query {index}", 1)
        assert result["freshness"]["status"] == "live"
    assert len(source["calls"]) == 100
    source["now"] += 60.0
    refused = devb.feed_courtlistener("SIMULATED beyond daily budget", 1)
    assert refused["value"] is None
    assert refused["freshness"]["status"] == "unavailable"
    assert "provider budget exhausted" in refused["freshness"]["error"]
    assert len(source["calls"]) == 100
    source["now"] = started_at + 86400.001
    renewed = devb.feed_courtlistener("SIMULATED beyond daily budget", 1)
    assert renewed["freshness"]["status"] == "live"
    assert renewed["freshness"]["fetched_at"] == source["now"]
    assert len(source["calls"]) == 101
    assert len(vertical._COURTLISTENER_REQUEST_TIMES) == 100
