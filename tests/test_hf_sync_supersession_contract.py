from __future__ import annotations

import re
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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

    def test_both_initial_provider_jobs_require_successful_owned_admission(self) -> None:
        for name in (
            "Resume the canonical Space without changing its allocation",
            "Deploy, source-bind, and attest exact surface",
        ):
            with self.subTest(job=name):
                job = job_block(self.workflow, name)
                self.assertIn("needs: source-admission", job)
                self.assertIn("if: ${{ needs.source-admission.outputs.publish == 'true' }}", job)
                self.assertNotRegex(job, r"(?m)^    if:.*always\(")
                self.assertNotIn("continue-on-error", job)
        deploy = job_block(self.workflow, "Deploy, source-bind, and attest exact surface")
        self.assertIn("require-default-branch-tip: true", deploy)
        self.assertIn("ref: ${{ github.sha }}", deploy)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_admission_is_read_only_source_bound_and_retained(self) -> None:
        job = job_block(self.workflow, "Admit the queued source before provider mutation")
        self.assertIn("publish: ${{ steps.owner.outputs.publish }}", job)
        self.assertIn("contents: read", job)
        self.assertNotIn("secrets.", job)
        self.assertNotIn("HF_TOKEN", job)
        self.assertIn("ref: ${{ github.sha }}", job)
        step = step_block(job, "Require main and classify current source ownership")
        self.assertIn('test "$GITHUB_REF" = refs/heads/main', step)
        self.assertIn("scripts/hf_exact_main_ownership.py", step)
        self.assertIn('--expected-sha "$GITHUB_SHA"', step)
        self.assertNotIn("continue-on-error", job)
        receipt = step_block(job, "Retain the source admission decision")
        self.assertIn("if: always()", receipt)
        self.assertIn("if-no-files-found: error", receipt)
        self.assertIn("canonical-source-admission-${{ github.run_id }}-${{ github.run_attempt }}", receipt)

    def test_actual_admission_outputs_deny_stale_and_uncertain_provider_jobs(self) -> None:
        # Exercise the helper consumed by both job conditions. These are injected
        # GitHub replies; no provider mutation or live deployment is performed.
        spec = importlib.util.spec_from_file_location("canonical_admission_test", HELPER)
        ownership = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ownership)
        expected, newer = "a" * 40, "b" * 40
        cases = (
            ("current", [{"commit": {"sha": expected}}], 0, "true", "OWNED"),
            ("superseded", [{"commit": {"sha": newer}}, {
                "status": "ahead", "ahead_by": 1, "behind_by": 0,
                "merge_base_commit": {"sha": expected},
            }], 0, "false", "SUPERSEDED_BY_NEWER_MAIN"),
            ("diverged", [{"commit": {"sha": newer}}, {
                "status": "diverged", "ahead_by": 1, "behind_by": 1,
                "merge_base_commit": {"sha": "c" * 40},
            }], 1, "false", "ERROR"),
            ("unavailable", [OSError("unavailable fixture")], 1, "false", "ERROR"),
        )
        for name, replies, code, publish, status in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temporary:
                receipt = Path(temporary) / "admission.json"
                output = Path(temporary) / "output"
                with mock.patch.object(ownership, "request_json", side_effect=replies), redirect_stdout(io.StringIO()):
                    observed = ownership.execute(repository="szl-holdings/a11oy",
                        expected_sha=expected, receipt_path=receipt,
                        github_output=output, token="github-fixture")
                values = dict(line.split("=", 1) for line in output.read_text().splitlines())
                report = json.loads(receipt.read_text())
                self.assertEqual(observed, code)
                self.assertEqual(values["publish"], publish)
                self.assertEqual(report["status"], status)
                self.assertIs(report["external_writes_performed"], False)
                self.assertIs(report["secret_values_recorded"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
