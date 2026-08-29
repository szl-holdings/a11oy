# SPDX-License-Identifier: Apache-2.0
"""Packet 8 Decision Integrity surface. Network-free."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_decision_integrity as surface  # noqa: E402


class DecisionIntegritySurfaceTests(unittest.TestCase):
    def test_catalog_lists_four_verticals(self) -> None:
        cat = surface.catalog()
        ids = [item["id"] for item in cat["verticals"]]
        self.assertEqual(ids, ["terra", "aegis", "puriq-markets", "counsel"])
        self.assertEqual(cat["status"], "ROADMAP")
        self.assertEqual(cat["formula_authority"], "NONE")
        self.assertFalse(cat["runtime_claimed"])
        self.assertEqual(cat["data_label"], "SAMPLE")

    def test_frozen_evals_match_expected_state(self) -> None:
        for vertical_id in surface.VERTICAL_IDS:
            packed = surface.load_vertical(vertical_id)
            self.assertGreaterEqual(len(packed["cases"]), 3, vertical_id)
            for case in packed["cases"]:
                payload = case.get("payload") or case
                result = surface.evaluate_case(vertical_id, payload)
                self.assertEqual(
                    result["state"],
                    case["expected_state"],
                    f"{vertical_id} {case.get('eval_id')}",
                )
                for item in result["formulas"]:
                    self.assertEqual(item["authority"], "NONE")

    def test_page_exists(self) -> None:
        page = surface.PAGES_DIR / "decision.html"
        self.assertTrue(page.is_file())
        text = page.read_text(encoding="utf-8")
        self.assertNotIn("googleapis.com", text)
        self.assertNotIn("cdn.", text)
        self.assertIn("Formula authority NONE", text)
        self.assertIn("PATH_TO_VERTICAL", text)
        for path in ("/terra", "/aegis", "/puriq-markets", "/counsel"):
            self.assertIn(path, text)

    def test_page_aliases_cover_the_four_desks(self) -> None:
        for path in ("/decision", "/terra", "/aegis", "/puriq-markets", "/puriq", "/counsel"):
            self.assertIn(path, surface.PAGE_ALIASES)
        self.assertEqual(surface.PAGE_ALIASES[0], "/decision")


if __name__ == "__main__":
    unittest.main()
