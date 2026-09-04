#!/usr/bin/env python3
# Regression contract for Flow Shell source ownership and mobile hit geometry.
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLLOUT_PATH = ROOT / "scripts" / "rollout_frontend_flow_shell.py"
STYLE_MARKER = 'data-szl-flow-asset="style"'
SCRIPT_MARKER = 'data-szl-flow-asset="script"'


def load_rollout():
    spec = importlib.util.spec_from_file_location("rollout_frontend_flow_shell", ROLLOUT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load rollout module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrontendSourceBoundaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rollout = load_rollout()

    def test_shared_and_vendored_html_are_never_source_mutated(self) -> None:
        integrations = ROOT / "pages" / "integrations.html"
        sda = ROOT / "spaces" / "sda" / "index.html"
        self.assertTrue(self.rollout.source_managed(integrations))
        self.assertTrue(self.rollout.source_managed(sda))

        candidates = {path.relative_to(ROOT).as_posix() for path in self.rollout.candidates()}
        self.assertNotIn("pages/integrations.html", candidates)
        self.assertNotIn("spaces/sda/index.html", candidates)

        for path in (integrations, sda):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(STYLE_MARKER, text, path.as_posix())
            self.assertNotIn(SCRIPT_MARKER, text, path.as_posix())

    def test_rollout_state_contains_only_eligible_bound_documents(self) -> None:
        state = json.loads(
            (ROOT / "docs" / "frontend-flow-shell-state.json").read_text(encoding="utf-8")
        )
        bound = set(state["injected_documents"])
        eligible = {path.relative_to(ROOT).as_posix() for path in self.rollout.candidates()}
        self.assertEqual(bound, eligible)
        self.assertEqual(state["examined_documents"], len(eligible))

    def test_mobile_controls_have_safe_rounded_hit_geometry(self) -> None:
        css = (ROOT / "console" / "assets" / "szl-flow.css").read_text(encoding="utf-8")
        toggle_bodies = re.findall(
            r"(?m)^[.]szl-flow-toggle[ ]*[{](?P<body>[^}]*)[}]",
            css,
            re.S,
        )
        body = next((candidate for candidate in toggle_bodies if "display: none" in candidate), None)
        self.assertIsNotNone(body)
        self.assertIn("min-width: 48px", body)
        self.assertIn("min-height: 48px", body)
        self.assertIn("border-radius: 6px", body)

        applied_bodies = re.findall(
            r"(?m)^body\[data-szl-flow\][ ]+[.]szl-flow-toggle[ ]*[{](?P<body>[^}]*)[}]",
            css,
            re.S,
        )
        applied = next(
            (candidate for candidate in applied_bodies if "min-height: 48px" in candidate),
            None,
        )
        self.assertIsNotNone(applied)
        self.assertIn("min-width: 48px", applied)
        self.assertIn("min-height: 48px", applied)
        self.assertIn("border-radius: 6px", applied)
        # A centered 44px square must remain inside all four 6px rounded corners.
        inset = (48 - 44) / 2
        self.assertLessEqual(2 * (6 - inset) ** 2, 6 ** 2)

        landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        self.assertIn(
            ".cta-row .btn{width:100%;min-height:52px;border-radius:6px;"
            "white-space:normal;text-align:center}",
            landing,
        )


if __name__ == "__main__":
    unittest.main()
