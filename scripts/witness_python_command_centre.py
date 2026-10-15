#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Local Python presentation witness; no operational runtime or inference claim."""

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
SCOPE = "LOCAL_SOURCE_PRESENTATION_ONLY_NO_OPERATIONAL_RUNTIME"
ROUTES = ("/command-centre", "/a11oy/atelier")
HEALTH_PATHS = ("/api/a11oy/v1/atelier/health", "/api/a11oy/v1/atelier/local/health",
                "/api/a11oy/v1/atelier/cpu-lab/health")
API_PATHS = ("/api/build-info", *HEALTH_PATHS, *(
    "/api/a11oy/v1/command-centre/" + name for name in ("manifest", "inventory", "study")))
ASSET_PATHS = tuple("/command-centre/" + name for name in (
    "app.js", "style.css", "szl/szl-design-system.css", "szl/szl-console.css"))
ALLOWED_PATHS = frozenset((*ROUTES, *API_PATHS, *ASSET_PATHS))
NAVIGATION = "#operate-links > a, #verify-links > a, #artifact-links > a"
BUTTONS = ("send", "local-send", "cpu-send")


class WitnessError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise WitnessError(message)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def source_identity(expected):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{40}", expected),
            "expected source must be an exact lowercase Git SHA40")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    require(revision == expected, "expected source does not match checkout HEAD")
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    return {"revision": revision, "worktree": "DIRTY_LOCAL_PRESENTATION" if dirty else "CLEAN",
            "changed_paths": dirty, "clean_source_claimed": not dirty}


def request_allowed(method, url, origin):
    parsed = urlsplit(url)
    return (method == "GET" and f"{parsed.scheme}://{parsed.netloc}" == origin
            and parsed.path in ALLOWED_PATHS and not parsed.query and not parsed.fragment
            and not parsed.username and not parsed.password)


def block_websocket(socket, requests, violations):
    record = {"method": "WEBSOCKET", "url": socket.url, "type": "websocket"}
    requests.append(record)
    violations.append(record)
    socket.close(code=1008, reason="Presentation witness forbids WebSockets")


@contextmanager
def fixture_server(revision):
    """Only this presentation router is installed; no production lifespan runs."""
    sys.path.insert(0, str(ROOT))
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from routers import command_centre as centre

    fixture_health = {"ready": False, "state": "UNAVAILABLE",
                      "blockers": ["LOCAL_PRESENTATION_FIXTURE"], "scope": SCOPE}
    with patch.dict("os.environ", {"SZL_GIT_SHA": revision, "A11OY_COMMAND_CENTRE_PREVIEW": "1"}), \
            patch.object(centre, "http_json", return_value=(None, "LOCAL_PRESENTATION_FIXTURE")):
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        centre.register(app)

        def health():
            return JSONResponse(fixture_health, headers={"Cache-Control": "no-store"})

        def build():
            return JSONResponse({"build": {"revision": revision}, "scope": SCOPE,
                                 "state": "LOCAL_PRESENTATION_FIXTURE"},
                                headers={"Cache-Control": "no-store"})

        for path in HEALTH_PATHS:
            app.add_api_route(path, health, methods=["GET"])
        app.add_api_route("/api/build-info", build, methods=["GET"])
        expected_body = centre.page_bytes()
        input_digests = re.findall(rb'data-view-input-sha256="([0-9a-f]{64})"', expected_body)
        require(len(input_digests) == 1, "renderer input digest missing or duplicated")
        bindings = centre.presentation_sources()
        requests = []
        lock = threading.Lock()
        with TestClient(app) as client:
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_args):
                    pass

                def do_GET(self):
                    requests.append({"method": self.command, "path": self.path})
                    if self.path not in ALLOWED_PATHS:
                        self.send_error(404)
                        return
                    with lock:
                        response = client.get(self.path, follow_redirects=False)
                    self.send_response(response.status_code)
                    for key, value in response.headers.items():
                        if key.lower() not in {"connection", "transfer-encoding"}:
                            self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(response.content)

                def reject(self):
                    requests.append({"method": self.command, "path": self.path})
                    self.send_error(405, "Presentation witness permits GET only")

                do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = reject

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield {"origin": f"http://127.0.0.1:{server.server_port}", "body": expected_body,
                       "headers": centre.PAGE_HEADERS, "bindings": bindings,
                       "renderer_input_sha256": input_digests[0].decode("ascii"),
                       "public_estate_sha256": centre.public_estate()["sha256"],
                       "surfaces": centre.SURFACES, "requests": requests, "centre": centre}
                require(bindings == centre.presentation_sources(), "presentation sources changed during witness")
                require(expected_body == centre.page_bytes(), "rendered source changed during witness")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


def check_presentation(page, surfaces):
    require(page.locator("h1").inner_text() == "Your work. One centre.", "heading missing")
    links = page.locator(NAVIGATION).evaluate_all(
        "nodes => nodes.map(n => ({href:n.getAttribute('href'), title:n.querySelector('strong').textContent, boundary:n.querySelector('span').textContent}))")
    expected = [{"href": href, "title": title, "boundary": boundary}
                for _lane, title, href, boundary in surfaces]
    require(len(links) == 18 and links == expected, "18 source-owned navigation links changed")
    ayllu = page.locator("#ownership-links a[href='https://huggingface.co/spaces/SZLHOLDINGS/ayllu']")
    require(ayllu.count() == 1 and "INVENTORY_ONLY" in ayllu.inner_text()
            and "FOLD" in ayllu.inner_text(), "Ayllu ownership boundary missing")
    require(page.locator("form").count() == 3, "three retained forms missing")
    require(all(page.locator("#" + button).is_disabled() for button in BUTTONS),
            "an execution button became enabled in unavailable fixture")
    geometry = page.evaluate("""() => ({viewport:innerWidth,
        document:document.documentElement.scrollWidth, body:document.body.scrollWidth})""")
    require(max(geometry["document"], geometry["body"]) <= geometry["viewport"], "horizontal overflow")
    return {"navigation_count": len(links), "ayllu_inventory_only": True,
            "disabled_action_buttons": list(BUTTONS), "geometry": geometry}


def observe(browser, fixture, route, width, javascript, output):
    from playwright.sync_api import expect
    errors, requests, violations = [], [], []
    context = browser.new_context(viewport={"width": width, "height": 900},
                                  java_script_enabled=javascript, service_workers="block",
                                  locale="en-US", timezone_id="UTC", color_scheme="dark")

    def guard(intercept):
        request = intercept.request
        record = {"method": request.method, "url": request.url, "type": request.resource_type}
        requests.append(record)
        if not request_allowed(request.method, request.url, fixture["origin"]):
            violations.append(record)
            intercept.abort("blockedbyclient")
        else:
            intercept.continue_()

    context.route("**/*", guard)
    context.route_web_socket("**/*", lambda socket: block_websocket(socket, requests, violations))
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append("page: " + str(error)))
    page.on("console", lambda message: errors.append("console: " + message.text)
            if message.type in {"error", "warning"} else None)
    page.on("requestfailed", lambda request: errors.append("request failed: " + request.url))
    try:
        response = page.goto(fixture["origin"] + route, wait_until="networkidle", timeout=20000)
        require(response is not None and response.status == 200, "page did not return HTTP 200")
        body = response.body()
        require(body == fixture["body"], "browser document differs from Python page_bytes")
        headers = response.all_headers()
        for key, expected in fixture["headers"].items():
            require(headers.get(key.lower()) == expected, "route header mismatch: " + key)
        require(headers.get("content-type") == "text/html; charset=utf-8", "document content type mismatch")
        if javascript:
            expect(page.locator("#refresh")).to_be_enabled()
            expect(page.locator("#grok-state")).to_have_text(re.compile(r"^Unavailable"))
            page.locator("#refresh").click()
            expect(page.locator("#refresh")).to_be_enabled()
            page.wait_for_load_state("networkidle")
            for prefix in ("grok", "local", "cpu"):
                require(page.locator("#" + prefix + "-state").inner_text().startswith("Unavailable"),
                        "fixture readiness label changed")
                require("LOCAL_PRESENTATION_FIXTURE" in page.locator("#" + prefix + "-detail").inner_text(),
                        "fixture limit missing")
            for path in API_PATHS:
                require(sum(urlsplit(item["url"]).path == path for item in requests) == 2,
                        "initial load and explicit refresh did not each read " + path)
        else:
            require("rendered by Python" in page.locator("noscript").inner_text(), "no-script guidance missing")
            require(not any(urlsplit(item["url"]).path in API_PATHS for item in requests),
                    "JavaScript-disabled view unexpectedly requested runtime observations")
        result = check_presentation(page, fixture["surfaces"])
        # Start keyboard traversal from the document, not the refresh button.
        page.goto(fixture["origin"] + route, wait_until="networkidle")
        page.keyboard.press("Tab")
        focused = page.evaluate("({tag:document.activeElement.tagName, href:document.activeElement.getAttribute('href'), top:document.activeElement.getBoundingClientRect().top})")
        require(focused["tag"] == "A" and focused["href"] == "#work" and focused["top"] >= 0,
                "keyboard skip link is not first and visible on focus")
        page.keyboard.press("Enter")
        require(urlsplit(page.url).fragment == "work", "skip link did not reach work section")
        page.evaluate("document.activeElement.blur(); window.scrollTo({top:0,left:0,behavior:'instant'})")
        result.update({"route": route, "viewport": {"width": width, "height": 900},
                       "javascript": javascript, "observed_at": now(), "document_bytes": len(body),
                       "document_sha256": sha256(body), "keyboard_skip_link": focused,
                       "requests": requests, "errors": errors, "violations": violations})
        require(not violations and not errors, "browser reported prohibited traffic or errors")
        if width in (320, 1280):
            name = route.strip("/").replace("/", "-") + f"-{width}-js-{'on' if javascript else 'off'}.png"
            image_path = output / name
            page.screenshot(path=str(image_path), full_page=True, animations="disabled")
            result["screenshot"] = {"path": name, "sha256": sha256(image_path.read_bytes()),
                                    "captured_at": now(), "full_page": True}
        return result
    finally:
        context.close()


def witness(expected, output, require_clean=False):
    source = source_identity(expected)
    require(not require_clean or source["clean_source_claimed"], "clean source is required")
    require(importlib.metadata.version("playwright") == "1.62.0", "Playwright 1.62.0 is required")
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
            "output directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema": "szl.python-command-centre-presentation-witness/v1", "scope": SCOPE,
              "state": "FAIL", "started_at": now(), "source": source,
              "require_clean_source": require_clean,
              "witness_source_sha256": sha256(Path(__file__).read_bytes()),
              "operational_runtime_verified": False, "provider_requests": 0,
              "fixture": {"inventory": "UNAVAILABLE", "health": "ready=false; LOCAL_PRESENTATION_FIXTURE",
                          "service_workers": "BLOCKED", "websockets": "BLOCKED",
                          "build_info": "local checkout declaration, not remote deployment evidence"},
              "observations": []}
    try:
        from playwright.sync_api import sync_playwright
        with fixture_server(expected) as fixture, sync_playwright() as playwright:
            report["presentation_sources"] = fixture["bindings"]
            report["renderer_input_sha256"] = fixture["renderer_input_sha256"]
            report["public_estate_sha256"] = fixture["public_estate_sha256"]
            with playwright.chromium.launch(headless=True) as browser:
                report["browser"] = {"playwright": "1.62.0", "chromium": browser.version,
                                     "binary_selection": "PLAYWRIGHT_BUNDLED_DEFAULT"}
                for route in ROUTES:
                    for width in (320, 390, 1280):
                        for javascript in (False, True):
                            report["observations"].append(observe(browser, fixture, route, width, javascript, output))
            require(all(row["method"] == "GET" for row in fixture["requests"]), "server observed a non-GET")
            report["server_request_count"] = len(fixture["requests"])
        require(source == source_identity(expected), "checkout changed during witness")
        report["state"] = "PASS"
        return report
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error)[:2000]}
        raise WitnessError(str(error)) from error
    finally:
        report["finished_at"] = now()
        (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--require-clean-source", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = witness(args.expected_source_sha, args.output_dir.resolve(), args.require_clean_source)
    except (WitnessError, OSError, subprocess.SubprocessError) as error:
        print("Presentation witness failed: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps({"state": report["state"], "scope": SCOPE,
                      "report": str(args.output_dir.resolve() / "report.json"),
                      "observations": len(report["observations"]), "source": report["source"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
