# SPDX-License-Identifier: Apache-2.0
"""Prove the immutable public archive exception retains credential detection."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = os.environ.get("SZL_TEST_GITLEAKS_BINARY")
MANIFEST = ".github/shared-source-payload-manifest.json"
HISTORY = ".github/shared-source-payloads/replication-payload-integrity-20261017-v1.json"
MODEL_HISTORY = ".github/shared-source-payloads/model-credential-origin-20261017-v1.json"
ARCHIVE = ".github/shared-source-payloads/execution-observer-operator-auth-20261016-v1.json"


def archive_row():
    digest = hashlib.sha256((ROOT / ARCHIVE).read_bytes()).hexdigest()
    return f'    "{ARCHIVE}": "{digest}",\n'


def disposable_credential():
    return hashlib.sha256(b"szl-archive-scanner-positive-control-v1").hexdigest()


class ArchiveExceptionContract(unittest.TestCase):
    def test_exception_requires_exact_path_and_immutable_complete_row(self):
        config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
        rule = next(item for item in config["rules"] if item["id"] == "generic-api-key")
        allow = next(item for item in rule["allowlists"]
                     if item["description"] == "Exact archived execution observer identity in active or preserved manifest")
        self.assertEqual(set(allow), {"description", "condition", "regexTarget", "paths", "regexes"})
        self.assertEqual(allow["condition"], "AND")
        self.assertEqual(allow["regexTarget"], "line")
        self.assertEqual(allow["paths"], [
            r"(^|[\\/])\.github[\\/]shared-source-payload-manifest\.json$",
            r"(^|[\\/])\.github[\\/]shared-source-payloads[\\/]replication-payload-integrity-20261017-v1\.json$",
            r"(^|[\\/])\.github[\\/]shared-source-payloads[\\/]model-credential-origin-20261017-v1\.json$",
        ])
        self.assertEqual(len(allow["regexes"]), 1)
        row = archive_row()
        self.assertIn(row, (ROOT / HISTORY).read_text(encoding="utf-8"))
        self.assertIn(row, (ROOT / MODEL_HISTORY).read_text(encoding="utf-8"))
        self.assertRegex(row, allow["regexes"][0])
        self.assertIsNone(re.search(allow["regexes"][0], row.rstrip() + ' "private_api_key": "' + disposable_credential() + '"'))
        self.assertIsNone(re.search(allow["regexes"][0], f'    "{ARCHIVE}": "{disposable_credential()}",\n'))


@unittest.skipUnless(BINARY, "actual scanner not configured; NOT VERIFIED")
class ArchiveScannerBoundary(unittest.TestCase):
    def scan(self, text, relative_path=MANIFEST):
        with tempfile.TemporaryDirectory(prefix="szl-archive-digest-probe-") as folder:
            target = Path(folder) / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [BINARY, "detect", "--source", ".", "--no-git",
                 "--config", str(ROOT / ".gitleaks.toml"), "--redact",
                 "--exit-code", "1", "--no-banner", "--log-level", "error"],
                cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=False,
            )
            return result.returncode

    def test_exact_public_archive_row_passes(self):
        for path in (MANIFEST, HISTORY, MODEL_HISTORY):
            with self.subTest(path=path):
                self.assertEqual(self.scan(archive_row(), path), 0)

    def test_same_row_in_another_path_remains_detected(self):
        self.assertEqual(self.scan(archive_row(), "other/shared-source-payload-manifest.json"), 1)
        self.assertEqual(self.scan(archive_row(), ".github/shared-source-payloads/unreviewed-successor.json"), 1)

    def test_changed_digest_remains_detected(self):
        for path in (MANIFEST, HISTORY, MODEL_HISTORY):
            with self.subTest(path=path):
                self.assertEqual(self.scan(f'    "{ARCHIVE}": "{disposable_credential()}",\n', path), 1)

    def test_adjacent_credential_remains_detected(self):
        for path in (MANIFEST, HISTORY, MODEL_HISTORY):
            with self.subTest(path=path):
                self.assertEqual(self.scan(archive_row() + '    "private_api_key": "' + disposable_credential() + '"\n', path), 1)

    def test_same_line_credential_remains_detected(self):
        for path in (MANIFEST, HISTORY, MODEL_HISTORY):
            with self.subTest(path=path):
                self.assertEqual(self.scan(archive_row().rstrip() + ' "private_api_key": "' + disposable_credential() + '"\n', path), 1)


if __name__ == "__main__":
    unittest.main()
