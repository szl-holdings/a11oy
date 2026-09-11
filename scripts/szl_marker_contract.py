"""Narrow image-marker derivation for an explicitly reviewed controller upgrade.

This code does not patch source files or publish HF artifacts. Integrate it into
an admitted new revision of the EXISTING Dockerfile controller. The presently
inspected controller must not be assumed to accept tracked-marker overrides.
Only Lyte's verified tracked UNAVAILABLE sentinel is eligible; arbitrary file
or content replacement is refused. Both original and derived bytes are bound.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping
from szl_release_guard import ContractError, sha

REPOSITORY = "szl-holdings/lyte-services"
PATH = "source_revision.txt"
SENTINEL = b"UNAVAILABLE\n"
SENTINEL_BLOB = "6f49dab0816c681d2c8a35bda5d13ab59d4b26fe"
SCHEMA = "szl.generated-lyte-source-marker/v1"


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def derive_marker(*, repository: str, path: str, original_bytes: bytes,
                  original_blob: str, admitted_source: str,
                  docker_copy_includes_marker: bool) -> dict[str, Any]:
    """Derive one admitted-source marker; never generalize into arbitrary overrides."""
    sha(admitted_source); sha(original_blob)
    if repository != REPOSITORY or path != PATH:
        raise ContractError("MARKER_TARGET_NOT_ALLOWLISTED")
    if docker_copy_includes_marker is not True:
        raise ContractError("MARKER_NOT_IN_DERIVED_COPY_CLOSURE")
    if (original_bytes != SENTINEL or original_blob != SENTINEL_BLOB
            or git_blob(original_bytes) != original_blob):
        raise ContractError("TRACKED_MARKER_SENTINEL_MISMATCH")
    content = (admitted_source + "\n").encode("ascii")
    return {"schema": SCHEMA, "repository": repository, "path": path,
            "source_revision": admitted_source, "original_git_blob_sha1": original_blob,
            "generated_content_utf8": content.decode("ascii"),
            "git_blob_sha1": git_blob(content), "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content), "source_path": path,
            "derivation": "EXACT_ADMITTED_SOURCE_SHA_PLUS_NEWLINE",
            "tracked_source_modified": False, "signature_verified": False}


def verify_marker(record: Mapping[str, Any], published_bytes: bytes, source: str) -> bool:
    """Verify the actual published/image file, not an environment-variable claim."""
    try:
        sha(source)
        expected = derive_marker(repository=record["repository"], path=record["path"],
                                 original_bytes=SENTINEL, original_blob=record["original_git_blob_sha1"],
                                 admitted_source=source, docker_copy_includes_marker=True)
        return (dict(record) == expected and published_bytes == (source+"\n").encode("ascii")
                and hashlib.sha256(published_bytes).hexdigest() == record["sha256"])
    except (KeyError, TypeError, ValueError):
        return False
