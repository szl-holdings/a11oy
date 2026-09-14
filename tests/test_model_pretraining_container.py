# SPDX-License-Identifier: Apache-2.0
"""Offline controls for the full-image smoke; fixtures are not a running image."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import test_model_pretraining_live as base

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('container_probe', ROOT/'scripts/test_model_pretraining_container.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
IMAGE = 'sha256:' + 'b'*64
POLICY = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
          "base-uri 'none'; form-action 'none'; object-src 'none'")


class ProbeTests(unittest.TestCase):
    def run_probe(self, change=None, modify_source=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = base.SequenceTests().setup_source(root)
            if modify_source:
                modify_source(root)
            def fetch(path, method):
                status, media, body = original(path, method)
                value = (status, {'content-type': media, 'x-content-type-options':'nosniff',
                                 'cache-control':'no-store', 'content-security-policy':POLICY}, body)
                return change(path, method, value) if change else value
            return M.collect(root, base.SHA, IMAGE, fetch=fetch)

    def test_all_positive_checks_have_local_only_scope(self):
        report = self.run_probe()
        self.assertEqual(report['state'], 'PASS_LOCAL_CONTAINER_FEATURE_CONTRACT')
        self.assertEqual(len(report['checks']), 18)
        self.assertEqual(len(report['observations']), 18)
        self.assertEqual(report['scope'], 'LOCAL_FULL_CONTAINER_INTEGRATION')
        self.assertEqual(report['origin'], 'http://127.0.0.1:7860')
        for key in ('productionDeploymentVerified','wholeEstateAligned','browserRenderingVerified',
                    'probeModelInferenceRequested','trainingStarted','probeProviderMutationRequested'):
            self.assertIs(report[key], False)
        self.assertEqual(report['failedChecks'], [])

    def test_transformed_html_is_diagnosed_not_silently_allowed(self):
        path = '/frontier-tooling/models'
        def change(p, method, value):
            return (200, value[1], value[2]+b'<script>injected()</script>') if p == path and method == 'GET' else value
        report = self.run_probe(change)
        self.assertEqual(report['failedChecks'], ['GET exact source '+path])
        row = next(r for r in report['observations'] if r['path']==path and r['method']=='GET')
        self.assertNotEqual(row['sha256'], row['expectedSha256'])
        self.assertEqual(report['checks'][-1], {'name':'source after', 'state':'PASS'})
        self.assertNotIn('injected()', json.dumps(report))

    def test_http_failure_preserves_other_observations_and_final_source(self):
        def change(p, method, value):
            return (503, {'content-type':'text/html'}, b'internal text not evidence') if p==M.V.API and method=='GET' else value
        report = self.run_probe(change)
        self.assertIn('model API and source declarations', report['failedChecks'])
        self.assertEqual(len(report['observations']), 18)
        self.assertEqual(report['checks'][-1]['state'], 'PASS')
        self.assertNotIn('internal text', json.dumps(report))
        self.assertTrue(any(r.get('status')==503 for r in report['observations']))

    def test_spa_html_200_cannot_satisfy_json(self):
        report = self.run_probe(lambda p,m,v: (200,{'content-type':'text/html'},b'{}') if p==M.V.API else v)
        self.assertIn('model API and source declarations', report['failedChecks'])

    def test_css_html_fallback_fails(self):
        report = self.run_probe(lambda p,m,v: (200,{'content-type':'text/html'},v[2]) if p=='/assets/szl-flow.css' else v)
        self.assertIn('GET exact source /assets/szl-flow.css', report['failedChecks'])

    def test_head_body_fails(self):
        report = self.run_probe(lambda p,m,v: (v[0],v[1],b'unexpected') if m=='HEAD' else v)
        self.assertEqual(len(report['failedChecks']), 8)

    def test_bool_status_is_not_200(self):
        report = self.run_probe(lambda p,m,v: (True,v[1],v[2]))
        self.assertEqual(len(report['failedChecks']), 18)
        self.assertEqual(report['observations'][0]['state'], 'UNAVAILABLE')

    def test_text_body_is_not_bytes(self):
        report = self.run_probe(lambda p,m,v: (v[0],v[1],v[2].decode()))
        self.assertEqual(len(report['failedChecks']), 18)

    def test_missing_header_fails(self):
        report = self.run_probe(lambda p,m,v: (v[0],{},v[2]))
        self.assertEqual(len(report['failedChecks']), 18)

    def test_transport_exception_not_persisted_and_never_success(self):
        def fail(*args):
            raise OSError('secret-like arbitrary transport detail')
        report = self.run_probe(fail)
        self.assertEqual(len(report['failedChecks']), 18)
        self.assertNotIn('secret-like', json.dumps(report))
        self.assertEqual(report['state'], 'FAIL_CONTAINER_FEATURE_CONTRACT')

    def test_after_source_drift_is_not_lost(self):
        count = 0
        def change(p,m,v):
            nonlocal count
            if p == '/api/build-info':
                count += 1
                if count == 2:
                    return v[0],v[1],v[2].replace(base.SHA.encode(), ('f'*40).encode())
            return v
        self.assertEqual(self.run_probe(change)['failedChecks'], ['source after'])

    def test_same_org_wrong_pointer_does_not_pass_container_contract(self):
        def change(p,m,v):
            if p==M.V.API and m=='GET':
                data=json.loads(v[2]);data['models'][0]['sourceUrl']='https://github.com/szl-holdings/wrong'
                return v[0],v[1],base.raw(data)
            return v
        self.assertIn('model API and source declarations', self.run_probe(change)['failedChecks'])

    def test_missing_source_file_preserves_failed_path_and_other_results(self):
        report=self.run_probe(modify_source=lambda r:(r/'pages/model-pretraining.js').unlink())
        self.assertIn('GET exact source /frontier-tooling/models/assets/view.js',report['failedChecks'])
        self.assertEqual(report['checks'][-1]['state'],'PASS')

    def test_changed_source_contract_is_not_repaired_by_prober(self):
        report=self.run_probe(modify_source=lambda r:(r/'a11oy_model_intel.py').write_text('unknown grammar'))
        self.assertIn('model API and source declarations',report['failedChecks'])
        self.assertNotIn('catalog',report)

    def test_no_raw_bodies_or_credentials_are_saved(self):
        report=self.run_probe()
        for row in report['observations']:
            self.assertNotIn('body',row)
            self.assertNotIn('headers',row)
            self.assertNotIn('cookie',row)
        self.assertNotIn('reviewed source',json.dumps(report))

    def test_bad_source_stops_before_fetch(self):
        with patch.object(M,'make_fetch',side_effect=AssertionError('not allowed')) as fetch:
            with self.assertRaises(M.V.VerificationError): M.collect(Path('/none'),'main',IMAGE)
            fetch.assert_not_called()

    def test_bad_image_identity_stops_before_fetch(self):
        with patch.object(M,'make_fetch',side_effect=AssertionError('not allowed')) as fetch:
            with self.assertRaises(M.V.VerificationError): M.collect(Path('/none'),base.SHA,'tag:latest')
            fetch.assert_not_called()

    def test_page_csp_weakening_fails(self):
        def change(p,m,v):
            return v[0],{**v[1], 'content-security-policy': POLICY.replace("script-src 'self'", "script-src * 'unsafe-inline'")},v[2]
        report=self.run_probe(change)
        self.assertIn('GET exact source /frontier-tooling/models',report['failedChecks'])

    def test_duplicate_page_csp_directives_fail(self):
        def change(p,m,v):
            return v[0],{**v[1], 'content-security-policy': POLICY+"; script-src *"},v[2]
        self.assertIn('GET exact source /frontier-tooling/models',self.run_probe(change)['failedChecks'])

    def test_model_api_cache_header_preserved(self):
        report=self.run_probe(lambda p,m,v:(v[0],{**v[1], 'cache-control':'public'},v[2]))
        self.assertIn('model API and source declarations',report['failedChecks'])

    def test_nosniff_header_preserved(self):
        report=self.run_probe(lambda p,m,v:(v[0],{**v[1], 'x-content-type-options':''},v[2]))
        self.assertIn('model API and source declarations',report['failedChecks'])

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root=Path(directory); target=Path(other)/'data'; target.write_text('external')
            (root/'linked').symlink_to(target)
            with self.assertRaises(M.V.VerificationError): M.source_bytes(root,'linked')


class TransportTests(unittest.TestCase):
    def test_only_fixed_paths_and_read_methods(self):
        opener=SimpleNamespace(open=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network not allowed')))
        with patch.object(M.request,'build_opener',return_value=opener):
            fetch=M.make_fetch()
            for p,m in [('https://example.com','GET'),('/api/build-info','POST'),('/other','GET')]:
                with self.subTest(path=p,method=m),self.assertRaises(M.V.VerificationError):fetch(p,m)

    def test_deadline_expires_before_open(self):
        with patch.object(M.request,'build_opener') as opener:
            fetch=M.make_fetch(seconds=-1)
            with self.assertRaises(M.V.VerificationError):fetch('/api/build-info','GET')
            opener.return_value.open.assert_not_called()

    def test_proxy_inheritance_is_disabled(self):
        with patch.object(M.request,'ProxyHandler') as proxy,patch.object(M.request,'build_opener'):
            M.make_fetch();proxy.assert_called_once_with({})

    def test_http_error_is_retained_with_real_status(self):
        e=HTTPError(M.ORIGIN+'/api/build-info',503,'unavailable',{'Content-Type':'application/json'},io.BytesIO(b'{}'))
        with patch.object(M.request,'build_opener') as opener:
            opener.return_value.open.side_effect=e
            status,headers,body=M.make_fetch()('/api/build-info','GET')
            self.assertEqual((status,headers['content-type'],body),(503,'application/json',b'{}'))

    def test_redirect_refusal_remains_active(self):
        with self.assertRaises(M.V.VerificationError): M.V.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')


class CommandTests(unittest.TestCase):
    def test_checkout_mismatch_writes_unavailable_and_does_not_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'report.json'
            argv=['probe','--expected-source',base.SHA,'--image-id',IMAGE,'--output',str(out)]
            with patch('sys.argv',argv),patch.object(M.subprocess,'run',return_value=SimpleNamespace(stdout='c'*40)),\
                 patch.object(M,'collect',side_effect=AssertionError('network not admitted')) as collect:
                self.assertEqual(M.main(),1);collect.assert_not_called()
            self.assertEqual(json.loads(out.read_text())['state'],'UNAVAILABLE')

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'report.json';out.write_text('original')
            argv=['probe','--expected-source',base.SHA,'--image-id',IMAGE,'--output',str(out)]
            with patch('sys.argv',argv),patch.object(M.subprocess,'run',side_effect=subprocess.TimeoutExpired('git',10)):
                with self.assertRaises(FileExistsError):M.main()
            self.assertEqual(out.read_text(),'original')


class WorkflowTests(unittest.TestCase):
    def test_container_smoke_invokes_existing_contract_before_cleanup(self):
        text=(ROOT/'.github/workflows/docker-build.yml').read_text()
        block=text.split('      - name: Smoke test image',1)[1].split('      - name:',1)[0]
        self.assertIn("if: github.event_name == 'pull_request'",block)
        self.assertIn('timeout-minutes: 12',block)
        self.assertIn('scripts/test_model_pretraining_container.py',block)
        self.assertLess(block.index('trap cleanup EXIT'),block.index('scripts/test_model_pretraining_container.py'))
        self.assertNotIn('secrets.',block)
        self.assertIn('127.0.0.1:7860:7860',block)

    def test_image_label_is_checked_before_container_launch(self):
        text=(ROOT/'.github/workflows/docker-build.yml').read_text()
        self.assertLess(text.index('test "${IMAGE_REVISION}" = "${GITHUB_SHA}"'),text.index('CID="$(docker run'))
        self.assertIn('--image-id "${IMAGE_ID}"',text)
        self.assertIn('SZL_GIT_SHA="${GITHUB_SHA}"',text)

    def test_reports_retained_on_failed_pr_smoke(self):
        text=(ROOT/'.github/workflows/docker-build.yml').read_text()
        block=text.split('      - name: Retain full-image',1)[1].split('      # FIX',1)[0]
        self.assertIn("if: always() && github.event_name == 'pull_request'",block)
        self.assertIn('artifacts/model-pretraining-container/',block)


if __name__ == '__main__':
    unittest.main()
