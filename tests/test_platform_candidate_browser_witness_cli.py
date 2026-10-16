#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""CLI report and exit-code regression for the candidate browser witness."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import witness_platform_candidate_preview as witness


class _Browser:
    version = "test-chromium"

    def close(self) -> None:
        pass


class _PlaywrightContext:
    def __enter__(self):
        return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_kwargs: _Browser()))

    def __exit__(self, *_args) -> None:
        pass


def _playwright_modules() -> dict[str, types.ModuleType]:
    package = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = _PlaywrightContext
    package.sync_api = sync_api
    return {"playwright": package, "playwright.sync_api": sync_api}


class BrowserWitnessCLITests(unittest.TestCase):
    def test_success_prints_and_retains_pass_report_with_zero_exit(self):
        contract = SimpleNamespace(
            source_revision="a" * 40,
            manifest_sha256="b" * 64,
            assets={},
        )

        def browser_trace(_browser, _contract, *, origin, route_path, timeout_ms):
            self.assertIn(origin, witness.ALLOWED_ORIGINS)
            self.assertIn(route_path, witness.REVIEWED_ROUTES)
            self.assertEqual(timeout_ms, 30_000)
            return [], {"route": route_path}

        def origin_traces(_contract, *, origin, traces):
            self.assertEqual(set(traces), set(witness.REVIEWED_ROUTES))
            return {"origin": origin, "routes": [], "verified_assets": []}

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            sys.modules, _playwright_modules()
        ), mock.patch.object(
            witness, "read_expected_contract", return_value=("a" * 40, "b" * 64)
        ), mock.patch.object(
            witness, "load_contract", return_value=contract
        ), mock.patch.object(
            witness, "_browser_trace", side_effect=browser_trace
        ), mock.patch.object(
            witness, "validate_origin_traces", side_effect=origin_traces
        ):
            output = Path(directory) / "browser.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = witness.run(["--output", str(output)])
            printed = json.loads(stdout.getvalue())
            retained = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(printed, retained)
        self.assertEqual(printed["status"], "PASS")
        self.assertEqual(printed["candidate_state"], "CANDIDATE_DEMO")
        self.assertIs(printed["production_ready"], False)
        self.assertEqual(printed["runtime_api_binding"], "UNAVAILABLE")
        self.assertEqual(printed["effectors"], 0)
        self.assertEqual(
            [row["origin"] for row in printed["origins"]],
            list(witness.ALLOWED_ORIGINS),
        )

    def test_failure_prints_and_retains_fail_report_with_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            witness,
            "read_expected_contract",
            side_effect=witness.WitnessError("fixture contract failure"),
        ):
            output = Path(directory) / "browser.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = witness.run(["--output", str(output)])
            printed = json.loads(stdout.getvalue())
            retained = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 1)
        self.assertEqual(printed, retained)
        self.assertEqual(printed["status"], "FAIL")
        self.assertEqual(printed["error_class"], "WitnessError")
        self.assertEqual(printed["error_code"], "fixture contract failure")
        self.assertIs(printed["production_ready"], False)
        self.assertEqual(printed["effectors"], 0)

    def test_partial_origin_scope_cannot_report_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "browser.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = witness.run(
                    [
                        "--origin",
                        witness.PRODUCT_ORIGIN,
                        "--output",
                        str(output),
                    ]
                )
            printed = json.loads(stdout.getvalue())
            retained = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 1)
        self.assertEqual(printed, retained)
        self.assertEqual(printed["status"], "FAIL")
        self.assertEqual(
            printed["error_code"],
            "origin list must contain exactly both fixed origins",
        )


if __name__ == "__main__":
    unittest.main()
