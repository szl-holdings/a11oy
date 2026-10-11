#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""OAC is a static, read-only release handoff, not a scoring or proxy route."""

from html.parser import HTMLParser
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import serve


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "oac.html"
CLIENT = TestClient(serve.app)
PATHS = ("/oac", "/oac/")
WRITES = ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT")


class Surface(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.mark.parametrize("path", PATHS)
def test_oac_get_head_are_exact_static_page(path):
    get = CLIENT.get(path)
    head = CLIENT.head(path)
    assert get.status_code == head.status_code == 200
    assert get.content == PAGE.read_bytes()
    assert head.content == b""
    assert get.headers["content-type"].startswith("text/html")
    assert get.headers["cache-control"] == "no-store, no-transform"
    assert head.headers["content-type"] == get.headers["content-type"]
    assert head.headers["cache-control"] == get.headers["cache-control"]
    assert head.headers["content-security-policy"] == get.headers["content-security-policy"]
    assert "script-src 'none'" in get.headers["content-security-policy"]
    assert "connect-src 'none'" in get.headers["content-security-policy"]
    assert "frame-ancestors 'self';" in get.headers["content-security-policy"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("method", WRITES)
def test_oac_plain_non_read_methods_are_explicitly_denied(path, method):
    response = CLIENT.request(method, path, content=b"not executable")
    assert response.status_code == 405
    assert response.headers["allow"] == "GET, HEAD"
    assert response.json()["status"] == "METHOD_NOT_ALLOWED"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method", ("POST", "PUT", "PATCH", "DELETE"))
def test_cors_preflight_is_transport_only_and_cannot_authorize_oac_writes(method):
    origin = "https://a-11-oy.com"
    preflight = CLIENT.options("/oac", headers={
        "Origin": origin, "Access-Control-Request-Method": method,
    })
    # Existing global CORS answers the preflight, not the OAC denial endpoint.
    assert preflight.status_code in {200, 400}
    write = CLIENT.request(method, "/oac", headers={"Origin": origin}, content=b"blocked")
    assert write.status_code == 405
    assert write.json()["status"] == "METHOD_NOT_ALLOWED"
    assert write.headers["allow"] == "GET, HEAD"


def test_oac_routes_own_all_methods_before_catchalls():
    for path in PATHS:
        for method in ("GET", "HEAD", *WRITES):
            owners = [
                index for index, route in enumerate(serve.app.routes)
                if getattr(route, "path", None) == path
                and method in getattr(route, "methods", set())
            ]
            assert len(owners) == 1, (path, method, owners)
            catchalls = [
                index for index, route in enumerate(serve.app.routes)
                if "{full_path:path}" in getattr(route, "path", "")
                and method in getattr(route, "methods", set())
            ]
            assert all(owners[0] < index for index in catchalls)


def test_oac_missing_page_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "PAGES_DIR", tmp_path)
    response = CLIENT.get("/oac")
    assert response.status_code == 404
    assert response.json()["status"] == "UNAVAILABLE"
    assert "text/html" not in response.headers["content-type"]
    assert "frame-ancestors 'self'" in response.headers["content-security-policy"]


def test_oac_page_is_bounded_accessible_and_has_no_execution_path():
    data = PAGE.read_bytes()
    assert len(data) < 16000
    source = data.decode("utf-8")
    parser = Surface()
    parser.feed(source)
    assert not any(tag in {"script", "iframe", "form", "object", "embed"}
                   for tag, _ in parser.elements)
    assert not any(key.startswith("on") for _, attrs in parser.elements for key in attrs)
    styles = [attrs["href"] for tag, attrs in parser.elements
              if tag == "link" and attrs.get("rel") == "stylesheet"]
    assert styles == ["/assets/szl/szl-design-system.css"]
    assert (ROOT / "console" / styles[0].lstrip("/")).is_file()
    assert 'href="#main"' in source
    assert 'id="main"' in source
    assert "min-height:44px" in source
    assert "focus-visible" in source
    assert "prefers-reduced-motion" in source
    for label in ("REPORTED", "UNKNOWN", "SAMPLE", "DECLARED", "SIMULATED",
                  "current runtime (not probed by this page)",
                  "synthetic numeric telemetry", "not clinical", "not device control",
                  "No new training", "mutable demo", "not a production or clinical result path",
                  "Do not enter patient or specimen information"):
        assert label in source
    for identity in (
        "234a2dfb4c511318febfd20ca2f695fa9cb2ea8c",
        "36966679696",
        "4bf4d94161c0d135af6b5a3bc25f45b06f6e3979",
        "dd7d109813abcd90c5250106dc2eabd2804e7ac3",
        "f7ab6170bf78138b187b8cb707d374a25ad85375",
        "6330dea7318effba583a6501346fee590174a39f",
        "a824a32d91a383d33a1e1e595f11b8362d1b4efa",
        "3f7554efaddf086680b25301502c3bf176d83089",
        "1c33503830a12c5661fc3ee8cd0a4b3a75451c25",
    ):
        assert identity in source
    assert "The default demo above remains the separate v1 experience." in source
    assert "https://szlholdings-oac-system-health-lab.hf.space/#v2-panel" in source
    assert "https://github.com/szl-holdings/szl-forge/actions/runs/37728965604" in source
    assert "https://a11oy.net/oac/#v2" in source
    assert "unsigned artifact receipt" in source
    assert "does not authenticate that origin, validate results, or authorize effects" in source
    for superseded in ("5b3dfdf9beafe0d6d1e6043ca005ec4b17c45204", "456801e7313e09b62c74fa68be5c165ecf12d79c"):
        assert superseded not in source


def test_oac_opts_out_of_product_flow_rollout():
    from scripts import rollout_frontend_flow_shell as flow

    state = json.loads((ROOT / "docs" / "frontend-flow-shell-state.json").read_text(encoding="utf-8"))
    source = PAGE.read_text(encoding="utf-8")
    assert "data-szl-flow-opt-out" in source
    assert flow.opted_out(PAGE)
    assert not flow.self_contained(PAGE)
    assert "pages/oac.html" not in state["self_contained_documents"]
    assert "pages/oac.html" not in state["injected_documents"]
    assert PAGE not in flow.candidates()
