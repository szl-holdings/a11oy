#!/usr/bin/env python3
"""Offline contract for the A11oy mobile-to-theatre responsive layer."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "console" / "assets" / "szl-responsive-v3.css"
HOST = ROOT / "console" / "assets" / "szl-hologram-v2.css"
STATE = ROOT / "docs" / "responsive-experience-v3.json"
BINDER = ROOT / "scripts" / "bind_responsive_experience_v3.py"
MARKER = "szl-responsive-v3"


class ResponsiveExperienceV3Contract(unittest.TestCase):
    def setUp(self) -> None:
        self.css = CSS.read_text(encoding="utf-8")
        self.state = json.loads(STATE.read_text(encoding="utf-8"))

    def test_viewport_matrix_covers_phone_landscape_tablet_desktop_theatre(self) -> None:
        viewports = {(row["width"], row["height"]) for row in self.state["viewports"]}
        required = {
            (320, 568),
            (375, 812),
            (430, 932),
            (812, 375),
            (768, 1024),
            (1440, 900),
            (1920, 1080),
            (2560, 1440),
            (3440, 1440),
        }
        self.assertTrue(required.issubset(viewports))

    def test_mobile_and_theatre_layouts_are_explicit(self) -> None:
        for token in (
            "@media (max-width: 47.999rem)",
            "orientation: landscape",
            "@media (min-width: 100rem)",
            "@media (min-width: 150rem)",
            "grid-template-columns: repeat(12",
            "container-type: inline-size",
            "@container (max-width: 28rem)",
        ):
            self.assertIn(token, self.css)

    def test_touch_keyboard_and_form_contract(self) -> None:
        self.assertIn("--szl-touch: 44px", self.css)
        self.assertIn("--szl-touch-roomy: 48px", self.css)
        self.assertIn(":focus-visible", self.css)
        self.assertIn("@media (pointer: coarse)", self.css)
        self.assertIn("font-size: max(16px, 1em)", self.css)
        self.assertIn("touch-action: manipulation", self.css)

    def test_overflow_media_code_table_and_dialog_contract(self) -> None:
        for token in (
            "overflow-x: clip",
            "max-inline-size: 100%",
            "overscroll-behavior-inline: contain",
            "table-scroll",
            "max-block-size: min(90dvh",
            "aspect-ratio: var(--szl-stage-ratio",
        ):
            self.assertIn(token, self.css)

    def test_accessibility_and_environment_fallbacks(self) -> None:
        for token in (
            "safe-area-inset-top",
            "safe-area-inset-bottom",
            "prefers-reduced-motion",
            "prefers-contrast: more",
            "forced-colors: active",
            "@media print",
        ):
            self.assertIn(token, self.css)

    def test_local_only_and_no_behavioral_claims(self) -> None:
        self.assertIsNone(re.search(r"https?://", self.css, re.IGNORECASE))
        combined = self.css.lower()
        for prohibited in ("analytics", "localstorage", "sessionstorage", "document.cookie", "fetch("):
            self.assertNotIn(prohibited, combined)

    def test_binding_state_is_explicit(self) -> None:
        self.assertIn(self.state["state"], {"ASSET_READY", "BOUND"})
        self.assertEqual(self.state["requirements"]["horizontal_overflow_px"], 0)
        self.assertEqual(self.state["requirements"]["minimum_touch_target_px"], 44)
        self.assertEqual(self.state["requirements"]["external_runtime_dependencies"], 0)
        if self.state["state"] == "BOUND":
            host = HOST.read_text(encoding="utf-8")
            self.assertEqual(host.count(MARKER), 1)
            self.assertTrue(host.lstrip().startswith('@import url("./szl-responsive-v3.css")'))

    def test_binder_exists_and_is_narrow(self) -> None:
        text = BINDER.read_text(encoding="utf-8")
        self.assertIn("console\" / \"assets\" / \"szl-hologram-v2.css", text)
        self.assertNotIn("rglob(\"*.html\")", text)
        self.assertIn("--check", text)


if __name__ == "__main__":
    unittest.main()
