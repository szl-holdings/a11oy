# SPDX-License-Identifier: Apache-2.0
"""Offline protocol races and provider-boundary controls; no Hub access."""
from __future__ import annotations

import copy
import ast
import base64
import hashlib
import json
import os
import sqlite3
import sys
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gdw_durable_storage as s


def snapshot(label, *, marker="a", count=3):
    digest = marker * 64
    value = {"path": f"{s.OBJECT_PREFIX}/{'b' * 32}/{label}-{digest}.sqlite3",
            "size": 4096, "sha256": digest, "xet_hash": "c" * 64,
            "generation": "d" * 32 if label == "gdw" else "store_" + "e" * 32,
            "receipt_count": count, "receipt_sequence": 0 if label == "gdw" else count,
            "receipt_head_sha256": "f" * 64}
    if label == "series_a":
        value["receipt_rows_sha256"] = "7" * 64
    return value


def bootstrap():
    return {"schema": s.SCHEMA, "space": s.SPACE, "dataset": s.DATASET, "bucket": s.BUCKET,
            "operation_id": "a" * 32, "writer_id": "0" * 32, "epoch": 0, "sequence": 0,
            "kind": "BOOTSTRAP", "previous_manifest_sha256": None,
            "source_revision": "b" * 40, "qualification_sha256": "c" * 64,
            "snapshots": {label: snapshot(label) for label in s.LABELS}}


class Backend:
    def __init__(self):
        self.serial = 0
        self.head = s.Head(self.revision(), s.canonical(bootstrap()))
        self.revisions = {self.head.revision: self.head}
        self.history = {}
        self.submissions = []
        self.on_submit = None
        self.on_read = None

    def revision(self):
        self.serial += 1
        return f"{self.serial:040x}"

    def observe(self, deadline):
        return self.head

    def unrelated_commit(self):
        self.head = s.Head(self.revision(), self.head.body)
        self.revisions[self.head.revision] = self.head

    def history_exists(self, revision, operation_id, deadline):
        return operation_id in self.history

    def submit(self, expected, body, operation_id, deadline):
        self.submissions.append((expected, body, operation_id))
        if self.on_submit:
            self.on_submit(expected, body, operation_id)
        if expected.revision != self.head.revision:
            raise s.ParentConflict()
        self.head = s.Head(self.revision(), body)
        self.revisions[self.head.revision] = self.head
        self.history[operation_id] = body
        return self.head.revision

    def read_at(self, revision, operation_id, deadline):
        if self.on_read:
            return self.on_read(revision, operation_id)
        return self.revisions[revision], self.history[operation_id]


def deadline():
    return time.monotonic() + 20


def active():
    backend = Backend()
    writer = s.Writer(backend, "b" * 40, "f" * 32)
    writer.claim(backend.head, deadline())
    return backend, writer


def test_claim_and_ack_bind_same_generation_exact_manifest_and_history():
    backend, writer = active()
    first = writer.head
    updated = first.value["snapshots"]
    updated["gdw"] = snapshot("gdw", marker="e", count=4)
    result = writer.commit(updated, deadline())
    assert writer.state == "ACTIVE"
    assert result.value["epoch"] == 1 and result.value["sequence"] == 2
    assert result.value["previous_manifest_sha256"] == first.digest
    assert backend.history[result.value["operation_id"]] == result.body
    assert writer.verify_read(deadline()) == result


def test_definite_conflict_rebases_only_unrelated_evidence_commit():
    backend, writer = active()
    before = len(backend.submissions)
    def conflict_once(*args):
        backend.on_submit = None
        backend.unrelated_commit()
    backend.on_submit = conflict_once
    result = writer.commit(writer.head.value["snapshots"], deadline())
    attempts = backend.submissions[before:]
    assert len(attempts) == 2
    assert attempts[0][1:] == attempts[1][1:]
    assert attempts[0][0].revision != attempts[1][0].revision
    assert result.body == attempts[-1][1]


def test_new_writer_epoch_fences_old_reads_writes_and_reclaims():
    backend, first = active()
    successor = s.Writer(backend, "c" * 40, "e" * 32)
    successor.claim(first.head, deadline())
    assert successor.head.value["epoch"] == 2
    with pytest.raises(s.StorageBlocked, match="WRITER_FENCED"):
        first.verify_read(deadline())
    assert first.state == "POISONED"
    with pytest.raises(s.StorageBlocked, match="WRITER_CANNOT_RECLAIM"):
        first.claim(successor.head, deadline())
    with pytest.raises(s.StorageBlocked, match="WRITER_NOT_ACTIVE"):
        first.commit(first.head.value["snapshots"], deadline())


def test_ambiguous_commit_is_not_retried_or_acknowledged_even_if_it_landed():
    backend, writer = active()
    before = len(backend.submissions)
    def lost_response(expected, body, operation_id):
        backend.head = s.Head(backend.revision(), body)
        backend.revisions[backend.head.revision] = backend.head
        backend.history[operation_id] = body
        raise TimeoutError("PRIVATE_PROVIDER_ERROR_MUST_NOT_LEAK")
    backend.on_submit = lost_response
    with pytest.raises(s.StorageBlocked, match="STORAGE_OUTCOME_UNCERTAIN") as error:
        writer.commit(writer.head.value["snapshots"], deadline())
    assert "PRIVATE_PROVIDER" not in str(error.value)
    assert len(backend.submissions) == before + 1
    assert writer.state == "POISONED"
    with pytest.raises(s.StorageBlocked, match="WRITER_NOT_ACTIVE"):
        writer.verify_read(deadline())


def test_history_collision_prevents_sdk_noop_success():
    backend, writer = active()
    before = len(backend.submissions)
    proposal = writer._proposal(writer.head, "COMMIT")
    backend.history[proposal["operation_id"]] = s.canonical(proposal)
    with pytest.raises(s.StorageBlocked, match="OPERATION_ID_ALREADY_EXISTS"):
        s.advance(backend, writer.head, proposal, deadline())
    assert len(backend.submissions) == before


@pytest.mark.parametrize("mode", ["head", "history", "revision", "noop"])
def test_success_response_requires_exact_immutable_readback(mode):
    backend, writer = active()
    prior = writer.head
    if mode == "noop":
        backend.submit = lambda expected, body, operation_id, end: expected.revision
    else:
        def bad_read(revision, operation_id):
            head = backend.revisions[revision]
            history = backend.history[operation_id]
            if mode == "head": head = s.Head(revision, prior.body)
            if mode == "history": history = prior.body
            if mode == "revision": head = s.Head(prior.revision, head.body)
            return head, history
        backend.on_read = bad_read
    with pytest.raises(s.StorageBlocked):
        writer.commit(prior.value["snapshots"], deadline())
    assert writer.state == "POISONED"


def test_conflict_never_rebases_over_changed_own_manifest():
    backend, writer = active()
    before = len(backend.submissions)
    def competitor(expected, body, operation_id):
        other = s.Writer(backend, "b" * 40, "e" * 32)
        backend.on_submit = None
        other.claim(expected, deadline())
    backend.on_submit = competitor
    with pytest.raises(s.StorageBlocked, match="WRITER_FENCED"):
        writer.commit(writer.head.value["snapshots"], deadline())
    # One original submission, one winning competitor; no original rebase.
    assert len(backend.submissions) == before + 2
    assert writer.state == "POISONED"


def test_rebase_contention_is_bounded():
    backend, writer = active()
    before = len(backend.submissions)
    backend.on_submit = lambda *args: backend.unrelated_commit()
    with pytest.raises(s.StorageBlocked, match="DATASET_CONTENTION"):
        writer.commit(writer.head.value["snapshots"], deadline())
    assert len(backend.submissions) == before + s.MAX_REBASE_ATTEMPTS
    assert writer.state == "POISONED"


def test_changed_generation_or_series_receipt_regression_poison_before_network():
    for kind in ("generation", "receipt_count", "receipt_sequence"):
        backend, writer = active()
        before = len(backend.submissions)
        snapshots = writer.head.value["snapshots"]
        if kind == "generation": snapshots["series_a"][kind] = "store_" + "f" * 32
        elif kind == "receipt_count": snapshots["series_a"][kind] = 2
        else:
            snapshots["series_a"]["receipt_count"] = 2
            snapshots["series_a"][kind] = 2
        with pytest.raises(s.StorageBlocked):
            writer.commit(snapshots, deadline())
        assert writer.state == "POISONED"
        assert len(backend.submissions) == before


def test_deadline_crossed_in_final_provider_read_prevents_ack(monkeypatch):
    backend, writer = active()
    clock = [10.0]
    monkeypatch.setattr(s.time, "monotonic", lambda: clock[0])
    native = backend.observe
    observations = [0]
    def delayed(end):
        observations[0] += 1
        value = native(end)
        if observations[0] == 2: clock[0] = 100.0
        return value
    backend.observe = delayed
    with pytest.raises(s.StorageBlocked, match="STORAGE_DEADLINE_EXHAUSTED"):
        writer.commit(writer.head.value["snapshots"], 50.0)
    assert writer.state == "POISONED"


@pytest.mark.parametrize("changes", [
    {"extra_payload": "PRIVATE_SQL"}, {"epoch": True}, {"sequence": 0.0},
    {"kind": []}, {"source_revision": "../private"}, {"source_revision": "0" * 40}, {"operation_id": "0" * 32},
    {"previous_manifest_sha256": "not-a-hash"}, {"writer_id": "e" * 32},
])
def test_manifest_has_no_private_payload_or_loose_scalar_admission(changes):
    value = bootstrap()
    value.update(changes)
    with pytest.raises(s.StorageBlocked):
        s.parse_manifest(s.canonical(value))


@pytest.mark.parametrize("path", ["a11oy/gdw/gdw.sqlite3", "../original.sqlite3", "https://other.invalid/a"])
def test_snapshot_path_cannot_target_original_or_external_storage(path):
    value = bootstrap()
    value["snapshots"]["gdw"]["path"] = path
    with pytest.raises(s.StorageBlocked, match="INVALID_SNAPSHOT_PATH"):
        s.validate_manifest(value)


def test_duplicate_keys_noncanonical_bytes_and_nan_are_rejected():
    raw = s.canonical(bootstrap())
    for invalid in (raw[:-2] + b',"epoch":0}\n', b" " + raw, raw.replace(b'"epoch":0', b'"epoch":NaN')):
        with pytest.raises(s.StorageBlocked):
            s.parse_manifest(invalid)


def test_accepted_manifest_is_detached_from_mutable_input():
    value = bootstrap()
    parsed = s.validate_manifest(value)
    value["snapshots"]["gdw"]["size"] = 1
    assert parsed["snapshots"]["gdw"]["size"] == 4096


def test_zero_revision_is_not_an_immutable_dataset_identity():
    with pytest.raises(s.StorageBlocked, match="INVALID_DATASET_REVISION"):
        s.Head("0" * 40, s.canonical(bootstrap()))


@pytest.mark.parametrize("field", ["qualification_sha256", "previous_manifest_sha256",
                                   "sha256", "xet_hash", "receipt_head_sha256"])
def test_zero_hash_cannot_establish_an_immutable_identity(field):
    value = bootstrap()
    if field == "previous_manifest_sha256":
        value.update(kind="CLAIM", epoch=1, sequence=1, writer_id="e" * 32)
    if field in {"sha256", "xet_hash", "receipt_head_sha256"}:
        value["snapshots"]["gdw"][field] = "0" * 64
    else:
        value[field] = "0" * 64
    with pytest.raises(s.StorageBlocked):
        s.validate_manifest(value)


def test_only_empty_native_series_chain_has_a_zero_head():
    value = bootstrap()
    series = value["snapshots"]["series_a"]
    series.update(receipt_count=0, receipt_sequence=0, receipt_head_sha256="0" * 64,
                  receipt_rows_sha256=hashlib.sha256(b"szl.series-a-receipt-rows/v1\n").hexdigest())
    assert s.validate_manifest(value)["snapshots"]["series_a"] == series
    for changes in ({"receipt_count": 1, "receipt_sequence": 1},
                    {"receipt_sequence": 1}, {"receipt_head_sha256": "f" * 64}):
        broken = copy.deepcopy(value)
        broken["snapshots"]["series_a"].update(changes)
        with pytest.raises(s.StorageBlocked):
            s.validate_manifest(broken)


def test_worker_success_is_rejected_if_private_cleanup_exhausts_deadline(tmp_path, monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(s.time, "monotonic", lambda: clock[0])
    native_temporary = s.tempfile.TemporaryDirectory

    class Temporary:
        def __init__(self, *args, **kwargs):
            self.native = native_temporary(*args, **kwargs)
            self.name = self.native.name

        def cleanup(self):
            self.native.cleanup()
            clock[0] = 100.0

    class Completed:
        returncode = 0

        def communicate(self, *args, **kwargs):
            return b'{"ok":true,"value":true}\n', b""

        def poll(self):
            return 0

    monkeypatch.setattr(s.tempfile, "TemporaryDirectory", Temporary)
    monkeypatch.setattr(s.subprocess, "Popen", lambda *args, **kwargs: Completed())
    with pytest.raises(s.StorageBlocked, match="STORAGE_DEADLINE_EXHAUSTED"):
        s._worker_call({"operation": "observe", "arguments": {},
                        "resource_group_sha256": "a" * 64}, tmp_path, 50.0)
    assert list(tmp_path.iterdir()) == []


def test_actual_worker_rejects_invalid_operation_without_provider_access(tmp_path):
    tmp_path.chmod(0o700)
    with pytest.raises(s.StorageBlocked, match="INVALID_WORKER_REQUEST") as error:
        s._worker_call({"operation": "not-an-operation", "arguments": {"PRIVATE": "NOT_FOR_OUTPUT"},
                        "resource_group_sha256": "a" * 64}, tmp_path, deadline())
    assert "NOT_FOR_OUTPUT" not in str(error.value)
    assert list(tmp_path.iterdir()) == []


def test_parent_kills_overdue_worker_and_never_retries(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    native = subprocess.Popen
    children = []
    def sleeping_worker(_command, **kwargs):
        child = native([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(s.subprocess, "Popen", sleeping_worker)
    started = time.monotonic()
    with pytest.raises(s.StorageBlocked, match="PROVIDER_DEADLINE_EXHAUSTED"):
        s._worker_call({"operation": "observe", "arguments": {},
                        "resource_group_sha256": "a" * 64}, tmp_path, started + 0.2)
    assert time.monotonic() - started < 3
    assert len(children) == 1 and children[0].poll() is not None
    assert list(tmp_path.iterdir()) == []


def native_schema(label):
    root = Path(__file__).resolve().parents[1]
    if label == "gdw":
        module = ast.parse((root / "gdw_workspace.py").read_text())
        for statement in module.body:
            if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "_SCHEMA_STATEMENTS"
                    for target in statement.targets):
                return ";".join(ast.literal_eval(statement.value))
    module = ast.parse((root / "routers/series_a_control_plane.py").read_text())
    store = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Store")
    init = next(node for node in store.body if isinstance(node, ast.FunctionDef) and node.name == "_init")
    call = next(node for node in ast.walk(init) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "executescript")
    return ast.literal_eval(call.args[0])


PRIVATE = "PRIVATE_NATIVE_ROW_MUST_NEVER_APPEAR_IN_METADATA"
GENERATIONS = {"gdw": "d" * 32, "series_a": "store_" + "e" * 32}


def native_database(path, label):
    with sqlite3.connect(path) as db:
        db.executescript(native_schema(label))
        if label == "gdw":
            db.execute("INSERT INTO schema_meta VALUES('gdw',4,?,?,?)",
                       (GENERATIONS[label], "2026-10-04", "2026-10-04"))
            receipt = {"namespace": "a11oy", "owner_id": "fixture", "request_id": "request-1",
                       "session_id": "session-1", "step": 0, "database_generation_id": GENERATIONS[label],
                       "private_payload": PRIVATE}
            digest = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            receipt["receipt_hash"] = digest
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       ("a11oy", "fixture", "request-1", "a" * 64, "session-1", PRIVATE,
                        "b" * 64, "ACTIVE", "2026-10-04", None, None))
            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)",
                       ("a11oy", "fixture", digest, "request-1", "session-1", 0,
                        json.dumps(receipt), "2026-10-04", None))
        else:
            db.execute("INSERT INTO metadata VALUES('storage_instance_id',?)", (GENERATIONS[label],))
            previous = "0" * 64
            for sequence in (1, 3):
                value = {"schema": "szl.series-a-receipt/v1", "receipt_id": f"rcpt_{sequence}",
                         "kind": "fixture", "created_at": "2026-10-04", "previous_receipt_hash": previous,
                         "payload": {"private_payload": PRIVATE}}
                body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                payload_type = s.SERIES_RECEIPT_TYPE.encode()
                pae = b"DSSEv1 " + str(len(payload_type)).encode() + b" " + payload_type + b" " \
                    + str(len(body)).encode() + b" " + body
                # Intentionally unsigned fixture: integrity is not relabeled as signature verification.
                envelope = {"payloadType": s.SERIES_RECEIPT_TYPE, "payload": base64.b64encode(body).decode(),
                            "signature_status": "UNSIGNED_UNAVAILABLE", "signatures": [],
                            "pae_sha256": hashlib.sha256(pae).hexdigest()}
                digest = hashlib.sha256(json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode()).hexdigest()
                db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)",
                           (sequence, value["receipt_id"], value["kind"], json.dumps(value), json.dumps(envelope),
                            previous, digest, value["created_at"]))
                previous = digest
            db.execute("UPDATE sqlite_sequence SET seq=12 WHERE name='receipts'")
    path.chmod(0o600)
    return path


class ObjectAPI:
    endpoint = s.ENDPOINT

    def __init__(self):
        self.objects = {}
        self.bytes_by_xet = {}
        self.additions = []
        self.downloads = []
        self.after_add = None
        self.on_download = None
        self.private = True

    def seed(self, path, data):
        xet = hashlib.sha256(b"synthetic-offline-xet-identity" + data).hexdigest()
        item = SimpleNamespace(type="file", path=path, size=len(data), xet_hash=xet)
        self.objects[path] = item
        self.bytes_by_xet[xet] = data
        return item

    def bucket_info(self, *, bucket_id):
        assert bucket_id == s.BUCKET
        return SimpleNamespace(id=bucket_id, private=self.private)

    def get_bucket_paths_info(self, *, bucket_id, paths):
        assert bucket_id == s.BUCKET and len(paths) == 1
        for path in paths:
            if path in self.objects:
                yield self.objects[path]

    def batch_bucket_files(self, *, bucket_id, add):
        assert bucket_id == s.BUCKET and len(add) == 1
        source, path = add[0]
        assert path.startswith(s.OBJECT_PREFIX + "/") or path.startswith(s.ARTIFACT_PREFIX + "/")
        self.additions.append((path, source.read_bytes()))
        self.seed(path, source.read_bytes())
        if self.after_add:
            self.after_add(source, path)

    def download_bucket_files(self, *, bucket_id, files):
        assert bucket_id == s.BUCKET and len(files) == 1
        observed, target = files[0]
        assert not isinstance(observed, str)
        self.downloads.append(observed)
        target.write_bytes(self.bytes_by_xet[observed.xet_hash])
        if self.on_download:
            self.on_download(observed, target)


@pytest.fixture
def object_store(tmp_path):
    tmp_path.chmod(0o700)
    staging = tmp_path / "staging"
    staging.mkdir(mode=0o700)
    paths = {label: native_database(tmp_path / (label + "-native.sqlite3"), label) for label in s.LABELS}
    api = ObjectAPI()
    store = s.HFPrivateObjectStore(api, staging, tmp_path)
    return SimpleNamespace(api=api, store=store, root=tmp_path, paths=paths)


def test_native_snapshots_publish_and_restore_exact_bytes_receipts_generation_and_high_water(object_store):
    state = object_store
    before = {label: path.read_bytes() for label, path in state.paths.items()}
    snapshots = state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert len(state.api.additions) == len(state.api.downloads) == 2
    assert snapshots["gdw"]["receipt_count"] == 1 and snapshots["gdw"]["receipt_sequence"] == 0
    assert snapshots["series_a"]["receipt_count"] == 2 and snapshots["series_a"]["receipt_sequence"] == 3
    assert PRIVATE not in s.canonical(snapshots).decode()
    destinations = {label: state.root / (label + "-restored.sqlite3") for label in s.LABELS}
    assert state.store.restore_snapshots(snapshots, destinations, deadline()) == snapshots
    for label in s.LABELS:
        assert destinations[label].read_bytes() == state.paths[label].read_bytes() == before[label]
        assert snapshots[label]["generation"] == GENERATIONS[label]
    with sqlite3.connect(destinations["series_a"]) as db:
        assert db.execute("SELECT seq FROM sqlite_sequence WHERE name='receipts'").fetchone()[0] == 12
    assert len(state.api.additions) == 2  # restoring is read-only


@pytest.mark.parametrize("defect", ["integrity", "foreign_key", "receipt", "generation", "schema", "sidecar", "wal"])
def test_both_native_snapshots_must_qualify_before_first_provider_add(object_store, defect):
    state = object_store
    path = state.paths["series_a"]
    if defect == "integrity":
        data = bytearray(path.read_bytes())
        page_size = int.from_bytes(data[16:18], "big")
        data[28:32] = (len(data) // page_size + 1).to_bytes(4, "big")
        data.extend(b"\0" * page_size)
        path.write_bytes(data)
    elif defect == "foreign_key":
        path = state.paths["gdw"]
        with sqlite3.connect(path) as db:
            db.execute("DELETE FROM requests")
    elif defect == "receipt":
        with sqlite3.connect(path) as db:
            db.execute("UPDATE receipts SET previous_hash=? WHERE sequence=3", ("a" * 64,))
    elif defect == "generation":
        with sqlite3.connect(path) as db:
            db.execute("UPDATE metadata SET value=? WHERE key='storage_instance_id'", ("store_" + "f" * 32,))
    elif defect == "schema":
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE unqualified_unkeyed_data(value TEXT)")
    elif defect == "sidecar":
        Path(str(path) + "-journal").write_bytes(b"private-journal")
    else:
        data = bytearray(path.read_bytes())
        data[18:20] = b"\2\2"
        path.write_bytes(data)
    before = {label: path.read_bytes() for label, path in state.paths.items()}
    with pytest.raises(s.StorageBlocked) as error:
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert PRIVATE not in str(error.value)
    assert state.api.additions == []
    assert {label: path.read_bytes() for label, path in state.paths.items()} == before


def test_uncertain_object_add_is_never_retried_even_when_remote_bytes_landed(object_store):
    state = object_store
    def lost(*args):
        raise TimeoutError(PRIVATE)
    state.api.after_add = lost
    with pytest.raises(s.StorageBlocked, match="STORAGE_OUTCOME_UNCERTAIN") as error:
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert len(state.api.additions) == 1 and len(state.api.objects) == 1
    assert state.api.downloads == [] and PRIVATE not in str(error.value)


def test_remote_path_change_after_exact_xet_download_blocks_ack(object_store):
    state = object_store
    def replace(observed, target):
        state.api.seed(observed.path, b"another writer changed the path")
    state.api.on_download = replace
    with pytest.raises(s.StorageBlocked, match="PRIVATE_OBJECT_IDENTITY_CHANGED"):
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert len(state.api.additions) == len(state.api.downloads) == 1


def artifact_input(state):
    path = state.root / "retained-artifact.json"
    body = json.dumps({"payload": PRIVATE}, sort_keys=True, indent=2).encode() + b"\n"
    path.write_bytes(body)
    path.chmod(0o600)
    digest = hashlib.sha256(body).hexdigest()
    key = f"{s.ARTIFACT_PREFIX}/{'b' * 64}/{digest}.json"
    return path, key, digest


def test_artifact_readback_is_exact_and_identical_rerun_performs_no_add(object_store):
    state = object_store
    path, key, digest = artifact_input(state)
    first = state.store.publish_artifact(path, key, digest, deadline())
    second = state.store.publish_artifact(path, key, digest, deadline())
    assert first == second and first["sha256"] == digest
    assert len(state.api.additions) == 1 and len(state.api.downloads) == 2
    assert PRIVATE not in s.canonical(first).decode()


def test_existing_different_artifact_never_gets_overwritten(object_store):
    state = object_store
    path, key, digest = artifact_input(state)
    altered = b"x" * path.stat().st_size
    state.api.seed(key, altered)
    with pytest.raises(s.StorageBlocked, match="PRIVATE_OBJECT_READBACK_MISMATCH"):
        state.store.publish_artifact(path, key, digest, deadline())
    assert state.api.additions == []
    assert state.api.bytes_by_xet[state.api.objects[key].xet_hash] == altered


@pytest.mark.parametrize("defect", ["path", "digest", "public_bucket", "hardlink", "symlink", "fifo", "loose_directory"])
def test_private_artifact_boundary_fails_before_any_provider_add(object_store, defect):
    state = object_store
    path, key, digest = artifact_input(state)
    if defect == "path": key = "a11oy/gdw/gdw.sqlite3"
    elif defect == "digest": digest = "f" * 64
    elif defect == "public_bucket": state.api.private = False
    elif defect == "hardlink": os.link(path, state.root / "second-name")
    elif defect == "symlink":
        target = path.with_suffix(".target")
        path.rename(target)
        path.symlink_to(target)
    elif defect == "fifo":
        path.unlink()
        os.mkfifo(path, 0o600)
    else: state.root.chmod(0o755)
    with pytest.raises(s.StorageBlocked):
        state.store.publish_artifact(path, key, digest, deadline())
    assert state.api.additions == []


def test_changed_restore_identity_or_existing_destination_has_no_fallback(object_store):
    state = object_store
    snapshots = state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    destinations = {label: state.root / (label + "-restored.sqlite3") for label in s.LABELS}
    state.api.seed(snapshots["gdw"]["path"], b"different-identity")
    before = len(state.api.downloads)
    with pytest.raises(s.StorageBlocked, match="RESTORE_OBJECT_IDENTITY_MISMATCH"):
        state.store.restore_snapshots(snapshots, destinations, deadline())
    assert len(state.api.downloads) == before
    assert not any(path.exists() for path in destinations.values())
    destinations["gdw"].write_bytes(b"preexisting-local-data")
    destinations["gdw"].chmod(0o600)
    with pytest.raises(s.StorageBlocked, match="PRIVATE_DESTINATION_ALREADY_EXISTS"):
        state.store.restore_snapshots(snapshots, destinations, deadline())
    assert destinations["gdw"].read_bytes() == b"preexisting-local-data"


def test_snapshot_metadata_iteration_must_complete_before_admission(object_store):
    state = object_store
    def incomplete(**kwargs):
        yield SimpleNamespace(type="file", path=kwargs["paths"][0], size=4096, xet_hash="b" * 64)
        raise TimeoutError(PRIVATE)
    state.api.get_bucket_paths_info = incomplete
    with pytest.raises(s.StorageBlocked, match="PRIVATE_OBJECT_IDENTITY_UNAVAILABLE"):
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert state.api.additions == []


def test_first_snapshot_changed_during_second_upload_blocks_pair_ack(object_store):
    state = object_store
    def supersede_first(source, path):
        if len(state.api.additions) == 2:
            state.api.seed(state.api.additions[0][0], b"changed-after-first-readback")
    state.api.after_add = supersede_first
    with pytest.raises(s.StorageBlocked, match="PRIVATE_OBJECT_IDENTITY_CHANGED"):
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert len(state.api.additions) == len(state.api.downloads) == 2


def test_same_named_unkeyed_application_table_cannot_be_admitted(object_store):
    state = object_store
    with sqlite3.connect(state.paths["series_a"]) as db:
        db.execute("ALTER TABLE events RENAME TO keyed_events")
        db.execute("CREATE TABLE events AS SELECT * FROM keyed_events")
        db.execute("DROP TABLE keyed_events")
    with pytest.raises(s.StorageBlocked, match="SNAPSHOT_SCHEMA_UNQUALIFIED"):
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    assert state.api.additions == []


@pytest.mark.parametrize("label", s.LABELS)
def test_zero_generation_is_not_a_qualified_store_identity(label):
    value = bootstrap()
    value["snapshots"][label]["generation"] = "0" * 32 if label == "gdw" else "store_" + "0" * 32
    with pytest.raises(s.StorageBlocked):
        s.validate_manifest(value)


def test_native_receipt_binding_distinguishes_missing_null_and_boolean_values():
    assert s._same_fields({"field": None}, {"field": None})
    assert not s._same_fields({}, {"field": None})
    assert not s._same_fields({"step": False}, {"step": 0})


def test_provider_worker_rejects_symlinked_private_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(s.StorageBlocked, match="PRIVATE_STAGING_REQUIRED"):
        s.WorkerFenceBackend(link, "a" * 64)


def test_killed_worker_cannot_ack_a_simulated_accepted_remote_operation(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    marker = tmp_path / "synthetic-remote-accepted"
    native = subprocess.Popen
    children = []
    def accepted_without_reply(_command, **kwargs):
        script = "from pathlib import Path; import sys,time; Path(sys.argv[1]).write_text('accepted'); time.sleep(60)"
        child = native([sys.executable, "-c", script, str(marker)], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(s.subprocess, "Popen", accepted_without_reply)
    with pytest.raises(s.StorageBlocked, match="PROVIDER_DEADLINE_EXHAUSTED"):
        s._worker_call({"operation": "submit", "arguments": {}, "resource_group_sha256": "a" * 64},
                       tmp_path, time.monotonic() + 0.4)
    assert marker.read_text() == "accepted"
    assert len(children) == 1 and children[0].poll() is not None
    assert [path.name for path in tmp_path.iterdir()] == [marker.name]


@pytest.mark.parametrize("change", ["head", "sequence", "rows"])
def test_series_history_cannot_change_when_no_receipt_is_appended(change):
    backend, writer = active()
    previous = len(backend.submissions)
    values = writer.head.value["snapshots"]
    if change == "head": values["series_a"]["receipt_head_sha256"] = "e" * 64
    elif change == "sequence": values["series_a"]["receipt_sequence"] += 1
    else: values["series_a"]["receipt_rows_sha256"] = "e" * 64
    with pytest.raises(s.StorageBlocked, match="RECEIPT_HISTORY_REWRITTEN"):
        writer.commit(values, deadline())
    assert writer.state == "POISONED" and len(backend.submissions) == previous


def test_claimed_append_cannot_reuse_the_prior_complete_row_identity():
    backend, writer = active()
    previous = len(backend.submissions)
    values = writer.head.value["snapshots"]
    values["series_a"].update(receipt_count=4, receipt_sequence=4, receipt_head_sha256="e" * 64)
    with pytest.raises(s.StorageBlocked, match="RECEIPT_HISTORY_REWRITTEN"):
        writer.commit(values, deadline())
    assert writer.state == "POISONED" and len(backend.submissions) == previous


def test_internally_valid_replacement_chain_cannot_erase_previous_receipt_anchor(object_store):
    state = object_store
    prior = state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    before = len(state.api.additions)
    path = state.paths["series_a"]
    with sqlite3.connect(path) as db:
        previous = "0" * 64
        for sequence, payload, envelope in db.execute("SELECT sequence,payload,envelope FROM receipts ORDER BY sequence").fetchall():
            value, signed = json.loads(payload), json.loads(envelope)
            value["payload"]["private_payload"] = "different internally valid history"
            value["previous_receipt_hash"] = previous
            body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ptype = s.SERIES_RECEIPT_TYPE.encode()
            pae = b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " + str(len(body)).encode() + b" " + body
            signed["payload"] = base64.b64encode(body).decode()
            signed["pae_sha256"] = hashlib.sha256(pae).hexdigest()
            digest = hashlib.sha256(json.dumps(signed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            db.execute("UPDATE receipts SET payload=?,envelope=?,previous_hash=?,receipt_hash=? WHERE sequence=?",
                       (json.dumps(value), json.dumps(signed), previous, digest, sequence))
            previous = digest
    # This is a self-consistent candidate, but not an extension of the last acknowledged chain.
    assert s.inspect_snapshot("series_a", path, state.root, deadline())["receipt_count"] == 2
    with pytest.raises(s.StorageBlocked, match="ACKNOWLEDGED_RECEIPT_ANCHOR_CHANGED"):
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline(), previous_snapshots=prior)
    assert len(state.api.additions) == before


def test_unchanged_receipt_chain_is_valid_for_nonreceipt_store_updates(object_store):
    state = object_store
    prior = state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    with sqlite3.connect(state.paths["series_a"]) as db:
        db.execute("INSERT INTO metadata VALUES('nonreceipt_fixture','changed')")
    current = state.store.publish_snapshots(state.paths, GENERATIONS, deadline(), previous_snapshots=prior)
    assert current["series_a"]["sha256"] != prior["series_a"]["sha256"]
    for key in ("generation", "receipt_count", "receipt_sequence", "receipt_head_sha256", "receipt_rows_sha256"):
        assert current["series_a"][key] == prior["series_a"][key]


def append_native_series_receipt(path):
    from routers.series_a_control_plane import Store, ReceiptSigner
    signer = ReceiptSigner.__new__(ReceiptSigner)
    signer.private_key, signer.public_pem, signer.source, signer.error = None, "", "unavailable", "offline fixture"
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        Store._append_receipt_in_transaction(db, "native.prefix.extension", {"private": PRIVATE}, signer)


@pytest.mark.parametrize("mutation", ["sequence", "payload_json", "envelope_json"])
@pytest.mark.parametrize("append", [False, True])
def test_earlier_receipt_rows_cannot_change_despite_unchanged_native_anchor(object_store, mutation, append):
    state = object_store
    prior = state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    path = state.paths["series_a"]
    with sqlite3.connect(path) as db:
        if mutation == "sequence":
            db.execute("UPDATE receipts SET sequence=2 WHERE sequence=1")
        else:
            column = "payload" if mutation == "payload_json" else "envelope"
            value = db.execute(f"SELECT {column} FROM receipts WHERE sequence=1").fetchone()[0]
            db.execute(f"UPDATE receipts SET {column}=? WHERE sequence=1", (json.dumps(json.loads(value), indent=2),))
    observed = s.inspect_snapshot("series_a", path, state.root, deadline())
    for key in ("receipt_head_sha256", "receipt_sequence", "receipt_count"):
        assert observed[key] == prior["series_a"][key]
    assert observed["receipt_rows_sha256"] != prior["series_a"]["receipt_rows_sha256"]
    if append:
        append_native_series_receipt(path)
        assert s.inspect_snapshot("series_a", path, state.root, deadline())["receipt_count"] == 3
    before = len(state.api.additions)
    with pytest.raises(s.StorageBlocked, match="ACKNOWLEDGED_RECEIPT_ANCHOR_CHANGED"):
        state.store.publish_snapshots(state.paths, GENERATIONS, deadline(), previous_snapshots=prior)
    assert len(state.api.additions) == before


def test_native_append_preserves_exact_old_row_prefix_and_sequence_gap(object_store):
    state = object_store
    prior = state.store.publish_snapshots(state.paths, GENERATIONS, deadline())
    with sqlite3.connect(state.paths["series_a"]) as db:
        previous_rows = db.execute("SELECT * FROM receipts ORDER BY sequence").fetchall()
    append_native_series_receipt(state.paths["series_a"])
    current = state.store.publish_snapshots(state.paths, GENERATIONS, deadline(), previous_snapshots=prior)
    assert current["series_a"]["receipt_count"] == 3
    assert current["series_a"]["receipt_sequence"] == 13
    with sqlite3.connect(state.paths["series_a"]) as db:
        rows = db.execute("SELECT * FROM receipts ORDER BY sequence").fetchall()
    assert rows[:2] == previous_rows and [row[0] for row in rows] == [1, 3, 13]
    digest = hashlib.sha256(b"szl.series-a-receipt-rows/v1\n")
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n")
    assert current["series_a"]["receipt_rows_sha256"] == digest.hexdigest()
    assert PRIVATE not in json.dumps(current)


@pytest.mark.parametrize("value", [None, "0" * 64, "f" * 63, True])
def test_series_row_identity_is_mandatory_and_nonzero(value):
    document = bootstrap()
    item = document["snapshots"]["series_a"]
    if value is None:
        del item["receipt_rows_sha256"]
    else:
        item["receipt_rows_sha256"] = value
    with pytest.raises(s.StorageBlocked):
        s.validate_manifest(document)


def test_runtime_snapshot_publisher_requires_previous_acknowledged_head(object_store):
    state = object_store
    publisher = s.WorkerSnapshotStore(state.root, GENERATIONS, "a" * 64)
    with pytest.raises(s.StorageBlocked, match="PREVIOUS_ACKNOWLEDGED_HEAD_REQUIRED"):
        publisher.publish(state.paths, deadline())


class InitialBackend(Backend):
    """Synthetic CAS boundary: no actual repository or admission provenance."""
    def __init__(self):
        super().__init__()
        self.current_revision = self.head.revision
        self.head = None
        self.revisions.clear()
        self.admissions = {}

    def empty_parent(self, deadline):
        if self.head is not None:
            raise s.StorageBlocked("INITIAL_HEAD_ALREADY_EXISTS")
        return self.current_revision

    def admission_exists(self, revision, digest, deadline):
        return digest in self.admissions

    def read_admission(self, head, deadline):
        return self.admissions[head.value["qualification_sha256"]]

    def submit_bootstrap(self, parent, body, admission, deadline):
        self.submissions.append((parent, body, admission))
        if self.on_submit:
            self.on_submit(parent, body, admission)
        if parent != self.current_revision:
            raise s.ParentConflict()
        self.current_revision = self.revision()
        self.head = s.Head(self.current_revision, body)
        self.revisions[self.head.revision] = self.head
        self.history[self.head.value["operation_id"]] = body
        self.admissions[self.head.value["qualification_sha256"]] = admission
        return self.current_revision


@pytest.fixture
def initial_admission(monkeypatch):
    # The coordinator owns exhaustive admission-schema tests. This deliberately
    # marked synthetic schema isolates absent-only CAS, readback and ambiguity.
    def parse(data):
        value = json.loads(data)
        assert set(value) == {"schema", "source_revision", "snapshots"}
        assert value["schema"] == "OFFLINE_PROTOCOL_TEST_ONLY"
        return value
    def bind(value, manifest):
        assert value["source_revision"] == manifest["source_revision"]
        assert value["snapshots"] == manifest["snapshots"]
    monkeypatch.setitem(sys.modules, "gdw_durable_startup",
                        SimpleNamespace(parse_admission=parse, validate_bootstrap_binding=bind))
    value = bootstrap()
    admission = s.canonical({"schema": "OFFLINE_PROTOCOL_TEST_ONLY", "source_revision": value["source_revision"],
                             "snapshots": value["snapshots"]})
    value["qualification_sha256"] = hashlib.sha256(admission).hexdigest()
    return value, admission


def test_initial_bootstrap_binds_head_history_and_admission_in_one_cas(initial_admission):
    value, admission = initial_admission
    backend = InitialBackend()
    committed = s.bootstrap(backend, value, admission, deadline())
    assert len(backend.submissions) == 1
    assert backend.history[value["operation_id"]] == committed.body
    assert backend.read_admission(committed, deadline()) == admission
    with pytest.raises(s.StorageBlocked, match="INITIAL_HEAD_ALREADY_EXISTS"):
        s.bootstrap(backend, value, admission, deadline())
    assert len(backend.submissions) == 1


def test_initial_bootstrap_rebases_only_definite_conflict_while_head_remains_absent(initial_admission):
    value, admission = initial_admission
    backend = InitialBackend()
    def unrelated(*args):
        backend.on_submit = None
        backend.current_revision = backend.revision()
    backend.on_submit = unrelated
    s.bootstrap(backend, value, admission, deadline())
    assert len(backend.submissions) == 2
    assert backend.submissions[0][0] != backend.submissions[1][0]
    assert backend.submissions[0][1:] == backend.submissions[1][1:]


@pytest.mark.parametrize("defect", ["history_collision", "admission_collision", "admission_hash", "source_binding"])
def test_initial_bootstrap_rejects_unqualified_or_existing_inputs_before_write(initial_admission, defect):
    value, admission = initial_admission
    backend = InitialBackend()
    if defect == "history_collision": backend.history[value["operation_id"]] = b"prior"
    elif defect == "admission_collision": backend.admissions[value["qualification_sha256"]] = admission
    elif defect == "admission_hash": value["qualification_sha256"] = "f" * 64
    else: value["source_revision"] = "f" * 40
    with pytest.raises(s.StorageBlocked):
        s.bootstrap(backend, value, admission, deadline())
    assert backend.submissions == []


def test_initial_bootstrap_lost_reply_is_not_retried_even_after_acceptance(initial_admission):
    value, admission = initial_admission
    backend = InitialBackend()
    def lost(parent, body, admission):
        backend.on_submit = None
        backend.current_revision = backend.revision()
        backend.head = s.Head(backend.current_revision, body)
        backend.revisions[backend.current_revision] = backend.head
        backend.history[value["operation_id"]] = body
        backend.admissions[value["qualification_sha256"]] = admission
        raise TimeoutError(PRIVATE)
    backend.on_submit = lost
    with pytest.raises(s.StorageBlocked, match="STORAGE_OUTCOME_UNCERTAIN"):
        s.bootstrap(backend, value, admission, deadline())
    assert len(backend.submissions) == 1 and backend.head is not None


def test_initial_bootstrap_requires_exact_admission_readback(initial_admission):
    value, admission = initial_admission
    backend = InitialBackend()
    backend.read_admission = lambda *args: b"different safe metadata"
    with pytest.raises(s.StorageBlocked, match="STORAGE_ADMISSION_IDENTITY_MISMATCH"):
        s.bootstrap(backend, value, admission, deadline())
    assert len(backend.submissions) == 1
