#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import base64
import hashlib
import json
import multiprocessing
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

import gdw_runtime
import gdw_workspace as workspace_module
from gdw_proofs import build_proof_payload
from gdw_workspace import (
    GDWConfigurationError,
    GDWQuotaPolicy,
    GDWWorkspace,
)


RECOVERY_CREDENTIAL_KEY_ID = "gdw-recovery-operator-key-v1"
RECOVERY_SOURCE_REVISION = "b" * 40


def _canonical_hash(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _recovery_governance(
    workspace,
    recovery_id,
    *,
    limit=100,
    source_revision=RECOVERY_SOURCE_REVISION,
    database_generation_id=None,
):
    generation_id = database_generation_id or workspace.database_generation_id
    binding = {
        "schema": "szl.gdw.transient-effect-recovery-authorization/v1",
        "action_type": "gdw.transient-effect-recovery",
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "credential_key_id": RECOVERY_CREDENTIAL_KEY_ID,
        "recovery_id": recovery_id,
        "source_revision": source_revision,
        "database_generation_id": generation_id,
        "limit": limit,
        "failure_class": "hf-hard-link-enotsup/v1",
    }
    binding_sha256 = _canonical_hash(binding)
    witnesses = [
        {
            "id": (
                f"principal:{workspace.namespace}:{workspace.owner_id}:"
                f"{RECOVERY_CREDENTIAL_KEY_ID}"
            ),
            "role": "operator",
            "attested": True,
        },
        {
            "id": f"workload:szl-holdings/a11oy@{source_revision}",
            "role": "workload",
            "attested": True,
        },
    ]
    return {
        "schema": "szl.gdw.transient-effect-recovery-governance/v1",
        "decision": "ALLOW",
        "binding": binding,
        "binding_sha256": binding_sha256,
        "policy_gateway": {
            "decision": "ALLOW",
            "gate": "ThresholdPolicySeverity",
            "receipt_hash": "c" * 64,
            "receipt_signed": True,
            "receipts_in_eq_out": True,
            "action_id": f"gdw-recovery:{binding_sha256}",
            "witnesses": witnesses,
        },
    }


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


def _queue_receipt(
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
    receipt = {
        "request_id": request_id,
        "request_digest": request_digest,
        "session_id": "session",
        "namespace": workspace.namespace,
        "owner_id": workspace.owner_id,
        "database_generation_id": workspace.database_generation_id,
        "step": 0,
        "decision": "REJECT",
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    response = {
        "request_id": request_id,
        "request_digest": request_digest,
        "session_id": "session",
        "step": 0,
        "state_before_hash": "b" * 64,
        "state_hash": "b" * 64,
        "decision": "REJECT",
        "scheduler_mode": "kda_local",
        "receipt_hash": receipt["receipt_hash"],
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
        workspace.save_receipt(
            connection,
            receipt["receipt_hash"],
            request_id,
            "session",
            0,
            receipt,
            created_at.isoformat(),
        )
        key = workspace.save_effect_outbox(
            connection,
            request_id,
            "receipt_projection",
            receipt,
            _canonical_hash(receipt),
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


def _effect_rows(workspace):
    connection = sqlite3.connect(workspace.path)
    connection.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT * FROM effect_outbox
                WHERE namespace = ? AND owner_id = ?
                ORDER BY request_id, kind
                """,
                (workspace.namespace, workspace.owner_id),
            ).fetchall()
        ]
    finally:
        connection.close()


def _audit_rows(workspace):
    connection = sqlite3.connect(workspace.path)
    connection.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT * FROM effect_recovery_audit
                WHERE namespace = ? AND owner_id = ?
                ORDER BY recovery_id
                """,
                (workspace.namespace, workspace.owner_id),
            ).fetchall()
        ]
    finally:
        connection.close()


def _usage_row(workspace):
    connection = sqlite3.connect(workspace.path)
    connection.row_factory = sqlite3.Row
    try:
        return dict(
            connection.execute(
                """
                SELECT * FROM usage
                WHERE namespace = ? AND owner_id = ?
                """,
                (workspace.namespace, workspace.owner_id),
            ).fetchone()
        )
    finally:
        connection.close()


def _persist_resealed_audit(workspace, recovery_id, report):
    outcome = dict(report)
    receipt = dict(outcome.pop("audit_receipt"))
    outcome.pop("replayed")
    outcome.pop("governance")
    outcome_sha256 = _canonical_hash(outcome)
    receipt["outcome_sha256"] = outcome_sha256
    receipt_payload = {
        key: value
        for key, value in receipt.items()
        if key
        not in {
            "receipt_status",
            "receipt_sha256",
            "dsse_envelope_sha256",
            "chain_sha256",
            "dsse_envelope",
        }
    }
    receipt_sha256 = _canonical_hash(receipt_payload)
    receipt["receipt_sha256"] = receipt_sha256
    receipt["chain_sha256"] = _canonical_hash(
        {
            "previous_chain_sha256": receipt["previous_chain_sha256"],
            "receipt_sha256": receipt_sha256,
            "receipt_status": receipt["receipt_status"],
            "dsse_envelope_sha256": receipt["dsse_envelope_sha256"],
        }
    )
    report["audit_receipt"] = receipt
    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            """
            UPDATE effect_recovery_audit
            SET outcome_sha256 = ?, receipt_sha256 = ?, chain_sha256 = ?,
                report_json = ?
            WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
            """,
            (
                outcome_sha256,
                receipt_sha256,
                receipt["chain_sha256"],
                json.dumps(report, sort_keys=True, separators=(",", ":")),
                workspace.namespace,
                workspace.owner_id,
                recovery_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _recover(
    workspace,
    now,
    *,
    recovery_id="recovery-1",
    limit=100,
    expected_database_generation_id=None,
):
    generation_id = (
        expected_database_generation_id
        if expected_database_generation_id is not None
        else workspace.database_generation_id
    )
    return workspace.recover_retry_scheduled_effects(
        now=now,
        limit=limit,
        recovery_id=recovery_id,
        credential_key_id=RECOVERY_CREDENTIAL_KEY_ID,
        expected_source_revision=RECOVERY_SOURCE_REVISION,
        expected_database_generation_id=generation_id,
        governance=_recovery_governance(
            workspace,
            recovery_id,
            limit=limit,
            database_generation_id=generation_id,
        ),
    )


def _assert_audit_receipt(report):
    assert report["replayed"] is False
    receipt = report["audit_receipt"]
    assert receipt["schema"] == (
        "szl.gdw.transient-effect-recovery-receipt/v2"
    )
    assert len(receipt["receipt_sha256"]) == 64
    assert len(receipt["outcome_sha256"]) == 64
    assert receipt["database_generation_id"] == report[
        "database_generation_id"
    ]
    outcome = dict(report)
    outcome.pop("audit_receipt")
    outcome.pop("replayed")
    outcome.pop("governance")
    assert receipt["outcome_sha256"] == _canonical_hash(outcome)
    receipt_payload = {
        key: value
        for key, value in receipt.items()
        if key
        not in {
            "receipt_status",
            "receipt_sha256",
            "dsse_envelope_sha256",
            "chain_sha256",
            "dsse_envelope",
        }
    }
    assert receipt["receipt_sha256"] == _canonical_hash(receipt_payload)
    assert receipt["dsse_envelope"]["signed"] in {True, False}
    assert receipt["atomic_with_mutation"] is True
    return receipt


def _recover_process(
    database_path,
    owner_id,
    now_text,
    recovery_id,
    expected_generation,
    start_barrier,
    output_queue,
):
    """Exercise recovery through independent SQLite connections/processes."""

    try:
        workspace = _workspace(database_path, owner=owner_id)
        start_barrier.wait(timeout=20)
        report = workspace.recover_retry_scheduled_effects(
            now=now_text,
            limit=100,
            recovery_id=recovery_id,
            credential_key_id=RECOVERY_CREDENTIAL_KEY_ID,
            expected_source_revision=RECOVERY_SOURCE_REVISION,
            expected_database_generation_id=expected_generation,
            governance=_recovery_governance(
                workspace,
                recovery_id,
                database_generation_id=expected_generation,
            ),
        )
        output_queue.put(("ok", report))
    except Exception as exc:  # pragma: no cover - asserted in parent process
        output_queue.put(("error", type(exc).__name__, str(exc)))


def _claim_process(
    database_path,
    owner_id,
    now_text,
    start_barrier,
    output_queue,
):
    """Race the ordinary supervisor claim path from a separate process."""

    try:
        workspace = _workspace(database_path, owner=owner_id)
        start_barrier.wait(timeout=20)
        claims = workspace.claim_effects(
            "process-racing-worker",
            now=now_text,
        )
        output_queue.put(("ok", claims))
    except Exception as exc:  # pragma: no cover - asserted in parent process
        output_queue.put(("error", type(exc).__name__, str(exc)))


def _leave_uncommitted_timer_update(
    database_path,
    owner_id,
    idempotency_key,
    next_attempt_at,
    ready_event,
):
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        """
        UPDATE effect_outbox SET next_attempt_at = ?
        WHERE namespace = 'a11oy' AND owner_id = ? AND idempotency_key = ?
        """,
        (next_attempt_at, owner_id, idempotency_key),
    )
    ready_event.set()
    threading.Event().wait(60)


def _publication_error(intent_sha256, *, stage_root="/data", final_root=None):
    destination_root = final_root if final_root is not None else stage_root
    return (
        "OSError: [Errno 95] Operation not supported: "
        f"'{stage_root}/.gdw-artifact-stage.tmp' -> "
        f"'{destination_root}/{intent_sha256}.json'"
    )


def _make_retry_scheduled(workspace, key, start, error=None):
    if error is None:
        error = _publication_error(_effect_row(workspace, key)["intent_sha256"])
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

    report = _recover(
        workspace,
        start + timedelta(seconds=1),
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
    _assert_audit_receipt(report)
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
        _recover(
            first_workspace,
            start + timedelta(seconds=1),
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

    report = _recover(workspace, recovery_time)

    assert report["status"] == "NO_ELIGIBLE_EFFECTS"
    assert report["rescheduled_effects"] == 0
    _assert_audit_receipt(report)
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

    report = _recover(workspace, start + timedelta(seconds=1))

    assert report["status"] == "DEFERRED_ACTIVE_CLAIM"
    assert report["claimed_effects"] == 1
    _assert_audit_receipt(report)
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
        _recover(workspace, start + timedelta(seconds=1))

    assert _effect_row(workspace, first_key) == before[0]
    assert _effect_row(workspace, second_key) == before[1]
    assert _audit_rows(workspace) == []


def test_recovery_rolls_back_timers_and_quota_when_audit_insert_aborts(tmp_path):
    workspace = _workspace(tmp_path / "audit-rollback.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "audit-rollback", start)
    _make_retry_scheduled(workspace, key, start)
    effect_before = _effect_row(workspace, key)
    usage_before = _usage_row(workspace)
    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            """
            CREATE TRIGGER abort_recovery_audit
            BEFORE INSERT ON effect_recovery_audit
            BEGIN
                SELECT RAISE(ABORT, 'injected audit failure');
            END
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="injected audit failure"):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id="audit-insert-rollback",
        )

    assert _effect_row(workspace, key) == effect_before
    assert _usage_row(workspace) == usage_before
    assert _audit_rows(workspace) == []


def test_recovery_serializes_with_normal_supervisor_claim(tmp_path):
    workspace = _workspace(tmp_path / "race.sqlite3")
    peer = _workspace(tmp_path / "race.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    due = start + timedelta(seconds=1)
    key = _queue_proof(workspace, "race", start)
    first = _make_retry_scheduled(workspace, key, start)
    barrier = threading.Barrier(2)
    claim_time = start + timedelta(seconds=10)

    def recover():
        barrier.wait()
        return _recover(workspace, due)

    def claim():
        barrier.wait()
        return peer.claim_effects("racing-worker", now=claim_time)

    with ThreadPoolExecutor(max_workers=2) as executor:
        recovery_future = executor.submit(recover)
        claim_future = executor.submit(claim)
        recovery_report = recovery_future.result()
        claims = claim_future.result()

    if not claims:
        claims = peer.claim_effects("followup-worker", now=claim_time)
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


def test_recovery_replay_returns_the_same_durable_receipt_and_collision_fails(
    tmp_path,
):
    workspace = _workspace(tmp_path / "replay.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "replay", start)
    _make_retry_scheduled(workspace, key, start)
    recovery_time = start + timedelta(seconds=1)

    first = _recover(
        workspace,
        recovery_time,
        recovery_id="operator-replay-1",
        limit=10,
    )
    first_receipt = _assert_audit_receipt(first)
    rows_after_first = _effect_rows(workspace)
    replay = _recover(
        workspace,
        recovery_time,
        recovery_id="operator-replay-1",
        limit=10,
    )

    assert replay["replayed"] is True
    assert replay["audit_receipt"] == first_receipt
    assert replay["audit_receipt"]["receipt_sha256"] == first_receipt[
        "receipt_sha256"
    ]
    assert replay["audit_receipt"]["outcome_sha256"] == first_receipt[
        "outcome_sha256"
    ]
    assert _effect_rows(workspace) == rows_after_first
    assert len(_audit_rows(workspace)) == 1

    with pytest.raises(
        GDWConfigurationError,
        match="recovery_id|idempotency|request",
    ):
        _recover(
            workspace,
            recovery_time,
            recovery_id="operator-replay-1",
            limit=11,
        )
    assert _effect_rows(workspace) == rows_after_first
    assert len(_audit_rows(workspace)) == 1


def test_malformed_recovery_audit_fails_integrity_and_replay_closed(tmp_path):
    workspace = _workspace(tmp_path / "malformed-audit.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "malformed-audit", start)
    _make_retry_scheduled(workspace, key, start)
    _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="malformed-audit",
    )
    connection = sqlite3.connect(workspace.path)
    try:
        report = json.loads(
            connection.execute(
                """
                SELECT report_json FROM effect_recovery_audit
                WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
                """,
                (
                    workspace.namespace,
                    workspace.owner_id,
                    "malformed-audit",
                ),
            ).fetchone()[0]
        )
        report["audit_receipt"] = 7
        connection.execute(
            """
            UPDATE effect_recovery_audit SET report_json = ?
            WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
            """,
            (
                json.dumps(report, sort_keys=True, separators=(",", ":")),
                workspace.namespace,
                workspace.owner_id,
                "malformed-audit",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    integrity = workspace.integrity(global_scope=True)
    assert integrity["ok"] is False
    assert integrity["invalid_recovery_audits"] == 1
    with pytest.raises(GDWConfigurationError, match="audit is invalid"):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id="malformed-audit",
        )


@pytest.mark.parametrize(
    "semantic_tamper",
    [
        "status",
        "attempt-accounting",
        "credential-values",
        "selection",
        "future-schedule",
    ],
)
def test_self_consistent_semantic_audit_tamper_fails_integrity_closed(
    tmp_path,
    semantic_tamper,
):
    workspace = _workspace(tmp_path / f"semantic-{semantic_tamper}.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, f"semantic-{semantic_tamper}", start)
    _make_retry_scheduled(workspace, key, start)
    recovery_id = f"semantic-{semantic_tamper}"
    _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id=recovery_id,
    )
    report = json.loads(_audit_rows(workspace)[0]["report_json"])
    if semantic_tamper == "status":
        report["status"] = "FORCED_SUCCESS"
    elif semantic_tamper == "attempt-accounting":
        report["attempts_after"] += 1
        report["audit_receipt"]["attempts_after"] += 1
    elif semantic_tamper == "credential-values":
        report["credential_values_recorded"] = True
        report["audit_receipt"]["credential_values_recorded"] = True
    elif semantic_tamper == "selection":
        report["selection_sha256"] = "f" * 64
        report["audit_receipt"]["selection_sha256"] = "f" * 64
    else:
        report["selection"][0]["next_attempt_at"] = report["audit_receipt"][
            "created_at"
        ]
        selection_sha256 = _canonical_hash(report["selection"])
        report["selection_sha256"] = selection_sha256
        report["audit_receipt"]["selection_sha256"] = selection_sha256
    _persist_resealed_audit(workspace, recovery_id, report)

    integrity = workspace.integrity(global_scope=True)
    assert integrity["ok"] is False
    assert integrity["invalid_recovery_audits"] == 1


@pytest.mark.parametrize("invalid_limit", [0, -1, 1001])
def test_recovery_rejects_out_of_contract_limits_without_audit(
    tmp_path,
    invalid_limit,
):
    workspace = _workspace(tmp_path / f"limit-{invalid_limit}.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, f"limit-{invalid_limit}", start)
    _make_retry_scheduled(workspace, key, start)
    before = _effect_rows(workspace)

    with pytest.raises(
        (ValueError, GDWConfigurationError),
        match="limit",
    ):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id=f"invalid-limit-{abs(invalid_limit)}",
            limit=invalid_limit,
        )

    assert _effect_rows(workspace) == before
    assert _audit_rows(workspace) == []


def test_recovery_rejects_stale_expected_generation_without_audit(tmp_path):
    workspace = _workspace(tmp_path / "generation.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "generation", start)
    _make_retry_scheduled(workspace, key, start)
    before = _effect_rows(workspace)

    with pytest.raises(
        GDWConfigurationError,
        match="generation",
    ):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id="wrong-generation",
            expected_database_generation_id="0" * 32,
        )

    assert _effect_rows(workspace) == before
    assert _audit_rows(workspace) == []


@pytest.mark.parametrize(
    ("column", "replacement"),
    [
        ("payload_json", "{}"),
        ("payload_sha256", "0" * 64),
        ("intent_sha256", "1" * 64),
        ("idempotency_key", "2" * 64),
        ("database_generation_id", "3" * 32),
    ],
)
def test_recovery_refuses_tampered_effect_bindings_without_mutation_or_audit(
    tmp_path,
    column,
    replacement,
):
    workspace = _workspace(tmp_path / f"tamper-{column}.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, f"tamper-{column}", start)
    _make_retry_scheduled(workspace, key, start)
    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            f"""
            UPDATE effect_outbox SET {column} = ?
            WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
            """,
            (replacement, workspace.namespace, workspace.owner_id, key),
        )
        connection.commit()
    finally:
        connection.close()
    before = _effect_rows(workspace)

    with pytest.raises(
        GDWConfigurationError,
        match="integrity|binding|generation|payload|intent|idempotency",
    ):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id=f"tamper-{column}",
        )

    assert _effect_rows(workspace) == before
    assert _audit_rows(workspace) == []


@pytest.mark.parametrize("failure_variant", ["cross-directory", "wrong-intent"])
def test_recovery_rejects_errno95_not_bound_to_the_effect_publication(
    tmp_path,
    failure_variant,
):
    workspace = _workspace(tmp_path / f"{failure_variant}.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, failure_variant, start)
    intent_sha256 = _effect_row(workspace, key)["intent_sha256"]
    if failure_variant == "cross-directory":
        error = _publication_error(
            intent_sha256,
            stage_root="/data/owner-a",
            final_root="/data/owner-b",
        )
    else:
        assert intent_sha256 != "f" * 64
        error = _publication_error("f" * 64)
    _make_retry_scheduled(
        workspace,
        key,
        start,
        error=error,
    )
    before = _effect_rows(workspace)

    with pytest.raises(GDWConfigurationError, match="unknown error"):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id=f"rejected-{failure_variant}",
        )

    assert _effect_rows(workspace) == before
    assert _audit_rows(workspace) == []


def test_recovery_covers_receipt_and_proof_effects_but_not_never_attempted(
    tmp_path,
):
    workspace = _workspace(tmp_path / "effect-kinds.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    proof_key = _queue_proof(workspace, "kind-proof", start)
    _make_retry_scheduled(workspace, proof_key, start)
    receipt_key = _queue_receipt(workspace, "kind-receipt", start)
    _make_retry_scheduled(workspace, receipt_key, start)
    never_attempted_key = _queue_proof(
        workspace,
        "kind-never-attempted",
        start,
    )
    never_attempted_before = _effect_row(workspace, never_attempted_key)

    report = _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="both-effect-kinds",
    )

    assert report["status"] == "RESCHEDULED"
    assert report["eligible_effects"] == 2
    assert report["rescheduled_effects"] == 2
    _assert_audit_receipt(report)
    assert _effect_row(workspace, never_attempted_key) == (
        never_attempted_before
    )
    claims = workspace.claim_effects(
        "kind-worker",
        now=start + timedelta(seconds=1),
    )
    assert {claim["kind"] for claim in claims} == {
        "proof_export",
        "receipt_projection",
    }


def test_recovery_fails_closed_when_an_exhausted_dead_letter_exists(tmp_path):
    workspace = _workspace(tmp_path / "dead-letter.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(
        workspace,
        "dead-letter",
        start,
        max_attempts=1,
    )
    claim = workspace.claim_effects("terminal-worker", now=start)[0]
    assert claim["idempotency_key"] == key
    assert workspace.release_effect(
        key,
        "terminal-worker",
        claim["claim_generation"],
        _publication_error(_effect_row(workspace, key)["intent_sha256"]),
        now=start,
    ) == "DEAD_LETTER"
    before = _effect_rows(workspace)

    with pytest.raises(GDWConfigurationError, match="integrity|dead"):
        _recover(
            workspace,
            start + timedelta(seconds=1),
            recovery_id="dead-letter-excluded",
        )

    assert _effect_rows(workspace) == before
    assert _audit_rows(workspace) == []


def test_recovery_is_idempotent_across_real_processes(tmp_path):
    database_path = tmp_path / "multiprocess.sqlite3"
    workspace = _workspace(database_path)
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "multiprocess", start)
    _make_retry_scheduled(workspace, key, start)
    before = _effect_row(workspace, key)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    output = context.Queue()
    processes = [
        context.Process(
            target=_recover_process,
            args=(
                str(database_path),
                workspace.owner_id,
                (start + timedelta(seconds=1)).isoformat(),
                "multiprocess-recovery",
                workspace.database_generation_id,
                barrier,
                output,
            ),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    # Drain before join: the DSSE audit envelope can exceed a Windows pipe's
    # small buffer, and Queue feeder threads must flush before child exit.
    results = [output.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0

    assert all(result[0] == "ok" for result in results), results
    reports = [result[1] for result in results]
    assert sorted(report["replayed"] for report in reports) == [False, True]
    assert len(
        {
            report["audit_receipt"]["receipt_sha256"]
            for report in reports
        }
    ) == 1
    assert len(_audit_rows(workspace)) == 1
    after = _effect_row(workspace, key)
    changed = {
        field
        for field in before
        if before[field] != after[field]
    }
    assert changed == {"next_attempt_at"}


def test_recovery_serializes_with_claim_from_a_separate_process(tmp_path):
    database_path = tmp_path / "multiprocess-claim.sqlite3"
    workspace = _workspace(database_path)
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "multiprocess-claim", start)
    first = _make_retry_scheduled(workspace, key, start)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    recovery_output = context.Queue()
    claim_output = context.Queue()
    recovery = context.Process(
        target=_recover_process,
        args=(
            str(database_path),
            workspace.owner_id,
            (start + timedelta(seconds=1)).isoformat(),
            "multiprocess-claim-recovery",
            workspace.database_generation_id,
            barrier,
            recovery_output,
        ),
    )
    claimant = context.Process(
        target=_claim_process,
        args=(
            str(database_path),
            workspace.owner_id,
            (start + timedelta(seconds=10)).isoformat(),
            barrier,
            claim_output,
        ),
    )

    recovery.start()
    claimant.start()
    recovery_result = recovery_output.get(timeout=30)
    claim_result = claim_output.get(timeout=30)
    recovery.join(timeout=30)
    claimant.join(timeout=30)

    assert recovery.exitcode == 0
    assert claimant.exitcode == 0
    assert recovery_result[0] == "ok", recovery_result
    assert claim_result[0] == "ok", claim_result
    assert recovery_result[1]["status"] in {
        "RESCHEDULED",
        "DEFERRED_ACTIVE_CLAIM",
    }
    assert len(claim_result[1]) == 1
    assert claim_result[1][0]["idempotency_key"] == key
    assert claim_result[1][0]["attempt"] == first["attempt"] + 1
    assert len(_audit_rows(workspace)) == 1
    row = _effect_row(workspace, key)
    assert row["status"] == "CLAIMED"
    assert row["attempts"] == 2
    assert row["claim_generation"] == 2


def test_process_death_rolls_back_uncommitted_recovery_timer(tmp_path):
    database_path = tmp_path / "crash-rollback.sqlite3"
    workspace = _workspace(database_path)
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "crash-rollback", start)
    _make_retry_scheduled(workspace, key, start)
    before = _effect_row(workspace, key)
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_leave_uncommitted_timer_update,
        args=(
            str(database_path),
            workspace.owner_id,
            key,
            (start + timedelta(seconds=1)).isoformat(),
            ready,
        ),
    )

    process.start()
    try:
        assert ready.wait(timeout=20)
    finally:
        process.terminate()
        process.join(timeout=20)

    assert process.exitcode is not None
    assert _effect_row(workspace, key) == before
    assert _audit_rows(workspace) == []


def test_recovery_then_supervisor_claim_and_export_converges(
    tmp_path,
    monkeypatch,
):
    workspace = _workspace(tmp_path / "converges.sqlite3")
    start = datetime.now(timezone.utc) - timedelta(
        seconds=workspace.retention_seconds + 60
    )
    key = _queue_proof(workspace, "converges", start)
    _make_retry_scheduled(workspace, key, start)
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "proofs"))
    monkeypatch.setenv(
        "GDW_RECEIPT_PROJECTION_DIR",
        str(tmp_path / "receipts"),
    )

    recovery = _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="recover-export-convergence",
    )
    drain = gdw_runtime.drain_once(
        worker_id="recovery-convergence-worker",
        workspace=workspace,
    )

    assert recovery["rescheduled_effects"] == 1
    assert drain["attempted"] == 1
    assert drain["exported"] == 1
    assert drain["failed"] == 0
    assert drain["pending_effects"] == 0
    assert drain["claimed_effects"] == 0
    assert drain["dead_letter_effects"] == 0
    assert drain["invalid_effect_bindings"] == 0
    assert drain["invalid_exported_artifacts"] == 0
    assert drain["garbage_collected"]["requests_tombstoned"] == 0
    assert drain["garbage_collected"]["effects_compacted"] == 0
    with workspace.transaction() as connection:
        assert workspace.cached_request(connection, "converges") is not None
    row = _effect_row(workspace, key)
    assert row["status"] == "EXPORTED"
    assert row["attempts"] == 2
    assert row["artifact_json"] is not None

    exported_report = _recover(
        workspace,
        datetime.now(timezone.utc),
        recovery_id="exported-effect-excluded",
    )
    assert exported_report["status"] == "NO_ELIGIBLE_EFFECTS"
    assert exported_report["rescheduled_effects"] == 0
    assert _effect_row(workspace, key)["status"] == "EXPORTED"

    workspace.retention_seconds = 1
    collected = workspace.collect_garbage(
        now=datetime.now(timezone.utc) + timedelta(seconds=2),
    )
    assert collected["requests_tombstoned"] == 0
    assert collected["effects_compacted"] == 1
    tombstoned = _effect_row(workspace, key)
    assert tombstoned["status"] == "EXPORTED"
    assert tombstoned["tombstoned_at"] is not None
    assert tombstoned["payload_json"] is None
    released = workspace.collect_garbage(
        now=datetime.now(timezone.utc) + timedelta(seconds=3),
    )
    assert released["requests_tombstoned"] == 1
    assert released["effects_compacted"] == 0
    persisted_audit = next(
        row
        for row in _audit_rows(workspace)
        if row["recovery_id"] == "recover-export-convergence"
    )
    persisted_report = json.loads(persisted_audit["report_json"])
    assert persisted_report["selection"] == recovery["selection"]
    assert persisted_report["selection_sha256"] == _canonical_hash(
        persisted_report["selection"]
    )
    assert all(
        "last_error" not in item and len(item["last_error_sha256"]) == 64
        for item in persisted_report["selection"]
    )
    tombstone_report = _recover(
        workspace,
        datetime.now(timezone.utc) + timedelta(seconds=3),
        recovery_id="tombstoned-effect-excluded",
    )
    assert tombstone_report["status"] == "NO_ELIGIBLE_EFFECTS"
    assert tombstone_report["rescheduled_effects"] == 0


def test_recovery_uses_signed_khipu_dsse_and_detects_signature_tamper(
    tmp_path,
    monkeypatch,
):
    workspace = _workspace(tmp_path / "signed-khipu.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "signed-khipu", start)
    _make_retry_scheduled(workspace, key, start)

    def sign_payload(payload, payload_type):
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).decode("ascii"),
            "signatures": [{"keyid": "test-khipu", "sig": "valid"}],
            "signed": True,
            "honesty": "REAL test-only signature fixture",
        }

    def verify_envelope(envelope):
        return {
            "verified": envelope.get("signatures")
            == [{"keyid": "test-khipu", "sig": "valid"}]
        }

    monkeypatch.setattr(
        workspace_module.szl_dsse,
        "sign_payload",
        sign_payload,
    )
    monkeypatch.setattr(
        workspace_module.szl_dsse,
        "verify_envelope",
        verify_envelope,
    )
    report = _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="signed-khipu-recovery",
    )
    receipt = report["audit_receipt"]
    assert receipt["receipt_status"] == "SIGNED_KHIPU_DSSE"
    assert workspace.integrity(global_scope=True)["invalid_recovery_audits"] == 0

    tampered = json.loads(_audit_rows(workspace)[0]["report_json"])
    tampered["audit_receipt"]["dsse_envelope"]["signatures"][0]["sig"] = "forged"
    tampered["audit_receipt"]["dsse_envelope_sha256"] = _canonical_hash(
        tampered["audit_receipt"]["dsse_envelope"]
    )
    tampered["audit_receipt"]["chain_sha256"] = _canonical_hash(
        {
            "previous_chain_sha256": tampered["audit_receipt"][
                "previous_chain_sha256"
            ],
            "receipt_sha256": tampered["audit_receipt"]["receipt_sha256"],
            "receipt_status": tampered["audit_receipt"]["receipt_status"],
            "dsse_envelope_sha256": tampered["audit_receipt"][
                "dsse_envelope_sha256"
            ],
        }
    )
    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            """
            UPDATE effect_recovery_audit
            SET dsse_envelope_sha256 = ?, chain_sha256 = ?, report_json = ?
            WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
            """,
            (
                tampered["audit_receipt"]["dsse_envelope_sha256"],
                tampered["audit_receipt"]["chain_sha256"],
                json.dumps(tampered, sort_keys=True, separators=(",", ":")),
                workspace.namespace,
                workspace.owner_id,
                "signed-khipu-recovery",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    assert workspace.integrity(global_scope=True)["invalid_recovery_audits"] == 1


def test_signed_recovery_receipt_cannot_be_downgraded_to_unsigned(
    tmp_path,
    monkeypatch,
):
    workspace = _workspace(tmp_path / "signed-downgrade.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "signed-downgrade", start)
    _make_retry_scheduled(workspace, key, start)

    def sign_payload(payload, payload_type):
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).decode("ascii"),
            "signatures": [{"keyid": "test-khipu", "sig": "valid"}],
            "signed": True,
            "honesty": "REAL test-only signature fixture",
        }

    monkeypatch.setattr(workspace_module.szl_dsse, "sign_payload", sign_payload)
    monkeypatch.setattr(
        workspace_module.szl_dsse,
        "verify_envelope",
        lambda envelope: {
            "verified": envelope.get("signatures")
            == [{"keyid": "test-khipu", "sig": "valid"}]
        },
    )
    _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="signed-downgrade-recovery",
    )
    assert workspace.integrity(global_scope=True)["invalid_recovery_audits"] == 0

    downgraded = json.loads(_audit_rows(workspace)[0]["report_json"])
    receipt = downgraded["audit_receipt"]
    receipt["dsse_envelope"]["signatures"] = []
    receipt["dsse_envelope"]["signed"] = False
    receipt["dsse_envelope"]["honesty"] = (
        "UNSIGNED - forged downgrade; no signature present"
    )
    receipt["receipt_status"] = "UNSIGNED_KHIPU_DSSE"
    receipt["dsse_envelope_sha256"] = _canonical_hash(
        receipt["dsse_envelope"]
    )
    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            """
            UPDATE effect_recovery_audit
            SET dsse_envelope_sha256 = ?, report_json = ?
            WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
            """,
            (
                receipt["dsse_envelope_sha256"],
                json.dumps(downgraded, sort_keys=True, separators=(",", ":")),
                workspace.namespace,
                workspace.owner_id,
                "signed-downgrade-recovery",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    assert workspace.integrity(global_scope=True)["invalid_recovery_audits"] == 1


def test_recovery_unsigned_khipu_envelope_is_honestly_labelled(
    tmp_path,
    monkeypatch,
):
    workspace = _workspace(tmp_path / "unsigned-khipu.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "unsigned-khipu", start)
    _make_retry_scheduled(workspace, key, start)

    def unsigned(payload, payload_type):
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).decode("ascii"),
            "signatures": [],
            "signed": False,
            "honesty": "UNSIGNED - no signer available; no signature fabricated",
        }

    monkeypatch.setattr(workspace_module.szl_dsse, "sign_payload", unsigned)
    report = _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="unsigned-khipu-recovery",
    )
    assert report["audit_receipt"]["receipt_status"] == "UNSIGNED_KHIPU_DSSE"
    assert report["audit_receipt"]["dsse_envelope"]["signatures"] == []


def test_recovery_khipu_chain_detects_predecessor_deletion(tmp_path):
    workspace = _workspace(tmp_path / "khipu-chain.sqlite3")
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    key = _queue_proof(workspace, "khipu-chain", start)
    _make_retry_scheduled(workspace, key, start)
    _recover(
        workspace,
        start + timedelta(seconds=1),
        recovery_id="khipu-chain-first",
    )
    _recover(
        workspace,
        start + timedelta(seconds=2),
        recovery_id="khipu-chain-second",
    )
    assert workspace.integrity(global_scope=True)["invalid_recovery_audits"] == 0

    connection = sqlite3.connect(workspace.path)
    try:
        connection.execute(
            """
            DELETE FROM effect_recovery_audit
            WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
            """,
            (workspace.namespace, workspace.owner_id, "khipu-chain-first"),
        )
        connection.commit()
    finally:
        connection.close()
    assert workspace.integrity(global_scope=True)["invalid_recovery_audits"] == 1
