#!/usr/bin/env python3
"""Network-free contract tests for the Living Command Fabric front door."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
MANIFEST = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
ACTIVE_PIN = ROOT / "docs" / "strategy" / "vertical-services-active-pin.v1.json"
PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_services_intelligence_v4.py"
PUBLISHER_TEST = ROOT / "tests" / "test_hf_publish_vertical_flagships_v4.py"

LOCKED_EIGHT = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
VERTICALS = ["terra", "killinchu", "counsel", "finance", "lyte"]
HISTORICAL_VERTICAL_REVISION = "83edba5c5e730c91d8f5f0a6531213fb860677af"


class LivingCommandFabricContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = LANDING.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.active_pin = json.loads(ACTIVE_PIN.read_text(encoding="utf-8"))

    def test_existing_buyer_and_runtime_truth_contracts_are_preserved(self) -> None:
        for literal in (
            "Every AI action your agents take,",
            'id="nv-panel"',
            'id="nv-signer"',
            'id="nv-verdict"',
            'id="hs-receipts"',
            "signer state",
            "Λ = Conjecture 1",
            "locked_formula_count",
        ):
            with self.subTest(literal=literal):
                self.assertIn(literal, self.html)
        self.assertEqual(self.html.count('class="card product-card"'), 3)

    def test_living_fabric_contract_is_exposed(self) -> None:
        for literal in (
            'data-szl-living-command-fabric-v1="true"',
            'id="anatomy"',
            'id="vertical-bodies"',
            "One intelligence fabric. Five public domain bodies. Six internal engines. One evidence bloodstream.",
            "ONE FABRIC",
            "FIVE PUBLIC DOMAIN BODIES",
            "EIGHT LOCKED FORMULA BINDINGS",
            "WILLAY/policy veto",
        ):
            with self.subTest(literal=literal):
                self.assertIn(literal, self.html)

    def test_formula_anatomy_is_exact_and_complete(self) -> None:
        expected = {
            "BRAIN": ["F1"],
            "HEART": ["F4", "F11"],
            "CIRCULATION": ["F7", "F22"],
            "NERVOUS_SYSTEM": ["F12"],
            "SKELETON": ["F18", "F19"],
        }
        observed = {
            row["organ"]: row["formula_ids"]
            for row in self.manifest["formula_contract"]["organs"]
        }
        self.assertEqual(observed, expected)
        self.assertEqual(
            self.manifest["authorities"]["lean_kernel"]["locked_proven_ids"],
            LOCKED_EIGHT,
        )
        self.assertEqual(
            self.manifest["authorities"]["lean_kernel"]["locked_proven_count"],
            8,
        )
        self.assertEqual(
            self.manifest["formula_contract"]["lambda"]["status"],
            "CONJECTURE_1_ADVISORY",
        )
        self.assertFalse(
            self.manifest["formula_contract"]["lambda"]["authorizes_actions"]
        )
        self.assertFalse(
            self.manifest["formula_contract"]["lambda"]["may_render_as_proven"]
        )
        for formula_id in LOCKED_EIGHT:
            self.assertRegex(self.html, rf"\b{re.escape(formula_id)}\b")

    def test_five_public_bodies_match_six_internal_engines(self) -> None:
        observed = [row["slug"] for row in self.manifest["verticals"]]
        self.assertEqual(observed, VERTICALS)
        self.assertEqual(self.html.count('class="body-card"'), 5)
        for slug in VERTICALS:
            with self.subTest(slug=slug):
                self.assertIn(f'id="body-{slug}"', self.html)
        for vertical in self.manifest["verticals"]:
            self.assertEqual(
                vertical["formula_binding"],
                "complete_locked_eight_via_shared_anatomy",
            )
            self.assertGreaterEqual(len(vertical["workflow"]), 5)
            self.assertTrue(vertical["canonical_source"])
            self.assertTrue(vertical["service_source"])

        taxonomy = self.manifest["public_product_taxonomy"]
        self.assertEqual(taxonomy["public_domain_body_count"], 5)
        self.assertEqual(taxonomy["public_domain_bodies"], VERTICALS)
        self.assertEqual(taxonomy["internal_engine_count"], 6)
        self.assertEqual(
            taxonomy["internal_engines"],
            ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"],
        )
        self.assertEqual(
            taxonomy["folded_into_killinchu"],
            ["aegis", "sentra", "immune", "vessels"],
        )
        self.assertNotIn('id="body-sentra"', self.html)
        self.assertNotIn('id="body-vessels"', self.html)
        killinchu = next(row for row in self.manifest["verticals"] if row["slug"] == "killinchu")
        self.assertEqual(killinchu["internal_engines"], ["sentra", "killinchu"])
        self.assertEqual(
            set(killinchu["capability_planes"]),
            {"aegis", "sentra_defend", "immune", "vessels_maritime", "counter_uas_airspace"},
        )

    def test_clean_room_policy_rejects_proprietary_source_copying(self) -> None:
        policy = self.manifest["clean_room_inspiration"]
        self.assertIn("Do not copy proprietary source", policy["rule"])
        allowed = {
            "pattern_only",
            "open_standard_or_licensed_oss_only",
            "open_source_with_attribution",
            "pattern_or_licensed_api; AISdb/open components by license",
            "pattern_and_public_benchmarks",
        }
        for item in policy["patterns"]:
            self.assertIn(item["reuse"], allowed)
            self.assertNotIn("copy", item["reuse"].lower())

    def test_vertical_publisher_pin_matches_current_declared_source(self) -> None:
        publisher = PUBLISHER.read_text(encoding="utf-8")
        contract_test = PUBLISHER_TEST.read_text(encoding="utf-8")
        active_revision = self.active_pin["source_revision"]
        self.assertIn(f'SOURCE_REVISION = "{active_revision}"', publisher)
        self.assertIn(f'SOURCE_REVISION = "{active_revision}"', contract_test)
        self.assertEqual(
            self.active_pin["repository"],
            "szl-holdings/vertical-services",
        )
        self.assertEqual(self.active_pin["runtime_version"], "2.2.0")
        self.assertEqual(
            self.active_pin["predecessor_revision"],
            HISTORICAL_VERTICAL_REVISION,
        )
        self.assertEqual(self.active_pin["guard"], "require-default-branch-tip")
        self.assertFalse(self.active_pin["historical_strategy_manifest_rewritten"])
        self.assertFalse(self.active_pin["authority"]["effectors_enabled"])
        self.assertTrue(self.active_pin["authority"]["human_approval_required"])
        stale = "96c4ffa8b9a8948c9ba84dc57c0c45885feaf5de"
        self.assertNotIn(stale, publisher)
        self.assertNotIn(stale, contract_test)
        intelligence = self.manifest["intelligence_fabric"]
        self.assertEqual(intelligence["runtime_version"], "2.2.0")
        self.assertEqual(
            intelligence["source_revision"],
            HISTORICAL_VERTICAL_REVISION,
        )
        self.assertEqual(
            intelligence["internal_engines"],
            ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"],
        )
        self.assertEqual(
            intelligence["killinchu_capability_aliases"],
            {"aegis": "sentra", "immune": "sentra", "vessels": "killinchu"},
        )
        self.assertFalse(intelligence["authority"]["hatun_can_authorize"])
        self.assertFalse(intelligence["authority"]["caller_supplied_model_endpoints"])

    def test_no_new_runtime_cdn_or_embedded_vendor_source_is_introduced(self) -> None:
        section = self.html.split(
            "<!-- ====================== LIVING COMMAND FABRIC ====================== -->",
            1,
        )[1].split(
            "<!-- ====================== FLAGSHIPS — three products max ====================== -->",
            1,
        )[0]
        self.assertNotIn("<script", section.lower())
        self.assertNotIn("<iframe", section.lower())
        self.assertNotIn("cdn.", section.lower())
        self.assertNotIn("unpkg", section.lower())
        self.assertNotIn("jsdelivr", section.lower())


if __name__ == "__main__":
    unittest.main()
