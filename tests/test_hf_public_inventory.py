# SPDX-License-Identifier: Apache-2.0
"""Deterministic membership tests: fixtures are not live inventory evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_inventory', ROOT / 'scripts/hf_public_inventory.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def row(name='one', **kw):
    return {'id': 'SZLHOLDINGS/' + name, 'private': False, **kw}


def get_empty(url):
    return {'status': 200, 'json': [], 'link': None}


def fixture(rows=None):
    rows = [row()] if rows is None else rows
    inventory = m.collect('SZLHOLDINGS', lambda u: {'status': 200, 'json': copy.deepcopy(rows)})
    manifest = {'org': 'SZLHOLDINGS', 'counts': dict(inventory['counts']),
                'inventoryScope': {'visibility': 'public-only', 'authenticated': False, 'privateAssetsIncluded': False},
                'inventory': {k: copy.deepcopy(rows) for k in m.KINDS}}
    return inventory, manifest, dict(inventory['counts'])


class PublicInventoryTests(unittest.TestCase):
    def test_empty_list_is_observed_zero(self):
        result = m.collect('SZLHOLDINGS', get_empty)
        self.assertTrue(result['observed'])
        self.assertEqual(result['counts'], dict.fromkeys(m.KINDS, 0))

    def test_object_200_is_unknown_not_zero(self):
        result = m.collect('SZLHOLDINGS', lambda u: {'status': 200, 'json': {'error': 'oops'}})
        self.assertFalse(result['observed'])
        self.assertEqual(result['counts'], dict.fromkeys(m.KINDS, None))

    def test_http_and_network_failures_never_zero(self):
        for status in (None, 401, 403, 429, 500, 302):
            with self.subTest(status=status):
                result = m.collect('SZLHOLDINGS', lambda u: {'status': status, 'json': []})
                self.assertFalse(result['observed'])
                self.assertIsNone(result['counts']['spaces'])
        def unavailable(_):
            raise TimeoutError('https://private.example/token-do-not-log')
        self.assertNotIn('private.example', json.dumps(m.collect('SZLHOLDINGS', unavailable)))

    def test_visibility_requires_explicit_false(self):
        for value in (None, True, 0, 'false'):
            with self.subTest(value=value):
                result = m.collect('SZLHOLDINGS', lambda u: {'status': 200, 'json': [row(private=value)]})
                self.assertFalse(result['observed'])
                self.assertEqual(result['items']['models'], [])

    def test_foreign_namespace_and_duplicate_rejected(self):
        for rows in ([row(id='other/model')], [row(), row()], [None], [row(id='../model')]):
            self.assertFalse(m.collect('SZLHOLDINGS', lambda u: {'status': 200, 'json': rows})['observed'])

    def test_gated_disabled_and_reserved_readme_still_inventory(self):
        rows = [row('README'), row('gated', gated=True), row('disabled', disabled=True)]
        inventory, manifest, counts = fixture(rows)
        self.assertEqual(counts['spaces'], 3)
        self.assertTrue(m.compare_manifest(inventory, manifest, counts)['aligned'])

    def test_private_labs_not_silently_mixed_into_public_count(self):
        result = m.collect('SZLHOLDINGS', lambda u: {'status': 200, 'json': [row('visible'), row('private-staging', private=True)]})
        self.assertFalse(result['observed'])
        self.assertNotIn('private-staging', json.dumps(result))

    def test_two_pages_complete(self):
        def get(url):
            if 'cursor=' in url:
                return {'status': 200, 'json': [row('last')], 'link': None}
            return {'status': 200, 'json': [row('first')], 'link': f'<{url}&cursor=page2>; rel="next"'}
        result = m.collect('SZLHOLDINGS', get)
        self.assertTrue(result['observed'])
        self.assertEqual(result['counts']['models'], 2)
        self.assertEqual(len(result['page_evidence']['models']), 2)

    def test_failed_later_page_discards_partial_count(self):
        def get(url):
            if 'cursor=' in url:
                return {'status': 503, 'json': []}
            return {'status': 200, 'json': [row()], 'link': f'<{url}&cursor=p2>; rel="next"'}
        result = m.collect('SZLHOLDINGS', get)
        self.assertIsNone(result['counts']['models'])
        self.assertEqual(result['items']['models'], [])
        self.assertEqual(len(result['page_evidence']['models']), 1)

    def test_duplicates_across_pages_rejected(self):
        def get(url):
            return {'status': 200, 'json': [row()], 'link': None if 'cursor=' in url else f'<{url}&cursor=p2>; rel="next"'}
        self.assertFalse(m.collect('SZLHOLDINGS', get)['observed'])

    def test_redirect_refused(self):
        with self.assertRaises(m.InventoryError):
            m.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://127.0.0.1')

    def test_scope_changes_in_pagination_refused(self):
        base = 'https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&full=true'
        for target in (base.replace('huggingface.co', 'example.com'), base.replace('models', 'datasets'),
                       base.replace('SZLHOLDINGS', 'other'), base+'&author=SZLHOLDINGS', base+'#a',
                       base.replace('https:', 'http:'), base.replace('huggingface.co', 'u:p@huggingface.co'),
                       base+'&cursor=', base+'&cursor=x&cursor=y', base+'&token=secret'):
            with self.subTest(target=target):
                with self.assertRaises(m.InventoryError):
                    m.next_url(f'<{target}>; rel="next"', 'SZLHOLDINGS', 'models')

    def test_malformed_links_cannot_mean_complete(self):
        base = 'https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&full=true'
        for link in ('unparseable', '<bad>', f'<{base}>; rel="next", <{base}>; rel="next"', 3):
            with self.assertRaises(m.InventoryError):
                m.next_url(link, 'SZLHOLDINGS', 'models')

    def test_pagination_cycles_bounded(self):
        def get(url):
            return {'status': 200, 'json': [row()], 'link': f'<{url}>; rel="next"'}
        self.assertFalse(m.collect('SZLHOLDINGS', get)['observed'])

    def test_page_budget_is_unknown(self):
        counter = 0
        def get(url):
            nonlocal counter
            counter += 1
            base = url.split('&cursor=')[0]
            return {'status': 200, 'json': [row(str(counter))], 'link': f'<{base}&cursor={counter}>; rel="next"'}
        with patch.object(m, 'MAX_PAGES', 2):
            result = m.collect('SZLHOLDINGS', get)
        self.assertFalse(result['observed'])
        self.assertEqual(counter, 6)

    def test_no_hidden_auth_headers_even_with_env_secrets(self):
        class Response:
            status = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return 'https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&full=true'
            def read(self, n): return b'[]'
        with patch.dict(os.environ, {'HF_TOKEN': 'not-a-real-token', 'GITHUB_TOKEN': 'not-a-real-token'}), patch.object(m, 'build_opener') as opener:
            opener.return_value.open.return_value = Response()
            m.public_get(Response().geturl())
            req = opener.return_value.open.call_args.args[0]
            self.assertFalse(req.has_header('Authorization'))
            self.assertFalse(req.has_header('Cookie'))

    def test_invalid_json_and_large_response_refused(self):
        class Response:
            status = 200
            headers = {}
            raw = b'{}'
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return 'https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&full=true'
            def read(self, n): return self.raw
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":1e999}', b'\xff', b' '*(m.MAX_BYTES+1)):
            response = Response(); response.raw = raw
            with patch.object(m, 'build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(m.InventoryError): m.public_get(response.geturl())

    def test_same_count_substitution_is_drift(self):
        inventory, manifest, counts = fixture()
        manifest['inventory']['models'][0]['id'] = 'SZLHOLDINGS/old'
        result = m.compare_manifest(inventory, manifest, counts)
        self.assertFalse(result['aligned'])
        self.assertEqual(result['delta']['models']['added'], ['SZLHOLDINGS/one'])
        self.assertEqual(result['delta']['models']['removed'], ['SZLHOLDINGS/old'])

    def test_missing_manifest_or_scope_never_aligned(self):
        inventory, manifest, counts = fixture()
        for change in ('absent', 'authenticated', 'private', 'org'):
            value = copy.deepcopy(manifest)
            if change == 'absent': value = None
            elif change == 'authenticated': value['inventoryScope']['authenticated'] = True
            elif change == 'private': value['inventoryScope']['privateAssetsIncluded'] = True
            else: value['org'] = 'other'
            self.assertFalse(m.compare_manifest(inventory, value, counts)['aligned'])

    def test_repeated_manifest_ids_or_wrong_counts_fail(self):
        inventory, manifest, counts = fixture()
        manifest['inventory']['models'].append(row())
        manifest['counts']['models'] = 2
        self.assertFalse(m.compare_manifest(inventory, manifest, counts)['aligned'])

    def test_none_declared_and_bool_counts_are_unknown(self):
        inventory, manifest, counts = fixture()
        for declared in (None, {}, dict(counts, models=True), dict(counts, extra=1)):
            self.assertIn('HF_PROFILE_COUNTS_UNAVAILABLE', m.compare_manifest(inventory, manifest, declared)['blockers'])

    def test_unknown_inventory_not_equal_empty_membership(self):
        inventory, manifest, counts = fixture([])
        inventory['observed'] = False
        inventory['counts']['spaces'] = None
        result = m.compare_manifest(inventory, manifest, counts)
        self.assertFalse(result['aligned'])
        self.assertIsNone(result['delta']['spaces']['added'])

    def test_scope_digest_mismatch_and_missing_scope_fail(self):
        inventory, manifest, counts = fixture()
        inventory['scope_sha256'] = '0'*64
        self.assertFalse(m.compare_manifest(inventory, manifest, counts)['aligned'])
        inventory['scope'] = {}
        self.assertFalse(m.compare_manifest(inventory, manifest, counts)['aligned'])

    def test_reordering_is_not_membership_drift(self):
        inventory, manifest, counts = fixture([row('b'), row('a')])
        manifest['inventory']['models'].reverse()
        self.assertTrue(m.compare_manifest(inventory, manifest, counts)['aligned'])

    def test_returned_scope_cannot_mutate_global_predicate(self):
        inventory = m.collect('SZLHOLDINGS', get_empty)
        inventory['scope']['kinds'].append('buckets')
        self.assertEqual(m.PREDICATE['kinds'], list(m.KINDS))

    def test_direct_transport_refuses_foreign_url_before_connection(self):
        with patch.object(m, 'build_opener') as opener:
            with self.assertRaises(m.InventoryError):
                m.public_get('https://example.com/api/models?author=SZLHOLDINGS&limit=100&full=true')
            opener.assert_not_called()

    def test_forged_observed_membership_is_not_aligned(self):
        for bad in ({'private': True}, {'id': None}, {'id': 'other/repo'}, {'id': []}):
            inventory, manifest, counts = fixture()
            inventory['items']['models'][0].update(bad)
            self.assertFalse(m.compare_manifest(inventory, manifest, counts)['aligned'])
        for key in ('counts', 'items'):
            inventory, manifest, counts = fixture()
            inventory[key] = 'malformed'
            self.assertFalse(m.compare_manifest(inventory, manifest, counts)['aligned'])

    def run_cli_fixture(self, directory, *, bad_digest=False, bad_scope=False, soft=False):
        from types import SimpleNamespace
        inventory, manifest, counts = fixture()
        config = {'huggingface_organization': 'SZLHOLDINGS', 'public_inventory_scope': m.PREDICATE}
        if bad_scope:
            config['public_inventory_scope'] = {'authentication': 'inherited'}
        estate = {'state': 'DIVERGENT', 'source_vector': {'a11oy': '1'*40},
                  'profile_inventory': {'declared_counts': counts, 'profile_sha': '2'*40}}
        estate['proof_chain_sha256'] = m.digest(estate) if not bad_digest else '0'*64
        for name, obj in [('config.json', config), ('manifest.json', manifest), ('estate.json', estate)]:
            (directory/name).write_text(json.dumps(obj))
        argv = ['hf_public_inventory.py', '--config', str(directory/'config.json'),
                '--manifest', str(directory/'manifest.json'), '--estate-report', str(directory/'estate.json'),
                '--output', str(directory/'receipt.json')] + (['--soft'] if soft else [])
        with patch('sys.argv', argv), patch('subprocess.run', return_value=SimpleNamespace(stdout='3'*40)), \
                patch.object(m, 'collect', return_value=inventory) as collect, patch('builtins.print'):
            code = m.main()
        report = json.loads((directory/'receipt.json').read_text())
        return code, report, collect.call_count

    def test_cli_receipt_is_hash_bound_and_not_overall_readiness(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, report, calls = self.run_cli_fixture(Path(tmp))
        self.assertEqual(code, 0)
        self.assertEqual(calls, 1)
        self.assertEqual(report['state'], 'ALIGNED')
        self.assertFalse(report['production_authorization'])
        self.assertFalse(report['provider_writes_performed'])
        self.assertFalse(report['card_semantics_refreshed'])
        self.assertEqual(report['checkout_source_revision'], '3'*40)
        self.assertEqual(report['estate_source_revision'], '1'*40)
        expected = report.pop('record_sha256')
        self.assertEqual(m.digest(report), expected)

    def test_cli_rejects_tampered_estate_before_network(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, report, calls = self.run_cli_fixture(Path(tmp), bad_digest=True)
        self.assertEqual((code, calls), (1, 0))
        self.assertEqual(report['state'], 'UNAVAILABLE')
        self.assertEqual(report['error'], 'ESTATE_RECEIPT_DIGEST_MISMATCH')

    def test_soft_mode_retains_failure_and_never_overwrites_evidence(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            code, report, calls = self.run_cli_fixture(directory, bad_scope=True, soft=True)
            before = (directory/'receipt.json').read_bytes()
            with self.assertRaises(FileExistsError):
                self.run_cli_fixture(directory)
            self.assertEqual(before, (directory/'receipt.json').read_bytes())
        self.assertEqual((code, calls), (0, 0))
        self.assertEqual(report['state'], 'UNAVAILABLE')
        self.assertEqual(report['error'], 'CONFIG_SCOPE_MISMATCH')

    def test_configuration_scope_is_exact(self):
        config_path = ROOT / 'config/estate-release-train.v1.json'
        self.assertTrue(config_path.is_file())
        self.assertEqual(json.loads(config_path.read_text())['public_inventory_scope'], m.PREDICATE)

    def test_workflow_enforces_both_receipts_and_preserves_artifacts(self):
        path = ROOT / '.github/workflows/estate-release-train.yml'
        self.assertTrue(path.is_file())
        text = path.read_text()
        self.assertIn('python tests/test_hf_public_inventory.py', text)
        self.assertIn('python scripts/hf_public_inventory.py', text)
        self.assertIn('test "$inventory_state" = ALIGNED', text)
        self.assertIn('test "$state" = ALIGNED', text)
        self.assertIn('if [ "$state" = ALIGNED ] && [ "$inventory_state" = ALIGNED ]; then', text)
        self.assertIn('reports/hf-public-inventory-preflight.json', text)


if __name__ == '__main__': unittest.main()
