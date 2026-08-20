from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import unittest

from a11oy_council import (
    ActionStatus,
    Assessment,
    CapabilityGrant,
    CouncilKernel,
    CouncilPolicy,
    Decision,
    HashChainLedger,
    LedgerIntegrityError,
    MemberIdentity,
    Proposal,
    Reveal,
    RiskClass,
    Role,
    SignatureState,
    make_commitment,
    measure_diversity,
    reveal_set_digest,
    seal_action_receipt,
    verify_action_receipt,
)
from a11oy_council.kernel import canonical_json, sha256_text


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
REQUIRED_EVIDENCE = "evidence://required"


def member(role: Role, suffix: str, *, correlated: bool = False) -> MemberIdentity:
    axis = "shared" if correlated else suffix
    return MemberIdentity(
        member_id=f"member-{suffix}",
        role=role,
        operator_id=f"operator-{axis}",
        key_id=f"key-{axis}",
        model_lineage=f"lineage-{axis}",
        implementation_id=f"implementation-{axis}",
        provider_id=f"provider-{axis}",
        retrieval_path=f"retrieval-{axis}",
        evidence_domain=f"evidence-{axis}",
        trust_domain=f"trust-{axis}",
    )


def assessment(
    recommendation: Decision = Decision.ACT,
    *,
    confidence: float = 0.9,
    veto: bool = False,
    evidence: tuple[str, ...] = (REQUIRED_EVIDENCE,),
    objections: tuple[str, ...] = (),
) -> Assessment:
    return Assessment(
        recommendation=recommendation,
        confidence=confidence,
        claims=("bounded claim",),
        evidence=evidence,
        objections=objections,
        veto=veto,
    )


def reveal(identity: MemberIdentity, value: Assessment, nonce: str) -> Reveal:
    return Reveal(
        member=identity,
        assessment=value,
        nonce=nonce,
        commitment=make_commitment(identity, value, nonce),
    )


def proposal(
    *,
    target: str = "repo://szl-holdings/a11oy",
    risk_class: RiskClass = RiskClass.B,
    cost: int = 100,
) -> Proposal:
    return Proposal(
        proposal_id="proposal-1",
        action="apply_patch",
        target=target,
        capability="source.write",
        risk_class=risk_class,
        estimated_cost_microunits=cost,
        evidence_requirements=(REQUIRED_EVIDENCE,),
    )


def grant(*, target: str = "repo://szl-holdings/a11oy", budget: int = 1_000) -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="grant-1",
        subject="council-alpha",
        capabilities=("source.write",),
        actions=("apply_patch",),
        exact_targets=(target,),
        budget_microunits=budget,
        expires_at=NOW + timedelta(days=1),
    )


def four_reveals(
    *,
    correlated: bool = False,
    value_assessment: Assessment | None = None,
    sentinel_assessment: Assessment | None = None,
    verifier_assessment: Assessment | None = None,
    authority_assessment: Assessment | None = None,
) -> tuple[Reveal, ...]:
    identities = (
        member(Role.AUTHORITY, "authority", correlated=correlated),
        member(Role.SENTINEL, "sentinel", correlated=correlated),
        member(Role.VERIFIER, "verifier", correlated=correlated),
        member(Role.VALUE, "value", correlated=correlated),
    )
    values = (
        authority_assessment or assessment(confidence=0.96),
        sentinel_assessment or assessment(confidence=0.94),
        verifier_assessment or assessment(confidence=0.92),
        value_assessment or assessment(confidence=0.82),
    )
    return tuple(
        reveal(identity, value, f"nonce-{index}-123456")
        for index, (identity, value) in enumerate(zip(identities, values, strict=True))
    )


class CouncilKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kernel = CouncilKernel()

    def test_independent_council_can_act(self) -> None:
        record = self.kernel.evaluate(
            proposal(), four_reveals(), (grant(),), now=NOW
        )
        self.assertEqual(record.decision, Decision.ACT)
        self.assertEqual(record.grant_id, "grant-1")
        self.assertEqual(record.diversity.effective_size, 4.0)
        self.assertGreaterEqual(record.score, 0.99)
        self.assertEqual(len(record.decision_digest), 64)

    def test_sentinel_veto_is_categorical(self) -> None:
        record = self.kernel.evaluate(
            proposal(),
            four_reveals(
                sentinel_assessment=assessment(
                    Decision.BLOCK,
                    confidence=1.0,
                    veto=True,
                    objections=("unsafe postcondition",),
                )
            ),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertTrue(any("SENTINEL veto" in reason for reason in record.reasons))

    def test_verifier_veto_is_categorical(self) -> None:
        record = self.kernel.evaluate(
            proposal(),
            four_reveals(
                verifier_assessment=assessment(
                    Decision.BLOCK,
                    confidence=1.0,
                    veto=True,
                    objections=("evidence cannot be reproduced",),
                )
            ),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertTrue(any("VERIFIER veto" in reason for reason in record.reasons))

    def test_authority_denial_blocks(self) -> None:
        record = self.kernel.evaluate(
            proposal(),
            four_reveals(
                authority_assessment=assessment(
                    Decision.BLOCK,
                    confidence=1.0,
                    objections=("mandate absent",),
                )
            ),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertTrue(any("Authority mandate denied" in reason for reason in record.reasons))

    def test_correlated_agreement_escalates(self) -> None:
        reveals = four_reveals(correlated=True)
        diversity = measure_diversity(tuple(item.member for item in reveals))
        self.assertEqual(diversity.effective_size, 1.0)
        record = self.kernel.evaluate(proposal(), reveals, (grant(),), now=NOW)
        self.assertEqual(record.decision, Decision.ESCALATE)
        self.assertTrue(any("independence threshold" in reason for reason in record.reasons))

    def test_exact_target_mismatch_blocks(self) -> None:
        record = self.kernel.evaluate(
            proposal(target="repo://szl-holdings/other"),
            four_reveals(),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertTrue(any("exactly match" in reason for reason in record.reasons))

    def test_budget_overrun_blocks(self) -> None:
        record = self.kernel.evaluate(
            proposal(cost=1_001), four_reveals(), (grant(budget=1_000),), now=NOW
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertTrue(any("budget" in reason for reason in record.reasons))

    def test_high_risk_escalates_and_class_d_blocks(self) -> None:
        class_c = self.kernel.evaluate(
            proposal(risk_class=RiskClass.C), four_reveals(), (grant(),), now=NOW
        )
        class_d = self.kernel.evaluate(
            proposal(risk_class=RiskClass.D), four_reveals(), (grant(),), now=NOW
        )
        self.assertEqual(class_c.decision, Decision.ESCALATE)
        self.assertEqual(class_d.decision, Decision.BLOCK)

    def test_missing_role_escalates(self) -> None:
        record = self.kernel.evaluate(
            proposal(), four_reveals()[:-1], (grant(),), now=NOW
        )
        self.assertEqual(record.decision, Decision.ESCALATE)
        self.assertTrue(any("VALUE" in reason for reason in record.reasons))

    def test_missing_evidence_escalates(self) -> None:
        record = self.kernel.evaluate(
            proposal(),
            four_reveals(value_assessment=assessment(evidence=())),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.ESCALATE)
        self.assertTrue(any("required evidence" in reason for reason in record.reasons))

    def test_commitment_mismatch_blocks(self) -> None:
        valid = four_reveals()
        original = valid[1]
        tampered_assessment = assessment(Decision.BLOCK, veto=True)
        tampered = Reveal(
            member=original.member,
            assessment=tampered_assessment,
            nonce=original.nonce,
            commitment=original.commitment,
        )
        record = self.kernel.evaluate(
            proposal(),
            (valid[0], tampered, valid[2], valid[3]),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertTrue(any("invalid commitment" in reason for reason in record.reasons))

    def test_duplicate_member_identity_returns_auditable_block(self) -> None:
        valid = four_reveals()
        duplicate = reveal(
            valid[0].member,
            assessment(),
            "duplicate-member-nonce-123456",
        )
        record = self.kernel.evaluate(
            proposal(),
            (valid[0], duplicate, valid[2], valid[3]),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertEqual(record.diversity.effective_size, 0.0)
        self.assertEqual(
            [result.member_id for result in record.member_results].count(
                valid[0].member.member_id
            ),
            2,
        )
        self.assertTrue(any("duplicate Council member" in reason for reason in record.reasons))
        self.assertEqual(len(record.decision_digest), 64)

    def test_minority_truth_is_retained(self) -> None:
        dissent = assessment(
            Decision.ESCALATE,
            confidence=0.8,
            objections=("value estimate remains uncertain",),
        )
        record = self.kernel.evaluate(
            proposal(),
            four_reveals(value_assessment=dissent),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(record.decision, Decision.ACT)
        self.assertEqual(len(record.minority_reports), 1)
        self.assertEqual(record.minority_reports[0].role, Role.VALUE)
        self.assertIn("value estimate remains uncertain", record.minority_reports[0].objections)

    def test_reveal_set_digest_is_order_independent(self) -> None:
        reveals = four_reveals()
        self.assertEqual(reveal_set_digest(reveals), reveal_set_digest(reversed(reveals)))

    def test_policy_can_require_more_independence(self) -> None:
        kernel = CouncilKernel(CouncilPolicy(minimum_effective_size=4.1))
        record = kernel.evaluate(proposal(), four_reveals(), (grant(),), now=NOW)
        self.assertEqual(record.decision, Decision.ESCALATE)


class LedgerTests(unittest.TestCase):
    def test_memory_and_disk_ledgers_verify(self) -> None:
        memory = HashChainLedger()
        memory.append("proposal", {"id": "p1"})
        memory.append("decision", {"decision": "ACT"})
        self.assertTrue(memory.verify())
        self.assertEqual(memory.entries[1].previous_hash, memory.entries[0].entry_hash)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "council.jsonl"
            disk = HashChainLedger(path)
            disk.append("proposal", {"id": "p1"})
            disk.append("decision", {"decision": "ACT"})
            self.assertTrue(disk.verify())
            reloaded = HashChainLedger(path)
            self.assertTrue(reloaded.verify())
            self.assertEqual(reloaded.entries, disk.entries)

    def test_disk_tamper_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "council.jsonl"
            ledger = HashChainLedger(path)
            ledger.append("decision", {"decision": "ACT"})
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["payload"]["decision"] = "BLOCK"
            path.write_text(json.dumps(raw, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaises(LedgerIntegrityError):
                HashChainLedger(path)


class _HmacSigner:
    def __init__(self, key: bytes) -> None:
        self._key = key
        self._key_id = "test-key"

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, payload: bytes) -> str:
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()


class _HmacVerifier:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def verify(self, key_id: str, payload: bytes, signature: str) -> bool:
        if key_id != "test-key":
            return False
        expected = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class ReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proposal = proposal()
        self.decision = CouncilKernel().evaluate(
            self.proposal, four_reveals(), (grant(),), now=NOW
        )

    def test_unsigned_receipt_is_labeled_unsigned(self) -> None:
        envelope = seal_action_receipt(
            proposal=self.proposal,
            decision=self.decision,
            status=ActionStatus.APPLIED,
            preconditions=("exact head matched",),
            postconditions=("tests passed",),
            observed_at=NOW,
        )
        self.assertEqual(envelope.signature_state, SignatureState.UNSIGNED)
        self.assertIsNone(envelope.key_id)
        self.assertIsNone(envelope.signature)
        self.assertTrue(verify_action_receipt(envelope))

    def test_signed_receipt_requires_verification(self) -> None:
        key = os.urandom(32)
        signer = _HmacSigner(key)
        envelope = seal_action_receipt(
            proposal=self.proposal,
            decision=self.decision,
            status=ActionStatus.APPLIED,
            preconditions=("exact head matched",),
            postconditions=("tests passed",),
            observed_at=NOW,
            signer=signer,
        )
        self.assertEqual(envelope.signature_state, SignatureState.SIGNED)
        self.assertFalse(verify_action_receipt(envelope))
        self.assertTrue(verify_action_receipt(envelope, _HmacVerifier(key)))
        self.assertFalse(verify_action_receipt(envelope, _HmacVerifier(os.urandom(32))))

    def test_receipt_rejects_a_decision_for_another_proposal(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not authorize this proposal"):
            seal_action_receipt(
                proposal=proposal(target="repo://szl-holdings/other"),
                decision=self.decision,
                status=ActionStatus.APPLIED,
                preconditions=("exact head matched",),
                postconditions=("tests passed",),
                observed_at=NOW,
            )

    def test_applied_receipt_requires_act_decision(self) -> None:
        blocked_proposal = proposal(target="repo://szl-holdings/other")
        blocked_decision = CouncilKernel().evaluate(
            blocked_proposal,
            four_reveals(),
            (grant(),),
            now=NOW,
        )
        self.assertEqual(blocked_decision.decision, Decision.BLOCK)
        with self.assertRaisesRegex(ValueError, "requires an ACT decision"):
            seal_action_receipt(
                proposal=blocked_proposal,
                decision=blocked_decision,
                status=ActionStatus.APPLIED,
                preconditions=("exact head matched",),
                postconditions=("action was not authorized",),
                observed_at=NOW,
            )

    def test_applied_receipt_rejects_tampered_decision_state(self) -> None:
        blocked_proposal = proposal(target="repo://szl-holdings/other")
        blocked_decision = CouncilKernel().evaluate(
            blocked_proposal,
            four_reveals(),
            (grant(),),
            now=NOW,
        )
        tampered = replace(blocked_decision, decision=Decision.ACT)
        with self.assertRaisesRegex(ValueError, "digest does not verify"):
            seal_action_receipt(
                proposal=blocked_proposal,
                decision=tampered,
                status=ActionStatus.APPLIED,
                preconditions=("exact head matched",),
                postconditions=("action was not authorized",),
                observed_at=NOW,
            )

    def test_verifier_rejects_signed_applied_receipt_for_block_decision(self) -> None:
        key = os.urandom(32)
        signer = _HmacSigner(key)
        envelope = seal_action_receipt(
            proposal=self.proposal,
            decision=self.decision,
            status=ActionStatus.APPLIED,
            preconditions=("exact head matched",),
            postconditions=("tests passed",),
            observed_at=NOW,
            signer=signer,
        )
        payload = {**envelope.payload, "decision": Decision.BLOCK.value}
        payload_bytes = canonical_json(payload).encode("utf-8")
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()
        signature = signer.sign(payload_bytes)
        receipt_body = {
            "payload": payload,
            "payload_digest": payload_digest,
            "signature_state": SignatureState.SIGNED.value,
            "key_id": signer.key_id,
            "signature": signature,
        }
        contradictory = replace(
            envelope,
            payload=payload,
            payload_digest=payload_digest,
            signature=signature,
            receipt_digest=sha256_text(canonical_json(receipt_body)),
        )

        self.assertFalse(verify_action_receipt(contradictory, _HmacVerifier(key)))

    def test_verifier_returns_false_for_malformed_envelope(self) -> None:
        envelope = seal_action_receipt(
            proposal=self.proposal,
            decision=self.decision,
            status=ActionStatus.APPLIED,
            preconditions=("exact head matched",),
            postconditions=("tests passed",),
            observed_at=NOW,
        )
        malformed = replace(envelope, payload_digest=None)  # type: ignore[arg-type]
        self.assertFalse(verify_action_receipt(malformed))


if __name__ == "__main__":
    unittest.main()
