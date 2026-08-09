import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from gdw_proofs import build_proof_payload, export_proof_payload
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
):
    receipt = {
        "request_id": request_id,
        "request_digest": request_digest or hashlib.sha256(
            request_id.encode()
        ).hexdigest(),
        "session_id": session_id,
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "database_generation_id": workspace.database_generation_id,
        "step": 0,
        "decision": "REJECT",
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    return receipt


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
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            {
                "large": "state",
                "database_generation_id": workspace.database_generation_id,
            },
            "state-hash",
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
    assert collected["requests_tombstoned"] == 1
    assert collected["effects_compacted"] == 1
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
            0,
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
