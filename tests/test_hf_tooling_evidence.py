# SPDX-License-Identifier: Apache-2.0
"""Archive integrity, process metadata and actual HTTP integration regressions."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import hf_tooling_evidence as tooling


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.raw = tooling.BUNDLE_PATH.read_bytes()
        self.bundle = json.loads(self.raw)

    def test_real_archive_verifies(self):
        value = tooling.validate_bundle(self.raw)
        self.assertEqual(len(value['rows']), 4)
        self.assertEqual(value['sourceRevision'], tooling.FORGE_SOURCE)

    def test_changed_bytes_are_rejected(self):
        with self.assertRaises(tooling.EvidenceError):
            tooling.validate_bundle(self.raw + b' ')

    def test_empty_and_oversized_data_rejected(self):
        for raw in (b'', b'x' * (tooling.MAX_BUNDLE_BYTES + 1)):
            with self.subTest(size=len(raw)), self.assertRaises(tooling.EvidenceError):
                tooling.validate_bundle(raw)

    def check_corruption(self, mutate):
        value = copy.deepcopy(self.bundle)
        mutate(value)
        raw = tooling.canonical(value)
        # Even a newly source-pinned outer bundle cannot silently replace the
        # specific archived source/run/receipt contracts pinned in this release.
        with patch.object(tooling, 'BUNDLE_SHA256', hashlib.sha256(raw).hexdigest()):
            with self.assertRaises(tooling.EvidenceError):
                tooling.validate_bundle(raw)

    def test_wrong_source(self):
        self.check_corruption(lambda b: b.update(sourceRevision='a' * 40))

    def test_wrong_workflow(self):
        self.check_corruption(lambda b: b.update(workflowRun=1))

    def test_missing_lane(self):
        self.check_corruption(lambda b: b['rows'].pop())

    def test_duplicate_lane(self):
        self.check_corruption(lambda b: b['rows'].__setitem__(1, b['rows'][0]))

    def test_false_signature_claim(self):
        self.check_corruption(lambda b: b.update(signatureState='SIGNED'))

    def test_wrong_platform(self):
        self.check_corruption(lambda b: b['rows'][0]['report']['environment'].update(platform='Windows'))

    def test_changed_metrics(self):
        self.check_corruption(lambda b: b['rows'][2]['report']['checks']['chunked_nll_loss_gradient_parity']['evidence'].update(cases=800))

    def test_rehashed_metrics_not_trusted(self):
        def mutate(b):
            r = b['rows'][2]['report']
            r['checks']['chunked_nll_loss_gradient_parity']['evidence']['cases'] = 800
            r['reportSha256'] = hashlib.sha256(tooling.canonical({k: v for k, v in r.items() if k != 'reportSha256'})).hexdigest()
        self.check_corruption(mutate)

    def test_authority_escalation(self):
        self.check_corruption(lambda b: b['rows'][0]['report']['authority'].update(jobCreation=True))

    def test_duplicate_json_keys(self):
        raw = b'{"schema":1,"schema":2}'
        with patch.object(tooling, 'BUNDLE_SHA256', hashlib.sha256(raw).hexdigest()):
            with self.assertRaises(tooling.EvidenceError):
                tooling.validate_bundle(raw)

    def test_nonfinite_json(self):
        raw = b'{"value":NaN}'
        with patch.object(tooling, 'BUNDLE_SHA256', hashlib.sha256(raw).hexdigest()):
            with self.assertRaises(tooling.EvidenceError):
                tooling.validate_bundle(raw)

    def test_missing_archive(self):
        with patch.object(tooling, 'BUNDLE_PATH', Path('/nonexistent/szl-evidence.json')):
            with self.assertRaises(tooling.EvidenceError):
                tooling.load_bundle()


class RuntimeTests(unittest.TestCase):
    def test_version_match_never_claims_exact_source(self):
        with patch.object(tooling.metadata, 'version', side_effect=lambda n: tooling.PACKAGES[n]):
            rows = tooling.installed_packages()
        self.assertTrue(all(r['state'] == 'VERSION_MATCH_ONLY' for r in rows))
        self.assertTrue(all(r['exactInstalledSourceVerified'] is False for r in rows))

    def test_missing_metadata_never_claims_installation(self):
        with patch.object(tooling.metadata, 'version', side_effect=tooling.metadata.PackageNotFoundError):
            rows = tooling.installed_packages()
        self.assertTrue(all(r['state'] == 'NOT_INSTALLED' and r['installedVersion'] is None for r in rows))

    def test_different_version_visible(self):
        with patch.object(tooling.metadata, 'version', return_value='1.29.0'):
            self.assertEqual(tooling.installed_packages()[0]['state'], 'VERSION_DIFFERS')

    def test_runtime_source_is_not_archive_source(self):
        with patch.dict(os.environ, {'A11OY_GIT_SHA': 'a' * 40, 'SZL_GIT_SHA': ''}):
            data = tooling.project(tooling.load_bundle())
        self.assertEqual(data['sourceRevision'], tooling.FORGE_SOURCE)
        self.assertEqual(data['runtime']['productSourceRevision'], 'a' * 40)
        self.assertEqual(data['productionDisposition'], 'HOLD')

    def test_canonical_publisher_source_variable_is_observed(self):
        with patch.dict(os.environ, {'SZL_GIT_SHA': 'b' * 40, 'A11OY_GIT_SHA': ''}):
            self.assertEqual(tooling.runtime_source(), ('b' * 40, 'REPORTED'))

    def test_conflicting_runtime_source_aliases_not_silently_selected(self):
        with patch.dict(os.environ, {'SZL_GIT_SHA': 'b' * 40, 'A11OY_GIT_SHA': 'a' * 40}):
            self.assertEqual(tooling.runtime_source(), (None, 'CONFLICT'))

    def test_matching_source_aliases_are_reported_not_attested(self):
        with patch.dict(os.environ, {'SZL_GIT_SHA': 'b' * 40, 'A11OY_GIT_SHA': 'b' * 40}):
            self.assertEqual(tooling.runtime_source(), ('b' * 40, 'REPORTED'))

    def test_invalid_runtime_source_not_invented(self):
        with patch.dict(os.environ, {'A11OY_GIT_SHA': 'main', 'SZL_GIT_SHA': ''}):
            self.assertIsNone(tooling.project(tooling.load_bundle())['runtime']['productSourceRevision'])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        tooling.register(self.app)
        @self.app.get('/{path:path}')
        def fallback(path: str):
            return {'spaFallback': True}
        self.client = TestClient(self.app)

    def test_live_python_endpoint_not_spa_fallback(self):
        response = self.client.get('/api/a11oy/v1/frontier-tooling')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['schema'], tooling.SCHEMA)
        self.assertEqual(len(response.json()['lanes']), 4)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_head_has_no_body(self):
        for path in ('/frontier-tooling', '/api/a11oy/v1/frontier-tooling', '/api/a11oy/v1/frontier-tooling/receipts/trl'):
            with self.subTest(path=path):
                r = self.client.head(path)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.content, b'')

    def test_no_write_methods(self):
        for method in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)('/api/a11oy/v1/frontier-tooling').status_code, 405)

    def test_receipt_is_original_unchanged_body(self):
        r = self.client.get('/api/a11oy/v1/frontier-tooling/receipts/trl')
        expected = next(row['report'] for row in tooling.load_bundle()['rows'] if row['id'] == 'trl')
        self.assertEqual(r.json(), expected)

    def test_unknown_receipt_is_404(self):
        self.assertEqual(self.client.get('/api/a11oy/v1/frontier-tooling/receipts/unknown').status_code, 404)

    def test_missing_evidence_503_empty_not_green(self):
        with patch.object(tooling, 'BUNDLE_PATH', Path('/nonexistent/szl-evidence.json')):
            r = self.client.get('/api/a11oy/v1/frontier-tooling')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['lanes'], [])
        self.assertFalse(r.json()['available'])

    def test_archive_tamper_after_first_request_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bundle.json'
            path.write_bytes(tooling.BUNDLE_PATH.read_bytes())
            with patch.object(tooling, 'BUNDLE_PATH', path):
                self.assertEqual(self.client.get('/api/a11oy/v1/frontier-tooling').status_code, 200)
                path.write_bytes(b'{}')
                self.assertEqual(self.client.get('/api/a11oy/v1/frontier-tooling').status_code, 503)

    def test_page_assets_real_and_csp_no_inline(self):
        r = self.client.get('/frontier-tooling')
        self.assertIn('Tooling observatory', r.text)
        self.assertIn('<link rel="stylesheet" href="/assets/szl-flow.css" data-szl-flow-asset="style" />', r.text)
        self.assertIn('<script src="/assets/szl-flow.js" defer data-szl-flow-asset="script"></script>', r.text)
        self.assertNotIn("unsafe-inline", r.headers['content-security-policy'])
        self.assertIn("script-src 'self'", r.headers['content-security-policy'])
        for path in ('/frontier-tooling/assets/view.js', '/frontier-tooling/assets/view.css'):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_registration_is_idempotent(self):
        count = len(self.app.routes)
        tooling.register(self.app)
        self.assertEqual(len(self.app.routes), count)

    def test_foreign_route_collision_is_rejected_without_partial_registration(self):
        app = FastAPI()
        @app.get('/frontier-tooling')
        def other_view():
            return {'different': True}
        before = len(app.routes)
        with self.assertRaises(RuntimeError):
            tooling.register(app)
        self.assertEqual(len(app.routes), before)

    def test_partial_registration_is_not_mistaken_for_success(self):
        self.app.router.routes[:] = [r for r in self.app.routes
            if getattr(r, 'path', None) != '/frontier-tooling/assets/view.js']
        with self.assertRaises(RuntimeError):
            tooling.register(self.app)

    def test_wrong_namespace_refused(self):
        with self.assertRaises(ValueError):
            tooling.register(FastAPI(), ns='other-product')


class RegistrationSeamTests(unittest.TestCase):
    def test_existing_product_seam_invokes_real_tooling_router(self):
        import sys
        import types
        import routers
        from routers import frontier_reads
        app = FastAPI()
        inert = types.SimpleNamespace(register=lambda *a, **k: {"ok": True})
        serve = types.SimpleNamespace(_A11OY_FORECAST={}, _A11OY_CAPS=[],
                                      _a11oy_build_chain=lambda n: {"depth": n})
        with patch.dict(sys.modules, {"serve": serve}), \
             patch.object(routers, 'series_a_control_plane', inert, create=True), \
             patch.object(routers, 'frontier_now_control_plane', inert, create=True), \
             patch.object(routers, 'atelier_frontier', inert, create=True):
            registry = frontier_reads.register(app)
        self.assertEqual(registry['hf_tooling']['state'], 'READ_ONLY')
        self.assertIn('/frontier-tooling', registry['routes'])
        @app.get('/{path:path}')
        def spa(path: str):
            return {'fallback': True}
        client = TestClient(app)
        self.assertEqual(client.get('/api/a11oy/v1/frontier-tooling').json()['schema'], tooling.SCHEMA)
        self.assertIn('Tooling observatory', client.get('/frontier-tooling').text)
        self.assertEqual(client.get('/api/a11oy/v1/vertical-packs').json()['total'], 13)


if __name__ == '__main__':
    unittest.main()
