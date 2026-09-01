#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the exact, bounded CourtListener rate-limit repair.

The temporary helper edits the shared source transport, the Dev-B cache TTL,
and deterministic regressions. Its workflow removes this helper before the
permanent product commit is pushed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERTICAL = ROOT / "a11oy_vertical_feeds.py"
DEVB = ROOT / "a11oy_devb_endpoints.py"
TESTS = ROOT / "tests" / "test_feed_cache_singleflight.py"

CONSTANTS_OLD = '''_SOURCE_HTTP_TIMEOUT_MAX_S = 15.0
'''
CONSTANTS_NEW = '''_SOURCE_HTTP_TIMEOUT_MAX_S = 15.0

# CourtListener v4 permits anonymous read traffic but rate-limits cold bursts.
# Every CourtListener transport in this process crosses one serialized scheduler
# so vertical, Dev-B, warm-loop, and readiness calls cannot fan out upstream.
_COURTLISTENER_MIN_INTERVAL_ENV = "A11OY_COURTLISTENER_MIN_INTERVAL_S"
_COURTLISTENER_MIN_INTERVAL_DEFAULT_S = 1.0
_COURTLISTENER_MIN_INTERVAL_MIN_S = 0.25
_COURTLISTENER_MIN_INTERVAL_MAX_S = 10.0
_COURTLISTENER_RETRY_MAX_DELAY_S = 10.0
_COURTLISTENER_MAX_ATTEMPTS = 3
_COURTLISTENER_RATE_LOCK = threading.Lock()
_COURTLISTENER_NEXT_REQUEST_AT = 0.0
'''

SOURCE_POLICY_OLD = '''def _source_url_allowed(url: str) -> bool:
    """Require TLS for external feeds; permit HTTP only for local loopback."""
    try:
        parsed = httpx.URL(url)
    except Exception:
        return False
    host = (parsed.host or "").lower().strip("[]")
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}


def _courtlistener_public_url'''
SOURCE_POLICY_NEW = '''def _source_url_allowed(url: str) -> bool:
    """Require TLS for external feeds; permit HTTP only for local loopback."""
    try:
        parsed = httpx.URL(url)
    except Exception:
        return False
    host = (parsed.host or "").lower().strip("[]")
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}


def _courtlistener_min_interval_s() -> float:
    """Return the bounded minimum spacing between CourtListener requests."""
    raw = os.environ.get(
        _COURTLISTENER_MIN_INTERVAL_ENV,
        str(_COURTLISTENER_MIN_INTERVAL_DEFAULT_S),
    )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = _COURTLISTENER_MIN_INTERVAL_DEFAULT_S
    if not math.isfinite(value):
        value = _COURTLISTENER_MIN_INTERVAL_DEFAULT_S
    return max(
        _COURTLISTENER_MIN_INTERVAL_MIN_S,
        min(_COURTLISTENER_MIN_INTERVAL_MAX_S, value),
    )


def _is_courtlistener_source(url: str) -> bool:
    try:
        parsed = httpx.URL(url)
    except Exception:
        return False
    return (
        parsed.scheme == "https"
        and (parsed.host or "").lower().rstrip(".") == "www.courtlistener.com"
        and parsed.path.startswith("/api/rest/v4/")
    )


def _courtlistener_retry_after_s(response: Any, attempt: int) -> float:
    """Honor a numeric Retry-After value, otherwise use bounded backoff."""
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    try:
        delay = float(raw)
    except (TypeError, ValueError, OverflowError):
        delay = _COURTLISTENER_MIN_INTERVAL_DEFAULT_S * (2 ** max(0, attempt))
    if not math.isfinite(delay):
        delay = _COURTLISTENER_MIN_INTERVAL_DEFAULT_S
    return max(
        _courtlistener_min_interval_s(),
        min(_COURTLISTENER_RETRY_MAX_DELAY_S, delay),
    )


def _courtlistener_wait_locked() -> None:
    """Reserve the next process-wide CourtListener request slot.

    Callers must hold ``_COURTLISTENER_RATE_LOCK``. Sleeping happens while the
    lock is held deliberately: no other request may leapfrog the reserved slot.
    """
    global _COURTLISTENER_NEXT_REQUEST_AT
    now = time.monotonic()
    delay = max(0.0, _COURTLISTENER_NEXT_REQUEST_AT - now)
    if delay:
        time.sleep(delay)
    _COURTLISTENER_NEXT_REQUEST_AT = (
        time.monotonic() + _courtlistener_min_interval_s()
    )


def _courtlistener_defer_locked(delay_s: float) -> None:
    global _COURTLISTENER_NEXT_REQUEST_AT
    _COURTLISTENER_NEXT_REQUEST_AT = max(
        _COURTLISTENER_NEXT_REQUEST_AT,
        time.monotonic() + max(0.0, delay_s),
    )


def _source_json_with_bounded_retry(
    client: httpx.Client,
    url: str,
    headers: Optional[dict[str, str]] = None,
) -> Any:
    """Fetch JSON once, except for bounded CourtListener HTTP 429 recovery."""
    def request() -> Any:
        return client.get(url, headers=headers) if headers else client.get(url)

    if not _is_courtlistener_source(url):
        response = request()
        response.raise_for_status()
        return response.json()

    with _COURTLISTENER_RATE_LOCK:
        for attempt in range(_COURTLISTENER_MAX_ATTEMPTS):
            _courtlistener_wait_locked()
            response = request()
            if (
                getattr(response, "status_code", None) == 429
                and attempt + 1 < _COURTLISTENER_MAX_ATTEMPTS
            ):
                _courtlistener_defer_locked(
                    _courtlistener_retry_after_s(response, attempt)
                )
                continue
            response.raise_for_status()
            return response.json()

    raise RuntimeError("CourtListener request exhausted bounded retry contract")


def _courtlistener_public_url'''

FETCH_OLD = '''    try:
        with _client() as cl:
            r = cl.get(url, headers=headers) if headers else cl.get(url)
            r.raise_for_status()
            data = r.json()
        val = parser(data) if parser else data
'''
FETCH_NEW = '''    try:
        with _client() as cl:
            data = _source_json_with_bounded_retry(cl, url, headers=headers)
        val = parser(data) if parser else data
'''

DEVB_TTL_OLD = '''    return _cached(_variant_cache_key("cl", kind=kind, term=term, limit=limit),
                   url, ttl=180, parser=parse)
'''
DEVB_TTL_NEW = '''    return _cached(_variant_cache_key("cl", kind=kind, term=term, limit=limit),
                   url, ttl=900, parser=parse)
'''

TEST_MARKER = "test_courtlistener_429_is_serialized_retried_and_recovers_live"
TEST_BLOCK = r'''


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
'''


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    if TEST_MARKER in text:
        raise RuntimeError("CourtListener rate-limit regressions already exist")
    TESTS.write_text(text.rstrip() + TEST_BLOCK.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    replace_once(VERTICAL, CONSTANTS_OLD, CONSTANTS_NEW, "transport constants")
    replace_once(VERTICAL, SOURCE_POLICY_OLD, SOURCE_POLICY_NEW, "source policy")
    replace_once(VERTICAL, FETCH_OLD, FETCH_NEW, "shared fetch transport")
    replace_once(DEVB, DEVB_TTL_OLD, DEVB_TTL_NEW, "Dev-B CourtListener TTL")
    append_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
