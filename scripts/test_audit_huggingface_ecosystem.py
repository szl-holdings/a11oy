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
REPO_ROOT = HERE.parent
SCRIPT = HERE / "audit_huggingface_ecosystem.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "operational.yml"
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "huggingface.yml"
SCHEMA = REPO_ROOT / "docs" / "huggingface-ecosystem-manifest.schema.json"
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
        "cardSemanticSha256": "c" * 64,
        "tags": ["license:apache-2.0"],
    }


class HuggingFaceEcosystemAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_fetch_page = audit.fetch_page
        self.original_api_items = audit.api_items
        self.original_fetch_revision = audit.fetch_revision
        self.original_fetch_card_markdown = audit.fetch_card_markdown
        audit.fetch_card_markdown = (
            lambda item_id, repo_type, revision: f"# {item_id}\n"
        )

    def tearDown(self) -> None:
        audit.fetch_page = self.original_fetch_page
        audit.api_items = self.original_api_items
        audit.fetch_revision = self.original_fetch_revision
        audit.fetch_card_markdown = self.original_fetch_card_markdown

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
            if key == "page-1":
                self.assertIn("full=true", url)
            return pages[key]

        audit.fetch_page = fake_fetch_page
        self.assertEqual(
            [entry["id"] for entry in audit.api_items("models")],
            ["SZLHOLDINGS/a", "SZLHOLDINGS/b", "SZLHOLDINGS/c"],
        )

    def test_live_fetch_retries_transient_transport_failure(self) -> None:
        calls = 0
        sleeps: list[float] = []
        original_urlopen = audit.urllib.request.urlopen

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_: object) -> None:
                return None

        def flaky_urlopen(url: str, *, timeout: float):
            nonlocal calls
            calls += 1
            self.assertEqual(url, "https://huggingface.co/api/models")
            self.assertEqual(timeout, 30)
            if calls < 3:
                raise audit.urllib.error.URLError(
                    ConnectionResetError("connection reset")
                )
            return Response()

        audit.urllib.request.urlopen = flaky_urlopen
        try:
            response = audit.open_url_with_retry(
                "https://huggingface.co/api/models",
                sleep=sleeps.append,
            )
        finally:
            audit.urllib.request.urlopen = original_urlopen

        self.assertIsInstance(response, Response)
        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_live_fetch_fails_closed_after_retry_exhaustion(self) -> None:
        calls = 0
        sleeps: list[float] = []
        original_urlopen = audit.urllib.request.urlopen

        def unavailable_urlopen(url: str, *, timeout: float):
            nonlocal calls
            calls += 1
            raise audit.urllib.error.URLError(
                ConnectionResetError("connection reset")
            )

        audit.urllib.request.urlopen = unavailable_urlopen
        try:
            with self.assertRaises(audit.urllib.error.URLError):
                audit.open_url_with_retry(
                    "https://huggingface.co/api/datasets",
                    attempts=3,
                    sleep=sleeps.append,
                )
        finally:
            audit.urllib.request.urlopen = original_urlopen

        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_live_fetch_does_not_retry_not_found(self) -> None:
        calls = 0
        sleeps: list[float] = []
        original_urlopen = audit.urllib.request.urlopen

        def missing_urlopen(url: str, *, timeout: float):
            nonlocal calls
            calls += 1
            raise audit.urllib.error.HTTPError(
                url,
                404,
                "Not Found",
                {},
                None,
            )

        audit.urllib.request.urlopen = missing_urlopen
        try:
            with self.assertRaises(audit.urllib.error.HTTPError):
                audit.open_url_with_retry(
                    "https://huggingface.co/missing",
                    sleep=sleeps.append,
                )
        finally:
            audit.urllib.request.urlopen = original_urlopen

        self.assertEqual(calls, 1)
        self.assertEqual(sleeps, [])

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
        self.assertTrue(
            all(
                entry["sha"]
                and entry["lastModified"]
                and len(entry["cardSemanticSha256"]) == 64
                for kind in ("models", "datasets", "spaces")
                for entry in manifest["inventory"][kind]
            )
        )
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
        fixtures["datasets"][0]["tags"] = [
            "size_categories:n<1K",
            "modality:text",
            "format:json",
            "library:datasets",
            "governed-live",
        ]
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
            fixtures["datasets"][0]["tags"] = [
                "size_categories:1K<n<10K",
                "modality:tabular",
                "format:parquet",
                "library:pandas",
                "governed-live",
            ]
            self.assertEqual(self.run_check(output)[0], 0)
            fixtures["datasets"][0]["tags"][-1] = "unreviewed"
            self.assertEqual(self.run_check(output)[0], 1)
            fixtures["datasets"][0]["tags"][-1] = "governed-live"
            fixtures["models"].append(item("SZLHOLDINGS/new-model"))
            self.assertEqual(self.run_check(output)[0], 1)

    def test_check_rejects_deleted_historical_revision(self) -> None:
        fixtures = {
            "models": [],
            "datasets": [],
            "spaces": [item("SZLHOLDINGS/recreated-space")],
        }
        audit.api_items = lambda kind: fixtures[kind]
        manifest = audit.build_manifest(
            observed_at="2026-07-26T00:00:00Z"
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            output.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            fixtures["spaces"][0]["sha"] = "b" * 40
            fixtures["spaces"][0][
                "lastModified"
            ] = "2026-07-26T00:30:00Z"

            def missing_revision(
                item_id: str,
                repo_type: str,
                revision: str,
            ) -> dict:
                raise audit.urllib.error.HTTPError(
                    (
                        f"https://huggingface.co/api/{repo_type}s/"
                        f"{item_id}/revision/{revision}"
                    ),
                    404,
                    "Not Found",
                    {},
                    None,
                )

            audit.fetch_revision = missing_revision
            result, message = self.run_check(output)
            self.assertEqual(result, 1)
            self.assertIn("historical revision", message)
            self.assertIn("is not verifiable", message)
            self.assertIn("HTTP Error 404", message)

    def test_check_rejects_card_only_semantic_drift(self) -> None:
        fixtures = {
            "models": [item("SZLHOLDINGS/model")],
            "datasets": [],
            "spaces": [],
        }
        audit.api_items = lambda kind: fixtures[kind]
        card = {"markdown": "# Model\n\nVerified inventory claim.\n"}
        audit.fetch_card_markdown = (
            lambda item_id, repo_type, revision: card["markdown"]
        )
        manifest = audit.build_manifest(observed_at="2026-07-26T00:00:00Z")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            output.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(self.run_check(output)[0], 0)
            card["markdown"] = "# Model\n\nUnverified production claim.\n"
            result, message = self.run_check(output)
            self.assertEqual(result, 1)
            self.assertIn("manifest is stale", message)

    def test_card_digest_normalizes_transport_only_whitespace(self) -> None:
        unix = "# Model\n\nA claim.\n"
        windows = "# Model  \r\n\r\nA claim.\r\n\r\n"
        self.assertEqual(
            audit.card_semantic_sha256(unix),
            audit.card_semantic_sha256(windows),
        )

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

    def test_check_rejects_incomplete_or_malformed_live_revision_evidence(
        self,
    ) -> None:
        observed_at = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)
        stored = item("SZLHOLDINGS/model")
        existing = {
            "inventory": {
                "models": [stored],
                "datasets": [],
                "spaces": [],
            }
        }
        historical = dict(stored)
        audit.fetch_revision = lambda item_id, repo_type, revision: historical
        invalid_live = (
            {
                **stored,
                "sha": "b" * 40,
                "lastModified": None,
            },
            {
                **stored,
                "sha": "not-a-sha",
                "lastModified": "2026-07-26T00:30:00Z",
            },
            {
                **stored,
                "sha": "b" * 40,
                "lastModified": "2026-07-26T01:00:01Z",
            },
        )
        for live_item in invalid_live:
            with self.subTest(live_item=live_item), self.assertRaises(ValueError):
                audit.validate_snapshot_revisions(
                    existing,
                    {
                        "inventory": {
                            "models": [live_item],
                            "datasets": [],
                            "spaces": [],
                        }
                    },
                    observed_at=observed_at,
                    now=observed_at,
                )

    def test_generated_manifest_requires_revision_evidence_at_observed_at(
        self,
    ) -> None:
        observed_at = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)
        manifest = {
            "inventory": {
                "models": [item("SZLHOLDINGS/model")],
                "datasets": [item("SZLHOLDINGS/dataset")],
                "spaces": [item("SZLHOLDINGS/space")],
            }
        }
        audit.validate_generated_revision_evidence(
            manifest,
            observed_at=observed_at,
        )
        for field, value in (
            ("sha", None),
            ("lastModified", None),
            ("sha", "not-a-sha"),
            ("lastModified", "2026-07-26T01:00:01Z"),
            ("cardSemanticSha256", None),
            ("cardSemanticSha256", "not-a-digest"),
        ):
            invalid = json.loads(json.dumps(manifest))
            invalid["inventory"]["models"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(
                ValueError
            ):
                audit.validate_generated_revision_evidence(
                    invalid,
                    observed_at=observed_at,
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
            "2026-07-25T24:00:00Z",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    audit.validate_observed_at(invalid, now=now)

    def test_operational_ci_runs_live_and_tracked_artifact_checks(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for path in (
            ".github/workflows/huggingface.yml",
            "package.json",
            "docs/ecosystem-stage-matrix.json",
            "docs/huggingface-ecosystem-manifest.json",
            "docs/huggingface-ecosystem-manifest.schema.json",
            "docs/theorem-runtime-manifest.json",
            "scripts/*.mjs",
        ):
            self.assertEqual(
                workflow.count(f"- '{path}'"),
                2,
                f"{path} must trigger both push and pull-request validation",
            )
        self.assertIn("pnpm hf:ecosystem:audit", workflow)
        self.assertIn(
            "python3 scripts/build_ecosystem_stage_matrix.py --check",
            workflow,
        )
        self.assertIn(
            "node scripts/validate_huggingface_ecosystem_schema.mjs",
            workflow,
        )
        self.assertLess(
            workflow.index("pnpm hf:ecosystem:audit"),
            workflow.index("npm run payload:huggingface"),
        )

    def test_publication_fails_closed_without_every_evidence_guard(self) -> None:
        workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        guards = (
            "pnpm hf:ecosystem:audit",
            "python3 scripts/build_ecosystem_stage_matrix.py --check",
            "node scripts/validate_huggingface_ecosystem_schema.mjs",
        )
        prepare = "run: pnpm payload:huggingface"
        upload = "python3 scripts/publish_huggingface_payload.py"

        def guarded(candidate: str) -> bool:
            return (
                prepare in candidate
                and upload in candidate
                and all(
                    guard in candidate
                    and candidate.index(guard) < candidate.index(prepare)
                    and candidate.index(guard) < candidate.index(upload)
                    for guard in guards
                )
            )

        self.assertTrue(guarded(workflow))
        for guard in guards:
            stripped = workflow.replace(guard, "", 1)
            self.assertFalse(guarded(stripped), guard)
            moved_after_upload = stripped + f"\n{guard}\n"
            self.assertFalse(guarded(moved_after_upload), guard)

    def test_published_item_schema_requires_revision_and_card_evidence(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        required = schema["$defs"]["items"]["items"]["required"]
        self.assertIn("sha", required)
        self.assertIn("lastModified", required)
        self.assertIn("cardSemanticSha256", required)


if __name__ == "__main__":
    unittest.main(verbosity=2)
