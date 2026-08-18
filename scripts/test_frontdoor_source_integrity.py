#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
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
    - cron: '37 6 * * 1'
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  hf-module-drift:
    name: Protected base matches immutable HF repository
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40
        with:
          egress-policy: audit
      - name: Checkout exact protected base verifier
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          path: baseline
          ref: ${{ github.event.pull_request.base.sha }}
          persist-credentials: false
      - name: Checkout exact reusable tools revision
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: szl-holdings/.github
          ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054
          path: tools
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: "3.12"
      - name: Prove stable immutable deployed-base repository parity
        run: |
          "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \
            --tools-script tools/.github/scripts/hf_module_drift_check.py \
            --github-repo "$GITHUB_REPOSITORY" \
            --github-ref "$SOURCE_REF" \
            --hf-repo SZLHOLDINGS/a11oy \
            --report-out hf-current-base-parity.out.json
        env:
          GITHUB_TOKEN: ${{ github.token }}
          SOURCE_REF: ${{ github.event.pull_request.base.sha }}
      - name: Upload immutable deployed-base proof
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: hf-current-base-parity
          path: hf-current-base-parity.out.json
          if-no-files-found: error
          retention-days: 90
  hf-runtime-live:
    name: Scheduled live HF runtime source witness
    if: github.event_name != 'pull_request'
    uses: szl-holdings/.github/.github/workflows/reusable-hf-module-drift-check.yml@0816263f1e83734658d6e5a8a7cd3834f36a2054
    with:
      hf-repo: SZLHOLDINGS/a11oy
      mode: source-bound-baseline
      trusted-base-ref: ${{ github.sha }}
      candidate-ref: ${{ github.sha }}
      source-probe-path: /api/build-info
      dockerfile-path: Dockerfile
      github-ref: ${{ github.sha }}
      hf-ref: main
  hf-repository-parity:
    name: Immutable HF repository byte parity
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40
        with:
          egress-policy: audit
      - name: Checkout exact protected-base verifier
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          path: baseline
          ref: ${{ github.event.pull_request.base.sha }}
          persist-credentials: false
      - name: Checkout exact reusable tools revision
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: szl-holdings/.github
          ref: 0816263f1e83734658d6e5a8a7cd3834f36a2054
          path: tools
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
        with:
          python-version: "3.12"
      - name: Prove the candidate introduces no unmanaged deployed-byte drift
        run: |
          "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \
            --tools-script tools/.github/scripts/hf_module_drift_check.py \
            --github-repo "$GITHUB_REPOSITORY" \
            --base-ref "$BASE_REF" \
            --github-ref "$SOURCE_REF" \
            --hf-repo SZLHOLDINGS/a11oy \
            --report-out hf-repository-parity.out.json
        env:
          GITHUB_TOKEN: ${{ github.token }}
          BASE_REF: ${{ github.event.pull_request.base.sha }}
          SOURCE_REF: ${{ github.event.pull_request.head.sha }}
      - name: Upload immutable candidate repository parity report
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: hf-repository-parity
          path: hf-repository-parity.out.json
          if-no-files-found: error
          retention-days: 90
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
            command = '''          "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \\
            --tools-script tools/.github/scripts/hf_module_drift_check.py \\
            --github-repo "$GITHUB_REPOSITORY" \\
            --github-ref "$SOURCE_REF" \\
            --hf-repo SZLHOLDINGS/a11oy \\
            --report-out hf-current-base-parity.out.json'''
            forged = '''          # "$pythonLocation/bin/python3" baseline/.github/scripts/verify_hf_repository_parity.py \\
          # --tools-script tools/.github/scripts/hf_module_drift_check.py \\
          # --github-repo "$GITHUB_REPOSITORY" \\
          # --github-ref "$SOURCE_REF" \\
          # --hf-repo SZLHOLDINGS/a11oy \\
          # --report-out hf-current-base-parity.out.json
          echo '{}' > hf-current-base-parity.out.json'''
            self.assertIn(command, VALID_WORKFLOW)
            workflow = VALID_WORKFLOW.replace(command, forged, 1)
            self.assertIn('# "$pythonLocation/bin/python3"', workflow)
            self.assertIn("echo '{}' > hf-current-base-parity.out.json", workflow)
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
            self.assertTrue(any("BOM codepoint is forbidden" in error for error in validator.validate(root)))

    def test_embedded_bom_codepoint_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_bytes(b"valid\xef\xbb\xbfstill-valid-utf8")
            self.assertTrue(
                any("BOM codepoint is forbidden" in error for error in validator.validate(root))
            )

    def test_additional_mojibake_sequences_fail(self) -> None:
        for content in ("visible ï»¿ marker", "visible ï¿½ marker", "broken ÐŸÑ€ marker"):
            temp, root = self.make_fixture()
            with temp:
                target = root / validator.PUBLIC_UTF8_PATHS[0]
                target.write_text(content, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

    def test_legitimate_international_text_remains_valid(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text("Ñawi · Español · Ð · Привет · 你好\n", encoding="utf-8")
            self.assertEqual(validator.validate(root), [])

    def test_symlinked_public_file_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            backing = root / "backing.html"
            backing.write_text("safe\n", encoding="utf-8")
            target.unlink()
            try:
                target.symlink_to(backing)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            self.assertTrue(any("symlink" in error for error in validator.validate(root)))

    def test_allowlist_duplicate_or_missing_accepted_divergences_fails(self) -> None:
        payloads = (
            '{"accepted_divergences": {}, "accepted_divergences": {}}',
            '{"ignore_paths": []}',
        )
        for payload in payloads:
            temp, root = self.make_fixture()
            with temp:
                (root / validator.ALLOWLIST_PATH).write_text(payload, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

    def test_mojibake_fails_but_real_unicode_passes(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text("broken â€” Î› Â©", encoding="utf-8")
            errors = validator.validate(root)
            self.assertTrue(any("mojibake marker" in error for error in errors))

    def test_accepted_divergence_fails_closed(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            key = validator.PUBLIC_UTF8_PATHS[0].as_posix()
            (root / validator.ALLOWLIST_PATH).write_text(
                json.dumps({"accepted_divergences": {key: "do not inspect"}}),
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertTrue(any("accepted divergences must be empty" in error for error in errors))

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

    def test_candidate_base_ref_is_required(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                '            --base-ref "$BASE_REF"',
                '            # --base-ref "$BASE_REF"',
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(
                any("protected BASE_REF" in error or "canonical parity command" in error for error in validator.validate(root))
            )

    def test_failure_suppressor_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            workflow = VALID_WORKFLOW.replace(
                '            --base-ref "$BASE_REF"',
                '            --base-ref "$BASE_REF" || true',
            )
            (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
            self.assertTrue(any("failure suppressor" in error for error in validator.validate(root)))

    def test_escaped_failure_suppressors_and_extra_inputs_fail(self) -> None:
        attacks = (
            VALID_WORKFLOW.replace(
                "    runs-on: ubuntu-latest\n    timeout-minutes: 15\n    steps:",
                "    runs-on: ubuntu-latest\n"
                '    "continue\\u002don\\u002derror": true\n'
                "    timeout-minutes: 15\n    steps:",
                1,
            ),
            VALID_WORKFLOW.replace(
                "        env:\n          GITHUB_TOKEN:",
                '        "continue\\u002don\\u002derror": true\n'
                "        env:\n          GITHUB_TOKEN:",
                1,
            ),
            VALID_WORKFLOW.replace(
                "        if: always()\n        uses: actions/upload-artifact@",
                '        "\\u0063ontinue-on-error": true\n'
                "        if: always()\n        uses: actions/upload-artifact@",
                1,
            ),
            VALID_WORKFLOW.replace(
                "          persist-credentials: false\n"
                "      - name: Checkout exact reusable tools revision",
                "          persist-credentials: false\n"
                "          github-server-url: https://attacker.example\n"
                "      - name: Checkout exact reusable tools revision",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    timeout-minutes: 15\n    steps:",
                "    timeout-minutes: 15\n    services: {}\n    steps:",
                1,
            ),
        )
        for workflow in attacks:
            temp, root = self.make_fixture()
            with temp:
                self.assertNotEqual(workflow, VALID_WORKFLOW)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

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

    def test_spaced_or_quoted_workflow_shell_keys_fail(self) -> None:
        attacks = (
            "env : { BASH_ENV: candidate/shadow.sh }",
            "'env' : { BASH_ENV: candidate/shadow.sh }",
            '"env" : { BASH_ENV: candidate/shadow.sh }',
        )
        for attack in attacks:
            temp, root = self.make_fixture()
            with temp:
                workflow = VALID_WORKFLOW.replace(
                    "permissions:\n",
                    f"{attack}\npermissions:\n",
                    1,
                )
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertTrue(
                    any("top-level env" in error for error in validator.validate(root))
                )

    def test_duplicate_and_flow_yaml_overrides_fail(self) -> None:
        attacks = (
            VALID_WORKFLOW + "\njobs: {}\n",
            VALID_WORKFLOW + "\n'jobs': {}\n",
            VALID_WORKFLOW + "\non: {workflow_dispatch: null}\n",
            VALID_WORKFLOW + "\n'on': {workflow_dispatch: null}\n",
            VALID_WORKFLOW + "\npwn: attacker\n",
            VALID_WORKFLOW.replace(
                "  hf-runtime-live:\n",
                "  pwn:\n    name: Source in sync with the live HF Space\n"
                "    uses: attacker/repo/.github/workflows/pwn.yml@main\n"
                "  hf-runtime-live:\n",
                1,
            ),
            VALID_WORKFLOW + "\n  'hf-module-drift':\n    if: false\n",
            VALID_WORKFLOW.replace(
                "          BASE_REF: ${{ github.event.pull_request.base.sha }}\n"
                "          SOURCE_REF: ${{ github.event.pull_request.head.sha }}",
                "          BASE_REF: ${{ github.event.pull_request.base.sha }}\n"
                "          SOURCE_REF: ${{ github.event.pull_request.head.sha }}\n"
                "        env: {BASE_REF: attacker, SOURCE_REF: attacker}",
                1,
            ),
            VALID_WORKFLOW.replace(
                "          persist-credentials: false\n"
                "      - name: Checkout exact reusable tools revision",
                "          persist-credentials: false\n"
                "        with: {path: attacker, ref: attacker}\n"
                "      - name: Checkout exact reusable tools revision",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    steps:\n",
                "    steps:\n      - &bypass {run: 'echo forged > hf-current-base-parity.out.json'}\n",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    steps:\n",
                "    steps:\n      - [run, 'echo forged']\n",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    steps:\n",
                "    steps:\n      - uses: &action "
                "step-security/harden-runner@b09bb98e06d4d774595224525879c09bc6e98c40\n",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    steps:\n",
                "    steps:\n      - !!map\n        run: echo forged\n",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    steps:\n",
                "    steps:\n      ? run\n      : echo forged\n",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    steps:\n",
                "    steps:\n      - run: echo canonical\n    steps:\n",
                1,
            ),
        )
        for workflow in attacks:
            temp, root = self.make_fixture()
            with temp:
                self.assertNotEqual(workflow, VALID_WORKFLOW)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

    def test_every_canonical_action_step_must_execute(self) -> None:
        actions = (
            validator.HARDEN_RUNNER_ACTION,
            validator.CHECKOUT_ACTION,
            validator.SETUP_PYTHON_ACTION,
        )
        for action in actions:
            temp, root = self.make_fixture()
            with temp:
                workflow = VALID_WORKFLOW.replace(
                    f"        uses: {action}",
                    f"        uses: {action}\n        if: false",
                    1,
                )
                self.assertNotEqual(workflow, VALID_WORKFLOW)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertTrue(
                    any(
                        "execute every canonical proof step" in error
                        for error in validator.validate(root)
                    )
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

    def test_trigger_and_runtime_lifecycle_are_canonical(self) -> None:
        attacks = (
            VALID_WORKFLOW.replace(
                "  workflow_dispatch:\n", "  workflow_dispatch:\n  push:\n", 1
            ),
            VALID_WORKFLOW.replace("37 6 * * 1", "0 0 * * *", 1),
            VALID_WORKFLOW.replace(
                "  schedule:\n    - cron: '37 6 * * 1'\n  workflow_dispatch:\n",
                "  # schedule:\n  #   - cron: '37 6 * * 1'\n"
                "  # workflow_dispatch:\n",
                1,
            ),
            VALID_WORKFLOW.replace(
                "    if: github.event_name != 'pull_request'",
                "    if: false",
                1,
            ),
            VALID_WORKFLOW.replace(
                validator.RUNTIME_WORKFLOW,
                "attacker/repo/.github/workflows/noop.yml@main # "
                + validator.RUNTIME_WORKFLOW,
                1,
            ),
            VALID_WORKFLOW.replace(
                "      trusted-base-ref: ${{ github.sha }}",
                "      trusted-base-ref: refs/heads/attacker",
                1,
            ),
        )
        for workflow in attacks:
            temp, root = self.make_fixture()
            with temp:
                self.assertNotEqual(workflow, VALID_WORKFLOW)
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

    def test_workflow_and_job_names_are_pinned_and_unique(self) -> None:
        attacks = (
            VALID_WORKFLOW.replace(
                "name: HF Space module-drift guard",
                "name: Attacker workflow",
                1,
            ),
            VALID_WORKFLOW.replace(
                "name: Protected base matches immutable HF repository",
                "name: Forged check",
                1,
            ),
            VALID_WORKFLOW.replace(
                "name: Scheduled live HF runtime source witness",
                "name: Protected base matches immutable HF repository",
                1,
            ),
            VALID_WORKFLOW.replace(
                "name: HF Space module-drift guard",
                "name: &evil.name HF Space module-drift guard",
                1,
            ).replace(
                "name: Protected base matches immutable HF repository",
                "name: *evil.name",
                1,
            ),
        )
        for workflow in attacks:
            temp, root = self.make_fixture()
            with temp:
                (root / validator.WORKFLOW_PATH).write_text(workflow, encoding="utf-8")
                self.assertNotEqual(validator.validate(root), [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
