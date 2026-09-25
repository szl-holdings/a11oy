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
        self.assertEqual(
            cat["desks"]["ais_lattice"],
            "https://a11oy.net/vessels/ais-lattice.json",
        )
        self.assertEqual(
            cat["desks"]["public_lists"],
            "https://a11oy.net/vessels/public-lists-world.json",
        )
        self.assertEqual(
            cat["desks"]["joint_freshness"],
            "https://a11oy.net/vessels/joint-freshness.json",
        )
        vessels = next(item for item in cat["verticals"] if item["id"] == "vessels")
        self.assertEqual(vessels["ais_standards_honesty"], "CITATION_ONLY")
        self.assertEqual(vessels["ais_lattice_honesty"], "CITATION_ONLY")
        self.assertEqual(vessels["ais_lattice_digest"], surface.AIS_LATTICE_DIGEST)
        self.assertEqual(vessels["ais_lattice_message_types"], 27)
        self.assertEqual(vessels["public_lists_honesty"], "CITATION_ONLY")
        self.assertEqual(vessels["public_lists_digest"], surface.PUBLIC_LISTS_DIGEST)
        self.assertEqual(vessels["public_list_authority_classes"], 7)
        self.assertEqual(vessels["joint_freshness_digest"], surface.JOINT_FRESHNESS_DIGEST)
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

    def test_empty_json_evaluate_is_unknown_not_admit(self) -> None:
        result = surface.evaluate_case("terra", {})
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["decision"], "UNKNOWN")
        self.assertEqual(result["honesty"], "UNKNOWN")
        self.assertEqual(result["formulas"], [])
        self.assertFalse(result.get("admit"))
        self.assertNotEqual(result["state"], "AWAITING_APPROVAL")
        self.assertEqual(result["status"], "ROADMAP")
        self.assertFalse(result["runtime_claimed"])

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
        self.assertNotIn("ais_lattice", terra)
        self.assertNotIn("public_lists", terra)

    def test_vessels_ais_lattice_citation_only(self) -> None:
        packed = surface.load_vertical("vessels")
        self.assertIn("ais_lattice", packed)
        pack = packed["ais_lattice"]
        self.assertEqual(pack.get("digest"), surface.AIS_LATTICE_DIGEST)
        self.assertEqual(len(pack.get("message_types") or []), 27)
        self.assertFalse(pack.get("licensed_ais_admitted"))
        self.assertEqual(pack.get("licensed_ais_queries"), 0)
        self.assertFalse(pack.get("stamps_live"))
        self.assertFalse(pack.get("production_ready"))
        self.assertEqual(pack.get("vessels_e03_licensed_ais_tpr"), "OUTSTANDING")
        refused = {row.get("id") for row in pack.get("open_source_codecs_refused") or []}
        self.assertGreaterEqual(refused, {"pyais", "libais", "aiscat"})
        self.assertFalse(pack.get("stamps_live"))
        self.assertFalse(pack.get("production_ready"))
        deny = next(item for item in packed["cases"] if item["eval_id"] == "VESSELS-E-DENY-AIS")
        result = surface.evaluate_case("vessels", deny["payload"])
        echo = result["ais_lattice"]
        self.assertEqual(echo["honesty"], "CITATION_ONLY")
        self.assertEqual(echo["digest"], surface.AIS_LATTICE_DIGEST)
        self.assertEqual(echo["message_types"], 27)
        self.assertEqual(echo["licensed_ais_queries"], 0)
        self.assertFalse(echo["licensed_ais_admitted"])
        self.assertFalse(echo["production_ready"])
        self.assertFalse(echo["stamps_live"])
        self.assertEqual(echo["fail_closed_eval"], "VESSELS-E-DENY-AIS")
        self.assertEqual(echo["proof"], "https://a11oy.net/vessels/ais-lattice.json")
        self.assertIn("pyais", echo["codecs_refused"])
        self.assertIn("libais", echo["codecs_refused"])
        self.assertIn("aiscat", echo["codecs_refused"])
        self.assertEqual(echo["vessels_e03_licensed_ais_tpr"], "OUTSTANDING")
        self.assertNotIn("LIVE", json.dumps(echo))
        empty = surface.evaluate_case("vessels", {})
        self.assertEqual(empty["state"], "UNKNOWN")
        self.assertEqual(empty["ais_lattice"]["honesty"], "CITATION_ONLY")
        self.assertEqual(empty["public_lists"]["honesty"], "CITATION_ONLY")

    def test_vessels_public_lists_citation_only(self) -> None:
        packed = surface.load_vertical("vessels")
        self.assertIn("public_lists", packed)
        pack = packed["public_lists"]
        self.assertEqual(pack.get("digest"), surface.PUBLIC_LISTS_DIGEST)
        self.assertEqual(len(pack.get("authority_classes") or []), 7)
        self.assertIn("OFAC-vessel", pack.get("authority_classes") or [])
        self.assertFalse(pack.get("licensed_ais_admitted"))
        self.assertEqual(pack.get("licensed_ais_queries"), 0)
        self.assertFalse(pack.get("stamps_live"))
        self.assertFalse(pack.get("production_ready"))
        self.assertEqual(pack.get("vessels_e01"), "OUTSTANDING")
        self.assertEqual(pack.get("ais_lattice_digest_unchanged"), surface.AIS_LATTICE_DIGEST)
        deny = next(item for item in packed["cases"] if item["eval_id"] == "VESSELS-E-DENY-AIS")
        result = surface.evaluate_case("vessels", deny["payload"])
        echo = result["public_lists"]
        self.assertEqual(echo["honesty"], "CITATION_ONLY")
        self.assertEqual(echo["digest"], surface.PUBLIC_LISTS_DIGEST)
        self.assertEqual(echo["authority_lattice_digest"], surface.PUBLIC_LIST_LATTICE_DIGEST)
        self.assertEqual(len(echo["authority_classes"]), 7)
        self.assertIn("UA-GUR-ship", echo["authority_classes"])
        self.assertIn("REFUSED", echo["freshness_classes"])
        self.assertEqual(echo["licensed_ais_queries"], 0)
        self.assertFalse(echo["licensed_ais_admitted"])
        self.assertFalse(echo["production_ready"])
        self.assertFalse(echo["stamps_live"])
        self.assertEqual(echo["fail_closed_eval_stale"], "VESSELS-E-ABSTAIN")
        self.assertEqual(echo["fail_closed_eval_ais"], "VESSELS-E-DENY-AIS")
        self.assertEqual(echo["proof"], "https://a11oy.net/vessels/public-lists-world.json")
        self.assertEqual(echo["typed_judgment"]["result"], "SAMPLE_TEXT_MISS")
        self.assertTrue(echo["typed_judgment"]["miss_is_not_clearance"])
        self.assertTrue(echo["typed_judgment"]["not_e01"])
        joint = echo["joint_freshness"]
        self.assertEqual(joint["digest"], surface.JOINT_FRESHNESS_DIGEST)
        self.assertTrue(joint["winner_not_picked"])
        self.assertTrue(joint["does_not_run_the_kernel"])
        self.assertEqual(joint["negative_evidence"]["result"], "SAMPLE_TEXT_MISS")
        self.assertTrue(joint["negative_evidence"]["miss_is_not_clearance"])
        self.assertFalse(joint["negative_evidence"]["is_clearance"])
        self.assertTrue(joint["negative_evidence"]["not_typesafe_jev_call"])
        self.assertIn("APAC-official-joint", joint["coverage_holes"])
        self.assertIn("KR-MOFA-vessel", joint["coverage_holes"])
        disagree_ids = {row["id"] for row in joint["disagreements"]}
        self.assertIn("UK-FCDO-vs-OFSI", disagree_ids)
        class_ids = {row["id"] for row in joint["classes"]}
        self.assertEqual(len(class_ids), 7)
        kr = next(row for row in joint["classes"] if row["id"] == "KR-MOFA-vessel")
        self.assertTrue(kr["hole"])
        self.assertEqual(kr["maps_to"], "VESSELS-E-ABSTAIN")
        self.assertEqual(joint["proof"], "https://a11oy.net/vessels/joint-freshness.json")
        clock_ids = {row["id"] for row in echo["clocks"]}
        self.assertIn("OFAC_SDN_CSV", clock_ids)
        self.assertIn("MARINETRAFFIC", clock_ids)
        empty = surface.evaluate_case("vessels", {})
        self.assertEqual(empty["state"], "UNKNOWN")
        self.assertEqual(empty["public_lists"]["honesty"], "CITATION_ONLY")
        terra_cases = surface.load_vertical("terra")["cases"]
        terra = surface.evaluate_case("terra", terra_cases[0].get("payload") or terra_cases[0])
        self.assertNotIn("public_lists", terra)

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
        self.assertIn("a11oy.net/vessels/ais-lattice.json", text)
        self.assertIn("ais_lattice", text)
        self.assertIn("f931b485", text)
        self.assertIn("a11oy.net/vessels/public-lists-world.json", text)
        self.assertIn("public_lists", text)
        self.assertIn("70fd1918", text)
        self.assertIn("joint_freshness", text)
        self.assertIn("1cb5b117", text)
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

    def test_evaluate_resolves_wrapper_and_eval_id(self) -> None:
        packed = surface.load_vertical("vessels")
        abstain = next(item for item in packed["cases"] if item["eval_id"] == "VESSELS-E-ABSTAIN")
        wrapped = surface.evaluate_case("vessels", abstain)
        self.assertEqual(wrapped["state"], "ABSTAINED")
        by_id = surface.evaluate_case("vessels", {"eval_id": "VESSELS-E-ABSTAIN"})
        self.assertEqual(by_id["state"], "ABSTAINED")
        by_case = surface.evaluate_case("vessels", {"case_id": "vessels-stale-list"})
        self.assertEqual(by_case["state"], "ABSTAINED")
        deny = surface.evaluate_case("vessels", {"eval_id": "VESSELS-E-DENY-AIS"})
        self.assertEqual(deny["state"], "DENIED")
        empty = surface.evaluate_case("vessels", {})
        self.assertEqual(empty["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
