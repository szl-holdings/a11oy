"""Security response-header regression guard (SAFE-NOW hardening, 2026-06-18).

a11oy stamps a conservative security-header posture onto every response:

  * the ENFORCED non-breaking baseline (X-Content-Type-Options: nosniff,
    Referrer-Policy, Strict-Transport-Security, and an enforced
    Content-Security-Policy whose `frame-ancestors` allow-list is the
    clickjacking control AND the reason the legitimate Hugging Face embed of the
    Space keeps working) comes from ``szl_be_hardening._apply_security_headers``;
  * the report-only resource CSP (default-src/script-src/style-src/...) is added
    by the app-level ``_SecurityHeadersMiddleware`` in ``serve.py``.

The middleware is purely additive (only adds a header via setdefault, never
rewrites bodies, never touches routing), so it must NOT change the status of any
demo surface.

This guard boots the REAL app in-process (Starlette TestClient, no mocks, no
network) and asserts:

  1. The enforced headers (nosniff, Referrer-Policy, HSTS) are present on both an
     HTML page and a JSON API response.
  2. The enforced CSP keeps its `frame-ancestors` allow-list that PERMITS the
     Hugging Face embed — so a future edit that flips it to a blanket DENY (which
     would white-screen the HF embed) trips this gate.
  3. The resource CSP is shipped REPORT-ONLY (Content-Security-Policy-Report-Only)
     — NOT as a second enforced policy — because the demo pages ship inline
     scripts/handlers/styles and an enforced resource CSP would blank the demo.
  4. The demo-critical pages still render (HTTP 200) WITH the headers attached.
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

pytest.importorskip("starlette.testclient")

from starlette.testclient import TestClient  # noqa: E402

import serve  # noqa: E402

ENFORCED_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
}

# Surfaces the hardening task explicitly must not break.
DEMO_PAGES = ["/console", "/determinacy", "/signature-is-not-proof"]
JSON_API = "/api/a11oy/v1/honest"


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


@pytest.mark.parametrize("name,value", ENFORCED_HEADERS.items())
def test_enforced_headers_on_html(client, name, value):
    """Every enforced security header is present (exact value) on an HTML page."""
    r = client.get("/console")
    assert r.status_code == 200
    assert r.headers.get(name) == value, f"{name} missing/wrong on /console"


@pytest.mark.parametrize("name,value", ENFORCED_HEADERS.items())
def test_enforced_headers_on_json(client, name, value):
    """Enforced security headers are present on a JSON API response too."""
    r = client.get(JSON_API)
    assert r.status_code == 200
    assert r.headers.get(name) == value, f"{name} missing/wrong on {JSON_API}"


def test_enforced_csp_preserves_hf_frame_ancestors(client):
    """The enforced CSP must keep the HF-embed frame-ancestors allow-list.

    The clickjacking control here is a `frame-ancestors` allow-list (self + HF),
    deliberately used instead of X-Frame-Options so the legitimate Hugging Face
    cross-origin embed of the Space still renders. A flip to a blanket DENY /
    'none' would white-screen the embed — guard against that regression.
    """
    r = client.get("/console")
    assert r.status_code == 200
    csp = r.headers.get("content-security-policy")
    assert csp is not None, "enforced CSP missing"
    assert "frame-ancestors" in csp
    assert "huggingface.co" in csp, "HF embed allow-list dropped from frame-ancestors"


def test_resource_csp_is_report_only(client):
    """The resource CSP must ship REPORT-ONLY so inline-script demo pages work.

    An enforced resource CSP (default-src/script-src/...) would block the demo's
    inline scripts and event handlers; SAFE-NOW doctrine is report-only CSP for
    the resource directives + the other headers enforced. Lock that in.
    """
    r = client.get("/console")
    assert r.status_code == 200
    ro = r.headers.get("content-security-policy-report-only")
    assert ro is not None, "expected a report-only resource CSP header"
    assert "default-src 'self'" in ro
    assert "script-src 'self' 'unsafe-inline'" in ro
    # The enforced CSP must remain frame-ancestors-only (no resource directives),
    # i.e. the resource policy is NOT enforced.
    enforced = r.headers.get("content-security-policy", "")
    assert "default-src" not in enforced, \
        "resource directives leaked into the ENFORCED CSP — would break inline scripts"


@pytest.mark.parametrize("path", DEMO_PAGES)
def test_demo_pages_still_render_with_headers(client, path):
    """Demo-critical pages still return 200 AND carry the headers (no breakage)."""
    r = client.get(path)
    assert r.status_code == 200, f"{path} regressed to {r.status_code}"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "content-security-policy-report-only" in r.headers
