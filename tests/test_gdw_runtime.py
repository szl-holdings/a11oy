import errno
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import gdw_proofs
import gdw_runtime
from gdw_proofs import (
    build_proof_payload,
    export_proof_payload,
    export_receipt_projection,
    sha256_json,
)
from gdw_workspace import GDWConfigurationError, GDWWorkspace


def _persistent_environment(monkeypatch, tmp_path):
    mount = tmp_path / "data"
    mount.mkdir()
    monkeypatch.setenv(
        "GDW_DB_PATH",
        str(mount / "a11oy" / "gdw" / "gdw.sqlite3"),
    )
    monkeypatch.setenv(
        "GDW_PROOF_DIR",
        str(mount / "a11oy" / "gdw" / "proofs"),
    )
    monkeypatch.setenv(
        "GDW_RECEIPT_PROJECTION_DIR",
        str(mount / "a11oy" / "gdw" / "receipts"),
    )
    monkeypatch.setenv("GDW_REQUIRE_PERSISTENT_STORAGE", "1")
    monkeypatch.setenv("GDW_REQUIRED_MOUNT", str(mount))
    monkeypatch.setenv("GDW_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("GDW_SQLITE_SYNCHRONOUS", "FULL")
    monkeypatch.setenv("GDW_PROOF_EXPORT_MODE", "outbox")
    return mount


def test_prepare_runtime_fails_closed_without_attached_mount(
    monkeypatch,
    tmp_path,
):
    _persistent_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(gdw_runtime.os.path, "ismount", lambda _path: False)

    with pytest.raises(
        gdw_runtime.GDWRuntimeError,
        match="storage mount is not attached",
    ):
        gdw_runtime.prepare_runtime()


def test_prepare_runtime_selects_network_safe_journal_and_reports_truth(
    monkeypatch,
    tmp_path,
):
    _persistent_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(gdw_runtime.os.path, "ismount", lambda _path: True)

    observed = gdw_runtime.prepare_runtime()

    assert observed["mount_verified"] is True
    assert observed["persistence_required"] is True
    assert observed["journal_mode_requested"] == "DELETE"
    assert observed["journal_mode_observed"] == "DELETE"
    assert observed["proof_export_mode"] == "outbox"
    assert observed["legacy_link_failures_requeued"] == 0
    with sqlite3.connect(observed["database_path"]) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    health = gdw_runtime.runtime_health()
    assert health["startup_state"] == "READY"
    assert health["evidence_label"] == "VERIFIED"
    assert health["storage"]["sqlite_integrity"] == "ok"


def test_prepare_runtime_rejects_synchronous_export(monkeypatch, tmp_path):
    _persistent_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(gdw_runtime.os.path, "ismount", lambda _path: True)
    monkeypatch.setenv("GDW_PROOF_EXPORT_MODE", "sync")

    with pytest.raises(
        gdw_runtime.GDWRuntimeError,
        match="must be 'outbox'",
    ):
        gdw_runtime.prepare_runtime()


def _queued_proof(workspace, request_id="request-1"):
    request_digest = "b" * 64
    response = {
        "request_id": request_id,
        "request_digest": request_digest,
        "database_generation_id": workspace.database_generation_id,
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "b" * 64,
        "decision": "REJECT",
        "scheduler_mode": "kda_local",
        "receipt_hash": None,
        "dry_run": True,
        "audit": {
            "governance": {
                "allowed": False,
                "policy": "test",
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
            }
        },
        "principal": {
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "key_id": "test-key",
        },
    }
    response["proposal_id"] = sha256_json(
        {
            "schema": "szl.gdw.proposal-identity/v1",
            "database_generation_id": workspace.database_generation_id,
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "request_id": request_id,
            "request_digest": request_digest,
            "state_before_hash": response["state_before_hash"],
            "governance_evidence_sha256": sha256_json(
                response["audit"]["governance"]
            ),
        }
    )
    payload = build_proof_payload(
        proposal_id=response["proposal_id"],
        request_id=response["request_id"],
        request_digest=request_digest,
        namespace=workspace.namespace,
        owner_id=workspace.owner_id,
        database_generation_id=workspace.database_generation_id,
        step=response["step"],
        before_hash=response["state_before_hash"],
        after_hash=response["state_hash"],
        decision=response["decision"],
        scheduler_mode=response["scheduler_mode"],
        receipt_hash="",
        dry_run=response["dry_run"],
        governance=response["audit"]["governance"],
    )
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            request_id,
            request_digest,
            "session-1",
            response,
            sha256_json(response),
            "2026-07-28T00:00:00+00:00",
        )
        key = workspace.save_effect_outbox(
            connection,
            request_id,
            "proof_export",
            payload,
            payload["payload_sha256"],
            None,
            "2026-07-28T00:00:00+00:00",
        )
    connection = workspace._connect()
    try:
        return connection.execute(
            """
            SELECT intent_sha256 FROM effect_outbox
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (workspace.namespace, workspace.owner_id, key),
        ).fetchone()["intent_sha256"]
    finally:
        connection.close()


def test_drain_once_exports_a_bounded_effect(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    intent_sha256 = _queued_proof(workspace)

    report = gdw_runtime.drain_once(
        limit=1,
        lease_seconds=30,
        worker_id="test-worker",
        workspace=workspace,
    )

    assert report["attempted"] == 1
    assert report["exported"] == 1
    assert report["failed"] == 0
    assert report["pending_effects"] == 0
    owner_scope = hashlib.sha256(workspace.owner_id.encode()).hexdigest()[:32]
    assert (
        tmp_path / "proofs" / owner_scope / f"{intent_sha256}.json"
    ).is_file()


def test_exported_artifact_tamper_fails_integrity(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)
    assert gdw_runtime.drain_once(
        worker_id="tamper-proof-worker",
        workspace=workspace,
    )["exported"] == 1
    artifact_path = next((tmp_path / "proofs").rglob("*.json"))
    artifact_path.write_text('{"tampered":true}\n', encoding="utf-8")

    integrity = workspace.integrity()

    assert integrity["ok"] is False
    assert integrity["invalid_exported_artifacts"] == 1


def test_effect_completion_rejects_wrong_artifact_identity(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)
    claim = workspace.claim_effects("binding-worker")[0]
    artifact = gdw_runtime._export_effect(workspace, claim)
    artifact["artifact_identity"] = "0" * 64

    with pytest.raises(
        GDWConfigurationError,
        match="artifact_identity_mismatch",
    ):
        workspace.mark_effect_exported(
            claim["idempotency_key"],
            "binding-worker",
            claim["claim_generation"],
            artifact,
            "2026-07-28T00:00:01+00:00",
        )

    assert workspace.integrity()["claimed_effects"] == 1


def test_owner_artifact_quota_is_enforced(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    monkeypatch.setenv("GDW_OWNER_MAX_ARTIFACTS", "1")
    monkeypatch.setenv("GDW_GLOBAL_MAX_ARTIFACTS", "2")
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 64,
        "request_id": "request-1",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    export_proof_payload(payload)
    second = dict(payload)
    second["request_id"] = "request-2"
    second.pop("payload_sha256")
    second["payload_sha256"] = sha256_json(second)

    with pytest.raises(RuntimeError, match="per-owner artifact quota"):
        export_proof_payload(second)


def test_database_generation_changes_effect_artifact_identity(tmp_path):
    first = GDWWorkspace(str(tmp_path / "first.sqlite3"))
    second = GDWWorkspace(str(tmp_path / "second.sqlite3"))

    first_intent = _queued_proof(first, request_id="same-request")
    second_intent = _queued_proof(second, request_id="same-request")

    assert first.database_generation_id != second.database_generation_id
    assert first_intent != second_intent


def test_failed_drain_releases_claim_for_retry(monkeypatch, tmp_path):
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)

    def fail_export(_workspace, _row):
        raise OSError("temporary projection failure")

    monkeypatch.setattr(gdw_runtime, "_export_effect", fail_export)
    report = gdw_runtime.drain_once(
        limit=1,
        lease_seconds=30,
        worker_id="test-worker",
        workspace=workspace,
    )

    assert report["failed"] == 1
    assert report["pending_effects"] == 1
    integrity = workspace.integrity()
    assert integrity["claimed_effects"] == 0


def test_drain_rejects_a_payload_rebound_to_a_claimed_row(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)
    connection = workspace._connect()
    try:
        row = connection.execute(
            """
            SELECT idempotency_key, payload_json FROM effect_outbox
            WHERE namespace = ? AND owner_id = ?
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload["formal_status"] = "ATTACKER_REBOUND"
        payload.pop("payload_sha256")
        payload["payload_sha256"] = sha256_json(payload)
        connection.execute(
            """
            UPDATE effect_outbox SET payload_json = ?
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                workspace.namespace,
                workspace.owner_id,
                row["idempotency_key"],
            ),
        )
    finally:
        connection.close()

    integrity = workspace.integrity()
    report = gdw_runtime.drain_once(
        worker_id="tamper-worker",
        workspace=workspace,
    )

    assert integrity["ok"] is False
    assert integrity["invalid_effect_bindings"] == 1
    assert report["exported"] == 0
    assert report["failed"] == 1
    assert not any((tmp_path / "proofs").rglob("*.json"))


def test_artifact_export_is_content_addressed_and_refuses_rebinding(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 32,
        "request_id": "request",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    first = export_proof_payload(payload)
    same = export_proof_payload(payload)
    changed = dict(payload)
    changed["formal_status"] = "DIFFERENT"
    changed.pop("payload_sha256")
    changed["payload_sha256"] = sha256_json(changed)
    distinct = export_proof_payload(changed)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        export_proof_payload(changed, artifact_id=payload["payload_sha256"])

    assert first["reused"] is False
    assert same["reused"] is True
    assert distinct["path"] != first["path"]


def test_both_artifact_kinds_publish_completed_stages_with_hard_links(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    monkeypatch.setenv(
        "GDW_RECEIPT_PROJECTION_DIR",
        str(tmp_path / "receipts"),
    )
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "c" * 64,
        "request_id": "network-mount",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)

    artifact = export_proof_payload(payload)
    receipt = {
        "schema": "szl.gdw.delta-update-receipt/v1",
        "request_id": "network-mount",
        "owner_id": "owner-a",
    }
    receipt["receipt_hash"] = sha256_json(receipt)
    projected = export_receipt_projection(
        receipt,
        "e" * 64,
        owner_id="owner-a",
    )

    assert artifact["publication_mode"] == "HARD_LINK"
    assert projected["publication_mode"] == "HARD_LINK"
    assert Path(artifact["path"]).read_text(encoding="utf-8") == (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    assert export_proof_payload(payload)["reused"] is True


def test_artifact_hard_link_reuses_a_concurrent_identical_file(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "d" * 64,
        "request_id": "concurrent-identical",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    def concurrent_identical(_temporary, destination):
        Path(destination).write_bytes(encoded)
        raise FileExistsError

    monkeypatch.setattr("gdw_proofs.os.link", concurrent_identical)

    artifact = export_proof_payload(payload)

    assert artifact["reused"] is True
    assert artifact["publication_mode"] == "REUSED"


def test_artifact_hard_link_never_overwrites_a_concurrent_mismatch(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "e" * 64,
        "request_id": "concurrent-mismatch",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    observed_inode = None

    def concurrent_mismatch(_temporary, destination):
        nonlocal observed_inode
        Path(destination).write_text("concurrent-mismatch", encoding="utf-8")
        observed_inode = Path(destination).stat().st_ino
        raise FileExistsError

    monkeypatch.setattr("gdw_proofs.os.link", concurrent_mismatch)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        export_proof_payload(payload)

    destination = next((tmp_path / "proofs").rglob("*.json"))
    assert destination.read_text(encoding="utf-8") == "concurrent-mismatch"
    assert destination.stat().st_ino == observed_inode


def test_artifact_temp_write_failure_never_exposes_a_partial_final(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "f" * 64,
        "request_id": "partial-write",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    real_fsync = os.fsync
    failures = 0

    def fail_once(descriptor):
        nonlocal failures
        failures += 1
        if failures == 1:
            raise OSError("injected fsync failure")
        return real_fsync(descriptor)

    monkeypatch.setattr("gdw_proofs.os.fsync", fail_once)

    with pytest.raises(OSError, match="injected fsync failure"):
        export_proof_payload(payload)
    assert not any((tmp_path / "proofs").rglob("*.json"))

    artifact = export_proof_payload(payload)
    assert artifact["reused"] is False
    assert Path(artifact["path"]).is_file()


def test_transient_link_failure_leaves_no_final_and_retry_succeeds(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "1" * 64,
        "request_id": "outer-retry",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    real_link = os.link
    monkeypatch.setattr(
        "gdw_proofs.os.link",
        lambda *_args: (_ for _ in ()).throw(
            OSError("injected transient link failure")
        ),
    )

    with pytest.raises(OSError, match="transient link failure"):
        export_proof_payload(payload)
    assert not any((tmp_path / "proofs").rglob("*.json"))
    assert not any((tmp_path / "proofs").rglob("*.stage"))

    monkeypatch.setattr("gdw_proofs.os.link", real_link)
    artifact = export_proof_payload(payload)
    assert Path(artifact["path"]).is_file()


def test_transient_hf_mount_link_errno_is_retried_before_failure(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "5" * 64,
        "request_id": "dirty-stage",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    real_link = os.link
    attempts = 0

    def link_after_flush(stage, destination):
        nonlocal attempts
        attempts += 1
        assert Path(stage).is_file()
        assert not Path(destination).exists()
        if attempts < 3:
            raise OSError(errno.ENOTSUP, "source is not committed yet")
        real_link(stage, destination)

    monkeypatch.setattr("gdw_proofs.os.link", link_after_flush)
    monkeypatch.setattr("gdw_proofs.time.sleep", lambda _seconds: None)

    artifact = export_proof_payload(payload)

    assert attempts == 3
    assert artifact["publication_mode"] == "HARD_LINK_AFTER_FLUSH"
    assert Path(artifact["path"]).is_file()


def test_transient_link_retry_bound_uses_locked_atomic_rename(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    if gdw_proofs.fcntl is None:
        class FakeFcntl:
            LOCK_EX = 1
            LOCK_UN = 2

            @staticmethod
            def flock(_descriptor, _operation):
                return None

        monkeypatch.setattr(gdw_proofs, "fcntl", FakeFcntl)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 64,
        "request_id": "retry-bound",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    attempts = 0

    def unsupported(_stage, _destination):
        nonlocal attempts
        attempts += 1
        raise OSError(errno.ENOTSUP, "source remains dirty")

    monkeypatch.setattr("gdw_proofs.os.link", unsupported)
    monkeypatch.setattr("gdw_proofs.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("gdw_proofs._LINK_MAX_ATTEMPTS", 3)
    monkeypatch.setattr("gdw_proofs._rename_noreplace", os.replace)

    artifact = export_proof_payload(payload)

    assert attempts == 3
    assert artifact["publication_mode"] == "ATOMIC_RENAME_LOCKED"
    assert Path(artifact["path"]).is_file()
    assert Path(artifact["path"]).read_text(encoding="utf-8") == (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    assert not any((tmp_path / "proofs").rglob("*.tmp"))


def test_locked_rename_unknown_result_is_reused_without_rebinding(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    if gdw_proofs.fcntl is None:
        class FakeFcntl:
            LOCK_EX = 1
            LOCK_UN = 2

            @staticmethod
            def flock(_descriptor, _operation):
                return None

        monkeypatch.setattr(gdw_proofs, "fcntl", FakeFcntl)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "b" * 64,
        "request_id": "unknown-rename-result",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    real_replace = os.replace

    monkeypatch.setattr(
        "gdw_proofs.os.link",
        lambda *_args: (_ for _ in ()).throw(
            OSError(errno.ENOTSUP, "hard links unsupported")
        ),
    )
    monkeypatch.setattr("gdw_proofs._LINK_MAX_ATTEMPTS", 1)

    def replace_then_report_io_error(staging, destination):
        real_replace(staging, destination)
        raise OSError(errno.EIO, "rename result was not acknowledged")

    monkeypatch.setattr(
        "gdw_proofs._rename_noreplace",
        replace_then_report_io_error,
    )
    with pytest.raises(OSError, match="rename result was not acknowledged"):
        export_proof_payload(payload)

    artifact = export_proof_payload(payload)

    assert artifact["reused"] is True
    assert artifact["publication_mode"] == "REUSED"
    assert Path(artifact["path"]).read_text(encoding="utf-8") == (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    assert not any((tmp_path / "proofs").rglob("*.tmp"))


def test_locked_rename_never_overwrites_uncooperative_concurrent_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    if gdw_proofs.fcntl is None:
        class FakeFcntl:
            LOCK_EX = 1
            LOCK_UN = 2

            @staticmethod
            def flock(_descriptor, _operation):
                return None

        monkeypatch.setattr(gdw_proofs, "fcntl", FakeFcntl)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "c" * 64,
        "request_id": "uncooperative-publisher",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    concurrent_bytes = b'{"external":true}\n'
    published_path = None

    monkeypatch.setattr(
        "gdw_proofs.os.link",
        lambda *_args: (_ for _ in ()).throw(
            OSError(errno.ENOTSUP, "hard links unsupported")
        ),
    )
    monkeypatch.setattr("gdw_proofs._LINK_MAX_ATTEMPTS", 1)

    def concurrent_publish(_staging, destination):
        nonlocal published_path
        published_path = Path(destination)
        published_path.write_bytes(concurrent_bytes)
        raise FileExistsError(errno.EEXIST, "destination exists")

    monkeypatch.setattr(
        "gdw_proofs._rename_noreplace",
        concurrent_publish,
    )

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        export_proof_payload(payload)

    assert published_path is not None
    assert published_path.read_bytes() == concurrent_bytes


def test_directory_fsync_is_capability_aware_but_propagates_io_errors(
    monkeypatch,
    tmp_path,
):
    closed = []
    monkeypatch.setattr(gdw_proofs.os, "name", "posix")
    monkeypatch.setattr(gdw_proofs.os, "open", lambda *_args: 41)
    monkeypatch.setattr(gdw_proofs.os, "close", closed.append)
    monkeypatch.setattr(
        gdw_proofs.os,
        "fsync",
        lambda _descriptor: (_ for _ in ()).throw(
            OSError(errno.ENOTSUP, "directory fsync unsupported")
        ),
    )

    gdw_proofs._fsync_directory(tmp_path)
    assert closed == [41]

    monkeypatch.setattr(
        gdw_proofs.os,
        "fsync",
        lambda _descriptor: (_ for _ in ()).throw(
            OSError(errno.EIO, "directory sync failed")
        ),
    )
    with pytest.raises(OSError) as exc_info:
        gdw_proofs._fsync_directory(tmp_path)
    assert exc_info.value.errno == errno.EIO
    assert closed == [41, 41]


def test_existing_artifact_symlink_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "3" * 64,
        "request_id": "symlink",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    owner_scope = hashlib.sha256(b"owner-a").hexdigest()[:32]
    owner_root = tmp_path / "proofs" / owner_scope
    owner_root.mkdir(parents=True)
    target = tmp_path / "outside.json"
    target.write_text("outside", encoding="utf-8")
    destination = owner_root / f"{payload['payload_sha256']}.json"
    try:
        destination.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not permitted")

    with pytest.raises((FileExistsError, OSError)):
        export_proof_payload(payload)
    assert target.read_text(encoding="utf-8") == "outside"


def test_process_death_before_finalization_leaves_no_visible_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "2" * 64,
        "request_id": "process-death",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    environment = os.environ.copy()
    environment["TEST_GDW_PAYLOAD"] = json.dumps(payload)
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, os; import gdw_proofs; "
                "payload = json.loads(os.environ['TEST_GDW_PAYLOAD']); "
                "gdw_proofs.os.link = lambda *_args: os._exit(17); "
                "gdw_proofs.export_proof_payload(payload)"
            ),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=False,
    )

    assert process.returncode == 17
    assert not any((tmp_path / "proofs").rglob("*.json"))
    assert any((tmp_path / "proofs").rglob("*.tmp"))

    artifact = export_proof_payload(payload)
    assert Path(artifact["path"]).is_file()
    assert any((tmp_path / "proofs").rglob("*.tmp"))


def test_process_death_after_finalization_reuses_exact_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "4" * 64,
        "request_id": "post-publication-death",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    environment = os.environ.copy()
    environment["TEST_GDW_PAYLOAD"] = json.dumps(payload)
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, os; import gdw_proofs; "
                "payload = json.loads(os.environ['TEST_GDW_PAYLOAD']); "
                "real_link = os.link; "
                "gdw_proofs.os.link = lambda *args: "
                "(real_link(*args), os._exit(19))[1]; "
                "gdw_proofs.export_proof_payload(payload)"
            ),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=False,
    )

    assert process.returncode == 19
    assert len(list((tmp_path / "proofs").rglob("*.json"))) == 1
    assert any((tmp_path / "proofs").rglob("*.tmp"))

    artifact = export_proof_payload(payload)
    assert artifact["reused"] is True
    assert Path(artifact["path"]).is_file()
    assert any((tmp_path / "proofs").rglob("*.tmp"))


def test_two_processes_reuse_the_same_complete_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "6" * 64,
        "request_id": "two-process-identical",
        "owner_id": "owner-a",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    environment = os.environ.copy()
    environment["TEST_GDW_PAYLOAD"] = json.dumps(payload)
    command = [
        sys.executable,
        "-c",
        (
            "import json, os; from gdw_proofs import export_proof_payload; "
            "payload = json.loads(os.environ['TEST_GDW_PAYLOAD']); "
            "export_proof_payload(payload)"
        ),
    ]
    processes = [
        subprocess.Popen(
            command,
            cwd=Path(__file__).parents[1],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(2)
    ]

    assert [process.wait(timeout=30) for process in processes] == [0, 0]
    finals = list((tmp_path / "proofs").rglob("*.json"))
    assert len(finals) == 1
    assert finals[0].read_text(encoding="utf-8") == (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def test_two_processes_never_overwrite_a_different_final(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payloads = []
    for marker in ("7", "8"):
        payload = {
            "schema": "szl.gdw.proof-input/v1",
            "proposal_id": marker * 64,
            "request_id": f"two-process-{marker}",
            "owner_id": "owner-a",
            "formal_status": "NOT_RUN",
        }
        payload["payload_sha256"] = sha256_json(payload)
        payloads.append(payload)
    artifact_id = "9" * 64
    command = [
        sys.executable,
        "-c",
        (
            "import json, os; from gdw_proofs import export_proof_payload; "
            "payload = json.loads(os.environ['TEST_GDW_PAYLOAD']); "
            "export_proof_payload("
            "payload, artifact_id=os.environ['TEST_GDW_ARTIFACT_ID'])"
        ),
    ]
    processes = []
    for payload in payloads:
        environment = os.environ.copy()
        environment["TEST_GDW_PAYLOAD"] = json.dumps(payload)
        environment["TEST_GDW_ARTIFACT_ID"] = artifact_id
        processes.append(
            subprocess.Popen(
                command,
                cwd=Path(__file__).parents[1],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )

    return_codes = sorted(
        process.wait(timeout=30) for process in processes
    )
    assert return_codes == [0, 1]
    finals = list((tmp_path / "proofs").rglob("*.json"))
    assert len(finals) == 1
    assert finals[0].read_bytes() in {
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        for payload in payloads
    }


def test_lost_claim_does_not_crash_the_bounded_drain(
    monkeypatch,
    tmp_path,
):
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)
    monkeypatch.setattr(
        gdw_runtime,
        "_export_effect",
        lambda _workspace, _row: (
            _ for _ in ()
        ).throw(OSError("projection failed")),
    )
    monkeypatch.setattr(
        workspace,
        "release_effect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("claim lost")
        ),
    )

    report = gdw_runtime.drain_once(
        worker_id="lost-claim-worker",
        workspace=workspace,
    )

    assert report["failed"] == 1
    assert "proof_export:CLAIM_LOST" in report["errors"]


def test_supervisor_resets_prior_success_before_its_first_pass(monkeypatch):
    old_generation = "a" * 32
    monkeypatch.setattr(
        gdw_runtime,
        "_STATE",
        {
            "startup_state": "READY",
            "evidence_label": "VERIFIED",
            "storage": {"database_generation_id": old_generation},
            "drain": {
                "enabled": True,
                "running": False,
                "last_outcome": "SUCCEEDED",
                "last_success_at": "2026-01-01T00:00:00+00:00",
                "last_error": None,
                "last_report": {"exported": 99},
                "run_generation_id": "old",
                "success_run_generation_id": "old",
                "success_database_generation_id": old_generation,
            },
        },
    )
    supervisor = gdw_runtime.OutboxSupervisor(
        enabled=True,
        interval_seconds=5,
        retry_max_seconds=60,
        batch_size=10,
        lease_seconds=30,
    )
    observed = {}

    class StopBeforeFirstPass:
        def wait(self, _delay):
            observed.update(gdw_runtime.runtime_health()["drain"])
            return True

    supervisor._stop = StopBeforeFirstPass()
    supervisor._run()

    assert observed["last_outcome"] == "STARTING"
    assert observed["last_success_at"] is None
    assert observed["last_report"] is None
    assert observed["success_run_generation_id"] is None
    assert observed["success_database_generation_id"] is None


def test_supervisor_binds_success_to_current_run_and_database(
    monkeypatch,
):
    database_generation = "b" * 32
    monkeypatch.setattr(
        gdw_runtime,
        "_STATE",
        {
            "startup_state": "READY",
            "evidence_label": "VERIFIED",
            "storage": {"database_generation_id": database_generation},
            "drain": {
                "enabled": False,
                "running": False,
                "last_outcome": "NOT_RUN",
            },
        },
    )
    monkeypatch.setattr(
        gdw_runtime,
        "drain_once",
        lambda **_kwargs: {
            "attempted": 0,
            "exported": 0,
            "failed": 0,
            "pending_effects": 0,
            "claimed_effects": 0,
            "dead_letter_effects": 0,
            "legacy_pending_proofs": 0,
            "sqlite_integrity": "ok",
            "invalid_effect_bindings": 0,
            "invalid_exported_artifacts": 0,
            "errors": [],
        },
    )
    supervisor = gdw_runtime.OutboxSupervisor(
        enabled=True,
        interval_seconds=5,
        retry_max_seconds=60,
        batch_size=10,
        lease_seconds=30,
    )
    waits = iter((False, True))
    supervisor._stop = type(
        "TwoPassStop",
        (),
        {"wait": lambda _self, _delay: next(waits)},
    )()

    supervisor._run()
    drain = gdw_runtime.runtime_health()["drain"]

    assert drain["last_outcome"] == "SUCCEEDED"
    assert drain["success_run_generation_id"] == drain["run_generation_id"]
    assert drain["success_database_generation_id"] == database_generation
    assert drain["last_success_at"]


def test_supervisor_retries_when_legacy_proofs_remain(monkeypatch):
    monkeypatch.setattr(
        gdw_runtime,
        "_STATE",
        {
            "startup_state": "READY",
            "evidence_label": "VERIFIED",
            "storage": {"database_generation_id": "c" * 32},
            "drain": {
                "enabled": False,
                "running": False,
                "last_outcome": "NOT_RUN",
            },
        },
    )
    monkeypatch.setattr(
        gdw_runtime,
        "drain_once",
        lambda **_kwargs: {
            "attempted": 0,
            "exported": 0,
            "failed": 0,
            "pending_effects": 0,
            "claimed_effects": 0,
            "dead_letter_effects": 0,
            "legacy_pending_proofs": 1,
            "sqlite_integrity": "ok",
            "invalid_effect_bindings": 0,
            "invalid_exported_artifacts": 0,
            "errors": [],
        },
    )
    supervisor = gdw_runtime.OutboxSupervisor(
        enabled=True,
        interval_seconds=5,
        retry_max_seconds=60,
        batch_size=10,
        lease_seconds=30,
    )
    waits = iter((False, True))
    supervisor._stop = type(
        "TwoPassStop",
        (),
        {"wait": lambda _self, _delay: next(waits)},
    )()

    supervisor._run()
    drain = gdw_runtime.runtime_health()["drain"]

    assert drain["last_outcome"] == "RETRY_SCHEDULED"
    assert "non-quiescent" in drain["last_error"]


def test_supervisor_does_not_report_success_during_effect_backoff(
    monkeypatch,
):
    database_generation = "d" * 32
    monkeypatch.setattr(
        gdw_runtime,
        "_STATE",
        {
            "startup_state": "READY",
            "evidence_label": "VERIFIED",
            "storage": {"database_generation_id": database_generation},
            "drain": {
                "enabled": False,
                "running": False,
                "last_outcome": "NOT_RUN",
            },
        },
    )
    monkeypatch.setattr(
        gdw_runtime,
        "drain_once",
        lambda **_kwargs: {
            "attempted": 0,
            "exported": 0,
            "failed": 0,
            "pending_effects": 1,
            "claimed_effects": 0,
            "dead_letter_effects": 0,
            "legacy_pending_proofs": 0,
            "sqlite_integrity": "ok",
            "invalid_effect_bindings": 0,
            "invalid_exported_artifacts": 0,
            "errors": [],
        },
    )
    supervisor = gdw_runtime.OutboxSupervisor(
        enabled=True,
        interval_seconds=5,
        retry_max_seconds=60,
        batch_size=10,
        lease_seconds=30,
    )
    waits = iter((False, True))
    supervisor._stop = type(
        "TwoPassStop",
        (),
        {"wait": lambda _self, _delay: next(waits)},
    )()

    supervisor._run()
    drain = gdw_runtime.runtime_health()["drain"]

    assert drain["last_outcome"] == "RETRY_SCHEDULED"
    assert drain["last_success_at"] is None
    assert drain["success_run_generation_id"] is None
