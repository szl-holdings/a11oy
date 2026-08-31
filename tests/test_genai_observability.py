# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from vsp_otel.genai import (
    CONTENT_CAPTURE_ENABLED,
    model_attributes,
    redact,
    sampling_decision,
    security_event,
)


def test_content_capture_is_off_and_model_attributes_are_minimal():
    attrs = model_attributes(
        operation="chat",
        provider="openai",
        model="model-revision",
        input_tokens=10,
        output_tokens=4,
        max_tokens=32,
        correlation={"run.id": "run-1", "not.allowed": "discarded"},
    )
    assert CONTENT_CAPTURE_ENABLED is False
    assert attrs["gen_ai.usage.input_tokens"] == 10
    assert attrs["run.id"] == "run-1"
    assert "not.allowed" not in attrs
    assert not any("prompt" in key or "message" in key for key in attrs)


def test_recursive_redaction_catches_nested_and_inline_secrets():
    source = {
        "tool_arguments": {"Authorization": "Bearer abc", "safe": "value"},
        "metadata": [{"api_key": "sk-live"}, {"note": "password=hunter2 next"}],
    }
    result = redact(source)
    assert str(result["tool_arguments"]).startswith("[REDACTED sha256:")
    assert str(result["metadata"][0]["api_key"]).startswith("[REDACTED sha256:")
    assert "hunter2" not in result["metadata"][1]["note"]


def test_all_mandatory_governance_events_are_sampled():
    for event in (
        "policy.rejected",
        "authorization_receipt.invalid",
        "deployment.production",
        "provenance.verification_failed",
        "admission.rejected",
        "security.alert",
        "benchmark.run",
        "incident.trace",
    ):
        assert sampling_decision(event) == "RECORD_AND_SAMPLE"
    assert sampling_decision("model.success") == "TAIL_POLICY_ELIGIBLE"
    assert sampling_decision("model.success", initial_production_validation=True) == "RECORD_AND_SAMPLE"


def test_telemetry_event_explicitly_authorizes_nothing():
    event = security_event("policy.rejected", {"token": "sensitive", "reason": "default deny"})
    assert event["authorization.effect"] == "NONE"
    assert event["sampling.decision"] == "RECORD_AND_SAMPLE"
    assert "sensitive" not in str(event)
