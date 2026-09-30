#!/usr/bin/env python3
"""Offline contract for the SZL Obsidian Signal product family."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "console" / "assets" / "szl-holo-v2.css").read_text(encoding="utf-8")
REGISTRY = json.loads(
    (ROOT / "docs" / "holographic-experience-v2" / "theme-registry.json").read_text(
        encoding="utf-8"
    )
)
WIRES = (ROOT / "pages" / "wires.html").read_text(encoding="utf-8")


class ObsidianSignalFamilyContract(unittest.TestCase):
    def test_family_has_one_shell_and_three_distinct_instruments(self) -> None:
        surfaces = REGISTRY["surfaces"]
        expected = {
            "a11oy": ("command-constellation", "#57ebff"),
            "killinchu": ("field-vector", "#68e8d8"),
            "hatun": ("gateway-weave", "#9e9bff"),
        }
        for name, (motif, accent) in expected.items():
            self.assertIn(name, surfaces)
            self.assertEqual(surfaces[name]["motif"], motif)
            self.assertEqual(surfaces[name]["palette"][4], accent)
        self.assertEqual(
            len({surfaces[name]["motif"] for name in expected}),
            len(expected),
        )
        self.assertEqual(
            len({tuple(surfaces[name]["palette"]) for name in expected}),
            len(expected),
        )

    def test_shared_accessibility_and_state_grammar_is_explicit(self) -> None:
        contract = REGISTRY["shared_contract"]
        self.assertEqual(contract["pathways"], ["Understand", "Build", "Verify"])
        self.assertEqual(contract["minimum_touch_target_px"], 44)
        self.assertEqual(contract["horizontal_overflow"], "forbidden")
        for state in (
            "LIVE",
            "MEASURED",
            "REPORTED",
            "DECLARED",
            "DEGRADED",
            "UNAVAILABLE",
        ):
            self.assertIn(state, contract["state_vocabulary"])
        for token in (
            "safe-area-inset",
            "prefers-reduced-motion",
            "prefers-contrast",
            "forced-colors",
            "focus-visible",
            "min-height: 44px",
        ):
            self.assertIn(token, CSS)

    def test_a11oy_has_no_yellow_front_door_signal(self) -> None:
        a11oy = REGISTRY["surfaces"]["a11oy"]["palette"]
        self.assertEqual(a11oy[4:], ["#57ebff", "#31e6d1"])
        self.assertNotIn("#b8ff45", a11oy)
        self.assertIn("--szl-holo-accent: #57ebff !important", CSS)
        self.assertIn("--gold: #8fa5b8 !important", CSS)

    def test_hatun_is_a_canonical_product_route_not_a_duplicate_space(self) -> None:
        self.assertIn("<title>Hatun Gateway", WIRES)
        self.assertIn('class="szl-hatun-gateway"', WIRES)
        self.assertIn("/api/a11oy/v1/mesh/state", WIRES)
        self.assertIn("https://github.com/szl-holdings/hatun-mcp", WIRES)
        self.assertIn("Understand", WIRES)
        self.assertIn("Build", WIRES)
        self.assertIn("Verify", WIRES)
        self.assertNotIn("szlholdings-hatun-mcp.hf.space", WIRES)
        self.assertEqual(WIRES.count('data-szl-holo-asset="style-v2"'), 1)
        self.assertEqual(WIRES.count('data-szl-holo-asset="script-v2"'), 1)

    def test_hatun_runtime_content_is_fail_closed(self) -> None:
        for token in (
            'var ENDPOINT="/api/a11oy/v1/mesh/state"',
            '"UNAVAILABLE"',
            "Nothing was fabricated",
            "No wire state was fabricated",
            'cache:"no-store"',
            "AbortController",
        ):
            self.assertIn(token, WIRES)
        self.assertNotIn("Math.random", WIRES)
        self.assertNotIn("setInterval", WIRES)

    def test_family_stylesheet_is_small_and_balanced(self) -> None:
        without_comments = re.sub(r"/\*.*?\*/", "", CSS, flags=re.DOTALL)
        self.assertEqual(without_comments.count("{"), without_comments.count("}"))
        self.assertLess(len(CSS.encode("utf-8")), 80_000)
        self.assertLessEqual(CSS.count("animation:"), 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
