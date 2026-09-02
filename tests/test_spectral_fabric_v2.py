#!/usr/bin/env python3
"""Offline contracts for the SZL Spectral Fabric v2 presentation layer."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "console" / "assets" / "szl-spectral-v2.css"
JS_PATH = ROOT / "console" / "assets" / "szl-flow.js"
BASE_CSS_PATH = ROOT / "console" / "assets" / "szl-flow.css"
REGISTRY_PATH = ROOT / "docs" / "frontend-theme-registry-v2.json"
CONTRACT_PATH = ROOT / "docs" / "SZL_SPECTRAL_FABRIC_V2.md"


class SpectralFabricV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.base_css = BASE_CSS_PATH.read_text(encoding="utf-8")
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_assets_are_bounded_local_and_syntactically_balanced(self) -> None:
        self.assertLess(CSS_PATH.stat().st_size, 32_000)
        self.assertLess(JS_PATH.stat().st_size, 24_000)
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        self.assertIn('var SPECTRAL_STYLE = "/assets/szl-spectral-v2.css"', self.js)
        self.assertNotRegex(self.css + self.js, r"https?://(?:cdn|unpkg|jsdelivr|fonts\.googleapis)")

    def test_runtime_is_nontracking_and_does_not_fabricate_data(self) -> None:
        combined = self.css + self.js
        for prohibited in (
            "fetch(",
            "XMLHttpRequest",
            "sendBeacon",
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "google-analytics",
        ):
            self.assertNotIn(prohibited, combined)
        self.assertIn("No fabricated operational state", self.css)
        self.assertIn("never invents telemetry", self.contract)

    def test_every_core_product_has_a_distinct_instrument(self) -> None:
        instruments = self.registry["product_instruments"]
        self.assertEqual(len(instruments), 15)
        self.assertEqual(len({item["route"] for item in instruments}), 15)
        self.assertEqual(len({item["theme"] for item in instruments}), 15)
        for item in instruments:
            self.assertIn(f'body[data-szl-theme="{item["theme"]}"]', self.css)
            self.assertIn(item["label"], self.js)

    def test_holographic_field_has_six_composable_layers(self) -> None:
        for layer in ("mesh", "orbit", "nodes", "beam", "scan", "bloom"):
            self.assertIn(f"szl-spectral-{layer}", self.css)
            self.assertIn(f'"{layer}"', self.js)
        self.assertIn("requestAnimationFrame", self.js)
        self.assertIn("pointermove", self.js)
        self.assertIn("--szl-spectral-scroll", self.js)
        self.assertNotIn("setInterval", self.js)

    def test_performance_tiers_are_adaptive_and_private(self) -> None:
        for token in (
            "prefers-reduced-motion",
            "saveData",
            "deviceMemory",
            "hardwareConcurrency",
            'return "quiet"',
            'return "balanced"',
            'return "full"',
        ):
            self.assertIn(token, self.js)
        for tier in ("balanced", "quiet"):
            self.assertIn(f'html[data-szl-performance="{tier}"]', self.css)

    def test_accessibility_and_responsive_contract_is_preserved(self) -> None:
        combined = self.base_css + self.css + self.js
        for token in (
            "min-height: 44px",
            "focus-visible",
            "safe-area-inset-bottom",
            "prefers-reduced-motion",
            "prefers-contrast",
            "forced-colors",
            "@media print",
            'event.key !== "Escape"',
            'aria-live',
            'aria-current',
        ):
            self.assertIn(token, combined)
        self.assertEqual(self.registry["shared_contract"]["minimum_touch_target_px"], 44)
        self.assertEqual(self.registry["shared_contract"]["viewports"], [320, 360, 390, 768, 1024, 1440])

    def test_five_estate_journeys_and_two_origins_remain_stable(self) -> None:
        journeys = self.registry["shared_contract"]["journeys"]
        self.assertEqual(
            [item["label"] for item in journeys],
            ["Start Here", "Products & Demos", "Models & Data", "Kernels & SDKs", "Proofs & Research"],
        )
        for label in (item["label"] for item in journeys):
            self.assertIn(label, self.js)
        self.assertIn("https://a-11-oy.com", self.js)
        self.assertIn("https://a11oy.net", self.js)

    def test_originality_boundary_and_reserved_palette_are_explicit(self) -> None:
        boundary = self.registry["originality_boundary"]
        self.assertIs(boundary["third_party_assets"], False)
        self.assertIs(boundary["third_party_code"], False)
        self.assertIs(boundary["third_party_trade_dress_replication"], False)
        self.assertIsNone(re.search(r"\b(?:purple|violet|magenta)\b", self.css + self.js, re.IGNORECASE))

    def test_space_families_are_varied_but_share_the_contract(self) -> None:
        families = self.registry["space_families"]
        self.assertGreaterEqual(len(families), 12)
        self.assertEqual(len({item["motif"] for item in families}), len(families))
        self.assertTrue(all(item["examples"] for item in families))
        self.assertIs(self.registry["shared_contract"]["runtime_data_claims_from_decoration"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
