"""Fail-closed immutable kernel boundary for MODELED workspace transitions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol

from .models import (
    CapabilityLabel,
    Decision,
    KernelReceipt,
    Proposal,
    WorkspaceState,
    canonical_hash,
    proposal_identity_hash,
)


class ImmutableKernel(Protocol):
    def evaluate_policy(
        self, state: WorkspaceState, proposal: Proposal
    ) -> Mapping[str, bool]: ...

    def evaluate_invariants(
        self, state: WorkspaceState, proposal: Proposal
    ) -> Mapping[str, bool]: ...

    def apply_authorized_transition(
        self, state: WorkspaceState, proposal: Proposal
    ) -> WorkspaceState: ...


def _receipt(
    proposal: Proposal,
    decision: Decision,
    policies: Mapping[str, bool],
    invariants: Mapping[str, bool],
    before: str,
    after: str | None,
    reason: str,
) -> KernelReceipt:
    body = {
        "schema": "szl.gdw.kernel-receipt/v1",
        "proposal_id": proposal.proposal_id,
        "decision": decision.value,
        "policy_results": dict(policies),
        "invariant_results": dict(invariants),
        "state_before": before,
        "state_after": after,
        "reason": reason,
        "created_at": proposal.created_at,
    }
    receipt_hash = canonical_hash(body)
    return KernelReceipt(
        receipt_id=f"receipt-{receipt_hash[:24]}",
        proposal_id=proposal.proposal_id,
        decision=decision,
        policy_results=policies,
        invariant_results=invariants,
        state_before=before,
        state_after=after,
        reason=reason,
        created_at=proposal.created_at,
        receipt_hash=receipt_hash,
    )


def kernel_dispose(
    kernel: ImmutableKernel,
    state: WorkspaceState,
    proposal: Proposal,
) -> tuple[WorkspaceState, KernelReceipt]:
    """Evaluate one proposal without mutating the caller's state."""
    before = state.canonical_hash()
    try:
        identity_matches = proposal_identity_hash(proposal) == proposal.proposal_id
    except (TypeError, ValueError):
        identity_matches = False
    if not identity_matches:
        return state, _receipt(
            proposal,
            Decision.REJECT,
            {"proposal_identity_match": False},
            {},
            before,
            None,
            "proposal identity does not bind canonical content",
        )
    if proposal.parent_state_hash != before:
        return state, _receipt(
            proposal,
            Decision.REJECT,
            {"proposal_identity_match": True, "parent_state_match": False},
            {},
            before,
            None,
            "stale or divergent parent state",
        )

    try:
        policies = {
            "proposal_identity_match": True,
            "parent_state_match": True,
            **dict(kernel.evaluate_policy(state, proposal)),
        }
        invariants = dict(kernel.evaluate_invariants(state, proposal))
    except Exception as exc:  # noqa: BLE001 - an untrusted kernel must fail closed
        return state, _receipt(
            proposal,
            Decision.REJECT,
            {
                "proposal_identity_match": True,
                "parent_state_match": True,
                "kernel_evaluation": False,
            },
            {},
            before,
            None,
            f"kernel evaluation failed closed: {type(exc).__name__}",
        )

    if state.canonical_hash() != before:
        return state, _receipt(
            proposal,
            Decision.REJECT,
            {**policies, "immutable_input": False},
            invariants,
            before,
            None,
            "kernel attempted to mutate the input state",
        )

    accepted = (
        bool(policies)
        and bool(invariants)
        and all(policies.values())
        and all(invariants.values())
    )
    if not accepted:
        return state, _receipt(
            proposal,
            Decision.REJECT,
            policies,
            invariants,
            before,
            None,
            "policy or invariant failure",
        )

    try:
        next_state = kernel.apply_authorized_transition(state, proposal)
        structurally_valid = (
            isinstance(next_state, WorkspaceState)
            and next_state.session_id == state.session_id
            and next_state.step == state.step + 1
            and state.canonical_hash() == before
        )
    except Exception as exc:  # noqa: BLE001 - transition code is a trust boundary
        return state, _receipt(
            proposal,
            Decision.REJECT,
            policies,
            {**invariants, "transition_application": False},
            before,
            None,
            f"transition application failed closed: {type(exc).__name__}",
        )

    if not structurally_valid:
        return state, _receipt(
            proposal,
            Decision.REJECT,
            policies,
            {**invariants, "structural_transition": False},
            before,
            None,
            "authorized transition violated structural invariants",
        )

    after = next_state.canonical_hash()
    return next_state, _receipt(
        proposal,
        Decision.ACCEPT,
        policies,
        {**invariants, "structural_transition": True},
        before,
        after,
        "all policies and invariants passed",
    )


class ReferenceImmutableKernel:
    """Small deterministic kernel for tests and standalone MODELED evaluation."""

    def evaluate_policy(
        self, state: WorkspaceState, proposal: Proposal
    ) -> Mapping[str, bool]:
        del state
        experts = proposal.payload.get("allowed_experts", ())
        return {
            "modeled_capability_only": (
                proposal.capability_label == CapabilityLabel.MODELED
            ),
            "known_operation": proposal.operation == "gdw.step",
            "expert_allowlist_nonempty": (
                isinstance(experts, tuple)
                and bool(experts)
                and all(
                    isinstance(expert, str) and expert.strip() for expert in experts
                )
            ),
        }

    def evaluate_invariants(
        self, state: WorkspaceState, proposal: Proposal
    ) -> Mapping[str, bool]:
        requested_risk = float(proposal.payload.get("risk_budget", -1.0))
        delta_memory = proposal.payload.get("delta_memory", ())
        return {
            "step_monotone": int(proposal.payload.get("next_step", -1))
            == state.step + 1,
            "risk_budget_bounded": 0.0 <= requested_risk <= state.risk_budget,
            "delta_memory_finite": (
                isinstance(delta_memory, tuple)
                and bool(delta_memory)
                and all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    for value in delta_memory
                )
            ),
        }

    def apply_authorized_transition(
        self, state: WorkspaceState, proposal: Proposal
    ) -> WorkspaceState:
        payload = proposal.payload
        yuyay_entry = payload["yuyay_entry"]
        broadcast_entry = {
            "step": state.step,
            "proposal_id": proposal.proposal_id,
            "retrieved_depth": payload["retrieved_depth"],
            "depth_attention": payload["depth_attention"],
        }
        return replace(
            state,
            step=state.step + 1,
            yuyay=state.yuyay + (yuyay_entry,),
            unay_refs=state.unay_refs + tuple(proposal.evidence_ids),
            broadcast=state.broadcast + (broadcast_entry,),
            delta_memory=tuple(float(value) for value in payload["delta_memory"]),
        )
