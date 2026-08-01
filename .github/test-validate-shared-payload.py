#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Regression tests for the content-addressed shared payload manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "validate-shared-payload.py"
MANIFEST_REL = Path(".github/shared-source-payload-manifest.json")
PAYLOAD_REL = Path("static-vendor/a11oy-operator-widget.js")


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.self_root = self.root / "self"
        self.peer_root = self.root / "peer"
        self.payload = b"shared-payload-v1\n"
        self.payload_digest = hashlib.sha256(self.payload).hexdigest()
        self.document = {
            "files": {PAYLOAD_REL.as_posix(): self.payload_digest},
            "payload_id": "operator-control-dock-test",
            "schema": "szl-shared-source-payload/v1",
        }
        self.manifest = (json.dumps(self.document, indent=2) + "\n").encode("utf-8")
        for checkout in (self.self_root, self.peer_root):
            (checkout / MANIFEST_REL.parent).mkdir(parents=True)
            (checkout / PAYLOAD_REL.parent).mkdir(parents=True)
            (checkout / MANIFEST_REL).write_bytes(self.manifest)
            (checkout / PAYLOAD_REL).write_bytes(self.payload)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_case(self, digest: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(self.self_root),
                str(self.peer_root),
                "--expected-manifest-sha256",
                digest or hashlib.sha256(self.manifest).hexdigest(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_valid_manifest_binds_both_payloads(self) -> None:
        result = self.run_case()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("files_verified=1", result.stdout)

    def test_wrong_content_address_fails(self) -> None:
        result = self.run_case("0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match", result.stderr)

    def test_peer_manifest_must_be_byte_identical(self) -> None:
        (self.peer_root / MANIFEST_REL).write_bytes(self.manifest + b"\n")
        result = self.run_case()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not byte-identical", result.stderr)

    def test_each_checkout_must_match_the_file_digest(self) -> None:
        (self.peer_root / PAYLOAD_REL).write_bytes(b"tampered\n")
        result = self.run_case()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sibling:static-vendor/a11oy-operator-widget.js", result.stderr)

    def test_duplicate_json_key_fails_closed(self) -> None:
        duplicate = self.manifest.replace(
            b'  "payload_id": "operator-control-dock-test",\n',
            b'  "payload_id": "operator-control-dock-test",\n  "payload_id": "duplicate",\n',
        )
        for checkout in (self.self_root, self.peer_root):
            (checkout / MANIFEST_REL).write_bytes(duplicate)
        result = self.run_case(hashlib.sha256(duplicate).hexdigest())
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate JSON key", result.stderr)

    def test_traversal_path_fails_closed(self) -> None:
        invalid = {
            "files": {"../escape": self.payload_digest},
            "payload_id": "operator-control-dock-test",
            "schema": "szl-shared-source-payload/v1",
        }
        raw = (json.dumps(invalid, indent=2) + "\n").encode("utf-8")
        for checkout in (self.self_root, self.peer_root):
            (checkout / MANIFEST_REL).write_bytes(raw)
        result = self.run_case(hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.returncode, 2)
        self.assertIn("traversal is forbidden", result.stderr)

    def test_empty_file_set_fails_closed(self) -> None:
        invalid = {
            "files": {},
            "payload_id": "operator-control-dock-test",
            "schema": "szl-shared-source-payload/v1",
        }
        raw = (json.dumps(invalid, indent=2) + "\n").encode("utf-8")
        for checkout in (self.self_root, self.peer_root):
            (checkout / MANIFEST_REL).write_bytes(raw)
        result = self.run_case(hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.returncode, 2)
        self.assertIn("non-empty", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
