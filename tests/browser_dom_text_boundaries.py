"""Offline Chromium regression of the two real HTML sources; no live requests.

Fixtures do not claim backend readiness, source deployment, profit or policy
admission. Existing server/CSP/integration checks remain separate requirements.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import hashlib
import sys
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://szl-fixture.invalid"
PAYLOAD = '<img src="missing" onerror="window.__fixtureInjected=1"><b>literal fixture</b>'


class DomBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        path = os.environ.get("SZL_TEST_CHROMIUM_EXECUTABLE")
        cls.browser = cls.playwright.chromium.launch(
            headless=True, **({"executable_path": path} if path else {})
        )
        cls.browser_version = cls.browser.version

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 375, "height": 812})
        self.errors = []
        self.requests = []
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.addCleanup(self.context.close)

    def open_source(self, path, *, storage=None, fragment=""):
        if storage is not None:
            key, value = storage
            self.context.add_init_script(
                f"localStorage.setItem({json.dumps(key)}, {json.dumps(json.dumps(value))});"
            )
        source = (ROOT / path).read_text(encoding="utf-8")
        def serve(route):
            url = route.request.url
            self.requests.append(url)
            if url.split("#")[0] == ORIGIN + "/":
                route.fulfill(status=200, body=source, content_type="text/html")
            elif url == ORIGIN + "/api/a11oy/v1/five-space/status":
                route.fulfill(status=503, json={"state": "UNAVAILABLE"})
            elif url.startswith(ORIGIN + "/assets/"):
                # Isolate the actual page's own source; shared assets have their
                # existing independent qualification, not claimed by this suite.
                route.fulfill(status=200, body="", content_type="text/css" if url.endswith(".css") else "application/javascript")
            else:
                route.abort()
        self.context.route("**/*", serve)
        self.page.goto(ORIGIN + "/" + fragment, wait_until="networkidle")

    def five_state(self):
        return {"selected": ["a11oy"], "loops": [], "ideas": [], "proposals": [],
                "memory": [], "receipts": [], "doctrineUnlocked": False}

    def assert_literal(self, selector):
        self.assertEqual(self.page.locator(selector + " img, " + selector + " svg, " + selector + " script").count(), 0)
        self.assertIn("<img", self.page.locator(selector).text_content())
        self.assertIsNone(self.page.evaluate("window.__fixtureInjected"))
        self.assertEqual(self.errors, [])

    def test_memory_form_input_renders_as_literal_text(self):
        self.open_source("web/five-space.html", fragment="#memory")
        self.page.locator("#memKey").fill(PAYLOAD)
        self.page.locator("#memBody").fill(PAYLOAD)
        self.page.locator('#memForm button[type="submit"]').click()
        self.page.locator("#memList article").wait_for()
        self.assert_literal("#memList")
        self.assert_literal("#ledgerBody")

    def test_persisted_memory_is_literal_after_reload(self):
        state = self.five_state()
        state["memory"] = [{"key": PAYLOAD, "body": PAYLOAD, "klass": PAYLOAD,
                            "writtenAt": "2026-01-01T00:00:00Z", "freshnessHours": 24}]
        self.open_source("web/five-space.html", storage=("szl-five-space-operator-v1", state), fragment="#memory")
        self.assert_literal("#memList")
        self.page.reload(wait_until="networkidle")
        self.assert_literal("#memList")

    def test_persisted_ideas_are_literal(self):
        state = self.five_state()
        state["ideas"] = [{"theme": PAYLOAD, "project": PAYLOAD, "description": PAYLOAD,
                           "risk": PAYLOAD, "createdAt": PAYLOAD}]
        self.open_source("web/five-space.html", storage=("szl-five-space-operator-v1", state))
        self.assert_literal("#loopList")

    def test_queue_values_do_not_create_markup_or_attribute_ids(self):
        state = self.five_state()
        state["proposals"] = [{"id": PAYLOAD, "status": "BLOCKED",
                               "idea": {"theme": PAYLOAD, "project": PAYLOAD, "description": PAYLOAD}}]
        self.open_source("web/five-space.html", storage=("szl-five-space-operator-v1", state), fragment="#queue")
        self.assert_literal("#queueList")
        self.assertEqual(self.page.locator('#queueList input[type="checkbox"]').get_attribute("id"), "queue-attestation-0")
        self.assertEqual(self.page.locator("#queueList label").get_attribute("for"), "queue-attestation-0")

    def test_queue_admission_still_requires_checkbox(self):
        self.open_source("web/five-space.html")
        self.page.locator("#runLoop").click()
        self.page.locator("#queueList article").first.wait_for()
        dialogs = []
        self.page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
        first = self.page.locator("#queueList article").first
        first.get_by_role("button", name="Admit", exact=True).click()
        self.assertEqual(len(dialogs), 1)
        self.assertIn("BLOCKED", first.text_content())
        first.locator('input[type="checkbox"]').check()
        first.get_by_role("button", name="Admit", exact=True).click()
        self.page.wait_for_function("document.querySelector('#queueList article').textContent.includes('ADMITTED')")
        self.assertEqual(self.errors, [])

    def test_queue_refusal_still_updates_the_local_record(self):
        self.open_source("web/five-space.html")
        self.page.locator("#runLoop").click()
        self.page.locator("#queueList article").first.get_by_role("button", name="Refuse", exact=True).click()
        self.page.wait_for_function("document.querySelector('#queueList article').textContent.includes('REFUSED')")
        self.assertEqual(self.errors, [])

    def test_ledger_fields_stay_literal_without_claiming_valid_chain(self):
        state = self.five_state()
        state["receipts"] = [{"createdAt": PAYLOAD, "kind": PAYLOAD, "summary": PAYLOAD,
                              "chainHash": PAYLOAD, "prevHash": "wrong", "payloadHash": "wrong", "id": "fixture"}]
        self.open_source("web/five-space.html", storage=("szl-five-space-operator-v1", state), fragment="#ledger")
        self.assert_literal("#ledgerBody")
        self.assertEqual(self.page.locator("#chainOk").text_content(), "BROKEN")

    def test_command_receipt_fields_are_literal(self):
        receipts = [{"action": PAYLOAD, "decision": PAYLOAD, "hash": PAYLOAD}]
        self.open_source("pages/command-center.html", storage=("a11oy-origin-lake", receipts), fragment="#console")
        self.assert_literal("#lake")
        self.assertEqual(self.page.locator("#lake .badge").get_attribute("class"), "badge")

    def test_threshold_does_not_reinterpret_dom_text(self):
        self.open_source("pages/command-center.html", fragment="#zk")
        self.page.get_by_role("button", name="SNARKs", exact=True).click()
        self.page.locator("#th").evaluate("(element,value)=>{element.type='text';element.value=value}", PAYLOAD)
        self.page.locator("#rsat").click()
        self.assert_literal("#rstate")

    def test_valid_navigation_and_mobile_menu_remain_available(self):
        self.open_source("pages/command-center.html")
        self.page.locator(".menu").click()
        self.assertEqual(self.page.locator("nav.mob a").count(), self.page.locator("nav.desk a").count())
        self.page.evaluate("location.hash='console'")
        self.page.locator("#submit").wait_for()
        self.page.locator("#submit").click()
        self.page.wait_for_function("document.querySelector('#lake').textContent.includes('1 receipts')")
        self.assertEqual(self.errors, [])

    def test_page_sources_no_longer_contain_dynamic_storage_html_sinks(self):
        five = (ROOT / "web/five-space.html").read_text()
        command = (ROOT / "pages/command-center.html").read_text()
        block = five[five.index("  function renderLoop"):five.index("  function renderAll")]
        self.assertNotIn("innerHTML", block)
        self.assertNotIn("PAGES[id]", command)
        self.assertNotIn('$("#rstate").innerHTML', command)


def unknown_route_case(fragment):
    def case(self):
        self.open_source("pages/command-center.html", fragment="#" + fragment)
        self.assertIn("Control before capability.", self.page.locator("#main").text_content())
        self.assertEqual(self.errors, [])
    return case


for route in ("constructor", "__proto__", "toString", "valueOf", "hasOwnProperty", "unknown"):
    setattr(DomBoundaryTests, "test_unknown_route_" + route, unknown_route_case(route))

if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    evidence = ROOT / "dom-evidence"
    evidence.mkdir(exist_ok=True)
    paths = ("web/five-space.html", "pages/command-center.html", "tests/browser_dom_text_boundaries.py")
    report = {
        "schema": "szl.dom-text-boundary-test/v1",
        "source_revision": os.environ.get("GITHUB_SHA", "LOCAL_UNBOUND"),
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "success": result.wasSuccessful(),
        "browser": getattr(DomBoundaryTests, "browser_version", "UNAVAILABLE"),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths},
        "data": "SYNTHETIC", "network": "INTERCEPTED_FIXTURES_ONLY",
        "shared_assets_qualified": False, "live_deployment_verified": False,
    }
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
