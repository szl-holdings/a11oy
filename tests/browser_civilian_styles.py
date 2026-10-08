#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local UI regression with software fixtures and no external provider requests."""
import functools
import json
import os
import re
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def fixture_overview():
    source = {"name": "SOFTWARE_TEST_FIXTURE", "source_url": "https://example.org/SOFTWARE_TEST_FIXTURE",
              "fetched_at": None, "source_date": None, "sha256": None, "status": "UNAVAILABLE",
              "error": "Offline software fixture, not an operational observation."}
    row = {"cve": "CVE-2024-0001", "kev_status": "UNKNOWN", "kev": None, "epss": None,
           "exposure": "UNKNOWN", "priority": "INSUFFICIENT_DATA", "explanation": "SOFTWARE TEST ONLY"}
    return {
        "server_time": "2026-10-03T00:00:00Z",
        "estate": {"scope": "SOFTWARE_TEST_FIXTURE", "repositories": [],
                   "summary": {"repo_count": 0, "files_indexed": 0, "archived": 0, "observed_at": "2026-10-03T00:00:00Z"}},
        "feeds": {"schema_version": "1.0", "generated_at": "2026-10-03T00:00:00Z",
                  "kev": {"source": {**source, "name": "CISA SOFTWARE_TEST_FIXTURE"}, "catalog_version": None, "entries": []},
                  "epss": {"source": {**source, "name": "EPSS SOFTWARE_TEST_FIXTURE"}, "entries": [], "requested": []}},
        "analysis": {"analyzed_at": "2026-10-03T00:00:00Z", "policy_version": "kev-first-epss-second/1.0",
                     "input": [row["cve"]], "rows": [row], "sources": [source],
                     "asset_inventory_connected": False, "model_executed": False},
    }


class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class CivilianStyles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The optional override permits a read-only comparison against the saved base build.
        static = Path(os.environ.get("CIVILIAN_BROWSER_STATIC", str(ROOT / "civilian_observatory/static"))).resolve()
        if not (static / "index.html").is_file():
            raise ValueError("An exact static UI build is required")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(StaticHandler, directory=str(static)))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.addClassCleanup(cls.worker.join, timeout=3)
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        executable = os.environ.get("CIVILIAN_BROWSER_EXECUTABLE") or None
        cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=executable)
        cls.addClassCleanup(cls.browser.close)
        print("LOCAL_BROWSER_VERSION:", cls.browser.version)

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="light")
        self.unexpected = []
        self.errors = []
        self.api_requests = []
        self.context.route("**/*", self.route)
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.origin + "/")
        expect(self.page.get_by_test_id("text-page-title")).to_have_text("Clarity before action.")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.unexpected, [])
        self.assertEqual(self.errors, [])
        self.assertTrue(all(method == "GET" for method, _path in self.api_requests))

    def route(self, route):
        request = route.request
        url = urlsplit(request.url)
        if not request.url.startswith(self.origin + "/"):
            self.unexpected.append(request.url)
            return route.abort()
        if url.path.startswith("/api/"):
            self.api_requests.append((request.method, url.path))
            if request.method != "GET":
                self.unexpected.append(request.method + " " + url.path)
                return route.abort()
            if url.path == "/api/a11oy/v1/civilian/overview":
                return route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture_overview()))
            self.unexpected.append(url.path)
            return route.abort()
        return route.continue_()

    def test_desktop_layout_and_light_dark_tokens(self):
        shell = self.page.locator(".main-shell")
        self.page.evaluate("document.fonts.ready")
        evidence = os.environ.get("CIVILIAN_BROWSER_EVIDENCE")
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(Path(evidence) / "desktop-light.png"), full_page=True)
        self.assertAlmostEqual(shell.bounding_box()["x"], 238, delta=1)
        self.assertEqual(self.page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor"), "rgb(249, 248, 246)")
        self.assertEqual(self.page.get_by_test_id("button-open-review").evaluate("e => getComputedStyle(e).borderRadius"), "6px")
        self.page.get_by_test_id("button-theme").click()
        expect(self.page.locator("html")).to_have_class("dark")
        self.assertEqual(self.page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor"), "rgb(20, 20, 20)")
        self.page.get_by_test_id("button-theme").click()
        expect(self.page.locator("html")).not_to_have_class("dark")

    def test_form_focus_and_forced_color_outline(self):
        self.page.get_by_test_id("nav-vulnerability-review").click()
        control = self.page.get_by_test_id("input-cves")
        control.focus()
        self.assertEqual(control.evaluate("e => getComputedStyle(e).borderTopWidth"), "1px")
        self.assertNotEqual(control.evaluate("e => getComputedStyle(e).boxShadow"), "none")
        self.page.emulate_media(forced_colors="active")
        self.assertEqual(control.evaluate("e => getComputedStyle(e).outlineWidth"), "2px")
        self.assertEqual(control.evaluate("e => getComputedStyle(e).outlineStyle"), "solid")
        self.assertEqual(control.evaluate("e => getComputedStyle(e).outlineOffset"), "2px")
        self.page.get_by_test_id("button-detail-CVE-2024-0001").click()
        dialog = self.page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        self.page.wait_for_function("() => Math.abs(document.querySelector('[role=dialog]').getBoundingClientRect().width - 650) < 1")
        self.assertAlmostEqual(dialog.bounding_box()["width"], 650, delta=1)
        self.page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()

    def test_mobile_sheet_navigation_and_touch_size(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.get_by_test_id("button-sidebar-toggle").click()
        sheet = self.page.get_by_role("dialog")
        expect(sheet).to_be_visible()
        self.assertAlmostEqual(sheet.bounding_box()["width"], 288, delta=1)
        navigation = self.page.get_by_test_id("nav-vulnerability-review")
        self.assertGreaterEqual(navigation.bounding_box()["height"], 44)
        navigation.click()
        expect(sheet).not_to_be_visible()
        expect(self.page.get_by_test_id("text-page-title")).to_have_text("Vulnerability evidence, in context.")
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 390)

    def test_reduced_motion_and_variable_transform_origin(self):
        self.page.emulate_media(reduced_motion="reduce")
        self.assertEqual(self.page.get_by_test_id("button-theme").evaluate("e => getComputedStyle(e).transitionDuration"), "1e-05s")
        source_root = Path(os.environ.get("CIVILIAN_BROWSER_SOURCE_ROOT", str(ROOT))).resolve()
        tooltip = (source_root / "web/civilian-observatory/client/src/components/ui/tooltip.tsx").read_text(encoding="utf-8")
        origin_class = re.search(r"\borigin-[^\s\"]+", tooltip)
        self.assertIsNotNone(origin_class, "the real tooltip component must declare its transform-origin utility")
        result = self.page.evaluate("""(originClass) => {
          const element = document.createElement('div');
          element.className = originClass;
          element.style.setProperty('--radix-tooltip-content-transform-origin', '7px 11px');
          document.body.append(element);
          const origin = getComputedStyle(element).transformOrigin;
          element.remove();
          return origin;
        }""", origin_class[0])
        self.assertEqual(result, "7px 11px")


if __name__ == "__main__":
    unittest.main(verbosity=2)
