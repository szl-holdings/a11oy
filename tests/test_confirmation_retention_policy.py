#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Run the real consolidation decision path without provider/network access."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts.hf_keep_policy import load_keep_ids

ROOT = Path(__file__).resolve().parents[1]
SPACE = 'SZLHOLDINGS/szl-foundation-confirmation'
POLICIES = (
    ROOT / 'docs/series-a/hf-space-keep-list.yaml',
    ROOT / 'docs/estate/hf-nine-flagship-keep.yaml',
)


class ConfirmationRetentionPolicyTest(unittest.TestCase):
    def test_exact_lab_retention_is_distinct_from_inventory_or_product_authority(self):
        for policy in POLICIES:
            with self.subTest(policy=policy.name):
                kept = load_keep_ids(policy)
                self.assertEqual(kept.count(SPACE), 1)
                self.assertEqual(len([x for x in kept if x.startswith('SZLHOLDINGS/')]), 8)
                self.assertIn('betterwithage/anatomy', kept)
                for folded in ('SZLHOLDINGS/yarqa', 'SZLHOLDINGS/szl-forge-lab', 'SZLHOLDINGS/unknown-new-space'):
                    self.assertNotIn(folded, kept)
                text = policy.read_text(encoding='utf-8')
                self.assertIn('role: exploratory_synthetic_cpu_trials', text)
                self.assertIn('source: szl-holdings/szl-forge', text)
                self.assertIn('registered_scientific_gate: FAILED', text)
                self.assertIn('wider_system_qualified: false', text)
        contract = json.loads((ROOT / 'static/shared/public-estate-contract.v1.json').read_bytes())
        self.assertIn(SPACE, contract['laboratorySurfaces'])
        self.assertNotIn(SPACE, [x['id'] for x in contract['inventoryOnlyHuggingFaceRepositories']])
        self.assertEqual(len(contract['publicDomainBodies']), 5)
        self.assertFalse(contract['authority']['productionAuthorization'])

    def test_real_consolidator_keeps_only_admitted_ids_and_folds_unknown_inventory(self):
        # Only the provider transport is substituted; the production parser,
        # classification, loops, mutation selection, and receipt remain real.
        hub = types.ModuleType('huggingface_hub')
        hub.HfApi = object
        utils = types.ModuleType('huggingface_hub.utils')
        utils.HfHubHTTPError = type('HfHubHTTPError', (Exception,), {})
        spec = importlib.util.spec_from_file_location('confirmation_retention_controller', ROOT / 'scripts/hf_consolidate_fleet.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'huggingface_hub': hub, 'huggingface_hub.utils': utils}):
            spec.loader.exec_module(module)
        for policy in POLICIES:
            with self.subTest(policy=policy.name), tempfile.TemporaryDirectory() as temp:
                keep = [x for x in load_keep_ids(policy) if x.startswith('SZLHOLDINGS/')]
                folded = ['SZLHOLDINGS/yarqa', 'SZLHOLDINGS/unknown-new-space']
                state = {x: {'private': False, 'stage': 'RUNNING'} for x in keep + folded}
                operations = []

                class RecordingProvider:
                    def __init__(self, token):
                        self.token = token

                    def list_spaces(self, author, full):
                        assert author == 'SZLHOLDINGS' and full is True
                        return [types.SimpleNamespace(id=x, private=y['private'], sdk='docker') for x, y in state.items()]

                    def get_space_runtime(self, repo_id):
                        return types.SimpleNamespace(stage=state[repo_id]['stage'])

                    def update_repo_settings(self, repo_id, repo_type, private):
                        assert repo_type == 'space'
                        operations.append((repo_id, 'private', private))
                        state[repo_id]['private'] = private

                    def pause_space(self, repo_id):
                        operations.append((repo_id, 'pause'))
                        state[repo_id]['stage'] = 'PAUSED'

                    def restart_space(self, repo_id):
                        operations.append((repo_id, 'restart'))
                        state[repo_id]['stage'] = 'RUNNING'

                receipt = Path(temp) / 'receipt.json'
                argv = ['hf_consolidate_fleet.py', '--org', 'SZLHOLDINGS', '--policy', str(policy), '--out', str(receipt)]
                with patch.object(module, 'HfApi', RecordingProvider), patch.object(module, 'token_from_env', return_value=('test-only-placeholder', 'TEST_TRANSPORT')), patch.object(sys, 'argv', argv):
                    self.assertEqual(module.main(), 0)
                report = json.loads(receipt.read_bytes())
                rows = {x['space']: x for x in report['actions']}
                self.assertEqual(rows[SPACE]['desired'], 'KEEP_PUBLIC_RUNNING')
                self.assertEqual(rows[SPACE]['operations'], [])
                self.assertFalse(state[SPACE]['private'])
                self.assertEqual(state[SPACE]['stage'], 'RUNNING')
                self.assertFalse(any(x[0] == SPACE for x in operations))
                for space in folded:
                    self.assertEqual(rows[space]['desired'], 'FOLD_PRIVATE_PAUSED')
                    self.assertIn((space, 'private', True), operations)
                    self.assertIn((space, 'pause'), operations)
                    self.assertTrue(state[space]['private'])
                    self.assertEqual(state[space]['stage'], 'PAUSED')
                self.assertEqual(report['keep_count'], 8)
                self.assertEqual(report['fold_count'], 2)
                self.assertTrue(report['terminal_green'])
                self.assertFalse(report['token_value_persisted'])
                self.assertNotIn('test-only-placeholder', receipt.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
