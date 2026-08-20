# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# sidecar/main.py — SENTRA verdict HTTP service (Wire B of the anatomy mesh).
#
# PhD-CS review (2026-05-30) confirmed Wire B is broken in production:
# a11oy/packages/mesh-router calls POST /v1/verdict against a sentra server
# that does not exist, causing every requestSentraVerdict() call to fail
# closed (deny). This service is the missing server.
#
# Wraps the pure function sentra_immune.sentra_inspect() from
# ../src/sentra_immune.py with a minimal FastAPI surface. No verdict logic
# lives here — the immune logic stays in sentra_immune.py.
#
# Routes:
#   GET  /healthz        — liveness probe; returns {"status": "ok"}
#   POST /v1/verdict     — full immune evaluation; may short-circuit on deny
#   POST /v1/inspect     — same evaluation but always returns all signals fired
#                          (no short-circuit); used by mesh-router /v1/inspect
#
# Request body (POST /v1/verdict and POST /v1/inspect):
#   {
#     "request_id":  str          (optional; a11oy trace correlation)
#     "agent":       str          (optional; calling agent identifier)
#     "action":      str | object (the action under inspection; required)
#     "context":     object       (optional; ambient context forwarded verbatim)
#     "axes":        list[float]  (optional; Λ-gate axis scores 0.0–1.0)
#     # mesh-router SentraVerdictRequest aliases:
#     "actionId":    str          (alias for request_id when present)
#     "kind":        str          (optional; "egress" | "threat" | "admission")
#     "payload":     any          (alias for action when action not present)
#   }
#
# Response body:
#   {
#     "decision":     "allow" | "deny"
#     "reason":       str
#     "signals":      list[str]   (human-readable signals fired)
#     "lambda_value": float       (0.0 = deny, 1.0 = allow; MIN of axes if given)
#   }
#
# The response satisfies the mesh-router SentraVerdict interface:
#   { decision: "allow" | "deny"; reason?: string }
# and extends it with signals + lambda_value for richer telemetry.
#
# Author: Stephen P. Lutar Jr. <stephen@szlholdings.com>
# Co-authored-by: Perplexity Computer Agent <agent@szlholdings.com>

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Import the real immune function from the sibling src/ module.
# ---------------------------------------------------------------------------
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sentra_immune import sentra_inspect  # noqa: E402

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="sentra verdict service",
    version="0.1.0",
    description=(
        "HTTP wrapper for the sentra immune organ. "
        "Exposes POST /v1/verdict and POST /v1/inspect so the a11oy "
        "mesh-router can delegate policy evaluation to the immune system."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

THREAT_KEYWORDS_EXPOSED = [
    "DROP TABLE",
    "rm -rf",
    "<script",
    "eval(",
    "subprocess",
    "../../etc",
]


class VerdictRequest(BaseModel):
    """Body accepted by POST /v1/verdict and POST /v1/inspect.

    Accepts both the task-specified schema and the mesh-router
    SentraVerdictRequest aliases so either caller shape works.
    """

    # Primary fields (task contract)
    request_id: str | None = Field(
        default=None,
        description="Trace-correlation identifier from the calling agent.",
    )
    agent: str | None = Field(
        default=None,
        description="Identifier of the agent submitting the action.",
    )
    action: Any = Field(
        default=None,
        description="The action or payload under immune inspection.",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Ambient context forwarded verbatim for audit purposes.",
    )
    axes: list[float] | None = Field(
        default=None,
        description="Λ-gate axis scores (0.0–1.0). MIN is used as lambda_value.",
    )

    # mesh-router SentraVerdictRequest aliases
    actionId: str | None = Field(
        default=None,
        description="Alias for request_id (mesh-router SentraVerdictRequest).",
    )
    kind: str | None = Field(
        default=None,
        description='Action kind hint: "egress" | "threat" | "admission".',
    )
    payload: Any = Field(
        default=None,
        description="Alias for action (mesh-router SentraVerdictRequest).",
    )

    def resolved_action(self) -> Any:
        """Return the action to inspect, preferring action over payload."""
        if self.action is not None:
            return self.action
        if self.payload is not None:
            return self.payload
        return {}

    def resolved_request_id(self) -> str:
        """Return the effective request_id, preferring request_id over actionId."""
        return self.request_id or self.actionId or "unspecified"


class VerdictResponse(BaseModel):
    """Response returned by /v1/verdict and /v1/inspect."""

    decision: str = Field(description='"allow" or "deny".')
    reason: str = Field(description="Human-readable rationale for the decision.")
    signals: list[str] = Field(description="Threat signals that fired during inspection.")
    lambda_value: float = Field(
        description=(
            "Governance gate score (0.0 = deny, 1.0 = allow). "
            "Equals MIN(axes) when axes are provided; otherwise 1.0 (allow) or 0.0 (deny)."
        ),
    )


# ---------------------------------------------------------------------------
# Internal evaluation helper
# ---------------------------------------------------------------------------


def _run_inspection(body: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate the action against every threat signature and return
    (is_clean, signals_fired). Always checks all signatures — no
    short-circuit so callers that need the full signal list can get it.
    """
    blob = str(body).lower()
    signals_fired: list[str] = []

    for sig in THREAT_KEYWORDS_EXPOSED:
        if sig.lower() in blob:
            signals_fired.append(f"threat-signature:{sig}")

    if len(blob) > 1_000_000:
        signals_fired.append("size-guard:payload-exceeds-1MB")

    return len(signals_fired) == 0, signals_fired


def _compute_lambda(axes: list[float] | None, is_clean: bool) -> float:
    """Compute the Λ-gate value.

    When axes are provided, uses MIN(axes) as the strictest gate.
    When no axes are provided, returns 1.0 for allow and 0.0 for deny,
    consistent with the binary sentra_inspect() output.
    """
    if axes:
        return min(axes)
    return 1.0 if is_clean else 0.0


def _build_verdict(req: VerdictRequest, *, full_signals: bool) -> VerdictResponse:
    """Build a VerdictResponse from the request.

    full_signals=True (used by /v1/inspect): returns all signals fired,
      never short-circuits on the first denial.
    full_signals=False (used by /v1/verdict): may short-circuit on deny.
    """
    action = req.resolved_action()
    packet = action if isinstance(action, dict) else {"value": action}

    # Run full inspection to collect every signal.
    is_clean, signals_fired = _run_inspection(packet)

    # Λ-gate value.
    lambda_val = _compute_lambda(req.axes, is_clean)

    # For /v1/verdict we may also consult the canonical sentra_inspect() which
    # has the authoritative threshold logic (size guard + signature scan).
    # For /v1/inspect we already have all signals; sentra_inspect() result is
    # used only for the decision line, not to suppress any signals.
    canonical_clean = sentra_inspect(packet)

    if full_signals:
        # /v1/inspect: decision reflects canonical immune result; signals are
        # the full set regardless of decision.
        decision = "allow" if canonical_clean else "deny"
        reason = (
            "no threat signature detected by the immune organ"
            if canonical_clean
            else "immune organ rejected: threat signature or size guard tripped"
        )
        return VerdictResponse(
            decision=decision,
            reason=reason,
            signals=signals_fired,
            lambda_value=lambda_val,
        )
    else:
        # /v1/verdict: canonical result drives the decision.
        decision = "allow" if canonical_clean else "deny"
        reason = (
            "no threat signature detected by the immune organ"
            if canonical_clean
            else "immune organ rejected: threat signature or size guard tripped"
        )
        return VerdictResponse(
            decision=decision,
            reason=reason,
            signals=signals_fired,
            lambda_value=lambda_val,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    """Liveness probe. Returns 200 {"status": "ok"} when the service is up."""
    return {"status": "ok"}


@app.post("/v1/verdict", response_model=VerdictResponse, tags=["immune"])
def verdict(body: VerdictRequest) -> VerdictResponse:
    """Evaluate an action through the immune organ and return a policy verdict.

    Called by the a11oy mesh-router before admitting an agent action into the
    substrate. Maps to the mesh-router SentraVerdictRequest/SentraVerdict
    contract defined in a11oy/packages/mesh-router/src/index.ts.

    Returns {"decision": "allow"|"deny", "reason", "signals", "lambda_value"}.
    The response is a superset of the SentraVerdict interface; mesh-router
    reads only decision and reason.
    """
    return _build_verdict(body, full_signals=False)


@app.post("/v1/inspect", response_model=VerdictResponse, tags=["immune"])
def inspect(body: VerdictRequest) -> VerdictResponse:
    """Inspect an action and return every signal fired — no short-circuit.

    Unlike /v1/verdict, this route always collects and returns all threat
    signals before computing the decision. Used for forensic analysis and
    the immune-system audit log, not for real-time admit/deny gating.
    """
    return _build_verdict(body, full_signals=True)


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.environ.get("SENTRA_SIDECAR_HOST", "0.0.0.0"),
        port=int(os.environ.get("SENTRA_SIDECAR_PORT", "8091")),
        log_level=os.environ.get("SENTRA_SIDECAR_LOG_LEVEL", "info"),
    )
