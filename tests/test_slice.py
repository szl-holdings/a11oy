#!/usr/bin/env python3
"""Unit tests for the a11oy v1 slice. Stdlib unittest only (no pytest).

Run from the repo root:

    python3 -m unittest discover -s tests -v

Each test names the CANON law or wedge guarantee it pins down.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from a11oy.flight_recorder import HEADER_LEN, SegmentedFlightRecorder
from a11oy.policy import Effect, Rule, TypedPolicyEngine
from a11oy.schemas import (
    Actor,
    Completeness,
    EvidenceItem,
    GovernedActionPredicate,
    GovernedActionReceipt,
    HumanApproval,
    ObservationWindow,
    PolicyDecisionRecord,
    RedactionCommitment,
    SideEffectClass,
)
from a11oy.signing import DemoEd25519Backend
from a11oy.verifier import ClaimState, OfflineVerifier, TimeStrength

import szl_miniyaml


def _receipt(evidence_kinds=("git-diff-hash",), side_effect=SideEffectClass.REVERSIBLE):
    evidence = [
        EvidenceItem(
            evidence_id=f"ev-{k}",
            kind=k,
            sha256=hashlib.sha256(k.encode()).hexdigest(),
        )
        for k in evidence_kinds
    ]
    actor = Actor(actor_id="u-stephen-lutar", display_name="Stephen Lutar")
    predicate = GovernedActionPredicate(
        action_id="act-test-1",
        actor=actor,
        action_type="deploy.patch",
        side_effect_class=side_effect,
        evidence=evidence,
        completeness=Completeness.COMPLETE if evidence else Completeness.INCOMPLETE,
        redaction_commitments=[],
        rfc3161_token="UNAVAILABLE",
        ntp_synced=False,
    )
    now = datetime.now(timezone.utc)
    return GovernedActionReceipt(
        receipt_id="rcpt-test-1",
        predicate=predicate,
        decision=PolicyDecisionRecord(
            decision="ALLOW",
            reason="allowed by first matching rule allow-deploy",
            first_match_rule="allow-deploy",
            matched_rules=["allow-deploy"],
            evidence_obligations=["git-diff-hash"],
            effective_side_effect_class=side_effect,
            requires_human_approval=True,
        ),
        human_approval=HumanApproval(
            approver=actor, approved_at=now, rationale="reviewed"
        ),
        observation_window=ObservationWindow(
            start=now, end=now + timedelta(minutes=30)
        ),
        retention_days=180,
        issued_at=now,
        generator="a11oy-test/0.1.0",
    )


class TestPolicyEngine(unittest.TestCase):
    def test_law2_default_deny(self):
        engine = TypedPolicyEngine([])
        decision = engine.evaluate(
            action_type="anything", side_effect_class=SideEffectClass.READ_ONLY
        )
        self.assertFalse(decision.allowed)
        self.assertIsNone(decision.first_match_rule)

    def test_first_match_wins_and_obligations_accumulate(self):
        engine = TypedPolicyEngine(
            [
                Rule("r1", Effect.ALLOW, ("a.b",), evidence_obligations=("o1",)),
                Rule("r2", Effect.DENY, ("a.*",), evidence_obligations=("o2",)),
            ]
        )
        decision = engine.evaluate(
            action_type="a.b", side_effect_class=SideEffectClass.READ_ONLY
        )
        self.assertTrue(decision.allowed)  # first match wins
        self.assertEqual(decision.first_match_rule, "r1")
        self.assertEqual(set(decision.evidence_obligations), {"o1", "o2"})  # all matched

    def test_law6_most_restrictive_and_irreversible_approval(self):
        engine = TypedPolicyEngine(
            [
                Rule(
                    "guard",
                    Effect.ALLOW,
                    ("deploy.*",),
                    side_effect_classes=(
                        SideEffectClass.REVERSIBLE,
                        SideEffectClass.IRREVERSIBLE,
                    ),
                )
            ]
        )
        decision = engine.evaluate(
            action_type="deploy.patch",
            side_effect_class=SideEffectClass.REVERSIBLE,
        )
        self.assertIs(
            decision.effective_side_effect_class, SideEffectClass.IRREVERSIBLE
        )
        self.assertTrue(decision.requires_human_approval)


class TestSchemas(unittest.TestCase):
    def test_law3_service_account_structurally_impossible(self):
        with self.assertRaises(Exception):
            Actor(actor_id="svc", display_name="bot", is_service_account=True)

    def test_law4_empty_evidence_cannot_be_complete(self):
        actor = Actor(actor_id="u1", display_name="Person One")
        with self.assertRaises(Exception):
            GovernedActionPredicate(
                action_id="a1",
                actor=actor,
                action_type="t",
                side_effect_class=SideEffectClass.READ_ONLY,
                evidence=[],
                completeness=Completeness.COMPLETE,
                redaction_commitments=[],
                rfc3161_token="UNAVAILABLE",
                ntp_synced=False,
            )

    def test_retention_floor_180_days(self):
        receipt = _receipt()
        data = receipt.model_dump(mode="json")
        data["retention_days"] = 30
        with self.assertRaises(Exception):
            GovernedActionReceipt.model_validate(data)


class TestVerifierAndSigning(unittest.TestCase):
    def setUp(self):
        self.backend = DemoEd25519Backend()
        self.verifier = OfflineVerifier({self.backend.keyid: self.backend.public_key_raw})

    def test_valid_receipt_passes(self):
        envelope = self.backend.sign(_receipt().model_dump(mode="json"))
        result = self.verifier.verify_envelope(
            envelope, required_obligations=("git-diff-hash",)
        )
        self.assertEqual(result.verdict, "VALID")
        self.assertIs(result.time_strength, TimeStrength.WEAK)  # disclosed, not hidden

    def test_one_byte_tamper_fails_offline_verification(self):
        envelope = self.backend.sign(_receipt().model_dump(mode="json"))
        raw = bytearray(base64.b64decode(envelope["payload"]))
        raw[10] ^= 0x01
        envelope["payload"] = base64.b64encode(bytes(raw)).decode("ascii")
        result = self.verifier.verify_envelope(envelope)
        self.assertFalse(result.signature_valid)
        self.assertEqual(result.verdict, "INVALID")

    def test_law4_missing_evidence_is_incomplete_never_pass(self):
        envelope = self.backend.sign(_receipt(evidence_kinds=()).model_dump(mode="json"))
        result = self.verifier.verify_envelope(
            envelope, required_obligations=("git-diff-hash",)
        )
        self.assertTrue(result.signature_valid)  # Law 5: signature is not truth
        self.assertIs(result.claim_state, ClaimState.INCOMPLETE)
        self.assertEqual(result.verdict, "INCOMPLETE")

    def test_law5_valid_signature_does_not_imply_true_claim(self):
        receipt = _receipt()
        data = receipt.model_dump(mode="json")
        data["predicate"]["evidence"] = []  # strip evidence
        data["predicate"]["completeness"] = "INCOMPLETE"
        envelope = self.backend.sign(data)
        result = self.verifier.verify_envelope(
            envelope, required_obligations=("git-diff-hash",)
        )
        self.assertTrue(result.signature_valid)
        self.assertNotEqual(result.verdict, "VALID")

    def test_law3_verifier_fails_service_account_actor(self):
        data = _receipt().model_dump(mode="json")
        data["predicate"]["actor"]["is_service_account"] = True
        envelope = self.backend.sign(data)
        result = self.verifier.verify_envelope(envelope)
        self.assertIs(result.claim_state, ClaimState.FAIL)


class TestFlightRecorder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "log.a11yfr"

    def tearDown(self):
        self.tmp.cleanup()

    def test_law7_local_ack_pending_sync_and_header(self):
        recorder = SegmentedFlightRecorder(self.path)
        ack = recorder.append({"x": 1}, idempotency_key="k1")
        self.assertEqual(ack.durability, "LOCAL")
        self.assertEqual(ack.sync_state, "PENDING_SYNC")
        self.assertEqual(self.path.read_bytes()[:8], b"A11YFR01")
        self.assertEqual(HEADER_LEN, 24)
        self.assertEqual(recorder.pending_sync(), [1])
        recorder.mark_synced([1])
        self.assertEqual(recorder.pending_sync(), [])

    def test_law8_replay_never_double_executes(self):
        recorder = SegmentedFlightRecorder(self.path)
        recorder.append({"x": 1}, idempotency_key="k1")
        recorder.append({"x": 2}, idempotency_key="k2")
        first = [p["idempotency_key"] for p in recorder.replay({"k1"})]
        self.assertEqual(first, ["k2"])
        second = list(recorder.replay({"k1", "k2"}))
        self.assertEqual(second, [])

    def test_integrity_reports_gaps_and_corruptions(self):
        recorder = SegmentedFlightRecorder(self.path)
        recorder.append({"x": 1}, idempotency_key="k1")
        recorder.append({"x": 2}, idempotency_key="k2")
        report = recorder.verify_integrity()
        self.assertTrue(report.chain_ok)
        self.assertEqual((report.first_seq, report.last_seq), (1, 2))
        data = bytearray(self.path.read_bytes())
        data[-3] ^= 0xFF
        self.path.write_bytes(bytes(data))
        bad = SegmentedFlightRecorder(self.path).verify_integrity()
        self.assertFalse(bad.chain_ok)
        self.assertTrue(bad.corruptions)


class TestMiniYaml(unittest.TestCase):
    def test_round_trip(self):
        doc = {
            "yaml_subset": "SZL-YAML-1",
            "rows": [
                {"id": "a", "state": "UNKNOWN", "value": None, "blocks": True},
                {"id": "b", "note": "has: colon", "n": 180, "f": 1.5},
            ],
        }
        self.assertEqual(szl_miniyaml.load(szl_miniyaml.dump(doc)), doc)


class TestRedactionCommitment(unittest.TestCase):
    def test_commitment_verifies_and_rejects(self):
        salt = os.urandom(16)
        commitment = RedactionCommitment.create(
            "rc1", "$.predicate.action_id", b"plaintext", salt
        )
        self.assertTrue(commitment.verify(b"plaintext"))
        self.assertFalse(commitment.verify(b"forged"))


if __name__ == "__main__":
    unittest.main()
