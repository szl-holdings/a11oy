#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Fail-closed immutable kernel boundary for GDW state disposal."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Protocol, Sequence, Tuple

from .models import (
    CapabilityLabel,
    Decision,
    DepthSummary,
    KernelReceipt,
    Proposal,
    WorkspaceState,
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


def _canonical_digest(value: Mapping[str, Any]) -> str:
    blob = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(blob).hexdigest()


class GovernedWorkspaceKernel:
    """Narrow production kernel: only the declared workspace.step transition."""

    def evaluate_policy(
        self, state: WorkspaceState, proposal: Proposal
    ) -> Mapping[str, bool]:
        payload = proposal.payload
        return {
            "operation_allowlisted": proposal.operation == "workspace.step",
            "modeled_label_preserved": (
                proposal.capability_label is CapabilityLabel.MODELED
            ),
            "risk_budget_bounded": (
                isinstance(payload.get("risk_budget"), (int, float))
                and math.isfinite(float(payload["risk_budget"]))
                and 0.0 <= float(payload["risk_budget"]) <= 1.0
            ),
            "proposer_allowlisted": proposal.proposer == "szl_gdw",
        }

    def evaluate_invariants(
        self, state: WorkspaceState, proposal: Proposal
    ) -> Mapping[str, bool]:
        payload = proposal.payload
        delta = payload.get("delta_memory")
        return {
            "session_unchanged": payload.get("session_id") == state.session_id,
            "step_advances_once": payload.get("step") == state.step + 1,
            "delta_finite": (
                isinstance(delta, Sequence)
                and not isinstance(delta, (str, bytes))
                and bool(delta)
                and all(
                    isinstance(value, (int, float))
                    and math.isfinite(float(value))
                    for value in delta
                )
            ),
            "parent_bound": proposal.parent_state_hash == state.canonical_hash(),
        }

    def apply_authorized_transition(
        self, state: WorkspaceState, proposal: Proposal
    ) -> WorkspaceState:
        payload = proposal.payload
        return WorkspaceState(
            session_id=str(payload["session_id"]),
            step=int(payload["step"]),
            yuyay=tuple(payload["yuyay"]),
            unay_refs=tuple(str(value) for value in payload["unay_refs"]),
            broadcast=tuple(payload["broadcast"]),
            delta_memory=tuple(float(value) for value in payload["delta_memory"]),
            depth_summaries=tuple(
                DepthSummary(
                    summary_id=str(item["summary_id"]),
                    depth=int(item["depth"]),
                    vector=tuple(float(value) for value in item["vector"]),
                    trust=float(item["trust"]),
                    risk=float(item["risk"]),
                    provenance=tuple(str(value) for value in item["provenance"]),
                )
                for item in payload["depth_summaries"]
            ),
            risk_budget=float(payload["risk_budget"]),
        )


def kernel_dispose(
    kernel: ImmutableKernel,
    state: WorkspaceState,
    proposal: Proposal,
) -> Tuple[WorkspaceState, KernelReceipt]:
    before = state.canonical_hash()
    policies: dict[str, bool]
    invariants: dict[str, bool]
    if proposal.parent_state_hash != before:
        policies = {"parent_state_match": False}
        invariants = {"transition_not_evaluated": False}
        next_state = state
        after = None
        decision = Decision.REJECT
        reason = "stale or divergent parent state"
    else:
        try:
            policies = dict(kernel.evaluate_policy(state, proposal))
            invariants = dict(kernel.evaluate_invariants(state, proposal))
            valid_results = (
                bool(policies)
                and bool(invariants)
                and all(isinstance(value, bool) for value in policies.values())
                and all(isinstance(value, bool) for value in invariants.values())
            )
            allowed = (
                valid_results
                and all(policies.values())
                and all(invariants.values())
            )
            if allowed:
                candidate = kernel.apply_authorized_transition(state, proposal)
                if not isinstance(candidate, WorkspaceState):
                    raise TypeError("kernel returned a non-workspace state")
                next_state = candidate
                after = next_state.canonical_hash()
                decision = Decision.ACCEPT
                reason = "all policies and invariants passed"
            else:
                next_state = state
                after = None
                decision = Decision.REJECT
                reason = "policy or invariant failure"
        except Exception:
            policies = {"kernel_evaluation": False}
            invariants = {"kernel_transition": False}
            next_state = state
            after = None
            decision = Decision.REJECT
            reason = "kernel evaluation failed closed"

    body = {
        "proposal_id": proposal.proposal_id,
        "decision": decision.value,
        "policy_results": policies,
        "invariant_results": invariants,
        "state_before": before,
        "state_after": after,
        "reason": reason,
    }
    receipt_hash = _canonical_digest(body)
    return next_state, KernelReceipt(
        receipt_id=f"gdwrcpt-{receipt_hash[:32]}",
        proposal_id=proposal.proposal_id,
        decision=decision,
        policy_results=policies,
        invariant_results=invariants,
        state_before=before,
        state_after=after,
        reason=reason,
        created_at=datetime.now(timezone.utc).isoformat(),
        receipt_hash=receipt_hash,
    )
