from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_hf_snapshot_restore import (
    build_manifest,
    download_snapshot_files,
    restore_archive,
    verify_local_snapshot,
)


def test_snapshot_archive_restores_byte_exact_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    (source / "README.md").write_bytes(b"# exact backup\n")
    (source / "nested" / "payload.bin").write_bytes(bytes(range(256)))
    (source / ".cache" / "huggingface").mkdir(parents=True)
    (source / ".cache" / "huggingface" / "metadata").write_text("ignored")

    result = verify_local_snapshot(source, tmp_path / "work", "fixture")

    assert result["restore_match"] is True
    assert result["file_count"] == 2
    assert result["total_bytes"] == len(b"# exact backup\n") + 256


def test_restore_replaces_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "only.txt").write_text("canonical", encoding="utf-8")
    workspace = tmp_path / "work"
    result = verify_local_snapshot(source, workspace, "fixture")
    restored = workspace / "restored" / "fixture"
    (restored / "stale.txt").write_text("remove me", encoding="utf-8")

    restore_archive(Path(result["archive"]), restored)

    assert build_manifest(restored) == build_manifest(source)
    assert not (restored / "stale.txt").exists()


class _FakeApi:
    def __init__(self, files: list[str]) -> None:
        self.files = files

    def list_repo_files(self, **_: object) -> list[str]:
        return self.files


def test_download_snapshot_files_is_complete_and_sequential(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    payloads = {
        "README.md": b"# Space\n",
        "nested/app.py": b"print('ready')\n",
    }
    calls: list[str] = []

    def download_file(*, filename: str, **_: object) -> str:
        calls.append(filename)
        cached = cache / filename.replace("/", "--")
        cached.write_bytes(payloads[filename])
        return str(cached)

    source = tmp_path / "snapshot"
    files = download_snapshot_files(
        _FakeApi(list(reversed(payloads))),
        "SZLHOLDINGS/example",
        "a" * 40,
        source,
        "not-logged",
        download_file,
    )

    assert files == sorted(payloads)
    assert calls == sorted(payloads)
    assert (source / "README.md").read_bytes() == payloads["README.md"]
    assert (source / "nested" / "app.py").read_bytes() == payloads["nested/app.py"]


def test_download_snapshot_files_rejects_empty_or_unsafe_listing(
    tmp_path: Path,
) -> None:
    def unused_download(**_: object) -> str:
        raise AssertionError("download must not run")

    with pytest.raises(RuntimeError, match="returned no files"):
        download_snapshot_files(
            _FakeApi([]), "SZLHOLDINGS/empty", "b" * 40,
            tmp_path / "empty", "not-logged", unused_download,
        )

    with pytest.raises(RuntimeError, match="unsafe Hub path"):
        download_snapshot_files(
            _FakeApi(["../escape"]), "SZLHOLDINGS/unsafe", "c" * 40,
            tmp_path / "unsafe", "not-logged", unused_download,
        )
