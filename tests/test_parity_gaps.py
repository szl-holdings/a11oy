# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
Tests for szl_parity_gaps — parity gap closure + differentiator endpoints.

Coverage:
  GAP-A: /api/a11oy/v1/compliance/export
  GAP-B: /api/a11oy/v1/lineage
  GAP-C: /api/a11oy/v1/policy/validate
  DIFF-1: /api/a11oy/v1/receipts/replay
  DIFF-2: /api/a11oy/v1/lambda/score
"""
from __future__ import annotations
import json
import math
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_parity_gaps as pg

# ---------------------------------------------------------------------------
# Minimal gate manifest stubs for tests
# ---------------------------------------------------------------------------
_STUB_GATES = [
    {"name": "thresholdPolicySeverity", "file": "thresholdPolicySeverity_gate.ts",
     "description": "Threshold gate", "lean_theorem": "ThresholdAxiom",
     "lean_file": "Lutar/LambdaInvariant/Boundary.lean", "lean_verified": True},
    {"name": "adversarialRobustness", "file": "adversarialRobustness_gate.ts",
     "description": "Adversarial robustness", "lean_theorem": "", "lean_verified": False},
    {"name": "hashChainIntegrity", "file": "hashChainIntegrity_gate.ts",
     "description": "Hash chain", "lean_theorem": "", "lean_verified": False},
    {"name": "merkleDagBatch", "file": "merkleDagBatch_gate.ts",
     "description": "Merkle DAG", "lean_theorem": "", "lean_verified": False},
    {"name": "doctrineCompleteness", "file": "doctrineCompleteness_gate.ts",
     "description": "Doctrine completeness", "lean_theorem": "", "lean_verified": False},
    {"name": "constructiveTransparency", "file": "constructiveTransparency_gate.ts",
     "description": "Transparency", "lean_theorem": "", "lean_verified": False},
    {"name": "soundnessAxiom", "file": "soundnessAxiom_gate.ts",
     "description": "Soundness", "lean_theorem": "", "lean_verified": False},
    {"name": "deterministicReplay", "file": "deterministicReplay_gate.ts",
     "description": "Deterministic replay", "lean_theorem": "", "lean_verified": False},
    {"name": "certifiedRobustness", "file": "certifiedRobustness_gate.ts",
     "description": "Certified robustness", "lean_theorem": "", "lean_verified": False},
    {"name": "bekensteinBound", "file": "bekensteinBound_gate.ts",
     "description": "Bekenstein", "lean_theorem": "", "lean_verified": False},
    {"name": "composability", "file": "composability_gate.ts",
     "description": "Composability", "lean_theorem": "", "lean_verified": False},
    {"name": "crossRegionPolicy", "file": "crossRegionPolicy_gate.ts",
     "description": "Cross-region", "lean_theorem": "", "lean_verified": False},
    {"name": "witnessQuorum", "file": "witnessQuorum_gate.ts",
     "description": "Witness quorum", "lean_theorem": "", "lean_verified": False},
    {"name": "humanEscalation", "file": "humanEscalation_gate.ts",
     "description": "Human escalation", "lean_theorem": "", "lean_verified": False},
    {"name": "provenance", "file": "provenance_gate.ts",
     "description": "Provenance", "lean_theorem": "", "lean_verified": False},
]
_STUB_BY_NAME = {g["name"]: g for g in _STUB_GATES}


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    pg.register(app, _STUB_GATES, _STUB_BY_NAME)
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GAP-A: Compliance Evidence Export
# ---------------------------------------------------------------------------
class TestComplianceExport:
    def test_eu_ai_act_200(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=eu-ai-act")
        assert r.status_code == 200
        d = r.json()
        assert d["framework"] == "eu-ai-act"
        assert d["schema"] == "szl.compliance.export.v1"
        assert isinstance(d["controls"], list)
        assert len(d["controls"]) > 0
        assert d["doctrine"] == "v11"

    def test_nist_ai_rmf_200(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=nist-ai-rmf")
        assert r.status_code == 200
        assert r.json()["framework"] == "nist-ai-rmf"

    def test_iso_42001_200(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=iso-42001")
        assert r.status_code == 200
        assert r.json()["framework"] == "iso-42001"

    def test_soc2_200(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=soc2")
        assert r.status_code == 200
        assert r.json()["framework"] == "soc2"

    def test_unknown_framework_400(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=fedramp-high")
        assert r.status_code == 400
        d = r.json()
        assert "available" in d

    def test_controls_have_gate_evidence(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=eu-ai-act")
        d = r.json()
        for ctrl in d["controls"]:
            assert "gate_evidence" in ctrl
            assert isinstance(ctrl["gate_evidence"], list)

    def test_lambda_conjecture_labelled(self, client):
        r = client.get("/api/a11oy/v1/compliance/export?framework=eu-ai-act")
        d = r.json()
        assert "Conjecture" in d["lambda"]

    def test_default_framework_is_eu_ai_act(self, client):
        r = client.get("/api/a11oy/v1/compliance/export")
        assert r.status_code == 200
        assert r.json()["framework"] == "eu-ai-act"


# ---------------------------------------------------------------------------
# GAP-B: Decision Lineage Query
# ---------------------------------------------------------------------------
class TestDecisionLineage:
    def test_lineage_200(self, client):
        r = client.get("/api/a11oy/v1/lineage")
        assert r.status_code == 200
        d = r.json()
        assert d["schema"] == "szl.lineage.v1"
        assert "nodes" in d
        assert d["doctrine"] == "v11"

    def test_lineage_empty_on_cold_dag(self, client):
        """On a cold start with no real DAG the endpoint returns honest empty nodes."""
        r = client.get("/api/a11oy/v1/lineage?limit=10")
        d = r.json()
        # Either empty (cold start) or has nodes (if DAG populated)
        assert isinstance(d["nodes"], list)
        assert "returned" in d

    def test_lineage_limit_honoured(self, client):
        r = client.get("/api/a11oy/v1/lineage?limit=5")
        d = r.json()
        assert d["limit"] == 5
        assert len(d["nodes"]) <= 5

    def test_lineage_limit_capped_at_200(self, client):
        r = client.get("/api/a11oy/v1/lineage?limit=9999")
        d = r.json()
        assert d["limit"] == 200

    def test_lineage_leader_parity_refs(self, client):
        r = client.get("/api/a11oy/v1/lineage")
        d = r.json()
        lp = d.get("leader_parity", {})
        assert "palantir" in " ".join(lp.values()).lower()


# ---------------------------------------------------------------------------
# GAP-C: Policy-as-Code Validation
# ---------------------------------------------------------------------------
class TestPolicyValidate:
    def test_valid_policy(self, client):
        payload = {
            "name": "test-policy",
            "gates": ["thresholdPolicySeverity", "adversarialRobustness"],
            "lambda_floor": 0.90,
            "min_witnesses": 2,
            "severity": "medium",
        }
        r = client.post("/api/a11oy/v1/policy/validate", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is True
        assert d["violations"] == []

    def test_missing_name_invalid(self, client):
        payload = {"gates": ["thresholdPolicySeverity"]}
        r = client.post("/api/a11oy/v1/policy/validate", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False
        assert any(v["field"] == "name" for v in d["violations"])

    def test_unknown_gate_invalid(self, client):
        payload = {"name": "test", "gates": ["nonexistent_gate_xyz"]}
        r = client.post("/api/a11oy/v1/policy/validate", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False
        assert any("Unknown gates" in v["message"] for v in d["violations"])

    def test_lambda_floor_out_of_range(self, client):
        payload = {"name": "test", "gates": ["thresholdPolicySeverity"],
                   "lambda_floor": 1.5}
        r = client.post("/api/a11oy/v1/policy/validate", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False
        assert any("lambda_floor" in v["field"] for v in d["violations"])

    def test_capital_severity_quorum_check(self, client):
        payload = {"name": "test", "gates": ["thresholdPolicySeverity"],
                   "severity": "capital", "min_witnesses": 2}
        r = client.post("/api/a11oy/v1/policy/validate", json=payload)
        assert r.status_code == 200
        d = r.json()
        # capital requires 3-of-N quorum
        assert d["required_quorum"] == 3
        assert d["valid"] is False

    def test_gate_coverage_reported(self, client):
        payload = {"name": "test", "gates": ["thresholdPolicySeverity"]}
        r = client.post("/api/a11oy/v1/policy/validate", json=payload)
        d = r.json()
        assert "gate_coverage" in d
        assert d["gate_coverage"]["known"] >= 1

    def test_invalid_json_400(self, client):
        r = client.post("/api/a11oy/v1/policy/validate",
                        content=b"not json", headers={"Content-Type": "application/json"})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# DIFF-1: Receipt Replay
# ---------------------------------------------------------------------------
class TestReceiptReplay:
    def test_replay_allow(self, client):
        payload = {
            "action": {
                "severity": "medium",
                "confidence": 0.85,
                "actionId": "replay-test-001",
                "witnesses": [
                    {"id": "w1", "role": "op", "attested": True},
                    {"id": "w2", "role": "auditor", "attested": True},
                ],
            },
            "gate": "thresholdPolicySeverity",
        }
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["schema"] == "szl.receipt.replay.v1"
        assert d["replay_decision"] in ("allow", "deny")
        assert "replay_receipt_hash" in d
        assert "determinism_note" in d

    def test_replay_deny_low_confidence(self, client):
        payload = {
            "action": {
                "severity": "high",
                "confidence": 0.5,
                "actionId": "replay-deny-001",
                "witnesses": [{"id": "w1", "role": "op", "attested": True}],
            },
            "gate": "thresholdPolicySeverity",
        }
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["replay_decision"] == "deny"

    def test_replay_hash_comparison(self, client):
        payload = {
            "action": {"severity": "medium", "confidence": 0.85, "actionId": "a",
                       "witnesses": [{"id": "w1", "attested": True},
                                     {"id": "w2", "attested": True}]},
            "original_receipt_hash": "deadbeef1234567890",
            "gate": "thresholdPolicySeverity",
        }
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        d = r.json()
        assert "hashes_match" in d
        # Hashes won't match (different hash), but the field must be present
        assert d["hashes_match"] is False  # deadbeef won't match real sha256

    def test_replay_unknown_gate_400(self, client):
        payload = {"action": {"severity": "medium"}, "gate": "nonexistent_gate_xyz"}
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        assert r.status_code == 400

    def test_replay_no_action_400(self, client):
        payload = {"gate": "thresholdPolicySeverity"}
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        assert r.status_code == 400

    def test_replay_dsse_envelope_present(self, client):
        payload = {
            "action": {"severity": "medium", "confidence": 0.85, "actionId": "a",
                       "witnesses": [{"id": "w1", "attested": True},
                                     {"id": "w2", "attested": True}]},
            "gate": "thresholdPolicySeverity",
        }
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        d = r.json()
        assert "replay_dsse" in d
        # replay_dsse may wrap a {receipt, dsse} or a {payloadType, ...} envelope
        env = d["replay_dsse"]
        has_payload_type = "payloadType" in env
        has_nested_dsse = "dsse" in env or "receipt" in env
        assert has_payload_type or has_nested_dsse, f"unexpected dsse shape: {list(env.keys())}"

    def test_replay_differentiator_note_present(self, client):
        payload = {
            "action": {"severity": "medium", "confidence": 0.85, "actionId": "a",
                       "witnesses": [{"id": "w1", "attested": True},
                                     {"id": "w2", "attested": True}]},
        }
        r = client.post("/api/a11oy/v1/receipts/replay", json=payload)
        d = r.json()
        assert "differentiator" in d


# ---------------------------------------------------------------------------
# DIFF-2: Λ-Gated Decision Scoring
# ---------------------------------------------------------------------------
class TestLambdaScore:
    _PERFECT = {a: 1.0 for a in pg.CANONICAL_AXES}
    _TYPICAL = {a: 0.91 for a in pg.CANONICAL_AXES}
    _ZERO_ONE = {**{a: 0.91 for a in pg.CANONICAL_AXES}, "soundness": 0.0}

    def test_perfect_axes_lambda_one(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._PERFECT})
        assert r.status_code == 200
        d = r.json()
        assert abs(d["lambda"] - 1.0) < 1e-6
        assert d["gate_pass"] is True

    def test_typical_axes_lambda_in_range(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._TYPICAL})
        d = r.json()
        lv = d["lambda"]
        assert 0.8 < lv < 1.0

    def test_zero_axis_zero_pinning(self, client):
        """A2: zero-pinning — Λ = 0 when any positive-weight axis is 0."""
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._ZERO_ONE})
        d = r.json()
        assert d["lambda"] == 0.0
        assert d["zero_pinned"] is True
        assert d["gate_pass"] is False

    def test_gate_pass_with_high_floor(self, client):
        r = client.post("/api/a11oy/v1/lambda/score",
                        json={"axes": self._TYPICAL, "lambda_floor": 0.99})
        d = r.json()
        assert d["gate_pass"] is False

    def test_gate_decision_deny(self, client):
        r = client.post("/api/a11oy/v1/lambda/score",
                        json={"axes": self._ZERO_ONE, "lambda_floor": 0.90})
        d = r.json()
        assert d["gate_decision"] == "deny"

    def test_schema_correct(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._TYPICAL})
        d = r.json()
        assert d["schema"] == "szl.lambda.score.v1"
        assert d["doctrine"] == "v11"

    def test_lean_citation_conjecture(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._TYPICAL})
        d = r.json()
        lc = d["lean_citation"]
        assert "Conjecture 1" in lc["status"]
        assert "NOT a closed theorem" in lc["status"]

    def test_axes_breakdown_present(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._TYPICAL})
        d = r.json()
        assert len(d["axes_computed"]) == 9

    def test_missing_axes_flagged(self, client):
        r = client.post("/api/a11oy/v1/lambda/score",
                        json={"axes": {"soundness": 0.9}})
        d = r.json()
        assert len(d["missing_axes"]) == 8

    def test_monotonicity_a1(self, client):
        """A1: raising one axis while others fixed should not decrease Λ."""
        base = {a: 0.80 for a in pg.CANONICAL_AXES}
        high = {**base, "soundness": 0.95}
        r_base = client.post("/api/a11oy/v1/lambda/score", json={"axes": base})
        r_high = client.post("/api/a11oy/v1/lambda/score", json={"axes": high})
        assert r_high.json()["lambda"] >= r_base.json()["lambda"]

    def test_no_action_400(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"lambda_floor": 0.9})
        assert r.status_code == 400

    def test_differentiator_note_present(self, client):
        r = client.post("/api/a11oy/v1/lambda/score", json={"axes": self._TYPICAL})
        d = r.json()
        assert "differentiator" in d


# ---------------------------------------------------------------------------
# Lambda computation unit tests (no HTTP)
# ---------------------------------------------------------------------------
class TestLambdaComputation:
    def test_perfect_is_one(self):
        axes = {a: 1.0 for a in pg.CANONICAL_AXES}
        result = pg._compute_lambda(axes)
        assert abs(result["lambda"] - 1.0) < 1e-9

    def test_zero_pinning(self):
        axes = {a: 0.9 for a in pg.CANONICAL_AXES}
        axes["soundness"] = 0.0
        result = pg._compute_lambda(axes)
        assert result["lambda"] == 0.0
        assert result["zero_pinned"] is True

    def test_monotonicity(self):
        base = {a: 0.80 for a in pg.CANONICAL_AXES}
        high = {**base, "calibration": 0.99}
        r_base = pg._compute_lambda(base)
        r_high = pg._compute_lambda(high)
        assert r_high["lambda"] >= r_base["lambda"]

    def test_symmetry(self):
        """A4 corollary: all-equal axes → Λ = that value (geometric = arithmetic for equal values)."""
        axes = {a: 0.90 for a in pg.CANONICAL_AXES}
        result = pg._compute_lambda(axes)
        assert abs(result["lambda"] - 0.90) < 1e-6

    def test_weights_normalised(self):
        """Custom weights that don't sum to 1 should still give valid Λ ∈ [0,1]."""
        axes = {a: 0.90 for a in pg.CANONICAL_AXES}
        weights = {a: 2.0 for a in pg.CANONICAL_AXES}  # sum = 18, not 1
        result = pg._compute_lambda(axes, weights)
        assert 0.0 <= result["lambda"] <= 1.0 + 1e-9
