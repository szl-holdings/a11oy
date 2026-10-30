#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline operator protocol tests: fake CAS and small in-memory heartbeat."""

import copy
import json

import pytest

import a11oy_state_store as ss
from scripts import request_state_store_handover as op
from tests.state_store_support import FakeClock, FakeHeadBackend


@pytest.fixture
def world():
    clock, backend = FakeClock(), FakeHeadBackend()
    snapshots = {}
    for spec in ss.STORES:
        snapshots[spec.label] = {
            "path": f"{ss.PREFIX}/{spec.label}/20260921T000000Z-1-1-{'a' * 16}.{spec.extension}",
            "sha256": "a" * 64, "size": 4096, "kind": spec.kind,
            "integrity": "lmdb_read" if spec.kind == "lmdb" else "integrity_check",
            "logical_sha256": "b" * 64, "taken_at": op.utc(clock.time()), "epoch": 1, "seq": 1}
    head = {"schema": ss.HEAD_SCHEMA, "operation_id": "1" * 32, "sequence": 1,
            "previous_manifest_sha256": None, "epoch": 1, "writer_id": "2" * 32,
            "boot_id": "3" * 32, "state": ss.STATE_ACTIVE, "transition": "BOOTSTRAP",
            "handover": None, "claim": {"kind": ss.CLAIM_FIRST_BOOT, "at": op.utc(clock.time()),
                                         "origins": {}, "previous_epoch": 0},
            "lease": {"renewed_at": op.utc(clock.time()), "heartbeat_path": ss.HEARTBEAT_PATH,
                      "stale_after_seconds": 120}, "source_revision": "c" * 40,
            "bucket": ss.DEFAULT_BUCKET, "snapshots": snapshots, "history": {}}
    backend._append(ss.canonical(ss.validate_head(head)))
    heartbeat = {"schema": ss.HEARTBEAT_SCHEMA, "epoch": 1, "writer_id": head["writer_id"],
                 "boot_id": head["boot_id"], "at": op.utc(clock.time()), "at_unix": clock.time()}

    class Objects:
        def get_bytes(self, path, limit):
            assert path == ss.HEARTBEAT_PATH
            assert limit == ss.MAX_SMALL_OBJECT_BYTES
            return json.dumps(heartbeat).encode()

    observed = backend.observe()
    expected = {"commit": observed.revision, "sha256": op.digest(observed.body),
                "writer_id": head["writer_id"], "boot_id": head["boot_id"], "epoch": 1}
    records = []
    options = dict(expected=expected, bucket=ss.DEFAULT_BUCKET, clock=clock.time,
                   monotonic=clock.monotonic, sleep=clock.sleep, timeout=6, poll=1,
                   requested_by="4" * 32, operation_id="5" * 32)
    return backend, Objects(), clock, heartbeat, records, options


def release(backend, clock, change=None):
    current = backend.head()
    if current["state"] != ss.STATE_HANDOVER:
        return
    final = copy.deepcopy(current)
    final.update(operation_id="6" * 32, sequence=current["sequence"] + 1,
                 previous_manifest_sha256=op.digest(backend.observe().body),
                 transition="RELEASE", state=ss.STATE_RELEASED, handover=None)
    final["lease"]["renewed_at"] = op.utc(clock.time())
    if change:
        change(final)
    backend._append(ss.canonical(final))


def run(world, **overrides):
    backend, objects, _, _, records, options = world
    return op.request_handover(backend, objects, record=records.append,
                              **dict(options, **overrides))


def test_preflight_never_submits_starts_or_claims(world, monkeypatch):
    monkeypatch.setattr(ss, "StateStore", lambda **_: pytest.fail("store constructed"))
    monkeypatch.setattr(ss, "activate", lambda **_: pytest.fail("store activated"))
    report = run(world)
    assert report["status"] == "PREFLIGHT_VERIFIED"
    assert world[0].submits == 0 and world[4] == []
    assert report["publication_authorized"] is False


@pytest.mark.parametrize("mode", [None, "uncertain_lost", "uncertain_landed", "parent_move"])
def test_request_and_exact_release_preserve_identity(world, mode):
    backend, _, clock, _, records, _ = world
    original = backend.head()
    if mode == "parent_move":
        backend.before_submit = backend.unrelated_commit
    else:
        backend.fail_next_submit = mode
    clock.on_sleep.append(lambda: release(backend, clock))
    report = run(world, execute=True)
    assert report["status"] == "RELEASE_OBSERVED", report
    request = next(ss.parse_head(body) for _, body in backend.commits
                   if body and ss.parse_head(body)["transition"] == "HANDOVER_REQUEST")
    for key in set(original) - {"operation_id", "sequence", "previous_manifest_sha256",
                                "transition", "state", "handover"}:
        assert request[key] == original[key]
    assert records[0]["event"] == "REQUEST_INTENT"
    assert records[-1]["event"] == "RELEASE_OBSERVED"
    assert report["object_preservation"] == report["runtime_health"] == "NOT_VERIFIED"
    assert backend.head()["epoch"] == 1


def test_intent_write_failure_prevents_provider_effect(world):
    backend, objects, _, _, _, options = world
    def denied(_):
        raise OSError("token-sensitive-error-must-not-appear")
    report = op.request_handover(backend, objects, **options, execute=True, record=denied)
    assert backend.submits == 0 and report["status"] == "HOLD"
    assert "token-sensitive" not in json.dumps(report)


@pytest.mark.parametrize("key,value", [("commit", "e" * 40), ("sha256", "e" * 64),
                                      ("writer_id", "e" * 32), ("boot_id", "e" * 32), ("epoch", 2)])
def test_expected_identity_mismatch_never_submits(world, key, value):
    expected = dict(world[5]["expected"], **{key: value})
    assert run(world, execute=True, expected=expected)["status"] == "HOLD"
    assert world[0].submits == 0


@pytest.mark.parametrize("field,value", [("writer_id", "f" * 32), ("boot_id", "f" * 32),
                                        ("epoch", True), ("at", "2026-10-17T12:00:00+00:00"),
                                        ("at_unix", float("nan"))])
def test_heartbeat_identity_and_timestamp_fail_closed(world, field, value):
    world[3][field] = value
    assert run(world, execute=True)["status"] == "HOLD"
    assert world[0].submits == 0


@pytest.mark.parametrize("age", [-1, 121])
def test_future_or_stale_heartbeat_never_submits(world, age):
    world[2].advance(age)
    assert run(world, execute=True)["reason"] == "HEARTBEAT_NOT_FRESH"
    assert world[0].submits == 0


def test_heartbeat_rechecked_after_durable_intent(world):
    backend, objects, clock, _, _, options = world
    report = op.request_handover(backend, objects, **options, execute=True,
                                record=lambda _: clock.advance(121))
    assert report["reason"] == "HEARTBEAT_NOT_FRESH" and backend.submits == 0


def test_missing_required_store_blocks_request(world):
    backend = world[0]
    head = backend.head()
    del head["snapshots"]["khipu_repl"]
    backend._append(ss.canonical(head))
    expected = dict(world[5]["expected"], commit=backend.observe().revision,
                    sha256=op.digest(backend.observe().body))
    assert run(world, execute=True, expected=expected)["reason"] == "REQUIRED_SNAPSHOT_COVERAGE_MISSING"
    assert backend.submits == 0


@pytest.mark.parametrize("mutation", [lambda h: h.update(previous_manifest_sha256="f" * 64),
                                      lambda h: h.update(sequence=h["sequence"] + 1),
                                      lambda h: h.update(boot_id="f" * 32),
                                      lambda h: h.update(epoch=2),
                                      lambda h: h["snapshots"].pop("unay")])
def test_wrong_release_causality_identity_or_coverage_is_hold(world, mutation):
    backend, _, clock, _, _, _ = world
    clock.on_sleep.append(lambda: release(backend, clock, mutation))
    assert run(world, execute=True)["status"] == "HOLD"
    assert backend.submits == 1


def test_timeout_never_forces_release_or_claim(world):
    report = run(world, execute=True)
    assert report["reason"] == "RELEASE_TIMEOUT"
    assert world[0].head()["state"] == ss.STATE_HANDOVER
    assert world[0].submits == 1 and world[0].head()["epoch"] == 1


def test_permanent_uncertain_failure_stays_hold_same_intent(world, monkeypatch):
    submitted = []
    def lost(parent, body, operation):
        submitted.append(body)
        raise ss.StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")
    monkeypatch.setattr(world[0], "submit", lost)
    report = run(world, execute=True)
    assert report["status"] == "HOLD" and report["request_submission"] == "OUTCOME_UNKNOWN"
    assert len(submitted) == 3 and len(set(submitted)) == 1
    assert world[0].head()["state"] == ss.STATE_ACTIVE


def test_uncertain_landed_request_with_immediate_release_is_causally_resolved(world, monkeypatch):
    backend, _, clock, _, _, _ = world
    submit = backend.submit
    def land_and_release(*args):
        submit(*args)
        release(backend, clock)
        raise ss.StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")
    monkeypatch.setattr(backend, "submit", land_and_release)
    report = run(world, execute=True)
    assert report["status"] == "RELEASE_OBSERVED", report
    assert backend.submits == 1


def test_lost_release_immutable_readback_stays_hold(world, monkeypatch):
    backend, _, clock, _, _, _ = world
    read_at = backend.read_at
    def lose_release(revision):
        body = read_at(revision)
        return b"different" if ss.parse_head(body)["state"] == ss.STATE_RELEASED else body
    monkeypatch.setattr(backend, "read_at", lose_release)
    clock.on_sleep.append(lambda: release(backend, clock))
    assert run(world, execute=True)["reason"] == "RELEASE_READBACK_MISMATCH"


def test_head_snapshot_race_never_rebases_operator_request(world):
    backend = world[0]
    def snapshot():
        current = backend.head()
        current.update(operation_id="7" * 32, sequence=current["sequence"] + 1,
                       previous_manifest_sha256=op.digest(backend.observe().body), transition="SNAPSHOT")
        backend._append(ss.canonical(current))
    backend.before_submit = snapshot
    report = run(world, execute=True)
    assert report["status"] == "HOLD" and backend.head()["transition"] == "SNAPSHOT"
    assert backend.submits == 1


def test_receipt_recovery_is_read_only_and_hash_bound(world, tmp_path):
    backend, objects, clock, _, _, options = world
    path = tmp_path / "receipt.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        report = op.request_handover(backend, objects, **options, execute=True, record=op.ReceiptLog(stream))
    assert report["reason"] == "RELEASE_TIMEOUT"
    release(backend, clock)
    before = backend.submits
    report = op.observe_receipt(backend, path, expected=options["expected"], bucket=ss.DEFAULT_BUCKET,
                               monotonic=clock.monotonic, sleep=clock.sleep)
    assert report["status"] == "RELEASE_OBSERVED", report
    assert backend.submits == before
    assert op.observe_receipt(backend, path, expected=options["expected"],
                              bucket=ss.DEFAULT_BUCKET, dataset="OTHER/state")["status"] == "HOLD"
    path.write_bytes(path.read_bytes().replace(b'"UNSIGNED"', b'"FORGED"', 1))
    assert op.observe_receipt(backend, path, expected=options["expected"],
                              bucket=ss.DEFAULT_BUCKET)["status"] == "HOLD"
    assert backend.submits == before
