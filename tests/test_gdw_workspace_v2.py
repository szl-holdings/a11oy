import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gdw_proofs import (
    build_proof_payload,
    export_proof_payload,
    export_receipt_projection,
)

from gdw_workspace import (
    SCHEMA_VERSION,
    GDWConfigurationError,
    GDWLegacyMigrationRequired,
    GDWLifecycleError,
    GDWQuotaExceeded,
    GDWQuotaPolicy,
    GDWSchemaError,
    GDWWorkspace,
)


def _canonical_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _policy(**overrides):
    values = {
        "owner_active_sessions": 100,
        "owner_active_requests": 100,
        "owner_pending_effects": 100,
        "owner_stored_bytes": 1_000_000,
        "global_active_sessions": 1_000,
        "global_active_requests": 1_000,
        "global_pending_effects": 1_000,
        "global_stored_bytes": 10_000_000,
    }
    values.update(overrides)
    return GDWQuotaPolicy(**values)


def _workspace(path, owner="owner-a", namespace="a11oy", policy=None):
    return GDWWorkspace(
        str(path),
        namespace=namespace,
        owner_id=owner,
        quota_policy=policy or _policy(),
    )


def _bind_response(workspace, response, request_digest):
    response["request_digest"] = request_digest
    response["database_generation_id"] = workspace.database_generation_id
    response["principal"] = {
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "key_id": "test-key",
    }
    response["proposal_id"] = _canonical_hash(
        {
            "schema": "szl.gdw.proposal-identity/v1",
            "database_generation_id": workspace.database_generation_id,
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "request_id": response["request_id"],
            "request_digest": request_digest,
            "state_before_hash": response["state_before_hash"],
            "governance_evidence_sha256": _canonical_hash(
                response["audit"]["governance"]
            ),
        }
    )
    return response


def _save_request(workspace, request_id, session_id="session", created_at=None):
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    request_digest = hashlib.sha256(request_id.encode()).hexdigest()
    response = {
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
    _bind_response(workspace, response, request_digest)
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            request_id,
            request_digest,
            session_id,
            response,
            _canonical_hash(response),
            timestamp,
        )
    return response


def _proof_payload(response):
    return build_proof_payload(
        proposal_id=response["proposal_id"],
        request_id=response["request_id"],
        request_digest=response["request_digest"],
        namespace=response["principal"]["namespace"],
        owner_id=response["principal"]["owner_id"],
        database_generation_id=response["database_generation_id"],
        step=response["step"],
        before_hash=response["state_before_hash"],
        after_hash=response["state_hash"],
        decision=response["decision"],
        scheduler_mode=response["scheduler_mode"],
        receipt_hash=response.get("receipt_hash") or "",
        dry_run=response["dry_run"],
        governance=response["audit"]["governance"],
    )


def _receipt_payload(
    workspace,
    request_id,
    session_id="session",
    request_digest=None,
    *,
    step=0,
    state_before_hash="b" * 64,
    state_after_hash="c" * 64,
    scheduler_mode="kda_local",
    governance=None,
    created_at="2026-07-28T00:00:00+00:00",
):
    resolved_digest = request_digest or hashlib.sha256(
        request_id.encode()
    ).hexdigest()
    resolved_governance = governance
    if resolved_governance is None:
        resolved_governance = {
            "allowed": True,
            "policy": "test",
            "principal": {
                "namespace": workspace.namespace,
                "owner_id": workspace.owner_id,
            },
        }
    proposal_id = _canonical_hash(
        {
            "schema": "szl.gdw.proposal-identity/v1",
            "database_generation_id": workspace.database_generation_id,
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "request_id": request_id,
            "request_digest": resolved_digest,
            "state_before_hash": state_before_hash,
            "governance_evidence_sha256": _canonical_hash(
                resolved_governance
            ),
        }
    )
    receipt = {
        "schema": "szl.gdw.transaction-receipt/v1",
        "status": "UNSIGNED_ATOMIC",
        "proposal_id": proposal_id,
        "request_id": request_id,
        "request_digest": resolved_digest,
        "session_id": session_id,
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "database_generation_id": workspace.database_generation_id,
        "credential_key_id": "test-key",
        "step": step,
        "state_before_hash": state_before_hash,
        "state_after_hash": state_after_hash,
        "scheduler_mode": scheduler_mode,
        "governance_evidence_sha256": _canonical_hash(
            resolved_governance
        ),
        "governance": resolved_governance,
        "created_at": created_at,
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    return receipt


def _accepted_response_and_receipt(
    workspace,
    request_id="request",
    session_id="session",
):
    request_digest = hashlib.sha256(request_id.encode()).hexdigest()
    receipt = _receipt_payload(
        workspace,
        request_id,
        session_id=session_id,
        request_digest=request_digest,
    )
    response = {
        "request_id": request_id,
        "session_id": session_id,
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "c" * 64,
        "decision": "ACCEPT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
        "dry_run": False,
        "audit": {"governance": receipt["governance"]},
    }
    _bind_response(workspace, response, request_digest)
    assert response["proposal_id"] == receipt["proposal_id"]
    return request_digest, response, receipt


def _queue_proof(
    workspace,
    request_id="request",
    *,
    created_at=None,
    max_attempts=None,
):
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    response = _save_request(workspace, request_id, created_at=timestamp)
    proof = _proof_payload(response)
    with workspace.transaction() as connection:
        key = workspace.save_effect_outbox(
            connection,
            request_id,
            "proof_export",
            proof,
            proof["payload_sha256"],
            None,
            timestamp,
            max_attempts=max_attempts,
        )
    return key, proof


def _export_claim(claim):
    return export_proof_payload(
        claim["payload"],
        artifact_id=claim["intent_sha256"],
        owner_id=claim["owner_id"],
    )


def _queue_expired_exported_proof(workspace, request_id, start, worker_id):
    key, _ = _queue_proof(
        workspace,
        request_id,
        created_at=start.isoformat(),
    )
    with workspace.transaction() as connection:
        connection.execute(
            "UPDATE requests SET expires_at = ? "
            "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
            (
                (start + timedelta(seconds=1)).isoformat(),
                workspace.namespace,
                workspace.owner_id,
                request_id,
            ),
        )
    claim = workspace.claim_effects(worker_id, limit=1)[0]
    workspace.mark_effect_exported(
        key,
        worker_id,
        claim["claim_generation"],
        _export_claim(claim),
        (start + timedelta(seconds=2)).isoformat(),
    )
    return key


def _queue_expired_exported_receipt(workspace, request_id, start, worker_id):
    request_digest = hashlib.sha256(request_id.encode()).hexdigest()
    receipt = _receipt_payload(
        workspace,
        request_id,
        request_digest=request_digest,
    )
    response = {
        "request_id": request_id,
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "c" * 64,
        "decision": "ACCEPT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
        "dry_run": False,
        "audit": {
            "governance": {
                "allowed": True,
                "policy": "test",
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
            }
        },
    }
    _bind_response(workspace, response, request_digest)
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            request_id,
            request_digest,
            "session",
            response,
            _canonical_hash(response),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        workspace.save_receipt(
            connection,
            receipt["receipt_hash"],
            request_id,
            "session",
            0,
            receipt,
            start.isoformat(),
        )
        key = workspace.save_effect_outbox(
            connection,
            request_id,
            "receipt_projection",
            receipt,
            _canonical_hash(receipt),
            None,
            start.isoformat(),
        )
    claim = workspace.claim_effects(worker_id, limit=1)[0]
    artifact = export_receipt_projection(
        claim["payload"],
        claim["intent_sha256"],
        owner_id=claim["owner_id"],
    )
    workspace.mark_effect_exported(
        key,
        worker_id,
        claim["claim_generation"],
        artifact,
        (start + timedelta(seconds=2)).isoformat(),
    )
    return key

def test_v2_schema_scopes_same_ids_by_namespace_and_owner(tmp_path):
    path = tmp_path / "gdw.sqlite3"
    owner_a = _workspace(path, owner="owner-a", namespace="alpha")
    owner_b = _workspace(path, owner="owner-b", namespace="alpha")
    owner_c = _workspace(path, owner="owner-a", namespace="beta")
    timestamp = datetime.now(timezone.utc).isoformat()

    for workspace, marker in (
        (owner_a, "a"),
        (owner_b, "b"),
        (owner_c, "c"),
    ):
        with workspace.transaction() as connection:
            state = {
                "marker": marker,
                "namespace": workspace.namespace,
                "owner_id": workspace.owner_id,
                "session_id": "same-session",
                "database_generation_id": workspace.database_generation_id,
                "step": 1,
            }
            workspace.save_state(
                connection,
                "same-session",
                1,
                state,
                _canonical_hash(state),
                timestamp,
            )
            response = {
                "marker": marker,
                "request_id": "same-request",
                "request_digest": f"digest-{marker}",
                "session_id": "same-session",
                "database_generation_id": workspace.database_generation_id,
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
                "receipt_hash": None,
            }
            workspace.save_request(
                connection,
                "same-request",
                f"digest-{marker}",
                "same-session",
                response,
                _canonical_hash(response),
                timestamp,
            )

    assert owner_a.read_session("same-session")["state"]["marker"] == "a"
    assert owner_b.read_session("same-session")["state"]["marker"] == "b"
    assert owner_c.read_session("same-session")["state"]["marker"] == "c"
    with owner_b.transaction() as connection:
        digest, response = owner_b.cached_request(connection, "same-request")
        assert digest == "digest-b"
        assert response["marker"] == "b"
    assert owner_a.integrity()["counts"]["session_state"] == 1
    assert owner_a.integrity(global_scope=True)["counts"]["session_state"] == 3
    assert "path" not in owner_a.integrity()
    assert owner_a.integrity(global_scope=True)["schema_version"] == SCHEMA_VERSION


def test_cached_request_and_integrity_accept_response_without_session_id(tmp_path):
    workspace = _workspace(tmp_path / "request-without-response-session.sqlite3")
    response = _save_request(workspace, "request", session_id="row-session")

    assert "session_id" not in response
    with workspace.transaction() as connection:
        digest, cached = workspace.cached_request(connection, "request")

    assert digest == hashlib.sha256(b"request").hexdigest()
    assert cached == response
    assert "session_id" not in cached
    assert workspace.integrity()["ok"] is True


def test_nonempty_legacy_database_requires_explicit_owner_mapping(
    tmp_path, monkeypatch
):
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE session_state(
            session_id TEXT PRIMARY KEY,
            step INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            state_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO session_state VALUES (?, ?, ?, ?, ?)",
        ("legacy-session", 1, '{"legacy":true}', "hash", "2026-01-01T00:00:00+00:00"),
    )
    connection.commit()
    connection.close()

    monkeypatch.delenv("GDW_LEGACY_NAMESPACE", raising=False)
    monkeypatch.delenv("GDW_LEGACY_OWNER_ID", raising=False)
    with pytest.raises(GDWLegacyMigrationRequired):
        _workspace(path)

    monkeypatch.setenv("GDW_LEGACY_NAMESPACE", "legacy-ns")
    monkeypatch.setenv("GDW_LEGACY_OWNER_ID", "legacy-owner")
    with pytest.raises(GDWLegacyMigrationRequired):
        _workspace(path, owner="legacy-owner", namespace="legacy-ns")
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM session_state").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name = 'schema_meta'"
            ).fetchone()[0]
            == 0
        )
    finally:
        connection.close()


def test_production_path_and_schema_fail_closed(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(GDWConfigurationError):
        GDWWorkspace(
            str(missing),
            namespace="a11oy",
            owner_id="owner-a",
            production=True,
        )

    empty = tmp_path / "empty.sqlite3"
    empty.touch()
    with pytest.raises(GDWSchemaError):
        GDWWorkspace(
            str(empty),
            namespace="a11oy",
            owner_id="owner-a",
            production=True,
        )

    valid = tmp_path / "valid.sqlite3"
    _workspace(valid)
    production = GDWWorkspace(
        str(valid),
        namespace="a11oy",
        owner_id="owner-a",
        production=True,
        quota_policy=_policy(),
    )
    assert production.integrity()["ok"] is True

    connection = sqlite3.connect(valid)
    connection.execute(
        "UPDATE schema_meta SET schema_version = 999 WHERE schema_name = 'gdw'"
    )
    connection.commit()
    connection.close()
    with pytest.raises(GDWSchemaError):
        GDWWorkspace(
            str(valid),
            namespace="a11oy",
            owner_id="owner-a",
            production=True,
        )


def test_owner_and_global_quotas_are_transactional(tmp_path):
    owner_policy = _policy(owner_active_sessions=1)
    workspace = _workspace(tmp_path / "owner.sqlite3", policy=owner_policy)
    timestamp = datetime.now(timezone.utc).isoformat()
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "one",
            1,
            {
                "n": 1,
                "database_generation_id": workspace.database_generation_id,
            },
            "h1",
            timestamp,
        )
    with pytest.raises(GDWQuotaExceeded) as exc:
        with workspace.transaction() as connection:
            workspace.save_state(
                connection,
                "two",
                1,
                {
                    "n": 2,
                    "database_generation_id": workspace.database_generation_id,
                },
                "h2",
                timestamp,
            )
    assert exc.value.code == "OWNER_SESSIONS_QUOTA"
    assert workspace.integrity()["counts"]["session_state"] == 1

    shared_path = tmp_path / "global.sqlite3"
    global_policy = _policy(global_active_sessions=1)
    first = _workspace(shared_path, owner="first", policy=global_policy)
    second = _workspace(shared_path, owner="second", policy=global_policy)
    with first.transaction() as connection:
        first.save_state(
            connection,
            "one",
            1,
            {
                "n": 1,
                "database_generation_id": first.database_generation_id,
            },
            "h1",
            timestamp,
        )
    with pytest.raises(GDWQuotaExceeded) as exc:
        with second.transaction() as connection:
            second.save_state(
                connection,
                "two",
                1,
                {
                    "n": 2,
                    "database_generation_id": second.database_generation_id,
                },
                "h2",
                timestamp,
            )
    assert exc.value.code == "GLOBAL_SESSIONS_QUOTA"
    assert second.integrity()["counts"]["session_state"] == 0


def test_pending_effect_quota_rolls_back_the_whole_transition(tmp_path):
    workspace = _workspace(
        tmp_path / "atomic.sqlite3",
        policy=_policy(owner_pending_effects=1),
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    request_digest = "request-digest"
    receipt = _receipt_payload(
        workspace,
        "request",
        request_digest=request_digest,
        state_after_hash="b" * 64,
        created_at=timestamp,
    )
    response = {
        "proposal_id": "a" * 64,
        "request_id": "request",
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "b" * 64,
        "decision": "ACCEPT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
        "dry_run": False,
        "audit": {
            "governance": {
                "allowed": True,
                "policy": "test",
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
            }
        },
    }
    _bind_response(workspace, response, request_digest)
    proof = _proof_payload(response)
    with pytest.raises(GDWQuotaExceeded):
        with workspace.transaction() as connection:
            workspace.save_state(
                connection,
                "session",
                1,
                {
                    "state": 1,
                    "database_generation_id": workspace.database_generation_id,
                },
                "state-hash",
                timestamp,
            )
            workspace.save_request(
                connection,
                "request",
                request_digest,
                "session",
                response,
                _canonical_hash(response),
                timestamp,
            )
            workspace.save_receipt(
                connection,
                receipt["receipt_hash"],
                "request",
                "session",
                0,
                receipt,
                timestamp,
            )
            workspace.save_effect_outbox(
                connection,
                "request",
                "receipt_projection",
                receipt,
                _canonical_hash(receipt),
                None,
                timestamp,
            )
            workspace.save_effect_outbox(
                connection,
                "request",
                "proof_export",
                proof,
                proof["payload_sha256"],
                None,
                timestamp,
            )

    integrity = workspace.integrity()
    for table in ("session_state", "requests", "effect_outbox"):
        assert integrity["counts"][table] == 0
    assert workspace.reconcile_usage() == {
        "active_sessions": 0,
        "active_requests": 0,
        "pending_effects": 0,
        "stored_bytes": 0,
    }


def test_effect_retry_is_bounded_backed_off_and_dead_lettered(tmp_path):
    workspace = _workspace(tmp_path / "retry.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    response = _save_request(workspace, "request", created_at=start.isoformat())
    proof = _proof_payload(response)
    with workspace.transaction() as connection:
        key = workspace.save_effect_outbox(
            connection,
            "request",
            "proof_export",
            proof,
            proof["payload_sha256"],
            None,
            start.isoformat(),
            max_attempts=2,
        )

    first = workspace.claim_effects("worker", now=start)
    assert first[0]["attempt"] == 1
    assert first[0]["idempotency_key"] == key
    assert (
        workspace.release_effect(
            key,
            "worker",
            first[0]["claim_generation"],
            "temporary",
            now=start,
        )
        == "PENDING"
    )
    assert workspace.claim_effects("worker", now=start + timedelta(seconds=1)) == []

    retry_time = start + timedelta(seconds=workspace.effect_backoff_seconds)
    second = workspace.claim_effects("worker", now=retry_time)
    assert second[0]["attempt"] == 2
    assert (
        workspace.release_effect(
            key,
            "worker",
            second[0]["claim_generation"],
            "permanent",
            now=retry_time,
        )
        == "DEAD_LETTER"
    )
    assert workspace.claim_effects("worker", now=start + timedelta(days=365)) == []
    connection = workspace._connect()
    try:
        row = connection.execute(
            """
            SELECT status, attempts, next_attempt_at
            FROM effect_outbox
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (workspace.namespace, workspace.owner_id, key),
        ).fetchone()
    finally:
        connection.close()
    assert row["status"] == "DEAD_LETTER"
    assert row["attempts"] == 2
    assert row["next_attempt_at"] is not None
    assert workspace.reconcile_usage()["pending_effects"] == 0


def test_only_legacy_unsupported_link_failures_are_requeued(tmp_path):
    workspace = _workspace(tmp_path / "legacy-link-retry.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    response = _save_request(
        workspace,
        "legacy-request",
        created_at=start.isoformat(),
    )
    proof = _proof_payload(response)
    ordinary_response = _save_request(
        workspace,
        "ordinary-request",
        created_at=start.isoformat(),
    )
    ordinary_proof = _proof_payload(ordinary_response)
    with workspace.transaction() as connection:
        legacy_key = workspace.save_effect_outbox(
            connection,
            "legacy-request",
            "proof_export",
            proof,
            proof["payload_sha256"],
            None,
            start.isoformat(),
            max_attempts=3,
        )
        ordinary_key = workspace.save_effect_outbox(
            connection,
            "ordinary-request",
            "proof_export",
            ordinary_proof,
            ordinary_proof["payload_sha256"],
            None,
            start.isoformat(),
            max_attempts=3,
        )

    claimed = workspace.claim_effects("worker", limit=2, now=start)
    by_key = {row["idempotency_key"]: row for row in claimed}
    workspace.release_effect(
        legacy_key,
        "worker",
        by_key[legacy_key]["claim_generation"],
        (
            "OSError: [Errno 95] Operation not supported: "
            "'/data/.gdw-artifact-stage.tmp' -> '/data/proof.json'"
        ),
        now=start,
    )
    workspace.release_effect(
        ordinary_key,
        "worker",
        by_key[ordinary_key]["claim_generation"],
        "OSError: [Errno 5] storage I/O failure",
        now=start,
    )

    recovery_time = start + timedelta(seconds=1)
    assert workspace.requeue_legacy_link_failures(now=recovery_time) == 1
    assert workspace.requeue_legacy_link_failures(now=recovery_time) == 0
    recovered = workspace.claim_effects("recovery", now=recovery_time)

    assert [row["idempotency_key"] for row in recovered] == [legacy_key]
    assert recovered[0]["attempt"] == 2
    assert (
        workspace.claim_effects(
            "ordinary",
            now=recovery_time,
        )
        == []
    )


def test_gc_tombstones_expired_objects_but_never_unexported_effects(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / "gc.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    response = {
        "proposal_id": "a" * 64,
        "request_id": "request",
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
    _bind_response(workspace, response, "digest")
    proof = _proof_payload(response)
    state = {
        "large": "state",
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "session_id": "session",
        "step": 1,
        "database_generation_id": workspace.database_generation_id,
    }
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            state,
            _canonical_hash(state),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        workspace.save_request(
            connection,
            "request",
            "digest",
            "session",
            response,
            _canonical_hash(response),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        key = workspace.save_effect_outbox(
            connection,
            "request",
            "proof_export",
            proof,
            proof["payload_sha256"],
            None,
            start.isoformat(),
        )

    collected = workspace.collect_garbage(now=start + timedelta(seconds=30))
    assert collected["sessions_tombstoned"] == 1
    assert collected["requests_tombstoned"] == 0
    assert collected["effects_compacted"] == 0
    connection = workspace._connect()
    try:
        effect = connection.execute(
            """
            SELECT status, payload_json FROM effect_outbox
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (workspace.namespace, workspace.owner_id, key),
        ).fetchone()
        request = connection.execute(
            """
            SELECT lifecycle, response_json FROM requests
            WHERE namespace = ? AND owner_id = ? AND request_id = 'request'
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()
    finally:
        connection.close()
    assert effect["status"] == "PENDING"
    assert json.loads(effect["payload_json"]) == proof
    assert request["lifecycle"] == "ACTIVE"
    assert request["response_json"] is not None

    claim = workspace.claim_effects("worker")[0]
    artifact = _export_claim(claim)
    workspace.mark_effect_exported(
        claim["idempotency_key"],
        "worker",
        claim["claim_generation"],
        artifact,
        (start + timedelta(seconds=30)).isoformat(),
    )
    collected = workspace.collect_garbage(now=start + timedelta(seconds=50))
    assert collected["requests_tombstoned"] == 0
    assert collected["effects_compacted"] == 1
    connection = workspace._connect()
    try:
        request = connection.execute(
            """
            SELECT lifecycle, response_json FROM requests
            WHERE namespace = ? AND owner_id = ? AND request_id = 'request'
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()
    finally:
        connection.close()
    assert request["lifecycle"] == "ACTIVE"
    assert request["response_json"] is not None

    released = workspace.collect_garbage(now=start + timedelta(seconds=50))
    assert released["requests_tombstoned"] == 1
    assert released["effects_compacted"] == 0
    with workspace.transaction() as connection:
        with pytest.raises(GDWLifecycleError):
            workspace.cached_request(connection, "request")
    connection = workspace._connect()
    try:
        row = connection.execute(
            """
            SELECT status, payload_json, artifact_json, tombstoned_at
            FROM effect_outbox
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (workspace.namespace, workspace.owner_id, key),
        ).fetchone()
    finally:
        connection.close()
    assert row["status"] == "EXPORTED"
    assert row["payload_json"] is None
    assert row["artifact_json"] is None
    assert row["tombstoned_at"] is not None


@pytest.mark.parametrize(
    "contradictory_state",
    (
        "artifact_only",
        "payload_only",
        "tombstoned_with_retained_bytes",
    ),
)
def test_gc_fails_closed_for_schema_valid_noncanonical_effect_state(
    tmp_path,
    monkeypatch,
    contradictory_state,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / f"{contradictory_state}.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    key = _queue_expired_exported_proof(
        workspace,
        "retained-request",
        start,
        "retained-worker",
    )
    with workspace.transaction() as connection:
        if contradictory_state == "artifact_only":
            connection.execute(
                "UPDATE effect_outbox SET payload_json = NULL "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            )
        elif contradictory_state == "payload_only":
            connection.execute(
                "UPDATE effect_outbox SET artifact_json = NULL "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            )
        else:
            connection.execute(
                "UPDATE effect_outbox SET tombstoned_at = ? "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (
                    (start + timedelta(seconds=3)).isoformat(),
                    workspace.namespace,
                    workspace.owner_id,
                    key,
                ),
            )

    with workspace.transaction() as connection:
        original_request = connection.execute(
            "SELECT lifecycle, response_json FROM requests "
            "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
            (workspace.namespace, workspace.owner_id, "retained-request"),
        ).fetchone()
        original_effect = connection.execute(
            "SELECT payload_json, artifact_json, tombstoned_at "
            "FROM effect_outbox "
            "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
            (workspace.namespace, workspace.owner_id, key),
        ).fetchone()

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_effect_bindings"] == 1
    for offset in (5, 50, 60):
        collected = workspace.collect_garbage(
            now=start + timedelta(seconds=offset)
        )
        assert collected["requests_tombstoned"] == 0
        assert collected["effects_compacted"] == 0
        integrity = workspace.integrity()
        assert integrity["ok"] is False
        assert integrity["invalid_effect_bindings"] == 1
    with workspace.transaction() as connection:
        request = connection.execute(
            "SELECT lifecycle, response_json FROM requests "
            "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
            (
                workspace.namespace,
                workspace.owner_id,
                "retained-request",
            ),
        ).fetchone()
        effect = connection.execute(
            "SELECT payload_json, artifact_json, tombstoned_at "
            "FROM effect_outbox "
            "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
            (workspace.namespace, workspace.owner_id, key),
        ).fetchone()
    assert dict(request) == dict(original_request)
    assert dict(effect) == dict(original_effect)
    assert request["lifecycle"] == "ACTIVE"
    assert request["response_json"] is not None
    if contradictory_state == "artifact_only":
        assert effect["payload_json"] is None
        assert effect["artifact_json"] is not None
        assert effect["tombstoned_at"] is None
    elif contradictory_state == "payload_only":
        assert effect["payload_json"] is not None
        assert effect["artifact_json"] is None
        assert effect["tombstoned_at"] is None
    else:
        assert effect["payload_json"] is not None
        assert effect["artifact_json"] is not None
        assert effect["tombstoned_at"] is not None


@pytest.mark.parametrize("tamper", ("payload", "artifact"))
def test_gc_never_normalizes_aged_tampered_retained_effect(
    tmp_path,
    monkeypatch,
    tamper,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / f"tampered-{tamper}.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    key = _queue_expired_exported_proof(
        workspace,
        "tampered-request",
        start,
        "tampered-worker",
    )
    if tamper == "payload":
        with workspace.transaction() as connection:
            connection.execute(
                "UPDATE effect_outbox SET payload_json = ? "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (
                    json.dumps(
                        {"tampered": True},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    workspace.namespace,
                    workspace.owner_id,
                    key,
                ),
            )
    else:
        with workspace.transaction() as connection:
            artifact = json.loads(
                connection.execute(
                    "SELECT artifact_json FROM effect_outbox "
                    "WHERE namespace = ? AND owner_id = ? "
                    "AND idempotency_key = ?",
                    (workspace.namespace, workspace.owner_id, key),
                ).fetchone()["artifact_json"]
            )
        Path(artifact["path"]).write_text(
            '{"tampered":true}\n',
            encoding="utf-8",
        )

    with workspace.transaction() as connection:
        original_effect = dict(
            connection.execute(
                "SELECT * FROM effect_outbox "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            ).fetchone()
        )
        original_request = dict(
            connection.execute(
                "SELECT * FROM requests "
                "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
                (
                    workspace.namespace,
                    workspace.owner_id,
                    "tampered-request",
                ),
            ).fetchone()
        )
    integrity = workspace.integrity()
    assert integrity["ok"] is False
    if tamper == "payload":
        assert integrity["invalid_effect_bindings"] == 1
    else:
        assert integrity["invalid_exported_artifacts"] == 1

    for offset in (50, 60):
        with pytest.raises(
            GDWConfigurationError,
            match="effect compaction refused invalid lifecycle",
        ):
            workspace.collect_garbage(
                now=start + timedelta(seconds=offset)
            )
        with workspace.transaction() as connection:
            effect = dict(
                connection.execute(
                    "SELECT * FROM effect_outbox "
                    "WHERE namespace = ? AND owner_id = ? "
                    "AND idempotency_key = ?",
                    (workspace.namespace, workspace.owner_id, key),
                ).fetchone()
            )
            request = dict(
                connection.execute(
                    "SELECT * FROM requests "
                    "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
                    (
                        workspace.namespace,
                        workspace.owner_id,
                        "tampered-request",
                    ),
                ).fetchone()
            )
        assert effect == original_effect
        assert request == original_request


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_exported_at",
        "retained_lease",
        "retained_error",
        "tombstone_before_export",
    ),
)
def test_gc_never_releases_impossible_compacted_effect_metadata(
    tmp_path,
    monkeypatch,
    mutation,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / f"impossible-{mutation}.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    key = _queue_expired_exported_proof(
        workspace,
        "impossible-request",
        start,
        "impossible-worker",
    )
    compacted = workspace.collect_garbage(
        now=start + timedelta(seconds=50)
    )
    assert compacted["effects_compacted"] == 1
    with workspace.transaction() as connection:
        if mutation == "missing_exported_at":
            connection.execute(
                "UPDATE effect_outbox SET exported_at = NULL "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            )
        elif mutation == "retained_lease":
            connection.execute(
                "UPDATE effect_outbox SET lease_owner = ?, lease_until = ? "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (
                    "stale-worker",
                    (start + timedelta(seconds=70)).isoformat(),
                    workspace.namespace,
                    workspace.owner_id,
                    key,
                ),
            )
        elif mutation == "retained_error":
            connection.execute(
                "UPDATE effect_outbox SET last_error = ? "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                ("stale-error", workspace.namespace, workspace.owner_id, key),
            )
        else:
            connection.execute(
                "UPDATE effect_outbox SET tombstoned_at = ? "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (
                    (start + timedelta(seconds=1)).isoformat(),
                    workspace.namespace,
                    workspace.owner_id,
                    key,
                ),
            )
        original_effect = dict(
            connection.execute(
                "SELECT * FROM effect_outbox "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            ).fetchone()
        )

    assert workspace.integrity()["invalid_effect_bindings"] == 1
    for offset in (50, 100):
        collected = workspace.collect_garbage(
            now=start + timedelta(seconds=offset)
        )
        assert collected["requests_tombstoned"] == 0
        with workspace.transaction() as connection:
            effect = dict(
                connection.execute(
                    "SELECT * FROM effect_outbox "
                    "WHERE namespace = ? AND owner_id = ? "
                    "AND idempotency_key = ?",
                    (workspace.namespace, workspace.owner_id, key),
                ).fetchone()
            )
            request = connection.execute(
                "SELECT lifecycle, response_json FROM requests "
                "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
                (
                    workspace.namespace,
                    workspace.owner_id,
                    "impossible-request",
                ),
            ).fetchone()
        assert effect == original_effect
        assert request["lifecycle"] == "ACTIVE"
        assert request["response_json"] is not None
        assert workspace.integrity()["invalid_effect_bindings"] == 1


def test_gc_refuses_noncanonical_compacted_timestamp_before_purge(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / "noncanonical-time.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    key = _queue_expired_exported_proof(
        workspace,
        "noncanonical-request",
        start,
        "noncanonical-worker",
    )
    assert workspace.collect_garbage(
        now=start + timedelta(seconds=50)
    )["effects_compacted"] == 1
    with workspace.transaction() as connection:
        connection.execute(
            "UPDATE effect_outbox SET exported_at = ? "
            "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
            (
                "2026-07-28T00:00:02Z",
                workspace.namespace,
                workspace.owner_id,
                key,
            ),
        )
        original = dict(
            connection.execute(
                "SELECT * FROM effect_outbox "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            ).fetchone()
        )
    assert workspace.integrity()["invalid_effect_bindings"] == 1
    first = workspace.collect_garbage(
        now=start + timedelta(seconds=50)
    )
    assert first["requests_tombstoned"] == 0
    with pytest.raises(
        GDWConfigurationError,
        match="effect purge refused invalid lifecycle",
    ):
        workspace.collect_garbage(now=start + timedelta(seconds=100))
    with workspace.transaction() as connection:
        retained = dict(
            connection.execute(
                "SELECT * FROM effect_outbox "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            ).fetchone()
        )
    assert retained == original


@pytest.mark.parametrize("corrupt_anchor", ("request", "receipt"))
def test_gc_never_erases_corrupt_request_or_receipt_anchor(
    tmp_path,
    monkeypatch,
    corrupt_anchor,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    monkeypatch.setenv(
        "GDW_RECEIPT_PROJECTION_DIR", str(tmp_path / "receipt-projections")
    )
    workspace = _workspace(tmp_path / f"corrupt-{corrupt_anchor}.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    if corrupt_anchor == "receipt":
        _queue_expired_exported_receipt(
            workspace,
            "corrupt-anchor-request",
            start,
            "corrupt-anchor-worker",
        )
    else:
        _queue_expired_exported_proof(
            workspace,
            "corrupt-anchor-request",
            start,
            "corrupt-anchor-worker",
        )

    compacted = workspace.collect_garbage(
        now=start + timedelta(seconds=50)
    )
    assert compacted["effects_compacted"] == 1
    assert compacted["requests_tombstoned"] == 0
    with workspace.transaction() as connection:
        if corrupt_anchor == "request":
            connection.execute(
                "UPDATE requests SET response_json = ? "
                "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
                (
                    '{"corrupt":true}',
                    workspace.namespace,
                    workspace.owner_id,
                    "corrupt-anchor-request",
                ),
            )
        else:
            connection.execute(
                "UPDATE receipts SET receipt_json = ? "
                "WHERE namespace = ? AND owner_id = ? AND request_id = ?",
                (
                    '{"corrupt":true}',
                    workspace.namespace,
                    workspace.owner_id,
                    "corrupt-anchor-request",
                ),
            )
        original_request = dict(
            connection.execute(
                "SELECT * FROM requests WHERE namespace = ? AND owner_id = ? "
                "AND request_id = ?",
                (
                    workspace.namespace,
                    workspace.owner_id,
                    "corrupt-anchor-request",
                ),
            ).fetchone()
        )
        receipt_row = connection.execute(
            "SELECT * FROM receipts WHERE namespace = ? AND owner_id = ? "
            "AND request_id = ?",
            (
                workspace.namespace,
                workspace.owner_id,
                "corrupt-anchor-request",
            ),
        ).fetchone()
        original_receipt = dict(receipt_row) if receipt_row is not None else None

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    if corrupt_anchor == "request":
        assert integrity["invalid_request_digests"] == 1
    else:
        assert integrity["invalid_receipt_digests"] == 1
    for offset in (50, 100, 110):
        collected = workspace.collect_garbage(
            now=start + timedelta(seconds=offset)
        )
        assert collected["requests_tombstoned"] == 0
        with workspace.transaction() as connection:
            request = dict(
                connection.execute(
                    "SELECT * FROM requests WHERE namespace = ? "
                    "AND owner_id = ? AND request_id = ?",
                    (
                        workspace.namespace,
                        workspace.owner_id,
                        "corrupt-anchor-request",
                    ),
                ).fetchone()
            )
            receipt_row = connection.execute(
                "SELECT * FROM receipts WHERE namespace = ? AND owner_id = ? "
                "AND request_id = ?",
                (
                    workspace.namespace,
                    workspace.owner_id,
                    "corrupt-anchor-request",
                ),
            ).fetchone()
            observed_receipt = (
                dict(receipt_row) if receipt_row is not None else None
            )
        assert request == original_request
        assert observed_receipt == original_receipt
        assert workspace.integrity()["ok"] is False


@pytest.mark.parametrize(
    "counter_state",
    ("attempts_zero", "claim_generation_zero", "attempts_exceed_max"),
)
def test_gc_preserves_unreachable_export_counter_state(
    tmp_path,
    monkeypatch,
    counter_state,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / f"counter-{counter_state}.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    key = _queue_expired_exported_proof(
        workspace,
        "counter-request",
        start,
        "counter-worker",
    )
    with workspace.transaction() as connection:
        if counter_state == "attempts_zero":
            connection.execute(
                "UPDATE effect_outbox SET attempts = 0 "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            )
        elif counter_state == "claim_generation_zero":
            connection.execute(
                "UPDATE effect_outbox SET claim_generation = 0 "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            )
        else:
            connection.execute(
                "UPDATE effect_outbox SET attempts = max_attempts + 1 "
                "WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            )
        original_effect = dict(
            connection.execute(
                "SELECT * FROM effect_outbox WHERE namespace = ? "
                "AND owner_id = ? AND idempotency_key = ?",
                (workspace.namespace, workspace.owner_id, key),
            ).fetchone()
        )
        original_request = dict(
            connection.execute(
                "SELECT * FROM requests WHERE namespace = ? AND owner_id = ? "
                "AND request_id = ?",
                (workspace.namespace, workspace.owner_id, "counter-request"),
            ).fetchone()
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_effect_bindings"] == 1
    for offset in (50, 100):
        collected = workspace.collect_garbage(
            now=start + timedelta(seconds=offset)
        )
        assert collected["effects_compacted"] == 0
        assert collected["requests_tombstoned"] == 0
        with workspace.transaction() as connection:
            effect = dict(
                connection.execute(
                    "SELECT * FROM effect_outbox WHERE namespace = ? "
                    "AND owner_id = ? AND idempotency_key = ?",
                    (workspace.namespace, workspace.owner_id, key),
                ).fetchone()
            )
            request = dict(
                connection.execute(
                    "SELECT * FROM requests WHERE namespace = ? "
                    "AND owner_id = ? AND request_id = ?",
                    (
                        workspace.namespace,
                        workspace.owner_id,
                        "counter-request",
                    ),
                ).fetchone()
            )
        assert effect == original_effect
        assert request == original_request
        assert workspace.integrity()["invalid_effect_bindings"] == 1

def test_gc_purge_deletes_at_most_limit_per_category(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / "bounded-purge.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    for index in range(3):
        _queue_expired_exported_proof(
            workspace,
            f"purge-request-{index}",
            start,
            f"purge-worker-{index}",
        )
    assert workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=10,
    )["effects_compacted"] == 3
    assert workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=10,
    )["requests_tombstoned"] == 3

    with workspace.transaction() as connection:
        for index in range(3):
            proposal_id = f"legacy-proof-{index}"
            connection.execute(
                """
                INSERT INTO proof_outbox(
                    namespace, owner_id, proposal_id, payload_json,
                    payload_sha256, status, artifact_json, created_at,
                    exported_at, tombstoned_at
                ) VALUES (?, ?, ?, NULL, ?, 'EXPORTED', NULL, ?, ?, ?)
                """,
                (
                    workspace.namespace,
                    workspace.owner_id,
                    proposal_id,
                    hashlib.sha256(proposal_id.encode()).hexdigest(),
                    start.isoformat(),
                    (start + timedelta(seconds=1)).isoformat(),
                    (start + timedelta(seconds=2)).isoformat(),
                ),
            )
            session_id = f"purge-session-{index}"
            connection.execute(
                """
                INSERT INTO session_state(
                    namespace, owner_id, session_id, step, state_json,
                    state_hash, lifecycle, created_at, updated_at,
                    last_accessed_at, expires_at, tombstoned_at
                ) VALUES (?, ?, ?, 1, NULL, ?, 'TOMBSTONED', ?, ?, ?, ?, ?)
                """,
                (
                    workspace.namespace,
                    workspace.owner_id,
                    session_id,
                    hashlib.sha256(session_id.encode()).hexdigest(),
                    start.isoformat(),
                    start.isoformat(),
                    start.isoformat(),
                    (start + timedelta(seconds=1)).isoformat(),
                    (start + timedelta(seconds=2)).isoformat(),
                ),
            )

    for expected_remaining in (2, 1, 0):
        workspace.collect_garbage(
            now=start + timedelta(seconds=100),
            limit=1,
        )
        with workspace.transaction() as connection:
            counts = {
                "effects": connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox"
                ).fetchone()[0],
                "proofs": connection.execute(
                    "SELECT COUNT(*) FROM proof_outbox"
                ).fetchone()[0],
                "sessions": connection.execute(
                    "SELECT COUNT(*) FROM session_state"
                ).fetchone()[0],
            }
        assert counts == {
            "effects": expected_remaining,
            "proofs": expected_remaining,
            "sessions": expected_remaining,
        }

def test_gc_bounded_batches_preserve_each_uncompacted_anchor(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / "bounded-batch.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    for index in range(2):
        _queue_expired_exported_proof(
            workspace,
            f"batch-{index}",
            start,
            f"batch-worker-{index}",
        )

    first = workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=1,
    )
    assert first["requests_tombstoned"] == 0
    assert first["effects_compacted"] == 1

    second = workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=1,
    )
    assert second["requests_tombstoned"] == 1
    assert second["effects_compacted"] == 1

    third = workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=1,
    )
    assert third["requests_tombstoned"] == 1
    assert third["effects_compacted"] == 0
    assert workspace.integrity()["invalid_effect_bindings"] == 0

def test_usage_reconciliation_repairs_persistent_counter_drift(tmp_path):
    workspace = _workspace(tmp_path / "usage.sqlite3")
    _save_request(workspace, "request")
    connection = workspace._connect()
    try:
        connection.execute(
            """
            UPDATE usage
            SET active_requests = 99, pending_effects = 88, stored_bytes = 77
            WHERE namespace = ? AND owner_id = ?
            """,
            (workspace.namespace, workspace.owner_id),
        )
    finally:
        connection.close()

    repaired = workspace.reconcile_usage()
    assert repaired["active_requests"] == 1
    assert repaired["pending_effects"] == 0
    assert repaired["stored_bytes"] > 0


def test_full_effect_rebind_cannot_escape_persisted_proof_intent(tmp_path):
    workspace = _workspace(tmp_path / "rebind.sqlite3")
    key, proof = _queue_proof(workspace)
    changed = dict(proof)
    changed["formal_status"] = "ATTACKER_REBOUND"
    changed.pop("payload_sha256")
    changed["payload_sha256"] = _canonical_hash(changed)
    changed_key = workspace.scoped_effect_key(
        workspace.namespace,
        workspace.owner_id,
        "request",
        "proof_export",
        changed["payload_sha256"],
    )
    with workspace.transaction() as connection:
        request_anchor = workspace._request_anchor(
            connection,
            workspace.namespace,
            workspace.owner_id,
            "request",
        )
        changed_intent = workspace._canonical_effect_intent(
            request_anchor,
            namespace=workspace.namespace,
            owner_id=workspace.owner_id,
            request_id="request",
            kind="proof_export",
            payload_sha256=changed["payload_sha256"],
            receipt_hash=None,
        )
        connection.execute(
            """
            UPDATE effect_outbox
            SET idempotency_key = ?, payload_json = ?, payload_sha256 = ?,
                intent_sha256 = ?
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (
                changed_key,
                json.dumps(changed, sort_keys=True, separators=(",", ":")),
                changed["payload_sha256"],
                changed_intent,
                workspace.namespace,
                workspace.owner_id,
                key,
            ),
        )

    assert workspace.integrity()["invalid_effect_bindings"] == 1
    claim = workspace.claim_effects("worker")[0]
    with pytest.raises(RuntimeError, match="proof_payload_anchor_mismatch"):
        workspace.assert_effect_claim(
            claim["idempotency_key"],
            "worker",
            claim["claim_generation"],
        )


def test_receipt_effect_must_match_persisted_receipt_bytes(tmp_path):
    workspace = _workspace(tmp_path / "receipt-rebind.sqlite3")
    request_digest = "request-digest"
    receipt = _receipt_payload(
        workspace,
        "request",
        request_digest=request_digest,
    )
    response = {
        "proposal_id": "a" * 64,
        "request_id": "request",
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "c" * 64,
        "decision": "ACCEPT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
        "dry_run": False,
        "audit": {
            "governance": {
                "allowed": True,
                "policy": "test",
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
            }
        },
    }
    _bind_response(workspace, response, request_digest)
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            "request",
            request_digest,
            "session",
            response,
            _canonical_hash(response),
            "2026-07-28T00:00:00+00:00",
        )
        workspace.save_receipt(
            connection,
            receipt["receipt_hash"],
            "request",
            "session",
            0,
            receipt,
            "2026-07-28T00:00:00+00:00",
        )
        key = workspace.save_effect_outbox(
            connection,
            "request",
            "receipt_projection",
            receipt,
            _canonical_hash(receipt),
            None,
            "2026-07-28T00:00:00+00:00",
        )

    changed = dict(receipt)
    changed["decision"] = "ATTACKER_REBOUND"
    changed.pop("receipt_hash")
    changed["receipt_hash"] = _canonical_hash(changed)
    changed_digest = _canonical_hash(changed)
    changed_key = workspace.scoped_effect_key(
        workspace.namespace,
        workspace.owner_id,
        "request",
        "receipt_projection",
        changed_digest,
    )
    with workspace.transaction() as connection:
        request_anchor = workspace._request_anchor(
            connection,
            workspace.namespace,
            workspace.owner_id,
            "request",
        )
        changed_intent = workspace._canonical_effect_intent(
            request_anchor,
            namespace=workspace.namespace,
            owner_id=workspace.owner_id,
            request_id="request",
            kind="receipt_projection",
            payload_sha256=changed_digest,
            receipt_hash=receipt["receipt_hash"],
        )
        connection.execute(
            """
            UPDATE effect_outbox
            SET idempotency_key = ?, payload_json = ?, payload_sha256 = ?,
                intent_sha256 = ?
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (
                changed_key,
                json.dumps(changed, sort_keys=True, separators=(",", ":")),
                changed_digest,
                changed_intent,
                workspace.namespace,
                workspace.owner_id,
                key,
            ),
        )

    assert workspace.integrity()["invalid_effect_bindings"] == 1


def test_expired_and_stale_claim_generations_cannot_finalize(
    tmp_path,
    monkeypatch,
):
    import gdw_workspace

    workspace = _workspace(tmp_path / "fencing.sqlite3")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    start = datetime.now(timezone.utc)
    key, _ = _queue_proof(
        workspace,
        created_at=start.isoformat(),
        max_attempts=3,
    )
    first = workspace.claim_effects(
        "same-worker",
        lease_seconds=1,
        now=start,
    )[0]
    expired = start + timedelta(seconds=2)
    monkeypatch.setattr(gdw_workspace, "_utc_now", lambda: expired)
    with pytest.raises(RuntimeError, match="expired"):
        workspace.mark_effect_exported(
            key,
            "same-worker",
            first["claim_generation"],
            {"path": "stale"},
            expired.isoformat(),
        )

    second = workspace.claim_effects(
        "same-worker",
        lease_seconds=30,
        now=expired,
    )[0]
    assert second["claim_generation"] > first["claim_generation"]
    with pytest.raises(RuntimeError, match="expired"):
        workspace.mark_effect_exported(
            key,
            "same-worker",
            first["claim_generation"],
            {"path": "stale-generation"},
            expired.isoformat(),
        )
    artifact = _export_claim(second)
    workspace.mark_effect_exported(
        key,
        "same-worker",
        second["claim_generation"],
        artifact,
        expired.isoformat(),
    )
    assert workspace.integrity()["pending_effects"] == 0


def test_expired_final_attempt_dead_letters_and_reconciles_quota(tmp_path):
    workspace = _workspace(tmp_path / "expired-final.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    _queue_proof(
        workspace,
        created_at=start.isoformat(),
        max_attempts=1,
    )
    assert workspace.claim_effects(
        "first-worker",
        lease_seconds=1,
        now=start,
    )
    assert (
        workspace.claim_effects(
            "second-worker",
            now=start + timedelta(seconds=2),
        )
        == []
    )
    integrity = workspace.integrity()
    assert integrity["dead_letter_effects"] == 1
    assert integrity["pending_effects"] == 0
    assert workspace.reconcile_usage()["pending_effects"] == 0


def test_historical_export_timestamp_cannot_extend_an_expired_lease(tmp_path):
    workspace = _workspace(tmp_path / "historical-finalize.sqlite3")
    historical = datetime.now(timezone.utc) - timedelta(seconds=10)
    key, _ = _queue_proof(
        workspace,
        created_at=historical.isoformat(),
        max_attempts=2,
    )
    claim = workspace.claim_effects(
        "historical-worker",
        lease_seconds=1,
        now=historical,
    )[0]

    with pytest.raises(RuntimeError, match="expired"):
        workspace.mark_effect_exported(
            key,
            "historical-worker",
            claim["claim_generation"],
            {"path": "stale"},
            historical.isoformat(),
        )


def test_v2_effects_migrate_transactionally_to_generation_bound_schema(tmp_path):
    path = tmp_path / "v2.sqlite3"
    workspace = _workspace(path)
    _queue_proof(workspace)
    old_generation = workspace.database_generation_id
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DROP TABLE effect_recovery_audit")
        connection.execute("DROP INDEX idx_effect_outbox_status")
        connection.execute(
            "ALTER TABLE effect_outbox RENAME TO effect_outbox_v3"
        )
        connection.execute(
            """
            CREATE TABLE effect_outbox (
                namespace TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                next_attempt_at TEXT NOT NULL,
                lease_owner TEXT,
                lease_until TEXT,
                last_error TEXT,
                artifact_json TEXT,
                created_at TEXT NOT NULL,
                exported_at TEXT,
                tombstoned_at TEXT,
                PRIMARY KEY(namespace, owner_id, idempotency_key)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO effect_outbox(
                namespace, owner_id, idempotency_key, request_id, kind,
                payload_json, payload_sha256, status, attempts, max_attempts,
                next_attempt_at, lease_owner, lease_until, last_error,
                artifact_json, created_at, exported_at, tombstoned_at
            )
            SELECT namespace, owner_id, idempotency_key, request_id, kind,
                   payload_json, payload_sha256, status, attempts, max_attempts,
                   next_attempt_at, lease_owner, lease_until, last_error,
                   artifact_json, created_at, exported_at, tombstoned_at
            FROM effect_outbox_v3
            """
        )
        connection.execute("DROP TABLE effect_outbox_v3")
        connection.execute(
            """
            CREATE INDEX idx_effect_outbox_status
            ON effect_outbox(
                namespace, owner_id, status, next_attempt_at,
                lease_until, created_at
            )
            """
        )
        connection.execute(
            "ALTER TABLE schema_meta DROP COLUMN database_generation_id"
        )
        connection.execute(
            "UPDATE schema_meta SET schema_version = 2 WHERE schema_name = 'gdw'"
        )
        connection.commit()
    finally:
        connection.close()

    migrated = _workspace(path)

    assert migrated.database_generation_id != old_generation
    assert migrated.integrity()["ok"] is True
    assert migrated.integrity()["schema_version"] == SCHEMA_VERSION
    claim = migrated.claim_effects("migrated-worker")
    assert len(claim) == 1
    assert (
        claim[0]["database_generation_id"]
        == migrated.database_generation_id
    )
    assert claim[0]["claim_generation"] == 1


def test_v3_schema_migrates_audit_table_without_rebinding_generation(tmp_path):
    path = tmp_path / "v3.sqlite3"
    workspace = _workspace(path)
    generation = workspace.database_generation_id
    connection = sqlite3.connect(path)
    try:
        connection.execute("DROP TABLE effect_recovery_audit")
        connection.execute(
            "UPDATE schema_meta SET schema_version = 3 WHERE schema_name = 'gdw'"
        )
        connection.commit()
    finally:
        connection.close()

    migrated = _workspace(path)

    assert migrated.database_generation_id == generation
    assert migrated.integrity()["ok"] is True
    assert migrated.integrity()["schema_version"] == SCHEMA_VERSION
    connection = sqlite3.connect(path)
    try:
        table = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'effect_recovery_audit'"
        ).fetchone()
    finally:
        connection.close()
    assert table == ("effect_recovery_audit",)


def test_receipt_identity_fields_are_bound_before_persistence(tmp_path):
    workspace = _workspace(tmp_path / "receipt-identity.sqlite3")
    request_digest = "digest"
    receipt = _receipt_payload(
        workspace,
        "request",
        session_id="wrong-session",
        request_digest=request_digest,
    )
    response = {
        "proposal_id": "a" * 64,
        "request_id": "request",
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "c" * 64,
        "decision": "ACCEPT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
        "dry_run": False,
        "audit": {
            "governance": {
                "allowed": True,
                "policy": "test",
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
            }
        },
    }
    _bind_response(workspace, response, request_digest)
    with pytest.raises(GDWConfigurationError, match="session"):
        with workspace.transaction() as connection:
            workspace.save_request(
                connection,
                "request",
                request_digest,
                "correct-session",
                response,
                _canonical_hash(response),
                "2026-07-28T00:00:00+00:00",
            )
            workspace.save_receipt(
                connection,
                receipt["receipt_hash"],
                "request",
                "correct-session",
                0,
                receipt,
                "2026-07-28T00:00:00+00:00",
            )
    assert workspace.integrity()["counts"]["requests"] == 0


def test_mutating_proof_requires_its_persisted_receipt_anchor(tmp_path):
    workspace = _workspace(tmp_path / "proof-receipt.sqlite3")
    request_digest = "digest"
    receipt = _receipt_payload(
        workspace,
        "request",
        request_digest=request_digest,
        step=1,
    )
    response = {
        "proposal_id": "a" * 64,
        "request_id": "request",
        "step": 1,
        "state_before_hash": "b" * 64,
        "state_hash": "c" * 64,
        "decision": "ACCEPT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
        "dry_run": False,
        "audit": {
            "governance": {
                "allowed": True,
                "policy": "test",
                "principal": {
                    "namespace": workspace.namespace,
                    "owner_id": workspace.owner_id,
                },
            }
        },
    }
    _bind_response(workspace, response, request_digest)
    proof = _proof_payload(response)
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            "request",
            request_digest,
            "session",
            response,
            _canonical_hash(response),
            "2026-07-28T00:00:00+00:00",
        )
        workspace.save_receipt(
            connection,
            receipt["receipt_hash"],
            "request",
            "session",
            1,
            receipt,
            "2026-07-28T00:00:00+00:00",
        )
        workspace.save_effect_outbox(
            connection,
            "request",
            "proof_export",
            proof,
            proof["payload_sha256"],
            None,
            "2026-07-28T00:00:00+00:00",
        )
    connection = sqlite3.connect(path := workspace.path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("DELETE FROM receipts")
        connection.commit()
    finally:
        connection.close()

    integrity = _workspace(path).integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_effect_bindings"] == 1


def test_integrity_rejects_corrupt_state_digest_and_reads_do_not_write(tmp_path):
    workspace = _workspace(tmp_path / "state-integrity.sqlite3")
    timestamp = "2026-07-28T00:00:00+00:00"
    state = {
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "session_id": "session",
        "database_generation_id": workspace.database_generation_id,
        "step": 1,
    }
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            state,
            _canonical_hash(state),
            timestamp,
        )
    connection = workspace._connect()
    try:
        before = connection.execute(
            """
            SELECT last_accessed_at FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()["last_accessed_at"]
    finally:
        connection.close()

    assert workspace.read_session("session")["state"] == state
    connection = workspace._connect()
    try:
        after = connection.execute(
            """
            SELECT last_accessed_at FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()["last_accessed_at"]
        connection.execute(
            """
            UPDATE session_state SET state_hash = ?
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            ("0" * 64, workspace.namespace, workspace.owner_id),
        )
    finally:
        connection.close()

    integrity = workspace.integrity()
    assert after == before
    assert integrity["ok"] is False
    assert integrity["invalid_state_digests"] == 1


def test_integrity_rejects_state_bound_to_another_session(tmp_path):
    workspace = _workspace(tmp_path / "state-identity.sqlite3")
    timestamp = "2026-07-28T00:00:00+00:00"

    def state_for(session_id):
        return {
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "session_id": session_id,
            "database_generation_id": workspace.database_generation_id,
            "step": 1,
        }

    state_a = state_for("session-a")
    state_b = state_for("session-b")
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session-a",
            1,
            state_a,
            _canonical_hash(state_a),
            timestamp,
        )
        workspace.save_state(
            connection,
            "session-b",
            1,
            state_b,
            _canonical_hash(state_b),
            timestamp,
        )
        connection.execute(
            """
            UPDATE session_state
            SET state_json = ?, state_hash = ?
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session-a'
            """,
            (
                json.dumps(state_b, sort_keys=True, separators=(",", ":")),
                _canonical_hash(state_b),
                workspace.namespace,
                workspace.owner_id,
            ),
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_state_digests"] == 1
    with pytest.raises(
        GDWConfigurationError,
        match="session state digest or identity is invalid",
    ):
        workspace.read_session("session-a")


def test_integrity_reports_non_object_receipt_and_proof_json(tmp_path):
    workspace = _workspace(tmp_path / "non-object-integrity.sqlite3")
    _queue_proof(workspace)
    timestamp = datetime.now(timezone.utc).isoformat()
    with workspace.transaction() as connection:
        connection.execute(
            """
            INSERT INTO receipts(
                namespace, owner_id, receipt_hash, request_id, session_id,
                step, receipt_json, created_at
            ) VALUES (?, ?, ?, 'request', 'session', 0, '1', ?)
            """,
            (
                workspace.namespace,
                workspace.owner_id,
                "c" * 64,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO proof_outbox(
                namespace, owner_id, proposal_id, payload_json,
                payload_sha256, status, created_at
            ) VALUES (?, ?, 'corrupt-proof', '1', ?, 'PENDING', ?)
            """,
            (
                workspace.namespace,
                workspace.owner_id,
                "d" * 64,
                timestamp,
            ),
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_receipt_digests"] == 1
    assert integrity["invalid_proof_digests"] == 1



def test_request_response_session_is_optional_but_never_contradictory(tmp_path):
    workspace = _workspace(tmp_path / "request-session-binding.sqlite3")
    response = _save_request(
        workspace,
        "request",
        session_id="correct-session",
    )
    response["session_id"] = "wrong-session"
    with workspace.transaction() as connection:
        connection.execute(
            """
            UPDATE requests SET response_json = ?, response_hash = ?
            WHERE namespace = ? AND owner_id = ? AND request_id = 'request'
            """,
            (
                json.dumps(response, sort_keys=True, separators=(",", ":")),
                _canonical_hash(response),
                workspace.namespace,
                workspace.owner_id,
            ),
        )

    with workspace.transaction() as connection:
        with pytest.raises(GDWConfigurationError, match="identity"):
            workspace.cached_request(connection, "request")
    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_request_digests"] == 1


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("request_digest", "f" * 64),
        ("proposal_id", "e" * 64),
        ("state_before_hash", "d" * 64),
        ("state_after_hash", "d" * 64),
        ("scheduler_mode", "attacker_mode"),
        ("governance_evidence_sha256", "c" * 64),
        ("credential_key_id", "attacker-key"),
    ),
)
def test_receipt_cross_record_fields_are_bound_before_persistence(
    tmp_path,
    field,
    replacement,
):
    workspace = _workspace(tmp_path / f"receipt-binding-{field}.sqlite3")
    request_digest, response, receipt = _accepted_response_and_receipt(workspace)
    changed = json.loads(json.dumps(receipt))
    changed[field] = replacement
    changed.pop("receipt_hash")
    changed["receipt_hash"] = _canonical_hash(changed)
    response["receipt_hash"] = changed["receipt_hash"]

    with pytest.raises(GDWConfigurationError, match="receipt"):
        with workspace.transaction() as connection:
            workspace.save_request(
                connection,
                "request",
                request_digest,
                "session",
                response,
                _canonical_hash(response),
                "2026-07-28T00:00:00+00:00",
            )
            workspace.save_receipt(
                connection,
                changed["receipt_hash"],
                "request",
                "session",
                0,
                changed,
                "2026-07-28T00:00:00+00:00",
            )
    assert workspace.integrity()["counts"]["requests"] == 0


def test_repeated_gc_never_hides_cross_record_receipt_contradiction(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    workspace = _workspace(tmp_path / "receipt-gc-binding.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    request_digest, response, receipt = _accepted_response_and_receipt(workspace)
    contradictory = dict(receipt)
    contradictory["request_digest"] = "f" * 64
    contradictory.pop("receipt_hash")
    contradictory["receipt_hash"] = _canonical_hash(contradictory)
    response["receipt_hash"] = contradictory["receipt_hash"]
    receipt_text = json.dumps(
        contradictory,
        sort_keys=True,
        separators=(",", ":"),
    )
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            "request",
            request_digest,
            "session",
            response,
            _canonical_hash(response),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        connection.execute(
            """
            INSERT INTO receipts(
                namespace, owner_id, receipt_hash, request_id, session_id,
                step, receipt_json, created_at
            ) VALUES (?, ?, ?, 'request', 'session', 0, ?, ?)
            """,
            (
                workspace.namespace,
                workspace.owner_id,
                contradictory["receipt_hash"],
                receipt_text,
                start.isoformat(),
            ),
        )

    for seconds in (30, 60):
        integrity = workspace.integrity()
        assert integrity["ok"] is False
        assert integrity["invalid_receipt_digests"] == 1
        result = workspace.collect_garbage(
            now=start + timedelta(seconds=seconds)
        )
        assert result["requests_tombstoned"] == 0
        connection = workspace._connect()
        try:
            row = connection.execute(
                """
                SELECT q.lifecycle, q.response_json, r.receipt_json
                FROM requests q JOIN receipts r
                  ON r.namespace = q.namespace AND r.owner_id = q.owner_id
                 AND r.request_id = q.request_id
                WHERE q.namespace = ? AND q.owner_id = ?
                  AND q.request_id = 'request'
                """,
                (workspace.namespace, workspace.owner_id),
            ).fetchone()
        finally:
            connection.close()
        assert row["lifecycle"] == "ACTIVE"
        assert row["response_json"] is not None
        assert row["receipt_json"] == receipt_text


def test_repeated_gc_never_hides_corrupt_session_state(tmp_path, monkeypatch):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    workspace = _workspace(tmp_path / "session-gc-integrity.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    state = {
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "session_id": "session",
        "database_generation_id": workspace.database_generation_id,
        "step": 1,
    }
    state_text = json.dumps(state, sort_keys=True, separators=(",", ":"))
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            state,
            _canonical_hash(state),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        connection.execute(
            """
            UPDATE session_state SET state_hash = ?
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            ("0" * 64, workspace.namespace, workspace.owner_id),
        )

    for seconds in (30, 60):
        integrity = workspace.integrity()
        assert integrity["ok"] is False
        assert integrity["invalid_state_digests"] == 1
        with pytest.raises(
            GDWConfigurationError,
            match="session compaction refused invalid lifecycle",
        ):
            workspace.collect_garbage(
                now=start + timedelta(seconds=seconds)
            )
        connection = workspace._connect()
        try:
            row = connection.execute(
                """
                SELECT lifecycle, state_json, tombstoned_at
                FROM session_state
                WHERE namespace = ? AND owner_id = ?
                  AND session_id = 'session'
                """,
                (workspace.namespace, workspace.owner_id),
            ).fetchone()
        finally:
            connection.close()
        assert row["lifecycle"] == "ACTIVE"
        assert row["state_json"] == state_text
        assert row["tombstoned_at"] is None


def test_repeated_gc_never_hides_corrupt_legacy_proof(tmp_path, monkeypatch):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / "proof-gc-integrity.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 64,
        "request_id": "legacy-request",
        "owner_id": workspace.owner_id,
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = _canonical_hash(payload)
    with workspace.transaction() as connection:
        workspace.save_proof_outbox(
            connection,
            payload["proposal_id"],
            payload,
            payload["payload_sha256"],
            start.isoformat(),
        )
    artifact = export_proof_payload(
        payload,
        artifact_id=payload["payload_sha256"],
        owner_id=workspace.owner_id,
    )
    workspace.mark_proof_exported(
        payload["proposal_id"],
        artifact,
        (start + timedelta(seconds=1)).isoformat(),
        expected_payload=payload,
        expected_payload_sha256=payload["payload_sha256"],
    )
    tampered = dict(payload)
    tampered["formal_status"] = "TAMPERED"
    tampered_text = json.dumps(
        tampered,
        sort_keys=True,
        separators=(",", ":"),
    )
    with workspace.transaction() as connection:
        connection.execute(
            """
            UPDATE proof_outbox SET payload_json = ?
            WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
            """,
            (
                tampered_text,
                workspace.namespace,
                workspace.owner_id,
                payload["proposal_id"],
            ),
        )

    for seconds in (20, 50):
        integrity = workspace.integrity()
        assert integrity["ok"] is False
        assert integrity["invalid_proof_digests"] == 1
        with pytest.raises(
            GDWConfigurationError,
            match="proof compaction refused invalid lifecycle",
        ):
            workspace.collect_garbage(
                now=start + timedelta(seconds=seconds)
            )
        connection = workspace._connect()
        try:
            row = connection.execute(
                """
                SELECT status, payload_json, artifact_json, tombstoned_at
                FROM proof_outbox
                WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
                """,
                (
                    workspace.namespace,
                    workspace.owner_id,
                    payload["proposal_id"],
                ),
            ).fetchone()
        finally:
            connection.close()
        assert row["status"] == "EXPORTED"
        assert row["payload_json"] == tampered_text
        assert row["artifact_json"] is not None
        assert row["tombstoned_at"] is None


def test_receipt_created_at_is_canonical_and_bound_to_its_row(tmp_path):
    workspace = _workspace(tmp_path / "receipt-created-at.sqlite3")
    timestamp = "2026-07-28T00:00:00+00:00"
    later = "2026-07-28T00:00:01+00:00"
    request_digest, response, receipt = _accepted_response_and_receipt(workspace)
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            "request",
            request_digest,
            "session",
            response,
            _canonical_hash(response),
            timestamp,
        )

    with pytest.raises(GDWConfigurationError, match="created_at"):
        with workspace.transaction() as connection:
            workspace.save_receipt(
                connection,
                receipt["receipt_hash"],
                "request",
                "session",
                0,
                receipt,
                later,
            )

    with workspace.transaction() as connection:
        workspace.save_receipt(
            connection,
            receipt["receipt_hash"],
            "request",
            "session",
            0,
            receipt,
            timestamp,
        )
        connection.execute(
            """
            UPDATE receipts SET created_at = ?
            WHERE namespace = ? AND owner_id = ? AND request_id = 'request'
            """,
            (later, workspace.namespace, workspace.owner_id),
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_receipt_digests"] == 1


def test_gc_never_erases_valid_state_with_impossible_expiry(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    workspace = _workspace(tmp_path / "session-expiry-integrity.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    state = {
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "session_id": "session",
        "database_generation_id": workspace.database_generation_id,
        "step": 1,
    }
    state_text = json.dumps(state, sort_keys=True, separators=(",", ":"))
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            state,
            _canonical_hash(state),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        connection.execute(
            """
            UPDATE session_state SET expires_at = ?
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (
                (start - timedelta(seconds=1)).isoformat(),
                workspace.namespace,
                workspace.owner_id,
            ),
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_state_digests"] == 1
    with pytest.raises(
        GDWConfigurationError,
        match="session compaction refused invalid lifecycle",
    ):
        workspace.collect_garbage(now=start + timedelta(seconds=30))
    with workspace.transaction() as connection:
        row = connection.execute(
            """
            SELECT lifecycle, state_json, tombstoned_at FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()
    assert row["lifecycle"] == "ACTIVE"
    assert row["state_json"] == state_text
    assert row["tombstoned_at"] is None


def test_integrity_rejects_active_session_with_missing_state(tmp_path):
    workspace = _workspace(tmp_path / "active-session-missing-state.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    state = {
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "session_id": "session",
        "database_generation_id": workspace.database_generation_id,
        "step": 1,
    }
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            state,
            _canonical_hash(state),
            start.isoformat(),
        )
        connection.execute(
            """
            UPDATE session_state SET state_json = NULL
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (workspace.namespace, workspace.owner_id),
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_state_digests"] == 1


def test_gc_never_purges_session_tombstoned_before_expiry(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    workspace = _workspace(tmp_path / "session-tombstone-order.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    state = {
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "session_id": "session",
        "database_generation_id": workspace.database_generation_id,
        "step": 1,
    }
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            state,
            _canonical_hash(state),
            start.isoformat(),
            expires_at=(start + timedelta(seconds=10)).isoformat(),
        )
        connection.execute(
            """
            UPDATE session_state
            SET lifecycle = 'TOMBSTONED', state_json = NULL, tombstoned_at = ?
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (
                (start + timedelta(seconds=5)).isoformat(),
                workspace.namespace,
                workspace.owner_id,
            ),
        )

    integrity = workspace.integrity()
    assert integrity["ok"] is False
    assert integrity["invalid_state_digests"] == 1
    with pytest.raises(
        GDWConfigurationError,
        match="session purge refused invalid lifecycle",
    ):
        workspace.collect_garbage(now=start + timedelta(seconds=40))
    with workspace.transaction() as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = 'session'
            """,
            (workspace.namespace, workspace.owner_id),
        ).fetchone()[0]
    assert count == 1


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("namespace", "attacker-namespace"),
        ("owner_id", "attacker-owner"),
        ("database_generation_id", "f" * 32),
    ),
)
def test_repeated_gc_never_hides_consistently_rebound_legacy_proof(
    tmp_path,
    monkeypatch,
    field,
    replacement,
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    workspace = _workspace(tmp_path / f"proof-rebind-{field}.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": "a" * 64,
        "request_id": "legacy-request",
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "database_generation_id": workspace.database_generation_id,
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = _canonical_hash(payload)
    with workspace.transaction() as connection:
        workspace.save_proof_outbox(
            connection,
            payload["proposal_id"],
            payload,
            payload["payload_sha256"],
            start.isoformat(),
        )
    artifact = export_proof_payload(
        payload,
        artifact_id=payload["payload_sha256"],
        owner_id=workspace.owner_id,
    )
    workspace.mark_proof_exported(
        payload["proposal_id"],
        artifact,
        (start + timedelta(seconds=1)).isoformat(),
        expected_payload=payload,
        expected_payload_sha256=payload["payload_sha256"],
    )

    rebound = dict(payload)
    rebound[field] = replacement
    rebound.pop("payload_sha256")
    rebound["payload_sha256"] = _canonical_hash(rebound)
    rebound_artifact = export_proof_payload(
        rebound,
        artifact_id=rebound["payload_sha256"],
        owner_id=workspace.owner_id,
    )
    rebound_text = json.dumps(
        rebound,
        sort_keys=True,
        separators=(",", ":"),
    )
    rebound_artifact_text = json.dumps(
        rebound_artifact,
        sort_keys=True,
        separators=(",", ":"),
    )
    with workspace.transaction() as connection:
        connection.execute(
            """
            UPDATE proof_outbox
            SET payload_json = ?, payload_sha256 = ?, artifact_json = ?
            WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
            """,
            (
                rebound_text,
                rebound["payload_sha256"],
                rebound_artifact_text,
                workspace.namespace,
                workspace.owner_id,
                payload["proposal_id"],
            ),
        )

    for seconds in (20, 50):
        integrity = workspace.integrity()
        assert integrity["ok"] is False
        assert integrity["invalid_proof_digests"] == 1
        with pytest.raises(
            GDWConfigurationError,
            match="proof compaction refused invalid lifecycle",
        ):
            workspace.collect_garbage(
                now=start + timedelta(seconds=seconds)
            )
        with workspace.transaction() as connection:
            row = connection.execute(
                """
                SELECT payload_json, payload_sha256, artifact_json, tombstoned_at
                FROM proof_outbox
                WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
                """,
                (
                    workspace.namespace,
                    workspace.owner_id,
                    payload["proposal_id"],
                ),
            ).fetchone()
        assert row["payload_json"] == rebound_text
        assert row["payload_sha256"] == rebound["payload_sha256"]
        assert row["artifact_json"] == rebound_artifact_text
        assert row["tombstoned_at"] is None


def test_gc_request_and_receipt_purge_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    monkeypatch.setenv(
        "GDW_RECEIPT_PROJECTION_DIR",
        str(tmp_path / "receipts"),
    )
    workspace = _workspace(tmp_path / "bounded-receipt-purge.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    for index in range(3):
        _queue_expired_exported_receipt(
            workspace,
            f"receipt-request-{index}",
            start,
            f"receipt-worker-{index}",
        )
    assert workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=10,
    )["effects_compacted"] == 3
    assert workspace.collect_garbage(
        now=start + timedelta(seconds=50),
        limit=10,
    )["requests_tombstoned"] == 3

    for expected_remaining in (2, 1, 0):
        workspace.collect_garbage(
            now=start + timedelta(seconds=100),
            limit=1,
        )
        with workspace.transaction() as connection:
            counts = {
                "effects": connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox"
                ).fetchone()[0],
                "requests": connection.execute(
                    "SELECT COUNT(*) FROM requests"
                ).fetchone()[0],
                "receipts": connection.execute(
                    "SELECT COUNT(*) FROM receipts"
                ).fetchone()[0],
            }
        assert counts == {
            "effects": expected_remaining,
            "requests": expected_remaining,
            "receipts": expected_remaining,
        }
