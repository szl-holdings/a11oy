#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline snapshot identity contracts; this does not claim a current Lean census."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = (
    "https://github.com/szl-holdings/.github/blob/"
    "5cd00651972728f0264ac6348d3a8bf30749fcc0/.github/data/lean_numbers.json"
)
SOURCE_BLOB = "5429d9eba29100659169e47c109066ce9745b249"
FIXTURE = ROOT / "tests/fixtures/lean_numbers.c7c0ba17.json"


def load_legacy_organ():
    # Exercise the documented stdlib fallback without loading unrelated live stores.
    spec = importlib.util.spec_from_file_location(
        "_yachay_snapshot_contract", ROOT / "szl_yachay_organ.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"szl_khipu": None, "szl_unay": None}):
        spec.loader.exec_module(module)
    return module


def source_constant(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Missing source constant {name}")


class YachayLeanSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.organ = load_legacy_organ()

    def test_fixture_is_the_exact_pinned_authority_blob(self):
        raw = FIXTURE.read_bytes()
        identity = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        self.assertEqual(
            hashlib.sha1(identity, usedforsecurity=False).hexdigest(), SOURCE_BLOB
        )

    def test_retained_source_matches_authority_counts_and_identity(self):
        snapshot = self.organ.DOCTRINE_LOCKED["lean_snapshot"]
        self.assertEqual(snapshot["sha"], self.manifest["sha"])
        self.assertEqual(snapshot["repo"], self.manifest["repo"])
        self.assertEqual(snapshot["measured_at_utc"], self.manifest["measured_at_utc"])
        self.assertEqual(snapshot["source_url"], AUTHORITY)
        self.assertEqual(snapshot["status"], "HISTORICAL")
        self.assertIs(snapshot["current_head_verified"], False)
        for field, source in {
            "declarations": "declarations", "sorries": "sorries_raw",
            "raw_axioms": "axioms_raw", "unique_axioms": "axioms_unique",
            "sorries_baseline": "sorries_baseline", "sorries_putnam": "sorries_putnam",
            "locked_formula_count": "locked_formula_count",
        }.items():
            with self.subTest(field=field):
                self.assertEqual(snapshot[field], self.manifest["numbers"][source])
        self.assertIsNone(self.organ.DOCTRINE_LOCKED["live_regen"])
        self.assertIsNone(self.organ.DOCTRINE_LOCKED["putnam_green"])

    def test_existing_active_brain_uses_the_same_snapshot(self):
        brain = source_constant(ROOT / "szl_brain.py", "CANONICAL")
        for brain_key, manifest_key in {
            "declarations": "declarations", "sorries": "sorries_raw",
            "axioms_unique": "axioms_unique", "axioms_raw": "axioms_raw",
            "sorries_baseline": "sorries_baseline", "sorries_putnam": "sorries_putnam",
        }.items():
            self.assertEqual(brain[brain_key], self.manifest["numbers"][manifest_key])
        self.assertIn(self.manifest["sha"], brain["source"])

    def test_request_time_does_not_make_historical_counts_live(self):
        first = self.organ._live_canon_block(7)
        with patch.object(self.organ.time, "strftime", return_value="2099-01-01T00:00:00Z"):
            later = self.organ._live_canon_block(8)
        for block in (first, later):
            self.assertIn("HISTORICAL at c7c0ba17", block)
            self.assertIn("measured 2026-05-31T11:00:00Z", block)
            self.assertIn("Current HEAD and current Putnam proof status are not verified", block)
            self.assertIn(AUTHORITY, block)
            self.assertNotIn("LIVE CANON", block)
            self.assertNotIn("752 declarations", block)
            self.assertIn("Lambda uniqueness remains Conjecture 1", block)
        self.assertIn("2099-01-01", later)
        self.assertIn("at this turn: 8", later)

    def test_ui_uses_payload_snapshot_and_has_an_unavailable_case(self):
        html = self.organ._YACHAY_HTML
        self.assertIn("(d.doctrine_locked||{}).lean_snapshot", html)
        self.assertIn("snapshot.status==='HISTORICAL'", html)
        self.assertIn("Lean snapshot unavailable", html)
        self.assertNotIn("752 decl", html)
        self.assertNotIn("160 sorries", html)
        self.assertNotIn("4/12 GREEN", html)

    def test_prompt_and_docs_keep_source_boundary(self):
        for relative in (
            "YACHAY_SYSTEM_PROMPT.md",
            "docs/SUBSTRATE_REALITY_MAP.md",
            "docs/site/docs/evidence/index.md",
        ):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(AUTHORITY, text)
                self.assertIn("c7c0ba17", text)
                self.assertIn("2026-05-31T11:00:00Z", text)
        prompt = self.organ._load_system_prompt()
        self.assertIn("historical snapshot", prompt.lower())
        self.assertNotIn("CANONICAL_NUMBERS_LIVE", prompt)
        self.assertNotIn("Never claim\nΛ-uniqueness is Conjecture 1", prompt)

    def test_source_correction_does_not_activate_retired_module(self):
        tree = ast.parse((ROOT / "serve.py").read_text(encoding="utf-8"))
        imports = {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        self.assertNotIn("szl_yachay_organ", imports)
        copy_lines = [
            line for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
            if line.lstrip().startswith("COPY ")
        ]
        for source in ("szl_yachay_organ.py", "YACHAY_SYSTEM_PROMPT.md"):
            with self.subTest(source=source):
                self.assertFalse(any(source in line for line in copy_lines))


if __name__ == "__main__":
    unittest.main()
