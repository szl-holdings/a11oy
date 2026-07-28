import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

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


def _save_request(workspace, request_id, session_id="session", created_at=None):
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    response = {"request_id": request_id, "owner": workspace.owner_id}
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            request_id,
            hashlib.sha256(request_id.encode()).hexdigest(),
            session_id,
            response,
            hashlib.sha256(json.dumps(response).encode()).hexdigest(),
            timestamp,
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
            state = {"marker": marker}
            workspace.save_state(
                connection,
                "same-session",
                1,
                state,
                hashlib.sha256(marker.encode()).hexdigest(),
                timestamp,
            )
            workspace.save_request(
                connection,
                "same-request",
                f"digest-{marker}",
                "same-session",
                {"marker": marker},
                f"response-{marker}",
                timestamp,
            )

    assert owner_a.read_session("same-session")["state"] == {"marker": "a"}
    assert owner_b.read_session("same-session")["state"] == {"marker": "b"}
    assert owner_c.read_session("same-session")["state"] == {"marker": "c"}
    with owner_b.transaction() as connection:
        assert owner_b.cached_request(connection, "same-request") == (
            "digest-b",
            {"marker": "b"},
        )
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
    migrated = _workspace(path, owner="legacy-owner", namespace="legacy-ns")
    assert migrated.read_session("legacy-session")["state"] == {"legacy": True}
    assert migrated.integrity()["schema_version"] == SCHEMA_VERSION
    assert (
        _workspace(path, owner="other", namespace="legacy-ns").read_session(
            "legacy-session"
        )
        is None
    )


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
        workspace.save_state(connection, "one", 1, {"n": 1}, "h1", timestamp)
    with pytest.raises(GDWQuotaExceeded) as exc:
        with workspace.transaction() as connection:
            workspace.save_state(connection, "two", 1, {"n": 2}, "h2", timestamp)
    assert exc.value.code == "OWNER_SESSIONS_QUOTA"
    assert workspace.integrity()["counts"]["session_state"] == 1

    shared_path = tmp_path / "global.sqlite3"
    global_policy = _policy(global_active_sessions=1)
    first = _workspace(shared_path, owner="first", policy=global_policy)
    second = _workspace(shared_path, owner="second", policy=global_policy)
    with first.transaction() as connection:
        first.save_state(connection, "one", 1, {"n": 1}, "h1", timestamp)
    with pytest.raises(GDWQuotaExceeded) as exc:
        with second.transaction() as connection:
            second.save_state(connection, "two", 1, {"n": 2}, "h2", timestamp)
    assert exc.value.code == "GLOBAL_SESSIONS_QUOTA"
    assert second.integrity()["counts"]["session_state"] == 0


def test_pending_effect_quota_rolls_back_the_whole_transition(tmp_path):
    workspace = _workspace(
        tmp_path / "atomic.sqlite3",
        policy=_policy(owner_pending_effects=1),
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    with pytest.raises(GDWQuotaExceeded):
        with workspace.transaction() as connection:
            workspace.save_state(
                connection, "session", 1, {"state": 1}, "state-hash", timestamp
            )
            workspace.save_request(
                connection,
                "request",
                "request-digest",
                "session",
                {"ok": True},
                "response-hash",
                timestamp,
            )
            workspace.save_effect_outbox(
                connection,
                "request",
                "receipt_projection",
                {"receipt": True},
                "receipt-payload-hash",
                None,
                timestamp,
            )
            workspace.save_effect_outbox(
                connection,
                "request",
                "proof_export",
                {"proof": True},
                "proof-payload-hash",
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
    _save_request(workspace, "request", created_at=start.isoformat())
    with workspace.transaction() as connection:
        key = workspace.save_effect_outbox(
            connection,
            "request",
            "proof_export",
            {"proof": "payload"},
            "payload-hash",
            None,
            start.isoformat(),
            max_attempts=2,
        )

    first = workspace.claim_effects("worker", now=start)
    assert first[0]["attempt"] == 1
    assert first[0]["idempotency_key"] == key
    assert workspace.release_effect(key, "worker", "temporary", now=start) == "PENDING"
    assert workspace.claim_effects("worker", now=start + timedelta(seconds=1)) == []

    retry_time = start + timedelta(seconds=workspace.effect_backoff_seconds)
    second = workspace.claim_effects("worker", now=retry_time)
    assert second[0]["attempt"] == 2
    assert (
        workspace.release_effect(key, "worker", "permanent", now=retry_time)
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


def test_gc_tombstones_expired_objects_but_never_unexported_effects(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GDW_RETENTION_SECONDS", "10")
    monkeypatch.setenv("GDW_TOMBSTONE_SECONDS", "20")
    workspace = _workspace(tmp_path / "gc.sqlite3")
    start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    with workspace.transaction() as connection:
        workspace.save_state(
            connection,
            "session",
            1,
            {"large": "state"},
            "state-hash",
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        workspace.save_request(
            connection,
            "request",
            "digest",
            "session",
            {"large": "response"},
            "response-hash",
            start.isoformat(),
            expires_at=(start + timedelta(seconds=1)).isoformat(),
        )
        key = workspace.save_effect_outbox(
            connection,
            "request",
            "proof_export",
            {"large": "unexported"},
            "payload-hash",
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
    assert json.loads(effect["payload_json"]) == {"large": "unexported"}
    assert request["lifecycle"] == "ACTIVE"
    assert request["response_json"] is not None

    claim = workspace.claim_effects("worker", now=start + timedelta(seconds=30))[0]
    workspace.mark_effect_exported(
        claim["idempotency_key"],
        "worker",
        {"artifact": True},
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
