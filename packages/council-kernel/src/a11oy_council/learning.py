"""Delayed outcome contracts and a negative-capability ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hmac
import math
import re
from threading import RLock
from typing import Any, Mapping, Sequence

from .kernel import HashChainLedger, canonical_json, sha256_text


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MetricDirection(str, Enum):
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"
    EQUAL = "EQUAL"


class OutcomeState(str, Enum):
    PENDING = "PENDING"
    MET = "MET"
    NOT_MET = "NOT_MET"
    INCONCLUSIVE = "INCONCLUSIVE"


class UnknownState(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"


class LearningPromotionState(str, Enum):
    PENDING = "PENDING"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class OutcomeContract:
    contract_id: str
    decision_digest: str
    metric_name: str
    direction: MetricDirection
    baseline_value: float
    target_value: float
    tolerance: float
    deadline: datetime
    required_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty("contract_id", self.contract_id)
        _nonempty("metric_name", self.metric_name)
        if not _SHA256.fullmatch(self.decision_digest):
            raise ValueError("decision_digest must be lowercase SHA-256 hex")
        for name in ("baseline_value", "target_value", "tolerance"):
            _finite(name, getattr(self, name))
        if self.tolerance < 0:
            raise ValueError("tolerance cannot be negative")
        _utc(self.deadline)
        if any(not item.strip() for item in self.required_evidence):
            raise ValueError("required_evidence must contain non-empty strings")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "decision_digest": self.decision_digest,
            "metric_name": self.metric_name,
            "direction": self.direction.value,
            "baseline_value": self.baseline_value,
            "target_value": self.target_value,
            "tolerance": self.tolerance,
            "deadline": _utc(self.deadline).isoformat().replace("+00:00", "Z"),
            "required_evidence": list(self.required_evidence),
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    contract_id: str
    observed_at: datetime
    value: float | None
    evidence: tuple[str, ...]
    source_digest: str | None
    complete: bool

    def __post_init__(self) -> None:
        _nonempty("contract_id", self.contract_id)
        _utc(self.observed_at)
        if self.value is not None:
            _finite("observation value", self.value)
        if any(not item.strip() for item in self.evidence):
            raise ValueError("evidence must contain non-empty strings")
        if self.source_digest is not None and not _SHA256.fullmatch(self.source_digest):
            raise ValueError("source_digest must be lowercase SHA-256 hex")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "observed_at": _utc(self.observed_at).isoformat().replace("+00:00", "Z"),
            "value": self.value,
            "evidence": list(self.evidence),
            "source_digest": self.source_digest,
            "complete": self.complete,
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class OutcomePolicy:
    accept_late_observations: bool = False
    require_source_digest: bool = True


@dataclass(frozen=True, slots=True)
class OutcomeEvaluation:
    contract_digest: str
    observation_digest: str | None
    state: OutcomeState
    reasons: tuple[str, ...]
    evaluated_at: datetime
    evaluation_digest: str

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "contract_digest": self.contract_digest,
            "observation_digest": self.observation_digest,
            "state": self.state.value,
            "reasons": list(self.reasons),
            "evaluated_at": _utc(self.evaluated_at).isoformat().replace("+00:00", "Z"),
        }
        if include_digest:
            value["evaluation_digest"] = self.evaluation_digest
        return value


def evaluate_outcome(
    contract: OutcomeContract,
    observation: OutcomeObservation | None,
    *,
    evaluated_at: datetime,
    policy: OutcomePolicy | None = None,
) -> OutcomeEvaluation:
    active_policy = policy or OutcomePolicy()
    now = _utc(evaluated_at)
    reasons: list[str] = []

    if observation is None:
        if now <= _utc(contract.deadline):
            state = OutcomeState.PENDING
            reasons.append("outcome observation is not yet due")
        else:
            state = OutcomeState.INCONCLUSIVE
            reasons.append("outcome deadline passed without an observation")
        observation_digest = None
    else:
        observation_digest = observation.digest
        if observation.contract_id != contract.contract_id:
            state = OutcomeState.INCONCLUSIVE
            reasons.append("observation contract_id does not match")
        elif not observation.complete or observation.value is None:
            state = OutcomeState.INCONCLUSIVE
            reasons.append("observation is incomplete")
        elif active_policy.require_source_digest and observation.source_digest is None:
            state = OutcomeState.INCONCLUSIVE
            reasons.append("observation source digest is absent")
        elif (
            not active_policy.accept_late_observations
            and _utc(observation.observed_at) > _utc(contract.deadline)
        ):
            state = OutcomeState.INCONCLUSIVE
            reasons.append("observation arrived after the contract deadline")
        else:
            evidence = set(observation.evidence)
            missing = sorted(set(contract.required_evidence) - evidence)
            if missing:
                state = OutcomeState.INCONCLUSIVE
                reasons.append("required outcome evidence is absent: " + ", ".join(missing))
            else:
                assert observation.value is not None
                if contract.direction is MetricDirection.AT_LEAST:
                    passed = observation.value + contract.tolerance >= contract.target_value
                elif contract.direction is MetricDirection.AT_MOST:
                    passed = observation.value - contract.tolerance <= contract.target_value
                else:
                    passed = abs(observation.value - contract.target_value) <= contract.tolerance
                state = OutcomeState.MET if passed else OutcomeState.NOT_MET
                reasons.append("outcome target met" if passed else "outcome target not met")

    body = {
        "contract_digest": contract.digest,
        "observation_digest": observation_digest,
        "state": state.value,
        "reasons": reasons,
        "evaluated_at": now.isoformat().replace("+00:00", "Z"),
    }
    return OutcomeEvaluation(
        contract_digest=contract.digest,
        observation_digest=observation_digest,
        state=state,
        reasons=tuple(reasons),
        evaluated_at=now,
        evaluation_digest=sha256_text(canonical_json(body)),
    )


@dataclass(frozen=True, slots=True)
class UnknownClaim:
    claim_id: str
    statement: str
    required_evidence: tuple[str, ...]
    opened_at: datetime
    expires_at: datetime
    source_decision_digest: str | None = None

    def __post_init__(self) -> None:
        _nonempty("claim_id", self.claim_id)
        _nonempty("statement", self.statement)
        if not self.required_evidence or any(not item.strip() for item in self.required_evidence):
            raise ValueError("required_evidence must contain non-empty strings")
        if _utc(self.expires_at) <= _utc(self.opened_at):
            raise ValueError("unknown claim expiry must follow opening")
        if self.source_decision_digest is not None and not _SHA256.fullmatch(
            self.source_decision_digest
        ):
            raise ValueError("source_decision_digest must be lowercase SHA-256 hex")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "required_evidence": list(self.required_evidence),
            "opened_at": _utc(self.opened_at).isoformat().replace("+00:00", "Z"),
            "expires_at": _utc(self.expires_at).isoformat().replace("+00:00", "Z"),
            "source_decision_digest": self.source_decision_digest,
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class UnknownResolution:
    claim_digest: str
    state: UnknownState
    evidence: tuple[str, ...]
    resolved_at: datetime
    resolution_digest: str


class NegativeCapabilityLedger:
    """Record what the system does not know and the evidence required to close it."""

    def __init__(self, ledger: HashChainLedger | None = None) -> None:
        self.ledger = ledger or HashChainLedger()
        self._claims: dict[str, UnknownClaim] = {}
        self._resolutions: dict[str, UnknownResolution] = {}
        self._lock = RLock()

    @property
    def claims(self) -> Mapping[str, UnknownClaim]:
        with self._lock:
            return dict(self._claims)

    def open(self, claim: UnknownClaim) -> None:
        with self._lock:
            existing = self._claims.get(claim.claim_id)
            if existing is not None and existing.digest != claim.digest:
                raise ValueError("claim_id already names different content")
            if existing is None:
                self._claims[claim.claim_id] = claim
                self.ledger.append(
                    "unknown.opened",
                    {"claim_id": claim.claim_id, "claim_digest": claim.digest},
                )

    def resolve(
        self,
        claim_id: str,
        *,
        evidence: Sequence[str],
        resolved_at: datetime,
    ) -> UnknownResolution:
        now = _utc(resolved_at)
        with self._lock:
            claim = self._claims.get(claim_id)
            if claim is None:
                raise KeyError(f"unknown claim_id: {claim_id}")
            evidence_values = tuple(evidence)
            if any(not item.strip() for item in evidence_values):
                raise ValueError("resolution evidence must contain non-empty strings")
            missing = sorted(set(claim.required_evidence) - set(evidence_values))
            if now > _utc(claim.expires_at):
                state = UnknownState.EXPIRED
            elif missing:
                state = UnknownState.OPEN
            else:
                state = UnknownState.RESOLVED
            body = {
                "claim_digest": claim.digest,
                "state": state.value,
                "evidence": list(evidence_values),
                "resolved_at": now.isoformat().replace("+00:00", "Z"),
            }
            resolution = UnknownResolution(
                claim_digest=claim.digest,
                state=state,
                evidence=evidence_values,
                resolved_at=now,
                resolution_digest=sha256_text(canonical_json(body)),
            )
            self._resolutions[claim_id] = resolution
            self.ledger.append(
                "unknown.evaluated",
                {
                    "claim_id": claim_id,
                    "claim_digest": claim.digest,
                    "state": state.value,
                    "resolution_digest": resolution.resolution_digest,
                },
            )
            return resolution

    def state(self, claim_id: str, *, at: datetime) -> UnknownState:
        now = _utc(at)
        with self._lock:
            claim = self._claims.get(claim_id)
            if claim is None:
                raise KeyError(f"unknown claim_id: {claim_id}")
            resolution = self._resolutions.get(claim_id)
        if resolution is not None and resolution.state is UnknownState.RESOLVED:
            return UnknownState.RESOLVED
        if now > _utc(claim.expires_at):
            return UnknownState.EXPIRED
        return UnknownState.OPEN

    def unresolved(self, *, at: datetime) -> tuple[str, ...]:
        with self._lock:
            identifiers = tuple(self._claims)
        return tuple(
            claim_id
            for claim_id in identifiers
            if self.state(claim_id, at=at) is not UnknownState.RESOLVED
        )


@dataclass(frozen=True, slots=True)
class LearningDisposition:
    contract_digest: str
    outcome_evaluation_digest: str | None
    state: LearningPromotionState
    reasons: tuple[str, ...]
    disposition_digest: str


class OutcomeLearningGate:
    """Bind decisions to delayed outcomes before admitting a learning candidate."""

    def __init__(
        self,
        *,
        policy: OutcomePolicy | None = None,
        ledger: HashChainLedger | None = None,
    ) -> None:
        self.policy = policy or OutcomePolicy()
        self.ledger = ledger or HashChainLedger()
        self._contracts: dict[str, OutcomeContract] = {}
        self._observations: dict[str, OutcomeObservation] = {}
        self._evaluations: dict[str, OutcomeEvaluation] = {}

    def register(self, contract: OutcomeContract) -> None:
        existing = self._contracts.get(contract.contract_id)
        if existing is not None and existing.digest != contract.digest:
            raise ValueError("contract_id already names different content")
        if existing is None:
            self._contracts[contract.contract_id] = contract
            self.ledger.append(
                "outcome.registered",
                {"contract_id": contract.contract_id, "contract_digest": contract.digest},
            )

    def observe(self, observation: OutcomeObservation) -> None:
        if observation.contract_id not in self._contracts:
            raise KeyError(f"unknown contract_id: {observation.contract_id}")
        existing = self._observations.get(observation.contract_id)
        if existing is not None and existing.digest != observation.digest:
            raise ValueError("contract already has a different observation")
        if existing is None:
            self._observations[observation.contract_id] = observation
            self.ledger.append(
                "outcome.observed",
                {
                    "contract_id": observation.contract_id,
                    "observation_digest": observation.digest,
                },
            )

    def evaluate(self, contract_id: str, *, evaluated_at: datetime) -> OutcomeEvaluation:
        contract = self._contracts.get(contract_id)
        if contract is None:
            raise KeyError(f"unknown contract_id: {contract_id}")
        evaluation = evaluate_outcome(
            contract,
            self._observations.get(contract_id),
            evaluated_at=evaluated_at,
            policy=self.policy,
        )
        self._evaluations[contract_id] = evaluation
        self.ledger.append(
            "outcome.evaluated",
            {
                "contract_id": contract_id,
                "evaluation_digest": evaluation.evaluation_digest,
                "state": evaluation.state.value,
            },
        )
        return evaluation

    def promotion_disposition(
        self,
        contract_id: str,
        *,
        evaluated_at: datetime,
        unresolved_unknowns: Sequence[str] = (),
        policy_findings: Sequence[str] = (),
    ) -> LearningDisposition:
        contract = self._contracts.get(contract_id)
        if contract is None:
            raise KeyError(f"unknown contract_id: {contract_id}")
        evaluation = self._evaluations.get(contract_id)
        reasons: list[str] = []
        if evaluation is None:
            state = LearningPromotionState.PENDING
            reasons.append("outcome has not been evaluated")
        elif evaluation.state is OutcomeState.PENDING:
            state = LearningPromotionState.PENDING
            reasons.append("outcome remains pending")
        elif evaluation.state is not OutcomeState.MET:
            state = LearningPromotionState.BLOCKED
            reasons.append(f"outcome state is {evaluation.state.value}")
        elif unresolved_unknowns:
            state = LearningPromotionState.BLOCKED
            reasons.append("negative-capability claims remain unresolved")
        elif policy_findings:
            state = LearningPromotionState.BLOCKED
            reasons.append("policy findings remain unresolved")
        else:
            state = LearningPromotionState.ELIGIBLE
            reasons.append("outcome, unknown-claim, and policy gates passed")

        body = {
            "contract_digest": contract.digest,
            "outcome_evaluation_digest": (
                evaluation.evaluation_digest if evaluation is not None else None
            ),
            "state": state.value,
            "reasons": reasons,
            "evaluated_at": _utc(evaluated_at).isoformat().replace("+00:00", "Z"),
        }
        disposition = LearningDisposition(
            contract_digest=contract.digest,
            outcome_evaluation_digest=body["outcome_evaluation_digest"],
            state=state,
            reasons=tuple(reasons),
            disposition_digest=sha256_text(canonical_json(body)),
        )
        self.ledger.append(
            "learning.promotion_evaluated",
            {
                "contract_id": contract_id,
                "state": state.value,
                "disposition_digest": disposition.disposition_digest,
            },
        )
        return disposition


def verify_outcome_evaluation(
    contract: OutcomeContract,
    observation: OutcomeObservation | None,
    evaluation: OutcomeEvaluation,
    *,
    policy: OutcomePolicy | None = None,
) -> bool:
    expected = evaluate_outcome(
        contract,
        observation,
        evaluated_at=evaluation.evaluated_at,
        policy=policy,
    )
    expected_record = canonical_json(expected.canonical_dict())
    provided_record = canonical_json(evaluation.canonical_dict())
    return hmac.compare_digest(expected_record, provided_record)
