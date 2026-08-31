from __future__ import annotations

import hashlib
import json

import gdw_runtime
from gdw_proofs import sha256_json
from gdw_runtime import drain_once
from gdw_workspace import GDWWorkspace


def _legacy_workspace(tmp_path, monkeypatch, *, payload_owner: str):
    database = tmp_path / "gdw.sqlite3"
    proof_dir = tmp_path / "proofs"
    monkeypatch.setenv("GDW_PROOF_DIR", str(proof_dir))
    bootstrap = GDWWorkspace(str(database), production=False)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 64,
        "request_id": "legacy-request",
        "owner_id": payload_owner,
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    with bootstrap.transaction() as connection:
        bootstrap.save_proof_outbox(
            connection,
            payload["proposal_id"],
            payload,
            payload["payload_sha256"],
            "2026-07-29T00:00:00+00:00",
        )
    production = GDWWorkspace(
        str(database),
        namespace=bootstrap.namespace,
        owner_id=bootstrap.owner_id,
        production=True,
    )
    return production, payload, proof_dir


def test_production_drain_preserves_a_valid_legacy_proof(
    tmp_path,
    monkeypatch,
) -> None:
    workspace, payload, proof_dir = _legacy_workspace(
        tmp_path,
        monkeypatch,
        payload_owner="local-owner",
    )

    report = drain_once(workspace=workspace, worker_id="migration-worker")

    owner_scope = hashlib.sha256(b"local-owner").hexdigest()[:32]
    assert report["exported"] == 1
    assert report["failed"] == 0
    assert report["legacy_pending_proofs"] == 0
    assert (
        proof_dir
        / owner_scope
        / f"{payload['payload_sha256']}.json"
    ).is_file()


def test_production_drain_rejects_a_rebound_legacy_proof(
    tmp_path,
    monkeypatch,
) -> None:
    workspace, _payload, _proof_dir = _legacy_workspace(
        tmp_path,
        monkeypatch,
        payload_owner="attacker-owner",
    )

    report = drain_once(workspace=workspace, worker_id="migration-worker")

    assert report["exported"] == 0
    assert report["failed"] == 1
    assert report["legacy_pending_proofs"] == 1
    assert report["errors"] == ["legacy:ValueError"]


def test_production_drain_rechecks_the_row_before_completion(
    tmp_path,
    monkeypatch,
) -> None:
    workspace, _payload, _proof_dir = _legacy_workspace(
        tmp_path,
        monkeypatch,
        payload_owner="local-owner",
    )
    original_export = gdw_runtime.export_proof_payload

    def export_then_rebind(payload, **kwargs):
        artifact = original_export(payload, **kwargs)
        rebound = dict(payload)
        rebound["owner_id"] = "attacker-owner"
        rebound.pop("payload_sha256")
        rebound["payload_sha256"] = sha256_json(rebound)
        connection = workspace._connect()
        try:
            connection.execute(
                """
                UPDATE proof_outbox
                SET payload_json = ?, payload_sha256 = ?
                WHERE proposal_id = ?
                """,
                (
                    json.dumps(
                        rebound,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    rebound["payload_sha256"],
                    rebound["proposal_id"],
                ),
            )
        finally:
            connection.close()
        return artifact

    monkeypatch.setattr(
        gdw_runtime,
        "export_proof_payload",
        export_then_rebind,
    )

    report = drain_once(workspace=workspace, worker_id="migration-worker")

    assert report["exported"] == 0
    assert report["failed"] == 1
    assert report["legacy_pending_proofs"] == 1
    assert report["errors"] == ["legacy:RuntimeError"]
