#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Single-writer lease between two simulated replicas on a fake CAS dataset.

No network: the dataset is FakeHeadBackend (parent_commit CAS, HTTP-412 style
ParentConflict) and the bucket is a local directory. A fake clock drives the
heartbeat, the handover wait and lease staleness deterministically.
"""

import json
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_state_store as ss
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
