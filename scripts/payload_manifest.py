#!/usr/bin/env python3
"""Build or verify deterministic SHA-256 manifests for payload directories."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(root: Path, output: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    output = output.resolve()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == output:
            continue

        rel = path.relative_to(root).as_posix()
        files.append(
            {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    return files


def build_manifest(root: Path, output: Path) -> dict[str, object]:
    files = collect_files(root, output)
    aggregate_input = "\n".join(
        f"{entry['path']}\0{entry['size']}\0{entry['sha256']}" for entry in files
    ).encode("utf-8")

    return {
        "manifestVersion": 1,
        "payloadRoot": root.name,
        "generator": "scripts/payload_manifest.py",
        "fileCount": len(files),
        "aggregateSha256": hashlib.sha256(aggregate_input).hexdigest(),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    root = args.payload_dir.resolve()
    output = args.output.resolve()
    manifest = build_manifest(root, output)
    serialized = json.dumps(manifest, indent=2, sort_keys=False) + "\n"

    if args.verify:
        existing = output.read_text(encoding="utf-8")
        if existing != serialized:
            rel_output = output.relative_to(Path.cwd()) if output.is_relative_to(Path.cwd()) else output
            print(f"Payload manifest is stale: {rel_output}")
            print(
                "Run: python3 scripts/payload_manifest.py "
                f"{args.payload_dir} --output {args.output}"
            )
            return 1
        print(f"Verified payload manifest: {output.relative_to(Path.cwd())}")
        return 0

    output.write_text(serialized, encoding="utf-8")
    print(f"Wrote payload manifest: {output.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
