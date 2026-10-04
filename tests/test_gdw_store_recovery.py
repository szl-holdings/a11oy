# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


q = load("qualify_gdw_store_recovery", ROOT / "scripts/qualify_gdw_store_recovery.py")
fixtures = load("preservation_fixtures", ROOT / "tests/test_hf_gdw_preservation.py")
p = q.preservation
PRIVATE = "PRIVATE_ROW_PAYLOAD_NOT_FOR_LOGS_OR_ARTIFACTS"
GDW_GENERATION = "c" * 32
SERIES_GENERATION = "store_" + "d" * 32


def native_schema(label):
    if label == "gdw":
        module = ast.parse((ROOT / "gdw_workspace.py").read_text())
        for statement in module.body:
            if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "_SCHEMA_STATEMENTS"
                    for target in statement.targets):
                return ";".join(ast.literal_eval(statement.value))
    module = ast.parse((ROOT / "routers/series_a_control_plane.py").read_text())
    store = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Store")
    init = next(node for node in store.body if isinstance(node, ast.FunctionDef) and node.name == "_init")
    call = next(node for node in ast.walk(init) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "executescript")
    return ast.literal_eval(call.args[0])


def database_fixture(path, label):
    with sqlite3.connect(path) as connection:
        connection.executescript(native_schema(label))
        if label == "gdw":
            connection.execute("INSERT INTO schema_meta VALUES('gdw',4,?,?,?)",
                               (GDW_GENERATION, "2026-10-04", "2026-10-04"))
            receipt = {"namespace": "a11oy", "owner_id": "fixture", "request_id": "request-1",
                       "session_id": "session-1", "step": 0,
                       "database_generation_id": GDW_GENERATION, "private_payload": PRIVATE}
            digest = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            receipt["receipt_hash"] = digest
            connection.execute("INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                               ("a11oy", "fixture", "request-1", "a" * 64,
                                "session-1", PRIVATE, "b" * 64, "ACTIVE", "2026-10-04", None, None))
            connection.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)",
                               ("a11oy", "fixture", digest, "request-1", "session-1", 0,
                                json.dumps(receipt), "2026-10-04", None))
        else:
            connection.execute("INSERT INTO metadata VALUES('storage_instance_id',?)", (SERIES_GENERATION,))
            connection.execute("INSERT INTO metadata VALUES('storage_created_at','2026-10-04T00:00:00.000Z')")
            prior = "0" * 64
            for sequence in (1, 3):
                receipt = {"schema": "szl.series-a-receipt/v1", "receipt_id": f"rcpt_{sequence}",
                           "kind": "fixture", "created_at": "2026-10-04T00:00:00.000Z",
                           "source_revision": "a" * 40, "previous_receipt_hash": prior,
                           "payload": {"private_payload": PRIVATE}}
                body = q._canonical(receipt)
                ptype = q.SERIES_RECEIPT_TYPE.encode()
                pae = b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " + str(len(body)).encode() + b" " + body
                envelope = {"payloadType": q.SERIES_RECEIPT_TYPE,
                            "payload": base64.b64encode(body).decode(), "signatures": [],
                            "signature_status": "UNSIGNED_UNAVAILABLE", "key_source": "fixture",
                            "pae_sha256": hashlib.sha256(pae).hexdigest()}
                digest = hashlib.sha256(q._canonical(envelope)).hexdigest()
                connection.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?)",
                                   (sequence, receipt["receipt_id"], receipt["kind"], json.dumps(receipt),
                                    json.dumps(envelope), prior, digest, receipt["created_at"]))
                prior = digest
            # The AUTOINCREMENT high-water mark must survive even after rows
            # have been removed; comparing visible receipt counts is not enough.
            connection.execute("UPDATE sqlite_sequence SET seq=12 WHERE name='receipts'")
    return path


@pytest.fixture
def originals(tmp_path):
    return {label: database_fixture(tmp_path / f"{label}.sqlite3", label) for label in p.DATABASES}


def unused_pages(path):
    data = bytearray(path.read_bytes())
    page_size = int.from_bytes(data[16:18], "big")
    data[28:32] = (len(data) // page_size + 2).to_bytes(4, "big")
    data.extend(b"\x00" * (2 * page_size))
    path.write_bytes(data)


def detached_freelist_pages(path):
    unused_pages(path)
    raw = bytearray(path.read_bytes())
    size = int.from_bytes(raw[16:18], "big")
    leaf = len(raw) // size
    start = len(raw) - 2 * size
    raw[start + 4:start + 8] = (1).to_bytes(4, "big")
    raw[start + 8:start + 12] = leaf.to_bytes(4, "big")
    path.write_bytes(raw)
    return [leaf - 1, leaf]


def qualify(label, originals, tmp_path, **kwargs):
    return q.qualify_database(label, originals[label], tmp_path / "working" / label,
                              GDW_GENERATION if label == "gdw" else SERIES_GENERATION,
                              kwargs.get("deadline", time.monotonic() + 30),
                              historical_anchors=kwargs.get("historical_anchors"))


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_native_backup_preserves_real_schema_values_and_generation(originals, tmp_path, label):
    original = originals[label].read_bytes()
    report = qualify(label, originals, tmp_path)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    assert report["candidate_method"] == "SQLITE_NATIVE_BACKUP"
    assert report["schema_unchanged"] and report["receipt_bytes_unchanged"]
    assert report["all_declared_stored_values_unchanged"] and report["database_generation_unchanged"]
    assert report["restore_admitted"] is False and report["durable_storage_qualified"] is False
    assert originals[label].read_bytes() == original
    assert PRIVATE not in json.dumps(report)
    if label == "series_a":
        assert report["original_receipts"]["last_sequence"] == 3
        assert report["original_receipts"]["unsigned_envelopes"] == 2
        assert report["original_receipts"]["signature_verification"] == "NOT_PERFORMED"
        with sqlite3.connect(tmp_path / "working" / label / "candidate.sqlite3") as candidate:
            assert candidate.execute("SELECT seq FROM sqlite_sequence WHERE name='receipts'").fetchone()[0] == 12


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_unused_pages_candidate_has_integrity_and_exact_logical_continuity(originals, tmp_path, label):
    unused_pages(originals[label])
    original = originals[label].read_bytes()
    report = qualify(label, originals, tmp_path)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    assert report["original_integrity"]["classification"] == "UNREFERENCED_PAGES"
    assert report["candidate_integrity"]["classification"] == "OK"
    assert report["candidate_method"] == "SQLITE_VACUUM_INTO_DISPOSABLE_EVALUATION"
    assert report["candidate_bytes"] < len(original)
    assert originals[label].read_bytes() == original
    assert report["restore_admitted"] is False


def test_sqlite_never_opens_captured_originals(originals, tmp_path, monkeypatch):
    connect = sqlite3.connect
    opened = []
    def guarded(path, *args, **kwargs):
        name = str(path)
        opened.append(name)
        assert "/working/" in name
        assert "/inspection/" in name or name.endswith("candidate.sqlite3?mode=ro") or name.endswith("candidate.sqlite3")
        return connect(path, *args, **kwargs)
    monkeypatch.setattr(q.sqlite3, "connect", guarded)
    assert qualify("gdw", originals, tmp_path)["state"] == "LOGICAL_CONTINUITY_VERIFIED"
    assert len(opened) == 3


@pytest.mark.parametrize("change", ["payload", "sequence", "generation", "schema"])
@pytest.mark.parametrize("detached", [False, True])
def test_candidate_tampering_cannot_be_qualified(originals, tmp_path, monkeypatch, change, detached):
    if detached:
        detached_freelist_pages(originals["series_a"])
    fingerprint = q.logical_fingerprint
    calls = []
    def altered(connection, label, deadline):
        calls.append(label)
        if len(calls) == 2:
            candidate = tmp_path / "working" / label / "candidate.sqlite3"
            with sqlite3.connect(candidate) as write:
                if change == "payload":
                    write.execute("UPDATE metadata SET value=? WHERE key='storage_created_at'", (PRIVATE + "altered",))
                elif change == "sequence":
                    write.execute("UPDATE sqlite_sequence SET seq=13 WHERE name='receipts'")
                elif change == "generation":
                    write.execute("UPDATE metadata SET value=? WHERE key='storage_instance_id'", ("store_" + "e" * 32,))
                else:
                    write.execute("CREATE INDEX altered_receipt_index ON receipts(kind)")
        return fingerprint(connection, label, deadline)
    monkeypatch.setattr(q, "logical_fingerprint", altered)
    report = qualify("series_a", originals, tmp_path)
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "CANDIDATE_LOGICAL_CONTINUITY_FAILED"


def test_generation_is_bound_to_preservation_evidence(originals, tmp_path):
    report = q.qualify_database("gdw", originals["gdw"], tmp_path / "working", "e" * 32,
                               time.monotonic() + 30)
    assert report["diagnostic_code"] == "CAPTURE_GENERATION_MISMATCH"
    assert not (tmp_path / "working" / "candidate.sqlite3").exists()


def test_unknown_schema_is_preserved_but_not_evaluated(originals, tmp_path):
    with sqlite3.connect(originals["gdw"]) as connection:
        connection.execute("CREATE TABLE unexpected(private TEXT)")
        connection.execute("INSERT INTO unexpected VALUES(?)", (PRIVATE,))
    raw = originals["gdw"].read_bytes()
    report = qualify("gdw", originals, tmp_path)
    assert report["diagnostic_code"] == "UNQUALIFIED_STORE_SCHEMA"
    assert originals["gdw"].read_bytes() == raw
    assert PRIVATE not in json.dumps(report)


def test_invalid_receipt_binding_prevents_candidate(originals, tmp_path):
    with sqlite3.connect(originals["series_a"]) as connection:
        connection.execute("UPDATE receipts SET previous_hash=? WHERE sequence=3", ("f" * 64,))
    report = qualify("series_a", originals, tmp_path)
    assert report["diagnostic_code"] == "ORIGINAL_RECEIPT_BINDINGS_INVALID"
    assert report["original_receipts"]["chain_link_errors"] == 1
    assert not (tmp_path / "working" / "series_a" / "candidate.sqlite3").exists()


def test_foreign_key_violations_cannot_be_repacked(originals, tmp_path):
    with sqlite3.connect(originals["gdw"]) as connection:
        connection.execute("DELETE FROM requests")
    report = qualify("gdw", originals, tmp_path)
    assert report["diagnostic_code"] == "ORIGINAL_NOT_ELIGIBLE_FOR_CANDIDATE"
    assert report["original_integrity"]["foreign_key_violation_count"] == 1


def test_type_framing_preserves_storage_classes_and_float_bits():
    assert len({q._framed(value) for value in (None, 1, 1.0, "1", b"1", -0.0, 0.0)}) == 7
    assert q._framed("ab") + q._framed("c") != q._framed("a") + q._framed("bc")


def test_deadline_cannot_produce_qualified_state(originals, tmp_path):
    report = qualify("gdw", originals, tmp_path, deadline=0)
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "QUALIFICATION_DEADLINE_EXHAUSTED"


@pytest.fixture
def capture(originals, tmp_path):
    hub = fixtures.FakeHub({path: originals[label].read_bytes() for label, path in p.DATABASES.items()})
    reference = p.preserve(hub, source_sha="a" * 40, run_id="37216937874", run_attempt="1",
                           nonce="b" * 32, workspace=tmp_path / "preservation",
                           require_owned_source=lambda: None, sleep=lambda _: None)
    assert reference["preservation_state"] == "VERIFIED", reference
    return hub, reference


def captured_run(capture, tmp_path, checker=lambda: None):
    hub, reference = capture
    return q.qualify_capture(q.ReadOnlyCaptureHub(hub), reference, tmp_path / "qualification", checker,
                              time.monotonic() + 30)


def test_exact_capture_readback_qualifies_without_provider_mutation(capture, tmp_path):
    hub, reference = capture
    batches = len(hub.batch_calls)
    original_remote = dict(hub.files)
    report = captured_run(capture, tmp_path)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    assert report["preservation_manifest_sha256"] == reference["private_manifest"]["sha256"]
    assert len(hub.batch_calls) == batches and hub.files == original_remote
    assert report["provider_writes_performed"] is False and report["restore_admitted"] is False
    assert PRIVATE not in json.dumps(report)
    assert not hasattr(q.ReadOnlyCaptureHub(hub), "batch_bucket_files")
    assert not hasattr(q.ReadOnlyCaptureHub(hub), "restart_space")
    for info, _local in hub.download_calls[-1]:
        assert info.path.startswith(reference["private_capture_prefix"] + "/")
        assert not isinstance(info, str)


@pytest.mark.parametrize("change", ["unverified", "path", "xet_hash", "sha256", "manifest"])
def test_invalid_or_changed_capture_never_reaches_sqlite(capture, tmp_path, monkeypatch, change):
    hub, reference = capture
    if change == "unverified":
        reference["preservation_state"] = "COPY_REQUESTED"
    elif change == "manifest":
        hub.files[reference["private_manifest"]["path"]] += b"changed"
    else:
        row = next(row for row in reference["files"] if row["present"])
        if change == "path":
            row["private_copy_path"] = p.DATABASES["gdw"]
        else:
            row[change] = "f" * 64
    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid captures must not open SQLite")
    monkeypatch.setattr(q.sqlite3, "connect", forbidden)
    report = captured_run(capture, tmp_path)
    assert report["state"] == "BLOCKED"
    assert report["diagnostic_code"] in {"CAPTURE_NOT_VERIFIED", "CAPTURE_REFERENCE_INVALID",
                                         "PRESERVED_OBJECT_IDENTITY_CHANGED", "PRESERVED_OBJECT_DIGEST_MISMATCH",
                                         "PRESERVED_MANIFEST_IDENTITY_CHANGED"}


def test_provider_text_is_never_public(capture, tmp_path):
    hub, _reference = capture
    def broken(**_kwargs):
        raise RuntimeError(PRIVATE)
    hub.bucket_info = broken
    report = captured_run(capture, tmp_path)
    assert report["state"] == "BLOCKED"
    assert report["diagnostic_code"] == "PROVIDER_OPERATION_UNAVAILABLE"
    assert PRIVATE not in json.dumps(report)


def test_loss_of_source_ownership_blocks_qualified_result(capture, tmp_path):
    calls = []
    def checker():
        calls.append(True)
        if len(calls) == 2:
            raise q.RecoveryError("SOURCE_NO_LONGER_CURRENT_MAIN")
    report = captured_run(capture, tmp_path, checker)
    assert report["state"] == "BLOCKED"
    assert report["diagnostic_code"] == "SOURCE_NO_LONGER_CURRENT_MAIN"


def test_duplicate_json_keys_do_not_replace_recorded_identities():
    with pytest.raises(q.RecoveryError, match="JSON_DUPLICATE_KEY"):
        q._json('{"capture_id":"one","capture_id":"two"}')


def _native_companion(path, label, kind):
    if kind == "invalid-wal":
        path.with_name(path.name + "-wal").write_bytes(PRIVATE.encode())
        return
    if kind == "shm":
        path.with_name(path.name + "-shm").write_bytes(PRIVATE.encode())
        return
    mode = "WAL" if kind == "valid-wal" else "PERSIST"
    connection = sqlite3.connect(path)
    try:
        connection.execute(f"PRAGMA journal_mode={mode}")
        connection.execute("PRAGMA cache_size=1")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        if label == "gdw":
            connection.execute("UPDATE schema_meta SET created_at=?", (PRIVATE * 2000,))
        else:
            connection.execute("UPDATE metadata SET value=? WHERE key='storage_created_at'",
                               (PRIVATE * 2000,))
        if kind != "hot-journal":
            connection.commit()
        captured = {suffix: path.with_name(path.name + suffix).read_bytes()
                    for suffix in p.SUFFIXES if path.with_name(path.name + suffix).exists()}
        if kind == "valid-wal":
            assert captured["-wal"][:4] in (bytes.fromhex("377f0682"), bytes.fromhex("377f0683"))
        elif kind == "hot-journal":
            assert captured["-journal"][:8] == bytes.fromhex("d9d505f920a163d7")
        else:
            assert captured["-journal"][:8] == b"\x00" * 8
    finally:
        connection.rollback()
        connection.close()
    # Restore the captured file set after closing the fixture writer. Only
    # this disposable test data contains a live-WAL or hot-journal snapshot.
    for suffix in p.SUFFIXES:
        target = path.with_name(path.name + suffix)
        if suffix in captured:
            target.write_bytes(captured[suffix])
        elif target.exists():
            target.unlink()


@pytest.mark.parametrize("label", ["gdw", "series_a"])
@pytest.mark.parametrize("kind", ["valid-wal", "invalid-wal", "hot-journal", "cold-journal", "shm"])
def test_nonempty_companions_require_review_before_any_sqlite_open(originals, tmp_path, monkeypatch, label, kind):
    original = originals[label]
    _native_companion(original, label, kind)
    before = {suffix: original.with_name(original.name + suffix).read_bytes()
              for suffix in p.SUFFIXES if original.with_name(original.name + suffix).exists()}
    def forbidden(*_args, **_kwargs):
        pytest.fail("nonempty companions must not reach SQLite evaluation or recovery")
    monkeypatch.setattr(q.sqlite3, "connect", forbidden)
    report = qualify(label, originals, tmp_path)
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "SIDECAR_REVIEW_REQUIRED"
    assert report["restore_admitted"] is False
    assert not (tmp_path / "working" / label / "candidate.sqlite3").exists()
    for suffix in p.SUFFIXES:
        if suffix:
            expected = {"present": False} if suffix not in before else {
                "present": True, "size": len(before[suffix]),
                "sha256": hashlib.sha256(before[suffix]).hexdigest(),
            }
            assert report["companions"][suffix] == expected
        if suffix in before:
            assert original.with_name(original.name + suffix).read_bytes() == before[suffix]
    assert PRIVATE not in json.dumps(report)


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_empty_companions_remain_eligible_and_preserved(originals, tmp_path, label):
    original = originals[label]
    for suffix in p.SUFFIXES[1:]:
        original.with_name(original.name + suffix).write_bytes(b"")
    report = qualify(label, originals, tmp_path)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    for suffix in p.SUFFIXES[1:]:
        assert report["companions"][suffix] == {
            "present": True, "size": 0, "sha256": hashlib.sha256(b"").hexdigest(),
        }
        assert original.with_name(original.name + suffix).read_bytes() == b""


@pytest.mark.parametrize("late_io", ["candidate_hash", "candidate_size"])
def test_final_candidate_io_cannot_cross_deadline_and_claim_qualification(originals, tmp_path, monkeypatch, late_io):
    clock = [0.0]
    monkeypatch.setattr(q.time, "monotonic", lambda: clock[0])
    if late_io == "candidate_hash":
        sha = p._sha
        def delayed(path):
            digest = sha(path)
            if path.name == "candidate.sqlite3":
                clock[0] = 11.0
            return digest
        monkeypatch.setattr(p, "_sha", delayed)
    else:
        file_stat = Path.stat
        def delayed(path, *args, **kwargs):
            result = file_stat(path, *args, **kwargs)
            if path.name == "candidate.sqlite3":
                clock[0] = 11.0
            return result
        monkeypatch.setattr(Path, "stat", delayed)
    report = qualify("gdw", originals, tmp_path, deadline=10.0)
    assert clock[0] == 11.0
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "QUALIFICATION_DEADLINE_EXHAUSTED"
    assert "all_declared_stored_values_unchanged" not in report


@pytest.mark.parametrize("late_io", ["ownership", "remote_identity", "local_hash"])
def test_final_capture_revalidation_cannot_cross_deadline(capture, tmp_path, monkeypatch, late_io):
    hub, reference = capture
    clock = [0.0]
    monkeypatch.setattr(q.time, "monotonic", lambda: clock[0])
    calls = []
    def ownership():
        calls.append(True)
        if late_io == "ownership" and len(calls) == 2:
            clock[0] = 11.0
    if late_io != "ownership":
        name = "paths_info" if late_io == "remote_identity" else "_local_files"
        function = getattr(p, name)
        reads = []
        def delayed(*args, **kwargs):
            value = function(*args, **kwargs)
            reads.append(True)
            if len(reads) == 2:
                clock[0] = 11.0
            return value
        monkeypatch.setattr(p, name, delayed)
    report = q.qualify_capture(q.ReadOnlyCaptureHub(hub), reference, tmp_path / "qualification",
                               ownership, 10.0)
    assert clock[0] == 11.0
    assert report["state"] == "BLOCKED"
    assert report["diagnostic_code"] == "QUALIFICATION_DEADLINE_EXHAUSTED"
    assert report["deployment_admitted"] is False and report["restore_admitted"] is False


@pytest.mark.parametrize("failure", ["elapsed", "exception", "unchecked_history"])
def test_cli_final_guards_cannot_leave_a_qualified_state(tmp_path, monkeypatch, failure):
    clock = [0.0]
    monkeypatch.setattr(q.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(q.os, "environ", dict(q.os.environ))
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "szl-holdings/a11oy",
                       "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "a" * 40,
                       "HF_TOKEN": "offline-hf-fixture", "GH_TOKEN": "offline-github-fixture"}.items():
        monkeypatch.setenv(key, value)
    reference = ROOT / "docs/operations/evidence/gdw-capture-37223162231.json"
    anchors = ROOT / "docs/operations/evidence/gdw-recovery-historical-anchors.json"
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["qualify", "--capture-report", str(reference),
                                     "--historical-anchors", str(anchors), "--output", str(output)])
    hub = types.ModuleType("huggingface_hub")
    hub.__version__ = p.SDK_VERSION
    hub.HfApi = lambda **_kwargs: types.SimpleNamespace(endpoint=p.ENDPOINT)
    utils = types.ModuleType("huggingface_hub.utils")
    utils.set_client_factory = lambda _factory: None
    ownership = types.ModuleType("hf_exact_main_ownership")
    ownership.fetch_main_sha = lambda *_args: pytest.fail("no network in this cleanup-boundary fixture")
    for name, module in (("huggingface_hub", hub), ("huggingface_hub.utils", utils),
                         ("hf_exact_main_ownership", ownership)):
        monkeypatch.setitem(sys.modules, name, module)
    def qualified(*_args, **_kwargs):
        return {"schema": q.SCHEMA, "state": "LOGICAL_CONTINUITY_VERIFIED",
                "diagnostic_code": "RESTORE_CONTRACT_REQUIRED", "deployment_admitted": False,
                "restore_admitted": False,
                "historical_anchor_state": "NOT_CHECKED" if failure == "unchecked_history" else "VERIFIED"}
    monkeypatch.setattr(q, "qualify_capture", qualified)
    class Cleanup:
        def __enter__(self):
            return str(tmp_path / "private")
        def __exit__(self, *_args):
            if failure != "unchecked_history":
                clock[0] = q.DEADLINE_SECONDS + 1
            if failure == "exception":
                raise q.RecoveryError("QUALIFICATION_DEADLINE_EXHAUSTED")
    monkeypatch.setattr(q.tempfile, "TemporaryDirectory", lambda **_kwargs: Cleanup())
    previous_umask = q.os.umask(0o077)
    q.os.umask(previous_umask)
    previous_logging = q.logging.root.manager.disable
    try:
        assert q.main() == 2
    finally:
        q.os.umask(previous_umask)
        q.logging.disable(previous_logging)
    report = json.loads(output.read_text())
    assert report["state"] == "BLOCKED"
    expected = "HISTORICAL_ANCHORS_NOT_VERIFIED" if failure == "unchecked_history" else "QUALIFICATION_DEADLINE_EXHAUSTED"
    assert report["diagnostic_code"] == expected


@pytest.mark.parametrize("orphan_count", [99, 100, 105])
def test_saturated_integrity_result_is_not_an_exact_orphan_class(originals, tmp_path, orphan_count):
    path = originals["gdw"]
    data = bytearray(path.read_bytes())
    page_size = int.from_bytes(data[16:18], "big")
    data[28:32] = (len(data) // page_size + orphan_count).to_bytes(4, "big")
    data.extend(b"\x00" * (orphan_count * page_size))
    path.write_bytes(data)
    report = qualify("gdw", originals, tmp_path)
    if orphan_count < q.MAX_INTEGRITY_ERRORS:
        assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED"
        assert report["original_integrity"]["integrity_check_complete"] is True
        assert report["unreferenced_page_contents"]["page_count"] == orphan_count
    else:
        assert report["state"] == "UNQUALIFIED"
        assert report["diagnostic_code"] == "ORIGINAL_NOT_ELIGIBLE_FOR_CANDIDATE"
        assert report["original_integrity"]["classification"] == "INTEGRITY_RESULT_INCOMPLETE"
        assert report["original_integrity"]["integrity_check_complete"] is False
        assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()
    assert path.read_bytes() == data


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_nonzero_orphan_pages_are_preserved_for_review_without_vacuum(originals, tmp_path, label):
    path = originals[label]
    unused_pages(path)
    data = bytearray(path.read_bytes())
    data[-len(PRIVATE):] = PRIVATE.encode()
    path.write_bytes(data)
    report = qualify(label, originals, tmp_path)
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"
    assert report["original_integrity"]["classification"] == "UNREFERENCED_PAGES"
    checked = report["unreferenced_page_contents"]
    assert checked["page_count"] == 2 and checked["all_zero"] is False
    assert set(checked) == {"page_count", "byte_count", "contents_sha256", "all_zero"}
    assert PRIVATE not in json.dumps(report)
    assert path.read_bytes() == data
    assert not (tmp_path / "working" / label / "candidate.sqlite3").exists()


def test_nonzero_forensics_are_bound_to_captured_bytes_and_keep_existing_hold(originals, tmp_path):
    path = originals["gdw"]
    unused_pages(path)
    raw = bytearray(path.read_bytes())
    raw[-len(PRIVATE):] = PRIVATE.encode()
    path.write_bytes(raw)
    report = qualify("gdw", originals, tmp_path)
    forensic = report["unreferenced_page_forensics"]
    assert forensic["inspection_sha256"] == hashlib.sha256(raw).hexdigest()
    assert forensic["orphan_contents_sha256"] == report["unreferenced_page_contents"]["contents_sha256"]
    assert forensic["orphan_page_count"] == 2
    assert forensic["state"] == "HELD" and forensic["candidate_created"] is False
    assert report["diagnostic_code"] == "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False
    assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()
    assert path.read_bytes() == raw and PRIVATE not in json.dumps(report)


def test_descriptive_detached_freelist_match_requires_separate_candidate_predicate(originals, tmp_path, monkeypatch):
    path = originals["gdw"]
    detached_freelist_pages(path)
    raw = path.read_bytes()
    monkeypatch.setattr(q, "detached_freelist_candidate_evidence", lambda *args: False)
    report = qualify("gdw", originals, tmp_path)
    forensic = report["unreferenced_page_forensics"]
    assert forensic["freelist_graph"]["state"] == "STRUCTURALLY_ACCOUNTED"
    assert forensic["state"] == "HELD" and forensic["candidate_created"] is False
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False
    assert report["diagnostic_code"] == "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"
    assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()
    assert path.read_bytes() == raw


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_byte_reconstructed_detached_graph_qualifies_only_a_disposable_candidate(originals, tmp_path, label, capsys):
    path = originals[label]
    detached_freelist_pages(path)
    original = path.read_bytes()
    report = qualify(label, originals, tmp_path)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    assert report["diagnostic_code"] == "RESTORE_CONTRACT_REQUIRED"
    assert report["candidate_method"] == "SQLITE_VACUUM_INTO_DISPOSABLE_EVALUATION"
    assert report["detached_freelist_candidate_contract"] == "BYTE_RECONSTRUCTED_DISPOSABLE_ONLY"
    assert report["restore_admitted"] is False and report["durable_storage_qualified"] is False
    assert report["inspection_copy_unchanged"] is True
    assert report["captured_originals_unchanged"] is True
    assert report["schema_unchanged"] is True and report["receipt_bytes_unchanged"] is True
    assert report["all_declared_stored_values_unchanged"] is True
    assert report["database_generation_unchanged"] is True
    assert report["unreferenced_page_forensics"]["state"] == "HELD"
    assert report["unreferenced_page_forensics"]["discard_admitted"] is False
    assert report["unreferenced_page_forensics"]["candidate_created"] is False
    assert path.read_bytes() == original
    assert (tmp_path / "working" / label / "inspection" / path.name).read_bytes() == original
    candidate = tmp_path / "working" / label / "candidate.sqlite3"
    assert candidate.stat().st_size < len(original)
    with sqlite3.connect(candidate) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        if label == "series_a":
            assert connection.execute("SELECT seq FROM sqlite_sequence WHERE name='receipts'").fetchone()[0] == 12
    assert PRIVATE not in json.dumps(report)
    assert capsys.readouterr() == ("", "")


@pytest.fixture
def detached_witness(originals, tmp_path):
    path = originals["gdw"]
    pages = detached_freelist_pages(path)
    private = tmp_path / "witness"
    private.mkdir(mode=0o700)
    copy = private / "inspection.sqlite3"
    copy.write_bytes(path.read_bytes())
    deadline = time.monotonic() + 30
    contents = q.unreferenced_page_contents(copy, pages, deadline)
    digest = hashlib.sha256(copy.read_bytes()).hexdigest()
    report = q.orphan_forensic_observation(copy, pages, deadline, digest, contents)
    assert q.detached_freelist_candidate_evidence(report, pages, contents, digest, deadline) is True
    return report, pages, contents, digest


@pytest.mark.parametrize("location", [
    ("candidate_created",), ("discard_admitted",), ("restore_admitted",), ("deployment_admitted",),
    ("provider_writes_performed",), ("private_payloads_emitted",), ("record_equivalence_verified",),
    ("all_bytes_semantically_explained",), ("inspection_copy_unchanged",),
    ("native_reachability", "complete"), ("native_reachability", "orphan_set_reconfirmed"),
    ("freelist_graph", "complete"), ("freelist_graph", "whole_database_accounted"),
    ("freelist_graph", "orphan_bytes_structurally_accounted"),
])
def test_detached_predicate_rejects_changed_or_equal_looking_boolean_fields(detached_witness, location):
    report, pages, contents, digest = detached_witness
    target = report
    for name in location[:-1]: target = target[name]
    initial = target[location[-1]]
    for value in (not initial, int(initial), str(initial), None):
        target[location[-1]] = value
        assert q.detached_freelist_candidate_evidence(report, pages, contents, digest, time.monotonic() + 10) is False


@pytest.mark.parametrize("defect", ["outer_key", "header_key", "graph_key", "native_key", "page_key",
    "trunk_key", "database_sha", "aggregate_sha", "page_sha", "page_number", "page_count_boolean",
    "byte_count", "reserved", "pointer_map", "incremental", "attached_head", "attached_count", "attached_digest",
    "reachable_count", "reachable_types", "native_version", "partial", "graph_state", "classification",
    "duplicate", "trunk_count", "leaf_count", "root", "next_self", "leaf_self", "leaf_boolean", "extra_leaf",
    "zero_leaf_list", "extra_trunk", "structure_bytes", "nonzero_bytes", "zero_bytes", "page_nonzero", "companion"])
def test_detached_predicate_requires_exact_bound_shape_and_page_reconstruction(detached_witness, defect):
    report, pages, contents, digest = detached_witness
    graph = report["freelist_graph"]
    detached = graph["detached_freelist"]
    if defect.endswith("_key"):
        target = {"outer_key": report, "header_key": report["database_header"], "graph_key": graph,
                  "native_key": report["native_reachability"], "page_key": report["pages"][0],
                  "trunk_key": detached["trunks"][0]}[defect]
        target["unknown"] = PRIVATE
    elif defect == "database_sha": report["inspection_sha256"] = "f" * 64
    elif defect == "aggregate_sha": report["orphan_contents_sha256"] = "f" * 64
    elif defect == "page_sha": report["pages"][0]["sha256"] = "f" * 64
    elif defect == "page_number": report["pages"][0]["page_number"] += 1
    elif defect == "page_count_boolean": report["orphan_page_count"] = True
    elif defect == "byte_count": report["orphan_byte_count"] += 1
    elif defect in {"reserved", "pointer_map", "incremental"}:
        report["database_header"][{"reserved": "reserved_bytes_per_page", "pointer_map": "largest_root_page",
                                   "incremental": "incremental_vacuum"}[defect]] = 1
    elif defect == "attached_head": graph["attached_freelist"]["head"] = pages[0]
    elif defect == "attached_count": graph["attached_freelist"]["page_count"] = 1
    elif defect == "attached_digest": graph["attached_freelist"]["page_numbers_sha256"] = "f" * 64
    elif defect == "reachable_count": report["native_reachability"]["reachable_page_count"] -= 1
    elif defect == "reachable_types": report["native_reachability"]["reachable_page_types"]["leaf"] += 1
    elif defect == "native_version": report["native_reachability"]["inspector_sqlite_version"] = "0.0.0"
    elif defect == "partial": report["analysis_state"] = "PARTIAL"
    elif defect == "graph_state": graph["state"] = "UNCLASSIFIED"
    elif defect == "classification": report["pages"][0]["structure"]["classification"] = "BTREE_LOCAL_LAYOUT_CONSISTENT"
    elif defect == "duplicate": report["pages"][0]["reachable_duplicate"]["state"] = "EXACT_FULL_PAGE_MATCH"
    elif defect == "trunk_count": detached["trunk_count"] = True
    elif defect == "leaf_count": detached["leaf_count"] += 1
    elif defect == "root": detached["root_page"] = pages[-1]
    elif defect == "next_self": detached["trunks"][0]["next_trunk"] = pages[0]
    elif defect == "leaf_self": detached["trunks"][0]["leaf_pages"] = [pages[0]]
    elif defect == "leaf_boolean": detached["trunks"][0]["leaf_pages"] = [True]
    elif defect == "extra_leaf": detached["trunks"][0]["leaf_pages"].append(pages[-1])
    elif defect == "zero_leaf_list": detached["zero_leaf_pages"] = [pages[0]]
    elif defect == "extra_trunk": detached["trunks"].append(dict(detached["trunks"][0]))
    elif defect == "structure_bytes": graph["byte_accounting"]["structural_bytes"] += 1
    elif defect == "nonzero_bytes": graph["byte_accounting"]["structural_nonzero_bytes"] += 1
    elif defect == "zero_bytes": graph["byte_accounting"]["zero_padding_and_leaf_bytes"] -= 1
    elif defect == "page_nonzero": report["pages"][0]["nonzero_byte_count"] += 1
    else: report["companions"] = "IGNORED"
    assert q.detached_freelist_candidate_evidence(report, pages, contents, digest, time.monotonic() + 10) is False


def test_reconstructed_page_bytes_must_match_independent_aggregate_even_if_page_claims_are_changed(detached_witness):
    report, pages, contents, digest = detached_witness
    graph = report["freelist_graph"]
    detached = graph["detached_freelist"]
    detached["root_page"] = pages[1]
    detached["trunks"] = [{"page_number": pages[1], "next_trunk": 0, "leaf_pages": [pages[0]]}]
    detached["zero_leaf_pages"] = [pages[0]]
    size = report["database_header"]["page_size"]
    alternate = {number: bytearray(size) for number in pages}
    alternate[pages[1]][4:8] = (1).to_bytes(4, "big")
    alternate[pages[1]][8:12] = pages[0].to_bytes(4, "big")
    total_nonzero = 0
    for observation in report["pages"]:
        raw = alternate[observation["page_number"]]
        nonzero = size - raw.count(0)
        total_nonzero += nonzero
        observation["sha256"] = hashlib.sha256(raw).hexdigest()
        observation["nonzero_byte_count"] = nonzero
        observation["structure"]["classification"] = "UNIDENTIFIED_BYTES" if nonzero else "ZERO_FILLED"
    graph["byte_accounting"]["structural_nonzero_bytes"] = total_nonzero
    # This is a different internally valid graph with coherent individual page
    # hashes. The unchanged independently measured aggregate must reject it.
    assert q.detached_freelist_candidate_evidence(report, pages, contents, digest, time.monotonic() + 10) is False


def test_detached_predicate_checks_deadline(detached_witness):
    report, pages, contents, digest = detached_witness
    with pytest.raises(q.RecoveryError, match="QUALIFICATION_DEADLINE_EXHAUSTED"):
        q.detached_freelist_candidate_evidence(report, pages, contents, digest, time.monotonic() - 1)


@pytest.mark.parametrize("defect", ["original_bytes", "inspection_bytes", "original_empty_companion", "inspection_empty_companion"])
def test_detached_candidate_rejects_changed_input_after_native_candidate(originals, tmp_path, monkeypatch, defect):
    path = originals["gdw"]
    detached_freelist_pages(path)
    native = q.logical_fingerprint
    calls = 0
    def changed(connection, label, deadline):
        nonlocal calls
        calls += 1
        value = native(connection, label, deadline)
        if calls == 2:
            target = path if defect.startswith("original") else tmp_path / "working" / label / "inspection" / path.name
            if defect.endswith("companion"):
                target.with_name(target.name + "-journal").write_bytes(b"")
            else:
                raw = bytearray(target.read_bytes())
                raw[-1] ^= 1
                target.write_bytes(raw)
        return value
    monkeypatch.setattr(q, "logical_fingerprint", changed)
    report = qualify("gdw", originals, tmp_path)
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False
    assert report["diagnostic_code"] in {"DETACHED_FREELIST_INPUT_CHANGED", "CAPTURED_ORIGINAL_CHANGED"}
    assert "detached_freelist_candidate_contract" not in report


def test_native_detached_vacuum_failure_is_retained_as_a_hold(originals, tmp_path, monkeypatch):
    path = originals["gdw"]
    detached_freelist_pages(path)
    before = path.read_bytes()
    readonly = q.readonly
    class RejectVacuum:
        def __init__(self, connection): self.connection = connection
        def __getattr__(self, name): return getattr(self.connection, name)
        def execute(self, sql, *args):
            if sql.startswith("VACUUM INTO"):
                raise sqlite3.DatabaseError(PRIVATE)
            return self.connection.execute(sql, *args)
    monkeypatch.setattr(q, "readonly", lambda path, deadline: RejectVacuum(readonly(path, deadline)))
    report = qualify("gdw", originals, tmp_path)
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False
    assert report["diagnostic_code"] == "QUALIFICATION_UNAVAILABLE"
    assert path.read_bytes() == before and PRIVATE not in json.dumps(report)
    assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()


@pytest.mark.parametrize("entry", ["file", "empty_file", "directory", "dangling_symlink", "existing_symlink"])
@pytest.mark.parametrize("late", [False, True])
def test_detached_candidate_destination_is_absent_without_following_links(originals, tmp_path, monkeypatch, entry, late):
    original = originals["gdw"]
    detached_freelist_pages(original)
    original_bytes = original.read_bytes()
    target = tmp_path / "outside-candidate-target.sqlite3"
    if entry == "existing_symlink":
        target.write_bytes(b"owned-existing-canary")
    expected_target = target.read_bytes() if target.exists() else None
    require_absent = q._require_absent_candidate
    calls = 0
    def placed(candidate):
        nonlocal calls
        calls += 1
        if calls == (2 if late else 1):
            if entry == "file": candidate.write_bytes(b"owned-existing-candidate")
            elif entry == "empty_file": candidate.write_bytes(b"")
            elif entry == "directory": candidate.mkdir()
            else: candidate.symlink_to(target)
        require_absent(candidate)
    monkeypatch.setattr(q, "_require_absent_candidate", placed)
    report = qualify("gdw", originals, tmp_path)
    assert calls == (2 if late else 1)
    assert report["diagnostic_code"] == "CANDIDATE_DESTINATION_EXISTS"
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False
    assert original.read_bytes() == original_bytes
    if expected_target is None:
        assert not target.exists()
    else:
        assert target.read_bytes() == expected_target


@pytest.mark.parametrize("field", ["expected", "observation", "aggregate", "page", "attached"])
def test_detached_predicate_rejects_placeholder_zero_digest(detached_witness, field):
    report, pages, contents, digest = detached_witness
    if field == "expected": digest = "0" * 64
    elif field == "observation": report["inspection_sha256"] = "0" * 64
    elif field == "aggregate": contents["contents_sha256"] = report["orphan_contents_sha256"] = "0" * 64
    elif field == "page": report["pages"][0]["sha256"] = "0" * 64
    else: report["freelist_graph"]["attached_freelist"]["page_numbers_sha256"] = "0" * 64
    assert q.detached_freelist_candidate_evidence(report, pages, contents, digest, time.monotonic() + 10) is False


def test_exact_reachable_page_duplicate_does_not_admit_discard_or_vacuum(originals, tmp_path):
    path = originals["gdw"]
    with sqlite3.connect(path) as db:
        if db.execute("SELECT sqlite_compileoption_used('ENABLE_DBSTAT_VTAB')").fetchone() != (1,):
            pytest.skip("native dbstat is unavailable in this interpreter")
        page = db.execute("SELECT pageno FROM dbstat('main') WHERE name='receipts' AND pagetype='leaf'").fetchone()[0]
    raw = bytearray(path.read_bytes())
    page_size = int.from_bytes(raw[16:18], "big")
    duplicate = raw[(page - 1) * page_size:page * page_size]
    assert any(duplicate)
    raw[28:32] = (len(raw) // page_size + 1).to_bytes(4, "big")
    raw.extend(duplicate)
    path.write_bytes(raw)
    report = qualify("gdw", originals, tmp_path)
    forensic = report["unreferenced_page_forensics"]
    assert forensic["native_reachability"]["complete"] is True
    assert forensic["pages"][0]["reachable_duplicate"]["state"] == "EXACT_FULL_PAGE_MATCH"
    assert forensic["record_equivalence_verified"] is False
    assert forensic["discard_admitted"] is False and forensic["candidate_created"] is False
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"
    assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()


@pytest.mark.parametrize("defect", ["database_identity", "page_identity", "candidate", "payload", "shape"])
def test_forensic_report_cannot_substitute_identity_or_admission(originals, tmp_path, monkeypatch, defect):
    path = originals["gdw"]
    unused_pages(path)
    raw = bytearray(path.read_bytes())
    raw[-len(PRIVATE):] = PRIVATE.encode()
    path.write_bytes(raw)
    native = q.orphan_forensics.inspect_orphan_pages
    def changed(*args, **kwargs):
        value = native(*args, **kwargs)
        if defect == "database_identity": value["inspection_sha256"] = "f" * 64
        elif defect == "page_identity": value["orphan_contents_sha256"] = "f" * 64
        elif defect == "candidate": value["candidate_created"] = True
        elif defect == "payload": value["unreviewed_private_field"] = PRIVATE
        else: value = {"private_error": PRIVATE}
        return value
    monkeypatch.setattr(q.orphan_forensics, "inspect_orphan_pages", changed)
    report = qualify("gdw", originals, tmp_path)
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False
    assert report["diagnostic_code"] in {"ORPHAN_FORENSIC_INPUT_IDENTITY_MISMATCH", "ORPHAN_FORENSIC_RESULT_UNQUALIFIED"}
    assert "unreferenced_page_forensics" not in report
    assert PRIVATE not in json.dumps(report)
    assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()


def test_unavailable_forensics_retains_reachable_evidence_and_recovery_hold(originals, tmp_path, monkeypatch):
    path = originals["gdw"]
    unused_pages(path)
    raw = bytearray(path.read_bytes())
    raw[-len(PRIVATE):] = PRIVATE.encode()
    path.write_bytes(raw)
    monkeypatch.setattr(q.orphan_forensics, "inspect_orphan_pages",
                        lambda *args, **kwargs: q.orphan_forensics._held("DBSTAT_UNAVAILABLE"))
    report = qualify("gdw", originals, tmp_path)
    assert report["unreferenced_page_forensics"]["analysis_state"] == "UNAVAILABLE"
    assert report["original_receipts"]["binding_errors"] == 0
    assert report["diagnostic_code"] == "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"
    assert report["state"] == "UNQUALIFIED" and report["restore_admitted"] is False


@pytest.mark.parametrize("pages", [[0], [-1], [10**20], [True], [1, 1], list(range(1, 101))])
def test_orphan_page_reader_rejects_unbounded_or_ambiguous_page_numbers(originals, pages):
    with pytest.raises(q.RecoveryError, match="UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW"):
        q.unreferenced_page_contents(originals["gdw"], pages, time.monotonic() + 10)


@pytest.mark.parametrize("step", [False, 0.0, "0"])
def test_receipt_binding_rejects_equal_looking_different_json_types(originals, tmp_path, step):
    path = originals["gdw"]
    with sqlite3.connect(path) as connection:
        receipt = json.loads(connection.execute("SELECT receipt_json FROM receipts").fetchone()[0])
        receipt.pop("receipt_hash")
        receipt["step"] = step
        digest = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        receipt["receipt_hash"] = digest
        connection.execute("UPDATE receipts SET receipt_hash=?,receipt_json=?", (digest, json.dumps(receipt)))
    report = qualify("gdw", originals, tmp_path)
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "ORIGINAL_RECEIPT_BINDINGS_INVALID"
    assert report["original_receipts"]["digest_errors"] == 0
    assert report["original_receipts"]["binding_errors"] == 1
    assert not (tmp_path / "working" / "gdw" / "candidate.sqlite3").exists()


@pytest.fixture
def historical_fixture(originals, tmp_path, monkeypatch):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    # Only this offline fixture generates an ephemeral key. The production
    # helper loads one fixed public PEM and never imports a signer or runtime.
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    key_root = tmp_path / "keys"
    key_path = key_root / q.PINNED_KEY_PATH
    key_path.parent.mkdir(parents=True)
    key_path.write_bytes(pem)
    monkeypatch.setattr(q, "ROOT", key_root)
    monkeypatch.setattr(q, "PINNED_KEY_DER_SHA256", hashlib.sha256(der).hexdigest())
    anchors = json.loads((ROOT / "docs/operations/evidence/gdw-recovery-historical-anchors.json").read_text())
    anchors["source_revision"] = "e" * 40
    recovery_id = "gdw-proof-" + "e" * 12 + "-" + GDW_GENERATION[:12] + "-1"
    governance = {"binding_sha256": "f" * 64, "private_note": PRIVATE}
    outcome = {key: 0 for key in q.AUDIT_OUTCOME_FIELDS}
    outcome.update(schema="szl.gdw.transient-effect-recovery/v2", status="NO_ELIGIBLE_EFFECTS",
                   recovery_id=recovery_id, source_revision=anchors["source_revision"], requested_limit=1,
                   failure_class="hf-hard-link-enotsup/v1", database_generation_id=GDW_GENERATION,
                   selection=[], selection_sha256=q._native_digest([]), sqlite_integrity="ok",
                   credential_values_recorded=False)
    operator = {"namespace": "a11oy", "owner_id": "gdw-operator", "credential_key_id": "fixture-public-key"}
    request = {"schema": "szl.gdw.transient-effect-recovery-request/v1", **operator,
               "recovery_id": recovery_id, "source_revision": anchors["source_revision"],
               "database_generation_id": GDW_GENERATION, "limit": 1,
               "failure_class": outcome["failure_class"], "governance_binding_sha256": governance["binding_sha256"]}
    payload = {"schema": "szl.gdw.transient-effect-recovery-receipt/v2", "operator": operator,
               "recovery_id": recovery_id, "source_revision": anchors["source_revision"],
               "database_generation_id": GDW_GENERATION, "request_sha256": q._native_digest(request),
               "outcome_sha256": q._native_digest(outcome), "governance_sha256": q._native_digest(governance),
               "selection_sha256": outcome["selection_sha256"], "rescheduled_effects": 0,
               "attempts_before": 0, "attempts_after": 0, "sequence": 87,
               "previous_receipt_sha256": "1" * 64, "previous_chain_sha256": "2" * 64,
               "atomic_with_mutation": True, "created_at": "2026-10-03T00:00:00+00:00",
               "credential_values_recorded": False}
    body, ptype = q._canonical(payload), q.KHIPU_RECEIPT_TYPE.encode()
    pae = b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " + str(len(body)).encode() + b" " + body
    envelope = {"signed": True, "payloadType": q.KHIPU_RECEIPT_TYPE,
                "payload": base64.b64encode(body).decode(),
                "signatures": [{"keyid": "offline-fixture", "sig": base64.b64encode(
                    private_key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode()}]}
    receipt = {**payload, "receipt_status": "SIGNED_KHIPU_DSSE", "receipt_sha256": q._native_digest(payload),
               "dsse_envelope_sha256": q._native_digest(envelope), "dsse_envelope": envelope}
    receipt["chain_sha256"] = q._native_digest({key: receipt[key] for key in (
        "previous_chain_sha256", "receipt_sha256", "receipt_status", "dsse_envelope_sha256")})
    report = {**outcome, "governance": governance, "audit_receipt": receipt, "replayed": False}
    row = {**operator, **{key: receipt[key] for key in ("recovery_id", "sequence", "database_generation_id",
           "request_sha256", "outcome_sha256", "governance_sha256", "receipt_sha256", "previous_receipt_sha256",
           "previous_chain_sha256", "chain_sha256", "dsse_envelope_sha256", "created_at")},
           "report_json": json.dumps(report)}
    with sqlite3.connect(originals["gdw"]) as connection:
        connection.execute("INSERT INTO effect_recovery_audit (" + ",".join(row) + ") VALUES ("
                           + ",".join("?" for _ in row) + ")", tuple(row.values()))
    with sqlite3.connect(originals["series_a"]) as connection:
        series_hash = connection.execute("SELECT receipt_hash FROM receipts WHERE sequence=3").fetchone()[0]
    anchors["gdw"].update(database_generation_id=GDW_GENERATION, recovery_id=recovery_id,
                          receipt_sha256=receipt["receipt_sha256"], chain_sha256=receipt["chain_sha256"],
                          pinned_key_der_sha256=q.PINNED_KEY_DER_SHA256)
    anchors["series_a"].update(database_generation_id=SERIES_GENERATION,
                               storage_created_at="2026-10-04T00:00:00.000Z", sequence=3,
                               minimum_receipt_count=2, receipt_sha256=series_hash)
    return anchors


def test_source_reviewed_anchor_document_matches_exact_capture_bytes_and_public_key():
    from cryptography.hazmat.primitives import serialization
    reference, raw = q.read_reference_bytes(ROOT / "docs/operations/evidence/gdw-capture-37223162231.json")
    anchors = q.read_reference(ROOT / "docs/operations/evidence/gdw-recovery-historical-anchors.json")
    q.validate_historical_anchors(anchors, reference, hashlib.sha256(raw).hexdigest())
    key = serialization.load_pem_public_key((ROOT / q.PINNED_KEY_PATH).read_bytes())
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    assert hashlib.sha256(der).hexdigest() == q.PINNED_KEY_DER_SHA256
    assert anchors["gdw"]["sequence"] == 87 and anchors["series_a"]["sequence"] == 46686


@pytest.mark.parametrize("label", ["gdw", "series_a"])
@pytest.mark.parametrize("detached", [False, True])
def test_historical_anchor_is_verified_in_original_and_candidate(originals, tmp_path, historical_fixture, label, detached):
    if detached:
        detached_freelist_pages(originals[label])
    before = originals[label].read_bytes()
    report = qualify(label, originals, tmp_path, historical_anchors=historical_fixture)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    assert report["historical_anchor_state"] == "VERIFIED"
    assert report["original_historical_anchor"] == report["candidate_historical_anchor"]
    expected = "VERIFIED_PINNED_PUBLIC_KEY" if label == "gdw" else "NOT_PERFORMED"
    assert report["original_historical_anchor"]["signature_verification"] == expected
    assert originals[label].read_bytes() == before and PRIVATE not in json.dumps(report)


def test_generic_internal_qualification_does_not_claim_historical_verification(originals, tmp_path):
    report = qualify("gdw", originals, tmp_path)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED"
    assert report["historical_anchor_state"] == "NOT_CHECKED"
    assert report["original_historical_anchor"]["state"] == "NOT_CHECKED"


@pytest.mark.parametrize("change", ["missing", "scope", "sequence", "receipt_hash", "chain_hash", "generation",
                                   "payload_type", "source", "bool_sequence", "outcome", "governance", "envelope"])
def test_changed_historical_gdw_row_or_report_is_rejected(originals, tmp_path, historical_fixture, change):
    with sqlite3.connect(originals["gdw"]) as connection:
        if change == "missing":
            connection.execute("DELETE FROM effect_recovery_audit")
        elif change in {"scope", "sequence", "receipt_hash", "chain_hash", "generation"}:
            column, value = {"scope": ("owner_id", "other"), "sequence": ("sequence", 88),
                             "receipt_hash": ("receipt_sha256", "f" * 64), "chain_hash": ("chain_sha256", "f" * 64),
                             "generation": ("database_generation_id", "f" * 32)}[change]
            connection.execute(f"UPDATE effect_recovery_audit SET {column}=?", (value,))
        else:
            report = json.loads(connection.execute("SELECT report_json FROM effect_recovery_audit").fetchone()[0])
            if change == "payload_type":
                report["audit_receipt"]["dsse_envelope"]["payloadType"] = "other"
            elif change == "source":
                report["audit_receipt"]["source_revision"] = "f" * 40
            elif change == "bool_sequence":
                report["audit_receipt"]["sequence"] = True
            elif change == "outcome":
                report["eligible_effects"] = 1
            elif change == "governance":
                report["governance"]["binding_sha256"] = "e" * 64
            else:
                report["audit_receipt"]["dsse_envelope"]["signatures"][0]["sig"] = base64.b64encode(PRIVATE.encode()).decode()
            connection.execute("UPDATE effect_recovery_audit SET report_json=?", (json.dumps(report),))
    report = qualify("gdw", originals, tmp_path, historical_anchors=historical_fixture)
    assert report["state"] == "UNQUALIFIED", report
    assert report["diagnostic_code"].startswith("HISTORICAL_")
    assert PRIVATE not in json.dumps(report)
    assert not (tmp_path / "working/gdw/candidate.sqlite3").exists()


@pytest.mark.parametrize("change", ["missing", "hash", "generation", "created", "count"])
def test_series_a_history_is_bound_to_generation_creation_count_and_exact_row(originals, tmp_path, historical_fixture, change):
    anchor = historical_fixture["series_a"]
    if change == "missing":
        anchor["sequence"] = 2
    elif change == "hash":
        anchor["receipt_sha256"] = "f" * 64
    elif change == "generation":
        anchor["database_generation_id"] = "store_" + "f" * 32
    elif change == "created":
        anchor["storage_created_at"] = "2026-10-03T00:00:00.000Z"
    else:
        anchor["minimum_receipt_count"] = 3
    report = qualify("series_a", originals, tmp_path, historical_anchors=historical_fixture)
    assert report["state"] == "UNQUALIFIED", report
    assert report["diagnostic_code"].startswith("HISTORICAL_")


@pytest.mark.parametrize("change", ["capture_hash", "source", "workflow_type", "gdw_sequence_type",
                                   "series_sequence_type", "count_type", "missing", "key_pin", "key_path", "generation"])
def test_invalid_historical_reference_fails_before_provider_reads(capture, tmp_path, historical_fixture, change):
    hub, reference = capture
    anchors = historical_fixture
    raw = p._json_bytes(reference)
    digest = hashlib.sha256(raw).hexdigest()
    anchors["capture_report_sha256"] = digest
    if change == "capture_hash":
        digest = hashlib.sha256(raw + b"\n").hexdigest()
    elif change == "source":
        anchors["source_revision"] = "0" * 40
    elif change == "workflow_type":
        anchors["workflow_attempt"] = True
    elif change == "gdw_sequence_type":
        anchors["gdw"]["sequence"] = 87.0
    elif change == "series_sequence_type":
        anchors["series_a"]["sequence"] = True
    elif change == "count_type":
        anchors["series_a"]["minimum_receipt_count"] = 2.0
    elif change == "missing":
        del anchors["gdw"]["chain_sha256"]
    elif change == "key_pin":
        anchors["gdw"]["pinned_key_der_sha256"] = "f" * 64
    elif change == "key_path":
        anchors["gdw"]["pinned_key_path"] = "private-key.pem"
    else:
        anchors["gdw"]["database_generation_id"] = "f" * 32
    def no_reads():
        pytest.fail("invalid historical evidence must fail before ownership/provider reads")
    report = q.qualify_capture(q.ReadOnlyCaptureHub(hub), reference, tmp_path / "qualification", no_reads,
                               time.monotonic() + 30, historical_anchors=anchors, capture_report_sha256=digest)
    assert report["state"] == "BLOCKED", report
    assert report["diagnostic_code"].startswith("HISTORICAL_")
    assert not (tmp_path / "qualification").exists()


@pytest.mark.parametrize("change", ["signature", "payload_boolean", "embedded_key", "pinned_file", "late_key_read"])
def test_public_key_verifier_cannot_accept_forged_or_late_envelopes(originals, historical_fixture, monkeypatch, change):
    with sqlite3.connect(originals["gdw"]) as connection:
        report = json.loads(connection.execute("SELECT report_json FROM effect_recovery_audit").fetchone()[0])
    receipt = report["audit_receipt"]
    payload = {key: receipt[key] for key in q.AUDIT_PAYLOAD_FIELDS}
    envelope = receipt["dsse_envelope"]
    deadline = time.monotonic() + 30
    if change in {"signature", "embedded_key"}:
        envelope["signatures"][0]["sig"] = base64.b64encode(b"invalid signature").decode()
        if change == "embedded_key":
            envelope["public_key"] = PRIVATE
    elif change == "payload_boolean":
        altered = dict(payload, rescheduled_effects=False)
        envelope["payload"] = base64.b64encode(q._canonical(altered)).decode()
    elif change == "pinned_file":
        monkeypatch.setattr(q, "PINNED_KEY_DER_SHA256", "f" * 64)
    else:
        clock = [0.0]
        deadline = 10.0
        monkeypatch.setattr(q.time, "monotonic", lambda: clock[0])
        read = q._bounded_file
        def late(*args):
            value = read(*args)
            clock[0] = 11.0
            return value
        monkeypatch.setattr(q, "_bounded_file", late)
    with pytest.raises(q.RecoveryError) as exc:
        q._verify_anchor_envelope(envelope, payload, deadline)
    assert PRIVATE not in str(exc.value)
    if change == "late_key_read":
        assert exc.value.code == "QUALIFICATION_DEADLINE_EXHAUSTED"


@pytest.mark.parametrize("label", ["gdw", "series_a"])
def test_nonzero_orphan_stop_retains_verified_original_history(originals, tmp_path, historical_fixture, label):
    unused_pages(originals[label])
    raw = bytearray(originals[label].read_bytes())
    raw[-len(PRIVATE):] = PRIVATE.encode()
    originals[label].write_bytes(raw)
    report = qualify(label, originals, tmp_path, historical_anchors=historical_fixture)
    assert report["diagnostic_code"] == "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW", report
    assert report["original_historical_anchor"]["state"] == "VERIFIED"
    assert report["original_logical_state"]["logical_sha256"]
    assert report["original_receipts"]["row_count"] > 0
    assert "candidate_historical_anchor" not in report
    assert not (tmp_path / "working" / label / "candidate.sqlite3").exists()
    assert originals[label].read_bytes() == raw and PRIVATE not in json.dumps(report)


@pytest.mark.parametrize("kind", ["fifo", "symlink", "oversize", "duplicate", "nonfinite"])
def test_historical_input_reader_is_bounded_and_strict(tmp_path, kind):
    path = tmp_path / "anchors.json"
    if kind == "fifo":
        q.os.mkfifo(path)
    elif kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text("{}")
        path.symlink_to(target)
    elif kind == "oversize":
        path.write_bytes(b" " * (q.MAX_REFERENCE_BYTES + 1))
    elif kind == "duplicate":
        path.write_text('{"schema":1,"schema":2}')
    else:
        path.write_text('{"sequence":NaN}')
    started = time.monotonic()
    with pytest.raises(q.RecoveryError):
        q.read_reference(path)
    assert time.monotonic() - started < 1


def test_cli_requires_historical_anchor_argument(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["qualify", "--capture-report", str(tmp_path / "capture.json"),
                                     "--output", str(tmp_path / "report.json")])
    with pytest.raises(SystemExit) as exc:
        q.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("label", ["gdw", "series_a"])
@pytest.mark.parametrize("detached", [False, True])
def test_history_is_rechecked_after_candidate_logical_fingerprint(originals, tmp_path, historical_fixture, monkeypatch, label, detached):
    if detached:
        detached_freelist_pages(originals[label])
    verify = q.historical_anchor
    calls = []
    def altered(connection, store, generation, anchors, deadline):
        calls.append(store)
        if len(calls) == 2:
            with sqlite3.connect(tmp_path / "working" / label / "candidate.sqlite3") as candidate:
                if label == "gdw":
                    candidate.execute("DELETE FROM effect_recovery_audit")
                else:
                    candidate.execute("DELETE FROM metadata WHERE key='storage_created_at'")
        return verify(connection, store, generation, anchors, deadline)
    monkeypatch.setattr(q, "historical_anchor", altered)
    report = qualify(label, originals, tmp_path, historical_anchors=historical_fixture)
    assert report["state"] == "UNQUALIFIED", report
    assert report["original_historical_anchor"]["state"] == "VERIFIED"
    assert report["diagnostic_code"].startswith("HISTORICAL_") and len(calls) == 2


def test_exact_capture_qualifies_with_historical_anchors_without_provider_writes(originals, tmp_path, historical_fixture):
    hub = fixtures.FakeHub({path: originals[label].read_bytes() for label, path in p.DATABASES.items()})
    reference = p.preserve(hub, source_sha="a" * 40, run_id="37216937874", run_attempt="1",
                           nonce="b" * 32, workspace=tmp_path / "preservation",
                           require_owned_source=lambda: None, sleep=lambda _: None)
    digest = hashlib.sha256(p._json_bytes(reference)).hexdigest()
    historical_fixture["capture_report_sha256"] = digest
    batches, remote = len(hub.batch_calls), dict(hub.files)
    report = q.qualify_capture(q.ReadOnlyCaptureHub(hub), reference, tmp_path / "qualification", lambda: None,
                               time.monotonic() + 30, historical_anchors=historical_fixture, capture_report_sha256=digest)
    assert report["state"] == "LOGICAL_CONTINUITY_VERIFIED", report
    assert report["historical_anchor_state"] == report["captured_historical_anchor_state"] == "VERIFIED"
    assert report["historical_anchor_reference"]["capture_report_sha256"] == digest
    assert report["provider_writes_performed"] is False and report["restore_admitted"] is False
    assert report["later_acknowledged_writes_verified"] is False
    assert len(hub.batch_calls) == batches and hub.files == remote
    assert PRIVATE not in json.dumps(report)


def test_fence_lookup_only_returns_safe_private_dataset_metadata():
    calls = []
    group = {"id": "PRIVATE_GROUP_ID", "name": PRIVATE}
    class MetadataHub:
        def dataset_info(self, **kwargs):
            calls.append(kwargs)
            return {"id": p.BUCKET, "private": True, "sha": "b" * 40, "resource_group": group}
    report = q.fence_metadata(MetadataHub(), time.monotonic() + 10)
    assert report["state"] == "METADATA_ONLY_OBSERVED"
    assert report["revision"] == "b" * 40 and report["resource_group_present"] is True
    assert report["resource_group_observation_sha256"] == hashlib.sha256(p._json_bytes(group)).hexdigest()
    assert report["bucket_dataset_audience_equivalence"] == "NOT_ESTABLISHED"
    assert report["write_capability"] == "NOT_TESTED" and report["provider_writes_performed"] is False
    assert calls == [{"repo_id": p.BUCKET, "revision": "main", "expand": ["sha", "private", "resourceGroup"]}]
    assert PRIVATE not in json.dumps(report) and "PRIVATE_GROUP_ID" not in json.dumps(report)


@pytest.mark.parametrize("change", [{"private": False}, {"private": None}, {"id": "untrusted/other"},
                                    {"sha": "0" * 40}, {"sha": "main"}, {"resource_group": PRIVATE}])
def test_fence_unknown_or_changed_private_metadata_never_qualifies(change):
    class MetadataHub:
        def dataset_info(self, **kwargs):
            return dict({"id": p.BUCKET, "private": True, "sha": "b" * 40, "resource_group": None}, **change)
    report = q.fence_metadata(MetadataHub(), time.monotonic() + 10)
    assert report["state"] == "UNQUALIFIED" and "revision" not in report
    assert PRIVATE not in json.dumps(report)


def test_absent_resource_group_is_an_observation_not_audience_proof():
    class MetadataHub:
        def dataset_info(self, **kwargs):
            return {"id": p.BUCKET, "private": True, "sha": "b" * 40, "resource_group": None}
    report = q.fence_metadata(MetadataHub(), time.monotonic() + 10)
    assert report["resource_group_present"] is False
    assert report["resource_group_observation"] == "NONE_RETURNED"
    assert report["bucket_dataset_audience_equivalence"] == "NOT_ESTABLISHED"


def test_optional_fence_lookup_redacts_errors_but_cannot_hide_a_deadline(monkeypatch):
    clock = [1.0]
    monkeypatch.setattr(q.time, "monotonic", lambda: clock[0])
    class MetadataHub:
        def dataset_info(self, **kwargs):
            raise RuntimeError(PRIVATE)
    report = q.fence_metadata(MetadataHub(), 2.0)
    assert report["state"] == "UNQUALIFIED" and PRIVATE not in json.dumps(report)
    class SlowMetadataHub:
        def dataset_info(self, **kwargs):
            clock[0] = 3.0
            raise RuntimeError(PRIVATE)
    with pytest.raises(q.RecoveryError, match="QUALIFICATION_DEADLINE_EXHAUSTED"):
        q.fence_metadata(SlowMetadataHub(), 2.0)


def test_unkeyed_application_table_cannot_qualify_hidden_rowid_changes(originals, tmp_path):
    path = originals["series_a"]
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE events RENAME TO former_events")
        connection.execute("CREATE TABLE events AS SELECT * FROM former_events")
        connection.execute("DROP TABLE former_events")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
    original = path.read_bytes()
    report = qualify("series_a", originals, tmp_path)
    assert report["state"] == "UNQUALIFIED"
    assert report["diagnostic_code"] == "UNQUALIFIED_STORE_SCHEMA"
    assert not (tmp_path / "working" / "series_a" / "candidate.sqlite3").exists()
    assert path.read_bytes() == original
