# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_canonical_domain — a11oy.net is redirect-only; it must NOT serve user surfaces.

Doctrine: "No a11oy.net on user surfaces (canonical a-11-oy.com WITH hyphens);
a11oy.net sunset except redirect middleware." These checks pin the behavior so the
sunset host can never regress to serving content:

  * ANY path on Host a11oy.net (apex), www.a11oy.net, or any *.a11oy.net subdomain
    301-redirects to the SAME path on https://a-11-oy.com (path + query preserved);
  * the canonical host a-11-oy.com, the HF Space host, and localhost are passed
    through untouched, so the app keeps serving on its origin.
"""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import a11oy_canonical_domain as cd


def _app():
    app = FastAPI()

    @app.get("/")
    async def _root():
        return {"surface": "root"}

    @app.get("/frontier")
    async def _frontier():
        return {"surface": "frontier"}

    @app.get("/elite")
    async def _elite():
        return {"surface": "elite"}

    cd.register(app)
    return TestClient(app, follow_redirects=False)


@pytest.mark.parametrize("host", ["a11oy.net", "www.a11oy.net", "app.a11oy.net", "A11OY.NET"])
@pytest.mark.parametrize("path", ["/", "/frontier", "/elite", "/deep/nested/path"])
def test_sunset_hosts_301_to_canonical_same_path(host, path):
    c = _app()
    r = c.get(path, headers={"host": host})
    assert r.status_code == 301, f"{host}{path} must 301, got {r.status_code}"
    assert r.headers["location"] == f"https://a-11-oy.com{path}", (
        f"{host}{path} must redirect to canonical same-path"
    )


def test_query_string_is_preserved():
    c = _app()
    r = c.get("/frontier?tab=live&x=1", headers={"host": "a11oy.net"})
    assert r.status_code == 301
    assert r.headers["location"] == "https://a-11-oy.com/frontier?tab=live&x=1"


def test_sunset_host_with_port_is_matched():
    c = _app()
    r = c.get("/frontier", headers={"host": "a11oy.net:8080"})
    assert r.status_code == 301
    assert r.headers["location"] == "https://a-11-oy.com/frontier"


@pytest.mark.parametrize(
    "host",
    ["a-11-oy.com", "www.a-11-oy.com", "szlholdings-a11oy.hf.space", "localhost", "nota11oy.net.evil.com"],
)
def test_canonical_and_origin_hosts_serve_untouched(host):
    c = _app()
    r = c.get("/frontier", headers={"host": host})
    assert r.status_code == 200, f"{host} must serve, not redirect"
    assert r.json() == {"surface": "frontier"}


def test_is_sunset_host_helper():
    assert cd._is_sunset_host("a11oy.net")
    assert cd._is_sunset_host("www.a11oy.net")
    assert cd._is_sunset_host("anything.a11oy.net")
    # Must NOT match look-alikes that merely contain the string.
    assert not cd._is_sunset_host("a-11-oy.com")
    assert not cd._is_sunset_host("a11oy.net.evil.com")
    assert not cd._is_sunset_host("evila11oy.net")
