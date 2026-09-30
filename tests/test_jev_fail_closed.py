#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline regressions for Jev measurement and outbound HTTP boundaries."""

import io
import json
import urllib.error

import pytest

import szl_jev_gate as gate
from payloads import yuyay_jev as measurement


INVALID_NUMBERS = [None, float("nan"), float("inf"), float("-inf"), "0", "bad", False, True, -0.1, 1.1, [], {}]


@pytest.mark.parametrize("polarity", ["direct", "invert"])
@pytest.mark.parametrize("value", INVALID_NUMBERS)
def test_invalid_noul_is_zero_before_polarity(polarity, value):
    assert measurement.axis_from_answer({"type": "noul", "polarity": polarity}, {"noul": value}, 0.55) == 0.0


@pytest.mark.parametrize("answer", [{}, None, [], "bad", 1])
def test_missing_or_invalid_inverted_answer_is_zero(answer):
    assert measurement.axis_from_answer({"type": "noul", "polarity": "invert"}, answer, 0.55) == 0.0


@pytest.mark.parametrize("value,expected", [(0.0, 1.0), (0.1, 0.9), (0.9, 0.1), (1.0, 0.0)])
def test_valid_hazard_inversion_is_preserved(value, expected):
    assert measurement.axis_from_answer({"type": "noul", "polarity": "invert"}, {"noul": value}, 0.55) == expected


@pytest.mark.parametrize("answer", [
    {}, {"score": None}, {"score": "1"},
    {"score": float("nan"), "confidence": 0.9, "legend": {"0": "low", "1": "high"}},
    {"score": 1, "confidence": float("nan"), "legend": {"0": "low", "1": "high"}},
    {"score": 1, "confidence": 0.1, "legend": {"0": "low", "1": "high"}},
    {"score": 1, "confidence": 0.9, "legend": {}},
    {"score": 1, "confidence": 0.9, "legend": "invalid"},
    {"score": 2, "confidence": 0.9, "legend": {"0": "low", "1": "high"}},
])
def test_invalid_score_never_inverts_to_one(answer):
    assert measurement.axis_from_answer({"type": "score", "polarity": "invert"}, answer, 0.55) == 0.0


def test_valid_score_and_missing_hazard_floor():
    answer = {"score": 1, "confidence": 0.9, "legend": {"0": "low", "1": "mid", "2": "high"}}
    assert measurement.axis_from_answer({"type": "score"}, answer, 0.55) == 0.5
    axes = {name: 0.97 for name in measurement.YUYAY_AXES}
    axes["deceptionKeywords"] = measurement.axis_from_answer({"type": "noul", "polarity": "invert"}, {}, 0.55)
    result = measurement.compose_vector(axes, model="offline-fixture", pack_hash="fixture", state_hash="fixture")
    assert result["lambda"] == 0.0
    assert result["floors_ok"] is False
    assert "deceptionKeywords" in result["floor_misses"]


class Response:
    def __init__(self, body, headers=None, status=200):
        self.body, self.headers, self.status = body, headers or {}, status
        self.read_sizes = []

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def install_payload_response(monkeypatch, response=None, error=None):
    captured = {}

    class Opener:
        def open(self, request, timeout):
            captured.update(request=request, timeout=timeout)
            if error is not None:
                raise error
            return response

    def build_opener(handler):
        captured["handler"] = handler
        return Opener()

    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-credential")
    monkeypatch.setattr(measurement.urllib.request, "build_opener", build_opener)
    return captured


def test_payload_request_is_bounded_and_refuses_redirects(monkeypatch):
    response = Response(b'{"answers":{"hazard":{"noul":0.2}}}')
    captured = install_payload_response(monkeypatch, response)
    assert measurement.call_jev({"intent": "fixture"}, {"questions": {}})["answers"]["hazard"]["noul"] == 0.2
    assert response.read_sizes == [measurement.MAX_RESPONSE_BYTES + 1]
    assert captured["timeout"] == 60
    assert captured["request"].full_url == measurement.ENDPOINT
    assert captured["handler"].redirect_request(None, None, 307, "redirect", {}, "https://elsewhere.invalid") is None


@pytest.mark.parametrize("headers,body", [
    ({"Content-Length": str(measurement.MAX_RESPONSE_BYTES + 1)}, b""),
    ({}, b"x" * (measurement.MAX_RESPONSE_BYTES + 1)),
], ids=["content-length", "stream-body"])
def test_payload_oversized_response(monkeypatch, headers, body):
    install_payload_response(monkeypatch, Response(body, headers))
    with pytest.raises(RuntimeError, match="^TYPESAFE_RESPONSE_TOO_LARGE$"):
        measurement.call_jev({}, {"questions": {}})


@pytest.mark.parametrize("body", [
    b"not JSON", b"[]", b'{}', b'{"answers":[]}', b'{"answers":{"axis":null}}',
    b'{"answers":{"axis":{"noul":NaN}}}', b'{"answers":{"axis":{"noul":1e400}}}',
    b'{"answers":{},"answers":{}}',
])
def test_payload_invalid_documents_have_safe_errors(monkeypatch, body):
    install_payload_response(monkeypatch, Response(body))
    with pytest.raises(RuntimeError, match="^TYPESAFE_INVALID_RESPONSE$"):
        measurement.call_jev({}, {"questions": {}})


def test_payload_http_error_never_reads_provider_body(monkeypatch):
    class SecretBody(io.BytesIO):
        def read(self, *args):
            raise AssertionError("provider failure body must not be read")

    error = urllib.error.HTTPError(measurement.ENDPOINT, 401, "private-detail", {}, SecretBody(b"private"))
    install_payload_response(monkeypatch, error=error)
    with pytest.raises(RuntimeError, match="^TYPESAFE_HTTP_401$"):
        measurement.call_jev({}, {"questions": {}})


@pytest.mark.parametrize("value,code", [(float("nan"), "TYPESAFE_INVALID_REQUEST"), ("x" * (measurement.MAX_REQUEST_BYTES + 1), "TYPESAFE_REQUEST_TOO_LARGE")], ids=["non-finite", "oversized"])
def test_payload_invalid_request_does_not_call_provider(monkeypatch, value, code):
    captured = install_payload_response(monkeypatch)
    with pytest.raises(RuntimeError, match=f"^{code}$"):
        measurement.call_jev({"fixture": value}, {"questions": {}})
    assert "request" not in captured


def test_gate_uses_existing_bounded_transport(monkeypatch):
    captured = {}

    def transport(url, **kwargs):
        captured.update(url=url, **kwargs)
        return {"answers": {"promote_ok": {"noul": 0.1}}}, None

    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-credential")
    monkeypatch.setattr(gate, "http_json", transport)
    assert gate.call_jev({"fixture": True})["ok"] is True
    assert captured["url"] == gate.ENDPOINT
    assert captured["timeout"] == 30.0
    assert captured["max_response_bytes"] == gate.MAX_RESPONSE_BYTES
    assert captured["max_redirects"] == 0
    assert captured["allow_private"] is False
    assert json.loads(captured["body"])["questions"] == gate.questions()


@pytest.mark.parametrize("document", [None, [], {}, {"answers": {}}, {"answers": []}, {"answers": {"a": None}}, {"answers": {"a": {"noul": float("nan")}}}])
def test_gate_rejects_malformed_response(monkeypatch, document):
    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-credential")
    monkeypatch.setattr(gate, "http_json", lambda *args, **kwargs: (document, None))
    result = gate.call_jev_questions({}, {})
    assert result["ok"] is False
    assert result["reason"] == "TYPESAFE_INVALID_RESPONSE"
    assert result["answers"] is None


@pytest.mark.parametrize("error,reason", [
    ("HTTP_STATUS:401", "TYPESAFE_HTTP_401"), ("HTTP_STATUS:429", "TYPESAFE_HTTP_429"),
    ("REDIRECT_LIMIT_EXCEEDED", "TYPESAFE_TRANSPORT"), ("RESPONSE_TOO_LARGE", "TYPESAFE_RESPONSE_TOO_LARGE"),
    ("INVALID_JSON", "TYPESAFE_INVALID_RESPONSE"), ("private upstream detail", "TYPESAFE_TRANSPORT"),
])
def test_gate_transport_errors_are_safe(monkeypatch, error, reason):
    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-credential")
    monkeypatch.setattr(gate, "http_json", lambda *args, **kwargs: (None, error))
    assert gate.call_jev({}) == {"ok": False, "engine": gate.engine_status(), "answers": None, "reason": reason}


def test_gate_exception_is_not_exposed(monkeypatch):
    def transport(*args, **kwargs):
        raise RuntimeError("private token and body")

    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-credential")
    monkeypatch.setattr(gate, "http_json", transport)
    assert gate.call_jev({})["reason"] == "TYPESAFE_TRANSPORT"


@pytest.mark.parametrize("value,reason", [(float("nan"), "TYPESAFE_INVALID_REQUEST"), ("x" * (gate.MAX_REQUEST_BYTES + 1), "TYPESAFE_REQUEST_TOO_LARGE")], ids=["non-finite", "oversized"])
def test_gate_invalid_request_does_not_call_provider(monkeypatch, value, reason):
    monkeypatch.setenv("TYPESAFE_API_KEY", "offline-test-credential")

    def forbidden(*args, **kwargs):
        raise AssertionError("must not call provider")

    monkeypatch.setattr(gate, "http_json", forbidden)
    assert gate.call_jev({"fixture": value})["reason"] == reason


@pytest.mark.parametrize("value", INVALID_NUMBERS)
def test_gate_malformed_confidence_cannot_be_admitted(value):
    answers = {"claim_kind": {"choice": "MEASURED", "confidence": value}, "card_relation": {"choice": "supports", "confidence": 0.99}, "promote_ok": {"noul": 0.99}, "evidence_strength": {"score": 3}}
    result = gate.compose("scoped claim", "fixture evidence", answers)
    assert result["verdict"] == "ABSTAIN"
    assert result["trust"]["admitted"] == 0.0
    assert result["promotion"] == "denied"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value", INVALID_NUMBERS)
def test_gate_malformed_clearance_hazard_is_blocked(value):
    answers = {"authority_class": {"choice": "OFAC-vessel"}, "miss_is_clearance": {"noul": value}}
    result = gate.compose_public_text("fixture", "fixture", answers)
    assert result["verdict"] == "BLOCKED"
    assert result["is_clearance"] is False
    assert result["miss_is_clearance_noul"] == 1.0
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("answers", [None, [], {}, {"claim_kind": "bad", "card_relation": []}])
def test_malformed_answers_cannot_create_optimistic_judgment(answers):
    result = gate.compose("scoped claim", "fixture", answers)
    assert result["verdict"] == "UNKNOWN"
    assert result["trust"]["admitted"] == 0.0
    assert result["promotion"] == "denied"
