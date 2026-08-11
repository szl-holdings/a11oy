import json,subprocess,sys
from pathlib import Path

import pytest
from jsonschema import ValidationError as JSONSchemaValidationError

from szl_council_kernel.benchmark import run_benchmark
from szl_council_kernel.canary import run_canary
from szl_council_kernel.cli import main,parser
from szl_council_kernel.schema_registry import load_schema,schema_names,validate_schema_instance
from szl_council_kernel.fourfold import COMMITMENT_CONTENT_TYPE
from szl_council_kernel.proof import PublicVerifier,verify_signed_object
from szl_council_kernel.errors import ValidationError
from szl_council_kernel.service import create_app
from szl_council_kernel.state_bus import StateBus


def test_cli_surface():
    help_text=parser().format_help();assert 'canary' in help_text and 'run-local' in help_text and 'serve' in help_text


def test_canary_cli_writes(tmp_path):
    out=tmp_path/'out.json';assert main(['canary','--workdir',str(tmp_path/'run'),'--output',str(out)])==0;assert json.loads(out.read_text())['status']=='PASS'


def test_bench_cli_writes(tmp_path):
    out=tmp_path/'out.json';assert main(['bench','--output',str(out)])==0;d=json.loads(out.read_text());assert d['passed']==d['scenario_count']==24


def test_canary_and_bench_deterministic(tmp_path):
    assert run_canary(tmp_path/'a')==run_canary(tmp_path/'b');assert run_benchmark()==run_benchmark()


def test_all_packaged_schemas_valid():
    assert len(schema_names())==18
    for name in schema_names(): assert load_schema(name)['$schema'].endswith('2020-12/schema')


def test_protocol_schemas_accept_complete_canary(tmp_path):
    report=run_canary(tmp_path/'schema-run');settlement=report['run']['council']
    for name,value in (
        ('council-settlement',settlement),
        ('council-case',settlement['case']),
        ('council-policy',settlement['policy']),
        ('council-registry',settlement['registry']),
        ('council-result',settlement['result']),
        ('epistemic-diversity-report',settlement['result']['diversity']),
        ('dsse-envelope',settlement['signed_result']),
        ('act-escalate-gate-result',report['run']['gate']),
    ):
        validate_schema_instance(name,value)
    for identity in settlement['registry']['identities']:
        validate_schema_instance('council-identity',identity)
    authority=settlement['registry']['identities'][0]
    commitment=verify_signed_object(
        settlement['commitments']['AUTHORITY'],
        PublicVerifier(key_id=authority['key_id'],public_key=authority['public_key']),
        expected_payload_type=COMMITMENT_CONTENT_TYPE,
    )
    validate_schema_instance('council-commitment',commitment)
    validate_schema_instance('council-assessment',settlement['reveals']['AUTHORITY']['assessment'])


def test_settlement_schema_rejects_private_reasoning_and_extra_fields(tmp_path):
    settlement=run_canary(tmp_path/'schema-run')['run']['council']
    settlement=dict(settlement);settlement['private_reasoning_included']=True
    with pytest.raises(JSONSchemaValidationError):validate_schema_instance('council-settlement',settlement)
    settlement=run_canary(tmp_path/'schema-run-2')['run']['council'];settlement=dict(settlement);settlement['hidden_override']=True
    with pytest.raises(JSONSchemaValidationError):validate_schema_instance('council-settlement',settlement)


def test_schema_format_checker_rejects_invalid_timestamp():
    value={
      'schema':'szl.council-case/v1','case_id':'case-format','subject':'format check','risk_class':'LOW',
      'value_claimed':False,'evidence_manifest_digest':'sha256:'+'1'*64,'policy_digest':'sha256:'+'2'*64,
      'envelope_digest':'sha256:'+'3'*64,'epochs_digest':'sha256:'+'4'*64,'created_at':'not-a-date'
    }
    with pytest.raises(JSONSchemaValidationError):validate_schema_instance('council-case',value)


def test_schema_rejects_extra_property(envelope):
    value=envelope.to_dict();value['unexpected']=True
    with pytest.raises(JSONSchemaValidationError):validate_schema_instance('autonomy-envelope',value)


def test_schema_accepts_envelope(envelope):
    validate_schema_instance('autonomy-envelope',envelope.to_dict())


def test_keygen_cli(tmp_path):
    key=tmp_path/'key';out=tmp_path/'pub.json';assert main(['keygen','--path',str(key),'--output',str(out)])==0;assert key.exists() and json.loads(out.read_text())['signer_state']=='SIGNED_PERSISTENT'


def test_foundry_cli(tmp_path):
    manifest=tmp_path/'f.json';out=tmp_path/'x.json';assert main(['foundry-register','--manifest',str(manifest),'--id','a','--title','A','--url','https://example.com/a','--type','PUBLICATION','--output',str(out)])==0;assert main(['foundry-inventory','--manifest',str(manifest),'--output',str(out)])==0;assert len(json.loads(out.read_text())['artifacts'])==1


def test_run_local_cli(tmp_path):
    spec={'case_id':'case-cli-local','target':'workspace/x.txt','content':'ok frontier','expected_text':'frontier','risk_class':'LOW','calibration_sample_size':200}
    p=tmp_path/'spec.json';p.write_text(json.dumps(spec));out=tmp_path/'run.json'
    rc=main(['run-local','--input',str(p),'--db',str(tmp_path/'x.db'),'--sandbox',str(tmp_path/'sb'),'--signing-key',str(tmp_path/'key'),'--allow-local-test-council','--output',str(out)])
    assert rc==0;d=json.loads(out.read_text());assert d['status']=='VERIFIED' and d['local_test_council'] is True


def test_service_health_and_read_only(tmp_path):
    pytest.importorskip('fastapi');from fastapi.testclient import TestClient
    app=create_app(db_path=str(tmp_path/'x.db'),runtime_root=str(tmp_path/'runtime'))
    c=TestClient(app);assert c.get('/healthz').status_code==200;status=c.get('/api/v1/status').json();assert status['projection_mode']=='read-only';assert c.post('/api/v1/canary').status_code==503


def test_console_assets_served(tmp_path):
    pytest.importorskip('fastapi');from fastapi.testclient import TestClient
    c=TestClient(create_app(db_path=str(tmp_path/'x.db'),runtime_root=str(tmp_path/'runtime')));html=c.get('/').text
    assert 'Models propose' in html and 'read-only' in html.lower()
    assert 'aria-live="polite"' in html and 'Skip to kernel status' in html and '<caption' in html
    script=c.get('/app.js').text
    assert 'innerHTML' not in script and 'textContent' in script and 'replaceChildren' in script


def test_secret_scan_passes_repository():
    root=Path(__file__).resolve().parents[1];proc=subprocess.run([sys.executable,str(root/'tools/static_secret_scan.py'),str(root)],capture_output=True,text=True);assert proc.returncode==0,proc.stdout+proc.stderr


def test_service_security_headers_and_sensitive_read_gate(tmp_path):
    pytest.importorskip('fastapi');from fastapi.testclient import TestClient
    read_token='r'*32
    c=TestClient(create_app(db_path=str(tmp_path/'x.db'),runtime_root=str(tmp_path/'runtime'),read_token=read_token))
    response=c.get('/api/v1/status')
    assert response.status_code==200
    assert response.headers['x-content-type-options']=='nosniff'
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert c.get('/api/v1/cases').status_code==401
    assert c.get('/api/v1/cases',headers={'X-Alloy-Read-Token':read_token}).status_code==200
    assert c.get('/api/v1/evidence/export',headers={'Authorization':'Bearer '+read_token}).status_code==200


def test_service_rejects_short_tokens(tmp_path):
    pytest.importorskip('fastapi')
    with pytest.raises(ValidationError):
        create_app(db_path=str(tmp_path/'x.db'),runtime_root=str(tmp_path/'runtime'),admin_token='short')
