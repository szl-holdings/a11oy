#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline transport fixtures for the operator model declaration diagnostic."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/check_model_declaration.py"
SPEC = importlib.util.spec_from_file_location("model_declaration_check", PATH)
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)
SOURCE = "a" * 40
BASE = "https://reviewed-model.example/v1"
DECLARED = "Qwen/Qwen2.5-Coder-32B-Instruct"
ADVERTISED = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


def run_fixture(*, listed=None, change=None, response=None, raw=None):
    calls = []
    build_reads = 0
    declaration_reads = 0

    def handler(request):
        nonlocal build_reads, declaration_reads
        calls.append(request)
        url = str(request.url)
        if url == subject.BUILD:
            build_reads += 1
            revision = "b" * 40 if change == "source" and build_reads > 1 else SOURCE
            return httpx.Response(200, json={"build": {"revision": revision}})
        if url == subject.MODELS:
            declaration_reads += 1
            endpoint = "https://unreviewed.example/v1" if change == "endpoint" else BASE
            model = ADVERTISED if change == "declaration" and declaration_reads > 1 else DECLARED
            return httpx.Response(200, json={"endpoint": endpoint, "backend": {
                "configured": True, "endpoint": endpoint, "primary_model": model}})
        assert url == BASE + "/models"
        if response is not None:
            return response
        if raw is not None:
            return httpx.Response(200, content=raw, headers={"content-type": "application/json"})
        return httpx.Response(200, json={"data": [{"id": item} for item in
                                               (listed if listed is not None else [DECLARED])]})

    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        report = subject.check(client, SOURCE, BASE)
    return report, calls


def test_listing_match_is_never_inference_or_production_authority():
    report, calls = run_fixture()
    assert report["status"] == "DECLARATION_LISTED"
    assert report["declaration_matches_listing"] is True
    assert report["source_bracket_unchanged"] is True
    assert report["declared_model_id"] == DECLARED
    for flag in ("inference_verified", "weights_verified", "hardware_verified",
                 "production_ready", "execution_authorized", "provider_state_changed"):
        assert report[flag] is False
    assert [str(call.url) for call in calls] == [
        subject.BUILD, subject.MODELS, BASE + "/models", subject.MODELS, subject.BUILD]
    assert all(call.method == "GET" and not call.content for call in calls)
    assert all("authorization" not in call.headers and "cookie" not in call.headers for call in calls)


def test_declared_32b_does_not_match_advertised_1_5b():
    report, calls = run_fixture(listed=[ADVERTISED])
    assert report["status"] == report["error"] == "DECLARED_MODEL_NOT_LISTED"
    assert report["declaration_matches_listing"] is False
    assert report["declared_model_id"] == DECLARED
    assert report["advertised_model_ids"] == [ADVERTISED]
    assert len(calls) == 5


@pytest.mark.parametrize("change,error,requests", [
    ("endpoint", "MODEL_ENDPOINT_CHANGED", 2),
    ("declaration", "MODEL_DECLARATION_CHANGED", 4),
    ("source", "SOURCE_REVISION_MISMATCH", 5),
])
def test_drift_fails_closed(change, error, requests):
    report, calls = run_fixture(change=change)
    assert report["status"] == "UNAVAILABLE"
    assert report["error"] == error
    assert not report["declaration_matches_listing"]
    assert not report["source_bracket_unchanged"]
    assert len(calls) == requests


@pytest.mark.parametrize("base", [
    "http://reviewed-model.example/v1", "https://localhost/v1",
    "https://127.0.0.1/v1", "https://[::1]/v1", "https://10.0.0.1/v1",
    "https://user:private-value@reviewed-model.example/v1",
    "https://reviewed-model.example/v1?token=private-value",
    "https://reviewed-model.example/v1#private-value",
    "https://reviewed-model.example:444/v1", "https://reviewed-model.example/arbitrary",
    "https://reviewed-model.example/v1\n", "https://metadata.internal/v1",
])
def test_unreviewable_target_is_refused_before_any_read(base):
    def forbidden(_):
        pytest.fail("Invalid explicit target must not cause a request")

    with httpx.Client(transport=httpx.MockTransport(forbidden), trust_env=False) as client:
        report = subject.check(client, SOURCE, base)
    assert report["failure_stage"] == "INPUT"
    assert report["status"] == "UNAVAILABLE"
    assert "private-value" not in json.dumps(report)


@pytest.mark.parametrize("rows", [[], [DECLARED, DECLARED], ["has a space"], [None],
                                  [DECLARED] * (subject.MAX_MODELS + 1)])
def test_malformed_or_ambiguous_model_lists_fail_closed(rows):
    report, _ = run_fixture(listed=rows)
    assert report["error"] == "MODEL_LIST_INVALID"
    assert report["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("raw", [
    b'{"data":[],"data":[{"id":"Qwen/example"}]}',
    b'{"data":[{"id":"Qwen/example","id":"Qwen/changed"}]}',
    b'{"data":[],"value":NaN}', b'not-json', b'[]', b'\xff',
])
def test_untrusted_json_is_not_accepted(raw):
    report, _ = run_fixture(raw=raw)
    assert report["error"] in ("JSON_INVALID", "READ_OBJECT_REQUIRED")
    assert report["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("response,error", [
    (httpx.Response(302, headers={"location": "https://unreviewed.example/"}),
     "READ_RESPONSE_UNAVAILABLE"),
    (httpx.Response(401, text="private-value"), "READ_RESPONSE_UNAVAILABLE"),
    (httpx.Response(200, text="private-value", headers={"content-type": "text/html"}),
     "READ_JSON_REQUIRED"),
    (httpx.Response(200, stream=httpx.ByteStream(b"{}"), headers={"content-type": "application/json",
                                              "content-encoding": "gzip"}),
     "READ_ENCODING_INVALID"),
    (httpx.Response(200, content=b"{}", headers={"content-type": "application/json",
                                              "content-length": str(subject.MAX_BYTES + 1)}),
     "READ_SIZE_INVALID"),
])
def test_http_failures_are_single_shot_and_sanitized(response, error):
    report, calls = run_fixture(response=response)
    assert report["error"] == error
    assert report["failure_stage"] == "PROVIDER_LIST"
    assert len(calls) == 3
    assert "private-value" not in json.dumps(report)


def test_streaming_body_is_bounded_without_content_length():
    class Oversized(httpx.SyncByteStream):
        def __iter__(self):
            yield b" " * (subject.MAX_BYTES + 1)

    response = httpx.Response(200, stream=Oversized(),
                             headers={"content-type": "application/json"})
    report, _ = run_fixture(response=response)
    assert report["error"] == "READ_SIZE_INVALID"


def test_transport_error_does_not_echo_endpoint_or_exception():
    def broken(request):
        raise httpx.ConnectError("private-value", request=request)

    with httpx.Client(transport=httpx.MockTransport(broken), trust_env=False) as client:
        report = subject.check(client, SOURCE, BASE)
    assert report["error"] == "READ_TRANSPORT_UNAVAILABLE"
    assert "private-value" not in json.dumps(report)


def test_source_required_before_any_read():
    with httpx.Client(transport=httpx.MockTransport(
            lambda _: pytest.fail("No read without an exact source")), trust_env=False) as client:
        report = subject.check(client, "main", BASE)
    assert report["error"] == "EXACT_SOURCE_REQUIRED"


@pytest.mark.parametrize("options", [
    {"auth": ("user", "private-value")},
    {"headers": {"Authorization": "Bearer private-value"}},
    {"headers": {"Cookie": "session=private-value"}},
    {"cookies": {"session": "private-value"}},
])
def test_credentialled_client_is_refused_before_network(options):
    def forbidden(_):
        pytest.fail("A supplied credential must never be sent")

    with httpx.Client(transport=httpx.MockTransport(forbidden), trust_env=False, **options) as client:
        report = subject.check(client, SOURCE, BASE)
    assert report["error"] == "CREDENTIALLED_CLIENT_REFUSED"
    assert report["status"] == "UNAVAILABLE"
    assert "private-value" not in json.dumps(report)
