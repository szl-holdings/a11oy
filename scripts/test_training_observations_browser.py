# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real restricted observation route and browser, using only fixtures.

LOCAL_ROUTE_GROUP integration: no production process, private report, existing
operator credential, model execution, provider mutation or release admission.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import threading
import time
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
API = "/api/a11oy/v1/models/training-observations"
IDENTITY = "SZLHOLDINGS/synthetic-browser-observation"


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def synthetic_report(ttl=660):
    """A terminal metadata fixture; every qualification and authority stays false."""
    now = datetime.now(timezone.utc)
    observed = now.isoformat()
    row = {
        "repo": IDENTITY, "state": "TERMINAL_METADATA_PRESENT", "target_steps": 200,
        "observed_at_utc": observed, "training_complete_verified": False,
        "promotion_authorized": False, "trainer_process_liveness_verified": False,
        "snapshot": {
            "id": IDENTITY, "status": "OBSERVED", "private": True, "revision": "a" * 40,
            "latest_checkpoint": 200, "artifact_integrity": "NOT_VERIFIED_BY_METADATA",
            "training_complete": "UNVERIFIED", "process_liveness_verified": False,
            "evaluation": "NOT_ASSESSED", "final_adapter": True,
            "final_config": True, "final_tokenizer": True,
        },
        "trainer_state": {"global_step": 200, "max_steps": 200,
            "trainer_state_sha256": "b" * 64, "integrity": "PINNED_OBJECT_BYTES_VERIFIED"},
        "provider": {"state": "OBSERVED", "instance_count": 0, "ready_count": 0,
            "trainer_process_liveness_verified": False},
    }
    return json.dumps({"schema": "szl.training-observation/v1", "cycle": 1,
        "started_at_utc": (now - timedelta(seconds=1)).isoformat(),
        "observed_at_utc": observed, "stale_after_seconds": ttl,
        "training_complete_verified": False, "promotion_authorized": False,
        "candidates": [row]}, allow_nan=False).encode()


def main():
    # Lazy imports keep basic fixture and compilation checks dependency-free.
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from playwright.sync_api import expect, sync_playwright
    sys.path.insert(0, str(ROOT))
    from routers import hf_tooling_evidence as tooling

    output = ROOT / "artifacts" / "training-observations"
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema": "szl.training-observations-browser/v1", "scope": "LOCAL_ROUTE_GROUP",
        "productionDeploymentVerified": False, "fixtureOnly": True,
        "trainingStarted": False, "modelInferencePerformed": False,
        "providerMutationPerformed": False, "observations": [], "pageErrors": []}
    with tempfile.TemporaryDirectory(prefix="szl-observation-browser-") as directory:
        source = Path(directory).resolve() / "synthetic-report.json"
        source.write_bytes(synthetic_report())
        # Always replace inherited credentials with fresh, process-local test values.
        token, tenant = secrets.token_urlsafe(32), "synthetic-" + secrets.token_hex(8)
        with patch.dict(os.environ, {"A11OY_TRAINING_OBSERVATION_FILE": str(source),
                "A11OY_CODE_ADMIN_KEY": token, "A11OY_CODE_TENANT": tenant}):
            app = FastAPI()
            tooling.register(app)
            app.mount("/assets", StaticFiles(directory=ROOT / "console/assets"), name="shared-assets")
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0)); listener.listen(128)
            origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
            server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
            worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            worker.start()
            try:
                deadline = time.monotonic() + 10
                while not server.started:
                    check(time.monotonic() < deadline, "Loopback server startup timed out")
                    time.sleep(.05)
                with sync_playwright() as playwright:
                    options = {"headless": True, "args": ["--no-sandbox"]}
                    if os.environ.get("SZL_TEST_CHROMIUM"):
                        options["executable_path"] = os.environ["SZL_TEST_CHROMIUM"]
                    browser = playwright.chromium.launch(**options)
                    try:
                        report["browser"] = browser.version
                        for width, height in ((1440, 1000), (390, 844), (320, 568)):
                            context = browser.new_context(viewport={"width": width, "height": height},
                                reduced_motion="reduce", service_workers="block")
                            page = context.new_page()
                            requests, forbidden = [], []

                            def restrict(route):
                                request = route.request
                                url = urlsplit(request.url)
                                own_origin = f"{url.scheme}://{url.netloc}" == origin
                                auth = "authorization" in request.headers
                                if not own_origin or request.method != "GET" or (auth and url.path != API):
                                    forbidden.append({"path": url.path, "method": request.method})
                                    route.abort(); return
                                if url.path == API:
                                    requests.append({"authorized": auth, "method": request.method})
                                route.continue_()

                            context.route("**/*", restrict)
                            page.on("pageerror", lambda error: report["pageErrors"].append(str(error)))
                            page.goto(origin + "/frontier-tooling/models", wait_until="networkidle")
                            expect(page.locator("#training-observation-load")).to_be_enabled()
                            check(not requests, "Anonymous page automatically fetched private observations")
                            expect(page.locator("#training-observation-cards")).to_be_empty()
                            headers = {"Authorization": "Bearer " + token, "X-A11oy-Tenant": tenant}
                            check(context.request.get(origin + API).status == 401, "Anonymous read admitted")
                            before = source.read_bytes()
                            for method in ("POST", "PUT", "PATCH", "DELETE"):
                                response = context.request.fetch(origin + API, method=method, headers=headers)
                                check(response.status == 405, "Observation write method was not rejected")
                            check(source.read_bytes() == before, "Read route changed the fixture")
                            tenant_field = page.locator("#training-observation-tenant")
                            token_field = page.locator("#training-observation-token")
                            status = page.locator("#training-observation-status")
                            cards = page.locator(".training-observation-card")
                            states = page.locator(".training-observation-state")
                            tenant_field.fill(tenant)

                            def load(*, ttl=660, fresh=True):
                                if fresh:
                                    source.write_bytes(synthetic_report(ttl))
                                token_field.fill(token)
                                with page.expect_response(lambda response: urlsplit(response.url).path == API) as pending:
                                    page.locator("#training-observation-load").click()
                                expect(token_field).to_have_value("")
                                return pending.value

                            response = load()
                            check(response.status == 200, "Real observation route failed")
                            check("private, no-store" == response.headers.get("cache-control"), "Private response cache changed")
                            observed = response.json()
                            check(observed["candidates"][0]["trainingCompleteVerified"] is False,
                                  "Terminal metadata claimed training completion")
                            expect(cards).to_have_count(1)
                            expect(cards).to_contain_text(IDENTITY)
                            expect(cards).to_contain_text("terminal metadata present")
                            expect(page.locator(".training-observation-checks")).to_contain_text("Training completion: unverified")
                            expect(page.locator(".training-observation-checks")).to_contain_text("Promotion: not authorized")
                            expect(states).to_contain_text("within reported time window")
                            page.locator("#search").fill("synthetic-no-public-inventory-match")
                            cards.locator("summary").click()
                            check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Viewport overflow")
                            page.screenshot(path=str(output / f"observations-{width}.png"), full_page=True)

                            source.write_bytes(b"{")
                            check(load(fresh=False).status == 503, "Corrupt source did not fail closed")
                            expect(status).to_contain_text("HTTP 503")
                            expect(cards).to_have_count(0)
                            load(); expect(cards).to_have_count(1)
                            tenant_field.fill("different-synthetic-tenant")
                            expect(cards).to_have_count(0)
                            tenant_field.fill(tenant)
                            load(); expect(cards).to_have_count(1)
                            # Negative browser fault only; successful responses above use real Python.
                            malformed = {**observed, "schema": "unknown-browser-fault/v99"}
                            pattern = "**" + API
                            page.route(pattern, lambda route: route.fulfill(status=200,
                                content_type="application/json", body=json.dumps(malformed)))
                            load(); expect(cards).to_have_count(0)
                            expect(status).to_contain_text("read-only contract")
                            page.unroute(pattern)

                            load(ttl=3)
                            expect(states).to_contain_text("within reported time window")
                            count = len(requests)
                            expect(states).to_contain_text("Expired observation", timeout=7000)
                            check(len(requests) == count, "Expiry automatically fetched private data")
                            load(); expect(states).to_contain_text("within reported time window")
                            count = len(requests)
                            page.evaluate("""() => {
                                const original = Date.now, future = original() + 700000;
                                try { Date.now = () => future;
                                    document.dispatchEvent(new Event('visibilitychange'));
                                } finally { Date.now = original; }
                            }""")
                            expect(states).to_contain_text("Expired observation")
                            check(len(requests) == count, "Visibility resume fetched private data")
                            page.locator("#training-observation-disconnect").click()
                            expect(cards).to_have_count(0)
                            expect(tenant_field).to_have_value("")
                            check(not forbidden, "Browser escaped the fixed local GET scope")
                            check(all(request["authorized"] for request in requests), "UI sent anonymous private request")
                            report["observations"].append({"width": width, "height": height,
                                "realRouteAndAdmission": True, "anonymousAutoFetch": False,
                                "terminalMetadataUnverified": True, "failedRefreshClearsRows": True,
                                "credentialEditClearsRows": True, "unknownSchemaRejected": True,
                                "localExpiry": True, "visibilityExpiry": True,
                                "writesRejected": True, "horizontalOverflow": False})
                            context.close()
                    finally:
                        browser.close()
                check(not report["pageErrors"], "Browser reported a script error")
                report["status"] = "PASS"
            finally:
                server.should_exit = True; worker.join(timeout=10); listener.close()
                report.setdefault("status", "FAILED")
                report["fileSha256"] = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                    for path in ("routers/hf_tooling_evidence.py", "routers/model_pretraining.py",
                        "routers/training_observations.py", "pages/model-pretraining.html",
                        "pages/training-observations.js", "pages/training-observations.css")}
                (output / "browser-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                check(not worker.is_alive(), "Loopback server did not terminate")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
