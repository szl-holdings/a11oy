"""Focused regression suite for the provider HTTP security boundary."""

from __future__ import annotations

import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import szl_provider_http as provider_http


class _Handler(BaseHTTPRequestHandler):
    # One request per test connection keeps intentional client-side timeout and
    # redirect closes from surfacing as noisy keep-alive reset tracebacks.
    protocol_version = "HTTP/1.0"
    cross_origin_location = ""
    captured_authorization: str | None = None

    def log_message(self, _format: str, *_args: object) -> None:
        pass

    def _send(self, status: int, body: bytes = b"", **headers: str) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path == "/json":
            self._send(200, json.dumps({"real": True}).encode(), Content_Type="application/json")
        elif self.path == "/redirect":
            self._send(302, Location="/json")
        elif self.path == "/redirect-loop":
            self._send(302, Location="/redirect-loop")
        elif self.path == "/redirect-credentials":
            host, port = self.server.server_address
            self._send(302, Location=f"http://user:secret@{host}:{port}/json")
        elif self.path == "/redirect-metadata":
            self._send(302, Location="http://169.254.169.254/latest/meta-data/")
        elif self.path == "/redirect-cross-origin":
            self._send(302, Location=self.cross_origin_location)
        elif self.path == "/capture":
            type(self).captured_authorization = self.headers.get("Authorization")
            self._send(200, b'{"captured":true}', Content_Type="application/json")
        elif self.path == "/large":
            self._send(200, json.dumps({"value": "x" * 512}).encode())
        elif self.path == "/large-without-length":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"value": "x" * 512}).encode())
        elif self.path == "/slow":
            time.sleep(0.25)
            self._send(200, b'{"late":true}')
        elif self.path == "/invalid":
            self._send(200, b"not-json")
        elif self.path == "/missing":
            self._send(404, b'{"error":"missing"}')
        else:
            self._send(404)


class ProviderHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

        cls.capture_server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.capture_thread = threading.Thread(
            target=cls.capture_server.serve_forever,
            daemon=True,
        )
        cls.capture_thread.start()
        _Handler.cross_origin_location = (
            f"http://127.0.0.1:{cls.capture_server.server_port}/capture"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.capture_server.shutdown()
        cls.capture_server.server_close()

    def test_only_http_and_https_are_accepted(self) -> None:
        for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://example.com"):
            self.assertEqual(provider_http.http_json(url), (None, "INVALID_URL_SCHEME"))

    def test_credentials_and_fragments_are_rejected_without_echoing_secrets(self) -> None:
        secret = "do-not-echo-this"
        for url, expected in (
            (f"http://user:{secret}@example.com/x", "URL_CREDENTIALS_FORBIDDEN"),
            (f"http://example.com/x#{secret}", "URL_FRAGMENT_FORBIDDEN"),
        ):
            doc, error = provider_http.http_json(url)
            self.assertIsNone(doc)
            self.assertEqual(error, expected)
            self.assertNotIn(secret, error or "")

    def test_loopback_requires_explicit_operator_opt_in(self) -> None:
        self.assertEqual(
            provider_http.http_json(self.base + "/json"),
            (None, "PRIVATE_DESTINATION_REQUIRES_OPT_IN"),
        )
        self.assertEqual(
            provider_http.http_json(self.base + "/json", allow_private=True),
            ({"real": True}, None),
        )
        self.assertEqual(
            provider_http.http_json(self.base + "/json", allow_private="yes"),  # type: ignore[arg-type]
            (None, "INVALID_PRIVATE_OPT_IN"),
        )

    def test_all_dns_answers_are_validated(self) -> None:
        mixed = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
        ]
        with mock.patch.object(provider_http.socket, "getaddrinfo", return_value=mixed):
            self.assertEqual(
                provider_http.http_json("http://mixed.example/json"),
                (None, "PRIVATE_DESTINATION_REQUIRES_OPT_IN"),
            )

    def test_link_local_metadata_is_always_forbidden(self) -> None:
        self.assertEqual(
            provider_http.http_json(
                "http://169.254.169.254/latest/meta-data/",
                allow_private=True,
            ),
            (None, "DESTINATION_FORBIDDEN"),
        )

    def test_each_redirect_target_is_revalidated(self) -> None:
        doc, error = provider_http.http_json(
            self.base + "/redirect-metadata",
            allow_private=True,
        )
        self.assertIsNone(doc)
        self.assertEqual(error, "DESTINATION_FORBIDDEN")

    def test_relative_redirect_succeeds_and_redirect_count_is_bounded(self) -> None:
        self.assertEqual(
            provider_http.http_json(self.base + "/redirect", allow_private=True),
            ({"real": True}, None),
        )
        self.assertEqual(
            provider_http.http_json(
                self.base + "/redirect-loop",
                allow_private=True,
                max_redirects=1,
            ),
            (None, "REDIRECT_LIMIT_EXCEEDED"),
        )

    def test_credentials_in_redirect_are_rejected(self) -> None:
        self.assertEqual(
            provider_http.http_json(
                self.base + "/redirect-credentials",
                allow_private=True,
            ),
            (None, "URL_CREDENTIALS_FORBIDDEN"),
        )

    def test_sensitive_header_is_removed_on_cross_origin_redirect(self) -> None:
        _Handler.captured_authorization = "not-called"
        doc, error = provider_http.http_json(
            self.base + "/redirect-cross-origin",
            headers={"Authorization": "Bearer top-secret"},
            allow_private=True,
        )
        self.assertEqual((doc, error), ({"captured": True}, None))
        self.assertIsNone(_Handler.captured_authorization)

    def test_response_size_and_timeout_are_bounded(self) -> None:
        for route in ("/large", "/large-without-length"):
            self.assertEqual(
                provider_http.http_json(
                    self.base + route,
                    allow_private=True,
                    max_response_bytes=64,
                ),
                (None, "RESPONSE_TOO_LARGE"),
            )
        self.assertEqual(
            provider_http.http_json(
                self.base + "/slow",
                allow_private=True,
                timeout=0.05,
            ),
            (None, "TIMEOUT"),
        )
        self.assertEqual(
            provider_http.http_json(self.base + "/json", timeout=121),
            (None, "INVALID_TIMEOUT"),
        )

    def test_dns_resolution_obeys_the_total_timeout(self) -> None:
        def _stalled_resolution(*_args: object, **_kwargs: object) -> list[object]:
            time.sleep(0.25)
            return []

        started = time.monotonic()
        with mock.patch.object(
            provider_http.socket,
            "getaddrinfo",
            side_effect=_stalled_resolution,
        ):
            result = provider_http.http_json("http://resolver.example/", timeout=0.05)
        self.assertEqual(result, (None, "TIMEOUT"))
        self.assertLess(time.monotonic() - started, 0.20)

    def test_invalid_json_and_non_2xx_never_fabricate(self) -> None:
        self.assertEqual(
            provider_http.http_json(self.base + "/invalid", allow_private=True),
            (None, "INVALID_JSON"),
        )
        self.assertEqual(
            provider_http.http_json(self.base + "/missing", allow_private=True),
            (None, "HTTP_STATUS:404"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
