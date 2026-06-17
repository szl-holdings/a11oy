"""test_prod_hardening — production HTTP hardening is wired, safe, and honest.

Asserts szl_prod_hardening.register(app, ns="a11oy") on a fresh FastAPI app:
  1. SECURITY HEADERS present on a normal response (OWASP set).
  2. RATE LIMIT returns 429 + Retry-After once the per-IP threshold is exceeded.
  3. REQUEST-ID present on every response and unique across requests.
  4. ERROR ENVELOPE {error,path,request_id,ts} on a forced exception, with NO
     stack trace / exception message leaked to the client (honest 500, not 200).
  5. LIVENESS (/healthz) is EXEMPT from the rate limit.

Pure stdlib + FastAPI TestClient — fully OFFLINE. Run:
    python3 test_prod_hardening.py     (or: pytest test_prod_hardening.py)
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Tiny rate-limit window keeps the test fast and deterministic.
os.environ["A11OY_RL_LIMIT"] = "5"
os.environ["A11OY_RL_WINDOW_S"] = "60"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import szl_prod_hardening as ph  # noqa: E402

NS = "a11oy"

# 2026-06-17 iframe fix: the legacy X-Frame-Options header is intentionally GONE
# (it could only say SAMEORIGIN/DENY and DENY refused the legitimate Hugging Face
# cross-origin embed → white screen + red 🚫). Framing is now governed by a CSP
# frame-ancestors allow-list (self + Hugging Face), asserted separately below.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": None,        # presence only
    "Strict-Transport-Security": None,      # presence only
}


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get(f"/api/{NS}/v1/ping")
    def ping():
        return {"ok": True, "doctrine": "v11"}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get(f"/api/{NS}/v1/boom")
    def boom():
        raise RuntimeError("SECRET_INTERNAL_DETAIL_should_not_leak")

    status = ph.register(app, ns=NS)
    assert any("middleware wired" in s for s in status), f"middleware not wired: {status}"
    assert any("error envelope wired" in s for s in status), f"envelope not wired: {status}"
    return app


def test_security_headers_present():
    # raise_server_exceptions=False so the boom route exercises the envelope, not pytest.
    client = TestClient(_build_app(), raise_server_exceptions=False)
    r = client.get(f"/api/{NS}/v1/ping")
    assert r.status_code == 200, r.status_code
    for name, expected in SECURITY_HEADERS.items():
        assert name in r.headers, f"missing security header: {name}"
        if expected is not None:
            assert r.headers[name] == expected, f"{name}={r.headers[name]!r} != {expected!r}"
    # JSON-API CSP keeps the strict deny-everything base.
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    # The legacy X-Frame-Options header must NOT be emitted (it blocked the HF
    # embed and cannot express an allow-list). Framing is governed by CSP only.
    assert "X-Frame-Options" not in r.headers, "legacy X-Frame-Options must be gone"
    # CSP frame-ancestors must allow-list self + Hugging Face (scoped embed),
    # NOT 'none' (which refused the HF iframe).
    assert "frame-ancestors" in csp, "CSP must declare a frame-ancestors policy"
    assert "frame-ancestors 'none'" not in csp, "frame-ancestors 'none' refuses the HF embed"
    assert "'self'" in csp, "frame-ancestors must keep 'self'"
    assert "https://huggingface.co" in csp, "frame-ancestors must allow Hugging Face"
    assert "https://*.hf.space" in csp, "frame-ancestors must allow *.hf.space"
    print("PASS security_headers_present")


def test_rate_limit_429_and_retry_after():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    # limit=5 -> first 5 allowed, 6th throttled. Distinct IP via header.
    hdr = {"x-forwarded-for": "203.0.113.7"}
    codes = [client.get(f"/api/{NS}/v1/ping", headers=hdr).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5, f"first 5 should pass: {codes}"
    assert codes[5] == 429, f"6th should be 429: {codes}"
    r = client.get(f"/api/{NS}/v1/ping", headers=hdr)
    assert r.status_code == 429
    assert "Retry-After" in r.headers, "429 must carry Retry-After"
    assert int(r.headers["Retry-After"]) >= 1
    body = r.json()
    assert body["error"] == "rate_limited"
    assert body["path"] == f"/api/{NS}/v1/ping"
    assert "request_id" in body and "ts" in body
    print("PASS rate_limit_429_and_retry_after")


def test_request_id_present_and_unique():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    r1 = client.get(f"/api/{NS}/v1/ping", headers={"x-forwarded-for": "198.51.100.1"})
    r2 = client.get(f"/api/{NS}/v1/ping", headers={"x-forwarded-for": "198.51.100.2"})
    assert "X-Request-ID" in r1.headers and r1.headers["X-Request-ID"]
    assert "X-Request-ID" in r2.headers and r2.headers["X-Request-ID"]
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"], "request ids must be unique"
    print("PASS request_id_present_and_unique")


def test_error_envelope_no_stack_leak():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    r = client.get(f"/api/{NS}/v1/boom", headers={"x-forwarded-for": "192.0.2.50"})
    # HONEST: a real 5xx, never a fake 200.
    assert r.status_code == 500, f"forced exception must be a true 5xx, got {r.status_code}"
    body = r.json()
    assert set(["error", "path", "request_id", "ts"]).issubset(body.keys()), body
    assert body["error"] == "internal_error"
    assert body["path"] == f"/api/{NS}/v1/boom"
    # No leak of the secret internal detail, exception type, or a traceback.
    blob = r.text
    assert "SECRET_INTERNAL_DETAIL_should_not_leak" not in blob, "exception message leaked!"
    assert "RuntimeError" not in blob, "exception type leaked!"
    assert "Traceback" not in blob and 'File "' not in blob, "stack trace leaked!"
    assert "X-Request-ID" in r.headers
    print("PASS error_envelope_no_stack_leak")


def test_liveness_exempt_from_rate_limit():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    hdr = {"x-forwarded-for": "203.0.113.99"}
    # Far exceed the limit (5) on the liveness probe; all must still pass.
    codes = [client.get("/healthz", headers=hdr).status_code for _ in range(25)]
    assert all(c == 200 for c in codes), f"liveness must be exempt: {codes}"
    print("PASS liveness_exempt_from_rate_limit")


def _build_page_app() -> FastAPI:
    app = FastAPI()

    @app.get("/frontier")
    def frontier():
        return {"page": "frontier"}

    @app.get("/governance")
    def governance():
        return {"page": "governance"}

    @app.get(f"/api/{NS}/v1/data")
    def data():
        return {"ok": True}

    status = ph.register(app, ns=NS)
    assert any("middleware wired" in s for s in status), f"middleware not wired: {status}"
    return app


def test_demo_pages_exempt_from_rate_limit():
    # DEMO-FLOOR FIX: human-facing HTML pages must NEVER be rate-limited so a booth
    # clicking rapidly through tabs on one IP never gets a raw rate_limited body.
    client = TestClient(_build_page_app(), raise_server_exceptions=False)
    hdr = {"x-forwarded-for": "203.0.113.55"}
    # Far exceed the limit (5) on demo page routes; all must still render 200.
    for path in ("/frontier", "/governance"):
        codes = [client.get(path, headers=hdr).status_code for _ in range(25)]
        assert all(c == 200 for c in codes), f"page {path} must be exempt: {codes}"
    # But the JSON DATA surface is STILL metered (abuse protection retained).
    api_codes = [client.get(f"/api/{NS}/v1/data", headers=hdr).status_code for _ in range(7)]
    assert api_codes[:5] == [200] * 5, f"first 5 api calls should pass: {api_codes}"
    assert 429 in api_codes, f"api data surface must still be capped: {api_codes}"
    print("PASS demo_pages_exempt_from_rate_limit")


def _run_all():
    fns = [
        test_security_headers_present,
        test_rate_limit_429_and_retry_after,
        test_request_id_present_and_unique,
        test_error_envelope_no_stack_leak,
        test_liveness_exempt_from_rate_limit,
        test_demo_pages_exempt_from_rate_limit,
    ]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # pragma: no cover
            failed += 1
            print(f"ERROR {fn.__name__}: {e!r}")
    if failed:
        print(f"\n{failed} test(s) FAILED")
        sys.exit(1)
    print("\nALL PROD-HARDENING TESTS PASSED")


if __name__ == "__main__":
    _run_all()
