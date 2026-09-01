"""Deterministic contracts for bounded, honest live-source refreshes."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

import a11oy_deva_feeds as deva
import a11oy_devb_endpoints as devb
import a11oy_vertical_feeds as vertical


def _configure_cache(
    monkeypatch: pytest.MonkeyPatch, lane: str, key: str,
) -> tuple[
    Callable[[], dict[str, Any]],
    Callable[[], int],
    Callable[[], tuple[dict[str, Any], bool]],
]:
    fetched_at = time.time() - 30.0
    old_value = {"generation": "old"}

    if lane == "vertical":
        cache = vertical._Cache()
        with cache._lock:
            cache._d[key] = {
                "value": old_value, "fetched_at": fetched_at,
                "ttl": 1.0, "status": "live",
            }
        monkeypatch.setattr(vertical, "_CACHE", cache)

        def fetch() -> dict[str, Any]:
            return vertical._cached_fetch(key, "https://source.invalid/data", 60.0)

        def waiters() -> int:
            with cache._lock:
                flight = cache._inflight.get(key)
                return flight.waiters if flight else -1

        def final() -> tuple[dict[str, Any], bool]:
            with cache._lock:
                return dict(cache._d[key]), key in cache._inflight

        return fetch, waiters, final

    if lane == "deva":
        monkeypatch.setattr(deva, "_CACHE", {
            key: {
                "value": old_value, "fetched_at": fetched_at,
                "fetched_at_iso": "2026-08-11T00:00:00+00:00",
                "ttl": 1.0, "status": "live",
            },
        })
        monkeypatch.setattr(deva, "_INFLIGHT", {})

        def fetch() -> dict[str, Any]:
            return deva._cached_fetch(key, "https://source.invalid/data", 60.0)

        def waiters() -> int:
            with deva._LOCK:
                flight = deva._INFLIGHT.get(key)
                return flight.waiters if flight else -1

        def final() -> tuple[dict[str, Any], bool]:
            with deva._LOCK:
                return dict(deva._CACHE[key]), key in deva._INFLIGHT

        return fetch, waiters, final

    if lane == "devb":
        monkeypatch.setattr(devb, "_HAS_VF", False)
        monkeypatch.setattr(devb, "_LOCAL_CACHE", {
            key: {
                "value": old_value, "fetched_at": fetched_at,
                "ttl": 1.0, "status": "live",
            },
        })
        monkeypatch.setattr(devb, "_LOCAL_INFLIGHT", {})

        def fetch() -> dict[str, Any]:
            return devb._cached(
                key, "https://source.invalid/data", 60.0, headers=devb.SEC_UA,
            )

        def waiters() -> int:
            with devb._LOCAL_CACHE_LOCK:
                flight = devb._LOCAL_INFLIGHT.get(key)
                return flight.waiters if flight else -1

        def final() -> tuple[dict[str, Any], bool]:
            with devb._LOCAL_CACHE_LOCK:
                return dict(devb._LOCAL_CACHE[key]), key in devb._LOCAL_INFLIGHT

        return fetch, waiters, final

    raise AssertionError(f"unknown lane: {lane}")


def test_source_transport_budget_has_one_default_and_clamped_env(monkeypatch) -> None:
    helpers = (
        vertical._source_http_timeout_s,
        deva._source_http_timeout_s,
        devb._source_http_timeout_s,
    )
    monkeypatch.delenv("A11OY_SOURCE_HTTP_TIMEOUT_S", raising=False)
    assert [helper() for helper in helpers] == [4.0, 4.0, 4.0]

    monkeypatch.setenv("A11OY_SOURCE_HTTP_TIMEOUT_S", "0.001")
    assert [helper() for helper in helpers] == [0.25, 0.25, 0.25]

    monkeypatch.setenv("A11OY_SOURCE_HTTP_TIMEOUT_S", "999")
    assert [helper() for helper in helpers] == [15.0, 15.0, 15.0]

    for invalid in ("not-a-number", "nan", "inf"):
        monkeypatch.setenv("A11OY_SOURCE_HTTP_TIMEOUT_S", invalid)
        assert [helper() for helper in helpers] == [4.0, 4.0, 4.0]


@pytest.mark.parametrize("lane", ["vertical", "deva", "devb"])
def test_same_key_refresh_is_singleflight_and_all_waiters_share_live_result(
    monkeypatch, lane: str,
) -> None:
    key = f"singleflight-{lane}"
    fetch, waiter_count, final_record = _configure_cache(monkeypatch, lane, key)
    refresh_started = threading.Event()
    release_refresh = threading.Event()
    calls_lock = threading.Lock()
    calls = 0

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"generation": "fresh"}

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> _Response:
            nonlocal calls
            with calls_lock:
                calls += 1
            refresh_started.set()
            if not release_refresh.wait(2.0):
                raise TimeoutError("test refresh release deadline exhausted")
            return _Response()

    monkeypatch.setattr(httpx, "Client", _Client)
    results: list[dict[str, Any]] = []
    results_lock = threading.Lock()

    def invoke() -> None:
        observed = fetch()
        with results_lock:
            results.append(observed)

    threads = [threading.Thread(target=invoke) for _ in range(6)]
    threads[0].start()
    assert refresh_started.wait(1.0)
    for thread in threads[1:]:
        thread.start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and waiter_count() != len(threads) - 1:
        time.sleep(0.001)
    assert waiter_count() == len(threads) - 1

    release_refresh.set()
    for thread in threads:
        thread.join(1.0)
        assert not thread.is_alive()

    record, still_inflight = final_record()
    assert calls == 1
    assert still_inflight is False
    assert record["value"] == {"generation": "fresh"}
    assert record["status"] == "live"
    assert len(results) == len(threads)
    assert all(result == results[0] for result in results)
    assert results[0]["value"] == {"generation": "fresh"}
    assert results[0]["freshness"]["status"] == "live"


@pytest.mark.parametrize("lane", ["vertical", "deva", "devb"])
def test_late_arrival_after_leader_retirement_does_not_refetch(
    monkeypatch, lane: str,
) -> None:
    key = f"late-arrival-{lane}"
    fetch, _waiter_count, final_record = _configure_cache(monkeypatch, lane, key)
    claim_blocked = threading.Event()
    release_claim = threading.Event()

    if lane == "vertical":
        original_claim = vertical._CACHE.claim_refresh

        def delayed_claim(claim_key: str):
            if threading.current_thread().name == "late-arrival":
                claim_blocked.set()
                assert release_claim.wait(2.0)
            return original_claim(claim_key)

        monkeypatch.setattr(vertical._CACHE, "claim_refresh", delayed_claim)
    elif lane == "deva":
        original_claim = deva._claim_refresh

        def delayed_claim(claim_key: str):
            if threading.current_thread().name == "late-arrival":
                claim_blocked.set()
                assert release_claim.wait(2.0)
            return original_claim(claim_key)

        monkeypatch.setattr(deva, "_claim_refresh", delayed_claim)
    else:
        original_claim = devb._claim_local_refresh

        def delayed_claim(claim_key: str):
            if threading.current_thread().name == "late-arrival":
                claim_blocked.set()
                assert release_claim.wait(2.0)
            return original_claim(claim_key)

        monkeypatch.setattr(devb, "_claim_local_refresh", delayed_claim)

    calls = 0

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"generation": "fresh"}

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> _Response:
            nonlocal calls
            calls += 1
            return _Response()

    monkeypatch.setattr(httpx, "Client", _Client)
    results: dict[str, dict[str, Any]] = {}

    def invoke(label: str) -> None:
        results[label] = fetch()

    late = threading.Thread(target=invoke, args=("late",), name="late-arrival")
    leader = threading.Thread(target=invoke, args=("leader",), name="refresh-leader")
    late.start()
    assert claim_blocked.wait(1.0)
    leader.start()
    leader.join(1.0)
    assert not leader.is_alive()

    release_claim.set()
    late.join(1.0)
    assert not late.is_alive()

    record, still_inflight = final_record()
    assert calls == 1
    assert still_inflight is False
    assert record["status"] == "live"
    assert results["leader"] == results["late"]
    assert results["late"]["freshness"]["status"] == "live"


@pytest.mark.parametrize("lane", ["vertical", "deva", "devb"])
def test_transport_timeout_is_four_seconds_and_never_becomes_live(
    monkeypatch, lane: str,
) -> None:
    monkeypatch.delenv("A11OY_SOURCE_HTTP_TIMEOUT_S", raising=False)
    observed_timeouts: list[float] = []

    class _Client:
        def __init__(self, **kwargs: Any) -> None:
            observed_timeouts.append(kwargs["timeout"])

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> Any:
            raise httpx.ReadTimeout("bounded test timeout")

    monkeypatch.setattr(httpx, "Client", _Client)
    key = f"timeout-{lane}"
    if lane == "vertical":
        monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())
        result = vertical._cached_fetch(key, "https://source.invalid/data", 60.0)
    elif lane == "deva":
        monkeypatch.setattr(deva, "_CACHE", {})
        monkeypatch.setattr(deva, "_INFLIGHT", {})
        result = deva._cached_fetch(key, "https://source.invalid/data", 60.0)
    else:
        monkeypatch.setattr(devb, "_HAS_VF", False)
        monkeypatch.setattr(devb, "_LOCAL_CACHE", {})
        monkeypatch.setattr(devb, "_LOCAL_INFLIGHT", {})
        result = devb._cached(
            key, "https://source.invalid/data", 60.0, headers=devb.SEC_UA,
        )

    assert observed_timeouts == [4.0]
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert result["freshness"]["status"] != "live"


@pytest.mark.parametrize("lane", ["vertical", "deva", "devb"])
def test_transport_timeout_preserves_last_good_only_as_stale(
    monkeypatch, lane: str,
) -> None:
    key = f"stale-timeout-{lane}"
    fetch, _waiter_count, final_record = _configure_cache(monkeypatch, lane, key)

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> Any:
            raise httpx.ReadTimeout("bounded test timeout")

    monkeypatch.setattr(httpx, "Client", _Client)
    result = fetch()
    record, still_inflight = final_record()

    assert still_inflight is False
    assert result["value"] == {"generation": "old"}
    assert result["freshness"]["status"] == "stale"
    assert result["freshness"]["status"] != "live"
    assert record["status"] == "stale"


@pytest.mark.parametrize("lane", ["vertical", "deva", "devb"])
def test_leader_baseexception_always_publishes_and_releases_waiters(
    monkeypatch, lane: str,
) -> None:
    key = f"fatal-leader-{lane}"
    fetch, waiter_count, final_record = _configure_cache(monkeypatch, lane, key)
    refresh_started = threading.Event()
    release_refresh = threading.Event()

    class _FatalRefresh(BaseException):
        pass

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> Any:
            refresh_started.set()
            assert release_refresh.wait(2.0)
            raise _FatalRefresh("controlled fatal refresh")

    monkeypatch.setattr(httpx, "Client", _Client)
    outcomes: dict[str, Any] = {}

    def leader() -> None:
        try:
            outcomes["leader"] = fetch()
        except BaseException as error:
            outcomes["leader_error"] = error

    def follower() -> None:
        outcomes["follower"] = fetch()

    leader_thread = threading.Thread(target=leader)
    follower_thread = threading.Thread(target=follower)
    leader_thread.start()
    assert refresh_started.wait(1.0)
    follower_thread.start()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and waiter_count() != 1:
        time.sleep(0.001)
    assert waiter_count() == 1
    release_refresh.set()

    leader_thread.join(1.0)
    follower_thread.join(1.0)
    assert not leader_thread.is_alive()
    assert not follower_thread.is_alive()
    record, still_inflight = final_record()

    assert isinstance(outcomes["leader_error"], _FatalRefresh)
    assert outcomes["follower"]["value"] == {"generation": "old"}
    assert outcomes["follower"]["freshness"]["status"] == "stale"
    assert "FatalRefresh" in outcomes["follower"]["freshness"]["error"]
    assert record["status"] == "stale"
    assert still_inflight is False


@pytest.mark.parametrize("lane", ["vertical", "deva", "devb"])
def test_external_plaintext_feed_url_fails_closed_before_transport(
    monkeypatch, lane: str,
) -> None:
    class _UnexpectedClient:
        def __init__(self, **_kwargs: Any) -> None:
            raise AssertionError("plaintext external URL must not construct a client")

    monkeypatch.setattr(httpx, "Client", _UnexpectedClient)
    if lane == "vertical":
        result = vertical._cached_fetch(
            "plaintext", "http://external.example.test/data", 60.0,
        )
    elif lane == "deva":
        result = deva._cached_fetch(
            "plaintext", "http://external.example.test/data", 60.0,
        )
    else:
        monkeypatch.setattr(devb, "_HAS_VF", False)
        result = devb._cached(
            "plaintext", "http://external.example.test/data", 60.0,
            headers=devb.SEC_UA,
        )

    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert "HTTPS" in result["freshness"]["error"]


def test_source_url_policy_allows_only_https_or_local_loopback() -> None:
    for helper in (
        vertical._source_url_allowed,
        deva._source_url_allowed,
        devb._source_url_allowed,
    ):
        assert helper("https://example.com/feed") is True
        assert helper("http://127.0.0.1:7860/feed") is True
        assert helper("http://localhost:7860/feed") is True
        assert helper("http://example.com/feed") is False
        assert helper("ftp://example.com/feed") is False

    source = Path(deva.__file__).read_text(encoding="utf-8")
    assert "https://export.arxiv.org/api/query" in source
    assert "http://export.arxiv.org/api/query" not in source


def test_response_affecting_parameter_variants_have_distinct_cache_keys(
    monkeypatch,
) -> None:
    vertical_keys: list[str] = []
    deva_keys: list[str] = []
    devb_keys: list[str] = []

    def vertical_spy(key: str, _url: str, ttl: float, **_kwargs: Any) -> dict[str, Any]:
        del ttl
        vertical_keys.append(key)
        return {"value": {"items": []}, "freshness": {"status": "live"}}

    def deva_spy(key: str, _url: str, ttl: float, **_kwargs: Any) -> dict[str, Any]:
        del ttl
        deva_keys.append(key)
        return {"value": {"items": []}, "freshness": {"status": "live"}}

    def devb_spy(key: str, _url: str, ttl: float, **_kwargs: Any) -> dict[str, Any]:
        del ttl
        devb_keys.append(key)
        return {"value": {"items": []}, "freshness": {"status": "live"}}

    monkeypatch.setattr(vertical, "_cached_fetch", vertical_spy)
    vertical.feed_nvd(5, "financial")
    vertical.feed_nvd(6, "financial")
    vertical.feed_courtlistener("alpha/beta", 10)
    vertical.feed_courtlistener("alpha beta", 10)
    vertical.feed_github("a_b/c")
    vertical.feed_github("a/b_c")

    monkeypatch.setattr(deva, "_cached_fetch", deva_spy)
    deva.feed_treasury(5)
    deva.feed_treasury(6)
    deva.feed_arxiv_frontier(5)
    deva.feed_arxiv_frontier(6)

    monkeypatch.setattr(devb, "_cached", devb_spy)
    devb.feed_courtlistener("securities", 5)
    devb.feed_courtlistener("securities", 6)
    devb.feed_gh_events("pytorch/pytorch", 5)
    devb.feed_gh_events("pytorch/pytorch", 6)

    assert vertical_keys[0] != vertical_keys[1]
    assert vertical_keys[2] != vertical_keys[3]
    assert vertical_keys[4] != vertical_keys[5]
    assert deva_keys[0] != deva_keys[1]
    assert deva_keys[2] != deva_keys[3]
    assert devb_keys[0] != devb_keys[1]
    assert devb_keys[2] != devb_keys[3]


def test_full_catalog_sources_cache_once_then_slice_per_requested_limit(
    monkeypatch,
) -> None:
    monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())
    monkeypatch.setattr(devb, "_HAS_VF", False)
    monkeypatch.setattr(devb, "_LOCAL_CACHE", {})
    monkeypatch.setattr(devb, "_LOCAL_INFLIGHT", {})
    calls = {"cisa": 0, "agencies": 0}

    class _Response:
        def __init__(self, payload: Any) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> Any:
            return self.payload

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **_kwargs: Any) -> _Response:
            if "known_exploited_vulnerabilities" in url:
                calls["cisa"] += 1
                return _Response({
                    "catalogVersion": "test", "dateReleased": "2026-08-11",
                    "count": 3,
                    "vulnerabilities": [
                        {"cveID": f"CVE-2026-000{i}", "dateAdded": f"2026-08-0{i}"}
                        for i in range(1, 4)
                    ],
                })
            calls["agencies"] += 1
            return _Response([
                {"name": f"Agency {i}", "slug": f"agency-{i}", "id": i}
                for i in range(1, 4)
            ])

    monkeypatch.setattr(httpx, "Client", _Client)
    cisa_one = vertical.feed_cisa_kev(1)
    cisa_three = vertical.feed_cisa_kev(3)
    agencies_one = devb.feed_fr_agencies(1)
    agencies_three = devb.feed_fr_agencies(3)

    assert calls == {"cisa": 1, "agencies": 1}
    assert len(cisa_one["value"]["items"]) == 1
    assert len(cisa_three["value"]["items"]) == 3
    assert len(agencies_one["value"]["items"]) == 1
    assert len(agencies_three["value"]["items"]) == 3


def test_courtlistener_interval_is_bounded(monkeypatch) -> None:
    monkeypatch.delenv("A11OY_COURTLISTENER_MIN_INTERVAL_S", raising=False)
    assert vertical._courtlistener_min_interval_s() == 1.0
    monkeypatch.setenv("A11OY_COURTLISTENER_MIN_INTERVAL_S", "0")
    assert vertical._courtlistener_min_interval_s() == 0.25
    monkeypatch.setenv("A11OY_COURTLISTENER_MIN_INTERVAL_S", "999")
    assert vertical._courtlistener_min_interval_s() == 10.0
    for invalid in ("invalid", "nan", "inf"):
        monkeypatch.setenv("A11OY_COURTLISTENER_MIN_INTERVAL_S", invalid)
        assert vertical._courtlistener_min_interval_s() == 1.0


def test_courtlistener_429_is_serialized_retried_and_recovers_live(monkeypatch) -> None:
    monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())
    monkeypatch.setattr(vertical, "_COURTLISTENER_NEXT_REQUEST_AT", 0.0)
    waited: list[str] = []
    deferred: list[float] = []
    monkeypatch.setattr(
        vertical, "_courtlistener_wait_locked", lambda: waited.append("slot")
    )
    monkeypatch.setattr(
        vertical, "_courtlistener_defer_locked", lambda delay: deferred.append(delay)
    )

    class _Response:
        def __init__(self, status: int, payload: dict[str, Any], headers=None) -> None:
            self.status_code = status
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "https://www.courtlistener.com/")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError(
                    "controlled CourtListener response",
                    request=request,
                    response=response,
                )

        def json(self) -> dict[str, Any]:
            return self._payload

    class _Client:
        calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> _Response:
            self.calls += 1
            if self.calls == 1:
                return _Response(429, {}, {"Retry-After": "2"})
            return _Response(200, {"results": [{"caseName": "Recovered"}], "count": 1})

    client = _Client()
    monkeypatch.setattr(vertical, "_client", lambda: client)
    result = vertical._cached_fetch(
        "courtlistener-test",
        "https://www.courtlistener.com/api/rest/v4/search/?q=defense&type=o",
        900.0,
    )

    assert client.calls == 2
    assert waited == ["slot", "slot"]
    assert deferred == [2.0]
    assert result["value"]["count"] == 1
    assert result["freshness"]["status"] == "live"


def test_non_courtlistener_429_is_not_retried(monkeypatch) -> None:
    monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())

    class _Response:
        status_code = 429
        headers = {"Retry-After": "1"}

        def raise_for_status(self) -> None:
            request = httpx.Request("GET", "https://source.invalid/")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError(
                "controlled non-CourtListener response",
                request=request,
                response=response,
            )

        def json(self) -> dict[str, Any]:
            return {}

    class _Client:
        calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, _url: str, **_kwargs: Any) -> _Response:
            self.calls += 1
            return _Response()

    client = _Client()
    monkeypatch.setattr(vertical, "_client", lambda: client)
    monkeypatch.setattr(
        vertical,
        "_courtlistener_wait_locked",
        lambda: (_ for _ in ()).throw(AssertionError("non-CourtListener path paced")),
    )
    result = vertical._cached_fetch(
        "non-courtlistener-429", "https://source.invalid/data", 60.0
    )

    assert client.calls == 1
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"


def test_devb_courtlistener_reuses_shared_cache_for_fifteen_minutes(monkeypatch) -> None:
    observed: dict[str, Any] = {}

    def shared_fetch(key: str, url: str, ttl: float, parser=None, **_kwargs: Any):
        observed.update({"key": key, "url": url, "ttl": ttl, "parser": parser})
        return {"value": {"count": 0, "items": []},
                "freshness": {"status": "live", "fetched_at": time.time()}}

    monkeypatch.setattr(devb, "_HAS_VF", True)
    monkeypatch.setattr(devb._vf, "_cached_fetch", shared_fetch)
    result = devb.feed_courtlistener("defense", 1)

    assert observed["ttl"] == 900
    assert "/api/rest/v4/search/" in observed["url"]
    assert result["freshness"]["status"] == "live"
