"""Deterministic MODELED Governed Delta Workspace orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol

import numpy as np

from .kernel_adapter import ImmutableKernel, kernel_dispose
from .math_core import delta_update, governed_depth_attention
from .models import (
    CapabilityLabel,
    Evidence,
    Proposal,
    WorkspaceState,
    canonical_hash,
    to_primitive,
)
from .telemetry import ModeledTelemetry


class ReceiptSink(Protocol):
    def append(
        self,
        proposal: Proposal,
        receipt,
        state_before: WorkspaceState,
        state_after: WorkspaceState,
    ) -> str: ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _modeled_observation(request: str, previous: np.ndarray) -> np.ndarray:
    digest = sha256(request.encode("utf-8")).digest()
    signal = np.asarray(
        [digest[index % len(digest)] / 255.0 - 0.5 for index in range(previous.size)],
        dtype=np.float64,
    )
    return previous + 0.1 * signal


class GovernedDeltaWorkspace:
    """Research workspace that sends every non-dry transition to a kernel."""

    def __init__(
        self,
        kernel: ImmutableKernel,
        *,
        receipt_sink: ReceiptSink | None = None,
        telemetry: ModeledTelemetry | None = None,
    ) -> None:
        self.kernel = kernel
        self.receipt_sink = receipt_sink
        self.telemetry = telemetry or ModeledTelemetry()

    def step(
        self,
        state: WorkspaceState,
        request: str,
        evidence: Sequence[Evidence],
        allowed_experts: Sequence[str],
        risk_budget: float,
        *,
        dry_run: bool = False,
        created_at: str | None = None,
        observed: Sequence[float] | None = None,
        predicted: Sequence[float] | None = None,
    ) -> tuple[WorkspaceState, Mapping[str, object]]:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("request must be a non-empty string")
        if not np.isfinite(risk_budget) or risk_budget < 0.0:
            raise ValueError("risk_budget must be finite and non-negative")
        expert_allowlist = tuple(
            expert.strip()
            for expert in allowed_experts
            if isinstance(expert, str) and expert.strip()
        )

        if state.delta_memory:
            width = len(state.delta_memory)
        elif state.depth_summaries:
            width = len(state.depth_summaries[0].vector)
        else:
            width = 4
        previous = np.asarray(state.delta_memory or (0.0,) * width, dtype=np.float64)
        predicted_vector = np.asarray(
            previous if predicted is None else predicted, dtype=np.float64
        )
        observed_vector = np.asarray(
            _modeled_observation(request, previous) if observed is None else observed,
            dtype=np.float64,
        )
        updated = delta_update(
            previous=previous,
            observed=observed_vector,
            predicted=predicted_vector,
            retention=0.95,
            learning_rate=0.5,
            novelty=1.0,
            risk=risk_budget,
        )
        retrieved, depth_weights = governed_depth_attention(
            updated, state.depth_summaries
        )

        timestamp = created_at or _utc_now()
        yuyay_entry = {
            "step": state.step,
            "request": request,
            "evidence_ids": [item.evidence_id for item in evidence],
            "capability_label": "MODELED",
        }
        payload = {
            "next_step": state.step + 1,
            "yuyay_entry": yuyay_entry,
            "delta_memory": updated.tolist(),
            "retrieved_depth": retrieved.tolist(),
            "depth_attention": depth_weights,
            "allowed_experts": list(expert_allowlist),
            "risk_budget": float(risk_budget),
        }
        identity = {
            "schema": "szl.gdw.proposal-identity/v1",
            "parent_state_hash": state.canonical_hash(),
            "operation": "gdw.step",
            "payload": payload,
            "evidence_ids": [item.evidence_id for item in evidence],
            "proposer": "szl_gdw.lambda_attnres",
            "created_at": timestamp,
            "capability_label": "MODELED",
        }
        proposal = Proposal(
            proposal_id=canonical_hash(identity),
            parent_state_hash=state.canonical_hash(),
            operation="gdw.step",
            payload=payload,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            proposer="szl_gdw.lambda_attnres",
            created_at=timestamp,
            capability_label=CapabilityLabel.MODELED,
        )

        if dry_run:
            next_state = state
            receipt = None
            self.telemetry.record(dry_run=True)
        else:
            next_state, receipt = kernel_dispose(self.kernel, state, proposal)
            self.telemetry.record(receipt)
            if self.receipt_sink is not None:
                self.receipt_sink.append(proposal, receipt, state, next_state)

        audit = {
            "capability_label": "MODELED",
            "proposal_id": proposal.proposal_id,
            "proposal": to_primitive(proposal),
            "depth_attention": depth_weights,
            "receipt": to_primitive(receipt) if receipt is not None else None,
            "state_unchanged": next_state.canonical_hash() == state.canonical_hash(),
            "dry_run": dry_run,
        }
        return next_state, audit
