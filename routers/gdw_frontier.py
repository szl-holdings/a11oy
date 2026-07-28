"""Authenticated Governed Delta Workspace API and benchmark surfaces."""

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from gdw_attention import AttentionFeatures, choose_attention_mode
from gdw_drain import drain_effects
from gdw_proofs import build_proof_payload, sha256_json
from gdw_telemetry import GDWTelemetry
from gdw_workspace import GDWWorkspace
from szl_sgh_scheduler import build_plan


_TELEMETRY = GDWTelemetry()
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_EXPERTS = {"planner", "retriever", "auditor", "verifier", "operator"}
_PRINCIPAL_ROLES = {"user", "admin"}


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


def _principal_registry() -> dict:
    configured = os.environ.get("GDW_PRINCIPALS_JSON", "")
    try:
        registry = json.loads(configured)
    except Exception as exc:
        raise RuntimeError("GDW principal registry is invalid") from exc
    if not isinstance(registry, dict) or not registry:
        raise RuntimeError("GDW principal registry is unavailable")

    normalized = {}
    token_digests = set()
    for principal_id, record in registry.items():
        if not isinstance(principal_id, str) or not _ID_PATTERN.fullmatch(
            principal_id
        ):
            raise RuntimeError("GDW principal identifier is invalid")
        if not isinstance(record, dict):
            raise RuntimeError("GDW principal record is invalid")
        token_sha256 = str(record.get("token_sha256") or "")
        if (
            len(token_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in token_sha256)
            or token_sha256 == hashlib.sha256(b"").hexdigest()
            or token_sha256 in token_digests
        ):
            raise RuntimeError("GDW principal token binding is invalid")
        roles = record.get("roles")
        if (
            not isinstance(roles, list)
            or not roles
            or not set(roles).issubset(_PRINCIPAL_ROLES)
        ):
            raise RuntimeError("GDW principal roles are invalid")
        token_digests.add(token_sha256)
        normalized[principal_id] = {
            "principal_id": principal_id,
            "token_sha256": token_sha256,
            "roles": sorted(set(roles)),
        }
    return normalized


def _authenticate(
    authorization: Optional[str],
    required_role: Optional[str] = None,
) -> dict:
    try:
        registry = _principal_registry()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="GDW principal registry is unavailable",
        ) from exc
    supplied = authorization or ""
    if not supplied.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid bearer token")
    token = supplied[len("Bearer ") :]
    if not token:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    principal = None
    for record in registry.values():
        if hmac.compare_digest(digest, record["token_sha256"]):
            principal = record
    if principal is None:
        raise HTTPException(status_code=401, detail="invalid bearer token")
    if required_role and required_role not in principal["roles"]:
        raise HTTPException(status_code=403, detail="principal role is insufficient")
    return principal


def _bounded_config(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except Exception as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 1 or value > maximum:
        raise RuntimeError(f"{name} must be between 1 and {maximum}")
    return value


def _admission_limits() -> dict:
    owner_requests = _bounded_config("GDW_OWNER_MAX_REQUESTS", 1000, 10000)
    owner_sessions = _bounded_config("GDW_OWNER_MAX_SESSIONS", 100, 1000)
    global_requests = _bounded_config(
        "GDW_GLOBAL_MAX_REQUESTS", 100000, 1000000
    )
    global_sessions = _bounded_config(
        "GDW_GLOBAL_MAX_SESSIONS", 10000, 100000
    )
    if global_requests < owner_requests or global_sessions < owner_sessions:
        raise RuntimeError("GDW global quotas cannot be lower than owner quotas")
    return {
        "owner_requests": owner_requests,
        "owner_sessions": owner_sessions,
        "global_requests": global_requests,
        "global_sessions": global_sessions,
    }


def _retention_seconds() -> int:
    return _bounded_config("GDW_RETENTION_SECONDS", 604800, 31536000)


def _effect_limits() -> dict:
    owner_artifacts = _bounded_config(
        "GDW_OWNER_MAX_ARTIFACTS", 10000, 100000
    )
    global_artifacts = _bounded_config(
        "GDW_GLOBAL_MAX_ARTIFACTS", 100000, 1000000
    )
    if global_artifacts < owner_artifacts:
        raise RuntimeError(
            "GDW global artifact quota cannot be lower than owner quota"
        )
    return {
        "owner_artifacts": owner_artifacts,
        "global_artifacts": global_artifacts,
        "max_attempts": _bounded_config("GDW_MAX_EFFECT_ATTEMPTS", 20, 100),
    }


def _strict_policy():
    import szl_colang_policy

    policy = szl_colang_policy.get_policy(reload=True)
    status = policy.enforcement_contract_status()
    if not policy.loaded or not status["valid"]:
        raise RuntimeError("strict file-backed governance is unavailable")
    return policy


def _runtime_workspace() -> GDWWorkspace:
    _principal_registry()
    _admission_limits()
    _retention_seconds()
    _effect_limits()
    _strict_policy()
    workspace = GDWWorkspace()
    integrity = workspace.integrity()
    if not integrity["ok"]:
        raise RuntimeError("GDW workspace integrity gate is closed")
    return workspace


def _available_workspace() -> GDWWorkspace:
    try:
        return _runtime_workspace()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GDW semantic gate is closed: {type(exc).__name__}",
        ) from exc


def _step_openapi() -> dict:
    if hasattr(GDWStepRequest, "model_json_schema"):
        schema = GDWStepRequest.model_json_schema()
    else:
        schema = GDWStepRequest.schema()
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": schema}},
        }
    }


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


def _governance_gate(
    payload_data: dict,
    request_id: str,
    request_digest: str,
    principal_id: str,
) -> dict:
    action = {
        "tool": "execute",
        "effecting": True,
        "events": ["gate.evaluate"],
        "action_type": "gdw.step",
        "target": payload_data["session_id"],
        "request_id": request_id,
        "request_digest": request_digest,
        "principal_id": principal_id,
        "target_owner_id": principal_id,
        "text": payload_data["request"],
        "high_impact": float(payload_data["risk_budget"]) >= 0.75,
        "irreversible": False,
    }
    try:
        policy = _strict_policy()
        colang = policy.evaluate_strict(action)
        if not colang.get("enforcement_contract", {}).get("valid"):
            raise RuntimeError("strict policy enforcement contract is invalid")
    except Exception as exc:
        return {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["DOCTRINE_GATE_UNAVAILABLE"],
            "detail": type(exc).__name__,
            "writer_is_judge": True,
            "enforcement_mode": "IN_PROCESS_STRICT_FILE_LOCK",
        }

    try:
        import szl_codename_gate

        serialized = json.dumps(
            payload_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        codename_hits = sorted(
            {str(value) for value in szl_codename_gate.scan_text(serialized)}
        )
    except Exception as exc:
        return {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["CODENAME_GATE_UNAVAILABLE"],
            "detail": type(exc).__name__,
            "writer_is_judge": True,
            "enforcement_mode": "IN_PROCESS_STRICT_FILE_LOCK",
            "colang": {
                "decision": colang.get("decision"),
                "fired_flows": colang.get("fired_flows", []),
                "flows_evaluated": colang.get("flows_evaluated", []),
                "policy_files": colang.get("policy_files", []),
                "enforcement_contract": colang.get("enforcement_contract", {}),
            },
        }

    reasons = []
    if not colang.get("allow"):
        reasons.append("DOCTRINE_POLICY_DENY")
    if codename_hits:
        reasons.append("CODENAME_POLICY_DENY")
    return {
        "allowed": not reasons,
        "decision": "ALLOW" if not reasons else "DENY",
        "reason_codes": reasons or ["STRICT_FILE_BACKED_GOVERNANCE_PASS"],
        "writer_is_judge": True,
        "enforcement_mode": "IN_PROCESS_STRICT_FILE_LOCK",
        "colang": {
            "decision": colang.get("decision"),
            "fired_flows": colang.get("fired_flows", []),
            "flows_evaluated": colang.get("flows_evaluated", []),
            "policy_files": colang.get("policy_files", []),
            "enforcement_contract": colang.get("enforcement_contract", {}),
        },
        "codename_gate": {
            "clean": not codename_hits,
            "hits": codename_hits,
        },
    }


def _atomic_receipt(
    *,
    proposal_id: str,
    request_id: str,
    request_digest: str,
    owner_id: str,
    generation_id: str,
    session_id: str,
    step: int,
    before_hash: str,
    after_hash: str,
    scheduler_mode: str,
    governance: dict,
    timestamp: str,
) -> dict:
    receipt = {
        "schema": "szl.gdw.transaction-receipt/v1",
        "status": "UNSIGNED_ATOMIC",
        "proposal_id": proposal_id,
        "request_id": request_id,
        "request_digest": request_digest,
        "owner_id": owner_id,
        "generation_id": generation_id,
        "session_id": session_id,
        "step": step,
        "state_before_hash": before_hash,
        "state_after_hash": after_hash,
        "scheduler_mode": scheduler_mode,
        "governance_evidence_sha256": sha256_json(governance),
        "governance": governance,
        "created_at": timestamp,
    }
    receipt["receipt_hash"] = sha256_json(receipt)
    return receipt


def _effect_key(
    *,
    generation_id: str,
    owner_id: str,
    request_id: str,
    request_digest: str,
    kind: str,
    canonical_identity: str,
    payload_sha256: str,
) -> str:
    return hashlib.sha256(
        (
            f"{generation_id}:{owner_id}:{request_id}:{request_digest}:"
            f"{kind}:{canonical_identity}:{payload_sha256}"
        ).encode("utf-8")
    ).hexdigest()


def register(app, ns: str = "a11oy"):
    prefix = f"/api/{ns}/v1/gdw"

    @app.get(prefix + "/healthz")
    @app.get("/v1/gdw/healthz")
    def gdw_healthz():
        try:
            workspace = _runtime_workspace()
            return {
                "service": "gdw-frontier",
                "status": "REAL",
                "write_ready": True,
                "persistence": f"SQLITE_{workspace.journal_mode}",
                "generation_id": workspace.generation_id(),
                "external_effects": "OUTBOX_ONLY",
                "benchmark_claim": "UNMEASURED",
            }
        except Exception as exc:
            return {
                "service": "gdw-frontier",
                "status": "UNAVAILABLE",
                "label": "UNAVAILABLE",
                "write_ready": False,
                "persistence": "SQLITE_CONFIGURATION_GATED",
                "external_effects": "DISABLED",
                "reason": f"semantic gate closed: {type(exc).__name__}",
                "benchmark_claim": "UNMEASURED",
            }

    @app.post(prefix + "/drain")
    @app.post("/v1/gdw/drain")
    def gdw_drain(
        limit: int = 100,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        _authenticate(authorization, "admin")
        workspace = _available_workspace()
        try:
            result = drain_effects(workspace, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"GDW effect drain failed closed: {type(exc).__name__}",
            ) from exc
        if result["failed"] or not result["integrity_ok"]:
            raise HTTPException(status_code=503, detail=result)
        return result

    @app.get(prefix + "/bench/meta")
    @app.get("/v1/gdw/bench/meta")
    def gdw_bench_meta(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        _authenticate(authorization, "admin")
        _available_workspace()
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
        _authenticate(authorization, "admin")
        _available_workspace()
        return PlainTextResponse(
            _TELEMETRY.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get(prefix + "/integrity")
    @app.get("/v1/gdw/integrity")
    def gdw_integrity(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        _authenticate(authorization, "admin")
        workspace = _available_workspace()
        return workspace.integrity()

    @app.get(prefix + "/sessions/{session_id}")
    @app.get("/v1/gdw/sessions/{session_id}")
    def gdw_session(
        session_id: str,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        principal = _authenticate(authorization)
        workspace = _available_workspace()
        if not _ID_PATTERN.fullmatch(session_id):
            raise HTTPException(status_code=422, detail="invalid session_id")
        try:
            state = workspace.read_session(session_id, principal["principal_id"])
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if state is None:
            raise HTTPException(status_code=404, detail="session not found")
        return state

    @app.post(prefix + "/step", openapi_extra=_step_openapi())
    @app.post("/v1/gdw/step", openapi_extra=_step_openapi())
    async def gdw_step(
        request: Request,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
        x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
    ):
        started = time.perf_counter()
        principal = _authenticate(authorization)
        workspace = _available_workspace()
        principal_id = principal["principal_id"]
        try:
            raw_payload = await request.json()
            if hasattr(GDWStepRequest, "model_validate"):
                payload = GDWStepRequest.model_validate(raw_payload)
            else:
                payload = GDWStepRequest.parse_obj(raw_payload)
        except (ValueError, TypeError, ValidationError) as exc:
            detail = (
                exc.errors()
                if isinstance(exc, ValidationError)
                else "request body must be valid JSON"
            )
            raise HTTPException(status_code=422, detail=detail) from exc
        request_id = _validate_identifiers(payload, x_request_id)
        payload_data = _dump_model(payload)
        request_digest = _sha(payload_data)
        generation_id = workspace.generation_id()
        limits = _admission_limits()
        retention_seconds = _retention_seconds()
        selected_mode = "unresolved"
        decision = "ERROR"
        receipt_hash = ""

        try:
            with workspace.transaction() as connection:
                cached = workspace.cached_request(
                    connection, request_id, principal_id
                )
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
                        False,
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
                    workspace.require_object_owner(
                        connection,
                        "session",
                        payload.session_id,
                        principal_id,
                    )
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
                precondition_decision = _decision(payload)
                governance = _governance_gate(
                    payload_data,
                    request_id,
                    request_digest,
                    principal_id,
                )
                decision = precondition_decision
                if decision == "ACCEPT" and not governance["allowed"]:
                    decision = "REJECT"
                mutates = decision == "ACCEPT" and not payload.dry_run
                step = before_step + 1 if mutates else before_step
                timestamp = _now()
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=retention_seconds)
                ).isoformat()
                workspace.admit_request(
                    connection,
                    owner_id=principal_id,
                    request_id=request_id,
                    session_id=payload.session_id,
                    mutates=mutates,
                    created_at=timestamp,
                    expires_at=expires_at,
                    limits=limits,
                )
                proposal_id = sha256_json(
                    {
                        "schema": "szl.gdw.proposal-identity/v1",
                        "generation_id": generation_id,
                        "owner_id": principal_id,
                        "request_id": request_id,
                        "request_digest": request_digest,
                        "state_before_hash": before_hash,
                        "governance_evidence_sha256": sha256_json(governance),
                    }
                )

                if mutates:
                    state = {
                        "session_id": payload.session_id,
                        "owner_id": principal_id,
                        "generation_id": generation_id,
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
                    receipt = _atomic_receipt(
                        proposal_id=proposal_id,
                        request_id=request_id,
                        request_digest=request_digest,
                        owner_id=principal_id,
                        generation_id=generation_id,
                        session_id=payload.session_id,
                        step=step,
                        before_hash=before_hash,
                        after_hash=after_hash,
                        scheduler_mode=selected_mode,
                        governance=governance,
                        timestamp=timestamp,
                    )
                    receipt_hash = receipt["receipt_hash"]
                else:
                    state = previous["state"] if previous else {"state": "GENESIS"}
                    after_hash = before_hash
                    receipt = None

                proof_payload = build_proof_payload(
                    proposal_id=proposal_id,
                    request_id=request_id,
                    request_digest=request_digest,
                    owner_id=principal_id,
                    generation_id=generation_id,
                    step=step,
                    before_hash=before_hash,
                    after_hash=after_hash,
                    decision=decision,
                    scheduler_mode=selected_mode,
                    receipt_hash=receipt_hash,
                    dry_run=payload.dry_run,
                    governance=governance,
                )
                proof_mode = os.environ.get(
                    "GDW_PROOF_EXPORT_MODE", "outbox"
                ).strip().lower()
                if proof_mode != "outbox":
                    raise ValueError(
                        "GDW_PROOF_EXPORT_MODE must be 'outbox'; "
                        "synchronous external effects are not transaction-safe"
                    )
                proof_payload_digest = sha256_json(proof_payload)
                proof_effect_key = _effect_key(
                    generation_id=generation_id,
                    owner_id=principal_id,
                    request_id=request_id,
                    request_digest=request_digest,
                    kind="proof_export",
                    canonical_identity=proof_payload["payload_sha256"],
                    payload_sha256=proof_payload_digest,
                )
                proof_artifact = {
                    "status": "OUTBOX_PENDING",
                    "kind": "proof_export",
                    "idempotency_key": proof_effect_key,
                    "canonical_identity": proof_payload["payload_sha256"],
                    "payload_sha256": proof_payload["payload_sha256"],
                    "formal_status": "NOT_RUN",
                }
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
                    "owner_id": principal_id,
                    "generation_id": generation_id,
                    "session_id": payload.session_id,
                    "decision": decision,
                    "step": step,
                    "state_hash": after_hash,
                    "state_before_hash": before_hash,
                    "receipt_hash": receipt_hash or None,
                    "receipt_status": receipt.get("status") if receipt else None,
                    "scheduler_mode": selected_mode,
                    "routing": routing,
                    "kernel_execution": "NOT_EXECUTED_BY_CONTROL_API",
                    "dry_run": payload.dry_run,
                    "replayed": False,
                    "retention": {
                        "expires_at": expires_at,
                        "seconds": retention_seconds,
                    },
                    "audit": {
                        "governance": governance,
                        "precondition_decision": precondition_decision,
                        "allowed_experts": sorted(set(payload.allowed_experts)),
                        "plan_version": plan["plan_version"],
                        "receipt_substrate": "gdw.sqlite.atomic/v1"
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
                    receipt_payload_digest = sha256_json(receipt)
                    receipt_effect_key = _effect_key(
                        generation_id=generation_id,
                        owner_id=principal_id,
                        request_id=request_id,
                        request_digest=request_digest,
                        kind="receipt_projection",
                        canonical_identity=receipt_hash,
                        payload_sha256=receipt_payload_digest,
                    )
                    workspace.save_effect_outbox(
                        connection,
                        request_id,
                        "receipt_projection",
                        generation_id,
                        principal_id,
                        receipt_hash,
                        receipt,
                        receipt_payload_digest,
                        receipt_effect_key,
                        timestamp,
                    )
                workspace.save_effect_outbox(
                    connection,
                    request_id,
                    "proof_export",
                    generation_id,
                    principal_id,
                    proof_payload["payload_sha256"],
                    proof_payload,
                    proof_payload_digest,
                    proof_effect_key,
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
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except OverflowError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
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
        "state": "CONFIGURATION_GATED",
        "routes": [
            prefix + "/healthz",
            prefix + "/bench/meta",
            prefix + "/metrics",
            prefix + "/integrity",
            prefix + "/drain",
            prefix + "/sessions/{session_id}",
            prefix + "/step",
        ],
    }
