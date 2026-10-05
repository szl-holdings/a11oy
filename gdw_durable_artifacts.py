#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: hash-bound reconstruction and private publication of GDW artifacts.

Restored database paths stay logical identities. This module never edits a row,
receipt, original bucket object, or signed payload. Reconstruction proves the
retained payload produces the already recorded bytes; it does not claim that the
original external artifact was captured.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from typing import Any, Callable, Mapping
import uuid

from gdw_durable_runtime import DurableStorageUnavailable, _private_directory


OBJECT_PREFIX = "a11oy/durable-artifacts/v1"
LOGICAL_ROOTS = {
    "proof_export": Path("/data/a11oy/gdw/proofs"),
    "receipt_projection": Path("/data/a11oy/gdw/receipts"),
}
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


# Closed descriptive codes only: no paths, payloads, provider text or retry authority.
ARTIFACT_FAILURE_CODES = frozenset({
    "ARTIFACT_ADAPTER_REQUIRED",
    "ARTIFACT_CACHE_IDENTITY_MISMATCH",
    "ARTIFACT_CACHE_MATERIALIZATION_UNAVAILABLE",
    "ARTIFACT_CACHE_PATH_INVALID",
    "ARTIFACT_DATABASE_OPEN_UNAVAILABLE",
    "ARTIFACT_DEADLINE_EXCEEDED",
    "ARTIFACT_DIGEST_INVALID",
    "ARTIFACT_IDENTITY_INVALID",
    "ARTIFACT_LIFECYCLE_INVALID",
    "ARTIFACT_NATIVE_BINDING_INVALID",
    "ARTIFACT_NATIVE_BINDING_UNAVAILABLE",
    "ARTIFACT_PATH_INVALID",
    "ARTIFACT_PATH_UNADMITTED",
    "ARTIFACT_PERSISTENCE_UNAVAILABLE",
    "ARTIFACT_PROVIDER_CALL_UNAVAILABLE",
    "ARTIFACT_PROVIDER_READBACK_UNAVAILABLE",
    "ARTIFACT_PUBLICATION_UNVERIFIED",
    "ARTIFACT_RECONSTRUCTION_MISMATCH",
    "ARTIFACT_RECORD_INVALID",
    "ARTIFACT_ROOT_INVALID",
    "ARTIFACT_ROOT_UNADMITTED",
    "ARTIFACT_ROW_READ_UNAVAILABLE",
    "ARTIFACT_ROW_VALIDATION_UNAVAILABLE",
    "ARTIFACT_SCHEMA_VALIDATION_UNAVAILABLE",
})


class _ArtifactValidationBlocked(DurableStorageUnavailable):
    """A source-authored validation failure, distinct from provider exceptions."""


def _preparation_diagnostic(error: Exception, boundary: str) -> str:
    if type(error) is _ArtifactValidationBlocked:
        args = BaseException.args.__get__(error)
        if (type(args) is tuple and len(args) == 1 and type(args[0]) is str
                and args[0] in ARTIFACT_FAILURE_CODES):
            return args[0]
    return boundary if boundary in ARTIFACT_FAILURE_CODES else "ARTIFACT_PERSISTENCE_UNAVAILABLE"


def _deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise _ArtifactValidationBlocked("ARTIFACT_DEADLINE_EXCEEDED")


def _json(value: Any) -> dict:
    def invalid_constant(_value):
        raise ValueError("nonfinite")

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    if type(value) is not str or len(value.encode()) > MAX_ARTIFACT_BYTES:
        raise _ArtifactValidationBlocked("ARTIFACT_RECORD_INVALID")
    result = json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if type(result) is not dict:
        raise _ArtifactValidationBlocked("ARTIFACT_RECORD_INVALID")
    return result


class ArtifactCache:
    def __init__(self, directory: Path, publish: Callable,
                 logical_roots: Mapping[str, Path] | None = None):
        self.directory = _private_directory(directory)
        self.publish = publish
        roots = dict(LOGICAL_ROOTS if logical_roots is None else logical_roots)
        if set(roots) != set(LOGICAL_ROOTS) or not callable(publish):
            raise _ArtifactValidationBlocked("ARTIFACT_ADAPTER_REQUIRED")
        self.roots = {kind: Path(root) for kind, root in roots.items()}
        if len(set(self.roots.values())) != 2 or any(
            not root.is_absolute() or root.resolve() != root for root in self.roots.values()
        ):
            raise _ArtifactValidationBlocked("ARTIFACT_ROOT_INVALID")
        for kind in self.roots:
            (self.directory / kind).mkdir(mode=0o700, exist_ok=True)
            _private_directory(self.directory / kind)
        self.last_report = {"verified_count": 0, "reconstructed_count": 0}

    def local_root(self, logical_root: Path) -> Path:
        for kind, root in self.roots.items():
            if Path(logical_root) == root:
                return self.directory / kind
        raise _ArtifactValidationBlocked("ARTIFACT_ROOT_UNADMITTED")

    def resolve(self, logical_path: Path) -> Path:
        path = Path(logical_path)
        if not path.is_absolute() or path.resolve() != path:
            raise _ArtifactValidationBlocked("ARTIFACT_PATH_INVALID")
        for kind, root in self.roots.items():
            if path.parent.parent == root:
                if (not re.fullmatch(r"[0-9a-f]{32}", path.parent.name)
                        or not re.fullmatch(r"[0-9a-f]{64}\.json", path.name)):
                    break
                return self.directory / kind / path.parent.name / path.name
        raise _ArtifactValidationBlocked("ARTIFACT_PATH_UNADMITTED")

    @staticmethod
    def object_path(logical_path: Path, digest: str) -> str:
        if not HEX64.fullmatch(digest):
            raise _ArtifactValidationBlocked("ARTIFACT_DIGEST_INVALID")
        path_digest = hashlib.sha256(str(logical_path).encode()).hexdigest()
        return f"{OBJECT_PREFIX}/{path_digest}/{digest}.json"

    def _materialize(self, logical_path: Path, encoded: bytes) -> tuple[Path, bool]:
        path = self.resolve(logical_path)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        if path.parent.resolve() != path.parent:
            raise _ArtifactValidationBlocked("ARTIFACT_CACHE_PATH_INVALID")
        if os.path.lexists(path):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                        or stream.read(MAX_ARTIFACT_BYTES + 1) != encoded):
                    raise _ArtifactValidationBlocked("ARTIFACT_CACHE_IDENTITY_MISMATCH")
            return path, False
        temporary = path.parent / (".restore-" + uuid.uuid4().hex)
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path, follow_symlinks=False)
        finally:
            temporary.unlink(missing_ok=True)
        return path, True

    def prepare(self, database: Path, deadline: float) -> dict[str, Any]:
        """Bind every retained exported artifact before acknowledging its DB."""
        from gdw_workspace import (
            GDWWorkspace, _canonical_timestamp, _exported_effect_lifecycle,
            _EXPORTED_EFFECT_COMPACTED,
        )

        report = {"verified_count": 0, "reconstructed_count": 0,
                  "reconstruction": "RECONSTRUCTED_FROM_RETAINED_PAYLOAD"}
        pending = {}
        connection = None
        boundary = "ARTIFACT_DATABASE_OPEN_UNAVAILABLE"
        try:
            connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            _deadline(deadline)
            boundary = "ARTIFACT_SCHEMA_VALIDATION_UNAVAILABLE"
            workspace = GDWWorkspace.__new__(GDWWorkspace)
            workspace.database_generation_id = GDWWorkspace._validate_schema(connection)
            for table in ("effect_outbox", "proof_outbox"):
                boundary = "ARTIFACT_ROW_READ_UNAVAILABLE"
                for item in connection.execute(f"SELECT * FROM {table} WHERE status='EXPORTED'"):
                    _deadline(deadline)
                    boundary = "ARTIFACT_ROW_VALIDATION_UNAVAILABLE"
                    row = dict(item)
                    if table == "effect_outbox":
                        state, errors = _exported_effect_lifecycle(row)
                        if errors:
                            raise _ArtifactValidationBlocked("ARTIFACT_LIFECYCLE_INVALID")
                        if state == _EXPORTED_EFFECT_COMPACTED:
                            continue
                        kind, identity = row["kind"], row["intent_sha256"]
                    else:
                        if row["payload_json"] is None and row["artifact_json"] is None:
                            if workspace._compacted_proof_errors(row):
                                raise _ArtifactValidationBlocked("ARTIFACT_LIFECYCLE_INVALID")
                            continue
                        created, errors = _canonical_timestamp(row["created_at"], "created")
                        exported, export_errors = _canonical_timestamp(row["exported_at"], "exported")
                        if errors or export_errors or exported < created or row["tombstoned_at"] is not None:
                            raise _ArtifactValidationBlocked("ARTIFACT_LIFECYCLE_INVALID")
                        kind, identity = "proof_export", row["payload_sha256"]
                    payload, artifact = _json(row["payload_json"]), _json(row["artifact_json"])
                    if table == "effect_outbox":
                        if workspace._connection_effect_binding_errors(connection, {**row, "payload": payload}):
                            raise _ArtifactValidationBlocked("ARTIFACT_NATIVE_BINDING_INVALID")
                    elif workspace._legacy_proof_payload_errors(row, payload):
                        raise _ArtifactValidationBlocked("ARTIFACT_NATIVE_BINDING_INVALID")
                    scope = hashlib.sha256(row["owner_id"].encode()).hexdigest()[:32]
                    if kind not in self.roots or not HEX64.fullmatch(identity):
                        raise _ArtifactValidationBlocked("ARTIFACT_IDENTITY_INVALID")
                    logical_path = self.roots[kind] / scope / (identity + ".json")
                    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
                    digest = hashlib.sha256(encoded).hexdigest()
                    if (len(encoded) > MAX_ARTIFACT_BYTES
                            or artifact.get("path") != str(logical_path)
                            or artifact.get("artifact_identity") != identity
                            or artifact.get("owner_scope") != scope
                            or artifact.get("immutable") is not True
                            or artifact.get("sha256") != digest
                            or ("size" in artifact and (type(artifact["size"]) is not int
                                                       or artifact["size"] != len(encoded)))):
                        raise _ArtifactValidationBlocked("ARTIFACT_RECONSTRUCTION_MISMATCH")
                    boundary = "ARTIFACT_CACHE_MATERIALIZATION_UNAVAILABLE"
                    physical_path, reconstructed = self._materialize(logical_path, encoded)
                    boundary = "ARTIFACT_NATIVE_BINDING_UNAVAILABLE"
                    if GDWWorkspace.artifact_binding_errors(
                        {"kind": kind, "owner_id": row["owner_id"], "intent_sha256": identity},
                        artifact, physical_path=physical_path,
                    ):
                        raise _ArtifactValidationBlocked("ARTIFACT_NATIVE_BINDING_INVALID")
                    object_path = self.object_path(logical_path, digest)
                    pending[object_path] = (physical_path, digest, len(encoded))
                    report["reconstructed_count"] += int(reconstructed)
                    boundary = "ARTIFACT_ROW_READ_UNAVAILABLE"
            # Validate all retained rows before making any provider call. A bad
            # later row cannot cause partial publication of an unqualified set.
            for object_path, (physical_path, digest, size) in pending.items():
                _deadline(deadline)
                boundary = "ARTIFACT_PROVIDER_CALL_UNAVAILABLE"
                result = self.publish(physical_path, object_path, digest, deadline)
                boundary = "ARTIFACT_PROVIDER_READBACK_UNAVAILABLE"
                _deadline(deadline)
                if (not isinstance(result, Mapping) or result.get("path") != object_path
                        or result.get("sha256") != digest or result.get("size") != size
                        or not HEX64.fullmatch(str(result.get("xet_hash") or ""))):
                    raise _ArtifactValidationBlocked("ARTIFACT_PUBLICATION_UNVERIFIED")
                report["verified_count"] += 1
            _deadline(deadline)
            self.last_report = report
            return dict(report)
        except Exception as error:
            raise DurableStorageUnavailable(_preparation_diagnostic(error, boundary)) from None
        finally:
            if connection is not None:
                connection.close()
