# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_canonical_domain — two origins, two jobs; this app never 301s a11oy.net.

Locked architecture:

  * a-11-oy.com is the product command center
  * a11oy.net is the public proof/registry (separate failure domain)
  * this app must NOT 301 .net onto .com, and must NOT 301 .com onto .net
  * the unhyphenated third-party host is never a redirect target
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
def test_registry_hosts_are_not_redirected_onto_the_product(host, path):
    c = _app()
    r = c.get(path, headers={"host": host})
    assert r.status_code != 301, f"{host}{path} must not 301 onto the product origin"
    assert "location" not in {k.lower() for k in r.headers.keys()} or not (
        r.headers.get("location") or ""
    ).startswith("https://a-11-oy.com")
    if path in ("/", "/frontier", "/elite"):
        assert r.status_code == 200, f"{host}{path} must pass through, got {r.status_code}"


def test_query_string_on_registry_host_is_not_rewritten():
    c = _app()
    r = c.get("/frontier?tab=live&x=1", headers={"host": "a11oy.net"})
    assert r.status_code == 200
    assert r.json() == {"surface": "frontier"}


def test_registry_host_with_port_is_not_redirected():
    c = _app()
    r = c.get("/frontier", headers={"host": "a11oy.net:8080"})
    assert r.status_code == 200
    assert r.json() == {"surface": "frontier"}


@pytest.mark.parametrize(
    "host",
    ["a-11-oy.com", "www.a-11-oy.com", "szlholdings-a11oy.hf.space", "localhost", "nota11oy.net.evil.com"],
)
def test_canonical_and_origin_hosts_serve_untouched(host):
    c = _app()
    r = c.get("/frontier", headers={"host": host})
    assert r.status_code == 200, f"{host} must serve, not redirect"
    assert r.json() == {"surface": "frontier"}


def test_product_host_is_not_redirected_onto_the_registry():
    c = _app()
    r = c.get("/frontier", headers={"host": "a-11-oy.com"})
    assert r.status_code == 200
    location = r.headers.get("location") or ""
    assert "a11oy.net" not in location


def test_forbidden_furniture_host_is_never_a_redirect_target():
    c = _app()
    for host in ("a11oy.net", "a-11-oy.com", "localhost"):
        r = c.get("/frontier", headers={"host": host})
        location = (r.headers.get("location") or "").lower()
        furniture = "a11oy.com"
        assert furniture not in location, f"{host} must not 301 toward the third-party host"


def test_registry_host_helper():
    assert cd._is_registry_host("a11oy.net")
    assert cd._is_registry_host("www.a11oy.net")
    assert cd._is_registry_host("anything.a11oy.net")
    assert not cd._is_registry_host("a-11-oy.com")
    assert not cd._is_registry_host("a11oy.net.evil.com")
    assert not cd._is_registry_host("evila11oy.net")
    assert not cd._is_forbidden_public_host("a-11-oy.com")
    assert cd._is_forbidden_public_host("a11oy.com")
    assert cd._is_product_host("a-11-oy.com")
    assert cd._is_product_host("www.a-11-oy.com")
    assert not cd._is_product_host("a11oy.net")
    assert cd._is_public_product_host("a-11-oy.com")
    assert cd._is_public_product_host("www.a-11-oy.com")
    assert cd._is_public_product_host("A-11-OY.COM:443")
    assert not cd._is_public_product_host("immune.a-11-oy.com")
    assert not cd._is_public_product_host("szlholdings-a11oy.hf.space")
    assert cd._is_hf_space_host("szlholdings-a11oy.hf.space")
    assert not cd._is_hf_space_host("a-11-oy.com")
    assert cd.FORBIDDEN_PUBLIC_HOST == "a11oy.com"
    assert cd.CANONICAL_HOST == "a-11-oy.com"
    assert cd.REGISTRY_HOST == "a11oy.net"
    assert not hasattr(cd, "SUNSET_DOMAIN")


def _joined_link(response) -> str:
    if hasattr(response.headers, "get_list"):
        return " ".join(response.headers.get_list("link") or [])
    if hasattr(response.headers, "getlist"):
        return " ".join(response.headers.getlist("link") or [])
    return response.headers.get("link") or ""


def test_product_canonical_url_never_uses_space_or_furniture_host():
    assert cd.product_canonical_url("/trust") == "https://a-11-oy.com/trust"
    assert cd.product_canonical_url("/") == "https://a-11-oy.com/"
    assert cd.product_canonical_url("/trust?utm=1") == "https://a-11-oy.com/trust"
    assert "huggingface.co" not in cd.product_canonical_url("/console")
    assert "a11oy.com" not in cd.product_canonical_url("/console").replace("a-11-oy.com", "")


@pytest.mark.parametrize("host", ["a-11-oy.com", "www.a-11-oy.com"])
def test_product_apex_host_stamps_link_canonical_not_hf_space(host):
    c = _app()
    r = c.get("/frontier", headers={"host": host})
    assert r.status_code == 200
    joined = _joined_link(r)
    assert "<https://a-11-oy.com/frontier>" in joined
    assert "canonical" in joined.lower()
    assert "huggingface.co/spaces/" not in joined
    furniture = "a11oy.com"
    assert furniture not in joined


def test_product_canonical_link_drops_query_string():
    c = _app()
    r = c.get("/frontier?utm=1&ref=hf", headers={"host": "a-11-oy.com"})
    joined = _joined_link(r)
    assert "<https://a-11-oy.com/frontier>" in joined
    assert "utm" not in joined
    assert "?" not in joined


def test_hf_space_host_omits_space_hub_canonical_and_does_not_stamp_product():
    """*.hf.space may omit Link canonical. Never emit the Space Hub as product canonical."""
    from starlette.responses import JSONResponse

    app = FastAPI()

    @app.get("/trust")
    async def _trust():
        response = JSONResponse({"surface": "trust"})
        response.headers["link"] = (
            '<https://huggingface.co/spaces/SZLHOLDINGS/a11oy>; rel="canonical"'
        )
        return response

    cd.register(app)
    c = TestClient(app, follow_redirects=False)
    r = c.get("/trust", headers={"host": "szlholdings-a11oy.hf.space"})
    assert r.status_code == 200
    joined = _joined_link(r)
    assert "huggingface.co/spaces/" not in joined
    furniture = "a11oy.com"
    assert furniture not in joined
    assert "<https://a-11-oy.com/trust>" not in joined


def test_forwarded_product_host_rewrites_even_when_origin_host_is_the_space():
    c = _app()
    r = c.get(
        "/frontier",
        headers={
            "host": "szlholdings-a11oy.hf.space",
            "x-forwarded-host": "a-11-oy.com",
        },
    )
    joined = _joined_link(r)
    assert "<https://a-11-oy.com/frontier>" in joined
    assert "huggingface.co/spaces/" not in joined


def test_registry_get_does_not_rewrite_product_canonical_link():
    c = _app()
    r = c.get("/frontier", headers={"host": "a11oy.net"})
    assert r.status_code == 200
    joined = " ".join(
        r.headers.get_list("link")
        if hasattr(r.headers, "get_list")
        else [r.headers.get("link") or ""]
    ).lower()
    assert "rel=" not in joined or "canonical" not in joined


def test_apply_product_canonical_link_drops_hf_space_header():
    from starlette.responses import Response

    response = Response(status_code=200)
    response.headers["link"] = '<https://huggingface.co/spaces/SZLHOLDINGS/a11oy>; rel="canonical"'
    cd.apply_product_canonical_link(response, "/trust")
    joined = " ".join(
        response.headers.getlist("link")
        if hasattr(response.headers, "getlist")
        else (
            response.headers.get_list("link")
            if hasattr(response.headers, "get_list")
            else [response.headers.get("link") or ""]
        )
    )
    assert "<https://a-11-oy.com/trust>" in joined
    assert "huggingface.co/spaces/" not in joined
    furniture = "a11oy.com"
    assert furniture not in joined

