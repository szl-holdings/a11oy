#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Validate a content-addressed payload shared by two repository checkouts.

The manifest is deliberately small and explicit.  Its raw bytes are the
content address carried by coordinated PR bodies; every listed file must then
match its declared digest in both repositories.  No branch name or mutable PR
head is treated as payload identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


MANIFEST_REL = PurePosixPath(".github/shared-source-payload-manifest.json")
SCHEMA = "szl-shared-source-payload/v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
PAYLOAD_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")


class DuplicateKeyError(ValueError):
    """Raised when a JSON object repeats a key."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(root: Path) -> Path:
    return root.joinpath(*MANIFEST_REL.parts)


def _load_manifest(root: Path) -> tuple[bytes, dict[str, Any]]:
    path = _manifest_path(root)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"regular manifest file is required: {path}")
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise ValueError(f"manifest is not strict UTF-8 JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("manifest root must be an object")
    expected_keys = ["files", "payload_id", "schema"]
    if list(document) != expected_keys:
        raise ValueError(f"manifest keys must be exactly {expected_keys} in canonical order")
    if document["schema"] != SCHEMA:
        raise ValueError(f"manifest schema must be {SCHEMA}")
    if not isinstance(document["payload_id"], str) or not PAYLOAD_ID_RE.fullmatch(document["payload_id"]):
        raise ValueError("payload_id must be a lowercase stable identifier")
    files = document["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("manifest files must be a non-empty object")
    if list(files) != sorted(files):
        raise ValueError("manifest file paths must be sorted")
    for relative, digest in files.items():
        if not isinstance(relative, str) or not relative:
            raise ValueError("manifest file paths must be non-empty strings")
        if "\\" in relative:
            raise ValueError(f"manifest path must use POSIX separators: {relative}")
        normalized = PurePosixPath(relative)
        if normalized.is_absolute() or normalized.as_posix() != relative:
            raise ValueError(f"manifest path must be normalized and relative: {relative}")
        if any(part in {"", ".", ".."} for part in normalized.parts):
            raise ValueError(f"manifest path traversal is forbidden: {relative}")
        if normalized.parts[0] == ".git":
            raise ValueError(f"manifest cannot address Git metadata: {relative}")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"manifest digest must be lowercase SHA-256: {relative}")
    return raw, document


def _payload_path(root: Path, relative: str) -> Path:
    return root.joinpath(*PurePosixPath(relative).parts)


def validate(self_root: Path, sibling_root: Path, expected_manifest_sha256: str) -> int:
    if not SHA256_RE.fullmatch(expected_manifest_sha256):
        print("::error::expected manifest digest must be 64 lowercase hexadecimal characters", file=sys.stderr)
        return 2
    try:
        self_raw, manifest = _load_manifest(self_root)
        sibling_raw, _ = _load_manifest(sibling_root)
    except (OSError, ValueError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    if self_raw != sibling_raw:
        print("::error::shared payload manifests are not byte-identical", file=sys.stderr)
        return 1
    actual_manifest_sha256 = _sha256(self_raw)
    if actual_manifest_sha256 != expected_manifest_sha256:
        print(
            "::error::shared payload manifest digest does not match the PR-body content address\n"
            f"expected: {expected_manifest_sha256}\nactual:   {actual_manifest_sha256}",
            file=sys.stderr,
        )
        return 1

    failures: list[str] = []
    for relative, expected_file_sha256 in manifest["files"].items():
        for label, root in (("self", self_root), ("sibling", sibling_root)):
            path = _payload_path(root, relative)
            if not path.is_file() or path.is_symlink():
                failures.append(f"{label}:{relative}: regular file is missing")
                continue
            actual_file_sha256 = _file_sha256(path)
            if actual_file_sha256 != expected_file_sha256:
                failures.append(
                    f"{label}:{relative}: expected {expected_file_sha256}, got {actual_file_sha256}"
                )
    if failures:
        for failure in failures:
            print(f"::error::{failure}", file=sys.stderr)
        return 1

    print(f"payload_id={manifest['payload_id']}")
    print(f"manifest_sha256={actual_manifest_sha256}")
    print(f"files_verified={len(manifest['files'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("self_root", type=Path)
    parser.add_argument("sibling_root", type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    return validate(args.self_root, args.sibling_root, args.expected_manifest_sha256)


if __name__ == "__main__":
    raise SystemExit(main())
