# SPDX-License-Identifier: Apache-2.0
"""Actual-scanner regression for a public source digest, never a path exclusion.

Set SZL_TEST_GITLEAKS_BINARY to the checksum-verified CI scanner executable.
Only disposable generated credentials are used; scanner output is never printed.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = os.environ.get("SZL_TEST_GITLEAKS_BINARY")
PUBLIC_DIGEST = "1ee6a88e37d522c5404ac04ac90eadcbfc6f7e59140a778d03275832e217e2cf"


CHECKER_PATH = "tools/check_copy_sync_lockstep.py"


def signing_source_row():
    # Derive the public digest rather than duplicating a scanner-looking value.
    digest = hashlib.sha256((ROOT / "a11oy_signing_key.py").read_bytes()).hexdigest()
    return '    "a11oy_signing_key.py": "' + digest + '",\n'


class ExactSourceExceptionContract(unittest.TestCase):
    def test_exception_is_one_exact_public_row_and_path_with_and_semantics(self):
        config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        rule = next(rule for rule in config["rules"] if rule["id"] == "generic-api-key")
        self.assertEqual(set(rule), {"id", "allowlists"})
        self.assertEqual(len(rule["allowlists"]), 1)
        allow = rule["allowlists"][0]
        self.assertEqual(set(allow), {"description", "condition", "regexTarget", "paths", "regexes"})
        self.assertEqual(allow["condition"], "AND")
        self.assertEqual(allow["regexTarget"], "line")
        self.assertEqual(len(allow["paths"]), 1)
        self.assertEqual(len(allow["regexes"]), 1)
        self.assertEqual(allow["paths"], [r"^tools/check_copy_sync_lockstep\.py$"])
        line = signing_source_row()
        self.assertIn(line, (ROOT / CHECKER_PATH).read_text())
        self.assertRegex(line, allow["regexes"][0])
        self.assertIsNone(re.search(allow["regexes"][0], line.rstrip() + ' "private_api_key": "' + disposable_credential() + '"'))
        self.assertIsNone(re.search(allow["regexes"][0], line.replace(hashlib.sha256((ROOT / "a11oy_signing_key.py").read_bytes()).hexdigest(), disposable_credential())))


def disposable_credential():
    """Stable synthetic positive control; no credential bytes are committed."""
    return hashlib.sha256(b"szl-gitleaks-positive-control-v1").hexdigest()


@unittest.skipUnless(BINARY, "actual scanner not configured; NOT VERIFIED")
class PublicDigestScannerBoundary(unittest.TestCase):
    def scan(self, text, relative_path="probe.json"):
        with tempfile.TemporaryDirectory(prefix="szl-public-digest-probe-") as folder:
            target = Path(folder) / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [BINARY, "detect", "--source", ".", "--no-git",
                 "--config", str(ROOT / ".gitleaks.toml"), "--redact",
                 "--exit-code", "1", "--no-banner", "--log-level", "error"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=False, cwd=folder,
            )
            return result.returncode

    def test_verified_public_row_is_not_a_credential(self):
        self.assertEqual(self.scan(
            '{\n  "szl_operator_auth.py": "' + PUBLIC_DIGEST + '"\n}\n'), 0)

    def test_adjacent_disposable_credential_remains_detected(self):
        credential = disposable_credential()
        self.assertEqual(self.scan(
            '{\n  "szl_operator_auth.py": "' + PUBLIC_DIGEST
            + '",\n  "private_api_key": "' + credential + '"\n}\n'), 1)

    def test_same_line_disposable_credential_cannot_borrow_public_exemption(self):
        credential = disposable_credential()
        self.assertEqual(self.scan(
            '{\n  "szl_operator_auth.py": "' + PUBLIC_DIGEST
            + '", "private_api_key": "' + credential + '"\n}\n'), 1)

    def test_other_auth_named_value_is_not_exempt(self):
        self.assertEqual(self.scan(
            '{\n  "other_auth.py": "' + disposable_credential() + '"\n}\n'), 1)

    def test_exact_signing_source_digest_in_checker_is_not_a_credential(self):
        self.assertEqual(self.scan(signing_source_row(), CHECKER_PATH), 0)

    def test_identical_signing_source_row_in_another_path_is_scanned(self):
        self.assertEqual(self.scan(signing_source_row(), "other.py"), 1)

    def test_different_value_in_exact_checker_is_scanned(self):
        row = '    "a11oy_signing_key.py": "' + disposable_credential() + '",\n'
        self.assertEqual(self.scan(row, CHECKER_PATH), 1)

    def test_adjacent_credential_in_exact_checker_is_scanned(self):
        row = signing_source_row() + '    "private_api_key": "' + disposable_credential() + '",\n'
        self.assertEqual(self.scan(row, CHECKER_PATH), 1)

    def test_same_line_credential_in_exact_checker_is_scanned(self):
        row = signing_source_row().rstrip() + ' "private_api_key": "' + disposable_credential() + '"\n'
        self.assertEqual(self.scan(row, CHECKER_PATH), 1)


if __name__ == "__main__":
    unittest.main()
