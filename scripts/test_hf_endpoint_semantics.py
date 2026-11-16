"""Opaque pagination cursors are transport evidence, never asset identity."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

import audit_huggingface_ecosystem as audit

BASE = "https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&full=true"
README = "https://huggingface.co/api/spaces/SZLHOLDINGS/README"


class EndpointSemanticsTests(unittest.TestCase):
    def stable(self, urls):
        return audit.semantic_api_endpoints(urls)

    def test_cursor_rotation_is_semantically_identical(self):
        self.assertEqual(self.stable([BASE, BASE + "&cursor=old"]), self.stable([BASE, BASE + "&cursor=new"]))

    def test_query_order_is_not_membership_drift(self):
        other = "https://huggingface.co/api/models?full=true&limit=100&author=SZLHOLDINGS"
        self.assertEqual(self.stable([BASE]), self.stable([other]))

    def test_raw_evidence_is_not_rewritten(self):
        raw = [BASE, BASE + "&cursor=opaque%2Fencoded"]
        before = copy.deepcopy(raw)
        self.stable(raw)
        self.assertEqual(raw, before)

    def test_page_count_still_matters(self):
        self.assertNotEqual(self.stable([BASE]), self.stable([BASE, BASE + "&cursor=next"]))

    def test_continuation_presence_still_matters(self):
        self.assertNotEqual(self.stable([BASE]), self.stable([BASE + "&cursor=next"]))

    def test_namespace_still_matters(self):
        self.assertNotEqual(self.stable([BASE]), self.stable([BASE.replace('/models?', '/datasets?')]))

    def test_order_still_matters(self):
        dataset = BASE.replace('/models?', '/datasets?')
        self.assertNotEqual(self.stable([BASE, dataset]), self.stable([dataset, BASE]))

    def test_reserved_readme_observation_stays_exact(self):
        self.assertNotEqual(self.stable([BASE]), self.stable([BASE, README]))
        self.assertEqual(self.stable([README]), [{"scopeUrl": README, "continuation": False}])

    def test_empty_or_malformed_evidence_rejected(self):
        for value in ([], None, {}, 'url', [None], [BASE, BASE]):
            with self.subTest(value=value), self.assertRaises((ValueError, audit.InventoryError)):
                self.stable(value)

    def test_public_scope_cannot_change(self):
        bad = [
            BASE.replace('SZLHOLDINGS', 'other'), BASE.replace('limit=100', 'limit=10'),
            BASE.replace('full=true', 'full=false'), BASE.replace('https:', 'http:'),
            BASE.replace('huggingface.co', 'huggingface.co.evil.example'),
            BASE.replace('huggingface.co', 'user:password@huggingface.co'),
            BASE.replace('huggingface.co', 'huggingface.co:443'),
            BASE + '&token=do-not-send', BASE + '&author=SZLHOLDINGS',
            BASE + '&cursor=', BASE + '&cursor=one&cursor=two', BASE + '#fragment',
            README + '?cursor=x', BASE.replace('/api/models', '/api/models/SZLHOLDINGS/private'),
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises((ValueError, audit.InventoryError)):
                self.stable([value])

    def test_endpoint_budget_enforced(self):
        with self.assertRaises(ValueError):
            self.stable([BASE + '&cursor=' + str(i) for i in range(len(audit.KINDS) * audit.MAX_PAGES + 2)])

    def manifest(self, cursor='old'):
        return {
            'schemaVersion': 2, 'publicApiEndpoints': [BASE, BASE + '&cursor=' + cursor],
            'counts': {'models': 1},
            'inventory': {'models': [{'id': 'SZLHOLDINGS/example', 'sha': 'a' * 40,
                                      'lastModified': '2026-11-16T00:00:00Z',
                                      'tags': ['license:apache-2.0'], 'cardSemanticSha256': 'b' * 64}]},
        }

    def test_projection_does_not_modify_snapshot_or_ignore_claim_changes(self):
        left = self.manifest()
        right = self.manifest('new')
        original = copy.deepcopy(left)
        classes = SimpleNamespace(governed=lambda kind, name: False)
        self.assertEqual(audit.semantic_manifest(left, classes), audit.semantic_manifest(right, classes))
        self.assertEqual(left, original)
        right['inventory']['models'][0]['cardSemanticSha256'] = 'c' * 64
        self.assertNotEqual(audit.semantic_manifest(left, classes), audit.semantic_manifest(right, classes))

    def test_governed_exact_revisions_still_fail_comparison(self):
        left, right = self.manifest(), self.manifest('new')
        right['inventory']['models'][0]['sha'] = 'd' * 40
        classes = SimpleNamespace(governed=lambda kind, name: True)
        self.assertNotEqual(audit.semantic_manifest(left, classes), audit.semantic_manifest(right, classes))

    def test_count_drift_is_not_suppressed(self):
        left, right = self.manifest(), self.manifest('new')
        right['counts']['models'] = 2
        classes = SimpleNamespace(governed=lambda kind, name: False)
        self.assertNotEqual(audit.semantic_manifest(left, classes), audit.semantic_manifest(right, classes))


if __name__ == '__main__':
    unittest.main()
