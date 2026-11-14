# SPDX-License-Identifier: Apache-2.0
"""Privileged workflow runs must not check out event-derived (untrusted) refs.

Regression for code-scanning alerts on szl-holdings/a11oy:
  * Scorecard DangerousWorkflow (critical) - hf-tooling-product.yml
  * CodeQL actions/cache-poisoning/poisonable-step (high) - atelier-frontier-live-proof.yml

A workflow_run job executes in the default-branch context (it can write the
default-branch Actions cache). Any actions/checkout there must use a trusted ref
(github.sha), never a value taken from the triggering event or a pull request.
"""
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github/workflows'
UNTRUSTED = re.compile(r'github\.event\.(workflow_run\.head_|pull_request\.head|pull_request_target)')
GUARDED = ('hf-tooling-product.yml', 'atelier-frontier-live-proof.yml')


def _load(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text())
    triggers = data.get(True, data.get('on')) or {}
    return data, set(triggers if isinstance(triggers, (dict, list)) else [triggers])


def _can_run_on_workflow_run(job):
    condition = str(job.get('if', ''))
    if not condition:
        return True
    # Jobs explicitly excluded from workflow_run are not privileged here.
    return not re.fullmatch(r"\s*github\.event_name\s*!=\s*'workflow_run'\s*", condition)


def _resolved_ref(job, step):
    ref = str((step.get('with') or {}).get('ref', ''))
    env = {**(job.get('env') or {}), **(step.get('env') or {})}
    for key, value in env.items():
        ref = ref.replace('${{ env.%s }}' % key, str(value))
    return ref


class PrivilegedCheckoutTests(unittest.TestCase):
    def test_guarded_workflows_still_trigger_on_workflow_run(self):
        for name in GUARDED:
            _, triggers = _load(name)
            self.assertIn('workflow_run', triggers, name)

    def test_no_event_derived_checkout_in_privileged_jobs(self):
        for name in GUARDED:
            data, _ = _load(name)
            for job_id, job in data['jobs'].items():
                if not _can_run_on_workflow_run(job):
                    continue
                for step in job.get('steps', []):
                    if not str(step.get('uses', '')).startswith('actions/checkout@'):
                        continue
                    with self.subTest(workflow=name, job=job_id, step=step.get('name')):
                        self.assertIsNone(UNTRUSTED.search(_resolved_ref(job, step)))

    def test_atelier_live_proof_keeps_its_offline_gate(self):
        data, _ = _load('atelier-frontier-live-proof.yml')
        live = data['jobs']['live']
        runs = '\n'.join(str(step.get('run', '')) for step in live['steps'])
        self.assertIn('pytest tests/test_atelier_frontier_live.py -q', runs)
        self.assertIn('--require-hashes -r .github/requirements/ci-core.txt', runs)
        self.assertEqual(live['env']['SOURCE_SHA'], '${{ github.sha }}')
        self.assertIn('github.event.workflow_run.head_sha == github.sha', str(live['if']))

    def test_published_snapshot_requires_main_ancestry_before_materialising(self):
        data, _ = _load('hf-tooling-product.yml')
        job = data['jobs']['published-model-readback']
        script = next(str(s['run']) for s in job['steps'] if 'PUBLISHED_SHA' in (s.get('env') or {}))
        self.assertLess(script.index('merge-base --is-ancestor'), script.index('git worktree add'))
        self.assertIn('^[0-9a-f]{40}$', script)
        self.assertEqual(job['permissions'], {'contents': 'read'})


if __name__ == '__main__':
    unittest.main()
