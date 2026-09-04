from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
HELPER = ROOT / "scripts" / "hf_exact_main_ownership.py"
TARGET_JOB = "Publish and live-verify six domain-native flagship Spaces"


def indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def job_block(source: str, name: str) -> str:
    lines = source.splitlines()
    pattern = re.compile(rf"^\s*name:\s*[\"']?{re.escape(name)}[\"']?\s*$")
    matches = [index for index, line in enumerate(lines) if pattern.fullmatch(line)]
    if len(matches) != 1:
        raise AssertionError(f"expected one job named {name!r}, found {len(matches)}")
    name_index = matches[0]
    name_indent = indent(lines[name_index])
    key_pattern = re.compile(r"^[A-Za-z0-9_-]+:\s*$")
    start = None
    for index in range(name_index - 1, -1, -1):
        if indent(lines[index]) < name_indent and key_pattern.fullmatch(lines[index].strip()):
            start = index
            break
    if start is None:
        raise AssertionError("target job key was not found")
    job_indent = indent(lines[start])
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if (
            stripped
            and not stripped.startswith("#")
            and indent(lines[index]) == job_indent
            and key_pattern.fullmatch(stripped)
        ):
            end = index
            break
    return "\n".join(lines[start:end])


def step_block(job: str, name: str) -> str:
    lines = job.splitlines()
    pattern = re.compile(rf"^(\s*)- name:\s*[\"']?{re.escape(name)}[\"']?\s*$")
    matches = []
    for index, line in enumerate(lines):
        match = pattern.fullmatch(line)
        if match:
            matches.append((index, len(match.group(1))))
    if len(matches) != 1:
        raise AssertionError(f"expected one step named {name!r}, found {len(matches)}")
    start, step_indent = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        current = indent(lines[index])
        if current < step_indent or (
            current == step_indent and lines[index].lstrip().startswith("- name:")
        ):
            end = index
            break
    return "\n".join(lines[start:end])


class HFSyncSupersessionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.job = job_block(cls.workflow, TARGET_JOB)

    def test_exact_main_controller_and_receipt_are_mandatory(self) -> None:
        ownership = step_block(self.job, "Assert the workflow owns exact protected main")
        receipt = step_block(self.job, "Upload exact-main ownership receipt")
        self.assertIn("id: exact_main_owner", ownership)
        self.assertIn("scripts/hf_exact_main_ownership.py", ownership)
        self.assertIn('--repository "$GITHUB_REPOSITORY"', ownership)
        self.assertIn('--expected-sha "$GITHUB_SHA"', ownership)
        self.assertIn('--github-output "$GITHUB_OUTPUT"', ownership)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", ownership)
        self.assertNotIn("continue-on-error", ownership)
        self.assertIn("if: always()", receipt)
        self.assertRegex(receipt, r"uses: actions/upload-artifact@[0-9a-f]{40}")
        self.assertIn("${{ runner.temp }}/hf-main-ownership.json", receipt)
        self.assertIn("if-no-files-found: error", receipt)

    def test_every_publication_capable_step_requires_owned_source(self) -> None:
        gate = "steps.exact_main_owner.outputs.publish == 'true'"
        for name in (
            "Set up Python",
            "Install pinned vertical publisher",
            "Publish and verify the v4 vertical estate",
        ):
            self.assertIn(gate, step_block(self.job, name), name)
        publication_receipt = step_block(
            self.job, "Upload immutable vertical publication receipt"
        )
        self.assertIn(gate, publication_receipt)
        self.assertIn("always()", publication_receipt)

    def test_helper_requires_ancestry_and_has_no_write_authority(self) -> None:
        helper = HELPER.read_text(encoding="utf-8")
        self.assertIn("prove_ancestor", helper)
        self.assertIn("/compare/", helper)
        self.assertIn("SUPERSEDED_BY_NEWER_MAIN", helper)
        self.assertIn('"status": "ERROR"', helper)
        self.assertIn('"external_writes_performed": False', helper)
        self.assertIn('method="GET"', helper)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotIn(f'method="{method}"', helper)


if __name__ == "__main__":
    unittest.main(verbosity=2)
