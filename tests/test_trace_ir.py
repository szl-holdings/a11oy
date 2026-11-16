#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Adversarial tests for unsigned, content-free receipt observations."""
import hashlib
import json

import pytest

from vsp_otel.trace_ir import CHECKS, gated_minimum, receipt_observation


TRACE = "00-" + "1" * 32 + "-" + "2" * 16 + "-01"
INVALID_NUMBERS = [
    float("nan"), float("inf"), float("-inf"), True, False,
    "1.0", None, [], {}, -0.01, 1.01, 10**10000,
]


def strict_json(value):
    return json.dumps(value, allow_nan=False, sort_keys=True)


@pytest.mark.parametrize("value", INVALID_NUMBERS, ids=["nan", "inf", "negative_inf", "true", "false", "string", "none", "list", "dict", "negative", "above_one", "huge_int"])
def test_invalid_threshold_always_holds_and_serializes(value):
    result = gated_minimum({"check": 1}, required_checks=["check"], threshold=value)
    assert result["decision"] == "HOLD"
    assert result["reason_codes"] == ["INVALID_THRESHOLD"]
    assert result["threshold"] is None
    strict_json(result)


@pytest.mark.parametrize("value", INVALID_NUMBERS, ids=["nan", "inf", "negative_inf", "true", "false", "string", "none", "list", "dict", "negative", "above_one", "huge_int"])
def test_invalid_score_always_holds_and_serializes(value):
    result = gated_minimum({"check": value}, required_checks=["check"])
    assert result["decision"] == "HOLD"
    assert result["minimum"] is None
    assert result["reason_codes"] == ["INVALID_SCORE"]
    strict_json(result)


@pytest.mark.parametrize("required", [
    [], (), set(), "check", None, ["check", "check"], [""], [True],
    [["unhashable"]], ["Bearer secret-marker"], ["x" * 65], [str(i) for i in range(33)],
])
def test_invalid_required_policy_fails_closed(required):
    result = gated_minimum({"check": 1}, required_checks=required)
    assert result["decision"] == "HOLD"
    assert result["reason_codes"] == ["INVALID_REQUIRED_CHECKS"]
    assert "secret-marker" not in strict_json(result)


@pytest.mark.parametrize("scores,reason", [
    ({}, "MISSING_REQUIRED_CHECK"),
    ({"accuracy": 1}, "MISSING_REQUIRED_CHECK"),
    ({"check": 1, "unknown": 1}, "UNEXPECTED_CHECK"),
    ({"check": 1, "Bearer secret-marker": 1}, "INVALID_SCORES"),
    ({"check": 0.999}, "BELOW_THRESHOLD"),
    ([], "INVALID_SCORES"),
    (None, "INVALID_SCORES"),
    ({"x" + str(i): 1 for i in range(33)}, "INVALID_SCORES"),
])
def test_missing_unknown_or_invalid_coverage_holds(scores, reason):
    result = gated_minimum(scores, required_checks=["check"])
    assert result["decision"] == "HOLD"
    assert reason in result["reason_codes"]
    assert "secret-marker" not in strict_json(result)


def test_complete_diagnostic_has_no_action_authority():
    result = gated_minimum({"one": 0.9, "two": 1}, required_checks=("one", "two"), threshold=0.9)
    assert result["decision"] == "PASS"
    assert result["minimum"] == 0.9
    assert result["coverage"] == {"required": 2, "observed": 2}
    assert result["scope"] == "STRUCTURAL_DIAGNOSTIC_ONLY"
    assert result["authority"] == "NONE"


def observation(**overrides):
    args = {
        "traceparent": TRACE,
        "receipt_sha256": "3" * 64,
        "model_sha256": "4" * 64,
        "source_revision": "5" * 40,
        "checks": dict.fromkeys(CHECKS, 1),
    }
    args.update(overrides)
    return receipt_observation(**args)


def test_observation_is_content_free_unsigned_and_deterministic():
    first = observation()
    assert first == observation()
    assert first["state"] == "OBSERVED"
    assert first["span_id"] == "2" * 16
    assert first["trace_id"] == "1" * 32
    assert first["authority"] == "NONE"
    assert first["signature_status"] == "UNSIGNED_DERIVED_OBSERVATION"
    assert first["collector_delivery"] == "UNVERIFIED"
    assert first["delivery"] == "RESPONSE_SIDECAR_ONLY"
    assert first["persistence"] == "RESPONSE_ONLY"
    assert not {"prompt", "output", "attributes", "energy", "exception"} & set(first)
    digest = first.pop("observation_sha256")
    encoded = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert hashlib.sha256(encoded.encode()).hexdigest() == digest
    first["receipt_sha256"] = "6" * 64
    changed = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert hashlib.sha256(changed.encode()).hexdigest() != digest


@pytest.mark.parametrize("trace", [
    None, "", True, [], "Bearer secret-marker",
    "00-" + "0" * 32 + "-" + "2" * 16 + "-01",
    "00-" + "1" * 32 + "-" + "0" * 16 + "-01",
    "00-" + "A" * 32 + "-" + "2" * 16 + "-01",
])
def test_invalid_trace_never_echoes_input(trace):
    result = observation(traceparent=trace)
    assert result["state"] == "UNAVAILABLE"
    assert result["reason_codes"] == ["TRACE_CONTEXT_UNAVAILABLE"]
    assert "secret-marker" not in strict_json(result)
    assert "observation_sha256" not in result


@pytest.mark.parametrize("key", ["receipt_sha256", "model_sha256", "source_revision"])
@pytest.mark.parametrize("value", [None, True, 1, [], "A" * 64, "Bearer secret-marker", "f" * 63])
def test_identity_rejects_malformed_or_free_text(key, value):
    result = observation(**{key: value})
    assert result["state"] == "UNAVAILABLE"
    assert result["reason_codes"] == ["INVALID_IDENTITY"]
    assert "secret-marker" not in strict_json(result)


def test_missing_witness_cannot_appear_as_observed():
    result = observation(checks={"receipt_digest_match": 1})
    assert result["state"] == "UNAVAILABLE"
    assert result["diagnostic"]["decision"] == "HOLD"
    assert "trace_id" not in result
    strict_json(result)


def test_arbitrary_attributes_are_not_an_accepted_interface():
    with pytest.raises(TypeError):
        observation(attributes={"message": "secret-marker"})


def test_score_key_subclasses_and_custom_mappings_do_not_satisfy_coverage():
    class ImpersonatedString(str):
        pass

    class ImpersonatedKey:
        def __hash__(self):
            return hash("check")

        def __eq__(self, other):
            return other == "check"

    class HostileMapping(dict):
        def __iter__(self):
            raise RuntimeError("private-error-marker")

    for scores in (
        {ImpersonatedString("check"): 1},
        {ImpersonatedKey(): 1},
        HostileMapping(check=1),
    ):
        result = gated_minimum(scores, required_checks=["check"])
        assert result["decision"] == "HOLD"
        assert result["reason_codes"] == ["INVALID_SCORES"]
        assert "private-error-marker" not in strict_json(result)
