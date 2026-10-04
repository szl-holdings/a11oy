# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Source-level shell contracts; not a WCAG or runtime certification."""
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static/shared/szl_command_bar.css").read_text(encoding="utf-8")
TOKENS = dict(re.findall(r"(--szl-shell-[a-z-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", CSS))


def luminance(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    bright, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (bright + .05) / (dark + .05)


def block(selector):
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", CSS)
    if not match:
        raise AssertionError("missing selector: " + selector)
    return re.sub(r"\s+", "", match.group(1))


class HolographicShellContract(unittest.TestCase):
    def test_contrast_reference_values(self):
        self.assertAlmostEqual(contrast("#000000", "#ffffff"), 21)
        self.assertAlmostEqual(contrast("#ffffff", "#ffffff"), 1)

    def test_text_and_state_colors_on_opaque_surfaces(self):
        for foreground in ("ink", "copy", "muted", "unknown", "accent", "prism", "warning", "error", "measured"):
            for background in ("ground", "panel", "raised"):
                with self.subTest(foreground=foreground, background=background):
                    self.assertGreaterEqual(contrast(TOKENS["--szl-shell-" + foreground], TOKENS["--szl-shell-" + background]), 4.5)

    def test_control_boundaries_have_nontext_contrast(self):
        for background in ("ground", "panel", "raised"):
            self.assertGreaterEqual(contrast(TOKENS["--szl-shell-line"], TOKENS["--szl-shell-" + background]), 3)

    def test_filled_status_labels_have_text_contrast(self):
        for background in ("measured", "error"):
            self.assertGreaterEqual(contrast(TOKENS["--szl-shell-ground"], TOKENS["--szl-shell-" + background]), 4.5)

    def test_default_dot_is_neutral_not_live(self):
        dot = block(".szl-dot")
        self.assertIn("background:var(--szl-shell-unknown)", dot)
        self.assertIn("box-shadow:none", dot)
        self.assertIn("background:var(--szl-shell-measured)", block(".szl-chip--live .szl-dot"))

    def test_off_and_advisory_override_live_class(self):
        neutral = ".szl-chip--off .szl-dot,.szl-chip--lambda .szl-dot"
        self.assertIn("background:var(--szl-shell-unknown)", block(neutral))
        self.assertGreater(CSS.index(neutral), CSS.index(".szl-chip--live .szl-dot"))
        self.assertIn("color:var(--szl-shell-unknown)!important", block(".szl-chip--lambda,.szl-lambda"))

    def test_software_listing_not_styled_as_measured(self):
        self.assertNotEqual(TOKENS["--szl-shell-accent"], TOKENS["--szl-shell-measured"])
        self.assertIn("color:var(--szl-shell-accent)", block(".szl-holo-chip--software"))
        self.assertIn("background:var(--szl-shell-measured)", block(".szl-holo-chip--measured"))

    def test_origin_targets_and_card_actions(self):
        origin = block(".szl-origins a,.szl-origins button.szl-origin")
        for contract in ("min-width:48px", "min-height:48px", "border-radius:6px"):
            self.assertIn(contract, origin)
        self.assertLessEqual(math.hypot(4, 4), 6)
        self.assertIn("min-height:44px", block(".szl-holo-act a"))

    def test_mobile_motion_and_high_contrast_paths_present(self):
        for condition in ("max-width:820px", "prefers-reduced-motion:reduce", "prefers-contrast:more", "forced-colors:active"):
            self.assertIn("@media(" + condition + ")", CSS)
        self.assertIn("minmax(min(100%,240px),1fr)", CSS)
        self.assertIn("flex-wrap:wrap!important", CSS)
        self.assertIn("animation:none!important", CSS)

    def test_existing_public_presentation_boundaries_remain(self):
        for selector in ('html:not([data-operator="1"]) [data-view="labs"]',
                         'html:not([data-operator="1"]) a[href*="killinchu"]',
                         'html:not([data-operator="1"]) [data-view="energyGrid"]'):
            self.assertIn(selector, CSS)
        self.assertIn("These are not server authorization", CSS)

    def test_no_remote_assets_or_palette_override_stack(self):
        self.assertNotIn("@import", CSS)
        self.assertNotRegex(CSS, r"url\s*\(")
        self.assertEqual(len(re.findall(r":root\s*\{", CSS)), 1)
        names = re.findall(r"(--szl-shell-[a-z-]+)\s*:", CSS)
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
