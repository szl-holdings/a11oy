"""Freshness and retry contracts for the live GDW promotion proof."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest


requests = types.ModuleType("requests")


class RequestException(Exception):
    pass


class Timeout(RequestException):
    pass


class HTTPError(RequestException):
    pass


requests.RequestException = RequestException
requests.Timeout = Timeout
requests.HTTPError = HTTPError
requests.request = lambda *_args, **_kwargs: None
sys.modules.setdefault("requests", requests)


SCRIPT = Path(__file__).parents[1] / "scripts" / "prove_hf_gdw_runtime.py"
SPEC = importlib.util.spec_from_file_location("prove_hf_gdw_runtime", SCRIPT)
proof = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(proof)

SOURCE = "a" * 40
TOKEN = "t" * 32
GENERATION = "b" * 32


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_fresh_preflight_and_non_replayed_transition_pass(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return FakeResponse(404)
        return FakeResponse(200, {"replayed": False})

    monkeypatch.setattr(proof.requests, "request", fake_request)
    step, freshness = proof._fresh_transition(
        base="https://example.invalid",
        source_sha=SOURCE,
        attempt_id="1:1:proof",
        operator_token=TOKEN,
        generation_id=GENERATION,
    )
    assert step["replayed"] is False
    assert freshness["fresh_logical_write"] is True
    assert freshness["fresh_response_observed"] is True
    assert freshness["recovered_after_ambiguous_retry"] is False
    assert [call[0] for call in calls] == ["GET", "POST"]


def test_preexisting_or_first_replayed_transition_fails(monkeypatch):
    monkeypatch.setattr(
        proof.requests,
        "request",
        lambda *_args, **_kwargs: FakeResponse(200, {"replayed": False}),
    )
    with pytest.raises(RuntimeError, match="existed before"):
        proof._fresh_transition(
            base="https://example.invalid",
            source_sha=SOURCE,
            attempt_id="1:1:proof",
            operator_token=TOKEN,
            generation_id=GENERATION,
        )

    responses = iter(
        [FakeResponse(404), FakeResponse(200, {"replayed": True})]
    )
    monkeypatch.setattr(
        proof.requests,
        "request",
        lambda *_args, **_kwargs: next(responses),
    )
    with pytest.raises(RuntimeError, match="already replayed"):
        proof._fresh_transition(
            base="https://example.invalid",
            source_sha=SOURCE,
            attempt_id="1:1:proof",
            operator_token=TOKEN,
            generation_id=GENERATION,
        )


def test_ambiguous_send_recovers_exact_replay(monkeypatch):
    calls = []
    post_payload = {}

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if len(calls) == 1:
            return FakeResponse(404)
        if len(calls) == 2:
            post_payload.update(kwargs["json"])
            raise requests.Timeout("response lost after commit")
        if len(calls) == 3:
            assert kwargs["json"] == post_payload
            return FakeResponse(200, {"replayed": True})
        canonical = {
            **post_payload,
            "novelty": None,
            "disagreement": None,
            "context_tokens": 0,
            "active_tool_count": 0,
            "memory_pressure": None,
        }
        return FakeResponse(
            200,
            {
                "step": 1,
                "state": {
                    "generation_id": GENERATION,
                    "request_digest": proof._request_digest(canonical),
                },
            },
        )

    monkeypatch.setattr(proof.requests, "request", fake_request)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    step, freshness = proof._fresh_transition(
        base="https://example.invalid",
        source_sha=SOURCE,
        attempt_id="1:1:proof",
        operator_token=TOKEN,
        generation_id=GENERATION,
    )
    assert step["replayed"] is True
    assert freshness["recovered_after_ambiguous_retry"] is True
    post_calls = [item for item in calls if item[0] == "POST"]
    assert post_calls[0][2]["headers"] == post_calls[1][2]["headers"]
    assert post_calls[0][2]["json"] == post_calls[1][2]["json"]


def test_client_rejection_is_not_retried_and_attempt_changes_identity(
    monkeypatch,
):
    calls = []

    def rejected(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(404 if method == "GET" else 409)

    monkeypatch.setattr(proof.requests, "request", rejected)
    with pytest.raises(RuntimeError, match="HTTP 409"):
        proof._fresh_transition(
            base="https://example.invalid",
            source_sha=SOURCE,
            attempt_id="1:1:proof",
            operator_token=TOKEN,
            generation_id=GENERATION,
        )
    assert [item[0] for item in calls] == ["GET", "POST"]

    observed = []

    def capture(method, url, **kwargs):
        observed.append((method, url, kwargs))
        return FakeResponse(404 if method == "GET" else 200, {"replayed": False})

    monkeypatch.setattr(proof.requests, "request", capture)
    _, first = proof._fresh_transition(
        base="https://example.invalid",
        source_sha=SOURCE,
        attempt_id="1:1:proof",
        operator_token=TOKEN,
        generation_id=GENERATION,
    )
    _, second = proof._fresh_transition(
        base="https://example.invalid",
        source_sha=SOURCE,
        attempt_id="1:2:proof",
        operator_token=TOKEN,
        generation_id=GENERATION,
    )
    assert first["request_id"] != second["request_id"]
    assert first["session_id"] != second["session_id"]
    assert first["attempt_id_sha256"] != second["attempt_id_sha256"]
