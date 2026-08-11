from __future__ import annotations

"""Deterministic end-to-end local Council Kernel canary."""

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .canonical import digest_object, file_digest
from .enums import ActionKind, AutonomyLevel, BlastRadius, CouncilRole, CouncilVote, RiskClass
from .fourfold import CouncilSession, sign_assessment, sign_commitment, verify_settlement
from .models import (
    ActionRequest,
    AutonomyEnvelope,
    BudgetLimits,
    CapabilityGrant,
    ConditionSpec,
    CouncilAssessment,
    CouncilCase,
    CouncilIdentity,
    CouncilPolicy,
    EpochBinding,
    GateInput,
    RetryPolicy,
    RollbackPlan,
)
from .proof import Ed25519Signer, verify_signed_object
from .workflow import ACTION_RECEIPT_CONTENT_TYPE, CouncilKernel

FIXED_TIME = "2026-08-03T12:00:00Z"
FIXED_EXPIRY = "2026-08-04T12:00:00Z"


def _seed(label: str) -> bytes:
    return hashlib.sha256(("szl-council-kernel-canary:" + label).encode("utf-8")).digest()


def _signer(label: str) -> Ed25519Signer:
    return Ed25519Signer.from_seed(_seed(label), signer_state="SIGNED_TEST")


def build_deterministic_council(
    *,
    envelope: AutonomyEnvelope,
    policy: CouncilPolicy,
    risk_class: RiskClass = RiskClass.LOW,
    value_claimed: bool = True,
    votes: dict[CouncilRole, CouncilVote] | None = None,
    correlated: bool = False,
    session_time: str = FIXED_TIME,
    expiry: str = FIXED_EXPIRY,
) -> tuple[CouncilCase, dict[str, Any]]:
    case = CouncilCase(
        case_id=envelope.case_id,
        subject=envelope.subject,
        risk_class=risk_class,
        value_claimed=value_claimed,
        evidence_manifest_digest=digest_object(
            {
                "schema": "szl.evidence-manifest/v1",
                "evidence": [
                    {"id": "policy", "tier": "VERIFIED", "digest": policy.digest},
                    {"id": "target", "tier": "MEASURED", "target": envelope.exact_targets[0]},
                ],
            }
        ),
        policy_digest=policy.digest,
        envelope_digest=envelope.digest,
        epochs_digest=envelope.epochs.digest,
        created_at=session_time,
    )
    role_signers = {role: _signer(role.value.lower()) for role in CouncilRole}
    identities: list[CouncilIdentity] = []
    for index, role in enumerate(CouncilRole):
        signer = role_signers[role]
        identities.append(
            CouncilIdentity(
                member_id=f"canary-{role.value.lower()}",
                role=role,
                key_id=signer.key_id,
                public_key=signer.public_key,
                trust_domain="spiffe://canary.shared" if correlated else f"spiffe://canary-{index}.szl.test",
                implementation_digest=digest_object({"implementation": "shared" if correlated else f"lane-{index}", "version": 1}),
                model_family="shared-model" if correlated else f"model-family-{index}",
                evidence_domain="shared-evidence" if correlated else f"evidence-domain-{index}",
                operator_id="shared-operator" if correlated else f"operator-{index}",
                retrieval_path="shared-index" if correlated else f"retrieval-{index}",
                provider_account="shared-provider" if correlated else f"provider-{index}",
                not_before=session_time,
                not_after=expiry,
            )
        )
    session = CouncilSession(case, policy, identities, session_time=session_time)
    assessments: dict[CouncilRole, CouncilAssessment] = {}
    selected_votes = votes or {role: CouncilVote.SUPPORT for role in CouncilRole}
    for role in CouncilRole:
        vote = selected_votes[role]
        counter = ()
        if vote in {CouncilVote.OPPOSE, CouncilVote.VETO}:
            counter = (digest_object({"counterevidence": role.value, "case": case.case_id}),)
        assessment = CouncilAssessment(
            case_id=case.case_id,
            role=role,
            member_id=f"canary-{role.value.lower()}",
            vote=vote,
            confidence=0.93,
            reason_codes=(f"{role.value}_{vote.value}",),
            evidence_digests=(digest_object({"evidence": role.value, "case": case.case_id}),),
            counterevidence_digests=counter,
            policy_digest=policy.digest,
            subject_digest=case.digest,
            issued_at=session_time,
            expires_at=expiry,
        )
        assessments[role] = assessment
        session.submit_commitment(
            role,
            sign_commitment(assessment, f"canary-salt-{role.value.lower()}-000000000000", role_signers[role]),
        )
    session.seal_commitments()
    for role in CouncilRole:
        assessment = assessments[role]
        session.reveal(
            role,
            assessment,
            f"canary-salt-{role.value.lower()}-000000000000",
            sign_assessment(assessment, role_signers[role]),
        )
    settlement = session.settle(_signer("aggregator"), issued_at=session_time)
    return case, settlement


def run_canary(workdir: str | Path) -> dict[str, Any]:
    root = Path(workdir)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    sandbox = root / "sandbox"
    db = root / "council.sqlite3"
    target = "workspace/canary.txt"
    marker = "proof-carrying-autonomy: verified local canary\n"
    policy = CouncilPolicy()
    epochs = EpochBinding(
        model="model:deterministic-test-specialists@1",
        tool="tool:sandbox_fs@1",
        policy=policy.digest,
        evidence="evidence:canary-manifest@1",
        state="state:szl-state-bus@1",
        retrieval="retrieval:isolated-test-index@1",
        prompt="prompt:none",
        tokenizer="tokenizer:none",
    )
    envelope = AutonomyEnvelope(
        case_id="case-canary-0001",
        principal="spiffe://szl.test/workload/canary-owner",
        subject="Write one bounded canary file, verify exact content, and issue a signed receipt.",
        exact_targets=(target,),
        capabilities=("file:write", "file:rollback"),
        tools=("sandbox_fs",),
        risk_class=RiskClass.LOW,
        blast_radius=BlastRadius.SANDBOX,
        autonomy_level=AutonomyLevel.A2_REVERSIBLE,
        budgets=BudgetLimits(
            max_cost_usd=0,
            max_duration_seconds=30,
            max_tool_calls=1,
            max_mutations=1,
            max_branches=1,
            max_recursion=0,
        ),
        preconditions=(ConditionSpec("FILE_ABSENT", target, True),),
        postconditions=(ConditionSpec("TEXT_CONTAINS", target, "proof-carrying-autonomy"),),
        idempotency_key="canary-write-0001",
        retry_policy=RetryPolicy(max_attempts=1),
        rollback_plan=RollbackPlan(required=True, strategy="RESTORE_PREIMAGE", authority_capability="file:rollback"),
        epochs=epochs,
        required_roles=tuple(CouncilRole),
        required_council_state="QUORUM_VERIFIED",
        receipt_required=True,
        transparency_required=False,
        issued_at=FIXED_TIME,
        expires_at=FIXED_EXPIRY,
    )
    grant = CapabilityGrant(
        grant_id="grant-canary-0001",
        principal=envelope.principal,
        capabilities=envelope.capabilities,
        target_patterns=("workspace/**",),
        tools=envelope.tools,
        budgets=envelope.budgets,
        issued_at=FIXED_TIME,
        expires_at=FIXED_EXPIRY,
    )
    case, settlement = build_deterministic_council(envelope=envelope, policy=policy)
    gate_input = GateInput(
        council_state="QUORUM_VERIFIED",
        risk_class=RiskClass.LOW,
        effective_diversity=settlement["result"]["diversity"]["joint_effective_size"],
        evidence_completeness=0.98,
        proof_completeness=0.98,
        novelty_score=0.05,
        ambiguity_score=0.03,
        irreversibility_score=0.02,
        drift_score=0.0,
        expected_blast_radius=0.02,
        historical_false_green_rate=0.0,
        calibration_sample_size=200,
    )
    action = ActionRequest(
        action_id="action-canary-write-0001",
        case_id=case.case_id,
        grant_id=grant.grant_id,
        kind=ActionKind.FILE_WRITE,
        tool="sandbox_fs",
        target=target,
        content=marker,
        expected_before_digest=None,
        idempotency_key=envelope.idempotency_key,
        postconditions=envelope.postconditions,
        metadata={"task_class": "file_mutation", "domain": "local-canary"},
    )
    kernel = CouncilKernel(
        db_path=str(db),
        sandbox_root=str(sandbox),
        receipt_signer=_signer("receipt"),
    )
    run = kernel.run_case(
        case=case,
        envelope=envelope,
        grant=grant,
        settlement=settlement,
        gate_input=gate_input,
        action=action,
        now=FIXED_TIME,
    )
    target_path = sandbox / target
    signed_receipt_payload = verify_signed_object(
        run["signed_receipt"],
        kernel.receipt_signer.verifier(),
        expected_payload_type=ACTION_RECEIPT_CONTENT_TYPE,
    )
    checks = {
        "council_settlement": verify_settlement(settlement)["status"] == "PASS",
        "council_state": settlement["result"]["state"] == "QUORUM_VERIFIED",
        "gate_act": run["gate"]["decision"] == "ACT",
        "mutation_verified": run["status"] == "VERIFIED" and run["execution"]["postconditions_passed"] is True,
        "receipt_signature": signed_receipt_payload == run["receipt"],
        "state_bus_chain": run["ledger"]["status"] == "PASS",
        "transparency_inclusion": run["transparency"]["verified"] is True,
        "a11oy_read_only": run["a11oy"]["mode"] == "read-only" and run["a11oy"]["write_authority"] is False,
        "target_content": target_path.read_text(encoding="utf-8") == marker,
        "production_independence_false": run["production_independence_verified"] is False,
    }
    body = {
        "schema": "szl.council-kernel-canary/v1",
        "release": "0.5.0rc1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "case_id": case.case_id,
        "council_result_digest": settlement["result_digest"],
        "run_digest": run["run_digest"],
        "receipt_digest": run["receipt_digest"],
        "ledger_head": run["ledger"]["head_hash"],
        "transparency_root": run["transparency"]["root_hash"],
        "target": target,
        "target_digest": file_digest(target_path),
        "assurance_scope": "LOCAL_KERNEL_AND_SANDBOX_EXECUTION_ONLY",
        "production_independence_verified": False,
        "test_key_boundary": "DETERMINISTIC_TEST_KEYS_NOT_FOR_PRODUCTION",
        "run": run,
    }
    return {**body, "report_digest": digest_object(body)}
