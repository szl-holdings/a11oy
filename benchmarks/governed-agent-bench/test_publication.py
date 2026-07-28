"""Network-free tests for the Hub publication bundle."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


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


class _FakeAdd:
    def __init__(self, path_in_repo: str, path_or_fileobj: io.BytesIO):
        self.path_in_repo = path_in_repo
        self.path_or_fileobj = path_or_fileobj


class _FakeDelete:
    def __init__(self, path_in_repo: str):
        self.path_in_repo = path_in_repo


class _FakeApi:
    def __init__(self, files: dict[str, bytes], download_root: Path):
        self.files = dict(files)
        self.download_root = download_root

    def create_repo(self, **_kwargs):
        return None

    def list_repo_files(self, **_kwargs):
        return sorted(self.files)

    def create_commit(self, operations, **_kwargs):
        for operation in operations:
            if isinstance(operation, _FakeDelete):
                self.files.pop(operation.path_in_repo, None)
            elif isinstance(operation, _FakeAdd):
                self.files[operation.path_in_repo] = operation.path_or_fileobj.getvalue()
            else:
                raise AssertionError(f"unknown fake operation: {type(operation)!r}")
        return SimpleNamespace(oid="b" * 40)


@contextmanager
def _fake_hub_module(api: _FakeApi):
    module = types.ModuleType("huggingface_hub")
    module.CommitOperationAdd = _FakeAdd
    module.CommitOperationDelete = _FakeDelete

    def download(filename: str, **_kwargs):
        target = api.download_root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(api.files[filename])
        return str(target)

    module.hf_hub_download = download
    previous = sys.modules.get("huggingface_hub")
    sys.modules["huggingface_hub"] = module
    try:
        yield
    finally:
        if previous is None:
            sys.modules.pop("huggingface_hub", None)
        else:
            sys.modules["huggingface_hub"] = previous


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
                self.assertEqual(
                    (folder / ".gitattributes").read_text(encoding="utf-8"),
                    "* text=auto eol=lf\n",
                )
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

    def test_publish_deletes_stale_files_and_verifies_exact_inventory(self):
        builder = _load_builder()
        publisher = _load_publisher()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            builder.build(bundle, "a" * 40, "2026-07-28T12:00:00Z")
            expected = {
                path.relative_to(bundle / "dataset").as_posix(): path.read_bytes()
                for path in (bundle / "dataset").rglob("*")
                if path.is_file()
            }
            api = _FakeApi(
                {
                    ".gitattributes": b"old attributes\n",
                    "README.md": b"old readme\n",
                    "stale/removed.json": b"must be deleted\n",
                },
                root / "downloads",
            )
            with _fake_hub_module(api):
                revision, observed = publisher._publish_and_readback(
                    api,
                    "SZLHOLDINGS/governed-agent-bench",
                    "dataset",
                    bundle / "dataset",
                    "token",
                )
            self.assertEqual(revision, "b" * 40)
            self.assertEqual(api.files, expected)
            self.assertEqual(set(observed), set(expected))

    def test_publish_rejects_unexpected_post_commit_file(self):
        builder = _load_builder()
        publisher = _load_publisher()

        class InjectingApi(_FakeApi):
            def create_commit(self, operations, **kwargs):
                result = super().create_commit(operations, **kwargs)
                self.files["unexpected.txt"] = b"platform drift\n"
                return result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            builder.build(bundle, "a" * 40, "2026-07-28T12:00:00Z")
            api = InjectingApi({}, root / "downloads")
            with _fake_hub_module(api):
                with self.assertRaisesRegex(
                    publisher.PublicationError, "immutable inventory mismatch"
                ):
                    publisher._publish_and_readback(
                        api,
                        "SZLHOLDINGS/governed-agent-bench",
                        "dataset",
                        bundle / "dataset",
                        "token",
                    )


if __name__ == "__main__":
    unittest.main()
