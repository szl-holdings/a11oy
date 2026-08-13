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
  schedule:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  hf-module-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
        with:
          repository: szl-holdings/.github
          ref: 0123456789abcdef0123456789abcdef01234567
      - run: |
          python3 baseline/.github/scripts/verify_hf_repository_parity.py \
            --tools-script tools/.github/scripts/hf_module_drift_check.py \
            --github-ref "$SOURCE_REF"
        env:
          SOURCE_REF: ${{ github.event.pull_request.base.sha }}
  hf-runtime-live:
    uses: reusable-hf-module-drift-check.yml@0123456789abcdef
  hf-repository-parity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
        with:
          repository: szl-holdings/.github
          ref: 0123456789abcdef0123456789abcdef01234567
      - run: |
          python3 candidate/.github/scripts/verify_hf_repository_parity.py \
            --tools-script tools/.github/scripts/hf_module_drift_check.py \
            --github-ref "$SOURCE_REF" \
            --allow candidate/.github/hf-module-drift-allow.json
        env:
          SOURCE_REF: ${{ github.event.pull_request.head.sha }}
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
                '--github-ref "$SOURCE_REF"\n        env:',
                '--github-ref "$SOURCE_REF" \\\n+            --allow baseline/.github/hf-module-drift-allow.json\n        env:',
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
