from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import unittest

from a11oy_council.learning import (
    LearningPromotionState,
    MetricDirection,
    NegativeCapabilityLedger,
    OutcomeContract,
    OutcomeLearningGate,
    OutcomeObservation,
    OutcomePolicy,
    OutcomeState,
    UnknownClaim,
    UnknownState,
    evaluate_outcome,
    verify_outcome_evaluation,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
DEADLINE = NOW + timedelta(hours=1)
DECISION_DIGEST = hashlib.sha256(b"decision").hexdigest()
SOURCE_DIGEST = hashlib.sha256(b"source").hexdigest()
EVIDENCE = "evidence://metric-export"


def contract(
    *,
    contract_id: str = "outcome-1",
    direction: MetricDirection = MetricDirection.AT_LEAST,
    target: float = 90.0,
    tolerance: float = 0.0,
) -> OutcomeContract:
    return OutcomeContract(
        contract_id=contract_id,
        decision_digest=DECISION_DIGEST,
        metric_name="verification_rate",
        direction=direction,
        baseline_value=70.0,
        target_value=target,
        tolerance=tolerance,
        deadline=DEADLINE,
        required_evidence=(EVIDENCE,),
    )


def observation(
    *,
    contract_id: str = "outcome-1",
    value: float | None = 95.0,
    observed_at: datetime = NOW + timedelta(minutes=30),
    evidence: tuple[str, ...] = (EVIDENCE,),
    source_digest: str | None = SOURCE_DIGEST,
    complete: bool = True,
) -> OutcomeObservation:
    return OutcomeObservation(
        contract_id=contract_id,
        observed_at=observed_at,
        value=value,
        evidence=evidence,
        source_digest=source_digest,
        complete=complete,
    )


def unknown(
    *,
    claim_id: str = "unknown-1",
    expires_at: datetime = NOW + timedelta(hours=2),
) -> UnknownClaim:
    return UnknownClaim(
        claim_id=claim_id,
        statement="Provider-side cache state has not been independently observed.",
        required_evidence=("evidence://cache-observation",),
        opened_at=NOW,
        expires_at=expires_at,
        source_decision_digest=DECISION_DIGEST,
    )


class OutcomeEvaluationTests(unittest.TestCase):
    def test_no_observation_before_deadline_is_pending(self) -> None:
        result = evaluate_outcome(contract(), None, evaluated_at=NOW)
        self.assertEqual(result.state, OutcomeState.PENDING)
        self.assertTrue(verify_outcome_evaluation(contract(), None, result))

    def test_no_observation_after_deadline_is_inconclusive(self) -> None:
        result = evaluate_outcome(
            contract(), None, evaluated_at=DEADLINE + timedelta(seconds=1)
        )
        self.assertEqual(result.state, OutcomeState.INCONCLUSIVE)

    def test_at_least_target_can_be_met(self) -> None:
        item = contract(direction=MetricDirection.AT_LEAST, target=90.0)
        result = evaluate_outcome(item, observation(value=90.0), evaluated_at=DEADLINE)
        self.assertEqual(result.state, OutcomeState.MET)

    def test_at_least_target_can_be_not_met(self) -> None:
        item = contract(direction=MetricDirection.AT_LEAST, target=90.0)
        result = evaluate_outcome(item, observation(value=89.9), evaluated_at=DEADLINE)
        self.assertEqual(result.state, OutcomeState.NOT_MET)

    def test_at_most_target_uses_tolerance(self) -> None:
        item = contract(
            direction=MetricDirection.AT_MOST,
            target=10.0,
            tolerance=0.5,
        )
        result = evaluate_outcome(item, observation(value=10.4), evaluated_at=DEADLINE)
        self.assertEqual(result.state, OutcomeState.MET)

    def test_equal_target_uses_absolute_tolerance(self) -> None:
        item = contract(
            direction=MetricDirection.EQUAL,
            target=42.0,
            tolerance=0.25,
        )
        result = evaluate_outcome(item, observation(value=42.2), evaluated_at=DEADLINE)
        self.assertEqual(result.state, OutcomeState.MET)

    def test_missing_source_digest_is_inconclusive(self) -> None:
        result = evaluate_outcome(
            contract(), observation(source_digest=None), evaluated_at=DEADLINE
        )
        self.assertEqual(result.state, OutcomeState.INCONCLUSIVE)
        self.assertTrue(any("source digest" in reason for reason in result.reasons))

    def test_missing_required_evidence_is_inconclusive(self) -> None:
        result = evaluate_outcome(
            contract(), observation(evidence=()), evaluated_at=DEADLINE
        )
        self.assertEqual(result.state, OutcomeState.INCONCLUSIVE)
        self.assertTrue(any("required outcome evidence" in reason for reason in result.reasons))

    def test_late_observation_fails_closed_by_default(self) -> None:
        late = observation(observed_at=DEADLINE + timedelta(seconds=1))
        result = evaluate_outcome(contract(), late, evaluated_at=late.observed_at)
        self.assertEqual(result.state, OutcomeState.INCONCLUSIVE)
        accepted = evaluate_outcome(
            contract(),
            late,
            evaluated_at=late.observed_at,
            policy=OutcomePolicy(accept_late_observations=True),
        )
        self.assertEqual(accepted.state, OutcomeState.MET)

    def test_future_observation_remains_pending(self) -> None:
        future = observation(observed_at=NOW + timedelta(minutes=1))
        result = evaluate_outcome(contract(), future, evaluated_at=NOW)
        self.assertEqual(result.state, OutcomeState.PENDING)
        self.assertTrue(any("after evaluation time" in reason for reason in result.reasons))
        self.assertTrue(verify_outcome_evaluation(contract(), future, result))

    def test_tampered_evaluation_is_rejected(self) -> None:
        item = contract()
        observed = observation()
        result = evaluate_outcome(item, observed, evaluated_at=DEADLINE)
        tampered = replace(result, state=OutcomeState.NOT_MET)
        self.assertFalse(verify_outcome_evaluation(item, observed, tampered))


class NegativeCapabilityTests(unittest.TestCase):
    def test_open_claim_is_reported_open(self) -> None:
        ledger = NegativeCapabilityLedger()
        ledger.open(unknown())
        self.assertEqual(ledger.state("unknown-1", at=NOW), UnknownState.OPEN)
        self.assertEqual(ledger.unresolved(at=NOW), ("unknown-1",))
        self.assertTrue(ledger.ledger.verify())

    def test_missing_evidence_does_not_resolve_claim(self) -> None:
        ledger = NegativeCapabilityLedger()
        ledger.open(unknown())
        result = ledger.resolve("unknown-1", evidence=(), resolved_at=NOW)
        self.assertEqual(result.state, UnknownState.OPEN)
        self.assertEqual(ledger.state("unknown-1", at=NOW), UnknownState.OPEN)

    def test_complete_evidence_resolves_claim(self) -> None:
        ledger = NegativeCapabilityLedger()
        ledger.open(unknown())
        result = ledger.resolve(
            "unknown-1",
            evidence=("evidence://cache-observation",),
            resolved_at=NOW + timedelta(minutes=10),
        )
        self.assertEqual(result.state, UnknownState.RESOLVED)
        self.assertEqual(
            ledger.state("unknown-1", at=NOW + timedelta(minutes=20)),
            UnknownState.RESOLVED,
        )
        self.assertEqual(ledger.unresolved(at=NOW + timedelta(minutes=20)), ())

    def test_expired_claim_cannot_be_painted_resolved(self) -> None:
        ledger = NegativeCapabilityLedger()
        ledger.open(unknown(expires_at=NOW + timedelta(minutes=5)))
        result = ledger.resolve(
            "unknown-1",
            evidence=("evidence://cache-observation",),
            resolved_at=NOW + timedelta(minutes=6),
        )
        self.assertEqual(result.state, UnknownState.EXPIRED)
        self.assertEqual(
            ledger.state("unknown-1", at=NOW + timedelta(minutes=6)),
            UnknownState.EXPIRED,
        )

    def test_claim_identifier_cannot_be_rebound(self) -> None:
        ledger = NegativeCapabilityLedger()
        ledger.open(unknown())
        altered = replace(unknown(), statement="Different unknown under the same identifier.")
        with self.assertRaises(ValueError):
            ledger.open(altered)
        self.assertEqual(len(ledger.ledger.entries), 1)


class OutcomeLearningGateTests(unittest.TestCase):
    def test_promotion_is_pending_without_evaluation(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        disposition = gate.promotion_disposition("outcome-1", evaluated_at=NOW)
        self.assertEqual(disposition.state, LearningPromotionState.PENDING)

    def test_not_met_outcome_blocks_promotion(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        gate.observe(observation(value=80.0))
        gate.evaluate("outcome-1", evaluated_at=DEADLINE)
        disposition = gate.promotion_disposition("outcome-1", evaluated_at=DEADLINE)
        self.assertEqual(disposition.state, LearningPromotionState.BLOCKED)
        self.assertTrue(any("NOT_MET" in reason for reason in disposition.reasons))

    def test_future_observation_cannot_make_candidate_eligible(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        gate.observe(observation(observed_at=NOW + timedelta(minutes=1)))
        evaluation = gate.evaluate("outcome-1", evaluated_at=NOW)
        disposition = gate.promotion_disposition("outcome-1", evaluated_at=NOW)
        self.assertEqual(evaluation.state, OutcomeState.PENDING)
        self.assertEqual(disposition.state, LearningPromotionState.PENDING)

    def test_future_evaluation_cannot_be_consumed_by_an_earlier_disposition(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        gate.observe(observation(observed_at=NOW + timedelta(minutes=1)))
        evaluation = gate.evaluate(
            "outcome-1", evaluated_at=NOW + timedelta(minutes=2)
        )
        disposition = gate.promotion_disposition("outcome-1", evaluated_at=NOW)
        self.assertEqual(evaluation.state, OutcomeState.MET)
        self.assertEqual(disposition.state, LearningPromotionState.PENDING)
        self.assertTrue(any("after promotion" in reason for reason in disposition.reasons))

    def test_unresolved_unknowns_block_promotion(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        gate.observe(observation())
        gate.evaluate("outcome-1", evaluated_at=DEADLINE)
        disposition = gate.promotion_disposition(
            "outcome-1",
            evaluated_at=DEADLINE,
            unresolved_unknowns=("unknown-1",),
        )
        self.assertEqual(disposition.state, LearningPromotionState.BLOCKED)
        self.assertTrue(any("negative-capability" in reason for reason in disposition.reasons))

    def test_policy_findings_block_promotion(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        gate.observe(observation())
        gate.evaluate("outcome-1", evaluated_at=DEADLINE)
        disposition = gate.promotion_disposition(
            "outcome-1",
            evaluated_at=DEADLINE,
            policy_findings=("finding://unresolved",),
        )
        self.assertEqual(disposition.state, LearningPromotionState.BLOCKED)
        self.assertTrue(any("policy findings" in reason for reason in disposition.reasons))

    def test_met_clean_outcome_is_eligible_and_ledger_verifies(self) -> None:
        gate = OutcomeLearningGate()
        gate.register(contract())
        gate.observe(observation())
        evaluation = gate.evaluate("outcome-1", evaluated_at=DEADLINE)
        disposition = gate.promotion_disposition("outcome-1", evaluated_at=DEADLINE)
        self.assertEqual(evaluation.state, OutcomeState.MET)
        self.assertEqual(disposition.state, LearningPromotionState.ELIGIBLE)
        self.assertTrue(gate.ledger.verify())
        self.assertEqual(len(gate.ledger.entries), 4)


if __name__ == "__main__":
    unittest.main()
