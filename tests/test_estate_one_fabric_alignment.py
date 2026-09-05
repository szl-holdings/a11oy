#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
LOCKED = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]


class EstateOneFabricAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_one_authority_graph(self) -> None:
        contract = self.value["estate_alignment_contract"]
        self.assertEqual(contract["schema"], "szl.estate-alignment/v1")
        self.assertEqual(contract["repository"], "szl-holdings/.github")
        self.assertEqual(contract["product_origin"], "https://a-11-oy.com")
        self.assertEqual(contract["proof_origin"], "https://a11oy.net")
        self.assertEqual(contract["artifact_registry"], "https://huggingface.co/SZLHOLDINGS")

    def test_three_five_six_taxonomy(self) -> None:
        taxonomy = self.value["public_product_taxonomy"]
        self.assertEqual(taxonomy["commercial_flagships"], ["a11oy", "killinchu", "forge"])
        self.assertEqual(taxonomy["commercial_flagship_count"], 3)
        self.assertEqual(taxonomy["public_domain_bodies"], ["terra", "killinchu", "counsel", "finance", "lyte"])
        self.assertEqual(taxonomy["public_domain_body_count"], 5)
        self.assertEqual(taxonomy["internal_engines"], ["sentra", "lyte", "killinchu", "finance", "terra", "counsel"])
        self.assertEqual(taxonomy["internal_engine_count"], 6)
        self.assertEqual(taxonomy["folded_into_killinchu"], ["aegis", "sentra", "immune", "vessels"])

    def test_lyte_uses_source_owned_runtime(self) -> None:
        lyte = next(row for row in self.value["verticals"] if row["slug"] == "lyte")
        self.assertEqual(lyte["canonical_source"], "szl-holdings/lyte-services")
        self.assertEqual(lyte["service_source"], "szl-holdings/lyte-services")
        self.assertEqual(lyte["service_runtime_version"], "3.0.0")
        self.assertEqual(lyte["service_revision"], self.value["authorities"]["lyte"]["revision"])

    def test_census_and_formula_contract_are_exact(self) -> None:
        estate = self.value["estate"]
        self.assertEqual(estate["repository_count"], estate["active_repository_count"] + estate["archived_repository_count"])
        self.assertEqual(estate["repository_count"], estate["public_repository_count"] + estate["private_repository_count"])
        self.assertEqual(self.value["authorities"]["lean_kernel"]["locked_proven_ids"], LOCKED)
        self.assertEqual(self.value["authorities"]["lean_kernel"]["locked_proven_count"], 8)
        self.assertFalse(self.value["formula_contract"]["lambda"]["authorizes_actions"])


if __name__ == "__main__":
    unittest.main()
