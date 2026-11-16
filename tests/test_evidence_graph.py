from __future__ import annotations

import pytest

from szl_evidence_graph import (
    EvidenceEdge,
    environment_snapshot,
    graph_snapshot,
    query_snapshot,
)


def make_edge(name: str, *, verdict: str = "OBSERVED", parents=()):
    return EvidenceEdge(
        subject={"kind": "route", "id": name},
        source_revision="1472e26b7015964789d3a9c4591ea3d10f0ce20b",
        runtime={"space": "szlholdings-a11oy"},
        evidence={"kind": "http-probe", "route_or_uri": f"/{name}", "measured_state": "OBSERVED"},
        authority={"execution_authorized": False, "method": "test-fixture"},
        parents=tuple(parents),
        invariant_ids=("freshness", "source-consistency"),
        verdict=verdict,
    )


def test_receipt_id_is_canonical_and_tamper_evident():
    first = make_edge("healthz")
    second = make_edge("healthz")
    assert first.receipt_id == second.receipt_id
    assert first.as_dict()["receipt_id"].startswith("edge-")
    tampered = first.as_dict()
    tampered["verdict"] = "VERIFIED"
    with pytest.raises(ValueError, match="receipt_id"):
        EvidenceEdge.from_dict(tampered)


def test_graph_is_bounded_deterministic_and_explicit_about_truncation():
    edges = [make_edge(f"route-{index}") for index in range(4)]
    left = graph_snapshot(edges, max_edges=2, observed_at="2026-11-16T00:00:00Z")
    right = graph_snapshot(list(reversed(edges)), max_edges=2, observed_at="2026-11-16T00:00:00Z")
    assert left == right
    assert left["bounded"] is True
    assert left["edge_count"] == 2
    assert left["total_input_edges"] == 4
    assert len(left["digest_sha256"]) == 64


def test_query_does_not_rewrite_original_graph_digest():
    edge = make_edge("readyz", verdict="DEGRADED")
    snapshot = graph_snapshot([edge], observed_at="2026-11-16T00:00:00Z")
    selected = query_snapshot(snapshot, verdict="DEGRADED", invariant_id="freshness")
    assert selected["selected_edge_count"] == 1
    assert selected["digest_sha256"] == snapshot["digest_sha256"]
    assert selected["query"]["verdict"] == "DEGRADED"


def test_unknown_verdict_and_bad_digest_fail_closed():
    with pytest.raises(ValueError, match="unsupported verdict"):
        make_edge("bad", verdict="GREEN")
    payload = make_edge("route").as_dict()
    payload["artifact_sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="SHA-256"):
        EvidenceEdge.from_dict(payload)


def test_empty_environment_is_unavailable(monkeypatch):
    for key in ("A11OY_SOURCE_REVISION", "GIT_COMMIT", "SOURCE_REVISION", "A11OY_RUNTIME_REVISION", "HF_REVISION"):
        monkeypatch.delenv(key, raising=False)
    result = environment_snapshot()
    assert result["state"] == "UNAVAILABLE"
    assert result["graph"]["edge_count"] == 0
