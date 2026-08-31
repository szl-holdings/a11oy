"""Standalone FastAPI surface for the MODELED Wave 26 research organ."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .kernel_adapter import ImmutableKernel, ReferenceImmutableKernel
from .models import (
    evidence_from_mapping,
    to_primitive,
    workspace_state_from_mapping,
)
from .persistence import JsonlReceiptStore
from .workspace import GovernedDeltaWorkspace

HONEST_LIMITATIONS = (
    "Governed Delta Workspace and Λ-AttnRes are **MODELED** orchestration and "
    "tensor-layer architectures inspired by Kimi K3, Kimi Linear, Attention "
    "Residuals, DeltaNet, and related work. They operate over explicit agent "
    "outputs, receipts, and stored representations. They do **not** reproduce "
    "Kimi K3’s weights, do **not** read proprietary model activations or J-space, "
    "and do **not** currently have loss or scaling-efficiency evidence beyond "
    "small-scale experiments. All numerical behavior and claims are subject "
    "to revision as empirical data accumulates."
)


class WorkspaceStepBody(BaseModel):
    state: dict
    request: str = Field(min_length=1)
    evidence: list[dict] = Field(default_factory=list)
    allowed_experts: list[str] = Field(default_factory=list)
    risk_budget: float = Field(default=1.0, ge=0.0)
    dry_run: bool = False
    created_at: str | None = None
    observed: list[float] | None = None
    predicted: list[float] | None = None


def create_app(
    kernel: ImmutableKernel | None = None,
    receipt_path: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="SZL Governed Delta Workspace research organ",
        version="0.1.0-modeled",
        description=HONEST_LIMITATIONS,
    )
    receipt_sink = JsonlReceiptStore(receipt_path) if receipt_path else None
    workspace = GovernedDeltaWorkspace(
        kernel or ReferenceImmutableKernel(), receipt_sink=receipt_sink
    )

    @app.get("/v1/szl-gdw/capability")
    def capability():
        return {
            "capability_label": "MODELED",
            "loss_evidence": "UNAVAILABLE",
            "scaling_evidence": "UNAVAILABLE",
            "limitations": HONEST_LIMITATIONS,
            "receipt_on_read": False,
        }

    @app.post("/v1/szl-gdw/step")
    def step(body: WorkspaceStepBody):
        try:
            state = workspace_state_from_mapping(body.state)
            evidence = [evidence_from_mapping(item) for item in body.evidence]
            next_state, audit = workspace.step(
                state,
                body.request,
                evidence,
                body.allowed_experts,
                body.risk_budget,
                dry_run=body.dry_run,
                created_at=body.created_at,
                observed=body.observed,
                predicted=body.predicted,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "capability_label": "MODELED",
            "limitations": HONEST_LIMITATIONS,
            "state": to_primitive(next_state),
            "audit": audit,
        }

    return app
