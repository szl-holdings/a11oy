#!/usr/bin/env python3
"""Network-free regressions for exact Hugging Face card transport under schema v2."""
from __future__ import annotations

import importlib.util
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "hf_inventory_v2_transport",
    HERE / "audit_huggingface_ecosystem.py",
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b"# exact revision\r\n"


class HuggingFaceResolveTransportV2Tests(unittest.TestCase):
    def test_public_cards_use_exact_resolve_revision_for_every_repo_type(self) -> None:
        calls: list[str] = []

        def success(url: str, *, timeout: float):
            self.assertEqual(timeout, 30)
            calls.append(url)
            return _Response()

        revision = "e" * 40
        cases = (
            ("model", "SZLHOLDINGS/model", ""),
            ("dataset", "SZLHOLDINGS/dataset", "datasets/"),
            ("space", "SZLHOLDINGS/space", "spaces/"),
        )
        with patch.object(AUDIT.urllib.request, "urlopen", side_effect=success):
            for repo_type, item_id, prefix in cases:
                with self.subTest(repo_type=repo_type):
                    self.assertEqual(
                        AUDIT.fetch_card_markdown(item_id, repo_type, revision),
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

    def test_404_is_empty_but_401_remains_blocking_for_ungated_cards(self) -> None:
        revision = "e" * 40

        def error(code: int):
            def fail(url: str, *, timeout: float):
                self.assertEqual(timeout, 30)
                raise urllib.error.HTTPError(url, code, "provider response", {}, None)

            return fail

        with patch.object(AUDIT.urllib.request, "urlopen", side_effect=error(404)):
            self.assertEqual(
                AUDIT.fetch_card_markdown(
                    "SZLHOLDINGS/no-card",
                    "model",
                    revision,
                ),
                "",
            )
        with patch.object(AUDIT.urllib.request, "urlopen", side_effect=error(401)):
            with self.assertRaises(urllib.error.HTTPError) as context:
                AUDIT.fetch_card_markdown(
                    "SZLHOLDINGS/unexpected-private-boundary",
                    "model",
                    revision,
                )
        self.assertEqual(context.exception.code, 401)

    def test_gated_schema_v2_cards_remain_metadata_only_without_any_file_fetch(self) -> None:
        item = {
            "id": "SZLHOLDINGS/gated-model",
            "sha": "a" * 40,
            "lastModified": "2026-09-05T00:00:00Z",
            "private": False,
            "gated": "auto",
            "tags": ["license:apache-2.0"],
            "cardData": {"license": "apache-2.0", "tags": ["receipt"]},
        }
        with patch.object(
            AUDIT,
            "fetch_card_markdown",
            side_effect=AssertionError("gated card fetch attempted"),
        ):
            summary = AUDIT.item_summary(item, "model")
        self.assertTrue(summary["gated"])
        self.assertIsNone(summary["cardSemanticSha256"])
        self.assertEqual(summary["cardObservation"]["state"], "ACCESS_RESTRICTED")
        self.assertEqual(summary["cardObservation"]["scope"], "PUBLIC_METADATA_ONLY")
        self.assertEqual(summary["cardObservation"]["gateMode"], "auto")


if __name__ == "__main__":
    unittest.main(verbosity=2)
