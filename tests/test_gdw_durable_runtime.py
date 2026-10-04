#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline provider boundaries, actual SQLite stores and native backups."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest

import gdw_durable_runtime as durable
from gdw_durable_artifacts import ArtifactCache, LOGICAL_ROOTS
import gdw_runtime
from gdw_workspace import GDWWorkspace
from routers.series_a_control_plane import Store


def identity(label, path):
    with sqlite3.connect(path) as db:
        if label == "gdw":
            generation = db.execute("SELECT database_generation_id FROM schema_meta").fetchone()[0]
        else:
            generation = db.execute("SELECT value FROM metadata WHERE key='storage_instance_id'").fetchone()[0]
    body = path.read_bytes()
    return {"size": len(body), "sha256": hashlib.sha256(body).hexdigest(), "generation": generation}


class OfflineWriter:
    """Only the remote boundary is simulated; no hosted durability is claimed."""
    def __init__(self, paths):
        self._sequence = 1
        self._set_head({label: identity(label, path) for label, path in paths.items()})
        self.state = "ACTIVE"
        self.commits = []
        self.fenced = False
        self.fail_commit = False

    def _set_head(self, snapshots):
        self.head = SimpleNamespace(revision=f"{self._sequence:040x}", value={
            "snapshots": snapshots, "source_revision": "b" * 40,
            "qualification_sha256": "c" * 64, "operation_id": f"{self._sequence:032x}", "epoch": 1})

    def verify_read(self, deadline):
        if self.fenced:
            raise RuntimeError("remote owner changed")
        return self.head

    def commit(self, snapshots, deadline):
        self.commits.append(snapshots)
        if self.fail_commit:
            raise TimeoutError("lost commit response")
        self._sequence += 1
        self._set_head(snapshots)


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.delenv("GDW_DURABLE_STORAGE", raising=False)
    monkeypatch.delenv("A11OY_SERIES_A_REQUIRE_MOUNT", raising=False)
    monkeypatch.delenv("GDW_REQUIRED_MOUNT", raising=False)
    monkeypatch.setenv("GDW_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("GDW_SQLITE_SYNCHRONOUS", "FULL")
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("GDW_NAMESPACE", "a11oy")
    monkeypatch.setenv("GDW_SERVICE_OWNER_ID", "owner")
    monkeypatch.setenv("GDW_PROOF_DIR", str(LOGICAL_ROOTS["proof_export"]))
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", str(LOGICAL_ROOTS["receipt_projection"]))
    monkeypatch.setattr(durable, "_GATE", None)
    directory = tmp_path / "local"
    directory.mkdir(mode=0o700)
    paths = {label: directory / (label + ".sqlite3") for label in durable.LABELS}
    gdw = GDWWorkspace(str(paths["gdw"]), namespace="a11oy", owner_id="owner")
    series = Store(str(paths["series_a"]))
    series.append_event("preserved", {"old": True})
    for path in paths.values():
        path.chmod(0o600)
    writer = OfflineWriter(paths)
    published = []

    def publish(snapshots, deadline):
        assert set(snapshots) == set(paths)
        for path in snapshots.values():
            assert not any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
                assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert db.execute("PRAGMA foreign_key_check").fetchone() is None
        published.append({label: path.read_bytes() for label, path in snapshots.items()})
        return {label: identity(label, path) for label, path in snapshots.items()}

    cache_directory = directory / "artifacts"
    cache_directory.mkdir(mode=0o700)
    artifact_publications = []

    def publish_artifact(path, object_path, digest, deadline):
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        artifact_publications.append((object_path, data))
        return {"path": object_path, "size": len(data), "sha256": digest, "xet_hash": "a" * 64}

    artifacts = ArtifactCache(cache_directory, publish_artifact)
    gate = durable.LocalGate(writer, paths, directory, publish, artifacts=artifacts)
    gate.bind_admission_context(admission_sha256="c" * 64, qualification_sha256="d" * 64,
        source_revision="b" * 40,
        generations={label: writer.head.value["snapshots"][label]["generation"] for label in durable.LABELS},
        actual_host_full_state_ack_ms=10)
    durable.install(gate)
    monkeypatch.setenv("GDW_DURABLE_STORAGE", durable.MODE)
    monkeypatch.setenv("GDW_DB_PATH", str(paths["gdw"]))
    monkeypatch.setenv("A11OY_SERIES_A_DB", str(paths["series_a"]))
    value = SimpleNamespace(gdw=gdw, series=series, paths=paths, writer=writer, gate=gate,
                            published=published, directory=directory,
                            artifact_publications=artifact_publications)
    yield value
    gate.close()


def test_safe_managed_status_binds_current_acknowledged_head_and_is_detached(stores):
    before = stores.gate.managed_status()
    stores.series.append_event("next-acknowledged-state", {})
    after = stores.gate.managed_status()
    assert after["dataset_revision"] != before["dataset_revision"]
    assert after["operation_id"] != before["operation_id"]
    assert after["dataset_revision"] == stores.writer.head.revision
    assert after["generations"] == before["generations"]
    assert after["admission_sha256"] == "c" * 64
    assert after["qualification_sha256"] == "d" * 64
    after["generations"]["gdw"] = "changed caller value"
    assert stores.gate.managed_status()["generations"] == before["generations"]
    status = stores.series.storage_status()
    assert status["managed_admission"] == stores.gate.managed_status()
    recovery, _ = stores.series.receipt_recovery_snapshot("missing")
    assert recovery["managed_admission"] == status["managed_admission"]
    assert not any(token in json.dumps(status["managed_admission"]) for token in (str(stores.directory), "sqlite3", "payload"))


def test_managed_witness_requires_bound_context_and_verified_owner(stores):
    context = stores.gate._admission_context
    stores.gate._admission_context = None
    with pytest.raises(durable.DurableStorageUnavailable, match="ADMISSION_CONTEXT_UNAVAILABLE"):
        stores.gate.managed_status()
    stores.gate._admission_context = context
    stores.writer.fenced = True
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gate.managed_status()
    assert stores.gate.poisoned


def test_managed_context_cannot_be_rebound_after_install(stores):
    context = stores.gate._admission_context
    with pytest.raises(durable.DurableStorageUnavailable, match="ADMISSION_CONTEXT_ALREADY_BOUND"):
        stores.gate.bind_admission_context(**context)


def test_environment_cannot_admit_or_create_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("GDW_DURABLE_STORAGE", durable.MODE)
    monkeypatch.setattr(durable, "_GATE", None)
    monkeypatch.setenv("GDW_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("GDW_SQLITE_SYNCHRONOUS", "FULL")
    for create in (lambda: Store(str(tmp_path / "new.sqlite3")),
                   lambda: GDWWorkspace(str(tmp_path / "new.sqlite3"))):
        with pytest.raises(durable.DurableStorageUnavailable, match="QUALIFIED_STORAGE_STARTUP_REQUIRED"):
            create()
    assert list(tmp_path.iterdir()) == []


def test_real_store_constructors_preserve_rows_and_generation_without_publishing(stores):
    before = {label: path.read_bytes() for label, path in stores.paths.items()}
    gdw = GDWWorkspace(str(stores.paths["gdw"]), namespace="a11oy", owner_id="owner", production=True)
    series = Store(str(stores.paths["series_a"]))
    assert gdw.database_generation_id == stores.gdw.database_generation_id
    assert series.events_since(0)[0]["kind"] == "preserved"
    assert {label: path.read_bytes() for label, path in stores.paths.items()} == before
    assert not stores.published and not stores.writer.commits


def test_series_commit_acknowledges_before_return_and_preserves_other_store(stores):
    generation = stores.gdw.database_generation_id
    stores.series.append_event("new", {"value": 1})
    assert len(stores.published) == len(stores.writer.commits) == 1
    assert [row["kind"] for row in stores.series.events_since(0)] == ["preserved", "new"]
    assert stores.writer.head.value["snapshots"]["gdw"]["generation"] == generation
    assert not list(stores.directory.glob("snapshot-*"))
    status, receipt = stores.series.receipt_recovery_snapshot("nonexistent")
    assert status["durable_storage"] == durable.MODE and receipt is None


def test_gdw_transaction_uses_real_commit_boundary(stores):
    with stores.gdw.transaction() as db:
        db.execute("UPDATE schema_meta SET upgraded_at='offline-test' WHERE schema_name='gdw'")
        assert not stores.writer.commits
    assert len(stores.writer.commits) == 1
    with stores.gdw.transaction() as db:
        assert db.execute("SELECT upgraded_at FROM schema_meta").fetchone()[0] == "offline-test"
    assert len(stores.writer.commits) == 1


@pytest.mark.parametrize("boundary", ["upload", "commit"])
def test_unknown_outcome_poison_blocks_both_reads_and_receipt_replay(stores, boundary):
    if boundary == "upload":
        def fail(*args):
            raise TimeoutError("unknown upload")
        stores.gate.publish = fail
    else:
        stores.writer.fail_commit = True
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.append_event("uncertain", {})
    assert stores.gate.poisoned
    actions = [lambda: stores.series.events_since(0),
               lambda: stores.series.outcome_for_passport("retained-passport"),
               lambda: stores.series.receipt_recovery_snapshot("retained-receipt"),
               lambda: stores.gdw.integrity(),
               lambda: stores.series.append_event("must-not-retry", {})]
    for action in actions:
        with pytest.raises(durable.DurableStorageUnavailable):
            action()
    assert len(stores.writer.commits) == (1 if boundary == "commit" else 0)
    assert list(stores.directory.glob("snapshot-*"))


def test_fenced_writer_blocks_even_cached_read(stores):
    stores.writer.fenced = True
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.events_since(0)
    assert stores.gate.poisoned and not stores.writer.commits


def test_rollback_does_not_publish_or_poison(stores):
    with pytest.raises(ValueError, match="abort"):
        with stores.gdw.transaction() as db:
            db.execute("UPDATE schema_meta SET upgraded_at='not-committed'")
            raise ValueError("abort")
    assert not stores.writer.commits and not stores.gate.poisoned
    with stores.gdw.transaction() as db:
        assert db.execute("SELECT upgraded_at FROM schema_meta").fetchone()[0] != "not-committed"


@pytest.mark.parametrize("sql", ["COMMIT", "PRAGMA synchronous=OFF", "PRAGMA journal_mode=WAL",
                                 "CREATE TABLE bypass(value)", "ATTACH ':memory:' AS bypass"])
def test_alternate_commit_or_schema_mutation_cannot_bypass_gate(stores, sql):
    with stores.gdw.transaction() as db:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute(sql)
    assert not stores.writer.commits


def test_native_local_file_lock_excludes_second_process(stores):
    code = "import fcntl,os,sys; f=os.open(sys.argv[1],os.O_RDWR); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
    result = subprocess.run([os.sys.executable, "-c", code, str(stores.directory / "writer.lock")], capture_output=True)
    assert result.returncode != 0 and b"BlockingIOError" in result.stderr


def test_local_lock_and_restore_checks_precede_remote_claim(stores):
    restored = stores.writer.head
    contender = OfflineWriter(stores.paths)
    contender.state = "NEW"
    claims = []

    def claim(head, deadline):
        claims.append(head)
        contender.state, contender.head = "ACTIVE", head

    contender.claim = claim
    with pytest.raises(BlockingIOError):
        durable.LocalGate(contender, stores.paths, stores.directory, stores.gate.publish, restored_head=restored, artifacts=stores.gate.artifacts)
    assert not claims
    stores.gate.close()
    gate = durable.LocalGate(contender, stores.paths, stores.directory, stores.gate.publish, restored_head=restored, artifacts=stores.gate.artifacts)
    try:
        assert claims == [restored] and contender.state == "ACTIVE"
    finally:
        gate.close()


def test_forked_process_cannot_reuse_claim(stores, monkeypatch):
    monkeypatch.setattr(stores.gate, "_pid", -1)
    with pytest.raises(durable.DurableStorageUnavailable, match="POISONED"):
        stores.series.events_since(0)


def test_both_stores_wait_for_remote_ack_before_exposing_state(stores):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = stores.gate.publish
    errors = []

    def delayed(paths, deadline):
        entered.set()
        assert release.wait(5)
        return original(paths, deadline)

    def write():
        try:
            stores.series.append_event("serialized", {})
        except BaseException as error:
            errors.append(error)

    def read():
        try:
            with stores.gdw.transaction() as db:
                db.execute("SELECT * FROM schema_meta").fetchall()
            finished.set()
        except BaseException as error:
            errors.append(error)

    stores.gate.publish = delayed
    writer = threading.Thread(target=write)
    reader = threading.Thread(target=read)
    writer.start()
    assert entered.wait(5)
    reader.start()
    assert not finished.wait(0.05)
    release.set()
    writer.join(5)
    reader.join(5)
    assert not writer.is_alive() and not reader.is_alive()
    assert not errors and finished.is_set()


def test_production_prepare_validates_restored_database_without_reinitializing(stores):
    before = stores.paths["gdw"].read_bytes()
    observed = gdw_runtime.prepare_runtime()
    assert observed["database_generation_id"] == stores.gdw.database_generation_id
    assert observed["durable_storage"] == durable.MODE
    assert observed["mount_verified"] is False
    assert stores.paths["gdw"].read_bytes() == before
    assert not stores.writer.commits


def test_unrestored_path_and_changed_database_fail_closed(stores, tmp_path):
    with pytest.raises(durable.DurableStorageUnavailable, match="UNADMITTED_STORE_PATH"):
        stores.gate.connect("gdw", tmp_path / "empty.sqlite3")
    assert not (tmp_path / "empty.sqlite3").exists()
    stores.gate.close()
    stores.paths["gdw"].write_bytes(b"unverified database")
    with pytest.raises(durable.DurableStorageUnavailable, match="IDENTITY_MISMATCH"):
        durable.LocalGate(stores.writer, stores.paths, stores.directory, stores.gate.publish, artifacts=stores.gate.artifacts)


def test_environment_removal_cannot_disable_installed_gate(stores, monkeypatch):
    monkeypatch.delenv("GDW_DURABLE_STORAGE")
    stores.gate.poisoned = True
    assert durable.enabled()
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.events_since(0)


def test_real_gdw_route_cannot_ack_or_replay_after_lost_commit(stores, monkeypatch):
    from fastapi.testclient import TestClient
    from tests.test_gdw_frontier import make_app, payload, headers

    app = make_app(stores.directory, monkeypatch)
    monkeypatch.setenv("GDW_PROOF_DIR", str(LOGICAL_ROOTS["proof_export"]))
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", str(LOGICAL_ROOTS["receipt_projection"]))
    with TestClient(app) as client:
        first = client.post("/v1/gdw/step", json=payload(), headers=headers("stored-request"))
        assert first.status_code == 200, first.text
        assert first.json()["receipt_hash"]
        count = len(stores.writer.commits)
        assert count > 0
        replay = client.post("/v1/gdw/step", json=payload(), headers=headers("stored-request"))
        assert replay.status_code == 200 and replay.json()["replayed"] is True
        assert len(stores.writer.commits) == count
        stores.writer.fail_commit = True
        uncertain = client.post("/v1/gdw/step", json=payload(), headers=headers("uncertain-request"))
        assert uncertain.status_code == 503, uncertain.text
        for request_id in ("stored-request", "uncertain-request", "new-request"):
            response = client.post("/v1/gdw/step", json=payload(), headers=headers(request_id))
            assert response.status_code == 503
        assert len(stores.writer.commits) == count + 1


def _series_execution_case(stores, monkeypatch, path):
    from routers import series_a_control_plane as series

    signer = series.ReceiptSigner.__new__(series.ReceiptSigner)
    signer.private_key, signer.public_pem, signer.source, signer.error = (
        None, "", "unavailable", "offline unsigned fixture"
    )
    service = series.Service.__new__(series.Service)
    service.store, service.signer = stores.series, signer
    service.runtime_boot_id = "boot_" + "a" * 32
    service.execution_tasks = set()
    monkeypatch.setattr(service, "_governance_gate", lambda _action: {
        "allowed": path != "governance-denial",
        "reason_codes": ["OFFLINE_GOVERNANCE_DENIAL"] if path == "governance-denial" else [],
    })
    monkeypatch.setattr(service, "_fresh_evidence_reasons", lambda _evidence: (
        ["OFFLINE_EVIDENCE_DENIAL"] if path == "evidence-denial" else []
    ))
    actions = []

    async def forbidden_action(*_args):
        actions.append(True)
        pytest.fail("an unacknowledged or consumed attempt reached execution")

    monkeypatch.setattr(service, "_execute_consumed", forbidden_action)
    digest = stores.series.save_passport({
        "passport_id": "offline-passport", "created_at": "2026-10-04T18:00:00Z",
        "decision": "BLOCK" if path == "initial-denial" else "ALLOW",
        "action": {"type": "probe.public_surface", "target": "https://example.invalid"},
        "evidence": [],
    })
    return service, digest, actions


def _series_execution_client(service, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers import series_a_control_plane as series

    # Use the real service method, store and registered HTTP handler without
    # loading signing credentials or starting unrelated provider refresh work.
    monkeypatch.setattr(series, "Service", lambda _path=None: service)
    app = FastAPI()
    series.register(app)
    return TestClient(app)


@pytest.mark.parametrize("path", ["allow", "initial-denial", "governance-denial", "evidence-denial"])
@pytest.mark.parametrize("transport", ["service", "http"])
def test_series_uncertain_accepted_commit_preserves_unavailable(stores, monkeypatch, path, transport):
    service, digest, actions = _series_execution_case(stores, monkeypatch, path)
    client = _series_execution_client(service, monkeypatch) if transport == "http" else None
    original = stores.writer.commit
    before = len(stores.writer.commits)

    def accepted_then_lost(snapshots, deadline):
        original(snapshots, deadline)
        raise TimeoutError("offline accepted commit response lost")

    monkeypatch.setattr(stores.writer, "commit", accepted_then_lost)
    try:
        if client is None:
            with pytest.raises(durable.DurableStorageUnavailable):
                asyncio.run(service.execute({"passport_digest": digest}))
        else:
            response = client.post("/api/a11oy/v1/series-a/passports/execute",
                                   json={"passport_digest": digest})
            assert response.status_code == 503, response.text
            assert response.json() == {"detail": "Durable storage is unavailable"}
            replay = client.post("/api/a11oy/v1/series-a/passports/execute",
                                 json={"passport_digest": digest})
            assert replay.status_code == 503, replay.text
    finally:
        if client is not None:
            client.close()
    assert len(stores.writer.commits) == before + 1
    assert stores.gate.poisoned and not actions
    assert stores.writer.head.value["snapshots"] == stores.writer.commits[-1]
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.load_passport(digest)
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gdw.integrity()


@pytest.mark.parametrize("path", ["allow", "initial-denial", "governance-denial", "evidence-denial"])
@pytest.mark.parametrize("transport", ["service", "http"])
def test_series_native_attempt_conflict_remains_409(stores, monkeypatch, path, transport):
    from fastapi import HTTPException

    service, digest, actions = _series_execution_case(stores, monkeypatch, path)
    client = _series_execution_client(service, monkeypatch) if transport == "http" else None
    original_load = stores.series.load_passport
    before = len(stores.writer.commits)

    def load_then_consume(requested):
        passport = original_load(requested)
        stores.series.begin_execution(requested, "boot_" + "b" * 32, "2026-10-04T18:00:01Z")
        return passport

    # A competing native transaction consumes the attempt after the service's
    # read, so the business RuntimeError originates at the guarded write itself.
    monkeypatch.setattr(stores.series, "load_passport", load_then_consume)
    try:
        if client is None:
            with pytest.raises(HTTPException) as error:
                asyncio.run(service.execute({"passport_digest": digest}))
            assert error.value.status_code == 409
            assert error.value.detail == "passport attempt already consumed"
        else:
            response = client.post("/api/a11oy/v1/series-a/passports/execute",
                                   json={"passport_digest": digest})
            assert response.status_code == 409, response.text
            assert response.json() == {"detail": "passport attempt already consumed"}
    finally:
        if client is not None:
            client.close()
    assert len(stores.writer.commits) == before + 1
    assert not stores.gate.poisoned and not actions
    assert original_load(digest)["attempts"] == 1
    assert stores.series.execution_status(digest)["state"] == "PENDING"


def test_actual_gdw_drain_and_series_receipt_pass_through_installed_gate(stores, monkeypatch, tmp_path):
    from tests.test_gdw_runtime import _queued_proof
    from routers.series_a_control_plane import ReceiptSigner

    _queued_proof(stores.gdw)
    before = len(stores.writer.commits)
    report = gdw_runtime.drain_once(limit=1, lease_seconds=30, worker_id="offline-worker", workspace=stores.gdw)
    assert report["exported"] == 1 and report["failed"] == 0
    assert len(stores.writer.commits) >= before + 2  # persisted claim and terminal outcome
    assert stores.gdw.integrity()["ok"] is True
    signer = ReceiptSigner.__new__(ReceiptSigner)
    signer.private_key, signer.public_pem, signer.source, signer.error = None, "", "unavailable", "offline unsigned fixture"
    receipt = stores.series.append_receipt("offline.ack", {"value": "preserved"}, signer)
    status, recovered = stores.series.receipt_recovery_snapshot(receipt["receipt_hash"])
    assert status["receipt_count"] == 1
    assert recovered["receipt_hash"] == receipt["receipt_hash"]
    assert recovered["envelope"]["signature_status"] == "UNSIGNED_UNAVAILABLE"


def test_snapshot_deadline_stops_before_publication(stores, monkeypatch):
    monkeypatch.setattr(stores.gate, "deadline", lambda: time.monotonic() - 1)
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.append_event("expired", {})
    assert stores.gate.poisoned
    assert not stores.published and not stores.writer.commits


def test_cleanup_failure_does_not_repeat_acknowledged_write(stores, monkeypatch):
    original = Path.unlink

    def fail_cleanup(path, *args, **kwargs):
        if path.parent.name.startswith("snapshot-"):
            raise OSError("private staging unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    stores.series.append_event("acknowledged", {})
    assert len(stores.writer.commits) == 1
    assert stores.gate.cleanup_pending and not stores.gate.poisoned
    assert stores.series.events_since(0)[-1]["kind"] == "acknowledged"
    assert len(stores.writer.commits) == 1


@pytest.mark.parametrize("field", ["sha256", "size", "generation"])
def test_wrong_uploaded_identity_is_not_acknowledged(stores, field):
    original = stores.gate.publish

    def wrong(paths, deadline):
        result = original(paths, deadline)
        result["gdw"][field] = 123 if field == "size" else "0" * 64
        return result

    stores.gate.publish = wrong
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.append_event("wrong-identity", {})
    assert stores.gate.poisoned and not stores.writer.commits


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "sidecar"])
def test_non_native_or_shared_file_is_rejected(stores, kind):
    stores.gate.close()
    path = stores.paths["gdw"]
    if kind == "symlink":
        target = path.with_name("target.sqlite3")
        path.rename(target)
        path.symlink_to(target)
    elif kind == "hardlink":
        os.link(path, path.with_name("alias.sqlite3"))
    else:
        Path(str(path) + "-wal").touch()
    with pytest.raises(durable.DurableStorageUnavailable):
        durable.LocalGate(stores.writer, stores.paths, stores.directory, stores.gate.publish, artifacts=stores.gate.artifacts)
