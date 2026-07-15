#!/usr/bin/env python3
"""Regression tests for the immutable shared-peer PR resolver."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "resolve-shared-peer-ref.py"
WORKFLOW = HERE / "workflows" / "shared-file-drift.yml"
REPOSITORY = "szl-holdings/killinchu"
SHA = "9fb553e483cd887f57799cf264424227d68db155"


class ResolverTests(unittest.TestCase):
    def run_case(self, event_name: str, body: str | None = None) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event_path = root / "event.json"
            output_path = root / "output.txt"
            event_path.write_text(json.dumps({"pull_request": {"body": body}}), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--event-name",
                    event_name,
                    "--event-path",
                    str(event_path),
                    "--output",
                    str(output_path),
                    "--expected-repository",
                    REPOSITORY,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            values: dict[str, str] = {}
            if output_path.exists():
                for line in output_path.read_text(encoding="utf-8").splitlines():
                    key, value = line.split("=", 1)
                    values[key] = value
            return result, values

    def test_non_pr_always_uses_main(self) -> None:
        result, values = self.run_case("push", f"{MARKER}\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["ref"], "main")
        self.assertEqual(values["source"], "sibling-main")

    def test_pr_without_marker_uses_main(self) -> None:
        result, values = self.run_case("pull_request", "ordinary pull request")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["ref"], "main")

    def test_valid_marker_emits_immutable_commit_and_pr(self) -> None:
        result, values = self.run_case("pull_request", f"context\n{MARKER}\nmore")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["repository"], REPOSITORY)
        self.assertEqual(values["pull_request"], "234")
        self.assertEqual(values["ref"], SHA)
        self.assertEqual(values["source"], "pinned-peer-pr")

    def test_duplicate_marker_fails_closed(self) -> None:
        result, values = self.run_case("pull_request", f"{MARKER}\n{MARKER}")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(values, {})

    def test_branch_name_is_rejected(self) -> None:
        result, values = self.run_case(
            "pull_request",
            "Shared-source-peer: szl-holdings/killinchu#234@codex/a11oy-shared-sync-wave23-websigned",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(values, {})

    def test_wrong_repository_is_rejected(self) -> None:
        result, values = self.run_case(
            "pull_request",
            f"Shared-source-peer: attacker/killinchu#234@{SHA}",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(values, {})

    def test_uppercase_or_short_sha_is_rejected(self) -> None:
        result, values = self.run_case(
            "pull_request",
            f"Shared-source-peer: {REPOSITORY}#234@{SHA.upper()}",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(values, {})


class WorkflowTests(unittest.TestCase):
    def test_peer_is_verified_before_checkout(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        verify = workflow.index("- name: Verify pinned peer is the declared open PR head")
        checkout = workflow.index("- name: Checkout killinchu (verified sibling)")
        self.assertLess(verify, checkout)

    def test_peer_comparison_uses_visible_delimiter(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("| join(\" \")", workflow)
        self.assertIn('expected="open main ${PEER_REF}"', workflow)
        self.assertNotIn('expected="open\\tmain\\t${PEER_REF}"', workflow)


MARKER = f"Shared-source-peer: {REPOSITORY}#234@{SHA}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
