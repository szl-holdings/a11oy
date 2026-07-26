from __future__ import annotations

from pathlib import Path

from scripts.verify_hf_snapshot_restore import (
    build_manifest,
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
