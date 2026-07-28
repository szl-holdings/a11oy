"""Network-free tests for the Hub publication bundle."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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
            self.assertEqual(
                leaderboard["status"], "REFERENCE_ONLY_NO_MODEL_SUBMISSIONS"
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

    def test_publish_job_is_protected_main_only(self):
        workflow = (
            HERE.parents[1] / ".github" / "workflows" / "governed-agent-bench.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "if: github.event_name != 'pull_request' && "
            "github.ref == 'refs/heads/main'",
            workflow,
        )

    def test_remote_publication_deletes_stale_files_and_closes_inventory(self):
        publisher = _load_publisher()

        class CommitOperationAdd:
            def __init__(self, path_in_repo, path_or_fileobj):
                self.path_in_repo = path_in_repo
                self.path_or_fileobj = path_or_fileobj

        class CommitOperationDelete:
            def __init__(self, path_in_repo):
                self.path_in_repo = path_in_repo

        class FakeApi:
            def __init__(self):
                self.remote = {
                    "publication-manifest.json": json.dumps(
                        {"managed_by": publisher.MANAGED_BY}
                    ).encode(),
                    "stale.txt": b"must disappear",
                }
                self.deleted = []
                self.commit_calls = 0

            def repo_exists(self, **_):
                return True

            def list_repo_files(self, **_):
                return sorted(self.remote)

            def create_commit(self, operations, **_):
                self.commit_calls += 1
                for operation in operations:
                    if isinstance(operation, CommitOperationDelete):
                        self.deleted.append(operation.path_in_repo)
                        self.remote.pop(operation.path_in_repo)
                    else:
                        self.remote[operation.path_in_repo] = (
                            operation.path_or_fileobj.getvalue()
                        )
                return types.SimpleNamespace(oid="b" * 40)

            def repo_info(self, **_):
                return types.SimpleNamespace(sha="b" * 40)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = tmp_path / "payload"
            payload.mkdir()
            (payload / "publication-manifest.json").write_text(
                json.dumps({"managed_by": publisher.MANAGED_BY}),
                encoding="utf-8",
            )
            (payload / "leaderboard.json").write_text(
                '{"eligible_model_submissions":0}\n',
                encoding="utf-8",
            )
            api = FakeApi()
            downloads = tmp_path / "downloads"
            downloads.mkdir()

            def hf_hub_download(filename, **_):
                target = downloads / filename.replace("/", "__")
                target.write_bytes(api.remote[filename])
                return str(target)

            fake_hub = types.ModuleType("huggingface_hub")
            fake_hub.CommitOperationAdd = CommitOperationAdd
            fake_hub.CommitOperationDelete = CommitOperationDelete
            fake_hub.hf_hub_download = hf_hub_download

            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
                revision, files, action, inventory = (
                    publisher._publish_and_readback(
                        api,
                        "SZLHOLDINGS/governed-agent-bench",
                        "dataset",
                        payload,
                        "test-token",
                    )
                )

        self.assertEqual(revision, "b" * 40)
        self.assertEqual(action, "published")
        self.assertEqual(api.commit_calls, 1)
        self.assertEqual(api.deleted, ["stale.txt"])
        self.assertEqual(inventory, sorted(api.remote))
        self.assertNotIn("stale.txt", inventory)
        self.assertEqual(set(files), set(inventory))

    def test_remote_publication_refuses_foreign_repository(self):
        publisher = _load_publisher()

        class FakeApi:
            @staticmethod
            def repo_exists(**_):
                return True

            @staticmethod
            def list_repo_files(**_):
                return ["publication-manifest.json"]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = tmp_path / "payload"
            payload.mkdir()
            (payload / "publication-manifest.json").write_text(
                json.dumps({"managed_by": publisher.MANAGED_BY}),
                encoding="utf-8",
            )
            foreign = tmp_path / "foreign.json"
            foreign.write_text(
                '{"managed_by":"another/repository"}',
                encoding="utf-8",
            )

            fake_hub = types.ModuleType("huggingface_hub")
            fake_hub.CommitOperationAdd = object
            fake_hub.CommitOperationDelete = object
            fake_hub.hf_hub_download = lambda **_: str(foreign)

            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
                with self.assertRaisesRegex(
                    publisher.PublicationError,
                    "foreign dataset repository",
                ):
                    publisher._publish_and_readback(
                        FakeApi(),
                        "SZLHOLDINGS/governed-agent-bench",
                        "dataset",
                        payload,
                        "test-token",
                    )

    def test_anonymous_repository_readback_is_exact_and_public(self):
        publisher = _load_publisher()
        expected = {
            "README.md": b"public\n",
            "publication-manifest.json": b'{"managed_by":"x"}\n',
        }
        revision = "c" * 40
        info = {
            "private": False,
            "sha": revision,
            "siblings": [{"rfilename": name} for name in expected],
        }

        def fetch_bytes(url: str):
            name = url.rsplit("/", 1)[-1]
            return 200, expected[name]

        result = publisher._verify_public_repository(
            "SZLHOLDINGS/governed-agent-bench",
            "dataset",
            revision,
            expected,
            fetch_json=lambda _url: info,
            fetch_bytes=fetch_bytes,
        )
        self.assertEqual(set(result["files"]), set(expected))

        private_info = dict(info, private=True)
        with self.assertRaisesRegex(
            publisher.PublicationError, "public visibility"
        ):
            publisher._verify_public_repository(
                "SZLHOLDINGS/governed-agent-bench",
                "dataset",
                revision,
                expected,
                fetch_json=lambda _url: private_info,
                fetch_bytes=fetch_bytes,
            )

    def test_space_waits_for_exact_running_revision_and_public_root(self):
        publisher = _load_publisher()
        expected = {"README.md": b"space\n"}
        revision = "d" * 40
        states = iter(
            [
                {
                    "private": False,
                    "sha": revision,
                    "siblings": [{"rfilename": "README.md"}],
                    "runtime": {"stage": "RUNNING_BUILDING", "sha": "e" * 40},
                    "subdomain": "szlholdings-governed-agent-bench",
                },
                {
                    "private": False,
                    "sha": revision,
                    "siblings": [{"rfilename": "README.md"}],
                    "runtime": {"stage": "RUNNING", "sha": revision},
                    "subdomain": "szlholdings-governed-agent-bench",
                },
            ]
        )

        def fetch_bytes(url: str):
            if url.endswith(".hf.space/"):
                return 200, b"<html>running</html>"
            return 200, expected["README.md"]

        result = publisher._wait_for_public_space(
            "SZLHOLDINGS/governed-agent-bench",
            revision,
            expected,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
            fetch_json=lambda _url: next(states),
            fetch_bytes=fetch_bytes,
            sleep=lambda _seconds: None,
            monotonic=lambda: 0.0,
        )
        self.assertEqual(result["runtime"]["stage"], "RUNNING")
        self.assertEqual(result["runtime"]["sha"], revision)
        self.assertEqual(result["runtime"]["http_status"], 200)

    def test_workflow_scopes_hf_token_to_the_publish_step(self):
        workflow = (
            HERE.parents[1] / ".github" / "workflows" / "governed-agent-bench.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count("HF_TOKEN:"), 1)
        self.assertIn(
            "- name: Publish and read back immutable revisions\n"
            "        env:\n"
            "          HF_TOKEN:",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
