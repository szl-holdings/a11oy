import json,sqlite3
from pathlib import Path

import pytest

from szl_council_kernel.canary import FIXED_TIME
from szl_council_kernel.canonical import digest_object
from szl_council_kernel.enums import WorkflowState
from szl_council_kernel.errors import IdempotencyConflict,IntegrityError,StateTransitionError,ValidationError
from szl_council_kernel.state_bus import StateBus


def test_empty_bus_verifies(tmp_path):
    assert StateBus(tmp_path/'x.db').verify_chain()['status']=='PASS'


def test_event_chain_and_object_store(tmp_path):
    bus=StateBus(tmp_path/'x.db');e=bus.append_event(event_id='e1',case_id=None,event_type='TEST',payload={'x':1},created_at=FIXED_TIME)
    assert e['previous_hash']==bus.verify_chain()['genesis_hash']
    assert bus.get_object(e['payload_digest'])=={'x':1}


def test_tamper_detected(tmp_path):
    db=tmp_path/'x.db';bus=StateBus(db);bus.append_event(event_id='e1',case_id=None,event_type='TEST',payload={'x':1},created_at=FIXED_TIME)
    with sqlite3.connect(db) as c:c.execute("update events set event_type='BAD'");c.commit()
    assert bus.verify_chain()['status']=='FAIL'


def test_case_transitions(tmp_path):
    bus=StateBus(tmp_path/'x.db');bus.create_case(case_id='case-1',case_value={'c':1},envelope_value={'e':1},created_at=FIXED_TIME)
    bus.transition_case('case-1',WorkflowState.DELIBERATING,created_at=FIXED_TIME)
    assert bus.get_case('case-1')['case']['state']=='DELIBERATING'


def test_illegal_case_transition_rejected(tmp_path):
    bus=StateBus(tmp_path/'x.db');bus.create_case(case_id='case-1',case_value={'c':1},envelope_value={'e':1},created_at=FIXED_TIME)
    with pytest.raises(StateTransitionError):bus.transition_case('case-1',WorkflowState.SETTLED,created_at=FIXED_TIME)


def test_idempotency_replay_and_conflict(tmp_path):
    bus=StateBus(tmp_path/'x.db');a=digest_object({'a':1});r=bus.store_object('receipt',{'r':1},created_at=FIXED_TIME)
    assert bus.reserve_idempotency('k',a,created_at=FIXED_TIME).state=='NEW';bus.settle_idempotency('k',a,r,created_at=FIXED_TIME)
    assert bus.reserve_idempotency('k',a,created_at=FIXED_TIME).replay
    with pytest.raises(IdempotencyConflict):bus.reserve_idempotency('k',digest_object({'a':2}),created_at=FIXED_TIME)


def test_transparency_inclusion(tmp_path):
    bus=StateBus(tmp_path/'x.db');r=bus.append_transparency({'x':1},created_at=FIXED_TIME)
    assert r['verified'] is True and bus.verify_transparency()['status']=='PASS'


def test_negative_capability_lookup(tmp_path):
    bus=StateBus(tmp_path/'x.db');bus.add_negative_capability({'entry_id':'n1','task_class':'deploy','tool':'api','domain':'prod','condition_code':'NO_ROLLBACK','epoch_digest':digest_object({'e':1}),'status':'ACTIVE'},created_at=FIXED_TIME)
    assert len(bus.query_negative_capabilities(task_class='deploy',tool='api',domain='prod'))==1
    assert bus.query_negative_capabilities(task_class='deploy',tool='other',domain='prod')==[]


def test_outcome_lifecycle(tmp_path):
    bus=StateBus(tmp_path/'x.db');d=bus.register_outcome('o1','c1',{'contract':1},created_at=FIXED_TIME);s=bus.settle_outcome('o1',{'settled':1},created_at=FIXED_TIME)
    assert d.startswith('sha256:') and s.startswith('sha256:')
    with pytest.raises(StateTransitionError):bus.settle_outcome('o1',{'again':1},created_at=FIXED_TIME)


def test_evidence_export_is_bound(tmp_path):
    bus=StateBus(tmp_path/'x.db');bus.append_event(event_id='e1',case_id=None,event_type='TEST',payload={'x':1},created_at=FIXED_TIME)
    export=bus.export_evidence();assert export['verification']['status']=='PASS';assert export['bundle_digest']==digest_object({k:v for k,v in export.items() if k!='bundle_digest'})


def test_state_bus_file_permissions_are_owner_only(tmp_path):
    db=tmp_path/'x.db';StateBus(db)
    assert db.stat().st_mode & 0o077 == 0


def test_noncanonical_object_encoding_detected(tmp_path):
    db=tmp_path/'x.db';bus=StateBus(db);event=bus.append_event(event_id='e1',case_id=None,event_type='TEST',payload={'x':1},created_at=FIXED_TIME)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE objects SET canonical_json=? WHERE digest=?", ('{"x": 1}',event['payload_digest']))
        conn.commit()
    report=bus.verify_chain()
    assert report['status']=='FAIL'
    assert any(item.startswith('OBJECT_NONCANONICAL:') for item in report['errors'])


def test_case_index_state_tamper_detected(tmp_path):
    db=tmp_path/'x.db';bus=StateBus(db);bus.create_case(case_id='case-1',case_value={'case_id':'case-1'},envelope_value={'case_id':'case-1','envelope':True},created_at=FIXED_TIME)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE cases SET state='SETTLED' WHERE case_id='case-1'")
        conn.commit()
    report=bus.verify_chain()
    assert report['status']=='FAIL'
    assert any(item.startswith('CASE_STATE_MISMATCH:case-1') for item in report['errors'])


def test_begin_attempt_is_atomic_on_orphan_case_conflict(tmp_path):
    bus=StateBus(tmp_path/'x.db');bus.create_case(case_id='case-1',case_value={'case_id':'case-1'},envelope_value={'case_id':'case-1','envelope':True},created_at=FIXED_TIME)
    with pytest.raises(IntegrityError):
        bus.begin_attempt_and_case(case_id='case-1',case_value={'case_id':'case-1'},envelope_value={'case_id':'case-1','envelope':True},idempotency_key='idem-1',action_digest=digest_object({'a':1}),created_at=FIXED_TIME)
    assert bus.lookup_idempotency('idem-1') is None


def test_settled_replay_rejects_missing_receipt_index(tmp_path):
    db=tmp_path/'x.db';bus=StateBus(db);attempt=digest_object({'attempt':1});receipt={'schema':'test-receipt','value':1};signed={'schema':'test-signed','value':1}
    bus.begin_attempt_and_case(case_id='case-1',case_value={'case_id':'case-1'},envelope_value={'case_id':'case-1','envelope':True},idempotency_key='idem-1',action_digest=attempt,created_at=FIXED_TIME)
    bus.settle_attempt_receipt(idempotency_key='idem-1',action_digest=attempt,receipt=receipt,case_id='case-1',action_id='action-1',signed_envelope=signed,created_at=FIXED_TIME)
    with sqlite3.connect(db) as conn:
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute('DELETE FROM receipts')
        conn.commit()
    with pytest.raises(IntegrityError):
        bus.settle_attempt_receipt(idempotency_key='idem-1',action_digest=attempt,receipt=receipt,case_id='case-1',action_id='action-1',signed_envelope=signed,created_at=FIXED_TIME)
    assert bus.verify_chain()['status']=='FAIL'


def test_negative_capability_identity_is_immutable_and_expiry_is_honored(tmp_path):
    bus=StateBus(tmp_path/'x.db');base={'entry_id':'n1','task_class':'deploy','tool':'api','domain':'prod','condition_code':'NO_ROLLBACK','epoch_digest':digest_object({'e':1}),'status':'ACTIVE','expires_at':'2026-08-04T12:00:00Z'}
    first=bus.add_negative_capability(base,created_at=FIXED_TIME)
    assert bus.add_negative_capability(base,created_at=FIXED_TIME)==first
    changed={**base,'condition_code':'OTHER'}
    with pytest.raises(IntegrityError):bus.add_negative_capability(changed,created_at=FIXED_TIME)
    resolved={**base,'status':'RESOLVED','evidence_digest':digest_object({'fixed':1})}
    bus.add_negative_capability(resolved,created_at=FIXED_TIME)
    with pytest.raises(StateTransitionError):bus.add_negative_capability(base,created_at=FIXED_TIME)
    assert bus.query_negative_capabilities(task_class='deploy',tool='api',domain='prod',now='2026-08-03T13:00:00Z')==[]


def test_negative_capability_rejects_already_expired_entry(tmp_path):
    bus=StateBus(tmp_path/'x.db')
    with pytest.raises(ValidationError):
        bus.add_negative_capability({'entry_id':'n1','task_class':'deploy','condition_code':'NOPE','epoch_digest':digest_object({'e':1}),'status':'ACTIVE','expires_at':'2026-08-03T11:59:59Z'},created_at=FIXED_TIME)
