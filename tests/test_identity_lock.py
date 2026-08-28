# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Identity-lock contracts: product canonicals, forbidden third-party host, HEAD.

The unhyphenated furniture-shop host must never appear as canonical / og:url /
twitter:url / sameAs / JSON-LD url. Trust Center on this app is a product route
(https://a-11-oy.com/trust). HEAD and GET must agree on HTML document routes.

Hugging Face runtime.domains may report a-11-oy.com PENDING while Cloudflare
still serves the apex. That is KALLPA/Stephen DNS. HTML canonicals stay on
the public product origin; they are not rewritten to *.hf.space.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Third-party furniture shop. Built at runtime so this file can name the
# prohibition without a literal href= canonical stamp.
_FURNITURE_HOST = "a11oy" + ".com"
_FORBIDDEN_ATTR = re.compile(
    r"""
    (?:
        rel\s*=\s*["']canonical["'][^>]*href\s*=\s*["']https?://(?:www\.)?a11oy\.com
        | href\s*=\s*["']https?://(?:www\.)?a11oy\.com[^"']*["'][^>]*rel\s*=\s*["']canonical["']
        | property\s*=\s*["']og:url["'][^>]*content\s*=\s*["']https?://(?:www\.)?a11oy\.com
        | name\s*=\s*["']twitter:url["'][^>]*content\s*=\s*["']https?://(?:www\.)?a11oy\.com
        | ["']sameAs["']\s*:\s*\[?[^\]]*"https?://(?:www\.)?a11oy\.com
        | ["']url["']\s*:\s*["']https?://(?:www\.)?a11oy\.com
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_SKIP_PARTS = {
    ".git",
    "node_modules",
    "dist",
    "vendor",
    "__pycache__",
    ".venv",
    "live_snapshots",
}
_SCAN_SUFFIXES = {".html", ".htm", ".json", ".xml", ".xhtml"}
_HTML_DOCUMENT_PATHS = ("/", "/console", "/trust", "/assurance")


def _should_scan(path: Path) -> bool:
    if path.suffix.lower() not in _SCAN_SUFFIXES:
        return False
    return not any(part in _SKIP_PARTS for part in path.parts)


def test_no_file_emits_furniture_host_as_canonical_og_or_sameas():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not _should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _FORBIDDEN_ATTR.search(text):
            hits.append(path.relative_to(ROOT).as_posix())
    assert hits == [], (
        "these files stamp the third-party furniture host as canonical/og/sameAs: "
        + ", ".join(hits)
    )


def test_trust_center_canonical_is_the_product_origin():
    """Product HTML stays on a-11-oy.com even if HF runtime.domains is PENDING.

    PENDING is KALLPA/Stephen DNS, not an HTML rewrite to *.hf.space.
    """
    html = (ROOT / "web" / "trust.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://a-11-oy.com/trust"' in html
    assert _FURNITURE_HOST not in html
    assert 'property="og:url" content="https://a-11-oy.com/trust"' in html


def test_assurance_canonical_is_the_product_origin():
    html = (ROOT / "pages" / "assurance.html").read_text(encoding="utf-8")
    assert 'rel="canonical" href="https://a-11-oy.com/assurance"' in html
    assert _FURNITURE_HOST not in html
    assert 'property="og:url" content="https://a-11-oy.com/assurance"' in html


def test_product_html_canonicals_are_not_rewritten_to_the_hf_space():
    """HF PENDING custom-domain state is not papered over in HTML.

    Hugging Face injects Link rel=canonical to the Space URL at the proxy.
    Product pages must keep <link rel="canonical"> on https://a-11-oy.com.
    """
    pages = (
        ROOT / "web" / "trust.html",
        ROOT / "pages" / "assurance.html",
        ROOT / "a11oy_landing.html",
        ROOT / "pages" / "console.html",
    )
    href_re = re.compile(
        r'rel\s*=\s*["\']canonical["\'][^>]*href\s*=\s*["\']([^"\']+)["\']'
        r'|href\s*=\s*["\']([^"\']+)["\'][^>]*rel\s*=\s*["\']canonical["\']',
        re.IGNORECASE,
    )
    for path in pages:
        html = path.read_text(encoding="utf-8")
        match = href_re.search(html)
        assert match, f"{path.relative_to(ROOT)} missing rel=canonical"
        href = match.group(1) or match.group(2)
        assert href.startswith("https://a-11-oy.com"), (
            f"{path.name} canonical must stay on the public product origin, got {href}"
        )
        assert "hf.space" not in href
        assert "huggingface.co" not in href
        assert _FURNITURE_HOST not in href


def test_app_does_not_export_net_as_sunset():
    import a11oy_canonical_domain as cd

    assert not hasattr(cd, "SUNSET_DOMAIN")
    assert cd.REGISTRY_HOST == "a11oy.net"
    assert cd.CANONICAL_HOST == "a-11-oy.com"
    assert cd.FORBIDDEN_PUBLIC_HOST == _FURNITURE_HOST


def _methods(path: str) -> set[str]:
    import serve

    return {
        method
        for route in serve.app.router.routes
        if getattr(route, "path", None) == path
        for method in getattr(route, "methods", set()) or set()
    }


@pytest.mark.parametrize("path", _HTML_DOCUMENT_PATHS)
def test_html_document_routes_declare_head(path):
    assert {"GET", "HEAD"}.issubset(_methods(path)), (
        f"{path} must accept HEAD as well as GET (crawlers/monitors use HEAD)"
    )


@pytest.mark.parametrize("path", ("/console", "/trust", "/assurance"))
def test_html_document_head_agrees_with_get(path):
    """HEAD must not 405; body empty; status matches GET when GET is 200."""
    from starlette.testclient import TestClient

    import serve

    client = TestClient(serve.app, raise_server_exceptions=False)
    get_r = client.get(path)
    head_r = client.head(path)
    assert head_r.status_code != 405, f"{path} HEAD must not be Method Not Allowed"
    assert head_r.content in (b"", None) or len(head_r.content) == 0
    if get_r.status_code == 200:
        assert head_r.status_code == 200
        get_ct = (get_r.headers.get("content-type") or "").split(";")[0]
        head_ct = (head_r.headers.get("content-type") or "").split(";")[0]
        if get_ct:
            assert head_ct == get_ct


def test_trust_get_body_uses_product_canonical():
    from starlette.testclient import TestClient

    import serve

    response = TestClient(serve.app, raise_server_exceptions=False).get("/trust")
    assert response.status_code == 200
    body = response.content
    assert b"https://a-11-oy.com/trust" in body
    assert _FURNITURE_HOST.encode("ascii") not in body
