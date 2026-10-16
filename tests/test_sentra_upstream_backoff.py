#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the emitted Sentra request budget without contacting a provider."""

import copy
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"


class Clock:
    def __init__(self):
        self.monotonic_now = 1000.0
        self.wall_now = 1792108800.0

    def monotonic(self):
        return self.monotonic_now

    def time(self):
        return self.wall_now

    def advance(self, seconds):
        self.monotonic_now += seconds
        self.wall_now += seconds


def manifest():
    return {
        "schema": "szl.public-receipt-verifier/manifest/v1",
        "state": "LIVE",
        "try": {"method": "POST", "endpoint": "/api/a11oy/v1/verify/receipt"},
        "evidence": ["signature", "payload_digest", "hash_chain"],
    }


class Response:
    def __init__(self, status=200, body=None, headers=None, json_error=False):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self.headers = {"content-type": "application/json", **(headers or {})}
        self.body = manifest() if body is None else body
        self.text = self.body if isinstance(self.body, str) else json.dumps(self.body)
        self.content = self.text.encode("utf-8")
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("invalid JSON")
        return copy.deepcopy(self.body)


def runtime(get, *, slug="sentra"):
    spec = importlib.util.spec_from_file_location(
        "sentra_budget_under_test", ROOT / "scripts/hf_sentra_upstream.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock = Clock()
    original = lambda: {"original_probe": True}
    namespace = {
        "CFG": {"slug": slug, "upstream": SOURCE},
        "httpx": SimpleNamespace(get=get),
        "time": clock,
        "probe": original,
    }
    exec(compile(module.APP_SUFFIX, "sentra-budget-suffix.py", "exec"), namespace)
    return namespace, clock, original


def test_first_429_and_repeated_reads_remain_unavailable_without_repolling():
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(429, {"error": "rate limited"})

    ns, clock, _ = runtime(get)
    for _ in range(20):
        result = ns["probe"]()
        assert result["status"] == "UNAVAILABLE"
        assert result["receipt_verified"] is False
        assert result["last_attempt"]["http_status"] == 429
    assert len(calls) == 1
    assert calls[0][0] == SOURCE
    assert 0 < calls[0][1]["timeout"] <= 15
    clock.advance(29)
    assert ns["probe"]()["status"] == "UNAVAILABLE"
    assert len(calls) == 1
    clock.advance(1)
    ns["probe"]()
    assert len(calls) == 2


def test_recognized_429_fingerprint_is_redacted_diagnostic_not_admission():
    response = Response(429, {
        "error": {"code": "rate_limited", "message": "private-owner-message",
                  "trace_id": "private-trace-id"},
        "debug_token": "private-debug-token",
    }, {"x-ratelimit-policy": "sliding-window;w=60", "x-secret-header": "private-header-value"})
    ns, _, _ = runtime(lambda *_args, **_kwargs: response)
    result = ns["probe"]()
    assert result["last_attempt"]["rate_limit"] == {
        "evidence_class": "REPORTED", "fingerprint": "A11OY_SHARED_IP_LIMIT"}
    assert result["last_attempt"]["http_status"] == 429
    assert result["status"] == "UNAVAILABLE" and result["data"] is None
    assert result["receipt_verified"] is False
    assert result["retry_after_seconds"] == 30
    public = json.dumps(result)
    for private in ("private-owner-message", "private-trace-id", "private-debug-token", "private-header-value",
                    "trace_id", "debug_token", "x-secret-header", "x-ratelimit-policy", "sliding-window;w=60"):
        assert private not in public


@pytest.mark.parametrize("response", [
    Response(429, {"error": {"code": "upstream_limited"}}, {"x-ratelimit-policy": "sliding-window;w=60"}),
    Response(429, {"error": {"code": "rate_limited"}}, {"x-ratelimit-policy": "sliding-window;w=61"}),
    Response(429, {"error": {"code": "rate_limited"}}, {"x-ratelimit-policy": "sliding-window;w=60 "}),
    Response(429, {"error": {"code": "rate_limited"}}),
    Response(429, {"error": "rate_limited"}, {"x-ratelimit-policy": "sliding-window;w=60"}),
    Response(429, [{"error": {"code": "rate_limited"}}], {"x-ratelimit-policy": "sliding-window;w=60"}),
    Response(429, "<html>rate limited</html>", {"content-type": "text/html", "x-ratelimit-policy": "sliding-window;w=60"}),
    Response(429, "{not-json", {"x-ratelimit-policy": "sliding-window;w=60"}, json_error=True),
    Response(429, {"error": {"code": "rate_limited", "message": "x" * 4096}},
             {"x-ratelimit-policy": "sliding-window;w=60"}),
], ids=["wrong-code", "wrong-policy", "policy-not-exact", "missing-policy", "error-not-object",
        "body-not-object", "html-body", "malformed-json", "oversized-json"])
def test_429_fingerprint_is_unknown_without_the_complete_bounded_signature(response):
    ns, _, _ = runtime(lambda *_args, **_kwargs: response)
    result = ns["probe"]()
    assert result["last_attempt"]["rate_limit"] == {"evidence_class": "UNKNOWN", "fingerprint": None}
    assert result["last_attempt"]["http_status"] == 429
    assert result["status"] == "UNAVAILABLE" and result["data"] is None
    assert result["receipt_verified"] is False
    assert result["retry_after_seconds"] == 30


@pytest.mark.parametrize("size, expected", [
    (4096, {"evidence_class": "REPORTED", "fingerprint": "A11OY_SHARED_IP_LIMIT"}),
    (4097, {"evidence_class": "UNKNOWN", "fingerprint": None}),
])
def test_429_fingerprint_checks_the_raw_body_byte_limit(size, expected):
    response = Response(429, {"error": {"code": "rate_limited"}},
                        {"x-ratelimit-policy": "sliding-window;w=60"})
    response.content = response.content.ljust(size, b" ")
    ns, _, _ = runtime(lambda *_args, **_kwargs: response)
    assert ns["probe"]()["last_attempt"]["rate_limit"] == expected


@pytest.mark.parametrize("status", [200, 403, 503])
def test_non_429_body_cannot_claim_the_shared_ip_limit(status):
    response = Response(status, {"error": {"code": "rate_limited"}},
                        {"x-ratelimit-policy": "sliding-window;w=60"})
    ns, _, _ = runtime(lambda *_args, **_kwargs: response)
    result = ns["probe"]()
    assert result["last_attempt"].get("rate_limit", {}).get("fingerprint") is None
    assert result["status"] == "UNAVAILABLE"
    assert result["receipt_verified"] is False


def test_returned_rate_limit_metadata_cannot_mutate_retained_evidence():
    response = Response(429, {"error": {"code": "rate_limited"}},
                        {"x-ratelimit-policy": "sliding-window;w=60"})
    ns, clock, _ = runtime(lambda *_args, **_kwargs: response)
    result = ns["probe"]()
    result["last_attempt"]["rate_limit"]["fingerprint"] = "caller-invented"
    clock.advance(1)
    assert ns["probe"]()["last_attempt"]["rate_limit"] == {
        "evidence_class": "REPORTED", "fingerprint": "A11OY_SHARED_IP_LIMIT"}


@pytest.mark.parametrize("date_header", [False, True])
def test_retry_after_delays_the_next_attempt(date_header):
    calls = []
    retry_after = ["90"]

    def get(url, **kwargs):
        calls.append(url)
        return Response(429, {"error": "limited"}, {"retry-after": retry_after[0]})

    ns, clock, _ = runtime(get)
    if date_header:
        retry_after[0] = format_datetime(
            datetime.fromtimestamp(clock.time() + 90, timezone.utc), usegmt=True
        )
    assert ns["probe"]()["status"] == "UNAVAILABLE"
    clock.advance(89)
    ns["probe"]()
    assert len(calls) == 1
    clock.advance(1)
    ns["probe"]()
    assert len(calls) == 2


def test_retry_after_is_capped_and_malformed_headers_do_not_disable_spacing():
    calls = []
    headers = iter(["999999999999999999999", "not-a-date", "-1"])

    def get(url, **kwargs):
        calls.append(url)
        return Response(429, {}, {"retry-after": next(headers)})

    ns, clock, _ = runtime(get)
    ns["probe"]()
    clock.advance(299)
    ns["probe"]()
    assert len(calls) == 1
    clock.advance(1)
    ns["probe"]()
    assert len(calls) == 2
    clock.advance(29)
    ns["probe"]()
    assert len(calls) == 2
    clock.advance(271)
    ns["probe"]()
    assert len(calls) == 3


def test_backoff_grows_and_stays_bounded_without_retry_after():
    calls = []

    def get(url, **kwargs):
        calls.append(clock.monotonic())
        return Response(429, {})

    ns, clock, _ = runtime(get)
    ns["probe"]()
    clock.advance(30)
    ns["probe"]()
    assert len(calls) == 2
    clock.advance(30)
    ns["probe"]()
    assert len(calls) == 2
    clock.advance(30)
    ns["probe"]()
    assert len(calls) == 3
    for _ in range(8):
        before = len(calls)
        clock.advance(300)
        ns["probe"]()
        assert len(calls) == before + 1


def test_last_good_reuse_keeps_original_timestamp_and_expires_at_ttl():
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response() if len(calls) == 1 else Response(
            429, {"error": {"code": "rate_limited"}}, {"x-ratelimit-policy": "sliding-window;w=60"})

    ns, clock, _ = runtime(get)
    fresh = ns["probe"]()
    assert fresh["status"] == "REACHABLE"
    assert fresh["receipt_verified"] is False
    assert fresh["observation"]["cached"] is False
    assert fresh["observation"]["scope"] == "process"
    assert fresh["observation"]["age_seconds"] == 0
    assert fresh["observation"]["ttl_seconds"] == 120
    original_time = fresh["observation"]["observed_at"]
    clock.advance(15)
    cached = ns["probe"]()
    assert len(calls) == 1
    assert cached["status"] == "SNAPSHOT"
    assert cached["observation"]["cached"] is True
    assert cached["observation"]["observed_at"] == original_time
    assert cached["observation"]["age_seconds"] == 15
    clock.advance(15)
    after_429 = ns["probe"]()
    assert len(calls) == 2
    assert after_429["status"] == "SNAPSHOT"
    assert after_429["last_attempt"]["http_status"] == 429
    assert after_429["last_attempt"]["rate_limit"] == {
        "evidence_class": "REPORTED", "fingerprint": "A11OY_SHARED_IP_LIMIT"}
    assert after_429["observation"]["observed_at"] == original_time
    assert after_429["receipt_verified"] is False
    clock.advance(90)
    expired = ns["probe"]()
    assert expired["status"] == "UNAVAILABLE"
    assert expired["receipt_verified"] is False


def test_wall_clock_changes_cannot_extend_last_good_monotonic_ttl():
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response() if len(calls) == 1 else Response(503, {})

    ns, clock, _ = runtime(get)
    ns["probe"]()
    clock.monotonic_now += 121
    clock.wall_now -= 3600
    assert ns["probe"]()["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("invalid", [
    Response(200, {"schema": "other"}),
    Response(200, {**manifest(), "state": "UNAVAILABLE"}),
    Response(200, "<html>error</html>", {"content-type": "text/html"}),
    Response(200, "invalid JSON", json_error=True),
])
def test_explicit_invalid_contract_revokes_last_good_immediately(invalid):
    responses = iter([Response(), invalid])
    ns, clock, _ = runtime(lambda *_args, **_kwargs: next(responses))
    assert ns["probe"]()["status"] == "REACHABLE"
    clock.advance(30)
    revoked = ns["probe"]()
    assert revoked["status"] == "UNAVAILABLE"
    assert revoked["data"] is None
    clock.advance(1)
    assert ns["probe"]()["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 404])
def test_permanent_upstream_rejection_revokes_last_good_immediately(status):
    responses = iter([Response(), Response(status, {"error": "unavailable contract"})])
    ns, clock, _ = runtime(lambda *_args, **_kwargs: next(responses))
    assert ns["probe"]()["status"] == "REACHABLE"
    clock.advance(30)
    rejected = ns["probe"]()
    assert rejected["status"] == "UNAVAILABLE"
    assert rejected["reason"] == "UPSTREAM_REJECTED"
    assert rejected["last_attempt"]["http_status"] == status
    assert rejected["data"] is None
    assert rejected["receipt_verified"] is False
    clock.advance(1)
    assert ns["probe"]()["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_http_failure_reuses_only_the_unexpired_last_good(status):
    calls = []

    def get(*args, **kwargs):
        calls.append(args)
        return Response() if len(calls) == 1 else Response(status, {})

    ns, clock, _ = runtime(get)
    observed_at = ns["probe"]()["observation"]["observed_at"]
    clock.advance(30)
    cached = ns["probe"]()
    assert cached["status"] == "SNAPSHOT"
    assert cached["observation"]["observed_at"] == observed_at
    assert cached["observation"]["age_seconds"] == 30
    assert cached["last_attempt"]["http_status"] == status
    assert cached["receipt_verified"] is False
    clock.advance(90)
    assert ns["probe"]()["status"] == "UNAVAILABLE"


def test_mutating_a_result_cannot_modify_shared_evidence():
    ns, clock, _ = runtime(lambda *_args, **_kwargs: Response())
    result = ns["probe"]()
    original_time = result["observation"]["observed_at"]
    result["data"]["try"]["endpoint"] = "https://other.example/forged"
    result["data"]["evidence"].clear()
    result["observation"]["observed_at"] = 0
    result["last_attempt"]["http_status"] = 299
    clock.advance(1)
    cached = ns["probe"]()
    assert cached["data"] == manifest()
    assert cached["observation"]["observed_at"] == original_time
    assert cached["last_attempt"]["http_status"] == 200


def test_successful_refresh_resets_the_failure_backoff():
    responses = iter([Response(429, {}), Response(429, {}), Response(), Response(429, {}), Response()])
    calls = []

    def get(*args, **kwargs):
        calls.append(args)
        return next(responses)

    ns, clock, _ = runtime(get)
    ns["probe"]()
    clock.advance(30)
    ns["probe"]()
    clock.advance(60)
    refreshed = ns["probe"]()
    assert refreshed["status"] == "REACHABLE"
    assert len(calls) == 3
    clock.advance(30)
    assert ns["probe"]()["status"] == "SNAPSHOT"
    assert len(calls) == 4
    clock.advance(29)
    ns["probe"]()
    assert len(calls) == 4
    clock.advance(1)
    assert ns["probe"]()["status"] == "REACHABLE"
    assert len(calls) == 5


def test_concurrent_observers_share_one_inflight_request():
    entered, release, start = Event(), Event(), Event()
    call_lock = Lock()
    calls = []

    def get(url, **kwargs):
        with call_lock:
            calls.append(url)
        entered.set()
        assert release.wait(5), "test did not release the upstream observation"
        return Response(429, {})

    ns, _, _ = runtime(get)

    def observe():
        assert start.wait(5)
        return ns["probe"]()

    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = [pool.submit(observe) for _ in range(8)]
        start.set()
        try:
            assert entered.wait(5)
        finally:
            release.set()
        results = [item.result(timeout=5) for item in pending]
    assert len(calls) == 1
    assert all(item["status"] == "UNAVAILABLE" for item in results)
    assert all(item["receipt_verified"] is False for item in results)


@pytest.mark.parametrize("bad", [
    {}, [], {"hello": "world"},
    {**manifest(), "schema": "wrong"},
    {**manifest(), "state": "UNAVAILABLE"},
    {**manifest(), "try": {"method": "GET", "endpoint": "/api/a11oy/v1/verify/receipt"}},
    {**manifest(), "try": {"method": "POST", "endpoint": "https://other.example/verify"}},
    {**manifest(), "evidence": ["signature", "payload_digest"]},
])
def test_http_success_does_not_admit_a_malformed_verifier_contract(bad):
    ns, _, _ = runtime(lambda *_args, **_kwargs: Response(200, bad))
    result = ns["probe"]()
    assert result["status"] == "UNAVAILABLE"
    assert result["receipt_verified"] is False


@pytest.mark.parametrize("response", [
    Response(200, "<html>error</html>", {"content-type": "text/html"}),
    Response(200, "invalid JSON", json_error=True),
])
def test_non_json_or_invalid_json_never_becomes_last_good(response):
    ns, clock, _ = runtime(lambda *_args, **_kwargs: response)
    assert ns["probe"]()["status"] == "UNAVAILABLE"
    clock.advance(1)
    assert ns["probe"]()["status"] == "UNAVAILABLE"


def test_network_failure_stays_unavailable_and_respects_request_spacing():
    calls = []

    def get(*args, **kwargs):
        calls.append(args)
        raise OSError("provider unavailable")

    ns, _, _ = runtime(get)
    for _ in range(4):
        result = ns["probe"]()
        assert result["status"] == "UNAVAILABLE"
        assert result["receipt_verified"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("slug", ["terra", "counsel", "finance", "lyte", "vessels"])
def test_non_sentra_probe_is_unchanged(slug):
    def forbidden(*args, **kwargs):
        pytest.fail("another vertical must retain its original probe")

    ns, _, original = runtime(forbidden, slug=slug)
    assert ns["probe"] is original
    assert ns["probe"]() == {"original_probe": True}


def test_generated_live_and_readiness_share_the_budget(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import httpx

    spec = importlib.util.spec_from_file_location(
        "sentra_generated_health_fixture", ROOT / "tests/test_vertical_shell_healthz_process_scoped.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response(429, {})

    monkeypatch.setattr(httpx, "get", get)
    with TestClient(fixture._serve(tmp_path, monkeypatch, "sentra")) as client:
        live = client.get("/api/live")
        ready = client.get("/readyz")
        again = client.get("/api/live")
        health = client.get("/healthz")
    assert len(calls) == 1
    assert live.status_code == again.status_code == ready.status_code == 503
    assert live.json()["receipt_verified"] is False
    assert ready.json()["ready"] is False
    assert ready.json()["state"] == "UPSTREAM_UNAVAILABLE"
    assert ready.json()["upstream"]["http_status"] == 429
    assert health.status_code == 200 and health.json()["ok"] is True
