#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise source checks through real Requests with offline HTTP responses."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error


REVISION = "a" * 40
MOVED_REVISION = "b" * 40
SOURCE_URL = "https://api.github.com/repos/szl-holdings/a11oy/commits/main"
MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "hf_publish_vertical_flagships_v4.py"
)


class Response:
    def __init__(self, revision: str) -> None:
        self.revision = revision

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps({"sha": self.revision}).encode()


class MemoryReceipt:
    """Keep publisher receipt writes in memory during offline tests."""
    def __init__(self) -> None:
        self.text = ""

    def write_text(self, text: str, *, encoding: str) -> None:
        if encoding != "utf-8":
            raise AssertionError("unexpected receipt encoding")
        self.text = text


class OwnRepositoryAuthentication(unittest.TestCase):
    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("own_repo_auth_test", MODULE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load publisher")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.requests = []
        self.environment = {"GITHUB_SHA": REVISION, "GITHUB_RUN_ID": "7"}
        self.guard = SimpleNamespace(guard_report=lambda: {"existing_only": True})

    def response_reader(self, revisions):
        remaining = iter(revisions)

        def read(request, *, timeout):
            self.assertEqual(request.full_url, SOURCE_URL)
            self.assertEqual(timeout, 30)
            self.requests.append(request)
            return Response(next(remaining))

        return read

    def check_finance_request(self, tokens, expected_token) -> None:
        with patch.dict(os.environ, {**self.environment, **tokens}, clear=True), patch.object(
            self.module.urllib.request, "urlopen", self.response_reader([MOVED_REVISION])
        ):
            with self.assertRaisesRegex(RuntimeError, "no longer current main"):
                self.module.finance_preflight()
        self.assertEqual(len(self.requests), 1)
        expected = None if expected_token is None else "Bearer " + expected_token
        self.assertEqual(self.requests[0].get_header("Authorization"), expected)

    def test_finance_passes_canonical_credential_to_actual_request(self) -> None:
        self.check_finance_request(
            {"GITHUB_TOKEN": "synthetic-canonical"}, "synthetic-canonical"
        )

    def test_finance_passes_cli_alias_to_actual_request(self) -> None:
        self.check_finance_request({"GH_TOKEN": "synthetic-cli"}, "synthetic-cli")

    def test_canonical_alias_wins_without_recording_either_value(self) -> None:
        self.check_finance_request(
            {"GITHUB_TOKEN": " synthetic-canonical ", "GH_TOKEN": "synthetic-cli"},
            "synthetic-canonical",
        )

    def test_blank_canonical_alias_uses_cli_alias(self) -> None:
        self.check_finance_request(
            {"GITHUB_TOKEN": " \t", "GH_TOKEN": " synthetic-cli "}, "synthetic-cli"
        )

    def test_missing_credential_does_not_change_source_revision_gate(self) -> None:
        self.check_finance_request({}, None)

    def test_selected_preflights_use_authenticated_actual_requests(self) -> None:
        for scope in ("terra", "counsel"):
            with self.subTest(scope=scope), patch.dict(
                os.environ, {**self.environment, "GH_TOKEN": "synthetic-cli"}, clear=True
            ), patch.object(
                self.module.urllib.request, "urlopen", self.response_reader([REVISION])
            ):
                self.assertEqual(self.module.selected_generated_preflight(scope), REVISION)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(
            request.get_header("Authorization") == "Bearer synthetic-cli"
            for request in self.requests
        ))

    def run_selected(self, revisions):
        receipt = MemoryReceipt()
        calls = []
        emitted = {
            "complete": True,
            "rows": [{
                "id": "SZLHOLDINGS/terra",
                "source_revision": REVISION,
                "workflow_run_id": 7,
                "operational": True,
            }],
        }

        def publish(name, path, **kwargs):
            calls.append((name, kwargs))
            return 0, None, ("terra",)

        with patch.dict(
            os.environ, {**self.environment, "GITHUB_TOKEN": "synthetic-canonical"},
            clear=True,
        ), patch.object(
            self.module.urllib.request, "urlopen", self.response_reader(revisions)
        ), patch.object(self.module, "FLAGSHIP_RECEIPT", receipt), patch.object(
            self.module, "read_receipt", lambda path: emitted
        ), patch.object(self.module, "run_publisher", publish), redirect_stdout(io.StringIO()):
            code = self.module.publish_selected_generated("terra", self.guard)
        return code, json.loads(receipt.text), calls

    def test_selected_preflight_and_postflight_authenticate_and_remain_bound(self) -> None:
        code, receipt, calls = self.run_selected([REVISION, REVISION])
        self.assertEqual(code, 0)
        self.assertTrue(receipt["complete"])
        self.assertTrue(receipt["source_still_current"])
        self.assertEqual(calls, [("szl_flagship_v4", {"selected_slug": "terra"})])
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(
            request.get_header("Authorization") == "Bearer synthetic-canonical"
            for request in self.requests
        ))
        self.assertNotIn("synthetic-canonical", json.dumps(receipt))

    def test_moved_main_before_publication_keeps_zero_effects(self) -> None:
        code, receipt, calls = self.run_selected([MOVED_REVISION])
        self.assertEqual(code, 1)
        self.assertFalse(receipt["complete"])
        self.assertEqual(calls, [])

    def test_moved_main_after_publication_cannot_qualify_receipt(self) -> None:
        code, receipt, calls = self.run_selected([REVISION, MOVED_REVISION])
        self.assertEqual(code, 1)
        self.assertFalse(receipt["complete"])
        self.assertFalse(receipt["source_still_current"])
        self.assertEqual(len(calls), 1)

    def test_finance_source_http_failure_stays_closed_and_omits_credentials(self) -> None:
        receipt = MemoryReceipt()

        def deny(request, *, timeout):
            self.requests.append(request)
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

        with patch.dict(
            os.environ, {**self.environment, "GITHUB_TOKEN": "synthetic-canonical"},
            clear=True,
        ), patch.object(self.module.urllib.request, "urlopen", deny), patch.object(
            self.module, "FLAGSHIP_RECEIPT", receipt
        ), patch.object(self.module, "run_publisher") as writer, redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.publish_finance_only(self.guard), 1)
            writer.assert_not_called()
        result = json.loads(receipt.text)
        self.assertFalse(result["complete"])
        self.assertFalse(result["secret_values_recorded"])
        self.assertIn("HTTP 403", result["detail"])
        self.assertNotIn("synthetic-canonical", receipt.text)
        self.assertEqual(self.requests[0].get_header("Authorization"), "Bearer synthetic-canonical")


if __name__ == "__main__":
    unittest.main(verbosity=2)
