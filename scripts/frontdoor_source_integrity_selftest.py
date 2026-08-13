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

    def test_01(self) -> None:
        """The honest fixture passes."""
        temp, root = self.make_fixture()
        with temp:
            self.assertEqual(validator.validate(root), [])

    def test_02(self) -> None:
        """A one-line commented workflow fails."""
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

    def test_03(self) -> None:
        """A NUL hidden in a comment fails before comment stripping."""
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

    def test_04(self) -> None:
        """A C1 control hidden in a comment fails before stripping."""
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

    def test_05(self) -> None:
        """Commented job keys fail even when tokens remain."""
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

    def test_06(self) -> None:
        """A commented uses field fails even when its token remains."""
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

    def test_07(self) -> None:
        """A commented job condition fails."""
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

    def test_08(self) -> None:
        """The pull-request branch filter cannot be retargeted."""
        temp, root = self.make_fixture()
        with temp:
            self.write_workflow(
                root,
                lambda text: text.replace("branches: [main]", "branches: [never-main]", 1),
            )
            errors = validator.validate(root)
            self.assertTrue(any("branches: [main]" in error for error in errors), errors)

    def test_09(self) -> None:
        """The schedule trigger cannot be disabled or malformed."""
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

    def test_10(self) -> None:
        """The manual trigger cannot be disabled."""
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

    def test_11(self) -> None:
        """Concurrency cannot cross-cancel another ref."""
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

    def test_12(self) -> None:
        """Unconsumed nested YAML cannot change semantics."""
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

    def test_13(self) -> None:
        """The protected base cannot be replaced by the candidate head."""
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

    def test_14(self) -> None:
        """The protected-base job forbids continue-on-error."""
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

    def test_15(self) -> None:
        """The protected-base parity command cannot mask failure."""
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

    def test_16(self) -> None:
        """The protected-base proof steps cannot be disabled."""
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

    def test_17(self) -> None:
        """An unnamed checkout cannot replace the protected base."""
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

    def test_18(self) -> None:
        """An unnamed run step cannot rewrite the protected verifier."""
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

    def test_19(self) -> None:
        """Quoted control keys cannot disable proof."""
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

    def test_20(self) -> None:
        """The source-bound contract cannot be replaced by direct mode."""
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

    def test_21(self) -> None:
        """An unpinned reusable workflow fails."""
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

    def test_22(self) -> None:
        """Workflow permission expansion fails."""
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

    def test_23(self) -> None:
        """A UTF-8 BOM fails."""
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

    def test_24(self) -> None:
        """Mojibake fails while multilingual Unicode passes."""
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

    def test_25(self) -> None:
        """Common Latin mojibake fails."""
        temp, root = self.make_fixture()
        with temp:
            target = root / validator.PUBLIC_UTF8_PATHS[0]
            target.write_text(
                "broken Espa\u00c3\u00b1ol and fran\u00c3\u00a7ais",
                encoding="utf-8",
            )
            errors = validator.validate(root)
            self.assertTrue(any("reversible CP1252/UTF-8" in error for error in errors), errors)

    def test_26(self) -> None:
        """An accepted divergence for a monitored file fails."""
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

    def test_27(self) -> None:
        """An ignore-path pattern for a monitored file fails."""
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

    def test_28(self) -> None:
        """An ignored extension is case-insensitive and fails."""
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
