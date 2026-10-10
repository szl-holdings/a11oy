#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The cyber feed uses its dedicated GitHub public reader.

An absent reader may observe the public commits Atom feed when the events
API returns no row. A configured reader is never retried on another origin.
"""

import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import a11oy_vertical_feeds as vertical


_ROOT = Path(__file__).resolve().parents[1]
_CYBER_ROUTE = "/api/a11oy/v1/vert/cyber/feed"


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
    "https://api.github.com/repos/../user",
    "https://api.github.com/repos/pytorch/..",
    "https://api.github.com/repos/pytorch/%2e%2e",
    "https://api.github.com/repos/pytorch/repo%2fevents",
    "https://api.github.com/repos/pytorch/repo?redirect=/user",
    "https://api.github.com/repos/pytorch/repo/events?per_page=12&redirect=/user",
])
def test_dedicated_reader_rejects_other_origins_and_paths(monkeypatch, url):
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", "synthetic-dedicated-reader")
    with pytest.raises(ValueError, match="outside exact API origin"):
        vertical._github_public_headers(url)


@pytest.mark.parametrize("repo", [
    "../user",
    "pytorch/..",
    "pytorch/%2e%2e",
    "pytorch/repo%2f..",
    "pytorch/repo/../user",
    "pytorch/repo?redirect=/user",
])
@pytest.mark.parametrize("read", [
    vertical.feed_github,
    lambda repo: vertical.feed_gh_events(repo, 12),
])
def test_untrusted_repo_never_sends_reader_to_normalized_path(monkeypatch, repo, read):
    token = "synthetic-dedicated-reader"
    monkeypatch.setenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", token)
    requests = install_transport(
        monkeypatch, lambda _request: httpx.Response(200, json={}),
    )

    observed = read(repo)

    assert requests == []
    assert observed["value"] is None
    assert observed["freshness"]["status"] == "unavailable"
    assert observed["freshness"]["error"] == (
        "ValueError: GitHub public reader URL outside exact API origin"
    )
    assert token not in json.dumps(observed)


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


def _commits_atom(owner, repo, entries):
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"<id>tag:github.com,2008:/{owner}/{repo}/commits/main</id>",
    ]
    for sha, actor, updated, linked in entries:
        href = (f"https://github.com/{owner}/{repo}/commit/{sha}" if linked
                else "https://example.invalid/commit")
        body.append(
            "<entry>"
            f"<id>tag:github.com,2008:Grit::Commit/{sha}</id>"
            f'<link href="{href}"/>'
            f"<updated>{updated}</updated>"
            f"<author><name>{actor}</name></author>"
            "</entry>"
        )
    body.append("</feed>")
    return "".join(body).encode()


def _cyber_probe(body, now_s):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the shipped readiness evaluator")
    probe = _ROOT / "tools/readiness-harness/probe_runner.mjs"
    tabs = _ROOT / "tools/readiness-harness/tabs.json"
    program = (
        'import { readFileSync } from "node:fs";\n'
        f'import * as probe from {json.dumps(probe.as_uri())};\n'
        f'const matrix = JSON.parse(readFileSync({json.dumps(str(tabs))}, "utf8"));\n'
        'const input = JSON.parse(readFileSync(0, "utf8"));\n'
        f'const path = {json.dumps(_CYBER_ROUTE)};\n'
        'const spec = matrix.endpoints[path];\n'
        'console.log(JSON.stringify({\n'
        ' schema: probe.validateSchema(spec.schema, input.body),\n'
        ' labels: probe.evaluateEndpointLabels(200, spec, input.body),\n'
        ' freshness: probe.evaluateFreshness(path, spec, input.body, input.now)\n'
        '}));\n'
    )
    result = subprocess.run(
        [node, "--input-type=module", "--eval", program],
        input=json.dumps({"body": body, "now": now_s * 1000}),
        cwd=_ROOT, capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _live_source(now):
    return {"value": {"items": [{"id": "observed"}]},
            "freshness": {"status": "live", "fetched_at": now}}


def test_anonymous_events_rate_limit_observes_public_commits(monkeypatch):
    monkeypatch.delenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "generic-token-must-not-be-used")
    monkeypatch.setenv("A11OY_FEED_WARM_ENABLED", "0")
    sha = "536ecc007387a50e77603bb5d92100e9b07514cc"
    older = "4f2db3309eb2b95b86090f8199482f522ccd6323"
    xml = _commits_atom("huggingface", "transformers", [
        (sha, "Rocketknight1", "2026-10-09T17:01:40Z", True),
        (older, "skipped", "2026-10-09T17:00:00Z", False),
        ("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "Other", "2026-10-09T16:00:00Z", True),
    ])

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403, json={"message": "rate limit exceeded"})
        if (request.url.host == "github.com"
                and request.url.path == "/huggingface/transformers/commits.atom"):
            return httpx.Response(200, content=xml)
        raise AssertionError(f"unexpected {request.url}")

    requests = install_transport(monkeypatch, handler)
    now = time.time()
    for name in ("feed_cisa_kev", "feed_nvd", "feed_github", "feed_hf"):
        monkeypatch.setattr(vertical, name, lambda *_a, **_k: _live_source(now))
    app = FastAPI()
    vertical.register(app)

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test.invalid",
        ) as client:
            response = await client.get(_CYBER_ROUTE)
            assert response.status_code == 200
            return response.json()

    body = asyncio.run(request())
    events = body["gh_events"]
    assert events["freshness"]["status"] == "live"
    assert events["value"]["source"] == "GitHub public commits Atom feed"
    assert events["value"]["source_url"] == (
        "https://github.com/huggingface/transformers/commits.atom"
    )
    assert events["value"]["retrieval"] == "github-commits-atom"
    assert events["value"]["items"] == [
        {"type": "Commit", "actor": "Rocketknight1",
         "created": "2026-10-09T17:01:40Z",
         "ref": f"https://github.com/huggingface/transformers/commit/{sha}"},
        {"type": "Commit", "actor": "Other",
         "created": "2026-10-09T16:00:00Z",
         "ref": "https://github.com/huggingface/transformers/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
    ]
    assert "authorization" not in requests[0].headers
    assert "authorization" not in requests[1].headers
    assert [item.url.host for item in requests] == ["api.github.com", "github.com"]
    verdict = _cyber_probe(body, time.time())
    assert verdict["schema"]["ok"] is True
    assert verdict["labels"]["ok"] is True
    assert "gh_events" not in verdict["labels"]["unavailableSources"]
    assert verdict["freshness"]["freshOk"] is True

    limited = vertical.feed_gh_events("huggingface/transformers", 1)
    assert limited["value"]["items"] == events["value"]["items"][:1]
    assert [item.url.host for item in requests] == [
        "api.github.com", "github.com", "api.github.com",
    ]


def test_events_api_observation_is_not_replaced_by_the_commits_feed(monkeypatch):
    monkeypatch.delenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", raising=False)

    def handler(request):
        if request.url.host == "github.com":
            raise AssertionError("commits feed must not run when the events API has a row")
        return httpx.Response(200, json=[{
            "type": "PushEvent",
            "actor": {"login": "octocat"},
            "created_at": "2026-10-09T00:00:00Z",
            "payload": {"ref": "refs/heads/main"},
        }])

    requests = install_transport(monkeypatch, handler)
    observed = vertical.feed_gh_events("pytorch/pytorch", 12)
    assert len(requests) == 1
    assert observed["value"]["items"] == [{
        "type": "PushEvent", "actor": "octocat",
        "created": "2026-10-09T00:00:00Z", "ref": "refs/heads/main",
    }]
    assert "source" not in observed["value"]


def test_anonymous_events_failure_without_commits_stays_unavailable(monkeypatch):
    monkeypatch.delenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", raising=False)

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403, json={"message": "rate limit exceeded"})
        return httpx.Response(404, text="missing")

    requests = install_transport(monkeypatch, handler)
    observed = vertical.feed_gh_events("pytorch/pytorch", 12)
    assert [item.url.host for item in requests] == ["api.github.com", "github.com"]
    assert observed["value"] is None
    assert observed["freshness"]["status"] == "unavailable"
    assert observed["freshness"]["error"].startswith("HTTPStatusError:")
    assert "403" in observed["freshness"]["error"]
    assert "GitHub commits atom" not in observed["freshness"]["error"]


@pytest.mark.parametrize("xml", [
    b"<?xml version='1.0'?><!DOCTYPE feed [<!ENTITY x 'y'>]><feed></feed>",
    b"<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><id>tag:github.com,2008:/pytorch/pytorch/commits/main</id></feed>",
    b"not xml",
])
def test_unobservable_commits_atom_does_not_invent_events(monkeypatch, xml):
    monkeypatch.delenv("A11OY_GITHUB_PUBLIC_READ_TOKEN", raising=False)

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403, json={"message": "rate limit exceeded"})
        return httpx.Response(200, content=xml)

    install_transport(monkeypatch, handler)
    observed = vertical.feed_gh_events("pytorch/pytorch", 12)
    assert observed["value"] is None
    assert observed["freshness"]["status"] == "unavailable"
    assert observed["freshness"]["error"].startswith("HTTPStatusError:")
