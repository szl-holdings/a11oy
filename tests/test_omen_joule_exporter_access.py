"""Telemetry reads require a client MAC even behind a loopback reverse proxy."""

from concurrent.futures import ThreadPoolExecutor
from email.message import Message
import importlib.util
import io
import json
import secrets
import threading
from types import SimpleNamespace
import urllib.error
import urllib.request
from pathlib import Path
import unittest
from unittest import mock
import szl_meter_access as auth


_MODULE_PATH = Path(__file__).resolve().parents[1] / "box-scripts" / "omen_joule_exporter.py"
_SPEC = importlib.util.spec_from_file_location("omen_joule_exporter_access_test", _MODULE_PATH)
_EXPORTER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EXPORTER)


class _Request(_EXPORTER.Handler):
    def __init__(self, address, *, verifier=None, headers=None, path="/metrics"):
        self.client_address = (address, 12345)
        self.server = SimpleNamespace(meter_verifier=verifier)
        self.path = path
        self.headers = Message()
        self.headers["Host"] = "meter2.a-11-oy.com"
        for name, value in (headers or {}).items():
            self.headers[name] = value
        self.code = None
        self.response_headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, code):
        self.code = code

    def send_error(self, code, *args):
        self.code = code

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


class RequestSourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.origin = "https://meter2.a-11-oy.com"
        self.key = secrets.token_hex(32)
        self.env = mock.patch.dict(auth.os.environ, {
            "SZL_METER_HMAC_TARGETS": json.dumps({self.origin: {
                "client_id": "reader", "key_hex": self.key}})})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.verifier = auth.MeterRequestVerifier(self.origin, json.dumps({"reader": self.key}))

    def request(self, address="127.0.0.1", *, authenticated=True, path="/metrics"):
        headers = auth.meter_request_headers(self.origin + path) if authenticated else {}
        return _Request(address, verifier=self.verifier, headers=headers, path=path)

    def deny_before_read(self, request):
        with mock.patch.object(_EXPORTER, "_meter_json", side_effect=AssertionError("private telemetry")):
            request.do_GET()
        self.assertEqual(request.code, 403)
        self.assertEqual(request.wfile.getvalue(), b"")

    def test_allowed_sources_require_valid_auth_to_keep_the_meter_usable(self):
        for address in ("127.0.0.1", "::1", "100.64.0.1", "100.127.255.254", "fd7a:115c:a1e0::1"):
            with self.subTest(address=address):
                request = self.request(address)
                with mock.patch.object(_EXPORTER, "_meter_json", return_value={"joules": 1}):
                    request.do_GET()
                self.assertEqual(request.code, 200)
                self.assertEqual(json.loads(request.wfile.getvalue()), {"joules": 1})
                self.assertNotIn("Access-Control-Allow-Origin", request.response_headers)

    def test_loopback_and_tailnet_are_not_an_authentication_bypass(self):
        for address in ("127.0.0.1", "::1", "100.64.0.1", "fd7a:115c:a1e0::1"):
            with self.subTest(address=address):
                self.deny_before_read(self.request(address, authenticated=False))

    def test_other_sources_are_rejected_before_telemetry_read(self):
        for address in ("192.168.1.163", "8.8.8.8", "100.128.0.1", "fe80::1", "invalid"):
            with self.subTest(address=address):
                self.deny_before_read(self.request(address))

    def test_forwarded_proxy_headers_do_not_authorize_a_loopback_read(self):
        request = self.request(authenticated=False)
        for name, value in (("X-Forwarded-For", "100.64.0.1"), ("CF-Connecting-IP", "100.64.0.1"),
                            ("Forwarded", "for=100.64.0.1"), ("CF-Access-Client-Id", "reader")):
            request.headers[name] = value
        self.deny_before_read(request)

    def test_duplicate_auth_and_security_headers_deny(self):
        for name in ("Host", "X-SZL-Meter-Signature", "Content-Length", "Origin"):
            with self.subTest(name=name):
                request = self.request()
                if name not in request.headers:
                    request.headers[name] = "0"
                request.headers[name] = "0"
                self.deny_before_read(request)

    def test_body_framing_and_oversized_headers_deny(self):
        for name, value in (("Content-Length", "1"), ("Transfer-Encoding", "chunked"),
                            ("Expect", "100-continue"), ("Huge", "x" * 8193)):
            with self.subTest(name=name):
                request = self.request()
                request.headers[name] = value
                self.deny_before_read(request)

    def test_query_or_unknown_path_is_not_a_telemetry_alias(self):
        for path in ("/metrics?scope=all", "/metrics/", "//metrics"):
            with self.subTest(path=path):
                request = self.request()
                request.path = path
                self.deny_before_read(request)

    def test_missing_verifier_denies_before_read(self):
        request = self.request()
        request.server.meter_verifier = None
        self.deny_before_read(request)

    def test_concurrent_replay_allows_exactly_one_telemetry_read(self):
        headers = auth.meter_request_headers(self.origin + "/metrics")
        def once(_):
            request = _Request("127.0.0.1", verifier=self.verifier, headers=headers)
            request.do_GET()
            return request.code
        reads = mock.Mock(return_value={"joules": 1})
        with mock.patch.object(_EXPORTER, "_meter_json", reads), ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(once, range(24)))
        self.assertEqual(codes.count(200), 1)
        self.assertEqual(codes.count(403), 23)
        self.assertEqual(reads.call_count, 1)

    def test_unconfigured_start_does_not_start_sampler_listener_or_gpu_reads(self):
        with mock.patch.dict(auth.os.environ, {"SZL_METER_HMAC_AUDIENCE": "", "SZL_METER_HMAC_CLIENT_KEYS": ""}), \
             mock.patch.object(_EXPORTER, "_read_gpu_power", side_effect=AssertionError("GPU read")), \
             mock.patch.object(_EXPORTER.threading, "Thread", side_effect=AssertionError("sampler")), \
             mock.patch.object(_EXPORTER, "ThreadingHTTPServer", side_effect=AssertionError("listener")):
            self.assertEqual(_EXPORTER.main(), 1)

    def test_default_bind_is_loopback_and_wildcard_cannot_start(self):
        self.assertEqual(_EXPORTER.BIND, "127.0.0.1")
        with mock.patch.dict(auth.os.environ, {"SZL_METER_HMAC_AUDIENCE": self.origin,
                                             "SZL_METER_HMAC_CLIENT_KEYS": json.dumps({"reader": self.key})}), \
             mock.patch.object(_EXPORTER, "BIND", "0.0.0.0"), \
             mock.patch.object(_EXPORTER, "_read_gpu_power", side_effect=AssertionError("GPU read")):
            self.assertEqual(_EXPORTER.main(), 1)

    def test_peer_without_keys_is_omitted_before_egress(self):
        with mock.patch.object(_EXPORTER, "PEER_EXPORTERS", ["https://peer.test/metrics"]), \
             mock.patch.dict(auth.os.environ, {"SZL_METER_HMAC_TARGETS": ""}), \
             mock.patch.object(auth.urllib.request, "build_opener", side_effect=AssertionError("unauthenticated egress")):
            self.assertEqual(_EXPORTER._fetch_peer_engines(), ([], False))

    def test_native_client_and_actual_http_parser_enforce_auth_on_loopback(self):
        # A disposable loopback listener and synthetic payload, never the installed
        # service, sampler, hardware, tunnel or production authentication keys.
        with _EXPORTER.ThreadingHTTPServer(("127.0.0.1", 0), _EXPORTER.Handler) as server:
            origin = f"http://127.0.0.1:{server.server_port}"
            server.meter_verifier = auth.MeterRequestVerifier(origin, json.dumps({"reader": self.key}))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with mock.patch.dict(auth.os.environ, {"SZL_METER_HMAC_TARGETS": json.dumps({origin: {
                        "client_id": "reader", "key_hex": self.key}})}), \
                     mock.patch.object(_EXPORTER, "_meter_json", return_value={"engines": [], "test": "synthetic"}) as reads:
                    with self.assertRaises(urllib.error.HTTPError) as denied:
                        urllib.request.urlopen(origin + "/metrics", timeout=2)
                    self.assertEqual(denied.exception.code, 403)
                    self.assertEqual(reads.call_count, 0)
                    with auth.open_meter_get(origin + "/metrics", timeout=2) as response:
                        self.assertEqual(json.loads(response.read())["test"], "synthetic")
                    self.assertEqual(reads.call_count, 1)
            finally:
                server.shutdown()
                worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
