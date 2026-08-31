"""Blinded Council session state machine with bounded commit and reveal windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Mapping, Sequence

from .delegation import grant_digest
from .kernel import (
    Assessment,
    CapabilityGrant,
    Commitment,
    CouncilKernel,
    CouncilPolicy,
    DecisionRecord,
    HashChainLedger,
    MemberIdentity,
    Proposal,
    Reveal,
    canonical_json,
    reveal_set_digest,
    sha256_text,
)


class SessionPhase(str, Enum):
    COMMIT_OPEN = "COMMIT_OPEN"
    REVEAL_OPEN = "REVEAL_OPEN"
    DECIDED = "DECIDED"
    CLOSED = "CLOSED"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    session_id: str
    phase: SessionPhase
    proposal_digest: str
    roster_member_ids: tuple[str, ...]
    committed_member_ids: tuple[str, ...]
    revealed_member_ids: tuple[str, ...]
    commit_deadline: datetime
    reveal_deadline: datetime
    reveal_set_digest: str | None
    decision_digest: str | None
    snapshot_digest: str

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "proposal_digest": self.proposal_digest,
            "roster_member_ids": list(self.roster_member_ids),
            "committed_member_ids": list(self.committed_member_ids),
            "revealed_member_ids": list(self.revealed_member_ids),
            "commit_deadline": _utc(self.commit_deadline).isoformat().replace("+00:00", "Z"),
            "reveal_deadline": _utc(self.reveal_deadline).isoformat().replace("+00:00", "Z"),
            "reveal_set_digest": self.reveal_set_digest,
            "decision_digest": self.decision_digest,
        }
        if include_digest:
            value["snapshot_digest"] = self.snapshot_digest
        return value


class CouncilSession:
    """Coordinate one proposal through immutable commit and reveal phases."""

    def __init__(
        self,
        *,
        session_id: str,
        proposal: Proposal,
        roster: Sequence[MemberIdentity],
        grants: Sequence[CapabilityGrant],
        created_at: datetime,
        commit_deadline: datetime,
        reveal_deadline: datetime,
        policy: CouncilPolicy | None = None,
        ledger: HashChainLedger | None = None,
    ) -> None:
        _nonempty("session_id", session_id)
        created = _utc(created_at)
        commit_limit = _utc(commit_deadline)
        reveal_limit = _utc(reveal_deadline)
        if commit_limit <= created:
            raise ValueError("commit deadline must follow session creation")
        if reveal_limit <= commit_limit:
            raise ValueError("reveal deadline must follow commit deadline")
        if not roster:
            raise ValueError("Council roster cannot be empty")
        roster_ids = [member.member_id for member in roster]
        if len(roster_ids) != len(set(roster_ids)):
            raise ValueError("Council roster member identities must be unique")
        grant_ids = [grant.grant_id for grant in grants]
        if len(grant_ids) != len(set(grant_ids)):
            raise ValueError("capability grant identities must be unique")

        self.session_id = session_id
        self.proposal = proposal
        self.created_at = created
        self.commit_deadline = commit_limit
        self.reveal_deadline = reveal_limit
        self.policy = policy or CouncilPolicy()
        self.ledger = ledger or HashChainLedger()
        self._kernel = CouncilKernel(self.policy)
        self._roster = {member.member_id: member for member in roster}
        self._grants = tuple(grants)
        self._commitments: dict[str, Commitment] = {}
        self._reveals: dict[str, Reveal] = {}
        self._decision: DecisionRecord | None = None
        self._phase = SessionPhase.COMMIT_OPEN
        self._lock = RLock()

        self.ledger.append(
            "council.session_created",
            {
                "session_id": self.session_id,
                "proposal_digest": self.proposal.digest,
                "roster": sorted(self._roster),
                "grant_digests": sorted(grant_digest(grant) for grant in self._grants),
                "created_at": created.isoformat().replace("+00:00", "Z"),
                "commit_deadline": commit_limit.isoformat().replace("+00:00", "Z"),
                "reveal_deadline": reveal_limit.isoformat().replace("+00:00", "Z"),
            },
        )

    @property
    def phase(self) -> SessionPhase:
        with self._lock:
            return self._phase

    @property
    def decision(self) -> DecisionRecord | None:
        with self._lock:
            return self._decision

    @property
    def commitments(self) -> Mapping[str, Commitment]:
        with self._lock:
            return dict(self._commitments)

    @property
    def reveals(self) -> Mapping[str, Reveal]:
        with self._lock:
            return dict(self._reveals)

    def submit_commitment(self, commitment: Commitment, *, submitted_at: datetime) -> None:
        now = _utc(submitted_at)
        with self._lock:
            self._require_phase(SessionPhase.COMMIT_OPEN)
            if now < self.created_at:
                raise ValueError("commitment predates the session")
            if now > self.commit_deadline:
                raise ValueError("commit window is closed")
            if commitment.member_id not in self._roster:
                raise ValueError("commitment member is not in the fixed roster")
            if commitment.member_id in self._commitments:
                existing = self._commitments[commitment.member_id]
                if existing.digest != commitment.digest:
                    raise ValueError("member already submitted a different commitment")
                return
            self._commitments[commitment.member_id] = commitment
            self.ledger.append(
                "council.commitment_submitted",
                {
                    "session_id": self.session_id,
                    "member_id": commitment.member_id,
                    "commitment_digest": commitment.digest,
                    "submitted_at": now.isoformat().replace("+00:00", "Z"),
                },
            )

    def seal_commit_phase(self, *, sealed_at: datetime) -> None:
        now = _utc(sealed_at)
        with self._lock:
            self._require_phase(SessionPhase.COMMIT_OPEN)
            if now < self.created_at:
                raise ValueError("commit seal predates the session")
            if now > self.reveal_deadline:
                raise ValueError("reveal window has already closed")
            self._phase = SessionPhase.REVEAL_OPEN
            self.ledger.append(
                "council.commit_phase_sealed",
                {
                    "session_id": self.session_id,
                    "committed_member_ids": sorted(self._commitments),
                    "sealed_at": now.isoformat().replace("+00:00", "Z"),
                },
            )

    def submit_reveal(
        self,
        *,
        member_id: str,
        assessment: Assessment,
        nonce: str,
        submitted_at: datetime,
    ) -> Reveal:
        now = _utc(submitted_at)
        with self._lock:
            self._require_phase(SessionPhase.REVEAL_OPEN)
            if now > self.reveal_deadline:
                raise ValueError("reveal window is closed")
            member = self._roster.get(member_id)
            if member is None:
                raise ValueError("reveal member is not in the fixed roster")
            commitment = self._commitments.get(member_id)
            if commitment is None:
                raise ValueError("reveal has no prior commitment")
            existing = self._reveals.get(member_id)
            candidate = Reveal(
                member=member,
                assessment=assessment,
                nonce=nonce,
                commitment=commitment,
            )
            candidate.verify()
            if existing is not None:
                if (
                    existing.assessment.canonical_dict() != assessment.canonical_dict()
                    or existing.nonce != nonce
                ):
                    raise ValueError("member already submitted a different reveal")
                return existing
            self._reveals[member_id] = candidate
            self.ledger.append(
                "council.reveal_submitted",
                {
                    "session_id": self.session_id,
                    "member_id": member_id,
                    "commitment_digest": commitment.digest,
                    "submitted_at": now.isoformat().replace("+00:00", "Z"),
                },
            )
            return candidate

    def decide(
        self,
        *,
        decided_at: datetime,
        spent_by_grant: Mapping[str, int] | None = None,
    ) -> DecisionRecord:
        now = _utc(decided_at)
        with self._lock:
            self._require_phase(SessionPhase.REVEAL_OPEN)
            roster_ids = set(self._roster)
            revealed_ids = set(self._reveals)
            if now < self.reveal_deadline and revealed_ids != roster_ids:
                raise ValueError("reveal window remains open for missing roster members")
            record = self._kernel.evaluate(
                self.proposal,
                tuple(self._reveals[member_id] for member_id in sorted(self._reveals)),
                self._grants,
                now=now,
                spent_by_grant=spent_by_grant,
            )
            self._decision = record
            self._phase = SessionPhase.DECIDED
            self.ledger.append(
                "council.decision_compiled",
                {
                    "session_id": self.session_id,
                    "proposal_digest": self.proposal.digest,
                    "decision": record.decision.value,
                    "decision_digest": record.decision_digest,
                    "decided_at": now.isoformat().replace("+00:00", "Z"),
                },
            )
            return record

    def close(self, *, closed_at: datetime) -> None:
        now = _utc(closed_at)
        with self._lock:
            self._require_phase(SessionPhase.DECIDED)
            assert self._decision is not None
            self._phase = SessionPhase.CLOSED
            self.ledger.append(
                "council.session_closed",
                {
                    "session_id": self.session_id,
                    "decision_digest": self._decision.decision_digest,
                    "closed_at": now.isoformat().replace("+00:00", "Z"),
                },
            )

    def snapshot(self) -> SessionSnapshot:
        with self._lock:
            roster_ids = tuple(sorted(self._roster))
            committed_ids = tuple(sorted(self._commitments))
            revealed_ids = tuple(sorted(self._reveals))
            current_reveals = tuple(
                self._reveals[member_id] for member_id in revealed_ids
            )
            current_reveal_digest = (
                reveal_set_digest(current_reveals) if current_reveals else None
            )
            decision_digest = (
                self._decision.decision_digest if self._decision is not None else None
            )
            body = {
                "session_id": self.session_id,
                "phase": self._phase.value,
                "proposal_digest": self.proposal.digest,
                "roster_member_ids": list(roster_ids),
                "committed_member_ids": list(committed_ids),
                "revealed_member_ids": list(revealed_ids),
                "commit_deadline": self.commit_deadline.isoformat().replace("+00:00", "Z"),
                "reveal_deadline": self.reveal_deadline.isoformat().replace("+00:00", "Z"),
                "reveal_set_digest": current_reveal_digest,
                "decision_digest": decision_digest,
            }
            return SessionSnapshot(
                session_id=self.session_id,
                phase=self._phase,
                proposal_digest=self.proposal.digest,
                roster_member_ids=roster_ids,
                committed_member_ids=committed_ids,
                revealed_member_ids=revealed_ids,
                commit_deadline=self.commit_deadline,
                reveal_deadline=self.reveal_deadline,
                reveal_set_digest=current_reveal_digest,
                decision_digest=decision_digest,
                snapshot_digest=sha256_text(canonical_json(body)),
            )

    def _require_phase(self, phase: SessionPhase) -> None:
        if self._phase is not phase:
            raise ValueError(
                f"session phase is {self._phase.value}; expected {phase.value}"
            )
