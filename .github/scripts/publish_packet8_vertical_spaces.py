#!/usr/bin/env python3
"""Inventory preserved Packet 8 sources after retiring their Hub writer.

The old workflow and its create/upload path have been removed. This compatible
CLI emits a local source-file receipt only; it never opens a network client or
claims that any Hugging Face Space has been deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

SPACES = []
RETIRED_SPACE_IDS = frozenset({
    "SZLHOLDINGS/aegis-assurance",
    "SZLHOLDINGS/terra-assurance",
    "SZLHOLDINGS/puriq-markets",
    "SZLHOLDINGS/counsel-assurance",
})
ARCHIVED_SOURCE_SLUGS = (
    "aegis-assurance",
    "terra-assurance",
    "puriq-markets",
    "counsel-assurance",
)
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


def source_receipt(root: Path, source_sha: str) -> dict:
    if not SHA40.fullmatch(source_sha) or source_sha == "0" * 40:
        raise ValueError("source_sha must be an exact nonzero 40-hex Git revision")
    if SPACES or RETIRED_SPACE_IDS != {
        f"SZLHOLDINGS/{slug}" for slug in ARCHIVED_SOURCE_SLUGS
    }:
        raise RuntimeError("Packet 8 writer inventory is no longer retired")

    root = root.resolve()
    def git(*args: str) -> bytes:
        try:
            return subprocess.run(
                ["git", *args], cwd=root, check=True, capture_output=True,
            ).stdout
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("archived Git revision unavailable") from exc

    if Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
        raise RuntimeError("root must be the Git repository top level")
    if git("cat-file", "-t", source_sha).strip() != b"commit":
        raise RuntimeError("source_sha must name a Git commit")
    archive_bytes = git(
        "archive", "--format=tar", source_sha,
        *(f"huggingface/spaces/{slug}" for slug in ARCHIVED_SOURCE_SLUGS),
    )
    files_by_slug: dict[str, list[dict]] = {
        slug: [] for slug in ARCHIVED_SOURCE_SLUGS
    }
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive:
            if member.isdir():
                continue
            parts = PurePosixPath(member.name).parts
            if (not member.isfile() or len(parts) < 4
                    or parts[:2] != ("huggingface", "spaces")
                    or parts[2] not in files_by_slug):
                raise RuntimeError("archived source contains an unexpected entry")
            raw_file = archive.extractfile(member)
            if raw_file is None:
                raise RuntimeError("archived source file unavailable")
            raw = raw_file.read()
            files_by_slug[parts[2]].append({
                "path": PurePosixPath(*parts[3:]).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })

    archives = []
    for slug, files in files_by_slug.items():
        if not files:
            raise RuntimeError(f"archived source folder is empty: {slug}")
        archives.append({
            "space_id": f"SZLHOLDINGS/{slug}",
            "files": sorted(files, key=lambda item: item["path"]),
        })

    return {
        "schema": "szl.packet8-source-archive/v1",
        "source_sha": source_sha,
        "state": "WRITER_RETIRED",
        "archives": archives,
        "active_space_writers": 0,
        "provider_mutations": 0,
        "provider_deletion_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    receipt = source_receipt(Path(args.root).resolve(), args.source_sha)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": receipt["state"],
        "source_sha": receipt["source_sha"],
        "archives": len(receipt["archives"]),
        "provider_mutations": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
