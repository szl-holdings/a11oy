#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bind the shipped civilian package's exact bytes; no signature or model claim."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    package = root / "civilian_observatory"
    entries = {}
    for path in sorted(package.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name == "PAYLOAD_MANIFEST.json":
            continue
        if path.is_symlink() or path.suffix in {".pyc", ".sqlite3"} or ".sqlite3-" in path.name:
            raise ValueError("Unexpected cache, executable cache, or link in release package")
        entries[path.relative_to(package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema": "szl.civilian.payload.v1", "version": "0.2.0", "files": entries,
            "trust": "UNSIGNED_SOURCE_HASHES", "model_loaded": False, "external_effectors": []}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    destination = ROOT / "civilian_observatory" / "PAYLOAD_MANIFEST.json"
    if args.check:
        if destination.read_text(encoding="utf-8") != expected:
            raise SystemExit("Civilian package manifest differs from the exact source/static files")
        print("Civilian payload byte manifest verified; no independent identity or execution attestation.")
    else:
        destination.write_text(expected, encoding="utf-8")
        print(f"Wrote {len(build()['files'])} admitted file digests")
