#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Source ownership regressions; these do not qualify live router inference."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "align_router_source_authority.py"
SPEC = importlib.util.spec_from_file_location("router_alignment", SCRIPT)
alignment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alignment)

BRAIN = """Integrated A11oy adapter for the canonical routing source at
szl-holdings/szl-router. A11oy owns the portfolio registry and operator
interface; routing-runtime changes originate in the router repository and
enter A11oy only through an explicit source-bound integration.
"""
FIXTURES = {
    "szl_brain.py": BRAIN,
    "organs/amaru/szl_brain.py": BRAIN,
    "organs/sentra/szl_brain.py": BRAIN,
    "szl_llm_registry.py": """szl_llm_registry — A11oy is the portfolio model registry and operator forum; szl-holdings/szl-router is the canonical routing-runtime source.
  1. A11oy catalogs approved model routes; szl-router owns runtime routing and provider fallback.
""",
    "a11oy_code.py": "a11oy.code — the integrated 7-tier organ-mapped view of the canonical szl-holdings/szl-router runtime.\n",
    "src/pages/A11oyCode.tsx": "// a11oy.code — integrated 7-tier view of the canonical szl-holdings/szl-router runtime (Doctrine v11 §14).\n",
}


class RouterSourceAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for relative, text in FIXTURES.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }

    def test_completed_alignment_passes_without_writes_and_is_repeatable(self):
        before = self.snapshot()
        self.assertEqual(set(alignment.check_alignment(self.root)), set(FIXTURES))
        alignment.check_alignment(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_missing_each_original_target_fails_without_rewriting_other_files(self):
        for relative in FIXTURES:
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.unlink()
                before = self.snapshot()
                with self.assertRaises(alignment.AlignmentError):
                    alignment.check_alignment(self.root)
                self.assertEqual(self.snapshot(), before)
                path.write_bytes(original)

    def test_drift_in_each_original_target_is_rejected(self):
        for relative, text in FIXTURES.items():
            with self.subTest(path=relative):
                path = self.root / relative
                path.write_text(text.replace("szl-holdings/szl-router", "unreviewed/router"), encoding="utf-8")
                before = self.snapshot()
                with self.assertRaises(alignment.AlignmentError):
                    alignment.check_alignment(self.root)
                self.assertEqual(self.snapshot(), before)
                path.write_text(text, encoding="utf-8")

    def test_duplicated_canonical_statement_is_ambiguous(self):
        path = self.root / "szl_brain.py"
        path.write_text(BRAIN + BRAIN, encoding="utf-8")
        with self.assertRaisesRegex(alignment.AlignmentError, "found 2"):
            alignment.check_alignment(self.root)

    def test_mixed_legacy_and_canonical_ownership_is_rejected(self):
        legacy = {
            "szl_brain.py": "szl-holdings/platform/packages/llm-router/",
            "organs/amaru/szl_brain.py": "szl-holdings/platform/packages/llm-router/",
            "organs/sentra/szl_brain.py": "szl-holdings/platform/packages/llm-router/",
            "szl_llm_registry.py": "szl_llm_registry — a11oy is THE LLM Hub for the SZL ecosystem.",
            "a11oy_code.py": "a11oy.code — the 7-tier organ-mapped LLM router baked into the anatomy.",
            "src/pages/A11oyCode.tsx": "// a11oy.code — 7-tier organ-mapped LLM router UI (Doctrine v11 §14).",
        }
        for relative, retired in legacy.items():
            with self.subTest(path=relative):
                path = self.root / relative
                path.write_text(FIXTURES[relative] + retired, encoding="utf-8")
                with self.assertRaisesRegex(alignment.AlignmentError, "retired source declaration"):
                    alignment.check_alignment(self.root)
                path.write_text(FIXTURES[relative], encoding="utf-8")

    def test_registry_policy_declaration_is_required_separately_from_title(self):
        path = self.root / "szl_llm_registry.py"
        path.write_text(FIXTURES["szl_llm_registry.py"].splitlines()[0], encoding="utf-8")
        with self.assertRaises(alignment.AlignmentError):
            alignment.check_alignment(self.root)

    def test_invalid_utf8_is_unavailable(self):
        (self.root / "szl_brain.py").write_bytes(b"\xff")
        with self.assertRaisesRegex(alignment.AlignmentError, "UnicodeDecodeError"):
            alignment.check_alignment(self.root)

    def test_directory_in_place_of_source_file_is_rejected(self):
        path = self.root / "szl_brain.py"
        path.unlink()
        path.mkdir()
        with self.assertRaises(alignment.AlignmentError):
            alignment.check_alignment(self.root)

    def test_cli_default_is_read_only_and_failure_returns_nonzero(self):
        before = self.snapshot()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(alignment.main(["--root", str(self.root)]), 0)
        self.assertEqual(self.snapshot(), before)
        (self.root / "szl_brain.py").unlink()
        before = self.snapshot()
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(alignment.main(["--check", "--root", str(self.root)]), 1)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
