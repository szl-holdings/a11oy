import hashlib
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from gdw_proofs import build_proof_payload
from gdw_workspace import (
    GDWConfigurationError,
    GDWQuotaPolicy,
    GDWWorkspace,
)


TRANSIENT_LINK_ERROR = (
    "OSError: [Errno 95] Operation not supported: "
    "'/data/.stage' -> '/data/proof.json'"
)


def _canonical_hash(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _workspace(path, owner="owner-a"):
    return GDWWorkspace(
        str(path),
        namespace="a11oy",
        owner_id=owner,
        quota_policy=GDWQuotaPolicy(
            owner_active_sessions=100,
            owner_active_requests=100,
            owner_pending_effects=100,
            owner_stored_bytes=1_000_000,
            global_active_sessions=1_000,
            global_active_requests=1_000,
            global_pending_effects=1_000,
            global_stored_bytes=10_000_000,
        ),
    )


def _queue_proof(
    workspace,
    request_id,
    created_at,
    *,
    max_attempts=5,
):
    request_digest = hashlib.sha256(request_id.encode()).hexdigest()
    governance = {
        "allowed": False,
        "principal": {
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
        },
    }
    response = {
        "request_id": request_id,
        "request_digest": request_digest,
        "session_id": "session",
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "b" * 64,
        "decision": "REJECT",
        "scheduler_mode": "kda_local",
        "receipt_hash": None,
        "dry_run": True,
        "database_generation_id": workspace.database_generation_id,
        "principal": {
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "key_id": "test-key",
        },
        "audit": {"governance": governance},
    }
    response["proposal_id"] = _canonical_hash(
        {
            "schema": "szl.gdw.proposal-identity/v1",
            "database_generation_id": workspace.database_generation_id,
            "namespace": workspace.namespace,
            "owner_id": workspace.owner_id,
            "request_id": request_id,
            "request_digest": request_digest,
            "state_before_hash": response["state_before_hash"],
            "governance_evidence_sha256": _canonical_hash(governance),
        }
    )
    proof = build_proof_payload(
        proposal_id=response["proposal_id"],
        request_id=request_id,
        request_digest=request_digest,
        namespace=workspace.namespace,
        owner_id=workspace.owner_id,
        database_generation_id=workspace.database_generation_id,
        step=0,
        before_hash="b" * 64,
        after_hash="b" * 64,
        decision="REJECT",
        scheduler_mode="kda_local",
        receipt_hash="",
        dry_run=True,
        governance=governance,
    )
    with workspace.transaction() as connection:
        workspace.save_request(
            connection,
            request_id,
            request_digest,
            "session",
            response,
            _canonical_hash(response),
            created_at.isoformat(),
        )
        key = workspace.save_effect_outbox(
            connection,
            request_id,
            "proof_export",
            proof,
            proof["payload_sha256"],
            None,
            created_at.isoformat(),
            max_attempts=max_attempts,
        )
    return key


def _effect_row(workspace, key):
    connection = sqlite3.connect(workspace.path)
    connection.row_factory = sqlite3.Row
    try:
        return dict(
            connection.execute(
                """
                SELECT * FROM effect_outbox
                WHERE namespace = ? AND owner_id = ?
                      AND idempotency_key = ?
                """,
                (workspace.namespace, workspace.owner_id, key),
            ).fetchone()
        )
    finally:
        connection.close()


def _make_retry_scheduled(workspace, key, start, error=TRANSIENT_LINK_ERROR):
    claim = workspace.claim_effects("worker-1", now=start)[0]
    assert claim["idempotency_key"] == key
    assert workspace.release_effect(
        key,
        "worker-1",
        claim["claim_generation"],
        error,
        now=start,
    ) == "PENDING"
    return claim


def test_recovery_only_advances_due_time_and_preserves_attempt_accounting(
    tmp_path,
):
    workspace = _workspace(tmp_path / "recovery.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "recover-1", start)
    first = _make_retry_scheduled(workspace, key, start)
    before = _effect_row(workspace, key)

    report = workspace.recover_retry_scheduled_effects(
        now=start + timedelta(seconds=1),
        limit=10,
    )
    after = _effect_row(workspace, key)

    changed = {
        field
        for field in before
        if before[field] != after[field]
    }
    assert changed == {"next_attempt_at"}
    assert report["status"] == "RESCHEDULED"
    assert report["eligible_effects"] == 1
    assert report["rescheduled_effects"] == 1
    assert report["attempts_before"] == report["attempts_after"] == 1
    assert len(report["selection_sha256"]) == 64
    assert after["status"] == "PENDING"
    assert after["attempts"] == first["attempt"]
    assert after["claim_generation"] == first["claim_generation"]

    second = workspace.claim_effects(
        "worker-2",
        now=start + timedelta(seconds=1),
    )[0]
    assert second["attempt"] == first["attempt"] + 1
    assert second["claim_generation"] == first["claim_generation"] + 1


def test_recovery_global_limit_refuses_partial_rescheduling(tmp_path):
    path = tmp_path / "bounded.sqlite3"
    first_workspace = _workspace(path, owner="owner-a")
    second_workspace = _workspace(path, owner="owner-b")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    first_key = _queue_proof(first_workspace, "bounded-a", start)
    second_key = _queue_proof(second_workspace, "bounded-b", start)
    _make_retry_scheduled(first_workspace, first_key, start)
    _make_retry_scheduled(second_workspace, second_key, start)
    before = (
        _effect_row(first_workspace, first_key),
        _effect_row(second_workspace, second_key),
    )

    with pytest.raises(
        GDWConfigurationError,
        match="bounded limit",
    ):
        first_workspace.recover_retry_scheduled_effects(
            now=start + timedelta(seconds=1),
            limit=1,
        )

    assert _effect_row(first_workspace, first_key) == before[0]
    assert _effect_row(second_workspace, second_key) == before[1]


def test_recovery_ignores_non_allowlisted_and_already_due_failures(tmp_path):
    workspace = _workspace(tmp_path / "ineligible.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    unknown_key = _queue_proof(workspace, "unknown-error", start)
    _make_retry_scheduled(
        workspace,
        unknown_key,
        start,
        error="ValueError: deterministic mismatch",
    )
    due_key = _queue_proof(workspace, "already-due", start)
    _make_retry_scheduled(workspace, due_key, start)
    recovery_time = start + timedelta(seconds=6)
    before = (
        _effect_row(workspace, unknown_key),
        _effect_row(workspace, due_key),
    )

    report = workspace.recover_retry_scheduled_effects(
        now=recovery_time,
    )

    assert report["status"] == "NO_ELIGIBLE_EFFECTS"
    assert report["rescheduled_effects"] == 0
    assert _effect_row(workspace, unknown_key) == before[0]
    assert _effect_row(workspace, due_key) == before[1]


def test_recovery_defers_without_mutation_while_supervisor_owns_claim(
    tmp_path,
):
    workspace = _workspace(tmp_path / "claimed.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "claimed", start)
    workspace.claim_effects(
        "active-worker",
        lease_seconds=300,
        now=start,
    )
    before = _effect_row(workspace, key)

    report = workspace.recover_retry_scheduled_effects(
        now=start + timedelta(seconds=1),
    )

    assert report["status"] == "DEFERRED_ACTIVE_CLAIM"
    assert report["claimed_effects"] == 1
    assert _effect_row(workspace, key) == before


def test_recovery_rolls_back_every_timer_when_one_update_aborts(tmp_path):
    workspace = _workspace(tmp_path / "rollback.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    first_key = _queue_proof(workspace, "rollback-a", start)
    _make_retry_scheduled(workspace, first_key, start)
    second_key = _queue_proof(workspace, "rollback-b", start)
    _make_retry_scheduled(workspace, second_key, start)
    before = (
        _effect_row(workspace, first_key),
        _effect_row(workspace, second_key),
    )
    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            f"""
            CREATE TRIGGER abort_second_recovery
            BEFORE UPDATE OF next_attempt_at ON effect_outbox
            WHEN OLD.idempotency_key = '{second_key}'
                 AND NEW.next_attempt_at != OLD.next_attempt_at
            BEGIN
                SELECT RAISE(ABORT, 'injected recovery failure');
            END
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError):
        workspace.recover_retry_scheduled_effects(
            now=start + timedelta(seconds=1),
        )

    assert _effect_row(workspace, first_key) == before[0]
    assert _effect_row(workspace, second_key) == before[1]


def test_recovery_serializes_with_normal_supervisor_claim(tmp_path):
    workspace = _workspace(tmp_path / "race.sqlite3")
    peer = _workspace(tmp_path / "race.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    due = start + timedelta(seconds=1)
    key = _queue_proof(workspace, "race", start)
    first = _make_retry_scheduled(workspace, key, start)
    barrier = threading.Barrier(2)

    def recover():
        barrier.wait()
        return workspace.recover_retry_scheduled_effects(now=due)

    def claim():
        barrier.wait()
        return peer.claim_effects("racing-worker", now=due)

    with ThreadPoolExecutor(max_workers=2) as executor:
        recovery_future = executor.submit(recover)
        claim_future = executor.submit(claim)
        recovery_report = recovery_future.result()
        claims = claim_future.result()

    if not claims:
        claims = peer.claim_effects("followup-worker", now=due)
    assert len(claims) == 1
    assert claims[0]["idempotency_key"] == key
    assert claims[0]["attempt"] == first["attempt"] + 1
    assert claims[0]["claim_generation"] == first["claim_generation"] + 1
    assert recovery_report["status"] in {
        "RESCHEDULED",
        "DEFERRED_ACTIVE_CLAIM",
    }
    row = _effect_row(workspace, key)
    assert row["status"] == "CLAIMED"
    assert row["attempts"] == 2
    assert row["claim_generation"] == 2
