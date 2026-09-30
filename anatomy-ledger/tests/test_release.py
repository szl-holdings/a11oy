#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Release archive must exclude operator evidence and bind exact file bytes."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
spec = importlib.util.spec_from_file_location(
    "anatomy_release_test", TOOLS / "package_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_package_is_deterministic_and_excludes_operator_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "public/data").mkdir(parents=True)
            (root / "public/data/ledger.json").write_text(
                '{"private":"LOCAL_ONLY_TEST_MARKER"}'
            )
            (root / "public/index.html").write_text("<h1>Anatomy</h1>")
            (root / "evidence").mkdir()
            (root / "evidence/secret.intoto.json").write_text("LOCAL_ONLY_TEST_MARKER")
            first, second = root / "one.tar.gz", root / "two.tar.gz"
            with patch.object(release, "BASE", root):
                release.package(first)
                release.package(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first, "r:gz") as archive:
                files = {
                    item.name: archive.extractfile(item).read()
                    for item in archive.getmembers()
                }
            self.assertFalse(
                any(b"LOCAL_ONLY_TEST_MARKER" in data for data in files.values())
            )
            self.assertEqual(
                json.loads(files["public/data/ledger.json"])["records"], []
            )
            manifest = json.loads(files.pop("MANIFEST.sha256.json"))
            self.assertEqual(
                manifest,
                {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in files.items()
                },
            )


if __name__ == "__main__":
    unittest.main()
