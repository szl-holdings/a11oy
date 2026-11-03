#!/usr/bin/env python3
"""Offline regression tests for the Hugging Face ecosystem manifest emitter."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import urllib.error


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
        self.original_public_get = audit.public_get
        self.original_fetch_revision = audit.fetch_revision
        self.original_fetch_card_markdown = audit.fetch_card_markdown
        audit.fetch_card_markdown = (
            lambda item_id, repo_type, revision: f"# {item_id}\n"
        )

    def tearDown(self) -> None:
        audit.fetch_page = self.original_fetch_page
        audit.api_items = self.original_api_items
        audit.public_get = self.original_public_get
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

    def test_model_rename_requires_new_identity_and_exact_revision(self) -> None:
        old_id = "SZLHOLDINGS/old-model"
        new_id = "SZLHOLDINGS/new-model"
        rename = [old_id, new_id, "a" * 40]
        audit.validate_model_rename({"inventory": {"models": [item(new_id)]}}, rename)
        for entries in (
            [],
            [item(old_id)],
            [item(old_id), item(new_id)],
            [item(new_id), item(new_id)],
            [{**item(new_id), "sha": "b" * 40}],
        ):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                audit.validate_model_rename({"inventory": {"models": entries}}, rename)

    def test_model_rename_rejects_ambiguous_identity_or_revision(self) -> None:
        for rename in (
            ["SZLHOLDINGS/model", "SZLHOLDINGS/model", "a" * 40],
            ["other/old-model", "SZLHOLDINGS/new-model", "a" * 40],
            ["SZLHOLDINGS/old-model", "other/new-model", "a" * 40],
            ["SZLHOLDINGS/old-model", "SZLHOLDINGS/new-model", "main"],
        ):
            with self.subTest(rename=rename), self.assertRaises(ValueError):
                audit.validate_model_rename({"inventory": {"models": []}}, rename)

    def test_pending_model_rename_does_not_replace_snapshot(self) -> None:
        old_id, new_id = "SZLHOLDINGS/old-model", "SZLHOLDINGS/new-model"
        manifest = {"inventory": {"models": [item(old_id)]}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.json"
            original = b'{"retained":"historical evidence"}\n'
            output.write_bytes(original)
            argv = [
                "audit", "--output", str(output), "--model-rename",
                old_id, new_id, "a" * 40,
            ]
            with patch.object(os.sys, "argv", argv), patch.object(
                audit, "build_manifest", return_value=manifest
            ), redirect_stdout(io.StringIO()):
                self.assertEqual(1, audit.main())
            self.assertEqual(original, output.read_bytes())

    def test_api_items_follows_scoped_next_link(self) -> None:
        base = "https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100&full=true"
        pages = {
            base: {"status": 200, "json": [item("SZLHOLDINGS/b"), item("SZLHOLDINGS/a")],
                   "link": f'<{base}&cursor=next>; rel="next"'},
            base + "&cursor=next": {"status": 200, "json": [item("SZLHOLDINGS/c")]},
        }
        audit.public_get = pages.__getitem__
        self.assertEqual([entry["id"] for entry in audit.api_items("models")],
                         ["SZLHOLDINGS/a", "SZLHOLDINGS/b", "SZLHOLDINGS/c"])

    def test_duplicate_private_foreign_and_unbounded_pages_fail_closed(self) -> None:
        invalid_pages = ([item("SZLHOLDINGS/a")] * 2,
                         [{**item("SZLHOLDINGS/a"), "private": True}],
                         [item("other/a")], [item("SZLHOLDINGS/a")] * 101)
        for rows in invalid_pages:
            with self.subTest(rows=len(rows)):
                audit.public_get = lambda url: {"status": 200, "json": rows}
                with self.assertRaises(audit.InventoryError):
                    audit.api_items("models")
        audit.public_get = lambda url: {"status": 200, "json": [],
            "link": '<https://example.com/api/models?author=SZLHOLDINGS&limit=100&full=true>; rel="next"'}
        with self.assertRaises(audit.InventoryError):
            audit.api_items("models")

    def test_same_id_in_model_and_native_kernel_namespace_remains_distinct(self) -> None:
        rows = [item("SZLHOLDINGS/shared-name")]
        audit.api_items = lambda kind: rows if kind in {"models", "kernels"} else []
        manifest = audit.build_manifest(observed_at="2026-07-26T00:00:00Z")
        self.assertEqual(manifest["counts"], {"models": 1, "datasets": 0, "spaces": 0, "kernels": 1})
        self.assertEqual(manifest["inventory"]["models"][0]["repoType"], "model")
        kernel = manifest["inventory"]["kernels"][0]
        self.assertEqual(kernel["repoType"], "kernel")
        self.assertEqual(kernel["evidenceUrls"], ["https://huggingface.co/kernels/SZLHOLDINGS/shared-name"])
        self.assertIn("not a unique-project", manifest["inventoryScope"]["countMeaning"])

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

    def test_live_fetch_honors_numeric_retry_after(self) -> None:
        calls = 0
        sleeps: list[float] = []
        original_urlopen = audit.urllib.request.urlopen

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_: object) -> None:
                return None

        def rate_limited_urlopen(url: str, *, timeout: float):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise audit.urllib.error.HTTPError(
                    url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "17"},
                    None,
                )
            return Response()

        audit.urllib.request.urlopen = rate_limited_urlopen
        try:
            response = audit.open_url_with_retry(
                "https://huggingface.co/api/models",
                attempts=2,
                sleep=sleeps.append,
            )
        finally:
            audit.urllib.request.urlopen = original_urlopen

        self.assertIsInstance(response, Response)
        self.assertEqual(calls, 2)
        self.assertEqual(sleeps, [17.0])

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
        audit.api_items = lambda kind: fixtures.get(kind, [])
        manifest = audit.build_manifest(observed_at="2026-07-26T00:00:00Z")
        self.assertEqual(manifest["counts"], {"models": 1, "datasets": 1, "spaces": 1, "kernels": 0})
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
        audit.api_items = lambda kind: fixtures.get(kind, [])
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
        audit.api_items = lambda kind: fixtures.get(kind, [])
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
        audit.api_items = lambda kind: fixtures.get(kind, [])
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
        audit.api_items = lambda kind: fixtures.get(kind, [])
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


TRACKED_MANIFEST = REPO_ROOT / "docs" / "huggingface-ecosystem-manifest.json"
NEMO = ("model", "SZLHOLDINGS/szl-nemo")


def classes_without(*keys: tuple[str, str]):
    """The real classes with some rows dropped back to the SOURCE_TRACKED default."""
    real = audit.revision_classes.load_revision_classes()
    return audit.revision_classes.RevisionClasses(
        entries={key: value for key, value in real.entries.items() if key not in keys},
        bindings=real.bindings, sha256=real.sha256, path=real.path,
    )


def classes_with(*keys: tuple[str, str]):
    entries = {
        key: {"repoType": key[0], "id": key[1], "class": audit.revision_classes.GOVERNED_EXACT,
              "policySource": ("test fixture",), "rationale": "fixture"}
        for key in keys
    }
    return audit.revision_classes.RevisionClasses(entries=entries, bindings=(), sha256="0" * 64, path="fixture")


class GovernedRevisionAndLabelledResultTests(unittest.TestCase):
    """Golden cases for GOVERNED_EXACT rows and labelled check results; no network."""

    def setUp(self) -> None:
        self.saved = {name: getattr(audit, name) for name in ("api_items", "fetch_revision", "fetch_card_markdown")}
        audit.fetch_card_markdown = lambda item_id, repo_type, revision: f"# {item_id}\n"
        audit.fetch_revision = lambda item_id, repo_type, revision: {
            "id": item_id, "sha": revision, "lastModified": "2026-07-26T00:00:00Z",
        }
        self.folder = tempfile.TemporaryDirectory()
        self.output = Path(self.folder.name) / "manifest.json"
        self.report = Path(self.folder.name) / "report.json"

    def tearDown(self) -> None:
        for name, value in self.saved.items():
            setattr(audit, name, value)
        self.folder.cleanup()

    def snapshot(self, fixtures: dict) -> dict:
        audit.api_items = lambda kind: fixtures.get(kind, [])
        manifest = audit.build_manifest(observed_at="2026-07-26T00:00:00Z")
        self.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest

    def check(self, *extra: str) -> tuple[int, str]:
        argv = ["audit", "--check", "--output", str(self.output), "--report", str(self.report), *extra]
        stdout = io.StringIO()
        with patch.object(os.sys, "argv", argv), redirect_stdout(stdout):
            result = audit.main()
        return result, stdout.getvalue()

    def report_result(self) -> dict:
        return json.loads(self.report.read_text(encoding="utf-8"))

    def advance(self, row: dict) -> None:
        row["sha"] = "b" * 40
        row["lastModified"] = "2026-07-26T00:30:00Z"

    def test_ungated_governed_head_move_with_unchanged_card_is_invalid(self) -> None:
        fixtures = {"models": [item("SZLHOLDINGS/szl-nemo")]}
        self.snapshot(fixtures)
        self.assertEqual(self.check()[0], 0)
        self.advance(fixtures["models"][0])
        result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn("SZLHOLDINGS/szl-nemo governed revision changed", message)
        self.assertIn("model_release/szl-nemo/release-manifest.json#/hub/repository", message)
        self.assertIn("result: INVALID", message)
        self.assertEqual(self.report_result()["result"], "INVALID")

    def test_same_fixture_classed_source_tracked_stays_current(self) -> None:
        fixtures = {"models": [item("SZLHOLDINGS/szl-nemo")]}
        self.snapshot(fixtures)
        self.advance(fixtures["models"][0])
        with patch.object(audit.revision_classes, "load_revision_classes", return_value=classes_without(NEMO)):
            result, message = self.check()
        self.assertEqual(result, 0, message)
        self.assertIn("result: CURRENT", message)
        self.assertEqual(self.report_result()["result"], "CURRENT")
        self.assertEqual(self.report_result()["exitCode"], 0)

    def test_semantic_manifest_keeps_revision_only_for_governed_rows(self) -> None:
        classes = audit.revision_classes.load_revision_classes()
        manifest = {"inventory": {"models": [item("SZLHOLDINGS/szl-nemo"), item("SZLHOLDINGS/other")]}}
        rows = audit.semantic_manifest(manifest, classes)["inventory"]["models"]
        self.assertIn("sha", rows[0])
        self.assertIn("lastModified", rows[0])
        self.assertNotIn("sha", rows[1])
        self.assertNotIn("lastModified", rows[1])
        self.assertEqual(audit.semantic_manifest(manifest), audit.semantic_manifest(manifest, classes))

    def test_twin_rows_are_keyed_by_repo_type(self) -> None:
        twin = "SZLHOLDINGS/twin"
        with patch.object(audit.revision_classes, "load_revision_classes", return_value=classes_with(("model", twin))):
            fixtures = {"models": [item(twin)], "kernels": [item(twin)]}
            self.snapshot(fixtures)
            self.advance(fixtures["kernels"][0])
            self.assertEqual(self.check()[0], 0)
            self.advance(fixtures["models"][0])
            result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn(f"{twin} governed revision changed (model,", message)

    def test_policy_failure_is_invalid_before_any_network_read(self) -> None:
        self.snapshot({"models": [item("SZLHOLDINGS/model")]})
        audit.api_items = lambda kind: (_ for _ in ()).throw(AssertionError("network read attempted"))
        with tempfile.TemporaryDirectory() as empty:
            with patch.object(audit.revision_classes, "REPO_ROOT", Path(empty)):
                result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn("revision classes or coverage are invalid", message)
        self.assertIn("result: INVALID", message)
        self.assertEqual(self.report_result()["revisionClasses"], None)

    def test_hub_outage_is_unavailable_and_never_drift_or_current(self) -> None:
        self.snapshot({"models": [item("SZLHOLDINGS/model")]})

        def http(code: int) -> urllib.error.HTTPError:
            return audit.urllib.error.HTTPError("https://huggingface.co/api/models", code, "x", {}, None)

        def wrapped(code: int) -> Exception:
            error = audit.InventoryError("HTTP_UNAVAILABLE")
            error.__cause__ = http(code)
            return error

        outages = {
            "connection": audit.urllib.error.URLError("offline"),
            "timeout": TimeoutError("timed out"),
            "listing 503": wrapped(503),
            "listing 429": wrapped(429),
        }
        for name, error in outages.items():
            with self.subTest(case=name):
                audit.api_items = lambda kind, error=error: (_ for _ in ()).throw(error)
                result, message = self.check()
                self.assertEqual(result, 1)
                self.assertIn("evidence is unavailable", message)
                self.assertIn("result: UNAVAILABLE", message)
                self.assertNotIn("stale", message)
                self.assertEqual(self.report_result()["result"], "UNAVAILABLE")

    def test_policy_and_evidence_failures_are_invalid_not_unavailable(self) -> None:
        self.snapshot({"models": [item("SZLHOLDINGS/model")]})
        forbidden = audit.InventoryError("HTTP_UNAVAILABLE")
        forbidden.__cause__ = audit.urllib.error.HTTPError("https://huggingface.co/api/models", 403, "x", {}, None)
        failures = {
            "listing 403": forbidden,
            "private row": audit.InventoryError("PUBLIC_VISIBILITY_UNOBSERVED"),
            "foreign row": audit.InventoryError("DUPLICATE_OR_FOREIGN_REPOSITORY"),
            "budget": audit.InventoryError("ITEM_BUDGET"),
        }
        for name, error in failures.items():
            with self.subTest(case=name):
                audit.api_items = lambda kind, error=error: (_ for _ in ()).throw(error)
                result, message = self.check()
                self.assertEqual(result, 1)
                self.assertIn("result: INVALID", message)
                self.assertEqual(self.report_result()["result"], "INVALID")
        audit.api_items = lambda kind: [{**item("SZLHOLDINGS/model"), "gated": "unexpected"}] if kind == "models" else []
        result, message = self.check()
        self.assertEqual((result, "result: INVALID" in message), (1, True))

    def test_card_fetch_failures_are_labelled_by_cause(self) -> None:
        fixtures = {"models": [item("SZLHOLDINGS/model")]}
        self.snapshot(fixtures)
        url = "https://huggingface.co/SZLHOLDINGS/model/resolve/x/README.md"
        for name, error, label in (
            ("401", audit.urllib.error.HTTPError(url, 401, "x", {}, None), "INVALID"),
            ("410", audit.urllib.error.HTTPError(url, 410, "x", {}, None), "INVALID"),
            ("503", audit.urllib.error.HTTPError(url, 503, "x", {}, None), "UNAVAILABLE"),
            ("timeout", TimeoutError("timed out"), "UNAVAILABLE"),
        ):
            with self.subTest(case=name):
                audit.fetch_card_markdown = lambda *args, error=error: (_ for _ in ()).throw(error)
                result, message = self.check()
                self.assertEqual(result, 1)
                self.assertIn(f"result: {label}", message)

    def test_historical_proof_outage_is_unavailable_and_deletion_stays_invalid(self) -> None:
        fixtures = {"spaces": [item("SZLHOLDINGS/space")]}
        self.snapshot(fixtures)
        self.advance(fixtures["spaces"][0])
        audit.fetch_revision = lambda *args: (_ for _ in ()).throw(audit.urllib.error.URLError("reset"))
        result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn("could not be observed", message)
        self.assertIn("result: UNAVAILABLE", message)
        audit.fetch_revision = lambda *args: (_ for _ in ()).throw(
            audit.urllib.error.HTTPError("https://huggingface.co/api/spaces", 404, "Not Found", {}, None))
        result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn("is not verifiable", message)
        self.assertIn("result: INVALID", message)

    def test_drift_report_names_each_row_with_class_and_policy_source(self) -> None:
        card = {"text": "# Model\n\nA claim.\n"}
        audit.fetch_card_markdown = lambda *args: card["text"]
        fixtures = {"models": [item("SZLHOLDINGS/model"), item("SZLHOLDINGS/szl-nemo")]}
        self.snapshot(fixtures)
        card["text"] = "# Model\n\nA different claim.\n"
        result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn("manifest is stale", message)
        self.assertIn("result: DRIFT", message)
        report = self.report_result()
        self.assertEqual((report["result"], report["exitCode"]), ("DRIFT", 1))
        rows = {row["id"]: row for row in report["changedRows"]}
        self.assertEqual(rows["SZLHOLDINGS/model"]["class"], "SOURCE_TRACKED")
        self.assertEqual(rows["SZLHOLDINGS/model"]["policySource"], ["default:SOURCE_TRACKED"])
        self.assertEqual(rows["SZLHOLDINGS/model"]["fields"], ["cardSemanticSha256"])
        self.assertEqual(rows["SZLHOLDINGS/szl-nemo"]["class"], "GOVERNED_EXACT")
        self.assertRegex(report["revisionClasses"]["sha256"], r"^[0-9a-f]{64}$")

    def test_unwritable_report_is_never_current(self) -> None:
        self.snapshot({"models": [item("SZLHOLDINGS/model")]})
        self.report.mkdir()
        result, message = self.check()
        self.assertEqual(result, 1)
        self.assertIn("report could not be written", message)
        self.assertIn("result: INVALID", message)
        self.assertNotIn("result: CURRENT", message)

    def test_tracked_manifest_still_validates_structurally_with_the_new_loader(self) -> None:
        raw = TRACKED_MANIFEST.read_text(encoding="utf-8")
        existing = json.loads(raw)
        self.assertEqual(raw, json.dumps(existing, indent=2, sort_keys=False) + "\n")
        classes = audit.revision_classes.load_revision_classes()
        audit.revision_classes.validate_manifest_coverage(classes, existing, label="tracked manifest")
        observed_at = audit.validate_observed_at(existing["observedAt"])
        audit.validate_generated_revision_evidence(existing, observed_at=observed_at)
        audit.fetch_revision = lambda *args: (_ for _ in ()).throw(AssertionError("network read attempted"))
        audit.validate_snapshot_revisions(existing, json.loads(raw), observed_at=observed_at, classes=classes)
        stable = audit.semantic_manifest(existing, classes)
        exact = 0
        for plural, repo_type in audit.revision_classes.PLURALS.items():
            for row, kept in zip(existing["inventory"][plural], stable["inventory"][plural]):
                if row.get("gated") or classes.governed(repo_type, row["id"]):
                    exact += 1
                    self.assertEqual((kept["sha"], kept["lastModified"]), (row["sha"], row["lastModified"]))
                else:
                    self.assertNotIn("sha", kept)
        self.assertGreater(exact, 0)
        self.output.write_text(raw, encoding="utf-8")
        with patch.object(audit, "build_manifest", side_effect=lambda **_: json.loads(raw)):
            result, message = self.check()
        self.assertEqual(result, 0, message)
        self.assertEqual(self.report_result()["result"], "CURRENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
