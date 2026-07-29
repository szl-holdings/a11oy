from dataclasses import replace

from szl_gdw.kernel_adapter import ReferenceImmutableKernel, kernel_dispose
from szl_gdw.models import (
    CapabilityLabel,
    Decision,
    Proposal,
    WorkspaceState,
    proposal_identity_hash,
)


def _proposal(state, **overrides):
    values = {
        "proposal_id": "proposal-1",
        "parent_state_hash": state.canonical_hash(),
        "operation": "gdw.step",
        "payload": {
            "next_step": state.step + 1,
            "yuyay_entry": {"request": "test"},
            "delta_memory": [0.1],
            "retrieved_depth": [0.0],
            "depth_attention": {},
            "allowed_experts": ["expert-a"],
            "risk_budget": 0.5,
        },
        "evidence_ids": (),
        "proposer": "test",
        "created_at": "2026-07-29T00:00:00+00:00",
        "capability_label": CapabilityLabel.MODELED,
    }
    values.update(overrides)
    proposal = Proposal(**values)
    if "proposal_id" not in overrides:
        proposal = replace(proposal, proposal_id=proposal_identity_hash(proposal))
    return proposal


def test_stale_parent_rejects_without_state_change():
    state = WorkspaceState("session")
    proposal = _proposal(state, parent_state_hash="0" * 64)
    next_state, receipt = kernel_dispose(ReferenceImmutableKernel(), state, proposal)
    assert receipt.decision == Decision.REJECT
    assert next_state is state
    assert next_state.canonical_hash() == state.canonical_hash()
    assert receipt.state_after is None


def test_empty_expert_allowlist_fails_closed():
    state = WorkspaceState("session")
    proposal = _proposal(
        state,
        payload={
            **dict(_proposal(state).payload),
            "allowed_experts": [],
        },
    )
    next_state, receipt = kernel_dispose(ReferenceImmutableKernel(), state, proposal)
    assert receipt.decision == Decision.REJECT
    assert next_state is state


def test_non_modeled_capability_cannot_cross_reference_kernel():
    state = WorkspaceState("session")
    proposal = _proposal(state, capability_label=CapabilityLabel.EXPERIMENTAL)
    next_state, receipt = kernel_dispose(ReferenceImmutableKernel(), state, proposal)
    assert receipt.decision == Decision.REJECT
    assert next_state is state


def test_proposal_identity_must_bind_content():
    state = WorkspaceState("session")
    proposal = _proposal(state, proposal_id="caller-chosen-id")
    next_state, receipt = kernel_dispose(ReferenceImmutableKernel(), state, proposal)
    assert receipt.decision == Decision.REJECT
    assert receipt.policy_results["proposal_identity_match"] is False
    assert next_state is state
