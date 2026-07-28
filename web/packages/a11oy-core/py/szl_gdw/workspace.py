#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Copy-on-write GDW orchestration with immutable-kernel disposal."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import List, Mapping, Tuple

from .kernel_adapter import ImmutableKernel, kernel_dispose
from .math_core import delta_update, governed_depth_attention
from .models import DepthSummary, Evidence, Proposal, WorkspaceState


class GovernedDeltaWorkspace:
    """MODELED orchestration organ; all writes cross the kernel boundary."""

    def __init__(self, kernel: ImmutableKernel):
        if kernel is None:
            raise ValueError("an immutable kernel is required")
        self.kernel = kernel

    def step(
        self,
        state: WorkspaceState,
        request: str,
        evidence: List[Evidence],
        allowed_experts: List[str],
        risk_budget: float,
        dry_run: bool = False,
    ) -> Tuple[WorkspaceState, Mapping[str, object]]:
        if not isinstance(state, WorkspaceState):
            raise TypeError("state must be a WorkspaceState")
        if not request or len(request) > 8_192:
            raise ValueError("request must be non-empty and bounded")
        if (
            not math.isfinite(risk_budget)
            or not 0.0 <= risk_budget <= 1.0
        ):
            raise ValueError("risk_budget must be in [0, 1]")
        if len(evidence) > 32 or len(allowed_experts) > 32:
            raise ValueError("workspace inputs exceed their item bounds")

        evidence_ids = tuple(item.evidence_id for item in evidence)
        request_record = {
            "step": state.step,
            "request_sha256": sha256(request.encode("utf-8")).hexdigest(),
            "evidence_ids": list(evidence_ids),
            "allowed_experts": list(allowed_experts),
        }
        prior_delta = tuple(float(value) for value in (state.delta_memory or (0.0,)))
        # A deterministic MODELED observation; not empirical model evidence.
        observed = tuple(value + 0.1 for value in prior_delta)
        updated = delta_update(
            previous=prior_delta,
            observed=observed,
            predicted=prior_delta,
            retention=0.95,
            learning_rate=0.5,
            novelty=1.0,
            risk=risk_budget,
        )
        retrieved, depth_weights = governed_depth_attention(
            query=updated,
            summaries=state.depth_summaries,
        )
        payload = {
            "session_id": state.session_id,
            "step": state.step + 1,
            "yuyay": [*state.yuyay, request_record],
            "unay_refs": list(state.unay_refs),
            "broadcast": list(state.broadcast),
            "delta_memory": list(updated),
            "depth_summaries": [
                {
                    "summary_id": summary.summary_id,
                    "depth": summary.depth,
                    "vector": list(summary.vector),
                    "trust": summary.trust,
                    "risk": summary.risk,
                    "provenance": list(summary.provenance),
                }
                for summary in state.depth_summaries
            ],
            "risk_budget": risk_budget,
            "retrieved_depth": list(retrieved),
        }
        proposal_basis = {
            "parent_state_hash": state.canonical_hash(),
            "operation": "workspace.step",
            "payload": payload,
            "evidence_ids": list(evidence_ids),
            "proposer": "szl_gdw",
        }
        proposal_digest = sha256(
            json.dumps(
                proposal_basis,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        proposal = Proposal(
            proposal_id=f"gdwprop-{proposal_digest[:32]}",
            parent_state_hash=state.canonical_hash(),
            operation="workspace.step",
            payload=payload,
            evidence_ids=evidence_ids,
            proposer="szl_gdw",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        if dry_run:
            return state, {
                "label": "MODELED",
                "dry_run": True,
                "depth_attention": depth_weights,
                "proposal_id": proposal.proposal_id,
                "receipt": None,
            }
        next_state, receipt = kernel_dispose(self.kernel, state, proposal)
        return next_state, {
            "label": "MODELED",
            "dry_run": False,
            "depth_attention": depth_weights,
            "proposal_id": proposal.proposal_id,
            "receipt": receipt,
        }
