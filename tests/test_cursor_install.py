#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the installer control flow without network or system changes."""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CursorInstallTests(unittest.TestCase):
    def run_install(self, version="0.4.0", failure="", optimize="",
                    locked=('F1','F4','F7','F11','F12','F18','F19','F22'),
                    envelope="doctrine-v11/E1-E10"):
        with tempfile.TemporaryDirectory(prefix="cursor install ") as tmp:
            root = Path(tmp)
            (root / ".cursor").mkdir()
            bin_dir = root / ".venv/bin"
            bin_dir.mkdir(parents=True)
            shutil.copy(ROOT / ".cursor/install.sh", root / ".cursor/install.sh")
            shutil.copy(ROOT / "requirements-runtime.txt", root / "requirements-runtime.txt")
            (bin_dir / "activate").write_text(
                f"export PATH={shlex.quote(str(bin_dir))}:$PATH\n"
            )
            # pip/pnpm are effect boundaries; Nemo's identity check uses
            # a real Python interpreter with a controlled module fixture.
            stub = f"#!{sys.executable}\n" + """
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps([pathlib.Path(sys.argv[0]).name, *args]) + '\\n')
if pathlib.Path(sys.argv[0]).name == 'pnpm':
    sys.exit(0)
if args[:2] == ['-m', 'pip']:
    fail = os.environ.get('FAIL_INSTALL', '')
    sys.exit(19 if fail and any(fail in arg for arg in args) else 0)
os.execv(sys.executable, [sys.executable, *args])
"""
            for name in ("python", "pnpm"):
                target = bin_dir / name
                target.write_text(stub)
                target.chmod(0o755)
            (root / "szl_nemo.py").write_text(
                f"__version__ = {version!r}\n"
                f"LOCKED_PROVEN_FORMULA_IDS = {locked!r}\n"
                f"ENVELOPE_RULE_VERSION = {envelope!r}\n"
            )
            log = root / "calls.jsonl"
            env = dict(os.environ, CALL_LOG=str(log), FAIL_INSTALL=failure,
                       PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE="1",
                       PYTHONOPTIMIZE=optimize)
            result = subprocess.run(
                ["bash", str(root / ".cursor/install.sh")], env=env,
                capture_output=True, text=True, timeout=30,
            )
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            return result, calls

    def test_canonical_requirements_and_image_witness_reach_node_setup(self):
        result, calls = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = [c for c in calls if "-r" in c]
        self.assertEqual(len(runtime), 1)
        self.assertTrue(runtime[0][runtime[0].index("-r") + 1].endswith("/requirements-runtime.txt"))
        image_pin = re.search(r'https://github.com/szl-holdings/szl-nemo/archive/[0-9a-f]{40}\.tar\.gz',
                              (ROOT / "Dockerfile").read_text()).group()
        self.assertIn(["python", "-m", "pip", "install", image_pin], calls)
        self.assertEqual(calls[-1], ["pnpm", "install", "--frozen-lockfile"])

    def test_wrong_witness_identity_stops_setup(self):
        result, calls = self.run_install(version="0.3.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Nemo witness identity", result.stderr)
        self.assertFalse(any(c[0] == "pnpm" for c in calls))

    def test_optimized_python_cannot_bypass_identity_check(self):
        result, calls = self.run_install(version="0.3.0", optimize="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Nemo witness identity", result.stderr)
        self.assertFalse(any(c[0] == "pnpm" for c in calls))

    def test_wrong_doctrine_identity_stops_setup(self):
        for identity in ({"locked": ("F1",)}, {"envelope": "wrong"}):
            with self.subTest(identity=identity):
                result, calls = self.run_install(**identity)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Nemo witness identity", result.stderr)
                self.assertFalse(any(c[0] == "pnpm" for c in calls))

    def test_runtime_install_failure_stops_before_witness(self):
        result, calls = self.run_install(failure="requirements-runtime.txt")
        self.assertEqual(result.returncode, 19)
        self.assertFalse(any("szl-nemo/archive" in str(c) for c in calls))
        self.assertFalse(any(c[0] == "pnpm" for c in calls))

    def test_witness_install_failure_stops_before_identity_and_node(self):
        result, calls = self.run_install(failure="szl-nemo/archive")
        self.assertEqual(result.returncode, 19)
        self.assertFalse(any("-" in c or c[0] == "pnpm" for c in calls))


if __name__ == "__main__":
    unittest.main()
