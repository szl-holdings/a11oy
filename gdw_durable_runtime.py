#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: local SQLite access and acknowledgement boundary for durable GDW.

Activation is an internal startup operation, never an HTTP or environment
admission. The caller must first verify the recovery qualification and stopped
legacy writers and restore BOTH immutable snapshots before claiming their head.
This module never creates a store or adopts an existing local working copy.
The provider adapter publishes closed native backups and verifies their bytes;
the writer then acknowledges them through its conditional metadata commit.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import time
from typing import Any, Callable, Mapping
import uuid


MODE = "private-dataset-v1"
LABELS = ("gdw", "series_a")
_LOCAL_FILESYSTEMS = {"ext4", "xfs", "btrfs", "overlay", "tmpfs", "zfs"}
_GATE = None
_INSTALL_LOCK = threading.Lock()


class DurableStorageUnavailable(RuntimeError):
    """No successful response or replay may cross an unproven storage boundary."""


def enabled(environ: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    value = values.get("GDW_DURABLE_STORAGE", "").strip()
    if value and value != MODE:
        raise DurableStorageUnavailable("DURABLE_STORAGE_MODE_INVALID")
    return _GATE is not None or value == MODE


def _private_directory(directory: Path) -> Path:
    if not directory.is_absolute() or directory.resolve() != directory:
        raise DurableStorageUnavailable("LOCAL_PATH_INVALID")
    metadata = directory.lstat()
    if (not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.geteuid()):
        raise DurableStorageUnavailable("PRIVATE_LOCAL_DIRECTORY_REQUIRED")
    # A write/fsync probe does not establish that a FUSE/object mount supports
    # SQLite locks or crash recovery. Admit only explicit local filesystem types.
    candidates = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, separator, right = line.partition(" - ")
        fields = left.split()
        if not separator or len(fields) < 5:
            continue
        mount = Path(fields[4].replace("\\040", " ").replace("\\134", "\\"))
        if directory == mount or mount in directory.parents:
            candidates.append((len(mount.parts), right.split()[0]))
    if not candidates or max(candidates)[1] not in _LOCAL_FILESYSTEMS:
        raise DurableStorageUnavailable("LOCAL_POSIX_STORAGE_REQUIRED")
    return directory


def _regular_file(path: Path) -> os.stat_result:
    if path.resolve() != path:
        raise DurableStorageUnavailable("LOCAL_PATH_INVALID")
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600):
        raise DurableStorageUnavailable("PRIVATE_LOCAL_FILE_REQUIRED")
    return metadata


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise DurableStorageUnavailable("LOCAL_FILE_INVALID")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalGate:
    """One claimed process, both stores, serialized until remote acknowledgement.

    The admitted startup coordinator supplies a NEW ``writer`` and exact
    ``restored_head``. The local lock and restored bytes are checked before its
    remote claim. An already claimed writer is also accepted for composition.
    On every restart the coordinator restores fresh paths from the remote head;
    an unacknowledged local working copy is never a recovery authority.
    """

    def __init__(self, writer: Any, paths: Mapping[str, Path],
                 directory: Path, publish: Callable, *, timeout_seconds: float = 60,
                 restored_head: Any = None, artifacts: Any = None):
        self.directory = _private_directory(directory)
        if set(paths) != set(LABELS) or not callable(publish):
            raise DurableStorageUnavailable("RESTORED_STORE_PAIR_REQUIRED")
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 300:
            raise DurableStorageUnavailable("STORAGE_DEADLINE_INVALID")
        self.paths = {label: Path(paths[label]) for label in LABELS}
        if len(set(self.paths.values())) != 2:
            raise DurableStorageUnavailable("RESTORED_STORE_PAIR_REQUIRED")
        self.writer, self.publish = writer, publish
        if artifacts is None or Path(artifacts.directory).parent != self.directory:
            raise DurableStorageUnavailable("ARTIFACT_ADAPTER_REQUIRED")
        self.artifacts = artifacts
        self.timeout_seconds = timeout_seconds
        self.lock = threading.RLock()
        self.poisoned = True
        self._active_connection = False
        self.cleanup_pending = False
        self._admission_context = None
        self._pid = os.getpid()
        self._lock_fd = None
        try:
            self._lock_fd = os.open(self.directory / "writer.lock",
                                    os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            lock_metadata = os.fstat(self._lock_fd)
            if (not stat.S_ISREG(lock_metadata.st_mode) or lock_metadata.st_nlink != 1
                    or stat.S_IMODE(lock_metadata.st_mode) != 0o600):
                raise DurableStorageUnavailable("LOCAL_WRITER_LOCK_INVALID")
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if restored_head is None:
                if getattr(writer, "state", None) != "ACTIVE" or writer.head is None:
                    raise DurableStorageUnavailable("CLAIMED_RESTORED_HEAD_REQUIRED")
                restored_head = writer.head
                claim = False
            else:
                if getattr(writer, "state", None) != "NEW":
                    raise DurableStorageUnavailable("WRITER_CANNOT_RECLAIM")
                claim = True
            for label, path in self.paths.items():
                if path.parent != self.directory:
                    raise DurableStorageUnavailable("LOCAL_PATH_INVALID")
                metadata = _regular_file(path)
                expected = restored_head.value["snapshots"][label]
                if metadata.st_size != expected["size"] or _file_digest(path) != expected["sha256"]:
                    raise DurableStorageUnavailable("RESTORED_STORE_IDENTITY_MISMATCH")
                if any(os.path.lexists(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")):
                    raise DurableStorageUnavailable("CLOSED_NATIVE_SNAPSHOT_REQUIRED")
            self.artifacts.prepare(self.paths["gdw"], self.deadline())
            if claim:
                writer.claim(restored_head, self.deadline())
            writer.verify_read(self.deadline())
            self.poisoned = False
        except BaseException:
            self.close()
            raise

    def deadline(self) -> float:
        return time.monotonic() + self.timeout_seconds

    def bind_admission_context(self, *, admission_sha256: str, qualification_sha256: str,
                               source_revision: str, generations: dict[str, str],
                               actual_host_full_state_ack_ms: int) -> None:
        """Bind safe witness fields after the actual startup acknowledgement."""
        with self.lock:
            if self._admission_context is not None or _GATE is self:
                raise DurableStorageUnavailable("ADMISSION_CONTEXT_ALREADY_BOUND")
            for value, length in ((admission_sha256, 64), (qualification_sha256, 64), (source_revision, 40)):
                if (type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is None
                        or value == "0" * length):
                    raise DurableStorageUnavailable("ADMISSION_CONTEXT_INVALID")
            if (type(generations) is not dict or set(generations) != set(LABELS)
                    or type(actual_host_full_state_ack_ms) is not int
                    or not 1 <= actual_host_full_state_ack_ms <= 60_000):
                raise DurableStorageUnavailable("ADMISSION_CONTEXT_INVALID")
            self._verify()
            head = self.writer.head.value
            if (head["qualification_sha256"] != admission_sha256 or head["source_revision"] != source_revision
                    or any(head["snapshots"][label]["generation"] != generations[label] for label in LABELS)):
                raise DurableStorageUnavailable("ADMISSION_CONTEXT_IDENTITY_MISMATCH")
            self._admission_context = {
                "source_revision": source_revision, "admission_sha256": admission_sha256,
                "qualification_sha256": qualification_sha256, "generations": dict(generations),
                "actual_host_full_state_ack_ms": actual_host_full_state_ack_ms,
            }

    def managed_status(self) -> dict[str, Any]:
        """Read the exact acknowledged metadata identity under both-store lock."""
        with self.lock:
            self._verify()
            if self._admission_context is None:
                raise DurableStorageUnavailable("ADMISSION_CONTEXT_UNAVAILABLE")
            head = self.writer.head
            value = head.value
            context = self._admission_context
            if (value["qualification_sha256"] != context["admission_sha256"]
                    or value["source_revision"] != context["source_revision"]
                    or any(value["snapshots"][label]["generation"] != context["generations"][label] for label in LABELS)):
                self.poisoned = True
                raise DurableStorageUnavailable("ADMISSION_CONTEXT_IDENTITY_MISMATCH")
            return json.loads(json.dumps({
                "schema": "szl.gdw-managed-runtime/v1", "mode": MODE, **context,
                "dataset_revision": head.revision, "operation_id": value["operation_id"],
                "writer_epoch": value["epoch"], "startup_state": "RESTORED_AND_ACKNOWLEDGED",
                "throughput_claim": "NOT_CLAIMED",
            }))

    def _verify(self) -> None:
        if self.poisoned or self._pid != os.getpid() or self._lock_fd is None:
            raise DurableStorageUnavailable("DURABLE_STORAGE_POISONED")
        try:
            self.writer.verify_read(self.deadline())
        except BaseException:
            self.poisoned = True
            raise DurableStorageUnavailable("DURABLE_STORAGE_UNAVAILABLE") from None

    def connect(self, label: str, path: Path) -> "GuardedConnection":
        if not self.lock.acquire(timeout=self.timeout_seconds):
            raise DurableStorageUnavailable("LOCAL_STORAGE_BUSY")
        connection = None
        entered = False
        try:
            self._verify()
            if self._active_connection:
                raise DurableStorageUnavailable("NESTED_STORE_ACCESS_REJECTED")
            if label not in self.paths or Path(path).resolve() != self.paths[label]:
                raise DurableStorageUnavailable("UNADMITTED_STORE_PATH")
            _regular_file(self.paths[label])
            self._active_connection = entered = True
            connection = sqlite3.connect(
                self.paths[label].as_uri() + "?mode=rw", uri=True, timeout=30,
                isolation_level=None, factory=GuardedConnection,
            )
            connection.row_factory = sqlite3.Row
            if str(connection.execute("PRAGMA journal_mode").fetchone()[0]).upper() != "DELETE":
                raise DurableStorageUnavailable("CLOSED_NATIVE_SNAPSHOT_REQUIRED")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            connection._bind(self)
            return connection
        except BaseException:
            if connection is not None:
                sqlite3.Connection.close(connection)
            if entered:
                self._active_connection = False
            self.lock.release()
            raise

    def acknowledge(self) -> None:
        self.poisoned = True
        deadline = self.deadline()
        directory = self.directory / ("snapshot-" + uuid.uuid4().hex)
        directory.mkdir(mode=0o700)
        snapshots = {}
        try:
            for label, path in self.paths.items():
                target = directory / (label + ".sqlite3")
                descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                destination = sqlite3.connect(target)
                try:
                    def progress(_status, _remaining, _total):
                        if time.monotonic() >= deadline:
                            raise DurableStorageUnavailable("STORAGE_DEADLINE_EXCEEDED")
                    source.backup(destination, pages=128, progress=progress, sleep=0.01)
                    destination.set_progress_handler(
                        lambda: int(time.monotonic() >= deadline), 1000
                    )
                    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise DurableStorageUnavailable("SNAPSHOT_INTEGRITY_FAILED")
                    if destination.execute("PRAGMA foreign_key_check").fetchone() is not None:
                        raise DurableStorageUnavailable("SNAPSHOT_FOREIGN_KEY_FAILED")
                    if time.monotonic() >= deadline:
                        raise DurableStorageUnavailable("STORAGE_DEADLINE_EXCEEDED")
                finally:
                    destination.close()
                    source.close()
                snapshots[label] = target
            self.artifacts.prepare(snapshots["gdw"], deadline)
            identities = self.publish(snapshots, deadline)
            if not isinstance(identities, Mapping) or set(identities) != set(LABELS):
                raise DurableStorageUnavailable("PUBLISHED_SNAPSHOT_IDENTITY_MISMATCH")
            for label, path in snapshots.items():
                record = identities[label]
                if (not isinstance(record, Mapping)
                        or record.get("size") != path.stat().st_size
                        or record.get("sha256") != _file_digest(path)
                        or record.get("generation") != self.writer.head.value["snapshots"][label]["generation"]):
                    raise DurableStorageUnavailable("PUBLISHED_SNAPSHOT_IDENTITY_MISMATCH")
            if time.monotonic() >= deadline:
                raise DurableStorageUnavailable("STORAGE_DEADLINE_EXCEEDED")
            self.writer.commit(identities, deadline)
            if time.monotonic() >= deadline:
                raise DurableStorageUnavailable("STORAGE_DEADLINE_EXCEEDED")
            self.poisoned = False
        except BaseException:
            raise DurableStorageUnavailable("DURABLE_STORAGE_OUTCOME_UNCERTAIN") from None
        # Retain failed candidates for private reconciliation; successful local
        # copies are no longer authoritative and can be removed without provider I/O.
        try:
            for path in snapshots.values():
                path.unlink()
            directory.rmdir()
        except OSError:
            # Remote acknowledgement is already proven. A private local cleanup
            # failure does not change its outcome or justify repeating the write.
            self.cleanup_pending = True

    def close(self) -> None:
        self.poisoned = True
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None


class GuardedConnection(sqlite3.Connection):
    """A store connection owns the shared gate until it is closed."""

    _gate = None
    _closed = False
    _allow_commit = False

    def _bind(self, gate: LocalGate) -> None:
        self._gate = gate
        self._baseline = self.total_changes
        self.set_authorizer(self._authorize)

    def _authorize(self, action, _first, second, _database, _trigger):
        if action == sqlite3.SQLITE_TRANSACTION and _first == "COMMIT":
            return sqlite3.SQLITE_OK if self._allow_commit else sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            return sqlite3.SQLITE_OK if self.in_transaction else sqlite3.SQLITE_DENY
        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH,
                      sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_TABLE,
                      sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_CREATE_INDEX,
                      sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_CREATE_TRIGGER,
                      sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_VIEW,
                      sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_SAVEPOINT):
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_PRAGMA and second is not None:
            # Schema inspection has an argument but does not mutate SQLite.
            if _first not in {"table_info", "index_info", "foreign_key_list"}:
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def executescript(self, _script):
        raise DurableStorageUnavailable("RUNTIME_SCHEMA_MUTATION_REJECTED")

    def commit(self) -> None:
        self._gate._verify()
        changed = self.total_changes != self._baseline
        self._allow_commit = True
        try:
            super().commit()
            if changed:
                self._gate.acknowledge()
            self._baseline = self.total_changes
        except BaseException:
            self._gate.poisoned = True
            raise
        finally:
            self._allow_commit = False

    def rollback(self) -> None:
        super().rollback()
        self._baseline = self.total_changes

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def close(self) -> None:
        if self._closed:
            return
        if self._gate is None:
            return super().close()
        try:
            if self.in_transaction:
                self.rollback()
            if self.total_changes != self._baseline:
                self._gate.poisoned = True
            self._gate._verify()
        finally:
            self._closed = True
            super().close()
            self._gate._active_connection = False
            self._gate.lock.release()


def install(gate: LocalGate) -> None:
    """Called once by the qualified startup coordinator before importing routes."""
    global _GATE
    with _INSTALL_LOCK:
        if _GATE is not None or not isinstance(gate, LocalGate):
            raise DurableStorageUnavailable("DURABLE_STORAGE_ALREADY_INSTALLED")
        gate._verify()
        _GATE = gate


def require_gate() -> LocalGate:
    if _GATE is None:
        raise DurableStorageUnavailable("QUALIFIED_STORAGE_STARTUP_REQUIRED")
    if not _GATE.lock.acquire(timeout=_GATE.timeout_seconds):
        raise DurableStorageUnavailable("LOCAL_STORAGE_BUSY")
    try:
        _GATE._verify()
    finally:
        _GATE.lock.release()
    return _GATE


def connect(label: str, path: Path) -> GuardedConnection:
    return require_gate().connect(label, path)


def ready(storage: Mapping[str, Any]) -> bool:
    """Verify the claimed authority without treating a mount as durability."""
    try:
        if (not enabled() or storage.get("durable_storage") != MODE
                or storage.get("durability_authority") != "verified-private-dataset-head"):
            return False
        require_gate()
        return True
    except DurableStorageUnavailable:
        return False
