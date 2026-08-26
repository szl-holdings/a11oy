"""Regression coverage for protected Frontier workflow source constants."""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIR_SCRIPT = ROOT / "ops/frontier/v16_7/apply_current_main_repairs.py"
SOURCE_TEST = ROOT / "ops/frontier/v16_7/test_frontier_v16_7_terminal_truth.py"
CONTRACT = ROOT / "ops/frontier/v16_7/SOLO_EXECUTION_CONTRACT.json"
CI_WORKFLOW = ROOT / ".github/workflows/tests.yml"
WORKFLOWS = (
    ROOT / ".github/workflows/frontier-solo-qualification.yml",
    ROOT / ".github/workflows/frontier-v16-7-exact-source-builder.yml",
)
ORPHAN_DIGEST_LINE = re.compile(
    r"^[ \t]*\$[0-9a-fA-F]+[ \t]*$", re.MULTILINE
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FrontierWorkflowSourceIntegrityTests(unittest.TestCase):
    def test_guard_is_wired_into_hosted_ci(self) -> None:
        source = CI_WORKFLOW.read_text(encoding="utf-8")
        job_header = "  frontdoor-source-integrity:\n"
        next_job = "\n  python-nemo-owner-dispatch:\n"
        command = (
            "python3 -m unittest discover -s tests "
            "-p test_frontier_workflow_source_integrity.py -v"
        )

        self.assertEqual(source.count(job_header), 1)
        self.assertEqual(source.count(next_job), 1)
        job = source.split(job_header, 1)[1].split(next_job, 1)[0]
        self.assertEqual(source.count(command), 1)
        self.assertIn(command, job)

    def test_orphan_digest_detection_rejects_indentation(self) -> None:
        for indentation in ("", "  ", "\t"):
            with self.subTest(indentation=repr(indentation)):
                source = f"{indentation}${'0' * 64}\n"
                self.assertIsNotNone(ORPHAN_DIGEST_LINE.search(source))

    def test_frontier_workflows_bind_all_protected_inputs(self) -> None:
        expected = {
            "CONTRACT": _digest(CONTRACT),
            "REPAIR_SCRIPT": _digest(REPAIR_SCRIPT),
            "SOURCE_TEST": _digest(SOURCE_TEST),
        }

        for workflow in WORKFLOWS:
            source = workflow.read_text(encoding="utf-8")
            for name, digest in expected.items():
                matches = re.findall(
                    rf"^      {name}_SHA256: ([0-9a-f]{{64}})$",
                    source,
                    re.MULTILINE,
                )
                self.assertEqual(matches, [digest], (workflow, name))
                self.assertGreaterEqual(
                    source.count(f"${name}_SHA256"),
                    1,
                    (workflow, name),
                )
            self.assertIsNone(ORPHAN_DIGEST_LINE.search(source), workflow)


if __name__ == "__main__":
    unittest.main()
