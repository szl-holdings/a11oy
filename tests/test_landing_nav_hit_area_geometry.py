from __future__ import annotations

import math
from pathlib import Path
import re
import unittest


LANDING = Path(__file__).resolve().parents[1] / "a11oy_landing.html"
RULE_RE = re.compile(r"[.]nav nav a[{](?P<body>[^}]*)[}]")


class LandingNavigationHitAreaGeometryTests(unittest.TestCase):
    def test_rounded_nav_control_contains_a_44px_square(self) -> None:
        source = LANDING.read_text(encoding="utf-8")
        match = RULE_RE.search(source)
        self.assertIsNotNone(match, "canonical navigation anchor rule is missing")
        body = match.group("body")

        def pixels(name: str) -> float:
            value = re.search(rf"{re.escape(name)}:([0-9]+(?:[.][0-9]+)?)px", body)
            self.assertIsNotNone(value, f"{name} is not fixed in pixels")
            return float(value.group(1))

        width = pixels("min-width")
        height = pixels("min-height")
        radius = pixels("border-radius")
        required_box = 44.0 + 2.0 * radius * (1.0 - 1.0 / math.sqrt(2.0))
        self.assertGreaterEqual(width, required_box)
        self.assertGreaterEqual(height, required_box)
        self.assertIn("pointer-events:auto", body)
        self.assertIn("touch-action:manipulation", body)

    def test_holographic_primary_navigation_target_remains_present(self) -> None:
        source = LANDING.read_text(encoding="utf-8")
        self.assertEqual(source.count('<a href="/holographic">Holo</a>'), 1)


if __name__ == "__main__":
    unittest.main()
