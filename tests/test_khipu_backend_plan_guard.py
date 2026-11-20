# SPDX-License-Identifier: Apache-2.0
"""In-process Khipu backend integration tests; no provider or network."""
from __future__ import annotations

import asyncio
import copy
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ayllu import backend
from tests.test_khipu_plan_guard import fixture, QUERY, N1


class KhipuBackendGuard(unittest.TestCase):
    def _simulate(self, plan, *, broken_evidence=False):
        _, handles, evidence = fixture()
        if broken_evidence:
            evidence[0]["sha256"] = "f" * 64
        grounding = {
            "schema": "szl.brain.navigator-context/v1",
            "state": "GROUNDED_HANDLES_READY",
            "ready": True,
            "content_access": "HANDLES_ONLY",
            "handles": handles,
            "evidence": evidence,
        }

        async def fake_model_complete(_messages, **_kwargs):
            return {
                "text": json.dumps(plan, sort_keys=True, separators=(",", ":")),
                "model": "khipu:latest",
                "stub": False,
                "model_attestation": {"served_model": "khipu:latest"},
                "honesty": "proposal only",
            }

        fake = SimpleNamespace(
            agent_rag_context=lambda *_args, **_kwargs: copy.deepcopy(grounding),
            agent_model_complete=fake_model_complete,
        )
        with patch.dict(sys.modules, {"a11oy_code_orchestrator": fake}):
            return asyncio.run(backend.model_complete(
                "system", QUERY, persona="Maskaq", max_tokens=600,
            ))

    def test_valid_navigation_emits_only_structural_honesty(self):
        plan, *_ = fixture()
        result = self._simulate(plan)
        self.assertFalse(result["stub"])
        self.assertEqual(result["grounding"]["citation_validation"]["state"],
                         "CITATIONS_WITHIN_OFFERED_HANDLES")
        check = result["grounding"]["plan_invariants"]
        self.assertTrue(check["admitted_structure"])
        self.assertFalse(check["semantic_relevance_verified"])
        self.assertFalse(check["execution_authorized"])
        self.assertFalse(check["signer_verified"])

    def test_valid_abstention_no_citations_or_actions(self):
        plan, *_ = fixture()
        plan.update(decision="ABSTAIN", steps=[], citedNodeIds=[],
                    abstainReason="No source supports this question")
        result = self._simulate(plan)
        self.assertFalse(result["stub"])
        self.assertEqual(result["grounding"]["citation_validation"]["cited_node_ids"], [])
        self.assertEqual(result["grounding"]["plan_invariants"]["admitted_structure"], True)

    def test_wrong_decision_or_proof_must_refuse_model_text(self):
        for case in ("NAVIGATE_WITH_NO_CITES", "ABSTAIN_WITH_STEPS",
                     "DIGEST_CONFLICT", "QUERY_TAMPER"):
            with self.subTest(case=case):
                plan, *_ = fixture()
                broken = False
                if case == "NAVIGATE_WITH_NO_CITES":
                    plan["citedNodeIds"] = []
                    plan["steps"] = []
                elif case == "ABSTAIN_WITH_STEPS":
                    plan.update(decision="ABSTAIN", citedNodeIds=[],
                                abstainReason="No source")
                elif case == "DIGEST_CONFLICT":
                    broken = True
                else:
                    plan["query"] = "fabricated question"
                result = self._simulate(plan, broken_evidence=broken)
                self.assertIsNone(result["text"])
                self.assertTrue(result["stub"])
                self.assertEqual(
                    result["grounding"]["citation_validation"]["state"],
                    "KHIPU_PLAN_INVARIANT_REFUSED",
                )
                self.assertFalse(
                    result["grounding"]["plan_invariants"]["admitted_structure"]
                )
                self.assertEqual(len(result["raw_model_output_sha256"]), 64)

    def test_unstructured_khipu_response_never_becomes_grounded_answer(self):
        for answer in ("free-form answer with no citations", {"decision": "PLAN"},
                       {"decision": "PLAN", "citedNodeIds": []}):
            with self.subTest(answer=repr(answer)):
                result = self._simulate(answer)
                self.assertIsNone(result["text"])
                self.assertTrue(result["stub"])
                self.assertIn(
                    result["grounding"]["citation_validation"]["state"],
                    {"MISSING_KHIPU_CITATION_CONTRACT_REFUSED", "EMPTY_LEGACY_PLAN_REFUSED"},
                )
                self.assertEqual(len(result["raw_model_output_sha256"]), 64)

    def test_existing_plan_contract_remains_legacy_proposal_only(self):
        legacy = {"decision": "PLAN", "citedNodeIds": [N1]}
        result = self._simulate(legacy)
        self.assertFalse(result["stub"])
        self.assertEqual(
            result["grounding"]["citation_validation"]["state"],
            "CITATIONS_WITHIN_OFFERED_HANDLES",
        )
        self.assertNotIn("plan_invariants", result["grounding"])


if __name__ == "__main__":
    unittest.main()
