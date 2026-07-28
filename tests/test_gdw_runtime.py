import sqlite3

import pytest

import gdw_runtime
from gdw_proofs import sha256_json
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
            "d" * 64,
            "e" * 64,
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
