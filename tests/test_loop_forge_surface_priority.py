# SPDX-License-Identifier: Apache-2.0

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LoopForgeSurfacePriorityTests(unittest.TestCase):
    def test_loop_forge_is_a_unique_top_three_surface(self):
        source = (ROOT / "static" / "3d" / "holographic.html").read_text(
            encoding="utf-8"
        )
        surface_block = source.split("const SURFACES = [", 1)[1].split("];", 1)[0]
        ids = re.findall(r'\{\s*id:\s*"([^"]+)"', surface_block)
        self.assertEqual(ids.count("loopforge"), 1)
        self.assertLess(ids.index("loopforge"), 3)
        loop_line = next(
            line for line in surface_block.splitlines() if 'id: "loopforge"' in line
        )
        self.assertIn("bounded kernel-gated recursion", loop_line)
        self.assertIn("MODELED reward signals", loop_line)

    def test_safety_doc_keeps_lambda_and_kernel_limits_visible(self):
        safety = (ROOT / "docs" / "LOOP_FORGE_SAFETY.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Conjecture 1", safety)
        self.assertIn("machine-checked false", safety)
        self.assertIn("not executed in the hosted surface", safety)
        self.assertIn("does not prove", safety)


if __name__ == "__main__":
    unittest.main()
