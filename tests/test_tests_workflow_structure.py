#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guard the 54-job Tests workflow against naked folded-run continuations.

A prior source edit lost YAML indentation before a pytest file, causing GitHub
to reject the entire workflow before *any* job could report a failure.
The source contract must fail the first job, not quietly abandon all CI.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/tests.yml"
EXECUTION_JOB = re.compile(r"(?ms)^  execution-observer:\s*(.*?)^  python-estate-rag:")


class WorkflowStructureTests(unittest.TestCase):
    def test_no_naked_pytest_path_can_invalidate_yaml_root(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        bad = [(n, line) for n, line in enumerate(source.splitlines(), 1)
               if re.match(r"^tests/[\w./-]+\.py\b", line)]
        self.assertEqual(bad, [], "Unindented test path invalidates all of tests.yml")

    def test_two_independent_observer_test_modules_remain_in_folded_run(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        match = EXECUTION_JOB.search(source)
        self.assertIsNotNone(match, "Execution observer job missing")
        block = match.group(1)
        expected = ("tests/test_model_declaration_check.py",
                    "tests/test_collector_reason_codes.py")
        self.assertIn("run: >-", block)
        for test_file in expected:
            with self.subTest(file=test_file):
                self.assertEqual(block.count(test_file), 1)
                self.assertTrue((ROOT / test_file).is_file())
                line = next(line for line in block.splitlines()
                            if test_file in line)
                self.assertTrue(line.startswith("          "),
                                "folded pytest command must remain indented")

    def test_source_contract_is_invoked_from_initial_smoke_job(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        first = source.split("  execution-observer:", 1)[0]
        self.assertIn("python -B tests/test_tests_workflow_structure.py -v",first)


if __name__ == "__main__":
    unittest.main()
