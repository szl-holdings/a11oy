# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline transport/isolation checks. Never start a server or browser."""
import copy
import hashlib
import importlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
fixture = importlib.import_module("console_lighthouse_fixture")
qa = importlib.import_module("test_console_mobile_integrity")
PORT = 8765
HOST = f"127.0.0.1:{PORT}"


@pytest.fixture(autouse=True)
def prohibit_processes_and_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Offline tests cannot open sockets, launch processes or fetch URLs")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(fixture, "ThreadingHTTPServer", forbidden)


@pytest.mark.parametrize("view", fixture.VIEWS)
def test_console_serves_exact_merged_bytes(view):
    response = fixture.resolve_request(f"/console?view={view}", "GET", HOST, PORT)
    assert response.status == 200
    assert response.body == (qa.ROOT / "pages/console.html").read_bytes()
    assert hashlib.sha256(response.body).hexdigest() == fixture.CONSOLE_SHA256


@pytest.mark.parametrize("target", [
    "/console", "/console?view=command", "/console?view=decision",
    "/console?view=estate&view=readiness", "/console?view=fleet&extra=1",
    "https://example.invalid/console?view=fleet", "//example.invalid/x",
    "/assets/../../AGENTS.md", "/assets/%2e%2e/%2e%2e/AGENTS.md",
    "/assets/..\\AGENTS.md", "/assets/%00file", "/console?view=fleet#decision",
])
def test_unapproved_routes_and_traversal_are_denied(target):
    assert fixture.resolve_request(target, "GET", HOST, PORT).status == 403


@pytest.mark.parametrize("host", ["localhost:8765", "example.invalid", "127.0.0.1:80", None])
def test_host_validation_prevents_nonloopback_authority(host):
    assert fixture.resolve_request("/console?view=fleet", "GET", host, PORT).status == 403


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT"])
def test_only_read_requests_are_accepted(method):
    assert fixture.resolve_request("/api/a11oy/v1/readiness", method, HOST, PORT).status == 405


def test_existing_fixtures_are_reused_without_mutation():
    state = qa.initial_fixture_state()
    snapshot = copy.deepcopy(state)
    for path in ("/api/a11oy/v1/readiness", "/api/a11oy/v1/models/series-a", "/api/a11oy/v1/observability/summary"):
        response = fixture.resolve_request(path, "GET", HOST, PORT, state=state)
        assert response.status == 200
        assert json.loads(response.body) == qa.fixture_payload(path, "", "GET", state, qa.fixture_receipts(), True)
    assert state == snapshot
    assert qa.fixture_receipts()[1].get("prev_hash") is None


@pytest.mark.parametrize("mode,expected", [("rows", 200), ("empty", 200), ("malformed", 200), ("error", 503)])
def test_readiness_and_health_fixture_states_remain_distinct(mode, expected):
    state = qa.initial_fixture_state()
    state["status_mode"] = mode
    for path in ("/api/a11oy/v1/readiness", "/api/a11oy/v1/observability/summary"):
        assert fixture.resolve_request(path, "GET", HOST, PORT, state=state).status == expected


@pytest.mark.parametrize("target", ["/api/counter-uas/evaluate", "/api/a11oy/v1/wow/ledger?advance=1", "/api/unknown"])
def test_unknown_or_advancing_requests_are_not_forwarded(target):
    response = fixture.resolve_request(target, "GET", HOST, PORT)
    assert response.status == 503
    assert json.loads(response.body)["source"] == "LOCAL TEST FIXTURE"


def test_static_assets_are_served_inside_their_own_tree(tmp_path):
    assets = tmp_path / "console/assets"
    assets.mkdir(parents=True)
    (assets / "safe.css").write_text("body {}")
    (tmp_path / "private.txt").write_text("not an asset")
    assert fixture.resolve_request("/assets/safe.css", "GET", HOST, PORT, root=tmp_path).status == 200
    assert fixture.resolve_request("/private.txt", "GET", HOST, PORT, root=tmp_path).status == 404
    assert qa.static_fixture_path("/assets/../../private.txt", tmp_path) is None


def test_source_pin_failure_is_explicit(tmp_path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages/console.html").write_text("different source")
    for target in ("/console?view=fleet", "/__fixture__/manifest"):
        assert fixture.resolve_request(target, "GET", HOST, PORT, root=tmp_path).status == 409


@pytest.mark.parametrize("name,length", [("SpaceGrotesk", 49256), ("JetBrainsMono", 113672)])
def test_real_embedded_fonts_have_exact_pinned_bytes(name, length):
    response = fixture.resolve_request(f"/vendor/fonts/{name}.woff2", "GET", HOST, PORT)
    assert response.status == 200
    assert response.content_type == "font/woff2"
    assert response.body.startswith(b"wOF2")
    assert len(response.body) == length
    assert hashlib.sha256(response.body).hexdigest() == fixture.FONT_SHA256[f"fonts/{name}.woff2"]
    headers = fixture.response_headers(response)
    assert headers["Cache-Control"] == "no-store"
    assert "font-src 'self' data:" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers


def test_embedded_font_routes_preserve_transport_guards():
    target = "/vendor/fonts/SpaceGrotesk.woff2"
    assert fixture.resolve_request(target, "POST", HOST, PORT).status == 405
    assert fixture.resolve_request(target, "GET", "example.invalid", PORT).status == 403
    assert fixture.resolve_request("/vendor/fonts/unknown.woff2", "GET", HOST, PORT).status == 404
    assert fixture.resolve_request("/vendor/fonts/../SpaceGrotesk.woff2", "GET", HOST, PORT).status == 403
    assert fixture.resolve_request("/_vendor_blobs.py", "GET", HOST, PORT).status == 404


@pytest.mark.parametrize("mode", ["missing", "tampered"])
def test_embedded_font_source_failures_stay_unavailable(tmp_path, mode):
    if mode == "tampered":
        (tmp_path / "_vendor_blobs.py").write_text("_B64 = {}")
    response = fixture.resolve_request("/vendor/fonts/SpaceGrotesk.woff2", "GET", HOST, PORT, root=tmp_path)
    assert response.status == 409
    assert json.loads(response.body)["state"] == "UNAVAILABLE"


def test_vendor_literals_are_never_executed(tmp_path, monkeypatch):
    sentinel = tmp_path / "executed.txt"
    source = ("_B64 = {'fonts/SpaceGrotesk.woff2': "
              f"__import__('pathlib').Path({str(sentinel)!r}).write_text('executed')}}").encode()
    (tmp_path / "_vendor_blobs.py").write_bytes(source)
    monkeypatch.setattr(fixture, "VENDOR_SOURCE_SHA256", hashlib.sha256(source).hexdigest())
    response = fixture.resolve_request("/vendor/fonts/SpaceGrotesk.woff2", "GET", HOST, PORT, root=tmp_path)
    assert response.status == 409
    assert not sentinel.exists()


@pytest.mark.parametrize("change", ["tamper", "delete"])
def test_vendor_source_is_revalidated_after_success(tmp_path, change):
    source = tmp_path / "_vendor_blobs.py"
    source.write_bytes((qa.ROOT / "_vendor_blobs.py").read_bytes())
    target = "/vendor/fonts/SpaceGrotesk.woff2"
    assert fixture.resolve_request(target, "GET", HOST, PORT, root=tmp_path).status == 200
    if change == "tamper":
        source.write_text("_B64 = {}")
    else:
        source.unlink()
    response = fixture.resolve_request(target, "GET", HOST, PORT, root=tmp_path)
    assert response.status == 409
    assert json.loads(response.body)["state"] == "UNAVAILABLE"
    source.write_bytes((qa.ROOT / "_vendor_blobs.py").read_bytes())
    assert fixture.resolve_request(target, "GET", HOST, PORT, root=tmp_path).status == 200


def test_headers_block_external_subresources_without_false_runtime_claims():
    response = fixture.resolve_request("/__fixture__/manifest", "GET", HOST, PORT)
    headers = fixture.response_headers(response)
    assert "connect-src 'self'" in headers["Content-Security-Policy"]
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "form-action 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers
    payload = json.loads(response.body)
    assert payload["source_pin_verified"] is True
    assert payload["runtime_qualified"] is False
    assert payload["source_revision"] == fixture.SOURCE_REVISION
    assert payload["vendor_source_sha256"] == fixture.VENDOR_SOURCE_SHA256
    assert payload["font_sha256"] == fixture.FONT_SHA256


def test_http_wrapper_uses_pure_resolver_without_socket():
    handler = object.__new__(fixture.FixtureHandler)
    handler.path, handler.command = "/api/a11oy/v1/readiness", "GET"
    handler.headers = {"Host": HOST}
    handler.server = SimpleNamespace(server_port=PORT)
    handler.wfile = io.BytesIO()
    statuses, headers = [], {}
    handler.send_response = statuses.append
    handler.send_header = lambda k, v: headers.update({k: v})
    handler.end_headers = lambda: None
    handler.handle_fixture()
    assert statuses == [200]
    assert json.loads(handler.wfile.getvalue())["source"] == "TEST FIXTURE"
    assert headers["Cache-Control"] == "no-store"


def test_cli_does_not_bind_without_explicit_serve(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["console_lighthouse_fixture.py"])
    with pytest.raises(SystemExit) as exit_info:
        fixture.main()
    assert exit_info.value.code == 2
