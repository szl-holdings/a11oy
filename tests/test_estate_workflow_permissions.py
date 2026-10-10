# SPDX-License-Identifier: Apache-2.0
"""Candidate observation must never inherit provider-dispatch permissions."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/estate-release-train.yml"


def job(text, name):
    match = re.search(r"^  " + re.escape(name) + r":\n(.*?)(?=^  [\w-]+:\n|\Z)",
                      text.split("jobs:\n", 1)[1], re.M | re.S)
    if match is None:
        raise AssertionError(f"Missing job {name}")
    return match.group(1)


class EstateWorkflowPermissionTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.reader = job(self.text, "verify-pr")
        self.operator = job(self.text, "verify")

    def test_candidate_has_only_read_permissions(self):
        permissions = self.reader.split("    permissions:\n", 1)[1].split("    runs-on:", 1)[0]
        self.assertEqual(permissions, "      actions: read\n      contents: read\n      issues: read\n")
        self.assertIn("if: github.event_name == 'pull_request'", self.reader)
        self.assertNotIn("secrets.", self.reader)
        self.assertNotIn("Dispatch only the established canonical writers", self.reader)
        self.assertNotIn("Synchronize one deterministic alignment incident", self.reader)

    def test_operational_job_excludes_candidate_and_unprotected_refs(self):
        condition = self.operator.split("    if: >-\n", 1)[1].split("    runs-on:", 1)[0]
        for predicate in ("github.event_name != 'pull_request'",
                          "github.ref == 'refs/heads/main'",
                          "github.event.workflow_run.conclusion == 'success'",
                          "github.event.workflow_run.head_branch == 'main'",
                          "github.event.workflow_run.head_sha == github.sha",
                          "github.event.workflow_run.head_repository.full_name == github.repository"):
            self.assertIn(predicate, condition)

    def test_reader_preserves_candidate_observation_and_proof(self):
        for name in ("Prove proposed release-vector controller offline",
                     "Observe the current three-plane estate",
                     "Observe one explicit public membership predicate",
                     "Upload immutable release-vector evidence"):
            self.assertIn("- name: " + name, self.reader)
        self.assertIn("ref: ${{ github.sha }}", self.reader)
        self.assertIn("persist-credentials: false", self.reader)
        self.assertIn("--soft", self.reader)
        self.assertNotIn('test "$state" = ALIGNED', self.reader)

    def test_privileged_job_keeps_dispatch_and_alignment_enforcement(self):
        self.assertIn("Dispatch only the established canonical writers", self.operator)
        self.assertIn("Synchronize one deterministic alignment incident", self.operator)
        self.assertIn('test "$state" = ALIGNED', self.operator)
        self.assertIn('test "$inventory_state" = ALIGNED', self.operator)
        self.assertIn("inputs.repair == true", self.operator)
        self.assertIn("ref: ${{ github.sha }}", self.operator)


if __name__ == "__main__":
    unittest.main(verbosity=2)
