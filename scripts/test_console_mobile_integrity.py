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
VIEWS = ("command", "lambda", "chain", "replay", "govern", "estate", "cve", "kev", "evidence", "receipts",
         "fleet", "readiness", "bounties", "genome", "honest", "launcher", "publications", "energySci", "energyReceipts")
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


def run(output, premium_only=False):
    widths = (375, 390, 768, 1280, 1920) if premium_only else WIDTHS
    views = ("fleet", "readiness", "estate") if premium_only else VIEWS
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), StaticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    state = {"energy": {}, "ledger": "rows", "lambda": .9191, "status_mode": "rows", "estate_mode": "rows"}
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
            elif url.path == "/api/a11oy/v1/observability/summary" and state["status_mode"] != "error":
                payload = {"dag_depth": 2, "mesh_reach": {"core": {"status": "ok", "name": "Fixture core"}, "missing": {"status": "unavailable", "name": "Fixture missing"}}}
                if state["status_mode"] == "rows":
                    payload["capabilities"] = [{"id": "fixture", "name": "TEST FIXTURE service", "status": "ok", "latency_ms": 0}, {"id": "missing", "name": "TEST FIXTURE missing latency", "status": "unavailable"}]
                elif state["status_mode"] == "empty":
                    payload["capabilities"] = []
            elif url.path == "/api/a11oy/v1/readiness" and state["status_mode"] != "error":
                payload = {"source": "TEST FIXTURE", "summary": {}, "sections": []}
                if state["status_mode"] == "rows":
                    payload["sections"] = [{"id": "fixture", "title": "TEST FIXTURE repository", "kind": "kv", "fields": [{"k": "Repository identity", "v": "fixture-only/" + "long-repository-name-" * 8}]}]
                    if premium_only:
                        payload["sections"].append({"id": "http", "title": "TEST FIXTURE transport", "kind": "endpoints", "endpoints": [
                            {"title": "Reported observation", "url": "https://example.invalid/reported", "liveness": {"reachable": True, "http_status": 200}},
                            {"title": "Malformed observation", "url": "https://example.invalid/malformed", "liveness": {"reachable": "false", "http_status": 200}},
                            {"title": "Missing observation", "url": "https://example.invalid/missing"},
                        ]})
                elif state["status_mode"] == "malformed":
                    payload = {}
            elif url.path == "/api/a11oy/v1/bounties" and state["status_mode"] != "error":
                payload = {"source": "TEST FIXTURE", "bounties": []} if state["status_mode"] != "malformed" else {}
            elif url.path == "/api/a11oy/v1/policy/decisions/feed":
                payload = {"verdicts": [], "total_buffered": 14}
            elif url.path == "/api/a11oy/v1/models/series-a":
                if state["estate_mode"] != "error":
                    payload = {"cards": [], "roadmap_kernels": []}
                    if premium_only and state["estate_mode"] == "rows":
                        payload["cards"] = [{"id": "fixture", "lane": "model", "title": "TEST FIXTURE model", "hub_id": "fixture/" + "long-name-" * 12, "hub_href": "https://example.invalid/model", "evidence_class": "REPORTED", "listing": {"label": "REPORTED"}, "artifacts": {"label": "UNAVAILABLE", "note": "Fixture only; no model is downloaded or evaluated."}}]
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
            page.goto(origin + "/console?view=" + ("fleet" if premium_only else "command"), wait_until="load")
            page.wait_for_function("window.VIEWS && window.VIEWS.chain && window.VIEWS.estate")
            page.wait_for_timeout(1500)
            inventory = page.evaluate("Object.entries(window.VIEWS).map(([key,v])=>({key,title:v.title,badge:v.badge,render_source:String(v.render)}))")
            (output / "registered-tabs.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
            check("registered views inventoried", len(inventory) >= 100, len(inventory))
            if premium_only:
                from test_console_focused_theme import MEASURE

                for theme in ("dark", "light"):
                    page.emulate_media(color_scheme=theme)
                    for width in widths:
                        page.set_viewport_size({"width": width, "height": 900})
                        for view in views:
                            page.evaluate("key=>go(key)", view)
                            page.wait_for_timeout(350)
                            size = page.evaluate("({document:document.documentElement.scrollWidth,content:document.querySelector('.content').scrollWidth,client:document.querySelector('.content').clientWidth})")
                            check(f"{view} {theme} contained at {width}px", size["document"] <= width + 1 and size["content"] <= size["client"] + 1, size)
                            check(f"{view} {theme} theme at {width}px", page.locator("html").get_attribute("data-surface") == theme)
                            controls = page.locator("#vbody a:visible,#vbody button:visible").evaluate_all("els=>els.map(e=>({label:e.textContent.trim(),width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))")
                            check(f"{view} {theme} touch targets at {width}px", all(c["width"] >= 44 and c["height"] >= 44 for c in controls), controls)
                            measurements = page.evaluate(MEASURE)
                            contrast_failures = [t for t in measurements["texts"] if t["ratio"] < 4.5]
                            check(f"{view} {theme} visible text contrast at {width}px", not contrast_failures, contrast_failures)
                            check(f"{view} {theme} flat surfaces at {width}px", not measurements["gradients"], measurements["gradients"])
                            if view == "estate":
                                check(f"estate {theme} flat title at {width}px", page.locator(".szl-holo-title").evaluate("e=>getComputedStyle(e).backgroundImage==='none' && getComputedStyle(e).webkitTextFillColor!=='transparent'"))
                            scroll_roots = page.evaluate("() => ['html','body','.app','.content'].map(selector=>{const e=document.querySelector(selector); return {selector,height:e.scrollHeight,client:e.clientHeight,overflow:getComputedStyle(e).overflowY};})")
                            height = max(r["height"] for r in scroll_roots)
                            step = 500
                            for offset in range(int(step), height, int(step)):
                                page.evaluate("y=>['html','body','.app','.content'].forEach(s=>document.querySelector(s).scrollTop=y)", offset)
                                measurements = page.evaluate(MEASURE)
                                contrast_failures = [t for t in measurements["texts"] if t["ratio"] < 4.5]
                                check(f"{view} {theme} lower text contrast at {width}px/{offset}", not contrast_failures, contrast_failures)
                            moved = page.evaluate("() => ['html','body','.app','.content'].some(s=>document.querySelector(s).scrollTop>0)")
                            check(f"{view} {theme} lower content reachable at {width}px", moved or height <= 900, scroll_roots)
                            if width == 390:
                                page.screenshot(path=str(output / f"premium-{view}-{theme}-{width}-lower.png"))
                            page.evaluate("()=>['html','body','.app','.content'].forEach(s=>document.querySelector(s).scrollTop=0)")
                            if width in (390, 1280):
                                page.screenshot(path=str(output / f"premium-{view}-{theme}-{width}.png"))
                page.set_viewport_size({"width": 390, "height": 844})
                page.evaluate("go('readiness')")
                page.wait_for_timeout(350)
                check("readiness reports transport separately", "REPORTED HTTP 200" in page.locator("#rd-sec-http").inner_text())
                check("missing and malformed liveness stay unavailable", page.locator("#rd-sec-http .rd-badge[data-tone=dim]").count() == 2)
                check("readiness missing counts stay explicit", "counts unavailable" in page.locator("#rd-sec-http").inner_text())
                check("readiness action names identify sections", page.locator("button[aria-label='Re-check source: TEST FIXTURE transport']").count() == 1)
                page.locator("#rd-reload").focus()
                check("keyboard focus visible", page.locator("#rd-reload").evaluate("e=>e.matches(':focus-visible') && getComputedStyle(e).outlineStyle!=='none'"))
                for mode in ("empty", "malformed", "error"):
                    state["status_mode"] = mode
                    for view in ("fleet", "readiness"):
                        page.evaluate("key=>go(key)", view)
                        page.wait_for_timeout(350)
                        check(f"premium {view} {mode} evidence state", ("EMPTY" if mode == "empty" else "UNAVAILABLE") in page.locator("#vbody").inner_text())
                for mode in ("empty", "error"):
                    state["estate_mode"] = mode
                    page.evaluate("go('estate')")
                    page.wait_for_timeout(350)
                    check(f"premium estate {mode} evidence state", ("NO ENTRIES REPORTED" if mode == "empty" else "UNAVAILABLE") in page.locator("#szl-estate-full").inner_text())
                page.locator(".szl-theme-toggle").click()
                check("theme control toggles and persists", page.evaluate("localStorage.getItem('szl.console.theme')===document.documentElement.dataset.surface"))
                check("reduced motion respected", page.locator(".content").evaluate("e=>getComputedStyle(e).animationName==='none'"))
                check("no mutation request from premium views", not any(r["method"] != "GET" for r in requests))
            else:
                for width in WIDTHS:
                    page.set_viewport_size({"width": width, "height": 900})
                    for view in VIEWS:
                        if not page.evaluate("key=>Boolean(window.VIEWS[key])", view):
                            continue
                        page.evaluate("key=>window.go(key)", view)
                        page.wait_for_timeout(500)
                        size = page.evaluate("({viewport:innerWidth,document:document.documentElement.scrollWidth,content:document.querySelector('.content').scrollWidth,client:document.querySelector('.content').clientWidth})")
                        check(f"{view} contained at {width}px", size["document"] <= width + 1 and size["content"] <= size["client"] + 1, size)
                        if width in (390, 1440) and view in ("command", "chain", "lambda", "govern", "replay", "estate", "fleet", "readiness", "bounties", "energySci", "energyReceipts", "publications"):
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
                page.evaluate("go('fleet')")
                page.wait_for_timeout(500)
                check("fleet missing latency stays unavailable", "latency unavailable" in page.locator("#fl-grid").inner_text())
                check("fleet true zero latency preserved", "0 ms" in page.locator("#fl-grid").inner_text())
                check("fleet status accessible without color", "unavailable" in page.locator("#fl-grid").inner_text())
                check("fleet history keyboard scrollable", page.locator("#fl-grid").get_attribute("tabindex") == "0")
                for mode in ("empty", "malformed", "error"):
                    state["status_mode"] = mode
                    for view in ("fleet", "readiness", "bounties"):
                        page.evaluate("key=>go(key)", view)
                        page.wait_for_timeout(500)
                        content = page.locator("#vbody").inner_text()
                        check(f"{view} {mode} evidence state", ("EMPTY" if mode == "empty" else "UNAVAILABLE") in content)
                        if view in ("readiness", "bounties"):
                            check(f"{view} {mode} has no invented observation time", "just now" not in content)
                        if view == "bounties":
                            check(f"bounties {mode} does not settle conjectures", "every conjecture on the board has been settled" not in content)
                state["status_mode"] = "rows"
                page.evaluate("go('readiness')")
                page.wait_for_timeout(500)
                check("readiness missing counts explicit", "endpoints unavailable" in page.locator("#vbody").inner_text())
                check("readiness missing timestamp explicit", "timestamp unavailable" in page.locator("#vbody").inner_text())
                page.locator(".rd-live-btn").click()
                page.wait_for_timeout(500)
                check("failed readiness section refresh keeps evidence and reports error", "re-read failed: HTTP 503" in page.locator("#vbody").inner_text() and "TEST FIXTURE repository" in page.locator("#vbody").inner_text())
                for view in ("readiness", "bounties"):
                    kept = page.evaluate("""async key=>{
                        const originalFetch=window.fetch;
                        window.fetch=(...args)=>String(args[0]).endsWith('/v1/'+key)
                            ? new Promise(resolve=>setTimeout(()=>resolve({ok:true,json:async()=>({summary:{},sections:[],bounties:[]})}),100))
                            : originalFetch(...args);
                        try{
                            go(key);
                            const pending=window[key+'_render'](document.querySelector('#vbody'),{silent:true});
                            go('replay');
                            await pending;
                            return document.documentElement.dataset.view==='replay' && document.querySelector('#vbody').innerText.includes('SAMPLE');
                        }finally{window.fetch=originalFetch;}
                    }""", view)
                    check(f"late {view} response preserves next view", kept)
                page.evaluate("go('replay')")
                page.wait_for_timeout(500)
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
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    report = {"commit": commit, "working_tree_dirty": dirty, "source": "LOCAL UI WITH LABELLED TEST FIXTURES; no production readiness claim", "registered_view_keys": len(inventory), "widths": widths, "selected_benign_views": views, "themes": ["dark", "light"] if premium_only else ["default"], "checks": checks, "failures": failures, "browser_errors": sorted(set(errors)), "intercepted_requests": requests}
    (output / "browser-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"checks": len(checks), "passed": len(checks) - len(failures), "failures": failures, "browser_errors": sorted(set(errors)), "report": str(output / "browser-report.json")}, ensure_ascii=True))
    return bool(failures or errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--premium-only", action="store_true", help="Only fleet/readiness/estate, five requested widths, light and dark")
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.premium_only))
