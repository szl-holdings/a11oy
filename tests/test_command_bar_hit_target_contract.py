# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CommandBarHitTargetContract(unittest.TestCase):
    def test_shared_origin_controls_reserve_real_44px_hit_region(self) -> None:
        css = (ROOT / "static/shared/szl_command_bar.css").read_text(encoding="utf-8")
        match = re.search(
  r"[.]szl-origins a,[.]szl-origins button[.]szl-origin[{](.*?)[}]",
  css,
  flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = re.sub(r"\s+", "", match.group(1))
        self.assertIn("display:inline-flex", block)
        self.assertIn("align-items:center", block)
        self.assertIn("justify-content:center", block)
        self.assertIn("min-width:48px", block)
        self.assertIn("min-height:48px", block)
        self.assertIn("border-radius:6px", block)

        # A centered 44x44 square leaves two CSS pixels on every side.
        # At a 6px rounded corner, the square's outer corner remains
        # inside the quarter circle: hypot(6-2, 6-2) <= 6.
        self.assertLessEqual(math.hypot(4, 4), 6)

    def test_holo_link_uses_the_shared_origin_contract(self) -> None:
        js = (ROOT / "static/shared/szl_command_bar.js").read_text(encoding="utf-8")
        self.assertRegex(
  js,
  r"var holo = el[(]'a', [{][^}]*class: 'szl-origin'[^}]*href: '/holographic'",
        )
        self.assertIn("var origins = el('div', { class: 'szl-origins' }", js)


if __name__ == "__main__":
    unittest.main()
