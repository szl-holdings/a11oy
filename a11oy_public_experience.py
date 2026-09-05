#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded public governed-action experience for the A11oy front door.

This module is an isolated FastAPI service-layer adapter.  It never calls a real
effector, never appends to an operational receipt chain, and never upgrades a
simulation into live evidence.  Every public scenario is server-allowlisted and
deterministic, every lifecycle edge is validated, and every terminal simulation
produces a receipt in the separate ``sim-experience`` namespace.

GET handlers are pure projections.  The only domain writes are session creation
and scoped approval; receipt verification recomputes a supplied or stored object
without changing it.  Registration front-moves the exact routes so an existing
SPA catch-all cannot turn a missing JSON route into an HTML 200.
"""

import base64
import copy
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Mapping
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)


API_PREFIX = "/api/experience/v1"
SCENARIO_SCHEMA = "a11oy.public-experience.scenarios/v1"
ESTATE_CONFIG_SCHEMA = "a11oy.public-experience.estate-projection/v1"
EVENT_SCHEMA = "a11oy.public-experience.event/v1"
SESSION_SCHEMA = "a11oy.public-experience.session/v1"
RECEIPT_SCHEMA = "a11oy.public-experience.receipt/v1"
VERIFY_SCHEMA = "a11oy.public-experience.receipt-verification/v1"
RECEIPT_NAMESPACE = "sim-experience"
RECEIPT_PAYLOAD_TYPE = "application/vnd.a11oy.public-experience-receipt.v1+json"
HOST_RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.receipt+json"
EXPECTED_RECEIPT_PAYLOAD_TYPES = frozenset(
    {RECEIPT_PAYLOAD_TYPE, HOST_RECEIPT_PAYLOAD_TYPE}
)
GENESIS_HASH = "0" * 64

DEFAULT_SESSION_TTL_SECONDS = 600
MAX_SESSION_TTL_SECONDS = 3600
DEFAULT_CAPABILITY_TTL_SECONDS = 300
DEFAULT_MAX_SESSIONS = 256
DEFAULT_MAX_RECEIPTS = 512
DEFAULT_RECEIPT_TTL_SECONDS = 3600
MAX_RECEIPT_TTL_SECONDS = 86_400
MAX_EVENTS_PER_SESSION = 32
MAX_REQUEST_BYTES = 16 * 1024
MAX_VERIFY_REQUEST_BYTES = 128 * 1024
MAX_SSE_AFTER = 9_223_372_036_854_775_807
RATE_WINDOW_SECONDS = 60
DEFAULT_MAX_RATE_BUCKETS = 4096
ROUTE_OWNER = "a11oy.public-experience/v1"
IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)

EXPECTED_SCENARIO_IDS = frozenset(
    {
        "investigate-outage",
        "screen-vessel",
        "review-property",
        "review-contract",
        "route-inference",
    }
)


class ExperienceStage(str, Enum):
    CREATED = "CREATED"
    PROPOSED = "PROPOSED"
    EVIDENCE_BOUND = "EVIDENCE_BOUND"
    QUALIFIED = "QUALIFIED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    RECEIPTED = "RECEIPTED"
    POLICY_DENIED = "POLICY_DENIED"
    BLOCKED = "BLOCKED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


class DataState(str, Enum):
    LIVE = "LIVE"
    MEASURED = "MEASURED"
    SIMULATION = "SIMULATION"
    SNAPSHOT = "SNAPSHOT"
    MODELED = "MODELED"
    UNAVAILABLE = "UNAVAILABLE"


TERMINAL_STAGES = frozenset(
    {
        ExperienceStage.RECEIPTED,
        ExperienceStage.POLICY_DENIED,
        ExperienceStage.BLOCKED,
        ExperienceStage.VERIFICATION_FAILED,
        ExperienceStage.RECOVERY_REQUIRED,
        ExperienceStage.UNAVAILABLE,
    }
)

# Every enum member is present, including every terminal member with no exits.
LEGAL_TRANSITIONS: dict[ExperienceStage, frozenset[ExperienceStage]] = {
    ExperienceStage.CREATED: frozenset(
        {ExperienceStage.PROPOSED, ExperienceStage.BLOCKED, ExperienceStage.UNAVAILABLE}
    ),
    ExperienceStage.PROPOSED: frozenset(
        {
            ExperienceStage.EVIDENCE_BOUND,
            ExperienceStage.BLOCKED,
            ExperienceStage.UNAVAILABLE,
        }
    ),
    ExperienceStage.EVIDENCE_BOUND: frozenset(
        {
            ExperienceStage.QUALIFIED,
            ExperienceStage.BLOCKED,
            ExperienceStage.UNAVAILABLE,
        }
    ),
    ExperienceStage.QUALIFIED: frozenset(
        {
            ExperienceStage.POLICY_EVALUATED,
            ExperienceStage.BLOCKED,
            ExperienceStage.UNAVAILABLE,
        }
    ),
    ExperienceStage.POLICY_EVALUATED: frozenset(
        {
            ExperienceStage.APPROVAL_REQUIRED,
            ExperienceStage.EXECUTING,
            ExperienceStage.POLICY_DENIED,
            ExperienceStage.BLOCKED,
            ExperienceStage.UNAVAILABLE,
        }
    ),
    ExperienceStage.APPROVAL_REQUIRED: frozenset(
        {ExperienceStage.APPROVED, ExperienceStage.BLOCKED, ExperienceStage.UNAVAILABLE}
    ),
    ExperienceStage.APPROVED: frozenset(
        {ExperienceStage.EXECUTING, ExperienceStage.BLOCKED, ExperienceStage.UNAVAILABLE}
    ),
    ExperienceStage.EXECUTING: frozenset(
        {
            ExperienceStage.VERIFIED,
            ExperienceStage.VERIFICATION_FAILED,
            ExperienceStage.RECOVERY_REQUIRED,
            ExperienceStage.BLOCKED,
            ExperienceStage.UNAVAILABLE,
        }
    ),
    ExperienceStage.VERIFIED: frozenset(
        {
            ExperienceStage.RECEIPTED,
            ExperienceStage.RECOVERY_REQUIRED,
            ExperienceStage.UNAVAILABLE,
        }
    ),
    ExperienceStage.RECEIPTED: frozenset(),
    ExperienceStage.POLICY_DENIED: frozenset(),
    ExperienceStage.BLOCKED: frozenset(),
    ExperienceStage.VERIFICATION_FAILED: frozenset(),
    ExperienceStage.RECOVERY_REQUIRED: frozenset(),
    ExperienceStage.UNAVAILABLE: frozenset(),
}


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )


class EvidenceConfig(StrictModel):
    id: str = Field(min_length=1, max_length=96, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=160)
    source_class: Literal["SIMULATION", "SNAPSHOT", "UNAVAILABLE"]
    uri: str | None = Field(default=None, max_length=512)

    @field_validator("uri")
    @classmethod
    def reject_nonpublic_uri(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme
            or parsed.netloc
            or not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)
        ):
            raise ValueError("evidence URI must be a same-origin absolute path")
        return value


class EvidenceHandle(StrictModel):
    id: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=160)
    source_class: Literal["SIMULATION", "SNAPSHOT", "UNAVAILABLE"]
    uri: str | None = Field(default=None, max_length=512)
    observed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScenarioDefinition(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1, max_length=32, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    title: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=240)
    domain: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    action: str = Field(min_length=1, max_length=96, pattern=r"^simulate\.[a-z0-9][a-z0-9-]*$")
    data_state: Literal["SIMULATION"]
    approval_required: StrictBool
    approval_scope: str | None = Field(default=None, max_length=160)
    seed: StrictInt = Field(ge=0, le=2_147_483_647)
    outcome: ExperienceStage
    model_revision: str | None = Field(default=None, max_length=128)
    evidence: list[EvidenceConfig] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_public_scenario(self) -> "ScenarioDefinition":
        if self.outcome not in TERMINAL_STAGES:
            raise ValueError("scenario outcome must be terminal")
        if self.approval_required and not self.approval_scope:
            raise ValueError("approval-required scenario must define a scope")
        if not self.approval_required and self.approval_scope is not None:
            raise ValueError("non-approval scenario must not define a scope")
        if self.outcome in {ExperienceStage.POLICY_DENIED, ExperienceStage.UNAVAILABLE} and self.approval_required:
            raise ValueError("pre-execution terminal scenario cannot require approval")
        if len({item.id for item in self.evidence}) != len(self.evidence):
            raise ValueError("scenario evidence ids must be unique")
        return self


class ScenarioSetConfig(StrictModel):
    spdx_license: Literal["Apache-2.0"] = Field(alias="_spdx_license")
    copyright_notice: Literal[
        "(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173"
    ] = Field(alias="_copyright")
    schema_id: Literal[SCENARIO_SCHEMA] = Field(alias="schema")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    policy_revision: str = Field(min_length=1, max_length=96)
    scenarios: list[ScenarioDefinition] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_ids(self) -> "ScenarioSetConfig":
        ids = [item.id for item in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario ids must be unique")
        if set(ids) != set(EXPECTED_SCENARIO_IDS):
            raise ValueError("scenario set must contain exactly the five public scenarios")
        return self


class EstateProjectionAssetConfig(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=180)
    kind: Literal["platform", "flagship"]
    vertical: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    public: Literal[True]
    active: Literal[True]
    visual_mode: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    scenario_ids: list[str] = Field(min_length=1, max_length=8)
    tags: list[str] = Field(min_length=1, max_length=12)
    evidence_path: str = Field(min_length=1, max_length=160, pattern=r"^/[A-Za-z0-9/_?&.=-]*$")

    @model_validator(mode="after")
    def validate_projection_asset(self) -> "EstateProjectionAssetConfig":
        if len(self.summary.split()) > 18:
            raise ValueError("public asset summary must not exceed 18 words")
        if len(self.scenario_ids) != len(set(self.scenario_ids)):
            raise ValueError("asset scenario ids must be unique")
        if not set(self.scenario_ids).issubset(EXPECTED_SCENARIO_IDS):
            raise ValueError("asset references a non-public scenario")
        normalized_tags = [tag.strip().lower() for tag in self.tags]
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tag) for tag in normalized_tags):
            raise ValueError("asset tags must be lowercase public tokens")
        if self.tags != normalized_tags:
            raise ValueError("asset tags must already be normalized lowercase tokens")
        if len(normalized_tags) != len(set(normalized_tags)):
            raise ValueError("asset tags must be unique")
        return self


class EstateProjectionConfig(StrictModel):
    spdx_license: Literal["Apache-2.0"] = Field(alias="_spdx_license")
    copyright_notice: Literal[
        "(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173"
    ] = Field(alias="_copyright")
    schema_id: Literal[ESTATE_CONFIG_SCHEMA] = Field(alias="schema")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    source_manifest: Literal["governance/public-estate.v1.json"]
    assets: list[EstateProjectionAssetConfig] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_asset_ids(self) -> "EstateProjectionConfig":
        ids = [item.id for item in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError("estate projection ids must be unique")
        return self


class PublicEstateAsset(StrictModel):
    id: str
    title: str
    summary: str
    kind: Literal["platform", "flagship"]
    vertical: str
    public: Literal[True]
    active: Literal[True]
    source_url: str
    live_url: str
    evidence_url: str
    visual_mode: str
    scenario_ids: list[str]
    tags: list[str]
    status_source: str
    data_state: Literal["SNAPSHOT"]


class PolicyResult(StrictModel):
    authority_state: Literal["UNAVAILABLE"]
    authoritative: Literal[False]
    simulation_decision: Literal[
        "ALLOW_SIMULATION", "REQUIRE_APPROVAL", "DENY_SIMULATION", "UNAVAILABLE"
    ]
    revision: str
    reason_codes: list[str] = Field(min_length=1, max_length=8)


class ApprovalState(StrictModel):
    state: Literal["NOT_REQUIRED", "REQUIRED", "APPROVED"]
    scope: str | None = None
    capability_id: str | None = None
    expires_at: datetime | None = None
    issued_sequence: StrictInt | None = Field(default=None, ge=0)
    token_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class EffectResult(StrictModel):
    state: Literal["SIMULATED_NO_EXTERNAL_EFFECT"]
    external_effector_state: Literal["UNAVAILABLE"]
    detail: str = Field(min_length=1, max_length=240)


class VerificationResult(StrictModel):
    state: Literal[
        "NOT_RUN",
        "SIMULATION_VERIFIED",
        "VERIFICATION_FAILED",
        "RECOVERY_REQUIRED",
        "UNAVAILABLE",
    ]
    authoritative: Literal[False]
    detail: str = Field(min_length=1, max_length=240)


class ReplayInfo(StrictModel):
    scenario_version: str
    seed: StrictInt
    policy_revision: str
    model_revision: str | None
    evidence_snapshot_ids: list[str]
    simulation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExperienceEvent(StrictModel):
    schema_id: Literal[EVENT_SCHEMA] = Field(alias="schema")
    event_id: str = Field(pattern=r"^evt_[0-9a-f]{32}$")
    session_id: str = Field(pattern=r"^exp_[0-9a-f]{32}$")
    sequence: StrictInt = Field(ge=0, le=MAX_EVENTS_PER_SESSION - 1)
    stage: ExperienceStage
    scenario_id: str
    scenario_version: str
    domain: str
    action: str
    data_state: Literal["SIMULATION"]
    evidence: list[EvidenceHandle] = Field(default_factory=list, max_length=8)
    policy_result: PolicyResult | None = None
    approval_state: ApprovalState | None = None
    effect_result: EffectResult | None = None
    verification_result: VerificationResult | None = None
    receipt_id: str | None = Field(default=None, pattern=r"^sim-experience:[0-9a-f]{32}$")
    previous_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    emitted_at: datetime


class ApprovalCapabilityPayload(StrictModel):
    capability_id: str = Field(pattern=r"^expcap:[0-9a-f]{24}$")
    session_id: str = Field(pattern=r"^exp_[0-9a-f]{32}$")
    scenario_id: str
    action: str
    scenario_version: str
    scope: str
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{32,128}$")
    issued_sequence: StrictInt = Field(ge=0, le=MAX_EVENTS_PER_SESSION - 1)
    expires_at: datetime


class ApprovalCapability(StrictModel):
    token: str = Field(min_length=64, max_length=2048, pattern=r"^expcap1\.[A-Za-z0-9_-]+$")
    capability_id: str
    scope: str
    issued_sequence: StrictInt
    expires_at: datetime


class ApprovalSummary(StrictModel):
    required: StrictBool
    state: Literal["NOT_REQUIRED", "REQUIRED", "APPROVED"]
    scope: str | None
    capability_id: str | None
    expires_at: datetime | None
    issued_sequence: StrictInt | None


class CreateSessionRequest(StrictModel):
    scenario_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")


class ApproveSessionRequest(StrictModel):
    capability_token: str = Field(min_length=64, max_length=2048, pattern=r"^expcap1\.[A-Za-z0-9_-]+$")
    scope: str = Field(min_length=1, max_length=160)
    expected_sequence: StrictInt = Field(ge=0, le=MAX_EVENTS_PER_SESSION - 1)


class SessionResponse(StrictModel):
    schema_id: Literal[SESSION_SCHEMA] = Field(alias="schema")
    session_id: str
    scenario_id: str
    scenario_version: str
    domain: str
    action: str
    data_state: Literal["SIMULATION"]
    stage: ExperienceStage
    terminal: StrictBool
    created_at: datetime
    expires_at: datetime
    next_sequence: StrictInt
    events_url: str
    approval: ApprovalSummary
    replay: ReplayInfo
    receipt_id: str | None
    idempotent_replay: StrictBool
    approval_capability: ApprovalCapability | None


class ExperienceReceipt(StrictModel):
    schema_id: Literal[RECEIPT_SCHEMA] = Field(alias="schema")
    receipt_id: str = Field(pattern=r"^sim-experience:[0-9a-f]{32}$")
    namespace: Literal[RECEIPT_NAMESPACE]
    data_state: Literal["SIMULATION"]
    session_id: str
    scenario_id: str
    scenario_version: str
    final_stage: ExperienceStage
    created_at: datetime
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    chain_integrity: Literal["INTACT"]
    signer_state: Literal[
        "UNSIGNED",
        "UNAVAILABLE",
        "SIGNED_UNVERIFIED",
        "VERIFIED_SIGNATURE",
        "VERIFIED_EPHEMERAL",
        "VERIFIED_PERSISTENT",
    ]
    effect_state: Literal["SIMULATED_NO_EXTERNAL_EFFECT"]
    verification_state: Literal["VERIFIED", "PARTIAL", "FAILED"]
    policy_result: PolicyResult | None
    approval_result: ApprovalState
    verification_result: VerificationResult
    evidence: list[EvidenceHandle] = Field(max_length=8)
    replay: ReplayInfo
    events: list[ExperienceEvent] = Field(min_length=1, max_length=MAX_EVENTS_PER_SESSION)
    envelope: dict[str, Any]
    limitations: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_terminal_receipt(self) -> "ExperienceReceipt":
        if self.final_stage not in TERMINAL_STAGES:
            raise ValueError("receipt final stage must be terminal")
        if self.current_hash != self.receipt_digest:
            raise ValueError("receipt current_hash must equal receipt_digest")
        return self


class VerifyReceiptRequest(StrictModel):
    receipt: ExperienceReceipt | None = None


class VerifyReceiptResponse(StrictModel):
    schema_id: Literal[VERIFY_SCHEMA] = Field(alias="schema")
    receipt_id: str
    ok: StrictBool
    chain_integrity: Literal["INTACT", "FAILED"]
    signer_state: str
    effect_state: str
    verification_state: Literal["VERIFIED", "PARTIAL", "FAILED"]
    checks: dict[str, str]


class EstateResponse(StrictModel):
    schema_id: Literal["a11oy.public-experience.estate/v1"] = Field(alias="schema")
    data_state: Literal["SNAPSHOT"]
    source_schema: Literal["szl.public-estate/v1"]
    source_repository: str
    projection_version: str
    assets: list[PublicEstateAsset]


class ScenarioListResponse(StrictModel):
    schema_id: Literal["a11oy.public-experience.scenario-list/v1"] = Field(alias="schema")
    data_state: Literal["SIMULATION"]
    scenario_set_version: str
    scenarios: list[ScenarioDefinition]


class StorageStatus(StrictModel):
    state: Literal["EPHEMERAL"]
    persistence_across_restart: Literal[False]
    session_ttl_seconds: StrictInt
    receipt_ttl_seconds: StrictInt
    session_capacity_remaining: StrictInt
    receipt_capacity_remaining: StrictInt
    retention_policy: Literal["TTL_BOUNDED"]
    active_sessions: StrictInt
    stored_receipts: StrictInt


class HealthResponse(StrictModel):
    schema_id: Literal["a11oy.public-experience.health/v1"] = Field(alias="schema")
    status: Literal["READY", "DEGRADED"]
    data_state: Literal["SIMULATION"]
    external_authority_state: Literal["UNAVAILABLE"]
    storage: StorageStatus
    limits: dict[str, StrictInt]
    scenario_count: StrictInt
    estate_asset_count: StrictInt
    endpoints: list[str]


@dataclass
class SessionRecord:
    session_id: str
    scenario: ScenarioDefinition
    created_at: datetime
    expires_at: datetime
    replay: ReplayInfo
    events: list[ExperienceEvent] = field(default_factory=list)
    approval_state: ApprovalState = field(
        default_factory=lambda: ApprovalState(state="NOT_REQUIRED")
    )
    approval_token_hash: str | None = None
    approval_binding: ApprovalCapabilityPayload | None = None
    approval_consumed: bool = False
    policy_result: PolicyResult | None = None
    effect_result: EffectResult | None = None
    verification_result: VerificationResult = field(
        default_factory=lambda: VerificationResult(
            state="NOT_RUN",
            authoritative=False,
            detail="No simulated verification step has run.",
        )
    )
    receipt_id: str | None = None

    @property
    def stage(self) -> ExperienceStage:
        if not self.events:
            raise RuntimeError("session has no lifecycle events")
        return self.events[-1].stage

    @property
    def terminal(self) -> bool:
        return self.stage in TERMINAL_STAGES


@dataclass(frozen=True)
class IdempotencyRecord:
    request_digest: str
    session_id: str
    expires_at: datetime


class ExperienceAPIError(RuntimeError):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=False)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "type": str(error.get("type", "validation_error")),
            "message": str(error.get("msg", "invalid value"))[:240],
        }
        for error in exc.errors(include_url=False, include_context=False, include_input=False)
    ]


class FixedWindowRateLimiter:
    """Small process-local limiter for a single-process public demo surface."""

    def __init__(
        self,
        window_seconds: int = RATE_WINDOW_SECONDS,
        max_buckets: int = DEFAULT_MAX_RATE_BUCKETS,
    ) -> None:
        self.window_seconds = max(1, int(window_seconds))
        self.max_buckets = max(1, min(int(max_buckets), 65_536))
        self._lock = threading.RLock()
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._next_sweep_at = 0.0

    def _prune_stale_locked(self, now: float) -> None:
        cutoff = now - self.window_seconds
        for key, bucket in list(self._buckets.items()):
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                self._buckets.pop(key, None)
        self._next_sweep_at = now + self.window_seconds

    def check(self, key: str, limit: int, now: float) -> None:
        with self._lock:
            if now >= self._next_sweep_at or (
                key not in self._buckets and len(self._buckets) >= self.max_buckets
            ):
                self._prune_stale_locked(now)
            if key not in self._buckets and len(self._buckets) >= self.max_buckets:
                raise ExperienceAPIError(
                    429,
                    "RATE_LIMITED",
                    "Public experience request limit reached; retry after the current window.",
                )
            bucket = self._buckets[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                raise ExperienceAPIError(
                    429,
                    "RATE_LIMITED",
                    "Public experience request limit reached; retry after the current window.",
                )
            bucket.append(now)


class ExperienceStore:
    """Bounded, thread-safe, explicitly ephemeral session and receipt store."""

    def __init__(self, max_sessions: int, max_receipts: int) -> None:
        self.max_sessions = max(1, min(int(max_sessions), 4096))
        self.max_receipts = max(1, min(int(max_receipts), 8192))
        self.lock = threading.RLock()
        self.sessions: dict[str, SessionRecord] = {}
        self.receipts: dict[str, ExperienceReceipt] = {}
        self.receipt_expiries: dict[str, datetime] = {}
        self.idempotency: dict[str, IdempotencyRecord] = {}

    def purge_expired_on_write(self, now: datetime) -> None:
        expired_ids = {
            session_id
            for session_id, record in self.sessions.items()
            if record.expires_at <= now
        }
        for session_id in expired_ids:
            self.sessions.pop(session_id, None)
        for key, record in list(self.idempotency.items()):
            if record.expires_at <= now or record.session_id in expired_ids:
                self.idempotency.pop(key, None)
        for receipt_id, expires_at in list(self.receipt_expiries.items()):
            if expires_at <= now:
                self.receipt_expiries.pop(receipt_id, None)
                self.receipts.pop(receipt_id, None)

    def status(self, now: datetime) -> tuple[int, int]:
        with self.lock:
            active = sum(1 for record in self.sessions.values() if record.expires_at > now)
            retained = sum(
                1
                for receipt_id in self.receipts
                if self.receipt_expiries.get(receipt_id, now) > now
            )
            return active, retained


class PublicExperienceService:
    def __init__(
        self,
        *,
        root: Path | None = None,
        config_dir: Path | None = None,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        capability_ttl_seconds: int = DEFAULT_CAPABILITY_TTL_SECONDS,
        receipt_ttl_seconds: int = DEFAULT_RECEIPT_TTL_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        max_receipts: int = DEFAULT_MAX_RECEIPTS,
        now_fn: Callable[[], datetime] = _utc_now,
        monotonic_fn: Callable[[], float] = time.monotonic,
        sign_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        verify_fn: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.root = (root or Path(__file__).resolve().parent).resolve()
        self.config_dir = (
            config_dir or self.root / "config" / "public-experience"
        ).resolve()
        self.session_ttl_seconds = max(
            30, min(int(session_ttl_seconds), MAX_SESSION_TTL_SECONDS)
        )
        self.capability_ttl_seconds = max(
            15,
            min(
                int(capability_ttl_seconds),
                self.session_ttl_seconds,
                DEFAULT_CAPABILITY_TTL_SECONDS,
            ),
        )
        self.receipt_ttl_seconds = max(
            30, min(int(receipt_ttl_seconds), MAX_RECEIPT_TTL_SECONDS)
        )
        self.now_fn = now_fn
        self.monotonic_fn = monotonic_fn
        self.sign_fn = sign_fn
        self.verify_fn = verify_fn
        self.store = ExperienceStore(max_sessions=max_sessions, max_receipts=max_receipts)
        self.rate_limiter = FixedWindowRateLimiter()
        self.rate_limits: dict[str, int] = {
            "read": 120,
            "create": 20,
            "approve": 30,
            "verify": 60,
            "events": 60,
        }

        self.scenario_set = self._load_scenario_set()
        self.scenarios = {item.id: item for item in self.scenario_set.scenarios}
        self.estate_config, self.estate_assets, self.estate_source = self._load_estate()

    def _now(self) -> datetime:
        value = self.now_fn()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RuntimeError("public experience clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    def _load_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"invalid public experience configuration: {path.name}") from exc

    def _load_scenario_set(self) -> ScenarioSetConfig:
        path = self.config_dir / "scenarios.v1.json"
        try:
            return ScenarioSetConfig.model_validate(self._load_json(path))
        except ValidationError as exc:
            raise RuntimeError("public experience scenario configuration failed validation") from exc

    def _load_estate(
        self,
    ) -> tuple[EstateProjectionConfig, list[PublicEstateAsset], dict[str, Any]]:
        projection_path = self.config_dir / "estate-projection.v1.json"
        try:
            projection = EstateProjectionConfig.model_validate(
                self._load_json(projection_path)
            )
        except ValidationError as exc:
            raise RuntimeError("public estate projection failed validation") from exc

        source_path = self.root / "governance" / "public-estate.v1.json"
        source = self._load_json(source_path)
        if not isinstance(source, dict) or source.get("schema") != "szl.public-estate/v1":
            raise RuntimeError("canonical public estate manifest has an unexpected schema")
        if source.get("source_repository") != "szl-holdings/a11oy":
            raise RuntimeError("canonical public estate source repository is unexpected")

        allowed_hosts = source.get("allowed_hosts")
        if not isinstance(allowed_hosts, list) or not all(
            isinstance(host, str) and host for host in allowed_hosts
        ):
            raise RuntimeError("canonical public estate allowed_hosts is invalid")
        host_allowlist = set(allowed_hosts)

        canonical: dict[str, dict[str, Any]] = {}
        for key, expected_kind in (("platforms", "platform"), ("public_products", "flagship")):
            values = source.get(key)
            if not isinstance(values, list):
                raise RuntimeError(f"canonical public estate {key} is invalid")
            for value in values:
                if not isinstance(value, dict) or value.get("public") is not True:
                    raise RuntimeError("canonical public estate contains a non-public projected asset")
                asset_id = value.get("id")
                if not isinstance(asset_id, str) or asset_id in canonical:
                    raise RuntimeError("canonical public estate ids are invalid")
                value = dict(value)
                value["_expected_kind"] = expected_kind
                canonical[asset_id] = value

        projected_ids = {item.id for item in projection.assets}
        if projected_ids != set(canonical):
            raise RuntimeError("estate projection must exactly match canonical public asset ids")

        assets: list[PublicEstateAsset] = []
        for item in projection.assets:
            source_item = canonical[item.id]
            if item.kind != source_item["_expected_kind"]:
                raise RuntimeError(f"estate projection kind mismatch for {item.id}")
            base_url = source_item.get("base_url")
            status_path = source_item.get("build_info_path")
            source_repository = source_item.get("deployment_source_repository")
            if not all(
                isinstance(value, str) and value
                for value in (base_url, status_path, source_repository)
            ):
                raise RuntimeError(f"canonical public estate fields are incomplete for {item.id}")
            parsed = urlsplit(base_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.hostname not in host_allowlist
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise RuntimeError(f"canonical public estate URL is outside the allowlist for {item.id}")
            if not re.fullmatch(r"szl-holdings/[A-Za-z0-9._-]+", source_repository):
                raise RuntimeError(f"canonical source repository is not public-allowlisted for {item.id}")
            live_url = base_url.rstrip("/") + "/"
            assets.append(
                PublicEstateAsset(
                    id=item.id,
                    title=item.title,
                    summary=item.summary,
                    kind=item.kind,
                    vertical=item.vertical,
                    public=True,
                    active=True,
                    source_url=f"https://github.com/{source_repository}",
                    live_url=live_url,
                    evidence_url=base_url.rstrip("/") + item.evidence_path,
                    visual_mode=item.visual_mode,
                    scenario_ids=list(item.scenario_ids),
                    tags=list(item.tags),
                    status_source=base_url.rstrip("/") + status_path,
                    data_state="SNAPSHOT",
                )
            )
        return projection, assets, source

    def check_rate(self, bucket: str, identity: str) -> None:
        limit = self.rate_limits[bucket]
        self.rate_limiter.check(
            f"{bucket}:{identity}", limit, float(self.monotonic_fn())
        )

    def health(self) -> HealthResponse:
        now = self._now()
        active_sessions, stored_receipts = self.store.status(now)
        session_capacity_remaining = max(
            0, self.store.max_sessions - active_sessions
        )
        receipt_capacity_remaining = max(
            0, self.store.max_receipts - stored_receipts
        )
        return HealthResponse(
            schema="a11oy.public-experience.health/v1",
            status=(
                "READY"
                if session_capacity_remaining and receipt_capacity_remaining
                else "DEGRADED"
            ),
            data_state="SIMULATION",
            external_authority_state="UNAVAILABLE",
            storage=StorageStatus(
                state="EPHEMERAL",
                persistence_across_restart=False,
                session_ttl_seconds=self.session_ttl_seconds,
                receipt_ttl_seconds=self.receipt_ttl_seconds,
                session_capacity_remaining=session_capacity_remaining,
                receipt_capacity_remaining=receipt_capacity_remaining,
                retention_policy="TTL_BOUNDED",
                active_sessions=active_sessions,
                stored_receipts=stored_receipts,
            ),
            limits={
                "max_request_bytes": MAX_REQUEST_BYTES,
                "max_verify_request_bytes": MAX_VERIFY_REQUEST_BYTES,
                "max_events_per_session": MAX_EVENTS_PER_SESSION,
                "max_sessions": self.store.max_sessions,
                "max_receipts": self.store.max_receipts,
                "rate_window_seconds": self.rate_limiter.window_seconds,
            },
            scenario_count=len(self.scenarios),
            estate_asset_count=len(self.estate_assets),
            endpoints=experience_routes(),
        )

    def estate(self) -> EstateResponse:
        return EstateResponse(
            schema="a11oy.public-experience.estate/v1",
            data_state="SNAPSHOT",
            source_schema="szl.public-estate/v1",
            source_repository=str(self.estate_source["source_repository"]),
            projection_version=self.estate_config.version,
            assets=copy.deepcopy(self.estate_assets),
        )

    def scenario_list(self) -> ScenarioListResponse:
        return ScenarioListResponse(
            schema="a11oy.public-experience.scenario-list/v1",
            data_state="SIMULATION",
            scenario_set_version=self.scenario_set.version,
            scenarios=copy.deepcopy(self.scenario_set.scenarios),
        )

    def _evidence_handles(self, scenario: ScenarioDefinition) -> list[EvidenceHandle]:
        handles: list[EvidenceHandle] = []
        for item in scenario.evidence:
            digest = _sha256(
                {
                    "scenario_id": scenario.id,
                    "scenario_version": scenario.version,
                    "evidence_id": item.id,
                    "title": item.title,
                    "source_class": item.source_class,
                    "uri": item.uri,
                }
            )
            handles.append(
                EvidenceHandle(
                    id=item.id,
                    title=item.title,
                    source_class=item.source_class,
                    uri=item.uri,
                    observed_at=None,
                    confidence=None,
                    digest=digest,
                )
            )
        return handles

    def _replay_info(self, scenario: ScenarioDefinition) -> ReplayInfo:
        evidence_ids = [item.id for item in scenario.evidence]
        simulation_digest = _sha256(
            {
                "scenario": scenario.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                ),
                "scenario_set_version": self.scenario_set.version,
                "policy_revision": self.scenario_set.policy_revision,
            }
        )
        return ReplayInfo(
            scenario_version=scenario.version,
            seed=scenario.seed,
            policy_revision=self.scenario_set.policy_revision,
            model_revision=scenario.model_revision,
            evidence_snapshot_ids=evidence_ids,
            simulation_digest=simulation_digest,
        )

    def _append_event_locked(
        self,
        record: SessionRecord,
        stage: ExperienceStage,
        *,
        evidence: list[EvidenceHandle] | None = None,
        policy_result: PolicyResult | None = None,
        approval_state: ApprovalState | None = None,
        effect_result: EffectResult | None = None,
        verification_result: VerificationResult | None = None,
        receipt_id: str | None = None,
    ) -> ExperienceEvent:
        if len(record.events) >= MAX_EVENTS_PER_SESSION:
            raise RuntimeError("public experience event cap reached")
        if not record.events:
            if stage is not ExperienceStage.CREATED:
                raise RuntimeError("lifecycle must begin at CREATED")
            previous_hash = GENESIS_HASH
        else:
            current = record.events[-1].stage
            if stage not in LEGAL_TRANSITIONS[current]:
                raise RuntimeError(f"illegal experience transition: {current.value}->{stage.value}")
            previous_hash = record.events[-1].current_hash

        event = ExperienceEvent(
            schema=EVENT_SCHEMA,
            event_id=f"evt_{uuid.uuid4().hex}",
            session_id=record.session_id,
            sequence=len(record.events),
            stage=stage,
            scenario_id=record.scenario.id,
            scenario_version=record.scenario.version,
            domain=record.scenario.domain,
            action=record.scenario.action,
            data_state="SIMULATION",
            evidence=copy.deepcopy(evidence or []),
            policy_result=copy.deepcopy(policy_result),
            approval_state=copy.deepcopy(approval_state),
            effect_result=copy.deepcopy(effect_result),
            verification_result=copy.deepcopy(verification_result),
            receipt_id=receipt_id,
            previous_hash=previous_hash,
            current_hash=GENESIS_HASH,
            emitted_at=self._now(),
        )
        hash_input = event.model_dump(mode="json", by_alias=True, exclude_none=False)
        hash_input.pop("current_hash")
        event.current_hash = _sha256(hash_input)
        record.events.append(event)
        return event

    def _simulation_policy(self, scenario: ScenarioDefinition) -> PolicyResult:
        if scenario.outcome is ExperienceStage.POLICY_DENIED:
            decision = "DENY_SIMULATION"
            reasons = ["SIMULATION_POLICY_DENY", "EXTERNAL_AUTHORITY_UNAVAILABLE"]
        elif scenario.approval_required:
            decision = "REQUIRE_APPROVAL"
            reasons = ["SCOPED_SIMULATION_APPROVAL_REQUIRED", "EXTERNAL_AUTHORITY_UNAVAILABLE"]
        else:
            decision = "ALLOW_SIMULATION"
            reasons = ["BOUNDED_SIMULATION_ONLY", "EXTERNAL_AUTHORITY_UNAVAILABLE"]
        return PolicyResult(
            authority_state="UNAVAILABLE",
            authoritative=False,
            simulation_decision=decision,
            revision=self.scenario_set.policy_revision,
            reason_codes=reasons,
        )

    def _effect_result(self) -> EffectResult:
        return EffectResult(
            state="SIMULATED_NO_EXTERNAL_EFFECT",
            external_effector_state="UNAVAILABLE",
            detail="The public scenario changed only this ephemeral simulation session.",
        )

    def _verification_for_outcome(
        self, outcome: ExperienceStage
    ) -> VerificationResult:
        if outcome is ExperienceStage.RECEIPTED:
            return VerificationResult(
                state="SIMULATION_VERIFIED",
                authoritative=False,
                detail="Deterministic simulation checks matched the configured replay outcome.",
            )
        if outcome is ExperienceStage.VERIFICATION_FAILED:
            return VerificationResult(
                state="VERIFICATION_FAILED",
                authoritative=False,
                detail="The configured simulation intentionally failed its consistency check.",
            )
        if outcome is ExperienceStage.RECOVERY_REQUIRED:
            return VerificationResult(
                state="RECOVERY_REQUIRED",
                authoritative=False,
                detail="The configured simulation requires recovery because evidence is incomplete.",
            )
        if outcome is ExperienceStage.UNAVAILABLE:
            return VerificationResult(
                state="UNAVAILABLE",
                authoritative=False,
                detail="The external authority is unavailable; no result was invented.",
            )
        return VerificationResult(
            state="NOT_RUN",
            authoritative=False,
            detail="Execution verification did not run because policy denied the simulation.",
        )

    def _issue_capability_locked(
        self, record: SessionRecord
    ) -> ApprovalCapability:
        now = self._now()
        expires_at = min(
            record.expires_at, now + timedelta(seconds=self.capability_ttl_seconds)
        )
        issued_sequence = len(record.events)
        nonce = secrets.token_urlsafe(32)
        identity = {
            "session_id": record.session_id,
            "scenario_id": record.scenario.id,
            "action": record.scenario.action,
            "scenario_version": record.scenario.version,
            "scope": record.scenario.approval_scope,
            "nonce": nonce,
            "issued_sequence": issued_sequence,
            "expires_at": expires_at,
        }
        capability_id = "expcap:" + _sha256(identity)[:24]
        binding = ApprovalCapabilityPayload(
            capability_id=capability_id,
            **identity,
        )
        token = self._encode_capability(binding)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        record.approval_binding = binding
        record.approval_token_hash = token_hash
        record.approval_state = ApprovalState(
            state="REQUIRED",
            scope=binding.scope,
            capability_id=capability_id,
            expires_at=expires_at,
            issued_sequence=issued_sequence,
            token_sha256=token_hash,
        )
        self._append_event_locked(
            record,
            ExperienceStage.APPROVAL_REQUIRED,
            approval_state=record.approval_state,
        )
        return ApprovalCapability(
            token=token,
            capability_id=capability_id,
            scope=binding.scope,
            issued_sequence=issued_sequence,
            expires_at=expires_at,
        )

    @staticmethod
    def _encode_capability(binding: ApprovalCapabilityPayload) -> str:
        return "expcap1." + _b64url_encode(_canonical(binding))

    def _recover_capability_locked(
        self, record: SessionRecord, now: datetime
    ) -> ApprovalCapability | None:
        if (
            record.stage is not ExperienceStage.APPROVAL_REQUIRED
            or record.approval_consumed
        ):
            return None
        binding = record.approval_binding
        token_hash = record.approval_token_hash
        if binding is None or token_hash is None:
            raise ExperienceAPIError(
                503,
                "APPROVAL_CAPABILITY_UNAVAILABLE",
                "The pending approval capability state is incomplete and failed closed.",
            )
        if binding.expires_at <= now:
            raise ExperienceAPIError(
                410,
                "APPROVAL_CAPABILITY_EXPIRED",
                "The scoped approval capability expired; use a new idempotency key after this session expires.",
            )
        token = self._encode_capability(binding)
        recovered_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(recovered_hash, token_hash):
            raise ExperienceAPIError(
                503,
                "APPROVAL_CAPABILITY_UNAVAILABLE",
                "The pending approval capability failed its integrity check.",
            )
        return ApprovalCapability(
            token=token,
            capability_id=binding.capability_id,
            scope=binding.scope,
            issued_sequence=binding.issued_sequence,
            expires_at=binding.expires_at,
        )

    def _unsigned_envelope(self, statement: dict[str, Any]) -> dict[str, Any]:
        return {
            "payloadType": RECEIPT_PAYLOAD_TYPE,
            "payload": base64.b64encode(_canonical(statement)).decode("ascii"),
            "signatures": [],
            "signed": False,
            "honesty": (
                "UNSIGNED simulation receipt; content integrity is recomputable, "
                "and no signing authority is implied."
            ),
        }

    @staticmethod
    def _verifier_passed(result: Any) -> bool:
        if result is True:
            return True
        if not isinstance(result, Mapping):
            return False
        # Transport success is not a signature verdict. Explicit signature
        # failures take precedence over a broad outer success field.
        if "signature_valid" in result:
            return result["signature_valid"] is True
        signature = result.get("signature")
        if isinstance(signature, Mapping):
            verdicts = [
                signature[key]
                for key in ("valid", "verified")
                if key in signature
            ]
            return bool(verdicts) and all(value is True for value in verdicts)
        checks = result.get("checks")
        if isinstance(checks, list):
            signature_checks = [
                check for check in checks
                if isinstance(check, Mapping) and check.get("check") == "signature"
            ]
            return bool(signature_checks) and all(
                check.get("status") in ("VERIFIED", "PASS")
                for check in signature_checks
            )
        return False

    @staticmethod
    def _verified_signer_state(identity: Mapping[str, Any]) -> str:
        scope = str(identity.get("key_scope") or "")
        if scope == "DEPLOYMENT_PERSISTENT":
            return "VERIFIED_PERSISTENT"
        if scope == "PROCESS_BOOT_EPHEMERAL":
            return "VERIFIED_EPHEMERAL"
        return "VERIFIED_SIGNATURE"

    @classmethod
    def _inspect_envelope(
        cls,
        envelope: Mapping[str, Any],
        statement: Mapping[str, Any],
        *,
        require_signed_identity: bool,
    ) -> tuple[bool, bool, bool, dict[str, Any] | None]:
        payload_type = envelope.get("payloadType")
        payload_type_ok = (
            isinstance(payload_type, str)
            and payload_type in EXPECTED_RECEIPT_PAYLOAD_TYPES
        )
        decoded = cls._envelope_statement(envelope)
        if decoded is None:
            return False, payload_type_ok, False, None
        decoded = dict(decoded)
        identity_value = decoded.pop("_signing_identity", None)
        try:
            statement_ok = hmac.compare_digest(_canonical(decoded), _canonical(statement))
        except (TypeError, ValueError, UnicodeError, RecursionError):
            return False, payload_type_ok, False, None
        if identity_value is None:
            return statement_ok, payload_type_ok, not require_signed_identity, None
        if not isinstance(identity_value, dict):
            return statement_ok, payload_type_ok, False, None

        identity = copy.deepcopy(identity_value)
        scope = identity.get("key_scope")
        required_identity = {
            "keyid",
            "verify_key_url",
            "key_scope",
            "key_lifetime",
            "key_fingerprint_sha256",
        }
        identity_ok = (
            required_identity.issubset(identity)
            and isinstance(scope, str)
            and scope
            in {"DEPLOYMENT_PERSISTENT", "PROCESS_BOOT_EPHEMERAL", "UNAVAILABLE"}
        )
        for key in (
            "verify_key_url",
            "key_scope",
            "key_lifetime",
            "key_fingerprint_sha256",
        ):
            identity_ok = identity_ok and envelope.get(key) == identity.get(key)

        signatures = envelope.get("signatures")
        if require_signed_identity:
            identity_ok = (
                identity_ok
                and scope in {"DEPLOYMENT_PERSISTENT", "PROCESS_BOOT_EPHEMERAL"}
                and identity.get("verify_key_url") == "/api/a11oy/cosign.pub"
                and isinstance(identity.get("key_fingerprint_sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", identity["key_fingerprint_sha256"])
                and identity.get("key_lifetime") == {
                    "DEPLOYMENT_PERSISTENT": "UNTIL_SECRET_ROTATION",
                    "PROCESS_BOOT_EPHEMERAL": "UNTIL_PROCESS_RESTART",
                }.get(scope)
                and isinstance(signatures, list)
                and bool(signatures)
                and isinstance(identity.get("keyid"), str)
                and bool(identity["keyid"])
                and all(
                    isinstance(signature, Mapping)
                    and signature.get("keyid") == identity["keyid"]
                    for signature in signatures
                )
            )
        return statement_ok, payload_type_ok, bool(identity_ok), identity

    def _sign_statement(
        self, statement: dict[str, Any]
    ) -> tuple[dict[str, Any], str, str]:
        if self.sign_fn is None:
            return self._unsigned_envelope(statement), "UNSIGNED", "PARTIAL"
        try:
            envelope = self.sign_fn(copy.deepcopy(statement))
        except Exception:
            return self._unsigned_envelope(statement), "UNAVAILABLE", "PARTIAL"
        if not isinstance(envelope, dict):
            return self._unsigned_envelope(statement), "UNAVAILABLE", "PARTIAL"
        signatures = envelope.get("signatures")
        has_signatures = isinstance(signatures, list) and bool(signatures)
        statement_ok, payload_type_ok, identity_ok, identity = self._inspect_envelope(
            envelope,
            statement,
            require_signed_identity=has_signatures,
        )
        if not all((statement_ok, payload_type_ok, identity_ok)):
            return self._unsigned_envelope(statement), "UNAVAILABLE", "PARTIAL"
        if not has_signatures:
            state = (
                "UNAVAILABLE"
                if identity is not None and identity.get("key_scope") == "UNAVAILABLE"
                else "UNSIGNED"
            )
            return envelope, state, "PARTIAL"
        if self.verify_fn is None:
            return envelope, "SIGNED_UNVERIFIED", "PARTIAL"
        try:
            verified = self._verifier_passed(self.verify_fn(copy.deepcopy(envelope)))
        except Exception:
            verified = False
        if not verified:
            return envelope, "SIGNED_UNVERIFIED", "PARTIAL"
        if identity is None:
            return self._unsigned_envelope(statement), "UNAVAILABLE", "PARTIAL"
        state = self._verified_signer_state(identity)
        return envelope, state, "VERIFIED"

    @staticmethod
    def _receipt_digest_payload(receipt: ExperienceReceipt | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(receipt, BaseModel):
            payload = receipt.model_dump(mode="json", by_alias=True, exclude_none=False)
        else:
            payload = copy.deepcopy(dict(receipt))
        for key in (
            "receipt_digest",
            "current_hash",
            "chain_integrity",
            "signer_state",
            "verification_state",
            "envelope",
        ):
            payload.pop(key, None)
        return payload

    def _issue_receipt_locked(
        self, record: SessionRecord, receipt_id: str
    ) -> ExperienceReceipt:
        self._ensure_receipt_capacity_locked()
        evidence = self._evidence_handles(record.scenario)
        created_at = self._now()
        payload = {
            "schema": RECEIPT_SCHEMA,
            "receipt_id": receipt_id,
            "namespace": RECEIPT_NAMESPACE,
            "data_state": "SIMULATION",
            "session_id": record.session_id,
            "scenario_id": record.scenario.id,
            "scenario_version": record.scenario.version,
            "final_stage": record.stage,
            "created_at": created_at,
            "previous_hash": record.events[-1].current_hash,
            "effect_state": "SIMULATED_NO_EXTERNAL_EFFECT",
            "policy_result": copy.deepcopy(record.policy_result),
            "approval_result": copy.deepcopy(record.approval_state),
            "verification_result": copy.deepcopy(record.verification_result),
            "evidence": evidence,
            "replay": copy.deepcopy(record.replay),
            "events": copy.deepcopy(record.events),
            "limitations": [
                "SIMULATION only; no external effector was called.",
                "Receipt integrity does not prove real-world execution or correctness.",
                "This receipt is not part of an operational A11oy or Khipu chain.",
                "The in-memory receipt is unavailable after process restart.",
            ],
        }
        digest = _sha256(payload)
        statement = {**_jsonable(payload), "receipt_digest": digest}
        envelope, signer_state, verification_state = self._sign_statement(statement)
        receipt = ExperienceReceipt(
            **payload,
            receipt_digest=digest,
            current_hash=digest,
            chain_integrity="INTACT",
            signer_state=signer_state,
            verification_state=verification_state,
            envelope=envelope,
        )
        self.store.receipts[receipt_id] = copy.deepcopy(receipt)
        self.store.receipt_expiries[receipt_id] = created_at + timedelta(
            seconds=self.receipt_ttl_seconds
        )
        record.receipt_id = receipt_id
        return receipt

    def _ensure_receipt_capacity_locked(self) -> None:
        if len(self.store.receipts) >= self.store.max_receipts:
            raise ExperienceAPIError(
                503,
                "RECEIPT_CAPACITY_REACHED",
                "The bounded simulation receipt store is full.",
            )

    def _complete_execution_locked(self, record: SessionRecord) -> None:
        outcome = record.scenario.outcome
        record.effect_result = self._effect_result()
        self._append_event_locked(
            record,
            ExperienceStage.EXECUTING,
            effect_result=record.effect_result,
        )
        record.verification_result = self._verification_for_outcome(outcome)
        receipt_id = f"sim-experience:{uuid.uuid4().hex}"
        if outcome is ExperienceStage.RECEIPTED:
            self._append_event_locked(
                record,
                ExperienceStage.VERIFIED,
                verification_result=record.verification_result,
            )
            self._append_event_locked(
                record,
                ExperienceStage.RECEIPTED,
                verification_result=record.verification_result,
                receipt_id=receipt_id,
            )
        elif outcome in {
            ExperienceStage.VERIFICATION_FAILED,
            ExperienceStage.RECOVERY_REQUIRED,
            ExperienceStage.BLOCKED,
            ExperienceStage.UNAVAILABLE,
        }:
            self._append_event_locked(
                record,
                outcome,
                verification_result=record.verification_result,
                receipt_id=receipt_id,
            )
        else:
            raise RuntimeError("invalid post-execution scenario outcome")
        self._issue_receipt_locked(record, receipt_id)

    def _start_lifecycle_locked(
        self, record: SessionRecord
    ) -> ApprovalCapability | None:
        scenario = record.scenario
        evidence = self._evidence_handles(scenario)
        self._append_event_locked(record, ExperienceStage.CREATED)
        self._append_event_locked(record, ExperienceStage.PROPOSED)
        self._append_event_locked(
            record, ExperienceStage.EVIDENCE_BOUND, evidence=evidence
        )

        if scenario.outcome is ExperienceStage.UNAVAILABLE:
            record.verification_result = self._verification_for_outcome(
                ExperienceStage.UNAVAILABLE
            )
            receipt_id = f"sim-experience:{uuid.uuid4().hex}"
            self._append_event_locked(
                record,
                ExperienceStage.UNAVAILABLE,
                evidence=evidence,
                verification_result=record.verification_result,
                receipt_id=receipt_id,
            )
            self._issue_receipt_locked(record, receipt_id)
            return None

        self._append_event_locked(record, ExperienceStage.QUALIFIED, evidence=evidence)
        record.policy_result = self._simulation_policy(scenario)
        self._append_event_locked(
            record,
            ExperienceStage.POLICY_EVALUATED,
            policy_result=record.policy_result,
        )

        if scenario.outcome is ExperienceStage.POLICY_DENIED:
            record.verification_result = self._verification_for_outcome(
                ExperienceStage.POLICY_DENIED
            )
            receipt_id = f"sim-experience:{uuid.uuid4().hex}"
            self._append_event_locked(
                record,
                ExperienceStage.POLICY_DENIED,
                policy_result=record.policy_result,
                verification_result=record.verification_result,
                receipt_id=receipt_id,
            )
            self._issue_receipt_locked(record, receipt_id)
            return None

        if scenario.approval_required:
            return self._issue_capability_locked(record)

        record.approval_state = ApprovalState(state="NOT_REQUIRED")
        self._complete_execution_locked(record)
        return None

    def _approval_summary(self, record: SessionRecord) -> ApprovalSummary:
        state = record.approval_state
        return ApprovalSummary(
            required=record.scenario.approval_required,
            state=state.state,
            scope=state.scope,
            capability_id=state.capability_id,
            expires_at=state.expires_at,
            issued_sequence=state.issued_sequence,
        )

    def _session_response(
        self,
        record: SessionRecord,
        *,
        idempotent_replay: bool,
        capability: ApprovalCapability | None,
    ) -> SessionResponse:
        return SessionResponse(
            schema=SESSION_SCHEMA,
            session_id=record.session_id,
            scenario_id=record.scenario.id,
            scenario_version=record.scenario.version,
            domain=record.scenario.domain,
            action=record.scenario.action,
            data_state="SIMULATION",
            stage=record.stage,
            terminal=record.terminal,
            created_at=record.created_at,
            expires_at=record.expires_at,
            next_sequence=len(record.events),
            events_url=f"{API_PREFIX}/sessions/{record.session_id}/events",
            approval=self._approval_summary(record),
            replay=copy.deepcopy(record.replay),
            receipt_id=record.receipt_id,
            idempotent_replay=idempotent_replay,
            approval_capability=copy.deepcopy(capability),
        )

    @staticmethod
    def _idempotency_scope(origin: str, key: str) -> str:
        return hashlib.sha256(f"{origin}\0{key}".encode("utf-8")).hexdigest()

    def create_session(
        self,
        request: CreateSessionRequest,
        *,
        idempotency_key: str | None,
        origin: str,
    ) -> tuple[SessionResponse, bool]:
        scenario = self.scenarios.get(request.scenario_id)
        if scenario is None:
            raise ExperienceAPIError(
                404,
                "SCENARIO_NOT_FOUND",
                "The requested scenario is not in the public allowlist.",
            )
        request_digest = _sha256({"scenario_id": request.scenario_id})
        now = self._now()
        with self.store.lock:
            self.store.purge_expired_on_write(now)
            scope_key = None
            if idempotency_key is not None:
                scope_key = self._idempotency_scope(origin, idempotency_key)
                existing = self.store.idempotency.get(scope_key)
                if existing is not None:
                    if existing.request_digest != request_digest:
                        raise ExperienceAPIError(
                            409,
                            "IDEMPOTENCY_CONFLICT",
                            "The idempotency key is already bound to a different request.",
                        )
                    record = self.store.sessions.get(existing.session_id)
                    if record is None or record.expires_at <= now:
                        raise ExperienceAPIError(
                            410,
                            "IDEMPOTENCY_EXPIRED",
                            "The idempotent session has expired; use a new key.",
                        )
                    capability = self._recover_capability_locked(record, now)
                    return (
                        self._session_response(
                            record,
                            idempotent_replay=True,
                            capability=capability,
                        ),
                        False,
                    )

            if len(self.store.sessions) >= self.store.max_sessions:
                raise ExperienceAPIError(
                    503,
                    "SESSION_CAPACITY_REACHED",
                    "The bounded simulation session store is full.",
                )
            if not scenario.approval_required:
                self._ensure_receipt_capacity_locked()
            session_id = f"exp_{uuid.uuid4().hex}"
            record = SessionRecord(
                session_id=session_id,
                scenario=copy.deepcopy(scenario),
                created_at=now,
                expires_at=now + timedelta(seconds=self.session_ttl_seconds),
                replay=self._replay_info(scenario),
            )
            self.store.sessions[session_id] = record
            receipts_before = set(self.store.receipts)
            try:
                capability = self._start_lifecycle_locked(record)
                response = self._session_response(
                    record,
                    idempotent_replay=False,
                    capability=capability,
                )
            except Exception:
                self.store.sessions.pop(session_id, None)
                for added_receipt_id in set(self.store.receipts) - receipts_before:
                    self.store.receipts.pop(added_receipt_id, None)
                    self.store.receipt_expiries.pop(added_receipt_id, None)
                raise
            if scope_key is not None:
                self.store.idempotency[scope_key] = IdempotencyRecord(
                    request_digest=request_digest,
                    session_id=session_id,
                    expires_at=record.expires_at,
                )
            return response, True

    def _record(self, session_id: str) -> SessionRecord:
        if not re.fullmatch(r"exp_[0-9a-f]{32}", session_id):
            raise ExperienceAPIError(404, "SESSION_NOT_FOUND", "Session not found.")
        now = self._now()
        with self.store.lock:
            record = self.store.sessions.get(session_id)
            if record is None:
                raise ExperienceAPIError(404, "SESSION_NOT_FOUND", "Session not found.")
            if record.expires_at <= now:
                raise ExperienceAPIError(410, "SESSION_EXPIRED", "The simulation session expired.")
            return record

    def get_session(self, session_id: str) -> SessionResponse:
        with self.store.lock:
            record = self._record(session_id)
            return self._session_response(
                record, idempotent_replay=False, capability=None
            )

    def event_snapshot(
        self, session_id: str, after: int
    ) -> tuple[list[ExperienceEvent], SessionResponse]:
        with self.store.lock:
            record = self._record(session_id)
            events = [
                copy.deepcopy(event)
                for event in record.events
                if event.sequence > after
            ]
            view = self._session_response(
                record, idempotent_replay=False, capability=None
            )
            return events, view

    @staticmethod
    def _decode_capability(token: str) -> ApprovalCapabilityPayload:
        try:
            prefix, encoded = token.split(".", 1)
            if prefix != "expcap1":
                raise ValueError("wrong capability prefix")
            payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
            return ApprovalCapabilityPayload.model_validate(payload)
        except Exception as exc:
            raise ExperienceAPIError(
                403,
                "INVALID_APPROVAL_CAPABILITY",
                "The approval capability is malformed or invalid.",
            ) from exc

    def approve_session(
        self, session_id: str, request: ApproveSessionRequest
    ) -> SessionResponse:
        now = self._now()
        with self.store.lock:
            record = self._record(session_id)
            self.store.purge_expired_on_write(now)
            if record.stage is not ExperienceStage.APPROVAL_REQUIRED:
                raise ExperienceAPIError(
                    409,
                    "APPROVAL_NOT_AVAILABLE",
                    "This session is not awaiting approval.",
                )
            if record.approval_consumed:
                raise ExperienceAPIError(
                    409,
                    "APPROVAL_ALREADY_CONSUMED",
                    "The approval capability has already been consumed.",
                )
            binding = self._decode_capability(request.capability_token)
            expected = record.approval_binding
            token_hash = hashlib.sha256(
                request.capability_token.encode("utf-8")
            ).hexdigest()
            if (
                expected is None
                or record.approval_token_hash is None
                or not hmac.compare_digest(token_hash, record.approval_token_hash)
                or binding.model_dump(mode="json")
                != expected.model_dump(mode="json")
                or binding.session_id != record.session_id
                or binding.scenario_id != record.scenario.id
                or binding.action != record.scenario.action
                or binding.scenario_version != record.scenario.version
                or binding.scope != record.scenario.approval_scope
                or request.scope != binding.scope
                or request.expected_sequence != binding.issued_sequence
                or record.events[-1].sequence != binding.issued_sequence
            ):
                raise ExperienceAPIError(
                    403,
                    "APPROVAL_CAPABILITY_MISMATCH",
                    "The approval capability does not match this exact session transition.",
                )
            if binding.expires_at <= now or record.expires_at <= now:
                raise ExperienceAPIError(
                    410,
                    "APPROVAL_CAPABILITY_EXPIRED",
                    "The scoped approval capability expired.",
                )
            self._ensure_receipt_capacity_locked()

            before = copy.deepcopy(record)
            receipts_before = set(self.store.receipts)
            try:
                record.approval_consumed = True
                record.approval_state = ApprovalState(
                    state="APPROVED",
                    scope=binding.scope,
                    capability_id=binding.capability_id,
                    expires_at=binding.expires_at,
                    issued_sequence=binding.issued_sequence,
                    token_sha256=record.approval_token_hash,
                )
                self._append_event_locked(
                    record,
                    ExperienceStage.APPROVED,
                    approval_state=record.approval_state,
                )
                self._complete_execution_locked(record)
                response = self._session_response(
                    record, idempotent_replay=False, capability=None
                )
            except Exception:
                self.store.sessions[session_id] = before
                for added_receipt_id in set(self.store.receipts) - receipts_before:
                    self.store.receipts.pop(added_receipt_id, None)
                    self.store.receipt_expiries.pop(added_receipt_id, None)
                raise
            return response

    def get_receipt(self, receipt_id: str) -> ExperienceReceipt:
        if not re.fullmatch(r"sim-experience:[0-9a-f]{32}", receipt_id):
            raise ExperienceAPIError(404, "RECEIPT_NOT_FOUND", "Receipt not found.")
        with self.store.lock:
            receipt = self.store.receipts.get(receipt_id)
            if receipt is None:
                raise ExperienceAPIError(404, "RECEIPT_NOT_FOUND", "Receipt not found.")
            expires_at = self.store.receipt_expiries.get(receipt_id)
            if expires_at is None:
                raise ExperienceAPIError(
                    503,
                    "RECEIPT_RETENTION_UNKNOWN",
                    "Receipt retention metadata is unavailable.",
                )
            if expires_at <= self._now():
                raise ExperienceAPIError(
                    410,
                    "RECEIPT_EXPIRED",
                    "The ephemeral simulation receipt retention window expired.",
                )
            return copy.deepcopy(receipt)

    @staticmethod
    def _verify_event_chain(events: list[ExperienceEvent]) -> bool:
        previous = GENESIS_HASH
        for expected_sequence, event in enumerate(events):
            if event.sequence != expected_sequence or event.previous_hash != previous:
                return False
            payload = event.model_dump(mode="json", by_alias=True, exclude_none=False)
            claimed = payload.pop("current_hash")
            if not hmac.compare_digest(_sha256(payload), claimed):
                return False
            previous = event.current_hash
        return bool(events)

    @staticmethod
    def _envelope_statement(envelope: Mapping[str, Any]) -> dict[str, Any] | None:
        payload = envelope.get("payload")
        if not isinstance(payload, str):
            return None
        try:
            decoded = base64.b64decode(payload, validate=True)
            value = json.loads(decoded.decode("utf-8"))
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def verify_receipt(
        self, stored_id: str, supplied: ExperienceReceipt | None = None
    ) -> VerifyReceiptResponse:
        stored = self.get_receipt(stored_id)
        candidate = copy.deepcopy(supplied or stored)
        if candidate.receipt_id != stored_id:
            raise ExperienceAPIError(
                409,
                "RECEIPT_ID_MISMATCH",
                "The supplied receipt does not match the receipt path.",
            )

        stored_binding_ok = hmac.compare_digest(
            _canonical(candidate), _canonical(stored)
        )

        digest_payload = self._receipt_digest_payload(candidate)
        expected_digest = _sha256(digest_payload)
        digest_ok = (
            hmac.compare_digest(candidate.receipt_digest, expected_digest)
            and hmac.compare_digest(candidate.current_hash, expected_digest)
        )
        event_chain_ok = self._verify_event_chain(candidate.events)
        previous_ok = bool(candidate.events) and hmac.compare_digest(
            candidate.previous_hash, candidate.events[-1].current_hash
        )
        namespace_ok = (
            candidate.namespace == RECEIPT_NAMESPACE
            and candidate.data_state == "SIMULATION"
            and candidate.effect_state == "SIMULATED_NO_EXTERNAL_EFFECT"
        )

        statement = {**_jsonable(digest_payload), "receipt_digest": expected_digest}
        signatures = candidate.envelope.get("signatures")
        has_signatures = isinstance(signatures, list) and bool(signatures)
        (
            envelope_binding_ok,
            payload_type_ok,
            signed_identity_ok,
            signed_identity,
        ) = self._inspect_envelope(
            candidate.envelope,
            statement,
            require_signed_identity=has_signatures,
        )
        signature_status = "UNSIGNED"
        expected_signer_state = "UNSIGNED"
        signature_ok = True
        if has_signatures:
            if not all((stored_binding_ok, envelope_binding_ok, payload_type_ok, signed_identity_ok)):
                signature_ok = False
                signature_status = "NOT_RUN_INVALID_BINDING"
                expected_signer_state = "SIGNED_UNVERIFIED"
            elif self.verify_fn is None:
                signature_status = "UNAVAILABLE"
                expected_signer_state = "SIGNED_UNVERIFIED"
            else:
                try:
                    signature_ok = self._verifier_passed(
                        self.verify_fn(copy.deepcopy(candidate.envelope))
                    )
                except Exception:
                    signature_ok = False
                if signature_ok:
                    signature_status = "VERIFIED"
                    expected_signer_state = (
                        self._verified_signer_state(signed_identity)
                        if signed_identity is not None
                        else "SIGNED_UNVERIFIED"
                    )
                else:
                    signature_status = "FAILED"
                    expected_signer_state = "SIGNED_UNVERIFIED"
        elif candidate.signer_state == "UNAVAILABLE":
            signature_status = "UNAVAILABLE"
            expected_signer_state = "UNAVAILABLE"

        signer_consistent = candidate.signer_state == expected_signer_state
        core_ok = all(
            (
                digest_ok,
                event_chain_ok,
                previous_ok,
                namespace_ok,
                stored_binding_ok,
                envelope_binding_ok,
                payload_type_ok,
                signed_identity_ok,
                signer_consistent,
                signature_ok,
            )
        )
        if not core_ok:
            verification_state = "FAILED"
        elif signature_status != "VERIFIED":
            verification_state = "PARTIAL"
        else:
            verification_state = "VERIFIED"
        return VerifyReceiptResponse(
            schema=VERIFY_SCHEMA,
            receipt_id=stored_id,
            ok=core_ok,
            chain_integrity="INTACT" if event_chain_ok and previous_ok else "FAILED",
            signer_state=candidate.signer_state,
            effect_state=candidate.effect_state,
            verification_state=verification_state,
            checks={
                "receipt_digest": "VERIFIED" if digest_ok else "FAILED",
                "event_chain": "VERIFIED" if event_chain_ok and previous_ok else "FAILED",
                "namespace": "VERIFIED" if namespace_ok else "FAILED",
                "stored_receipt": "VERIFIED" if stored_binding_ok else "FAILED",
                "envelope_binding": "VERIFIED" if envelope_binding_ok else "FAILED",
                "payload_type": "VERIFIED" if payload_type_ok else "FAILED",
                "signed_identity": "VERIFIED" if signed_identity_ok else "FAILED",
                "signature": signature_status,
                "signer_state_consistency": "VERIFIED" if signer_consistent else "FAILED",
                "effect": "SIMULATED_NO_EXTERNAL_EFFECT",
            },
        )


def experience_routes() -> list[str]:
    return list(_experience_route_contract())


def _experience_route_contract() -> dict[str, frozenset[str]]:
    return {
        f"{API_PREFIX}/health": frozenset({"GET"}),
        f"{API_PREFIX}/estate": frozenset({"GET"}),
        f"{API_PREFIX}/scenarios": frozenset({"GET"}),
        f"{API_PREFIX}/sessions": frozenset({"POST"}),
        f"{API_PREFIX}/sessions/{{session_id}}": frozenset({"GET"}),
        f"{API_PREFIX}/sessions/{{session_id}}/events": frozenset({"GET"}),
        f"{API_PREFIX}/sessions/{{session_id}}/approve": frozenset({"POST"}),
        f"{API_PREFIX}/receipts/{{receipt_id}}": frozenset({"GET"}),
        f"{API_PREFIX}/receipts/{{receipt_id}}/verify": frozenset({"POST"}),
    }


def _client_identity(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:24]


def _expected_origin(request: Request) -> str:
    host = (request.headers.get("host") or "").strip().lower()
    if not host or any(char in host for char in ("/", "\\", "@", "#", "?")):
        raise HTTPException(
            status_code=403,
            detail={"code": "INVALID_HOST", "message": "A valid Host header is required."},
        )
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    scheme = forwarded or request.url.scheme.lower()
    if scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=403,
            detail={"code": "INVALID_ORIGIN", "message": "Unsupported request origin scheme."},
        )
    return f"{scheme}://{host}"


def _require_same_origin(request: Request) -> str:
    fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if fetch_site and fetch_site not in {"same-origin", "none"}:
        raise HTTPException(
            status_code=403,
            detail={"code": "CROSS_ORIGIN_DENIED", "message": "Cross-origin POST is denied."},
        )
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        raise HTTPException(
            status_code=403,
            detail={"code": "ORIGIN_REQUIRED", "message": "State-changing POST requires Origin."},
        )
    parsed = urlsplit(origin)
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or normalized != _expected_origin(request)
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "CROSS_ORIGIN_DENIED", "message": "POST origin does not match this host."},
        )
    return normalized


def _validate_idempotency_key(request: Request) -> str | None:
    values = request.headers.getlist("idempotency-key")
    if len(values) > 1:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_IDEMPOTENCY_KEY", "message": "Supply Idempotency-Key at most once."},
        )
    if not values:
        return None
    value = values[0].strip()
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_IDEMPOTENCY_KEY",
                "message": (
                    "Idempotency-Key must be an unguessable canonical lowercase UUIDv4 "
                    "and is treated as replay capability material."
                ),
            },
        )
    return value


async def _bounded_model(
    request: Request,
    model_type: type[StrictModel],
    *,
    allow_empty: bool = False,
    max_bytes: int = MAX_REQUEST_BYTES,
) -> StrictModel:
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(
            status_code=415,
            detail={"code": "JSON_REQUIRED", "message": "Content-Type must be application/json."},
        )
    declared = request.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_CONTENT_LENGTH", "message": "Content-Length must be an integer."},
            ) from exc
        if declared_size < 0 or declared_size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={"code": "REQUEST_TOO_LARGE", "message": f"Request exceeds {max_bytes} bytes."},
            )
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={"code": "REQUEST_TOO_LARGE", "message": f"Request exceeds {max_bytes} bytes."},
            )
        if chunk:
            chunks.append(chunk)
    body = b"".join(chunks)
    if not body and allow_empty:
        value: Any = {}
    else:
        try:
            value = json.loads(body.decode("utf-8"))
            _canonical(value)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_JSON", "message": "Request must be UTF-8 JSON."},
            ) from exc
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=422,
            detail={"code": "OBJECT_REQUIRED", "message": "Request body must be one JSON object."},
        )
    try:
        return model_type.model_validate(value)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "errors": _safe_validation_errors(exc)},
        ) from exc


def _event_cursor(request: Request) -> int:
    header_values = request.headers.getlist("last-event-id")
    query_values = request.query_params.getlist("after")
    if len(header_values) > 1 or len(query_values) > 1:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_EVENT_CURSOR", "message": "Event cursor must be supplied at most once."},
        )
    raw = header_values[0] if header_values else (query_values[0] if query_values else "-1")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_EVENT_CURSOR", "message": "Event cursor must be an integer."},
        ) from exc
    if value < -1 or value > MAX_SSE_AFTER:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_EVENT_CURSOR", "message": "Event cursor is outside the supported range."},
        )
    return value


def _raise_service_error(exc: ExperienceAPIError) -> None:
    headers = {"Retry-After": str(RATE_WINDOW_SECONDS)} if exc.status_code == 429 else None
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.detail},
        headers=headers,
    ) from exc


def _json_response(model: BaseModel, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        model.model_dump(mode="json", by_alias=True, exclude_none=False),
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


def register(
    app: FastAPI,
    ns: str = "a11oy",
    *,
    service: PublicExperienceService | None = None,
    root: Path | None = None,
    config_dir: Path | None = None,
    sign_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    verify_fn: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Register all nine public-experience routes and front-move exact matches."""

    del ns  # The public contract intentionally uses one stable, non-duplicated prefix.
    health_path = f"{API_PREFIX}/health"
    route_contract = _experience_route_contract()
    relevant = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in route_contract
    ]
    if relevant:
        complete = len(relevant) == len(route_contract)
        for route in relevant:
            path = str(getattr(route, "path", ""))
            methods = frozenset(getattr(route, "methods", set()) or set())
            endpoint = getattr(route, "endpoint", None)
            complete = complete and methods == route_contract[path]
            complete = complete and (
                getattr(endpoint, "__a11oy_public_experience_owner__", None)
                == ROUTE_OWNER
            )
        if complete and {getattr(route, "path", None) for route in relevant} == set(
            route_contract
        ):
            return {"ok": True, "state": "ALREADY_REGISTERED", "routes": []}
        raise RuntimeError(
            "public experience route contract is partial, duplicated, or owned by another surface"
        )

    if service is None:
        state_signer = getattr(app.state, "szl_sign_receipt", None)
        state_verifier = getattr(app.state, "szl_verify_receipt", None)
        service = PublicExperienceService(
            root=root,
            config_dir=config_dir,
            sign_fn=sign_fn if sign_fn is not None else state_signer,
            verify_fn=verify_fn if verify_fn is not None else state_verifier,
        )

    def rate(request: Request, bucket: str) -> None:
        try:
            service.check_rate(bucket, _client_identity(request))
        except ExperienceAPIError as exc:
            _raise_service_error(exc)

    async def health(request: Request) -> JSONResponse:
        rate(request, "read")
        return _json_response(service.health())

    async def estate(request: Request) -> JSONResponse:
        rate(request, "read")
        return _json_response(service.estate())

    async def scenarios(request: Request) -> JSONResponse:
        rate(request, "read")
        return _json_response(service.scenario_list())

    async def create_session(request: Request) -> JSONResponse:
        rate(request, "create")
        origin = _require_same_origin(request)
        idempotency_key = _validate_idempotency_key(request)
        model = await _bounded_model(request, CreateSessionRequest)
        try:
            response, created = service.create_session(
                model,
                idempotency_key=idempotency_key,
                origin=origin,
            )
        except ExperienceAPIError as exc:
            _raise_service_error(exc)
        return _json_response(response, status_code=201 if created else 200)

    async def get_session(request: Request) -> JSONResponse:
        rate(request, "read")
        try:
            response = service.get_session(str(request.path_params["session_id"]))
        except ExperienceAPIError as exc:
            _raise_service_error(exc)
        return _json_response(response)

    async def events(request: Request) -> StreamingResponse:
        rate(request, "events")
        after = _event_cursor(request)
        try:
            values, view = service.event_snapshot(
                str(request.path_params["session_id"]), after
            )
        except ExperienceAPIError as exc:
            _raise_service_error(exc)

        async def generate():
            for event in values:
                if await request.is_disconnected():
                    return
                data = json.dumps(
                    event.model_dump(mode="json", by_alias=True, exclude_none=False),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                yield f"id: {event.sequence}\nevent: experience\ndata: {data}\n\n".encode("utf-8")
            end = {
                "session_id": view.session_id,
                "next_sequence": view.next_sequence,
                "stage": view.stage.value,
                "terminal": view.terminal,
                "receipt_id": view.receipt_id,
            }
            yield (
                "event: end\ndata: "
                + json.dumps(end, sort_keys=True, separators=(",", ":"))
                + "\n\n"
            ).encode("utf-8")

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def approve(request: Request) -> JSONResponse:
        rate(request, "approve")
        _require_same_origin(request)
        model = await _bounded_model(request, ApproveSessionRequest)
        try:
            response = service.approve_session(
                str(request.path_params["session_id"]), model
            )
        except ExperienceAPIError as exc:
            _raise_service_error(exc)
        return _json_response(response)

    async def receipt(request: Request) -> JSONResponse:
        rate(request, "read")
        try:
            response = service.get_receipt(str(request.path_params["receipt_id"]))
        except ExperienceAPIError as exc:
            _raise_service_error(exc)
        return _json_response(response)

    async def verify(request: Request) -> JSONResponse:
        rate(request, "verify")
        _require_same_origin(request)
        model = await _bounded_model(
            request,
            VerifyReceiptRequest,
            allow_empty=True,
            max_bytes=MAX_VERIFY_REQUEST_BYTES,
        )
        try:
            response = service.verify_receipt(
                str(request.path_params["receipt_id"]), model.receipt
            )
        except ExperienceAPIError as exc:
            _raise_service_error(exc)
        return _json_response(response)

    routes: list[tuple[str, Callable[..., Any], list[str]]] = [
        (health_path, health, ["GET"]),
        (f"{API_PREFIX}/estate", estate, ["GET"]),
        (f"{API_PREFIX}/scenarios", scenarios, ["GET"]),
        (f"{API_PREFIX}/sessions", create_session, ["POST"]),
        (f"{API_PREFIX}/sessions/{{session_id}}", get_session, ["GET"]),
        (f"{API_PREFIX}/sessions/{{session_id}}/events", events, ["GET"]),
        (f"{API_PREFIX}/sessions/{{session_id}}/approve", approve, ["POST"]),
        (f"{API_PREFIX}/receipts/{{receipt_id}}", receipt, ["GET"]),
        (f"{API_PREFIX}/receipts/{{receipt_id}}/verify", verify, ["POST"]),
    ]
    added: list[str] = []
    for path, endpoint, methods in routes:
        setattr(endpoint, "__a11oy_public_experience_owner__", ROUTE_OWNER)
        app.add_api_route(
            path,
            endpoint,
            methods=methods,
            include_in_schema=False,
        )
        added.append(path)

    route_set = set(added)
    selected = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in route_set
        and getattr(
            getattr(route, "endpoint", None),
            "__a11oy_public_experience_owner__",
            None,
        )
        == ROUTE_OWNER
    ]
    selected_ids = {id(route) for route in selected}
    app.router.routes[:] = selected + [
        route for route in app.router.routes if id(route) not in selected_ids
    ]
    app.state.a11oy_public_experience_service = service
    return {
        "ok": True,
        "state": "REGISTERED",
        "data_state": "SIMULATION",
        "external_authority_state": "UNAVAILABLE",
        "routes": added,
        "storage": "EPHEMERAL",
    }


__all__ = [
    "API_PREFIX",
    "DataState",
    "ExperienceEvent",
    "ExperienceReceipt",
    "ExperienceStage",
    "EXPECTED_SCENARIO_IDS",
    "LEGAL_TRANSITIONS",
    "PublicExperienceService",
    "TERMINAL_STAGES",
    "experience_routes",
    "register",
]
