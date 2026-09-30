# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.witness_command_release import InlineScripts, read_allowed, relay_readonly, require_revision


class ReleaseWitnessBoundaryTests(unittest.TestCase):
    def test_known_public_gets_only(self):
        self.assertTrue(read_allowed("GET", "https://a-11-oy.com/command-v2"))
        self.assertTrue(read_allowed("GET", "https://a-11-oy.com/api/a11oy/v1/readiness/tab-matrix?view=summary"))
        for method, url in (
            ("POST", "https://a-11-oy.com/api/a11oy/v1/kernel/probe"),
            ("POST", "https://a-11-oy.com/command-v2"),
            ("GET", "http://a-11-oy.com/command-v2"),
            ("GET", "https://a-11-oy.com.evil.invalid/command-v2"),
            ("GET", "https://user@a-11-oy.com/command-v2"),
            ("GET", "https://a-11-oy.com:443/command-v2"),
            ("GET", "https://a-11-oy.com/command-v2#unexpected"),
            ("GET", "https://a-11-oy.com/api/build-info?redirect=1"),
            ("GET", "https://a-11-oy.com/unknown"),
        ):
            with self.subTest(method=method, url=url):
                self.assertFalse(read_allowed(method, url))

    def test_source_readback_must_be_exact_and_non_minting(self):
        expected = "a" * 40
        valid = {"status": "OBSERVED", "build": {"revision": expected}, "receipt_minted": False}
        require_revision(valid, expected)
        for data in (None, [], {}, {**valid, "status": "UNKNOWN"},
                     {**valid, "build": {"revision": "b" * 40}},
                     {**valid, "receipt_minted": 0}, {**valid, "receipt_minted": True}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                require_revision(data, expected)
        with self.assertRaises(ValueError):
            require_revision(valid, "main")

    def test_inline_script_match_does_not_confuse_provider_script(self):
        scripts = InlineScripts('<SCRIPT>const observed = 1;</SCRIPT><script src="/provider.js"></script>')
        self.assertEqual(scripts.scripts, ["const observed = 1;"])

    def test_writes_and_redirects_never_reach_a_second_origin(self):
        for method, status, reason in (
            ("POST", 200, "OUTSIDE_GET_ALLOWLIST"),
            ("GET", 302, "REDIRECT_REJECTED"),
            ("GET", 307, "REDIRECT_REJECTED"),
        ):
            with self.subTest(method=method, status=status):
                route = Mock(request=SimpleNamespace(method=method, url="https://a-11-oy.com/command-v2"))
                route.fetch.return_value.status = status
                blocked, requests = [], []
                relay_readonly(route, blocked, requests)
                route.abort.assert_called_once_with()
                route.fulfill.assert_not_called()
                self.assertEqual(blocked[0]["reason"], reason)
                if method == "POST":
                    route.fetch.assert_not_called()
                else:
                    route.fetch.assert_called_once_with(max_redirects=0, timeout=15000)

    def test_real_response_bytes_are_preserved_without_fixture_substitution(self):
        route = Mock(request=SimpleNamespace(method="GET", url="https://a-11-oy.com/command-v2"))
        response = route.fetch.return_value
        response.status = 200
        response.body.return_value = b"<html>source bytes</html>"
        blocked, requests = [], []
        relay_readonly(route, blocked, requests)
        route.fulfill.assert_called_once_with(response=response, body=response.body.return_value)
        route.abort.assert_not_called()
        self.assertEqual(blocked, [])
        response.body.return_value = b"x" * 2_000_001
        relay_readonly(route, blocked, requests)
        self.assertEqual(blocked[0]["reason"], "RESPONSE_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
