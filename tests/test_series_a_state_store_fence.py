# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline Series-A admission/drain regressions using real disposable SQLite."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_state_store as ss
from routers import series_a_control_plane as control
from tests.state_store_support import FakeClock, FakeHeadBackend, replica


class UnsignedCountingSigner:
    """No key discovery or signing; only a synthetic envelope for local tests."""

    source = "UNSIGNED_SYNTHETIC"

    def __init__(self):
        self.calls = 0

    def sign(self, payload):
        self.calls += 1
        return {"payload": payload, "signature_status": "UNSIGNED_SYNTHETIC"}


@pytest.fixture
def fenced_world(tmp_path, monkeypatch):
    clock, backend = FakeClock(), FakeHeadBackend()
    objects = ss.LocalDirObjectStore(tmp_path / "objects")
    monkeypatch.setattr(ss, "_ACTIVE", None)
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setattr(control, "ReceiptSigner", UnsignedCountingSigner)
    writer = replica(tmp_path, "writer", objects, backend, clock)
    writer.boot()
    writer.heartbeat_once()
    monkeypatch.setattr(ss, "_ACTIVE", writer)
    owner = control.Store()
    yield SimpleNamespace(writer=writer, owner=owner, backend=backend,
                          objects=objects, clock=clock, root=tmp_path,
                          signer=UnsignedCountingSigner())
    writer._close_watchers()


def counts(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        return {table: db.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
                for table in ("receipts", "events", "snapshots", "passports", "passport_executions")}


def test_released_store_refuses_receipt_before_signing(fenced_world):
    world = fenced_world
    world.writer.close()
    before = counts(world.owner.path)
    assert world.writer.role == ss.ROLE_RELEASED

    with pytest.raises(ss.StorageBlocked):
        world.owner.append_receipt("SYNTHETIC", {"marker": "after-release"}, world.signer)

    assert world.signer.calls == 0
    assert counts(world.owner.path) == before
    assert world.writer._inflight == 0


def test_fenced_store_refuses_writes_before_signing(fenced_world):
    world = fenced_world
    world.writer._fence("SYNTHETIC_TEST_FENCE")
    before = counts(world.owner.path)
    with pytest.raises(ss.StorageBlocked):
        world.owner.append_receipt("SYNTHETIC", {"marker": "fenced"}, world.signer)
    assert world.signer.calls == 0
    assert counts(world.owner.path) == before


def test_released_service_refresh_never_signs_or_collects(fenced_world, monkeypatch):
    world = fenced_world
    service = control.Service()
    collected = []

    async def collect():
        collected.append(True)
        return {"observed_at": "2026-11-17T00:00:00Z", "valid_until": "2026-11-17T00:05:00Z",
                "status": "SAMPLE", "counts": {}}

    monkeypatch.setattr(service.collector, "collect", collect)
    world.writer.close()
    before = counts(world.owner.path)
    with pytest.raises(ss.StorageBlocked):
        asyncio.run(service.refresh("periodic", governance={"allowed": True, "decision": "ALLOW"}))
    assert service.signer.calls == 0
    assert not collected
    assert counts(world.owner.path) == before


def test_released_reads_preserve_receipts_events_and_head(fenced_world):
    world = fenced_world
    receipt = world.owner.append_receipt("SYNTHETIC", {"marker": "before-release"}, world.signer)
    world.writer.close()
    before = counts(world.owner.path)
    signed = world.signer.calls
    head = world.backend.observe()

    assert world.owner.storage_status()["receipt_count"] == 1
    assert world.owner.list_receipts()[0]["receipt_hash"] == receipt["receipt_hash"]
    assert len(world.owner.events_since(0)) == 1
    status, recovered = world.owner.receipt_recovery_snapshot(receipt["receipt_hash"])
    assert status["receipt_count"] == 1
    assert recovered["receipt_hash"] == receipt["receipt_hash"]
    assert world.owner.latest_snapshot() is None
    assert world.owner.load_passport("absent-synthetic-passport") is None

    assert counts(world.owner.path) == before
    assert world.signer.calls == signed
    assert world.backend.observe() == head
    assert world.writer._inflight == 0


def test_read_connection_opened_while_active_stays_read_only_after_release(fenced_world):
    world = fenced_world
    with world.owner.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
        assert world.writer._inflight == 0
        world.writer.close()
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("INSERT INTO events(event_id,kind,payload,created_at) VALUES(?,?,?,?)",
                       ("synthetic-forbidden", "SYNTHETIC", "{}", "2026-11-17T00:00:00Z"))
    assert counts(world.owner.path)["events"] == 0


def test_requested_path_cannot_escape_active_v2_owner(fenced_world):
    world = fenced_world
    outside = world.root / "outside-owner.sqlite3"
    with pytest.raises(ss.StorageBlocked):
        control.Store(requested_path=str(outside))
    assert not outside.exists()
    assert world.writer._inflight == 0


def test_old_store_cannot_borrow_successors_write_authority(fenced_world, monkeypatch):
    world = fenced_world
    old_path = world.owner.path
    world.writer.close()
    successor = replica(world.root, "successor", world.objects, world.backend, world.clock)
    try:
        successor.boot()
        assert successor.claim_kind == ss.CLAIM_CLEAN
        monkeypatch.setattr(ss, "_ACTIVE", successor)
        new_owner = control.Store()
        with pytest.raises(ss.StorageBlocked):
            world.owner.append_receipt("SYNTHETIC", {"marker": "old-owner"}, world.signer)
        assert world.signer.calls == 0
        new_owner.append_event("SYNTHETIC", {"marker": "new-owner"})
        assert counts(old_path)["events"] == 0
        assert counts(new_owner.path)["events"] == 1
    finally:
        successor._close_watchers()


def test_write_exception_rolls_back_and_releases_admission(fenced_world):
    world = fenced_world
    with pytest.raises(RuntimeError, match="synthetic rollback"):
        with world.owner.connect(write=True) as db:
            db.execute("INSERT INTO events(event_id,kind,payload,created_at) VALUES(?,?,?,?)",
                       ("synthetic-rollback", "SYNTHETIC", "{}", "2026-11-17T00:00:00Z"))
            raise RuntimeError("synthetic rollback")
    assert world.writer._inflight == 0
    assert counts(world.owner.path)["events"] == 0
    world.owner.append_event("SYNTHETIC", {"marker": "after-rollback"})
    world.writer.close()
    assert world.writer.role == ss.ROLE_RELEASED


def test_failed_commit_releases_admission_and_rolls_back(fenced_world):
    world = fenced_world
    with pytest.raises(sqlite3.IntegrityError):
        with world.owner.connect(write=True) as db:
            db.execute("PRAGMA defer_foreign_keys=ON")
            db.execute("INSERT INTO passport_executions(passport_digest,state,runtime_boot_id,started_at) VALUES(?,?,?,?)",
                       ("absent-synthetic-passport", "PENDING", "synthetic-boot", "2026-11-17T00:00:00Z"))
    assert world.writer._inflight == 0
    assert counts(world.owner.path)["passport_executions"] == 0
    world.owner.append_event("SYNTHETIC", {"marker": "after-failed-commit"})


def test_receipt_and_event_roll_back_as_one_acknowledgement(fenced_world):
    world = fenced_world
    with world.owner.connect(write=True) as db:
        db.execute("CREATE TRIGGER reject_synthetic_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'synthetic event failure'); END")
    before = counts(world.owner.path)
    with pytest.raises(sqlite3.IntegrityError, match="synthetic event failure"):
        world.owner.append_receipt("SYNTHETIC", {"marker": "atomicity"}, world.signer)
    assert counts(world.owner.path) == before
    assert world.writer._inflight == 0


def test_connection_and_prepared_cursor_cannot_write_after_scope_closes(fenced_world):
    world = fenced_world
    statement = "INSERT INTO events(event_id,kind,payload,created_at) VALUES(?,?,?,?)"
    with world.owner.connect(write=True) as db:
        cursor = db.cursor()
        cursor.execute(statement, ("synthetic-before", "SYNTHETIC", "{}", "2026-11-17T00:00:00Z"))
    assert world.writer._inflight == 0
    world.writer.close()
    with pytest.raises(sqlite3.ProgrammingError):
        cursor.execute(statement, ("synthetic-after", "SYNTHETIC", "{}", "2026-11-17T00:01:00Z"))
    assert counts(world.owner.path)["events"] == 1


def test_release_waits_for_receipt_and_event_then_restores_both(fenced_world):
    world = fenced_world
    signing_started = threading.Event()
    finish_signing = threading.Event()
    handover_started = threading.Event()
    world.writer.add_quiesce_hook(handover_started.set)

    class PausedSigner(UnsignedCountingSigner):
        def sign(self, payload):
            signing_started.set()
            if not finish_signing.wait(timeout=5):
                raise RuntimeError("synthetic signer barrier timeout")
            return super().sign(payload)

    signer = PausedSigner()
    with ThreadPoolExecutor(max_workers=2) as pool:
        appending = pool.submit(world.owner.append_receipt, "SYNTHETIC", {"marker": "admitted-before-handover"}, signer)
        releasing = None
        try:
            assert signing_started.wait(timeout=5)
            assert world.writer._inflight == 1
            releasing = pool.submit(world.writer.close)
            assert handover_started.wait(timeout=5)
            assert world.writer.role == ss.ROLE_HANDOVER
            assert not releasing.done()
            assert world.backend.head()["state"] == ss.STATE_ACTIVE
        finally:
            finish_signing.set()
        receipt = appending.result(timeout=5)
        if releasing is not None:
            releasing.result(timeout=5)
    assert world.writer.role == ss.ROLE_RELEASED
    assert world.writer._inflight == 0
    assert world.backend.head()["state"] == ss.STATE_RELEASED

    successor = replica(world.root, "successor", world.objects, world.backend, world.clock)
    try:
        successor.boot()
        assert successor.claim_kind == ss.CLAIM_CLEAN
        restored_path = successor.local_path("series_a")
        assert counts(restored_path)["receipts"] == 1
        assert counts(restored_path)["events"] == 1
        with closing(sqlite3.connect(restored_path)) as db:
            assert db.execute("SELECT receipt_hash FROM receipts").fetchone()[0] == receipt["receipt_hash"]
    finally:
        successor._close_watchers()


@pytest.mark.parametrize("child_kind", ["task", "thread"])
def test_child_cannot_borrow_inherited_admission_during_handover(fenced_world, child_kind):
    world = fenced_world
    handover_started = threading.Event()
    world.writer.add_quiesce_hook(handover_started.set)
    signer = UnsignedCountingSigner()

    def refused_child_write():
        with pytest.raises(ss.StorageBlocked):
            world.owner.append_receipt("SYNTHETIC", {"marker": "child-after-handover"}, signer)

    with ThreadPoolExecutor(max_workers=1) as pool:
        async def exercise():
            releasing = None
            child_go = asyncio.Event()
            child = None
            try:
                with world.owner.write_scope():
                    async def inherited_child():
                        await child_go.wait()
                        refused_child_write()

                    if child_kind == "task":
                        child = asyncio.create_task(inherited_child())
                    releasing = pool.submit(world.writer.close)
                    assert await asyncio.to_thread(handover_started.wait, 5)
                    assert world.writer.role == ss.ROLE_HANDOVER
                    assert not releasing.done()
                    if child_kind == "task":
                        child_go.set()
                        await child
                    else:
                        # to_thread copies ContextVars but may not copy authority.
                        await asyncio.to_thread(refused_child_write)
                    assert signer.calls == 0
                    assert world.writer._inflight == 1
                    world.owner.append_event("SYNTHETIC", {"marker": "admitted-parent-drain"})
            finally:
                child_go.set()
                if child is not None and not child.done():
                    child.cancel()
                    await asyncio.gather(child, return_exceptions=True)
            if releasing is not None:
                releasing.result(timeout=5)

        asyncio.run(exercise())

    assert world.writer.role == ss.ROLE_RELEASED
    assert world.writer._inflight == 0
    assert counts(world.owner.path)["events"] == 1
    assert counts(world.owner.path)["receipts"] == 0


def test_fenced_inflight_transaction_cannot_commit(fenced_world):
    world = fenced_world
    with pytest.raises(ss.StorageBlocked):
        with world.owner.connect(write=True) as db:
            db.execute("INSERT INTO events(event_id,kind,payload,created_at) VALUES(?,?,?,?)",
                       ("synthetic-lost-owner", "SYNTHETIC", "{}", "2026-11-17T00:00:00Z"))
            world.writer._fence("SYNTHETIC_LEASE_LOSS")
    assert counts(world.owner.path)["events"] == 0
    assert world.writer._inflight == 0


def test_sqlite_connection_rejects_path_for_another_store_label(fenced_world):
    world = fenced_world
    with pytest.raises(ss.StorageBlocked):
        with world.writer.sqlite_connection("gdw", world.owner.path, write=True):
            pytest.fail("wrong label was admitted")
    assert world.writer._inflight == 0


def test_nested_write_refusal_has_bounded_http_response(fenced_world):
    world = fenced_world
    app = FastAPI()

    @app.post("/synthetic-admitted-write")
    async def admitted_then_refused():
        raise ss.StateWriteUnavailable("STATE_STORE_HANDOVER")

    @app.get("/synthetic-unrelated-storage-error")
    async def unrelated_storage_error():
        raise ss.StorageBlocked("SYNTHETIC_UNRELATED_STORAGE_ERROR")

    ss.register(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/synthetic-admitted-write", json={})
        assert response.status_code == 503
        assert response.headers["retry-after"] == str(ss.RETRY_AFTER_SECONDS)
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"error": {"code": "STATE_STORE_HANDOVER",
                                  "message": "storage is read-only",
                                  "retry_after_seconds": ss.RETRY_AFTER_SECONDS}}
        unrelated = client.get("/synthetic-unrelated-storage-error")
        assert unrelated.status_code == 500
        assert "retry-after" not in unrelated.headers
        assert client.get("/api/a11oy/v1/storage/status").status_code == 200
    assert world.writer._inflight == 0
    assert counts(world.owner.path)["receipts"] == 0


def synthetic_manifest():
    manifest = {"schema": control.SCHEMA_MANIFEST,
                "observed_at": control._now(), "valid_until": control._future(300),
                "source_revision": "a" * 40, "status": "SAMPLE",
                "critical_failures": [], "counts": {}, "fixture": "UNSIGNED_SYNTHETIC"}
    manifest["manifest_digest"] = control._sha(manifest)
    return manifest


def restored_series_a_path(world):
    successor = replica(world.root, "service-successor", world.objects, world.backend, world.clock)
    try:
        successor.boot()
        assert successor.claim_kind == ss.CLAIM_CLEAN
        return successor.local_path("series_a")
    finally:
        successor._close_watchers()


def test_admitted_refresh_finishes_before_release_snapshot(fenced_world, monkeypatch):
    world = fenced_world
    service = control.Service()
    handover_started = threading.Event()
    world.writer.add_quiesce_hook(handover_started.set)

    with ThreadPoolExecutor(max_workers=1) as pool:
        async def exercise():
            collecting, finish_collection = asyncio.Event(), asyncio.Event()

            async def collect():
                collecting.set()
                await finish_collection.wait()
                return synthetic_manifest()

            monkeypatch.setattr(service.collector, "collect", collect)
            refreshing = asyncio.create_task(service.refresh("periodic", governance={"allowed": True, "decision": "ALLOW"}))
            releasing = None
            try:
                await asyncio.wait_for(collecting.wait(), timeout=5)
                assert world.writer._inflight == 1
                assert service.signer.calls == 1  # authorization only
                releasing = pool.submit(world.writer.close)
                assert await asyncio.to_thread(handover_started.wait, 5)
                assert world.writer.role == ss.ROLE_HANDOVER
                assert not releasing.done()
                finish_collection.set()
                result = await asyncio.wait_for(refreshing, timeout=5)
            finally:
                finish_collection.set()
                if not refreshing.done():
                    refreshing.cancel()
                    await asyncio.gather(refreshing, return_exceptions=True)
            if releasing is not None:
                releasing.result(timeout=5)
            return result

        result = asyncio.run(exercise())

    assert world.writer.role == ss.ROLE_RELEASED
    assert world.writer._inflight == 0
    assert service.signer.calls == 3
    restored = restored_series_a_path(world)
    assert counts(restored) == {"receipts": 2, "events": 2, "snapshots": 1, "passports": 0, "passport_executions": 0}
    with closing(sqlite3.connect(restored)) as db:
        assert db.execute("SELECT digest FROM snapshots").fetchone()[0] == control._sha(result["manifest"])
        assert db.execute("SELECT receipt_hash FROM receipts WHERE kind='estate.refresh'").fetchone()[0] == result["refresh_receipt"]["receipt_hash"]


def test_cancelled_refresh_releases_admission_without_later_signing(fenced_world, monkeypatch):
    world = fenced_world
    service = control.Service()

    async def exercise():
        collecting, finish_collection = asyncio.Event(), asyncio.Event()

        async def collect():
            collecting.set()
            await finish_collection.wait()
            return synthetic_manifest()

        monkeypatch.setattr(service.collector, "collect", collect)
        refreshing = asyncio.create_task(service.refresh("periodic", governance={"allowed": True, "decision": "ALLOW"}))
        try:
            await asyncio.wait_for(collecting.wait(), timeout=5)
            assert world.writer._inflight == 1
            assert service.signer.calls == 1
            refreshing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await refreshing
            assert world.writer._inflight == 0
            world.writer.close()
            finish_collection.set()
            await asyncio.sleep(0)
        finally:
            if not refreshing.done():
                refreshing.cancel()
                await asyncio.gather(refreshing, return_exceptions=True)
        assert refreshing.cancelled()

    asyncio.run(exercise())
    assert world.writer.role == ss.ROLE_RELEASED
    assert service.signer.calls == 1
    restored = restored_series_a_path(world)
    assert counts(restored) == {"receipts": 1, "events": 1, "snapshots": 0, "passports": 0, "passport_executions": 0}


def test_cancelled_execute_waiter_does_not_release_child_admission(fenced_world, monkeypatch):
    world = fenced_world
    service = control.Service()
    # Authorization inputs and action output are bounded synthetic fixtures.
    # The actual evaluate/execute journal and cancellation lifecycle remain real.
    monkeypatch.setattr(service, "_governance_gate", lambda action: {"allowed": True, "decision": "ALLOW", "reason_codes": ["SYNTHETIC_FIXTURE_ONLY"]})
    monkeypatch.setattr(service, "_fresh_evidence_reasons", lambda evidence: [])
    evaluated = service.evaluate_passport({"action": {"type": "probe.public_surface", "target": "https://a-11-oy.com/healthz", "impact": "MODERATE", "irreversible": False}, "evidence": []})
    digest = evaluated["passport_digest"]
    handover_started = threading.Event()
    world.writer.add_quiesce_hook(handover_started.set)

    with ThreadPoolExecutor(max_workers=1) as pool:
        async def exercise():
            probing, finish_probe = asyncio.Event(), asyncio.Event()

            async def probe(target):
                probing.set()
                await finish_probe.wait()
                return {"status": "SUCCEEDED", "target": target, "fixture": "UNSIGNED_SYNTHETIC"}

            monkeypatch.setattr(service, "_probe", probe)
            waiter = asyncio.create_task(service.execute({"passport_digest": digest}))
            child = None
            releasing = None
            try:
                await asyncio.wait_for(probing.wait(), timeout=5)
                assert len(service.execution_tasks) == 1
                child = next(iter(service.execution_tasks))
                assert child is not waiter
                assert world.writer._inflight == 1
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
                assert not child.done()
                assert world.writer._inflight == 1
                releasing = pool.submit(world.writer.close)
                assert await asyncio.to_thread(handover_started.wait, 5)
                assert world.writer.role == ss.ROLE_HANDOVER
                assert not releasing.done()
                finish_probe.set()
                result = await asyncio.wait_for(asyncio.shield(child), timeout=5)
            finally:
                finish_probe.set()
                if not waiter.done():
                    waiter.cancel()
                    await asyncio.gather(waiter, return_exceptions=True)
                if child is not None and not child.done():
                    child.cancel()
                    await asyncio.gather(child, return_exceptions=True)
            if releasing is not None:
                releasing.result(timeout=5)
            return result

        result = asyncio.run(exercise())

    assert result["outcome"]["status"] == "SUCCEEDED"
    assert world.writer.role == ss.ROLE_RELEASED
    assert world.writer._inflight == 0
    assert not service.execution_tasks
    restored = restored_series_a_path(world)
    assert counts(restored)["receipts"] == 2
    with closing(sqlite3.connect(restored)) as db:
        row = db.execute("SELECT state,outcome_receipt_hash FROM passport_executions WHERE passport_digest=?", (digest,)).fetchone()
        assert row == ("COMPLETED", result["outcome_receipt"]["receipt_hash"])


def test_serialized_nonblocking_admission_refuses_busy_without_count(fenced_world):
    world = fenced_world
    lock_held, finish = threading.Event(), threading.Event()

    def hold_storage_lock():
        with world.writer._lock:
            lock_held.set()
            assert finish.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        holder = pool.submit(hold_storage_lock)
        try:
            assert lock_held.wait(timeout=5)
            with pytest.raises(ss.StateWriteUnavailable) as refused:
                with world.writer.serialized_write_scope(blocking=False):
                    pytest.fail("busy storage lock was admitted")
            assert refused.value.code == "STATE_STORE_BUSY"
            assert world.writer._inflight == 0
        finally:
            finish.set()
        holder.result(timeout=5)
    with world.writer.serialized_write_scope(blocking=False):
        assert world.writer._inflight == 1
    assert world.writer._inflight == 0


def test_serialized_refusal_releases_lock_for_another_thread(fenced_world):
    world = fenced_world
    world.writer.close()
    with pytest.raises(ss.StateWriteUnavailable):
        with world.writer.serialized_write_scope(blocking=False):
            pytest.fail("released storage was admitted")

    def acquire_and_release():
        acquired = world.writer._lock.acquire(blocking=False)
        if acquired:
            world.writer._lock.release()
        return acquired

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(acquire_and_release).result(timeout=5)
    assert world.writer._inflight == 0


def test_serialized_waiter_has_no_admission_before_acquiring_lock(fenced_world, monkeypatch):
    world = fenced_world
    actual_lock = world.writer._lock
    attempted = threading.Event()

    class ObservedLock:
        def acquire(self, *args, **kwargs):
            attempted.set()
            return actual_lock.acquire(*args, **kwargs)

        def release(self):
            return actual_lock.release()

    monkeypatch.setattr(world.writer, "_lock", ObservedLock())

    def queued_write():
        with world.writer.serialized_write_scope():
            return world.writer._inflight

    with ThreadPoolExecutor(max_workers=1) as pool:
        with actual_lock:
            waiting = pool.submit(queued_write)
            assert attempted.wait(timeout=5)
            assert not waiting.done()
            assert world.writer._inflight == 0
        assert waiting.result(timeout=5) == 1
    assert world.writer._inflight == 0


def test_stop_joins_live_siblings_after_reconciliation_task_failed(fenced_world, monkeypatch):
    world = fenced_world
    service = control.Service()
    monkeypatch.setattr(service, "_governance_gate", lambda action: {"allowed": True, "decision": "ALLOW", "reason_codes": ["SYNTHETIC_FIXTURE_ONLY"]})
    monkeypatch.setattr(service, "_fresh_evidence_reasons", lambda evidence: [])
    evaluated = service.evaluate_passport({"action": {"type": "probe.public_surface", "target": "https://a-11-oy.com/healthz", "impact": "MODERATE", "irreversible": False}, "evidence": []})
    digest = evaluated["passport_digest"]

    async def exercise():
        collecting, probing = asyncio.Event(), asyncio.Event()
        never_complete = asyncio.Event()
        joined = []

        async def collect():
            collecting.set()
            try:
                await never_complete.wait()
                return synthetic_manifest()
            finally:
                await asyncio.sleep(0)
                joined.append("refresh")

        async def probe(target):
            probing.set()
            try:
                await never_complete.wait()
                return {"status": "SUCCEEDED", "fixture": "UNSIGNED_SYNTHETIC"}
            finally:
                await asyncio.sleep(0)
                joined.append("probe")

        async def failed_reconciliation():
            raise RuntimeError("synthetic reconciliation failure")

        monkeypatch.setattr(service.collector, "collect", collect)
        monkeypatch.setattr(service, "_probe", probe)
        reconciliation = asyncio.create_task(failed_reconciliation())
        background = asyncio.create_task(service._refresh_loop())
        waiter = asyncio.create_task(service.execute({"passport_digest": digest}))
        service.reconciliation_task = reconciliation
        service.background_task = background
        service.started = True
        execution = None
        try:
            await asyncio.wait_for(collecting.wait(), timeout=5)
            await asyncio.wait_for(probing.wait(), timeout=5)
            assert reconciliation.done()
            assert isinstance(reconciliation.exception(), RuntimeError)
            assert len(service.execution_tasks) == 1
            execution = next(iter(service.execution_tasks))
            assert world.writer._inflight == 2
            signed = service.signer.calls
            before = counts(service.store.path)

            with pytest.raises(RuntimeError, match="synthetic reconciliation failure"):
                await service.stop()

            assert background.cancelled()
            assert execution.cancelled()
            assert set(joined) == {"refresh", "probe"}
            assert service.background_task is None
            assert service.reconciliation_task is None
            assert not service.execution_tasks
            assert not service.started
            assert world.writer._inflight == 0
            assert service.signer.calls == signed
            assert counts(service.store.path) == before
            with pytest.raises(asyncio.CancelledError):
                await waiter
            # Failure was surfaced after cleanup, and cleanup remains idempotent.
            await service.stop()
        finally:
            captured = {reconciliation, background, waiter, *service.execution_tasks}
            if execution is not None:
                captured.add(execution)
            for task in captured:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*captured, return_exceptions=True)

    asyncio.run(exercise())
    assert service.store.execution_status(digest)["state"] == "PENDING"
    world.writer.close()
    assert world.writer.role == ss.ROLE_RELEASED
    assert world.writer._inflight == 0
