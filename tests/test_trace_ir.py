# SPDX-License-Identifier: Apache-2.0
from vsp_otel.trace_ir import canonical_sha256, gated_minimum, trace_event


def test_trace_event_is_deterministic_and_redacts_sensitive_fields():
    digest = "a" * 64
    first = trace_event(
        trace_id="tr-1",
        span_id="sp-1",
        operation="execute_tool",
        status="SUCCEEDED",
        input_hash=digest,
        result_hash=digest,
        model_hash=digest,
        adapter_hash=digest,
        dataset_version="dataset@rev1",
        invariant_set=["F4", "F1", "F4"],
        energy={"joules": 12.5, "method": "nvml"},
        attributes={"Authorization": "Bearer secret", "safe": "ok"},
    )
    second = trace_event(
        trace_id="tr-1",
        span_id="sp-1",
        operation="execute_tool",
        status="SUCCEEDED",
        input_hash=digest,
        result_hash=digest,
        model_hash=digest,
        adapter_hash=digest,
        dataset_version="dataset@rev1",
        invariant_set=["F1", "F4"],
        energy={"joules": 12.5, "method": "nvml"},
        attributes={"Authorization": "Bearer secret", "safe": "ok"},
    )
    assert first == second
    assert first["schema"] == "szl.trace-ir/v1"
    assert first["invariant_set"] == ["F1", "F4"]
    assert first["authorization"]["effect"] == "NONE"
    assert "secret" not in str(first)
    assert first["event_sha256"] == canonical_sha256(
        {key: value for key, value in first.items() if key != "event_sha256"}
    )


def test_trace_event_rejects_invalid_hash_and_self_parent():
    try:
        trace_event(trace_id="tr", span_id="sp", operation="chat", status="SUCCEEDED", input_hash="bad")
    except ValueError as exc:
        assert "input_hash" in str(exc)
    else:
        raise AssertionError("invalid hash must be rejected")
    try:
        trace_event(trace_id="tr", span_id="sp", operation="chat", status="SUCCEEDED", parent_span_id="sp")
    except ValueError as exc:
        assert "parent" in str(exc)
    else:
        raise AssertionError("self-parent must be rejected")


def test_gated_minimum_cannot_hide_critical_failure_behind_average():
    passed = gated_minimum({"invariants": 1.0, "replay": 1.0}, threshold=1.0)
    held = gated_minimum(
        {"invariants": 1.0, "replay": 1.0, "energy": 0.2},
        threshold=0.0,
        critical_failures=["receipt_signature"],
    )
    empty = gated_minimum({})
    assert passed["verdict"] == "PASS"
    assert held["verdict"] == "HOLD"
    assert held["critical_failures"] == ["receipt_signature"]
    assert empty["verdict"] == "HOLD"
