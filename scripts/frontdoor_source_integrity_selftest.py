#!/usr/bin/env python3
"""Adversarial self-test for the front-door source-integrity guard."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
VALIDATOR_PATH = HERE / "validate_frontdoor_source_integrity.py"
SPEC = importlib.util.spec_from_file_location(
    "validate_frontdoor_source_integrity", VALIDATOR_PATH
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class IntegrityGuardSelfTest(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".github/workflows").mkdir(parents=True)
        (root / validator.WORKFLOW_PATH).write_bytes(
            (REPO_ROOT / validator.WORKFLOW_PATH).read_bytes()
        )
        (root / validator.ALLOWLIST_PATH).write_text(
            json.dumps(
                {
                    "ignore_paths": ["console/assets/**"],
                    "ignore_extensions": [".png"],
                    "accepted_divergences": {},
                }
            ),
            encoding="utf-8",
        )
        for relative in validator.PUBLIC_UTF8_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "Valid UTF-8: — Λ © · ≥. Español, français, Ã, ð, Þ.\n",
                encoding="utf-8",
            )
        return temp, root

    def write_workflow(self, root: Path, transform) -> None:
        path = root / validator.WORKFLOW_PATH
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")

    def write_allowlist(self, root: Path, payload: dict[str, object]) -> None:
        (root / validator.ALLOWLIST_PATH).write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_honest_fixture_passes(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.assertEqual(validator.validate(root), [])

    def test_one_line_commented_workflow_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            (root / validator.WORKFLOW_PATH).write_text(
                "name: HF guard # on: jobs: all controls are comment text\n",
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertTrue(any("unexpectedly short" in error for error in errors))
            self.assertTrue(any("active on:" in error for error in errors))
            self.assertTrue(any("active jobs:" in error for error in errors))

    def test_nul_hidden_in_comment_fails_before_comment_stripping(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "# Pull requests",
                    "# hidden control \x00 Pull requests",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("U+0000" in error for error in errors), errors)

    def test_c1_hidden_in_comment_fails_before_comment_stripping(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "# Pull requests",
                    "# hidden control \u0085 Pull requests",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("U+0085" in error for error in errors), errors)

    def test_commented_job_keys_fail_even_when_tokens_remain(self) -> None:
        for job in validator.JOB_FIELDS:
            with self.subTest(job=job):
                temp, root = self.make_fixture()
                with temp:
                    self.write_workflow(
                        root,
                        lambda text, job=job: text.replace(
                            f"  {job}:\n", f"  # {job}:\n", 1
                        ),
                    )
                    errors = validator.validate(root)
                    self.assertTrue(
                        any("workflow jobs must be exactly" in error for error in errors),
                        errors,
                    )

    def test_commented_uses_fails_even_when_token_remains_in_comment(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    f"    uses: {validator.REUSABLE_WORKFLOW}",
                    f"    # uses: {validator.REUSABLE_WORKFLOW}",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("requires active uses" in error for error in errors), errors)

    def test_commented_condition_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "    if: github.event_name == 'pull_request'",
                    "    # if: github.event_name == 'pull_request'",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("requires active if" in error for error in errors), errors)

    def test_pull_request_branch_filter_cannot_be_retargeted(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace("branches: [main]", "branches: [never-main]", 1),
            )
            errors = validator.validate(root)
            self.assertTrue(any("branches: [main]" in error for error in errors), errors)

    def test_schedule_trigger_cannot_be_disabled_or_malformed(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace("  schedule:", "  schedule: false", 1),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("exact active mappings" in error for error in errors),
                errors,
            )

    def test_manual_trigger_cannot_be_disabled(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "  workflow_dispatch:", "  workflow_dispatch: false", 1
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("exact active mappings" in error for error in errors),
                errors,
            )

    def test_concurrency_cannot_cross_cancel_other_refs(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "  group: ${{ github.workflow }}-${{ github.ref }}",
                    "  group: global-hf-proof",
                    1,
                ).replace("  cancel-in-progress: true", "  cancel-in-progress: false", 1),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("exact per-workflow/ref contract" in error for error in errors),
                errors,
            )

    def test_unconsumed_nested_yaml_cannot_change_semantics(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "  contents: read",
                    "  contents: read\n    malformed-child: write",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("audited canonical contract" in error for error in errors),
                errors,
            )

    def test_protected_base_cannot_be_replaced_by_candidate_head(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "${{ github.event.pull_request.base.sha }}",
                    "${{ github.event.pull_request.head.sha }}",
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any(
                    "exact PR base" in error or "bind the exact PR base" in error
                    for error in errors
                ),
                errors,
            )

    def test_protected_base_job_forbids_continue_on_error(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "    timeout-minutes: 15\n    steps:",
                    "    timeout-minutes: 15\n    continue-on-error: true\n    steps:",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("continue-on-error" in error for error in errors), errors)

    def test_protected_base_parity_command_cannot_mask_failure(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "--report-out hf-current-base-parity.out.json",
                    "--report-out hf-current-base-parity.out.json || true",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("exact fail-closed command" in error for error in errors),
                errors,
            )

    def test_protected_base_proof_steps_cannot_be_disabled(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "      - name: Prove stable immutable deployed-base repository parity\n"
                    "        env:",
                    "      - name: Prove stable immutable deployed-base repository parity\n"
                    "        if: false\n"
                    "        env:",
                    1,
                ).replace(
                    "      - name: Upload immutable deployed-base proof\n"
                    "        if: always()",
                    "      - name: Upload immutable deployed-base proof\n"
                    "        if: false",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("parity step fields" in error for error in errors),
                errors,
            )
            self.assertTrue(
                any("proof upload step fields" in error for error in errors),
                errors,
            )

    def test_unnamed_checkout_cannot_replace_protected_base(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "      - name: Prove stable immutable deployed-base repository parity",
                    "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n"
                    "        with:\n"
                    "          path: baseline\n"
                    "          ref: ${{ github.event.pull_request.head.sha }}\n"
                    "          persist-credentials: false\n\n"
                    "      - name: Prove stable immutable deployed-base repository parity",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("exact ordered contract" in error for error in errors),
                errors,
            )

    def test_unnamed_run_cannot_rewrite_protected_verifier(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "      - name: Prove stable immutable deployed-base repository parity",
                    "      - run: echo replacement > baseline/.github/scripts/verify_hf_repository_parity.py\n\n"
                    "      - name: Prove stable immutable deployed-base repository parity",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(
                any("exact ordered contract" in error for error in errors),
                errors,
            )

    def test_quoted_control_keys_cannot_disable_proof(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "      - name: Prove stable immutable deployed-base repository parity\n"
                    "        env:",
                    "      - name: Prove stable immutable deployed-base repository parity\n"
                    "        \"if\": false\n"
                    "        \"continue-on-error\": true\n"
                    "        env:",
                    1,
                ).replace(
                    "      - name: Upload immutable deployed-base proof\n"
                    "        if: always()",
                    "      - name: Upload immutable deployed-base proof\n"
                    "        \"if\": false\n"
                    "        if: always()",
                    1,
                ),
            )
            errors = validator.validate(root)
            noncanonical = [
                error for error in errors if "noncanonical workflow mapping" in error
            ]
            self.assertGreaterEqual(len(noncanonical), 3, errors)

    def test_source_bound_contract_cannot_be_replaced_by_direct_mode(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "      mode: source-bound-baseline",
                    "      mode: direct",
                    1,
                ),
            )
            self.assertTrue(
                any("source-bound contract" in error for error in validator.validate(root))
            )

    def test_unpinned_reusable_workflow_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    f"reusable-hf-module-drift-check.yml@{validator.TOOLS_REVISION}",
                    "reusable-hf-module-drift-check.yml@main",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("40-hex" in error for error in errors), errors)

    def test_permissions_expansion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace(
                    "permissions:\n  contents: read",
                    "permissions:\n  contents: write",
                    1,
                ),
            )
            errors = validator.validate(root)
            self.assertTrue(any("permissions must be exactly" in error for error in errors))

    def test_bom_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_bytes(b"\xef\xbb\xbfvalid")
            self.assertTrue(
                any("BOM is forbidden" in error for error in validator.validate(root))
            )

    def _legacy_mojibake_fixture(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.assertEqual(validator.validate(root), [])
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text("broken â€” Î› Â©", encoding="utf-8")
            errors = validator.validate(root)
            self.assertTrue(any("mojibake sequence" in error for error in errors), errors)

    def test_mojibake_fails_but_multilingual_unicode_passes(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.assertEqual(validator.validate(root), [])
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text(
                "broken \u00e2\u20ac\u201d \u00ce\u203a \u00c2\u00a9",
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertTrue(any("reversible CP1252/UTF-8" in error for error in errors), errors)

    def test_common_latin_mojibake_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text(
                "broken Espa\u00c3\u00b1ol and fran\u00c3\u00a7ais",
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertTrue(any("reversible CP1252/UTF-8" in error for error in errors), errors)

    def test_accepted_divergence_for_monitored_file_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            key = validator.PUBLIC_UTF8_PATHS[0].as_posix()
            self.write_allowlist(
                root,
                {
                    "ignore_paths": [],
                    "ignore_extensions": [],
                    "accepted_divergences": {key: "must not bypass"},
                },
            )
            self.assertTrue(
                any("cannot bypass HF parity" in error for error in validator.validate(root))
            )

    def test_ignore_path_pattern_for_monitored_file_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_allowlist(
                root,
                {
                    "ignore_paths": ["pages/**"],
                    "ignore_extensions": [],
                    "accepted_divergences": {},
                },
            )
            errors = validator.validate(root)
            self.assertTrue(any("ignore_paths pattern" in error for error in errors), errors)

    def test_ignore_extension_is_case_insensitive_and_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            self.write_allowlist(
                root,
                {
                    "ignore_paths": [],
                    "ignore_extensions": [".HTML"],
                    "accepted_divergences": {},
                },
            )
            errors = validator.validate(root)
            self.assertTrue(any("ignore_extensions entry" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
