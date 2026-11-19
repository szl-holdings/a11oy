# SPDX-License-Identifier: Apache-2.0
"""Adversarial source tests for the read-only Proof-to-Discovery slice."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from szl_evidence_graph import EvidenceEdge, graph_snapshot, register
from szl_evidence_discovery import binary_evsi, discovery_gaps

ROOT = Path(__file__).resolve().parents[1]


def edge(name="training-a", *, kind="training", verdict="OBSERVED",
         source=None, artifact=None, parents=()):
    return EvidenceEdge(
        subject={"kind": kind, "id": name},
        source_revision=source,
        artifact_sha256=artifact,
        evidence={"kind": "historical-receipt", "claims_verified": False},
        authority={"execution_authorized": False},
        verdict=verdict,
        parents=parents,
    )


def bound_graph(*items, limit=256):
    return graph_snapshot(items, observed_at="2026-11-17T20:00:00Z", max_edges=limit)


def decision():
    return {
        "decision_id": "fixture-model-admission",
        "binding": {"model_sha256": "a" * 64, "dataset_sha256": "b" * 64,
                    "harness_sha256": "c" * 64},
        "prior_pass": 0.5,
        "utility_usd": {
            "release": {"pass": 10, "fail": -10},
            "hold": {"pass": 0, "fail": 0},
        },
    }


def proposal(name="heldout-check", *, sens=1.0, spec=1.0, cost=1.0, risk=0.5):
    return {"experiment_id": name, "sensitivity": sens, "specificity": spec,
            "cost_usd": cost, "risk_expected_loss_usd": risk}


def test_discovery_is_advisory_even_when_observer_says_verified():
    result = discovery_gaps(bound_graph(edge(
        verdict="VERIFIED", source="a" * 40, artifact="b" * 64,
    )))
    assert result["state"] == "GAPS_OBSERVED"
    assert result["authority"] == {"execute": False, "promote": False, "publish": False}
    item = result["candidates"][0]
    assert item["qualification"] == "UNQUALIFIED"
    assert set(item["gate_status"].values()) == {"UNVERIFIED"}
    assert item["experiment_authorized"] is False
    assert item["independent_signature_verified"] is False


def test_historical_evaluation_cannot_be_transferred_to_training():
    result = discovery_gaps(bound_graph(
        edge("run-1", kind="training"), edge("run-1", kind="evaluation")))
    assert result["candidate_count"] == 2
    assert {i["subject"]["kind"] for i in result["candidates"]} == {
        "training", "evaluation"}
    assert all(i["qualification"] == "UNQUALIFIED" for i in result["candidates"])


def test_duplicate_subjects_preserve_both_edges():
    result = discovery_gaps(bound_graph(edge("same"), edge("same", verdict="DEGRADED")))
    assert result["candidate_count"] == 1
    assert len(result["candidates"][0]["evidence_edge_ids"]) == 2


def test_source_conflict_does_not_choose_a_winner():
    result = discovery_gaps(bound_graph(
        edge("same", source="a" * 40), edge("same", source="b" * 40)))
    item = result["candidates"][0]
    assert item["conflicting_source_declarations"] is True
    assert item["declared_source_revision"] is None


def test_graph_digest_or_edge_tamper_fails_closed():
    graph = bound_graph(edge())
    graph["edges"][0]["verdict"] = "VERIFIED"
    with pytest.raises(ValueError):
        discovery_gaps(graph)


def test_graph_coverage_truncation_and_parent_gap_refuse_planning():
    items = [edge("one"), edge("two")]
    assert discovery_gaps(bound_graph(*items, limit=1))["state"] == "UNAVAILABLE"
    assert discovery_gaps(bound_graph(edge(parents=("edge-unavailable",))))[
        "reason"] == "GRAPH_COVERAGE_OR_PARENT_UNAVAILABLE"


def test_no_eligible_subject_does_not_fake_a_clean_estate():
    assert discovery_gaps(bound_graph(edge(kind="runtime")))["state"] == "UNAVAILABLE"


def test_target_cap_is_explicit_and_not_a_silent_omission():
    items = [edge(f"training-{i}") for i in range(5)]
    result = discovery_gaps(bound_graph(*items), max_targets=4)
    assert result["reason"] == "DISCOVERY_CANDIDATE_CAP"
    assert result["candidates"] == []


@pytest.mark.parametrize("value", [0, 33, True, 1.5, None])
def test_invalid_target_cap_refused(value):
    with pytest.raises(ValueError):
        discovery_gaps(bound_graph(edge()), max_targets=value)


def test_monetary_evsi_includes_real_hypothetical_cost_and_risk():
    report = binary_evsi(decision(), [proposal()])
    row = report["ranked"][0]
    assert row["evsi_usd"] == pytest.approx(5.0)
    assert row["modeled_net_value_usd"] == pytest.approx(3.5)
    assert report["analytical_priority_only"] == "heldout-check"
    assert report["assumptions_independently_verified"] is False
    assert row["execution_authorized"] is False
    assert report["authority"]["execute"] is False


def test_noninformative_or_expensive_test_is_not_selected():
    report = binary_evsi(decision(), [proposal(sens=0.5, spec=0.5)])
    assert report["ranked"][0]["evsi_usd"] == pytest.approx(0.0)
    assert report["analytical_priority_only"] is None
    assert binary_evsi(decision(), [proposal(cost=100)])[
        "analytical_priority_only"] is None


@pytest.mark.parametrize("sens", [x / 10 for x in range(11)])
@pytest.mark.parametrize("spec", [x / 10 for x in range(11)])
def test_binary_experiment_grid_is_finite_nonnegative_and_non_authorizing(sens, spec):
    row = binary_evsi(decision(), [proposal(sens=sens, spec=spec)])["ranked"][0]
    assert row["evsi_usd"] >= 0
    assert row["evsi_usd"] <= 5.00000001
    assert row["execution_authorized"] is False


def test_identical_order_independent_digest_and_tiebreak():
    a, b = proposal("b"), proposal("a")
    left = binary_evsi(decision(), [a, b])
    right = binary_evsi(decision(), [b, a])
    assert left == right
    assert left["analytical_priority_only"] == "a"


@pytest.mark.parametrize("field,bad", [
    ("prior_pass", True), ("prior_pass", float("nan")),
    ("prior_pass", float("inf")), ("prior_pass", -0.1),
    ("prior_pass", 1.1), ("decision_id", ""),
    ("decision_id", "UNSAFE PRIV"), ("binding", {}),
    ("utility_usd", {}), ("unexpected", "authorization"),
])
def test_untrusted_decision_contract_rejected(field, bad):
    plan = decision()
    plan[field] = bad
    with pytest.raises(ValueError):
        binary_evsi(plan, [proposal()])


@pytest.mark.parametrize("field,bad", [
    ("sensitivity", True), ("sensitivity", -0.1),
    ("specificity", float("inf")), ("specificity", 1.01),
    ("cost_usd", -1), ("cost_usd", float("nan")),
    ("risk_expected_loss_usd", -1), ("experiment_id", ""),
    ("experiment_id", "../bad"), ("unexpected", "execute"),
])
def test_untrusted_experiment_contract_rejected(field, bad):
    experiment = proposal()
    experiment[field] = bad
    with pytest.raises(ValueError):
        binary_evsi(decision(), [experiment])


def test_duplicate_or_overbudget_experiments_rejected():
    with pytest.raises(ValueError, match="DUPLICATE"):
        binary_evsi(decision(), [proposal(), proposal()])
    with pytest.raises(ValueError, match="COUNT"):
        binary_evsi(decision(), [proposal(str(i)) for i in range(33)])


def test_manifest_identity_binding_not_inferred():
    spec = decision()
    spec["binding"]["model_sha256"] = "pending"
    with pytest.raises(ValueError, match="IMMUTABLE"):
        binary_evsi(spec, [proposal()])


def test_discovery_api_uses_existing_public_bundle_without_writes(monkeypatch):
    for key in ("A11OY_SOURCE_REVISION", "GIT_COMMIT", "SOURCE_REVISION",
                "SZL_GIT_SHA", "A11OY_RUNTIME_REVISION", "HF_REVISION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    path = ROOT / "evidence_graph_receipts.json"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    app = FastAPI()
    register(app)
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get("/api/a11oy/v1/evidence/discovery")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            result = response.json()
            assert result["state"] == "GAPS_OBSERVED"
            assert result["candidate_count"] == 2
            assert result["runtime_identity_state"] == "OBSERVED"
            assert result["authority"]["promote"] is False
            assert "private" not in response.text.lower()
        capped = client.get("/api/a11oy/v1/evidence/discovery?limit=1")
        assert capped.status_code == 503
        assert capped.json()["state"] == "UNAVAILABLE"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_discovery_api_invalid_catalog_returns_503_without_path_leak(tmp_path):
    app = FastAPI()
    register(app, receipt_bundle_path=tmp_path / "do-not-echo-private-path.json")
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/evidence/discovery")
        assert response.status_code == 503
        assert response.json() == {
            "state": "UNAVAILABLE", "reason": "RECEIPT_BUNDLE_UNAVAILABLE",
        }
        assert "private-path" not in response.text


def test_discovery_source_in_docker_copy():
    content = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "szl_evidence_graph.py szl_evidence_discovery.py szl_evidence_receipts.py" in content
