"""CORS lockdown regression guard (SAFE-NOW hardening, 2026-06-18).

CORS used to be wide-open (``allow_origins=["*"]``), letting any website's browser
JS read every a11oy API response cross-origin. ``serve.py`` now restricts the
Access-Control-Allow-Origin allow-list to the known a11oy / killinchu / HF origins
(+ localhost and a regex for ``szlholdings-*.hf.space`` / ``*.a11oy.net``).

Crucially this must NOT break public read endpoints: CORS only governs
CROSS-ORIGIN *browser JS* reads, so same-origin loads, server-to-server calls and
curl (no ``Origin`` header) keep working. This guard boots the REAL app
in-process (Starlette TestClient, no mocks/network) and asserts both halves:

  1. allowed origins (explicit + regex) get their origin echoed back;
  2. an unknown origin gets NO Access-Control-Allow-Origin (browser blocks the
     cross-origin read) and its preflight is rejected;
  3. wildcard ``*`` is gone;
  4. a no-Origin request (curl / server-to-server / same-origin) still returns
     200 — public reads are unaffected.
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

pytest.importorskip("starlette.testclient")

from starlette.testclient import TestClient  # noqa: E402

import serve  # noqa: E402

API = "/api/a11oy/v1/honest"

ALLOWED_ORIGINS = [
    "https://a11oy.net",
    "https://killinchu.a11oy.net",
    "https://szlholdings-a11oy.hf.space",
    "https://szlholdings-killinchu.hf.space",
    "https://immune.a11oy.net",   # via the *.a11oy.net regex
]

DISALLOWED_ORIGINS = [
    "https://evil.example.com",
    "http://attacker.test",
    "https://a11oy.net.evil.com",   # suffix-spoof must NOT match the regex
]


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_allowed_origin_is_echoed(client, origin):
    r = client.get(API, headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin, \
        f"{origin} should be an allowed CORS origin"


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_allowed_origin_preflight_ok(client, origin):
    r = client.options(
        API,
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_disallowed_origin_not_echoed(client, origin):
    """Unknown origin gets NO ACAO header — the browser blocks the cross-origin read."""
    r = client.get(API, headers={"Origin": origin})
    # The endpoint itself still answers (public read for non-browser clients),
    # but the browser-enforced CORS header must be absent for unknown origins.
    assert r.headers.get("access-control-allow-origin") not in (origin, "*"), \
        f"{origin} must NOT be granted cross-origin read access"


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_disallowed_origin_preflight_rejected(client, origin):
    r = client.options(
        API,
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") != origin


def test_no_wildcard_origin(client):
    """The wildcard '*' must be gone for any concrete request."""
    r = client.get(API, headers={"Origin": "https://szlholdings-a11oy.hf.space"})
    assert r.headers.get("access-control-allow-origin") != "*"


def test_public_read_without_origin_still_works(client):
    """A no-Origin request (curl / server-to-server) is unaffected by the lockdown."""
    r = client.get(API)
    assert r.status_code == 200
    # No Origin => no CORS header at all; the body is still served.
    assert r.headers.get("access-control-allow-origin") is None
    assert r.json()  # real payload, not blocked
