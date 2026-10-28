#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only rehearsal of the seven snapshots named by the current v2 HEAD.

The Space keeps running. This tool does not pause it, claim or release the
lease, upload an object, repair a database, or admit restore or deployment.
A passing result verifies the snapshot objects named by one pinned HEAD and
still current when the read finishes. It is not recovery admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import a11oy_state_store as ss
import gdw_sqlite_repair
from gdw_durable_storage import StorageBlocked, canonical

SCHEMA = "szl.a11oy-state-snapshot-rehearsal/v1"
PUBLIC_SCHEMA = "szl.a11oy-state-snapshot-rehearsal-public/v1"
_READS = frozenset({
    "dataset_info",
    "download_bucket_files",
    "get_bucket_paths_info",
    "get_paths_info",
    "hf_hub_download",
})
_ADMISSION = {
    "restore_admitted": False,
    "deployment_admitted": False,
    "execution_authorized": False,
    "space_paused": False,
    "lease_changed": False,
    "repairs": 0,
    "provider_writes": 0,
}


class ReadOnlyHub:
    """Allow the HEAD and snapshot reads. Every other Hub call fails closed."""

    def __init__(self, inner: Any):
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name: str) -> Any:
        if name not in _READS:
            raise StorageBlocked("REHEARSAL_PROVIDER_WRITE_REFUSED")
        return getattr(object.__getattribute__(self, "_inner"), name)


def _blocked(reason: str, **fields: Any) -> dict[str, Any]:
    report = {
        "schema": SCHEMA,
        **_ADMISSION,
        "status": "BLOCKED",
        "reason": reason,
        "head_revision": None,
        "head_sequence": None,
        "epoch": None,
        "tip_sequence_after": None,
        "latest_snapshots_unchanged": None,
        "snapshot_map_sha256": None,
        "stores": {},
    }
    report.update(fields)
    report.update(_ADMISSION)
    report["schema"] = SCHEMA
    return report


def _assert_scratch(scratch: Path) -> Path:
    resolved = Path(scratch).resolve()
    posix = resolved.as_posix()
    if posix == "/tmp/a11oy-state" or posix.startswith("/tmp/a11oy-state/"):
        raise StorageBlocked("REHEARSAL_SCRATCH_REFUSED")
    if posix == "/data" or posix.startswith("/data/"):
        raise StorageBlocked("REHEARSAL_SCRATCH_REFUSED")
    if resolved.exists() and any(resolved.iterdir()):
        raise StorageBlocked("REHEARSAL_SCRATCH_NONEMPTY")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _snapshot_map(head: Mapping[str, Any]) -> dict[str, str]:
    snapshots = head["snapshots"]
    return {label: snapshots[label]["sha256"] for label in sorted(snapshots)}


def _map_sha256(mapping: Mapping[str, str]) -> str:
    raw = json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _entry_binding(spec: ss.StoreSpec, entry: Mapping[str, Any]) -> None:
    name = entry["path"].rsplit("/", 1)[-1]
    match = ss._OBJECT_NAME.fullmatch(name)
    if (match is None or entry["kind"] != spec.kind or match.group("ext") != spec.extension
            or int(match.group("epoch")) != entry["epoch"]
            or int(match.group("seq")) != entry["seq"]
            or match.group("sha16") != entry["sha256"][:16]):
        raise StorageBlocked("STATE_HEAD_SNAPSHOT_INVALID")
    if entry["logical_sha256"] is None:
        raise StorageBlocked("SNAPSHOT_LOGICAL_UNAVAILABLE")


def _verify_file(spec: ss.StoreSpec, entry: Mapping[str, Any], blob: bytes, work: Path) -> dict[str, Any]:
    target = work / ("object." + spec.extension)
    target.write_bytes(blob)
    digest = gdw_sqlite_repair.file_sha256(target)
    if digest != entry["sha256"] or target.stat().st_size != entry["size"]:
        raise StorageBlocked("SNAPSHOT_DIGEST_MISMATCH")
    if spec.kind == "sqlite":
        report = ss.verify_sqlite(target, full=True)
        if not report["integrity_ok"]:
            raise StorageBlocked("SQLITE_INTEGRITY_FAILED")
        if report["foreign_key_violations"]:
            raise StorageBlocked("FOREIGN_KEY_CHECK_FAILED")
        logical = report["logical_sha256"]
        integrity = "integrity_check"
    else:
        directory = work / "env"
        directory.mkdir()
        os_replace = directory / "data.mdb"
        target.replace(os_replace)
        try:
            digest_report = ss.lmdb_logical_digest(directory)
        except ImportError:
            raise StorageBlocked("LMDB_RUNTIME_UNAVAILABLE") from None
        except StorageBlocked:
            raise
        except Exception:
            raise StorageBlocked("LMDB_LOGICAL_UNAVAILABLE") from None
        logical = digest_report["logical_sha256"]
        integrity = "lmdb_read"
    if logical != entry["logical_sha256"]:
        raise StorageBlocked("SNAPSHOT_LOGICAL_MISMATCH")
    return {
        "ok": True,
        "size": entry["size"],
        "sha256": entry["sha256"],
        "logical_sha256": logical,
        "integrity": integrity,
    }


def rehearse_pinned_head(*, head_body: bytes, tip_body: bytes, objects: Mapping[str, bytes],
                          scratch: Path, head_revision: Optional[str] = None) -> dict[str, Any]:
    """Verify the seven pinned snapshot objects without installing or repairing them."""
    root = _assert_scratch(scratch)
    try:
        head = ss.parse_head(head_body)
    except StorageBlocked as error:
        return _blocked(error.code)
    labels = [spec.label for spec in ss.STORES]
    if set(head["snapshots"]) != set(labels):
        return _blocked("SNAPSHOT_SET_INCOMPLETE", head_revision=head_revision,
                        head_sequence=head["sequence"], epoch=head["epoch"])
    expected = {head["snapshots"][label]["path"] for label in labels}
    if set(objects) != expected:
        return _blocked("SNAPSHOT_SET_MISMATCH", head_revision=head_revision,
                        head_sequence=head["sequence"], epoch=head["epoch"])
    stores: dict[str, Any] = {}
    try:
        for spec in ss.STORES:
            entry = head["snapshots"][spec.label]
            _entry_binding(spec, entry)
            work = root / spec.label
            work.mkdir()
            try:
                stores[spec.label] = _verify_file(spec, entry, objects[entry["path"]], work)
            finally:
                shutil.rmtree(work, ignore_errors=True)
        tip = ss.parse_head(tip_body)
    except StorageBlocked as error:
        return _blocked(error.code, head_revision=head_revision, head_sequence=head["sequence"],
                        epoch=head["epoch"], stores=stores)
    pinned_map = _snapshot_map(head)
    tip_map = _snapshot_map(tip) if set(tip["snapshots"]) == set(labels) else None
    unchanged = tip_map == pinned_map
    status = "SNAPSHOTS_VERIFIED" if unchanged else "SNAPSHOTS_ADVANCED"
    reason = None if unchanged else "SNAPSHOTS_ADVANCED"
    return {
        "schema": SCHEMA,
        **_ADMISSION,
        "status": status,
        "reason": reason,
        "head_revision": head_revision,
        "head_sequence": head["sequence"],
        "epoch": head["epoch"],
        "tip_sequence_after": tip["sequence"],
        "latest_snapshots_unchanged": unchanged,
        "snapshot_map_sha256": _map_sha256(pinned_map),
        "stores": stores,
    }


def public_view(report: Mapping[str, Any]) -> dict[str, Any]:
    """Drop private HEAD revisions, object paths, and full content hashes."""
    stores = {}
    ok_count = 0
    for label, row in report.get("stores", {}).items():
        ok = row.get("ok") is True
        ok_count += int(ok)
        stores[label] = {
            "ok": ok,
            "integrity": row.get("integrity") if ok else None,
            "sha16": row["sha256"][:16] if ok and isinstance(row.get("sha256"), str) else None,
            "size": row.get("size") if ok else None,
        }
    return {
        "schema": PUBLIC_SCHEMA,
        **_ADMISSION,
        "status": report.get("status"),
        "reason": report.get("reason"),
        "epoch": report.get("epoch"),
        "head_sequence": report.get("head_sequence"),
        "tip_sequence_after": report.get("tip_sequence_after"),
        "latest_snapshots_unchanged": report.get("latest_snapshots_unchanged"),
        "store_count": len(ss.STORES),
        "stores_ok": ok_count,
        "stores": stores,
    }


def _head_document(snapshots: Mapping[str, Mapping[str, Any]], *, sequence: int,
                   previous: Optional[str], renewed_at: str) -> bytes:
    labels = [spec.label for spec in ss.STORES]
    body = {
        "schema": ss.HEAD_SCHEMA,
        "operation_id": "ab" * 16,
        "sequence": sequence,
        "previous_manifest_sha256": previous,
        "epoch": 52,
        "writer_id": "cd" * 16,
        "boot_id": "ef" * 16,
        "state": ss.STATE_ACTIVE,
        "transition": "SNAPSHOT",
        "handover": None,
        "claim": {"kind": ss.CLAIM_CLEAN, "at": "2026-10-25T00:00:00Z",
                  "origins": {label: ss.ORIGIN_RESTORED for label in labels},
                  "previous_epoch": 51},
        "lease": {"renewed_at": renewed_at, "heartbeat_path": ss.HEARTBEAT_PATH,
                  "stale_after_seconds": 120},
        "source_revision": "d2f8013b68dbc911229e50e02ecb2208c1d08b43",
        "bucket": ss.DEFAULT_BUCKET,
        "snapshots": {label: dict(snapshots[label]) for label in labels},
        "history": {label: [] for label in labels},
    }
    rendered = canonical(body)
    ss.parse_head(rendered)
    return rendered


def _sqlite_blob(path: Path, *, broken_foreign_key: bool = False,
                 body: str = "receipt-1") -> tuple[bytes, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA foreign_keys=OFF" if broken_foreign_key else "PRAGMA foreign_keys=ON")
        connection.executescript(
            """
            CREATE TABLE owners(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE receipts(
              id INTEGER PRIMARY KEY,
              owner_id INTEGER NOT NULL REFERENCES owners(id),
              body TEXT NOT NULL);
            """
        )
        connection.execute("INSERT INTO owners(id, name) VALUES(1, 'a11oy')")
        owner = 99 if broken_foreign_key else 1
        connection.execute("INSERT INTO receipts(id, owner_id, body) VALUES(1, ?, ?)", (owner, body))
        connection.commit()
    finally:
        connection.close()
    report = ss.verify_sqlite(path, full=True)
    logical = report["logical_sha256"] if report["logical_sha256"] is not None else "0" * 64
    if broken_foreign_key:
        opened = gdw_sqlite_repair._connect_read_only(path)
        try:
            logical = gdw_sqlite_repair.logical_fingerprint(opened)["sha256"]
        finally:
            opened.close()
    return path.read_bytes(), logical


def _lmdb_blob(directory: Path) -> tuple[bytes, str]:
    lmdb = ss._lmdb()
    directory.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(directory), subdir=True, map_size=1 << 20, max_dbs=0, create=True)
    try:
        with env.begin(write=True) as txn:
            txn.put(b"store", b"rehearsal")
    finally:
        env.close()
    logical = ss.lmdb_logical_digest(directory)["logical_sha256"]
    return (directory / "data.mdb").read_bytes(), logical


def _entry(spec: ss.StoreSpec, blob: bytes, logical: str, *, seq: int) -> dict[str, Any]:
    digest = hashlib.sha256(blob).hexdigest()
    name = f"20261025T020000Z-52-{seq}-{digest[:16]}.{spec.extension}"
    return {
        "path": f"{ss.PREFIX}/{spec.label}/{name}",
        "sha256": digest,
        "size": len(blob),
        "kind": spec.kind,
        "integrity": "integrity_check" if spec.kind == "sqlite" else "lmdb_read",
        "logical_sha256": logical,
        "taken_at": "2026-10-25T02:00:00Z",
        "epoch": 52,
        "seq": seq,
    }


def matching_fixture(root: Path) -> tuple[bytes, bytes, dict[str, bytes]]:
    """One canonical HEAD, a later heartbeat with the same snapshots, and its objects."""
    snapshots = {}
    objects = {}
    for index, spec in enumerate(ss.STORES, start=1):
        if spec.kind == "sqlite":
            blob, logical = _sqlite_blob(root / spec.label / "source.sqlite3")
        else:
            blob, logical = _lmdb_blob(root / spec.label / "env")
        entry = _entry(spec, blob, logical, seq=index)
        snapshots[spec.label] = entry
        objects[entry["path"]] = blob
    pinned = _head_document(snapshots, sequence=1, previous=None, renewed_at="2026-10-25T02:00:00Z")
    tip = _head_document(snapshots, sequence=2, previous=hashlib.sha256(pinned).hexdigest(),
                         renewed_at="2026-10-25T02:00:15Z")
    return pinned, tip, objects


def rehearse_from_provider(provider: Any, scratch: Path) -> dict[str, Any]:
    """Read one pinned HEAD and its named objects. The provider cannot be asked to write."""
    if not isinstance(provider, ReadOnlyHub):
        raise StorageBlocked("REHEARSAL_PROVIDER_UNGUARDED")
    root = _assert_scratch(scratch)
    observed = provider_observe(provider)
    pinned = provider_read(provider, observed.revision)
    if pinned != observed.body or pinned is None:
        return _blocked("STATE_HEAD_READBACK_MISMATCH", head_revision=observed.revision)
    head = ss.parse_head(pinned)
    objects: dict[str, bytes] = {}
    download = root / "download"
    download.mkdir()
    bucket = ss.HFBucketObjectStore(provider, ss.DEFAULT_BUCKET, download)
    try:
        for spec in ss.STORES:
            entry = head["snapshots"][spec.label]
            target = download / spec.label
            bucket.get_file(entry["path"], target)
            objects[entry["path"]] = target.read_bytes()
            target.unlink()
    finally:
        shutil.rmtree(download, ignore_errors=True)
    tip = provider_observe(provider)
    tip_body = provider_read(provider, tip.revision)
    if tip_body != tip.body or tip_body is None:
        return _blocked("STATE_HEAD_READBACK_MISMATCH", head_revision=observed.revision)
    verify_root = root / "verify"
    verify_root.mkdir()
    return rehearse_pinned_head(head_body=pinned, tip_body=tip_body, objects=objects,
                                 scratch=verify_root, head_revision=observed.revision)


def provider_observe(provider: ReadOnlyHub) -> ss.Observation:
    backend = ss.HFDatasetHeadBackend(provider, ss.DEFAULT_DATASET, Path(tempfile.mkdtemp()))
    try:
        return backend.observe()
    finally:
        shutil.rmtree(backend.scratch, ignore_errors=True)


def provider_read(provider: ReadOnlyHub, revision: str) -> Optional[bytes]:
    backend = ss.HFDatasetHeadBackend(provider, ss.DEFAULT_DATASET, Path(tempfile.mkdtemp()))
    try:
        return backend.read_at(revision)
    finally:
        shutil.rmtree(backend.scratch, ignore_errors=True)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _exit_code(report: Mapping[str, Any]) -> int:
    if report.get("status") == "SNAPSHOTS_VERIFIED":
        return 0
    if report.get("status") == "SNAPSHOTS_ADVANCED":
        return 3
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--public", dest="public_path", type=Path)
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args(argv)
    if args.self_test == args.fetch:
        print(json.dumps(public_view(_blocked("REHEARSAL_MODE_REQUIRED")), sort_keys=True))
        return 2
    scratch = args.scratch or Path(tempfile.mkdtemp(prefix="a11oy-snapshot-rehearsal-"))
    try:
        if args.self_test:
            with tempfile.TemporaryDirectory(prefix="a11oy-snapshot-fixture-") as fixture:
                pinned, tip, objects = matching_fixture(Path(fixture))
            report = rehearse_pinned_head(head_body=pinned, tip_body=tip, objects=objects,
                                           scratch=scratch, head_revision="1" * 40)
        else:
            token = os.environ.get("HF_TOKEN") or ""
            if not token:
                report = _blocked("HF_TOKEN_REQUIRED")
            else:
                from huggingface_hub import HfApi
                report = rehearse_from_provider(ReadOnlyHub(HfApi(token=token)), scratch)
    except StorageBlocked as error:
        report = _blocked(error.code)
    finally:
        if args.scratch is None:
            shutil.rmtree(scratch, ignore_errors=True)
    public = public_view(report)
    if args.evidence is not None:
        _write_json(args.evidence, report)
    if args.public_path is not None:
        _write_json(args.public_path, public)
    print(json.dumps(public, sort_keys=True))
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
