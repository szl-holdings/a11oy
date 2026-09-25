# SPDX-License-Identifier: Apache-2.0
"""Trusted workflow source must match the selected deployment before HTTP."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('trusted_model_live', ROOT/'scripts/verify_model_pretraining_live.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SHA = 'a'*40


class WorkflowSourceTests(unittest.TestCase):
    def test_post_publish_checkout_is_trusted_workflow_source(self):
        workflow=(ROOT/'.github/workflows/hf-tooling-product.yml').read_text()
        job=workflow.split('  published-model-readback:',1)[1]
        self.assertIn('ref: ${{ github.sha }}',job)
        self.assertNotIn('ref: ${{ github.event.workflow_run.head_sha }}',job)
        self.assertIn('SOURCE_SHA: ${{ github.event.workflow_run.head_sha }}',job)
        self.assertIn('contents: read',job)
        self.assertNotIn('secrets.',job)
        self.assertNotIn('git checkout',job)

    def test_moved_checkout_stops_before_http_and_writes_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'failure.json'
            arguments=SimpleNamespace(surface='canonical',expected_source=SHA,output=output)
            with patch.object(M.argparse.ArgumentParser,'parse_args',return_value=arguments), \
                    patch.object(M.subprocess,'run',return_value=SimpleNamespace(stdout='b'*40)), \
                    patch.object(M,'probe') as observe, patch('builtins.print'):
                self.assertEqual(M.main(),1)
            observe.assert_not_called()
            report=json.loads(output.read_text())
            self.assertEqual(report['state'],'UNAVAILABLE')
            self.assertFalse(report['trainingAllowed'])
            self.assertIn('checkout/source mismatch',report['reason'])


if __name__ == '__main__': unittest.main()
