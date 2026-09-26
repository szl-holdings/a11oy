#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from scripts.preview_command_observations import Preview, READ_PATHS, ROOT


class PreviewTests(unittest.TestCase):
    def setUp(self):
        handler = type("FixturePreview", (Preview,), {"source": "fixture", "log_message": lambda *_args: None})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_page_is_the_exact_candidate(self):
        status, headers, body = self.request("GET", "/command-v2")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(body, (ROOT / "pages/command-v2.html").read_bytes())

    def test_fixture_reports_explicit_software_qa_and_zero(self):
        with patch("scripts.preview_command_observations.build_opener", side_effect=AssertionError("no network in fixtures")):
            status, _, body = self.request("GET", "/api/a11oy/v1/ledger")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["preview"], "SYNTHETIC SOFTWARE QA")

    def test_unknown_paths_do_not_proxy_or_serve_files(self):
        for path in ("/../AGENTS.md", "/.git/config", "/api/unknown", "/healthz?url=https://example.com"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)

    def test_host_boundary(self):
        self.assertEqual(self.request("GET", "/command-v2", {"Host": "example.com"})[0], 403)

    def test_posts_never_reach_a_backend(self):
        for path in ("/api/a11oy/v1/kernel/probe", "/api/a11oy/v1/energy/operator/start"):
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path)[0], 405)

    def test_live_proxy_only_has_the_existing_read_paths(self):
        self.assertEqual(len(READ_PATHS), 11)
        self.assertNotIn("/api/a11oy/v1/kernel/probe", READ_PATHS)
        self.assertTrue(all(path.startswith("/") and not path.startswith("//") for path in READ_PATHS))


if __name__ == "__main__":
    unittest.main()
