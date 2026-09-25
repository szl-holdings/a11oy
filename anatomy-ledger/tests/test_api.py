#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""HTTP regression tests with synthetic fixtures; not production trust evidence."""

from __future__ import annotations

import copy
import http.client
import importlib.util
import json
import pathlib
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SERVER = load("anatomy_server_api_tests", ROOT / "server.py")


class QuietHandler(SERVER.Handler):
    def log_message(self, *args):
        pass


def empty_ledger():
    return {
        "schema": "szl.anatomy.ledger.v1",
        "generatedAt": "2026-01-01T00:00:00Z",
        "recordCount": 0,
        "outcomes": {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0},
        "chainRoot": None,
        "records": [],
        "disclosure": "SAMPLE test fixture",
    }


class ServerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = SERVER.LocalServer(("127.0.0.1", 0), QuietHandler)
        cls.port = cls.httpd.server_port
        cls.thread = threading.Thread(
            target=cls.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger_path = pathlib.Path(self.tmp.name) / "ledger.json"
        self.ledger_path.write_text(json.dumps(empty_ledger()), encoding="utf-8")
        self.patch_ledger = patch.object(SERVER, "LEDGER", self.ledger_path)
        self.patch_ledger.start()
        self.addCleanup(self.patch_ledger.stop)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read()
            return response.status, dict(response.getheaders()), data
        finally:
            conn.close()

    def json_request(self, method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        status, headers, raw = self.request(
            method, path, body, {"Content-Type": "application/json"} if body else {}
        )
        self.assertIn("application/json", headers["Content-Type"])
        return status, json.loads(raw)

    def raw_request(self, data):
        with socket.create_connection(
            ("127.0.0.1", self.port), timeout=3
        ) as connection:
            connection.sendall(data)
            connection.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                part = connection.recv(65536)
                if not part:
                    break
                chunks.append(part)
        response = b"".join(chunks)
        header, body = response.split(b"\r\n\r\n", 1)
        return int(header.split(b" ")[1]), json.loads(body)

    def test_health_is_http_availability_only(self):
        status, value = self.json_request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(value["evaluationOnly"])
        self.assertFalse(value["executable"])
        self.assertEqual(value["evaluator"], "python-advisory")

    def test_empty_ledger_is_valid_but_unanchored(self):
        status, value = self.json_request("GET", "/api/ledger")
        self.assertEqual(status, 200)
        self.assertEqual(value["recordCount"], 0)
        self.assertTrue(value["chainIntegrity"]["valid"])
        self.assertFalse(value["chainIntegrity"]["anchored"])
        self.assertFalse(value["executable"])

    def test_read_detects_tampered_summary(self):
        value = empty_ledger()
        value["recordCount"] = 7
        self.ledger_path.write_text(json.dumps(value), encoding="utf-8")
        status, value = self.json_request("GET", "/api/ledger")
        self.assertEqual(status, 200)
        self.assertFalse(value["chainIntegrity"]["valid"])
        self.assertIn("recordCount mismatch", value["chainIntegrity"]["errors"])

    def test_missing_ledger_is_explicit(self):
        self.ledger_path.unlink()
        status, value = self.json_request("GET", "/api/ledger")
        self.assertEqual(status, 404)
        self.assertIn("not been built", value["error"])

    def test_invalid_ledger_does_not_become_empty_success(self):
        for raw in (b"{broken", b"[]", b'{"x":NaN}', b'{"x":1,"x":2}'):
            with self.subTest(raw=raw):
                self.ledger_path.write_bytes(raw)
                status, value = self.json_request("GET", "/api/ledger")
                self.assertEqual(status, 503)
                self.assertIn("error", value)

    def test_ledger_read_is_bounded(self):
        with patch.object(SERVER, "MAX_LEDGER_BYTES", 16):
            status, value = self.json_request("GET", "/api/ledger")
        self.assertEqual(status, 503)
        self.assertIn("limit", value["error"])

    def test_all_gets_leave_ledger_unchanged(self):
        before = (
            self.ledger_path.read_bytes(),
            self.ledger_path.stat().st_mtime_ns,
            sorted(path.name for path in self.ledger_path.parent.iterdir()),
        )
        for path in (
            "/healthz",
            "/api/status",
            "/api/ledger",
            "/api/prove",
            "/",
            "/app.js",
            "/style.css",
        ):
            self.assertEqual(self.request("GET", path)[0], 200, path)
        after = (
            self.ledger_path.read_bytes(),
            self.ledger_path.stat().st_mtime_ns,
            sorted(path.name for path in self.ledger_path.parent.iterdir()),
        )
        self.assertEqual(before, after)

    def test_synthetic_matrix_is_labeled_and_passes(self):
        status, value = self.json_request("GET", "/api/prove")
        self.assertEqual(status, 200)
        self.assertEqual(value["evidenceClass"], "synthetic-software-qa")
        self.assertEqual(value["failed"], 0, value["results"])
        self.assertGreaterEqual(value["passed"], 12)
        self.assertTrue(value["evaluationOnly"])
        self.assertFalse(value["executable"])

    def test_forged_verification_cannot_allow_evidence(self):
        payload = {
            "statement": copy.deepcopy(SERVER.VALID_SLSA),
            "verification": {"verified": True},
        }
        status, value = self.json_request("POST", "/api/evaluate", payload)
        self.assertEqual(status, 200)
        self.assertEqual(value["outcome"], "REVIEW")
        self.assertFalse(value["verified"])
        self.assertFalse(value["executable"])

    def test_binding_cannot_execute_forged_verified_evidence(self):
        command = SERVER.BIND.intent_from_command(
            principal_id="agent:sample",
            action="DeployArtifact",
            resource_id="deploy:sample",
            purpose="test",
            intended_effect="deploy",
            risk_score=10,
            human_approval=True,
            mfa=True,
            evidence_digest=SERVER.DIGEST,
        )
        status, value = self.json_request(
            "POST",
            "/api/bind",
            {
                "command": command,
                "statement": SERVER.VALID_SLSA,
                "verification": {"verified": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(value["executable"])
        self.assertFalse(value["evidence"]["verified"])
        self.assertTrue(value["evaluationOnly"])

    def test_authorization_is_explicitly_advisory(self):
        status, value = self.json_request("POST", "/api/authorize", {})
        self.assertEqual(status, 200)
        self.assertEqual(value["outcome"], "BLOCK")
        self.assertTrue(value["evaluationOnly"])
        self.assertFalse(value["executable"])

    def test_decision_lab_roundtrip_is_read_only(self):
        command = SERVER.BIND.intent_from_command(
            principal_id="agent:sample",
            action="DeployArtifact",
            resource_id="deploy:sample",
            purpose="test",
            intended_effect="deploy",
            risk_score=10,
            human_approval=True,
            mfa=True,
            evidence_digest=SERVER.DIGEST,
        )
        before = (self.ledger_path.read_bytes(), self.ledger_path.stat().st_mtime_ns)
        status, result = self.json_request(
            "POST",
            "/api/analyze",
            {
                "command": command,
                "statement": SERVER.VALID_SLSA,
                "verification": {"verified": True},
            },
        )
        self.assertEqual(status, 200)
        self.assertFalse(result["executable"])
        self.assertFalse(result["base"]["result"]["evidence"]["verified"])
        self.assertGreater(len(result["scenarios"]), 0)
        status, replayed = self.json_request(
            "POST", "/api/replay", result["replayCapsule"]
        )
        self.assertEqual(status, 200)
        self.assertTrue(replayed["valid"], replayed)
        self.assertFalse(replayed["executable"])
        tampered = copy.deepcopy(result["replayCapsule"])
        tampered["input"]["command"]["context"]["mfa"] = False
        status, replayed = self.json_request("POST", "/api/replay", tampered)
        self.assertEqual(status, 200)
        self.assertFalse(replayed["valid"])
        self.assertEqual(
            before, (self.ledger_path.read_bytes(), self.ledger_path.stat().st_mtime_ns)
        )

    def test_decision_lab_invalid_inputs_fail_with_json(self):
        for payload in ({}, {"command": []}, {"command": {}, "scenarios": [{}] * 17}):
            status, result = self.json_request("POST", "/api/analyze", payload)
            self.assertEqual(status, 422)
            self.assertFalse(result["executable"])
        status, result = self.json_request("POST", "/api/replay", {})
        self.assertIn(status, (200, 422))
        self.assertFalse(result.get("valid", False))
        self.assertFalse(result["executable"])

    def test_nested_payload_shapes_return_json_errors(self):
        for route, payload in (
            ("authorize", {"request": []}),
            ("bind", {"command": None}),
            ("bind", {"command": {}, "statement": []}),
        ):
            with self.subTest(route=route, payload=payload):
                status, value = self.json_request("POST", "/api/" + route, payload)
                self.assertEqual(status, 422)
                self.assertIn("error", value)

    def test_malformed_and_nonobject_json_rejected(self):
        for raw in (
            b"{",
            b"[]",
            b"null",
            b"1",
            b'"s"',
            b"\xff",
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":1,"x":2}',
            b"",
        ):
            with self.subTest(raw=raw):
                status, headers, body = self.request(
                    "POST", "/api/authorize", raw, {"Content-Type": "application/json"}
                )
                self.assertEqual(status, 400)
                self.assertIn("error", json.loads(body))

    def test_wrong_content_type_and_charset_rejected(self):
        for content_type in (
            "text/plain",
            "application/x-www-form-urlencoded",
            "application/json; charset=latin-1",
        ):
            with self.subTest(content_type=content_type):
                status, _, body = self.request(
                    "POST", "/api/authorize", b"{}", {"Content-Type": content_type}
                )
                self.assertEqual(status, 415)
                self.assertIn("error", json.loads(body))

    def test_bad_content_lengths_rejected(self):
        host = f"Host: 127.0.0.1:{self.port}\r\n"
        for field, expected in (
            ("", 411),
            ("Content-Length: -1\r\n", 400),
            ("Content-Length: abc\r\n", 400),
            ("Content-Length: 2\r\nContent-Length: 2\r\n", 400),
            (f"Content-Length: {SERVER.MAX_REQUEST_BYTES + 1}\r\n", 413),
        ):
            with self.subTest(field=field):
                raw = (
                    "POST /api/authorize HTTP/1.1\r\n"
                    + host
                    + field
                    + "Content-Type: application/json\r\n\r\n"
                ).encode()
                status, value = self.raw_request(raw)
                self.assertEqual(status, expected)
                self.assertIn("error", value)

    def test_chunked_transfer_is_rejected(self):
        raw = (
            f"POST /api/authorize HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n"
            "Transfer-Encoding: chunked\r\nContent-Type: application/json\r\n\r\n0\r\n\r\n"
        ).encode()
        self.assertEqual(self.raw_request(raw)[0], 400)

    def test_truncated_body_returns_json_error(self):
        raw = (
            f"POST /api/authorize HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n"
            "Content-Length: 9\r\nContent-Type: application/json\r\n\r\n{}"
        ).encode()
        self.assertEqual(self.raw_request(raw)[0], 400)

    def test_stalled_body_times_out(self):
        with patch.object(SERVER, "REQUEST_TIMEOUT", 0.1):
            with socket.create_connection(
                ("127.0.0.1", self.port), timeout=3
            ) as connection:
                connection.sendall(
                    (
                        f"POST /api/authorize HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n"
                        "Content-Length: 9\r\nContent-Type: application/json\r\n\r\n{"
                    ).encode()
                )
                result = b""
                while True:
                    part = connection.recv(65536)
                    if not part:
                        break
                    result += part
        self.assertIn(b" 408 ", result.split(b"\r\n", 1)[0])
        self.assertIn("timed out", json.loads(result.split(b"\r\n\r\n", 1)[1])["error"])

    def test_static_allowlist_and_no_directory_listing(self):
        for path in ("/", "/index.html", "/app.js", "/style.css"):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 100)
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        for path in (
            "/data",
            "/data/",
            "/data/ledger.json",
            "/../server.py",
            "/%2e%2e/server.py",
            "/.git/config",
            "/unknown.js",
        ):
            with self.subTest(path=path):
                status, value = self.json_request("GET", path)
                self.assertEqual(status, 404)
                self.assertIn("error", value)

    def test_static_symlink_is_not_served(self):
        directory = pathlib.Path(self.tmp.name) / "public"
        directory.mkdir()
        link = directory / "index.html"
        try:
            link.symlink_to(self.ledger_path)
        except OSError:
            self.skipTest("OS does not permit this process to create symlinks")
        with patch.object(SERVER, "PUBLIC", directory):
            self.assertEqual(self.request("GET", "/")[0], 404)

    def test_ledger_symlink_is_not_served(self):
        link = pathlib.Path(self.tmp.name) / "linked.json"
        try:
            link.symlink_to(self.ledger_path)
        except OSError:
            self.skipTest("OS does not permit this process to create symlinks")
        with patch.object(SERVER, "LEDGER", link):
            self.assertEqual(self.json_request("GET", "/api/ledger")[0], 503)

    def test_host_and_origin_must_match_local_service(self):
        status, _, body = self.request(
            "GET", "/api/status", headers={"Host": f"attacker.invalid:{self.port}"}
        )
        self.assertEqual(status, 421)
        self.assertIn("error", json.loads(body))
        status, _, body = self.request(
            "POST",
            "/api/authorize",
            b"{}",
            {
                "Content-Type": "application/json",
                "Origin": "https://attacker.invalid",
            },
        )
        self.assertEqual(status, 403)
        self.assertIn("error", json.loads(body))
        status, _, _ = self.request(
            "POST",
            "/api/authorize",
            b"{}",
            {
                "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.port}",
            },
        )
        self.assertEqual(status, 200)

    def test_head_has_no_body_and_options_does_not_enable_cors(self):
        status, headers, body = self.request("HEAD", "/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        status, headers, body = self.request("OPTIONS", "/api/bind")
        self.assertEqual(status, 405)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_overloaded_service_rejects_before_spawning_worker(self):
        acquired = 0
        try:
            for _ in range(32):
                if self.httpd._workers.acquire(timeout=1):
                    acquired += 1
            self.assertEqual(acquired, 32)
            status, value = self.json_request("GET", "/api/status")
            self.assertEqual(status, 503)
            self.assertIn("busy", value["error"])
        finally:
            for _ in range(acquired):
                self.httpd._workers.release()


if __name__ == "__main__":
    unittest.main()
