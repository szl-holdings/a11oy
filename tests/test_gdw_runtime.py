import json
import sqlite3

import pytest

import gdw_runtime
from gdw_proofs import build_proof_payload, export_proof_payload, sha256_json
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
    response = {
        "proposal_id": "a" * 64,
        "request_id": request_id,
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
    }
    payload = build_proof_payload(
        proposal_id=response["proposal_id"],
        request_id=response["request_id"],
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
            "b" * 64,
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
    assert (tmp_path / "proofs" / f"{intent_sha256}.json").is_file()


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
    assert not any((tmp_path / "proofs").glob("*.json"))


def test_artifact_export_is_content_addressed_and_refuses_rebinding(
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
    distinct = export_proof_payload(changed)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        export_proof_payload(changed, artifact_id=payload["payload_sha256"])

    assert first["reused"] is False
    assert same["reused"] is True
    assert distinct["path"] != first["path"]


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
            "legacy_pending_proofs": 0,
            "sqlite_integrity": "ok",
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
            "legacy_pending_proofs": 1,
            "sqlite_integrity": "ok",
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
    assert "unmigrated legacy proofs" in drain["last_error"]
