from dataclasses import replace
from pathlib import Path

import pytest

from szl_council_kernel.canary import FIXED_TIME,run_canary
from szl_council_kernel.canonical import digest_bytes
from szl_council_kernel.enums import ActionKind,CouncilState,RiskClass
from szl_council_kernel.errors import IntegrityError,ValidationError
from szl_council_kernel.executor import SandboxExecutor
from szl_council_kernel.models import ActionRequest,ConditionSpec,GateInput
from szl_council_kernel.proof import Ed25519Signer
from szl_council_kernel.workflow import CouncilKernel


def make_action(envelope,grant,kind=ActionKind.FILE_WRITE,content='ok',conditions=None,target=None):
    target=target or envelope.exact_targets[0]
    return ActionRequest(action_id='action-1',case_id=envelope.case_id,grant_id=grant.grant_id,kind=kind,tool='sandbox_fs',target=target,content=content,expected_before_digest=None,idempotency_key=envelope.idempotency_key,postconditions=conditions if conditions is not None else envelope.postconditions)


def test_atomic_write(tmp_path,envelope,grant):
    result=SandboxExecutor(tmp_path).execute(make_action(envelope,grant));assert result.postconditions_passed;assert (tmp_path/envelope.exact_targets[0]).read_text()=='ok'


def test_append(tmp_path,envelope,grant):
    p=tmp_path/envelope.exact_targets[0];p.parent.mkdir(parents=True);p.write_text('first ')
    c=(ConditionSpec('TEXT_CONTAINS',envelope.exact_targets[0],'first ok'),)
    result=SandboxExecutor(tmp_path).execute(make_action(envelope,grant,ActionKind.FILE_APPEND,'ok',c));assert result.postconditions_passed


def test_delete(tmp_path,envelope,grant):
    p=tmp_path/envelope.exact_targets[0];p.parent.mkdir(parents=True);p.write_text('x')
    c=(ConditionSpec('FILE_ABSENT',envelope.exact_targets[0],True),)
    result=SandboxExecutor(tmp_path).execute(make_action(envelope,grant,ActionKind.FILE_DELETE,None,c));assert result.postconditions_passed and not p.exists()


def test_failed_postcondition_rolls_back(tmp_path,envelope,grant):
    c=(ConditionSpec('TEXT_CONTAINS',envelope.exact_targets[0],'never'),)
    result=SandboxExecutor(tmp_path).execute(make_action(envelope,grant,conditions=c));assert result.rolled_back and not (tmp_path/envelope.exact_targets[0]).exists()


def test_preimage_mismatch_rejected(tmp_path,envelope,grant):
    p=tmp_path/envelope.exact_targets[0];p.parent.mkdir(parents=True);p.write_text('before')
    a=make_action(envelope,grant);a=ActionRequest(**{**a.to_dict(),'kind':a.kind,'postconditions':a.postconditions,'expected_before_digest':digest_bytes(b'wrong')})
    with pytest.raises(IntegrityError):SandboxExecutor(tmp_path).execute(a)


def test_path_traversal_rejected(tmp_path,envelope,grant):
    with pytest.raises(ValidationError):SandboxExecutor(tmp_path).execute(make_action(envelope,grant,target='../x'))


def test_symlink_rejected(tmp_path,envelope,grant):
    outside=tmp_path/'outside';outside.write_text('safe');link=tmp_path/'workspace/test.txt';link.parent.mkdir();link.symlink_to(outside)
    with pytest.raises(ValidationError):SandboxExecutor(tmp_path).execute(make_action(envelope,grant))
    assert outside.read_text()=='safe'


def test_full_canary_repeatable(tmp_path):
    a=run_canary(tmp_path/'a');b=run_canary(tmp_path/'b');assert a==b and a['status']=='PASS'


def test_full_workflow_verified(tmp_path,envelope,grant,case_settlement,test_signer):
    case,settlement=case_settlement
    gate=GateInput(council_state=CouncilState.QUORUM_VERIFIED,risk_class=RiskClass.LOW,effective_diversity=4,evidence_completeness=.99,proof_completeness=.99,novelty_score=0,ambiguity_score=0,irreversibility_score=0,drift_score=0,expected_blast_radius=0,historical_false_green_rate=0,calibration_sample_size=200)
    run=CouncilKernel(db_path=str(tmp_path/'x.db'),sandbox_root=str(tmp_path/'sb'),receipt_signer=test_signer).run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=gate,action=make_action(envelope,grant),now=FIXED_TIME)
    assert run['status']=='VERIFIED' and run['ledger']['status']=='PASS' and run['a11oy']['write_authority'] is False


def test_persistent_signer_permissions(tmp_path):
    p=tmp_path/'key';s=Ed25519Signer.load_or_create(p);assert s.signer_state=='SIGNED_PERSISTENT';assert (p.stat().st_mode&0o077)==0
    assert Ed25519Signer.load_or_create(p).key_id==s.key_id


def test_full_workflow_replays_without_second_mutation(tmp_path,envelope,grant,case_settlement,test_signer):
    case,settlement=case_settlement
    gate=GateInput(council_state=CouncilState.QUORUM_VERIFIED,risk_class=RiskClass.LOW,effective_diversity=4,evidence_completeness=.99,proof_completeness=.99,novelty_score=0,ambiguity_score=0,irreversibility_score=0,drift_score=0,expected_blast_radius=0,historical_false_green_rate=0,calibration_sample_size=200)
    kernel=CouncilKernel(db_path=str(tmp_path/'x.db'),sandbox_root=str(tmp_path/'sb'),receipt_signer=test_signer)
    action=make_action(envelope,grant)
    first=kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=gate,action=action,now=FIXED_TIME)
    event_count=first['ledger']['event_count']
    second=kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=gate,action=action,now=FIXED_TIME)
    assert second['status']=='REPLAYED'
    assert second['original_status']=='VERIFIED'
    assert second['receipt_digest']==first['receipt_digest']
    assert second['ledger']['event_count']==event_count
    assert (tmp_path/'sb'/envelope.exact_targets[0]).read_text()=='ok'


def test_idempotency_binds_gate_context(tmp_path,envelope,grant,case_settlement,test_signer):
    from szl_council_kernel.errors import IdempotencyConflict
    case,settlement=case_settlement
    base=dict(council_state=CouncilState.QUORUM_VERIFIED,risk_class=RiskClass.LOW,effective_diversity=4,evidence_completeness=.99,proof_completeness=.99,novelty_score=0,ambiguity_score=0,irreversibility_score=0,drift_score=0,expected_blast_radius=0,historical_false_green_rate=0,calibration_sample_size=200)
    kernel=CouncilKernel(db_path=str(tmp_path/'x.db'),sandbox_root=str(tmp_path/'sb'),receipt_signer=test_signer)
    action=make_action(envelope,grant)
    kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=GateInput(**base),action=action,now=FIXED_TIME)
    changed={**base,'novelty_score':.1}
    with pytest.raises(IdempotencyConflict):
        kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=GateInput(**changed),action=action,now=FIXED_TIME)


def test_blocked_result_is_replayable(tmp_path,envelope,grant,case_settlement,test_signer):
    case,settlement=case_settlement
    gate=GateInput(council_state=CouncilState.QUORUM_VERIFIED,risk_class=RiskClass.LOW,effective_diversity=4,evidence_completeness=.99,proof_completeness=.99,novelty_score=.9,ambiguity_score=.9,irreversibility_score=.9,drift_score=.9,expected_blast_radius=.9,historical_false_green_rate=.5,calibration_sample_size=200)
    kernel=CouncilKernel(db_path=str(tmp_path/'x.db'),sandbox_root=str(tmp_path/'sb'),receipt_signer=test_signer)
    action=make_action(envelope,grant)
    first=kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=gate,action=action,now=FIXED_TIME)
    second=kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=gate,action=action,now=FIXED_TIME)
    assert first['status']=='BLOCKED'
    assert second['status']=='REPLAYED' and second['original_status']=='BLOCKED'
    assert not (tmp_path/'sb'/envelope.exact_targets[0]).exists()


def _acting_gate():
    return GateInput(council_state=CouncilState.QUORUM_VERIFIED,risk_class=RiskClass.LOW,effective_diversity=4,evidence_completeness=.99,proof_completeness=.99,novelty_score=0,ambiguity_score=0,irreversibility_score=0,drift_score=0,expected_blast_radius=0,historical_false_green_rate=0,calibration_sample_size=200)


def test_authorization_denial_settles_before_target_read(tmp_path,envelope,grant,case_settlement,test_signer,monkeypatch):
    case,settlement=case_settlement
    denied=replace(grant,target_patterns=('other/**',))
    kernel=CouncilKernel(db_path=str(tmp_path/'x.db'),sandbox_root=str(tmp_path/'sb'),receipt_signer=test_signer)
    monkeypatch.setattr(kernel.executor,'check_conditions',lambda *_: (_ for _ in ()).throw(AssertionError('target read occurred before authorization')))
    action=make_action(envelope,denied)
    first=kernel.run_case(case=case,envelope=envelope,grant=denied,settlement=settlement,gate_input=_acting_gate(),action=action,now=FIXED_TIME)
    second=kernel.run_case(case=case,envelope=envelope,grant=denied,settlement=settlement,gate_input=_acting_gate(),action=action,now=FIXED_TIME)
    assert first['status']=='BLOCKED'
    assert first['receipt']['postconditions_passed'] is False
    assert second['status']=='REPLAYED' and second['original_status']=='BLOCKED'
    assert not (tmp_path/'sb'/envelope.exact_targets[0]).exists()


def test_executor_internal_failure_gets_signed_terminal_receipt(tmp_path,envelope,grant,case_settlement,test_signer,monkeypatch):
    case,settlement=case_settlement
    kernel=CouncilKernel(db_path=str(tmp_path/'x.db'),sandbox_root=str(tmp_path/'sb'),receipt_signer=test_signer)
    monkeypatch.setattr(kernel.executor,'execute',lambda *_: (_ for _ in ()).throw(RuntimeError('provider secret must not persist')))
    action=make_action(envelope,grant)
    first=kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=_acting_gate(),action=action,now=FIXED_TIME)
    second=kernel.run_case(case=case,envelope=envelope,grant=grant,settlement=settlement,gate_input=_acting_gate(),action=action,now=FIXED_TIME)
    assert first['status']=='FAILED'
    assert first['signed_receipt']['schema']=='szl.dsse-envelope/v1'
    assert 'provider secret' not in str(first)
    assert first['ledger']['status']=='PASS'
    assert second['status']=='REPLAYED' and second['original_status']=='FAILED'


def test_delete_of_absent_target_is_verified_noop(tmp_path,envelope,grant):
    conditions=(ConditionSpec('FILE_ABSENT',envelope.exact_targets[0],True),)
    result=SandboxExecutor(tmp_path).execute(make_action(envelope,grant,ActionKind.FILE_DELETE,None,conditions))
    assert result.postconditions_passed is True
    assert result.mutation_applied is False
    assert result.rolled_back is False
