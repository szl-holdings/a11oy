import copy

import pytest

from szl_council_kernel.canary import FIXED_EXPIRY,FIXED_TIME,build_deterministic_council
from szl_council_kernel.canonical import digest_object
from szl_council_kernel.enums import CouncilRole,CouncilVote,RiskClass
from szl_council_kernel.errors import IntegrityError,ValidationError
from szl_council_kernel.fourfold import CouncilSession,sign_assessment,sign_commitment,verify_settlement
from szl_council_kernel.models import CouncilAssessment,CouncilCase,CouncilIdentity
from szl_council_kernel.proof import Ed25519Signer


def votes(**overrides):
    value={role:CouncilVote.SUPPORT for role in CouncilRole}
    for key,vote in overrides.items():value[CouncilRole[key]]=CouncilVote[vote]
    return value


def test_all_support_verifies(envelope,policy):
    case,settlement=build_deterministic_council(envelope=envelope,policy=policy)
    assert settlement['result']['state']=='QUORUM_VERIFIED'
    assert settlement['result']['verified'] is True
    assert verify_settlement(settlement)['status']=='PASS'


@pytest.mark.parametrize('role',[CouncilRole.SENTINEL,CouncilRole.VERIFIER])
def test_categorical_veto_blocks(envelope,policy,role):
    v={item:CouncilVote.SUPPORT for item in CouncilRole};v[role]=CouncilVote.VETO
    _,s=build_deterministic_council(envelope=envelope,policy=policy,votes=v)
    assert s['result']['state']=='BLOCKED'


def test_authority_opposition_blocks(envelope,policy):
    _,s=build_deterministic_council(envelope=envelope,policy=policy,votes=votes(AUTHORITY='OPPOSE'))
    assert s['result']['state']=='BLOCKED'


def test_value_opposition_preserves_conflict(envelope,policy):
    _,s=build_deterministic_council(envelope=envelope,policy=policy,votes=votes(VALUE='OPPOSE'))
    assert s['result']['state']=='CONFLICT'
    assert s['result']['minority_evidence_digests']
    assert s['minority_truth_vault']['verification']['status']=='PASS'


def test_correlated_replicas_insufficient(envelope,policy):
    _,s=build_deterministic_council(envelope=envelope,policy=policy,correlated=True)
    assert s['result']['state']=='INSUFFICIENT'
    assert 'EFFECTIVE_COUNCIL_SIZE_BELOW_MINIMUM' in s['result']['reason_codes']


def test_signed_result_tamper_detected(envelope,policy):
    _,s=build_deterministic_council(envelope=envelope,policy=policy)
    bad=copy.deepcopy(s);bad['result']['state']='BLOCKED'
    assert verify_settlement(bad)['status']=='FAIL'


def build_manual(envelope,policy):
    case=CouncilCase(case_id=envelope.case_id,subject=envelope.subject,risk_class=RiskClass.LOW,value_claimed=False,evidence_manifest_digest=digest_object({'e':1}),policy_digest=policy.digest,envelope_digest=envelope.digest,epochs_digest=envelope.epochs.digest,created_at=FIXED_TIME)
    signers={r:Ed25519Signer.from_seed(digest_object({'r':r.value}).split(':',1)[1].encode()[:32],signer_state='SIGNED_TEST') for r in CouncilRole}
    # Above seed is ASCII hex; still exactly 32 bytes and deterministic.
    identities=[]
    for i,r in enumerate(CouncilRole):
        s=signers[r]
        identities.append(CouncilIdentity(member_id='manual-'+r.value.lower(),role=r,key_id=s.key_id,public_key=s.public_key,trust_domain=f'td-{i}',implementation_digest=digest_object({'i':i}),model_family=f'm-{i}',evidence_domain=f'e-{i}',operator_id=f'o-{i}',retrieval_path=f'r-{i}',provider_account=f'p-{i}',not_before=FIXED_TIME,not_after=FIXED_EXPIRY))
    return case,signers,identities


def test_reveal_before_seal_rejected(envelope,policy):
    case,signers,identities=build_manual(envelope,policy)
    session=CouncilSession(case,policy,identities,session_time=FIXED_TIME)
    r=CouncilRole.AUTHORITY
    a=CouncilAssessment(case_id=case.case_id,role=r,member_id='manual-authority',vote=CouncilVote.SUPPORT,confidence=.9,reason_codes=('OK',),evidence_digests=(digest_object({'e':'a'}),),counterevidence_digests=(),policy_digest=policy.digest,subject_digest=case.digest,issued_at=FIXED_TIME,expires_at=FIXED_EXPIRY)
    with pytest.raises(IntegrityError):session.reveal(r,a,'salt-0123456789012345',sign_assessment(a,signers[r]))


def test_commitment_payload_tamper_rejected(envelope,policy):
    case,signers,identities=build_manual(envelope,policy)
    session=CouncilSession(case,policy,identities,session_time=FIXED_TIME)
    r=CouncilRole.AUTHORITY
    a=CouncilAssessment(case_id=case.case_id,role=r,member_id='manual-authority',vote=CouncilVote.SUPPORT,confidence=.9,reason_codes=('OK',),evidence_digests=(digest_object({'e':'a'}),),counterevidence_digests=(),policy_digest=policy.digest,subject_digest=case.digest,issued_at=FIXED_TIME,expires_at=FIXED_EXPIRY)
    signed=sign_commitment(a,'salt-0123456789012345',signers[r]);signed['envelope_digest']=digest_object({'tampered':1})
    with pytest.raises(IntegrityError):session.submit_commitment(r,signed)


def test_duplicate_key_registry_rejected(envelope,policy,test_signer):
    case=CouncilCase(case_id=envelope.case_id,subject=envelope.subject,risk_class=RiskClass.LOW,value_claimed=False,evidence_manifest_digest=digest_object({'e':1}),policy_digest=policy.digest,envelope_digest=envelope.digest,epochs_digest=envelope.epochs.digest,created_at=FIXED_TIME)
    ids=[CouncilIdentity(member_id='m-'+r.value.lower(),role=r,key_id=test_signer.key_id,public_key=test_signer.public_key,trust_domain=f'td-{i}',implementation_digest=digest_object({'i':i}),model_family=f'm-{i}',evidence_domain=f'e-{i}',operator_id=f'o-{i}',retrieval_path=f'r-{i}',provider_account=f'p-{i}',not_before=FIXED_TIME,not_after=FIXED_EXPIRY) for i,r in enumerate(CouncilRole)]
    with pytest.raises(ValidationError):CouncilSession(case,policy,ids,session_time=FIXED_TIME)


def test_high_risk_all_support_verifies(envelope,policy):
    _,s=build_deterministic_council(envelope=envelope,policy=policy,risk_class=RiskClass.HIGH)
    assert s['result']['required_support']==4 and s['result']['state']=='QUORUM_VERIFIED'


def _retag_settlement(value):
    body={key:item for key,item in value.items() if key!='settlement_digest'}
    value['settlement_digest']=digest_object(body)
    return value


@pytest.mark.parametrize(
    'tamper',
    [
        'commitment_payload',
        'reveal_salt',
        'registry_diversity',
        'minority_vault',
        'policy',
        'case',
    ],
)
def test_portable_settlement_detects_transcript_tampering(envelope,policy,tamper):
    _,settlement=build_deterministic_council(
        envelope=envelope,
        policy=policy,
        votes=votes(VALUE='OPPOSE') if tamper=='minority_vault' else None,
    )
    bad=copy.deepcopy(settlement)
    if tamper=='commitment_payload':
        role=CouncilRole.AUTHORITY.value
        bad['commitments'][role]['envelope']['payload']='AA'
        bad['commitments'][role]['envelope_digest']=digest_object(bad['commitments'][role]['envelope'])
    elif tamper=='reveal_salt':
        bad['reveals'][CouncilRole.AUTHORITY.value]['salt']='different-salt-0123456789'
    elif tamper=='registry_diversity':
        bad['registry']['identities'][0]['operator_id']='operator-tampered'
        registry_body={key:item for key,item in bad['registry'].items() if key!='registry_digest'}
        bad['registry']['registry_digest']=digest_object(registry_body)
    elif tamper=='minority_vault':
        bad['minority_truth_vault']['entries'][0]['reason_codes']=['REWRITTEN']
    elif tamper=='policy':
        bad['policy']['low_medium_support_threshold']=4
    elif tamper=='case':
        bad['case']['subject']='tampered subject'
    _retag_settlement(bad)
    report=verify_settlement(bad)
    assert report['status']=='FAIL'
    assert report['portable_transcript_replayed'] is False


def test_portable_settlement_rejects_reveal_order_substitution(envelope,policy):
    _,settlement=build_deterministic_council(envelope=envelope,policy=policy)
    bad=copy.deepcopy(settlement)
    bad['reveal_order'][0]=bad['reveal_order'][1]
    _retag_settlement(bad)
    assert verify_settlement(bad)['status']=='FAIL'
