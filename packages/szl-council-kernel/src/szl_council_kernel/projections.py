from __future__ import annotations

"""Privacy-preserving OpenTelemetry and read-only A11oy projections."""

from typing import Any, Mapping

from .canonical import digest_object
from .enums import CouncilState, ReleaseDecision


def council_otel_projection(
    settlement: Mapping[str, Any],
    *,
    gate_result: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = settlement["result"]
    attributes: dict[str, Any] = {
        "gen_ai.operation.name": "invoke_agent",
        "szl.council.case_id": result["case_id"],
        "szl.council.state": result["state"],
        "szl.council.verified": bool(result["verified"]),
        "szl.council.result_digest": settlement["result_digest"],
        "szl.council.transcript_digest": result["transcript_digest"],
        "szl.council.received_support": result["received_support"],
        "szl.council.required_support": result["required_support"],
        "szl.council.effective_size": result["diversity"]["joint_effective_size"],
        "szl.telemetry.private_reasoning_included": False,
        "szl.telemetry.raw_evidence_included": False,
        "szl.telemetry.credentials_included": False,
    }
    if gate_result is not None:
        attributes.update(
            {
                "szl.gate.decision": gate_result["decision"],
                "szl.gate.risk_score": gate_result["risk_score"],
                "szl.gate.false_green_upper": gate_result["empirical_false_green_upper"],
            }
        )
    if receipt is not None:
        attributes.update(
            {
                "szl.receipt.id": receipt["receipt_id"],
                "szl.receipt.status": receipt["status"],
                "szl.receipt.postconditions_passed": receipt["postconditions_passed"],
                "szl.receipt.rolled_back": receipt["rolled_back"],
            }
        )
    return {
        "schema": "szl.otel-span-projection/v1",
        "name": "invoke_agent szl_alloy_council",
        "kind": "INTERNAL",
        "status": {"code": "OK" if result["state"] == CouncilState.QUORUM_VERIFIED.value else "UNSET"},
        "attributes": attributes,
    }


def a11oy_read_only_projection(
    settlement: Mapping[str, Any],
    *,
    gate_result: Mapping[str, Any] | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = settlement["result"]
    state_map = {
        CouncilState.QUORUM_VERIFIED.value: "VERIFIED",
        CouncilState.REQUIRE_HUMAN.value: "HUMAN_GATE",
        CouncilState.BLOCKED.value: "BLOCKED",
        CouncilState.CONFLICT.value: "CONFLICT",
        CouncilState.INSUFFICIENT.value: "INSUFFICIENT",
        CouncilState.INVALID.value: "INVALID",
    }
    projection = {
        "schema": "a11oy.council-projection/v1",
        "mode": "read-only",
        "case_id": result["case_id"],
        "state": state_map[result["state"]],
        "verified": result["state"] == CouncilState.QUORUM_VERIFIED.value and result["verified"] is True,
        "result_digest": settlement["result_digest"],
        "reason_codes": list(result["reason_codes"]),
        "support": f"{result['received_support']}/{result['required_support']}",
        "effective_council_size": result["diversity"]["joint_effective_size"],
        "minority_counterevidence_count": len(result["minority_evidence_digests"]),
        "write_authority": False,
    }
    if gate_result is not None:
        projection["release_decision"] = gate_result["decision"]
    if receipt is not None:
        projection["receipt"] = {
            "receipt_id": receipt["receipt_id"],
            "status": receipt["status"],
            "postconditions_passed": receipt["postconditions_passed"],
            "rolled_back": receipt["rolled_back"],
            "signer_state": receipt["signer_state"],
        }
    projection["projection_digest"] = digest_object(projection)
    return projection
