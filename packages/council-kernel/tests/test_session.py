from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from a11oy_council import (
    Assessment,
    CapabilityGrant,
    Commitment,
    CommitmentError,
    Decision,
    MemberIdentity,
    Proposal,
    RiskClass,
    Role,
    make_commitment,
)
from a11oy_council.session import CouncilSession, SessionPhase


CREATED = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
COMMIT_DEADLINE = CREATED + timedelta(minutes=10)
REVEAL_DEADLINE = CREATED + timedelta(minutes=20)
EVIDENCE = "evidence://session-proof"


def identity(role: Role, suffix: str) -> MemberIdentity:
    return MemberIdentity(
        member_id=f"member-{suffix}",
        role=role,
        operator_id=f"operator-{suffix}",
        key_id=f"key-{suffix}",
        model_lineage=f"lineage-{suffix}",
        implementation_id=f"implementation-{suffix}",
        provider_id=f"provider-{suffix}",
        retrieval_path=f"retrieval-{suffix}",
        evidence_domain=f"evidence-{suffix}",
        trust_domain=f"trust-{suffix}",
    )


def roster() -> tuple[MemberIdentity, ...]:
    return (
        identity(Role.AUTHORITY, "authority"),
        identity(Role.SENTINEL, "sentinel"),
        identity(Role.VERIFIER, "verifier"),
        identity(Role.VALUE, "value"),
    )


def proposal() -> Proposal:
    return Proposal(
        proposal_id="proposal-session",
        action="apply_patch",
        target="repo://szl-holdings/a11oy",
        capability="source.write",
        risk_class=RiskClass.B,
        estimated_cost_microunits=100,
        evidence_requirements=(EVIDENCE,),
    )


def grant() -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="grant-session",
        subject="council-session",
        capabilities=("source.write",),
        actions=("apply_patch",),
        exact_targets=("repo://szl-holdings/a11oy",),
        budget_microunits=1_000,
        expires_at=CREATED + timedelta(days=1),
    )


def assessment(
    recommendation: Decision = Decision.ACT,
    *,
    confidence: float = 0.9,
) -> Assessment:
    return Assessment(
        recommendation=recommendation,
        confidence=confidence,
        claims=("bounded session claim",),
        evidence=(EVIDENCE,),
    )


def new_session(*, members: tuple[MemberIdentity, ...] | None = None) -> CouncilSession:
    return CouncilSession(
        session_id="session-1",
        proposal=proposal(),
        roster=members or roster(),
        grants=(grant(),),
        created_at=CREATED,
        commit_deadline=COMMIT_DEADLINE,
        reveal_deadline=REVEAL_DEADLINE,
    )


def commit_all(session: CouncilSession, members: tuple[MemberIdentity, ...] | None = None):
    selected = members or roster()
    values: dict[str, tuple[Assessment, str]] = {}
    for index, member in enumerate(selected):
        item = assessment(confidence=0.96 - index * 0.02)
        nonce = f"nonce-{index}-12345678"
        session.submit_commitment(
            make_commitment(member, item, nonce),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        values[member.member_id] = (item, nonce)
    return values


def reveal_all(
    session: CouncilSession,
    values: dict[str, tuple[Assessment, str]],
) -> None:
    session.seal_commit_phase(sealed_at=CREATED + timedelta(minutes=2))
    for member_id, (item, nonce) in values.items():
        session.submit_reveal(
            member_id=member_id,
            assessment=item,
            nonce=nonce,
            submitted_at=CREATED + timedelta(minutes=3),
        )


class SessionConstructionTests(unittest.TestCase):
    def test_deadline_contract_is_strict(self) -> None:
        with self.assertRaises(ValueError):
            CouncilSession(
                session_id="invalid",
                proposal=proposal(),
                roster=roster(),
                grants=(grant(),),
                created_at=CREATED,
                commit_deadline=CREATED,
                reveal_deadline=REVEAL_DEADLINE,
            )
        with self.assertRaises(ValueError):
            CouncilSession(
                session_id="invalid",
                proposal=proposal(),
                roster=roster(),
                grants=(grant(),),
                created_at=CREATED,
                commit_deadline=COMMIT_DEADLINE,
                reveal_deadline=COMMIT_DEADLINE,
            )

    def test_roster_identity_must_be_unique(self) -> None:
        members = roster()
        with self.assertRaises(ValueError):
            new_session(members=(members[0], members[0]))


class CommitPhaseTests(unittest.TestCase):
    def test_happy_path_compiles_act(self) -> None:
        session = new_session()
        values = commit_all(session)
        reveal_all(session, values)
        record = session.decide(decided_at=CREATED + timedelta(minutes=4))
        self.assertEqual(record.decision, Decision.ACT)
        self.assertEqual(session.phase, SessionPhase.DECIDED)
        snapshot = session.snapshot()
        self.assertEqual(snapshot.decision_digest, record.decision_digest)
        self.assertEqual(len(snapshot.revealed_member_ids), 4)
        self.assertTrue(session.ledger.verify())

    def test_unknown_member_commitment_is_rejected(self) -> None:
        session = new_session()
        outsider = identity(Role.VALUE, "outsider")
        item = assessment()
        with self.assertRaises(ValueError):
            session.submit_commitment(
                make_commitment(outsider, item, "nonce-outsider-123456"),
                submitted_at=CREATED + timedelta(minutes=1),
            )

    def test_commitment_rebinding_is_rejected(self) -> None:
        session = new_session()
        member = roster()[0]
        first = assessment()
        session.submit_commitment(
            make_commitment(member, first, "nonce-first-123456"),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        session.submit_commitment(
            make_commitment(member, first, "nonce-first-123456"),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        with self.assertRaises(ValueError):
            session.submit_commitment(
                make_commitment(member, assessment(Decision.BLOCK), "nonce-second-123456"),
                submitted_at=CREATED + timedelta(minutes=1),
            )
        self.assertEqual(len(session.commitments), 1)

    def test_late_commitment_is_rejected(self) -> None:
        session = new_session()
        member = roster()[0]
        item = assessment()
        with self.assertRaises(ValueError):
            session.submit_commitment(
                make_commitment(member, item, "nonce-late-12345678"),
                submitted_at=COMMIT_DEADLINE + timedelta(microseconds=1),
            )


class RevealPhaseTests(unittest.TestCase):
    def test_reveal_before_seal_is_rejected(self) -> None:
        session = new_session()
        member = roster()[0]
        item = assessment()
        nonce = "nonce-before-123456"
        session.submit_commitment(
            make_commitment(member, item, nonce),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        with self.assertRaises(ValueError):
            session.submit_reveal(
                member_id=member.member_id,
                assessment=item,
                nonce=nonce,
                submitted_at=CREATED + timedelta(minutes=2),
            )

    def test_reveal_without_commitment_is_rejected(self) -> None:
        session = new_session()
        session.seal_commit_phase(sealed_at=CREATED + timedelta(minutes=2))
        member = roster()[0]
        with self.assertRaises(ValueError):
            session.submit_reveal(
                member_id=member.member_id,
                assessment=assessment(),
                nonce="nonce-missing-123456",
                submitted_at=CREATED + timedelta(minutes=3),
            )

    def test_commitment_mismatch_reveal_is_rejected(self) -> None:
        session = new_session()
        member = roster()[0]
        committed = assessment()
        nonce = "nonce-match-12345678"
        session.submit_commitment(
            make_commitment(member, committed, nonce),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        session.seal_commit_phase(sealed_at=CREATED + timedelta(minutes=2))
        with self.assertRaises(CommitmentError):
            session.submit_reveal(
                member_id=member.member_id,
                assessment=assessment(Decision.BLOCK),
                nonce=nonce,
                submitted_at=CREATED + timedelta(minutes=3),
            )

    def test_reveal_rebinding_is_rejected(self) -> None:
        session = new_session()
        member = roster()[0]
        item = assessment()
        nonce = "nonce-reveal-123456"
        session.submit_commitment(
            make_commitment(member, item, nonce),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        session.seal_commit_phase(sealed_at=CREATED + timedelta(minutes=2))
        first = session.submit_reveal(
            member_id=member.member_id,
            assessment=item,
            nonce=nonce,
            submitted_at=CREATED + timedelta(minutes=3),
        )
        second = session.submit_reveal(
            member_id=member.member_id,
            assessment=item,
            nonce=nonce,
            submitted_at=CREATED + timedelta(minutes=3),
        )
        self.assertIs(first, second)
        with self.assertRaises((CommitmentError, ValueError)):
            session.submit_reveal(
                member_id=member.member_id,
                assessment=assessment(Decision.ESCALATE),
                nonce=nonce,
                submitted_at=CREATED + timedelta(minutes=3),
            )

    def test_late_reveal_is_rejected(self) -> None:
        session = new_session()
        member = roster()[0]
        item = assessment()
        nonce = "nonce-late-reveal-123456"
        session.submit_commitment(
            make_commitment(member, item, nonce),
            submitted_at=CREATED + timedelta(minutes=1),
        )
        session.seal_commit_phase(sealed_at=CREATED + timedelta(minutes=2))
        with self.assertRaises(ValueError):
            session.submit_reveal(
                member_id=member.member_id,
                assessment=item,
                nonce=nonce,
                submitted_at=REVEAL_DEADLINE + timedelta(microseconds=1),
            )


class DecisionLifecycleTests(unittest.TestCase):
    def test_early_decision_waits_for_fixed_roster(self) -> None:
        session = new_session()
        selected = roster()[:3]
        values = commit_all(session, selected)
        reveal_all(session, values)
        with self.assertRaises(ValueError):
            session.decide(decided_at=CREATED + timedelta(minutes=4))

    def test_deadline_decision_with_missing_role_escalates(self) -> None:
        session = new_session()
        selected = roster()[:3]
        values = commit_all(session, selected)
        reveal_all(session, values)
        record = session.decide(decided_at=REVEAL_DEADLINE)
        self.assertEqual(record.decision, Decision.ESCALATE)
        self.assertTrue(any("VALUE" in reason for reason in record.reasons))

    def test_close_requires_decision_and_is_terminal(self) -> None:
        session = new_session()
        with self.assertRaises(ValueError):
            session.close(closed_at=CREATED + timedelta(minutes=1))
        values = commit_all(session)
        reveal_all(session, values)
        session.decide(decided_at=CREATED + timedelta(minutes=4))
        session.close(closed_at=CREATED + timedelta(minutes=5))
        self.assertEqual(session.phase, SessionPhase.CLOSED)
        with self.assertRaises(ValueError):
            session.decide(decided_at=CREATED + timedelta(minutes=6))

    def test_snapshot_digest_and_ledger_are_deterministic(self) -> None:
        first = new_session()
        second = new_session(members=tuple(reversed(roster())))
        self.assertEqual(first.snapshot().snapshot_digest, second.snapshot().snapshot_digest)
        self.assertEqual(first.snapshot(), first.snapshot())
        self.assertTrue(first.ledger.verify())
        self.assertEqual(len(first.ledger.entries), 1)


if __name__ == "__main__":
    unittest.main()
