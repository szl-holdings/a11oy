# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: bounded, cooperative fencing for acknowledged private snapshots.

This protocol core is not wired into the production entrypoint. Admission still
requires verified recovery data, the exact private provider metadata, local
POSIX database storage, and every database writer using the same transaction
gate. It cannot constrain a legacy writer that never reads the fence.

The existing private evidence dataset holds only a small, allowlisted manifest.
Database bytes remain in the existing private evidence bucket under new object
identities. A commit is acknowledged only after immutable readback and current
ownership verification. An uncertain provider outcome poisons the local writer;
it is never retried as a fresh transaction or acknowledged optimistically.
"""
from __future__ import annotations

import hashlib
import base64
import contextlib
import json
import logging
import math
import os
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

SCHEMA = "szl.gdw-durable-store-head/v1"
SPACE = "SZLHOLDINGS/a11oy"
DATASET = "SZLHOLDINGS/szl-evidence"
BUCKET = "SZLHOLDINGS/szl-evidence"
HEAD_PATH = "a11oy/durable-store/v1/head.json"
HISTORY_PREFIX = "a11oy/durable-store/v1/history"
ADMISSION_PREFIX = "a11oy/durable-store/v1/admissions"
OBJECT_PREFIX = "a11oy/durable-store/v1/objects"
ARTIFACT_PREFIX = "a11oy/durable-artifacts/v1"
ENDPOINT = "https://huggingface.co"
SDK_VERSION = "1.31.0"
MAX_MANIFEST_BYTES = 16 * 1024
MAX_ADMISSION_BYTES = 512 * 1024
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_RECEIPTS = 1_000_000
MAX_REBASE_ATTEMPTS = 3
MAX_SEQUENCE = 2**63 - 1
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
LABELS = ("gdw", "series_a")
APPLICATION_TABLES = {
    "gdw": {"schema_meta", "usage", "session_state", "requests", "receipts",
            "proof_outbox", "effect_outbox", "effect_recovery_audit"},
    "series_a": {"snapshots", "passports", "passport_executions", "receipts", "events", "metadata"},
}
SERIES_RECEIPT_TYPE = "application/vnd.szl.series-a-receipt.v1+json"


class StorageBlocked(RuntimeError):
    """Only fixed codes cross the storage boundary; never exception details."""

    def __init__(self, code: str):
        self.code = code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) else "STORAGE_UNAVAILABLE"
        super().__init__(self.code)


class ParentConflict(StorageBlocked):
    """The submitted parent CAS was definitively rejected with HTTP 412."""

    def __init__(self):
        super().__init__("PARENT_CONFLICT")


def canonical(value: Any) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False) + "\n").encode()
    except (TypeError, ValueError):
        raise StorageBlocked("INVALID_MANIFEST") from None


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= MAX_SEQUENCE


def _hex(pattern: re.Pattern, value: Any) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _revision(value: Any) -> bool:
    return _hex(HEX40, value) and value != "0" * 40


def _digest(value: Any) -> bool:
    return _hex(HEX64, value) and value != "0" * 64


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StorageBlocked("DUPLICATE_MANIFEST_KEY")
        value[key] = item
    return value


def validate_snapshots(snapshots: Any) -> dict[str, Any]:
    """Validate the exact two-store identity contract independently of HEAD."""
    if type(snapshots) is not dict or set(snapshots) != set(LABELS):
        raise StorageBlocked("INVALID_SNAPSHOT_SET")
    for label in LABELS:
        item = snapshots[label]
        fields = {"path", "size", "sha256", "xet_hash", "generation", "receipt_count",
                  "receipt_sequence", "receipt_head_sha256"}
        if label == "series_a":
            fields.add("receipt_rows_sha256")
        if type(item) is not dict or set(item) != fields:
            raise StorageBlocked("INVALID_SNAPSHOT")
        generation_pattern = HEX32 if label == "gdw" else re.compile(r"store_[0-9a-f]{32}\Z")
        if (not _digest(item["sha256"]) or not _digest(item["xet_hash"])
                or not _integer(item["size"], 1) or item["size"] > MAX_SNAPSHOT_BYTES
                or not _integer(item["receipt_count"]) or not _integer(item["receipt_sequence"])
                or (label == "series_a" and item["receipt_sequence"] < item["receipt_count"])
                or (label == "gdw" and item["receipt_sequence"] != 0)
                or not _hex(HEX64, item["receipt_head_sha256"])
                or not _hex(generation_pattern, item["generation"])
                or item["generation"] == ("0" * 32 if label == "gdw" else "store_" + "0" * 32)):
            raise StorageBlocked("INVALID_SNAPSHOT")
        # Only the native empty Series A chain has an all-zero sentinel. GDW
        # has no global receipt sequence: its head is a nonzero hash of the
        # ordered receipt identities, including for an empty collection.
        empty_series = label == "series_a" and item["receipt_count"] == item["receipt_sequence"] == 0
        if (empty_series and item["receipt_head_sha256"] != "0" * 64) or (
                not empty_series and not _digest(item["receipt_head_sha256"])):
            raise StorageBlocked("INVALID_RECEIPT_HEAD")
        if label == "series_a" and (not _digest(item["receipt_rows_sha256"])
                or (empty_series and item["receipt_rows_sha256"]
                    != sha256(b"szl.series-a-receipt-rows/v1\n"))):
            raise StorageBlocked("INVALID_RECEIPT_ROWS_IDENTITY")
        expected_path = re.compile(re.escape(OBJECT_PREFIX) + r"/[0-9a-f]{32}/"
                                   + label + "-" + item["sha256"] + r"\.sqlite3\Z")
        if not _hex(expected_path, item["path"]):
            raise StorageBlocked("INVALID_SNAPSHOT_PATH")
    return json.loads(canonical(snapshots))


def validate_manifest(value: Any) -> dict[str, Any]:
    """Reject payload fields, paths outside the dedicated prefix and loose types."""
    fields = {"schema", "space", "dataset", "bucket", "operation_id", "writer_id",
              "epoch", "sequence", "kind", "previous_manifest_sha256", "source_revision",
              "qualification_sha256", "snapshots"}
    if type(value) is not dict or set(value) != fields:
        raise StorageBlocked("INVALID_MANIFEST")
    if (value["schema"] != SCHEMA or value["space"] != SPACE or value["dataset"] != DATASET
            or value["bucket"] != BUCKET or not _hex(HEX32, value["operation_id"])
            or value["operation_id"] == "0" * 32 or not _hex(HEX32, value["writer_id"])
            or not _integer(value["epoch"]) or not _integer(value["sequence"])
            or not _revision(value["source_revision"])
            or not _digest(value["qualification_sha256"])):
        raise StorageBlocked("INVALID_MANIFEST")
    if type(value["kind"]) is not str:
        raise StorageBlocked("INVALID_MANIFEST")
    if value["kind"] == "BOOTSTRAP":
        if (value["epoch"] != 0 or value["sequence"] != 0 or value["writer_id"] != "0" * 32
                or value["previous_manifest_sha256"] is not None):
            raise StorageBlocked("INVALID_BOOTSTRAP")
    elif value["kind"] in {"CLAIM", "COMMIT"}:
        if (value["epoch"] < 1 or value["sequence"] < 1 or value["writer_id"] == "0" * 32
                or not _digest(value["previous_manifest_sha256"])):
            raise StorageBlocked("INVALID_MANIFEST")
    else:
        raise StorageBlocked("INVALID_MANIFEST")
    validate_snapshots(value["snapshots"])
    # Return a detached plain object so a caller cannot mutate accepted state.
    rendered = canonical(value)
    if len(rendered) > MAX_MANIFEST_BYTES:
        raise StorageBlocked("MANIFEST_TOO_LARGE")
    return json.loads(rendered)


def parse_manifest(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes or not 1 <= len(data) <= MAX_MANIFEST_BYTES:
        raise StorageBlocked("MANIFEST_TOO_LARGE")
    try:
        value = json.loads(data, object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(StorageBlocked("INVALID_MANIFEST")))
    except (ValueError, UnicodeError, RecursionError):
        raise StorageBlocked("INVALID_MANIFEST") from None
    value = validate_manifest(value)
    if data != canonical(value):
        raise StorageBlocked("NONCANONICAL_MANIFEST")
    return value


@dataclass(frozen=True)
class Head:
    """Exact immutable dataset revision plus canonical manifest bytes."""
    revision: str
    body: bytes

    def __post_init__(self):
        if not _revision(self.revision):
            raise StorageBlocked("INVALID_DATASET_REVISION")
        parse_manifest(self.body)

    @property
    def value(self) -> dict[str, Any]:
        return parse_manifest(self.body)

    @property
    def digest(self) -> str:
        return sha256(self.body)


class FenceBackend(Protocol):
    """Provider boundary: production uses the deadline-isolated worker adapter.

    observe/read_at must check canonical private identity and fetch exact bytes
    at immutable revisions. submit atomically adds a fresh history object and
    replaces HEAD, with parent_commit=expected.revision, create_pr=False, one
    network submission. Only a definite HTTP 412 may raise ParentConflict.
    Every other exception is outcome-uncertain. No operation creates a repo,
    changes visibility, deletes a file, or writes a Space.
    """
    def observe(self, deadline: float) -> Head: ...
    def read_at(self, revision: str, operation_id: str, deadline: float) -> tuple[Head, bytes]: ...
    def history_exists(self, revision: str, operation_id: str, deadline: float) -> bool: ...
    def submit(self, expected: Head, body: bytes, operation_id: str, deadline: float) -> str: ...


class BootstrapBackend(FenceBackend, Protocol):
    def empty_parent(self, deadline: float) -> str: ...
    def admission_exists(self, revision: str, digest: str, deadline: float) -> bool: ...
    def submit_bootstrap(self, parent: str, body: bytes, admission: bytes, deadline: float) -> str: ...
    def read_admission(self, head: Head, deadline: float) -> bytes: ...


def _deadline(deadline: float) -> None:
    if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or not time.monotonic() < deadline):
        raise StorageBlocked("STORAGE_DEADLINE_EXHAUSTED")


def _safe_call(function: Callable, *args: Any) -> Any:
    try:
        return function(*args)
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("STORAGE_OUTCOME_UNCERTAIN") from None


def advance(backend: FenceBackend, expected: Head, proposal: dict[str, Any], deadline: float) -> Head:
    """One logical CAS, with bounded rebase only after definite conflicts.

    Unrelated evidence commits may advance the repository parent. They may not
    change our exact manifest or introduce the operation's history identity.
    An unknown response never triggers another submission, even if a read might
    later show that the commit succeeded. A new process reconciles that state.
    """
    body = canonical(validate_manifest(proposal))
    operation_id = proposal["operation_id"]
    before = expected.value
    if (body == expected.body or proposal["previous_manifest_sha256"] != expected.digest
            or proposal["sequence"] != before["sequence"] + 1
            or proposal["qualification_sha256"] != before["qualification_sha256"]
            or operation_id == before["operation_id"]):
        raise StorageBlocked("INVALID_ADVANCE")
    if proposal["kind"] == "CLAIM":
        if (proposal["epoch"] != before["epoch"] + 1 or proposal["writer_id"] == before["writer_id"]
                or proposal["snapshots"] != before["snapshots"]):
            raise StorageBlocked("INVALID_CLAIM")
    elif proposal["kind"] == "COMMIT":
        if (before["kind"] == "BOOTSTRAP" or proposal["epoch"] != before["epoch"]
                or proposal["writer_id"] != before["writer_id"]
                or proposal["source_revision"] != before["source_revision"]):
            raise StorageBlocked("INVALID_COMMIT")
        for label in LABELS:
            old, new = before["snapshots"][label], proposal["snapshots"][label]
            if new["generation"] != old["generation"]:
                raise StorageBlocked("DATABASE_GENERATION_CHANGED")
            if label == "series_a" and (new["receipt_count"] < old["receipt_count"]
                    or new["receipt_sequence"] < old["receipt_sequence"]):
                raise StorageBlocked("RECEIPT_HISTORY_REGRESSED")
            if label == "series_a":
                added = new["receipt_count"] - old["receipt_count"]
                if ((added == 0 and any(new[key] != old[key] for key in (
                        "receipt_sequence", "receipt_head_sha256", "receipt_rows_sha256")))
                        or (added > 0 and (new["receipt_sequence"] - old["receipt_sequence"] < added
                                           or new["receipt_head_sha256"] == old["receipt_head_sha256"]
                                           or new["receipt_rows_sha256"] == old["receipt_rows_sha256"]))):
                    raise StorageBlocked("RECEIPT_HISTORY_REWRITTEN")
    else:
        raise StorageBlocked("INVALID_ADVANCE")
    parent = expected
    for _ in range(MAX_REBASE_ATTEMPTS):
        _deadline(deadline)
        observed = _safe_call(backend.observe, deadline)
        _deadline(deadline)
        if observed.body != expected.body:
            raise StorageBlocked("WRITER_FENCED")
        parent = observed
        if _safe_call(backend.history_exists, parent.revision, operation_id, deadline):
            raise StorageBlocked("OPERATION_ID_ALREADY_EXISTS")
        _deadline(deadline)
        try:
            revision = _safe_call(backend.submit, parent, body, operation_id, deadline)
        except ParentConflict:
            # Only this definite non-commit outcome can be retried. The next
            # iteration checks exact own bytes at the new immutable parent.
            continue
        _deadline(deadline)
        if not _revision(revision) or revision == parent.revision:
            raise StorageBlocked("COMMIT_IDENTITY_UNVERIFIED")
        committed, history = _safe_call(backend.read_at, revision, operation_id, deadline)
        _deadline(deadline)
        if committed.revision != revision or committed.body != body or history != body:
            raise StorageBlocked("COMMIT_READBACK_MISMATCH")
        current = _safe_call(backend.observe, deadline)
        _deadline(deadline)
        if current.body != body:
            raise StorageBlocked("WRITER_FENCED")
        return committed
    raise StorageBlocked("DATASET_CONTENTION")


def _admission_body(data: bytes, digest: str) -> dict[str, Any]:
    """Reuse the coordinator's one strict metadata schema; no free-form bytes."""
    if type(data) is not bytes or not 1 <= len(data) <= MAX_ADMISSION_BYTES or not _digest(digest):
        raise StorageBlocked("INVALID_STORAGE_ADMISSION")
    try:
        from gdw_durable_startup import parse_admission
        value = parse_admission(data)
        if type(value) is not dict or canonical(value) != data or sha256(data) != digest:
            raise StorageBlocked("STORAGE_ADMISSION_IDENTITY_MISMATCH")
        return value
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("INVALID_STORAGE_ADMISSION") from None


def bootstrap(backend: BootstrapBackend, proposal: dict[str, Any], admission: bytes, deadline: float) -> Head:
    """Create the first HEAD only if it is absent at the exact CAS parent.

    All admitted candidate bytes/artifacts must already have been published and
    read back. This operation adds only validated metadata, never repairs a DB
    or overwrites a prior HEAD. Ambiguity cannot become an automatic retry.
    """
    value = validate_manifest(proposal)
    if value["kind"] != "BOOTSTRAP":
        raise StorageBlocked("INITIAL_BOOTSTRAP_REQUIRED")
    parsed = _admission_body(admission, value["qualification_sha256"])
    try:
        from gdw_durable_startup import validate_bootstrap_binding
        validate_bootstrap_binding(parsed, value)
    except Exception:
        raise StorageBlocked("BOOTSTRAP_ADMISSION_BINDING_FAILED") from None
    body = canonical(value)
    for _ in range(MAX_REBASE_ATTEMPTS):
        _deadline(deadline)
        parent = _safe_call(backend.empty_parent, deadline)
        if not _revision(parent):
            raise StorageBlocked("INVALID_DATASET_REVISION")
        if (_safe_call(backend.history_exists, parent, value["operation_id"], deadline)
                or _safe_call(backend.admission_exists, parent, value["qualification_sha256"], deadline)):
            raise StorageBlocked("BOOTSTRAP_OBJECT_ALREADY_EXISTS")
        _deadline(deadline)
        try:
            revision = _safe_call(backend.submit_bootstrap, parent, body, admission, deadline)
        except ParentConflict:
            continue
        _deadline(deadline)
        if not _revision(revision) or revision == parent:
            raise StorageBlocked("COMMIT_IDENTITY_UNVERIFIED")
        committed, history = _safe_call(backend.read_at, revision, value["operation_id"], deadline)
        if committed.revision != revision or committed.body != body or history != body:
            raise StorageBlocked("COMMIT_READBACK_MISMATCH")
        if _safe_call(backend.read_admission, committed, deadline) != admission:
            raise StorageBlocked("STORAGE_ADMISSION_IDENTITY_MISMATCH")
        current = _safe_call(backend.observe, deadline)
        _deadline(deadline)
        if current.body != body:
            raise StorageBlocked("WRITER_FENCED")
        return committed
    raise StorageBlocked("DATASET_CONTENTION")


class Writer:
    """A process may claim once; any failed claim/commit permanently fences it.

    The caller must hold one local process/file lock around all database reads,
    commits, closed native backups, snapshot publication and this call. A
    successful result is permission to acknowledge that exact persisted state,
    not permission to acknowledge later local changes.
    """
    def __init__(self, backend: FenceBackend, source_revision: str, writer_id: str | None = None):
        self.backend = backend
        self.source_revision = source_revision
        self.writer_id = uuid.uuid4().hex if writer_id is None else writer_id
        if not _revision(source_revision) or not _hex(HEX32, self.writer_id) or self.writer_id == "0" * 32:
            raise StorageBlocked("INVALID_WRITER_IDENTITY")
        self.state = "NEW"
        self.head: Head | None = None
        self._lock = threading.RLock()

    def _proposal(self, previous: Head, kind: str) -> dict[str, Any]:
        value = previous.value
        value.update(kind=kind, operation_id=uuid.uuid4().hex, writer_id=self.writer_id,
                     source_revision=self.source_revision, previous_manifest_sha256=previous.digest,
                     sequence=value["sequence"] + 1)
        return value

    def claim(self, restored: Head, deadline: float) -> Head:
        """Claim only the exact head whose complete snapshots were restored."""
        with self._lock:
            if self.state != "NEW":
                raise StorageBlocked("WRITER_CANNOT_RECLAIM")
            self.state = "POISONED"
            proposal = self._proposal(restored, "CLAIM")
            proposal["epoch"] += 1
            self.head = advance(self.backend, restored, proposal, deadline)
            self.state = "ACTIVE"
            return self.head

    def commit(self, snapshots: Mapping[str, Any], deadline: float) -> Head:
        """Publish only already uploaded, readback-verified snapshot identities."""
        with self._lock:
            if self.state != "ACTIVE" or self.head is None:
                raise StorageBlocked("WRITER_NOT_ACTIVE")
            previous = self.head
            self.state = "POISONED"
            proposal = self._proposal(previous, "COMMIT")
            proposal["snapshots"] = dict(snapshots)
            proposal = validate_manifest(proposal)
            self.head = advance(self.backend, previous, proposal, deadline)
            self.state = "ACTIVE"
            return self.head

    def verify_read(self, deadline: float) -> Head:
        """Gate reads after failures and reject a successor's observed epoch."""
        with self._lock:
            if self.state != "ACTIVE" or self.head is None:
                raise StorageBlocked("WRITER_NOT_ACTIVE")
            try:
                _deadline(deadline)
                current = _safe_call(self.backend.observe, deadline)
                _deadline(deadline)
                if current.body != self.head.body:
                    raise StorageBlocked("WRITER_FENCED")
                return self.head
            except Exception:
                self.state = "POISONED"
                raise


def _value(value: Any, key: str, default: Any = None) -> Any:
    return value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)


def bounded_hub_client(*, transport: Any = None) -> Any:
    """Public SDK client factory: bounded reads and single bucket/pause submissions.

    create_commit in the pinned SDK already submits once. Its preupload stage
    may use normal safe metadata retries. Bucket batch calls otherwise retry
    mutations five times; convert their failure outside that retry hierarchy.
    """
    import httpx

    class Client(httpx.Client):
        def request(self, method: str, url: Any, *args: Any, **kwargs: Any) -> Any:
            guarded_write = method.upper() == "POST" and str(url) in {
                f"{ENDPOINT}/api/buckets/{BUCKET}/batch", f"{ENDPOINT}/api/spaces/{SPACE}/pause"}
            if not guarded_write:
                return super().request(method, url, *args, **kwargs)
            try:
                response = super().request(method, url, *args, **kwargs)
            except httpx.HTTPError:
                raise StorageBlocked("STORAGE_OUTCOME_UNCERTAIN") from None
            if not 200 <= response.status_code < 300:
                response.close()
                raise StorageBlocked("STORAGE_OUTCOME_UNCERTAIN")
            return response

    return Client(timeout=20, follow_redirects=False, transport=transport)


def _hub_api(token: str) -> Any:
    import huggingface_hub
    from huggingface_hub import HfApi, set_client_factory
    if huggingface_hub.__version__ != SDK_VERSION or type(token) is not str or not token:
        raise StorageBlocked("QUALIFIED_SDK_AND_TOKEN_REQUIRED")
    set_client_factory(bounded_hub_client)
    return HfApi(endpoint=ENDPOINT, token=token)


class HFDatasetFenceBackend:
    """Worker-side SDK operations; safe metadata writes, never SQL bytes.

    A caller supplies the resource-group observation digest from the reviewed
    admission. A null observation is recorded as unavailable, never claimed to
    establish the bucket and dataset have identical audiences. Their payload
    classes remain separate regardless of resource groups.

    Its socket timeout is an individual-I/O limit. It is not a total wall-clock
    bound; production invokes this adapter through WorkerFenceBackend, whose
    parent process kills an overdue provider operation and refuses to ack.
    """
    def __init__(self, api: Any, private_directory: Path,
                 expected_resource_group_sha256: str, operation_factory: Callable):
        if _value(api, "endpoint") != ENDPOINT or not _digest(expected_resource_group_sha256):
            raise StorageBlocked("UNQUALIFIED_PROVIDER_METADATA")
        directory = _private_directory(private_directory)
        self.api = api
        self.directory = directory
        self.resource_group_sha256 = expected_resource_group_sha256
        self.operation_factory = operation_factory

    @classmethod
    def from_token(cls, token: str, private_directory: Path,
                   expected_resource_group_sha256: str) -> "HFDatasetFenceBackend":
        """Called only during admitted startup, before other SDK worker threads."""
        from huggingface_hub import CommitOperationAdd
        return cls(_hub_api(token), private_directory, expected_resource_group_sha256, CommitOperationAdd)

    def _metadata(self, deadline: float, revision: str = "main") -> str:
        _deadline(deadline)
        info = _safe_call(lambda: self.api.dataset_info(
            DATASET, revision=revision, expand=["sha", "private", "resourceGroup"]))
        _deadline(deadline)
        sha = _value(info, "sha")
        if (_value(info, "id") != DATASET or _value(info, "private") is not True
                or not _revision(sha)
                or sha256(canonical(_value(info, "resource_group"))) != self.resource_group_sha256
                or (revision != "main" and sha != revision)):
            raise StorageBlocked("PRIVATE_DATASET_IDENTITY_CHANGED")
        return sha

    def _paths(self, revision: str, path: str, deadline: float) -> list[Any]:
        _deadline(deadline)
        values = _safe_call(lambda: self.api.get_paths_info(
            DATASET, [path], repo_type="dataset", revision=revision))
        _deadline(deadline)
        if type(values) is not list or len(values) > 1:
            raise StorageBlocked("MANIFEST_IDENTITY_UNAVAILABLE")
        return values

    def _read(self, revision: str, path: str, deadline: float, *, bound: int = MAX_MANIFEST_BYTES) -> bytes:
        items = self._paths(revision, path, deadline)
        if not items:
            raise StorageBlocked("RESTORE_MANIFEST_MISSING")
        item = items[0]
        size, blob_id = _value(item, "size"), _value(item, "blob_id")
        if (_value(item, "path") != path or type(size) is not int
                or not 1 <= size <= bound or not _revision(blob_id)
                or _value(item, "lfs") is not None):
            raise StorageBlocked("MANIFEST_IDENTITY_UNAVAILABLE")
        # An isolated local_dir materializes regular files, not the shared Hub
        # cache's revision symlinks. All reads remain tied to the exact commit.
        directory = self.directory / uuid.uuid4().hex
        directory.mkdir(mode=0o700)
        result = _safe_call(lambda: self.api.hf_hub_download(
            DATASET, filename=path, repo_type="dataset", revision=revision,
            local_dir=directory, cache_dir=self.directory / "hub-cache"))
        _deadline(deadline)
        expected = directory / path
        if type(result) is not str or Path(result) != expected:
            raise StorageBlocked("MANIFEST_DOWNLOAD_PATH_MISMATCH")
        descriptor = os.open(expected, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != size:
                raise StorageBlocked("MANIFEST_DOWNLOAD_SIZE_MISMATCH")
            data = os.read(descriptor, bound + 1)
        finally:
            os.close(descriptor)
        _deadline(deadline)
        if len(data) != size or hashlib.sha1(b"blob " + str(size).encode() + b"\0" + data).hexdigest() != blob_id:
            raise StorageBlocked("MANIFEST_DOWNLOAD_HASH_MISMATCH")
        return data

    def observe(self, deadline: float) -> Head:
        revision = self._metadata(deadline)
        return Head(revision, self._read(revision, HEAD_PATH, deadline))

    def read_at(self, revision: str, operation_id: str, deadline: float) -> tuple[Head, bytes]:
        if not _revision(revision) or not _hex(HEX32, operation_id):
            raise StorageBlocked("INVALID_COMMIT_IDENTITY")
        self._metadata(deadline, revision)
        head = Head(revision, self._read(revision, HEAD_PATH, deadline))
        history = self._read(revision, f"{HISTORY_PREFIX}/{operation_id}.json", deadline)
        return head, history

    def history_exists(self, revision: str, operation_id: str, deadline: float) -> bool:
        if not _revision(revision) or not _hex(HEX32, operation_id):
            raise StorageBlocked("INVALID_COMMIT_IDENTITY")
        return bool(self._paths(revision, f"{HISTORY_PREFIX}/{operation_id}.json", deadline))

    def empty_parent(self, deadline: float) -> str:
        revision = self._metadata(deadline)
        if self._paths(revision, HEAD_PATH, deadline):
            raise StorageBlocked("INITIAL_HEAD_ALREADY_EXISTS")
        return revision

    def admission_exists(self, revision: str, digest: str, deadline: float) -> bool:
        if not _revision(revision) or not _digest(digest):
            raise StorageBlocked("INVALID_STORAGE_ADMISSION")
        return bool(self._paths(revision, f"{ADMISSION_PREFIX}/{digest}.json", deadline))

    def read_admission(self, head: Head, deadline: float) -> bytes:
        digest = head.value["qualification_sha256"]
        self._metadata(deadline, head.revision)
        data = self._read(head.revision, f"{ADMISSION_PREFIX}/{digest}.json", deadline, bound=MAX_ADMISSION_BYTES)
        _admission_body(data, digest)
        _deadline(deadline)
        return data

    def submit(self, expected: Head, body: bytes, operation_id: str, deadline: float) -> str:
        _deadline(deadline)
        value = parse_manifest(body)
        if value["operation_id"] != operation_id or body == expected.body:
            raise StorageBlocked("INVALID_COMMIT_OPERATION")
        # Fresh object instances on every definite-conflict attempt are required
        # because the native SDK mutates CommitOperationAdd during preupload.
        return self._commit(expected.revision, [(HEAD_PATH, body),
                            (f"{HISTORY_PREFIX}/{operation_id}.json", body)], deadline)

    def submit_bootstrap(self, parent: str, body: bytes, admission: bytes, deadline: float) -> str:
        value = parse_manifest(body)
        if not _revision(parent) or value["kind"] != "BOOTSTRAP":
            raise StorageBlocked("INITIAL_BOOTSTRAP_REQUIRED")
        parsed = _admission_body(admission, value["qualification_sha256"])
        try:
            from gdw_durable_startup import validate_bootstrap_binding
            validate_bootstrap_binding(parsed, value)
        except Exception:
            raise StorageBlocked("BOOTSTRAP_ADMISSION_BINDING_FAILED") from None
        return self._commit(parent, [(HEAD_PATH, body),
                            (f"{HISTORY_PREFIX}/{value['operation_id']}.json", body),
                            (f"{ADMISSION_PREFIX}/{value['qualification_sha256']}.json", admission)], deadline)

    def _commit(self, parent: str, files: list[tuple[str, bytes]], deadline: float) -> str:
        _deadline(deadline)
        operations = [self.operation_factory(path_in_repo=path, path_or_fileobj=body) for path, body in files]
        try:
            result = self.api.create_commit(
                DATASET, repo_type="dataset", revision="main", parent_commit=parent,
                create_pr=False, run_as_future=False, num_threads=1,
                operations=operations, commit_message="chore(gdw): persist private storage manifest")
        except Exception as error:
            response = getattr(error, "response", None)
            if getattr(response, "status_code", None) == 412:
                raise ParentConflict() from None
            raise StorageBlocked("STORAGE_OUTCOME_UNCERTAIN") from None
        _deadline(deadline)
        revision = _value(result, "oid")
        if not _revision(revision):
            raise StorageBlocked("COMMIT_IDENTITY_UNVERIFIED")
        return revision


def _private_directory(path: Path) -> Path:
    path = Path(path)
    try:
        metadata = path.lstat()
        if (not path.is_absolute() or path.resolve() != path or not stat.S_ISDIR(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o700 or metadata.st_uid != os.geteuid()):
            raise StorageBlocked("PRIVATE_STAGING_REQUIRED")
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("PRIVATE_STAGING_REQUIRED") from None
    return path


def _private_path(path: Path, root: Path, *, absent: bool = False) -> Path:
    """Only owned, private descendants; never follow a final or parent link."""
    path, root = Path(path), _private_directory(root)
    try:
        if not path.is_absolute() or ".." in path.parts or path == root:
            raise StorageBlocked("PRIVATE_FILE_PATH_INVALID")
        relative = path.relative_to(root)
        parent = root
        for segment in relative.parts[:-1]:
            parent = _private_directory(parent / segment)
        if absent:
            if os.path.lexists(path):
                raise StorageBlocked("PRIVATE_DESTINATION_ALREADY_EXISTS")
        else:
            metadata = path.lstat()
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) not in {0o400, 0o600}):
                raise StorageBlocked("PRIVATE_REGULAR_FILE_REQUIRED")
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("PRIVATE_FILE_PATH_INVALID") from None
    return path


def _stat_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink,
            metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns, metadata.st_uid)


def _file_identity(path: Path, root: Path, bound: int, deadline: float) -> dict[str, Any]:
    path = _private_path(path, root)
    descriptor = None
    try:
        _deadline(deadline)
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        before = os.fstat(descriptor)
        if (_stat_identity(before) != _stat_identity(path.lstat())
                or not 1 <= before.st_size <= bound):
            raise StorageBlocked("PRIVATE_FILE_BOUND_EXCEEDED")
        digest = hashlib.sha256()
        consumed = 0
        while True:
            _deadline(deadline)
            chunk = os.read(descriptor, min(1024 * 1024, bound + 1 - consumed))
            if not chunk:
                break
            consumed += len(chunk)
            digest.update(chunk)
            if consumed > bound:
                raise StorageBlocked("PRIVATE_FILE_BOUND_EXCEEDED")
        if (consumed != before.st_size or _stat_identity(os.fstat(descriptor)) != _stat_identity(before)
                or _stat_identity(path.lstat()) != _stat_identity(before)):
            raise StorageBlocked("PRIVATE_FILE_CHANGED_DURING_READ")
        _deadline(deadline)
        return {"size": consumed, "sha256": digest.hexdigest()}
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("PRIVATE_FILE_UNAVAILABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _freeze_file(source: Path, target: Path, root: Path, bound: int, deadline: float) -> dict[str, Any]:
    """Freeze a closed caller-owned backup before SDK/native readers see it."""
    expected = _file_identity(source, root, bound, deadline)
    _private_path(target, root, absent=True)
    incoming = outgoing = None
    try:
        incoming = os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        outgoing = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        total = 0
        while True:
            _deadline(deadline)
            chunk = os.read(incoming, min(1024 * 1024, bound + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > bound:
                raise StorageBlocked("PRIVATE_FILE_BOUND_EXCEEDED")
            while chunk:
                _deadline(deadline)
                written = os.write(outgoing, chunk)
                if written <= 0:
                    raise StorageBlocked("PRIVATE_SNAPSHOT_COPY_FAILED")
                chunk = chunk[written:]
        os.fsync(outgoing)
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("PRIVATE_SNAPSHOT_COPY_FAILED") from None
    finally:
        if incoming is not None:
            os.close(incoming)
        if outgoing is not None:
            os.close(outgoing)
    if (_file_identity(source, root, bound, deadline) != expected
            or _file_identity(target, root, bound, deadline) != expected):
        raise StorageBlocked("PRIVATE_FILE_CHANGED_DURING_COPY")
    target.chmod(0o400)
    _deadline(deadline)
    return expected


def _private_json(payload: Any) -> dict[str, Any]:
    if type(payload) is not str or len(payload.encode("utf-8")) > MAX_ARTIFACT_BYTES:
        raise StorageBlocked("SNAPSHOT_RECEIPT_SHAPE_INVALID")
    try:
        value = json.loads(payload, object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(value) is not dict:
            raise ValueError()
        return value
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("SNAPSHOT_RECEIPT_SHAPE_INVALID") from None


def _same_fields(value: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(key in value and type(value[key]) is type(item) and value[key] == item
               for key, item in expected.items())


def _native_series_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def inspect_snapshot(label: str, path: Path, root: Path, deadline: float, *,
                     previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read a closed local backup; no constructors, migration, repair or signer.

    Full immutable bytes bind every table. The small public summary also checks
    native generation, integrity, foreign keys and receipt digest/chain fields.
    It does not relabel all historical envelopes as signature-verified.
    """
    if label not in LABELS:
        raise StorageBlocked("INVALID_SNAPSHOT_SET")
    before = _file_identity(path, root, MAX_SNAPSHOT_BYTES, deadline)
    if any(os.path.lexists(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise StorageBlocked("CLOSED_SQLITE_BACKUP_REQUIRED")
    connection = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            header = os.read(descriptor, 100)
        finally:
            os.close(descriptor)
        if len(header) != 100 or header[:16] != b"SQLite format 3\x00" or header[18:20] != b"\x01\x01":
            raise StorageBlocked("CLOSED_DELETE_SQLITE_BACKUP_REQUIRED")
        # immutable is justified only by the fresh, private, closed backup and
        # sidecar/header checks above. No original incident object is opened.
        connection = sqlite3.connect(Path(path).as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
        connection.enable_load_extension(False)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_ARTIFACT_BYTES)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        if connection.execute("PRAGMA integrity_check(100)").fetchmany(101) != [("ok",)]:
            raise StorageBlocked("SNAPSHOT_INTEGRITY_FAILED")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StorageBlocked("SNAPSHOT_FOREIGN_KEY_FAILED")
        schema = connection.execute("SELECT name,sql FROM sqlite_schema WHERE type='table'").fetchmany(101)
        tables = {row[0] for row in schema}
        if (len(schema) > 100 or tables - {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}
                != APPLICATION_TABLES[label]
                or any(not sql or not re.match(r"CREATE\s+TABLE\b", sql, re.I) for _, sql in schema)):
            raise StorageBlocked("SNAPSHOT_SCHEMA_UNQUALIFIED")
        for table in APPLICATION_TABLES[label]:
            columns = connection.execute('PRAGMA table_xinfo("' + table + '")').fetchall()
            if not columns or not any(row[5] > 0 for row in columns) or any(row[6] != 0 for row in columns):
                raise StorageBlocked("SNAPSHOT_SCHEMA_UNQUALIFIED")
        if label == "gdw":
            rows = connection.execute("SELECT schema_version,database_generation_id FROM schema_meta "
                                      "WHERE schema_name='gdw'").fetchmany(2)
            if len(rows) != 1 or rows[0][0] != 4 or not _hex(HEX32, rows[0][1]) or rows[0][1] == "0" * 32:
                raise StorageBlocked("SNAPSHOT_GENERATION_UNQUALIFIED")
            generation = rows[0][1]
            digest = hashlib.sha256(b"szl.gdw-receipt-identities/v1\n")
            count = 0
            for ns, owner, request, session, step, payload, claimed in connection.execute(
                    "SELECT namespace,owner_id,request_id,session_id,step,receipt_json,receipt_hash "
                    "FROM receipts ORDER BY namespace,owner_id,receipt_hash"):
                _deadline(deadline)
                count += 1
                if count > MAX_RECEIPTS or not _digest(claimed):
                    raise StorageBlocked("SNAPSHOT_RECEIPT_SHAPE_INVALID")
                if payload is not None:
                    value = _private_json(payload)
                    unsigned = dict(value)
                    unsigned.pop("receipt_hash", None)
                    observed = sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                                                allow_nan=False).encode())
                    if claimed != observed or not _same_fields(value, {
                            "namespace": ns, "owner_id": owner, "request_id": request,
                            "session_id": session, "step": step, "database_generation_id": generation,
                            "receipt_hash": claimed}):
                        raise StorageBlocked("SNAPSHOT_RECEIPT_BINDING_FAILED")
                # Receipt tombstones retain their native immutable identity.
                # Payload bytes themselves remain bound by the complete DB hash.
                digest.update(canonical([ns, owner, request, session, step, claimed, payload is None]))
            summary = {"generation": generation, "receipt_count": count, "receipt_sequence": 0,
                       "receipt_head_sha256": digest.hexdigest()}
        else:
            rows = connection.execute("SELECT value FROM metadata WHERE key='storage_instance_id'").fetchmany(2)
            if (len(rows) != 1 or not _hex(re.compile(r"store_[0-9a-f]{32}\Z"), rows[0][0])
                    or rows[0][0] == "store_" + "0" * 32):
                raise StorageBlocked("SNAPSHOT_GENERATION_UNQUALIFIED")
            generation, count, prior_hash, last_sequence = rows[0][0], 0, "0" * 64, 0
            receipt_rows = hashlib.sha256(b"szl.series-a-receipt-rows/v1\n")
            anchor_seen = previous is None or (previous["receipt_count"] == previous["receipt_sequence"] == 0
                                               and previous["receipt_head_sha256"] == "0" * 64
                                               and previous.get("receipt_rows_sha256") == receipt_rows.hexdigest())
            for sequence, receipt_id, kind, payload, envelope, prior, claimed, created in connection.execute(
                    "SELECT sequence,receipt_id,kind,payload,envelope,previous_hash,receipt_hash,created_at "
                    "FROM receipts ORDER BY sequence"):
                _deadline(deadline)
                count += 1
                if count > MAX_RECEIPTS or not _integer(sequence, last_sequence + 1) or not _digest(claimed):
                    raise StorageBlocked("SNAPSHOT_RECEIPT_SHAPE_INVALID")
                value, signed = _private_json(payload), _private_json(envelope)
                encoded = base64.b64decode(signed.get("payload", ""), validate=True)
                payload_type = SERIES_RECEIPT_TYPE.encode()
                pae = b"DSSEv1 " + str(len(payload_type)).encode() + b" " + payload_type + b" " \
                    + str(len(encoded)).encode() + b" " + encoded
                if (sha256(_native_series_bytes(signed)) != claimed or prior != prior_hash
                        or not _same_fields(value, {"schema": "szl.series-a-receipt/v1", "receipt_id": receipt_id,
                                                   "kind": kind, "created_at": created,
                                                   "previous_receipt_hash": prior})
                        or encoded != _native_series_bytes(value)
                        or signed.get("payloadType") != SERIES_RECEIPT_TYPE
                        or signed.get("pae_sha256") != sha256(pae)):
                    raise StorageBlocked("SNAPSHOT_RECEIPT_BINDING_FAILED")
                # Native envelope chaining does not cover the SQL sequence or
                # raw JSON strings. Bind every exact row, including those IDs
                # and bytes, before checking the acknowledged prefix.
                receipt_rows.update(canonical([sequence, receipt_id, kind, payload, envelope,
                                               prior, claimed, created]))
                if previous is not None and sequence == previous["receipt_sequence"]:
                    if (claimed != previous["receipt_head_sha256"] or count != previous["receipt_count"]
                            or receipt_rows.hexdigest() != previous.get("receipt_rows_sha256")):
                        raise StorageBlocked("ACKNOWLEDGED_RECEIPT_ANCHOR_CHANGED")
                    anchor_seen = True
                prior_hash, last_sequence = claimed, sequence
            if not anchor_seen:
                raise StorageBlocked("ACKNOWLEDGED_RECEIPT_ANCHOR_MISSING")
            summary = {"generation": generation, "receipt_count": count, "receipt_sequence": last_sequence,
                       "receipt_head_sha256": prior_hash, "receipt_rows_sha256": receipt_rows.hexdigest()}
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("SNAPSHOT_INSPECTION_UNAVAILABLE") from None
    finally:
        if connection is not None:
            connection.close()
    if _file_identity(path, root, MAX_SNAPSHOT_BYTES, deadline) != before:
        raise StorageBlocked("PRIVATE_SNAPSHOT_CHANGED_DURING_INSPECTION")
    _deadline(deadline)
    return dict(before, **summary)


def _object_record(value: Any, *, artifact: bool = False) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {"path", "size", "sha256", "xet_hash"}:
        raise StorageBlocked("INVALID_PRIVATE_OBJECT")
    bound = MAX_ARTIFACT_BYTES if artifact else MAX_SNAPSHOT_BYTES
    if (not _digest(value["sha256"]) or not _digest(value["xet_hash"])
            or not _integer(value["size"], 1) or value["size"] > bound):
        raise StorageBlocked("INVALID_PRIVATE_OBJECT")
    pattern = (re.escape(ARTIFACT_PREFIX) + r"/[0-9a-f]{64}/" + value["sha256"] + r"\.json\Z"
               if artifact else re.escape(OBJECT_PREFIX) + r"/[0-9a-f]{32}/(?:gdw|series_a)-"
               + value["sha256"] + r"\.sqlite3\Z")
    if not _hex(re.compile(pattern), value["path"]):
        raise StorageBlocked("INVALID_PRIVATE_OBJECT_PATH")
    return json.loads(canonical(value))


class HFPrivateObjectStore:
    """Worker-only private add/readback, with no overwrite or uncertain retry.

    Hub bucket add has no absent-only CAS. Fresh UUID plus content hash keys
    and exact readback are a cooperative protocol for all admitted writers,
    not a claim that a rogue legacy writer is constrained by this API.
    """
    def __init__(self, api: Any, private_directory: Path, allowed_root: Path):
        if _value(api, "endpoint") != ENDPOINT:
            raise StorageBlocked("NONCANONICAL_ENDPOINT")
        self.api = api
        self.directory = _private_directory(private_directory)
        self.root = _private_directory(allowed_root)
        if self.directory != self.root:
            try:
                self.directory.relative_to(self.root)
            except ValueError:
                raise StorageBlocked("PRIVATE_STAGING_REQUIRED") from None

    def _metadata(self, deadline: float) -> None:
        _deadline(deadline)
        info = _safe_call(lambda: self.api.bucket_info(bucket_id=BUCKET))
        _deadline(deadline)
        if _value(info, "id") != BUCKET or _value(info, "private") is not True:
            raise StorageBlocked("PRIVATE_BUCKET_IDENTITY_CHANGED")

    def _observe(self, path: str, deadline: float) -> Any | None:
        _deadline(deadline)
        try:
            found = []
            for value in self.api.get_bucket_paths_info(bucket_id=BUCKET, paths=[path]):
                _deadline(deadline)
                if (found or _value(value, "path") != path or _value(value, "type") != "file"
                        or not _integer(_value(value, "size"), 1)
                        or _value(value, "size") > MAX_SNAPSHOT_BYTES
                        or not _digest(_value(value, "xet_hash"))):
                    raise StorageBlocked("PRIVATE_OBJECT_IDENTITY_MALFORMED")
                found.append(value)
            _deadline(deadline)
            return found[0] if found else None
        except StorageBlocked:
            raise
        except Exception:
            raise StorageBlocked("PRIVATE_OBJECT_IDENTITY_UNAVAILABLE") from None

    @staticmethod
    def _identity(value: Any) -> tuple[Any, Any, Any]:
        return (_value(value, "path"), _value(value, "size"), _value(value, "xet_hash"))

    def _download(self, observed: Any, path: Path, expected: dict[str, Any], deadline: float) -> None:
        _private_path(path, self.root, absent=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        # Actual BucketFile carries exact observed Xet hash and size. Strings
        # would silently resolve a mutable path again during the native call.
        _safe_call(lambda: self.api.download_bucket_files(bucket_id=BUCKET, files=[(observed, path)]))
        if _file_identity(path, self.root, MAX_SNAPSHOT_BYTES, deadline) != expected:
            raise StorageBlocked("PRIVATE_OBJECT_READBACK_MISMATCH")
        current = self._observe(_value(observed, "path"), deadline)
        if current is None or self._identity(current) != self._identity(observed):
            raise StorageBlocked("PRIVATE_OBJECT_IDENTITY_CHANGED")
        self._metadata(deadline)

    def _publish(self, path: Path, object_path: str, identity: dict[str, Any],
                 deadline: float, *, artifact: bool = False) -> dict[str, Any]:
        # Validate destination before even a metadata read. The placeholder is
        # used only for shape checking; the result always uses observed Xet.
        _object_record(dict(identity, path=object_path, xet_hash="1" * 64), artifact=artifact)
        self._metadata(deadline)
        observed = self._observe(object_path, deadline)
        if observed is not None and _value(observed, "size") != identity["size"]:
            raise StorageBlocked("PRIVATE_OBJECT_COLLISION")
        if observed is None:
            if _file_identity(path, self.root, MAX_SNAPSHOT_BYTES, deadline) != identity:
                raise StorageBlocked("PRIVATE_SNAPSHOT_CHANGED_BEFORE_UPLOAD")
            # Exactly one add. Never copy/delete, modify an original path, or
            # repeat an ambiguous namespace POST, even if it may have landed.
            _safe_call(lambda: self.api.batch_bucket_files(bucket_id=BUCKET, add=[(path, object_path)]))
            if _file_identity(path, self.root, MAX_SNAPSHOT_BYTES, deadline) != identity:
                raise StorageBlocked("PRIVATE_SNAPSHOT_CHANGED_DURING_UPLOAD")
            observed = self._observe(object_path, deadline)
            if observed is None or _value(observed, "size") != identity["size"]:
                raise StorageBlocked("PRIVATE_OBJECT_COMMIT_UNVERIFIED")
        target = self.directory / ("readback-" + uuid.uuid4().hex)
        self._download(observed, target, identity, deadline)
        record = _object_record(dict(identity, path=object_path, xet_hash=_value(observed, "xet_hash")),
                                artifact=artifact)
        _deadline(deadline)
        return record

    def publish_snapshots(self, paths: Mapping[str, Path], generations: Mapping[str, str],
                          deadline: float, *, previous_snapshots: dict[str, Any] | None = None) -> dict[str, Any]:
        if set(paths) != set(LABELS) or set(generations) != set(LABELS):
            raise StorageBlocked("INVALID_SNAPSHOT_SET")
        if previous_snapshots is not None:
            previous_snapshots = validate_snapshots(previous_snapshots)
            if any(previous_snapshots[label]["generation"] != generations[label] for label in LABELS):
                raise StorageBlocked("DATABASE_GENERATION_CHANGED")
        prepared = {}
        operation_id = uuid.uuid4().hex
        # Both complete snapshots are inspected before the first provider write.
        for label in LABELS:
            source = _private_path(Path(paths[label]), self.root)
            if any(os.path.lexists(str(source) + suffix) for suffix in ("-wal", "-shm", "-journal")):
                raise StorageBlocked("CLOSED_SQLITE_BACKUP_REQUIRED")
            frozen = self.directory / (label + "-" + uuid.uuid4().hex + ".sqlite3")
            identity = _freeze_file(source, frozen, self.root, MAX_SNAPSHOT_BYTES, deadline)
            summary = inspect_snapshot(label, frozen, self.root, deadline,
                                       previous=None if previous_snapshots is None else previous_snapshots[label])
            if summary["generation"] != generations[label] or any(summary[k] != identity[k] for k in identity):
                raise StorageBlocked("DATABASE_GENERATION_CHANGED")
            prepared[label] = (frozen, summary)
        result = {}
        for label in LABELS:
            frozen, summary = prepared[label]
            object_path = f"{OBJECT_PREFIX}/{operation_id}/{label}-{summary['sha256']}.sqlite3"
            record = self._publish(frozen, object_path, {key: summary[key] for key in ("size", "sha256")}, deadline)
            result[label] = dict(summary, **{key: record[key] for key in ("path", "xet_hash")})
        for record in result.values():
            current = self._observe(record["path"], deadline)
            if current is None or self._identity(current) != tuple(record[key] for key in ("path", "size", "xet_hash")):
                raise StorageBlocked("PRIVATE_OBJECT_IDENTITY_CHANGED")
        self._metadata(deadline)
        _deadline(deadline)
        return validate_snapshots(result)

    def restore_snapshots(self, snapshots: dict[str, Any], destinations: Mapping[str, Path],
                          deadline: float) -> dict[str, Any]:
        snapshots = validate_snapshots(snapshots)
        if set(destinations) != set(LABELS):
            raise StorageBlocked("INVALID_SNAPSHOT_SET")
        self._metadata(deadline)
        observed = {}
        for label in LABELS:
            path = _private_path(Path(destinations[label]), self.root, absent=True)
            if any(os.path.lexists(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")):
                raise StorageBlocked("CLOSED_SQLITE_BACKUP_REQUIRED")
            item = self._observe(snapshots[label]["path"], deadline)
            if item is None or self._identity(item) != tuple(snapshots[label][key] for key in ("path", "size", "xet_hash")):
                raise StorageBlocked("RESTORE_OBJECT_IDENTITY_MISMATCH")
            observed[label] = item
        for label in LABELS:
            expected = snapshots[label]
            target = Path(destinations[label])
            self._download(observed[label], target, {key: expected[key] for key in ("size", "sha256")}, deadline)
            summary = inspect_snapshot(label, target, self.root, deadline)
            if any(summary[key] != expected[key] for key in summary):
                raise StorageBlocked("RESTORE_SNAPSHOT_SUMMARY_MISMATCH")
        for label in LABELS:
            current = self._observe(snapshots[label]["path"], deadline)
            if current is None or self._identity(current) != self._identity(observed[label]):
                raise StorageBlocked("PRIVATE_OBJECT_IDENTITY_CHANGED")
        self._metadata(deadline)
        _deadline(deadline)
        return snapshots

    def publish_artifact(self, local_path: Path, object_path: str, digest: str, deadline: float) -> dict[str, Any]:
        if not _digest(digest):
            raise StorageBlocked("INVALID_ARTIFACT_DIGEST")
        frozen = self.directory / ("artifact-" + uuid.uuid4().hex + ".json")
        identity = _freeze_file(Path(local_path), frozen, self.root, MAX_ARTIFACT_BYTES, deadline)
        if identity["sha256"] != digest:
            raise StorageBlocked("ARTIFACT_DIGEST_MISMATCH")
        return self._publish(frozen, object_path, identity, deadline, artifact=True)


MAX_WORKER_MESSAGE_BYTES = 1024 * 1024
MAX_PROVIDER_SECONDS = 120


def _head_message(head: Head) -> dict[str, str]:
    return {"revision": head.revision, "body": head.body.decode("ascii")}


def _message_head(value: Any) -> Head:
    if type(value) is not dict or set(value) != {"revision", "body"} or type(value["body"]) is not str:
        raise StorageBlocked("INVALID_WORKER_RESULT")
    try:
        return Head(value["revision"], value["body"].encode("ascii"))
    except UnicodeError:
        raise StorageBlocked("INVALID_WORKER_RESULT") from None


def _worker_call(message: dict[str, Any], directory: Path, deadline: float) -> Any:
    """Run one provider operation with a parent-enforced total deadline.

    A killed operation has an uncertain effect, including after a server commit.
    It can never produce a success acknowledgement or a definite-conflict retry.
    Credentials are inherited by the isolated application child, not placed in
    arguments, protocol messages, output or exception text.
    """
    _deadline(deadline)
    effective_deadline = min(float(deadline), time.monotonic() + MAX_PROVIDER_SECONDS)
    request = canonical(dict(message, deadline=effective_deadline))
    if len(request) > MAX_WORKER_MESSAGE_BYTES:
        raise StorageBlocked("WORKER_MESSAGE_BOUND_EXCEEDED")
    process = None
    staging = None
    try:
        staging = tempfile.TemporaryDirectory(prefix="gdw-provider-operation-", dir=directory)
        process = subprocess.Popen(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--provider-worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=staging.name, start_new_session=True)
        try:
            _deadline(effective_deadline)
            output, _ = process.communicate(request, timeout=effective_deadline - time.monotonic())
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            raise StorageBlocked("PROVIDER_DEADLINE_EXHAUSTED") from None
        _deadline(effective_deadline)
        if process.returncode != 0 or not 1 <= len(output) <= MAX_WORKER_MESSAGE_BYTES:
            raise StorageBlocked("STORAGE_OUTCOME_UNCERTAIN")
        result = json.loads(output, object_pairs_hook=_object)
        if type(result) is not dict or type(result.get("ok")) is not bool:
            raise StorageBlocked("INVALID_WORKER_RESULT")
        if result["ok"] is False:
            if set(result) != {"ok", "code"}:
                raise StorageBlocked("INVALID_WORKER_RESULT")
            if result["code"] == "PARENT_CONFLICT":
                raise ParentConflict()
            raise StorageBlocked(result["code"] if type(result["code"]) is str else "STORAGE_OUTCOME_UNCERTAIN")
        if set(result) != {"ok", "value"}:
            raise StorageBlocked("INVALID_WORKER_RESULT")
        value = result["value"]
    except StorageBlocked:
        raise
    except Exception:
        raise StorageBlocked("STORAGE_OUTCOME_UNCERTAIN") from None
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if staging is not None:
            # The parent owns this exact private directory, so a killed child
            # cannot leave a cache or raw snapshot eligible for later reuse.
            try:
                staging.cleanup()
            except OSError:
                raise StorageBlocked("PRIVATE_STAGING_CLEANUP_FAILED") from None
    # Cleanup is part of the operation's total budget. Never return a success
    # that became overdue while removing a private SDK staging directory.
    _deadline(effective_deadline)
    return value


class WorkerFenceBackend:
    """Production protocol port: each SDK operation has a killable deadline."""
    def __init__(self, private_directory: Path, expected_resource_group_sha256: str):
        self.directory = _private_directory(private_directory)
        if not _digest(expected_resource_group_sha256):
            raise StorageBlocked("PRIVATE_STAGING_REQUIRED")
        self.resource_group_sha256 = expected_resource_group_sha256

    def _call(self, operation: str, arguments: dict[str, Any], deadline: float) -> Any:
        return _worker_call({"operation": operation, "arguments": arguments,
                             "resource_group_sha256": self.resource_group_sha256},
                            self.directory, deadline)

    def observe(self, deadline: float) -> Head:
        return _message_head(self._call("observe", {}, deadline))

    def read_at(self, revision: str, operation_id: str, deadline: float) -> tuple[Head, bytes]:
        value = self._call("read_at", {"revision": revision, "operation_id": operation_id}, deadline)
        if type(value) is not dict or set(value) != {"head", "history"} or type(value["history"]) is not str:
            raise StorageBlocked("INVALID_WORKER_RESULT")
        head, history = _message_head(value["head"]), value["history"].encode("ascii")
        parse_manifest(history)
        return head, history

    def history_exists(self, revision: str, operation_id: str, deadline: float) -> bool:
        result = self._call("history_exists", {"revision": revision, "operation_id": operation_id}, deadline)
        if type(result) is not bool:
            raise StorageBlocked("INVALID_WORKER_RESULT")
        return result

    def submit(self, expected: Head, body: bytes, operation_id: str, deadline: float) -> str:
        parse_manifest(body)
        result = self._call("submit", {"expected": _head_message(expected), "body": body.decode("ascii"),
                                       "operation_id": operation_id}, deadline)
        if not _revision(result):
            raise StorageBlocked("COMMIT_IDENTITY_UNVERIFIED")
        return result

    def empty_parent(self, deadline: float) -> str:
        value = self._call("empty_parent", {}, deadline)
        if not _revision(value):
            raise StorageBlocked("INVALID_DATASET_REVISION")
        return value

    def admission_exists(self, revision: str, digest: str, deadline: float) -> bool:
        value = self._call("admission_exists", {"revision": revision, "digest": digest}, deadline)
        if type(value) is not bool:
            raise StorageBlocked("INVALID_WORKER_RESULT")
        return value

    def read_admission(self, head: Head, deadline: float) -> bytes:
        value = self._call("read_admission", {"head": _head_message(head)}, deadline)
        if type(value) is not str:
            raise StorageBlocked("INVALID_WORKER_RESULT")
        data = value.encode("ascii")
        _admission_body(data, head.value["qualification_sha256"])
        _deadline(deadline)
        return data

    def submit_bootstrap(self, parent: str, body: bytes, admission: bytes, deadline: float) -> str:
        value = self._call("submit_bootstrap", {"parent": parent, "body": body.decode("ascii"),
                                               "admission": admission.decode("ascii")}, deadline)
        if not _revision(value):
            raise StorageBlocked("COMMIT_IDENTITY_UNVERIFIED")
        return value


def load_admitted_head(private_directory: Path, deadline: float) -> tuple[Head, bytes, str]:
    """Read-only startup observation; no environment-provided admission hash."""
    directory = _private_directory(private_directory)
    value = _worker_call({"operation": "load_admission", "arguments": {}, "resource_group_sha256": None},
                         directory, deadline)
    if (type(value) is not dict or set(value) != {"head", "admission", "resource_group_sha256"}
            or type(value["admission"]) is not str or not _digest(value["resource_group_sha256"])):
        raise StorageBlocked("INVALID_WORKER_RESULT")
    head = _message_head(value["head"])
    data = value["admission"].encode("ascii")
    _admission_body(data, head.value["qualification_sha256"])
    _deadline(deadline)
    return head, data, value["resource_group_sha256"]


class WorkerSnapshotStore:
    """Runtime callbacks for closed snapshots and retained artifact objects.

    Construction does not admit startup. The coordinator must supply the two
    already-qualified generation IDs and exact private dataset metadata digest,
    restore an existing Head, and take the local lifetime lock before its claim.
    Every provider operation runs in a killable private child process.
    """
    def __init__(self, private_directory: Path, generations: Mapping[str, str],
                 expected_resource_group_sha256: str, *, head: Callable[[], Head] | None = None):
        self.directory = _private_directory(private_directory)
        if (type(generations) is not dict or set(generations) != set(LABELS)
                or not _hex(HEX32, generations["gdw"]) or generations["gdw"] == "0" * 32
                or not _hex(re.compile(r"store_[0-9a-f]{32}\Z"), generations["series_a"])
                or generations["series_a"] == "store_" + "0" * 32
                or not _digest(expected_resource_group_sha256)):
            raise StorageBlocked("QUALIFIED_STORAGE_IDENTITIES_REQUIRED")
        self.generations = dict(generations)
        self.resource_group_sha256 = expected_resource_group_sha256
        self.current_head = head

    def _call(self, operation: str, arguments: dict[str, Any], deadline: float) -> Any:
        return _worker_call({"operation": operation, "arguments": arguments,
                             "resource_group_sha256": self.resource_group_sha256},
                            self.directory, deadline)

    def publish(self, paths: Mapping[str, Path], deadline: float) -> dict[str, Any]:
        if set(paths) != set(LABELS):
            raise StorageBlocked("INVALID_SNAPSHOT_SET")
        if not callable(self.current_head):
            raise StorageBlocked("PREVIOUS_ACKNOWLEDGED_HEAD_REQUIRED")
        previous = self.current_head()
        if not isinstance(previous, Head):
            raise StorageBlocked("PREVIOUS_ACKNOWLEDGED_HEAD_REQUIRED")
        frozen_inputs = {label: str(_private_path(Path(paths[label]), self.directory)) for label in LABELS}
        value = validate_snapshots(self._call("publish_snapshots", {
            "paths": frozen_inputs, "generations": self.generations,
            "previous_snapshots": previous.value["snapshots"]}, deadline))
        if any(value[label]["generation"] != self.generations[label] for label in LABELS):
            raise StorageBlocked("DATABASE_GENERATION_CHANGED")
        _deadline(deadline)
        return value

    def restore(self, head: Head, deadline: float) -> dict[str, Path]:
        snapshots = head.value["snapshots"]
        if any(snapshots[label]["generation"] != self.generations[label] for label in LABELS):
            raise StorageBlocked("DATABASE_GENERATION_CHANGED")
        destinations = {label: _private_path(self.directory / (label + ".sqlite3"), self.directory, absent=True)
                        for label in LABELS}
        value = validate_snapshots(self._call("restore_snapshots", {
            "snapshots": snapshots, "destinations": {label: str(path) for label, path in destinations.items()}}, deadline))
        if value != snapshots:
            raise StorageBlocked("RESTORE_SNAPSHOT_SUMMARY_MISMATCH")
        for path in destinations.values():
            _private_path(path, self.directory)
        _deadline(deadline)
        return destinations

    def publish_artifact(self, local_path: Path, object_path: str, digest: str, deadline: float) -> dict[str, Any]:
        path = _private_path(Path(local_path), self.directory)
        value = _object_record(self._call("publish_artifact", {
            "local_path": str(path), "object_path": object_path, "sha256": digest}, deadline), artifact=True)
        if value["sha256"] != digest or value["path"] != object_path:
            raise StorageBlocked("ARTIFACT_READBACK_IDENTITY_MISMATCH")
        _deadline(deadline)
        return value


@contextlib.contextmanager
def _private_worker_output():
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    try:
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
    finally:
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])


def _provider_worker() -> int:
    response: dict[str, Any] = {"ok": False, "code": "INVALID_WORKER_REQUEST"}
    try:
        raw = sys.stdin.buffer.read(MAX_WORKER_MESSAGE_BYTES + 1)
        if not 1 <= len(raw) <= MAX_WORKER_MESSAGE_BYTES:
            raise StorageBlocked("WORKER_MESSAGE_BOUND_EXCEEDED")
        request = json.loads(raw, object_pairs_hook=_object)
        if type(request) is not dict or set(request) != {"operation", "arguments", "resource_group_sha256", "deadline"}:
            raise StorageBlocked("INVALID_WORKER_REQUEST")
        operation, arguments, deadline = request["operation"], request["arguments"], request["deadline"]
        allowed = {"observe": set(), "read_at": {"revision", "operation_id"},
                   "history_exists": {"revision", "operation_id"},
                   "submit": {"expected", "body", "operation_id"},
                   "empty_parent": set(), "admission_exists": {"revision", "digest"},
                   "read_admission": {"head"}, "submit_bootstrap": {"parent", "body", "admission"},
                   "load_admission": set(),
                   "publish_snapshots": {"paths", "generations", "previous_snapshots"},
                   "restore_snapshots": {"snapshots", "destinations"},
                   "publish_artifact": {"local_path", "object_path", "sha256"}}
        if (type(operation) is not str or operation not in allowed or type(arguments) is not dict
                or set(arguments) != allowed[operation]):
            raise StorageBlocked("INVALID_WORKER_REQUEST")
        _deadline(deadline)
        if deadline - time.monotonic() > MAX_PROVIDER_SECONDS:
            raise StorageBlocked("WORKER_DEADLINE_BOUND_EXCEEDED")
        token = os.environ.get("HF_TOKEN", "")
        if not token:
            raise StorageBlocked("EXISTING_HF_TOKEN_REQUIRED")
        os.umask(0o077)
        logging.disable(logging.CRITICAL)
        os.environ.pop("HF_DEBUG", None)
        os.environ.update(HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DISABLE_TELEMETRY="1",
                          HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
        with _private_worker_output():
            with tempfile.TemporaryDirectory(prefix="gdw-private-provider-", dir=Path.cwd()) as temporary:
                directory = Path(temporary)
                for name, suffix in (("HF_HOME", "cache"), ("HF_HUB_CACHE", "cache/hub"), ("HF_XET_CACHE", "cache/xet")):
                    os.environ[name] = str(directory / suffix)
                if operation == "load_admission":
                    if request["resource_group_sha256"] is not None:
                        raise StorageBlocked("INVALID_WORKER_REQUEST")
                    from huggingface_hub import CommitOperationAdd
                    api = _hub_api(token)
                    observed = _safe_call(lambda: api.dataset_info(
                        DATASET, revision="main", expand=["sha", "private", "resourceGroup"]))
                    if (_value(observed, "id") != DATASET or _value(observed, "private") is not True
                            or not _revision(_value(observed, "sha"))):
                        raise StorageBlocked("PRIVATE_DATASET_IDENTITY_CHANGED")
                    group_digest = sha256(canonical(_value(observed, "resource_group")))
                    backend = HFDatasetFenceBackend(api, directory, group_digest, CommitOperationAdd)
                else:
                    backend = HFDatasetFenceBackend.from_token(token, directory, request["resource_group_sha256"])
                if operation == "observe":
                    value: Any = _head_message(backend.observe(deadline))
                elif operation == "read_at":
                    head, history = backend.read_at(arguments["revision"], arguments["operation_id"], deadline)
                    value = {"head": _head_message(head), "history": history.decode("ascii")}
                elif operation == "history_exists":
                    value = backend.history_exists(arguments["revision"], arguments["operation_id"], deadline)
                elif operation == "empty_parent":
                    value = backend.empty_parent(deadline)
                elif operation == "admission_exists":
                    value = backend.admission_exists(arguments["revision"], arguments["digest"], deadline)
                elif operation == "read_admission":
                    value = backend.read_admission(_message_head(arguments["head"]), deadline).decode("ascii")
                elif operation == "load_admission":
                    head = backend.observe(deadline)
                    admission = backend.read_admission(head, deadline)
                    backend._metadata(deadline)
                    value = {"head": _head_message(head), "admission": admission.decode("ascii"),
                             "resource_group_sha256": group_digest}
                elif operation == "submit_bootstrap":
                    value = backend.submit_bootstrap(arguments["parent"], arguments["body"].encode("ascii"),
                                                     arguments["admission"].encode("ascii"), deadline)
                elif operation == "submit":
                    if type(arguments["body"]) is not str:
                        raise StorageBlocked("INVALID_WORKER_REQUEST")
                    value = backend.submit(_message_head(arguments["expected"]), arguments["body"].encode("ascii"),
                                           arguments["operation_id"], deadline)
                else:
                    objects = HFPrivateObjectStore(backend.api, directory, Path.cwd().parent)
                    if operation == "publish_snapshots":
                        # Runtime publication always has a prior acknowledged
                        # pair. Initial candidate publication uses the separately
                        # source-admitted private acquisition helper.
                        prior = validate_snapshots(arguments["previous_snapshots"])
                        value = objects.publish_snapshots(arguments["paths"], arguments["generations"], deadline,
                                                          previous_snapshots=prior)
                    elif operation == "restore_snapshots":
                        value = objects.restore_snapshots(arguments["snapshots"], arguments["destinations"], deadline)
                    else:
                        value = objects.publish_artifact(Path(arguments["local_path"]), arguments["object_path"],
                                                         arguments["sha256"], deadline)
        _deadline(deadline)
        response = {"ok": True, "value": value}
    except StorageBlocked as error:
        response = {"ok": False, "code": error.code}
    except Exception:
        response = {"ok": False, "code": "STORAGE_OUTCOME_UNCERTAIN"}
    rendered = canonical(response)
    if len(rendered) > MAX_WORKER_MESSAGE_BYTES:
        rendered = canonical({"ok": False, "code": "WORKER_MESSAGE_BOUND_EXCEEDED"})
    sys.stdout.buffer.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(_provider_worker() if sys.argv[1:] == ["--provider-worker"] else 2)
