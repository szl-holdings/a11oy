#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the mounted cyber feed against the unchanged readiness harness."""

import asyncio
import copy
import json
from pathlib import Path
import shutil
import subprocess
import time

from fastapi import FastAPI
import httpx
import pytest

import a11oy_vertical_feeds as vertical


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "/api/a11oy/v1/vert/cyber/feed"
PROBE = ROOT / "tools/readiness-harness/probe_runner.mjs"
SOURCE_PATHS = (
    ("kev",),
    ("nvd",),
    ("github", "huggingface/transformers"),
    ("github", "openai/gpt-2"),
    ("github", "pytorch/pytorch"),
    ("gh_events",),
    ("hf",),
)


def _at_path(body, path):
    result = body
    for key in path:
        result = result[key]
    return result


@pytest.fixture
def cyber_response(monkeypatch):
    monkeypatch.setenv("A11OY_FEED_WARM_ENABLED", "0")
    observed_at = time.time() - 5
    observed = {
        "value": {"items": [{"id": "observed-source-record"}]},
        "freshness": {"status": "live", "fetched_at": observed_at, "age_s": 5},
    }
    sources = {
        "kev": copy.deepcopy(observed),
        "nvd": copy.deepcopy(observed),
        "github": {repo: copy.deepcopy(observed) for repo in (
            "huggingface/transformers", "openai/gpt-2", "pytorch/pytorch",
        )},
        "gh_events": copy.deepcopy(observed),
        "hf": copy.deepcopy(observed),
    }
    for repo, entry in sources["github"].items():
        entry["value"] = {"repo": repo, "stars": 1, "forks": 1, "issues": 0}

    monkeypatch.setattr(vertical, "feed_cisa_kev", lambda *args: sources["kev"])
    monkeypatch.setattr(vertical, "feed_nvd", lambda *args: sources["nvd"])
    monkeypatch.setattr(vertical, "feed_github", lambda repo: sources["github"][repo])
    monkeypatch.setattr(vertical, "feed_gh_events", lambda *args: sources["gh_events"])
    monkeypatch.setattr(vertical, "feed_hf", lambda *args: sources["hf"])

    def no_network():
        raise AssertionError("cyber route regression must use retained source fixtures")

    monkeypatch.setattr(vertical, "_client", no_network)
    app = FastAPI()
    vertical.register(app, ns="a11oy")

    @app.get("/{path:path}")
    async def shell(path: str):
        return {"shell": path}

    def request():
        async def exercise():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://a11oy.test",
            ) as client:
                response = await client.get(ENDPOINT)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/json")
            result = response.json()
            assert result["vertical"] == "cyber"
            assert "shell" not in result
            return result

        return asyncio.run(exercise())

    return sources, request


def _harness_result(body):
    node = shutil.which("node")
    assert node is not None, "Node is required to exercise the production readiness checker"
    program = (
        'import { readFileSync } from "node:fs";\n'
        f'import * as probe from {json.dumps(PROBE.as_uri())};\n'
        f'const tabs = JSON.parse(readFileSync({json.dumps(str(PROBE.parent / "tabs.json"))}, "utf8"));\n'
        'const body = JSON.parse(readFileSync(0, "utf8"));\n'
        f'const spec = tabs.endpoints[{json.dumps(ENDPOINT)}];\n'
        'const schema = probe.validateSchema(spec.schema, body);\n'
        'const labels = probe.evaluateEndpointLabels(200, spec, body);\n'
        f'const freshness = probe.evaluateFreshness({json.dumps(ENDPOINT)}, spec, body);\n'
        'console.log(JSON.stringify({schema, labels, freshness}));\n'
    )
    result = subprocess.run(
        [node, "--input-type=module", "--eval", program],
        input=json.dumps(body), text=True, capture_output=True,
        cwd=ROOT, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("path", SOURCE_PATHS)
def test_mounted_cyber_cold_failure_is_typed_without_inventing_data(cyber_response, path):
    sources, request = cyber_response
    source = _at_path(sources, path)
    source.clear()
    source.update({
        "value": None,
        "freshness": {
            "status": "unavailable", "fetched_at": time.time() - 2,
            "error": "ReadTimeout: bounded upstream attempt failed",
        },
    })
    before = copy.deepcopy(sources)
    body = request()
    public = _at_path(body, path)
    assert public["value"] is None
    assert public["freshness"] == {**source["freshness"], "status": "UNAVAILABLE"}
    assert sources == before
    for other in SOURCE_PATHS:
        if other != path:
            assert _at_path(body, other) == _at_path(sources, other)
    verdict = _harness_result(body)
    assert verdict["schema"]["ok"], verdict
    assert verdict["labels"]["ok"], verdict
    assert verdict["freshness"]["freshOk"], verdict


def test_mixed_cyber_sources_preserve_each_failure_and_last_good_clock(cyber_response):
    sources, request = cyber_response
    old_clock = time.time() - 30
    sources["nvd"]["freshness"].update({
        "status": "stale", "fetched_at": old_clock, "error": "refresh timeout",
    })
    for path in SOURCE_PATHS[2:6]:
        source = _at_path(sources, path)
        source.update({"value": None, "freshness": {
            "status": "unavailable", "fetched_at": time.time() - 2,
            "error": "HTTPStatusError: upstream rejected the bounded read",
        }})
    before = copy.deepcopy(sources)
    body = request()
    assert body["nvd"]["value"] == sources["nvd"]["value"]
    assert body["nvd"]["freshness"]["status"] == "cached"
    assert body["nvd"]["freshness"]["fetched_at"] == old_clock
    assert body["nvd"]["freshness"]["error"] == "refresh timeout"
    assert sources == before
    verdict = _harness_result(body)
    assert verdict["schema"]["ok"] and verdict["labels"]["ok"], verdict
    assert verdict["freshness"]["freshOk"], verdict


@pytest.mark.parametrize("path", [SOURCE_PATHS[index] for index in (0, 1, 5, 6)])
def test_last_good_cyber_data_cannot_hide_expired_observation(cyber_response, path):
    sources, request = cyber_response
    source = _at_path(sources, path)
    old_clock = time.time() - 3601
    source["freshness"].update({
        "status": "stale", "fetched_at": old_clock, "error": "refresh timeout",
    })
    public = request()
    result = _at_path(public, path)
    assert result["value"] == source["value"]
    assert result["freshness"]["status"] == "cached"
    assert result["freshness"]["fetched_at"] == old_clock
    verdict = _harness_result(public)
    assert verdict["labels"]["ok"], verdict
    assert not verdict["freshness"]["freshOk"], verdict


@pytest.mark.parametrize("path", [SOURCE_PATHS[index] for index in (0, 1, 5, 6)])
@pytest.mark.parametrize("clock", [
    pytest.param("missing", id="missing"),
    pytest.param(None, id="null"),
    pytest.param("invalid-clock", id="malformed"),
])
def test_retained_cyber_data_needs_its_original_observation_clock(
    cyber_response, path, clock,
):
    sources, request = cyber_response
    source = _at_path(sources, path)
    source["freshness"] = {
        "status": "stale", "age_s": 5, "error": "refresh timeout",
    }
    if clock != "missing":
        source["freshness"]["fetched_at"] = clock
    before = copy.deepcopy(sources)
    body = request()
    public = _at_path(body, path)
    assert public["value"] == source["value"]
    assert public["freshness"] == {**source["freshness"], "status": "cached"}
    assert sources == before
    verdict = _harness_result(body)
    assert not verdict["schema"]["ok"], verdict
    assert not verdict["freshness"]["freshOk"], verdict


@pytest.mark.parametrize("age_s", [
    pytest.param(5, id="positive"),
    pytest.param(-86400, id="negative"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="positive-infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
])
def test_retained_source_age_cannot_synthesize_an_observation_clock(age_s):
    source = {
        "value": {"items": [{"id": "observed-source-record"}]},
        "freshness": {
            "status": "stale", "age_s": age_s, "error": "refresh timeout",
        },
    }
    public = vertical._readiness_public_source(source)
    assert public["value"] == source["value"]
    assert public["freshness"]["status"] == "cached"
    assert public["freshness"]["age_s"] is source["freshness"]["age_s"]
    assert "fetched_at" not in public["freshness"]
    assert "fetched_at" not in source["freshness"]
    assert source["freshness"]["status"] == "stale"


def test_negative_retained_cyber_age_cannot_become_a_fresh_current_clock(cyber_response):
    sources, request = cyber_response
    source = sources["gh_events"]
    source["freshness"] = {
        "status": "stale", "age_s": -86400, "error": "refresh timeout",
    }
    body = request()
    assert "fetched_at" not in body["gh_events"]["freshness"]
    verdict = _harness_result(body)
    assert not verdict["schema"]["ok"], verdict
    assert not verdict["freshness"]["freshOk"], verdict


@pytest.mark.parametrize("path", SOURCE_PATHS[2:5])
def test_supplemental_repository_metadata_preserves_last_good_observation(cyber_response, path):
    sources, request = cyber_response
    source = _at_path(sources, path)
    original = copy.deepcopy(source)
    source["freshness"].update({"status": "stale", "error": "refresh timeout"})
    body = request()
    public = _at_path(body, path)
    assert public["value"] == original["value"]
    assert public["freshness"] == {**source["freshness"], "status": "cached"}
    assert source["freshness"]["status"] == "stale"


@pytest.mark.parametrize("status", ["vendor-pending", "", "live unavailable"])
@pytest.mark.parametrize("path", [("gh_events",), ("github", "openai/gpt-2")])
def test_unknown_cyber_status_cannot_be_laundered_into_failure_evidence(
    cyber_response, status, path,
):
    sources, request = cyber_response
    source = _at_path(sources, path)
    source.update({"value": None, "freshness": {
        "status": status, "fetched_at": time.time() - 2, "error": "provider rejected read",
    }})
    body = request()
    assert _at_path(body, path) == source
    verdict = _harness_result(body)
    assert not verdict["schema"]["ok"] or not verdict["labels"]["ok"], verdict


@pytest.mark.parametrize("malformation", ["missing_error", "blank_error", "invalid_clock", "missing_clock", "invented_items"])
def test_malformed_cyber_failure_cannot_pass_the_readiness_contract(cyber_response, malformation):
    sources, request = cyber_response
    source = sources["gh_events"]
    source.update({"value": None, "freshness": {
        "status": "unavailable", "fetched_at": time.time() - 2, "error": "bounded timeout",
    }})
    if malformation == "missing_error":
        source["freshness"].pop("error")
    elif malformation == "blank_error":
        source["freshness"]["error"] = " "
    elif malformation == "invalid_clock":
        source["freshness"]["fetched_at"] = "invalid-clock"
    elif malformation == "missing_clock":
        source["freshness"].pop("fetched_at")
    else:
        source["freshness"]["status"] = "UNAVAILABLE"
        source["value"] = {"items": []}
    body = request()
    verdict = _harness_result(body)
    assert not verdict["schema"]["ok"] or not verdict["labels"]["ok"], verdict
