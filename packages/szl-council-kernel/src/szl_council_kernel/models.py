from __future__ import annotations

"""Strict protocol records used by the deterministic Council Kernel."""

import math
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping, Sequence, TypeVar

from .canonical import (
    digest_object,
    isoformat_utc,
    parse_utc,
    require_digest,
    require_identifier,
)
from .enums import (
    ActionKind,
    AutonomyLevel,
    BlastRadius,
    CouncilRole,
    CouncilState,
    CouncilVote,
    EvidenceTier,
    ReleaseDecision,
    RiskClass,
    WorkflowState,
)
from .errors import ValidationError

E = TypeVar("E")


def _enum(enum_type: type[E], value: E | str, field_name: str) -> E:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)  # type: ignore[call-arg]
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)  # type: ignore[attr-defined]
        raise ValidationError(f"{field_name} must be one of: {allowed}") from exc


def _bounded_strings(
    values: Iterable[str],
    *,
    field_name: str,
    minimum: int = 0,
    maximum: int = 256,
    item_maximum: int = 2048,
    unique: bool = True,
) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value or len(value) > item_maximum:
            raise ValidationError(f"{field_name} contains an invalid string")
        result.append(value)
    if len(result) < minimum or len(result) > maximum:
        raise ValidationError(f"{field_name} must contain between {minimum} and {maximum} items")
    if unique and len(set(result)) != len(result):
        raise ValidationError(f"{field_name} must not contain duplicates")
    return tuple(result)


def _number(value: Any, *, field_name: str, minimum: float = 0, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError(f"{field_name} must be finite")
    if result < minimum or (maximum is not None and result > maximum):
        raise ValidationError(f"{field_name} is outside its allowed range")
    return result


def _integer(value: Any, *, field_name: str, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValidationError(f"{field_name} is outside its allowed range")
    return value


def _boolean(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a boolean")
    return value


def _require_schema(value: Any, expected: str) -> None:
    if value != expected:
        raise ValidationError(f"schema must be exactly {expected}")


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    max_cost_usd: float = 0.0
    max_duration_seconds: int = 300
    max_tool_calls: int = 8
    max_mutations: int = 1
    max_branches: int = 4
    max_recursion: int = 2

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_cost_usd", _number(self.max_cost_usd, field_name="max_cost_usd", maximum=1_000_000_000))
        for name, maximum in (
            ("max_duration_seconds", 31_536_000),
            ("max_tool_calls", 100_000),
            ("max_mutations", 100_000),
            ("max_branches", 10_000),
            ("max_recursion", 1_000),
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), field_name=name, maximum=maximum))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "BudgetLimits":
        return cls(**dict(value or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_subset_of(self, parent: "BudgetLimits") -> bool:
        return all(getattr(self, name) <= getattr(parent, name) for name in asdict(self))


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    cost_usd: float = 0.0
    duration_seconds: int = 0
    tool_calls: int = 0
    mutations: int = 0
    branches: int = 0
    recursion: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "cost_usd", _number(self.cost_usd, field_name="cost_usd", maximum=1_000_000_000))
        for name in ("duration_seconds", "tool_calls", "mutations", "branches", "recursion"):
            object.__setattr__(self, name, _integer(getattr(self, name), field_name=name, maximum=1_000_000_000))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def within(self, limits: BudgetLimits) -> bool:
        mapping = {
            "cost_usd": "max_cost_usd",
            "duration_seconds": "max_duration_seconds",
            "tool_calls": "max_tool_calls",
            "mutations": "max_mutations",
            "branches": "max_branches",
            "recursion": "max_recursion",
        }
        return all(getattr(self, usage) <= getattr(limits, limit) for usage, limit in mapping.items())


@dataclass(frozen=True, slots=True)
class EpochBinding:
    model: str
    tool: str
    policy: str
    evidence: str
    state: str
    retrieval: str
    prompt: str = "prompt:none"
    tokenizer: str = "tokenizer:none"

    def __post_init__(self) -> None:
        for name in ("model", "tool", "policy", "evidence", "state", "retrieval", "prompt", "tokenizer"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 512:
                raise ValidationError(f"epoch {name} must be a non-empty bounded string")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EpochBinding":
        return cls(**dict(value))

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return digest_object({"schema": "szl.cognitive-epochs/v1", **self.to_dict()})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0
    retry_on: tuple[str, ...] = ()
    ambiguous_external_retry: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_attempts", _integer(self.max_attempts, field_name="max_attempts", minimum=1, maximum=16))
        object.__setattr__(self, "backoff_seconds", _number(self.backoff_seconds, field_name="backoff_seconds", maximum=3600))
        object.__setattr__(self, "retry_on", _bounded_strings(self.retry_on, field_name="retry_on", maximum=32, item_maximum=128))
        object.__setattr__(
            self,
            "ambiguous_external_retry",
            _boolean(self.ambiguous_external_retry, field_name="ambiguous_external_retry"),
        )
        if self.ambiguous_external_retry:
            raise ValidationError("ambiguous external retries are forbidden by the reference kernel")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "RetryPolicy":
        data = dict(value or {})
        if "retry_on" in data:
            data["retry_on"] = tuple(data["retry_on"])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "retry_on": list(self.retry_on),
            "ambiguous_external_retry": self.ambiguous_external_retry,
        }


@dataclass(frozen=True, slots=True)
class ConditionSpec:
    kind: str
    target: str
    expected: Any = True

    def __post_init__(self) -> None:
        allowed = {
            "FILE_EXISTS",
            "FILE_ABSENT",
            "SHA256_EQUALS",
            "TEXT_CONTAINS",
            "JSON_POINTER_EQUALS",
        }
        if self.kind not in allowed:
            raise ValidationError(f"unsupported condition kind: {self.kind}")
        if not isinstance(self.target, str) or not self.target or len(self.target) > 2048:
            raise ValidationError("condition target must be a bounded string")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConditionSpec":
        return cls(kind=str(value["kind"]), target=str(value["target"]), expected=value.get("expected", True))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    required: bool = True
    strategy: str = "RESTORE_PREIMAGE"
    authority_capability: str = "file:rollback"
    max_seconds: int = 30

    def __post_init__(self) -> None:
        object.__setattr__(self, "required", _boolean(self.required, field_name="rollback required"))
        if self.strategy not in {"RESTORE_PREIMAGE", "DELETE_CREATED", "NONE"}:
            raise ValidationError("unsupported rollback strategy")
        if self.required and self.strategy == "NONE":
            raise ValidationError("required rollback cannot use NONE")
        require_identifier(self.authority_capability, field="rollback authority capability")
        object.__setattr__(self, "max_seconds", _integer(self.max_seconds, field_name="rollback max_seconds", maximum=86_400))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "RollbackPlan":
        return cls(**dict(value or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    grant_id: str
    principal: str
    capabilities: tuple[str, ...]
    target_patterns: tuple[str, ...]
    tools: tuple[str, ...]
    budgets: BudgetLimits
    issued_at: str
    expires_at: str
    parent_grant_id: str | None = None
    revoked_at: str | None = None
    revocation_ref: str | None = None
    schema: str = "szl.capability-grant/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.capability-grant/v1")
        require_identifier(self.grant_id, field="grant_id")
        require_identifier(self.principal, field="principal")
        if self.parent_grant_id is not None:
            require_identifier(self.parent_grant_id, field="parent_grant_id")
        object.__setattr__(self, "capabilities", _bounded_strings(self.capabilities, field_name="capabilities", minimum=1, item_maximum=128))
        object.__setattr__(self, "target_patterns", _bounded_strings(self.target_patterns, field_name="target_patterns", minimum=1))
        object.__setattr__(self, "tools", _bounded_strings(self.tools, field_name="tools", minimum=1, item_maximum=128))
        object.__setattr__(self, "issued_at", isoformat_utc(self.issued_at))
        object.__setattr__(self, "expires_at", isoformat_utc(self.expires_at))
        if parse_utc(self.expires_at) <= parse_utc(self.issued_at):
            raise ValidationError("capability grant expiry must be after issue time")
        if self.revoked_at is not None:
            object.__setattr__(self, "revoked_at", isoformat_utc(self.revoked_at))
            if not self.revocation_ref:
                raise ValidationError("revoked grant requires revocation_ref")
            if parse_utc(self.revoked_at) < parse_utc(self.issued_at):
                raise ValidationError("capability grant cannot be revoked before it is issued")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityGrant":
        data = dict(value)
        data["capabilities"] = tuple(data.get("capabilities", ()))
        data["target_patterns"] = tuple(data.get("target_patterns", ()))
        data["tools"] = tuple(data.get("tools", ()))
        data["budgets"] = BudgetLimits.from_dict(data.get("budgets"))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["budgets"] = self.budgets.to_dict()
        return value

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())

    def active_at(self, when: str | datetime) -> bool:
        now = parse_utc(when)
        return parse_utc(self.issued_at) <= now < parse_utc(self.expires_at) and self.revoked_at is None


@dataclass(frozen=True, slots=True)
class AutonomyEnvelope:
    case_id: str
    principal: str
    subject: str
    exact_targets: tuple[str, ...]
    capabilities: tuple[str, ...]
    tools: tuple[str, ...]
    risk_class: RiskClass
    blast_radius: BlastRadius
    autonomy_level: AutonomyLevel
    budgets: BudgetLimits
    preconditions: tuple[ConditionSpec, ...]
    postconditions: tuple[ConditionSpec, ...]
    idempotency_key: str
    retry_policy: RetryPolicy
    rollback_plan: RollbackPlan
    epochs: EpochBinding
    required_roles: tuple[CouncilRole, ...]
    required_council_state: CouncilState
    receipt_required: bool
    transparency_required: bool
    issued_at: str
    expires_at: str
    revocation_ref: str | None = None
    schema: str = "szl.autonomy-envelope/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.autonomy-envelope/v1")
        require_identifier(self.case_id, field="case_id")
        require_identifier(self.principal, field="principal")
        if not isinstance(self.subject, str) or not self.subject or len(self.subject) > 4096:
            raise ValidationError("subject must be a bounded non-empty string")
        object.__setattr__(self, "exact_targets", _bounded_strings(self.exact_targets, field_name="exact_targets", minimum=1))
        object.__setattr__(self, "capabilities", _bounded_strings(self.capabilities, field_name="capabilities", minimum=1, item_maximum=128))
        object.__setattr__(self, "tools", _bounded_strings(self.tools, field_name="tools", minimum=1, item_maximum=128))
        object.__setattr__(self, "risk_class", _enum(RiskClass, self.risk_class, "risk_class"))
        object.__setattr__(self, "blast_radius", _enum(BlastRadius, self.blast_radius, "blast_radius"))
        object.__setattr__(self, "autonomy_level", _enum(AutonomyLevel, self.autonomy_level, "autonomy_level"))
        object.__setattr__(self, "required_council_state", _enum(CouncilState, self.required_council_state, "required_council_state"))
        object.__setattr__(self, "receipt_required", _boolean(self.receipt_required, field_name="receipt_required"))
        object.__setattr__(self, "transparency_required", _boolean(self.transparency_required, field_name="transparency_required"))
        roles = tuple(_enum(CouncilRole, role, "required_roles") for role in self.required_roles)
        if set(roles) != set(CouncilRole):
            raise ValidationError("reference envelope requires all four Council roles")
        object.__setattr__(self, "required_roles", roles)
        object.__setattr__(self, "issued_at", isoformat_utc(self.issued_at))
        object.__setattr__(self, "expires_at", isoformat_utc(self.expires_at))
        if parse_utc(self.expires_at) <= parse_utc(self.issued_at):
            raise ValidationError("envelope expiry must be after issue time")
        require_identifier(self.idempotency_key, field="idempotency_key")
        if self.autonomy_level in {AutonomyLevel.A0_OBSERVE, AutonomyLevel.A1_PROPOSE} and self.budgets.max_mutations > 0:
            raise ValidationError("A0/A1 envelopes cannot carry a mutation budget")
        if self.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL} and not self.transparency_required:
            raise ValidationError("high/critical-risk envelopes require transparency")
        if self.budgets.max_mutations and not self.rollback_plan.required:
            raise ValidationError("mutating envelopes require rollback")
        if self.budgets.max_mutations and not self.postconditions:
            raise ValidationError("mutating envelopes require explicit postconditions")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AutonomyEnvelope":
        data = dict(value)
        data["exact_targets"] = tuple(data.get("exact_targets", ()))
        data["capabilities"] = tuple(data.get("capabilities", ()))
        data["tools"] = tuple(data.get("tools", ()))
        data["risk_class"] = _enum(RiskClass, data["risk_class"], "risk_class")
        data["blast_radius"] = _enum(BlastRadius, data["blast_radius"], "blast_radius")
        data["autonomy_level"] = _enum(AutonomyLevel, data["autonomy_level"], "autonomy_level")
        data["budgets"] = BudgetLimits.from_dict(data.get("budgets"))
        data["preconditions"] = tuple(ConditionSpec.from_dict(item) for item in data.get("preconditions", ()))
        data["postconditions"] = tuple(ConditionSpec.from_dict(item) for item in data.get("postconditions", ()))
        data["retry_policy"] = RetryPolicy.from_dict(data.get("retry_policy"))
        data["rollback_plan"] = RollbackPlan.from_dict(data.get("rollback_plan"))
        data["epochs"] = EpochBinding.from_dict(data["epochs"])
        data["required_roles"] = tuple(_enum(CouncilRole, item, "required_roles") for item in data.get("required_roles", tuple(CouncilRole)))
        data["required_council_state"] = _enum(CouncilState, data.get("required_council_state", CouncilState.QUORUM_VERIFIED), "required_council_state")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "principal": self.principal,
            "subject": self.subject,
            "exact_targets": list(self.exact_targets),
            "capabilities": list(self.capabilities),
            "tools": list(self.tools),
            "risk_class": self.risk_class.value,
            "blast_radius": self.blast_radius.value,
            "autonomy_level": self.autonomy_level.value,
            "budgets": self.budgets.to_dict(),
            "preconditions": [item.to_dict() for item in self.preconditions],
            "postconditions": [item.to_dict() for item in self.postconditions],
            "idempotency_key": self.idempotency_key,
            "retry_policy": self.retry_policy.to_dict(),
            "rollback_plan": self.rollback_plan.to_dict(),
            "epochs": self.epochs.to_dict(),
            "required_roles": [item.value for item in self.required_roles],
            "required_council_state": self.required_council_state.value,
            "receipt_required": self.receipt_required,
            "transparency_required": self.transparency_required,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revocation_ref": self.revocation_ref,
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())

    def active_at(self, when: str | datetime) -> bool:
        now = parse_utc(when)
        return parse_utc(self.issued_at) <= now < parse_utc(self.expires_at) and self.revocation_ref is None


@dataclass(frozen=True, slots=True)
class CouncilCase:
    case_id: str
    subject: str
    risk_class: RiskClass
    value_claimed: bool
    evidence_manifest_digest: str
    policy_digest: str
    envelope_digest: str
    epochs_digest: str
    created_at: str
    schema: str = "szl.council-case/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.council-case/v1")
        require_identifier(self.case_id, field="case_id")
        if not isinstance(self.subject, str) or not self.subject or len(self.subject) > 4096:
            raise ValidationError("case subject must be bounded")
        object.__setattr__(self, "risk_class", _enum(RiskClass, self.risk_class, "risk_class"))
        object.__setattr__(self, "value_claimed", _boolean(self.value_claimed, field_name="value_claimed"))
        for name in ("evidence_manifest_digest", "policy_digest", "envelope_digest", "epochs_digest"):
            require_digest(getattr(self, name), field=name)
        object.__setattr__(self, "created_at", isoformat_utc(self.created_at))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CouncilCase":
        data = dict(value)
        data["risk_class"] = _enum(RiskClass, data["risk_class"], "risk_class")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "subject": self.subject,
            "risk_class": self.risk_class.value,
            "value_claimed": self.value_claimed,
            "evidence_manifest_digest": self.evidence_manifest_digest,
            "policy_digest": self.policy_digest,
            "envelope_digest": self.envelope_digest,
            "epochs_digest": self.epochs_digest,
            "created_at": self.created_at,
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class CouncilIdentity:
    member_id: str
    role: CouncilRole
    key_id: str
    public_key: str
    trust_domain: str
    implementation_digest: str
    model_family: str
    evidence_domain: str
    operator_id: str
    retrieval_path: str
    provider_account: str
    not_before: str
    not_after: str
    schema: str = "szl.council-identity/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.council-identity/v1")
        require_identifier(self.member_id, field="member_id")
        object.__setattr__(self, "role", _enum(CouncilRole, self.role, "role"))
        require_digest(self.key_id, field="key_id")
        if not isinstance(self.public_key, str) or len(self.public_key) < 20:
            raise ValidationError("public_key must be encoded")
        for name in (
            "trust_domain",
            "implementation_digest",
            "model_family",
            "evidence_domain",
            "operator_id",
            "retrieval_path",
            "provider_account",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or len(value) > 512:
                raise ValidationError(f"identity {name} must be bounded")
        require_digest(self.implementation_digest, field="implementation_digest")
        object.__setattr__(self, "not_before", isoformat_utc(self.not_before))
        object.__setattr__(self, "not_after", isoformat_utc(self.not_after))
        if parse_utc(self.not_after) <= parse_utc(self.not_before):
            raise ValidationError("identity not_after must be after not_before")

    def active_at(self, when: str | datetime) -> bool:
        now = parse_utc(when)
        return parse_utc(self.not_before) <= now < parse_utc(self.not_after)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CouncilIdentity":
        data = dict(value)
        data["role"] = _enum(CouncilRole, data["role"], "role")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["role"] = self.role.value
        return value


@dataclass(frozen=True, slots=True)
class CouncilAssessment:
    case_id: str
    role: CouncilRole
    member_id: str
    vote: CouncilVote
    confidence: float
    reason_codes: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    counterevidence_digests: tuple[str, ...]
    policy_digest: str
    subject_digest: str
    issued_at: str
    expires_at: str
    schema: str = "szl.council-assessment/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.council-assessment/v1")
        require_identifier(self.case_id, field="case_id")
        require_identifier(self.member_id, field="member_id")
        object.__setattr__(self, "role", _enum(CouncilRole, self.role, "role"))
        object.__setattr__(self, "vote", _enum(CouncilVote, self.vote, "vote"))
        object.__setattr__(self, "confidence", _number(self.confidence, field_name="confidence", maximum=1.0))
        object.__setattr__(self, "reason_codes", _bounded_strings(self.reason_codes, field_name="reason_codes", minimum=1, maximum=64, item_maximum=128))
        evidence = tuple(require_digest(item, field="evidence_digest") for item in self.evidence_digests)
        counter = tuple(require_digest(item, field="counterevidence_digest") for item in self.counterevidence_digests)
        object.__setattr__(self, "evidence_digests", tuple(sorted(set(evidence))))
        object.__setattr__(self, "counterevidence_digests", tuple(sorted(set(counter))))
        require_digest(self.policy_digest, field="policy_digest")
        require_digest(self.subject_digest, field="subject_digest")
        object.__setattr__(self, "issued_at", isoformat_utc(self.issued_at))
        object.__setattr__(self, "expires_at", isoformat_utc(self.expires_at))
        if parse_utc(self.expires_at) <= parse_utc(self.issued_at):
            raise ValidationError("assessment expiry must be after issue time")
        if self.vote == CouncilVote.SUPPORT and not self.evidence_digests:
            raise ValidationError("support assessments require explicit evidence")
        if self.vote in {CouncilVote.OPPOSE, CouncilVote.VETO} and not self.counterevidence_digests:
            raise ValidationError("opposition and veto assessments require counterevidence")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CouncilAssessment":
        data = dict(value)
        data["role"] = _enum(CouncilRole, data["role"], "role")
        data["vote"] = _enum(CouncilVote, data["vote"], "vote")
        data["reason_codes"] = tuple(data.get("reason_codes", ()))
        data["evidence_digests"] = tuple(data.get("evidence_digests", ()))
        data["counterevidence_digests"] = tuple(data.get("counterevidence_digests", ()))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "role": self.role.value,
            "member_id": self.member_id,
            "vote": self.vote.value,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "evidence_digests": list(self.evidence_digests),
            "counterevidence_digests": list(self.counterevidence_digests),
            "policy_digest": self.policy_digest,
            "subject_digest": self.subject_digest,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())

    def active_at(self, when: str | datetime) -> bool:
        now = parse_utc(when)
        return parse_utc(self.issued_at) <= now < parse_utc(self.expires_at)


@dataclass(frozen=True, slots=True)
class CouncilPolicy:
    policy_id: str = "szl-fourfold-default"
    version: str = "1.0.0"
    min_distinct_trust_domains: int = 4
    min_distinct_keys: int = 4
    min_distinct_implementations: int = 3
    min_distinct_model_families: int = 3
    min_distinct_evidence_domains: int = 3
    min_distinct_operators: int = 3
    min_distinct_retrieval_paths: int = 3
    min_distinct_provider_accounts: int = 3
    minimum_effective_size: float = 2.5
    low_medium_support_threshold: int = 3
    high_critical_support_threshold: int = 4
    require_authority_support: bool = True
    require_verifier_support: bool = True
    require_value_support_when_claimed: bool = True
    preserve_minority_truth: bool = True
    sentinel_veto_categorical: bool = True
    verifier_veto_categorical: bool = True
    schema: str = "szl.council-policy/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.council-policy/v1")
        require_identifier(self.policy_id, field="policy_id")
        if not isinstance(self.version, str) or not self.version or len(self.version) > 64:
            raise ValidationError("policy version must be bounded")
        for name in (
            "min_distinct_trust_domains",
            "min_distinct_keys",
            "min_distinct_implementations",
            "min_distinct_model_families",
            "min_distinct_evidence_domains",
            "min_distinct_operators",
            "min_distinct_retrieval_paths",
            "min_distinct_provider_accounts",
            "low_medium_support_threshold",
            "high_critical_support_threshold",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), field_name=name, minimum=1, maximum=4))
        object.__setattr__(self, "minimum_effective_size", _number(self.minimum_effective_size, field_name="minimum_effective_size", minimum=1, maximum=4))
        for name in (
            "require_authority_support",
            "require_verifier_support",
            "require_value_support_when_claimed",
            "preserve_minority_truth",
            "sentinel_veto_categorical",
            "verifier_veto_categorical",
        ):
            object.__setattr__(self, name, _boolean(getattr(self, name), field_name=name))
        if self.high_critical_support_threshold < self.low_medium_support_threshold:
            raise ValidationError("high/critical support threshold cannot be lower than low/medium")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "CouncilPolicy":
        return cls(**dict(value or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class CouncilResult:
    case_id: str
    state: CouncilState
    verified: bool
    support_roles: tuple[CouncilRole, ...]
    oppose_roles: tuple[CouncilRole, ...]
    abstain_roles: tuple[CouncilRole, ...]
    veto_roles: tuple[CouncilRole, ...]
    missing_roles: tuple[CouncilRole, ...]
    reason_codes: tuple[str, ...]
    minority_evidence_digests: tuple[str, ...]
    received_support: int
    required_support: int
    diversity: Mapping[str, Any]
    policy_digest: str
    subject_digest: str
    transcript_digest: str
    issued_at: str
    schema: str = "szl.council-result/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.council-result/v1")
        require_identifier(self.case_id, field="case_id")
        object.__setattr__(self, "state", _enum(CouncilState, self.state, "state"))
        object.__setattr__(self, "verified", _boolean(self.verified, field_name="verified"))
        if self.verified != (self.state == CouncilState.QUORUM_VERIFIED):
            raise ValidationError("verified must be true only for QUORUM_VERIFIED")
        role_groups: list[tuple[CouncilRole, ...]] = []
        for name in ("support_roles", "oppose_roles", "abstain_roles", "veto_roles", "missing_roles"):
            roles = tuple(_enum(CouncilRole, item, name) for item in getattr(self, name))
            if len(set(roles)) != len(roles):
                raise ValidationError(f"{name} contains duplicate roles")
            normalized_roles = tuple(sorted(roles, key=lambda role: role.value))
            object.__setattr__(self, name, normalized_roles)
            role_groups.append(normalized_roles)
        flattened = [role for group in role_groups for role in group]
        if len(flattened) != len(set(flattened)):
            raise ValidationError("Council result role classifications must be disjoint")
        if set(flattened) != set(CouncilRole):
            raise ValidationError("Council result must classify every Fourfold role exactly once")
        object.__setattr__(self, "reason_codes", _bounded_strings(self.reason_codes, field_name="reason_codes", minimum=1, maximum=128, item_maximum=128))
        object.__setattr__(self, "minority_evidence_digests", tuple(sorted(set(require_digest(item) for item in self.minority_evidence_digests))))
        object.__setattr__(self, "received_support", _integer(self.received_support, field_name="received_support", maximum=4))
        object.__setattr__(self, "required_support", _integer(self.required_support, field_name="required_support", minimum=1, maximum=4))
        if self.received_support != len(self.support_roles):
            raise ValidationError("received_support must equal the support role count")
        if not isinstance(self.diversity, Mapping):
            raise ValidationError("diversity must be a mapping")
        if self.state == CouncilState.QUORUM_VERIFIED:
            if self.oppose_roles or self.abstain_roles or self.veto_roles or self.missing_roles:
                raise ValidationError("QUORUM_VERIFIED cannot contain opposition, abstention, veto, or missing roles")
            if self.received_support < self.required_support:
                raise ValidationError("QUORUM_VERIFIED must satisfy its support threshold")
            if self.diversity.get("requirements_met") is not True:
                raise ValidationError("QUORUM_VERIFIED requires a passing diversity report")
        for name in ("policy_digest", "subject_digest", "transcript_digest"):
            require_digest(getattr(self, name), field=name)
        object.__setattr__(self, "issued_at", isoformat_utc(self.issued_at))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CouncilResult":
        data = dict(value)
        data["state"] = _enum(CouncilState, data["state"], "state")
        for name in ("support_roles", "oppose_roles", "abstain_roles", "veto_roles", "missing_roles"):
            data[name] = tuple(_enum(CouncilRole, item, name) for item in data.get(name, ()))
        data["reason_codes"] = tuple(data.get("reason_codes", ()))
        data["minority_evidence_digests"] = tuple(data.get("minority_evidence_digests", ()))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "state": self.state.value,
            "verified": self.verified,
            "support_roles": [item.value for item in self.support_roles],
            "oppose_roles": [item.value for item in self.oppose_roles],
            "abstain_roles": [item.value for item in self.abstain_roles],
            "veto_roles": [item.value for item in self.veto_roles],
            "missing_roles": [item.value for item in self.missing_roles],
            "reason_codes": list(self.reason_codes),
            "minority_evidence_digests": list(self.minority_evidence_digests),
            "received_support": self.received_support,
            "required_support": self.required_support,
            "diversity": dict(self.diversity),
            "policy_digest": self.policy_digest,
            "subject_digest": self.subject_digest,
            "transcript_digest": self.transcript_digest,
            "issued_at": self.issued_at,
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    case_id: str
    grant_id: str
    kind: ActionKind
    tool: str
    target: str
    content: str | None
    expected_before_digest: str | None
    idempotency_key: str
    postconditions: tuple[ConditionSpec, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema: str = "szl.action-request/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.action-request/v1")
        require_identifier(self.action_id, field="action_id")
        require_identifier(self.case_id, field="case_id")
        require_identifier(self.grant_id, field="grant_id")
        require_identifier(self.idempotency_key, field="idempotency_key")
        object.__setattr__(self, "kind", _enum(ActionKind, self.kind, "kind"))
        if self.tool != "sandbox_fs":
            raise ValidationError("reference executor supports only sandbox_fs")
        if not isinstance(self.target, str) or not self.target or len(self.target) > 2048:
            raise ValidationError("action target must be bounded")
        if self.kind in {ActionKind.FILE_WRITE, ActionKind.FILE_APPEND} and self.content is None:
            raise ValidationError("write and append actions require content")
        if self.kind == ActionKind.FILE_DELETE and self.content is not None:
            raise ValidationError("delete action must not include content")
        if self.expected_before_digest is not None:
            require_digest(self.expected_before_digest, field="expected_before_digest")
        if self.kind in {ActionKind.FILE_WRITE, ActionKind.FILE_APPEND, ActionKind.FILE_DELETE} and not self.postconditions:
            raise ValidationError("mutating actions require explicit postconditions")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ActionRequest":
        data = dict(value)
        data["kind"] = _enum(ActionKind, data["kind"], "kind")
        data["postconditions"] = tuple(ConditionSpec.from_dict(item) for item in data.get("postconditions", ()))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "action_id": self.action_id,
            "case_id": self.case_id,
            "grant_id": self.grant_id,
            "kind": self.kind.value,
            "tool": self.tool,
            "target": self.target,
            "content": self.content,
            "expected_before_digest": self.expected_before_digest,
            "idempotency_key": self.idempotency_key,
            "postconditions": [item.to_dict() for item in self.postconditions],
            "metadata": dict(self.metadata),
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    receipt_id: str
    case_id: str
    action_id: str
    action_digest: str
    status: str
    target: str
    before_digest: str | None
    after_digest: str | None
    postconditions_passed: bool
    rolled_back: bool
    rollback_digest: str | None
    council_result_digest: str
    gate_result_digest: str
    event_hash: str
    previous_receipt_digest: str | None
    issued_at: str
    signer_state: str
    schema: str = "szl.action-receipt/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.action-receipt/v1")
        for name in ("receipt_id", "case_id", "action_id"):
            require_identifier(getattr(self, name), field=name)
        for name in ("action_digest", "council_result_digest", "gate_result_digest", "event_hash"):
            require_digest(getattr(self, name), field=name)
        for name in ("before_digest", "after_digest", "rollback_digest", "previous_receipt_digest"):
            value = getattr(self, name)
            if value is not None:
                require_digest(value, field=name)
        if self.status not in {"VERIFIED", "ROLLED_BACK", "BLOCKED", "FAILED", "REPLAYED"}:
            raise ValidationError("invalid receipt status")
        object.__setattr__(
            self,
            "postconditions_passed",
            _boolean(self.postconditions_passed, field_name="postconditions_passed"),
        )
        object.__setattr__(self, "rolled_back", _boolean(self.rolled_back, field_name="rolled_back"))
        if self.signer_state not in {"SIGNED_TEST", "SIGNED_PERSISTENT", "UNSIGNED"}:
            raise ValidationError("invalid signer_state")
        if self.status == "VERIFIED" and (not self.postconditions_passed or self.rolled_back):
            raise ValidationError("VERIFIED receipt requires passing postconditions and no rollback")
        if self.status == "ROLLED_BACK" and (self.postconditions_passed or not self.rolled_back or self.rollback_digest is None):
            raise ValidationError("ROLLED_BACK receipt requires verified compensation evidence")
        if self.status == "BLOCKED" and (self.postconditions_passed or self.rolled_back):
            raise ValidationError("BLOCKED receipt cannot claim postconditions or rollback")
        object.__setattr__(self, "issued_at", isoformat_utc(self.issued_at))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ActionReceipt":
        return cls(**dict(value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class GateInput:
    council_state: CouncilState
    risk_class: RiskClass
    effective_diversity: float
    evidence_completeness: float
    proof_completeness: float
    novelty_score: float
    ambiguity_score: float
    irreversibility_score: float
    drift_score: float
    expected_blast_radius: float
    historical_false_green_rate: float
    calibration_sample_size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "council_state", _enum(CouncilState, self.council_state, "council_state"))
        object.__setattr__(self, "risk_class", _enum(RiskClass, self.risk_class, "risk_class"))
        object.__setattr__(self, "effective_diversity", _number(self.effective_diversity, field_name="effective_diversity", maximum=4))
        for name in (
            "evidence_completeness",
            "proof_completeness",
            "novelty_score",
            "ambiguity_score",
            "irreversibility_score",
            "drift_score",
            "expected_blast_radius",
            "historical_false_green_rate",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), field_name=name, maximum=1))
        object.__setattr__(self, "calibration_sample_size", _integer(self.calibration_sample_size, field_name="calibration_sample_size", maximum=10_000_000))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GateInput":
        data = dict(value)
        data["council_state"] = _enum(CouncilState, data["council_state"], "council_state")
        data["risk_class"] = _enum(RiskClass, data["risk_class"], "risk_class")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["council_state"] = self.council_state.value
        value["risk_class"] = self.risk_class.value
        return value


@dataclass(frozen=True, slots=True)
class GateResult:
    decision: ReleaseDecision
    risk_score: float
    empirical_false_green_upper: float
    reason_codes: tuple[str, ...]
    calibration_method: str
    formal_coverage_claimed: bool
    issued_at: str
    schema: str = "szl.act-escalate-gate-result/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.act-escalate-gate-result/v1")
        object.__setattr__(self, "decision", _enum(ReleaseDecision, self.decision, "decision"))
        object.__setattr__(self, "risk_score", _number(self.risk_score, field_name="risk_score", maximum=1))
        object.__setattr__(self, "empirical_false_green_upper", _number(self.empirical_false_green_upper, field_name="empirical_false_green_upper", maximum=1))
        object.__setattr__(self, "reason_codes", _bounded_strings(self.reason_codes, field_name="reason_codes", minimum=1, maximum=64, item_maximum=128))
        object.__setattr__(
            self,
            "formal_coverage_claimed",
            _boolean(self.formal_coverage_claimed, field_name="formal_coverage_claimed"),
        )
        if self.formal_coverage_claimed:
            raise ValidationError("reference empirical gate cannot claim formal coverage")
        object.__setattr__(self, "issued_at", isoformat_utc(self.issued_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "risk_score": self.risk_score,
            "empirical_false_green_upper": self.empirical_false_green_upper,
            "reason_codes": list(self.reason_codes),
            "calibration_method": self.calibration_method,
            "formal_coverage_claimed": self.formal_coverage_claimed,
            "issued_at": self.issued_at,
            "schema": self.schema,
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())


@dataclass(frozen=True, slots=True)
class BranchCandidate:
    branch_id: str
    case_id: str
    required_capabilities: tuple[str, ...]
    expected_utility: float
    risk: float
    cost: float
    latency: float
    proof_completeness: float
    diversity_contribution: float
    novelty_penalty: float
    evidence_digests: tuple[str, ...]
    schema: str = "szl.counterfactual-branch/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.counterfactual-branch/v1")
        require_identifier(self.branch_id, field="branch_id")
        require_identifier(self.case_id, field="case_id")
        object.__setattr__(self, "required_capabilities", _bounded_strings(self.required_capabilities, field_name="required_capabilities", item_maximum=128))
        for name in (
            "expected_utility",
            "risk",
            "cost",
            "latency",
            "proof_completeness",
            "diversity_contribution",
            "novelty_penalty",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), field_name=name, maximum=1))
        object.__setattr__(self, "evidence_digests", tuple(sorted(set(require_digest(item) for item in self.evidence_digests))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "branch_id": self.branch_id,
            "case_id": self.case_id,
            "required_capabilities": list(self.required_capabilities),
            "expected_utility": self.expected_utility,
            "risk": self.risk,
            "cost": self.cost,
            "latency": self.latency,
            "proof_completeness": self.proof_completeness,
            "diversity_contribution": self.diversity_contribution,
            "novelty_penalty": self.novelty_penalty,
            "evidence_digests": list(self.evidence_digests),
        }


@dataclass(frozen=True, slots=True)
class OutcomeContract:
    outcome_id: str
    case_id: str
    action_receipt_digest: str
    metric: str
    baseline: float
    expected_direction: str
    effect_window_start: str
    effect_window_end: str
    observation_schedule: tuple[str, ...]
    attribution_method: str
    stop_loss: float | None
    confounders: tuple[str, ...]
    schema: str = "szl.outcome-contract/v1"

    def __post_init__(self) -> None:
        _require_schema(self.schema, "szl.outcome-contract/v1")
        require_identifier(self.outcome_id, field="outcome_id")
        require_identifier(self.case_id, field="case_id")
        require_digest(self.action_receipt_digest, field="action_receipt_digest")
        if not isinstance(self.metric, str) or not self.metric or len(self.metric) > 512:
            raise ValidationError("outcome metric must be bounded")
        object.__setattr__(self, "baseline", _number(self.baseline, field_name="baseline", minimum=-1_000_000_000, maximum=1_000_000_000))
        if self.expected_direction not in {"INCREASE", "DECREASE", "HOLD"}:
            raise ValidationError("invalid expected_direction")
        object.__setattr__(self, "effect_window_start", isoformat_utc(self.effect_window_start))
        object.__setattr__(self, "effect_window_end", isoformat_utc(self.effect_window_end))
        if parse_utc(self.effect_window_end) <= parse_utc(self.effect_window_start):
            raise ValidationError("outcome effect window must be positive")
        object.__setattr__(self, "observation_schedule", tuple(isoformat_utc(item) for item in self.observation_schedule))
        object.__setattr__(self, "confounders", _bounded_strings(self.confounders, field_name="confounders", maximum=128))
        if self.stop_loss is not None:
            object.__setattr__(self, "stop_loss", _number(self.stop_loss, field_name="stop_loss", minimum=-1_000_000_000, maximum=1_000_000_000))

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "observation_schedule": list(self.observation_schedule),
            "confounders": list(self.confounders),
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())
