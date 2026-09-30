#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Provenance/services deployment closure, not whole-application boot proof."""

import ast
import hashlib
import json
import shlex
import unittest
from pathlib import Path

import a11oy_steward_surface as surface

ROOT = Path(__file__).resolve().parents[1]


class PublicStewardPackageTests(unittest.TestCase):
    def test_real_package_is_pinned_and_contract_valid_even_after_expiry(self):
        package = surface._initialize()
        lock = package['lock']
        for filename, key in [('steward_public.py', 'module_sha256'),
                              ('steward-public.json', 'projection_sha256')]:
            self.assertEqual(hashlib.sha256((ROOT / filename).read_bytes()).hexdigest(), lock[key])
        result = package['reader'].load_public_projection(
            ROOT / 'steward-public.json', expected_source_revision=lock['revision'],
            expected_sha256=lock['projection_sha256'], allowed_directory=ROOT,
        )
        self.assertTrue(result['valid'], result['errors'])
        self.assertIn(result['state'], ('CURRENT', 'STALE'))
        self.assertFalse(result['projection']['production_ready'])
        self.assertFalse(result['projection']['provider']['model_invoked'])
        if result['state'] == 'STALE':
            self.assertEqual(result['projection']['proposals'], [])

    def test_explicit_docker_copy_closure(self):
        copies = [line.strip() for line in (ROOT / 'Dockerfile').read_text().splitlines()
                  if line.strip().startswith('COPY ')]
        root_sources = {name for line in copies for parts in [shlex.split(line)]
                        if parts[-1] == './' for name in parts[1:-1]}
        for filename in ('a11oy_steward_surface.py', 'steward_public.py',
                         'steward-public.json', 'steward-source-lock.json'):
            self.assertIn(filename, root_sources)
        self.assertFalse(any('estate.db' in line or 'frontier_steward_plan.json' in line
                             for line in copies))

    def test_service_registration_precedes_proxy_and_spa(self):
        source = (ROOT / 'serve.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        registration = [node.lineno for node in ast.walk(tree)
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == '_steward_surface'
                        and node.func.attr == 'register']
        self.assertEqual(len(registration), 1)
        fallbacks = [node.lineno for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and any(
                         isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                         and '{' in arg.value and ':path}' in arg.value
                         for arg in node.args)]
        self.assertTrue(fallbacks)
        self.assertLess(registration[0], min(fallbacks))

    def test_no_future_annotations_in_service_handlers(self):
        tree = ast.parse((ROOT / 'a11oy_steward_surface.py').read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module == '__future__'
                             and any(alias.name == 'annotations' for alias in node.names)
                             for node in ast.walk(tree)))

    def test_public_bundle_has_no_private_store_or_execution_claim(self):
        value = json.loads((ROOT / 'steward-public.json').read_text(encoding='utf-8'))
        self.assertEqual(value['scope'], 'PUBLIC_READ_ONLY')
        self.assertEqual(value['mutation_policy'], 'PROPOSAL_ONLY')
        self.assertFalse(value['production_ready'])
        self.assertEqual(value['provider']['runtime'], 'NO_MODEL_CALL')
        self.assertEqual(value['integrity']['signature_status'], 'UNSIGNED')
        self.assertFalse(value['integrity']['independent_witness'])


if __name__ == '__main__':
    unittest.main()
