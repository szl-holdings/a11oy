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


def _write_manifested_payload(
    payload: Path,
    publisher,
    *,
    repo_type: str = "dataset",
    repo_id: str = "SZLHOLDINGS/governed-agent-bench",
    source_revision: str = "a" * 40,
) -> None:
    payload.mkdir()
    (payload / "leaderboard.json").write_text(
        '{"eligible_model_submissions":0}\n',
        encoding="utf-8",
    )
    files = [
        {
            "path": "leaderboard.json",
            "bytes": (payload / "leaderboard.json").stat().st_size,
            "sha256": hashlib.sha256(
                (payload / "leaderboard.json").read_bytes()
            ).hexdigest(),
        }
    ]
    (payload / "publication-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": publisher.MANIFEST_SCHEMA,
                "managed_by": publisher.MANAGED_BY,
                "repo_type": repo_type,
                "repo_id": repo_id,
                "source_revision": source_revision,
                "observed_at": "2026-07-28T12:00:00Z",
                "files": files,
            }
        ),
        encoding="utf-8",
    )


class PublicationTests(unittest.TestCase):
    def test_bundle_is_hash_closed_and_truth_labeled(self):
        builder = _load_builder()
        publisher = _load_publisher()
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
            publisher._require_bundle_source(
                output / "dataset",
                output / "space",
                "a" * 40,
            )

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
            self.assertEqual(
                requirements,
                "--only-binary=:all:\ngradio==6.20.0\n",
            )

    def test_bundle_rebuild_is_identical_for_same_source_metadata(self):
        builder = _load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            for output in (first, second):
                builder.build(
                    output,
                    "a" * 40,
                    "2026-07-28T12:00:00Z",
                )

            def snapshot(folder):
                return {
                    path.relative_to(folder).as_posix(): path.read_bytes()
                    for path in sorted(folder.rglob("*"))
                    if path.is_file()
                }

            self.assertEqual(snapshot(first), snapshot(second))

    def test_invalid_source_revision_fails_closed(self):
        builder = _load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(builder.PublicationBuildError):
                builder.build(Path(tmp), "main", "2026-07-28T12:00:00Z")

    def test_bundle_source_must_match_supplied_protected_revision(self):
        publisher = _load_publisher()
        supplied = "9" * 40
        stale = "a" * 40
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            dataset = bundle / "dataset"
            space = bundle / "space"
            dataset.mkdir()
            space.mkdir()
            (dataset / "publication-manifest.json").write_text(
                json.dumps({"source_revision": supplied}),
                encoding="utf-8",
            )
            (space / "publication-manifest.json").write_text(
                json.dumps({"source_revision": supplied}),
                encoding="utf-8",
            )
            (space / "publication.json").write_text(
                json.dumps({"source_revision": stale}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                publisher.PublicationError,
                "source revision mismatch",
            ):
                publisher._require_bundle_source(dataset, space, supplied)


    def test_publish_job_has_no_manual_path_and_is_non_cancelable(self):
        workflow = (
            HERE.parents[1] / ".github" / "workflows" / "governed-agent-bench.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('"LICENSE"', workflow)
        self.assertIn(
            ".github/requirements/governed-agent-bench-publish.txt",
            workflow,
        )
        self.assertIn("--require-hashes", workflow)

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
                        {
                            "schema_version": publisher.MANIFEST_SCHEMA,
                            "managed_by": publisher.MANAGED_BY,
                            "repo_type": "dataset",
                            "repo_id": "SZLHOLDINGS/governed-agent-bench",
                        }
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
            _write_manifested_payload(payload, publisher)
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
                        "a" * 40,
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
            _write_manifested_payload(payload, publisher)
            foreign = tmp_path / "foreign.json"
            foreign.write_text(
                json.dumps(
                    {
                        "schema_version": publisher.MANIFEST_SCHEMA,
                        "managed_by": "another/repository",
                        "repo_type": "dataset",
                        "repo_id": "SZLHOLDINGS/governed-agent-bench",
                    }
                ),
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
                        "a" * 40,
                        "test-token",
                    )

    def test_local_manifest_must_bind_source_and_target(self):
        publisher = _load_publisher()
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload"
            _write_manifested_payload(payload, publisher)
            with self.assertRaisesRegex(
                publisher.PublicationError,
                "source_revision mismatch",
            ):
                publisher._manifest_is_bound(
                    publisher._files(payload),
                    "SZLHOLDINGS/governed-agent-bench",
                    "dataset",
                    "b" * 40,
                )

    def test_space_source_binding_requires_exact_publication_identity(self):
        publisher = _load_publisher()
        source_revision = "a" * 40
        dataset_revision = "b" * 40
        expected = {
            "publication.json": json.dumps(
                {
                    "source_revision": source_revision,
                    "dataset_revision": dataset_revision,
                }
            ).encode(),
            "leaderboard.json": json.dumps(
                {"source_revision": source_revision}
            ).encode(),
        }
        binding = publisher._space_source_binding(
            expected,
            source_revision,
            dataset_revision,
        )
        self.assertEqual(
            binding["verified_by"],
            "ANONYMOUS_EXACT_SPACE_FILE_READBACK",
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

        def fetch_bytes(url: str, _timeout_seconds: float):
            name = url.rsplit("/", 1)[-1]
            return 200, expected[name]

        result = publisher._verify_public_repository(
            "SZLHOLDINGS/governed-agent-bench",
            "dataset",
            revision,
            expected,
            fetch_json=lambda _url, _timeout: info,
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
                fetch_json=lambda _url, _timeout: private_info,
                fetch_bytes=fetch_bytes,
            )

    def test_space_waits_for_exact_running_revision_and_public_root(self):
        publisher = _load_publisher()
        expected = {"README.md": b"space\n"}
        revision = "d" * 40

        def fetch_bytes(url: str, _timeout_seconds: float):
            if url.endswith(".hf.space/config"):
                return (
                    200,
                    json.dumps(
                        {
                            "mode": "blocks",
                            "title": "Governed Agent Bench",
                            "components": [
                                {
                                    "type": "json",
                                    "props": {
                                        "label": "Immutable publication identity",
                                        "value": {
                                            "source_revision": source_revision,
                                            "dataset_revision": dataset_revision,
                                        },
                                    },
                                }
                            ],
                        }
                    ).encode(),
                )
            if url.endswith(".hf.space/"):
                return 200, b"<html>running</html>"
            return 200, expected[url.rsplit("/", 1)[-1]]

        source_revision = "f" * 40
        dataset_revision = "a" * 40
        expected["publication.json"] = json.dumps(
            {
                "source_revision": source_revision,
                "dataset_revision": dataset_revision,
            }
        ).encode()
        states = iter(
            [
                {
                    "private": False,
                    "sha": revision,
                    "siblings": [{"rfilename": name} for name in expected],
                    "runtime": {"stage": "RUNNING_BUILDING", "sha": "e" * 40},
                    "subdomain": "szlholdings-governed-agent-bench",
                },
                {
                    "private": False,
                    "sha": revision,
                    "siblings": [{"rfilename": name} for name in expected],
                    "runtime": {"stage": "RUNNING", "sha": revision},
                    "subdomain": "szlholdings-governed-agent-bench",
                },
            ]
        )
        result = publisher._wait_for_public_space(
            "SZLHOLDINGS/governed-agent-bench",
            revision,
            expected,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
            fetch_json=lambda _url, _timeout: next(states),
            fetch_bytes=fetch_bytes,
            sleep=lambda _seconds: None,
            monotonic=lambda: 0.0,
        )
        self.assertEqual(result["runtime"]["stage"], "RUNNING")
        self.assertEqual(result["runtime"]["sha"], revision)
        self.assertEqual(result["runtime"]["http_status"], 200)
        self.assertEqual(
            result["runtime"]["identity"]["source_revision"],
            source_revision,
        )
        self.assertEqual(
            result["runtime"]["identity"]["dataset_revision"],
            dataset_revision,
        )

    def test_space_ignores_terminal_failure_from_stale_runtime_revision(self):
        publisher = _load_publisher()
        revision = "1" * 40
        source_revision = "2" * 40
        dataset_revision = "4" * 40
        expected = {
            "README.md": b"space\n",
            "publication.json": json.dumps(
                {
                    "source_revision": source_revision,
                    "dataset_revision": dataset_revision,
                }
            ).encode(),
        }
        states = iter(
            [
                {
                    "private": False,
                    "sha": revision,
                    "siblings": [{"rfilename": name} for name in expected],
                    "runtime": {"stage": "RUNTIME_ERROR", "sha": "3" * 40},
                    "subdomain": "szlholdings-governed-agent-bench",
                },
                {
                    "private": False,
                    "sha": revision,
                    "siblings": [{"rfilename": name} for name in expected],
                    "runtime": {"stage": "RUNNING", "sha": revision},
                    "subdomain": "szlholdings-governed-agent-bench",
                },
            ]
        )

        def fetch_bytes(url: str, _timeout_seconds: float):
            if url.endswith(".hf.space/config"):
                return 200, json.dumps(
                    {
                        "mode": "blocks",
                        "title": "Governed Agent Bench",
                        "components": [
                            {
                                "type": "json",
                                "props": {
                                    "label": "Immutable publication identity",
                                    "value": {
                                        "source_revision": source_revision,
                                        "dataset_revision": dataset_revision,
                                    },
                                }
                            }
                        ],
                    }
                ).encode()
            if url.endswith(".hf.space/"):
                return 200, b"<html>running</html>"
            name = url.rsplit("/", 1)[-1]
            return 200, expected[name]

        result = publisher._wait_for_public_space(
            "SZLHOLDINGS/governed-agent-bench",
            revision,
            expected,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
            fetch_json=lambda _url, _timeout: next(states),
            fetch_bytes=fetch_bytes,
            sleep=lambda _seconds: None,
            monotonic=lambda: 0.0,
        )
        self.assertEqual(result["runtime"]["sha"], revision)

    def test_space_rejects_terminal_failure_from_new_runtime_revision(self):
        publisher = _load_publisher()
        revision = "7" * 40
        with self.assertRaisesRegex(
            publisher.PublicationError,
            "terminal failure stage",
        ):
            publisher._wait_for_public_space(
                "SZLHOLDINGS/governed-agent-bench",
                revision,
                {
                    "publication.json": json.dumps(
                        {
                            "source_revision": "8" * 40,
                            "dataset_revision": "9" * 40,
                        }
                    ).encode()
                },
                timeout_seconds=1.0,
                poll_interval_seconds=0.0,
                fetch_json=lambda _url, _timeout: {
                    "runtime": {"stage": "BUILD_ERROR", "sha": revision}
                },
                fetch_bytes=lambda _url, _timeout: (200, b"unused"),
                sleep=lambda _seconds: None,
                monotonic=lambda: 0.0,
            )

    def test_dataset_public_readback_retries_eventual_consistency(self):
        publisher = _load_publisher()
        revision = "4" * 40
        expected = {"README.md": b"dataset\n"}
        calls = {"count": 0}

        def fetch_json(_url: str, _timeout_seconds: float):
            calls["count"] += 1
            return {
                "private": False,
                "sha": "5" * 40 if calls["count"] == 1 else revision,
                "siblings": [{"rfilename": "README.md"}],
            }

        result = publisher._wait_for_public_repository(
            "SZLHOLDINGS/governed-agent-bench",
            "dataset",
            revision,
            expected,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
            fetch_json=fetch_json,
            fetch_bytes=lambda _url, _timeout: (200, expected["README.md"]),
            sleep=lambda _seconds: None,
            monotonic=lambda: 0.0,
        )
        self.assertEqual(set(result["files"]), {"README.md"})
        self.assertEqual(calls["count"], 2)

    def test_space_identity_endpoint_must_match_application_and_source(self):
        publisher = _load_publisher()
        source_revision = "6" * 40
        dataset_revision = "7" * 40
        with self.assertRaisesRegex(
            publisher.PublicationError,
            "expected application identity",
        ):
            publisher._validate_space_identity(
                json.dumps(
                    {
                        "mode": "blocks",
                        "components": [
                            {"props": {"value": source_revision}}
                        ],
                    }
                ).encode(),
                source_revision,
                dataset_revision,
            )

    def test_space_identity_endpoint_requires_exact_dataset_revision(self):
        publisher = _load_publisher()
        source_revision = "6" * 40
        dataset_revision = "7" * 40
        with self.assertRaisesRegex(
            publisher.PublicationError,
            "exact published dataset revision",
        ):
            publisher._validate_space_identity(
                json.dumps(
                    {
                        "mode": "blocks",
                        "title": "Governed Agent Bench",
                        "components": [
                            {
                                "type": "json",
                                "props": {
                                    "label": "Immutable publication identity",
                                    "value": {
                                        "source_revision": source_revision,
                                        "dataset_revision": "8" * 40,
                                    },
                                }
                            }
                        ],
                    }
                ).encode(),
                source_revision,
                dataset_revision,
            )

    def test_space_retries_stale_identity_until_revision_tuple_matches(self):
        publisher = _load_publisher()
        revision = "b" * 40
        source_revision = "c" * 40
        dataset_revision = "e" * 40
        expected = {
            "README.md": b"space\n",
            "publication.json": json.dumps(
                {
                    "source_revision": source_revision,
                    "dataset_revision": dataset_revision,
                }
            ).encode(),
        }
        config_calls = {"count": 0}

        def fetch_bytes(url: str, _timeout_seconds: float):
            if url.endswith(".hf.space/config"):
                config_calls["count"] += 1
                observed_dataset = (
                    "d" * 40 if config_calls["count"] == 1 else dataset_revision
                )
                return 200, json.dumps(
                    {
                        "mode": "blocks",
                        "title": "Governed Agent Bench",
                        "components": [
                            {
                                "type": "json",
                                "props": {
                                    "label": "Immutable publication identity",
                                    "value": {
                                        "source_revision": source_revision,
                                        "dataset_revision": observed_dataset,
                                    },
                                }
                            }
                        ],
                    }
                ).encode()
            if url.endswith(".hf.space/"):
                return 200, b"<html>running</html>"
            return 200, expected[url.rsplit("/", 1)[-1]]

        result = publisher._wait_for_public_space(
            "SZLHOLDINGS/governed-agent-bench",
            revision,
            expected,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
            fetch_json=lambda _url, _timeout: {
                "private": False,
                "sha": revision,
                "siblings": [{"rfilename": name} for name in expected],
                "runtime": {"stage": "RUNNING", "sha": revision},
                "subdomain": "szlholdings-governed-agent-bench",
            },
            fetch_bytes=fetch_bytes,
            sleep=lambda _seconds: None,
            monotonic=lambda: 0.0,
        )

        self.assertEqual(config_calls["count"], 2)
        self.assertEqual(
            result["runtime"]["identity"]["source_revision"],
            source_revision,
        )
        self.assertEqual(
            result["runtime"]["identity"]["dataset_revision"],
            dataset_revision,
        )

    def test_public_readback_caps_every_request_to_remaining_deadline(self):
        publisher = _load_publisher()
        revision = "e" * 40
        expected = {
            "README.md": b"one\n",
            "publication-manifest.json": b"two\n",
        }
        observed_timeouts = []
        clock = iter([0.0, 0.5, 9.5, 10.0])

        def fetch_json(_url: str, timeout_seconds: float):
            observed_timeouts.append(timeout_seconds)
            return {
                "private": False,
                "sha": revision,
                "siblings": [{"rfilename": name} for name in expected],
            }

        def fetch_bytes(url: str, timeout_seconds: float):
            observed_timeouts.append(timeout_seconds)
            return 200, expected[url.rsplit("/", 1)[-1]]

        with self.assertRaisesRegex(
            publisher.PublicationError,
            "deadline exhausted",
        ):
            publisher._verify_public_repository(
                "SZLHOLDINGS/governed-agent-bench",
                "dataset",
                revision,
                expected,
                fetch_json=fetch_json,
                fetch_bytes=fetch_bytes,
                deadline=10.0,
                monotonic=lambda: next(clock),
            )

        self.assertEqual(observed_timeouts, [10.0, 0.5])

    def test_space_refuses_root_or_config_returned_after_deadline(self):
        publisher = _load_publisher()
        revision = "a" * 40
        source_revision = "b" * 40
        dataset_revision = "c" * 40
        publication = json.dumps(
            {
                "source_revision": source_revision,
                "dataset_revision": dataset_revision,
            }
        ).encode()
        expected = {"publication.json": publication}

        for expires_on in ("root", "config"):
            with self.subTest(expires_on=expires_on):
                clock = {"now": 0.0}
                config_calls = {"count": 0}

                def fetch_bytes(url: str, _timeout_seconds: float):
                    if url.endswith(".hf.space/config"):
                        config_calls["count"] += 1
                        if expires_on == "config":
                            clock["now"] = 2.0
                        return 200, json.dumps(
                            {
                                "mode": "blocks",
                                "title": "Governed Agent Bench",
                                "components": [
                                    {
                                        "type": "json",
                                        "props": {
                                            "label": "Immutable publication identity",
                                            "value": {
                                                "source_revision": source_revision,
                                                "dataset_revision": dataset_revision,
                                            },
                                        },
                                    }
                                ],
                            }
                        ).encode()
                    if url.endswith(".hf.space/"):
                        if expires_on == "root":
                            clock["now"] = 2.0
                        return 200, b"<html>running</html>"
                    return 200, publication

                with self.assertRaisesRegex(
                    publisher.PublicationError,
                    "deadline exhausted",
                ):
                    publisher._wait_for_public_space(
                        "SZLHOLDINGS/governed-agent-bench",
                        revision,
                        expected,
                        timeout_seconds=1.0,
                        poll_interval_seconds=0.0,
                        fetch_json=lambda _url, _timeout: {
                            "private": False,
                            "sha": revision,
                            "siblings": [
                                {"rfilename": "publication.json"}
                            ],
                            "runtime": {
                                "stage": "RUNNING",
                                "sha": revision,
                            },
                            "subdomain": "szlholdings-governed-agent-bench",
                        },
                        fetch_bytes=fetch_bytes,
                        sleep=lambda _seconds: None,
                        monotonic=lambda: clock["now"],
                    )

                if expires_on == "root":
                    self.assertEqual(config_calls["count"], 0)
                else:
                    self.assertEqual(config_calls["count"], 1)

    def test_publish_job_timeout_covers_publication_deadlines(self):
        workflow = (
            HERE.parents[1] / ".github" / "workflows" / "governed-agent-bench.yml"
        ).read_text(encoding="utf-8")
        publish_job = workflow.split("\n  publish:\n", maxsplit=1)[1]
        self.assertIn("timeout-minutes: 30", publish_job)

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

    def test_space_failure_writes_recoverable_partial_receipt(self):
        publisher = _load_publisher()

        def fake_publish(
            _api,
            _repo_id,
            repo_type,
            _folder,
            _source_revision,
            _token,
            on_revision=None,
        ):
            if repo_type == "dataset":
                if on_revision is not None:
                    on_revision("b" * 40, "published")
                return (
                    "b" * 40,
                    {"leaderboard.json": {"bytes": 1, "sha256": "0" * 64}},
                    "published",
                    ["leaderboard.json"],
                )
            raise publisher.PublicationError("space failed closed")

        fake_hub = types.ModuleType("huggingface_hub")
        fake_hub.HfApi = lambda token: object()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            _load_builder().build(
                bundle,
                "a" * 40,
                "2026-07-28T12:00:00Z",
            )
            receipt_path = root / "publication-receipt.json"
            with (
                patch.dict(sys.modules, {"huggingface_hub": fake_hub}),
                patch.dict(publisher.os.environ, {"HF_TOKEN": "test-token"}),
                patch.object(
                    publisher,
                    "_publish_and_readback",
                    side_effect=fake_publish,
                ),
                patch.object(
                    publisher,
                    "_wait_for_public_repository",
                    return_value={"files": {}},
                ),
            ):
                with self.assertRaises(publisher.PublicationError):
                    publisher.publish(
                        bundle,
                        "a" * 40,
                        "SZLHOLDINGS/governed-agent-bench",
                        "SZLHOLDINGS/governed-agent-bench",
                        receipt_path,
                        0.0,
                        0.0,
                    )

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["status"],
                "PARTIAL_PUBLICATION_FAILED_CLOSED",
            )
            self.assertEqual(receipt["publication_state"], "NOT_LIVE")
            self.assertEqual(receipt["dataset"]["revision"], "b" * 40)
            self.assertEqual(receipt["failure"]["stage"], "space_publication")


if __name__ == "__main__":
    unittest.main()
