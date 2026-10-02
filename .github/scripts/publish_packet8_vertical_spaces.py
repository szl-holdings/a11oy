#!/usr/bin/env python3
"""Inventory preserved Packet 8 sources after retiring their Hub writer.

The old workflow and its create/upload path have been removed. This compatible
CLI emits a local source-file receipt only; it never opens a network client or
claims that any Hugging Face Space has been deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

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

    archives = []
    for slug in ARCHIVED_SOURCE_SLUGS:
        folder = root / "huggingface" / "spaces" / slug
        if not folder.is_dir() or folder.is_symlink():
            raise RuntimeError(f"archived source folder unavailable: {slug}")
        files = []
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"archived source symlink refused: {slug}")
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            raw = path.read_bytes()
            files.append({
                "path": path.relative_to(folder).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
        if not files:
            raise RuntimeError(f"archived source folder is empty: {slug}")
        archives.append({"space_id": f"SZLHOLDINGS/{slug}", "files": files})

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
