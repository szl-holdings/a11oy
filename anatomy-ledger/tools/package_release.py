#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Create a deterministic source package without caches or ingested evidence."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

BASE = Path(__file__).resolve().parents[1]


def package(output):
    files = {}
    for name in (
        "README.md",
        "server.py",
        "Makefile",
        "toolchain-lock.json",
        "public",
        "policy",
        "tools",
        "tests",
        "evidence/README.md",
    ):
        source = BASE / name
        for path in [source] if source.is_file() else sorted(source.rglob("*")):
            if (
                not path.is_file()
                or path.is_symlink()
                or "__pycache__" in path.parts
                or path.suffix == ".pyc"
            ):
                continue
            files[path.relative_to(BASE).as_posix()] = path.read_bytes()
    # Operator evidence must never be redistributed in a source release.
    files["public/data/ledger.json"] = (
        json.dumps(
            {
                "schema": "szl.anatomy.ledger.v1",
                "generatedAt": None,
                "recordCount": 0,
                "outcomes": {"ALLOW": 0, "REVIEW": 0, "BLOCK": 0},
                "chainRoot": None,
                "records": [],
                "disclosure": "Release package starts empty; operator evidence is not distributed.",
            },
            indent=2,
        )
        + "\n"
    ).encode()
    manifest = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }
    files["MANIFEST.sha256.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    ).encode()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        output.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, io.BytesIO(data))
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{sha}  {output.name}\n", encoding="utf-8"
    )
    return {
        "artifact": str(output),
        "sha256": sha,
        "fileCount": len(files),
        "attestation": "NOT_CREATED_LOCALLY",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(BASE / "dist/anatomy-ledger.tar.gz"))
    args = parser.parse_args()
    print(json.dumps(package(args.output), indent=2))


if __name__ == "__main__":
    main()
