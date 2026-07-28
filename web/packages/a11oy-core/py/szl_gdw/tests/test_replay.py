#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

from hashlib import sha256
import json
import sqlite3

import pytest

import szl_dsse
from szl_gdw.kernel_adapter import GovernedWorkspaceKernel
from szl_gdw.models import Decision, WorkspaceState
from szl_gdw.persistence import (
    IntegrityViolation,
    ReplayConflict,
    SQLiteWorkspaceStore,
)
from szl_gdw.workspace import GovernedDeltaWorkspace


@pytest.fixture(autouse=True)
def unsigned_runtime(monkeypatch):
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: None)


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256(body).hexdigest()


def _step(workspace, state, request="advance"):
    return workspace.step(
        state=state,
        request=request,
        evidence=[],
        allowed_experts=["modeled-expert"],
        risk_budget=0.5,
    )


def test_transition_commit_is_atomic_and_replay_exact(tmp_path):
    store = SQLiteWorkspaceStore(tmp_path / "replay.sqlite3")
    state = WorkspaceState(session_id="replay-1", step=0)
    store.create_session(state)
    next_state, audit = _step(
        GovernedDeltaWorkspace(GovernedWorkspaceKernel()), state
    )
    request_hash = _digest({"request": "advance"})
    response = {
        "decision": audit["receipt"].decision.value,
        "audit": {"proposal_id": audit["proposal_id"]},
        "replayed": False,
    }

    committed = store.commit_transition(
        session_id=state.session_id,
        idempotency_key="idem-1",
        request_hash=request_hash,
        expected_state_hash=state.canonical_hash(),
        next_state=next_state,
        receipt=audit["receipt"],
        response=response,
    )
    replay = store.lookup_operation(
        state.session_id, "idem-1", request_hash
    )

    assert committed.replayed is False
    assert replay is not None and replay.replayed is True
    assert replay.response == committed.response
    assert committed.response["khipu_receipt"]["signed"] is False
    assert store.load_session(state.session_id) == next_state
    assert store.snapshot()["counts"]["operations"] == 1
    assert store.snapshot()["counts"]["receipts"] == 2

    with pytest.raises(ReplayConflict):
        store.lookup_operation(
            state.session_id, "idem-1", _digest({"request": "different"})
        )


class _RejectKernel(GovernedWorkspaceKernel):
    def evaluate_policy(self, state, proposal):
        return {"operation_allowlisted": False}


def test_rejected_proposal_writes_receipt_but_not_workspace_state(tmp_path):
    store = SQLiteWorkspaceStore(tmp_path / "reject.sqlite3")
    state = WorkspaceState(session_id="reject-1", step=0)
    store.create_session(state)
    next_state, audit = _step(GovernedDeltaWorkspace(_RejectKernel()), state)

    assert audit["receipt"].decision is Decision.REJECT
    assert next_state is state

    committed = store.commit_transition(
        session_id=state.session_id,
        idempotency_key="reject-idem",
        request_hash=_digest({"request": "advance"}),
        expected_state_hash=state.canonical_hash(),
        next_state=next_state,
        receipt=audit["receipt"],
        response={"decision": "REJECT", "replayed": False},
    )
    recovered = store.recover_session(state.session_id)

    assert committed.state_hash == state.canonical_hash()
    assert recovered["state"] == state
    assert recovered["revision"] == 1
    assert len(recovered["receipts"]) == 2
    assert (
        recovered["receipts"][-1]["receipt"]["kernel_receipt"]["state_after"]
        is None
    )


def test_dsse_or_chain_tampering_fails_receipt_recovery(tmp_path):
    path = tmp_path / "receipt-tamper.sqlite3"
    store = SQLiteWorkspaceStore(path)
    state = WorkspaceState(session_id="tamper-receipt", step=0)
    created = store.create_session(state)
    receipt_id = created["receipt"]["receipt"]["receipt_id"]

    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT dsse_json FROM receipts WHERE receipt_id=?", (receipt_id,)
        ).fetchone()
        envelope = json.loads(row[0])
        envelope["payload"] = envelope["payload"][:-2] + "AA"
        db.execute(
            "UPDATE receipts SET dsse_json=? WHERE receipt_id=?",
            (json.dumps(envelope), receipt_id),
        )

    with pytest.raises(IntegrityViolation):
        store.get_receipt(receipt_id)
    with pytest.raises(IntegrityViolation):
        store.recover_session(state.session_id)
