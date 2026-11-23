"""Offline synthetic Lean 4 diagnostic parsing regression tests."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("lean_axiom_gate.py")
spec = importlib.util.spec_from_file_location("lean_axiom_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class AxiomDiagnosticTests(unittest.TestCase):
    def run_gate(self, lean_output):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            (root / "Proof.lean").write_text(
                "theorem Clean : True := by trivial\n", encoding="utf-8"
            )
            result = subprocess.CompletedProcess(
                args=["lean"], returncode=0, stdout=lean_output, stderr=""
            )
            stdout = io.StringIO()
            with mock.patch.object(gate.subprocess, "run", return_value=result), \
                 mock.patch.object(sys, "argv", ["gate", str(root), "--no-lake"]), \
                 contextlib.redirect_stdout(stdout):
                try:
                    gate.main()
                except SystemExit as exc:
                    return exc.code or 1, stdout.getvalue()
            return 0, stdout.getvalue()

    def test_info_prefix_clean_proof_passes(self):
        rc, output = self.run_gate(
            "/tmp/Proof.lean:5:0: info: 'Clean' does not depend on any axioms\n"
        )
        self.assertEqual(rc, 0, output)
        self.assertIn("GATE OK", output)

    def test_info_prefix_allowed_axioms_pass(self):
        rc, output = self.run_gate(
            "/tmp/Proof.lean:5:0: info: 'Clean' depends on axioms: "
            "[propext, Classical.choice]\n"
        )
        self.assertEqual(rc, 0, output)
        self.assertIn("'propext': 1", output)

    def test_disallowed_axiom_still_fails_closed(self):
        rc, output = self.run_gate(
            "/tmp/Proof.lean:5:0: info: 'Clean' depends on axioms: [sorryAx]\n"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("depends on sorryAx", output)

    def test_warning_cannot_impersonate_kernel_info(self):
        rc, output = self.run_gate(
            "/tmp/Proof.lean:5:0: warning: 'Clean' does not depend on any axioms\n"
        )
        self.assertNotEqual(rc, 0)
        self.assertIn("kernel gave no axiom report", output)


if __name__ == "__main__":
    unittest.main()
