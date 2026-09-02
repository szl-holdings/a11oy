#!/usr/bin/env python3
"""Offline contracts for the mobile-to-theatre adaptive experience layer."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "console" / "assets" / "szl-adaptive-theatre-v3.css"
JS = ROOT / "console" / "assets" / "szl-adaptive-theatre-v3.js"
HOST_CSS = ROOT / "console" / "assets" / "szl-hologram-v2.css"
HOST_JS = ROOT / "console" / "assets" / "szl-hologram-v2.js"
CSS_IMPORT = '@import url("/assets/szl-adaptive-theatre-v3.css"); /* szl:adaptive-theatre-v3 */'
JS_LOADER = 'data-szl-adaptive-theatre-v3-loader'


class AdaptiveTheatreV3Contract(unittest.TestCase):
    def setUp(self) -> None:
        self.css = CSS.read_text(encoding="utf-8")
        self.js = JS.read_text(encoding="utf-8")
        self.host_css = HOST_CSS.read_text(encoding="utf-8")
        self.host_js = HOST_JS.read_text(encoding="utf-8")

    def test_host_assets_load_the_layer_exactly_once(self) -> None:
        self.assertEqual(self.host_css.count(CSS_IMPORT), 1)
        self.assertEqual(self.host_js.count(JS_LOADER), 1)

    def test_mobile_tablet_desktop_and_theatre_modes_exist(self) -> None:
        for mode in ("mobile", "tablet", "desktop", "theatre"):
            self.assertIn(f'"{mode}"', self.js)
        self.assertIn("min-width: 1680px", self.css)
        self.assertIn('data-szl-display-mode="theatre"', self.css)
        self.assertIn("orientation: landscape", self.css)

    def test_touch_safe_and_overflow_safe(self) -> None:
        self.assertIn("--szl-control-min: 44px", self.css)
        self.assertIn("--szl-control-coarse: 48px", self.css)
        self.assertIn("overflow-x: clip", self.css)
        self.assertIn("overflow-x: auto", self.css)
        self.assertIn("safe-area-inset-bottom", self.css)
        self.assertIn("container-type: inline-size", self.css)

    def test_accessibility_modes_are_explicit(self) -> None:
        for contract in (
            "prefers-reduced-motion: reduce",
            "prefers-contrast: more",
            "forced-colors: active",
            "@media print",
            ":focus-visible",
        ):
            self.assertIn(contract, self.css)
        self.assertIn("aria-label", self.js)
        self.assertIn("IntersectionObserver", self.js)

    def test_controller_has_no_network_tracking_or_persistence(self) -> None:
        forbidden = (
            "fetch(",
            "XMLHttpRequest",
            "sendBeacon",
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "analytics",
        )
        for token in forbidden:
            self.assertNotIn(token, self.js)

    def test_assets_are_bounded_and_structurally_balanced(self) -> None:
        self.assertLess(CSS.stat().st_size, 32_000)
        self.assertLess(JS.stat().st_size, 20_000)
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        self.assertIsNone(re.search(r"https?://(?:cdn|unpkg|jsdelivr)", self.css + self.js))

    def test_decorative_state_is_not_telemetry(self) -> None:
        self.assertIn("Decorative motion is never telemetry", self.css)
        self.assertNotIn("MEASURED", self.js)
        self.assertNotIn("LIVE", self.js)


if __name__ == "__main__":
    unittest.main()
