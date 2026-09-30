#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Browser regression for benign console UI. All API calls use labelled fixtures.

No production request is allowed. This checks presentation, not backend readiness.
Run: python scripts/test_console_mobile_integrity.py --output <evidence-directory>
"""
import argparse
import json
import mimetypes
import os
import subprocess
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ("command", "lambda", "chain", "replay", "govern", "estate", "cve", "kev", "evidence", "receipts")
WIDTHS = (320, 360, 390, 768, 1024, 1440)


class StaticHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/console", "/console/"):
            file = ROOT / "pages/console.html"
        elif path.startswith("/vendor/"):
            file = ROOT / "static-vendor" / path.removeprefix("/vendor/")
        elif path.startswith("/assets/"):
            file = ROOT / "console/assets" / path.removeprefix("/assets/")
        elif path.startswith("/static/shared/"):
            file = ROOT / path.lstrip("/")
        else:
            file = ROOT / "__missing__"
        if not file.resolve().is_relative_to(ROOT) or not file.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file)[0] or "application/octet-stream")
        self.end_headers()
        self.wfile.write(file.read_bytes())


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), StaticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    state = {"energy": {}, "ledger": "rows", "lambda": .9191}
    requests = []
    failures = []
    checks = []
    errors = []
    rows = [
        {"seq": 2, "hash": "b" * 64, "prev_hash": "a" * 64, "vertical": "software", "action": "Review fixture findings", "simulated": True},
        {"seq": 1, "hash": "a" * 64, "vertical": "software", "action": "Read fixture manifest", "simulated": True},
    ]

    def check(name, condition, detail=None):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})
        if not condition:
            failures.append(name)

    def intercept(route):
        req = route.request
        url = urlsplit(req.url)
        local = req.url.startswith(origin + "/")
        if local and (url.path.startswith(("/vendor/", "/assets/", "/static/shared/")) or url.path in ("/console", "/console/")):
            route.continue_()
            return
        requests.append({"path": url.path, "query": url.query, "method": req.method, "source": "TEST FIXTURE"})
        payload = None
        if req.method == "GET" and local:
            if url.path == "/healthz":
                payload = {"status": "ok"}
            elif url.path == "/api/a11oy/v1/honest":
                payload = {"locked_formula_count": 8, "locked_formula_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]}
            elif url.path == "/api/a11oy/v1/lambda":
                payload = {"lambda": state["lambda"], "lambda_floor": .9, "pass": True, "axes": []}
            elif url.path == "/api/a11oy/v1/lambda/org":
                payload = {"lambda_org": state["lambda"], "pass": True, "inputs": {"class": "SUPPLIED"}}
            elif url.path == "/api/a11oy/v1/energy/operator/status":
                payload = state["energy"]
            elif url.path == "/api/a11oy/v1/wow/ledger":
                query = parse_qs(url.query)
                if query.get("advance") == ["0"] and state["ledger"] != "error":
                    payload = {"chain_depth": 2 if state["ledger"] == "rows" else 0, "receipts": rows if state["ledger"] == "rows" else [], "window_verified": True, "final_hash": "b" * 64, "verticals_in_window": {"software": 2}}
            elif url.path == "/api/a11oy/v1/observability/summary":
                payload = {"dag_depth": 2, "mesh_reach": {"core": {"status": "ok", "name": "Fixture core"}, "missing": {"status": "unavailable", "name": "Fixture missing"}}}
            elif url.path == "/api/a11oy/v1/policy/decisions/feed":
                payload = {"verdicts": [], "total_buffered": 14}
            elif url.path == "/api/a11oy/v1/models/series-a":
                payload = {"cards": [], "roadmap_kernels": []}
            elif url.path == "/api/a11oy/v1/formulas/selftest":
                payload = {"unifying": {"governed_run_sound": {"P4_replay_determinism": True}}}
            elif url.path in ("/api/a11oy/v1/gates", "/api/a11oy/v1/policy/gates"):
                payload = {"gates": []}
        route.fulfill(status=200 if payload is not None else 503, content_type="application/json", body=json.dumps(payload if payload is not None else {"available": False, "state": "UNAVAILABLE", "source": "TEST: no network permitted"}))

    try:
        with sync_playwright() as p:
            executable = os.environ.get("CONSOLE_QA_BROWSER")
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            if not executable and edge.is_file():
                executable = str(edge)
            browser = p.chromium.launch(executable_path=executable, headless=True, args=["--disable-gpu"])
            context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce", service_workers="block")
            context.route("**/*", intercept)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(origin + "/console?view=command", wait_until="load")
            page.wait_for_function("window.VIEWS && window.VIEWS.chain && window.VIEWS.estate")
            page.wait_for_timeout(1500)
            inventory = page.evaluate("Object.entries(window.VIEWS).map(([key,v])=>({key,title:v.title,badge:v.badge,render_source:String(v.render)}))")
            (output / "registered-tabs.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
            check("registered views inventoried", len(inventory) >= 100, len(inventory))
            for width in WIDTHS:
                page.set_viewport_size({"width": width, "height": 900})
                for view in VIEWS:
                    if not page.evaluate("key=>Boolean(window.VIEWS[key])", view):
                        continue
                    page.evaluate("key=>window.go(key)", view)
                    page.wait_for_timeout(500)
                    size = page.evaluate("({viewport:innerWidth,document:document.documentElement.scrollWidth,content:document.querySelector('.content').scrollWidth,client:document.querySelector('.content').clientWidth})")
                    check(f"{view} contained at {width}px", size["document"] <= width + 1 and size["content"] <= size["client"] + 1, size)
                    if width in (390, 1440) and view in ("command", "chain", "lambda", "govern", "replay", "estate"):
                        page.screenshot(path=str(output / f"{view}-{width}.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("go('command')")
            page.wait_for_timeout(500)
            check("energy missing stays unavailable", page.locator("#hero-joules-tag").inner_text() == "UNAVAILABLE")
            check("buffered counter has correct label", page.locator("#cc-dec").locator("..").locator(".k").text_content() == "Decisions buffered")
            for name, data, expected in (
                ("pending meter", {"stub_mode": False, "measured_token_joules": None, "measured_tokens": 0}, "UNAVAILABLE"),
                ("malformed energy", {"stub_mode": False, "measured_token_joules": "3.2", "measured_tokens": 10}, "UNAVAILABLE"),
                ("numeric measured reading", {"stub_mode": False, "measured_token_joules": 3.2, "measured_tokens": 10}, "MEASURED"),
                ("sample exporter", {"stub_mode": True, "sample_token_joules": 2.5}, "SAMPLE"),
            ):
                state["energy"] = data
                page.evaluate("go('command')")
                page.wait_for_timeout(500)
                check(name, page.locator("#hero-joules-tag").inner_text() == expected)
            page.evaluate("go('lambda')")
            page.wait_for_timeout(500)
            check("lambda is advisory", page.locator("#la-pass").inner_text() == "At/above floor")
            check("lambda title neutral", "✓" not in page.title() and "⚠" not in page.title())
            page.evaluate("go('chain')")
            page.wait_for_timeout(500)
            check("accessible receipt list uses actual fixture rows", page.locator(".receipt-chain-list li").count() == 2)
            check("chain labels separate signature from hash", "hash-linked entries" in page.locator("#vbody").inner_text())
            for mode, expected in (("empty", "EMPTY"), ("error", "UNAVAILABLE")):
                state["ledger"] = mode
                page.evaluate("go('chain')")
                page.wait_for_timeout(500)
                check("ledger " + mode + " state", page.locator("#rc-ver").inner_text() == expected)
            state["ledger"] = "rows"
            page.evaluate("go('replay')")
            page.wait_for_timeout(500)
            check("replay is labelled sample", "SAMPLE" in page.locator("#vbody").inner_text() and "Live data, no mock" not in page.locator("#vbody").inner_text())
            check("shared header keeps ownership", page.locator("[data-szl-command-bar]").get_attribute("data-szl-navigation") != "converged")
            check("mobile palette control visible", page.locator(".szl-cmdk").is_visible())
            check("mobile More control visible", page.locator(".szl-more").is_visible())
            check("all evidence chips remain available", page.locator(".szl-hbar-live .szl-chip:visible").count() == 5)
            check("reduced-motion skip link hidden until focused", page.locator(".szl-holo-skip").bounding_box()["y"] < 0)
            page.locator(".szl-more").focus()
            page.keyboard.press("ArrowDown")
            check("More opens by keyboard", page.locator(".szl-more").get_attribute("aria-expanded") == "true" and page.evaluate("document.activeElement.matches('.szl-overflow-menu a')"))
            bounds = page.locator(".szl-overflow-menu").bounding_box()
            check("More menu stays in viewport", bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 390)
            page.keyboard.press("Escape")
            check("More restores trigger", page.evaluate("document.activeElement===document.querySelector('.szl-more')"))
            page.locator(".menu-btn").click()
            check("drawer opens and contains keyboard focus", page.evaluate("document.querySelector('.side').contains(document.activeElement)"))
            check("drawer starts below measured header", page.evaluate("Math.abs(document.querySelector('.side').getBoundingClientRect().top-document.querySelector('[data-szl-command-bar]').getBoundingClientRect().bottom)<2"))
            page.keyboard.press("Escape")
            check("drawer closes and restores trigger", page.locator(".menu-btn").get_attribute("aria-expanded") == "false" and page.evaluate("document.activeElement===document.querySelector('.menu-btn')"), page.evaluate("({focus:document.activeElement.outerHTML,view:document.documentElement.dataset.view})"))
            page.keyboard.press("Control+k")
            check("palette modal visible", page.locator("#szl-command-palette").get_attribute("aria-hidden") == "false")
            check("palette makes content inert", page.locator(".app").get_attribute("inert") is not None)
            page.locator(".szl-pal input").dispatch_event("keydown", {"key": "Enter", "isComposing": True})
            check("IME Enter keeps palette open", page.locator("#szl-command-palette").get_attribute("aria-hidden") == "false")
            page.keyboard.press("ArrowDown")
            check("palette arrow selects native link", page.evaluate("document.activeElement.matches('.szl-pal-item[href]')"))
            page.keyboard.press("Escape")
            check("palette restores focus", page.evaluate("document.activeElement===document.querySelector('.menu-btn')"))
            page.keyboard.press("Control+k")
            page.locator(".szl-pal input").fill("no_such_command_fixture")
            check("palette empty result", page.locator(".szl-pal-empty").inner_text() == "No matching commands.")
            page.keyboard.press("Shift+Tab")
            check("palette traps reverse Tab with no results", page.evaluate("document.activeElement.matches('.szl-pal-close')"))
            page.keyboard.press("Escape")
            check("palette restores content inert state", page.locator(".app").get_attribute("inert") is None)
            led = [r for r in requests if r["path"].endswith("/wow/ledger")]
            check("all ledger probes passive", bool(led) and all(parse_qs(r["query"]).get("advance") == ["0"] for r in led))
            check("no mutation request from selected views", not any(r["method"] != "GET" for r in requests))
            browser.close()
    finally:
        server.shutdown()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report = {"commit": commit, "source": "LOCAL UI WITH LABELLED TEST FIXTURES; no production readiness claim", "registered_view_keys": len(inventory), "widths": WIDTHS, "selected_benign_views": VIEWS, "checks": checks, "failures": failures, "browser_errors": sorted(set(errors)), "intercepted_requests": requests}
    (output / "browser-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"checks": len(checks), "passed": len(checks) - len(failures), "failures": failures, "browser_errors": sorted(set(errors)), "report": str(output / "browser-report.json")}, ensure_ascii=True))
    return bool(failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output))
