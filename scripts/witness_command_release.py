#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings
"""Opt-in browser witness: fixed public origin, allowlisted GETs, no credentials."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_command_observations import ASSETS, ORIGIN, READ_PATHS

ALLOWED_PATHS = READ_PATHS | frozenset(ASSETS) | {"/command-v2"}
EDGE_SPECULATION_URL = ORIGIN + "/cdn-cgi/speculation"
EDGE_SPECULATION_HEADER = '"/cdn-cgi/speculation"'


def read_allowed(method, url):
    parsed = urlsplit(url)
    return (
        method == "GET" and parsed.scheme == "https"
        and parsed.netloc == "a-11-oy.com" and not parsed.fragment
        and parsed.path + ("?" + parsed.query if parsed.query else "") in ALLOWED_PATHS
    )


def require_revision(data, expected):
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("INVALID_EXPECTED_REVISION")
    if (
        not isinstance(data, dict) or data.get("status") != "OBSERVED"
        or not isinstance(data.get("build"), dict)
        or data["build"].get("revision") != expected
        or data.get("receipt_minted") is not False
    ):
        raise ValueError("LIVE_SOURCE_REVISION_NOT_MATCHED")


def expected_blocked_edge_config(blocked, page_headers):
    # Cloudflare Speed Brain advertises this browser GET via the response header.
    return (
        len(blocked) == 1
        and blocked[0].get("edge_speculation_config") is True
        and page_headers.get("speculation-rules") == EDGE_SPECULATION_HEADER
    )


def relay_readonly(route, blocked, requests):
    request = route.request
    requests.append((request.method, request.url))
    parsed = urlsplit(request.url)
    reason = None
    if not read_allowed(request.method, request.url):
        reason = "OUTSIDE_GET_ALLOWLIST"
    else:
        response = route.fetch(max_redirects=0, timeout=15000)
        if 300 <= response.status < 400:
            reason = "REDIRECT_REJECTED"
        else:
            body = response.body()
            if len(body) > 2_000_000:
                reason = "RESPONSE_TOO_LARGE"
            else:
                route.fulfill(response=response, body=body)
                return
    blocked.append({
        "method": request.method, "host": parsed.hostname, "path": parsed.path,
        "reason": reason,
        "edge_speculation_config": (
            reason == "OUTSIDE_GET_ALLOWLIST" and request.method == "GET"
            and request.url == EDGE_SPECULATION_URL
        ),
    })
    route.abort()


class InlineScripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.scripts = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script" and "src" not in dict(attrs):
            self.current = []

    def handle_data(self, text):
        if self.current is not None:
            self.current.append(text)

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--output", type=Path, default=Path("command-live-evidence"))
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_source):
        parser.error("expected-source must be a full lowercase Git revision")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "szl.command-browser-witness/v1", "origin": ORIGIN,
        "source_revision": args.expected_source, "started_at": datetime.now(timezone.utc).isoformat(),
        "state": "FAIL", "production_ready": False,
        "scope": "Command v2 read interactions only; no model, signer, readiness or action admission",
        "request_policy": "Fixed HTTPS origin; exact GET allowlist; no stored browser credentials; service workers blocked",
        "blocked_requests": [], "viewports": [], "asset_sha256": {},
    }
    try:
        from playwright.sync_api import expect, sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            report["browser"] = browser.version
            context = browser.new_context(viewport={"width": 1280, "height": 800}, service_workers="block")
            requests = []
            errors = []

            def guard(route):
                relay_readonly(route, report["blocked_requests"], requests)

            context.route("**/*", guard)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(type(error).__name__))

            def response_bytes(path):
                assert read_allowed("GET", ORIGIN + path)
                response = context.request.get(ORIGIN + path, timeout=20000, max_redirects=0)
                assert response.status == 200, "PUBLIC_GET_FAILED"
                body = response.body()
                assert len(body) <= 2_000_000, "PUBLIC_BODY_TOO_LARGE"
                return response, body

            def source_readback():
                response, body = response_bytes("/api/build-info")
                assert "application/json" in response.headers.get("content-type", "").lower()
                data = json.loads(body)
                require_revision(data, args.expected_source)
                return data["build"]["revision"]

            report["source_before"] = source_readback()
            for route_path, (name, _) in ASSETS.items():
                _, body = response_bytes(route_path)
                assert body == (ROOT / "console/assets/szl" / name).read_bytes(), "LIVE_ASSET_DIFFERS_FROM_CHECKOUT"
                report["asset_sha256"][route_path] = hashlib.sha256(body).hexdigest()
            response = page.goto(ORIGIN + "/command-v2", wait_until="networkidle", timeout=30000)
            assert response and response.status == 200
            expected_scripts = InlineScripts((ROOT / "pages/command-v2.html").read_text(encoding="utf-8")).scripts
            live_scripts = InlineScripts(response.text()).scripts
            assert expected_scripts and all(script in live_scripts for script in expected_scripts), "LIVE_SCRIPT_DIFFERS_FROM_CHECKOUT"
            expect(page.locator('.source-state[data-state="OBSERVED"]')).to_have_count(11, timeout=15000)
            report["eleven_observations_visible"] = True

            for width, height in ((1280, 800), (390, 844), (320, 740)):
                page.set_viewport_size({"width": width, "height": height})
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "PAGE_OVERFLOW"
                assert page.locator(".brand img").evaluate("image => image.complete && image.naturalWidth > 0"), "BRAND_ASSET_NOT_RENDERED"
                page.screenshot(path=str(args.output / f"live-command-{width}.png"))
                request_count = len(requests)
                page.get_by_role("button", name="Inspect Receipts source", exact=True).click()
                dialog = page.locator("#source-inspector")
                expect(dialog).to_be_visible()
                assert not dialog.evaluate("node => node.scrollWidth > node.clientWidth"), "INSPECTOR_OVERFLOW"
                assert isinstance(json.loads(dialog.locator("pre").text_content()), dict)
                assert dialog.locator("script, img, iframe").count() == 0
                assert len(requests) == request_count, "INSPECTION_STARTED_A_REQUEST"
                page.screenshot(path=str(args.output / f"live-inspector-{width}.png"))
                page.keyboard.press("Escape")
                expect(page.get_by_role("button", name="Inspect Receipts source", exact=True)).to_be_focused()
                report["viewports"].append({"width": width, "height": height, "layout_and_inspection": "PASS"})

            page.get_by_role("button", name="Open command palette", exact=True).click()
            page.get_by_role("searchbox", name="Search rooms").fill("telemetry")
            page.get_by_role("option", name=re.compile("Telemetry")).click()
            expect(page.locator("h1")).to_have_text("Mesh observations")
            report["palette_navigation"] = "PASS"
            report["source_after"] = source_readback()
            assert not errors, "BROWSER_SCRIPT_ERROR"
            assert all(method == "GET" for method, _ in requests), "WRITE_REQUEST_ATTEMPTED"
            blocked = report["blocked_requests"]
            assert not blocked or expected_blocked_edge_config(blocked, response.headers), "UNEXPECTED_NETWORK_REQUEST"
            report["edge_speculation_config_blocked"] = bool(blocked)
            report["state"] = "PASS"
            context.close()
            browser.close()
    except Exception as exc:
        # Keep browser exception messages and response bodies out of public logs.
        report["error_class"] = type(exc).__name__
        report["error_code"] = str(exc) if re.fullmatch(r"[A-Z_]{3,80}", str(exc)) else "BROWSER_WITNESS_FAILED"
    finally:
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        (args.output / "witness.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    return 0 if report["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
