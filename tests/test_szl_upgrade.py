"""Offline regressions for the upgrade kit; no network or HF mutations.

Path bootstrap keeps these primitives importable from A11oy tests/ without a
new top-level runtime service.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import copy
import hashlib
import io
import json
import math
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

from szl_release_guard import (
    ContractError, PhaseFailure, ReleaseJournal, VIEWPORTS, browser_gate, canonical,
    classify_process, digest, identity_gate, immutable_json, inspect_archive,
    inspect_publisher, phase_step_gate, run_bounded, strict_json, verify_event_chain,
)
from szl_forecast_acceptance import (
    INPUT, PREFIX, PublicTransport, expected_risk, quantile_label,
    validate_envelope, validate_forecast, validate_risk, verify_extended_contract,
)

SOURCE = "a" * 40
PUBLISHER = "b" * 40
HF = "c" * 40
EVIDENCE = "d" * 64


def forecast_fixture(request=None):
    request = copy.deepcopy(request or INPUT)
    points = [{"step": i, "quantiles": {"q10": float(8+i), "q50": float(11+i),
                                       "q90": float(15+i)}} for i in range(1, 4)]
    basis = {"contract": "szl.lyte.forecast-loom/v1", "signal_id": request["signal_id"],
             "values": [10.0, 11.0, 11.0, 13.0, 14.0], "horizon": 3,
             "quantiles": [0.1, 0.5, 0.9]}
    receipt = {"contract": basis["contract"], "signal_id": request["signal_id"],
               "provider": "szl.robust-drift/v1", "horizon": 3, "quantiles": [0.1,0.5,0.9],
               "input_sha256": digest(basis),
               "raw_input_sha256": digest({**basis, "values": request["values"]}),
               "output_sha256": digest(points), "context_points": 5,
               "original_context_points": 5, "truncated_points": 0,
               "imputed_points": request["values"].count(None)}
    risk = {"contract": "szl.lyte.forecast-risk-window/v1",
            "signal_id": request["signal_id"], "provider": "szl.robust-drift/v1",
            "rule": request["risk"], "execution_authority": "NONE", "production_admitted": False,
            "calibration_status": "NOT_ESTABLISHED", "time_unit": "FORECAST_STEPS_NOT_WALL_CLOCK",
            "event_semantics": "STRICT_GREATER_THAN" if request["risk"]["direction"] == "above"
                               else "STRICT_LESS_THAN",
            "forecast_output_sha256": digest(points), "forecast_receipt_sha256": digest(receipt),
            **expected_risk(points, request["quantiles"], request["risk"])}
    risk["report_sha256"] = digest(risk)
    return {"points": points, "receipt": receipt, "risk_window": risk, "execution_authority": "NONE"}


def envelope_fixture(request=None):
    request = copy.deepcopy(request or INPUT)
    body = {"schema": "szl.lyte.forecast-inspection/v1",
            "source": {"repository": "szl-holdings/lyte-services", "revision": SOURCE},
            "request": request, "forecast": forecast_fixture(request),
            "input_provenance": "CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED",
            "execution_authority": "NONE", "persisted": False}
    raw = canonical(body).decode()
    return {"schema": "szl.lyte.forecast-inspection-envelope/v1", "canonical_json": raw,
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "hash_semantics": "CONTENT_INTEGRITY_NOT_SIGNATURE_OR_ACCURACY"}


class FixtureTransport:
    def json(self, path, method="GET", payload=None, **_):
        if path == "/api/build-info":
            return 200, {"source_revision": SOURCE, "runtime_source_revision": SOURCE,
                         "effectors_enabled": False}
        if method == "GET" and path == PREFIX:
            return 200, {"schema": "szl.lyte.forecast-workbench/v1",
                         "workbench": PREFIX + "/workbench", "inspection": PREFIX + "/inspect",
                         "inspection_provider": "baseline", "execution_authority": "NONE"}
        if path == PREFIX + "/inspect":
            if payload["provider"] != "baseline" or payload["risk"] is None:
                return 422, {"detail": "rejected"}
            return 200, envelope_fixture(payload)
        if path == PREFIX and method == "POST":
            if payload["provider"] == "granite":
                return 503, {"detail": "Granite provider is not admitted in this deployment"}
            if payload["horizon"] == 0:
                return 422, {"detail": "rejected"}
            return 200, forecast_fixture(payload)
        raise AssertionError("unexpected test path")

    def text(self, path):
        if path == PREFIX + "/workbench":
            return 200, '<html>Forecast Loom<script src="/static/lyte/forecast.mjs"></script></html>'
        raise AssertionError(path)


class CoreTests(unittest.TestCase):
    def test_canonical_is_stable(self):
        self.assertEqual(digest({"a":1,"b":2}), digest({"b":2,"a":1}))

    def test_nonfinite_rejected(self):
        for x in (math.nan, math.inf, -math.inf):
            with self.subTest(x=x), self.assertRaises(ValueError): canonical(x)

    def test_strict_duplicate_json(self):
        with self.assertRaises(ContractError): strict_json('{"a":1,"a":2}')

    def test_strict_nonfinite_tokens(self):
        for x in ('NaN','Infinity','-Infinity','1e999'):
            with self.subTest(x=x), self.assertRaises(ContractError): strict_json(x)

    def test_strict_size_utf8_and_shape(self):
        for raw in (b'\xff', b'{', b'"' + b'x'*50 + b'"'):
            with self.subTest(raw=raw), self.assertRaises(ContractError): strict_json(raw,limit=20)

    def test_strict_roundtrip(self):
        self.assertEqual(strict_json(canonical({"é": [1,None,False]})), {"é":[1,None,False]})

    def test_immutable_write_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            a=immutable_json(pathlib.Path(td),{"ok":True})
            b=immutable_json(pathlib.Path(td),{"ok":True})
            self.assertEqual(a,b)
            self.assertEqual(a.stat().st_mode & 0o777,0o600)

    def test_tampered_existing_content_fails(self):
        with tempfile.TemporaryDirectory() as td:
            a=immutable_json(pathlib.Path(td),{"ok":True})
            a.write_bytes(b'broken')
            with self.assertRaises(ContractError): immutable_json(pathlib.Path(td),{"ok":True})

    def test_symlink_output_directory_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);(root/'real').mkdir();(root/'link').symlink_to(root/'real')
            with self.assertRaises(ContractError): immutable_json(root/'link',{})

    def test_process_success(self):
        r=run_bounded([sys.executable,'-c','print("actual process")'],cwd=pathlib.Path.cwd())
        self.assertTrue(r['passed']); self.assertEqual(r['exit_code'],0)
        self.assertFalse(r['raw_output_recorded'])

    def test_process_failure_classifies_without_raw_message(self):
        code='import sys;print("::error title=HF deploy contract::private-token");sys.exit(2)'
        r=run_bounded([sys.executable,'-c',code],cwd=pathlib.Path.cwd())
        self.assertFalse(r['passed']);self.assertEqual(r['reason_code'],'DEPLOY_CONTRACT_REJECTED')
        self.assertNotIn('private-token',json.dumps(r))

    def test_exit_two_does_not_invent_root_cause(self):
        self.assertEqual(classify_process(2,b'',timed_out=False,output_limited=False),'NONZERO_EXIT_UNCLASSIFIED')

    def test_error_code_categories(self):
        for text,want in ((b'unrecognized arguments: --oops','CLI_ARGUMENT_REJECTED'),
                          (b'HTTP Error 502: unavailable','UPSTREAM_502_REPORTED'),
                          (b'default-branch-tip mismatch','DEFAULT_TIP_GUARD_REPORTED')):
            with self.subTest(text=text):
                self.assertEqual(classify_process(2,text,timed_out=False,output_limited=False),want)

    def test_timeout_fails_and_terminates(self):
        r=run_bounded([sys.executable,'-c','import time;time.sleep(20)'],cwd=pathlib.Path.cwd(),timeout=.15)
        self.assertTrue(r['timed_out']);self.assertFalse(r['passed'])
        self.assertLess(r['elapsed_seconds'],4)

    def test_output_limit_fails(self):
        r=run_bounded([sys.executable,'-c','print("x"*1000000)'],cwd=pathlib.Path.cwd(),max_output=1024)
        self.assertTrue(r['output_limited']);self.assertFalse(r['passed'])
        self.assertLessEqual(sum(x['captured_bytes'] for x in r['streams'].values()),1024)

    def test_shell_string_is_rejected(self):
        with self.assertRaises(ContractError): run_bounded('echo hi',cwd=pathlib.Path.cwd())

    def test_invalid_timeouts(self):
        for timeout in (0,-1,math.nan,math.inf,True,4000):
            with self.subTest(timeout=timeout),self.assertRaises(ContractError):
                run_bounded([sys.executable,'-V'],cwd=pathlib.Path.cwd(),timeout=timeout)

    def test_no_output_does_not_deadlock(self):
        self.assertTrue(run_bounded([sys.executable,'-c','pass'],cwd=pathlib.Path.cwd())['passed'])

    def test_stdout_and_stderr_are_drained(self):
        code='import sys;sys.stdout.write("a"*50000);sys.stderr.write("b"*50000)'
        r=run_bounded([sys.executable,'-c',code],cwd=pathlib.Path.cwd())
        self.assertTrue(r['passed']);self.assertEqual(r['streams']['stdout']['captured_bytes'],50000)
        self.assertEqual(r['streams']['stderr']['captured_bytes'],50000)

    def test_child_process_group_is_killed(self):
        with tempfile.TemporaryDirectory() as td:
            marker=pathlib.Path(td)/'should-not-exist'
            child=f'import time,pathlib;time.sleep(.8);pathlib.Path({str(marker)!r}).write_text("leak")'
            parent=f'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",{child!r}]);time.sleep(10)'
            r=run_bounded([sys.executable,'-c',parent],cwd=pathlib.Path(td),timeout=.15)
            import time;time.sleep(.9)
            self.assertTrue(r['timed_out']);self.assertFalse(marker.exists())

    def test_journal_complete_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            j=ReleaseJournal(pathlib.Path(td),source=SOURCE,publisher=PUBLISHER,phases=('first','second'))
            for p in ('first','second'):
                j.perform(p,lambda:{'executed':True,'passed':True,'evidence_sha256':EVIDENCE})
            self.assertTrue(j.summary()['complete']);self.assertTrue(verify_event_chain(j.events))

    def test_journal_refuses_out_of_order(self):
        with tempfile.TemporaryDirectory() as td:
            j=ReleaseJournal(pathlib.Path(td),source=SOURCE,publisher=PUBLISHER,phases=('first','second'))
            with self.assertRaises(ContractError):j.perform('second',lambda:{})

    def test_journal_fail_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            j=ReleaseJournal(pathlib.Path(td),source=SOURCE,publisher=PUBLISHER,phases=('first','second'))
            def fail():raise RuntimeError('secret detail')
            with self.assertRaises(PhaseFailure):j.perform('first',fail)
            self.assertEqual(len(list(j.directory.glob('*.json'))),2)
            self.assertFalse(j.summary()['complete']);self.assertNotIn('secret detail',json.dumps(j.events))
            with self.assertRaises(ContractError):j.perform('second',lambda:{})

    def test_journal_skipped_is_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            j=ReleaseJournal(pathlib.Path(td),source=SOURCE,publisher=PUBLISHER,phases=('first',))
            with self.assertRaises(PhaseFailure):
                j.perform('first',lambda:{'executed':False,'passed':True,'evidence_sha256':EVIDENCE})

    def test_journal_requires_evidence_digest(self):
        with tempfile.TemporaryDirectory() as td:
            j=ReleaseJournal(pathlib.Path(td),source=SOURCE,publisher=PUBLISHER,phases=('first',))
            with self.assertRaises(PhaseFailure): j.perform('first',lambda:{'executed':True,'passed':True})

    def test_chain_tamper_detected(self):
        with tempfile.TemporaryDirectory() as td:
            j=ReleaseJournal(pathlib.Path(td),source=SOURCE,publisher=PUBLISHER,phases=('first',))
            j.perform('first',lambda:{'executed':True,'passed':True,'evidence_sha256':EVIDENCE})
            j.events[0]['state']='FAKE'
            self.assertFalse(verify_event_chain(j.events))

    def test_empty_chain_is_not_evidence(self):
        self.assertFalse(verify_event_chain([]))

    def test_identity_namespaces_are_separate(self):
        self.assertTrue(identity_gate(producer=SOURCE,observed_source=SOURCE,hf_published=HF,
                                      hf_running=HF,hf_stage='RUNNING',image_manifest_match=True))

    def test_identity_fails_old_image_even_if_config_agrees(self):
        self.assertFalse(identity_gate(producer=SOURCE,observed_source=SOURCE,hf_published=HF,
                         hf_running=PUBLISHER,hf_stage='RUNNING',image_manifest_match=True))

    def test_identity_requires_image_manifest(self):
        self.assertFalse(identity_gate(producer=SOURCE,observed_source=SOURCE,hf_published=HF,
                         hf_running=HF,hf_stage='RUNNING',image_manifest_match=False))

    def test_green_job_with_skipped_publish_is_not_deployed(self):
        jobs=[{'name':'publish','status':'completed','conclusion':'success','steps':[
            {'name':'upload','status':'completed','conclusion':'skipped'}]}]
        self.assertFalse(phase_step_gate(jobs,job_name='publish',required_steps=['upload'])['passed'])

    def test_real_step_is_required(self):
        jobs=[{'name':'publish','status':'completed','conclusion':'success','steps':[
            {'name':'upload','status':'completed','conclusion':'success'}]}]
        self.assertTrue(phase_step_gate(jobs,job_name='publish',required_steps=['upload'])['passed'])
        self.assertFalse(phase_step_gate(jobs*2,job_name='publish',required_steps=['upload'])['passed'])

    def test_browser_requires_all_seven_live_sizes(self):
        rows=[{'viewport':list(v),'executed':True,'passed':True,'source_revision':SOURCE,
               'scope':'PUBLIC_RUNTIME','report_sha256':EVIDENCE} for v in VIEWPORTS]
        self.assertTrue(browser_gate(rows,source=SOURCE))
        self.assertFalse(browser_gate(rows[:4],source=SOURCE))
        rows[0]['scope']='LOCAL_APPLICATION'
        self.assertFalse(browser_gate(rows,source=SOURCE))

    def test_browser_no_duplicate_or_missing_proof(self):
        rows=[{'viewport':list(v),'executed':True,'passed':True,'source_revision':SOURCE,
               'scope':'PUBLIC_RUNTIME','report_sha256':EVIDENCE} for v in VIEWPORTS]
        rows[-1]=rows[0]
        self.assertFalse(browser_gate(rows,source=SOURCE))

    def test_static_audit_never_executes_source(self):
        text='SOURCE_REVISION="'+SOURCE+'"\nraise RuntimeError("must not execute")\ndef main():\n ensure_runtime_configuration()\n deploy_with_controller()\n'
        r=inspect_publisher(text)
        self.assertEqual(r['constants']['SOURCE_REVISION'],SOURCE)
        self.assertTrue(r['config_call_lexically_before_deploy'])

    def test_static_duplicate_constants_rejected(self):
        with self.assertRaises(ContractError):inspect_publisher('SOURCE_REVISION="a"\nSOURCE_REVISION="b"')

    def archive(self,members):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for name,data in members:z.writestr(name,data)
        return stream.getvalue()

    def test_archive_exact_digest_and_no_extraction(self):
        raw=self.archive([('receipt.json','{"complete":false}')])
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'a.zip';p.write_bytes(raw)
            r=inspect_archive(p,hashlib.sha256(raw).hexdigest(),'receipt.json')
            self.assertFalse(r['receipt']['complete']);self.assertEqual(len(list(pathlib.Path(td).iterdir())),1)

    def test_archive_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'a.zip';p.write_bytes(self.archive([('r.json','{}')]))
            with self.assertRaises(ContractError):inspect_archive(p,'0'*64,'r.json')

    def test_archive_traversal_symlink_and_duplicates(self):
        import warnings
        variants=[[('../escape','{}')],[('/absolute','{}')],[('C:x','{}')],[('r.json','{}'),('r.json','{}')]]
        for members in variants:
            with self.subTest(members=members), tempfile.TemporaryDirectory() as td:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore');raw=self.archive(members)
                p=pathlib.Path(td)/'a.zip';p.write_bytes(raw)
                with self.assertRaises(ContractError):inspect_archive(p,hashlib.sha256(raw).hexdigest(),members[0][0])

    def test_archive_symlink_member(self):
        stream=io.BytesIO();info=zipfile.ZipInfo('link');info.external_attr=(stat.S_IFLNK|0o777)<<16
        with zipfile.ZipFile(stream,'w') as z:z.writestr(info,'target')
        raw=stream.getvalue()
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'a.zip';p.write_bytes(raw)
            with self.assertRaises(ContractError):inspect_archive(p,hashlib.sha256(raw).hexdigest(),'link')


class ForecastTests(unittest.TestCase):
    def test_good_forecast(self):validate_forecast(forecast_fixture(),INPUT)

    def test_good_risk(self):validate_risk(forecast_fixture(),INPUT)

    def test_good_envelope(self):validate_envelope(envelope_fixture(),INPUT,SOURCE)

    def test_quantile_precision(self):
        self.assertEqual(quantile_label(.101),'q10.1');self.assertEqual(quantile_label(.104),'q10.4')
        self.assertNotEqual(quantile_label(.1),quantile_label(math.nextafter(.1,1)))

    def test_forecast_hash_tampering(self):
        for field in ('input_sha256','raw_input_sha256','output_sha256'):
            with self.subTest(field=field),self.assertRaises(ContractError):
                x=forecast_fixture();x['receipt'][field]='f'*64;validate_forecast(x,INPUT)

    def test_crossing_and_bool_step_rejected(self):
        x=forecast_fixture();x['points'][0]['quantiles']['q10']=999
        x['receipt']['output_sha256']=digest(x['points'])
        with self.assertRaises(ContractError):validate_forecast(x,INPUT)
        x=forecast_fixture();x['points'][0]['step']=True
        with self.assertRaises(ContractError):validate_forecast(x,INPUT)

    def test_missingness_changes_raw_not_processed(self):
        original=forecast_fixture();req=copy.deepcopy(INPUT);req['values'][2]=11.0
        observed=forecast_fixture(req);validate_forecast(observed,req)
        self.assertEqual(original['receipt']['input_sha256'],observed['receipt']['input_sha256'])
        self.assertNotEqual(original['receipt']['raw_input_sha256'],observed['receipt']['raw_input_sha256'])

    def test_rule_mismatch_rejected(self):
        x=forecast_fixture();x['risk_window']['rule']={**INPUT['risk'],'threshold':15.0}
        with self.assertRaises(ContractError):validate_risk(x,INPUT)

    def test_conservative_risk_reference_hand_cases(self):
        p=[{'step':1,'quantiles':{'q10':10.0,'q50':20.0,'q90':30.0}}]
        above=expected_risk(p,[.1,.5,.9],{'threshold':20.0,'direction':'above','alert_level':.5})
        self.assertEqual(above['steps'][0]['model_implied_breach_lower'],.1)
        self.assertEqual(above['steps'][0]['model_implied_breach_upper'],.5)
        self.assertFalse(above['steps'][0]['median_crosses'])
        below=expected_risk(p,[.1,.5,.9],{'threshold':20.0,'direction':'below','alert_level':.5})
        self.assertEqual(below['steps'][0]['model_implied_breach_lower'],.1)
        self.assertEqual(below['steps'][0]['model_implied_breach_upper'],.5)
        self.assertFalse(below['steps'][0]['median_crosses'])

    def test_union_risk_does_not_assume_independence(self):
        p=[{'step':i,'quantiles':{'q10':10.0,'q50':20.0,'q90':30.0}} for i in (1,2)]
        x=expected_risk(p,[.1,.5,.9],{'threshold':20.0,'direction':'above','alert_level':.5})
        self.assertEqual(x['any_breach_over_horizon']['lower'],.1)
        self.assertEqual(x['any_breach_over_horizon']['upper'],1.0)

    def test_risk_modified_then_rehashed_still_fails_math(self):
        x=forecast_fixture();r=x['risk_window'];r['steps'][0]['model_implied_breach_lower']=.999
        r['report_sha256']=digest({k:v for k,v in r.items() if k!='report_sha256'})
        with self.assertRaises(ContractError):validate_risk(x,INPUT)

    def test_risk_authority_never_escalates(self):
        for key,value in (('production_admitted',True),('execution_authority','ALLOW'),('calibration_status','CALIBRATED')):
            with self.subTest(key=key),self.assertRaises(ContractError):
                x=forecast_fixture();x['risk_window'][key]=value;validate_risk(x,INPUT)

    def test_envelope_byte_digest_rejected(self):
        x=envelope_fixture();x['canonical_json']+=' '
        with self.assertRaises(ContractError):validate_envelope(x,INPUT,SOURCE)

    def test_rehashed_envelope_wrong_source_still_rejected(self):
        x=envelope_fixture();b=json.loads(x['canonical_json']);b['source']['revision']=PUBLISHER
        x['canonical_json']=canonical(b).decode();x['sha256']=hashlib.sha256(x['canonical_json'].encode()).hexdigest()
        with self.assertRaises(ContractError):validate_envelope(x,INPUT,SOURCE)

    def test_envelope_duplicate_json_keys_rejected(self):
        x=envelope_fixture();x['canonical_json']='{"schema":"x","schema":"y"}'
        x['sha256']=hashlib.sha256(x['canonical_json'].encode()).hexdigest()
        with self.assertRaises(ContractError):validate_envelope(x,INPUT,SOURCE)

    def test_complete_fixture_transport(self):
        t=FixtureTransport();r=verify_extended_contract(t.json,t.text,source=SOURCE)
        self.assertTrue(r['http_contract_pass']);self.assertEqual(len(r['checks']),11)
        self.assertFalse(r['browser_verified']);self.assertFalse(r['production_qualified'])

    def test_html_fallback_rejected(self):
        t=FixtureTransport();t.text=lambda p:(200,'<html>generic homepage</html>')
        r=verify_extended_contract(t.json,t.text,source=SOURCE)
        self.assertFalse(r['http_contract_pass']);self.assertFalse(r['checks']['workbench-document'])

    def test_missing_new_routes_fail(self):
        t=FixtureTransport();original=t.json
        t.json=lambda p,**kw:(404,{'detail':'not found'}) if p.endswith('/inspect') else original(p,**kw)
        self.assertFalse(verify_extended_contract(t.json,t.text,source=SOURCE)['http_contract_pass'])

    def test_unrelated_503_is_not_withheld_provider_evidence(self):
        t=FixtureTransport();original=t.json
        def j(path,**kw):
            code,obj=original(path,**kw)
            return (503,{'detail':'load failed'}) if code==503 else (code,obj)
        self.assertFalse(verify_extended_contract(j,t.text,source=SOURCE)['http_contract_pass'])

    def test_final_source_drift_fails(self):
        t=FixtureTransport();original=t.json;count=0
        def j(path,**kw):
            nonlocal count
            code,obj=original(path,**kw)
            if path=='/api/build-info':
                count+=1
                if count==2:obj['runtime_source_revision']=PUBLISHER
            return code,obj
        r=verify_extended_contract(j,t.text,source=SOURCE)
        self.assertFalse(r['http_contract_pass']);self.assertTrue(r['checks']['source-before'])

    def test_public_transport_rejects_unscoped_paths_without_network(self):
        t=PublicTransport()
        for path in ('https://elsewhere','//elsewhere','/path?token=x','/path#x','/\\bad'):
            with self.subTest(path=path),self.assertRaises(ContractError):t.fetch(path)

    def test_expired_transport_does_not_open_network(self):
        t=PublicTransport(seconds=-1)
        with self.assertRaises(ContractError):t.fetch('/api/build-info')

    def test_exceptions_do_not_leak_private_details(self):
        def j(*a,**kw):raise RuntimeError('PRIVATE_VALUE_SHOULD_NOT_APPEAR')
        r=verify_extended_contract(j,FixtureTransport().text,source=SOURCE)
        self.assertFalse(r['http_contract_pass']);self.assertNotIn('PRIVATE_VALUE',json.dumps(r))



class AdmissionAndMarkerTests(unittest.TestCase):
    def native(self):
        from szl_release_guard import SOURCE_JOBS
        run={'id':12,'run_attempt':2,'head_sha':SOURCE,'workflow_id':123,'status':'completed',
             'conclusion':'success','repository':{'full_name':'szl-holdings/lyte-services'}}
        jobs=[{'name':name,'status':'completed','conclusion':'success','run_id':12,
               'run_attempt':2,'head_sha':SOURCE} for name in SOURCE_JOBS]
        return {'source':SOURCE,'repository':'szl-holdings/lyte-services',
                'default_tip':{'object':{'sha':SOURCE}},'workflow_run':run,'jobs':jobs,
                'expected_workflow_id':123}

    def test_exact_source_jobs_admitted(self):
        from szl_release_guard import source_qualification
        self.assertTrue(source_qualification(**self.native())['passed'])

    def test_old_source_rejected(self):
        from szl_release_guard import source_qualification
        x=self.native();x['default_tip']['object']['sha']=HF
        self.assertFalse(source_qualification(**x)['passed'])

    def test_mixed_attempts_and_skipped_jobs_rejected(self):
        from szl_release_guard import source_qualification
        for key,val in (('run_attempt',1),('run_id',13),('head_sha',HF),('conclusion','skipped')):
            x=self.native();x['jobs'][0][key]=val
            with self.subTest(key=key):self.assertFalse(source_qualification(**x)['passed'])

    def test_missing_and_duplicate_source_jobs_rejected(self):
        from szl_release_guard import source_qualification
        x=self.native();x['jobs'].pop()
        self.assertFalse(source_qualification(**x)['passed'])
        x=self.native();x['jobs'].append(x['jobs'][0])
        self.assertFalse(source_qualification(**x)['passed'])

    def test_overall_run_failure_not_hidden_by_source_pass(self):
        from szl_release_guard import source_qualification
        x=self.native();x['workflow_run']['conclusion']='failure'
        r=source_qualification(**x)
        self.assertTrue(r['passed']);self.assertEqual(r['native_run_conclusion'],'failure')
        self.assertIn('NOT_MERGE_OR_LIVE_AUTHORITY',r['scope'])

    def test_manifest_absence_is_recorded(self):
        from szl_release_guard import retain_manifest_metadata
        with tempfile.TemporaryDirectory() as td:
            r=retain_manifest_metadata(pathlib.Path(td)/'absent',pathlib.Path(td)/'out')
            self.assertEqual(r['state'],'ABSENT')
            self.assertTrue((pathlib.Path(td)/'out'/r['metadata_receipt_name']).exists())

    def test_manifest_arbitrary_content_not_published(self):
        from szl_release_guard import retain_manifest_metadata
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'manifest.json'
            p.write_text(json.dumps({'ref':SOURCE,'hf_commit_oid':HF,'files':{
                'secret.file':{'generated_content_utf8':'DO_NOT_DISCLOSE'}},'secret':'OTHER_PRIVATE'}))
            r=retain_manifest_metadata(p,pathlib.Path(td)/'out')
            self.assertEqual(r['state'],'PARSED_METADATA_ONLY')
            self.assertNotIn('PRIVATE',json.dumps(r));self.assertNotIn('DISCLOSE',json.dumps(r))

    def test_malformed_manifest_remains_failure_evidence(self):
        from szl_release_guard import retain_manifest_metadata
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'manifest.json';p.write_text('{')
            self.assertEqual(retain_manifest_metadata(p,pathlib.Path(td)/'out')['state'],'MALFORMED')

    def test_readiness_is_not_one_global_green_flag(self):
        from szl_release_guard import readiness_levels,SAMPLE_RECORDS
        records={key:{'executed':True,'passed':True,'state':'OBSERVED_PASS','source_revision':SOURCE,
                      'publisher_revision':PUBLISHER,'report_sha256':EVIDENCE} for key in SAMPLE_RECORDS}
        r=readiness_levels(records,source=SOURCE,publisher=PUBLISHER)
        self.assertEqual(r['sample'],'LIVE_VERIFIED_SAMPLE');self.assertEqual(r['production'],'HOLD')
        self.assertEqual(r['provider'],'HOLD');self.assertFalse(r['model_enablement_performed'])

    def test_missing_or_forged_release_evidence_is_not_accepted(self):
        from szl_release_guard import readiness_levels,SAMPLE_RECORDS
        records={key:{'executed':True,'passed':True,'state':'OBSERVED_PASS','source_revision':SOURCE,
                      'publisher_revision':PUBLISHER,'report_sha256':EVIDENCE} for key in SAMPLE_RECORDS}
        records['publication']['executed']=False
        self.assertEqual(readiness_levels(records,source=SOURCE,publisher=PUBLISHER)['sample'],'BLOCKED')
        self.assertEqual(readiness_levels({},source=SOURCE,publisher=PUBLISHER)['sample'],'BLOCKED')

    def marker(self):
        from szl_marker_contract import derive_marker,SENTINEL,SENTINEL_BLOB
        return derive_marker(repository='szl-holdings/lyte-services',path='source_revision.txt',
                             original_bytes=SENTINEL,original_blob=SENTINEL_BLOB,
                             admitted_source=SOURCE,docker_copy_includes_marker=True)

    def test_marker_exact_derived_bytes(self):
        from szl_marker_contract import verify_marker
        m=self.marker();self.assertTrue(verify_marker(m,(SOURCE+'\n').encode(),SOURCE))
        self.assertFalse(m['tracked_source_modified']);self.assertEqual(m['size'],41)

    def test_marker_environment_claim_not_image_bytes(self):
        from szl_marker_contract import verify_marker
        self.assertFalse(verify_marker(self.marker(),(HF+'\n').encode(),SOURCE))
        self.assertFalse(verify_marker(self.marker(),b'UNAVAILABLE\n',SOURCE))

    def test_marker_never_overwrites_arbitrary_source(self):
        from szl_marker_contract import derive_marker,SENTINEL,SENTINEL_BLOB
        base={'repository':'szl-holdings/lyte-services','path':'source_revision.txt',
              'original_bytes':SENTINEL,'original_blob':SENTINEL_BLOB,
              'admitted_source':SOURCE,'docker_copy_includes_marker':True}
        for key,val in (('path','lyte/app.py'),('repository','someone/else'),('original_bytes',b'changed\n'),
                        ('original_blob',SOURCE),('docker_copy_includes_marker',False),('admitted_source','main')):
            with self.subTest(key=key),self.assertRaises(ContractError):derive_marker(**{**base,key:val})

    def test_marker_metadata_tamper(self):
        from szl_marker_contract import verify_marker
        m=self.marker();m['sha256']='f'*64
        self.assertFalse(verify_marker(m,(SOURCE+'\n').encode(),SOURCE))


if __name__=='__main__':unittest.main(verbosity=2)
