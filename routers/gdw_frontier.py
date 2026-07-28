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
    def gdw_step():
        return _hold_response()

    return {
        "ok": True,
        "state": "UNAVAILABLE",
        "reason": _HOLD_REASON,
        "routes": [
            prefix + "/healthz",
            prefix + "/bench/meta",
            prefix + "/metrics",
            prefix + "/integrity",
            prefix + "/sessions/{session_id}",
            prefix + "/step",
        ],
    }
