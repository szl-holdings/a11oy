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


if __name__ == "__main__":
    unittest.main()
