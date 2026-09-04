#!/usr/bin/env python3
"""Offline contract for the founder-requested fluid estate rail v4."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "console" / "assets" / "szl-holo-v2.css"
JS_PATH = ROOT / "console" / "assets" / "szl-holo-v2.js"
CSS_MARKER = "/* SZL FLUID ESTATE RAIL V4 */"
JS_MARKER = "/* SZL FLUID ESTATE RAIL V4 */"


class FluidEstateRailV4Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.javascript = JS_PATH.read_text(encoding="utf-8")
        cls.css_extension = cls.css.split(CSS_MARKER, 1)[1]
        cls.js_extension = cls.javascript.split(JS_MARKER, 1)[1]

    def test_extension_is_single_and_preserves_holo_core(self) -> None:
        self.assertEqual(self.css.count(CSS_MARKER), 1)
        self.assertEqual(self.javascript.count(JS_MARKER), 1)
        self.assertIn("A11oy Holo-Constellation v2.0.0", self.css)
        self.assertIn("A11oy Holo-Constellation v2.0.0", self.javascript)
        self.assertIn("0x811c9dc5", self.javascript)

    def test_all_requested_estate_tabs_are_real_local_routes(self) -> None:
        expected = {
            "A11OY": "/console",
            "KILLINCHU": "/killinchu",
            "HATUN": "/hatun-mcp",
            "COCKPIT": "/cockpit",
            "SECOND BRAIN": "/brain",
            "ANATOMY": "/anatomy-v5",
            "LIVING ANATOMY": "/living-anatomy",
            "KHIPU": "/khipu",
            "IMMUNE": "/immune",
            "LYTE": "/lyte",
            "ESTATE": "/estate",
        }
        for label, href in expected.items():
            self.assertIn(f'label: "{label}"', self.js_extension)
            self.assertIn(f'href: "{href}"', self.js_extension)
        self.assertNotIn("huggingface.co", self.js_extension)
        self.assertNotIn("hf.space", self.js_extension)

    def test_second_brain_and_anatomy_are_explicitly_bound(self) -> None:
        self.assertGreaterEqual(self.js_extension.count('bind: "brain-anatomy"'), 3)
        self.assertIn('dataset.szlBrainAnatomyNav = "bound"', self.js_extension)
        self.assertIn('[data-bind="brain-anatomy"]::before', self.css_extension)

    def test_scroller_supports_touch_wheel_keyboard_and_arrows(self) -> None:
        for token in (
            "scrollBy",
            "scrollIntoView",
            '"wheel"',
            '"ArrowLeft"',
            '"ArrowRight"',
            '"Home"',
            '"End"',
            "ResizeObserver",
            "Scroll estate tabs left",
            "Scroll estate tabs right",
        ):
            self.assertIn(token, self.js_extension)
        for token in (
            "overflow-x: auto !important",
            "touch-action: pan-x",
            "scroll-snap-type: x proximity",
            "overscroll-behavior-inline: contain",
            "-webkit-overflow-scrolling: touch",
        ):
            self.assertIn(token, self.css_extension)

    def test_public_mode_cannot_hide_killinchu_or_estate(self) -> None:
        self.assertIn(':not([data-operator="1"])', self.css_extension)
        self.assertIn('a.szl-estate-link[href*="killinchu"]', self.css_extension)
        self.assertIn("display: flex !important", self.css_extension)

    def test_a11oy_front_door_uses_cyan_not_lime_or_gold(self) -> None:
        self.assertIn("--szl-holo-accent: #57ebff !important", self.css_extension)
        self.assertIn("--szl-holo-accent-2: #31e6d1 !important", self.css_extension)
        self.assertIn("--gold: #8fa5b8 !important", self.css_extension)
        self.assertIn("--warn: #8fa5b8 !important", self.css_extension)

    def test_all_screen_accessibility_contract(self) -> None:
        for token in (
            "max-width: 1380px",
            "max-width: 760px",
            "max-width: 430px",
            "prefers-reduced-motion",
            "forced-colors",
            "focus-visible",
            "min-height: 44px",
        ):
            self.assertIn(token, self.css_extension)
        without_comments = re.sub(r"/\*.*?\*/", "", self.css_extension, flags=re.DOTALL)
        self.assertEqual(without_comments.count("{"), without_comments.count("}"))

    def test_navigation_extension_is_passive_and_local(self) -> None:
        for prohibited in (
            "fetch(",
            "XMLHttpRequest",
            "sendBeacon",
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "setInterval",
        ):
            self.assertNotIn(prohibited, self.js_extension)


if __name__ == "__main__":
    unittest.main(verbosity=2)
