#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline/local transport contracts; browser execution is a separate witness."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "python_command_centre_witness", ROOT / "scripts/witness_python_command_centre.py")
witness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(witness)
REVISION = "a" * 40
ORIGIN = "http://127.0.0.1:4567"


@pytest.mark.parametrize("path", sorted(witness.ALLOWED_PATHS))
def test_only_fixed_local_get_paths_are_allowed(path):
    assert witness.request_allowed("GET", ORIGIN + path, ORIGIN)


@pytest.mark.parametrize("method,url", [
    ("POST", ORIGIN + "/api/a11oy/v1/atelier/turn"),
    ("POST", ORIGIN + "/command-centre"),
    ("HEAD", ORIGIN + "/command-centre"),
    ("GET", "https://a-11-oy.com/command-centre"),
    ("GET", "http://localhost:4567/command-centre"),
    ("GET", "http://127.0.0.1:4568/command-centre"),
    ("GET", ORIGIN + "/command-centre?redirect=foreign"),
    ("GET", ORIGIN + "/unknown"),
    ("GET", "http://user@127.0.0.1:4567/command-centre"),
])
def test_non_get_foreign_or_unknown_requests_are_denied(method, url):
    assert not witness.request_allowed(method, url, ORIGIN)


@pytest.mark.parametrize("url", ["ws://127.0.0.1:4567/socket", "wss://example.invalid/socket"])
def test_websockets_are_closed_without_connecting_to_server(url):
    socket = SimpleNamespace(url=url, close=Mock(), connect_to_server=Mock())
    requests, violations = [], []
    witness.block_websocket(socket, requests, violations)
    socket.close.assert_called_once_with(code=1008, reason="Presentation witness forbids WebSockets")
    socket.connect_to_server.assert_not_called()
    assert requests == violations == [{"method": "WEBSOCKET", "url": url, "type": "websocket"}]


def test_revision_mismatch_fails_before_browser_or_server(monkeypatch):
    monkeypatch.setattr(witness.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=REVISION + "\n"))
    with pytest.raises(witness.WitnessError, match="does not match"):
        witness.source_identity("b" * 40)


@pytest.mark.parametrize("revision", ["a" * 39, "A" * 40, "main", "", None])
def test_revision_must_be_exact_sha(revision):
    with pytest.raises(witness.WitnessError, match="exact lowercase"):
        witness.source_identity(revision)


def test_dirty_checkout_is_explicit_not_clean_source(monkeypatch):
    outputs = iter([REVISION + "\n", " M routers/command_centre.py\n"])
    monkeypatch.setattr(witness.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=next(outputs)))
    identity = witness.source_identity(REVISION)
    assert identity["worktree"] == "DIRTY_LOCAL_PRESENTATION"
    assert identity["clean_source_claimed"] is False
    assert identity["changed_paths"] == [" M routers/command_centre.py"]


def test_fixture_serves_real_page_headers_and_explicit_unavailable_health():
    with witness.fixture_server(REVISION) as fixture:
        with httpx.Client(trust_env=False, follow_redirects=False) as client:
            for path in witness.ROUTES:
                response = client.get(fixture["origin"] + path)
                assert response.status_code == 200
                assert response.content == fixture["body"]
                for header, value in fixture["headers"].items():
                    assert response.headers[header] == value
            for path in witness.HEALTH_PATHS:
                response = client.get(fixture["origin"] + path)
                assert response.json() == {
                    "ready": False, "state": "UNAVAILABLE",
                    "blockers": ["LOCAL_PRESENTATION_FIXTURE"], "scope": witness.SCOPE}
            inventory = client.get(fixture["origin"] + "/api/a11oy/v1/command-centre/inventory").json()
            assert inventory["state"] == "UNAVAILABLE" and inventory["counts"] is None
            build = client.get(fixture["origin"] + "/api/build-info").json()
            assert build["build"]["revision"] == REVISION and build["scope"] == witness.SCOPE
        assert all(row["method"] == "GET" for row in fixture["requests"])
        assert len(fixture["renderer_input_sha256"]) == 64
        assert len(fixture["public_estate_sha256"]) == 64


def test_existing_output_is_not_overwritten(tmp_path, monkeypatch):
    retained = tmp_path / "retained.txt"
    retained.write_text("preserved", encoding="utf-8")
    monkeypatch.setattr(witness, "source_identity", lambda _: {"revision": REVISION})
    monkeypatch.setattr(witness.importlib.metadata, "version", lambda _: "1.62.0")
    with pytest.raises(witness.WitnessError, match="new or empty"):
        witness.witness(REVISION, tmp_path)
    assert retained.read_text(encoding="utf-8") == "preserved"


def test_clean_source_mode_refuses_dirty_checkout_before_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(witness, "source_identity", lambda _: {
        "revision": REVISION, "clean_source_claimed": False})
    with pytest.raises(witness.WitnessError, match="clean source is required"):
        witness.witness(REVISION, tmp_path, require_clean=True)
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize("destination", ["work", "wrong"])
def test_skip_link_waits_for_navigation_but_rejects_wrong_destination(destination):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright, playwright.chromium.launch(headless=True) as browser:
        page = browser.new_page()
        page.set_content("<a href='#work'>Skip to work</a><main id='work'>Work</main>")
        page.evaluate("""destination => document.querySelector('a').addEventListener('click', event => {
            event.preventDefault();
            setTimeout(() => { location.hash = destination; }, 100);
        })""", destination)
        page.keyboard.press("Tab")
        if destination == "work":
            witness.follow_skip_link(page, "about:blank#work")
            assert page.url == "about:blank#work"
        else:
            with pytest.raises(AssertionError):
                witness.follow_skip_link(page, "about:blank#work", timeout=500)
            assert page.url == "about:blank#wrong"



def test_keyboard_origin_reset_preserves_document_and_existing_body_tabindex():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright, playwright.chromium.launch(headless=True) as browser:
        page = browser.new_page()
        page.set_content("<a href='#work'>Skip</a><button id='refresh'>Refresh</button>"
                         "<main id='work'>Work</main>")
        page.evaluate("document.body.setAttribute('tabindex', '7')")
        page.locator("#refresh").focus()
        before_url = page.url
        witness.reset_keyboard_origin(page)
        assert page.url == before_url
        assert page.locator("body").get_attribute("tabindex") == "7"
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.getAttribute('href')") == "#work"
        # Missing original tabindex is also restored: no persistent DOM mutation.
        page.evaluate("document.body.removeAttribute('tabindex')")
        page.locator("#refresh").focus()
        witness.reset_keyboard_origin(page)
        assert page.locator("body").get_attribute("tabindex") is None
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.getAttribute('href')") == "#work"


def test_failure_diagnostics_remain_bounded_and_omit_sensitive_url_parts():
    records = [{"method": "GET", "type": "fetch",
                "url": "https://user:password@example.invalid/path?credential=secret#fragment"}] * 40
    evidence = witness.failed_observation("/command-centre", 320, True,
                                          ["fixture-error" * 100] * 25, records, records)
    assert len(evidence["errors"]) == 20
    assert len(evidence["errors"][0]) <= 1000
    assert len(evidence["requests"]) == 30
    assert len(evidence["violations"]) == 20
    assert evidence["counts"] == {"errors": 25, "requests": 40, "violations": 40}
    assert evidence["truncated"] is True
    assert evidence["requests"][0] == {"method": "GET", "type": "fetch",
                                      "host": "example.invalid", "path": "/path"}


def test_browser_errors_are_retained_without_waiving_the_gate(tmp_path):
    from playwright.sync_api import sync_playwright
    with witness.fixture_server(REVISION) as fixture, sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as browser:
            def context_with_error(**kwargs):
                context = browser.new_context(**kwargs)
                context.add_init_script("console.error('SYNTHETIC_EXPECTED_BROWSER_FAILURE')")
                return context
            with pytest.raises(witness.WitnessError, match="browser reported") as raised:
                witness.observe(SimpleNamespace(new_context=context_with_error), fixture,
                                "/command-centre", 320, True, tmp_path)
    evidence = raised.value.observation
    assert evidence["javascript"] is True and evidence["width"] == 320
    assert any("SYNTHETIC_EXPECTED_BROWSER_FAILURE" in item for item in evidence["errors"])
    assert evidence["counts"]["errors"] > 0
    assert evidence["violations"] == []

def test_fixture_allows_only_its_exact_digest_assets():
    import hashlib
    from routers import command_centre_view as view
    with witness.fixture_server(REVISION) as fixture:
        assert len(fixture['asset_paths']) == 4
        with httpx.Client(trust_env=False, follow_redirects=False) as client:
            for path in fixture['asset_paths']:
                digest, filename = path.split('/')[-2:]
                assert digest == fixture['bindings'][view.ASSET_SOURCES[filename]]
                assert witness.request_allowed('GET', fixture['origin'] + path,
                                               fixture['origin'], fixture['allowed_paths'])
                response = client.get(fixture['origin'] + path)
                assert response.status_code == 200
                assert hashlib.sha256(response.content).hexdigest() == digest
                assert not witness.request_allowed(
                    'GET', fixture['origin'] + path.replace(digest, '0' * 64),
                    fixture['origin'], fixture['allowed_paths'])
                assert not witness.request_allowed(
                    'POST', fixture['origin'] + path, fixture['origin'], fixture['allowed_paths'])
                assert not witness.request_allowed(
                    'GET', fixture['origin'] + path + '?bypass=1',
                    fixture['origin'], fixture['allowed_paths'])


def test_browser_rejects_altered_script_and_keeps_all_send_buttons_disabled(monkeypatch):
    from fastapi.responses import Response
    from playwright.sync_api import expect, sync_playwright
    from routers import command_centre as centre

    register = centre.register
    tampered_body = b"window.alteredAssetRan=true; for(const id of ['send','local-send','cpu-send']) document.getElementById(id).disabled=false;"

    def register_with_tampered_transport(app):
        result = register(app)
        @app.middleware('http')
        async def alter_script(request, call_next):
            response = await call_next(request)
            if request.url.path.startswith('/command-centre/assets/') and request.url.path.endswith('/app.js'):
                return Response(tampered_body, media_type='text/javascript')
            return response
        return result

    monkeypatch.setattr(centre, 'register', register_with_tampered_transport)
    with witness.fixture_server(REVISION) as fixture:
        with sync_playwright() as playwright, playwright.chromium.launch(headless=True) as browser:
            page = browser.new_page()
            console_errors, scripts = [], []
            page.on('console', lambda message: console_errors.append(message.text)
                    if message.type == 'error' else None)
            page.on('response', lambda response: scripts.append(response)
                    if response.url.endswith('/app.js') else None)
            response = page.goto(fixture['origin'] + '/command-centre', wait_until='networkidle')
            assert response.status == 200
            assert len(scripts) == 1 and scripts[0].status == 200
            assert scripts[0].body() == tampered_body
            assert page.evaluate('window.alteredAssetRan === undefined') is True
            for button in witness.BUTTONS:
                expect(page.locator('#' + button)).to_be_disabled()
            assert any('integrity' in error.lower() for error in console_errors)
            assert all(row['method'] == 'GET' for row in fixture['requests'])
            assert not any('/atelier/' in row['path'] for row in fixture['requests'])
