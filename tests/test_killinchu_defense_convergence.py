#!/usr/bin/env python3
"""Network-free truth tests for the Killinchu/Aegis/Vessels convergence."""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
VISION = ROOT / "docs" / "strategy" / "living-command-fabric.v1.json"
CONVERGENCE = ROOT / "docs" / "strategy" / "killinchu-defense-convergence.v1.json"
PUBLISHER = ROOT / "scripts" / "hf_publish_vertical_flagships_v4_impl.py"
HOLO_JS = ROOT / "console" / "assets" / "szl-holo-v2.js"
THEME_REGISTRY = ROOT / "docs" / "holographic-experience-v2" / "theme-registry.json"

LOCKED_EIGHT = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]


class KillinchuDefenseConvergenceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = LANDING.read_text(encoding="utf-8")
        cls.vision = json.loads(VISION.read_text(encoding="utf-8"))
        cls.contract = json.loads(CONVERGENCE.read_text(encoding="utf-8"))
        cls.publisher = PUBLISHER.read_text(encoding="utf-8")
        cls.holo = HOLO_JS.read_text(encoding="utf-8")
        cls.theme = json.loads(THEME_REGISTRY.read_text(encoding="utf-8"))

    def test_front_door_has_five_bodies_and_one_defense_product(self) -> None:
        self.assertIn("FIVE DOMAIN BODIES", self.html)
        self.assertNotIn("SIX DOMAIN BODIES", self.html)
        self.assertEqual(self.html.count('class="body-card"'), 5)
        self.assertIn('id="body-killinchu"', self.html)
        self.assertNotIn('id="body-sentra"', self.html)
        self.assertNotIn('id="body-vessels"', self.html)
        defense_section = self.html.split('id="body-killinchu"', 1)[1].split("</article>", 1)[0]
        for literal in (
            "Aegis",
            "defensive/cyber lobe",
            "Vessels",
            "maritime lobe",
            "EFFECTORS SIMULATED",
            "Canonical source",
            "Canonical product",
        ):
            with self.subTest(literal=literal):
                self.assertIn(literal, defense_section)

    def test_machine_readable_verticals_have_one_killinchu_row(self) -> None:
        rows = self.vision["verticals"]
        self.assertEqual([row["slug"] for row in rows], ["terra", "counsel", "finance", "killinchu", "lyte"])
        self.assertEqual(self.vision["estate"]["domain_body_count"], 5)
        killinchu = next(row for row in rows if row["slug"] == "killinchu")
        self.assertEqual(killinchu["canonical_source"], "szl-holdings/killinchu")
        self.assertEqual(killinchu["formula_binding"], "complete_locked_eight_via_shared_anatomy")
        self.assertEqual([lobe["id"] for lobe in killinchu["lobes"]], ["aegis", "vessels"])
        self.assertTrue(all(lobe["standalone_product"] is False for lobe in killinchu["lobes"]))
        self.assertEqual(killinchu["effectors"], "SIMULATED_UNLESS_INDEPENDENTLY_PROVED")

    def test_convergence_contract_preserves_source_but_removes_product_competition(self) -> None:
        self.assertEqual(self.contract["canonical_product"]["id"], "killinchu")
        self.assertEqual(self.contract["shared_contract"]["formula_ids"], LOCKED_EIGHT)
        self.assertEqual(self.contract["shared_contract"]["lambda"], "CONJECTURE_1_ADVISORY")
        self.assertEqual(self.contract["shared_contract"]["consequential_actions"], "HUMAN_AUTHORITY_REQUIRED")
        self.assertFalse(self.contract["shared_contract"]["destructive_or_offensive_autonomy"])
        self.assertTrue(self.contract["compatibility_policy"]["preserve_source_and_receipts"])
        self.assertFalse(self.contract["compatibility_policy"]["present_as_independent_flagship"])
        self.assertFalse(self.contract["compatibility_policy"]["delete_source"])

    def test_holographic_identity_canonicalizes_all_defense_aliases(self) -> None:
        for alias in ("aegis", "sentra", "vessels"):
            self.assertIn(f'{alias}: "killinchu"', self.holo)
            self.assertEqual(
                self.theme["consolidated_surfaces"][alias]["canonical_surface"],
                "killinchu",
            )
        self.assertIn("CONSOLIDATED_SURFACES[requestedId] || requestedId", self.holo)

    def test_hf_compatibility_spaces_are_lobes_not_flagships(self) -> None:
        ast.parse(self.publisher)
        self.assertIn('CONSOLIDATED_ALIASES: dict[str, dict[str, str]]', self.publisher)
        self.assertIn('"sentra": {"canonical_product": "killinchu", "lobe": "aegis"}', self.publisher)
        self.assertIn('"vessels": {"canonical_product": "killinchu", "lobe": "vessels"}', self.publisher)
        for title, lobe in (("Killinchu · Aegis", "aegis"), ("Killinchu · Vessels", "vessels")):
            block = self.publisher.split(f'"title": "{title}"', 1)[1].split("    },", 1)[0]
            self.assertIn('"canonical_product": "killinchu"', block)
            self.assertIn(f'"lobe": "{lobe}"', block)
            self.assertIn('"standalone_product": False', block)
            self.assertIn('"source": "https://github.com/szl-holdings/killinchu"', block)

    def test_no_new_external_runtime_script_or_embedded_vendor_ui(self) -> None:
        section = self.html.split(
            "<!-- ====================== DOMAIN BODIES ====================== -->",
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
