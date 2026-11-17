#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline manifest-to-observation-bundle import; no provider or signing access."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from szl_evidence_receipts import (  # noqa: E402
    MAX_BUNDLE_BYTES,
    MAX_BUNDLE_EDGES,
    MAX_RECEIPT_BYTES,
    build_bundle,
    decode_bundle,
    import_receipt,
    strict_json,
)

MANIFEST_SCHEMA = "szl.evidence-import-manifest/v1"
_FIELDS = {"path", "expected_sha256", "artifact_uri", "kind", "observed_at"}


def _read(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("local input exceeds the size bound")
    return raw


def _local_path(value: str, base: Path) -> Path:
    if not isinstance(value, str) or not value or "://" in value or value.startswith(("\\\\", "//")):
        raise ValueError("receipt path must identify a local file")
    path = Path(value)
    return path if path.is_absolute() else base / path


def import_manifest(manifest_path: Path, output_path: Path) -> dict:
    base = Path.cwd()
    manifest_path = _local_path(os.fspath(manifest_path), base)
    output_path = _local_path(os.fspath(output_path), base)
    manifest = strict_json(_read(manifest_path, MAX_BUNDLE_BYTES))
    if (
        not isinstance(manifest, dict) or set(manifest) != {"schema", "receipts"}
        or manifest["schema"] != MANIFEST_SCHEMA or not isinstance(manifest["receipts"], list)
        or not 1 <= len(manifest["receipts"]) <= MAX_BUNDLE_EDGES
    ):
        raise ValueError("invalid bounded receipt-import manifest")
    inputs = []
    edges = []
    for item in manifest["receipts"]:
        if not isinstance(item, dict) or set(item) != _FIELDS:
            raise ValueError("invalid manifest receipt fields")
        path = _local_path(item["path"], manifest_path.parent)
        inputs.append(path.resolve())
        edges.append(import_receipt(
            _read(path, MAX_RECEIPT_BYTES),
            expected_sha256=item["expected_sha256"], artifact_uri=item["artifact_uri"],
            kind=item["kind"], observed_at=item["observed_at"],
        ))
    if output_path.resolve() in {manifest_path.resolve(), *inputs}:
        raise ValueError("output must not replace a receipt or manifest")
    bundle = build_bundle(edges)
    raw = json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8") + b"\n"
    decode_bundle(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".receipt-bundle-", suffix=".tmp", dir=output_path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        bundle = import_manifest(args.manifest, args.output)
    except (OSError, ValueError, TypeError):
        print("RECEIPT_IMPORT_REJECTED: local input or observation contract invalid", file=sys.stderr)
        return 2
    print(json.dumps({
        "state": "OBSERVED", "signature_status": "UNSIGNED",
        "edge_count": len(bundle["edges"]), "digest_sha256": bundle["digest_sha256"],
        "execution_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
