"""Authenticated Governed Delta Workspace API and benchmark surfaces."""

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import Header, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from gdw_attention import AttentionFeatures, choose_attention_mode
from gdw_proofs import build_proof_payload, export_proof_payload, sha256_json
from gdw_telemetry import GDWTelemetry
from gdw_workspace import GDWWorkspace
from szl_receipt_substrate import append_receipt
from szl_sgh_scheduler import build_plan


_TELEMETRY = GDWTelemetry()
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_EXPERTS = {"planner", "retriever", "auditor", "verifier", "operator"}
_HOLD_REASON = "GDW_CONSOLIDATION_REQUIRED"
_HOLD_DETAIL = {
    "schema": "szl.gdw.hold/v1",
    "status": "UNAVAILABLE",
    "label": "UNAVAILABLE",
    "reason": _HOLD_REASON,
    "write_ready": False,
    "external_effects": "DISABLED",
}


class GDWStepRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    request: str = Field(min_length=1, max_length=4096)
    allowed_experts: List[str] = Field(default_factory=list)
    risk_budget: float = Field(default=0.35, ge=0.0, le=1.0)
    mode_hint: Literal[
        "auto", "kda_local", "laguna_hybrid", "mla_global"
    ] = "auto"
    dry_run: bool = False
    novelty: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    disagreement: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    context_tokens: int = Field(default=0, ge=0, le=1000000)
    active_tool_count: int = Field(default=0, ge=0, le=64)
    memory_pressure: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    class Config:
        extra = "forbid"


def _dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _authorise(authorization: Optional[str]) -> None:
    token = os.environ.get("GDW_AUTH_TOKEN")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="GDW_AUTH_TOKEN is not configured; write surface is unavailable",
        )
    supplied = authorization or ""
    expected = "Bearer " + token
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid bearer token")


def _validate_identifiers(payload: GDWStepRequest, request_id: Optional[str]) -> str:
    if not request_id or not _ID_PATTERN.fullmatch(request_id):
        raise HTTPException(
            status_code=422,
            detail="X-Request-Id must be 1-128 canonical identifier characters",
        )
    if not _ID_PATTERN.fullmatch(payload.session_id):
        raise HTTPException(status_code=422, detail="invalid session_id")
    if len(payload.allowed_experts) > 16:
        raise HTTPException(status_code=422, detail="too many allowed_experts")
    return request_id


def _decision(payload: GDWStepRequest) -> str:
    experts = set(payload.allowed_experts)
    if not experts or not experts.issubset(_EXPERTS):
        return "QUARANTINE"
    if payload.risk_budget >= 0.90:
        return "REJECT"
    if payload.risk_budget >= 0.75:
        return "QUARANTINE"
    return "ACCEPT"


def _hold_response() -> JSONResponse:
    """Keep the conflicted surface fail-closed until one contract replaces it."""
    return JSONResponse(status_code=503, content=_HOLD_DETAIL)


def register(app, ns: str = "a11oy"):
    prefix = f"/api/{ns}/v1/gdw"

    @app.get(prefix + "/healthz")
    @app.get("/v1/gdw/healthz")
    def gdw_healthz():
        return {
            "service": "gdw-frontier",
            "status": "UNAVAILABLE",
            "label": "UNAVAILABLE",
            "reason": _HOLD_REASON,
            "write_ready": False,
            "external_effects": "DISABLED",
            "persistence": "DISABLED_PENDING_CONSOLIDATION",
            "benchmark_claim": "UNMEASURED",
        }

    @app.get(prefix + "/bench/meta")
    @app.get("/v1/gdw/bench/meta")
    def gdw_bench_meta(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        return _hold_response()
        _authorise(authorization)
        return {
            "service": "gdw-frontier",
            "implementation_status": "REAL",
            "benchmark_status": "UNMEASURED",
            "recommended_burst": 10000,
            "metrics_path": prefix + "/metrics",
            "notes": [
                "A 10k-request run is harness evidence, not a production guarantee.",
                "Use p95, p99, error rate, receipt integrity, and SQLite integrity.",
            ],
        }

    @app.get(prefix + "/metrics", response_class=PlainTextResponse)
    @app.get("/v1/gdw/metrics", response_class=PlainTextResponse)
    def gdw_metrics(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        return _hold_response()
        _authorise(authorization)
        return PlainTextResponse(
            _TELEMETRY.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get(prefix + "/integrity")
    @app.get("/v1/gdw/integrity")
    def gdw_integrity(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        return _hold_response()
        _authorise(authorization)
        return GDWWorkspace().integrity()

    @app.get(prefix + "/sessions/{session_id}")
    @app.get("/v1/gdw/sessions/{session_id}")
    def gdw_session(
        session_id: str,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        return _hold_response()
        _authorise(authorization)
        if not _ID_PATTERN.fullmatch(session_id):
            raise HTTPException(status_code=422, detail="invalid session_id")
        state = GDWWorkspace().read_session(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail="session not found")
        return state

    @app.post(prefix + "/step")
    @app.post("/v1/gdw/step")
    def gdw_step(
        payload: GDWStepRequest,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
        x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
    ):
        return _hold_response()
        started = time.perf_counter()
        _authorise(authorization)
        request_id = _validate_identifiers(payload, x_request_id)
        payload_data = _dump_model(payload)
        request_digest = _sha(payload_data)
        workspace = GDWWorkspace()
        selected_mode = "unresolved"
        decision = "ERROR"
        receipt_hash = ""

        try:
            with workspace.transaction() as connection:
                cached = workspace.cached_request(connection, request_id)
                if cached is not None:
                    cached_digest, cached_response = cached
                    if cached_digest != request_digest:
                        raise HTTPException(
                            status_code=409,
                            detail="X-Request-Id was already used with different content",
                        )
                    cached_response["replayed"] = True
                    selected_mode = cached_response["scheduler_mode"]
                    decision = cached_response["decision"]
                    receipt_hash = cached_response.get("receipt_hash") or ""
                    _TELEMETRY.observe(
                        (time.perf_counter() - started) * 1000.0,
                        decision,
                        selected_mode,
                        bool(receipt_hash),
                    )
                    return cached_response

                previous = workspace.session_state(connection, payload.session_id)
                if previous is None:
                    before_step = 0
                    before_hash = _sha(
                        {
                            "session_id": payload.session_id,
                            "step": 0,
                            "state": "GENESIS",
                        }
                    )
                else:
                    before_step = previous["step"]
                    before_hash = previous["state_hash"]

                features = AttentionFeatures(
                    novelty=payload.novelty
                    if payload.novelty is not None
                    else min(1.0, len(payload.request) / 1024.0),
                    disagreement=payload.disagreement
                    if payload.disagreement is not None
                    else min(1.0, max(0, len(set(payload.allowed_experts)) - 1) / 5.0),
                    risk=payload.risk_budget,
                    context_tokens=payload.context_tokens
                    or max(1, len(payload.request) // 4),
                    active_tool_count=payload.active_tool_count,
                    memory_pressure=payload.memory_pressure or 0.0,
                )
                routing = choose_attention_mode(features, payload.mode_hint)
                selected_mode = routing["mode"]
                decision = _decision(payload)
                mutates = decision == "ACCEPT" and not payload.dry_run
                step = before_step + 1 if mutates else before_step
                proposal_id = hashlib.sha256(
                    (request_id + ":" + request_digest).encode("utf-8")
                ).hexdigest()[:32]
                timestamp = _now()

                if mutates:
                    state = {
                        "session_id": payload.session_id,
                        "step": step,
                        "previous_state_hash": before_hash,
                        "request_digest": request_digest,
                        "scheduler_mode": selected_mode,
                        "allowed_experts": sorted(set(payload.allowed_experts)),
                    }
                    after_hash = _sha(state)
                    workspace.save_state(
                        connection,
                        payload.session_id,
                        step,
                        state,
                        after_hash,
                        timestamp,
                    )
                    receipt = append_receipt(
                        actor_id="gdw-frontier",
                        tool_name="gdw.step",
                        payload={
                            "proposal_id": proposal_id,
                            "request_id": request_id,
                            "session_id": payload.session_id,
                            "step": step,
                            "state_before_hash": before_hash,
                            "state_after_hash": after_hash,
                            "scheduler_mode": selected_mode,
                        },
                    )
                    receipt_hash = receipt.get("receipt_hash") or sha256_json(receipt)
                else:
                    state = previous["state"] if previous else {"state": "GENESIS"}
                    after_hash = before_hash
                    receipt = None

                proof_payload = build_proof_payload(
                    proposal_id=proposal_id,
                    request_id=request_id,
                    step=step,
                    before_hash=before_hash,
                    after_hash=after_hash,
                    decision=decision,
                    scheduler_mode=selected_mode,
                    receipt_hash=receipt_hash,
                    dry_run=payload.dry_run,
                )
                proof_mode = os.environ.get(
                    "GDW_PROOF_EXPORT_MODE", "sync"
                ).strip().lower()
                if proof_mode == "outbox":
                    workspace.save_proof_outbox(
                        connection,
                        proposal_id,
                        proof_payload,
                        proof_payload["payload_sha256"],
                        timestamp,
                    )
                    proof_artifact = {
                        "status": "OUTBOX_PERSISTED",
                        "payload_sha256": proof_payload["payload_sha256"],
                        "formal_status": "NOT_RUN",
                    }
                elif proof_mode == "sync":
                    proof_artifact = export_proof_payload(proof_payload)
                else:
                    raise ValueError(
                        "GDW_PROOF_EXPORT_MODE must be 'sync' or 'outbox'"
                    )
                plan = build_plan(
                    tasks=("governance", "attention_route", "state_transition", "verify"),
                    meta={"proposal_id": proposal_id},
                )
                response = {
                    "service": "gdw-frontier",
                    "implementation_status": "REAL",
                    "benchmark_status": "UNMEASURED",
                    "proposal_id": proposal_id,
                    "request_id": request_id,
                    "session_id": payload.session_id,
                    "decision": decision,
                    "step": step,
                    "state_hash": after_hash,
                    "state_before_hash": before_hash,
                    "receipt_hash": receipt_hash or None,
                    "scheduler_mode": selected_mode,
                    "routing": routing,
                    "kernel_execution": "NOT_EXECUTED_BY_CONTROL_API",
                    "dry_run": payload.dry_run,
                    "replayed": False,
                    "audit": {
                        "governance": "DENY_BY_DEFAULT",
                        "allowed_experts": sorted(set(payload.allowed_experts)),
                        "plan_version": plan["plan_version"],
                        "receipt_substrate": "szl_receipt_substrate"
                        if receipt is not None
                        else None,
                        "proof_export_mode": proof_mode,
                    },
                    "proof": proof_artifact,
                }
                response_hash = _sha(response)
                workspace.save_request(
                    connection,
                    request_id,
                    request_digest,
                    payload.session_id,
                    response,
                    response_hash,
                    timestamp,
                )
                if receipt is not None:
                    workspace.save_receipt(
                        connection,
                        receipt_hash,
                        request_id,
                        payload.session_id,
                        step,
                        receipt,
                        timestamp,
                    )

            _TELEMETRY.observe(
                (time.perf_counter() - started) * 1000.0,
                decision,
                selected_mode,
                bool(receipt_hash),
            )
            return response
        except HTTPException:
            raise
        except Exception as exc:
            _TELEMETRY.observe(
                (time.perf_counter() - started) * 1000.0,
                "ERROR",
                selected_mode,
                False,
                error=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"GDW transition failed closed: {type(exc).__name__}",
            ) from exc

    return {
        "ok": True,
        "state": "REAL",
        "routes": [
            prefix + "/healthz",
            prefix + "/bench/meta",
            prefix + "/metrics",
            prefix + "/integrity",
            prefix + "/sessions/{session_id}",
            prefix + "/step",
        ],
    }
