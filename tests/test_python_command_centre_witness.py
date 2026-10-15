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
