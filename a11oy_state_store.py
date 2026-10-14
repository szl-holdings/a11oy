#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: a11oy local state store, immutable bucket snapshots and a CAS lease.

Decision record: docs/adr/ADR-0001-a11oy-state-store.md.

Why this exists. On 2026-10-04 overlapping container lifetimes during a deploy
left two orphan pages in the GDW SQLite file, because live SQLite and LMDB files
sat on a read-write HF Storage Bucket FUSE mount (/data). The Space then
crash-looped for about 41 hours. A FUSE object mount does not give SQLite or
LMDB the locking and write ordering they need, and no repair at boot changes
that. This module moves every live store off the mount:

* Live files live under a local root (default /tmp/a11oy-state). Boot verifies
  through /proc/self/mountinfo that the root is a local filesystem, private to
  this process user (mode 0700). Nothing under /data is ever opened for writing.
* Durability comes from immutable snapshot objects in the bucket,
  a11oy/state/v2/<label>/<utc>-<epoch>-<seq>-<sha16>.<ext>. A snapshot is the
  SQLite backup API (or an LMDB compact copy), then quick_check (hourly a full
  integrity_check), foreign_key_check, logical fingerprint and sha256, then an
  upload and a size/sha256 readback. The live database is never touched by a
  failed snapshot; failures retry with backoff and show on the status route.
* One small HEAD manifest (epoch, writer, boot, lease state, latest snapshots
  and up to five previous ones per store) is advanced by compare-and-swap. The
  bucket has no CAS, so HEAD lives in a dedicated private dataset
  (A11OY_STATE_DATASET, default SZLHOLDINGS/a11oy-state) and every change is a
  ``create_commit(parent_commit=...)``; only HTTP 412 is a definite conflict.
  If that dataset does not exist the store runs in SNAPSHOT_ONLY_UNFENCED mode
  and says so loudly. This module never creates a repository.
* Single writer across overlapping containers: a new container asks the
  current writer to hand over (HANDOVER_REQUESTED). The writer's 15 s heartbeat
  sees it, refuses writes with 503 + Retry-After, takes final snapshots and
  marks HEAD RELEASED. The new container restores, verifies and claims epoch+1
  before serve.py is imported, so it never serves before it owns the stores.
  A writer that does not answer within 120 s (or whose heartbeat is stale) is
  taken over from the latest snapshots and the claim is recorded as
  UNCLEAN_HANDOVER.
* Boot never crash-loops. A store that cannot be restored is BLOCKED and its
  last good snapshot stays in HEAD; GDW maps that onto its existing degraded
  mode and every other store onto a process-wide write fence.

Durable v1 (GDW_DURABLE_STORAGE=private-dataset-v1, gdw_durable_*.py) is
RETIRED. It is left inert and is not extended. This module reuses its error
taxonomy and canonical encoding from gdw_durable_storage, and its local
filesystem admission check from gdw_durable_runtime. It does not reuse v1's
Head/advance/HFDatasetFenceBackend: those are bound to the v1 two-store
schema, the shared szl-evidence dataset and an exact SDK version pin, which
are the defects that retired v1. ``source_revision`` here is informational.
"""

import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

import gdw_sqlite_repair
from gdw_durable_storage import ParentConflict, StorageBlocked, canonical


# --------------------------------------------------------------------------- #
# Identity and configuration
# --------------------------------------------------------------------------- #
HEAD_SCHEMA = "szl.a11oy-state-head/v2"
STATUS_SCHEMA = "szl.a11oy-storage-status/v2"
FROZEN_SCHEMA = "szl.a11oy-legacy-frozen/v1"
HEARTBEAT_SCHEMA = "szl.a11oy-state-heartbeat/v1"
PREFIX = "a11oy/state/v2"
HEAD_PATH = "state/v2/head.json"
LEGACY_FROZEN_PATH = PREFIX + "/LEGACY_FROZEN.json"
HEARTBEAT_PATH = PREFIX + "/lease/heartbeat.json"
UNFENCED_HEAD_PATH = PREFIX + "/HEAD.unfenced.json"
ENABLE_ENV = "A11OY_STATE_STORE"
ENABLED_VALUE = "v2"
DEFAULT_ROOT = "/tmp/a11oy-state"
DEFAULT_BUCKET = "SZLHOLDINGS/szl-evidence"
DEFAULT_DATASET = "SZLHOLDINGS/a11oy-state"
DEFAULT_LEGACY_ROOT = "/data"
DURABLE_V1_ENV = "GDW_DURABLE_STORAGE"
HISTORY_DEPTH = 5
MAX_HEAD_BYTES = 64 * 1024
MAX_SMALL_OBJECT_BYTES = 64 * 1024

MODE_DISABLED = "DISABLED"
MODE_FENCED = "FENCED"
MODE_UNFENCED = "SNAPSHOT_ONLY_UNFENCED"

STATE_ACTIVE = "ACTIVE"
STATE_HANDOVER = "HANDOVER_REQUESTED"
STATE_RELEASED = "RELEASED"
LEASE_STATES = (STATE_ACTIVE, STATE_HANDOVER, STATE_RELEASED)

ROLE_NOT_ACTIVATED = "NOT_ACTIVATED"
ROLE_BOOTING = "BOOTING"
ROLE_WRITER = "WRITER"
ROLE_UNFENCED_WRITER = "UNFENCED_WRITER"
ROLE_HANDOVER = "HANDING_OVER"
ROLE_RELEASED = "RELEASED"
ROLE_FENCED = "FENCED"
ROLE_BLOCKED = "BLOCKED"
WRITABLE_ROLES = (ROLE_WRITER, ROLE_UNFENCED_WRITER)

CLAIM_CLEAN = "CLEAN"
CLAIM_UNCLEAN = "UNCLEAN_HANDOVER"
CLAIM_FIRST_BOOT = "FIRST_BOOT"

ORIGIN_RESTORED = "RESTORED"
ORIGIN_LEGACY = "LEGACY_BOOTSTRAP"
ORIGIN_ADOPTED = "ADOPTED_UNFENCED_SNAPSHOT"
ORIGIN_FRESH = "FRESH"

TRANSITIONS = ("BOOTSTRAP", "CLAIM", "SNAPSHOT", "HANDOVER_REQUEST", "RELEASE")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RETRY_AFTER_SECONDS = 30
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_OBJECT_NAME = re.compile(
    r"(?P<stamp>\d{8}T\d{6}Z)-(?P<epoch>\d{1,18})-(?P<seq>\d{1,18})-(?P<sha16>[0-9a-f]{16})"
    r"\.(?P<ext>sqlite3|mdb)\Z")
_LABEL = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


def _log(message: str) -> None:
    print(f"[a11oy-state] {message}", file=sys.stderr, flush=True)


def _iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _code(error: BaseException) -> str:
    for candidate in (getattr(error, "code", None), str(error)):
        if isinstance(candidate, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,79}", candidate):
            return candidate
    return type(error).__name__


@dataclass(frozen=True)
class StoreSpec:
    """One live store: its local location and where the legacy copy sat."""
    label: str
    kind: str  # "sqlite" or "lmdb"
    local: str  # path relative to the local root
    legacy_env: Optional[str]
    legacy_suffix: Optional[str]  # joined to the legacy_env directory, if any
    legacy_default: str  # path relative to the legacy root

    @property
    def extension(self) -> str:
        return "sqlite3" if self.kind == "sqlite" else "mdb"


# The khipu, council, unay and LMDB names carry the a11oy namespace that
# serve.py registers (harden(app, organ="a11oy"), ayllu/unay ns="a11oy").
STORES: tuple[StoreSpec, ...] = (
    StoreSpec("gdw", "sqlite", "gdw/gdw.sqlite3", "GDW_DB_PATH", None,
              "a11oy/gdw/gdw.sqlite3"),
    StoreSpec("series_a", "sqlite", "series-a/control-plane-v2.sqlite3",
              "A11OY_SERIES_A_DB", None, "a11oy/series-a/control-plane-v2.sqlite3"),
    StoreSpec("khipu", "sqlite", "khipu/khipu_a11oy.sqlite3", "SZL_KHIPU_DIR",
              "khipu_a11oy.sqlite3", "khipu/khipu_a11oy.sqlite3"),
    StoreSpec("khipu_council", "sqlite", "khipu/khipu_a11oy_council.sqlite3",
              "SZL_KHIPU_DIR", "khipu_a11oy_council.sqlite3",
              "khipu/khipu_a11oy_council.sqlite3"),
    StoreSpec("unay", "sqlite", "unay/unay_a11oy.sqlite", "UNAY_DATA_DIR",
              "unay_a11oy.sqlite", "unay_a11oy.sqlite"),
    StoreSpec("khipu_lmdb", "lmdb", "unay/khipu_lmdb_a11oy", "UNAY_DATA_DIR",
              "khipu_lmdb_a11oy", "khipu_lmdb_a11oy"),
    StoreSpec("khipu_repl", "lmdb", "unay/khipu_repl_a11oy", "UNAY_DATA_DIR",
              "khipu_repl_a11oy", "khipu_repl_a11oy"),
)
# Module directories handed to code that derives its own file names.
DIRECTORIES = {"khipu": "khipu", "unay": "unay"}


def _bounded(values: Mapping[str, str], name: str, default: float,
             minimum: float, maximum: float) -> float:
    raw = (values.get(name) or "").strip()
    try:
        parsed = float(raw) if raw else float(default)
    except ValueError:
        raise StorageBlocked("STATE_SETTING_INVALID") from None
    if not minimum <= parsed <= maximum:
        raise StorageBlocked("STATE_SETTING_OUT_OF_RANGE")
    return parsed


@dataclass(frozen=True)
class Settings:
    root: Path
    bucket: str
    dataset: str
    legacy_root: Path
    debounce_s: float = 30.0
    periodic_s: float = 300.0
    heartbeat_s: float = 15.0
    stale_s: float = 120.0
    alert_s: float = 900.0
    full_integrity_s: float = 3600.0
    boot_deadline_s: float = 600.0
    drain_s: float = 20.0
    poll_s: float = 3.0

    @classmethod
    def from_environ(cls, environ: Optional[Mapping[str, str]] = None) -> "Settings":
        values = os.environ if environ is None else environ
        return cls(
            root=Path(values.get("A11OY_STATE_ROOT") or DEFAULT_ROOT),
            bucket=(values.get("A11OY_STATE_BUCKET") or DEFAULT_BUCKET).strip(),
            dataset=(values.get("A11OY_STATE_DATASET") or DEFAULT_DATASET).strip(),
            legacy_root=Path(values.get("A11OY_STATE_LEGACY_ROOT") or DEFAULT_LEGACY_ROOT),
            debounce_s=_bounded(values, "A11OY_STATE_DEBOUNCE_SECONDS", 30, 1, 3600),
            periodic_s=_bounded(values, "A11OY_STATE_PERIODIC_SECONDS", 300, 5, 86400),
            heartbeat_s=_bounded(values, "A11OY_STATE_HEARTBEAT_SECONDS", 15, 1, 300),
            stale_s=_bounded(values, "A11OY_STATE_LEASE_STALE_SECONDS", 120, 10, 3600),
            alert_s=_bounded(values, "A11OY_STATE_ALERT_SECONDS", 900, 60, 86400),
            full_integrity_s=_bounded(values, "A11OY_STATE_FULL_INTEGRITY_SECONDS", 3600, 60, 86400),
            boot_deadline_s=_bounded(values, "A11OY_STATE_BOOT_DEADLINE_SECONDS", 600, 5, 3600),
        )


def enabled(environ: Optional[Mapping[str, str]] = None) -> bool:
    values = os.environ if environ is None else environ
    return (values.get(ENABLE_ENV) or "").strip().lower() == ENABLED_VALUE


def legacy_path(spec: StoreSpec, environ: Mapping[str, str], legacy_root: Path) -> Path:
    """Where the pre-v2 runtime kept this store. Read once, never written."""
    configured = (environ.get(spec.legacy_env) or "").strip() if spec.legacy_env else ""
    if configured:
        candidate = Path(configured)
        if spec.legacy_suffix:
            candidate = candidate / spec.legacy_suffix
        return candidate
    return legacy_root / spec.legacy_default


# --------------------------------------------------------------------------- #
# Local filesystem primitives
# --------------------------------------------------------------------------- #
def verify_local_root(root: Path) -> Path:
    """Create the private root and admit it only on a local filesystem.

    Reuses durable v1's mountinfo admission (explicit local filesystem types
    only; a write probe cannot prove a FUSE mount supports SQLite locking).
    """
    root = Path(root)
    if not root.is_absolute():
        raise StorageBlocked("STATE_ROOT_NOT_ABSOLUTE")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    try:
        from gdw_durable_runtime import _private_directory
        return _private_directory(root.resolve())
    except StorageBlocked:
        raise
    except Exception as error:
        code = _code(error)
        raise StorageBlocked(code if code.isupper() else "LOCAL_POSIX_STORAGE_REQUIRED") from None


def _fsync_path(path: Path) -> None:
    with open(path, "rb+") as stream:
        os.fsync(stream.fileno())


def _stat_signature(path: Path) -> Optional[tuple[int, int]]:
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return None
    return (metadata.st_size, metadata.st_mtime_ns)


def _copy_stable(source: Path, target: Path, *, attempts: int = 3) -> None:
    """Read-only byte copy that refuses a source that changed while copied."""
    for _ in range(attempts):
        before = _stat_signature(source)
        if before is None:
            raise StorageBlocked("LEGACY_SOURCE_MISSING")
        target.unlink(missing_ok=True)
        with open(source, "rb") as reader, open(target, "xb") as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        if _stat_signature(source) == before and target.stat().st_size == before[0]:
            return
    raise StorageBlocked("LEGACY_SOURCE_UNSTABLE")


def sqlite_backup(source: Path, target: Path) -> None:
    """Consistent online copy through the SQLite backup API."""
    target.unlink(missing_ok=True)
    origin = sqlite3.connect(str(source), timeout=30)
    try:
        copy = sqlite3.connect(str(target))
        try:
            origin.backup(copy)
        finally:
            copy.close()
    finally:
        origin.close()
    _fsync_path(target)


def _read_only(path: Path) -> sqlite3.Connection:
    # Shared by the snapshot thread and the shutdown path, never concurrently.
    return sqlite3.connect(gdw_sqlite_repair._read_only_uri(path), uri=True, timeout=30,
                           check_same_thread=False)


def verify_sqlite(path: Path, *, full: bool) -> dict[str, Any]:
    """Integrity (quick or full), foreign keys and logical fingerprint."""
    connection = _read_only(path)
    try:
        if full:
            lines = gdw_sqlite_repair.integrity_lines(connection)
        else:
            lines = [str(row[0]) for row in connection.execute("PRAGMA quick_check").fetchall()]
        ok = lines == ["ok"]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall()) if ok else None
        logical = None
        if ok:
            try:
                logical = gdw_sqlite_repair.logical_fingerprint(connection)["sha256"]
            except gdw_sqlite_repair.OrphanRepairError:
                logical = None
    finally:
        connection.close()
    return {
        "ok": ok and foreign_keys == 0,
        "integrity": "integrity_check" if full else "quick_check",
        "integrity_ok": ok,
        "foreign_key_violations": foreign_keys,
        "orphan_pages": None if ok or not full else gdw_sqlite_repair.classify_orphan_pages(lines),
        "logical_sha256": logical,
        "detail": lines[:3],
    }


def _lmdb():
    import lmdb  # runtime dependency (requirements-runtime.txt); optional in tests
    return lmdb


def lmdb_logical_digest(directory: Path) -> dict[str, Any]:
    """Every key and value, in LMDB order, from a read-only lock-free open."""
    lmdb = _lmdb()
    env = lmdb.open(str(directory), readonly=True, lock=False, subdir=True, max_dbs=0)
    digest = hashlib.sha256(b"szl.lmdb-logical/v1\n")
    entries = 0
    try:
        with env.begin(buffers=False) as txn:
            for key, value in txn.cursor():
                for item in (key, value):
                    digest.update(len(item).to_bytes(8, "big"))
                    digest.update(item)
                entries += 1
    finally:
        env.close()
    return {"entries": entries, "logical_sha256": digest.hexdigest()}


def _registered_lmdb_env(path: Path) -> Any:
    module = sys.modules.get("szl_khipu_lmdb")
    registry = getattr(module, "_ENV_REGISTRY", None)
    if not isinstance(registry, dict):
        return None
    return registry.get(os.path.abspath(str(path)))


# --------------------------------------------------------------------------- #
# Provider boundaries
# --------------------------------------------------------------------------- #
class DatasetUnavailable(StorageBlocked):
    """The fence dataset definitely does not exist or is not private."""


class HeadChanged(StorageBlocked):
    """HEAD moved under a CAS; the caller re-classifies from ``observed``."""

    def __init__(self, observed: "Observation"):
        super().__init__("HEAD_CHANGED")
        self.observed = observed


@dataclass(frozen=True)
class Observation:
    revision: str
    body: Optional[bytes]


class LocalDirObjectStore:
    """Directory-backed object store for tests and local development."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, remote: str) -> Path:
        if remote.startswith("/") or ".." in remote.split("/"):
            raise StorageBlocked("OBJECT_PATH_INVALID")
        return self.root / remote

    def put_file(self, local: Path, remote: str) -> None:
        target = self._path(remote)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, target)

    def put_bytes(self, remote: str, data: bytes) -> None:
        target = self._path(remote)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def size(self, remote: str) -> Optional[int]:
        target = self._path(remote)
        return target.stat().st_size if target.is_file() else None

    def get_file(self, remote: str, local: Path) -> None:
        target = self._path(remote)
        if not target.is_file():
            raise StorageBlocked("OBJECT_MISSING")
        shutil.copyfile(target, local)

    def get_bytes(self, remote: str, limit: int = MAX_SMALL_OBJECT_BYTES) -> Optional[bytes]:
        target = self._path(remote)
        if not target.is_file():
            return None
        data = target.read_bytes()
        if len(data) > limit:
            raise StorageBlocked("OBJECT_TOO_LARGE")
        return data

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix.rstrip("/"))
        if not base.is_dir():
            return []
        return sorted(path.relative_to(self.root).as_posix()
                      for path in base.rglob("*") if path.is_file())


class HFBucketObjectStore:
    """Snapshot objects in the private HF Storage Bucket, through the Hub API.

    The bucket is used as an object store only; nothing here relies on the
    /data FUSE mount.
    """

    def __init__(self, api: Any, bucket_id: str, scratch: Path):
        self.api = api
        self.bucket_id = bucket_id
        self.scratch = Path(scratch)

    def put_file(self, local: Path, remote: str) -> None:
        self.api.batch_bucket_files(self.bucket_id, add=[(str(local), remote)])

    def put_bytes(self, remote: str, data: bytes) -> None:
        self.api.batch_bucket_files(self.bucket_id, add=[(bytes(data), remote)])

    def size(self, remote: str) -> Optional[int]:
        for item in self.api.get_bucket_paths_info(self.bucket_id, [remote]):
            if getattr(item, "path", None) == remote and getattr(item, "type", "file") == "file":
                return int(getattr(item, "size"))
        return None

    def get_file(self, remote: str, local: Path) -> None:
        self.api.download_bucket_files(self.bucket_id, files=[(remote, str(local))],
                                       raise_on_missing_files=True)

    def get_bytes(self, remote: str, limit: int = MAX_SMALL_OBJECT_BYTES) -> Optional[bytes]:
        size = self.size(remote)
        if size is None:
            return None
        if size > limit:
            raise StorageBlocked("OBJECT_TOO_LARGE")
        self.scratch.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="obj-", dir=str(self.scratch)))
        try:
            target = directory / "object"
            self.get_file(remote, target)
            return target.read_bytes()
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def list(self, prefix: str) -> list[str]:
        paths = []
        for item in self.api.list_bucket_tree(self.bucket_id, prefix=prefix, recursive=True):
            if getattr(item, "type", "file") == "file":
                paths.append(str(getattr(item, "path")))
        return sorted(paths)


class HFDatasetHeadBackend:
    """HEAD in a dedicated private dataset; ``parent_commit`` is the CAS.

    Same discipline as durable v1's fence: one submission per attempt and only
    an HTTP 412 is a definite conflict. An uncertain submission is resolved by
    reading HEAD, because every manifest carries a fresh operation_id.
    """

    def __init__(self, api: Any, repo_id: str, scratch: Path):
        self.api = api
        self.repo_id = repo_id
        self.scratch = Path(scratch)

    def _info(self, revision: Optional[str] = None) -> str:
        try:
            info = self.api.dataset_info(self.repo_id, revision=revision)
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if type(error).__name__ == "RepositoryNotFoundError" or status == 404:
                raise DatasetUnavailable("STATE_DATASET_ABSENT") from None
            if type(error).__name__ == "GatedRepoError" or status in (401, 403):
                raise DatasetUnavailable("STATE_DATASET_FORBIDDEN") from None
            raise StorageBlocked("STATE_DATASET_UNREACHABLE") from None
        if getattr(info, "private", None) is not True:
            raise DatasetUnavailable("STATE_DATASET_NOT_PRIVATE")
        sha = getattr(info, "sha", None)
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise DatasetUnavailable("STATE_DATASET_UNINITIALIZED")
        return sha

    def probe(self) -> None:
        self._info()

    def read_at(self, revision: str) -> Optional[bytes]:
        try:
            items = self.api.get_paths_info(self.repo_id, [HEAD_PATH], repo_type="dataset",
                                            revision=revision)
        except Exception:
            raise StorageBlocked("STATE_HEAD_UNREADABLE") from None
        if not items:
            return None
        size = getattr(items[0], "size", None)
        if not isinstance(size, int) or not 1 <= size <= MAX_HEAD_BYTES:
            raise StorageBlocked("STATE_HEAD_SIZE_INVALID")
        self.scratch.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="head-", dir=str(self.scratch)))
        try:
            local = self.api.hf_hub_download(self.repo_id, HEAD_PATH, repo_type="dataset",
                                             revision=revision, local_dir=str(directory))
            data = Path(local).read_bytes()
        except Exception:
            raise StorageBlocked("STATE_HEAD_UNREADABLE") from None
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        if len(data) != size:
            raise StorageBlocked("STATE_HEAD_SIZE_INVALID")
        return data

    def observe(self) -> Observation:
        revision = self._info()
        return Observation(revision, self.read_at(revision))

    def submit(self, parent: str, body: bytes, operation_id: str) -> str:
        from huggingface_hub import CommitOperationAdd
        operations = [CommitOperationAdd(path_in_repo=HEAD_PATH, path_or_fileobj=body)]
        try:
            result = self.api.create_commit(
                self.repo_id, operations=operations, repo_type="dataset", revision="main",
                parent_commit=parent, create_pr=False,
                commit_message=f"chore(a11oy-state): advance HEAD {operation_id[:12]}")
        except Exception as error:
            if getattr(getattr(error, "response", None), "status_code", None) == 412:
                raise ParentConflict() from None
            raise StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN") from None
        revision = getattr(result, "oid", None)
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")
        return revision


# --------------------------------------------------------------------------- #
# HEAD manifest
# --------------------------------------------------------------------------- #
def _entry_valid(label: str, entry: Any) -> bool:
    fields = {"path", "sha256", "size", "kind", "integrity", "logical_sha256", "taken_at",
              "epoch", "seq"}
    if type(entry) is not dict or set(entry) != fields:
        return False
    name = entry["path"].rsplit("/", 1)[-1] if isinstance(entry["path"], str) else ""
    match = _OBJECT_NAME.fullmatch(name)
    return (isinstance(entry["path"], str) and entry["path"] == f"{PREFIX}/{label}/{name}"
            and match is not None and isinstance(entry["sha256"], str)
            and _HEX64.fullmatch(entry["sha256"]) is not None
            and match.group("sha16") == entry["sha256"][:16]
            and type(entry["size"]) is int and entry["size"] >= 1
            and entry["kind"] in ("sqlite", "lmdb")
            and entry["integrity"] in ("integrity_check", "quick_check", "lmdb_read")
            and (entry["logical_sha256"] is None
                 or (isinstance(entry["logical_sha256"], str)
                     and _HEX64.fullmatch(entry["logical_sha256"]) is not None))
            and isinstance(entry["taken_at"], str)
            and type(entry["epoch"]) is int and type(entry["seq"]) is int)


def validate_head(value: Any) -> dict[str, Any]:
    fields = {"schema", "operation_id", "sequence", "previous_manifest_sha256", "epoch",
              "writer_id", "boot_id", "state", "transition", "handover", "claim", "lease",
              "source_revision", "bucket", "snapshots", "history"}
    if type(value) is not dict or set(value) != fields or value["schema"] != HEAD_SCHEMA:
        raise StorageBlocked("STATE_HEAD_INVALID")
    if (not isinstance(value["operation_id"], str) or not _HEX32.fullmatch(value["operation_id"])
            or not isinstance(value["writer_id"], str) or not _HEX32.fullmatch(value["writer_id"])
            or not isinstance(value["boot_id"], str) or not _HEX32.fullmatch(value["boot_id"])
            or type(value["sequence"]) is not int or value["sequence"] < 1
            or type(value["epoch"]) is not int or value["epoch"] < 1
            or value["state"] not in LEASE_STATES or value["transition"] not in TRANSITIONS
            or not isinstance(value["bucket"], str) or not isinstance(value["source_revision"], str)):
        raise StorageBlocked("STATE_HEAD_INVALID")
    previous = value["previous_manifest_sha256"]
    if (value["sequence"] == 1) != (previous is None) or (
            previous is not None and (not isinstance(previous, str) or not _HEX64.fullmatch(previous))):
        raise StorageBlocked("STATE_HEAD_INVALID")
    handover = value["handover"]
    if value["state"] == STATE_HANDOVER:
        if (type(handover) is not dict or set(handover) != {"requested_by", "requested_at"}
                or not isinstance(handover["requested_by"], str)
                or not _HEX32.fullmatch(handover["requested_by"])):
            raise StorageBlocked("STATE_HEAD_INVALID")
    elif handover is not None:
        raise StorageBlocked("STATE_HEAD_INVALID")
    claim, lease = value["claim"], value["lease"]
    if (type(claim) is not dict or set(claim) != {"kind", "at", "origins", "previous_epoch"}
            or claim["kind"] not in (CLAIM_CLEAN, CLAIM_UNCLEAN, CLAIM_FIRST_BOOT)
            or type(claim["origins"]) is not dict
            or type(lease) is not dict or set(lease) != {"renewed_at", "heartbeat_path", "stale_after_seconds"}):
        raise StorageBlocked("STATE_HEAD_INVALID")
    labels = {spec.label for spec in STORES}
    snapshots, history = value["snapshots"], value["history"]
    if type(snapshots) is not dict or type(history) is not dict:
        raise StorageBlocked("STATE_HEAD_INVALID")
    for label, entry in snapshots.items():
        if label not in labels or not _entry_valid(label, entry):
            raise StorageBlocked("STATE_HEAD_SNAPSHOT_INVALID")
    for label, entries in history.items():
        if (label not in labels or type(entries) is not list or len(entries) > HISTORY_DEPTH
                or not all(_entry_valid(label, entry) for entry in entries)):
            raise StorageBlocked("STATE_HEAD_SNAPSHOT_INVALID")
    rendered = canonical(value)
    if len(rendered) > MAX_HEAD_BYTES:
        raise StorageBlocked("STATE_HEAD_TOO_LARGE")
    return json.loads(rendered)


def parse_head(body: bytes) -> dict[str, Any]:
    if type(body) is not bytes or not 1 <= len(body) <= MAX_HEAD_BYTES:
        raise StorageBlocked("STATE_HEAD_INVALID")
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise StorageBlocked("STATE_HEAD_INVALID") from None
    value = validate_head(value)
    if canonical(value) != body:
        raise StorageBlocked("STATE_HEAD_NONCANONICAL")
    return value


def validate_transition(before: Optional[dict[str, Any]], after: dict[str, Any]) -> None:
    """The lease rules every HEAD change must keep."""
    kind = after["transition"]
    if before is None:
        if (kind != "BOOTSTRAP" or after["sequence"] != 1 or after["epoch"] != 1
                or after["state"] != STATE_ACTIVE):
            raise StorageBlocked("STATE_TRANSITION_INVALID")
        return
    if after["sequence"] != before["sequence"] + 1 or kind == "BOOTSTRAP":
        raise StorageBlocked("STATE_TRANSITION_INVALID")
    same_writer = after["epoch"] == before["epoch"] and after["writer_id"] == before["writer_id"]
    if kind == "CLAIM":
        valid = (after["epoch"] == before["epoch"] + 1 and after["writer_id"] != before["writer_id"]
                 and after["state"] == STATE_ACTIVE and after["snapshots"] == before["snapshots"])
    elif kind == "SNAPSHOT":
        valid = same_writer and before["state"] == STATE_ACTIVE and after["state"] == STATE_ACTIVE
    elif kind == "HANDOVER_REQUEST":
        valid = (same_writer and before["state"] == STATE_ACTIVE and after["state"] == STATE_HANDOVER
                 and after["snapshots"] == before["snapshots"])
    elif kind == "RELEASE":
        valid = (same_writer and before["state"] in (STATE_ACTIVE, STATE_HANDOVER)
                 and after["state"] == STATE_RELEASED)
    else:
        valid = False
    if not valid:
        raise StorageBlocked("STATE_TRANSITION_INVALID")


def cas_advance(backend: Any, expected: Observation, proposal: dict[str, Any],
                *, attempts: int = 3) -> Observation:
    """Replace exactly ``expected`` with ``proposal``; never a blind overwrite.

    ``expected.body`` None means "HEAD absent" (first bootstrap). A changed HEAD
    raises HeadChanged carrying what was observed. An uncertain submission is
    resolved by reading: the fresh operation_id makes our own body unique.
    """
    before = parse_head(expected.body) if expected.body is not None else None
    after = validate_head(proposal)
    validate_transition(before, after)
    if before is not None and after["previous_manifest_sha256"] != _sha256_bytes(expected.body):
        raise StorageBlocked("STATE_TRANSITION_INVALID")
    body = canonical(after)
    for _ in range(attempts):
        observed = backend.observe()
        if observed.body != expected.body:
            if observed.body == body:
                return observed
            raise HeadChanged(observed)
        try:
            revision = backend.submit(observed.revision, body, after["operation_id"])
        except ParentConflict:
            continue
        except StorageBlocked as error:
            if error.code != "STATE_HEAD_OUTCOME_UNCERTAIN":
                raise
            current = backend.observe()
            if current.body == body:
                return current
            if current.body != expected.body:
                raise HeadChanged(current) from None
            continue
        if backend.read_at(revision) != body:
            raise StorageBlocked("STATE_HEAD_READBACK_MISMATCH")
        return Observation(revision, body)
    raise StorageBlocked("STATE_HEAD_CONTENTION")


# --------------------------------------------------------------------------- #
# The store
# --------------------------------------------------------------------------- #
@dataclass
class StoreState:
    spec: StoreSpec
    origin: str = ORIGIN_FRESH
    health: str = "OK"
    blocked_code: Optional[str] = None
    entry: Optional[dict[str, Any]] = None
    signature: Any = None
    seen: Any = None
    dirty_since: Optional[float] = None
    changed_at: Optional[float] = None
    captured_at: Optional[float] = None
    full_integrity_at: float = 0.0
    failures: int = 0
    next_attempt_at: float = 0.0
    last_error: Optional[str] = None


class StateStore:
    def __init__(self, *, settings: Settings, objects: Any, head_backend: Any = None,
                 environ: Optional[Mapping[str, str]] = None,
                 specs: Iterable[StoreSpec] = STORES,
                 clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 local_root_check: Callable[[Path], Path] = verify_local_root,
                 source_revision: str = ""):
        self.settings = settings
        self.objects = objects
        self.backend = head_backend
        self.environ = dict(os.environ if environ is None else environ)
        self.specs = tuple(specs)
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        self.local_root_check = local_root_check
        self.source_revision = source_revision[:64]
        self.mode = MODE_FENCED if head_backend is not None else MODE_UNFENCED
        self.mode_reason: Optional[str] = None if head_backend is not None else "STATE_DATASET_ABSENT"
        self.role = ROLE_BOOTING
        self.boot_id = uuid.uuid4().hex
        self.writer_id = uuid.uuid4().hex
        self.epoch: Optional[int] = None
        self.head: Optional[Observation] = None
        self.claim_kind: Optional[str] = None
        self.stores = {spec.label: StoreState(spec) for spec in self.specs}
        self.last_error: Optional[dict[str, Any]] = None
        self._active_errors: dict[str, dict[str, Any]] = {}
        self._error_history: dict[str, dict[str, Any]] = {}
        self._error_lock = threading.RLock()
        self.heartbeat_at: Optional[float] = None
        self.durable_v1_env_ignored = False
        self._seq = 0
        self._unpublished: dict[str, dict[str, Any]] = {}
        self._publish_failures = 0
        self._publish_next_at = 0.0
        self._lock = threading.RLock()
        self._inflight = 0
        self._inflight_cond = threading.Condition()
        self._quiesce_hooks: list[Callable[[], Any]] = []
        self._watchers: dict[str, sqlite3.Connection] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_heartbeat_tick = 0.0
        self.root = Path(settings.root)

    # -- paths -------------------------------------------------------------
    def local_path(self, label: str) -> Path:
        spec = next(spec for spec in self.specs if spec.label == label)
        return self.root / spec.local

    def local_dir(self, name: str) -> Path:
        return self.root / DIRECTORIES[name]

    def _work(self, prefix: str) -> Path:
        base = self.root / ".work"
        base.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=prefix + "-", dir=str(base)))

    # -- error bookkeeping -------------------------------------------------
    def _error(self, error: BaseException, where: str) -> None:
        record = {"class": type(error).__name__, "code": _code(error),
                  "where": where, "at": _iso(self.clock())}
        with self._error_lock:
            previous = self._error_history.get(where, {})
            self._error_history[where] = dict(
                record, first_at=previous.get("first_at", record["at"]),
                occurrences=previous.get("occurrences", 0) + 1, recovered_at=None)
            # Keep insertion order equal to failure order, including repeated failures.
            self._active_errors.pop(where, None)
            self._active_errors[where] = record
            self.last_error = record
        _log(f"{where} failed: {type(error).__name__} {_code(error)}")

    def _recovered(self, where: str) -> None:
        """Clear only a component whose complete matching operation succeeded."""
        with self._error_lock:
            if self._active_errors.pop(where, None) is not None:
                self._error_history[where]["recovered_at"] = _iso(self.clock())
                self.last_error = next(reversed(self._active_errors.values()), None)

    # -- write fence -------------------------------------------------------
    def blocked_labels(self) -> list[str]:
        return sorted(label for label, state in self.stores.items() if state.health == "BLOCKED")

    def writable(self) -> bool:
        return self.role in WRITABLE_ROLES and not [
            label for label in self.blocked_labels() if label != "gdw"]

    def fence_reason(self) -> str:
        if self.role not in WRITABLE_ROLES:
            return f"STATE_STORE_{self.role}"
        return "STATE_STORE_BLOCKED_" + "_".join(
            label.upper() for label in self.blocked_labels() if label != "gdw")

    def begin_write(self) -> bool:
        with self._inflight_cond:
            if not self.writable():
                return False
            self._inflight += 1
            return True

    def end_write(self) -> None:
        with self._inflight_cond:
            self._inflight -= 1
            self._inflight_cond.notify_all()

    def add_quiesce_hook(self, hook: Callable[[], Any]) -> None:
        self._quiesce_hooks.append(hook)

    def _quiesce(self) -> bool:
        stopped = True
        for hook in list(self._quiesce_hooks):
            try:
                hook()
            except Exception as error:
                stopped = False
                self._error(error, "quiesce")
        deadline = self.monotonic() + self.settings.drain_s
        with self._inflight_cond:
            while self._inflight > 0 and self.monotonic() < deadline:
                self._inflight_cond.wait(timeout=0.25)
            return stopped and self._inflight == 0

    # -- boot --------------------------------------------------------------
    def boot(self) -> None:
        """Restore and claim before serving. Retries transient provider faults."""
        try:
            self.root = self.local_root_check(self.root)
        except Exception as error:
            self.role = ROLE_BLOCKED
            self._error(error, "local-root")
            raise
        deadline = self.monotonic() + self.settings.boot_deadline_s
        delay = 1.0
        while True:
            if self.monotonic() >= deadline:
                self.role = ROLE_BLOCKED
                error = StorageBlocked("STATE_BOOT_DEADLINE_EXHAUSTED")
                self._error(error, "boot")
                raise error
            try:
                self._reset_local()
                self._probe_fence()
                if self.mode == MODE_FENCED:
                    self._boot_fenced(deadline)
                else:
                    self._boot_unfenced()
                self._recovered("boot-retry")
                break
            except HeadChanged:
                continue
            except StorageBlocked as error:
                if not self._transient(error) or self.monotonic() + delay >= deadline:
                    self.role = ROLE_BLOCKED
                    self._error(error, "boot")
                    raise
                self._error(error, "boot-retry")
                self.sleep(delay)
                delay = min(delay * 2, 30.0)
            except Exception as error:
                self.role = ROLE_BLOCKED
                self._error(error, "boot")
                raise
        _log(f"boot complete: mode={self.mode} role={self.role} epoch={self.epoch} "
             f"claim={self.claim_kind} blocked={self.blocked_labels()}")

    def _probe_fence(self) -> None:
        """A definitely absent or forbidden fence dataset means UNFENCED, loudly."""
        probe = getattr(self.backend, "probe", None)
        if self.mode != MODE_FENCED or probe is None:
            return
        try:
            probe()
        except DatasetUnavailable as error:
            self.backend, self.mode, self.mode_reason = None, MODE_UNFENCED, error.code
            _log(f"WARNING mode={MODE_UNFENCED} reason={error.code}: create the private "
                 f"dataset {self.settings.dataset} to enable the single-writer lease")

    @staticmethod
    def _transient(error: StorageBlocked) -> bool:
        return error.code in {
            "STATE_DATASET_UNREACHABLE", "STATE_HEAD_UNREADABLE", "STATE_HEAD_OUTCOME_UNCERTAIN",
            "STATE_HEAD_CONTENTION", "OBJECT_UNAVAILABLE", "STORAGE_OUTCOME_UNCERTAIN"}

    def _reset_local(self) -> None:
        """A container's local files are never an authority; HEAD is."""
        self._close_watchers()
        for spec in self.specs:
            target = self.local_path(spec.label)
            if target.exists() or any(Path(str(target) + suffix).exists()
                                      for suffix in ("-journal", "-wal", "-shm")):
                aside = self.root / ".stale" / f"{self.boot_id}-{uuid.uuid4().hex[:8]}" / spec.label
                aside.mkdir(parents=True, exist_ok=True)
                for path in [target] + [Path(str(target) + suffix) for suffix in ("-journal", "-wal", "-shm")]:
                    if path.exists():
                        os.replace(path, aside / path.name)
            self.stores[spec.label] = StoreState(spec)

    def _observe(self) -> Observation:
        try:
            return self.backend.observe()
        except StorageBlocked:
            raise
        except Exception:
            raise StorageBlocked("STATE_DATASET_UNREACHABLE") from None

    def _boot_fenced(self, deadline: float) -> None:
        while True:
            if self.monotonic() >= deadline:
                raise StorageBlocked("STATE_BOOT_DEADLINE_EXHAUSTED")
            observed = self._observe()
            if observed.body is None:
                self._first_boot(observed)
                return
            head = parse_head(observed.body)
            if head["state"] == STATE_RELEASED:
                self._restore_and_claim(observed, CLAIM_CLEAN)
                return
            if self._lease_stale(head):
                self._restore_and_claim(observed, CLAIM_UNCLEAN)
                return
            if head["state"] == STATE_ACTIVE:
                proposal = self._next(head, observed.body, transition="HANDOVER_REQUEST",
                                      state=STATE_HANDOVER,
                                      handover={"requested_by": self.boot_id,
                                                "requested_at": _iso(self.clock())})
                try:
                    observed = cas_advance(self.backend, observed, proposal)
                except HeadChanged:
                    continue
                _log(f"handover requested from epoch {head['epoch']}")
            waited_from = self.monotonic()
            outcome = None
            while self.monotonic() - waited_from < self.settings.stale_s:
                self.sleep(self.settings.poll_s)
                current = self._observe()
                if current.body is None:
                    outcome = "RESTART"
                    break
                now = parse_head(current.body)
                if now["epoch"] != head["epoch"]:
                    outcome = "RESTART"
                    break
                if now["state"] == STATE_RELEASED:
                    self._restore_and_claim(current, CLAIM_CLEAN)
                    return
            if outcome == "RESTART":
                continue
            current = self._observe()
            if current.body is not None and parse_head(current.body)["epoch"] == head["epoch"]:
                self._restore_and_claim(current, CLAIM_UNCLEAN)
                return

    def _lease_stale(self, head: dict[str, Any]) -> bool:
        try:
            raw = self.objects.get_bytes(head["lease"]["heartbeat_path"])
        except Exception:
            raw = None
        if raw is None:
            # No heartbeat object at all: fall back to the HEAD renewal time.
            return self._age(head["lease"]["renewed_at"]) > self.settings.stale_s
        try:
            beat = json.loads(raw)
            if beat.get("epoch") != head["epoch"] or beat.get("writer_id") != head["writer_id"]:
                return self._age(head["lease"]["renewed_at"]) > self.settings.stale_s
            return self.clock() - float(beat["at_unix"]) > self.settings.stale_s
        except (ValueError, TypeError, KeyError):
            return True

    def _age(self, iso_value: str) -> float:
        try:
            moment = datetime.strptime(iso_value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return float("inf")
        return self.clock() - moment.timestamp()

    def _restore_and_claim(self, observed: Observation, kind: str) -> None:
        head = parse_head(observed.body)
        self._restore_from_head(head)
        proposal = self._next(head, observed.body, transition="CLAIM", state=STATE_ACTIVE,
                              epoch=head["epoch"] + 1, writer_id=self.writer_id,
                              handover=None,
                              claim={"kind": kind, "at": _iso(self.clock()),
                                     "origins": {label: state.origin for label, state in self.stores.items()},
                                     "previous_epoch": head["epoch"]})
        self.head = cas_advance(self.backend, observed, proposal)
        self.epoch = head["epoch"] + 1
        self.claim_kind = kind
        self.role = ROLE_WRITER
        if kind == CLAIM_UNCLEAN:
            _log(f"UNCLEAN_HANDOVER: epoch {head['epoch']} writer did not release; "
                 "restored from its latest snapshots")

    def _initial_entries(self, epoch: int) -> dict[str, dict[str, Any]]:
        """Adopted objects as they are, plus fresh captures of everything else."""
        entries = {label: state.entry for label, state in self.stores.items()
                   if state.entry is not None and state.health == "OK"}
        entries.update(self._snapshot_labels([s.label for s in self.specs], force=True, epoch=epoch))
        return entries

    def _first_boot(self, observed: Observation) -> None:
        self._seed_without_head()
        entries = self._initial_entries(1)
        now = _iso(self.clock())
        proposal = {
            "schema": HEAD_SCHEMA, "operation_id": uuid.uuid4().hex, "sequence": 1,
            "previous_manifest_sha256": None, "epoch": 1, "writer_id": self.writer_id,
            "boot_id": self.boot_id, "state": STATE_ACTIVE, "transition": "BOOTSTRAP",
            "handover": None,
            "claim": {"kind": CLAIM_FIRST_BOOT, "at": now,
                      "origins": {label: state.origin for label, state in self.stores.items()},
                      "previous_epoch": 0},
            "lease": {"renewed_at": now, "heartbeat_path": HEARTBEAT_PATH,
                      "stale_after_seconds": int(self.settings.stale_s)},
            "source_revision": self.source_revision, "bucket": self.settings.bucket,
            "snapshots": entries, "history": {},
        }
        self.head = cas_advance(self.backend, observed, proposal)
        self.epoch = 1
        self.claim_kind = CLAIM_FIRST_BOOT
        self.role = ROLE_WRITER
        self._commit_entries(entries)
        self._write_legacy_frozen(entries)

    def _boot_unfenced(self) -> None:
        _log("SNAPSHOT_ONLY_UNFENCED: the fence dataset is unavailable "
             f"({self.mode_reason}); no single-writer lease is enforced")
        self._seed_without_head()
        self.epoch = 0
        self.role = ROLE_UNFENCED_WRITER
        entries = self._initial_entries(0)
        self._commit_entries(entries)
        self._write_legacy_frozen(entries)
        self._write_unfenced_head()

    # -- restore -----------------------------------------------------------
    def _seed_without_head(self) -> None:
        """No HEAD: adopt v2 objects if present, else a one-time legacy copy."""
        frozen = self.objects.get_bytes(LEGACY_FROZEN_PATH) is not None
        for spec in self.specs:
            names = self._listed(spec)
            if names:
                self._restore_label(spec, [(f"{PREFIX}/{spec.label}/{name}", None) for name in names],
                                    origin=ORIGIN_ADOPTED)
                continue
            if frozen:
                continue
            source = legacy_path(spec, self.environ, self.settings.legacy_root)
            exists = source.is_file() if spec.kind == "sqlite" else (source / "data.mdb").is_file()
            if exists:
                self._bootstrap_legacy(spec, source)

    def _listed(self, spec: StoreSpec) -> list[str]:
        names = []
        for path in self.objects.list(f"{PREFIX}/{spec.label}/"):
            name = path.rsplit("/", 1)[-1]
            match = _OBJECT_NAME.fullmatch(name)
            if match and path == f"{PREFIX}/{spec.label}/{name}" and match.group("ext") == spec.extension:
                names.append((match.group("stamp"), int(match.group("epoch")), int(match.group("seq")), name))
        return [item[3] for item in sorted(names, reverse=True)[: HISTORY_DEPTH + 1]]

    def _restore_from_head(self, head: dict[str, Any]) -> None:
        for spec in self.specs:
            entries = []
            if spec.label in head["snapshots"]:
                entries.append(head["snapshots"][spec.label])
            entries.extend(head["history"].get(spec.label, []))
            if entries:
                self._restore_label(spec, [(entry["path"], entry) for entry in entries],
                                    origin=ORIGIN_RESTORED)

    def _restore_label(self, spec: StoreSpec, candidates: list[tuple[str, Optional[dict[str, Any]]]],
                       *, origin: str) -> None:
        state = self.stores[spec.label]
        last: Optional[BaseException] = None
        for index, (remote, expected) in enumerate(candidates):
            work = self._work("restore-" + spec.label)
            try:
                installed = self._restore_candidate(spec, remote, expected, work)
                state.origin, state.health, state.blocked_code = origin, "OK", None
                state.entry = installed
                state.captured_at = self.clock()
                state.full_integrity_at = self.clock()
                self._recovered(f"restore:{spec.label}")
                if index:
                    # Republish the verified bytes so HEAD stops naming the bad object.
                    state.entry = None
                    _log(f"{spec.label}: restored from history item {index} after newer snapshots failed")
                return
            except StorageBlocked as error:
                if self._transient(error):
                    raise
                last = error
                _log(f"{spec.label}: snapshot {remote.rsplit('/', 1)[-1]} rejected: {_code(error)}")
            except (OSError, sqlite3.Error, gdw_sqlite_repair.OrphanRepairError) as error:
                last = error
                _log(f"{spec.label}: snapshot {remote.rsplit('/', 1)[-1]} rejected: {type(error).__name__}")
            finally:
                shutil.rmtree(work, ignore_errors=True)
        state.health, state.blocked_code = "BLOCKED", "NO_VERIFIED_SNAPSHOT"
        state.origin = origin
        if last is not None:
            self._error(last, f"restore:{spec.label}")

    def _download(self, remote: str, target: Path) -> None:
        # A missing object is a bad candidate (walk back); an unreachable
        # provider is transient (retry the whole boot).
        try:
            present = self.objects.size(remote)
        except StorageBlocked:
            raise
        except Exception:
            raise StorageBlocked("OBJECT_UNAVAILABLE") from None
        if present is None:
            raise StorageBlocked("SNAPSHOT_OBJECT_MISSING")
        try:
            self.objects.get_file(remote, target)
        except StorageBlocked:
            raise
        except Exception:
            raise StorageBlocked("OBJECT_UNAVAILABLE") from None

    def _restore_candidate(self, spec: StoreSpec, remote: str, expected: Optional[dict[str, Any]],
                           work: Path) -> dict[str, Any]:
        name = remote.rsplit("/", 1)[-1]
        sha16 = _OBJECT_NAME.fullmatch(name).group("sha16")
        downloaded = work / ("object." + spec.extension)
        self._download(remote, downloaded)
        digest = gdw_sqlite_repair.file_sha256(downloaded)
        if digest[:16] != sha16 or (expected is not None and (
                digest != expected["sha256"] or downloaded.stat().st_size != expected["size"])):
            raise StorageBlocked("SNAPSHOT_DIGEST_MISMATCH")
        if spec.kind == "sqlite":
            report = self._verify_or_repair(spec, downloaded, work, source=remote)
            if (expected is not None and expected["logical_sha256"] is not None
                    and report["logical_sha256"] != expected["logical_sha256"]):
                raise StorageBlocked("SNAPSHOT_LOGICAL_MISMATCH")
            target = self.local_path(spec.label)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(downloaded, target)
            logical = report["logical_sha256"]
        else:
            directory = work / "env"
            directory.mkdir()
            os.replace(downloaded, directory / "data.mdb")
            report = lmdb_logical_digest(directory)
            if (expected is not None and expected["logical_sha256"] is not None
                    and report["logical_sha256"] != expected["logical_sha256"]):
                raise StorageBlocked("SNAPSHOT_LOGICAL_MISMATCH")
            target = self.local_path(spec.label)
            target.mkdir(parents=True, exist_ok=True)
            os.replace(directory / "data.mdb", target / "data.mdb")
            logical = report["logical_sha256"]
        return expected or {
            "path": remote, "sha256": digest, "size": self.local_size(spec), "kind": spec.kind,
            "integrity": "integrity_check" if spec.kind == "sqlite" else "lmdb_read",
            "logical_sha256": logical, "taken_at": _iso(self.clock()),
            "epoch": int(_OBJECT_NAME.fullmatch(name).group("epoch")),
            "seq": int(_OBJECT_NAME.fullmatch(name).group("seq"))}

    def local_size(self, spec: StoreSpec) -> int:
        target = self.local_path(spec.label)
        return (target if spec.kind == "sqlite" else target / "data.mdb").stat().st_size

    def _verify_or_repair(self, spec: StoreSpec, database: Path, work: Path,
                          *, source: str) -> dict[str, Any]:
        report = verify_sqlite(database, full=True)
        if report["ok"]:
            return report
        if report["integrity_ok"]:
            raise StorageBlocked("FOREIGN_KEY_CHECK_FAILED")
        if not report["orphan_pages"]:
            raise StorageBlocked("SQLITE_INTEGRITY_FAILED")
        # Orphan-page-only damage on a private copy no other opener can reach:
        # writer quiescence holds by construction. The original stays where it
        # was (an immutable object, or the frozen legacy file).
        scratch = self._work("repair-" + spec.label)
        try:
            receipt = gdw_sqlite_repair.repair_orphan_pages(database, label=spec.label,
                                                            work_dir=scratch)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        receipt["original_source"] = source
        receipt["state_store_boot_id"] = self.boot_id
        stamp = _stamp(self.clock())
        try:
            self.objects.put_bytes(
                f"{PREFIX}/{spec.label}/quarantine/{stamp}-{receipt['original']['sha256'][:16]}.json",
                json.dumps(receipt, sort_keys=True, indent=2).encode())
        except Exception as error:
            self._error(error, f"repair-receipt:{spec.label}")
        for leftover in database.parent.glob(database.name + ".orphan-pages-*"):
            leftover.unlink(missing_ok=True)
        report = verify_sqlite(database, full=True)
        if not report["ok"]:
            raise StorageBlocked("SQLITE_REPAIR_UNVERIFIED")
        _log(f"{spec.label}: orphan-page-only damage repaired (logical fingerprint preserved)")
        return report

    def _bootstrap_legacy(self, spec: StoreSpec, source: Path) -> None:
        """One-time copy of a pre-v2 store. The legacy file is only read."""
        state = self.stores[spec.label]
        work = self._work("legacy-" + spec.label)
        try:
            if spec.kind == "sqlite":
                copy = work / "legacy.sqlite3"
                _copy_stable(source, copy)
                for suffix in ("-journal", "-wal"):
                    sidecar = Path(str(source) + suffix)
                    if sidecar.is_file() and sidecar.stat().st_size > 0:
                        _copy_stable(sidecar, Path(str(copy) + suffix))
                # Hot-journal rollback happens on the private copy, never on /data.
                gdw_sqlite_repair.recover_hot_journal(copy)
                self._verify_or_repair(spec, copy, work, source=f"legacy:{spec.label}")
                target = self.local_path(spec.label)
                target.parent.mkdir(parents=True, exist_ok=True)
                sqlite_backup(copy, target)
            else:
                directory = work / "env"
                directory.mkdir()
                _copy_stable(source / "data.mdb", directory / "data.mdb")
                lmdb_logical_digest(directory)
                target = self.local_path(spec.label)
                target.mkdir(parents=True, exist_ok=True)
                os.replace(directory / "data.mdb", target / "data.mdb")
            state.origin, state.health = ORIGIN_LEGACY, "OK"
            self._recovered(f"legacy:{spec.label}")
            _log(f"{spec.label}: legacy bootstrap copied read-only from the legacy mount")
        except (StorageBlocked, OSError, sqlite3.Error, gdw_sqlite_repair.OrphanRepairError,
                ImportError) as error:
            state.origin, state.health = ORIGIN_LEGACY, "BLOCKED"
            state.blocked_code = _code(error)
            self._error(error, f"legacy:{spec.label}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _write_legacy_frozen(self, entries: Mapping[str, dict[str, Any]]) -> None:
        legacy = [label for label, state in self.stores.items() if state.origin == ORIGIN_LEGACY]
        if not legacy or self.objects.get_bytes(LEGACY_FROZEN_PATH) is not None:
            return
        body = {
            "schema": FROZEN_SCHEMA, "frozen_at": _iso(self.clock()), "boot_id": self.boot_id,
            "mode": self.mode, "epoch": self.epoch,
            "note": ("The legacy /data stores were copied read-only into the a11oy state "
                     "store. They are never opened for writing again and are history only."),
            "stores": {label: {"origin": self.stores[label].origin,
                               "health": self.stores[label].health,
                               "snapshot": (entries.get(label) or {}).get("path")}
                       for label in legacy},
        }
        try:
            self.objects.put_bytes(LEGACY_FROZEN_PATH, json.dumps(body, sort_keys=True, indent=2).encode())
            self._recovered("legacy-frozen")
        except Exception as error:
            self._error(error, "legacy-frozen")

    # -- snapshots ---------------------------------------------------------
    def _signature(self, spec: StoreSpec) -> Any:
        target = self.local_path(spec.label)
        if spec.kind == "sqlite":
            if not target.is_file():
                return None
            watcher = self._watchers.get(spec.label)
            if watcher is None:
                watcher = _read_only(target)
                self._watchers[spec.label] = watcher
            version = watcher.execute("PRAGMA data_version").fetchone()[0]
            return (version, _stat_signature(target), _stat_signature(Path(str(target) + "-wal")))
        data = target / "data.mdb"
        if not data.is_file():
            return None
        env = _registered_lmdb_env(target)
        txn = None
        if env is not None:
            with contextlib.suppress(Exception):
                txn = env.info().get("last_txnid")
        return (txn, _stat_signature(data))

    def _close_watchers(self) -> None:
        for watcher in self._watchers.values():
            with contextlib.suppress(Exception):
                watcher.close()
        self._watchers.clear()

    def _capture(self, spec: StoreSpec, work: Path, epoch: int) -> Optional[dict[str, Any]]:
        """Backup, verify, upload, read back. Returns None when bytes are unchanged."""
        state = self.stores[spec.label]
        source = self.local_path(spec.label)
        now = self.clock()
        if spec.kind == "sqlite":
            snapshot = work / "snapshot.sqlite3"
            sqlite_backup(source, snapshot)
            full = now - state.full_integrity_at >= self.settings.full_integrity_s
            report = verify_sqlite(snapshot, full=full)
            if not report["ok"]:
                raise StorageBlocked("SNAPSHOT_INTEGRITY_FAILED" if not report["integrity_ok"]
                                     else "FOREIGN_KEY_CHECK_FAILED")
            if full:
                state.full_integrity_at = now
            integrity, logical = report["integrity"], report["logical_sha256"]
        else:
            directory = work / "env"
            directory.mkdir()
            env = _registered_lmdb_env(source)
            if env is not None:
                env.copy(str(directory), compact=True)
            else:
                # Not opened in this process yet, so nothing can be writing it.
                shutil.copyfile(source / "data.mdb", directory / "data.mdb")
            snapshot = directory / "data.mdb"
            integrity, logical = "lmdb_read", lmdb_logical_digest(directory)["logical_sha256"]
        digest = gdw_sqlite_repair.file_sha256(snapshot)
        known = self._unpublished.get(spec.label) or state.entry
        if known is not None and known["sha256"] == digest:
            return None
        size = snapshot.stat().st_size
        self._seq += 1
        remote = f"{PREFIX}/{spec.label}/{_stamp(now)}-{epoch}-{self._seq}-{digest[:16]}.{spec.extension}"
        try:
            self.objects.put_file(snapshot, remote)
            readback = work / "readback"
            self.objects.get_file(remote, readback)
        except StorageBlocked:
            raise
        except Exception:
            raise StorageBlocked("OBJECT_UNAVAILABLE") from None
        if (self.objects.size(remote) != size or readback.stat().st_size != size
                or gdw_sqlite_repair.file_sha256(readback) != digest):
            raise StorageBlocked("SNAPSHOT_READBACK_MISMATCH")
        return {"path": remote, "sha256": digest, "size": size, "kind": spec.kind,
                "integrity": integrity, "logical_sha256": logical, "taken_at": _iso(now),
                "epoch": epoch, "seq": self._seq}

    def _snapshot_labels(self, labels: Iterable[str], *, force: bool,
                         epoch: Optional[int] = None,
                         require_complete: bool = False) -> dict[str, dict[str, Any]]:
        """Capture stores; a clean release additionally requires every capture."""
        entries: dict[str, dict[str, Any]] = {}
        incomplete = False
        epoch = self.epoch if epoch is None else epoch
        for label in labels:
            state = self.stores[label]
            spec = state.spec
            if state.health == "BLOCKED":
                continue
            now = self.clock()
            if not force and now < state.next_attempt_at:
                continue
            try:
                signature = self._signature(spec)
            except (OSError, sqlite3.Error) as error:
                self._error(error, f"signature:{label}")
                incomplete = True
                continue
            if signature is None:
                if state.entry is not None or state.seen is not None or label in self._unpublished:
                    incomplete = True
                    self._error(StorageBlocked("STATE_STORE_SOURCE_MISSING"), f"signature:{label}")
                continue
            self._recovered(f"signature:{label}")
            work = None
            try:
                work = self._work("snap-" + label)
                entry = self._capture(spec, work, epoch or 0)
                if entry is not None:
                    entries[label] = entry
                state.signature = signature
                state.failures, state.next_attempt_at, state.last_error = 0, 0.0, None
                self._recovered(f"snapshot:{label}")
                if entry is None and label not in self._unpublished:
                    # Bytes equal the published snapshot: nothing is at risk.
                    state.captured_at = now
                    state.dirty_since = None
            except (StorageBlocked, OSError, sqlite3.Error, ImportError) as error:
                incomplete = True
                state.failures += 1
                state.last_error = _code(error)
                state.next_attempt_at = now + min(self.settings.periodic_s, 5.0 * 2 ** min(state.failures, 6))
                self._error(error, f"snapshot:{label}")
            finally:
                if work is not None:
                    shutil.rmtree(work, ignore_errors=True)
        if require_complete and incomplete:
            self._unpublished.update(entries)
            raise StorageBlocked("STATE_FINAL_SNAPSHOT_INCOMPLETE")
        return entries

    def _commit_entries(self, entries: Mapping[str, dict[str, Any]]) -> None:
        now = self.clock()
        for label, entry in entries.items():
            state = self.stores[label]
            state.entry = entry
            state.captured_at = now
            state.dirty_since = None

    def snapshot_once(self, *, force: bool = False) -> dict[str, dict[str, Any]]:
        """One debounce/periodic pass. Safe to call from any thread."""
        with self._lock:
            if self.role not in WRITABLE_ROLES:
                return {}
            with self._error_lock:
                retry_loop = "snapshot-loop" in self._active_errors
                retry_unfenced = "unfenced-head" in self._active_errors
            # An unexpected loop failure needs a complete capture pass, not a
            # debounce/backoff no-op, before its recovery can be established.
            now = self.clock()
            loop_due = retry_loop and now >= max(
                [self._publish_next_at] + [state.next_attempt_at for state in self.stores.values()])
            force = force or loop_due
            complete = True
            due = []
            for label, state in self.stores.items():
                if state.health == "BLOCKED":
                    complete = False
                    continue
                try:
                    signature = self._signature(state.spec)
                except (OSError, sqlite3.Error) as error:
                    self._error(error, f"signature:{label}")
                    complete = False
                    continue
                if signature is None:
                    if state.entry is not None or state.seen is not None or label in self._unpublished:
                        complete = False
                        self._error(StorageBlocked("STATE_STORE_SOURCE_MISSING"), f"signature:{label}")
                    continue
                self._recovered(f"signature:{label}")
                if signature != state.seen:
                    state.seen, state.changed_at = signature, now
                if signature != state.signature:
                    state.dirty_since = state.dirty_since or now
                if force:
                    due.append(label)
                    continue
                if state.dirty_since is None:
                    if state.captured_at is None or now - state.captured_at >= self.settings.periodic_s:
                        state.captured_at = now  # unchanged since the last capture
                    continue
                quiet = now - (state.changed_at or now) >= self.settings.debounce_s
                overdue = now - state.dirty_since >= self.settings.periodic_s
                if quiet or overdue:
                    due.append(label)
            entries = self._snapshot_labels(due, force=force) if due else {}
            if entries or (self._unpublished and (force or now >= self._publish_next_at)):
                merged = dict(self._unpublished)
                merged.update(entries)
                self._publish(merged)
            elif self.mode == MODE_UNFENCED and retry_unfenced and (force or now >= self._publish_next_at):
                self._write_unfenced_head()
            if retry_loop and force and complete and due and not self._unpublished and self.role in WRITABLE_ROLES:
                with self._error_lock:
                    failed = any(where.startswith(("snapshot:", "signature:"))
                                 or where in ("publish", "unfenced-head")
                                 for where in self._active_errors)
                    if not failed:
                        self._recovered("snapshot-loop")
            return entries

    def _publish(self, entries: Mapping[str, dict[str, Any]]) -> None:
        if self.mode == MODE_UNFENCED:
            self._commit_entries(entries)
            self._write_unfenced_head()
            return
        assert self.head is not None and self.head.body is not None
        current = parse_head(self.head.body)
        snapshots, history = self._merged(current, entries)
        proposal = self._next(current, self.head.body, transition="SNAPSHOT", state=STATE_ACTIVE,
                              snapshots=snapshots, history=history)
        try:
            self.head = cas_advance(self.backend, self.head, proposal)
        except HeadChanged as changed:
            self._unpublished = {}
            self._on_head_changed(changed.observed, pending=entries)
            return
        except StorageBlocked as error:
            # Uploaded objects stay pending and are published on the next pass;
            # the live databases are not touched.
            self._unpublished = dict(entries)
            self._publish_failures += 1
            self._publish_next_at = self.clock() + min(
                self.settings.periodic_s, 5.0 * 2 ** min(self._publish_failures, 6))
            self._error(error, "publish")
            return
        self._unpublished, self._publish_failures, self._publish_next_at = {}, 0, 0.0
        self._commit_entries(entries)
        self._recovered("publish")

    @staticmethod
    def _merged(current: dict[str, Any], entries: Mapping[str, dict[str, Any]]):
        snapshots = dict(current["snapshots"])
        history = {label: list(items) for label, items in current["history"].items()}
        for label, entry in entries.items():
            previous = snapshots.get(label)
            if previous is not None:
                history[label] = ([previous] + history.get(label, []))[:HISTORY_DEPTH]
            snapshots[label] = entry
        return snapshots, history

    def _next(self, current: dict[str, Any], current_body: bytes, **changes: Any) -> dict[str, Any]:
        value = json.loads(json.dumps(current))
        value.update(operation_id=uuid.uuid4().hex, sequence=current["sequence"] + 1,
                     previous_manifest_sha256=_sha256_bytes(current_body),
                     boot_id=self.boot_id if changes.get("transition") != "HANDOVER_REQUEST" else current["boot_id"],
                     source_revision=self.source_revision or current["source_revision"])
        value["lease"] = dict(current["lease"], renewed_at=_iso(self.clock()))
        if changes.get("transition") == "HANDOVER_REQUEST":
            value["lease"] = dict(current["lease"])
        value.update(changes)
        return value

    # -- lease -------------------------------------------------------------
    def heartbeat_once(self) -> None:
        """Publish liveness, then react to a handover request or a successor."""
        with self._lock:
            if self.role not in WRITABLE_ROLES:
                return
            now = self.clock()
            beat = {"schema": HEARTBEAT_SCHEMA, "epoch": self.epoch, "writer_id": self.writer_id,
                    "boot_id": self.boot_id, "at": _iso(now), "at_unix": now}
            try:
                self.objects.put_bytes(HEARTBEAT_PATH, json.dumps(beat, sort_keys=True).encode())
                self.heartbeat_at = now
                self._recovered("heartbeat")
            except Exception as error:
                self._error(error, "heartbeat")
            if self.mode != MODE_FENCED:
                with self._error_lock:
                    if "heartbeat" not in self._active_errors:
                        self._recovered("heartbeat-loop")
                return
            try:
                observed = self._observe()
            except StorageBlocked as error:
                self._error(error, "heartbeat-observe")
                return
            if self._on_head_changed(observed):
                self._recovered("heartbeat-observe")
                with self._error_lock:
                    if "heartbeat" not in self._active_errors:
                        self._recovered("heartbeat-loop")

    def _on_head_changed(self, observed: Observation, *, pending: Optional[Mapping[str, Any]] = None) -> bool:
        if self.head is not None and self.head.body is not None and observed.body == self.head.body:
            return self.role == ROLE_WRITER
        if observed.body is None:
            self._fence("STATE_HEAD_VANISHED")
            return False
        try:
            value = parse_head(observed.body)
        except StorageBlocked as error:
            self._fence(error.code)
            return False
        mine = parse_head(self.head.body) if self.head and self.head.body else None
        if mine is not None and value["epoch"] == mine["epoch"] and value["sequence"] < mine["sequence"]:
            return False  # a read that predates our own last advance
        if (mine is not None and value["epoch"] == self.epoch and value["writer_id"] == self.writer_id
                and value["state"] == STATE_HANDOVER):
            self._release(observed, pending=pending)
            return False
        self._fence("WRITER_FENCED")
        return False

    def _fence(self, code: str) -> None:
        if self.role != ROLE_FENCED:
            self.role = ROLE_FENCED
            self._error(StorageBlocked(code), "lease")
            _log(f"writer FENCED ({code}); this process is read-only from now on")

    def _release(self, observed: Observation, *, pending: Optional[Mapping[str, Any]] = None) -> None:
        """Hand over: refuse writes, drain, take final snapshots, mark RELEASED."""
        with self._lock:
            with self._inflight_cond:
                self.role = ROLE_HANDOVER
            _log("handover requested; refusing writes and taking final snapshots")
            if not self._quiesce():
                self._fence("STATE_WRITERS_NOT_QUIESCED")
                return
            entries = dict(self._unpublished)
            entries.update(pending or {})
            self._unpublished = {}
            # Already-uploaded objects count as captured, so identical bytes
            # are not uploaded twice under a new name.
            self._commit_entries(entries)
            self._unpublished = dict(entries)
            try:
                fresh = self._snapshot_labels([label for label in self.stores], force=True,
                                              require_complete=True)
            except StorageBlocked as error:
                # RELEASED promises a complete final snapshot. A failed capture
                # may only be recovered through the existing unclean takeover.
                self._error(error, "release")
                self._fence(_code(error))
                return
            entries.update(fresh)
            self._unpublished = dict(entries)
            current = parse_head(observed.body)
            snapshots, history = self._merged(current, entries)
            proposal = self._next(current, observed.body, transition="RELEASE", state=STATE_RELEASED,
                                  handover=None, snapshots=snapshots, history=history)
            try:
                self.head = cas_advance(self.backend, observed, proposal)
            except StorageBlocked as error:
                self._error(error, "release")
                self._fence(_code(error))
                return
            self._commit_entries(entries)
            self._unpublished = {}
            self._recovered("publish")
            self.role = ROLE_RELEASED
            _log(f"RELEASED epoch {self.epoch}; read-only until this container stops")

    def _write_unfenced_head(self) -> None:
        body = {"schema": HEAD_SCHEMA + "+unfenced", "mode": MODE_UNFENCED, "boot_id": self.boot_id,
                "at": _iso(self.clock()), "authoritative": False,
                "snapshots": {label: state.entry for label, state in self.stores.items()
                              if state.entry is not None}}
        try:
            self.objects.put_bytes(UNFENCED_HEAD_PATH, json.dumps(body, sort_keys=True, indent=2).encode())
            self._publish_failures, self._publish_next_at = 0, 0.0
            self._recovered("unfenced-head")
        except Exception as error:
            self._publish_failures += 1
            self._publish_next_at = self.clock() + min(
                self.settings.periodic_s, 5.0 * 2 ** min(self._publish_failures, 6))
            self._error(error, "unfenced-head")

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="a11oy-state-store", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        tick = min(self.settings.poll_s, self.settings.heartbeat_s)
        while not self._stop.wait(tick):
            if self.role not in WRITABLE_ROLES:
                continue
            now = self.monotonic()
            if now - self._last_heartbeat_tick >= self.settings.heartbeat_s:
                self._last_heartbeat_tick = now
                try:
                    self.heartbeat_once()
                except Exception as error:
                    self._error(error, "heartbeat-loop")
            try:
                self.snapshot_once()
            except Exception as error:
                self._error(error, "snapshot-loop")

    def close(self) -> None:
        """Container stop: final snapshots, then RELEASE so the successor is clean."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        try:
            if self.role == ROLE_WRITER and self.head is not None:
                with self._lock:
                    observed = self._observe()
                    if observed.body == self.head.body or (
                            observed.body is not None
                            and parse_head(observed.body)["writer_id"] == self.writer_id
                            and parse_head(observed.body)["state"] == STATE_HANDOVER):
                        self._release(observed)
                    else:
                        self._on_head_changed(observed)
            elif self.role == ROLE_UNFENCED_WRITER:
                self._quiesce()
                self.snapshot_once(force=True)
        except Exception as error:
            self._error(error, "close")
        finally:
            self._close_watchers()

    # -- status ------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        now = self.clock()
        head = None
        if self.head is not None and self.head.body is not None:
            with contextlib.suppress(StorageBlocked):
                head = parse_head(self.head.body)
        stores = {}
        worst = 0.0
        for label, state in self.stores.items():
            age = None if state.captured_at is None else round(now - state.captured_at, 1)
            pending = None if state.dirty_since is None else round(now - state.dirty_since, 1)
            if state.health != "BLOCKED" and pending is not None:
                worst = max(worst, pending)
            if state.health != "BLOCKED" and age is not None and self.role in WRITABLE_ROLES:
                worst = max(worst, age)
            stores[label] = {
                "kind": state.spec.kind,
                "origin": state.origin,
                "health": state.health,
                "blocked_code": state.blocked_code,
                "last_snapshot_age_s": age,
                "unsnapshotted_change_age_s": pending,
                "sha16": None if state.entry is None else state.entry["sha256"][:16],
                "integrity": None if state.entry is None else state.entry["integrity"],
                "snapshot_failures": state.failures,
                "last_error_code": state.last_error,
            }
        with self._error_lock:
            active_errors = {where: dict(error) for where, error in self._active_errors.items()}
            error_history = {where: dict(error) for where, error in self._error_history.items()}
            last_error = None if self.last_error is None else dict(self.last_error)
        return {
            "schema": STATUS_SCHEMA,
            "mode": self.mode,
            "mode_reason": self.mode_reason,
            "unfenced": self.mode == MODE_UNFENCED,
            "role": self.role,
            "writable": self.writable(),
            "epoch": self.epoch,
            "claim": self.claim_kind,
            "lease": {
                "state": None if head is None else head["state"],
                "sequence": None if head is None else head["sequence"],
                "heartbeat_age_s": None if self.heartbeat_at is None else round(now - self.heartbeat_at, 1),
            },
            "stores": stores,
            "alert": worst > self.settings.alert_s or self.role in (ROLE_BLOCKED, ROLE_FENCED),
            "alert_after_s": self.settings.alert_s,
            "pending_publish": sorted(self._unpublished),
            "last_error": last_error,
            "active_errors": active_errors,
            "last_error_history": error_history,
            "durable_v1": {"status": "RETIRED", "env_ignored": self.durable_v1_env_ignored},
        }


# --------------------------------------------------------------------------- #
# Process-wide activation and the hooks other modules call
# --------------------------------------------------------------------------- #
_ACTIVE: Optional[StateStore] = None
_ACTIVATION_LOCK = threading.Lock()


def active() -> Optional[StateStore]:
    return _ACTIVE


def local_path(label: str) -> Optional[Path]:
    """The live path for ``label`` when v2 owns storage, else None.

    When v2 is enabled, legacy env values (GDW_DB_PATH=/data/..., ...) are only
    the one-time bootstrap source, so the state store path always wins.
    """
    if _ACTIVE is not None:
        return _ACTIVE.local_path(label)
    if not enabled():
        return None
    spec = next(spec for spec in STORES if spec.label == label)
    return _configured_root() / spec.local


def local_dir(name: str) -> Optional[Path]:
    if _ACTIVE is not None:
        return _ACTIVE.local_dir(name)
    if not enabled():
        return None
    return _configured_root() / DIRECTORIES[name]


def _configured_root() -> Path:
    return Path(os.environ.get("A11OY_STATE_ROOT") or DEFAULT_ROOT)


def writable() -> bool:
    if _ACTIVE is not None:
        return _ACTIVE.writable()
    return not enabled()


def status() -> dict[str, Any]:
    if _ACTIVE is not None:
        return _ACTIVE.status()
    return {"schema": STATUS_SCHEMA, "mode": MODE_DISABLED if not enabled() else MODE_FENCED,
            "role": ROLE_NOT_ACTIVATED if enabled() else MODE_DISABLED,
            "writable": writable(), "unfenced": False, "epoch": None, "stores": {},
            "alert": enabled(), "last_error": None,
            "active_errors": None, "last_error_history": {},
            "durable_v1": {"status": "RETIRED", "env_ignored": False}}


def export_environment(store: StateStore, environ: Any = None) -> None:
    """Point modules that only read an env directory at the local root.

    szl_unay_routes.py is shared byte-for-byte with killinchu, so it is wired
    through its existing first-priority setting instead of an edit. The
    store's legacy paths were captured from the environment before this runs.
    """
    values = os.environ if environ is None else environ
    values["UNAY_DATA_DIR"] = str(store.local_dir("unay"))


def _production_store(environ: Mapping[str, str]) -> StateStore:
    settings = Settings.from_environ(environ)
    token = (environ.get("HF_TOKEN") or "").strip()
    if not token:
        raise StorageBlocked("HF_TOKEN_MISSING")
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    scratch = settings.root / ".provider"
    objects = HFBucketObjectStore(api, settings.bucket, scratch)
    # Whether the fence dataset exists is probed inside boot(), so a transient
    # Hub fault is retried instead of silently selecting the unfenced mode.
    head_backend = HFDatasetHeadBackend(api, settings.dataset, scratch)
    return StateStore(settings=settings, objects=objects, head_backend=head_backend,
                      environ=environ, source_revision=environ.get("SZL_GIT_SHA", ""))


def activate(environ: Optional[Mapping[str, str]] = None,
             factory: Callable[[Mapping[str, str]], StateStore] = _production_store) -> Optional[StateStore]:
    """Boot the state store before serve.py is imported. None when disabled.

    On failure the store stays installed in a BLOCKED role (so modules still
    resolve local paths and the write fence holds) and the error is re-raised
    for gdw_runtime to record as a degraded boot.
    """
    global _ACTIVE
    values = os.environ if environ is None else environ
    if not enabled(values):
        return None
    with _ACTIVATION_LOCK:
        ignored = bool((values.get(DURABLE_V1_ENV) or "").strip())
        if ignored and values is os.environ:
            os.environ.pop(DURABLE_V1_ENV, None)
        if ignored:
            _log(f"{DURABLE_V1_ENV} is set but durable v1 is RETIRED; ignoring it")
        try:
            store = factory(values)
        except Exception as error:
            settings = Settings(root=Path(values.get("A11OY_STATE_ROOT") or DEFAULT_ROOT),
                                bucket=DEFAULT_BUCKET, dataset=DEFAULT_DATASET,
                                legacy_root=Path(DEFAULT_LEGACY_ROOT))
            store = StateStore(settings=settings, objects=None, environ=values)
            store.role = ROLE_BLOCKED
            store._error(error, "activate")
            store.durable_v1_env_ignored = ignored
            _ACTIVE = store
            if values is os.environ:
                export_environment(store)
            raise
        store.durable_v1_env_ignored = ignored
        _ACTIVE = store
        if values is os.environ:
            export_environment(store)
        store.boot()
        store.start()
        return store


def shutdown() -> None:
    store = _ACTIVE
    if store is not None:
        store.close()


def register(app: Any) -> dict[str, Any]:
    """Mount the status route and the write fence. Safe when disabled."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/api/a11oy/v1/storage/status")
    def a11oy_storage_status() -> JSONResponse:
        return JSONResponse(status(), headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def a11oy_state_write_fence(request: Request, call_next):
        if request.method.upper() in SAFE_METHODS or not enabled():
            return await call_next(request)
        store = _ACTIVE
        if store is None or not store.begin_write():
            reason = "STATE_STORE_NOT_ACTIVATED" if store is None else store.fence_reason()
            return JSONResponse(
                status_code=503,
                content={"error": {"code": reason, "message": "storage is read-only",
                                   "retry_after_seconds": RETRY_AFTER_SECONDS}},
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)})
        try:
            return await call_next(request)
        finally:
            store.end_write()

    return {"registered": ["/api/a11oy/v1/storage/status", "write-fence"]}
