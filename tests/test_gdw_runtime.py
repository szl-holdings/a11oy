import json
import sqlite3

import pytest

import gdw_runtime
from gdw_proofs import export_proof_payload, sha256_json
from gdw_workspace import GDWWorkspace


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
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 32,
        "request_id": request_id,
        "formal_status": "NOT_RUN",
        "governance": {
            "principal": {
                "namespace": workspace.namespace,
                "owner_id": workspace.owner_id,
            }
        },
    }
    payload["payload_sha256"] = sha256_json(payload)
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            request_id,
            "b" * 64,
            "session-1",
            {"ok": True},
            "c" * 64,
            "2026-07-28T00:00:00+00:00",
        )
        workspace.save_effect_outbox(
            connection,
            request_id,
            "proof_export",
            payload,
            payload["payload_sha256"],
            None,
            "2026-07-28T00:00:00+00:00",
        )


def test_drain_once_exports_a_bounded_effect(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)

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
    assert (tmp_path / "proofs" / f"{'a' * 32}.json").is_file()


def test_failed_drain_releases_claim_for_retry(monkeypatch, tmp_path):
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)

    def fail_export(_row):
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
    assert not (tmp_path / "proofs" / f"{'a' * 32}.json").exists()


def test_artifact_export_refuses_non_identical_existing_bytes(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 32,
        "request_id": "request",
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    first = export_proof_payload(payload)
    same = export_proof_payload(payload)
    changed = dict(payload)
    changed["formal_status"] = "DIFFERENT"
    changed.pop("payload_sha256")
    changed["payload_sha256"] = sha256_json(changed)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        export_proof_payload(changed)

    assert first["reused"] is False
    assert same["reused"] is True


def test_lost_claim_does_not_crash_the_bounded_drain(
    monkeypatch,
    tmp_path,
):
    workspace = GDWWorkspace(str(tmp_path / "gdw.sqlite3"))
    _queued_proof(workspace)
    monkeypatch.setattr(
        gdw_runtime,
        "_export_effect",
        lambda _row: (_ for _ in ()).throw(OSError("projection failed")),
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
