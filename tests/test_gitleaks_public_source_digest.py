# SPDX-License-Identifier: Apache-2.0
"""Actual-scanner regression for a public source digest, never a path exclusion.

Set SZL_TEST_GITLEAKS_BINARY to the checksum-verified CI scanner executable.
Only disposable generated credentials are used; scanner output is never printed.
"""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = os.environ.get("SZL_TEST_GITLEAKS_BINARY")
PUBLIC_DIGEST = "1ee6a88e37d522c5404ac04ac90eadcbfc6f7e59140a778d03275832e217e2cf"


@unittest.skipUnless(BINARY, "actual scanner not configured; NOT VERIFIED")
class PublicDigestScannerBoundary(unittest.TestCase):
    def scan(self, text):
        with tempfile.TemporaryDirectory(prefix="szl-public-digest-probe-") as folder:
            (Path(folder) / "probe.json").write_text(text, encoding="utf-8")
            result = subprocess.run(
                [BINARY, "detect", "--source", folder, "--no-git",
                 "--config", str(ROOT / ".gitleaks.toml"), "--redact",
                 "--exit-code", "1", "--no-banner", "--log-level", "error"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=False,
            )
            return result.returncode

    def test_verified_public_row_is_not_a_credential(self):
        self.assertEqual(self.scan(
            '{\n  "szl_operator_auth.py": "' + PUBLIC_DIGEST + '"\n}\n'), 0)

    def test_adjacent_disposable_credential_remains_detected(self):
        credential = secrets.token_hex(32)
        self.assertEqual(self.scan(
            '{\n  "szl_operator_auth.py": "' + PUBLIC_DIGEST
            + '",\n  "private_api_key": "' + credential + '"\n}\n'), 1)

    def test_same_line_disposable_credential_cannot_borrow_public_exemption(self):
        credential = secrets.token_hex(32)
        self.assertEqual(self.scan(
            '{\n  "szl_operator_auth.py": "' + PUBLIC_DIGEST
            + '", "private_api_key": "' + credential + '"\n}\n'), 1)

    def test_other_auth_named_value_is_not_exempt(self):
        self.assertEqual(self.scan(
            '{\n  "other_auth.py": "' + secrets.token_hex(32) + '"\n}\n'), 1)


if __name__ == "__main__":
    unittest.main()
