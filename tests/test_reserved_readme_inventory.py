# SPDX-License-Identifier: Apache-2.0
"""Offline reserved-Space regressions; fixtures are not live inventory proof."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import audit_huggingface_ecosystem as audit
from scripts import hf_public_inventory as public
from scripts import verify_estate_release_train as release


ORG = 'SZLHOLDINGS'
URL = f'https://huggingface.co/api/spaces/{ORG}/README'
ROW = {'id': f'{ORG}/README', 'private': False, 'disabled': True,
       'sha': 'a' * 40, 'lastModified': '2026-09-29T00:00:00Z'}


def getter(response, *, listed=False):
    def get(url):
        if url == URL:
            return response
        rows = [ROW] if listed and '/api/spaces?' in url else []
        return {'status': 200, 'json': rows, 'link': None}
    return get


class ReservedReadmeTests(unittest.TestCase):
    def emitter_manifest(self, *, listed=False, reserved_get=None):
        def fetch_page(url):
            return {"status": 200, "json": [ROW] if listed and '/api/spaces?' in url else []}

        def supplement(org):
            if reserved_get is None:
                raise AssertionError('unexpected reserved README request')
            return public.reserved_readme(org, reserved_get)

        with patch.object(audit, 'public_get', side_effect=fetch_page), \
             patch.object(audit, 'fetch_card_markdown', return_value='# Public Space\n'), \
             patch.object(audit, 'reserved_readme', side_effect=supplement) as request:
            manifest = audit.build_manifest(observed_at='2026-10-02T01:04:24Z')
        return manifest, request

    def test_emitter_manifest_records_supplemental_public_endpoint_once(self):
        manifest, request = self.emitter_manifest(
            reserved_get=getter({'status': 200, 'json': ROW}))
        request.assert_called_once_with(ORG)
        self.assertEqual(manifest['counts'], {'models': 0, 'datasets': 0, 'spaces': 1, 'kernels': 0})
        self.assertEqual([row['id'] for row in manifest['inventory']['spaces']], [ROW['id']])
        self.assertEqual(manifest['publicApiEndpoints'].count(URL), 1)
        self.assertEqual(manifest['publicApiEndpoints'][-2], URL)
        meaning = manifest['inventoryScope']['countMeaning'].lower()
        for term in ('anonymous', 'author-filtered', 'reserved', 'readme', 'once'):
            self.assertIn(term, meaning)

    def test_emitter_manifest_does_not_infer_reserved_request_from_listed_row(self):
        manifest, request = self.emitter_manifest(listed=True)
        request.assert_not_called()
        self.assertEqual(manifest['counts']['spaces'], 1)
        self.assertEqual([row['id'] for row in manifest['inventory']['spaces']], [ROW['id']])
        self.assertNotIn(URL, manifest['publicApiEndpoints'])

    def test_emitter_manifest_records_negative_reserved_observations_without_details(self):
        for response in ({'status': 404},
                         {'status': 200, 'json': {**ROW, 'private': True,
                          'private_detail': 'never retain'}}):
            with self.subTest(status=response['status']):
                manifest, request = self.emitter_manifest(reserved_get=getter(response))
                request.assert_called_once_with(ORG)
                self.assertEqual(manifest['counts']['spaces'], 0)
                self.assertEqual(manifest['inventory']['spaces'], [])
                self.assertEqual(manifest['publicApiEndpoints'].count(URL), 1)
                rendered = json.dumps(manifest)
                self.assertNotIn('private_detail', rendered)
                self.assertNotIn('never retain', rendered)

    def test_emitter_manifest_refuses_invalid_or_unavailable_reserved_metadata(self):
        invalid = ({'status': 401}, {'status': 500},
                   {'status': 200, 'json': []},
                   {'status': 200, 'json': {**ROW, 'id': 'other/README'}},
                   {'status': 200, 'json': {**ROW, 'private': None}})
        for response in invalid:
            with self.subTest(response=response), self.assertRaises(public.InventoryError):
                self.emitter_manifest(reserved_get=getter(response))

        def unavailable(_):
            raise TimeoutError('private.example/token')

        with self.assertRaises(TimeoutError):
            self.emitter_manifest(reserved_get=unavailable)

    def test_supplemental_public_metadata_counts_once_in_both_membership_collectors(self):
        get = getter({'status': 200, 'json': ROW, 'response_sha256': 'b' * 64})
        for collect in (public.collect, release.hf_inventory):
            with self.subTest(collect=collect.__name__):
                result = collect(ORG, get)
                self.assertTrue(result['observed'])
                self.assertEqual(result['counts'], {'models': 0, 'datasets': 0, 'spaces': 1, 'kernels': 0})
                self.assertEqual(result['items']['spaces'][0]['id'], ROW['id'])
                self.assertEqual(result['reserved_readme_evidence']['state'], 'PUBLIC_METADATA')
                self.assertEqual(result['reserved_readme_evidence']['response_sha256'], 'b' * 64)

    def test_existing_author_member_is_not_requested_or_double_counted(self):
        def get(url):
            self.assertNotEqual(url, URL)
            return {'status': 200, 'json': [ROW] if '/api/spaces?' in url else []}
        for collect in (public.collect, release.hf_inventory):
            result = collect(ORG, get)
            self.assertTrue(result['observed'])
            self.assertEqual(result['counts']['spaces'], 1)
            self.assertEqual(result['reserved_readme_evidence']['state'], 'AUTHOR_LIST')
        with patch.object(audit, 'public_get', return_value={'status': 200, 'json': [ROW]}), \
             patch.object(audit, 'reserved_readme') as supplemental:
            self.assertEqual(audit.api_items('spaces'), [ROW])
            supplemental.assert_not_called()

    def test_explicit_absent_and_nonpublic_dispositions_complete_without_details(self):
        for response, state in (({'status': 404}, 'NOT_PUBLICLY_OBSERVABLE'),
                                ({'status': 200, 'json': {**ROW, 'private': True,
                                  'private_detail': 'never retain'}}, 'EXPLICITLY_NON_PUBLIC')):
            for collect in (public.collect, release.hf_inventory):
                result = collect(ORG, getter(response))
                self.assertTrue(result['observed'])
                self.assertEqual(result['counts']['spaces'], 0)
                self.assertEqual(result['reserved_readme_evidence']['state'], state)
                self.assertNotIn('never retain', str(result))

    def test_unavailable_or_invalid_metadata_never_completes_scope(self):
        cases = [{'status': status} for status in (401, 403, 429, 500, 302, None)]
        cases += [{'status': 200, 'json': value} for value in (
            [], None, {}, {**ROW, 'id': 'other/README'}, {**ROW, 'id': 'SZLHOLDINGS/readme'},
            {**ROW, 'private': None}, {**ROW, 'private': 0}, {**ROW, 'private': 'false'})]
        cases += [{'status': 200, 'json': ROW, 'redirect': 'https://example.invalid'},
                  {'status': 200, 'json': ROW, 'link': '<anything>; rel="next"'}]
        for response in cases:
            for collect in (public.collect, release.hf_inventory):
                with self.subTest(response=response, collect=collect.__name__):
                    result = collect(ORG, getter(response))
                    self.assertFalse(result['observed'])
                    self.assertIsNone(result['counts']['spaces'])
                    self.assertIsNone(result['items']['spaces'])

    def test_provider_transport_exception_is_unavailable_without_url_leak(self):
        def get(url):
            if url == URL:
                raise TimeoutError('private.example/token')
            return {'status': 200, 'json': []}
        for collect in (public.collect, release.hf_inventory):
            result = collect(ORG, get)
            self.assertFalse(result['observed'])
            self.assertNotIn('private.example', str(result))

    def test_supplement_respects_existing_item_budget(self):
        for module, collect, cap in ((public, public.collect, 'MAX_ITEMS'),
                                    (release, release.hf_inventory, 'MAX_INVENTORY_ITEMS')):
            with patch.object(module, cap, 0):
                result = collect(ORG, getter({'status': 200, 'json': ROW}))
                self.assertFalse(result['observed'])
                self.assertIsNone(result['counts']['spaces'])

    def test_emitter_uses_same_reserved_observation_without_modifying_metadata(self):
        with patch.object(audit, 'public_get', return_value={'status': 200, 'json': []}), \
             patch.object(audit, 'reserved_readme', return_value=(ROW, {'state': 'PUBLIC_METADATA'})):
            self.assertEqual(audit.api_items('spaces'), [ROW])
        with patch.object(audit, 'public_get', return_value={'status': 200, 'json': []}), \
             patch.object(audit, 'reserved_readme', side_effect=public.InventoryError('HTTP_UNAVAILABLE')):
            with self.assertRaises(public.InventoryError):
                audit.api_items('spaces')

    def test_reserved_url_is_fixed_and_has_no_credentials_query_or_redirect(self):
        for url in (URL + '?token=x', URL + '#x', URL.replace('https:', 'http:'),
                    URL.replace('huggingface.co', 'u:p@huggingface.co'),
                    URL.replace('/README', '/other'), URL.replace('SZLHOLDINGS', 'other')):
            with self.subTest(url=url), patch.object(public, 'build_opener') as opener:
                with self.assertRaises(public.InventoryError):
                    public.validate_reserved_url(url, ORG)
                opener.assert_not_called()

    def test_reserved_404_transport_retains_bounded_raw_digest(self):
        error = HTTPError(URL, 404, 'absent', {}, io.BytesIO(b'not found'))
        with patch.object(public, 'build_opener') as opener:
            opener.return_value.open.side_effect = error
            result = public.public_get(URL)
        self.assertEqual(result['status'], 404)
        self.assertEqual(len(result['response_sha256']), 64)
        with patch.object(public, 'MAX_BYTES', 1), patch.object(public, 'build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError(URL, 404, 'absent', {}, io.BytesIO(b'large'))
            with self.assertRaisesRegex(public.InventoryError, 'RESPONSE_BYTE_BUDGET'):
                public.public_get(URL)

    def test_default_release_listing_uses_anonymous_transport(self):
        with patch.object(release, 'public_get', side_effect=getter({'status': 404})) as get, \
             patch.object(release, 'fetch') as authenticated:
            result = release.hf_inventory(ORG)
        self.assertTrue(result['observed'])
        self.assertEqual(get.call_count, len(public.KINDS) + 1)
        authenticated.assert_not_called()

    def test_reserved_response_malformed_json_and_byte_budget_fail_closed(self):
        class Response:
            status = 200
            headers = {}
            def __init__(self, raw): self.raw = raw
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def geturl(self): return URL
            def read(self, limit): return self.raw[:limit]
        for raw in (b'{', b'{"id":"SZLHOLDINGS/README","id":"other/README"}',
                    b'{"private":NaN}', b'\xff'):
            with self.subTest(raw=raw), patch.object(public, 'build_opener') as opener:
                opener.return_value.open.return_value = Response(raw)
                with self.assertRaisesRegex(public.InventoryError, 'INVALID_JSON_RESPONSE'):
                    public.public_get(URL)
        with patch.object(public, 'MAX_BYTES', 1), patch.object(public, 'build_opener') as opener:
            opener.return_value.open.return_value = Response(b'{}')
            with self.assertRaisesRegex(public.InventoryError, 'RESPONSE_BYTE_BUDGET'):
                public.public_get(URL)

    def test_release_rejects_nonpublic_listing_before_supplement(self):
        result = release.hf_inventory(ORG, getter({'status': 404}, listed=True))
        self.assertTrue(result['observed'])
        for private in (True, None, 0, 'false'):
            result = release.hf_inventory(ORG, lambda _: {'status': 200, 'json': [{**ROW, 'private': private}]})
            self.assertFalse(result['observed'])
            self.assertIsNone(result['counts']['spaces'])


if __name__ == '__main__':
    unittest.main()
