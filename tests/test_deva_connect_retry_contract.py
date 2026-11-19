"""Deterministic contracts for the bounded DEV-A connect-phase retry.

Verify runs observed intermittent httpx ConnectTimeout ("The handshake
operation timed out") against the live NYC HPD source inside the unchanged
4s per-attempt transport budget, which degraded whole endpoints to
UNAVAILABLE and blocked the readiness verdict. These contracts pin the
exact bounded, fail-closed shape of the connect-phase retry in
a11oy_deva_feeds._cached_fetch.
"""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

import a11oy_deva_feeds as deva


class _LiveResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


def _install_client(
    monkeypatch: pytest.MonkeyPatch,
    behaviour: Callable[[str], Any],
) -> list[float]:
    """SIMULATED httpx.Client: never contacts a network source."""
    observed_timeouts: list[float] = []

    class _Client:
        def __init__(self, **kwargs: Any) -> None:
            observed_timeouts.append(kwargs["timeout"])

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def get(self, url: str, **_kwargs: Any) -> Any:
            return behaviour(url)

    monkeypatch.setattr(httpx, "Client", _Client)
    return observed_timeouts


def _reset_deva_lane(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    monkeypatch.setattr(deva, "_CACHE", {})
    monkeypatch.setattr(deva, "_INFLIGHT", {})
    monkeypatch.delenv("A11OY_SOURCE_HTTP_TIMEOUT_S", raising=False)
    sleeps: list[float] = []
    monkeypatch.setattr(deva.time, "sleep", lambda delay: sleeps.append(delay))
    return sleeps


def test_transient_connect_timeout_is_retried_and_publishes_live(monkeypatch):
    sleeps = _reset_deva_lane(monkeypatch)
    calls = {"n": 0}

    def behaviour(_url: str) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectTimeout("The handshake operation timed out")
        return _LiveResponse({"items": ["fresh"]})

    observed_timeouts = _install_client(monkeypatch, behaviour)
    result = deva._cached_fetch("connect-retry-live", "https://source.invalid/data", 60.0)

    assert calls["n"] == 2
    assert observed_timeouts == [4.0, 4.0]
    assert sleeps == [0.5]
    assert result["value"] == {"items": ["fresh"]}
    assert result["freshness"]["status"] == "live"


def test_persistent_connect_failure_fails_closed_after_bounded_attempts(monkeypatch):
    sleeps = _reset_deva_lane(monkeypatch)

    def behaviour(_url: str) -> Any:
        raise httpx.ConnectError("all attempts failed")

    observed_timeouts = _install_client(monkeypatch, behaviour)
    result = deva._cached_fetch("connect-retry-exhausted", "https://source.invalid/data", 60.0)

    assert observed_timeouts == [4.0, 4.0, 4.0]
    assert sleeps == [0.5, 0.5]
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert result["freshness"]["status"] != "live"
    assert "ConnectError" in result["freshness"]["error"]


def test_http_status_answer_is_final_and_never_retried(monkeypatch):
    _reset_deva_lane(monkeypatch)

    class _BadStatus:
        def raise_for_status(self) -> None:
            request = httpx.Request("GET", "https://source.invalid/data")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError(
                "controlled upstream answer", request=request, response=response
            )

        def json(self) -> Any:
            return {}

    observed_timeouts = _install_client(monkeypatch, lambda _url: _BadStatus())
    result = deva._cached_fetch("status-answer-final", "https://source.invalid/data", 60.0)

    assert observed_timeouts == [4.0]
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert result["freshness"]["status"] != "live"
    assert "HTTPStatusError" in result["freshness"]["error"]


def test_read_timeout_is_not_retried(monkeypatch):
    _reset_deva_lane(monkeypatch)

    def behaviour(_url: str) -> Any:
        raise httpx.ReadTimeout("bounded read timeout")

    observed_timeouts = _install_client(monkeypatch, behaviour)
    result = deva._cached_fetch("read-timeout-single", "https://source.invalid/data", 60.0)

    assert observed_timeouts == [4.0]
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert "ReadTimeout" in result["freshness"]["error"]
