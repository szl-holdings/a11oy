#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Source contracts complement the browser-tested homepage shell behavior."""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class HomepageShellCoherence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        cls.elements = Elements(cls.html).elements
        cls.css = cls.html.split('<style id="szl-homepage-shell">', 1)[1].split('</style>', 1)[0]

    def test_one_explicit_shell_owner_and_accessible_navigation(self):
        roots = [attrs for tag, attrs in self.elements if tag == "html"]
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["data-szl-shell-owner"], "homepage")
        toggles = [a for t, a in self.elements if t == "button" and a.get("id") == "menu-toggle"]
        self.assertEqual(len(toggles), 1)
        self.assertEqual(toggles[0]["aria-controls"], "site-nav")
        self.assertEqual(toggles[0]["aria-expanded"], "false")
        self.assertIn(("nav", {"class": "nav-links", "id": "site-nav", "aria-label": "Primary navigation"}), self.elements)

    def test_shared_enhancers_remain_bound_but_cannot_add_homepage_navigation(self):
        for script in ("szl-flow.js", "szl-holo-v2.js"):
            self.assertEqual(self.html.count('src="/assets/' + script + '"'), 1)
        flow = (ROOT / "console/assets/szl-flow.js").read_text(encoding="utf-8")
        holo = (ROOT / "console/assets/szl-holo-v2.js").read_text(encoding="utf-8")
        self.assertIn('dataset.szlShellOwner === "homepage"', flow)
        self.assertRegex(flow, r'if \(!ownsShell\)\s*\{\s*document.body.appendChild\(progress\);\s*document.body.appendChild\(rail\);\s*document.body.appendChild\(live\);\s*\}')
        rail_guard = holo.split("function buildRail(theme)", 1)[1].split("const rail", 1)[0]
        self.assertIn('dataset.szlShellOwner === "homepage"', rail_guard)
        self.assertIn(") return;", rail_guard)
        self.assertIn("installMotion();", holo)
        self.assertIn("markSpectralCards();", flow)

    def test_responsive_rules_are_page_scoped(self):
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        for selector in re.findall(r'([^{}]+)\{', self.css):
            if not selector.strip().startswith("@"):
                self.assertIn('html[data-szl-shell-owner="homepage"]', selector)
        for contract in ("font-size:clamp(34px,4.2vw,58px)", "@media(max-width:760px)",
                         "@media(max-width:1100px)", "prefers-reduced-motion", "forced-colors",
                         "--gold:#c9b787", "--proof:#5fb3a3", "padding-bottom:0"):
            self.assertIn(contract, self.css)

    def test_disclosure_closes_on_escape_outside_focus_and_resize(self):
        menu = self.html.split('var btn=document.getElementById("menu-toggle");', 1)[1].split("</script>", 1)[0]
        for contract in ('e.key==="Escape"', "btn.focus()", '"focusout"',
                         "header.contains(e.relatedTarget)", "header.contains(e.target)",
                         'window.matchMedia("(min-width:1101px)")', '"aria-expanded"'):
            self.assertIn(contract, menu)

    def test_evidence_states_and_offline_verification_remain_explicit(self):
        hero = self.html.split('<section class="hero">', 1)[1].split("</section>", 1)[0]
        for label in ("SIGNED", "HASH-LINKED", "UNSIGNED", "DISABLED", "UNAVAILABLE", "BLOCKED", "Conjecture 1"):
            self.assertIn(label, hero)
        self.assertIn("persistent signer evidence is active and verification passes", hero)
        title = hero.split('<h1 class="title">', 1)[1].split("</h1>", 1)[0]
        self.assertNotIn("signed", title.lower())
        for endpoint in ("/api/a11oy/healthz", "/api/a11oy/v1/frontier/surfaces", "/api/a11oy/v1/attest/manifest"):
            self.assertIn(endpoint, hero)


if __name__ == "__main__":
    unittest.main()
