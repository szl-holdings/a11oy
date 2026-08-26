"""Adversarial tests for the protected Frontier source-pin validator."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_frontier_protected_source_pins.py"
WORKFLOW_PATH = ROOT / ".github/workflows/frontier-protected-source-pins.yml"
SPEC = importlib.util.spec_from_file_location("frontier_protected_pins", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ProtectedSourcePinTests(unittest.TestCase):
    def make_bundle(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        sources = {
            validator.CONTRACT: b'{"contract":"candidate data only"}\n',
            validator.REPAIR_SCRIPT: (
                b"raise SystemExit('candidate repair script must never execute')\n"
            ),
            validator.SOURCE_TEST: (
                b"raise SystemExit('candidate source test must never execute')\n"
            ),
        }
        pins = {
            name: digest(sources[path]) for name, path in validator.PIN_NAMES.items()
        }
        declarations = "\n".join(
            f"      {name}_SHA256: {value}" for name, value in pins.items()
        )
        solo = f"""name: fixture
on:
  pull_request:
  merge_group:
jobs:
  platform-solo-qualification:
    env:
{declarations}
    steps:
      - name: Fixture
        run: |
          verify_protected_material() {{
            test "$observed_repair_digest" = "$REPAIR_SCRIPT_SHA256"
            test "$contract_digest" = "$CONTRACT_SHA256"
          }}
          validate_pull_request() {{
            verify_protected_material "$base_sha"
            test "$test_digest" = "$SOURCE_TEST_SHA256"
          }}
          validate_merge_group() {{
            verify_protected_material "$base_sha"
            test "$test_digest" = "$SOURCE_TEST_SHA256"
          }}
          case "$EVENT_NAME" in
            pull_request) validate_pull_request ;;
            merge_group) validate_merge_group ;;
            *) echo "unsupported event: $EVENT_NAME" >&2; exit 2 ;;
          esac
"""
        builder = f"""name: fixture
on:
  issues:
jobs:
  build-exact-source:
    env:
{declarations}
    steps:
      - name: Fixture
        run: |
          test "$contract" = "$CONTRACT_SHA256"
          test "$(sha256sum "$repair_script" | awk '{{print $1}}')" = "$REPAIR_SCRIPT_SHA256"
          test "$(sha256sum "$source_test" | awk '{{print $1}}')" = "$SOURCE_TEST_SHA256"
"""
        sources[validator.SOLO_WORKFLOW] = solo.encode()
        sources[validator.BUILDER_WORKFLOW] = builder.encode()
        for relative, data in sources.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return temp, root

    def replace_once(self, root: Path, relative: str, old: str, new: str) -> None:
        path = root / relative
        source = path.read_text(encoding="utf-8")
        self.assertEqual(source.count(old), 1)
        path.write_text(source.replace(old, new, 1), encoding="utf-8")

    def assert_invalid(self, root: Path, message: str) -> None:
        with self.assertRaisesRegex(validator.ValidationError, message):
            validator.validate(root)

    def test_valid_bundle_passes_without_executing_candidate_python(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            marker = root / "candidate-executed"
            os.environ["FRONTIER_CANDIDATE_MARKER"] = str(marker)
            observed = validator.validate(root)
            self.assertEqual(set(observed), set(validator.PIN_NAMES))
            self.assertFalse(marker.exists())

    def test_each_wrong_digest_fails(self) -> None:
        for name in validator.PIN_NAMES:
            with self.subTest(name=name):
                temp, root = self.make_bundle()
                with temp:
                    workflow = validator.SOLO_WORKFLOW
                    path = root / workflow
                    source = path.read_text(encoding="utf-8")
                    old = next(
                        line
                        for line in source.splitlines()
                        if line.startswith(f"      {name}_SHA256:")
                    )
                    self.replace_once(
                        root,
                        workflow,
                        old,
                        f"      {name}_SHA256: {'0' * 64}",
                    )
                    self.assert_invalid(root, f"{name}_SHA256")

    def test_duplicate_declaration_fails(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            path = root / validator.SOLO_WORKFLOW
            source = path.read_text(encoding="utf-8")
            line = next(
                row
                for row in source.splitlines()
                if row.startswith("      CONTRACT_SHA256:")
            )
            path.write_text(source + line + "\n", encoding="utf-8")
            self.assert_invalid(root, "expected one CONTRACT_SHA256")

    def test_orphan_digest_fails_at_any_indentation(self) -> None:
        for indentation in ("", "  ", "\t"):
            with self.subTest(indentation=repr(indentation)):
                temp, root = self.make_bundle()
                with temp:
                    path = root / validator.SOLO_WORKFLOW
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(f"{indentation}$" + "a" * 65 + "\n")
                    self.assert_invalid(root, "orphan digest-like")

    def test_pull_request_comparison_removal_fails(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            self.replace_once(
                root,
                validator.SOLO_WORKFLOW,
                '            test "$test_digest" = "$SOURCE_TEST_SHA256"\n'
                "          }\n"
                "          validate_merge_group",
                "            true\n"
                "          }\n"
                "          validate_merge_group",
            )
            self.assert_invalid(root, "validate_pull_request source-test comparison")

    def test_merge_group_comparison_removal_fails(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            path = root / validator.SOLO_WORKFLOW
            source = path.read_text(encoding="utf-8")
            marker = "          validate_merge_group() {"
            start = source.index(marker)
            before, block = source[:start], source[start:]
            block = block.replace(
                '            test "$test_digest" = "$SOURCE_TEST_SHA256"',
                "            true",
                1,
            )
            path.write_text(before + block, encoding="utf-8")
            self.assert_invalid(root, "validate_merge_group source-test comparison")

    def test_protected_material_call_removal_fails(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            self.replace_once(
                root,
                validator.SOLO_WORKFLOW,
                '            verify_protected_material "$base_sha"\n'
                '            test "$test_digest" = "$SOURCE_TEST_SHA256"\n'
                "          }\n"
                "          validate_merge_group",
                '            test "$test_digest" = "$SOURCE_TEST_SHA256"\n'
                "          }\n"
                "          validate_merge_group",
            )
            self.assert_invalid(root, "protected-material call")

    def test_dead_pull_request_handler_fails(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            self.replace_once(
                root,
                validator.SOLO_WORKFLOW,
                "            pull_request) validate_pull_request ;;",
                "            pull_request) true ;;",
            )
            self.assert_invalid(root, "pull-request dispatcher")

    def test_each_builder_comparison_removal_fails(self) -> None:
        tokens = (
            '          test "$contract" = "$CONTRACT_SHA256"',
            '          test "$(sha256sum "$repair_script" | awk '
            "'{print $1}')\" = \"$REPAIR_SCRIPT_SHA256\"",
            '          test "$(sha256sum "$source_test" | awk '
            "'{print $1}')\" = \"$SOURCE_TEST_SHA256\"",
        )
        for token in tokens:
            with self.subTest(token=token):
                temp, root = self.make_bundle()
                with temp:
                    self.replace_once(
                        root, validator.BUILDER_WORKFLOW, token, "          true"
                    )
                    self.assert_invalid(root, "comparison")

    def test_missing_and_symlinked_managed_files_fail(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            (root / validator.CONTRACT).unlink()
            self.assert_invalid(root, "absent or not a regular file")

        temp, root = self.make_bundle()
        with temp:
            path = root / validator.CONTRACT
            path.unlink()
            path.symlink_to(root / validator.REPAIR_SCRIPT)
            self.assert_invalid(root, "absent or not a regular file")

    def test_oversized_candidate_fails(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            (root / validator.CONTRACT).write_bytes(
                b"x" * (validator.MAX_FILE_BYTES + 1)
            )
            self.assert_invalid(root, "exceeds")

    def test_cli_is_fail_closed(self) -> None:
        temp, root = self.make_bundle()
        with temp:
            passed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(VALIDATOR_PATH),
                    "--bundle-dir",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(passed.returncode, 0, passed.stderr)
            (root / validator.CONTRACT).unlink()
            failed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(VALIDATOR_PATH),
                    "--bundle-dir",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("FAIL", failed.stderr)

    def test_workflow_uses_protected_base_and_never_executes_head(self) -> None:
        source = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("  pull_request_target:", source)
        self.assertNotIn("\n  pull_request:\n", source)
        self.assertIn("  checks: write", source)
        self.assertNotIn("  statuses: write", source)
        self.assertIn(
            "ref: ${{ github.event.pull_request.base.sha }}",
            source,
        )
        self.assertIn("persist-credentials: false", source)
        self.assertNotIn(
            "ref: ${{ github.event.pull_request.head.sha }}",
            source,
        )
        self.assertNotIn("actions/setup-python", source)
        self.assertNotIn("pip install", source)
        self.assertIn(
            "python3 -I -B scripts/validate_frontier_protected_source_pins.py",
            source,
        )
        self.assertIn(
            "CHECK_NAME: Frontier protected-base source-pin qualification",
            source,
        )
        self.assertIn('"repos/${REPOSITORY}/check-runs"', source)
        self.assertIn(
            '"repos/${REPOSITORY}/check-runs/'
            '${CHECK_ID}"',
            source,
        )
        self.assertIn('conclusion="failure"', source)
        self.assertIn('test "$conclusion" = "success"', source)


if __name__ == "__main__":
    unittest.main()
