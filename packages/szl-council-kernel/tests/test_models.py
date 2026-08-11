from dataclasses import replace

import pytest

from szl_council_kernel.canonical import digest_object
from szl_council_kernel.enums import ActionKind, AutonomyLevel, CouncilRole, CouncilState, CouncilVote, RiskClass
from szl_council_kernel.errors import ValidationError
from szl_council_kernel.models import (
    ActionReceipt,
    ActionRequest,
    AutonomyEnvelope,
    BudgetLimits,
    BudgetUsage,
    ConditionSpec,
    CouncilAssessment,
    CouncilIdentity,
    CouncilResult,
    OutcomeContract,
    RetryPolicy,
)

T="2026-08-03T12:00:00Z"; E="2026-08-04T12:00:00Z"
D=digest_object({"d":1})


def test_budget_subset():
    assert BudgetLimits(max_mutations=1).is_subset_of(BudgetLimits(max_mutations=2))
    assert not BudgetLimits(max_mutations=2).is_subset_of(BudgetLimits(max_mutations=1))


def test_budget_usage_within():
    assert BudgetUsage(mutations=1).within(BudgetLimits(max_mutations=1))
    assert not BudgetUsage(mutations=2).within(BudgetLimits(max_mutations=1))


def test_a0_mutation_budget_rejected(envelope):
    with pytest.raises(ValidationError):
        replace(envelope, autonomy_level=AutonomyLevel.A0_OBSERVE)


def test_high_risk_requires_transparency(envelope):
    with pytest.raises(ValidationError):
        replace(envelope, risk_class=RiskClass.HIGH, transparency_required=False)


def test_required_four_roles(envelope):
    with pytest.raises(ValidationError):
        replace(envelope, required_roles=(CouncilRole.AUTHORITY,))


def test_retry_ambiguous_external_forbidden():
    with pytest.raises(ValidationError):
        RetryPolicy(ambiguous_external_retry=True)


def test_invalid_condition_rejected():
    with pytest.raises(ValidationError):
        ConditionSpec("SHELL_EXIT_ZERO", "x", True)


def test_opposition_requires_counterevidence():
    with pytest.raises(ValidationError):
        CouncilAssessment(case_id="case-x",role=CouncilRole.SENTINEL,member_id="member-x",vote=CouncilVote.OPPOSE,confidence=.5,reason_codes=("NO",),evidence_digests=(D,),counterevidence_digests=(),policy_digest=D,subject_digest=D,issued_at=T,expires_at=E)


def test_support_assessment_digest_stable():
    a=CouncilAssessment(case_id="case-x",role=CouncilRole.AUTHORITY,member_id="member-x",vote=CouncilVote.SUPPORT,confidence=.9,reason_codes=("OK",),evidence_digests=(D,),counterevidence_digests=(),policy_digest=D,subject_digest=D,issued_at=T,expires_at=E)
    assert a.digest == digest_object(a.to_dict())


def test_identity_key_id_binding_is_structural(test_signer):
    identity=CouncilIdentity(member_id="member-x",role=CouncilRole.AUTHORITY,key_id=test_signer.key_id,public_key=test_signer.public_key,trust_domain="td",implementation_digest=D,model_family="m",evidence_domain="e",operator_id="o",retrieval_path="r",provider_account="p",not_before=T,not_after=E)
    assert identity.active_at(T)


def test_result_verified_invariant():
    with pytest.raises(ValidationError):
        CouncilResult(case_id="case-x",state=CouncilState.BLOCKED,verified=True,support_roles=(),oppose_roles=(),abstain_roles=(),veto_roles=(),missing_roles=tuple(CouncilRole),reason_codes=("BLOCK",),minority_evidence_digests=(),received_support=0,required_support=3,diversity={},policy_digest=D,subject_digest=D,transcript_digest=D,issued_at=T)


def test_action_write_requires_content():
    with pytest.raises(ValidationError):
        ActionRequest(action_id="a",case_id="c",grant_id="g",kind=ActionKind.FILE_WRITE,tool="sandbox_fs",target="x",content=None,expected_before_digest=None,idempotency_key="i",postconditions=())


def test_action_delete_forbids_content():
    with pytest.raises(ValidationError):
        ActionRequest(action_id="a",case_id="c",grant_id="g",kind=ActionKind.FILE_DELETE,tool="sandbox_fs",target="x",content="bad",expected_before_digest=None,idempotency_key="i",postconditions=())


def test_receipt_signed_state_validation():
    with pytest.raises(ValidationError):
        ActionReceipt(receipt_id="r",case_id="c",action_id="a",action_digest=D,status="VERIFIED",target="x",before_digest=None,after_digest=D,postconditions_passed=True,rolled_back=False,rollback_digest=None,council_result_digest=D,gate_result_digest=D,event_hash=D,previous_receipt_digest=None,issued_at=T,signer_state="MAGIC")


def test_outcome_window_must_be_positive():
    with pytest.raises(ValidationError):
        OutcomeContract(outcome_id="o",case_id="c",action_receipt_digest=D,metric="m",baseline=0,expected_direction="INCREASE",effect_window_start=E,effect_window_end=T,observation_schedule=(E,),attribution_method="x",stop_loss=None,confounders=())


def test_envelope_roundtrip(envelope):
    restored=AutonomyEnvelope.from_dict(envelope.to_dict())
    assert restored.digest == envelope.digest
