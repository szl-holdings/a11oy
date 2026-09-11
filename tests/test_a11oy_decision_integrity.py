# SPDX-License-Identifier: Apache-2.0
"""Packet 8 Decision Integrity surface. Network-free."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_decision_integrity as surface  # noqa: E402


class DecisionIntegritySurfaceTests(unittest.TestCase):
    def test_catalog_lists_five_verticals(self) -> None:
        cat = surface.catalog()
        ids = [item["id"] for item in cat["verticals"]]
        self.assertEqual(ids, ["terra", "aegis", "puriq-markets", "counsel", "vessels"])
        self.assertEqual(cat["status"], "ROADMAP")
        self.assertEqual(cat["formula_authority"], "NONE")
        self.assertFalse(cat["runtime_claimed"])
        self.assertFalse(cat["production_ready"])
        self.assertFalse(cat["licensed_ais_admitted"])
        self.assertEqual(cat["data_label"], "SAMPLE")
        self.assertEqual(cat["desks"]["vessels"], "/vessels")
        self.assertEqual(cat["desks"]["demo"], "/demo")
        self.assertEqual(
            cat["desks"]["ais_standards"],
            "https://a11oy.net/vessels/ais-standards.json",
        )
        vessels = next(item for item in cat["verticals"] if item["id"] == "vessels")
        self.assertEqual(vessels["ais_standards_honesty"], "CITATION_ONLY")
        self.assertFalse(vessels["licensed_ais_admitted"])
        self.assertEqual(vessels["vessels_e03_licensed_ais_tpr"], "OUTSTANDING")

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

    def test_vessels_denies_licensed_ais(self) -> None:
        packed = surface.load_vertical("vessels")
        deny = next(item for item in packed["cases"] if item["eval_id"] == "VESSELS-E-DENY-AIS")
        result = surface.evaluate_case("vessels", deny["payload"])
        self.assertEqual(result["state"], "DENIED")
        self.assertIn("PROHIBITED_ACTION", result.get("reason_codes") or [])

    def test_vessels_ais_standards_citation_only(self) -> None:
        packed = surface.load_vertical("vessels")
        self.assertIn("ais_standards", packed)
        pack = packed["ais_standards"]
        self.assertFalse(pack.get("licensed_ais_admitted"))
        self.assertEqual(pack.get("licensed_ais_queries"), 0)
        self.assertEqual(pack.get("vessels_e03_licensed_ais_tpr"), "OUTSTANDING")
        self.assertFalse(pack.get("stamps_live"))
        self.assertNotIn("LIVE", json.dumps(pack))
        deny = next(item for item in packed["cases"] if item["eval_id"] == "VESSELS-E-DENY-AIS")
        result = surface.evaluate_case("vessels", deny["payload"])
        self.assertEqual(result["state"], "DENIED")
        self.assertFalse(result.get("licensed_ais_admitted"))
        echo = result["ais_standards"]
        self.assertEqual(echo["honesty"], "CITATION_ONLY")
        self.assertFalse(echo["licensed_ais_admitted"])
        self.assertEqual(echo["licensed_ais_queries"], 0)
        self.assertEqual(echo["vessels_e03_licensed_ais_tpr"], "OUTSTANDING")
        self.assertEqual(echo["fail_closed_eval"], "VESSELS-E-DENY-AIS")
        self.assertIn("ITU-R M.1371", echo["instruments"])
        self.assertEqual(len(echo["instruments"]), 8)
        self.assertEqual(echo["proof"], "https://a11oy.net/vessels/ais-standards.json")
        self.assertNotIn("LIVE", json.dumps(echo))
        terra_cases = surface.load_vertical("terra")["cases"]
        terra = surface.evaluate_case("terra", terra_cases[0].get("payload") or terra_cases[0])
        self.assertNotIn("ais_standards", terra)

    def test_page_exists(self) -> None:
        page = surface.PAGES_DIR / "decision.html"
        self.assertTrue(page.is_file())
        text = page.read_text(encoding="utf-8")
        self.assertNotIn("googleapis.com", text)
        self.assertNotIn("cdn.", text)
        self.assertIn("Formula authority NONE", text)
        self.assertIn("PATH_TO_VERTICAL", text)
        self.assertIn("CITATION_ONLY", text)
        self.assertIn("a11oy.net/vessels/ais-standards.json", text)
        for path in ("/terra", "/aegis", "/puriq-markets", "/counsel", "/vessels"):
            self.assertIn(path, text)

    def test_page_aliases_cover_the_desks(self) -> None:
        for path in (
            "/decision",
            "/terra",
            "/aegis",
            "/puriq-markets",
            "/puriq",
            "/counsel",
            "/vessels",
            "/demo",
            "/evaluations",
        ):
            self.assertIn(path, surface.PAGE_ALIASES)
        self.assertEqual(surface.PAGE_ALIASES[0], "/decision")
        self.assertTrue((surface.PAGES_DIR / "demo.html").is_file())
        self.assertTrue((surface.PAGES_DIR / "evaluations.html").is_file())


if __name__ == "__main__":
    unittest.main()
