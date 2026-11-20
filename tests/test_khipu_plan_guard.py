# SPDX-License-Identifier: Apache-2.0
"""Synthetic, pure tests for controller-owned Khipu NAVIGATE/ABSTAIN gates."""
from __future__ import annotations

import copy
import unittest

from ayllu.khipu_plan_guard import validate_khipu_plan


QUERY = "Which offered handle documents the source receipt?"
N1 = "node://szl-synthetic/proof-1"
N2 = "node://szl-synthetic/unrelated-2"
D1, D2 = "a" * 64, "b" * 64


def fixture():
    handles = [
        {"nodeId": N1, "chunkId": "chunk-proof", "sha256": D1},
        {"nodeId": N2, "chunkId": "chunk-other", "sha256": D2},
    ]
    evidence = [
        {"node_id": N1, "chunk_id": "chunk-proof", "sha256": D1},
        {"node_id": N2, "chunk_id": "chunk-other", "sha256": D2},
    ]
    plan = {
        "planId": "plan-synthetic-1",
        "capabilityProfile": "SZL-Khipu-1.5B-BrainNavigator",
        "provenance": "MODEL_PROPOSED",
        "query": QUERY,
        "contentAccess": "HANDLES_ONLY",
        "candidates": [
            {"nodeId": N1, "nodeKind": "ARTIFACT", "label": "MEASURED", "note": "synthetic source receipt"},
            {"nodeId": N2, "nodeKind": "SUMMARY", "label": "DECLARED", "note": "synthetic unrelated"},
        ],
        "decision": "NAVIGATE",
        "steps": [
            {"action": "RETRIEVE", "nodeId": N1, "rationale": "offered synthetic tag"},
            {"action": "CITE", "nodeId": N1, "rationale": "offered synthetic tag"},
        ],
        "citedNodeIds": [N1],
        "groundedOnly": True,
        "brainBinding": {"protocol": "khipu-retrieval", "status": "NOT_RESOLVED", "note": "controller owns retrieval"},
        "controllerBoundary": "Only the controller resolves handles outside weights.",
        "abstainReason": None,
    }
    return plan, handles, evidence


class KhipuPlanAdmission(unittest.TestCase):
    def test_navigation_binds_controller_evidence_but_never_claims_relevance_or_execution(self):
        p, h, e = fixture()
        result = validate_khipu_plan(p, h, e, requested_query=QUERY)
        self.assertTrue(result.admitted_structure, result.code)
        self.assertEqual(result.cited_node_ids, (N1,))
        self.assertFalse(result.semantic_relevance_verified)
        self.assertFalse(result.execution_authorized)
        self.assertFalse(result.signer_verified)

    def test_abstention_with_zero_actions_can_be_structurally_admitted(self):
        p, h, e = fixture()
        p.update({"decision": "ABSTAIN", "steps": [], "citedNodeIds": [],
                  "abstainReason": "No relevant handle supports this question"})
        result = validate_khipu_plan(p, h, e, requested_query=QUERY)
        self.assertTrue(result.admitted_structure, result.code)
        self.assertEqual(result.cited_node_ids, ())
        self.assertFalse(result.semantic_relevance_verified)

    def test_invalid_plans_denied_without_revealing_model_content(self):
        cases = [
            ("NO_CITATION", lambda p, h, e: (p.update(citedNodeIds=[], steps=[]))),
            ("FABRICATED_CITATION", lambda p, h, e: p.update(citedNodeIds=["node://invented"])),
            ("CITE_ACTION_MISMATCH", lambda p, h, e: p["steps"].pop()),
            ("UNOFFERED_CITE_STEP", lambda p, h, e: p["steps"][1].update(nodeId="node://invented")),
            ("DUPLICATE_CITE_ACTION", lambda p, h, e: p["steps"].append(copy.deepcopy(p["steps"][1]))),
            ("ABSTAIN_CITES", lambda p, h, e: p.update(decision="ABSTAIN", abstainReason="No source")),
            ("ABSTAIN_RETRIEVES", lambda p, h, e: p.update(decision="ABSTAIN", citedNodeIds=[], abstainReason="No source")),
            ("ABSTAIN_NO_REASON", lambda p, h, e: p.update(decision="ABSTAIN", citedNodeIds=[], steps=[], abstainReason="   ")),
            ("NAVIGATE_WITH_REFUSAL", lambda p, h, e: p.update(abstainReason="No source")),
            ("MODEL_CLAIMS_TEXT", lambda p, h, e: p["brainBinding"].update(status="RESOLVED")),
            ("MODEL_CLAIMS_EXECUTION", lambda p, h, e: p.update(executed=True)),
            ("MODEL_CLAIMS_SIGNING", lambda p, h, e: p.update(signed=True)),
            ("INVALID_GROUNDED_BOOL", lambda p, h, e: p.update(groundedOnly="true")),
            ("CANDIDATE_NOT_OFFERED", lambda p, h, e: p["candidates"][0].update(nodeId="node://invented")),
            ("CANDIDATE_RAW_CONTENT", lambda p, h, e: p["candidates"][0].update(content="PRIVATE_DO_NOT_LEAK")),
            ("MISSING_INDEPENDENT_EVIDENCE", lambda p, h, e: e.clear()),
            ("DIGEST_MISMATCH", lambda p, h, e: e[0].update(sha256="c" * 64)),
            ("EVIDENCE_NODE_MISMATCH", lambda p, h, e: e[0].update(node_id="node://wrong")),
            ("CHUNK_MISMATCH", lambda p, h, e: e[0].update(chunk_id="wrong")),
            ("DUPLICATE_OFFERED", lambda p, h, e: h.append(copy.deepcopy(h[0]))),
            ("DUPLICATE_CITATIONS", lambda p, h, e: p.update(citedNodeIds=[N1, N1])),
            ("QUERY_CHANGED_BY_MODEL", lambda p, h, e: p.update(query="different")),
            ("UNKNOWN_DECISION", lambda p, h, e: p.update(decision="PLAN")),
            ("UNTRUSTED_ACTION", lambda p, h, e: p["steps"][0].update(action="EXECUTE")),
            ("EMPTY_RATIONALE", lambda p, h, e: p["steps"][0].update(rationale="")),
            ("NOT_JSON_DICT", lambda p, h, e: p.update(candidates=[])),
            ("DUPLICATE_CANDIDATE", lambda p, h, e: p["candidates"].append(copy.deepcopy(p["candidates"][0]))),
            ("UNHASHABLE_CANDIDATE_KIND", lambda p, h, e: p["candidates"][0].update(nodeKind=[])),
            ("UNHASHABLE_STEP_ACTION", lambda p, h, e: p["steps"][0].update(action=[])),
            ("UNHASHABLE_STEP_ID", lambda p, h, e: p["steps"][0].update(nodeId=[])),
        ]
        for label, change in cases:
            with self.subTest(case=label):
                p, h, e = fixture()
                change(p, h, e)
                got = validate_khipu_plan(p, h, e, requested_query=QUERY)
                self.assertFalse(got.admitted_structure, label)
                self.assertFalse(got.execution_authorized)
                self.assertFalse(got.signer_verified)
                self.assertNotIn("PRIVATE_DO_NOT_LEAK", got.code)

    def test_invalid_outer_data_denied(self):
        plan, handles, evidence = fixture()
        for value in (None, [], "NAVIGATE", 5, {"decision": "NAVIGATE"}):
            with self.subTest(value=repr(value)):
                got = validate_khipu_plan(value, handles, evidence, requested_query=QUERY)
                self.assertFalse(got.admitted_structure)
        got = validate_khipu_plan(plan, handles, evidence, requested_query=123)
        self.assertFalse(got.admitted_structure)


if __name__ == "__main__":
    unittest.main()
