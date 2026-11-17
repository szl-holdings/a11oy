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

    def _drip(self, data: bytes) -> bool:
        for byte in data:
            try:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return False
            time.sleep(0.03)
        return True

    def _slow_response(self, status: int, phase: str) -> None:
        body = b'{"decision":"ABSTAIN"}' if status == 422 else b'{"slow":"response"}'
        try:
            if phase == "headers":
                self.wfile.write(f"HTTP/1.1 {status} Test\r\n".encode())
                if not self._drip(b"X-Slow: " + b"x" * 30 + b"\r\n"):
                    return
                self.wfile.write(
                    f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                )
                self.wfile.write(body)
                return
            self.send_response(status)
            if phase == "body":
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self._drip(body)
                return
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            if phase == "chunk-size":
                if not self._drip(f"{len(body):x};slow=".encode() + b"x" * 30 + b"\r\n"):
                    return
                self.wfile.write(body + b"\r\n0\r\n\r\n")
            elif phase == "chunk-trailer":
                self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n")
                if self._drip(b"X-Slow: " + b"x" * 30 + b"\r\n"):
                    self.wfile.write(b"\r\n")
            elif phase == "chunk-body":
                for byte in body:
                    self.wfile.write(b"1\r\n" + bytes([byte]) + b"\r\n")
                    self.wfile.flush()
                    time.sleep(0.03)
                self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path.startswith("/drip-"):
            status, phase = self.path[len("/drip-"):].split("-", 1)
            self._slow_response(int(status), phase)
        elif self.path == "/chunked-json":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.write(b'5\r\n{"rea\r\n8\r\nl":true}\r\n0\r\nX-End: yes\r\n\r\n')
        elif self.path == "/json":
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
        elif self.path in {"/accepted", "/partial"}:
            self._send(202 if self.path == "/accepted" else 206,
                       b'{"state":"PROPOSAL"}', Content_Type="application/json")
        elif self.path == "/governed-abstain":
            self._send(422, b'{"decision":"ABSTAIN"}', Content_Type="application/json")
        elif self.path == "/invalid-error":
            self._send(422, b"not-json")
        elif self.path == "/large-error":
            self._send(422, json.dumps({"reason": "x" * 512}).encode())
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

    def test_slow_drip_cannot_extend_total_response_deadline(self) -> None:
        for status in (200, 422):
            for phase in ("body", "headers", "chunk-size", "chunk-body", "chunk-trailer"):
                with self.subTest(status=status, phase=phase):
                    started = time.monotonic()
                    result = provider_http.http_json(
                        self.base + f"/drip-{status}-{phase}",
                        allow_private=True, timeout=0.2, error_body_statuses=(422,),
                    )
                    elapsed = time.monotonic() - started
                    self.assertEqual(result, (None, "TIMEOUT"))
                    # All payloads would need at least .54s without interruption.
                    # Scheduling allowance is deliberately below that completion time.
                    self.assertLess(elapsed, 0.40, f"{phase} exceeded absolute budget: {elapsed:.3f}s")

    def test_chunked_response_and_trailers_still_parse_within_budget(self) -> None:
        self.assertEqual(
            provider_http.http_json(self.base + "/chunked-json", allow_private=True),
            ({"real": True}, None),
        )

    def test_deadline_timers_are_cancelled_on_every_exit_path(self) -> None:
        guards = []
        real_guard = provider_http._SocketDeadline

        def record_guard(*args, **kwargs):
            guard = real_guard(*args, **kwargs)
            guards.append(guard)
            return guard

        with mock.patch.object(provider_http, "_SocketDeadline", side_effect=record_guard):
            for route in ("/json", "/redirect", "/large", "/invalid", "/missing",
                          "/governed-abstain", "/drip-200-headers", "/drip-422-body"):
                provider_http.http_json(
                    self.base + route, allow_private=True, timeout=0.2,
                    max_response_bytes=64, error_body_statuses=(422,),
                )
        self.assertGreater(len(guards), 8)  # redirect contributes its own hop
        for guard in guards:
            self.assertTrue(guard._cancelled.is_set())
            self.assertTrue(guard._timer.finished.is_set())
            guard._timer.join(timeout=0.1)
            self.assertFalse(guard._timer.is_alive())

    def test_tls_handshake_keeps_hostname_binding_and_deadline_cleanup(self) -> None:
        real_guard = provider_http._SocketDeadline
        for stalled in (False, True):
            with self.subTest(stalled=stalled):
                guards = []
                raw_socket = mock.Mock(spec=socket.socket)
                tls_socket = mock.Mock(spec=provider_http.ssl.SSLSocket)
                interrupted = threading.Event()
                tls_socket.shutdown.side_effect = lambda _how: interrupted.set()
                if stalled:
                    tls_socket.do_handshake.side_effect = lambda: interrupted.wait(2.0)
                context = mock.Mock(spec=provider_http.ssl.SSLContext)
                context.wrap_socket.return_value = tls_socket

                def record_guard(*args, **kwargs):
                    guard = real_guard(*args, **kwargs)
                    guards.append(guard)
                    return guard

                connection = provider_http._PinnedHTTPSConnection(
                    "provider.example", "93.184.216.34", 443, timeout=0.1,
                    context=context, deadline=time.monotonic() + 0.1,
                )
                started = time.monotonic()
                try:
                    with mock.patch.object(provider_http.socket, "create_connection",
                                           return_value=raw_socket), mock.patch.object(
                            provider_http, "_SocketDeadline", side_effect=record_guard):
                        if stalled:
                            with self.assertRaises(TimeoutError):
                                connection.connect()
                        else:
                            connection.connect()
                finally:
                    connection.close()
                self.assertLess(time.monotonic() - started, 0.4)
                context.wrap_socket.assert_called_once_with(
                    raw_socket, server_hostname="provider.example", do_handshake_on_connect=False,
                )
                self.assertEqual(len(guards), 1)
                self.assertTrue(guards[0]._cancelled.is_set())
                self.assertTrue(guards[0]._timer.finished.is_set())
                self.assertEqual(interrupted.is_set(), stalled)

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

    def test_governed_error_body_requires_explicit_allowlist_and_keeps_status(self):
        self.assertEqual(
            provider_http.http_json(self.base + "/governed-abstain", allow_private=True),
            (None, "HTTP_STATUS:422"),
        )
        self.assertEqual(
            provider_http.http_json(self.base + "/governed-abstain", allow_private=True,
                                    error_body_statuses=(409, 422, 503)),
            ({"decision": "ABSTAIN"}, "HTTP_STATUS:422"),
        )
        self.assertEqual(
            provider_http.http_json(self.base + "/missing", allow_private=True,
                                    error_body_statuses=(422,)),
            (None, "HTTP_STATUS:404"),
        )

    def test_error_documents_still_obey_json_and_size_boundaries(self):
        for route, expected in (("/invalid-error", "INVALID_JSON"),
                                ("/large-error", "RESPONSE_TOO_LARGE")):
            self.assertEqual(
                provider_http.http_json(self.base + route, allow_private=True,
                                        error_body_statuses=(422,), max_response_bytes=64),
                (None, expected),
            )

    def test_error_body_status_allowlist_is_strict(self):
        for statuses in (True, "422", (True,), (200,), (600,), tuple(range(400, 409))):
            self.assertEqual(
                provider_http.http_json(self.base + "/json", error_body_statuses=statuses),
                (None, "INVALID_ERROR_BODY_STATUSES"),
            )

    def test_post_is_never_replayed_to_second_address_after_lost_acknowledgement(self):
        target = provider_http._Target(
            url="http://provider.example/infer", scheme="http",
            hostname="provider.example", port=80, request_target="/infer",
            host_header="provider.example", origin=("http", "provider.example", 80),
            addresses=("93.184.216.34", "93.184.216.35"),
        )
        for method, attempts in (("POST", 1), ("GET", 2)):
            with self.subTest(method=method):
                connection = mock.Mock()
                connection.sock = None
                connection.getresponse.side_effect = TimeoutError("lost acknowledgement")
                with mock.patch.object(provider_http.http.client, "HTTPConnection",
                                       return_value=connection) as factory:
                    result = provider_http._request_once(
                        target, method=method, body=b"{}", headers={},
                        deadline=time.monotonic() + 5.0,
                    )
                self.assertEqual(result, (None, None, "TIMEOUT"))
                self.assertEqual(factory.call_count, attempts)
                self.assertEqual(connection.request.call_count, attempts)

    def test_exact_success_status_does_not_accept_pending_or_partial_response(self):
        for route, status in (("/accepted", 202), ("/partial", 206)):
            with self.subTest(status=status):
                self.assertEqual(
                    provider_http.http_json(self.base + route, allow_private=True,
                                            success_status=200),
                    (None, f"HTTP_STATUS:{status}"),
                )
                self.assertEqual(
                    provider_http.http_json(self.base + route, allow_private=True),
                    ({"state": "PROPOSAL"}, None),
                )
        self.assertEqual(
            provider_http.http_json(self.base + "/json", allow_private=True,
                                    success_status=200),
            ({"real": True}, None),
        )

    def test_invalid_success_status_is_rejected_before_egress(self):
        for status in (True, "200", 199, 300):
            self.assertEqual(
                provider_http.http_json(self.base + "/json", success_status=status),
                (None, "INVALID_SUCCESS_STATUS"),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
