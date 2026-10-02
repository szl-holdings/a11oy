"""Public receipt navigation and renderer-free estate source contracts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
HOLOGRAPHIC = ROOT / "static" / "3d" / "holographic.html"


class ReceiptAndFallbackContract(unittest.TestCase):
    def test_hero_receipt_action_uses_verifier_and_keeps_registry_distinct(self):
        html = LANDING.read_text(encoding="utf-8")
        hero_actions = html.split('<div class="cta-row">', 1)[1].split("</div>", 1)[0]
        match = re.search(r'<a\b([^>]+)>Verify a receipt</a>', hero_actions)
        self.assertIsNotNone(match)
        attributes = dict(re.findall(r'([\w-]+)="([^"]*)"', match.group(1)))
        self.assertEqual(attributes.get("href"), "/verify")
        self.assertNotIn("target", attributes)
        self.assertNotIn("rel", attributes)
        self.assertIn('href="https://a11oy.net"', html.split('<div class="origin-banner"', 1)[1].split("</div>", 1)[0])
        self.assertNotIn("offline, in your own browser", html.split('<p class="lede">', 1)[1].split("</p>", 1)[0])

    def test_renderer_failure_has_accessible_real_destinations(self):
        html = HOLOGRAPHIC.read_text(encoding="utf-8")
        panel = html.split('<section id="fallback"', 1)[1].split("</section>", 1)[0]
        self.assertIn('aria-labelledby="fallback-title"', panel)
        self.assertIn('tabindex="-1"', panel)
        self.assertIn('role="status"', panel)
        self.assertIn('id="fallback-surface"', panel)
        self.assertLess(panel.index('class="fallback-links"'), panel.index('id="fallback-surface"'))
        self.assertEqual(
            re.findall(r'<a href="([^"]+)"', panel),
            [
                "/api/a11oy/v1/frontier-index/catalog",
                "/api/a11oy/v1/holographic/info",
                "/api/a11oy/v1/readiness/tab-matrix?view=summary",
                "/api/build-info",
                "/verify",
            ],
        )
        self.assertNotIn("All underlying data is still available", panel)
        self.assertIn('document.getElementById("fallback-surface").textContent = def.title', html)
        self.assertIn('body[data-renderer-unavailable="true"]', html)
        self.assertIn('fallbackEl.focus({ preventScroll: true })', html)

    def test_registry_listing_never_claims_backend_reachability(self):
        html = HOLOGRAPHIC.read_text(encoding="utf-8")
        card = html.split('id="card-estate"', 1)[1].split('id="card-verify"', 1)[0]
        loader = html.split("async function loadEstate()", 1)[1].split("let introReturnFocus", 1)[0]
        self.assertNotIn("each wired to a live backend", card + loader)
        self.assertNotIn("Every value each surface shows", html)
        self.assertNotIn("every value carries its honesty label", html)
        self.assertIn('<a href="/api/a11oy/v1/frontier-index/catalog">frontier catalog</a>', html)
        self.assertIn("backend health UNVERIFIED", card + loader)
        self.assertIn("Array.isArray(j?.surfaces)", loader)
        self.assertIn("j.surfaces.every", loader)
        self.assertIn('"REGISTRY · UNVERIFIED"', loader)
        self.assertIn('"MANIFEST · UNVERIFIED"', loader)
        self.assertNotIn('setLabel("estate-lbl", "reachable"', loader)


if __name__ == "__main__":
    unittest.main()
