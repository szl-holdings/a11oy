#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Source contracts complement the browser-tested homepage shell behavior."""
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

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
        cls.css = (ROOT / "console/assets/a11oy-homepage.css").read_text(encoding="utf-8")

    def test_one_local_visual_owner_uses_the_canonical_surface_roles(self):
        links = [attrs for tag, attrs in self.elements if tag == "link"]
        owner = [a for a in links if a.get("id") == "szl-homepage-shell"]
        self.assertEqual(owner, [{"rel": "stylesheet", "href": "/assets/a11oy-homepage.css", "id": "szl-homepage-shell"}])
        hrefs = [a.get("href") for a in links]
        self.assertLess(hrefs.index("/assets/szl/szl-design-system.css"), hrefs.index("/assets/a11oy-homepage.css"))
        self.assertNotIn("/assets/apex-v2.css", hrefs)
        self.assertNotIn("<style", self.html)
        self.assertNotIn("@font-face", self.css)
        self.assertIn('data-surface="light"', self.html)
        for role in ("--action-bg", "--action-hover-bg", "--action-press-bg", "--holo-edge", "--text-sub", "--font-display"):
            self.assertIn("var(" + role + ")", self.css)
        self.assertIn('class="specimen-wrap" data-surface="dark"', self.html)
        self.assertIn('class="deep-record" data-surface="dark"', self.html)

    def test_one_explicit_shell_owner_and_accessible_navigation(self):
        roots = [attrs for tag, attrs in self.elements if tag == "html"]
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0]["data-szl-shell-owner"], "homepage")
        toggles = [a for t, a in self.elements if t == "button" and a.get("id") == "menu-toggle"]
        self.assertEqual(len(toggles), 1)
        self.assertEqual(toggles[0]["aria-controls"], "site-nav")
        self.assertEqual(toggles[0]["aria-expanded"], "false")
        self.assertIn(("nav", {"class": "nav-links", "id": "site-nav", "aria-label": "Primary navigation"}), self.elements)

    def test_standalone_governed_frontdoor_serves_its_exact_stylesheet(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import szl_governed_api
        app = FastAPI()
        szl_governed_api.register(app, public_pem="")
        client = TestClient(app)
        landing = client.get("/")
        self.assertEqual(landing.status_code, 200)
        self.assertEqual(landing.content, (ROOT / "a11oy_landing.html").read_bytes())
        css = client.get("/assets/a11oy-homepage.css")
        self.assertEqual(css.status_code, 200)
        self.assertTrue(css.headers["content-type"].startswith("text/css"))
        self.assertEqual(css.headers["x-content-type-options"], "nosniff")
        self.assertEqual(css.content, (ROOT / "console/assets/a11oy-homepage.css").read_bytes())
        self.assertEqual(client.post("/assets/a11oy-homepage.css").status_code, 405)
        self.assertEqual(client.get("/assets/requirements-runtime.txt").status_code, 404)

    def test_packaged_frontdoor_serves_exact_stylesheet_route(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import szl_governed_api

        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            assets = package / "static" / "assets"
            assets.mkdir(parents=True)
            expected = b"body { color: #123456; }\n"
            (assets / "a11oy-homepage.css").write_bytes(expected)
            app = FastAPI()
            with patch.object(szl_governed_api, "__file__", str(package / "szl_governed_api.py")):
                szl_governed_api.register(app, public_pem="")
            client = TestClient(app)
            css = client.get("/assets/a11oy-homepage.css")
            self.assertEqual(css.status_code, 200)
            self.assertTrue(css.headers["content-type"].startswith("text/css"))
            self.assertEqual(css.headers["x-content-type-options"], "nosniff")
            self.assertEqual(css.content, expected)
            self.assertEqual(client.post("/assets/a11oy-homepage.css").status_code, 405)
            self.assertEqual(client.get("/assets/requirements-runtime.txt").status_code, 404)

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
        css_without_comments = re.sub(r'/\*.*?\*/', '', self.css, flags=re.S)
        for selector in re.findall(r'([^{}]+)\{', css_without_comments):
            if not selector.strip().startswith("@"):
                self.assertIn('html[data-szl-shell-owner="homepage"]', selector)
        for contract in ("font-size:clamp(2.7rem,5.15vw,4.75rem)", "@media(max-width:760px)",
                         "@media(max-width:1100px)", "prefers-reduced-motion", "forced-colors",
                         "--ink:var(--text)", "--sub:var(--text-sub)",
                         "overflow:visible !important"):
            self.assertIn(contract, self.css)

    def test_disclosure_closes_on_escape_outside_focus_and_resize(self):
        menu = self.html.split('var btn=document.getElementById("menu-toggle");', 1)[1].split("</script>", 1)[0]
        for contract in ('e.key==="Escape"', "btn.focus()", '"focusout"',
                         "header.contains(e.relatedTarget)", "header.contains(e.target)",
                         'window.matchMedia("(min-width:1101px)")', '"aria-expanded"'):
            self.assertIn(contract, menu)

    def test_evidence_states_and_offline_verification_remain_explicit(self):
        hero = self.html.split('<section class="hero"', 1)[1].split("</section>", 1)[0]
        evidence = self.html.split('id="evidence"', 1)[1].split("</section>", 1)[0]
        self.assertIn('Make AI decisions <em>inspectable.</em>', hero)
        self.assertIn('MODELED SPECIMEN / illustrative', hero)
        self.assertIn('SAMPLE · committed offline fixture', hero)
        self.assertIn('BLOCKED pending approval', hero)
        for label in ("SIGNED", "UNAVAILABLE", "Conjecture 1"):
            self.assertIn(label, evidence)
        self.assertIn("SIGNED is written only when the attestation", evidence)
        title = hero.split('<h1 class="title"', 1)[1].split("</h1>", 1)[0]
        self.assertNotIn("signed", title.lower())
        for endpoint in ("/api/a11oy/healthz", "/api/a11oy/v1/frontier/surfaces", "/api/a11oy/v1/attest/manifest"):
            self.assertIn(endpoint, evidence)

    def test_evidence_handle_navigation_targets_the_query_surface(self):
        command = (ROOT / "a11oy_command_center.py").read_text(encoding="utf-8")
        hickok = (ROOT / "a11oy_v4_hickok.py").read_text(encoding="utf-8")
        anatomy = (ROOT / "web/living-anatomy.html").read_text(encoding="utf-8")
        self.assertIn('("/command/brain", "second-brain.html")', command)
        self.assertIn('PAGES_DIR / "brain-dual.html"', hickok)
        self.assertIn('href="/command/brain">Explore evidence handles', self.html)
        self.assertIn('href="/command/brain"><div class="lt">/command/brain — Second Brain evidence handles', anatomy)
        self.assertIn('href="/brain">Open Hickok /brain', anatomy)
        self.assertNotIn('href="/brain">Explore evidence handles', self.html)


if __name__ == "__main__":
    unittest.main()
