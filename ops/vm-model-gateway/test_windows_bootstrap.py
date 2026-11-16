#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Subprocess regressions for private bootstrap failure diagnostics."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


BOOTSTRAP = Path(__file__).with_name("windows-bootstrap.py")
CANARY = "fixture-private-value-must-not-appear-in-bootstrap-output"


class BootstrapTests(unittest.TestCase):
    def run_bootstrap(self, supervisor_source):
        with tempfile.TemporaryDirectory(prefix="szl-bootstrap-test-") as directory:
            root = Path(directory)
            (root / "logs").mkdir()
            shutil.copyfile(BOOTSTRAP, root / BOOTSTRAP.name)
            (root / "windows-supervisor.py").write_text(
                supervisor_source, encoding="utf-8")
            env = {
                name: os.environ[name]
                for name in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
                if name in os.environ
            }
            env["BOOTSTRAP_TEST_SECRET"] = CANARY
            result = subprocess.run(
                [sys.executable, "-I", "-B", str(root / BOOTSTRAP.name)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            errors = list((root / "logs").glob("*-supervisor.stderr"))
            outputs = list((root / "logs").glob("*-supervisor.stdout"))
            self.assertEqual(len(errors), 1)
            self.assertEqual(len(outputs), 1)
            private_error = errors[0].read_text(encoding="utf-8")
            private_output = outputs[0].read_text(encoding="utf-8")
            return result, private_error, private_output

    def assert_failure(self, source, code, exit_code=1):
        result, private_error, private_output = self.run_bootstrap(source)
        self.assertEqual(result.returncode, exit_code)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(private_output, "")
        self.assertEqual(
            json.loads(private_error),
            {
                "schema": "szl.vm-model-bootstrap-failure/v1",
                "failure_code": code,
                "signed": False,
            },
        )
        self.assertEqual(len(private_error.splitlines()), 1)
        self.assertNotIn(CANARY, private_error)
        return private_error

    def test_known_preflight_refusals_are_logged_without_changing_failure(self):
        cases = {
            "Pinned source mismatch": "SOURCE_PIN_MISMATCH",
            "Pinned SSH configuration mismatch": "SSH_CONFIG_PIN_MISMATCH",
            "Existing listener preserved; startup refused": "EXISTING_LISTENER_PRESERVED",
            "Invalid private gateway credential": "INVALID_GATEWAY_CREDENTIAL",
        }
        for message, code in cases.items():
            with self.subTest(code=code):
                private_error = self.assert_failure(
                    "raise SystemExit(" + repr(message) + ")\n", code)
                self.assertNotIn(message, private_error)

    def test_normal_completion_and_successful_system_exit_are_clean(self):
        for source in ("pass\n", "raise SystemExit\n",
                       "raise SystemExit(0)\n", "raise SystemExit(False)\n"):
            with self.subTest(source=source):
                result, private_error, private_output = self.run_bootstrap(source)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    (result.stdout, result.stderr, private_error, private_output),
                    ("", "", "", ""),
                )

    def test_numeric_failure_exit_is_preserved(self):
        self.assert_failure("raise SystemExit(7)\n", "NONZERO_SYSTEM_EXIT", 7)

    def test_unknown_system_exit_does_not_escape_to_outer_stderr(self):
        self.assert_failure(
            "import os\nraise SystemExit(os.environ['BOOTSTRAP_TEST_SECRET'])\n",
            "UNCLASSIFIED_SYSTEM_EXIT",
        )

    def test_non_string_system_exit_is_not_rendered(self):
        self.assert_failure(
            "import os\nraise SystemExit({'private': os.environ['BOOTSTRAP_TEST_SECRET']})\n",
            "UNCLASSIFIED_SYSTEM_EXIT",
        )

    def test_unexpected_exception_does_not_log_message_or_traceback(self):
        private_error = self.assert_failure(
            "import os\nraise RuntimeError(os.environ['BOOTSTRAP_TEST_SECRET'])\n",
            "SUPERVISOR_EXCEPTION",
        )
        self.assertNotIn("RuntimeError", private_error)
        self.assertNotIn("Traceback", private_error)


if __name__ == "__main__":
    unittest.main()
