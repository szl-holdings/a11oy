"""Access credential scoping and redirect containment for the meter2 reader."""

import threading
import json
import secrets
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import szl_meter_access


_ID = "test-meter-client-id"
_SECRET = "test-meter-client-secret"


def _set_test_credentials(monkeypatch):
    monkeypatch.setenv("A11OY_METER2_CF_ACCESS_CLIENT_ID", _ID)
    monkeypatch.setenv("A11OY_METER2_CF_ACCESS_CLIENT_SECRET", _SECRET)
    _set_test_hmac(monkeypatch, "https://meter2.a-11-oy.com")


def _set_test_hmac(monkeypatch, origin):
    monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({
        origin: {"client_id": "test-reader", "key_hex": secrets.token_hex(32)}}))


def test_headers_require_pair_and_exact_https_host(monkeypatch):
    monkeypatch.setenv("A11OY_METER2_CF_ACCESS_CLIENT_ID", _ID)
    monkeypatch.delenv("A11OY_METER2_CF_ACCESS_CLIENT_SECRET", raising=False)
    assert szl_meter_access.meter_access_headers("https://meter2.a-11-oy.com/metrics") == {}
    _set_test_credentials(monkeypatch)
    assert szl_meter_access.meter_access_headers("https://meter2.a-11-oy.com/metrics") == {
        "CF-Access-Client-Id": _ID,
        "CF-Access-Client-Secret": _SECRET,
    }
    for url in (
        "http://meter2.a-11-oy.com/metrics",
        "https://meter.a-11-oy.com/metrics",
        "https://meter2.a-11-oy.com.evil.test/metrics",
        "https://meter2.a-11-oy.com@evil.test/metrics",
        "https://meter2.a-11-oy.com./metrics",
        "https://meter2.a-11-oy.com:444/metrics",
        "https://user@meter2.a-11-oy.com/metrics",
    ):
        assert szl_meter_access.meter_access_headers(url) == {}, url


def test_unconfigured_get_denies_before_network_and_never_adds_access_headers(monkeypatch):
    _set_test_credentials(monkeypatch)
    captured = []

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: captured.append(args))
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: pytest.fail(
        "unconfigured meter must not use transport"))
    with pytest.raises(szl_meter_access.MeterAuthConfigurationError):
        szl_meter_access.open_meter_get("https://gpu2.a-11-oy.com/api/tags", timeout=1,
                                       headers={"User-Agent": "test",
                                                "CF-Access-Client-Secret": "accidental"})
    assert captured == []


def test_authenticated_get_never_follows_redirect_or_leaks_headers(monkeypatch):
    _set_test_credentials(monkeypatch)
    redirected = []

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            redirected.append(dict(self.headers))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Target) as target:
        target_thread = threading.Thread(target=target.serve_forever, daemon=True)
        target_thread.start()
        destination = f"http://127.0.0.1:{target.server_port}/capture"

        class Origin(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", destination)
                self.end_headers()

            def log_message(self, *_args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Origin) as origin:
            origin_thread = threading.Thread(target=origin.serve_forever, daemon=True)
            origin_thread.start()
            source = f"http://127.0.0.1:{origin.server_port}/metrics"
            _set_test_hmac(monkeypatch, f"http://127.0.0.1:{origin.server_port}")
            # The production host matcher is tested separately. Override it only so a
            # local HTTP server can exercise urllib's real redirect behavior.
            monkeypatch.setattr(szl_meter_access, "meter_access_headers",
                                lambda url: {"CF-Access-Client-Id": _ID,
                                             "CF-Access-Client-Secret": _SECRET}
                                if url == source else {})
            with pytest.raises(urllib.error.HTTPError) as exc:
                szl_meter_access.open_meter_get(source, timeout=2)
            assert exc.value.code == 302
            assert _SECRET not in str(exc.value)
            origin.shutdown()
            origin_thread.join(timeout=2)
        target.shutdown()
        target_thread.join(timeout=2)
    assert redirected == []


def test_live_httpx_meter_rejects_redirect_with_auth(monkeypatch):
    import httpx
    import szl_energy_live

    _set_test_credentials(monkeypatch)
    monkeypatch.setattr(szl_energy_live, "METER_URL", "https://meter2.a-11-oy.com")
    observed = {}

    class Client:
        def __init__(self, *, timeout, follow_redirects):
            observed["follow_redirects"] = follow_redirects

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, *, headers):
            observed["url"] = url
            observed["headers"] = headers
            return type("Response", (), {"status_code": 302, "text": "redirect"})()

    monkeypatch.setattr(httpx, "Client", Client)
    result = szl_energy_live._fetch_meter()
    assert result == {"reachable": False, "status": "http-302"}
    assert observed["url"] == "https://meter2.a-11-oy.com/metrics"
    assert observed["follow_redirects"] is False
    assert observed["headers"]["CF-Access-Client-Id"] == _ID
    assert observed["headers"]["CF-Access-Client-Secret"] == _SECRET
