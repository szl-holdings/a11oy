from __future__ import annotations

import base64
import copy

import pytest

from szl_waqay_security_loop import (
    Advisory,
    Artifact,
    Component,
    ContractError,
    Deployment,
    EvidenceState,
    FleetCatalog,
    GateInputs,
    LoopState,
    PlanKind,
    TransitionDenied,
    canonical_json,
    catalog_digest,
    detect_findings,
    evaluate_gates,
    make_plan,
    normalize_catalog,
    replay_receipts,
    security_loop_manifest,
    start_record,
    transition,
    verify_receipt,
)


H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64
H6 = "6" * 64


def fixture_catalog(*, reverse: bool = False) -> FleetCatalog:
    current = Artifact(
        artifact_digest=H1,
        sbom_digest=H2,
        provenance_digest=H3,
        signature_state=EvidenceState.VERIFIED,
        components=(
            Component("safe", "2.0.0", "pkg:pypi/safe@2.0.0"),
            Component("demo-lib", "1.0.0", "pkg:pypi/demo-lib@1.0.0"),
        ),
    )
    rollback = Artifact(
        artifact_digest=H0,
        sbom_digest=H4,
        provenance_digest=H5,
        signature_state=EvidenceState.VERIFIED,
        components=(Component("demo-lib", "0.9.0", "pkg:pypi/demo-lib@0.9.0"),),
    )
    deployments = (
        Deployment("prod-b", H1, "prod", "spiffe://szl/service/b", H0),
        Deployment("prod-a", H1, "prod", "spiffe://szl/service/a", H0),
    )
    artifacts = (current, rollback)
    if reverse:
        artifacts = tuple(reversed(artifacts))
        deployments = tuple(reversed(deployments))
    return FleetCatalog("2026-07-12T08:00:00Z", artifacts, deployments)


def fixture_advisory() -> Advisory:
    return Advisory(
        advisory_id="GHSA-DEMO-0001",
        component_name="demo-lib",
        affected_versions=("1.0.0",),
        severity="high",
        evidence_digest=H6,
        source_uri="https://example.invalid/advisories/GHSA-DEMO-0001",
    )


def gates(**overrides: object) -> GateInputs:
    values: dict[str, object] = {
        "sbom_verified": True,
        "vulnerability_validated": True,
        "provenance_verified": True,
        "artifact_signature_verified": True,
        "principal_verified": True,
        "human_approval_verified": True,
        "rollback_target_previously_admitted": True,
        "graph_trust": "VERIFIED",
        "unresolved_contradiction": False,
        "principal_id": "user:reviewer@example.invalid",
        "approval_id": "approval:0001",
        "validation_evidence_digest": H5,
    }
    values.update(overrides)
    return GateInputs(**values)  # type: ignore[arg-type]


def fixture_finding():
    findings = detect_findings(fixture_catalog(), [fixture_advisory()])
    assert len(findings) == 1
    return findings[0]


def test_catalog_normalization_and_digest_are_order_independent() -> None:
    left = normalize_catalog(fixture_catalog())
    right = normalize_catalog(fixture_catalog(reverse=True))
    assert left == right
    assert catalog_digest(left) == catalog_digest(right)
    assert [d.deployment_id for d in left.deployments] == ["prod-a", "prod-b"]


def test_public_manifest_is_explicitly_read_only_and_bounded() -> None:
    manifest = security_loop_manifest()
    assert manifest["mode"] == "PROPOSAL_ONLY"
    assert manifest["effectors"] == 0
    assert manifest["external_mutations"] == "DISABLED"
    assert manifest["bounds"]["max_findings"] == 128
    assert manifest["receipt"]["signature_default"] == "UNSIGNED_NO_SIGNER_AVAILABLE"
    assert "HUMAN_APPROVAL_VERIFIED" in manifest["gate_ids"]


def test_catalog_rejects_unadmitted_rollback_target() -> None:
    catalog = fixture_catalog()
    bad = FleetCatalog(
        catalog.observed_at,
        catalog.artifacts,
        (Deployment("prod-a", H1, "prod", "spiffe://szl/service/a", "f" * 64),),
    )
    with pytest.raises(ContractError, match="rollback digest is not admitted"):
        normalize_catalog(bad)


def test_detect_is_exact_deterministic_and_fleet_aware() -> None:
    first = detect_findings(fixture_catalog(), [fixture_advisory()])
    second = detect_findings(fixture_catalog(reverse=True), [fixture_advisory()])
    assert first == second
    assert first[0].affected_deployments == ("prod-a", "prod-b")
    assert first[0].finding_id.startswith("waqay:")
    wrong = Advisory("ADV-2", "demo-lib", ("9.9.9",), "HIGH", H6, "https://example.invalid/2")
    assert detect_findings(fixture_catalog(), [wrong]) == ()


def test_detection_bound_fails_closed() -> None:
    second = Advisory(
        advisory_id="GHSA-DEMO-0002",
        component_name="demo-lib",
        affected_versions=("1.0.0",),
        severity="critical",
        evidence_digest=H5,
        source_uri="https://example.invalid/advisories/GHSA-DEMO-0002",
    )
    with pytest.raises(ContractError, match="finding bound exceeded"):
        detect_findings(fixture_catalog(), [fixture_advisory(), second], max_findings=1)


def test_gate_results_expose_each_failure_without_collapsing_scores() -> None:
    results = evaluate_gates(
        gates(
            provenance_verified=False,
            human_approval_verified=False,
            graph_trust="UNTRUSTWORTHY",
            unresolved_contradiction=True,
        )
    )
    failures = {result.gate_id for result in results if not result.passed}
    assert failures == {
        "PROVENANCE_VERIFIED",
        "HUMAN_APPROVAL_VERIFIED",
        "GRAPH_TRUST",
        "NO_UNRESOLVED_CONTRADICTION",
    }


def test_validation_requires_technical_witness_digest() -> None:
    record = start_record(fixture_finding())
    with pytest.raises(TransitionDenied, match="validation evidence"):
        transition(
            record,
            LoopState.VALIDATED,
            observed_at="2026-07-12T08:01:00Z",
            rationale="bounded reproduction",
            gates=gates(validation_evidence_digest="not-a-digest"),
        )


def test_state_machine_rejects_skips() -> None:
    record = start_record(fixture_finding())
    with pytest.raises(TransitionDenied, match="is not allowed"):
        transition(
            record,
            LoopState.REMEDIATION_PROPOSED,
            observed_at="2026-07-12T08:01:00Z",
            rationale="attempted skip",
        )


def test_plan_is_bounded_sorted_and_exact_to_blast_radius() -> None:
    finding = fixture_finding()
    plan = make_plan(
        kind=PlanKind.RECALL,
        finding=finding,
        target_artifact_digest=H1,
        rollback_digest=H0,
        deployment_ids=("prod-b", "prod-a"),
        batch_size=1,
        max_parallel=1,
    )
    assert plan.deployment_ids == ("prod-a", "prod-b")
    assert plan.batches == (("prod-a",), ("prod-b",))
    assert plan.mode == "PROPOSAL_ONLY"
    assert plan.effectors == 0
    with pytest.raises(ContractError, match="blast radius"):
        make_plan(
            kind=PlanKind.RECALL,
            finding=finding,
            target_artifact_digest=H1,
            rollback_digest=H0,
            deployment_ids=("prod-a",),
        )


def test_recall_is_denied_when_any_gate_fails() -> None:
    finding = fixture_finding()
    record = start_record(finding)
    record, _ = transition(
        record, LoopState.VALIDATED, observed_at="t1", rationale="witness", gates=gates()
    )
    record, _ = transition(record, LoopState.REMEDIATION_PROPOSED, observed_at="t2", rationale="minimal patch")
    record, _ = transition(record, LoopState.APPROVAL_REQUIRED, observed_at="t3", rationale="human review required")
    plan = make_plan(
        kind=PlanKind.RECALL,
        finding=finding,
        target_artifact_digest=H1,
        rollback_digest=H0,
        deployment_ids=finding.affected_deployments,
    )
    with pytest.raises(TransitionDenied, match="all safety"):
        transition(
            record,
            LoopState.RECALL_PROPOSED,
            observed_at="t4",
            rationale="recall proposal",
            gates=gates(principal_verified=False),
            plan=plan,
        )


def test_full_proposal_chain_replays_and_performs_no_effect() -> None:
    finding = fixture_finding()
    record = start_record(finding)
    receipts = []
    record, receipt = transition(record, LoopState.VALIDATED, observed_at="t1", rationale="witness", gates=gates())
    receipts.append(receipt)
    record, receipt = transition(record, LoopState.REMEDIATION_PROPOSED, observed_at="t2", rationale="minimal diff")
    receipts.append(receipt)
    record, receipt = transition(record, LoopState.APPROVAL_REQUIRED, observed_at="t3", rationale="human gate")
    receipts.append(receipt)
    recall = make_plan(
        kind=PlanKind.RECALL,
        finding=finding,
        target_artifact_digest=H1,
        rollback_digest=H0,
        deployment_ids=finding.affected_deployments,
    )
    record, receipt = transition(
        record,
        LoopState.RECALL_PROPOSED,
        observed_at="t4",
        rationale="bounded recall proposal",
        gates=gates(),
        plan=recall,
    )
    receipts.append(receipt)
    rolloff = make_plan(
        kind=PlanKind.ROLLOFF,
        finding=finding,
        target_artifact_digest=H0,
        rollback_digest=H0,
        deployment_ids=finding.affected_deployments,
    )
    record, receipt = transition(
        record,
        LoopState.ROLLOFF_PROPOSED,
        observed_at="t5",
        rationale="bounded rolloff proposal",
        gates=gates(),
        plan=rolloff,
    )
    receipts.append(receipt)

    replay = replay_receipts(finding, receipts)
    assert replay["valid"] is True
    assert replay["final_state"] == "ROLLOFF_PROPOSED"
    assert replay["effectors"] == 0
    assert all(r["payload"]["mode"] == "PROPOSAL_ONLY" for r in receipts)
    assert all(r["payload"]["effectors"] == 0 for r in receipts)


def test_unsigned_dsse_fallback_is_explicit_and_payload_bound() -> None:
    record = start_record(fixture_finding())
    _, receipt = transition(
        record, LoopState.VALIDATED, observed_at="t1", rationale="witness", gates=gates()
    )
    envelope = receipt["dsse_envelope"]
    assert envelope["signed"] is False
    assert envelope["signatures"] == []
    assert envelope["verification_state"] == "UNSIGNED_NO_SIGNER_AVAILABLE"
    assert verify_receipt(receipt)["valid"] is True
    assert verify_receipt(receipt)["signature_verified"] is False


def test_dsse_hook_cannot_substitute_different_payload() -> None:
    record = start_record(fixture_finding())

    def bad_signer(_payload, payload_type):
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(canonical_json({"different": True})).decode("ascii"),
            "signatures": [{"keyid": "test", "sig": "AA=="}],
        }

    with pytest.raises(ContractError, match="different payload bytes"):
        transition(
            record,
            LoopState.VALIDATED,
            observed_at="t1",
            rationale="witness",
            gates=gates(),
            signer=bad_signer,
        )


def test_tamper_breaks_content_verification_and_chain_replay() -> None:
    finding = fixture_finding()
    record = start_record(finding)
    _, receipt = transition(record, LoopState.VALIDATED, observed_at="t1", rationale="witness", gates=gates())
    tampered = copy.deepcopy(receipt)
    tampered["payload"]["rationale"] = "changed"
    assert verify_receipt(tampered)["valid"] is False
    assert replay_receipts(finding, [tampered])["valid"] is False
