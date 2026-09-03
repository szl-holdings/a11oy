#!/usr/bin/env python3
"""Offline contracts for A11oy Holo-Constellation v2."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "console" / "assets" / "szl-holo-v2.css"
JS_PATH = ROOT / "console" / "assets" / "szl-holo-v2.js"
APEX_PATH = ROOT / "console" / "assets" / "apex-v2.css"
REGISTRY_PATH = ROOT / "docs" / "holographic-experience-v2" / "theme-registry.json"
STATE_PATH = ROOT / "docs" / "holographic-experience-v2" / "rollout-state.json"
BINDER_PATH = ROOT / "scripts" / "rollout_holographic_experience_v2.py"
STYLE_MARKER = 'data-szl-holo-asset="style-v2"'
SCRIPT_MARKER = 'data-szl-holo-asset="script-v2"'
SOURCE_MANAGED = {
    "pages/integrations.html",
    "spaces/sda/index.html",
}


class HolographicExperienceV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.javascript = JS_PATH.read_text(encoding="utf-8")
        cls.apex = APEX_PATH.read_text(encoding="utf-8")
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        cls.binder = BINDER_PATH.read_text(encoding="utf-8")

    def test_registry_is_originality_bound(self) -> None:
        self.assertEqual(self.registry["schema"], "szl.holographic-experience/v2")
        boundaries = " ".join(self.registry["originality_boundary"]).lower()
        self.assertIn("no copied source code", boundaries)
        self.assertIn("szl-original", boundaries)
        self.assertIn("decorative motion", boundaries)
        self.assertIn("measured evidence", boundaries)

    def test_product_and_proof_origins_are_deliberately_distinct(self) -> None:
        product = self.registry["origins"]["product"]
        proof = self.registry["origins"]["proof"]
        self.assertNotEqual(product["instrument"], proof["instrument"])
        self.assertNotEqual(product["material"], proof["material"])
        self.assertNotEqual(product["motif"], proof["motif"])
        self.assertEqual(product["host"], "a-11-oy.com")
        self.assertEqual(proof["host"], "a11oy.net")

    def test_verticals_are_not_one_recolored_template(self) -> None:
        surfaces = self.registry["surfaces"]
        required = {
            "a11oy",
            "lyte",
            "vessels",
            "terra",
            "aegis",
            "prism-counsel",
            "carlota-jo",
            "nexus",
            "factory",
            "ouroboros",
            "khipu",
            "killinchu",
            "proof",
        }
        self.assertTrue(required <= set(surfaces))
        motifs = [surfaces[name]["motif"] for name in required]
        self.assertEqual(len(motifs), len(set(motifs)))
        palettes = [tuple(surfaces[name]["palette"]) for name in required]
        self.assertEqual(len(palettes), len(set(palettes)))
        self.assertEqual(len({surfaces[name]["archetype"] for name in required}), len(required))

    def test_accessibility_and_responsive_contract(self) -> None:
        contract = self.registry["shared_contract"]
        self.assertEqual(contract["minimum_touch_target_px"], 44)
        self.assertEqual(contract["reduced_motion"], "required")
        self.assertEqual(contract["forced_colors"], "required")
        self.assertEqual(contract["horizontal_overflow"], "forbidden")
        for token in (
            "prefers-reduced-motion",
            "prefers-contrast",
            "forced-colors",
            "focus-visible",
            "safe-area-inset",
            "max-width: 760px",
            "@media print",
        ):
            self.assertIn(token, self.css)
        for token in ("Escape", "aria-expanded", "Skip to main content", "pointerdown"):
            self.assertIn(token, self.javascript)

    def test_frontdoor_touch_geometry_survives_shared_cascade(self) -> None:
        inner = re.search(
            r'html\[data-szl-holo="v2"\]\s+body\[data-szl-flow\]\s+'
            r'\.menu-toggle\{([^}]*)\}',
            self.apex,
        )
        self.assertIsNotNone(inner)
        inner_contract = inner.group(1)
        for token in (
            "width:48px",
            "height:48px",
            "min-width:48px",
            "min-height:48px",
            "border-radius:6px",
        ):
            self.assertIn(token, inner_contract)

        outer = re.search(
            r'html\[data-szl-holo="v2"\]\s+\.szl-holo-rail\s+'
            r'\.szl-holo-link,\s*html\[data-szl-holo="v2"\]\s+'
            r'\.szl-holo-rail\s+\.szl-holo-menu\{([^}]*)\}',
            self.apex,
        )
        self.assertIsNotNone(outer)
        outer_contract = outer.group(1)
        for token in (
            "min-width:54px",
            "min-height:48px",
            "border-radius:10px",
        ):
            self.assertIn(token, outer_contract)

        def contains_centered_square(width: int, height: int, radius: int) -> bool:
            inset_x = (width - 44) / 2
            inset_y = (height - 44) / 2
            corner_x = max(0.0, radius - inset_x)
            corner_y = max(0.0, radius - inset_y)
            return corner_x**2 + corner_y**2 <= radius**2

        self.assertTrue(contains_centered_square(48, 48, 6))
        self.assertTrue(contains_centered_square(54, 48, 10))

    def test_runtime_is_dependency_free_and_non_tracking(self) -> None:
        implementation = self.css + "\n" + self.javascript
        for prohibited in (
            "fetch(",
            "XMLHttpRequest",
            "sendBeacon",
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "google-analytics",
            "googletagmanager",
            "cdn.jsdelivr.net",
            "unpkg.com",
            "fonts.googleapis.com",
        ):
            self.assertNotIn(prohibited, implementation)
        self.assertNotRegex(implementation, r"https?://(?:cdn|unpkg|jsdelivr)")

    def test_unknown_space_identity_is_stable(self) -> None:
        self.assertIn("0x811c9dc5", self.javascript)
        self.assertIn("Math.imul", self.javascript)
        self.assertIn('source: "deterministic"', self.javascript)
        self.assertIn("huggingFaceSlug", self.javascript)
        self.assertGreaterEqual(self.javascript.count("#"), 60)

    def test_motion_is_progressively_bounded(self) -> None:
        self.assertIn("requestAnimationFrame", self.javascript)
        self.assertIn("navigator.connection", self.javascript)
        self.assertIn("SAVE_DATA", self.javascript)
        self.assertIn("document.hidden", self.javascript)
        self.assertIn("REDUCE_MOTION", self.javascript)
        self.assertLessEqual(self.css.count("animation:"), 10)
        self.assertNotIn("setInterval", self.javascript)

    def test_decorative_motion_cannot_be_mistaken_for_telemetry(self) -> None:
        self.assertIn("measuredTelemetry: false", self.javascript)
        self.assertIs(self.state["decorative_motion_is_measured_telemetry"], False)
        self.assertIn("Decorative motion", " ".join(self.registry["originality_boundary"]))

    def test_stylesheet_is_structurally_balanced(self) -> None:
        without_comments = re.sub(r"/\*.*?\*/", "", self.css, flags=re.DOTALL)
        self.assertEqual(without_comments.count("{"), without_comments.count("}"))
        self.assertIn("@supports not", self.css)
        self.assertIn("color-mix", self.css)
        self.assertIn("backdrop-filter", self.css)

    def test_asset_budgets_are_reasonable_before_compression(self) -> None:
        # Raw bounds prevent accidental megabyte-scale assets. The declared gzip
        # budgets are enforced in CI with gzip -9.
        self.assertLess(CSS_PATH.stat().st_size, 80_000)
        self.assertLess(JS_PATH.stat().st_size, 60_000)

    def test_binder_is_local_idempotent_and_scope_limited(self) -> None:
        self.assertIn("def is_bound", self.binder)
        self.assertIn("def bind", self.binder)
        self.assertIn("def source_managed", self.binder)
        self.assertIn("SOURCE_MANAGED", self.binder)
        self.assertIn("data-szl-holo-disabled", self.binder)
        self.assertIn("a11oy_landing.html", self.binder)
        for relative in SOURCE_MANAGED:
            self.assertIn(relative, self.binder)
        for prohibited in ("requests.", "urllib", "subprocess", "os.environ", "force_push"):
            self.assertNotIn(prohibited, self.binder)

    def test_rollout_state_enforces_exact_bindings_when_active(self) -> None:
        self.assertIn(self.state["state"], {"ASSETS_READY", "ROLLED_OUT"})
        if self.state["state"] != "ROLLED_OUT":
            return
        bindings = self.state.get("bindings", [])
        self.assertIn("a11oy_landing.html", bindings)
        self.assertEqual(self.state["bound_documents"], len(bindings))
        self.assertEqual(self.state["examined_documents"], len(bindings))
        self.assertEqual(set(self.state.get("source_managed_documents", [])), SOURCE_MANAGED)
        self.assertTrue(SOURCE_MANAGED.isdisjoint(bindings))
        for relative in SOURCE_MANAGED:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn(STYLE_MARKER, text, relative)
            self.assertNotIn(SCRIPT_MARKER, text, relative)
        for relative in bindings:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(text.count(STYLE_MARKER), 1, relative)
            self.assertEqual(text.count(SCRIPT_MARKER), 1, relative)


if __name__ == "__main__":
    unittest.main(verbosity=2)
