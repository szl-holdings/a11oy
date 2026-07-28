#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""FastAPI registration for the MODELED Governed Delta Workspace."""

from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Annotated, Any, Callable, List, Mapping, Optional
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .kernel_adapter import GovernedWorkspaceKernel
from .models import Evidence, WorkspaceState
from .persistence import (
    IntegrityViolation,
    PersistenceError,
    ReplayConflict,
    SessionConflict,
    SessionLimitExceeded,
    SessionNotFound,
    SQLiteWorkspaceStore,
    receipt_to_dict,
    state_to_dict,
)
from .telemetry import OperationalTelemetry
from .workspace import GovernedDeltaWorkspace


MAX_REQUEST_CHARS = 8_192
MAX_BODY_BYTES = 1_048_576
MAX_EVIDENCE = 32
MAX_EXPERTS = 32
MAX_AGGREGATE_ELEMENTS = 8_192
MAX_BATCH = 4
MAX_TOKENS = 64
MAX_SOURCES = 16
MAX_DIMENSION = 512
DEFAULT_MAX_SESSIONS = 128
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NS_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
PRIMARY_CITATIONS = [
    {
        "identifier": "arXiv:2603.15031",
        "url": "https://arxiv.org/abs/2603.15031",
        "role": "Attention Residuals design inspiration",
    },
    {
        "identifier": "arXiv:2510.26692",
        "url": "https://arxiv.org/abs/2510.26692",
        "role": "delta attention design inspiration",
    },
    {
        "identifier": "arXiv:2412.06464",
        "url": "https://arxiv.org/abs/2412.06464",
        "role": "gated delta-rule design inspiration",
    },
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SessionCreateRequest(_StrictModel):
    session_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    risk_budget: float = Field(default=1.0, ge=0.0, le=1.0)


class EvidenceRequest(_StrictModel):
    evidence_id: str = Field(min_length=1, max_length=128)
    uri: str = Field(min_length=1, max_length=2_048)
    content_hash: str = Field(min_length=64, max_length=64)
    trust: float = Field(ge=0.0, le=1.0)
    observed_at: str = Field(min_length=1, max_length=64)


class StepRequest(_StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    request: str = Field(min_length=1, max_length=MAX_REQUEST_CHARS)
    evidence: List[EvidenceRequest] = Field(
        default_factory=list, max_length=MAX_EVIDENCE
    )
    allowed_experts: List[str] = Field(
        default_factory=list, max_length=MAX_EXPERTS
    )
    risk_budget: float = Field(default=1.0, ge=0.0, le=1.0)


AggregateVector = Annotated[
    List[float], Field(min_length=1, max_length=MAX_DIMENSION)
]
AggregateSources = Annotated[
    List[AggregateVector], Field(min_length=1, max_length=MAX_SOURCES)
]
AggregateTokens = Annotated[
    List[AggregateSources], Field(min_length=1, max_length=MAX_TOKENS)
]
AggregateBatch = Annotated[
    List[AggregateTokens], Field(min_length=1, max_length=MAX_BATCH)
]


class AggregateRequest(_StrictModel):
    sources: AggregateBatch
    lam: float = Field(default=0.25, ge=0.0, le=1.0)
    egyptian: bool = True
    depth: int = Field(default=4, ge=1, le=16)
    eps: float = Field(default=math.exp(-5.0), gt=0.0, le=1.0)


def _canonical_digest(value: Any) -> str:
    try:
        body = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise IntegrityViolation("request is not finite canonical JSON") from exc
    return sha256(body.encode("utf-8")).hexdigest()


def _api_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _api_jsonable(value.to_dict())
    if is_dataclass(value):
        return _api_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _api_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_api_jsonable(item) for item in value]
    return value


def _valid_identifier(value: str, name: str) -> str:
    if not _ID_PATTERN.fullmatch(value):
        raise IntegrityViolation(f"{name} has an invalid format")
    return value


def _request_payload(body: BaseModel) -> Mapping[str, Any]:
    return body.model_dump(mode="json")


def _positive_bounded_int(raw: str, *, default: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if 1 <= value <= maximum else default


async def _parse_body(request: Request, model: Any) -> BaseModel:
    try:
        declared = request.headers.get("content-length")
        if declared is not None:
            declared_bytes = int(declared)
            if declared_bytes < 0 or declared_bytes > MAX_BODY_BYTES:
                raise ValueError("request body exceeds its byte limit")
        chunks: list[bytes] = []
        observed_bytes = 0
        async for chunk in request.stream():
            observed_bytes += len(chunk)
            if observed_bytes > MAX_BODY_BYTES:
                raise ValueError("request body exceeds its byte limit")
            chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
        return model.model_validate(payload)
    except Exception as exc:
        raise IntegrityViolation("request body is invalid") from exc


def _validate_step(body: StepRequest) -> None:
    _valid_identifier(body.idempotency_key, "idempotency_key")
    if len(body.evidence) > MAX_EVIDENCE:
        raise IntegrityViolation("evidence exceeds the item limit")
    if len(body.allowed_experts) > MAX_EXPERTS:
        raise IntegrityViolation("allowed_experts exceeds the item limit")
    evidence_ids: set[str] = set()
    for item in body.evidence:
        _valid_identifier(item.evidence_id, "evidence_id")
        if not re.fullmatch(r"[0-9a-f]{64}", item.content_hash):
            raise IntegrityViolation("evidence content_hash must be lowercase SHA-256")
        if item.evidence_id in evidence_ids:
            raise IntegrityViolation("evidence identifiers must be unique")
        evidence_ids.add(item.evidence_id)
    for expert in body.allowed_experts:
        _valid_identifier(expert, "allowed_expert")
    if len(set(body.allowed_experts)) != len(body.allowed_experts):
        raise IntegrityViolation("allowed_experts must be unique")


def _aggregate_shape(sources: List[List[List[List[float]]]]) -> tuple[int, int, int, int]:
    batch = len(sources)
    if not (1 <= batch <= MAX_BATCH):
        raise IntegrityViolation("aggregate batch dimension is outside bounds")
    tokens = len(sources[0])
    if not (1 <= tokens <= MAX_TOKENS):
        raise IntegrityViolation("aggregate token dimension is outside bounds")
    source_count = len(sources[0][0])
    if not (1 <= source_count <= MAX_SOURCES):
        raise IntegrityViolation("aggregate source dimension is outside bounds")
    dimension = len(sources[0][0][0])
    if not (1 <= dimension <= MAX_DIMENSION):
        raise IntegrityViolation("aggregate vector dimension is outside bounds")
    total = batch * tokens * source_count * dimension
    if total > MAX_AGGREGATE_ELEMENTS:
        raise IntegrityViolation("aggregate tensor exceeds the element limit")
    for batch_row in sources:
        if len(batch_row) != tokens:
            raise IntegrityViolation("aggregate tensor must be rectangular")
        for token_row in batch_row:
            if len(token_row) != source_count:
                raise IntegrityViolation("aggregate tensor must be rectangular")
            for vector in token_row:
                if len(vector) != dimension:
                    raise IntegrityViolation("aggregate tensor must be rectangular")
                if not all(math.isfinite(float(value)) for value in vector):
                    raise IntegrityViolation("aggregate tensor values must be finite")
    return batch, tokens, source_count, dimension


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "schema": "szl.gdw.error/v1",
            "label": "MODELED",
            "status": "MODELED",
            "citations": PRIMARY_CITATIONS,
            "error": code,
            "message": message,
        },
    )


def register(
    app: FastAPI,
    ns: str = "a11oy",
    *,
    store: Optional[SQLiteWorkspaceStore] = None,
    workspace: Optional[GovernedDeltaWorkspace] = None,
    kernel: Any = None,
    db_path: Optional[str | Path] = None,
    telemetry: Optional[OperationalTelemetry] = None,
    governance_gate: Optional[
        Callable[[Mapping[str, Any]], Mapping[str, Any]]
    ] = None,
    persistent_required: Optional[bool] = None,
    required_mount: Optional[str | Path] = None,
    journal_mode: Optional[str] = None,
    max_sessions: Optional[int] = None,
) -> Mapping[str, Any]:
    """Register the GDW surface before the host application's SPA catch-all."""

    if not _NS_PATTERN.fullmatch(ns):
        raise ValueError("namespace has an invalid format")
    base = f"/api/{ns}/v1/gdw"
    marker = f"_szl_gdw_registered_{ns}"
    if getattr(app.state, marker, False):
        return {
            "status": "already_registered",
            "label": "MODELED",
            "base": base,
            "runtime_ready": (
                (workspace is not None or kernel is not None)
                and governance_gate is not None
            ),
            "governance_ready": governance_gate is not None,
        }

    storage_unavailable: Optional[Mapping[str, Any]] = None
    if store is None:
        ephemeral_allowed = os.environ.get("SZL_GDW_ALLOW_EPHEMERAL") == "1"
        require_persistent = (
            persistent_required
            if persistent_required is not None
            else db_path is None and not ephemeral_allowed
        )
        selected_path = (
            str(db_path)
            if db_path is not None
            else os.environ.get(
                "SZL_GDW_DB_PATH",
                (
                    str(Path(tempfile.gettempdir()) / "szl-gdw.sqlite3")
                    if ephemeral_allowed
                    else "/data/a11oy/gdw/workspace.sqlite3"
                ),
            )
        )
        selected_mount = (
            str(required_mount)
            if required_mount is not None
            else os.environ.get("SZL_GDW_REQUIRED_MOUNT", "/data")
            if require_persistent
            else None
        )
        try:
            selected_journal_mode = (
                journal_mode
                if journal_mode is not None
                else os.environ.get(
                    "SZL_GDW_SQLITE_JOURNAL_MODE",
                    "DELETE" if require_persistent else "WAL",
                )
            )
            selected_max_sessions = (
                max_sessions
                if max_sessions is not None
                else _positive_bounded_int(
                    os.environ.get("SZL_GDW_MAX_SESSIONS", ""),
                    default=DEFAULT_MAX_SESSIONS,
                    maximum=100_000,
                )
            )
            store = SQLiteWorkspaceStore(
                selected_path,
                persistent_required=require_persistent,
                required_mount=selected_mount,
                journal_mode=selected_journal_mode,
                max_sessions=selected_max_sessions,
            )
        except PersistenceError:
            store = None
            storage_unavailable = {
                "schema": "szl.gdw.storage-snapshot/v1",
                "status": "UNAVAILABLE",
                "path": str(Path(selected_path)),
                "persistent_required": require_persistent,
                "required_mount": selected_mount,
                "mount_ok": False,
            }
    if telemetry is None:
        telemetry = OperationalTelemetry()
    if workspace is None:
        workspace = GovernedDeltaWorkspace(
            kernel if kernel is not None else GovernedWorkspaceKernel()
        )

    runtime = workspace
    repository = store
    observations = telemetry

    @app.get(base + "/status", include_in_schema=False)
    async def gdw_status():
        if repository is None:
            storage = storage_unavailable
            storage_ready = False
        else:
            try:
                storage = repository.snapshot()
                storage_ready = True
            except PersistenceError:
                storage = {
                    "schema": "szl.gdw.storage-snapshot/v1",
                    "status": "UNAVAILABLE",
                    "persistent_required": True,
                    "mount_ok": False,
                }
                storage_ready = False
        return {
            "schema": "szl.gdw.status/v1",
            "label": "MODELED",
            "status": "MODELED",
            "citations": PRIMARY_CITATIONS,
            "runtime_ready": (
                runtime is not None
                and storage_ready
                and governance_gate is not None
            ),
            "storage_ready": storage_ready,
            "governance_ready": governance_gate is not None,
            "storage": storage,
            "limitations": {
                "training_evidence": "UNAVAILABLE",
                "hardware_observation": "UNAVAILABLE",
                "performance_claim": "UNAVAILABLE",
            },
        }

    @app.post(base + "/sessions", status_code=201, include_in_schema=False)
    async def gdw_create_session(request: Request):
        try:
            body = await _parse_body(request, SessionCreateRequest)
        except IntegrityViolation:
            observations.record_error("validation")
            return _error(422, "INVALID_INPUT", "session request is invalid")
        if repository is None:
            observations.record_error("persistence")
            return _error(
                503, "PERSISTENCE_UNAVAILABLE", "session storage unavailable"
            )
        try:
            session_id = (
                _valid_identifier(body.session_id, "session_id")
                if body.session_id
                else f"gdw-{uuid4().hex}"
            )
            state = WorkspaceState(
                session_id=session_id,
                step=0,
                risk_budget=body.risk_budget,
            )
            result = repository.create_session(state)
            observations.record_session_created()
            return {
                "schema": "szl.gdw.session/v1",
                "label": "MODELED",
                "status": "MODELED",
                "citations": PRIMARY_CITATIONS,
                **result,
                "state": state_to_dict(state),
            }
        except IntegrityViolation:
            observations.record_error("validation")
            return _error(422, "INVALID_INPUT", "session request is invalid")
        except SessionConflict:
            observations.record_error("conflict")
            return _error(409, "SESSION_CONFLICT", "session already exists")
        except SessionLimitExceeded:
            observations.record_error("quota")
            return _error(
                429,
                "SESSION_LIMIT_REACHED",
                "durable workspace session quota is exhausted",
            )
        except PersistenceError:
            observations.record_error("persistence")
            return _error(503, "PERSISTENCE_UNAVAILABLE", "session could not be stored")

    @app.get(base + "/sessions/{session_id}", include_in_schema=False)
    async def gdw_read_session(session_id: str):
        if repository is None:
            return _error(
                503, "PERSISTENCE_UNAVAILABLE", "session storage unavailable"
            )
        try:
            record = repository.recover_session(session_id)
            return {
                "schema": "szl.gdw.session/v1",
                "label": "MODELED",
                "status": "MODELED",
                "citations": PRIMARY_CITATIONS,
                "session_id": session_id,
                "state": state_to_dict(record["state"]),
                "state_hash": record["state_hash"],
                "revision": record["revision"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
            }
        except IntegrityViolation:
            return _error(422, "INVALID_INPUT", "session identifier is invalid")
        except SessionNotFound:
            return _error(404, "NOT_FOUND", "session does not exist")
        except PersistenceError:
            return _error(503, "PERSISTENCE_UNAVAILABLE", "session read unavailable")

    @app.post(base + "/sessions/{session_id}/step", include_in_schema=False)
    async def gdw_step(session_id: str, request: Request):
        try:
            body = await _parse_body(request, StepRequest)
        except IntegrityViolation:
            observations.record_error("validation")
            return _error(422, "INVALID_INPUT", "step request is invalid")
        if runtime is None or repository is None or governance_gate is None:
            observations.record_error("unavailable")
            return _error(
                503,
                "GOVERNED_RUNTIME_UNAVAILABLE",
                "governance gate, governed runtime, or durable storage is unavailable",
            )
        try:
            session_id = _valid_identifier(session_id, "session_id")
            _validate_step(body)
            request_payload = _request_payload(body)
            request_hash = _canonical_digest(request_payload)
            replay = repository.lookup_operation(
                session_id, body.idempotency_key, request_hash
            )
            if replay is not None:
                response = dict(replay.response)
                response["replayed"] = True
                observations.record_step(
                    str(response.get("decision", "UNAVAILABLE")), replayed=True
                )
                return response

            governance = governance_gate(
                {
                    "type": "workspace.step",
                    "target": f"szl://gdw/session/{session_id}",
                    "effecting": True,
                    "irreversible": False,
                    "impact": "MODERATE",
                    "request": body.request,
                    "risk_budget": body.risk_budget,
                    "evidence_count": len(body.evidence),
                    "allowed_expert_count": len(body.allowed_experts),
                }
            )
            if (
                not isinstance(governance, Mapping)
                or governance.get("allowed") is not True
                or governance.get("decision") != "ALLOW"
            ):
                observations.record_error("governance")
                return _error(
                    403,
                    "GOVERNANCE_DENIED",
                    "the file-backed governance boundary denied this step",
                )
            governance_payload = _api_jsonable(governance)
            _canonical_digest(governance_payload)
            record = repository.recover_session(session_id)
            state = record["state"]
            evidence = [
                Evidence(
                    evidence_id=item.evidence_id,
                    uri=item.uri,
                    content_hash=item.content_hash,
                    trust=item.trust,
                    observed_at=item.observed_at,
                )
                for item in body.evidence
            ]
            next_state, audit = runtime.step(
                state=state,
                request=body.request,
                evidence=evidence,
                allowed_experts=list(body.allowed_experts),
                risk_budget=body.risk_budget,
                dry_run=False,
            )
            receipt = audit.get("receipt")
            if receipt is None:
                raise IntegrityViolation("governed write returned no receipt")
            receipt_payload = receipt_to_dict(receipt)
            audit_payload = _api_jsonable(audit)
            audit_payload["receipt"] = receipt_payload
            audit_payload["governance"] = governance_payload
            _canonical_digest(audit_payload)
            response = {
                "schema": "szl.gdw.step/v1",
                "label": "MODELED",
                "status": "MODELED",
                "citations": PRIMARY_CITATIONS,
                "session_id": session_id,
                "proposal_id": receipt_payload["proposal_id"],
                "decision": receipt_payload["decision"],
                "state_hash": next_state.canonical_hash(),
                "state": state_to_dict(next_state),
                "audit": audit_payload,
                "replayed": False,
            }
            committed = repository.commit_transition(
                session_id=session_id,
                idempotency_key=body.idempotency_key,
                request_hash=request_hash,
                expected_state_hash=record["state_hash"],
                next_state=next_state,
                receipt=receipt,
                response=response,
            )
            result = dict(committed.response)
            result["replayed"] = committed.replayed
            observations.record_step(
                str(result.get("decision", "UNAVAILABLE")),
                replayed=committed.replayed,
            )
            return result
        except IntegrityViolation:
            observations.record_error("integrity")
            return _error(
                422, "INVALID_OR_UNVERIFIED_WRITE", "governed write was not persisted"
            )
        except ReplayConflict:
            observations.record_error("conflict")
            return _error(
                409,
                "IDEMPOTENCY_CONFLICT",
                "idempotency key is bound to another request",
            )
        except SessionConflict:
            observations.record_error("conflict")
            return _error(409, "SESSION_CONFLICT", "session changed; retry safely")
        except SessionNotFound:
            observations.record_error("not_found")
            return _error(404, "NOT_FOUND", "session does not exist")
        except PersistenceError:
            observations.record_error("persistence")
            return _error(503, "PERSISTENCE_UNAVAILABLE", "write storage unavailable")
        except Exception:
            observations.record_error("unavailable")
            return _error(
                503,
                "GOVERNED_RUNTIME_UNAVAILABLE",
                "governed step failed closed",
            )

    @app.get(base + "/receipts/{receipt_id}", include_in_schema=False)
    async def gdw_receipt(receipt_id: str):
        if repository is None:
            return _error(
                503, "PERSISTENCE_UNAVAILABLE", "receipt storage unavailable"
            )
        try:
            record = repository.get_receipt(receipt_id)
            return {
                "schema": "szl.gdw.receipt-view/v1",
                "label": "MODELED",
                "status": "MODELED",
                "citations": PRIMARY_CITATIONS,
                **record,
            }
        except IntegrityViolation:
            return _error(422, "INVALID_INPUT", "receipt identifier is invalid")
        except SessionNotFound:
            return _error(404, "NOT_FOUND", "receipt does not exist")
        except PersistenceError:
            return _error(503, "PERSISTENCE_UNAVAILABLE", "receipt read unavailable")

    @app.get(base + "/telemetry", include_in_schema=False)
    async def gdw_telemetry():
        if repository is None:
            return _error(503, "PERSISTENCE_UNAVAILABLE", "telemetry unavailable")
        try:
            storage = repository.snapshot()
        except PersistenceError:
            return _error(503, "PERSISTENCE_UNAVAILABLE", "telemetry unavailable")
        return {
            **dict(observations.snapshot(storage)),
            "label": "MODELED",
            "citations": PRIMARY_CITATIONS,
        }

    @app.post(base + "/aggregate", include_in_schema=False)
    async def gdw_aggregate(request: Request):
        try:
            body = await _parse_body(request, AggregateRequest)
        except IntegrityViolation:
            observations.record_error("validation")
            return _error(422, "INVALID_INPUT", "aggregate tensor is invalid")
        try:
            batch, tokens, source_count, dimension = _aggregate_shape(body.sources)
        except IntegrityViolation:
            observations.record_error("validation")
            return _error(422, "INVALID_INPUT", "aggregate tensor is invalid")
        try:
            import torch

            from .lambda_attnres import LambdaAttnRes
        except (ImportError, OSError):
            observations.record_aggregate(available=False)
            return JSONResponse(
                status_code=503,
                content={
                    "schema": "szl.gdw.aggregate/v1",
                    "label": "MODELED",
                    "status": "UNAVAILABLE",
                    "citations": PRIMARY_CITATIONS,
                    "reason": "tensor backend is not installed",
                    "shape": [batch, tokens, source_count, dimension],
                    "performance_claim": "UNAVAILABLE",
                },
            )
        try:
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(0)
                module = LambdaAttnRes(
                    d_model=dimension,
                    n_sources_max=source_count,
                    lam_init=body.lam,
                    egyptian=body.egyptian,
                    depth=body.depth,
                    eps=body.eps,
                )
                module.eval()
                tensor = torch.tensor(body.sources, dtype=torch.float32)
                with torch.no_grad():
                    output, certificate = module(tensor, return_cert=True)
            result = output.detach().cpu().tolist()
            if not all(
                math.isfinite(float(value))
                for batch_row in result
                for token_row in batch_row
                for value in token_row
            ):
                raise ValueError("non-finite aggregate output")
        except Exception:
            observations.record_error("unavailable")
            observations.record_aggregate(available=False)
            return _error(
                503,
                "TENSOR_BACKEND_FAILURE",
                "aggregate computation failed closed",
            )
        observations.record_aggregate(available=True)
        return {
            "schema": "szl.gdw.aggregate/v1",
            "label": "MODELED",
            "status": "MODELED",
            "citations": PRIMARY_CITATIONS,
            "shape": [batch, tokens, dimension],
            "output": result,
            "certificate": certificate,
            "performance_claim": "UNAVAILABLE",
        }

    setattr(app.state, marker, True)
    return {
        "status": "registered",
        "label": "MODELED",
        "base": base,
        "citations": PRIMARY_CITATIONS,
        "runtime_ready": (
            runtime is not None
            and repository is not None
            and governance_gate is not None
        ),
        "storage_ready": repository is not None,
        "governance_ready": governance_gate is not None,
        "routes": [
            base + "/status",
            base + "/sessions",
            base + "/sessions/{session_id}",
            base + "/sessions/{session_id}/step",
            base + "/receipts/{receipt_id}",
            base + "/telemetry",
            base + "/aggregate",
        ],
    }
