#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

import base64
import json
import sqlite3

import pytest

import szl_dsse
from szl_gdw.models import WorkspaceState
from szl_gdw.persistence import (
    IntegrityViolation,
    PersistenceError,
    SchemaVersionError,
    SessionConflict,
    SessionLimitExceeded,
    SQLiteWorkspaceStore,
)


@pytest.fixture(autouse=True)
def unsigned_runtime(monkeypatch):
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: None)


def test_session_creation_is_dsse_bound_and_recovers(tmp_path):
    path = tmp_path / "gdw.sqlite3"
    store = SQLiteWorkspaceStore(path)
    state = WorkspaceState(session_id="recover-1", step=0, risk_budget=0.5)

    created = store.create_session(state)
    record = created["receipt"]
    decoded = json.loads(base64.b64decode(record["dsse"]["payload"]))

    assert decoded == record["receipt"]
    assert record["dsse"]["signed"] is False
    assert record["dsse"]["signatures"] == []
    assert "UNSIGNED" in record["dsse"]["honesty"]
    assert record["receipt"]["state_after"] == state.canonical_hash()

    recovered = SQLiteWorkspaceStore(path).recover_session("recover-1")
    assert recovered["state"] == state
    assert recovered["state_hash"] == state.canonical_hash()
    assert len(recovered["receipts"]) == 1
    assert recovered["chain_head"] == record["receipt_hash"]


def test_conflicting_creation_does_not_mint_again(tmp_path, monkeypatch):
    calls = 0
    original = szl_dsse.sign_khipu_receipt

    def counted(payload):
        nonlocal calls
        calls += 1
        return original(payload)

    monkeypatch.setattr(szl_dsse, "sign_khipu_receipt", counted)
    store = SQLiteWorkspaceStore(tmp_path / "conflict.sqlite3")
    state = WorkspaceState(session_id="same-session", step=0)

    store.create_session(state)
    with pytest.raises(SessionConflict):
        store.create_session(state)

    assert calls == 1
    assert store.snapshot()["counts"]["receipts"] == 1


def test_state_tampering_fails_recovery(tmp_path):
    path = tmp_path / "tamper.sqlite3"
    store = SQLiteWorkspaceStore(path)
    store.create_session(WorkspaceState(session_id="tamper-state", step=0))

    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE sessions SET state_json=? WHERE session_id=?",
            ('{"session_id":"tamper-state","step":99}', "tamper-state"),
        )

    with pytest.raises(IntegrityViolation):
        store.load_session("tamper-state")


def test_unknown_schema_version_fails_closed(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=99")

    with pytest.raises(SchemaVersionError):
        SQLiteWorkspaceStore(path)


def test_persistent_mode_requires_attached_mount(tmp_path):
    with pytest.raises(PersistenceError):
        SQLiteWorkspaceStore(
            tmp_path / "persistent.sqlite3",
            persistent_required=True,
            required_mount=tmp_path,
        )


def test_delete_journal_mode_is_supported_for_bucket_backed_deployments(
    tmp_path,
):
    path = tmp_path / "rollback.sqlite3"
    store = SQLiteWorkspaceStore(path, journal_mode="DELETE")

    with sqlite3.connect(path) as db:
        observed = str(db.execute("PRAGMA journal_mode").fetchone()[0]).upper()

    assert observed == "DELETE"
    assert store.snapshot()["journal_mode"] == "DELETE"


def test_durable_session_quota_is_atomic_and_survives_reopen(tmp_path):
    path = tmp_path / "quota.sqlite3"
    SQLiteWorkspaceStore(path, max_sessions=1).create_session(
        WorkspaceState(session_id="quota-1", step=0)
    )
    reopened = SQLiteWorkspaceStore(path, max_sessions=1)

    with pytest.raises(SessionLimitExceeded):
        reopened.create_session(
            WorkspaceState(session_id="quota-2", step=0)
        )

    assert reopened.snapshot()["counts"]["sessions"] == 1
