#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Acceptance suite for the A11oy Proof-to-Discovery engine (pytest, offline).

The suite has four parts:
1. RFC 8032 Ed25519 test vectors: the crypto is real, not asserted.
2. The prespecified acceptance manifest: every case fixes its expected
   verdicts, action-gate answer, and recommendation before the engine runs.
3. The zero-false-qualification sweep: across every known-invalid case, no
   corrupted, stale, model-generated, downgraded, or unregistered-signer
   record may ever contribute to a PROVEN verdict, a REFUTED verdict it did
   not honestly earn, an authorized action, or a recommendation of an
   unauthorized experiment.
4. The admission demonstration contract, including its ``--check`` gate.

Runs under pytest (as unittest cases) or ``python -m unittest``. Offline and
deterministic: no network, no clock reads, no live-estate claims.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from proof_to_discovery import cases as fixture_cases
from proof_to_discovery import ed25519
from proof_to_discovery.cases import CASE_COUNT, build_acceptance_manifest
from proof_to_discovery.demo import build_report, check_report, main as demo_main, render
from proof_to_discovery.experiments import Experiment, recommend
from proof_to_discovery.graph import GraphInvalid, Obligation, ObligationGraph, evaluate
from proof_to_discovery.policy import (
    AuthorizationGrant,
    TrustPolicy,
    check_grant,
    evaluate_action,
)
from proof_to_discovery.records import WitnessTier, check_record


class Ed25519Rfc8032Vectors(unittest.TestCase):
    """The RFC 8032 section 7.1 vectors: known keys, signatures, and rejections."""

    VECTORS = [
        (
            "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
            "",
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        ),
        (
            "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
            "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
            "72",
            "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
        ),
        (
            "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
            "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
            "af82",
            "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
            "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
        ),
    ]

    def test_public_keys_signatures_and_verification(self) -> None:
        for index, (seed_hex, public_hex, message_hex, signature_hex) in enumerate(
            self.VECTORS, start=1
        ):
            with self.subTest(vector=index):
                seed = bytes.fromhex(seed_hex)
                public = bytes.fromhex(public_hex)
                message = bytes.fromhex(message_hex)
                signature = bytes.fromhex(signature_hex)
                self.assertEqual(ed25519.public_key(seed).hex(), public.hex())
                self.assertTrue(ed25519.verify(public, message, signature))
                self.assertEqual(ed25519.sign(seed, message).hex(), signature.hex())

    def test_tampered_inputs_fail_closed(self) -> None:
        seed = bytes.fromhex(self.VECTORS[0][0])
        public = bytes.fromhex(self.VECTORS[0][1])
        message = b"proof-to-discovery"
        signature = ed25519.sign(seed, message)
        self.assertTrue(ed25519.verify(public, message, signature))
        self.assertFalse(ed25519.verify(public, b"tampered", signature))
        self.assertFalse(
            ed25519.verify(public, message, signature[:-1] + bytes([signature[-1] ^ 1]))
        )
        self.assertFalse(ed25519.verify(public[:31], message, signature))
        self.assertFalse(ed25519.verify(public, message, signature + b"\x00"))
        self.assertFalse(ed25519.verify(b"\xff" * 32, message, signature))


class AcceptanceManifest(unittest.TestCase):
    """Every prespecified case must produce exactly its expected answers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_acceptance_manifest()

    def test_manifest_is_large_enough(self) -> None:
        self.assertGreaterEqual(len(self.manifest), 100)
        self.assertEqual(CASE_COUNT, len(self.manifest))
        names = [case.name for case in self.manifest]
        self.assertEqual(len(names), len(set(names)), "case names must be unique")

    def test_case_families_are_represented(self) -> None:
        families = {case.family for case in self.manifest}
        expected = {
            "valid_positive", "refuted", "stale", "corrupted", "missing",
            "model_claim_only", "downgrade_tier", "authorization", "evsi",
        }
        self.assertEqual(families, expected)

    def test_every_case_meets_its_prespecified_expectations(self) -> None:
        for case in self.manifest:
            with self.subTest(case=case.name):
                evaluation = evaluate(case.graph, case.records, case.policy, case.evaluated_at)
                for obligation_id, expected in case.expected_verdicts.items():
                    self.assertEqual(
                        evaluation.verdicts[obligation_id].verdict,
                        expected,
                        f"{case.name}: obligation {obligation_id}",
                    )
                action = evaluate_action(
                    graph=case.graph,
                    evaluation=evaluation,
                    grant=case.grant,
                    policy=case.policy,
                    action=case.action,
                    evaluated_at=case.evaluated_at,
                )
                self.assertEqual(
                    action.may_act,
                    case.expected_may_act,
                    f"{case.name}: may_act reasons {action.reasons}",
                )
                recommendation = recommend(
                    graph=case.graph,
                    evaluation=evaluation,
                    experiments=case.experiments,
                    policy=case.policy,
                )
                recommended_id = (
                    recommendation.recommended.experiment_id
                    if recommendation.recommended is not None
                    else None
                )
                self.assertEqual(
                    recommended_id,
                    case.expected_recommendation,
                    f"{case.name}: recommendation rationale {recommendation.rationale}",
                )

    def test_evaluations_are_deterministic(self) -> None:
        for case in self.manifest[:20]:
            first = evaluate(case.graph, case.records, case.policy, case.evaluated_at)
            second = evaluate(case.graph, case.records, case.policy, case.evaluated_at)
            self.assertEqual(first.verdicts, second.verdicts)
            self.assertEqual(first.anomalies, second.anomalies)


class ZeroFalseQualification(unittest.TestCase):
    """The acceptance criterion: known-invalid evidence must never qualify.

    For every case in the manifest whose family contains known-invalid
    evidence (corrupted, stale, model_claim_only, downgrade_tier, refuted,
    and forged grants), the engine must never answer PROVEN for an
    obligation whose only honest outcome is UNRESOLVED or REFUTED, must never
    authorize an action, and must never recommend an unauthorized
    experiment.
    """

    INVALID_FAMILIES = {
        "corrupted", "stale", "model_claim_only", "downgrade_tier", "refuted",
        "authorization",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_acceptance_manifest()

    def test_no_false_qualification_across_invalid_families(self) -> None:
        checked = 0
        for case in self.manifest:
            if not case.known_invalid:
                continue
            self.assertFalse(
                case.expected_may_act,
                f"known-invalid case {case.name} expects may_act; this is a false qualification",
            )
            evaluation = evaluate(case.graph, case.records, case.policy, case.evaluated_at)
            for obligation_id, expected in case.expected_verdicts.items():
                verdict = evaluation.verdicts[obligation_id].verdict
                if expected != "PROVEN":
                    self.assertNotEqual(
                        verdict, "PROVEN", f"{case.name}: {obligation_id} falsely qualified"
                    )
                self.assertIn(verdict, {"PROVEN", "REFUTED", "UNRESOLVED"})
            action = evaluate_action(
                graph=case.graph,
                evaluation=evaluation,
                grant=case.grant,
                policy=case.policy,
                action=case.action,
                evaluated_at=case.evaluated_at,
            )
            self.assertFalse(
                action.may_act, f"{case.name}: known-invalid evidence authorized an action"
            )
            recommendation = recommend(
                graph=case.graph,
                evaluation=evaluation,
                experiments=case.experiments,
                policy=case.policy,
            )
            if recommendation.recommended is not None:
                blocked = set(recommendation.blocked_by_authorization)
                self.assertNotIn(recommendation.recommended.experiment_id, blocked)
            checked += 1
        self.assertGreaterEqual(checked, 40)

    def test_model_generated_records_are_annotations_only(self) -> None:
        graph = fixture_cases.fixture_graph()
        full = fixture_cases.full_valid_bundle()
        model_only = {
            key: replace(
                value,
                record_id=value.record_id + "-model",
                witness_tier="MODEL_GENERATED",
                signature=None,
                signer_key=None,
            )
            for key, value in full.items()
        }
        evaluation = evaluate(graph, list(model_only.values()), fixture_cases.POLICY,
                              fixture_cases.EVALUATED_AT)
        for item in evaluation.verdicts.values():
            self.assertEqual(item.verdict, "UNRESOLVED")
            self.assertEqual(item.supporting_records, ())
            self.assertTrue(any("MODEL_GENERATED" in note for note in item.notes))

    def test_unregistered_signer_never_qualifies(self) -> None:
        graph = fixture_cases.fixture_graph()
        record = fixture_cases.record(
            "r-adversarial", "adversarial-audit",
            tier="SIGNED_WITNESS", seed=fixture_cases.ADVERSARY_SEED,
        )
        evaluation = evaluate(graph, [record], fixture_cases.POLICY, fixture_cases.EVALUATED_AT)
        self.assertEqual(evaluation.verdicts["adversarial-audit"].verdict, "UNRESOLVED")
        self.assertTrue(
            any("unregistered" in note for note in evaluation.verdicts["adversarial-audit"].notes)
        )


class EngineSemantics(unittest.TestCase):
    """Structural and fail-closed semantics of the engine itself."""

    def test_graph_rejects_cycles(self) -> None:
        with self.assertRaises(GraphInvalid):
            ObligationGraph(
                decision_id="bad",
                decision_statement="Bad.",
                decision_value=1.0,
                obligations=(
                    Obligation("a", "A?", "CONTENT_HASH_BINDING", None, True, ("b",)),
                    Obligation("b", "B?", "CONTENT_HASH_BINDING", None, True, ("a",)),
                ),
            )

    def test_graph_rejects_unknown_dependency(self) -> None:
        with self.assertRaises(GraphInvalid):
            ObligationGraph(
                decision_id="bad",
                decision_statement="Bad.",
                decision_value=1.0,
                obligations=(
                    Obligation("a", "A?", "CONTENT_HASH_BINDING", None, True, ("ghost",)),
                ),
            )

    def test_graph_rejects_empty_and_duplicate_ids(self) -> None:
        with self.assertRaises(GraphInvalid):
            ObligationGraph("bad", "Bad.", 1.0, ())
        with self.assertRaises(GraphInvalid):
            ObligationGraph(
                "bad", "Bad.", 1.0,
                (Obligation("a", "A?", "CONTENT_HASH_BINDING"),
                 Obligation("a", "A again?", "CONTENT_HASH_BINDING")),
            )

    def test_graph_rejects_unknown_required_tier(self) -> None:
        with self.assertRaises(GraphInvalid):
            ObligationGraph(
                "bad", "Bad.", 1.0,
                (Obligation("a", "A?", "VIBES"),),
            )

    def test_experiment_validation_is_strict(self) -> None:
        with self.assertRaises(ValueError):
            Experiment("e1", ("a",), {}, 1.0, 0.0, True)
        with self.assertRaises(ValueError):
            Experiment("e2", (), {"a": 0.5}, 1.0, 0.0, True)
        with self.assertRaises(ValueError):
            Experiment("e3", ("a",), {"a": 1.5}, 1.0, 0.0, True)

    def test_stance_is_cryptographically_bound(self) -> None:
        signed = fixture_cases.record(
            "r-bound", "adversarial-audit", tier="SIGNED_WITNESS",
            seed=fixture_cases.WITNESS_SEED,
        )
        flipped = replace(signed, stance="refutes")
        check = check_record(
            flipped,
            required_tier=WitnessTier.SIGNED_WITNESS,
            freshness_seconds=3600,
            evaluated_at=fixture_cases.EVALUATED_AT,
            policy=fixture_cases.POLICY,
        )
        self.assertFalse(check.admissible)
        self.assertFalse(check.intact)

    def test_witness_tier_ordering(self) -> None:
        self.assertLess(WitnessTier.MODEL_GENERATED, WitnessTier.CONTENT_HASH_BINDING)
        self.assertLess(WitnessTier.CONTENT_HASH_BINDING, WitnessTier.SIGNED_WITNESS)
        self.assertLess(WitnessTier.SIGNED_WITNESS, WitnessTier.OWNER_DIRECTIVE)

    def test_grant_binding_is_cryptographically_bound(self) -> None:
        grant = AuthorizationGrant.build(
            grant_id="g1", decision_id="d1", action="act",
            granted_at="2026-11-18T05:00:00Z", expires_at="2026-11-18T07:00:00Z",
            owner_seed=fixture_cases.OWNER_SEED,
        )
        policy = TrustPolicy(frozenset(), frozenset({grant.signer_key}))
        ok, reasons = check_grant(grant, policy=policy, decision_id="d1", action="act",
                                  evaluated_at="2026-11-18T06:00:00Z")
        self.assertTrue(ok, reasons)
        tampered = replace(grant, action="other")
        ok, reasons = check_grant(tampered, policy=policy, decision_id="d1", action="other",
                                  evaluated_at="2026-11-18T06:00:00Z")
        self.assertFalse(ok)


class AdmissionDemonstration(unittest.TestCase):
    """The Flagship54-style demonstration must be honest and machine-checkable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report()

    def test_report_is_labeled_as_demonstration(self) -> None:
        self.assertTrue(self.report["demonstration"])
        self.assertIn("no live-estate claims", self.report["claims"])

    def test_check_gate_passes(self) -> None:
        problems = check_report(self.report)
        self.assertEqual(problems, [])

    def test_mix_of_proven_and_unresolved(self) -> None:
        verdicts = {name: item["verdict"] for name, item in self.report["obligations"].items()}
        self.assertIn("PROVEN", verdicts.values())
        self.assertIn("UNRESOLVED", verdicts.values())
        self.assertNotIn("REFUTED", verdicts.values())

    def test_action_refused_without_owner_grant(self) -> None:
        self.assertFalse(self.report["action"]["may_act"])
        self.assertTrue(any("not PROVEN" in reason or "authorization" in reason.lower()
                            for reason in self.report["action"]["reasons"]))

    def test_unauthorized_experiment_blocked(self) -> None:
        blocked = self.report["recommendation"]["blocked_by_authorization"]
        self.assertIn("exp-untargeted-benchmark", blocked)
        recommended = self.report["recommendation"]["recommended"]
        self.assertIsNotNone(recommended)
        self.assertNotIn(recommended["experiment_id"], blocked)

    def test_cli_check_exit_code(self) -> None:
        self.assertEqual(demo_main(["--check"]), 0)

    def test_render_mentions_missing_evidence(self) -> None:
        text = render(self.report)
        self.assertIn("UNRESOLVED", text)
        self.assertIn("DEMONSTRATION", text)
        self.assertIn("independently-recoverable", text)


if __name__ == "__main__":
    unittest.main()
