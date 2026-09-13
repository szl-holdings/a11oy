# SPDX-License-Identifier: Apache-2.0
"""Existing snapshot -> actual read-only route tests, without weight/Hub execution."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import hf_tooling_evidence as tooling
from routers import model_pretraining as view

NOW = datetime(2026, 9, 13, tzinfo=timezone.utc)


def sample():
    return {"schemaVersion": 2, "org": "SZLHOLDINGS", "observedAt": "2026-09-10T03:20:41Z",
            "inventoryScope": {"visibility": "public-only", "authenticated": False,
                               "privateAssetsIncluded": False},
            "counts": {"models": 1}, "inventory": {"models": [{
                "id": "SZLHOLDINGS/sample", "repoType": "model", "private": False,
                "sha": "a" * 40, "lastModified": "2026-09-09T12:00:00Z",
                "tags": ["peft", "safetensors"], "gated": False, "disabled": False,
                "license": "apache-2.0"}]}}


class ManifestTests(unittest.TestCase):
    def test_source_packaged_manifest_has_self_consistent_models_not_fixed_46(self):
        # Count is derived from the existing source, not frozen into another roster.
        raw = view.SOURCE_MANIFEST.read_bytes()
        original = json.loads(raw)
        result = view.project(raw, [], now=NOW)
        self.assertEqual(result['returned'], original['counts']['models'])
        self.assertEqual(len(result['models']), original['counts']['models'])
        self.assertEqual(result['manifestSha256'], hashlib.sha256(raw).hexdigest())
        self.assertFalse(result['wholeOrganizationInventoryVerified'])
        self.assertFalse(result['sourceAlignmentVerified'])
        self.assertFalse(result['trainingAllowed'])

    def invalid(self, mutate):
        source = sample()
        mutate(source)
        with self.assertRaises(view.CatalogError):
            view.parse_manifest(json.dumps(source).encode())

    def test_wrong_count_rejected(self):
        self.invalid(lambda s: s['counts'].update(models=2))

    def test_boolean_count_is_not_one(self):
        self.invalid(lambda s: s['counts'].update(models=True))

    def test_duplicate_ids_rejected(self):
        def change(s):
            s['inventory']['models'].append(copy.deepcopy(s['inventory']['models'][0]))
            s['counts']['models'] = 2
        self.invalid(change)

    def test_wrong_namespace_rejected(self):
        self.invalid(lambda s: s['inventory']['models'][0].update(id='other/model'))

    def test_wrong_type_rejected(self):
        self.invalid(lambda s: s['inventory']['models'][0].update(repoType='kernel'))

    def test_private_row_rejected(self):
        self.invalid(lambda s: s['inventory']['models'][0].update(private=True))

    def test_private_inventory_rejected(self):
        self.invalid(lambda s: s['inventoryScope'].update(privateAssetsIncluded=True))

    def test_authenticated_scope_not_mixed_with_public(self):
        self.invalid(lambda s: s['inventoryScope'].update(authenticated=True))

    def test_mutable_revision_rejected(self):
        self.invalid(lambda s: s['inventory']['models'][0].update(sha='main'))

    def test_missing_dates_rejected(self):
        self.invalid(lambda s: s.pop('observedAt'))

    def test_naive_date_rejected(self):
        self.invalid(lambda s: s.update(observedAt='2026-09-10T01:00:00'))

    def test_invalid_tags_rejected(self):
        self.invalid(lambda s: s['inventory']['models'][0].update(tags=None))

    def test_invalid_gate_rejected(self):
        self.invalid(lambda s: s['inventory']['models'][0].update(gated=1))

    def test_empty_snapshot_can_be_observed_without_qualification(self):
        value = sample(); value['inventory']['models'] = []; value['counts']['models'] = 0
        result = view.project(view.canonical(value), [], now=NOW)
        self.assertEqual(result['returned'], 0)
        self.assertFalse(result['sourceAlignmentVerified'])
        self.assertFalse(result['trainingAllowed'])

    def test_invalid_json_and_duplicate_keys(self):
        for raw in (b'{', b'[]', b'{"org": "a", "org": "b"}', b'NaN', b'Infinity'):
            with self.subTest(raw=raw), self.assertRaises(view.CatalogError):
                view.parse_manifest(raw)

    def test_exponent_overflow_is_nonfinite_not_valid_metadata(self):
        raw = view.canonical(sample()).replace(b'"schemaVersion":2', b'"unused":1e999,"schemaVersion":2')
        with self.assertRaises(view.CatalogError):
            view.parse_manifest(raw)

    def test_oversized_input_rejected(self):
        with self.assertRaises(view.CatalogError):
            view.parse_manifest(b' ' * (view.MAX_BYTES + 1))


class ProjectionTests(unittest.TestCase):
    def test_build_projection_matches_existing_source_exactly(self):
        raw = view.SOURCE_MANIFEST.read_bytes()
        self.assertEqual(view.MANIFEST.read_bytes(), view.build_projection(raw))
        snapshot, digest = view.decode_projection(view.MANIFEST.read_bytes())
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(view.parse_manifest(snapshot)['inventory']['models']),
                         len(view.parse_manifest(raw)['inventory']['models']))

    def test_build_projection_copies_no_dataset_or_space_rows(self):
        value = json.loads(view.build_projection(view.SOURCE_MANIFEST.read_bytes()))
        self.assertEqual(set(value['snapshot']['inventory']), {'models'})
        self.assertEqual(set(value['snapshot']['counts']), {'models'})

    def test_malformed_projection_and_extra_keys_rejected(self):
        value = json.loads(view.build_projection(view.canonical(sample())))
        for update in ({'sourceManifestSha256':'bad'}, {'schema':'other'},
                       {'unexpected':True}, {'sourceManifestPath':'/private/file'}):
            with self.subTest(update=update), self.assertRaises(view.CatalogError):
                view.decode_projection(view.canonical({**value, **update}))

    def test_old_date_is_not_refreshed_to_now(self):
        result = view.project(view.canonical(sample()), [], now=NOW)
        self.assertEqual(result['observedAt'], sample()['observedAt'])
        self.assertEqual(result['snapshotFreshness'], 'STALE_SNAPSHOT')

    def test_future_date_reports_clock_skew(self):
        result = view.project(view.canonical(sample()), [], now=datetime(2026, 9, 1, tzinfo=timezone.utc))
        self.assertEqual(result['snapshotFreshness'], 'CLOCK_SKEW')

    def test_recent_snapshot_still_not_live(self):
        now = view.timestamp(sample()['observedAt'])
        result = view.project(view.canonical(sample()), [], now=now)
        self.assertEqual(result['snapshotFreshness'], 'SNAPSHOT_NOT_LIVE')

    def test_declared_source_does_not_grant_byte_or_training_authority(self):
        card = {'hub_kind': 'model', 'hub_id': 'SZLHOLDINGS/sample',
                'github': 'https://github.com/szl-holdings/szl-forge/tree/main/receiptagent'}
        result = view.project(view.canonical(sample()), [card], now=NOW)
        row = result['models'][0]
        self.assertEqual(row['sourceState'], 'DECLARED_POINTER_ONLY')
        self.assertEqual(result['sourcePointersDeclared'], 1)
        self.assertTrue(all(row[k] is False for k in ('sourceBytesVerified', 'weightsVerified',
                        'evaluationVerified', 'runtimeVerified', 'trainingAllowed')))

    def test_no_name_based_source_invention(self):
        row = view.project(view.canonical(sample()), [], now=NOW)['models'][0]
        self.assertIsNone(row['sourceUrl'])
        self.assertEqual(row['sourceState'], 'NOT_RESOLVED_BY_THIS_CATALOG')

    def test_duplicate_source_pointers_are_ambiguous(self):
        card = {'hub_kind': 'model', 'hub_id': 'SZLHOLDINGS/sample',
                'github': 'https://github.com/szl-holdings/szl-forge'}
        row = view.project(view.canonical(sample()), [card, card], now=NOW)['models'][0]
        self.assertEqual(row['sourceState'], 'AMBIGUOUS')
        self.assertIsNone(row['sourceUrl'])

    def test_space_pointer_cannot_supply_model_source(self):
        card = {'hub_kind': 'space', 'hub_id': 'SZLHOLDINGS/sample',
                'github': 'https://github.com/szl-holdings/szl-forge'}
        result = view.project(view.canonical(sample()), [card], now=NOW)
        self.assertEqual(result['sourcePointersDeclared'], 0)

    def test_malicious_source_urls_not_returned(self):
        for url in ['http://github.com/szl-holdings/a11oy', 'https://github.com.evil/szl-holdings/a',
                    'https://user@github.com/szl-holdings/a', 'https://github.com/other/repo',
                    'javascript:alert(1)', 'https://github.com/szl-holdings/a/../b',
                    'https://github.com/szl-holdings/a?token=bad', 'https://github.com/szl-holdings/a#x',
                    'https://github.com/szl-holdings/a/%2e%2e/b', '\nhttps://github.com/szl-holdings/a']:
            with self.subTest(url=url):
                self.assertIsNone(view.safe_source(url))

    def test_hints_do_not_promote_metadata_into_weights(self):
        for tags, expected in [(['gguf'], 'GGUF_HINT'), (['peft'], 'ADAPTER_HINT'),
            (['transformers', 'safetensors'], 'CHECKPOINT_HINT'),
            (['logistic-regression'], 'CLASSICAL_MODEL_HINT'), (['no-weights', 'gguf'], 'RECIPE_OR_PLACEHOLDER_HINT'),
            (['test-fixture', 'safetensors'], 'KERNEL_OR_SOFTWARE_HINT'), ([], 'UNCLASSIFIED')]:
            self.assertEqual(view.category(tags), expected)

    def test_exact_product_revision_only_reported(self):
        result = view.project(view.canonical(sample()), [], now=NOW, product_revision='a' * 40)
        self.assertEqual(result['productSourceRevisionReported'], 'a' * 40)
        self.assertFalse(result['productSourceIndependentlyAttested'])
        self.assertIsNone(view.project(view.canonical(sample()), [], now=NOW, product_revision='main')['productSourceRevisionReported'])

    def test_static_catalog_import_does_not_call_network_functions(self):
        module = types.SimpleNamespace(SERIES_A_CARDS=({'hub_id':'SZLHOLDINGS/sample'},))
        with patch.dict('sys.modules', {'a11oy_model_intel': module}):
            cards, state = view.declared_source_cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(state, 'EXISTING_SERIES_A_CATALOG_SUBSET')


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        tooling.register(self.app)  # Actual existing parent invocation, not direct new registration.
        @self.app.get('/{rest:path}')
        def fallback(rest: str):
            return {'fallback': True}
        self.client = TestClient(self.app)
        self.api = '/api/a11oy/v1/models/pretraining'

    def test_actual_parent_exposes_new_route_before_fallback(self):
        with patch.object(view, 'declared_source_cards', return_value=([], 'UNAVAILABLE')):
            response = self.client.get(self.api)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['schema'], view.SCHEMA)
        self.assertEqual(response.json()['sourcePointerCatalogState'], 'UNAVAILABLE')

    def test_model_api_headers_and_head(self):
        with patch.object(view, 'declared_source_cards', return_value=([], 'UNAVAILABLE')):
            get = self.client.get(self.api); head = self.client.head(self.api)
        self.assertEqual(get.headers['cache-control'], 'no-store')
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertGreater(int(head.headers['content-length']), 0)

    def test_old_archive_route_stays_unchanged(self):
        response = self.client.get('/api/a11oy/v1/frontier-tooling')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['lanes']), 4)
        self.assertEqual(response.json()['archiveSha256'], tooling.BUNDLE_SHA256)

    def test_all_write_methods_denied(self):
        for method in ('post','put','patch','delete'):
            for path in (self.api, '/frontier-tooling/models'):
                with self.subTest(method=method, path=path):
                    self.assertEqual(getattr(self.client, method)(path).status_code, 405)

    def test_missing_snapshot_is_503_not_empty_success(self):
        with patch.object(view, 'MANIFEST', Path('/nonexistent/hidden-private-path')):
            response = self.client.get(self.api)
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(response.json()['returned'])
        self.assertNotIn('hidden-private-path', response.text)
        self.assertEqual(response.json()['models'], [])

    def test_removed_or_corrupt_snapshot_does_not_reuse_last_success(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'inventory.json'; p.write_bytes(view.build_projection(view.canonical(sample())))
            with patch.object(view, 'MANIFEST', p):
                self.assertEqual(self.client.get(self.api).status_code, 200)
                p.write_bytes(b'{}')
                self.assertEqual(self.client.get(self.api).status_code, 503)

    def test_fixed_files_and_secure_headers(self):
        paths = ('/frontier-tooling/models', '/frontier-tooling/models/',
                 '/frontier-tooling/models/assets/view.js', '/frontier-tooling/models/assets/view.css')
        for path in paths:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.client.head(path).content, b'')
            self.assertEqual(r.headers['x-content-type-options'], 'nosniff')
        page = self.client.get(paths[0])
        self.assertNotIn('unsafe-inline', page.headers['content-security-policy'])
        self.assertIn('Source before training', page.text)
        self.assertIn('href="/frontier-tooling/models"', self.client.get('/frontier-tooling').text)

    def test_repeated_parent_registration_is_idempotent(self):
        before = len(self.app.routes)
        tooling.register(self.app)
        self.assertEqual(len(self.app.routes), before)

    def test_partial_subview_fails_rather_than_report_success(self):
        self.app.router.routes[:] = [r for r in self.app.routes if getattr(r,'path',None) != self.api]
        with self.assertRaises(RuntimeError):
            tooling.register(self.app)

    def test_foreign_subview_collision_adds_no_parent_routes(self):
        app = FastAPI()
        @app.get(self.api)
        def other():
            return {}
        before = len(app.routes)
        with self.assertRaises(RuntimeError):
            tooling.register(app)
        self.assertEqual(before, len(app.routes))


if __name__ == '__main__':
    unittest.main()
