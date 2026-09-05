#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
ACTIVE_PIN = ROOT / "docs" / "strategy" / "vertical-services-active-pin.v1.json"
PUBLISHER_TEST = ROOT / "tests" / "test_hf_publish_vertical_flagships_v4.py"
EXPECTED = {
    "repository_count": 123,
    "active_repository_count": 89,
    "archived_repository_count": 34,
    "public_repository_count": 117,
    "private_repository_count": 6,
}
HISTORICAL_VERTICAL_SERVICES_REVISION = "83edba5c5e730c91d8f5f0a6531213fb860677af"
CURRENT_VERTICAL_SERVICES_AUTHORITY = "895c4de2e8c07236c4adeabc7376ca5367b2b835"


class EstateCensusSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_authenticated_snapshot_is_exact_and_arithmetic_closes(self) -> None:
        estate = self.value["estate"]
        self.assertEqual({key: estate[key] for key in EXPECTED}, EXPECTED)
        self.assertEqual(
  estate["repository_count"],
  estate["active_repository_count"] + estate["archived_repository_count"],
        )
        self.assertEqual(
  estate["repository_count"],
  estate["public_repository_count"] + estate["private_repository_count"],
        )
        self.assertIn("Authenticated GitHub installation inventory", estate["census_method"])
        self.assertIn("point-in-time", estate["census_method"])

    def test_current_authority_and_historical_strategy_pins_are_distinct(self) -> None:
        self.assertEqual(
  self.value["authorities"]["vertical_services"]["revision"],
  CURRENT_VERTICAL_SERVICES_AUTHORITY,
        )
        self.assertEqual(
  self.value["public_product_taxonomy"]["vertical_services_revision"],
  HISTORICAL_VERTICAL_SERVICES_REVISION,
        )
        self.assertEqual(
  self.value["intelligence_fabric"]["source_revision"],
  HISTORICAL_VERTICAL_SERVICES_REVISION,
        )

    def test_active_publisher_revision_is_carried_by_contract_test(self) -> None:
        active = json.loads(ACTIVE_PIN.read_text(encoding="utf-8"))
        literal = f'SOURCE_REVISION = "{active["source_revision"]}"'
        self.assertIn(literal, PUBLISHER_TEST.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
