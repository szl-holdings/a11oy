#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The cyber feed uses only its dedicated GitHub public reader."""

import json
import time

import httpx
import pytest

import a11oy_vertical_feeds as vertical


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())


def install_transport(monkeypatch, handler):
    requests = []

    def capture(request):
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(
        vertical, "_client",
        lambda *_args, **_kwargs: httpx.Client(
            transport=httpx.MockTransport(capture), follow_redirects=False,
        ),
    )
    return requests


@pytest.mark.parametrize(
    ("read", "response_body", "path"),
    [
        (lambda: vertical.feed_github("pytorch/pytorch"),
         {"stargazers_count": 1}, "/repos/pytorch/pytorch"),
        (lambda: vertical.feed_gh_events("pytorch/pytorch", 12),
         [{"type": "PushEvent"}], "/repos/pytorch/pytorch/events"),
    ],
)
def test_dedicated_reader_on_exact_api_origin_only(
    monkeypatch, read, response_body, path,
):
    token = "synthetic-dedicated-reader"
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", token)
    monkeypatch.setenv("GITHUB_TOKEN", "generic-token-must-not-be-used")
    requests = install_transport(
        monkeypatch, lambda _request: httpx.Response(200, json=response_body),
    )

    observed = read()

    assert len(requests) == 1
    assert requests[0].url.scheme == "https"
    assert requests[0].url.host == "api.github.com"
    assert requests[0].url.path == path
    assert requests[0].headers["authorization"] == f"Bearer {token}"
    assert observed["value"] is not None
    assert observed["freshness"]["status"] == "live"
    assert token not in json.dumps(observed)


def test_missing_dedicated_reader_stays_anonymous_and_ignores_generic_token(monkeypatch):
    monkeypatch.delenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "generic-token-must-not-be-used")
    requests = install_transport(
        monkeypatch, lambda _request: httpx.Response(200, json={}),
    )

    observed = vertical.feed_github("pytorch/pytorch")

    assert len(requests) == 1
    assert "authorization" not in requests[0].headers
    assert observed["freshness"]["status"] == "live"


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_dedicated_reader_does_not_retry_anonymously_or_leak(
    monkeypatch, status,
):
    token = "synthetic-dedicated-reader"
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", token)
    requests = install_transport(
        monkeypatch, lambda _request: httpx.Response(status, json={"message": "denied"}),
    )

    observed = vertical.feed_gh_events("pytorch/pytorch", 12)

    assert len(requests) == 1
    assert requests[0].headers["authorization"] == f"Bearer {token}"
    assert observed["value"] is None
    assert observed["freshness"]["status"] == "unavailable"
    assert observed["freshness"]["error"] == f"RuntimeError: GitHub public reader HTTP {status}"
    assert token not in json.dumps(observed)


def test_failed_refresh_preserves_last_good_clock_and_public_cache_label(monkeypatch):
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", "synthetic-dedicated-reader")
    responses = iter([
        httpx.Response(200, json={"stargazers_count": 3}),
        httpx.Response(403, json={"message": "rate limit exceeded"}),
    ])
    requests = install_transport(monkeypatch, lambda _request: next(responses))
    first = vertical.feed_github("pytorch/pytorch")
    key = vertical._variant_cache_key("gh_pytorch_pytorch", repo="pytorch/pytorch")
    original_clock = time.time() - 301
    vertical._CACHE._d[key]["fetched_at"] = original_clock

    failed = vertical.feed_github("pytorch/pytorch")
    public = vertical._readiness_public_source(failed)

    assert len(requests) == 2
    assert failed["value"] == first["value"]
    assert failed["freshness"]["status"] == "stale"
    assert failed["freshness"]["fetched_at"] == original_clock
    assert public["freshness"]["status"] == "cached"
    assert public["freshness"]["fetched_at"] == original_clock
    assert public["freshness"]["error"] == "RuntimeError: GitHub public reader HTTP 403"


def test_redirect_and_transport_error_never_disclose_dedicated_reader(monkeypatch):
    token = "synthetic-dedicated-reader"
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", token)
    requests = install_transport(
        monkeypatch,
        lambda _request: httpx.Response(
            302, headers={"Location": "https://attacker.invalid/capture"},
        ),
    )
    redirected = vertical.feed_github("pytorch/pytorch")
    assert len(requests) == 1
    assert requests[0].url.host == "api.github.com"
    assert redirected["value"] is None
    assert token not in json.dumps(redirected)

    key = vertical._variant_cache_key("gh_pytorch_pytorch", repo="pytorch/pytorch")
    assert key not in vertical._CACHE._d

    def leaking_transport(_request):
        raise RuntimeError(token)

    requests = install_transport(monkeypatch, leaking_transport)
    failed = vertical.feed_github("pytorch/pytorch")
    assert len(requests) == 1
    assert failed["freshness"]["error"] == "RuntimeError: GitHub public reader RuntimeError"
    assert token not in json.dumps(failed)


@pytest.mark.parametrize("url", [
    "http://api.github.com/repos/pytorch/pytorch",
    "https://api.github.com.evil.invalid/repos/pytorch/pytorch",
    "https://api.github.com@evil.invalid/repos/pytorch/pytorch",
    "https://api.github.com:444/repos/pytorch/pytorch",
    "https://api.github.com/user",
    "https://api.github.com/repos/pytorch/pytorch#fragment",
])
def test_dedicated_reader_rejects_other_origins_and_paths(monkeypatch, url):
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", "synthetic-dedicated-reader")
    with pytest.raises(ValueError, match="outside exact API origin"):
        vertical._github_public_headers(url)


@pytest.mark.parametrize("token", ["", "bad\nreader"])
def test_malformed_dedicated_reader_blocks_upstream_request(monkeypatch, token):
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", token)
    requests = install_transport(
        monkeypatch, lambda _request: httpx.Response(200, json={}),
    )

    observed = vertical.feed_github("pytorch/pytorch")

    assert requests == []
    assert observed["value"] is None
    assert observed["freshness"]["status"] == "unavailable"
    assert observed["freshness"]["error"] == "ValueError: GitHub public reader credential malformed"
    assert "bad" not in json.dumps(observed)
