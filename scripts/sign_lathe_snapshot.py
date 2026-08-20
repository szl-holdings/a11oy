#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sign a validated One Lathe snapshot with real Sigstore keyless DSSE.

This command is intentionally CI-only.  It requires an ambient OIDC identity,
validates the snapshot contract and canonical digest, and refuses to emit a
placeholder when real Fulcio/Rekor signing is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lathe_snapshot as lathe  # noqa: E402
from szl_formulas import DsseSigningUnavailable, dsse_envelope_real  # noqa: E402


PAYLOAD_TYPE = "application/vnd.szl.lathe.snapshot.v1+json"
SUBJECT_NAME = "szl-one-lathe-program-snapshot"
RECEIPT_SUBJECT_SCHEMA = "szl.lathe.receipt-subject.v1"
ARTIFACT_PATH = "artifacts/lathe/program-snapshot.v1.json"
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GIT_SHA_RE = re.compile(r"^[a-f0-9]{40}$")


class LatheSigningError(ValueError):
    """The snapshot is not safe or eligible to be signed as a subject."""


def _read_regular_file(path: Path, *, max_bytes: int = MAX_SNAPSHOT_BYTES) -> bytes:
    """Read one bounded regular file without following a final symlink."""

    try:
        named_before = os.lstat(path)
    except OSError as exc:
        raise LatheSigningError(f"cannot inspect snapshot path: {path}") from exc
    if stat.S_ISLNK(named_before.st_mode):
        raise LatheSigningError("snapshot path may not be a symbolic link")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise LatheSigningError(f"cannot open snapshot as a regular file: {path}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise LatheSigningError("snapshot must be a regular file")
        if before.st_size > max_bytes:
            raise LatheSigningError(f"snapshot exceeds the {max_bytes}-byte limit")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        body = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(body) > max_bytes:
            raise LatheSigningError(f"snapshot exceeds the {max_bytes}-byte limit")
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise LatheSigningError("snapshot changed while it was being read")
        try:
            named_after = os.lstat(path)
        except OSError as exc:
            raise LatheSigningError("snapshot path changed while it was being read") from exc
        if (named_before.st_dev, named_before.st_ino) != (
            named_after.st_dev,
            named_after.st_ino,
        ) or (before.st_dev, before.st_ino) != (
            named_after.st_dev,
            named_after.st_ino,
        ):
            raise LatheSigningError("snapshot path identity changed while it was being read")
        return body
    finally:
        os.close(descriptor)


def load_validated_snapshot(path: Path) -> dict[str, Any]:
    """Validate schema, canonical digest, and fail-closed candidate state."""

    raw = _read_regular_file(path)
    try:
        snapshot = json.loads(raw, object_pairs_hook=lathe._json_object)
    except (json.JSONDecodeError, UnicodeDecodeError, lathe.LatheSnapshotError) as exc:
        raise LatheSigningError("snapshot is not valid duplicate-free UTF-8 JSON") from exc
    if not isinstance(snapshot, dict):
        raise LatheSigningError("snapshot root must be a JSON object")

    schema_path = REPO_ROOT / "schemas" / "lathe" / "program-snapshot.v1.schema.json"
    schema = json.loads(_read_regular_file(schema_path))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(snapshot), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        where = ".".join(map(str, first.absolute_path)) or "<root>"
        raise LatheSigningError(f"snapshot schema validation failed at {where}: {first.message}")

    digest_body = {
        key: value for key, value in snapshot.items() if key not in {"generatedAt", "digest"}
    }
    expected = lathe.canonical_digest(digest_body)
    if snapshot.get("digest") != expected:
        raise LatheSigningError("snapshot digest does not match its canonical subject")
    if snapshot.get("promotionEligible") is not False:
        raise LatheSigningError("candidate signing cannot promote a snapshot")
    binding = snapshot.get("receiptBinding") or {}
    if binding.get("state") == "BOUND":
        raise LatheSigningError("refusing to re-sign a receipt-bound derivative view")
    return snapshot


def canonical_snapshot_bytes(snapshot: dict[str, Any]) -> bytes:
    return lathe.canonical_json_bytes(snapshot)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def receipt_subject(
    snapshot: dict[str, Any],
    *,
    repository: str,
    source_revision: str,
    workflow_identity: str,
    artifact_path: str = ARTIFACT_PATH,
) -> dict[str, Any]:
    """Build the provenance-bound object whose bytes are signed by Sigstore."""

    if not _REPOSITORY_RE.fullmatch(repository):
        raise LatheSigningError("repository must be an owner/name identifier")
    if not _GIT_SHA_RE.fullmatch(source_revision):
        raise LatheSigningError("source revision must be a full lowercase git SHA")
    expected_identity = (
        f"https://github.com/{repository}/.github/workflows/"
        "one-lathe-receipt.yml@refs/heads/main"
    )
    if workflow_identity != expected_identity:
        raise LatheSigningError("workflow identity is not the pinned main-branch signer")
    if artifact_path != ARTIFACT_PATH:
        raise LatheSigningError("artifact path is not the pinned One Lathe snapshot")
    return {
        "schemaVersion": RECEIPT_SUBJECT_SCHEMA,
        "snapshot": snapshot,
        "provenance": {
            "repository": repository,
            "sourceRevision": source_revision,
            "workflowIdentity": workflow_identity,
            "artifactPath": artifact_path,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        default=str(REPO_ROOT / "artifacts" / "lathe" / "program-snapshot.v1.json"),
    )
    parser.add_argument(
        "--out-dir", default=str(REPO_ROOT / "attestations" / "lathe")
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--workflow-identity", required=True)
    parser.add_argument("--artifact-path", default=ARTIFACT_PATH)
    args = parser.parse_args(argv)

    try:
        snapshot = load_validated_snapshot(Path(args.snapshot))
        subject = receipt_subject(
            snapshot,
            repository=args.repository,
            source_revision=args.source_revision,
            workflow_identity=args.workflow_identity,
            artifact_path=args.artifact_path,
        )
        payload = lathe.canonical_json_bytes(subject)
        payload_digest = hashlib.sha256(payload).hexdigest()
        envelope = dsse_envelope_real(
            payload,
            PAYLOAD_TYPE,
            subject_name=SUBJECT_NAME,
        )
        if envelope.get("_mode") != "SIGSTORE-KEYLESS":
            raise LatheSigningError("signer did not return a real Sigstore keyless envelope")
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{payload_digest}.dsse.json"
        _atomic_write_json(out_path, envelope)
    except DsseSigningUnavailable as exc:
        print(f"[lathe-sign] REFUSED: real Sigstore signing unavailable: {exc}", file=sys.stderr)
        return 2
    except (OSError, LatheSigningError, lathe.LatheSnapshotError) as exc:
        print(f"[lathe-sign] REFUSED: {exc}", file=sys.stderr)
        return 1

    print(f"[lathe-sign] snapshot_digest={snapshot['digest']}")
    print(f"[lathe-sign] payload_sha256={payload_digest}")
    print(f"[lathe-sign] wrote={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
