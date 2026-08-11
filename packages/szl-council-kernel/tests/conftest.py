from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from szl_council_kernel.canary import FIXED_EXPIRY, FIXED_TIME, build_deterministic_council
from szl_council_kernel.enums import AutonomyLevel, BlastRadius, CouncilRole, RiskClass
from szl_council_kernel.models import (
    AutonomyEnvelope,
    BudgetLimits,
    CapabilityGrant,
    ConditionSpec,
    CouncilPolicy,
    EpochBinding,
    RetryPolicy,
    RollbackPlan,
)
from szl_council_kernel.proof import Ed25519Signer


@pytest.fixture
def policy() -> CouncilPolicy:
    return CouncilPolicy()


@pytest.fixture
def envelope(policy: CouncilPolicy) -> AutonomyEnvelope:
    target = "workspace/test.txt"
    epochs = EpochBinding(
        model="model:test@1",
        tool="tool:sandbox_fs@1",
        policy=policy.digest,
        evidence="evidence:test@1",
        state="state:test@1",
        retrieval="retrieval:test@1",
    )
    return AutonomyEnvelope(
        case_id="case-test-0001",
        principal="spiffe://test.szl/owner",
        subject="test one bounded write",
        exact_targets=(target,),
        capabilities=("file:write", "file:rollback"),
        tools=("sandbox_fs",),
        risk_class=RiskClass.LOW,
        blast_radius=BlastRadius.SANDBOX,
        autonomy_level=AutonomyLevel.A2_REVERSIBLE,
        budgets=BudgetLimits(max_tool_calls=1, max_mutations=1, max_branches=2),
        preconditions=(ConditionSpec("FILE_ABSENT", target, True),),
        postconditions=(ConditionSpec("TEXT_CONTAINS", target, "ok"),),
        idempotency_key="idem-test-0001",
        retry_policy=RetryPolicy(),
        rollback_plan=RollbackPlan(),
        epochs=epochs,
        required_roles=tuple(CouncilRole),
        required_council_state="QUORUM_VERIFIED",
        receipt_required=True,
        transparency_required=False,
        issued_at=FIXED_TIME,
        expires_at=FIXED_EXPIRY,
    )


@pytest.fixture
def grant(envelope: AutonomyEnvelope) -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="grant-test-0001",
        principal=envelope.principal,
        capabilities=envelope.capabilities,
        target_patterns=("workspace/**",),
        tools=envelope.tools,
        budgets=envelope.budgets,
        issued_at=FIXED_TIME,
        expires_at=FIXED_EXPIRY,
    )


@pytest.fixture
def case_settlement(envelope: AutonomyEnvelope, policy: CouncilPolicy):
    return build_deterministic_council(envelope=envelope, policy=policy)


@pytest.fixture
def test_signer() -> Ed25519Signer:
    return Ed25519Signer.from_seed(hashlib.sha256(b"pytest-signer").digest(), signer_state="SIGNED_TEST")
