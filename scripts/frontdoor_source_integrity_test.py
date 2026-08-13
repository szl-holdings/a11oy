#!/usr/bin/env python3
"""Adversarial self-test for the front-door source-integrity guard."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
VALIDATOR_PATH = HERE / "validate_frontdoor_source_integrity.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_frontdoor_source_integrity", VALIDATOR_PATH
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


VALID_WORKFLOW = r"""name: HF Space module-drift guard

on:
  pull_request:
    branches: [main]
  schedule:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  hf-module-drift:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40
        with:
          egress-policy: audit
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          path: baseline
          ref: ${{ github.event.pull_request.base.sha }}
          persist-credentials: false
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: szl-holdings/.github
          ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054
          path: tools
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: "3.12"
      - run: |
          "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \
            --tools-script tools/.github/scripts/hf_module_drift_check.py \
            --github-repo "$GITHUB_REPOSITORY" \
            --github-ref "$SOURCE_REF" \
            --hf-repo SZLHOLDINGS/a11oy \
            --report-out hf-current-base-parity.out.json
        env:
          GITHUB_TOKEN: ${{ github.token }}
          SOURCE_REF: ${{ github.event.pull_request.base.sha }}
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        if: always()
        with:
          path: hf-current-base-parity.out.json
          if-no-files-found: error
  hf-runtime-live:
    uses: reusable-hf-module-drift-check.yml@0123456789abcdef
  hf-repository-parity:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40
        with:
          egress-policy: audit
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          path: candidate
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: szl-holdings/.github
          ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054
          path: tools
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: "3.12"
      - run: |
          "$pythonLocation/bin/python3" candidate/.github/scripts/verify_hf_repository_parity.py \
            --tools-script tools/.github/scripts/hf_module_drift_check.py \
            --github-repo "$GITHUB_REPOSITORY" \
            --github-ref "$SOURCE_REF" \
            --hf-repo SZLHOLDINGS/a11oy \
            --allow candidate/.github/hf-module-drift-allow.json \
            --report-out hf-repository-parity.out.json
        env:
          GITHUB_TOKEN: ${{ github.token }}
          SOURCE_REF: ${{ github.event.pull_request.head.sha }}
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        if: always()
        with:
          path: hf-repository-parity.out.json
          if-no-files-found: error
""" + "\n".join(f"# retained workflow line {index}" for index in range(100))


class IntegrityGuardSelfTest(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".github/workflows").mkdir(parents=True)
        (root / ".github/hf-module-drift-allow.json").write_text(
            json.dumps({"accepted_divergences": {}}), encoding="utf-8"
        )
        (root / validator.WORKFLOW_PATH).write_text(VALID_WORKFLOW, encoding="utf-8")
        for relative in validator.PUBLIC_UTF8_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Valid UTF-8: — Λ © · ≥\n", encoding="utf-8")
        return temp, root

    def test_honest_fixture_passes(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.assertEqual(validator.validate(root), [])

    def test_one_line_commented_workflow_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            (root / validator.WORKFLOW_PATH).write_text(
                "name: HF guard # on: jobs: everything is now a comment\n",
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertTrue(any("unexpectedly short" in error for error in errors))
            self.assertTrue(any("missing top-level line: on:" in error for error in errors))
            self.assertTrue(any("missing top-level line: jobs:" in error for error in errors))

    def test_commented_wrapper_and_forged_report_do_not_count_as_execution(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                "          python3 baseline/.github/scripts/verify_hf_repository_parity.py \\",
                '          # "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \\',
                1,
            ).replace(
                "            --tools-script tools/.github/scripts/hf_module_drift_check.py \\",
                "          # --tools-script tools/.github/scripts/hf_module_drift_check.py \\",
                1,
            ).replace(
                '            --github-ref "$SOURCE_REF"\n        env:',
                '          # --github-ref "$SOURCE_REF"\n'
                "          echo '{}' > hf-current-base-parity.out.json\n"
                "        env:",
                1,
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any(
                    "protected-base job must invoke the baseline wrapper" in error
                    for error in validator.validate(root)
                )
            )

    def test_bom_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_bytes(b"\xef\xbb\xbfvalid")
            self.assertTrue(any("BOM is forbidden" in error for error in validator.validate(root)))

    def test_mojibake_fails_but_real_unicode_passes(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text("broken â€” Î› Â©", encoding="utf-8")
            errors = validator.validate(root)
            self.assertTrue(any("mojibake marker" in error for error in errors))

    def test_explicit_candidate_divergence_is_allowed_only_with_bound_workflow(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            key = validator.PUBLIC_UTF8_PATHS[0].as_posix()
            (root / validator.ALLOWLIST_PATH).write_text(
                json.dumps({"accepted_divergences": {key: "do not inspect"}}),
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertEqual(errors, [])

    def test_protected_base_allowlist_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                "            --report-out hf-current-base-parity.out.json",
                "            --allow baseline/.github/hf-module-drift-allow.json \\\n"
                "            --report-out hf-current-base-parity.out.json",
                1,
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any("protected-base job must not receive" in error for error in validator.validate(root))
            )

    def test_candidate_missing_or_commented_allowlist_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                "            --allow candidate/.github/hf-module-drift-allow.json",
                "            # --allow candidate/.github/hf-module-drift-allow.json",
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any("same-checkout allowlist" in error for error in validator.validate(root))
            )

    def test_failure_suppressor_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                "            --allow candidate/.github/hf-module-drift-allow.json",
                "            --allow candidate/.github/hf-module-drift-allow.json || true",
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(any("failure suppressor" in error for error in validator.validate(root)))

    def test_shell_shadowing_and_extra_commands_fail(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                '          "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \\',
                "          python3() { :; }\n"
                '          "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \\',
                1,
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any(
                    "protected-base job must invoke the baseline wrapper" in error
                    for error in validator.validate(root)
                )
            )

    def test_parity_repositories_are_canonical(self) -> None:
        attacks = (
            ("SZLHOLDINGS/a11oy", "attacker/space"),
            ("$GITHUB_REPOSITORY", "attacker/repo"),
        )
        for trusted, attacker in attacks:
            temp, root = self.make_fixture()
            with temp:
                workflow = VALID_WORKFLOW.replace(trusted, attacker)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertTrue(
                    any("exact canonical parity command" in error for error in validator.validate(root))
                )

    def test_tools_checkout_identity_is_canonical(self) -> None:
        attacks = (
            ("repository: szl-holdings/.github", "repository: attacker/tools"),
            (
                "ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054",
                "ref: 0123456789abcdef0123456789abcdef01234567",
            ),
            ("path: tools", "path: untrusted-tools"),
            (
                "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "actions/checkout@abcdef0123456789abcdef0123456789abcdef01",
            ),
        )
        for trusted, attacker in attacks:
            temp, root = self.make_fixture()
            with temp:
                workflow = VALID_WORKFLOW.replace(trusted, attacker)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertTrue(
                    any(
                        "checkout" in error or "canonical proof steps" in error
                        for error in validator.validate(root)
                    )
                )

    def test_parity_jobs_cannot_be_conditionally_skipped(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                "if: github.event_name == 'pull_request'",
                "if: false",
                1,
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any("exact pull-request predicate" in error for error in validator.validate(root))
            )

    def test_workflow_level_shell_initialization_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                "permissions:\n",
                "env: { BASH_ENV: candidate/shadow.sh }\npermissions:\n",
                1,
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any("top-level env" in error for error in validator.validate(root))
            )

    def test_trigger_and_job_execution_envelope_is_canonical(self) -> None:
        attacks = (
            ("branches: [main]", "paths: [never/**]"),
            ("runs-on: ubuntu-latest", "runs-on: self-hosted"),
            ('python-version: "3.12"', 'python-version: "pypy"'),
            ("if-no-files-found: error", "if-no-files-found: ignore"),
        )
        for trusted, attacker in attacks:
            temp, root = self.make_fixture()
            with temp:
                workflow = VALID_WORKFLOW.replace(trusted, attacker, 1)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

    def test_security_source_cannot_be_allowlisted(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            (root / validator.ALLOWLIST_PATH).write_text(
                json.dumps(
                    {"accepted_divergences": {".well-known/security.txt": "bypass"}}
                ),
                encoding="utf-8",
            )
            self.assertTrue(any("security.txt cannot bypass" in error for error in validator.validate(root)))

    def test_candidate_cannot_broaden_comparator_exclusions(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            (root / validator.ALLOWLIST_PATH).write_text(
                json.dumps({"ignore_paths": ["**"], "accepted_divergences": {}}),
                encoding="utf-8",
            )
            self.assertTrue(
                any(
                    "ignore_paths broadens protected exclusions" in error
                    for error in validator.validate(root)
                )
            )

    def test_missing_runtime_job_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace("  hf-runtime-live:\n", "")
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any("hf-runtime-live" in error for error in validator.validate(root))
            )

if __name__ == "__main__":
    unittest.main(verbosity=2)
