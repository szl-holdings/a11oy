#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Isolated route and browser contracts; no full server import or external network."""

import copy
import json
import os
import re
from urllib.parse import urlsplit

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_frontier_page as frontier


RUNTIME_ID = "edge-" + "a" * 64
HISTORY_ID = "edge-" + "b" * 64
WITNESS_ID = "edge-" + "c" * 64
MISSING_ID = "edge-" + "e" * 64
ENDPOINT = "/api/a11oy/v1/evidence/graph"


def _edge(receipt_id, kind, subject_id, parents=()):
    return {
        "schema": "szl.evidence-edge/v1",
        "receipt_id": receipt_id,
        "subject": {"kind": kind, "id": subject_id},
        "source_revision": "a" * 40,
        "artifact_sha256": None,
        "runtime": {"boot_id": "fixture-boot"},
        "evidence": {"kind": "fixture", "signature_status": "UNSIGNED", "claims_verified": False},
        "authority": {"execution_authorized": False},
        "parents": list(parents),
        "invariant_ids": [],
        "verdict": "OBSERVED",
        "reason": "SYNTHETIC_TEST_FIXTURE",
    }


def _payload():
    runtime = _edge(RUNTIME_ID, "runtime", "fixture-runtime")
    history = _edge(HISTORY_ID, "training", "fixture-history")
    history.update(source_revision=None, artifact_sha256="f" * 64, runtime={})
    history["evidence"].update(
        kind="receipt-artifact",
        artifact_uri="https://huggingface.co/datasets/example/receipts/resolve/fixture/receipt.json",
        signature_status="UNVERIFIED",
    )
    witness = _edge(WITNESS_ID, "runtime-source-witness", "fixture-source-witness", (RUNTIME_ID, MISSING_ID))
    assessments = {
        RUNTIME_ID: {"scope": "RUNTIME_OBSERVATION", "source_relation": "MATCHES_RUNTIME_OBSERVATION"},
        HISTORY_ID: {"scope": "HISTORICAL_ARTIFACT", "source_relation": "UNBOUND"},
        WITNESS_ID: {"scope": "RUNTIME_SOURCE_WITNESS", "source_relation": "MATCHES_RUNTIME_OBSERVATION"},
    }
    for item in assessments.values():
        item.update(freshness="UNKNOWN", observed_at="2026-11-01T00:00:00Z", valid_until=None)
    return {
        "schema": "szl.evidence-graph/v1",
        "state": "DEGRADED",
        "reason": "SYNTHETIC_TEST_FIXTURE",
        "captured_at": "2026-11-01T00:00:00Z",
        "runtime_identity_state": "OBSERVED",
        "graph": {
            "schema": "szl.evidence-graph/v1",
            "edges": [runtime, history, witness],
            "edge_count": 3,
            "digest_sha256": "d" * 64,
            "digest_scope": "RETURNED_EDGES",
            "bounded": False,
            "ledger_head": None,
            "causal_heads": [HISTORY_ID, WITNESS_ID],
        },
        "edge_assessments": assessments,
        "provenance_witness": {
            "state": "DEGRADED", "status": "BLOCKED", "reason": "FIXTURE_SOURCE_BLOCKER",
            "source_revision": "a" * 40, "hf_revision": "b" * 40,
            "runtime_boot_id": "fixture-boot", "local_bytes_evidence": "UNAVAILABLE",
            "scope": "FINAL_APP_SOURCE_COPY_FILES", "execution_authority": False,
        },
        "blockers": ["FIXTURE_SOURCE_BLOCKER"],
    }


@pytest.fixture
def client():
    app = FastAPI()
    frontier.register(app)
    with TestClient(app) as test_client:
        yield test_client


def test_lightweight_page_serves_inspector_and_fixed_assets(client):
    response = client.get("/frontier")
    assert response.status_code == 200
    assert 'data-endpoint="' + ENDPOINT + '"' in response.text
    assert 'aria-labelledby="ceg-heading"' in response.text
    assert 'href="' + ENDPOINT + '"' in response.text
    assert 'defer src="/frontier/evidence-explorer.js"' in response.text
    for route, filename, content_type in (
        ("/frontier/evidence-explorer.js", "ceg-explorer.js", "application/javascript"),
        ("/frontier/evidence-explorer.css", "ceg-explorer.css", "text/css"),
    ):
        asset = client.get(route)
        assert asset.status_code == 200
        assert asset.headers["content-type"].startswith(content_type)
        assert asset.headers["x-content-type-options"] == "nosniff"
        assert asset.content == (frontier._REPO_ROOT / "static" / "shared" / filename).read_bytes()
    assert client.get("/frontier/unknown.js").status_code == 404
    manifest = client.get("/api/a11oy/v1/frontier/page-manifest").json()
    assert ENDPOINT in manifest["renders_endpoints"]
    assert manifest["evidence_inspector"]["execution_authority"] is False
    assert manifest["links"]["evidence_graph"] == ENDPOINT


def test_missing_inspector_asset_is_a_json_404(client, monkeypatch, tmp_path):
    monkeypatch.setattr(frontier, "_REPO_ROOT", tmp_path)
    response = client.get("/frontier/evidence-explorer.js")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_inspector_styles_use_vendored_design_tokens():
    css = (frontier._REPO_ROOT / "static" / "shared" / "ceg-explorer.css").read_text(encoding="utf-8")
    assert "var(--font-body)" in css
    assert "var(--focus)" in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|https?://", css)
    html = frontier._page_html("a11oy")
    assert html.index("/assets/szl/szl-design-system.css") < html.index("/frontier/evidence-explorer.css")


@pytest.fixture
def browser_view(client):
    require_browser = os.environ.get("SZL_REQUIRE_EVIDENCE_BROWSER") == "1"
    try:
        import playwright.sync_api as playwright_api
    except ImportError:
        if require_browser:
            pytest.fail("SZL_REQUIRE_EVIDENCE_BROWSER=1 requires Playwright; it could not be imported.", pytrace=False)
        pytest.skip("Playwright is not installed for this optional local browser contract.")
    with playwright_api.sync_playwright() as playwright:
        browser = None
        for channel in (None, "chrome", "msedge"):
            try:
                options = {"headless": True}
                if channel:
                    options["channel"] = channel
                browser = playwright.chromium.launch(**options)
                break
            except playwright_api.Error:
                continue
        if browser is None:
            message = "A local Chromium, Chrome, or Edge installation is required for this browser contract."
            if require_browser:
                pytest.fail("SZL_REQUIRE_EVIDENCE_BROWSER=1: " + message, pytrace=False)
            pytest.skip(message)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        response_state = {"payload": _payload(), "status": 200, "content_type": "application/json"}
        requests = []

        def respond(route):
            url = urlsplit(route.request.url)
            requests.append(route.request.url)
            if url.hostname != "frontier.test":
                route.abort()
                return
            if url.path == ENDPOINT:
                body = response_state.get("body")
                if body is None:
                    body = json.dumps(response_state["payload"])
                route.fulfill(status=response_state["status"],
                              content_type=response_state["content_type"], body=body)
            elif url.path.startswith("/assets/szl/"):
                filename = url.path.rsplit("/", 1)[-1]
                if filename in ("szl-design-system.css", "szl-console.css"):
                    body = (frontier._REPO_ROOT / "console" / "assets" / "szl" / filename).read_bytes()
                    route.fulfill(status=200, content_type="text/css", body=body)
                else:
                    route.fulfill(status=404, body="Unavailable")
            elif url.path in ("/frontier", "/frontier/evidence-explorer.js", "/frontier/evidence-explorer.css"):
                response = client.get(url.path)
                route.fulfill(status=response.status_code, body=response.content,
                              content_type=response.headers["content-type"])
            else:
                # The independent inspector must work even if the 3D module is absent.
                route.fulfill(status=404, content_type="application/json", body='{"state":"UNAVAILABLE"}')

        page.route("**/*", respond)
        page.goto("http://frontier.test/frontier", wait_until="domcontentloaded")
        playwright_api.expect(page.locator("#ceg-status")).to_contain_text("Received by this browser")
        yield page, response_state, requests, playwright_api.expect
        browser.close()


def test_browser_separates_history_and_follows_only_declared_parents(browser_view):
    page, _, requests, expect = browser_view
    expect(page.locator("#ceg-count")).to_have_text("3 of 3 returned edges")
    expect(page.locator("#ceg-blockers")).to_contain_text("FIXTURE_SOURCE_BLOCKER")
    page.locator("#ceg-scope").select_option("historical")
    expect(page.locator("#ceg-count")).to_have_text("1 of 3 returned edges")
    expect(page.locator("#ceg-details h3")).to_have_text("training / fixture-history")
    expect(page.locator("#ceg-details")).to_contain_text("UNVERIFIED")
    expect(page.locator("#ceg-details")).to_contain_text("UNBOUND")
    expect(page.locator("#ceg-details")).to_contain_text("f" * 64)
    expect(page.locator("#ceg-details .ceg-parent-link")).to_have_count(0)
    expect(page.locator("#ceg-details .ceg-artifact a")).to_have_attribute("rel", "noopener noreferrer")
    page.locator("#ceg-scope").select_option("all")
    page.locator("#ceg-list button").filter(has_text="fixture-source-witness").click()
    expect(page.locator("#ceg-details .ceg-parent-link")).to_have_count(1)
    expect(page.locator("#ceg-details .ceg-parents")).to_contain_text(MISSING_ID + " — outside")
    page.locator("#ceg-details .ceg-parent-link").click()
    expect(page.locator("#ceg-details h3")).to_have_text("runtime / fixture-runtime")
    expect(page.locator("#ceg-details")).to_be_focused()
    page.locator("#ceg-filter").fill(HISTORY_ID)
    expect(page.locator("#ceg-count")).to_have_text("1 of 3 returned edges")
    expect(page.locator("#ceg-details h3")).to_have_text("training / fixture-history")
    assert all(urlsplit(url).hostname == "frontier.test" for url in requests)


def test_browser_failed_refresh_clears_prior_data(browser_view):
    page, response, _, expect = browser_view
    response["status"] = 503
    page.locator("#ceg-refresh").click()
    expect(page.locator("#ceg-status")).to_contain_text("UNAVAILABLE — HTTP 503")
    expect(page.locator("#ceg-list button")).to_have_count(0)
    expect(page.locator("#ceg-summary")).to_be_empty()
    expect(page.locator("#evidence-inspector")).not_to_contain_text(RUNTIME_ID)
    expect(page.locator("#ceg-witness")).to_have_text("Runtime source witness unavailable.")
    expect(page.locator("#ceg-refresh")).to_be_enabled()


@pytest.mark.parametrize("bad_response", ["html", "schema", "count", "duplicate", "oversized"])
def test_browser_rejects_invalid_response_without_retaining_evidence(browser_view, bad_response):
    page, response, _, expect = browser_view
    if bad_response == "html":
        response.update(content_type="text/html", body="<html>SPA fallback</html>")
    elif bad_response == "schema":
        response["payload"]["graph"]["schema"] = "unknown"
    elif bad_response == "count":
        response["payload"]["graph"]["edge_count"] = 12
    elif bad_response == "duplicate":
        response["payload"]["graph"]["edges"][1] = copy.deepcopy(response["payload"]["graph"]["edges"][0])
    else:
        response["body"] = " " * (2 * 1024 * 1024 + 1)
    page.locator("#ceg-refresh").click()
    expect(page.locator("#ceg-status")).to_contain_text("UNAVAILABLE")
    expect(page.locator("#ceg-list button")).to_have_count(0)
    expect(page.locator("#ceg-summary")).to_be_empty()


def test_browser_uses_safe_text_and_public_https_links_only(browser_view):
    page, response, requests, expect = browser_view
    history = response["payload"]["graph"]["edges"][1]
    history["subject"]["id"] = '<img id="ceg-injected" src=x onerror="window.cegInjected=true">'
    for uri in (
        "javascript:alert(1)", "http://huggingface.co/file",
        "https://user:password@huggingface.co/file", "https://127.0.0.1/file",
        "https://huggingface.co.attacker.test/file", "https://github.com:8443/file",
        "//github.com/example/file", "https://unknown.example/file",
    ):
        history["evidence"]["artifact_uri"] = uri
        page.locator("#ceg-refresh").click()
        expect(page.locator("#ceg-status")).to_contain_text("Received by this browser")
        page.locator("#ceg-scope").select_option("historical")
        expect(page.locator("#ceg-details h3")).to_contain_text('<img id="ceg-injected"')
        expect(page.locator("#ceg-injected")).to_have_count(0)
        expect(page.locator("#ceg-details .ceg-artifact a")).to_have_count(0)
    assert page.evaluate("window.cegInjected === undefined")
    assert all(urlsplit(url).hostname == "frontier.test" for url in requests)


def test_browser_keeps_keyboard_focus_and_mobile_digest_readable(browser_view):
    page, _, _, expect = browser_view
    history = page.locator("#ceg-list button").filter(has_text="fixture-history")
    history.focus()
    history.press("Enter")
    expect(page.locator('#ceg-list button[aria-pressed="true"]')).to_be_focused()
    page.set_viewport_size({"width": 375, "height": 812})
    page.locator("#evidence-inspector").scroll_into_view_if_needed()
    expect(page.locator("#ceg-details")).to_contain_text("f" * 64)
    assert page.locator("#evidence-inspector").evaluate(
        "(element) => element.scrollWidth <= element.clientWidth + 1"
    )


def test_browser_preserves_explicit_unknowns_for_older_observation_api(browser_view):
    page, response, _, expect = browser_view
    response["payload"].pop("edge_assessments")
    response["payload"].pop("provenance_witness")
    response["payload"].pop("blockers")
    response["payload"]["graph"]["edges"][1]["evidence"].pop("signature_status")
    page.locator("#ceg-refresh").click()
    expect(page.locator("#ceg-status")).to_contain_text("Received by this browser")
    page.locator("#ceg-scope").select_option("historical")
    expect(page.locator("#ceg-details")).to_contain_text("Assessment unavailable")
    expect(page.locator("#ceg-details")).to_contain_text("UNSPECIFIED")
    expect(page.locator("#ceg-details")).to_contain_text("NOT ASSESSED")
    expect(page.locator("#ceg-witness")).to_contain_text("NOT SUPPLIED")


def test_browser_accepts_the_registered_backend_contract(browser_view):
    import szl_evidence_graph as evidence_graph

    page, response, _, expect = browser_view
    app = FastAPI()
    evidence_graph.register(app)
    with TestClient(app) as backend:
        result = backend.get(ENDPOINT)
    assert result.status_code == 200
    payload = result.json()
    response["payload"] = payload
    page.locator("#ceg-refresh").click()
    expect(page.locator("#ceg-status")).to_contain_text("Received by this browser")
    count = payload["graph"]["edge_count"]
    expect(page.locator("#ceg-count")).to_have_text(f"{count} of {count} returned edges")
    expect(page.locator("#ceg-summary")).to_contain_text(payload["graph"]["digest_sha256"])
    if count:
        expect(page.locator("#ceg-list button")).to_have_count(count)


def test_browser_labels_missing_omitted_and_unresolved_parent_evidence(browser_view):
    page, response, _, expect = browser_view
    graph = response["payload"]["graph"]
    graph.update(missing_parent_ids=[MISSING_ID], missing_parent_count=1,
                 omitted_parent_ids=[], omitted_parent_count=0, unresolved_parent_count=0)
    page.locator("#ceg-refresh").click()
    expect(page.locator("#ceg-status")).to_contain_text("Received by this browser")
    page.locator("#ceg-list button").filter(has_text="fixture-source-witness").click()
    expect(page.locator("#ceg-details .ceg-parents")).to_contain_text("reported missing from the source")
    expect(page.locator("#ceg-details .ceg-parents")).to_contain_text("source comparison only")
    expect(page.locator("#ceg-summary")).to_contain_text("Unresolved parent IDs")
    graph.update(missing_parent_ids=[], missing_parent_count=0,
                 omitted_parent_ids=[MISSING_ID], omitted_parent_count=1)
    page.locator("#ceg-refresh").click()
    expect(page.locator("#ceg-status")).to_contain_text("Received by this browser")
    page.locator("#ceg-list button").filter(has_text="fixture-source-witness").click()
    expect(page.locator("#ceg-details .ceg-parents")).to_contain_text("omitted from the returned snapshot")
    expect(page.locator("#ceg-details .ceg-parent-link")).to_have_count(1)
