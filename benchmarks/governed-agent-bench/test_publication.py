"""Network-free tests for the Hub publication bundle."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "governed_agent_bench_build_publication",
        HERE / "build_publication.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_publisher():
    spec = importlib.util.spec_from_file_location(
        "governed_agent_bench_publish_huggingface",
        HERE / "publish_huggingface.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeAdd:
    def __init__(self, *, path_in_repo, path_or_fileobj):
        self.path_in_repo = path_in_repo
        self.body = path_or_fileobj.read()


class FakeDelete:
    def __init__(self, *, path_in_repo):
        self.path_in_repo = path_in_repo


class PublicationTests(unittest.TestCase):
    def test_bundle_is_hash_closed_and_truth_labeled(self):
        builder = _load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            report = builder.build(
                output,
                "a" * 40,
                "2026-07-28T12:00:00Z",
            )
            self.assertFalse(report["network_accessed"])
            self.assertFalse(report["credentials_accessed"])
            self.assertFalse(report["publication_performed"])

            for repo_type in ("dataset", "space"):
                folder = output / repo_type
                manifest = json.loads(
                    (folder / "publication-manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(
                    manifest["managed_by"],
                    "szl-holdings/a11oy:benchmarks/governed-agent-bench",
                )
                for entry in manifest["files"]:
                    path = folder / entry["path"]
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.stat().st_size, entry["bytes"])
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                        entry["sha256"],
                    )

            leaderboard = json.loads(
                (output / "dataset" / "leaderboard.json").read_text(encoding="utf-8")
            )
            self.assertEqual(leaderboard["eligible_model_submissions"], 0)
            self.assertEqual(leaderboard["model_submissions"], [])
            reference = leaderboard["reference_rows"][0]
            self.assertEqual(reference["score"], 100.0)
            self.assertEqual(reference["entry_class"], "SAMPLE_REFERENCE_NOT_MODEL")
            self.assertFalse(reference["eligible_for_model_ranking"])
            self.assertEqual(reference["receipt_verification"], "STRUCTURE_ONLY")
            self.assertFalse(reference["cryptographic_verification"])

            app = output / "space" / "app.py"
            ast.parse(app.read_text(encoding="utf-8"))
            space_result = json.loads(
                (
                    output
                    / "space"
                    / "results"
                    / "reference-conformance.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(space_result["axes"]["fail_closed"]["passed"], 2)
            requirements = (output / "space" / "requirements.txt").read_text(
                encoding="utf-8"
            )
            self.assertEqual(requirements, "gradio==6.20.0\n")

    def test_invalid_source_revision_fails_closed(self):
        builder = _load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(builder.PublicationBuildError):
                builder.build(Path(tmp), "main", "2026-07-28T12:00:00Z")

    def test_publish_job_is_bound_to_protected_main(self):
        workflow = (HERE.parents[1] / ".github" / "workflows" / "governed-agent-bench.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
            workflow,
        )

    def test_operation_plan_deletes_every_stale_remote_path(self):
        publisher = _load_publisher()
        expected = {
            "README.md": b"card\n",
            "publication-manifest.json": json.dumps(
                {"managed_by": publisher.MANAGED_BY}
            ).encode(),
        }
        operations, stale = publisher._operation_plan(
            expected,
            {"README.md", "publication-manifest.json", "renamed.json", "stale.txt"},
            FakeAdd,
            FakeDelete,
        )
        self.assertEqual(stale, ("renamed.json", "stale.txt"))
        self.assertEqual(
            {item.path_in_repo for item in operations if isinstance(item, FakeAdd)},
            set(expected),
        )
        self.assertEqual(
            {item.path_in_repo for item in operations if isinstance(item, FakeDelete)},
            set(stale),
        )

    def test_exact_inventory_rejects_unexpected_remote_file(self):
        publisher = _load_publisher()
        with self.assertRaisesRegex(publisher.PublicationError, "unexpected=.*stale.txt"):
            publisher._require_exact_inventory(
                "SZLHOLDINGS/example",
                "dataset",
                {"README.md": b"card\n"},
                {"README.md", "stale.txt"},
            )

    def test_exact_inventory_accepts_only_the_payload(self):
        publisher = _load_publisher()
        self.assertIsNone(
            publisher._require_exact_inventory(
                "SZLHOLDINGS/example",
                "space",
                {"README.md": b"card\n", "app.py": b"pass\n"},
                {"app.py", "README.md"},
            )
        )


if __name__ == "__main__":
    unittest.main()
