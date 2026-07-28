#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

from dataclasses import replace

import pytest

from szl_gdw.kernel_adapter import (
    GovernedWorkspaceKernel,
    kernel_dispose,
)
from szl_gdw.models import Decision, Proposal, WorkspaceState
from szl_gdw.workspace import GovernedDeltaWorkspace


def test_workspace_is_copy_on_write_and_dry_run_does_not_advance():
    state = WorkspaceState(session_id="copy-on-write", step=0)
    runtime = GovernedDeltaWorkspace(GovernedWorkspaceKernel())
    dry_state, dry_audit = runtime.step(
        state, "inspect", [], [], 0.5, dry_run=True
    )
    assert dry_state is state
    assert state.step == 0
    assert state.yuyay == ()
    assert dry_audit["receipt"] is None

    next_state, audit = runtime.step(state, "advance", [], [], 0.5)
    assert next_state is not state
    assert next_state.step == 1
    assert state.step == 0
    assert state.yuyay == ()
    assert audit["receipt"].decision is Decision.ACCEPT
    with pytest.raises(TypeError):
        next_state.yuyay[0]["step"] = 99


def test_stale_parent_rejects_without_mutation_or_advance():
    state = WorkspaceState(session_id="stale", step=3)
    proposal = Proposal(
        proposal_id="proposal-stale",
        parent_state_hash="0" * 64,
        operation="workspace.step",
        payload={},
        evidence_ids=(),
        proposer="szl_gdw",
        created_at="2026-01-01T00:00:00+00:00",
    )
    next_state, receipt = kernel_dispose(
        GovernedWorkspaceKernel(), state, proposal
    )
    assert next_state is state
    assert next_state.canonical_hash() == state.canonical_hash()
    assert receipt.decision is Decision.REJECT
    assert receipt.state_after is None


def test_kernel_failure_rejects_and_receipt_is_deterministically_identified():
    state = WorkspaceState(session_id="failure", step=0)

    class BrokenKernel:
        def evaluate_policy(self, state, proposal):
            raise RuntimeError("boom")

    proposal = Proposal(
        proposal_id="proposal-failure",
        parent_state_hash=state.canonical_hash(),
        operation="workspace.step",
        payload={},
        evidence_ids=(),
        proposer="szl_gdw",
        created_at="2026-01-01T00:00:00+00:00",
    )
    _, first = kernel_dispose(BrokenKernel(), state, proposal)
    _, second = kernel_dispose(BrokenKernel(), state, replace(proposal))
    assert first.decision is Decision.REJECT
    assert first.receipt_id == second.receipt_id
    assert first.receipt_hash == second.receipt_hash
