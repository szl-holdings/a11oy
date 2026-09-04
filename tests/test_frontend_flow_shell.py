#!/usr/bin/env python3
"""Offline contract checks for the product Flow Shell and KEEP-6 registry."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "console" / "assets" / "szl-flow.css"
JS = ROOT / "console" / "assets" / "szl-flow.js"
REGISTRY = ROOT / "docs" / "frontend-theme-registry-v1.json"
STATE = ROOT / "docs" / "frontend-flow-shell-state.json"
LANDING = ROOT / "a11oy_landing.html"
HATUN = ROOT / "pages" / "wires.html"
DOCKER = ROOT / "Dockerfile"
STYLE_MARKER = 'data-szl-flow-asset="style"'
SCRIPT_MARKER = 'data-szl-flow-asset="script"'
HOLO_STYLE_MARKER = 'data-szl-holo-asset="style-v2"'
HOLO_SCRIPT_MARKER = 'data-szl-holo-asset="script-v2"'


class FrontendFlowShellContract(unittest.TestCase):
    def setUp(self) -> None:
        self.css = CSS.read_text(encoding="utf-8")
        self.js = JS.read_text(encoding="utf-8")
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.state = json.loads(STATE.read_text(encoding="utf-8"))

    def test_assets_are_local_accessible_and_touch_safe(self) -> None:
        self.assertIn("min-height: 44px", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("safe-area-inset-bottom", self.css)
        self.assertNotRegex(self.css + self.js, r"https?://(?:cdn|unpkg|jsdelivr)")
        self.assertIn("COPY console/ ./static/", DOCKER.read_text(encoding="utf-8"))

    def test_five_journeys_and_two_origins_are_one_grammar(self) -> None:
        for label in (
            "Start Here",
            "Products & Demos",
            "Models & Data",
            "Kernels & SDKs",
            "Proofs & Research",
        ):
            self.assertIn(label, self.js)
        self.assertIn("https://a-11-oy.com", self.js)
        self.assertIn("https://a11oy.net", self.js)
        self.assertIn("aria-current", self.js)

    def test_keep_six_have_six_distinct_instruments(self) -> None:
        rows = self.registry["application_spaces"]
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({row["id"] for row in rows}), 6)
        self.assertEqual(len({row["theme"] for row in rows}), 6)
        self.assertEqual(self.registry["shared_contract"]["minimum_touch_target_px"], 44)
        self.assertEqual(self.registry["shared_contract"]["viewports"], [320, 360, 390, 768, 1024, 1440])

    def test_route_themes_are_not_one_generic_skin(self) -> None:
        themes = set(self.registry["product_routes"].values())
        self.assertGreaterEqual(len(themes), 10)
        for theme in ("operator", "atlas", "anatomy", "sentinel", "weave", "forensic"):
            self.assertIn(f'data-szl-theme="{theme}"', self.css)

    def test_rollout_state_controls_document_enforcement(self) -> None:
        self.assertIn(self.state["state"], {"ASSETS_READY", "ROLLED_OUT"})
        if self.state["state"] == "ROLLED_OUT":
            landing = LANDING.read_text(encoding="utf-8")
            self.assertEqual(landing.count(STYLE_MARKER), 1)
            self.assertEqual(landing.count(SCRIPT_MARKER), 1)
            for rel in self.state.get("injected_documents", []):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(text.count(STYLE_MARKER), 1, rel)
                self.assertEqual(text.count(SCRIPT_MARKER), 1, rel)

    def test_hatun_owns_one_bespoke_shell_without_double_injection(self) -> None:
        rel = "pages/wires.html"
        self.assertEqual(self.state.get("bespoke_shell_documents"), [rel])
        self.assertNotIn(rel, self.state.get("injected_documents", []))
        text = HATUN.read_text(encoding="utf-8")
        self.assertEqual(text.count(STYLE_MARKER), 0)
        self.assertEqual(text.count(SCRIPT_MARKER), 0)
        self.assertEqual(text.count(HOLO_STYLE_MARKER), 1)
        self.assertEqual(text.count(HOLO_SCRIPT_MARKER), 1)
        self.assertIn('class="szl-hatun-gateway"', text)
        self.assertIn("/api/a11oy/v1/mesh/state", text)

    def test_css_is_balanced_and_no_reserved_hue_literal_is_added(self) -> None:
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        self.assertIsNone(re.search(r"\b(?:purple|violet|magenta)\b", self.css + self.js, re.I))


if __name__ == "__main__":
    unittest.main()
