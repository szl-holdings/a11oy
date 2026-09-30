#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Cyber source failures remain honest at the public readiness boundary."""

import asyncio
import copy
import json
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import a11oy_vertical_feeds as vertical


ROOT = Path(__file__).resolve().parents[1]
ROUTE = "/api/a11oy/v1/vert/cyber/feed"
REPOS = ("huggingface/transformers", "openai/gpt-2", "pytorch/pytorch")


@pytest.fixture(autouse=True)
def isolated_sources(monkeypatch):
    monkeypatch.setenv("A11OY_FEED_WARM_ENABLED", "0")
    monkeypatch.setattr(vertical, "_CACHE", vertical._Cache())

    class FailedTransport:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url, **_kwargs):
            raise TimeoutError(f"source unavailable: {url}")

    # Every real adapter crosses this transport; no unit test can use upstream I/O.
    monkeypatch.setattr(vertical, "_client", FailedTransport)


def response_body():
    app = FastAPI()
    vertical.register(app)

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test.invalid"
        ) as client:
            response = await client.get(ROUTE)
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            return response.json()

    return asyncio.run(request())


def children(body):
    return [body["kev"], body["nvd"], *(body["github"][repo] for repo in REPOS),
            body["gh_events"], body["hf"]]


def install_sources(monkeypatch, sources):
    monkeypatch.setattr(vertical, "feed_cisa_kev", lambda *_a, **_k: sources[0])
    monkeypatch.setattr(vertical, "feed_nvd", lambda *_a, **_k: sources[1])
    monkeypatch.setattr(vertical, "feed_github", lambda repo: sources[2 + REPOS.index(repo)])
    monkeypatch.setattr(vertical, "feed_gh_events", lambda *_a, **_k: sources[5])
    monkeypatch.setattr(vertical, "feed_hf", lambda *_a, **_k: sources[6])


def observed_sources(now):
    return [
        {"value": {"items": [{"source_index": index}]},
         "freshness": {"status": "live", "fetched_at": now - index}}
        for index in range(7)
    ]


def readiness(body, now=None):
    """Use the shipped gate and matrix, not a test-local schema approximation."""
    node = shutil.which("node")
    assert node, "Node.js is required to verify the production readiness contract"
    probe = ROOT / "tools/readiness-harness/probe_runner.mjs"
    tabs = ROOT / "tools/readiness-harness/tabs.json"
    program = (
        'import { readFileSync } from "node:fs";\n'
        f'import * as probe from {json.dumps(probe.as_uri())};\n'
        f'const matrix = JSON.parse(readFileSync({json.dumps(str(tabs))}, "utf8"));\n'
        'const input = JSON.parse(readFileSync(0, "utf8"));\n'
        f'const path = {json.dumps(ROUTE)};\n'
        'const spec = matrix.endpoints[path];\n'
        'console.log(JSON.stringify({\n'
        ' schema: probe.validateSchema(spec.schema, input.body),\n'
        ' labels: probe.evaluateEndpointLabels(200, spec, input.body),\n'
        ' freshness: probe.evaluateFreshness(path, spec, input.body, input.now)\n'
        '}));\n'
    )
    result = subprocess.run(
        [node, "--input-type=module", "--eval", program],
        input=json.dumps({"body": body, "now": (now or time.time()) * 1000}),
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_cold_cache_upstream_failures_are_canonical_without_invented_values():
    before = time.time()
    body = response_body()
    after = time.time()
    for source in children(body):
        assert source["value"] is None
        fresh = source["freshness"]
        assert fresh["status"] == "UNAVAILABLE"
        assert before <= fresh["fetched_at"] <= after
        assert fresh["error"].startswith("TimeoutError: source unavailable:")
    assert vertical._CACHE._d == {}
    assert vertical._CACHE._inflight == {}
    assert body["sources_cited"] == vertical.cited_leaders("cyber")
    verdict = readiness(body, after)
    assert verdict["schema"]["ok"]
    assert verdict["labels"]["ok"]
    assert verdict["freshness"]["freshOk"]


def test_mixed_github_failures_preserve_independent_values_errors_and_clocks(monkeypatch):
    now = time.time()
    sources = observed_sources(now)
    for index in (2, 3, 4, 5):
        sources[index] = {
            "value": None,
            "freshness": {"status": "unavailable", "fetched_at": now - index,
                          "error": f"HTTPStatusError: 429 source {index}"},
        }
    original = copy.deepcopy(sources)
    install_sources(monkeypatch, sources)
    body = response_body()
    for index, source in enumerate(children(body)):
        expected = copy.deepcopy(original[index])
        if index in (2, 3, 4, 5):
            expected["freshness"]["status"] = "UNAVAILABLE"
        assert source == expected
    assert sources == original
    verdict = readiness(body, now)
    assert verdict["schema"]["ok"]
    assert verdict["labels"]["ok"]
    assert verdict["freshness"]["freshOk"]


def test_last_good_cache_keeps_original_clock_error_and_fails_when_too_old(monkeypatch):
    now = time.time()
    sources = observed_sources(now)
    sources[5]["freshness"] = {
        "status": "stale", "fetched_at": now - 3601,
        "age_s": 3601, "error": "refresh timed out",
    }
    original = copy.deepcopy(sources)
    install_sources(monkeypatch, sources)
    body = response_body()
    expected = copy.deepcopy(original[5])
    expected["freshness"]["status"] = "cached"
    assert body["gh_events"] == expected
    assert sources == original
    verdict = readiness(body, now)
    assert verdict["schema"]["ok"]
    assert verdict["labels"]["ok"]
    assert verdict["freshness"]["freshOk"] is False
    assert verdict["freshness"]["ageSec"] == 3601


def test_public_normalization_does_not_rewrite_the_shared_stale_cache(monkeypatch):
    now = time.time()
    real_events = vertical.feed_gh_events
    install_sources(monkeypatch, observed_sources(now))
    monkeypatch.setattr(vertical, "feed_gh_events", real_events)
    key = vertical._variant_cache_key(
        "ghev_huggingface_transformers", repo=REPOS[0], limit=12,
    )
    record = {"value": {"repo": REPOS[0], "items": [{"type": "PushEvent"}]},
              "fetched_at": now - 90, "ttl": 1, "status": "stale"}
    vertical._CACHE._d[key] = copy.deepcopy(record)
    body = response_body()
    assert vertical._CACHE._d[key] == record
    assert body["gh_events"]["value"] == record["value"]
    assert body["gh_events"]["freshness"]["status"] == "cached"
    assert body["gh_events"]["freshness"]["fetched_at"] == record["fetched_at"]
    assert body["gh_events"]["freshness"]["error"].startswith("TimeoutError:")
    verdict = readiness(body, now)
    assert verdict["schema"]["ok"]
    assert verdict["labels"]["ok"]
    assert verdict["freshness"]["freshOk"]


@pytest.mark.parametrize("missing", ["error", "fetched_at"])
def test_incomplete_unavailable_evidence_still_fails_the_unchanged_gate(monkeypatch, missing):
    now = time.time()
    sources = observed_sources(now)
    sources[5] = {"value": None, "freshness": {
        "status": "unavailable", "error": "upstream timeout", "fetched_at": now,
    }}
    del sources[5]["freshness"][missing]
    install_sources(monkeypatch, sources)
    body = response_body()
    assert body["gh_events"]["value"] is None
    assert missing not in body["gh_events"]["freshness"]
    verdict = readiness(body, now)
    assert verdict["schema"]["ok"] is False
    assert verdict["labels"]["ok"] is False
    if missing == "fetched_at":
        assert verdict["freshness"]["freshOk"] is False


def test_live_sources_are_not_relabelled_or_mutated(monkeypatch):
    now = time.time()
    sources = observed_sources(now)
    original = copy.deepcopy(sources)
    install_sources(monkeypatch, sources)
    body = response_body()
    assert children(body) == original
    assert sources == original
    verdict = readiness(body, now)
    assert verdict["schema"]["ok"]
    assert verdict["labels"]["ok"]
    assert verdict["freshness"]["freshOk"]
