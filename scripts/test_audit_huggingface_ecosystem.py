#!/usr/bin/env python3
"""Offline regression tests for the Hugging Face ecosystem manifest emitter."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "audit_huggingface_ecosystem.py"
REVISION_FIXTURE = (
    HERE / "fixtures" / "huggingface_snapshot_revisions.json"
)
SPEC = importlib.util.spec_from_file_location("audit_huggingface_ecosystem", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


def item(item_id: str) -> dict:
    return {
        "id": item_id,
        "private": False,
        "sha": "a" * 40,
        "lastModified": "2026-07-26T00:00:00Z",
        "tags": ["license:apache-2.0"],
    }


class HuggingFaceEcosystemAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_fetch_page = audit.fetch_page
        self.original_api_items = audit.api_items
        self.original_fetch_revision = audit.fetch_revision

    def tearDown(self) -> None:
        audit.fetch_page = self.original_fetch_page
        audit.api_items = self.original_api_items
        audit.fetch_revision = self.original_fetch_revision

    def run_check(self, output: Path) -> tuple[int, str]:
        original_argv = os.sys.argv
        try:
            os.sys.argv = ["audit", "--check", "--output", str(output)]
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = audit.main()
            return result, stdout.getvalue()
        finally:
            os.sys.argv = original_argv

    def test_api_items_follows_next_link_and_deduplicates(self) -> None:
        pages = {
            "page-1": ([item("SZLHOLDINGS/b"), item("SZLHOLDINGS/a")], "page-2"),
            "page-2": ([item("SZLHOLDINGS/b"), item("SZLHOLDINGS/c")], None),
        }

        def fake_fetch_page(url: str):
            key = "page-1" if "huggingface.co" in url else url
            return pages[key]

        audit.fetch_page = fake_fetch_page
        self.assertEqual(
            [entry["id"] for entry in audit.api_items("models")],
            ["SZLHOLDINGS/a", "SZLHOLDINGS/b", "SZLHOLDINGS/c"],
        )

    def test_manifest_has_public_scope_and_no_unrelated_canonical_numbers(self) -> None:
        fixtures = {
            "models": [item("SZLHOLDINGS/model")],
            "datasets": [item("SZLHOLDINGS/dataset")],
            "spaces": [item("SZLHOLDINGS/space")],
        }
        audit.api_items = lambda kind: fixtures[kind]
        manifest = audit.build_manifest(observed_at="2026-07-26T00:00:00Z")
        self.assertEqual(manifest["counts"], {"models": 1, "datasets": 1, "spaces": 1})
        self.assertEqual(manifest["inventoryScope"]["visibility"], "public-only")
        self.assertFalse(manifest["inventoryScope"]["authenticated"])
        self.assertNotIn("canonicalNumbers", manifest)
        self.assertEqual(
            manifest["inventory"]["datasets"][0]["evidenceUrls"],
            ["https://huggingface.co/datasets/SZLHOLDINGS/dataset"],
        )
        self.assertEqual(
            manifest["inventory"]["spaces"][0]["evidenceUrls"],
            ["https://huggingface.co/spaces/SZLHOLDINGS/space"],
        )

    def test_check_ignores_revision_advance_but_rejects_inventory_drift(self) -> None:
        fixtures = {
            "models": [item("SZLHOLDINGS/model")],
            "datasets": [item("SZLHOLDINGS/dataset")],
            "spaces": [item("SZLHOLDINGS/space")],
        }
        audit.api_items = lambda kind: fixtures[kind]
        audit.fetch_revision = lambda item_id, repo_type, revision: {
            "id": item_id,
            "sha": revision,
            "lastModified": "2026-07-26T00:00:00Z",
        }
        observed_at = "2026-07-26T00:00:00Z"
        manifest = audit.build_manifest(observed_at=observed_at)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(self.run_check(output)[0], 0)
            fixtures["datasets"][0]["sha"] = "b" * 40
            fixtures["datasets"][0]["lastModified"] = "2026-07-26T00:30:00Z"
            self.assertEqual(self.run_check(output)[0], 0)
            fixtures["models"].append(item("SZLHOLDINGS/new-model"))
            self.assertEqual(self.run_check(output)[0], 1)

    def test_check_verifies_retained_historical_revision_fields(self) -> None:
        fixture = json.loads(REVISION_FIXTURE.read_text(encoding="utf-8"))
        fixtures = {
            "models": [fixture["liveNewer"]],
            "datasets": [],
            "spaces": [],
        }
        audit.api_items = lambda kind: fixtures[kind]
        audit.fetch_revision = lambda item_id, repo_type, revision: fixture[
            "historical"
        ]
        manifest = audit.build_manifest(observed_at=fixture["observedAt"])
        manifest["inventory"]["models"][0].update(fixture["stored"])

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            output.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            result, _ = self.run_check(output)
            self.assertEqual(result, 0)

            manifest["inventory"]["models"][0]["sha"] = "not-a-sha"
            output.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            result, message = self.run_check(output)
            self.assertEqual(result, 1)
            self.assertIn("sha must be a 40-character Git SHA", message)

            manifest["inventory"]["models"][0].update(fixture["stored"])
            manifest["inventory"]["models"][0][
                "lastModified"
            ] = "2026-07-25T23:59:59Z"
            output.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            result, message = self.run_check(output)
            self.assertEqual(result, 1)
            self.assertIn(
                "lastModified does not match its historical revision",
                message,
            )

    def test_observed_at_requires_non_future_rfc3339_utc(self) -> None:
        now = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(
            audit.validate_observed_at(
                "2026-07-26T01:00:00Z",
                now=now,
            ),
            now,
        )
        self.assertEqual(
            audit.validate_observed_at(
                "2026-07-26T01:00:00+00:00",
                now=now,
            ),
            now,
        )
        for invalid in (
            "not-a-date",
            "2026-07-26",
            "2026-07-26T01:00:00",
            "2026-07-26T01:00:00-04:00",
            "2026-07-26T01:00:01Z",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    audit.validate_observed_at(invalid, now=now)


if __name__ == "__main__":
    unittest.main(verbosity=2)
