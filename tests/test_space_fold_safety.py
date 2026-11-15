#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline containment regressions. No provider client or network is used."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/fold_space.py"
WORKFLOW = ROOT / ".github/workflows/execute-space-fold.yml"
TARGET = "SZLHOLDINGS/yarqa"
CONFIRM = "FOLD-SZLHOLDINGS-YARQA"
SHA = "a" * 40


def load_controller():
    # A real HF client must never be imported by this offline suite.
    stub = types.ModuleType("huggingface_hub")
    stub.HfApi = mock.Mock(side_effect=AssertionError("provider access forbidden"))
    stub.hf_hub_download = mock.Mock(side_effect=AssertionError("download forbidden"))
    spec = importlib.util.spec_from_file_location("fold_safety_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"huggingface_hub": stub}):
        spec.loader.exec_module(module)
    return module


def run_block(name: str) -> str:
    """Read this workflow's literal bash block without a YAML dependency."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"      - name: {name}") + 1
    while start < len(lines) and lines[start] != "        run: |":
        if lines[start].startswith("      - name:"):
            raise AssertionError(f"missing literal run block: {name}")
        start += 1
    result = []
    for line in lines[start + 1:]:
        if line and not line.startswith("          "):
            break
        result.append(line[10:] if line else "")
    return "\n".join(result) + "\n"


class FoldInputBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fold-input-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "publishing").mkdir()
        self.registry = self.root / "publishing/space-fold-registry.json"
        self.registry.write_text(json.dumps({"targets": [{"space_id": TARGET, "status": "pending"}]}))
        self.before = self.registry.read_bytes()
        self.output = self.root / "output"
        self.env = {
            "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
            "FOLD_SPACE_ID": TARGET,
            "FOLD_CONFIRM": CONFIRM,
            "FOLD_DRY_RUN": "true",
            "GITHUB_OUTPUT": str(self.output),
            "PYTHONOPTIMIZE": "1",
        }

    def validate(self, **values):
        env = dict(self.env, **values)
        script = run_block("Validate dispatch inputs against the registry")
        self.assertNotIn("${{", script)
        return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                              env=env, cwd=self.root, capture_output=True, text=True, timeout=10)

    def test_run_blocks_have_no_expression_interpolation(self):
        for name in ("Validate dispatch inputs against the registry", "Execute bounded fold",
                     "Enforce proved terminal state"):
            with self.subTest(name=name):
                self.assertNotIn("${{", run_block(name))
        workflow = WORKFLOW.read_text()
        for field in ("FOLD_SPACE_ID: ${{ inputs.space_id }}",
                      "FOLD_CONFIRM: ${{ inputs.confirm }}",
                      "FOLD_DRY_RUN: ${{ inputs.dry_run }}"):
            self.assertEqual(workflow.count(field), 2)

    def test_validated_slug_written_only_after_all_checks(self):
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), "slug=yarqa\n")
        self.assertEqual(self.registry.read_bytes(), self.before)

    def test_injection_shaped_values_are_data_and_leave_no_output(self):
        payloads = ["'; touch injected; #", '"; touch injected; #',
                    "$(touch injected)", "`touch injected`", "\nslug=other\n",
                    "'; __import__('pathlib').Path('injected').touch(); #"]
        for field in ("FOLD_SPACE_ID", "FOLD_CONFIRM"):
            for payload in payloads:
                with self.subTest(field=field, payload=payload):
                    result = self.validate(**{field: payload})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(self.output.exists())
                    self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["publishing"])
                    self.assertEqual(self.registry.read_bytes(), self.before)

    def test_whitespace_unknown_target_wrong_confirmation_and_bad_boolean_reject(self):
        cases = [{"FOLD_SPACE_ID": TARGET + "\n"}, {"FOLD_SPACE_ID": " " + TARGET},
                 {"FOLD_SPACE_ID": "SZLHOLDINGS/unknown"}, {"FOLD_CONFIRM": CONFIRM + "\n"},
                 {"FOLD_CONFIRM": "wrong"}, {"FOLD_DRY_RUN": ""},
                 {"FOLD_DRY_RUN": "TRUE"}, {"FOLD_DRY_RUN": "$(touch injected)"}]
        for case in cases:
            with self.subTest(case=case):
                self.assertNotEqual(self.validate(**case).returncode, 0)
                self.assertFalse(self.output.exists())
                self.assertFalse((self.root / "injected").exists())

    def test_execution_step_passes_arguments_as_data_and_preserves_failure(self):
        # Exercise only bash argument construction, using a local recording stub.
        # The controller, provider, and fixed /tmp report path are never invoked.
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        python = bin_dir / "python"
        python.write_text(f"#!{sys.executable}\nimport json,sys\n"
                          "from pathlib import Path\n"
                          "Path('argv.json').write_text(json.dumps(sys.argv[1:]))\n"
                          "raise SystemExit(7)\n")
        python.chmod(0o700)
        payload = "'; touch injected; #\n$(touch injected)"
        env = dict(self.env, PATH=str(bin_dir) + os.pathsep + os.defpath,
                   FOLD_SPACE_ID=payload, FOLD_CONFIRM=payload)
        script = run_block("Execute bounded fold")
        self.assertNotIn("${{", script)
        result = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                                env=env, cwd=self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / "argv.json").read_text())
        self.assertEqual(args[args.index("--space-id") + 1], payload)
        self.assertEqual(args[args.index("--confirm") + 1], payload)
        self.assertIn("--dry-run", args)
        self.assertEqual(self.output.read_text(), "exit_code=7\n")
        self.assertFalse((self.root / "injected").exists())


class FoldReviewContainment(unittest.TestCase):
    def setUp(self):
        self.controller = load_controller()

    def invoke(self, target, *, dry_run=False, confirm=None):
        with tempfile.TemporaryDirectory(prefix="fold-main-test-") as tmp:
            path = Path(tmp) / "report.json"
            argv = [str(SCRIPT), "--repo-root", str(ROOT), "--report", str(path),
                    "--space-id", target,
                    "--confirm", confirm if confirm is not None else self.controller.confirmation_for(target)]
            if dry_run:
                argv.append("--dry-run")
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.dict(os.environ, {"HF_TOKEN": "offline-unit-test"}, clear=True), \
                    mock.patch.object(self.controller, "_get", side_effect=AssertionError("network forbidden")) as get, \
                    contextlib.redirect_stdout(io.StringIO()):
                code = self.controller.main()
            get.assert_not_called()
            self.controller.HfApi.assert_not_called()
            return code, json.loads(path.read_text())

    def test_every_pending_target_blocks_before_any_provider_access(self):
        registry = json.loads((ROOT / "publishing/space-fold-registry.json").read_text())
        for entry in registry["targets"]:
            for dry_run in (False, True):
                with self.subTest(target=entry["space_id"], dry_run=dry_run):
                    code, report = self.invoke(entry["space_id"], dry_run=dry_run)
                    self.assertEqual(code, 1)
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assertIn(entry["review_gate"], report["error"])
                    self.assertIn("pending inventory is not authorization", report["error"])
                    for field in ("deleted", "paused", "made_private", "token_recorded", "secret_values_read"):
                        self.assertIs(report[field], False)

    def test_missing_malformed_unknown_and_self_asserted_review_never_unlock(self):
        entries = [{}, {"review_gate": None}, {"review_gate": {}}, {"review_gate": ""},
                   {"review_gate": " "}, {"review_gate": "unknown"},
                   {"review_gate": "complete_fold", "approved": True, "review_complete": True,
                    "authorization": {"target": TARGET, "sha": SHA, "approved": True},
                    "evidence_url": "https://example.invalid/review"}]
        for entry in entries:
            with self.subTest(entry=entry):
                with self.assertRaises(self.controller.FoldError):
                    self.controller.prove_review_prerequisites(entry)

    def test_invalid_cli_inputs_and_keep_targets_cannot_access_provider(self):
        for target, confirm in [(TARGET + "\n", None), ("SZLHOLDINGS/immune", None),
                                ("SZLHOLDINGS/vertical-services", None),
                                ("SZLHOLDINGS/unknown", None), (TARGET, "wrong")]:
            with self.subTest(target=target, confirm=confirm):
                code, report = self.invoke(target, confirm=confirm)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "BLOCKED")
                if target.endswith("\n"):
                    self.assertIn("invalid space id", report["error"])


class FoldCaptureEvidence(unittest.TestCase):
    def setUp(self):
        self.controller = load_controller()
        self.api = mock.Mock()
        self.api.repo_exists.return_value = True
        self.api.space_info.return_value = types.SimpleNamespace(sha=SHA, sdk="docker", private=False)
        self.api.list_repo_files.return_value = ["app.py", "README.md"]

    def assert_no_mutations(self):
        for name in ("pause_space", "update_repo_settings", "delete_repo"):
            getattr(self.api, name).assert_not_called()

    def test_readme_download_failure_is_fatal_without_leaking_exception_data(self):
        for error in (OSError("offline-unit-test"), TimeoutError("offline-unit-test"),
                      FileNotFoundError("offline-unit-test"), PermissionError("offline-unit-test")):
            with self.subTest(error=type(error).__name__):
                self.controller.hf_hub_download.side_effect = error
                with self.assertRaises(self.controller.FoldError) as caught:
                    self.controller.capture_target(self.api, "offline-unit-test", TARGET)
                self.assertIn("required README capture failed", str(caught.exception))
                self.assertNotIn("offline-unit-test", str(caught.exception))
                self.assert_no_mutations()

    def test_readme_read_failure_is_fatal(self):
        with tempfile.TemporaryDirectory(prefix="fold-missing-readme-") as tmp:
            self.controller.hf_hub_download.side_effect = None
            self.controller.hf_hub_download.return_value = str(Path(tmp) / "missing.md")
            with self.assertRaises(self.controller.FoldError):
                self.controller.capture_target(self.api, "offline-unit-test", TARGET)
        self.assert_no_mutations()

    def test_file_listing_failure_is_fatal(self):
        self.api.list_repo_files.side_effect = OSError("offline")
        with self.assertRaises(OSError):
            self.controller.capture_target(self.api, "offline-unit-test", TARGET)
        self.controller.hf_hub_download.assert_not_called()
        self.assert_no_mutations()

    def test_capture_rejects_missing_or_malformed_immutable_revision(self):
        for sha in (None, "", "main", "a" * 39, "a" * 40 + "\n", True):
            with self.subTest(sha=sha):
                self.api.space_info.return_value.sha = sha
                with self.assertRaises(self.controller.FoldError):
                    self.controller.capture_target(self.api, "offline-unit-test", TARGET)
        self.api.list_repo_files.assert_not_called()
        self.controller.hf_hub_download.assert_not_called()
        self.assert_no_mutations()

    def test_capture_is_revision_pinned_and_digest_matches_read_bytes(self):
        content = b"# Offline fixture\n"
        def download(**kwargs):
            self.assertEqual(kwargs["revision"], SHA)
            path = Path(kwargs["local_dir"]) / "README.md"
            path.write_bytes(content)
            return str(path)
        self.controller.hf_hub_download.side_effect = download
        record = self.controller.capture_target(self.api, "offline-unit-test", TARGET)
        self.api.list_repo_files.assert_called_once_with(TARGET, repo_type="space", revision=SHA,
                                                        token="offline-unit-test")
        self.assertEqual(record["sha"], SHA)
        self.assertEqual(record["readme_sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(record["readme_bytes"], len(content))
        self.assertEqual(record["files"], ["README.md", "app.py"])
        self.assert_no_mutations()

    def test_absent_target_needs_no_capture_or_mutation(self):
        self.api.repo_exists.return_value = False
        self.assertEqual(self.controller.capture_target(self.api, "offline-unit-test", TARGET),
                         {"existed": False, "already_absent": True})
        self.api.space_info.assert_not_called()
        self.controller.hf_hub_download.assert_not_called()
        self.assert_no_mutations()


if __name__ == "__main__":
    unittest.main()
