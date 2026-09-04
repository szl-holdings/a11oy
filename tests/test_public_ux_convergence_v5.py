#!/usr/bin/env python3
"""Offline acceptance contract for the converged public experience."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "console" / "assets" / "szl-holo-v2.js").read_text(encoding="utf-8")
CSS = (ROOT / "console" / "assets" / "szl-holo-v2.css").read_text(encoding="utf-8")


class PublicUxConvergenceV5(unittest.TestCase):
    def test_one_five_item_global_navigation(self) -> None:
        for label in ("Overview", "Platform", "Portfolio", "Proof", "Investor"):
            self.assertIn(f'label: "{label}"', JS)
        self.assertIn('dataset.szlPrimaryNavigation = "five"', JS)
        self.assertIn("hasProductCommandBar()", JS)
        self.assertIn("hasProductCommandBar() ||", JS)
        self.assertIn('if (origins) origins.hidden = true', JS)
        self.assertIn('if (investor) investor.hidden = true', JS)

    def test_domain_surfaces_are_contextual_not_primary(self) -> None:
        self.assertIn('divider.textContent = "Product surfaces"', JS)
        self.assertIn("addContextualMenu", JS)
        primary = JS.split("var TOP_LINKS = [", 1)[1].split("];", 1)[0]
        for redundant in ("KILLINCHU", "HATUN", "SECOND BRAIN", "ANATOMY", "LIVING ANATOMY"):
            self.assertNotIn(redundant, primary)

    def test_console_geometry_never_allocates_a_chat_column(self) -> None:
        self.assertIn("grid-template-columns: minmax(216px, 244px) minmax(0, 1fr)", CSS)
        self.assertIn("The operator is an explicit overlay", CSS)
        self.assertIn("position: fixed", CSS)
        self.assertIn("width: min(420px, calc(100vw - 28px))", CSS)
        self.assertNotIn("grid-template-columns: 248px 1fr 370px", CSS)

    def test_mobile_tablet_desktop_breakpoints_and_safe_areas(self) -> None:
        for token in (
            "max-width: 1380px",
            "max-width: 1120px",
            "max-width: 900px",
            "max-width: 760px",
            "max-width: 430px",
            "safe-area-inset-top",
            "safe-area-inset-right",
            "safe-area-inset-bottom",
            "safe-area-inset-left",
            "min-height: 44px",
            "min-height: 48px",
        ):
            self.assertIn(token, CSS)

    def test_console_has_no_fourth_journey_navigation(self) -> None:
        self.assertIn('body[data-szl-instrument="Command Console"] .szl-flow-rail', CSS)
        self.assertIn("display: none !important", CSS)

    def test_accessibility_motion_and_fallbacks(self) -> None:
        for token in (
            "Skip to main content",
            "aria-current",
            "aria-expanded",
            "Escape",
            "prefers-reduced-motion",
            "prefers-contrast",
            "forced-colors",
            "@supports not",
            "@media print",
        ):
            self.assertIn(token, JS + CSS)
        self.assertNotIn("setInterval", JS)
        self.assertNotIn("fetch(", JS)

    def test_stylesheet_balanced_and_asset_bounded(self) -> None:
        without_comments = re.sub(r"/\*.*?\*/", "", CSS, flags=re.DOTALL)
        self.assertEqual(without_comments.count("{"), without_comments.count("}"))
        self.assertLess(len(JS.encode("utf-8")), 60_000)
        self.assertLess(len(CSS.encode("utf-8")), 80_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
