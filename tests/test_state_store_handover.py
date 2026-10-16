#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Single-writer lease between two simulated replicas on a fake CAS dataset.

No network: the dataset is FakeHeadBackend (parent_commit CAS, HTTP-412 style
ParentConflict) and the bucket is a local directory. A fake clock drives the
heartbeat, the handover wait and lease staleness deterministically.
"""

import copy
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_state_store as ss
from routers.series_a_control_plane import Store
from tests.state_store_support import FakeClock, FakeHeadBackend, count, make_db, replica
# The hosted GDW job enumerates this suite; collect its lifecycle companion too.
from tests.state_store_error_lifecycle import TestStateStoreErrorLifecycle


@pytest.fixture(autouse=True)
def no_active_store(monkeypatch):
    monkeypatch.setattr(ss, "_ACTIVE", None)
    yield
    monkeypatch.setattr(ss, "_ACTIVE", None)


@pytest.fixture
def world(tmp_path):
    return {
        "objects": ss.LocalDirObjectStore(tmp_path / "bucket"),
        "backend": FakeHeadBackend(),
        "clock": FakeClock(),
        "tmp": tmp_path,
    }


def boot_writer(world, name="a"):
    store = replica(world["tmp"], name, world["objects"], world["backend"], world["clock"])
    store.boot()
    return store


def test_first_boot_bootstraps_head_epoch_one(world):
    a = boot_writer(world)
    head = world["backend"].head()
    assert a.role == ss.ROLE_WRITER and a.writable()
    assert head["epoch"] == 1 and head["state"] == ss.STATE_ACTIVE
    assert head["transition"] == "BOOTSTRAP" and head["writer_id"] == a.writer_id
    assert head["claim"]["kind"] == ss.CLAIM_FIRST_BOOT
    assert head["snapshots"] == {}


def test_clean_handover_moves_every_acknowledged_write(world):
    a = boot_writer(world)
    gdw = a.local_path("gdw")
    make_db(gdw, 10)
    a.snapshot_once(force=True)
    make_db(gdw, 5, start=10)  # acknowledged after A's last periodic snapshot
    a.heartbeat_once()

    b = replica(world["tmp"], "b", world["objects"], world["backend"], world["clock"])
    world["clock"].on_sleep.append(a.heartbeat_once)  # A keeps beating while B waits
    b.boot()

    head = world["backend"].head()
    assert head["epoch"] == 2 and head["writer_id"] == b.writer_id
    assert head["claim"]["kind"] == ss.CLAIM_CLEAN
    assert head["state"] == ss.STATE_ACTIVE
    assert a.role == ss.ROLE_RELEASED and not a.writable()
    assert b.role == ss.ROLE_WRITER and b.writable()
    assert count(b.local_path("gdw")) == 15, "the final snapshot must carry the late write"
    transitions = [ss.parse_head(body)["transition"]
                   for _, body in world["backend"].commits if body is not None]
    assert transitions == ["BOOTSTRAP", "SNAPSHOT", "HANDOVER_REQUEST", "RELEASE", "CLAIM"]


def test_stale_lease_is_taken_over_unclean_and_old_writer_is_fenced(world):
    a = boot_writer(world)
    make_db(a.local_path("gdw"), 7)
    a.snapshot_once(force=True)
    a.heartbeat_once()
    make_db(a.local_path("gdw"), 3, start=7)  # never snapshotted: A "crashes"
    world["clock"].advance(200)  # heartbeat now older than the 120 s lease

    b = replica(world["tmp"], "b", world["objects"], world["backend"], world["clock"])
    started = world["clock"].now
    b.boot()

    head = world["backend"].head()
    assert world["clock"].now == started, "a stale lease must not wait for a handover"
    assert head["claim"]["kind"] == ss.CLAIM_UNCLEAN and head["epoch"] == 2
    assert count(b.local_path("gdw")) == 7, "RPO: only snapshotted writes survive a crash"
    a.heartbeat_once()
    assert a.role == ss.ROLE_FENCED and not a.writable()
    assert a.snapshot_once(force=True) == {}
    assert world["backend"].head()["writer_id"] == b.writer_id


@pytest.mark.parametrize("failure", ["upload", "signature", "missing_file"])
def test_failed_final_capture_never_claims_clean_handover(world, monkeypatch, failure):
    a = boot_writer(world)
    make_db(a.local_path("gdw"), 10)
    a.snapshot_once(force=True)
    make_db(a.local_path("gdw"), 5, start=10)
    # Another store can upload successfully while GDW fails. Its immutable
    # object must remain pending, rather than being forgotten at release.
    make_db(a.local_path("series_a"), 2)
    a.heartbeat_once()
    if failure == "upload":
        original = world["objects"].put_file

        def put_file(local, remote):
            if "/gdw/" in remote:
                raise ss.StorageBlocked("OBJECT_UNAVAILABLE")
            original(local, remote)

        monkeypatch.setattr(world["objects"], "put_file", put_file)
    elif failure == "signature":
        original = a._signature

        def signature(spec):
            if spec.label == "gdw":
                raise OSError("offline synthetic signature failure")
            return original(spec)

        monkeypatch.setattr(a, "_signature", signature)
    else:
        a._close_watchers()
        a.local_path("gdw").unlink()

    b = replica(world["tmp"], "b", world["objects"], world["backend"], world["clock"])
    world["clock"].on_sleep.append(a.heartbeat_once)
    b.boot()

    transitions = [ss.parse_head(body)["transition"]
                   for _, body in world["backend"].commits if body is not None]
    assert "RELEASE" not in transitions
    assert a.role == ss.ROLE_FENCED and not a.writable()
    assert a.last_error["code"] == "STATE_FINAL_SNAPSHOT_INCOMPLETE"
    assert "series_a" in a._unpublished
    assert b.claim_kind == ss.CLAIM_UNCLEAN
    assert count(b.local_path("gdw")) == 10


@pytest.mark.parametrize("failure", ["inflight", "quiesce_hook"])
def test_unquiesced_writer_never_releases_cleanly(world, failure):
    a = boot_writer(world)
    make_db(a.local_path("gdw"), 10)
    a.snapshot_once(force=True)
    if failure == "inflight":
        a.begin_write()
        a.settings = replace(a.settings, drain_s=0)
    else:
        def fail_hook():
            raise RuntimeError("offline synthetic quiesce failure")

        a.add_quiesce_hook(fail_hook)
    a._release(a.head)
    assert a.role == ss.ROLE_FENCED and not a.writable()
    assert not a.begin_write()
    assert a.last_error["code"] == "STATE_WRITERS_NOT_QUIESCED"
    assert world["backend"].head()["state"] == ss.STATE_ACTIVE
    assert world["backend"].head()["transition"] == "SNAPSHOT"
    if failure == "inflight":
        a.end_write()


def test_unresponsive_live_writer_is_taken_over_after_the_wait(world):
    a = boot_writer(world)
    a.heartbeat_once()
    b = replica(world["tmp"], "b", world["objects"], world["backend"], world["clock"],
                stale_s=30.0)
    # A's heartbeat object stays fresh only at boot; A never answers the request.
    started = world["clock"].now
    b.boot()
    assert world["clock"].now - started >= 30.0
    head = world["backend"].head()
    assert head["claim"]["kind"] == ss.CLAIM_UNCLEAN
    a.heartbeat_once()
    assert a.role == ss.ROLE_FENCED


def test_fenced_writer_refuses_writes_with_503_and_retry_after(world, monkeypatch):
    a = boot_writer(world)
    a.heartbeat_once()
    world["clock"].advance(200)
    b = replica(world["tmp"], "b", world["objects"], world["backend"], world["clock"])
    b.boot()
    a.heartbeat_once()
    assert a.role == ss.ROLE_FENCED

    app = FastAPI()

    @app.post("/api/a11oy/v1/gdw/step")
    def step():
        return {"ok": True}

    ss.register(app)
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    client = TestClient(app)

    monkeypatch.setattr(ss, "_ACTIVE", a)
    refused = client.post("/api/a11oy/v1/gdw/step", json={})
    assert refused.status_code == 503
    assert refused.headers["Retry-After"] == str(ss.RETRY_AFTER_SECONDS)
    assert refused.json()["error"]["code"] == "STATE_STORE_FENCED"
    status = client.get("/api/a11oy/v1/storage/status")
    assert status.status_code == 200 and status.json()["role"] == ss.ROLE_FENCED

    monkeypatch.setattr(ss, "_ACTIVE", b)
    assert client.post("/api/a11oy/v1/gdw/step", json={}).status_code == 200


def test_released_and_unactivated_processes_are_read_only(world, monkeypatch):
    a = boot_writer(world)
    a.close()
    assert a.role == ss.ROLE_RELEASED
    assert world["backend"].head()["state"] == ss.STATE_RELEASED

    app = FastAPI()

    @app.post("/write")
    def write():
        return {"ok": True}

    ss.register(app)
    client = TestClient(app)
    monkeypatch.setattr(ss, "_ACTIVE", a)
    monkeypatch.delenv(ss.ENABLE_ENV, raising=False)
    assert client.post("/write").status_code == 200, "disabled store must be inert"
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    assert client.post("/write").status_code == 503
    monkeypatch.setattr(ss, "_ACTIVE", None)
    response = client.post("/write")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STATE_STORE_NOT_ACTIVATED"


def test_released_head_is_claimed_cleanly_without_waiting(world):
    a = boot_writer(world)
    make_db(a.local_path("series_a"), 4)
    a.close()
    b = replica(world["tmp"], "b", world["objects"], world["backend"], world["clock"])
    started = world["clock"].now
    b.boot()
    assert world["clock"].now == started
    assert world["backend"].head()["claim"]["kind"] == ss.CLAIM_CLEAN
    assert count(b.local_path("series_a")) == 4


def test_cas_retries_unrelated_parent_moves_and_resolves_uncertain_outcomes(world):
    a = boot_writer(world)
    backend = world["backend"]
    make_db(a.local_path("gdw"), 2)
    backend.before_submit = backend.unrelated_commit  # 412-style parent conflict once
    a.snapshot_once(force=True)
    assert backend.head()["transition"] == "SNAPSHOT"

    make_db(a.local_path("gdw"), 1, start=2)
    backend.fail_next_submit = "uncertain_landed"
    a.snapshot_once(force=True)
    assert backend.head()["sequence"] == 3 and a.head.body == backend.commits[-1][1]

    make_db(a.local_path("gdw"), 1, start=3)
    backend.fail_next_submit = "uncertain_lost"
    a.snapshot_once(force=True)
    assert backend.head()["sequence"] == 4
    assert a.role == ss.ROLE_WRITER


def test_transitions_that_break_the_lease_rules_are_rejected(world):
    a = boot_writer(world)
    current = world["backend"].head()
    body = world["backend"].commits[-1][1]
    stolen = a._next(current, body, transition="SNAPSHOT", state=ss.STATE_ACTIVE,
                     writer_id="f" * 32)
    with pytest.raises(ss.StorageBlocked, match="STATE_TRANSITION_INVALID"):
        ss.cas_advance(world["backend"], a.head, stolen)
    skipped = a._next(current, body, transition="CLAIM", state=ss.STATE_ACTIVE,
                      epoch=current["epoch"] + 2, writer_id="e" * 32)
    with pytest.raises(ss.StorageBlocked, match="STATE_TRANSITION_INVALID"):
        ss.cas_advance(world["backend"], a.head, skipped)


def test_concurrent_writer_change_raises_head_changed(world):
    a = boot_writer(world)
    observed = a.head
    world["backend"].unrelated_commit()
    a.close()  # RELEASE moves HEAD
    proposal = a._next(ss.parse_head(observed.body), observed.body, transition="SNAPSHOT",
                       state=ss.STATE_ACTIVE)
    with pytest.raises(ss.HeadChanged):
        ss.cas_advance(world["backend"], observed, proposal)


def test_heartbeat_object_names_the_lease_holder(world):
    a = boot_writer(world)
    a.heartbeat_once()
    beat = json.loads(world["objects"].get_bytes(ss.HEARTBEAT_PATH))
    assert beat["epoch"] == 1 and beat["writer_id"] == a.writer_id
    assert beat["schema"] == ss.HEARTBEAT_SCHEMA


# Explicit observation acknowledgements use real disposable SQLite snapshots.
@pytest.fixture
def observation_world(tmp_path, monkeypatch):
    clock, backend = FakeClock(), FakeHeadBackend()
    objects = ss.LocalDirObjectStore(tmp_path / "objects")
    writer = replica(tmp_path, "a", objects, backend, clock)
    writer.boot()
    writer.heartbeat_once()
    monkeypatch.setattr(ss, "_ACTIVE", writer)
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")
    owner = Store()
    yield writer, owner, backend, objects, clock, tmp_path
    writer._close_watchers()


def reserve_observation(writer, owner, **overrides):
    values = dict(source_revision=writer.source_revision, runtime_boot_id=writer.boot_id,
                  run_nonce="c" * 64, plan_sha256="d" * 64, case_id="policy-decide",
                  request_sha256="e" * 64, receipt_id="observation-fixture-1",
                  started_at="2026-10-15T03:00:00Z")
    values.update(overrides)
    return owner.reserve_execution_observation(**values)


def acknowledge_observation(writer, owner, row):
    return writer.snapshot_confirmed("series_a",
        lambda path: owner.execution_observation_matches(path, row))


def legacy_observation_rows(owner):
    with sqlite3.connect(owner.path) as db:
        return {table: db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
                for table in ("snapshots", "passports", "passport_executions",
                              "receipts", "events", "metadata")}


def test_owner_reservation_and_completed_object_survive_clean_restore(observation_world):
    writer, owner, backend, objects, clock, root = observation_world
    stamp = "2026-10-15T03:00:00Z"
    owner.save_snapshot({"observed_at": stamp, "valid_until": stamp},
                        {"fixture": "UNSIGNED_SYNTHETIC"})
    passport = owner.save_passport({"decision": "DENY", "created_at": stamp})
    owner.begin_execution(passport, writer.boot_id, stamp)

    class UnsignedFixtureSigner:
        def sign(self, payload):
            return {"payload": payload, "signature_status": "UNSIGNED_SYNTHETIC"}

    owner.append_receipt("SYNTHETIC", {"fixture": "NOT_EXECUTED"}, UnsignedFixtureSigner())
    before = legacy_observation_rows(owner)
    assert all(before.values())
    row = reserve_observation(writer, owner)
    reserved = acknowledge_observation(writer, owner, row)
    assert reserved["entry"] == backend.head()["snapshots"]["series_a"]
    observation = {"receipt": {"fixture": "NOT_A_LIVE_RECEIPT"},
                   "response_b64": "e30=", "readback_b64": "e30="}
    completed = owner.complete_execution_observation(row["receipt_id"], observation)
    proof = acknowledge_observation(writer, owner, completed)
    assert proof["entry"]["sha256"] != reserved["entry"]["sha256"]
    assert proof["head_sha256"] == hashlib.sha256(backend.observe().body).hexdigest()
    assert legacy_observation_rows(owner) == before
    clock.on_sleep.append(writer.heartbeat_once)
    successor = replica(root, "b", objects, backend, clock)
    try:
        successor.boot()
        assert successor.claim_kind == ss.CLAIM_CLEAN
        assert successor.boot_id != writer.boot_id
        assert Store.execution_observation_matches(successor.local_path("series_a"), completed)
    finally:
        successor._close_watchers()


def test_duplicate_attempt_and_nonce_rebinding_are_consumed(observation_world):
    writer, owner, *_ = observation_world
    reserve_observation(writer, owner)
    with pytest.raises(ValueError, match="ATTEMPT_ALREADY_CONSUMED"):
        reserve_observation(writer, owner)
    for changes in ({"plan_sha256": "f" * 64}, {"source_revision": "f" * 40},
                    {"runtime_boot_id": "f" * 32}):
        with pytest.raises(ValueError, match="NONCE_ALREADY_BOUND"):
            reserve_observation(writer, owner, **changes)
    assert reserve_observation(writer, owner, case_id="policy-compliance",
                   receipt_id="observation-fixture-2")["state"] == "RESERVED"


def test_concurrent_duplicate_has_one_winner(observation_world):
    writer, owner, *_ = observation_world

    def attempt(_):
        try:
            return reserve_observation(writer, owner)["state"]
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert outcomes.count("RESERVED") == 1
    assert outcomes.count("OBSERVATION_ATTEMPT_ALREADY_CONSUMED") == 7


def test_completion_requires_reservation_and_cannot_be_replaced(observation_world):
    writer, owner, *_ = observation_world
    row = reserve_observation(writer, owner)
    expected = owner.complete_execution_observation(row["receipt_id"], {"fixture": "first"})
    for receipt_id in (row["receipt_id"], "missing"):
        with pytest.raises(ValueError, match="RESERVATION_REQUIRED"):
            owner.complete_execution_observation(receipt_id, {"fixture": "replacement"})
    assert owner.read_execution_observation(row["receipt_id"]) == expected


def test_read_does_not_initialize_tables_or_change_database(observation_world):
    _, owner, *_ = observation_world
    path = Path(owner.path)
    before = path.read_bytes()
    assert owner.read_execution_observation("missing") is None
    assert path.read_bytes() == before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'execution_observ%'").fetchall() == []


@pytest.mark.parametrize("mode,role", [(ss.MODE_UNFENCED, ss.ROLE_UNFENCED_WRITER),
                                      (ss.MODE_FENCED, ss.ROLE_FENCED),
                                      (ss.MODE_FENCED, ss.ROLE_HANDOVER)])
def test_nonfenced_or_nonwriter_never_uploads(observation_world, monkeypatch, mode, role):
    writer, owner, _, objects, *_ = observation_world
    row = reserve_observation(writer, owner)
    writer.mode, writer.role = mode, role
    monkeypatch.setattr(objects, "put_file", lambda *_: pytest.fail("uploaded without writer"))
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_WRITER_REQUIRED"):
        acknowledge_observation(writer, owner, row)


def test_stale_lease_rejects_before_snapshot(observation_world):
    writer, owner, _, _, clock, _ = observation_world
    row = reserve_observation(writer, owner)
    clock.advance(writer.settings.stale_s + 1)
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_LEASE_REQUIRED"):
        acknowledge_observation(writer, owner, row)


def test_wrong_snapshot_contents_are_not_acknowledged(observation_world):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)
    wrong = dict(row, request_sha256="f" * 64)
    head_before = backend.observe()
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_CONTENT_MISMATCH"):
        acknowledge_observation(writer, owner, wrong)
    assert backend.observe() == head_before


def test_uncertain_cas_never_acknowledges_or_discards_unrelated_pending(observation_world, monkeypatch):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)
    unrelated = {"fixture": "unrelated pending bytes"}
    writer._unpublished["gdw"] = copy.deepcopy(unrelated)
    head_before = backend.observe()

    def uncertain(*_):
        raise ss.StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")

    monkeypatch.setattr(backend, "submit", uncertain)
    with pytest.raises(ss.StorageBlocked):
        acknowledge_observation(writer, owner, row)
    assert backend.observe() == head_before
    assert writer._unpublished["gdw"] == unrelated
    assert owner.read_execution_observation(row["receipt_id"])["state"] == "RESERVED"


def test_reused_unpublished_object_is_checked_and_acknowledged(observation_world):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)
    backend.unreachable = True
    writer.snapshot_once(force=True)
    backend.unreachable = False
    pending = dict(writer._unpublished["series_a"])
    writer._unpublished["gdw"] = {"fixture": "preserve unrelated"}
    proof = acknowledge_observation(writer, owner, row)
    assert proof["entry"] == pending
    assert "series_a" not in writer._unpublished
    assert writer._unpublished["gdw"] == {"fixture": "preserve unrelated"}


def test_repeated_confirmation_preserves_distinct_restore_history(observation_world, monkeypatch):
    writer, owner, backend, objects, *_ = observation_world
    row = reserve_observation(writer, owner)
    for generation in range(ss.HISTORY_DEPTH + 2):
        owner.append_event("SYNTHETIC", {"generation": generation})
        acknowledge_observation(writer, owner, row)
    expected_head = backend.head()
    history = expected_head["history"]["series_a"]
    assert len(history) == ss.HISTORY_DEPTH
    assert len({entry["sha256"] for entry in history}) == ss.HISTORY_DEPTH
    expected = backend.observe()
    submissions = backend.submits
    writer._unpublished["series_a"] = dict(expected_head["snapshots"]["series_a"])
    writer._unpublished["gdw"] = {"fixture": "preserve unrelated"}
    monkeypatch.setattr(objects, "put_file", lambda *_: pytest.fail("unchanged upload"))
    downloads = []
    download = writer._download

    def observed_download(remote, path):
        downloads.append(remote)
        download(remote, path)

    monkeypatch.setattr(writer, "_download", observed_download)
    for _ in range(ss.HISTORY_DEPTH + 3):
        proof = acknowledge_observation(writer, owner, row)
        assert proof["entry"] == expected_head["snapshots"]["series_a"]
        assert proof["head_sha256"] == hashlib.sha256(expected.body).hexdigest()
        assert backend.observe() == expected
        assert backend.head() == expected_head
        assert backend.submits == submissions
    assert downloads == [proof["entry"]["path"]] * (ss.HISTORY_DEPTH + 3)
    assert "series_a" not in writer._unpublished
    assert writer._unpublished["gdw"] == {"fixture": "preserve unrelated"}


def test_different_pending_confirmation_advances_published_head(observation_world):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)
    first = acknowledge_observation(writer, owner, row)
    completed = owner.complete_execution_observation(row["receipt_id"],
                                                    {"fixture": "NOT_A_LIVE_RECEIPT"})
    backend.unreachable = True
    writer.snapshot_once(force=True)
    backend.unreachable = False
    pending = dict(writer._unpublished["series_a"])
    assert pending != first["entry"]
    before = backend.observe()
    submissions = backend.submits
    proof = acknowledge_observation(writer, owner, completed)
    assert proof["entry"] == pending
    assert backend.observe() != before
    assert backend.submits == submissions + 1
    assert backend.head()["history"]["series_a"] == [first["entry"]]
    assert "series_a" not in writer._unpublished


def test_pending_handover_does_not_drain_the_current_request(observation_world, monkeypatch):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)
    before = backend.head()
    requested = writer._next(before, backend.observe().body, transition="HANDOVER_REQUEST",
                             state=ss.STATE_HANDOVER,
                             handover={"requested_by": "f" * 32,
                                       "requested_at": "2026-10-15T03:00:00Z"})
    backend._append(ss.canonical(requested))
    monkeypatch.setattr(writer, "_release", lambda *_: pytest.fail("synchronous self-drain"))
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_HEAD_CHANGED"):
        acknowledge_observation(writer, owner, row)
    assert writer.role == ss.ROLE_WRITER


@pytest.mark.parametrize("mutation", ["absent", "empty", "wrong_epoch", "wrong_writer",
                                     "wrong_boot", "wrong_schema", "boolean_epoch",
                                     "boolean_time", "future", "nan", "malformed"])
def test_confirmed_writer_requires_its_own_valid_fresh_heartbeat(
        observation_world, monkeypatch, mutation):
    writer, owner, _, objects, clock, _ = observation_world
    row = reserve_observation(writer, owner)
    beat = json.loads(objects.get_bytes(ss.HEARTBEAT_PATH))
    if mutation == "empty":
        beat = {}
    elif mutation == "wrong_epoch":
        beat["epoch"] += 1
    elif mutation == "wrong_writer":
        beat["writer_id"] = "f" * 32
    elif mutation == "wrong_boot":
        beat["boot_id"] = "f" * 32
    elif mutation == "wrong_schema":
        beat["schema"] = "unknown"
    elif mutation == "boolean_epoch":
        beat["epoch"] = True
    elif mutation == "boolean_time":
        beat["at_unix"] = True
    elif mutation == "future":
        beat["at_unix"] = clock.time() + 1
    elif mutation == "nan":
        beat["at_unix"] = float("nan")
    raw = (None if mutation == "absent" else b"{" if mutation == "malformed"
           else json.dumps(beat).encode())
    monkeypatch.setattr(objects, "get_bytes", lambda _: raw)
    monkeypatch.setattr(objects, "put_file", lambda *_: pytest.fail("unadmitted upload"))
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_LEASE_REQUIRED"):
        acknowledge_observation(writer, owner, row)


def test_expiry_during_capture_never_advances_head(observation_world, monkeypatch):
    writer, owner, backend, _, clock, _ = observation_world
    row = reserve_observation(writer, owner)
    before = backend.observe()
    capture = writer._capture

    def slow_capture(*args):
        entry = capture(*args)
        clock.advance(writer.settings.stale_s + 1)
        return entry

    monkeypatch.setattr(writer, "_capture", slow_capture)
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_LEASE_REQUIRED"):
        acknowledge_observation(writer, owner, row)
    assert backend.observe() == before


@pytest.mark.parametrize("failure", ["upload", "readback", "tamper"])
def test_object_failure_never_acknowledges(observation_world, monkeypatch, failure):
    writer, owner, backend, objects, *_ = observation_world
    row = reserve_observation(writer, owner)
    before = backend.observe()

    def unavailable(*_):
        raise ss.StorageBlocked("OBJECT_UNAVAILABLE")

    if failure == "upload":
        monkeypatch.setattr(objects, "put_file", unavailable)
    elif failure == "readback":
        monkeypatch.setattr(objects, "get_file", unavailable)
    else:
        download = writer._download

        def tampered(remote, path):
            download(remote, path)
            with path.open("ab") as output:
                output.write(b"tampered")

        monkeypatch.setattr(writer, "_download", tampered)
    with pytest.raises(ss.StorageBlocked):
        acknowledge_observation(writer, owner, row)
    assert backend.observe() == before
    assert owner.read_execution_observation(row["receipt_id"])["state"] == "RESERVED"


def test_uncertain_cas_that_landed_requires_exact_remote_readback(observation_world):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)
    backend.fail_next_submit = "uncertain_landed"
    proof = acknowledge_observation(writer, owner, row)
    assert proof["entry"] == backend.head()["snapshots"]["series_a"]
    assert proof["head_sha256"] == hashlib.sha256(backend.observe().body).hexdigest()


@pytest.mark.parametrize("point", ["submit", "after_submit"])
def test_handover_at_publication_never_acknowledges_or_self_drains(
        observation_world, monkeypatch, point):
    writer, owner, backend, *_ = observation_world
    row = reserve_observation(writer, owner)

    def handover():
        current = backend.head()
        requested = writer._next(current, backend.observe().body,
                                 transition="HANDOVER_REQUEST", state=ss.STATE_HANDOVER,
                                 handover={"requested_by": "f" * 32,
                                           "requested_at": "2026-10-15T03:00:00Z"})
        backend._append(ss.canonical(requested))

    monkeypatch.setattr(writer, "_release", lambda *_: pytest.fail("self-drain"))
    if point == "submit":
        backend.before_submit = handover
    else:
        read_at = backend.read_at

        def read_then_handover(revision):
            result = read_at(revision)
            handover()
            return result

        monkeypatch.setattr(backend, "read_at", read_then_handover)
    with pytest.raises(ss.StorageBlocked, match="CONFIRMED_HEAD_CHANGED"):
        acknowledge_observation(writer, owner, row)
    assert writer.role == ss.ROLE_WRITER


def test_separate_owner_connections_still_consume_attempt_once(observation_world):
    writer, owner, *_ = observation_world
    other = Store(requested_path=owner.path)

    def attempt(index):
        try:
            return reserve_observation(writer, owner if index % 2 else other)["state"]
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert outcomes.count("RESERVED") == 1
    assert outcomes.count("OBSERVATION_ATTEMPT_ALREADY_CONSUMED") == 7


def test_read_only_accessor_retains_committed_wal_data(observation_world, monkeypatch):
    writer, owner, *_ = observation_world
    monkeypatch.setenv("A11OY_SERIES_A_SQLITE_JOURNAL", "WAL")
    wal_owner = Store(requested_path=owner.path)
    connection = wal_owner.connect()
    try:
        row = reserve_observation(writer, wal_owner)
        before = legacy_observation_rows(wal_owner)
        assert wal_owner.read_execution_observation(row["receipt_id"]) == row
        assert legacy_observation_rows(wal_owner) == before
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        connection.close()


# Exact local SNAPSHOT intent after ambiguous CAS/readback failure.
@pytest.fixture
def readback_world(tmp_path):
    clock, backend = FakeClock(), FakeHeadBackend()
    objects = ss.LocalDirObjectStore(tmp_path / "objects")
    writer = replica(tmp_path, "writer", objects, backend, clock)
    writer.boot()
    writer.heartbeat_once()
    make_db(writer.local_path("series_a"), 2)
    yield writer, backend, clock
    writer._close_watchers()


@pytest.mark.parametrize("point", ["successful_submit_readback", "uncertain_submit_resolution"])
def test_own_landed_snapshot_readback_failure_does_not_fence_writer(readback_world, monkeypatch, point):
    writer, backend, clock = readback_world
    original_body = writer.head.body
    if point == "successful_submit_readback":
        read_at = backend.read_at
        fail = [True]
        def fail_first_readback(revision):
            if fail[0]:
                fail[0] = False
                raise ss.StorageBlocked("STATE_HEAD_UNREADABLE")
            return read_at(revision)
        monkeypatch.setattr(backend, "read_at", fail_first_readback)
    else:
        submit, observe = backend.submit, backend.observe
        fail = [False]
        def landed_submit(*args):
            submit(*args)
            fail[0] = True
            raise ss.StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")
        def fail_resolution():
            if fail[0]:
                fail[0] = False
                raise ss.StorageBlocked("STATE_HEAD_UNREADABLE")
            return observe()
        monkeypatch.setattr(backend, "submit", landed_submit)
        monkeypatch.setattr(backend, "observe", fail_resolution)
    writer.snapshot_once(force=True)
    observed = backend.observe()
    latest = ss.parse_head(observed.body)
    before = ss.parse_head(original_body)
    assert latest["writer_id"] == writer.writer_id and latest["epoch"] == writer.epoch
    assert latest["boot_id"] == writer.boot_id and latest["state"] == ss.STATE_ACTIVE
    assert latest["sequence"] == before["sequence"] + 1
    assert writer.head.body == original_body and observed.body != original_body
    assert writer._active_errors["publish"]["code"] == "STATE_HEAD_UNREADABLE"
    assert writer.role == ss.ROLE_WRITER
    clock.advance(3)
    writer.heartbeat_once()
    assert writer.role == ss.ROLE_WRITER, {
        "failure": "Own successful immutable HEAD commit mistaken for another writer",
        "active_errors": writer._active_errors,
        "before_sequence": before["sequence"], "remote_sequence": latest["sequence"],
        "same_writer": True, "same_epoch": True, "same_boot": True,
    }
    assert writer.head.body == observed.body


def test_unrecognized_same_writer_active_manifest_still_fences(readback_world):
    writer, backend, _ = readback_world
    current = backend.head()
    foreign = writer._next(current, writer.head.body, transition="SNAPSHOT", state=ss.STATE_ACTIVE)
    # Same identity is not enough: this operation was never submitted by writer.
    backend._append(ss.canonical(foreign))
    writer.heartbeat_once()
    assert writer.role == ss.ROLE_FENCED
    assert writer._active_errors["lease"]["code"] == "WRITER_FENCED"


def _lose_snapshot_readback(writer, backend, monkeypatch, *, mismatch=False):
    read_at = backend.read_at
    remaining = [True]
    def read(revision):
        if remaining[0]:
            remaining[0] = False
            if mismatch:
                return b'known incorrect immutable revision bytes'
            raise ss.StorageBlocked('STATE_HEAD_UNREADABLE')
        return read_at(revision)
    monkeypatch.setattr(backend, 'read_at', read)
    writer.snapshot_once(force=True)
    return backend.observe()


def test_retry_before_heartbeat_resolves_exact_landed_body_without_resubmit(readback_world, monkeypatch):
    writer, backend, _ = readback_world
    landed = _lose_snapshot_readback(writer, backend, monkeypatch)
    submits = backend.submits
    writer.snapshot_once(force=True)
    assert writer.role == ss.ROLE_WRITER and writer.head == landed
    assert backend.submits == submits
    assert writer._pending_snapshot is None and writer._unpublished == {}
    assert 'publish' not in writer._active_errors


def test_repeated_lost_submit_reuses_original_operation_and_then_captures_new_rows(readback_world, monkeypatch, tmp_path):
    writer, backend, _ = readback_world
    submit = backend.submit
    old = writer.head
    calls, lost = [], [True]
    def fail_then_submit(parent, body, operation_id):
        calls.append((body, operation_id))
        if lost[0]:
            raise ss.StorageBlocked('STATE_HEAD_OUTCOME_UNCERTAIN')
        return submit(parent, body, operation_id)
    monkeypatch.setattr(backend, 'submit', fail_then_submit)
    writer.snapshot_once(force=True)
    assert writer.head == old and writer._pending_snapshot['submitted'] is True
    first = calls[0]
    make_db(writer.local_path('series_a'), 3, start=2)
    writer.snapshot_once(force=True)
    assert calls and all(value == first for value in calls)
    assert writer._pending_snapshot['body'] == first[0]
    lost[0] = False
    writer.snapshot_once(force=True)
    assert calls[-2] == first and calls[-1] != first
    head = backend.head()
    old_entry = ss.parse_head(first[0])['snapshots']['series_a']
    assert old_entry in head['history']['series_a']
    downloaded = tmp_path / 'latest.sqlite'
    writer.objects.get_file(head['snapshots']['series_a']['path'], downloaded)
    assert count(downloaded) == 5
    assert writer._pending_snapshot is None and writer._unpublished == {}


def test_known_immutable_mismatch_does_not_authorize_later_adoption(readback_world, monkeypatch):
    writer, backend, _ = readback_world
    landed = _lose_snapshot_readback(writer, backend, monkeypatch, mismatch=True)
    assert writer._active_errors['publish']['code'] == 'STATE_HEAD_READBACK_MISMATCH'
    assert writer._pending_snapshot is None
    assert landed.body != writer.head.body
    writer.heartbeat_once()
    assert writer.role == ss.ROLE_FENCED and writer.head.body != landed.body


@pytest.mark.parametrize('terminal_code', ['STATE_HEAD_READBACK_MISMATCH', 'STATE_TRANSITION_INVALID',
                                          'STATE_HEAD_SCHEMA_INVALID'])
def test_known_verification_failure_discards_original_intent(readback_world, monkeypatch, terminal_code):
    writer, backend, _ = readback_world
    read_at = backend.read_at
    def reject(_):
        raise ss.StorageBlocked(terminal_code)
    monkeypatch.setattr(backend, 'read_at', reject)
    writer.snapshot_once(force=True)
    assert writer._pending_snapshot is None
    monkeypatch.setattr(backend, 'read_at', read_at)
    writer.heartbeat_once()
    assert writer.role == ss.ROLE_FENCED


def test_never_submitted_proposal_does_not_authorize_adoption(readback_world, monkeypatch):
    writer, backend, _ = readback_world
    backend.unreachable = True
    writer.snapshot_once(force=True)
    assert writer._pending_snapshot['submitted'] is False
    candidate = writer._pending_snapshot['body']
    backend.unreachable = False
    backend._append(candidate)
    writer.heartbeat_once()
    assert writer.role == ss.ROLE_FENCED


def test_terminal_fence_cannot_recover_even_exact_old_pending_head(readback_world, monkeypatch):
    writer, backend, _ = readback_world
    landed = _lose_snapshot_readback(writer, backend, monkeypatch)
    pending = copy.deepcopy(writer._pending_snapshot)
    writer._fence('INDEPENDENT_TERMINAL_FAILURE')
    assert writer._pending_snapshot is None
    writer._pending_snapshot = pending  # Even corrupted retained state cannot revive role.
    assert writer._accept_pending_snapshot(landed) is False
    submits = backend.submits
    writer.heartbeat_once()
    assert writer.snapshot_once(force=True) == {}
    assert writer.role == ss.ROLE_FENCED and backend.submits == submits


def test_confirmed_writer_stays_read_only_until_mutating_snapshot_recovers(readback_world, monkeypatch):
    writer, backend, _ = readback_world
    landed = _lose_snapshot_readback(writer, backend, monkeypatch)
    submits = backend.submits
    with pytest.raises(ss.StorageBlocked, match='STATE_CONFIRMED_HEAD_CHANGED'):
        writer.confirmed_writer()
    assert writer.head != landed and backend.submits == submits
    proof = writer.snapshot_confirmed('series_a', lambda path: count(path) == 2)
    assert writer.head == landed and backend.submits == submits
    assert proof['entry'] == backend.head()['snapshots']['series_a']


def test_mutating_recovery_still_checks_snapshot_content_and_fresh_lease(readback_world, monkeypatch):
    writer, backend, clock = readback_world
    _lose_snapshot_readback(writer, backend, monkeypatch)
    clock.advance(writer.settings.stale_s + 1)
    submits = backend.submits
    with pytest.raises(ss.StorageBlocked, match='STATE_CONFIRMED_LEASE_REQUIRED'):
        writer.snapshot_confirmed('series_a', lambda path: count(path) == 2)
    assert backend.submits == submits
    writer.heartbeat_once()
    with pytest.raises(ss.StorageBlocked, match='STATE_CONFIRMED_CONTENT_MISMATCH'):
        writer.snapshot_confirmed('series_a', lambda path: False)
    assert backend.submits == submits


def test_retry_publishes_new_other_store_without_dropping_first_intent(readback_world, monkeypatch, tmp_path):
    writer, backend, _ = readback_world
    landed = _lose_snapshot_readback(writer, backend, monkeypatch)
    make_db(writer.local_path('gdw'), 4)
    writer.snapshot_once(force=True)
    head = backend.head()
    assert head['snapshots']['series_a'] == ss.parse_head(landed.body)['snapshots']['series_a']
    assert set(head['snapshots']) == {'series_a', 'gdw'}
    downloaded = tmp_path / 'gdw.sqlite'
    writer.objects.get_file(head['snapshots']['gdw']['path'], downloaded)
    assert count(downloaded) == 4
    assert writer._unpublished == {} and writer._pending_snapshot is None


def test_confirmed_snapshot_of_other_label_keeps_old_unsubmitted_intent_recoverable(readback_world, monkeypatch):
    writer, backend, _ = readback_world
    # Establish series_a, then lose an unrelated GDW submission entirely.
    writer.snapshot_once(force=True)
    make_db(writer.local_path('gdw'), 4)
    submit = backend.submit
    monkeypatch.setattr(backend, 'submit', lambda *_: (_ for _ in ()).throw(
        ss.StorageBlocked('STATE_HEAD_OUTCOME_UNCERTAIN')))
    writer.snapshot_once(force=True)
    pending = writer._pending_snapshot['body']
    monkeypatch.setattr(backend, 'submit', submit)
    proof = writer.snapshot_confirmed('series_a', lambda path: count(path) == 2)
    assert proof['entry'] == backend.head()['snapshots']['series_a']
    assert writer._pending_snapshot['body'] == pending
    writer.snapshot_once(force=True)
    assert backend.observe().body == pending
    assert writer._pending_snapshot is None
