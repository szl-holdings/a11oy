#!/usr/bin/env python3
"""Schema-v2 regressions for immutable public-card transport."""

from __future__ import annotations

import importlib.util
import urllib.error
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "audit_huggingface_ecosystem.py"
SPEC = importlib.util.spec_from_file_location("audit_hf_resolve_v2", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class HuggingFaceResolveTransportV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_urlopen = audit.urllib.request.urlopen
        self.original_fetch_card = audit.fetch_card_markdown

    def tearDown(self) -> None:
        audit.urllib.request.urlopen = self.original_urlopen
        audit.fetch_card_markdown = self.original_fetch_card

    def test_ungated_cards_use_exact_resolve_revision(self) -> None:
        calls: list[str] = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def read(self) -> bytes:
                return b"# exact revision\r\n"

        def urlopen(url: str, *, timeout: float):
            self.assertEqual(timeout, 30)
            calls.append(url)
            return Response()

        audit.urllib.request.urlopen = urlopen
        revision = "e" * 40
        cases = (
            ("model", "SZLHOLDINGS/model", ""),
            ("dataset", "SZLHOLDINGS/dataset", "datasets/"),
            ("space", "SZLHOLDINGS/space", "spaces/"),
        )
        for repo_type, item_id, prefix in cases:
            with self.subTest(repo_type=repo_type):
                self.assertEqual(
                    audit.fetch_card_markdown(item_id, repo_type, revision),
                    "# exact revision\r\n",
                )
                self.assertEqual(
                    calls[-1],
                    f"https://huggingface.co/{prefix}{item_id}/"
                    f"resolve/{revision}/README.md",
                )
        self.assertEqual(len(calls), 3)
        self.assertTrue(all("/resolve/" in url for url in calls))
        self.assertTrue(all("/raw/" not in url for url in calls))

    def test_only_not_found_maps_to_empty_ungated_card(self) -> None:
        calls = 0

        def missing(url: str, *, timeout: float):
            nonlocal calls
            calls += 1
            self.assertEqual(timeout, 30)
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        audit.urllib.request.urlopen = missing
        self.assertEqual(
            audit.fetch_card_markdown(
                "SZLHOLDINGS/no-card", "model", "a" * 40
            ),
            "",
        )
        self.assertEqual(calls, 1)

    def test_unexpected_access_error_stays_fail_closed(self) -> None:
        calls = 0

        def unauthorized(url: str, *, timeout: float):
            nonlocal calls
            calls += 1
            self.assertEqual(timeout, 30)
            raise urllib.error.HTTPError(
                url, 401, "Authentication Required", {}, None
            )

        audit.urllib.request.urlopen = unauthorized
        with self.assertRaises(urllib.error.HTTPError) as context:
            audit.fetch_card_markdown(
                "SZLHOLDINGS/unexpected-401", "model", "b" * 40
            )
        self.assertEqual(context.exception.code, 401)
        self.assertEqual(calls, 1)

    def test_every_supported_gated_mode_bypasses_card_transport(self) -> None:
        def forbidden_fetch(*_: object, **__: object) -> str:
            raise AssertionError("gated card transport must not be called")

        audit.fetch_card_markdown = forbidden_fetch
        for provider_mode, normalized_mode in (
            ("auto", "auto"),
            ("manual", "manual"),
            (True, "enabled"),
        ):
            with self.subTest(provider_mode=provider_mode):
                item = {
                    "id": f"SZLHOLDINGS/gated-{normalized_mode}",
                    "private": False,
                    "gated": provider_mode,
                    "disabled": False,
                    "sha": "c" * 40,
                    "lastModified": "2026-09-05T00:00:00.000Z",
                    "cardData": {"license": "apache-2.0"},
                    "tags": ["license:apache-2.0"],
                }
                summary = audit.item_summary(item, "model")
                self.assertTrue(summary["gated"])
                self.assertIsNone(summary["cardSemanticSha256"])
                observation = summary["cardObservation"]
                self.assertEqual(observation["state"], "ACCESS_RESTRICTED")
                self.assertEqual(observation["scope"], "PUBLIC_METADATA_ONLY")
                self.assertEqual(observation["gateMode"], normalized_mode)
                self.assertEqual(len(observation["metadataSha256"]), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
