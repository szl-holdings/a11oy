#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Cross-platform regression tests for the copy-sync lockstep guard."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("check_copy_sync_lockstep.py")
SPEC = importlib.util.spec_from_file_location("check_copy_sync_lockstep", MODULE_PATH)
assert SPEC and SPEC.loader
lockstep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lockstep)


class PathNormalizationTests(unittest.TestCase):
    def test_normalizes_windows_and_dot_prefixes(self) -> None:
        self.assertEqual(
            lockstep.normalize_repo_path(r".\pages\console\index.js"),
            "pages/console/index.js",
        )

    def test_mirror_parser_normalizes_explicit_and_glob_paths(self) -> None:
        explicit, globs = lockstep.parse_hf_sync_mirror(
            """
env:
  APP_FILES: "serve.py pages\\index.html"
on:
  push:
    paths:
      - "console\\**"
"""
        )
        self.assertEqual(explicit, {"serve.py", "pages/index.html"})
        self.assertEqual(globs, ["console/**"])

    def test_matcher_normalizes_assets_and_patterns(self) -> None:
        self.assertTrue(
            lockstep.gha_path_matches(
                r"console\assets\app.js",
                set(),
                [r"console\**"],
            )
        )
        self.assertTrue(
            lockstep.gha_path_matches(
                r"pages\index.html",
                {r"pages\index.html"},
                [],
            )
        )


class SyntheticRepositoryTests(unittest.TestCase):
    def test_required_source_contract_cannot_fall_back_to_declared_mirror_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "static").mkdir()
            (root / "Dockerfile").write_text(
                "COPY serve.py /app/serve.py\nCOPY static/app.js /app/static/app.js\n",
                encoding="utf-8",
            )
            (root / "serve.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "static" / "app.js").write_text("console.log('ok');\n", encoding="utf-8")
            (root / ".github" / "workflows" / "hf-sync.yml").write_text(
                "on:\n  push:\n    branches: [main]\njobs: {}\n", encoding="utf-8"
            )
            for required, expected in ((None, 0), (False, 0), (True, 1), ("true", 2), (1, 2)):
                with self.subTest(required=required):
                    config = {"mirror_asset_exts": [".js"], "extra_mirror_paths": ["static/app.js"]}
                    if required is not None:
                        config["require_source_derived_deploy"] = required
                    (root / ".github" / "copy-sync-lockstep.json").write_text(
                        json.dumps(config), encoding="utf-8"
                    )
                    stdout = io.StringIO()
                    with mock.patch.object(sys, "argv", ["guard", str(root)]), contextlib.redirect_stdout(stdout):
                        result = lockstep.main()
                    self.assertEqual(expected, result, stdout.getvalue())
                    if required is True:
                        self.assertIn("required source-derived deploy contract invalid", stdout.getvalue())
                        self.assertNotIn("OK: COPY", stdout.getvalue())

    def test_guard_passes_with_windows_relpath_separators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "static").mkdir()
            (root / "Dockerfile").write_text(
                "COPY serve.py /app/serve.py\n"
                "COPY static/app.js /app/static/app.js\n",
                encoding="utf-8",
            )
            (root / "serve.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "static" / "app.js").write_text(
                "console.log('ok');\n",
                encoding="utf-8",
            )
            (root / ".github" / "copy-sync-lockstep.json").write_text(
                json.dumps({"mirror_asset_exts": [".js"]}),
                encoding="utf-8",
            )
            (root / ".github" / "workflows" / "hf-sync.yml").write_text(
                "on:\n"
                "  push:\n"
                "    paths:\n"
                "      - \"static/*.js\"\n",
                encoding="utf-8",
            )

            real_relpath = os.path.relpath

            def windows_relpath(path: str, start: str) -> str:
                return real_relpath(path, start).replace("/", "\\")

            stdout = io.StringIO()
            with (
                mock.patch.object(lockstep.os.path, "relpath", windows_relpath),
                mock.patch.object(sys, "argv", ["guard", str(root)]),
                contextlib.redirect_stdout(stdout),
            ):
                result = lockstep.main()

            self.assertEqual(result, 0, stdout.getvalue())
            self.assertIn("OK: COPY <-> serve.py imports", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
