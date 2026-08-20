"""Deterministic authority kernel for governed adviser councils.

Advisers can propose assessments. This module retains execution authority in
explicit capability, role, veto, diversity, risk, and receipt contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Mapping, Protocol, Sequence


DIVERSITY_AXES: tuple[str, ...] = (
    "operator_id",
    "key_id",
    "model_lineage",
    "implementation_id",
    "provider_id",
    "retrieval_path",
    "evidence_domain",
    "trust_domain",
)


class CouncilError(RuntimeError):
    """Base exception for invalid Council state."""


class CommitmentError(CouncilError):
    """Raised when a reveal does not match its prior commitment."""


class LedgerIntegrityError(CouncilError):
    """Raised when an append-only ledger does not verify."""


class Role(str, Enum):
    AUTHORITY = "AUTHORITY"
    SENTINEL = "SENTINEL"
    VERIFIER = "VERIFIER"
    VALUE = "VALUE"


class Decision(str, Enum):
    ACT = "ACT"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


class RiskClass(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class SignatureState(str, Enum):
    UNSIGNED = "UNSIGNED"
    SIGNED = "SIGNED"


class ActionStatus(str, Enum):
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    BLOCKED = "BLOCKED"


def canonical_json(value: Any) -> str:
    """Return deterministic UTF-8 JSON text for hashing and commitments."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class MemberIdentity:
    member_id: str
    role: Role
    operator_id: str
    key_id: str
    model_lineage: str
    implementation_id: str
    provider_id: str
    retrieval_path: str
    evidence_domain: str
    trust_domain: str

    def __post_init__(self) -> None:
        _require_nonempty("member_id", self.member_id)
        for axis in DIVERSITY_AXES:
            _require_nonempty(axis, getattr(self, axis))

    def axes(self) -> tuple[str, ...]:
        return tuple(getattr(self, axis) for axis in DIVERSITY_AXES)

    def canonical_dict(self) -> dict[str, str]:
        return {
            "member_id": self.member_id,
            "role": self.role.value,
            **{axis: getattr(self, axis) for axis in DIVERSITY_AXES},
        }


@dataclass(frozen=True, slots=True)
class Assessment:
    recommendation: Decision
    confidence: float
    claims: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    objections: tuple[str, ...] = ()
    veto: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        for collection_name in ("claims", "evidence", "objections"):
            values = getattr(self, collection_name)
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{collection_name} must contain non-empty strings")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "claims": list(self.claims),
            "evidence": list(self.evidence),
            "objections": list(self.objections),
            "veto": self.veto,
        }


@dataclass(frozen=True, slots=True)
class Commitment:
    member_id: str
    digest: str

    def __post_init__(self) -> None:
        _require_nonempty("member_id", self.member_id)
        if len(self.digest) != 64 or any(ch not in "0123456789abcdef" for ch in self.digest):
            raise ValueError("commitment digest must be lowercase SHA-256 hex")


@dataclass(frozen=True, slots=True)
class Reveal:
    member: MemberIdentity
    assessment: Assessment
    nonce: str
    commitment: Commitment

    def verify(self) -> None:
        if self.commitment.member_id != self.member.member_id:
            raise CommitmentError("commitment member does not match reveal member")
        if len(self.nonce) < 8:
            raise CommitmentError("reveal nonce must contain at least eight characters")
        if self.assessment.veto and self.member.role not in (Role.SENTINEL, Role.VERIFIER):
            raise CommitmentError("only Sentinel and Verifier may submit categorical vetoes")
        expected = make_commitment(self.member, self.assessment, self.nonce)
        if not hmac.compare_digest(expected.digest, self.commitment.digest):
            raise CommitmentError("reveal payload does not match commitment")


def make_commitment(
    member: MemberIdentity,
    assessment: Assessment,
    nonce: str,
) -> Commitment:
    if len(nonce) < 8:
        raise ValueError("nonce must contain at least eight characters")
    payload = {
        "member": member.canonical_dict(),
        "assessment": assessment.canonical_dict(),
        "nonce": nonce,
    }
    return Commitment(member_id=member.member_id, digest=sha256_text(canonical_json(payload)))


@dataclass(frozen=True, slots=True)
class Proposal:
    proposal_id: str
    action: str
    target: str
    capability: str
    risk_class: RiskClass
    estimated_cost_microunits: int
    evidence_requirements: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("proposal_id", "action", "target", "capability"):
            _require_nonempty(name, getattr(self, name))
        if self.estimated_cost_microunits < 0:
            raise ValueError("estimated cost cannot be negative")
        keys = [key for key, _ in self.metadata]
        if len(keys) != len(set(keys)):
            raise ValueError("proposal metadata keys must be unique")
        for key, value in self.metadata:
            _require_nonempty("metadata key", key)
            if not isinstance(value, str):
                raise ValueError("proposal metadata values must be strings")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "action": self.action,
            "target": self.target,
            "capability": self.capability,
            "risk_class": self.risk_class.value,
            "estimated_cost_microunits": self.estimated_cost_microunits,
            "evidence_requirements": list(self.evidence_requirements),
            "metadata": {key: value for key, value in self.metadata},
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    grant_id: str
    subject: str
    capabilities: tuple[str, ...]
    actions: tuple[str, ...]
    exact_targets: tuple[str, ...]
    budget_microunits: int
    expires_at: datetime
    revoked: bool = False

    def __post_init__(self) -> None:
        _require_nonempty("grant_id", self.grant_id)
        _require_nonempty("subject", self.subject)
        if self.budget_microunits < 0:
            raise ValueError("grant budget cannot be negative")
        _utc(self.expires_at)
        for name in ("capabilities", "actions", "exact_targets"):
            values = getattr(self, name)
            if not values or any(not item.strip() for item in values):
                raise ValueError(f"{name} must contain non-empty values")

    def denial_reasons(
        self,
        proposal: Proposal,
        *,
        now: datetime,
        spent_microunits: int = 0,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.revoked:
            reasons.append("capability grant is revoked")
        if _utc(now) >= _utc(self.expires_at):
            reasons.append("capability grant is expired")
        if proposal.capability not in self.capabilities:
            reasons.append("capability is not granted")
        if proposal.action not in self.actions:
            reasons.append("action is not granted")
        if proposal.target not in self.exact_targets:
            reasons.append("target does not exactly match the grant")
        if spent_microunits < 0:
            reasons.append("recorded spend cannot be negative")
        elif spent_microunits + proposal.estimated_cost_microunits > self.budget_microunits:
            reasons.append("grant budget would be exceeded")
        return tuple(reasons)


@dataclass(frozen=True, slots=True)
class CouncilPolicy:
    required_roles: frozenset[Role] = field(
        default_factory=lambda: frozenset(
            {Role.AUTHORITY, Role.SENTINEL, Role.VERIFIER, Role.VALUE}
        )
    )
    minimum_effective_size: float = 2.5
    act_score_threshold: float = 0.67
    minimum_evidence_per_member: int = 1
    maximum_autonomous_risk: RiskClass = RiskClass.B

    def __post_init__(self) -> None:
        if not self.required_roles:
            raise ValueError("at least one role must be required")
        if self.minimum_effective_size <= 0:
            raise ValueError("minimum effective size must be positive")
        if not -1.0 <= self.act_score_threshold <= 1.0:
            raise ValueError("act score threshold must be between -1 and 1")
        if self.minimum_evidence_per_member < 0:
            raise ValueError("minimum evidence count cannot be negative")


@dataclass(frozen=True, slots=True)
class DiversityReport:
    effective_size: float
    member_weights: tuple[tuple[str, float], ...]
    unique_values_by_axis: tuple[tuple[str, int], ...]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "effective_size": self.effective_size,
            "member_weights": {member: weight for member, weight in self.member_weights},
            "unique_values_by_axis": {
                axis: count for axis, count in self.unique_values_by_axis
            },
        }


def measure_diversity(members: Sequence[MemberIdentity]) -> DiversityReport:
    if not members:
        return DiversityReport(0.0, (), tuple((axis, 0) for axis in DIVERSITY_AXES))

    identifiers = [member.member_id for member in members]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("member identities must be unique")

    weights: list[tuple[str, float]] = []
    for index, member in enumerate(members):
        correlation = 0.0
        member_axes = member.axes()
        for other_index, other in enumerate(members):
            if index == other_index:
                continue
            other_axes = other.axes()
            equal_axes = sum(
                1 for left, right in zip(member_axes, other_axes, strict=True) if left == right
            )
            correlation += equal_axes / len(DIVERSITY_AXES)
        weights.append((member.member_id, 1.0 / (1.0 + correlation)))

    effective_size = round(sum(weight for _, weight in weights), 6)
    unique_values = tuple(
        (axis, len({getattr(member, axis) for member in members}))
        for axis in DIVERSITY_AXES
    )
    return DiversityReport(
        effective_size=effective_size,
        member_weights=tuple(weights),
        unique_values_by_axis=unique_values,
    )


@dataclass(frozen=True, slots=True)
class MemberResult:
    member_id: str
    role: Role
    recommendation: Decision
    confidence: float
    veto: bool
    evidence: tuple[str, ...]
    objections: tuple[str, ...]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "role": self.role.value,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "veto": self.veto,
            "evidence": list(self.evidence),
            "objections": list(self.objections),
        }


@dataclass(frozen=True, slots=True)
class MinorityReport:
    member_id: str
    role: Role
    recommendation: Decision
    objections: tuple[str, ...]
    evidence: tuple[str, ...]

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "role": self.role.value,
            "recommendation": self.recommendation.value,
            "objections": list(self.objections),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    proposal_digest: str
    decision: Decision
    score: float
    reasons: tuple[str, ...]
    grant_id: str | None
    diversity: DiversityReport
    member_results: tuple[MemberResult, ...]
    minority_reports: tuple[MinorityReport, ...]
    decision_digest: str

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "proposal_digest": self.proposal_digest,
            "decision": self.decision.value,
            "score": self.score,
            "reasons": list(self.reasons),
            "grant_id": self.grant_id,
            "diversity": self.diversity.canonical_dict(),
            "member_results": [result.canonical_dict() for result in self.member_results],
            "minority_reports": [report.canonical_dict() for report in self.minority_reports],
        }
        if include_digest:
            value["decision_digest"] = self.decision_digest
        return value


_RISK_ORDER: Mapping[RiskClass, int] = {
    RiskClass.A: 0,
    RiskClass.B: 1,
    RiskClass.C: 2,
    RiskClass.D: 3,
}

_RECOMMENDATION_SCORE: Mapping[Decision, float] = {
    Decision.ACT: 1.0,
    Decision.ESCALATE: 0.0,
    Decision.BLOCK: -1.0,
}


class CouncilKernel:
    """Compile committed adviser assessments into one bounded decision."""

    def __init__(self, policy: CouncilPolicy | None = None) -> None:
        self.policy = policy or CouncilPolicy()

    def evaluate(
        self,
        proposal: Proposal,
        reveals: Sequence[Reveal],
        grants: Sequence[CapabilityGrant],
        *,
        now: datetime | None = None,
        spent_by_grant: Mapping[str, int] | None = None,
    ) -> DecisionRecord:
        evaluation_time = _utc(now or datetime.now(timezone.utc))
        spent = spent_by_grant or {}
        reasons: list[str] = []
        invalid_members: list[str] = []

        member_ids = [reveal.member.member_id for reveal in reveals]
        has_duplicate_members = len(member_ids) != len(set(member_ids))
        if has_duplicate_members:
            reasons.append("duplicate Council member identity")

        for reveal in reveals:
            try:
                reveal.verify()
            except CommitmentError as exc:
                invalid_members.append(reveal.member.member_id)
                reasons.append(f"invalid commitment for {reveal.member.member_id}: {exc}")

        valid_reveals = tuple(
            reveal for reveal in reveals if reveal.member.member_id not in invalid_members
        )
        members = tuple(reveal.member for reveal in valid_reveals)
        diversity = (
            measure_diversity(())
            if has_duplicate_members
            else measure_diversity(members)
        )
        member_results = tuple(
            MemberResult(
                member_id=reveal.member.member_id,
                role=reveal.member.role,
                recommendation=reveal.assessment.recommendation,
                confidence=reveal.assessment.confidence,
                veto=reveal.assessment.veto,
                evidence=reveal.assessment.evidence,
                objections=reveal.assessment.objections,
            )
            for reveal in valid_reveals
        )

        decision = Decision.ESCALATE
        grant_id: str | None = None

        if invalid_members or has_duplicate_members:
            decision = Decision.BLOCK
        else:
            matching_grant: CapabilityGrant | None = None
            grant_denials: list[str] = []
            for grant in grants:
                denials = grant.denial_reasons(
                    proposal,
                    now=evaluation_time,
                    spent_microunits=spent.get(grant.grant_id, 0),
                )
                if not denials:
                    matching_grant = grant
                    break
                grant_denials.extend(f"{grant.grant_id}: {reason}" for reason in denials)

            if matching_grant is None:
                decision = Decision.BLOCK
                reasons.append("no capability grant authorizes the exact proposal")
                reasons.extend(sorted(set(grant_denials)))
            else:
                grant_id = matching_grant.grant_id

                observed_roles = {reveal.member.role for reveal in valid_reveals}
                missing_roles = sorted(
                    (role.value for role in self.policy.required_roles - observed_roles)
                )
                if missing_roles:
                    decision = Decision.ESCALATE
                    reasons.append(f"required Council roles are missing: {', '.join(missing_roles)}")
                else:
                    vetoes = tuple(
                        reveal
                        for reveal in valid_reveals
                        if reveal.assessment.veto
                        and reveal.member.role in (Role.SENTINEL, Role.VERIFIER)
                    )
                    authority_blocks = tuple(
                        reveal
                        for reveal in valid_reveals
                        if reveal.member.role is Role.AUTHORITY
                        and reveal.assessment.recommendation is Decision.BLOCK
                    )
                    if vetoes:
                        decision = Decision.BLOCK
                        reasons.extend(
                            f"categorical {reveal.member.role.value} veto by {reveal.member.member_id}"
                            for reveal in vetoes
                        )
                    elif authority_blocks:
                        decision = Decision.BLOCK
                        reasons.extend(
                            f"Authority mandate denied by {reveal.member.member_id}"
                            for reveal in authority_blocks
                        )
                    else:
                        missing_evidence = tuple(
                            reveal.member.member_id
                            for reveal in valid_reveals
                            if len(reveal.assessment.evidence)
                            < self.policy.minimum_evidence_per_member
                        )
                        evidence_pool = {
                            reference
                            for reveal in valid_reveals
                            for reference in reveal.assessment.evidence
                        }
                        unmet_requirements = tuple(
                            requirement
                            for requirement in proposal.evidence_requirements
                            if requirement not in evidence_pool
                        )
                        if missing_evidence or unmet_requirements:
                            decision = Decision.ESCALATE
                            if missing_evidence:
                                reasons.append(
                                    "members without required evidence: "
                                    + ", ".join(sorted(missing_evidence))
                                )
                            if unmet_requirements:
                                reasons.append(
                                    "proposal evidence requirements are unmet: "
                                    + ", ".join(sorted(unmet_requirements))
                                )
                        elif diversity.effective_size < self.policy.minimum_effective_size:
                            decision = Decision.ESCALATE
                            reasons.append(
                                "effective Council size is below the independence threshold"
                            )
                        elif _RISK_ORDER[proposal.risk_class] > _RISK_ORDER[
                            self.policy.maximum_autonomous_risk
                        ]:
                            decision = (
                                Decision.BLOCK
                                if proposal.risk_class is RiskClass.D
                                else Decision.ESCALATE
                            )
                            reasons.append(
                                f"risk class {proposal.risk_class.value} exceeds autonomous policy"
                            )
                        else:
                            authority_acts = any(
                                reveal.member.role is Role.AUTHORITY
                                and reveal.assessment.recommendation is Decision.ACT
                                for reveal in valid_reveals
                            )
                            if not authority_acts:
                                decision = Decision.ESCALATE
                                reasons.append("no Authority member affirmatively grants action")
                            else:
                                score = self._score(valid_reveals, diversity)
                                if score >= self.policy.act_score_threshold:
                                    decision = Decision.ACT
                                    reasons.append("capability, evidence, diversity, risk, and score gates passed")
                                else:
                                    decision = Decision.ESCALATE
                                    reasons.append("Council score is below the action threshold")

        score = self._score(valid_reveals, diversity)
        minority_reports = tuple(
            MinorityReport(
                member_id=reveal.member.member_id,
                role=reveal.member.role,
                recommendation=reveal.assessment.recommendation,
                objections=reveal.assessment.objections,
                evidence=reveal.assessment.evidence,
            )
            for reveal in valid_reveals
            if reveal.assessment.recommendation is not decision
            or bool(reveal.assessment.objections)
        )

        record_without_digest = {
            "proposal_digest": proposal.digest,
            "decision": decision.value,
            "score": score,
            "reasons": reasons,
            "grant_id": grant_id,
            "diversity": diversity.canonical_dict(),
            "member_results": [result.canonical_dict() for result in member_results],
            "minority_reports": [report.canonical_dict() for report in minority_reports],
        }
        decision_digest = sha256_text(canonical_json(record_without_digest))
        return DecisionRecord(
            proposal_digest=proposal.digest,
            decision=decision,
            score=score,
            reasons=tuple(reasons),
            grant_id=grant_id,
            diversity=diversity,
            member_results=member_results,
            minority_reports=minority_reports,
            decision_digest=decision_digest,
        )

    @staticmethod
    def _score(reveals: Sequence[Reveal], diversity: DiversityReport) -> float:
        if not reveals:
            return 0.0
        diversity_weights = dict(diversity.member_weights)
        numerator = 0.0
        denominator = 0.0
        for reveal in reveals:
            weight = diversity_weights.get(reveal.member.member_id, 0.0)
            confidence_weight = weight * reveal.assessment.confidence
            numerator += (
                _RECOMMENDATION_SCORE[reveal.assessment.recommendation]
                * confidence_weight
            )
            denominator += confidence_weight
        if denominator == 0.0:
            return 0.0
        return round(numerator / denominator, 6)


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    sequence: int
    kind: str
    payload: Mapping[str, Any]
    previous_hash: str
    entry_hash: str

    def canonical_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": dict(self.payload),
            "previous_hash": self.previous_hash,
        }
        if include_hash:
            value["entry_hash"] = self.entry_hash
        return value


class HashChainLedger:
    """Append-only canonical JSON ledger with optional durable JSONL storage."""

    GENESIS_HASH = "0" * 64

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._entries: list[LedgerEntry] = []
        self._lock = RLock()
        if self._path is not None and self._path.exists():
            self._load()

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def append(self, kind: str, payload: Mapping[str, Any]) -> LedgerEntry:
        _require_nonempty("ledger kind", kind)
        canonical_json(payload)
        with self._lock:
            previous_hash = (
                self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH
            )
            body = {
                "sequence": len(self._entries),
                "kind": kind,
                "payload": dict(payload),
                "previous_hash": previous_hash,
            }
            entry = LedgerEntry(
                sequence=body["sequence"],
                kind=kind,
                payload=dict(payload),
                previous_hash=previous_hash,
                entry_hash=sha256_text(canonical_json(body)),
            )
            self._entries.append(entry)
            if self._path is not None:
                self._append_to_disk(entry)
            return entry

    def verify(self) -> bool:
        with self._lock:
            previous_hash = self.GENESIS_HASH
            for expected_sequence, entry in enumerate(self._entries):
                if entry.sequence != expected_sequence:
                    return False
                if entry.previous_hash != previous_hash:
                    return False
                expected_hash = sha256_text(
                    canonical_json(entry.canonical_dict(include_hash=False))
                )
                if not hmac.compare_digest(expected_hash, entry.entry_hash):
                    return False
                previous_hash = entry.entry_hash
            return True

    def _append_to_disk(self, entry: LedgerEntry) -> None:
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(entry.canonical_dict()))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _load(self) -> None:
        assert self._path is not None
        loaded: list[LedgerEntry] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise LedgerIntegrityError(f"blank ledger line at {line_number}")
                try:
                    raw = json.loads(line)
                    entry = LedgerEntry(
                        sequence=int(raw["sequence"]),
                        kind=str(raw["kind"]),
                        payload=dict(raw["payload"]),
                        previous_hash=str(raw["previous_hash"]),
                        entry_hash=str(raw["entry_hash"]),
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise LedgerIntegrityError(
                        f"invalid ledger line at {line_number}"
                    ) from exc
                loaded.append(entry)
        self._entries = loaded
        if not self.verify():
            raise LedgerIntegrityError("ledger hash chain verification failed")


class Signer(Protocol):
    @property
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> str: ...


class Verifier(Protocol):
    def verify(self, key_id: str, payload: bytes, signature: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class ReceiptEnvelope:
    payload: Mapping[str, Any]
    payload_digest: str
    signature_state: SignatureState
    key_id: str | None
    signature: str | None
    receipt_digest: str

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "payload": dict(self.payload),
            "payload_digest": self.payload_digest,
            "signature_state": self.signature_state.value,
            "key_id": self.key_id,
            "signature": self.signature,
        }
        if include_digest:
            value["receipt_digest"] = self.receipt_digest
        return value


def seal_action_receipt(
    *,
    proposal: Proposal,
    decision: DecisionRecord,
    status: ActionStatus,
    preconditions: Sequence[str],
    postconditions: Sequence[str],
    observed_at: datetime,
    signer: Signer | None = None,
) -> ReceiptEnvelope:
    expected_decision_digest = sha256_text(
        canonical_json(decision.canonical_dict(include_digest=False))
    )
    if not hmac.compare_digest(decision.decision_digest, expected_decision_digest):
        raise ValueError("decision record digest does not verify")
    if not hmac.compare_digest(decision.proposal_digest, proposal.digest):
        raise ValueError("decision does not authorize this proposal digest")
    if status is ActionStatus.APPLIED and decision.decision is not Decision.ACT:
        raise ValueError("APPLIED status requires an ACT decision")

    timestamp = _utc(observed_at).isoformat().replace("+00:00", "Z")
    payload: dict[str, Any] = {
        "proposal_id": proposal.proposal_id,
        "proposal_digest": proposal.digest,
        "decision_digest": decision.decision_digest,
        "decision": decision.decision.value,
        "action": proposal.action,
        "target": proposal.target,
        "status": status.value,
        "preconditions": list(preconditions),
        "postconditions": list(postconditions),
        "observed_at": timestamp,
    }
    payload_bytes = canonical_json(payload).encode("utf-8")
    payload_digest = hashlib.sha256(payload_bytes).hexdigest()

    if signer is None:
        signature_state = SignatureState.UNSIGNED
        key_id = None
        signature = None
    else:
        _require_nonempty("signer key_id", signer.key_id)
        signature = signer.sign(payload_bytes)
        _require_nonempty("signature", signature)
        signature_state = SignatureState.SIGNED
        key_id = signer.key_id

    envelope_without_digest = {
        "payload": payload,
        "payload_digest": payload_digest,
        "signature_state": signature_state.value,
        "key_id": key_id,
        "signature": signature,
    }
    receipt_digest = sha256_text(canonical_json(envelope_without_digest))
    return ReceiptEnvelope(
        payload=payload,
        payload_digest=payload_digest,
        signature_state=signature_state,
        key_id=key_id,
        signature=signature,
        receipt_digest=receipt_digest,
    )


def verify_action_receipt(
    envelope: ReceiptEnvelope,
    verifier: Verifier | None = None,
    *,
    proposal: Proposal | None = None,
    decision: DecisionRecord | None = None,
) -> bool:
    try:
        if proposal is None or decision is None:
            return False
        expected_decision_digest = sha256_text(
            canonical_json(decision.canonical_dict(include_digest=False))
        )
        if not hmac.compare_digest(decision.decision_digest, expected_decision_digest):
            return False
        if not hmac.compare_digest(proposal.digest, decision.proposal_digest):
            return False
        if envelope.payload["proposal_id"] != proposal.proposal_id:
            return False
        if envelope.payload["action"] != proposal.action:
            return False
        if envelope.payload["target"] != proposal.target:
            return False
        if not hmac.compare_digest(envelope.payload["proposal_digest"], proposal.digest):
            return False
        if not hmac.compare_digest(
            envelope.payload["decision_digest"], decision.decision_digest
        ):
            return False
        if envelope.payload["decision"] != decision.decision.value:
            return False
        payload_decision = Decision(envelope.payload["decision"])
        payload_status = ActionStatus(envelope.payload["status"])
        payload_bytes = canonical_json(envelope.payload).encode("utf-8")
        if payload_status is ActionStatus.APPLIED and payload_decision is not Decision.ACT:
            return False
        if not hmac.compare_digest(
            hashlib.sha256(payload_bytes).hexdigest(), envelope.payload_digest
        ):
            return False

        expected_receipt_digest = sha256_text(
            canonical_json(envelope.canonical_dict(include_digest=False))
        )
        if not hmac.compare_digest(expected_receipt_digest, envelope.receipt_digest):
            return False
    except (AttributeError, KeyError, TypeError, ValueError):
        return False

    if envelope.signature_state is SignatureState.UNSIGNED:
        return envelope.key_id is None and envelope.signature is None

    if envelope.key_id is None or envelope.signature is None or verifier is None:
        return False
    try:
        return verifier.verify(
            envelope.key_id,
            payload_bytes,
            envelope.signature,
        )
    except Exception:
        # A verifier implementation is an injected trust boundary; errors deny.
        return False


def decision_to_ledger_payload(record: DecisionRecord) -> Mapping[str, Any]:
    return record.canonical_dict()


def receipt_to_ledger_payload(envelope: ReceiptEnvelope) -> Mapping[str, Any]:
    return envelope.canonical_dict()


def reveal_set_digest(reveals: Iterable[Reveal]) -> str:
    ordered = sorted(
        (
            {
                "member": reveal.member.canonical_dict(),
                "assessment": reveal.assessment.canonical_dict(),
                "commitment": reveal.commitment.digest,
            }
            for reveal in reveals
        ),
        key=lambda value: value["member"]["member_id"],
    )
    return sha256_text(canonical_json(ordered))
