# SPDX-License-Identifier: Apache-2.0
"""Offline monitor/publisher contract and negative controls; not live evidence.

Read the publisher's literal route declaration without importing its provider
client. A package release number is not an HTTP API namespace. In particular,
Lyte 4 owns /api/lyte/v2; the removed v3 routes must not drive recovery alarms.
"""
import ast
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ('/', '/healthz', '/readyz', '/api/build-info', '/.well-known/szl-source.json')
CAPABILITIES = ('/api/lyte/v2/catalog', '/api/lyte/v2/capabilities', '/api/lyte/v2/formulas')
EXPECTED = FOUNDATION + CAPABILITIES


def declared_publisher_paths(source):
    tree = ast.parse(source)
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'SMOKE_PATHS'
                      for target in node.targets)]
    if len(values) != 1:
        raise ValueError('publisher must declare one literal SMOKE_PATHS')
    paths = ast.literal_eval(values[0])
    if (not isinstance(paths, tuple) or not paths
            or any(not isinstance(p, str) for p in paths)
            or len(paths) != len(set(paths))):
        raise ValueError('invalid publisher route declaration')
    return paths


def validate_monitor(manifest, publisher_paths):
    rows = [row for row in manifest['public_products'] if row.get('id') == 'lyte']
    if len(rows) != 1:
        raise ValueError('one Lyte monitor required')
    row = rows[0]
    expected_binding = {
        'hf_repository': 'SZLHOLDINGS/lyte',
        'base_url': 'https://szlholdings-lyte.hf.space',
        'deployment_source_repository': 'szl-holdings/lyte-services',
        'revision_policy': 'exact-default-branch',
        'default_branch': 'main',
        'source_repository_policy': 'lyte-source-bound-build',
        'hf_revision_policy': 'provider-observed',
        'build_info_path': '/api/build-info',
    }
    if any(row.get(key) != value for key, value in expected_binding.items()):
        raise ValueError('Lyte monitor source authority drift')
    paths = row.get('required_paths')
    if paths != list(EXPECTED):
        raise ValueError('Lyte monitor must retain all eight current GET probes')
    if not set(paths).issubset(publisher_paths):
        raise ValueError('monitor routes are not verified by the canonical publisher')
    return row


class LyteMonitoringContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT/'governance/public-estate.v1.json').read_text())
        self.publisher = declared_publisher_paths((ROOT/'scripts/hf_publish_lyte_enterprise.py').read_text())

    def test_actual_monitor_retains_eight_current_publisher_probes(self):
        self.assertEqual(validate_monitor(self.manifest, self.publisher)['required_paths'], list(EXPECTED))

    def test_removed_v3_endpoints_are_not_availability_evidence(self):
        for current in CAPABILITIES:
            doc = copy.deepcopy(self.manifest)
            row = next(r for r in doc['public_products'] if r['id'] == 'lyte')
            row['required_paths'][row['required_paths'].index(current)] = current.replace('/v2/', '/v3/')
            with self.assertRaises(ValueError): validate_monitor(doc, self.publisher)

    def test_no_foundation_or_capability_probe_can_be_dropped(self):
        for missing in EXPECTED:
            doc = copy.deepcopy(self.manifest)
            row = next(r for r in doc['public_products'] if r['id'] == 'lyte')
            row['required_paths'].remove(missing)
            with self.assertRaises(ValueError): validate_monitor(doc, self.publisher)

    def test_duplicate_or_wrong_route_is_not_more_coverage(self):
        for extra in ('/', '/health', '/api/lyte/v2/health'):
            doc = copy.deepcopy(self.manifest)
            next(r for r in doc['public_products'] if r['id'] == 'lyte')['required_paths'].append(extra)
            with self.assertRaises(ValueError): validate_monitor(doc, self.publisher)

    def test_wrong_origin_source_and_revision_policy_fail(self):
        for key, value in (('base_url', 'https://example.invalid'),
                           ('deployment_source_repository', 'szl-holdings/a11oy'),
                           ('revision_policy', 'declared-commit'),
                           ('source_repository_policy', 'manifest-fixed-runtime-revision')):
            doc = copy.deepcopy(self.manifest)
            next(r for r in doc['public_products'] if r['id'] == 'lyte')[key] = value
            with self.assertRaises(ValueError): validate_monitor(doc, self.publisher)

    def test_publisher_route_retirement_requires_monitor_migration(self):
        with self.assertRaises(ValueError):
            validate_monitor(self.manifest, tuple(p for p in self.publisher if p != CAPABILITIES[0]))

    def test_ambiguous_or_executable_publisher_declaration_rejected(self):
        for source in ('SMOKE_PATHS = tuple(fetch_remote())',
                       'SMOKE_PATHS = ("/",)\nSMOKE_PATHS = ("/healthz",)',
                       'SMOKE_PATHS = ("/", "/")', 'pass'):
            with self.assertRaises((ValueError, TypeError)):
                declared_publisher_paths(source)

    def test_missing_or_duplicate_monitor_rejected(self):
        for duplicate in (False, True):
            doc = copy.deepcopy(self.manifest)
            row = next(r for r in doc['public_products'] if r['id'] == 'lyte')
            if duplicate: doc['public_products'].append(row)
            else: doc['public_products'].remove(row)
            with self.assertRaises(ValueError): validate_monitor(doc, self.publisher)


if __name__ == '__main__':
    unittest.main(verbosity=2)
