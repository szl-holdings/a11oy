#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline Chromium checks of the actual page and local assets, not runtime proof."""
import json
import os
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_command_observations import ASSETS, READ_PATHS

ORIGIN = "https://command-fixture.invalid"
EVIDENCE = Path(os.environ.get("COMMAND_BROWSER_EVIDENCE", "command-evidence"))


class CommandBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "browser.txt").write_text(cls.browser.version, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 800})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.requests = []
        self.unavailable = False
        self.note = '<img src=x onerror="alert(1)">'
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.context.route("**/*", self.serve)
        self.page.goto(ORIGIN + "/command-v2", wait_until="networkidle")
        self.page.wait_for_function("document.querySelectorAll('.source-state[data-state=OBSERVED]').length === 11")

    def serve(self, route):
        request = route.request
        self.requests.append((request.method, request.url))
        parsed = urlsplit(request.url)
        path = parsed.path + ("?" + parsed.query if parsed.query else "")
        if not request.url.startswith(ORIGIN + "/") or request.method != "GET":
            route.abort()
        elif path == "/command-v2":
            route.fulfill(status=200, body=(ROOT / "pages/command-v2.html").read_bytes(), content_type="text/html")
        elif path in ASSETS:
            name, content_type = ASSETS[path]
            route.fulfill(status=200, body=(ROOT / "console/assets/szl" / name).read_bytes(), content_type=content_type)
        elif path in READ_PATHS:
            if self.unavailable:
                route.fulfill(status=503, json={"error": "synthetic_unavailable"})
                return
            body = {"preview": "SYNTHETIC SOFTWARE QA", "status": "DEGRADED", "note": self.note}
            if path.endswith("/ledger"):
                body.update(count=0, signature_state="UNSIGNED", chain_verified=False)
            if path == "/healthz":
                body.update(signer={"status": "ABSENT"})
            route.fulfill(status=200, json=body)
        else:
            route.abort()

    def test_layout_and_inspector_at_desktop_and_mobile_sizes(self):
        for width, height in ((1280, 800), (390, 844), (320, 740)):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": height})
                self.assertFalse(self.page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                self.assertTrue(self.page.locator(".brand img").evaluate("image => image.complete && image.naturalWidth > 0"))
                self.assertEqual(self.page.locator('link[rel="stylesheet"]').count(), 2)
                self.page.screenshot(path=str(EVIDENCE / f"command-{width}.png"))
                before = len(self.requests)
                self.page.get_by_role("button", name="Inspect Receipts source", exact=True).click()
                dialog = self.page.locator("#source-inspector")
                self.assertTrue(dialog.is_visible())
                self.assertFalse(dialog.evaluate("element => element.scrollWidth > element.clientWidth"))
                payload = json.loads(dialog.locator("pre").text_content())
                self.assertEqual(payload["count"], 0)
                self.assertEqual(payload["note"], self.note)
                self.assertEqual(dialog.locator("img, script").count(), 0)
                self.assertEqual(len(self.requests), before)
                self.page.screenshot(path=str(EVIDENCE / f"inspector-{width}.png"))
                self.page.keyboard.press("Escape")
                self.assertFalse(dialog.is_visible())
                self.assertEqual(self.page.evaluate("document.activeElement.id"), "inspect-card-receipts")
        self.assertEqual(self.errors, [])

    def test_mobile_palette_and_evidence_navigation(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.get_by_role("button", name="Evidence", exact=True).click()
        self.assertEqual(self.page.locator("h1").inner_text(), "Receipt evidence")
        self.assertIn("REPORTED UNVERIFIED", self.page.locator("#content").inner_text())
        self.page.get_by_role("button", name="Open command palette", exact=True).click()
        self.page.get_by_role("searchbox", name="Search rooms").fill("telemetry")
        self.page.get_by_role("option", name=re.compile("Telemetry")).click()
        self.assertEqual(self.page.locator("h1").inner_text(), "Mesh observations")
        self.assertFalse(self.page.locator("#palette").is_visible())
        self.assertEqual(self.errors, [])

    def test_refresh_failure_clears_headlines_and_never_writes(self):
        self.assertEqual(self.page.locator("#receipts").inner_text(), "Receipts · 0")
        self.unavailable = True
        self.page.get_by_role("button", name="Refresh observations", exact=True).click()
        self.page.wait_for_function("document.querySelectorAll('.source-state[data-state=UNAVAILABLE]').length === 11")
        self.assertEqual(self.page.locator("#receipts").inner_text(), "Receipts · UNAVAILABLE")
        self.assertTrue(all(method == "GET" for method, _ in self.requests))
        self.assertFalse(any("/kernel/probe" in url for _, url in self.requests))
        self.page.screenshot(path=str(EVIDENCE / "unavailable.png"))
        self.assertEqual(self.errors, [])

    def test_real_client_expiry_preserves_inspector_and_focus(self):
        self.page.get_by_role("button", name="Inspect Receipts source", exact=True).click()
        self.page.wait_for_function("document.querySelector('#source-inspector dl').textContent.includes('STALE')", timeout=70000)
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "close-source-inspector")
        self.assertEqual(self.page.locator("#receipts").inner_text(), "Receipts · UNAVAILABLE")
        self.assertEqual(json.loads(self.page.locator("#source-inspector pre").text_content())["count"], 0)
        self.page.screenshot(path=str(EVIDENCE / "expired-inspector.png"))
        self.page.keyboard.press("Escape")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "inspect-card-receipts")
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
