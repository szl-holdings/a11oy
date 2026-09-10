# SPDX-License-Identifier: Apache-2.0
"""Static wiring contracts: PR readers must not queue behind canonical writers."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/estate-release-train.yml'

class EstateReadOnlyConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding='utf-8')

    def test_pr_has_own_named_group_and_canonical_group_is_preserved(self):
        self.assertIn("group: ${{ github.event_name == 'pull_request' && format('estate-release-train-pr-{0}', github.event.pull_request.number) || 'estate-release-train' }}", self.text)
        self.assertIn('cancel-in-progress: false', self.text)

    def test_provider_dispatch_remains_explicit_manual_repair_only(self):
        block = self.text.split('- name: Dispatch only the established canonical writers\n', 1)[1].split('        env:', 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' &&", block)
        self.assertIn('inputs.repair == true &&', block)
        self.assertIn("steps.initial.outputs.state != 'ALIGNED'", block)

    def test_pr_cannot_write_alignment_incident(self):
        block = self.text.split('- name: Synchronize one deterministic alignment incident\n', 1)[1].split('        env:', 1)[0]
        self.assertIn("if: github.event_name != 'pull_request'", block)

    def test_pr_observes_exact_candidate_and_tests_are_run(self):
        self.assertIn("ref: ${{ github.event_name == 'pull_request' && github.sha || 'main' }}", self.text)
        self.assertIn('python tests/test_estate_pr_concurrency.py', self.text)
        self.assertIn('      - tests/test_estate_pr_concurrency.py', self.text)
        self.assertIn('test "$state" = ALIGNED', self.text)
        self.assertIn('test "$inventory_state" = ALIGNED', self.text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
