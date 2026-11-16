from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from szl_evidence_graph import (
    EvidenceEdge,
    canonical_json,
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


def test_full_query_preserves_content_identity_and_reports_source_digest():
    edge = make_edge("readyz", verdict="DEGRADED")
    snapshot = graph_snapshot([edge], observed_at="2026-11-16T00:00:00Z")
    selected = query_snapshot(snapshot, verdict="DEGRADED", invariant_id="freshness")
    assert selected["selected_edge_count"] == 1
    assert selected["digest_sha256"] == snapshot["digest_sha256"]
    assert selected["source_digest_sha256"] == snapshot["digest_sha256"]
    assert selected["query"]["verdict"] == "DEGRADED"


def test_unknown_verdict_and_bad_digest_fail_closed():
    with pytest.raises(ValueError, match="unsupported verdict"):
        make_edge("bad", verdict="GREEN")
    payload = make_edge("route").as_dict()
    payload["artifact_sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="SHA-256"):
        EvidenceEdge.from_dict(payload)


def test_empty_environment_is_unavailable(monkeypatch):
    for key in ("A11OY_SOURCE_REVISION", "GIT_COMMIT", "SOURCE_REVISION", "SZL_GIT_SHA", "A11OY_RUNTIME_REVISION", "HF_REVISION"):
        monkeypatch.delenv(key, raising=False)
    result = environment_snapshot()
    assert result["state"] == "UNAVAILABLE"
    assert result["graph"]["edge_count"] == 0


def test_space_build_identity_is_observed(monkeypatch):
    for key in ("A11OY_SOURCE_REVISION", "GIT_COMMIT", "SOURCE_REVISION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SZL_GIT_SHA", "1472e26b7015964789d3a9c4591ea3d10f0ce20b")
    result = environment_snapshot()
    assert result["state"] == "OBSERVED"
    assert result["graph"]["edge_count"] == 1
    assert result["graph"]["edges"][0]["source_revision"].startswith("1472e26")


def test_edge_owns_nested_inputs_and_preserves_references():
    metrics = {"scores": [{"value": 0.75}], "tags": ["held-out"]}
    runtime = {"deployment": {"revision": "runtime-a"}}
    authority = {"execution_authorized": False, "checks": ["observed-only"]}
    subject = {"kind": "evaluation", "id": "run-a", "metadata": {"split": "test"}}
    edge = EvidenceEdge(subject=subject, evidence=metrics, runtime=runtime, authority=authority)
    receipt_id = edge.receipt_id
    before = edge.as_dict()
    child = make_edge("receipt-consumer", parents=(receipt_id,))
    metrics["scores"][0]["value"] = 1.0
    metrics["tags"].append("changed")
    runtime["deployment"]["revision"] = "runtime-b"
    authority["checks"].append("changed")
    subject["metadata"]["split"] = "train"
    assert edge.as_dict() == before
    assert edge.receipt_id == receipt_id
    assert graph_snapshot([edge, child])["dangling_parent_count"] == 0


@pytest.mark.parametrize("export", ["payload", "as_dict"])
def test_exported_nested_payload_is_detached(export):
    edge = EvidenceEdge(
        subject={"kind": "evaluation", "id": "run-a"},
        evidence={"metrics": [{"score": 0.75}]},
        runtime={"replicas": [{"id": "one"}]},
        authority={"checks": [{"verified": False}]},
    )
    before = edge.as_dict()
    rendered = getattr(edge, export)()
    rendered["evidence"]["metrics"][0]["score"] = 1.0
    rendered["runtime"]["replicas"].append({"id": "two"})
    rendered["authority"]["checks"][0]["verified"] = True
    assert edge.as_dict() == before


def test_stored_nested_payload_is_immutable():
    edge = EvidenceEdge(
        subject={"kind": "evaluation", "id": "run-a"},
        evidence={"metrics": [{"score": 0.75}]},
    )
    with pytest.raises(TypeError):
        edge.evidence["metrics"][0]["score"] = 1.0
    with pytest.raises(TypeError):
        edge.evidence["metrics"][0] = {"score": 1.0}
    with pytest.raises(TypeError):
        edge.subject["id"] = "other"


def test_valid_json_round_trip_preserves_existing_receipt_id():
    edge = EvidenceEdge(
        subject={"kind": "evaluation", "id": "baseline"},
        source_revision="1472e26b7015964789d3a9c4591ea3d10f0ce20b",
        evidence={
            "metrics": {"loss": 0.25, "count": 2, "passed": True, "missing": None},
            "labels": ["base", "adapter"],
        },
        parents=("edge-parent-b", "edge-parent-a"),
        invariant_ids=("source-consistency",),
    )
    # Captured from the pre-change serializer, not regenerated by this test.
    assert edge.receipt_id == "edge-1ce855aecbea87da142fc0eefa4dd809b070719c1ceef6789513dec580de4cfe"
    serialized = canonical_json(edge.as_dict())
    restored = EvidenceEdge.from_dict(json.loads(serialized))
    assert restored.as_dict() == edge.as_dict()
    assert isinstance(restored.payload()["evidence"]["labels"], list)
    assert canonical_json({"text": "Qu\u00e9chua", "values": (1, None, False)}) == '{"text":"Qu\u00e9chua","values":[1,null,false]}'


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_metrics_are_rejected_before_receipt_creation(number):
    with pytest.raises(ValueError, match="finite"):
        EvidenceEdge(subject={"kind": "evaluation", "id": "run-a"}, evidence={"metrics": [number]})
    payload = make_edge("fixture").as_dict()
    payload["evidence"]["metrics"] = {"score": number}
    with pytest.raises(ValueError, match="finite"):
        EvidenceEdge.from_dict(payload)
    with pytest.raises(ValueError, match="finite"):
        canonical_json({"score": number})


@pytest.mark.parametrize("bad", [{1: "integer-key"}, {"nested": {False: "boolean-key"}}, {"loss": {0.5}}, {"raw": b"bytes"}])
def test_non_json_values_and_object_keys_are_rejected(bad):
    with pytest.raises(ValueError, match="JSON"):
        EvidenceEdge(subject={"kind": "evaluation", "id": "run-a"}, evidence=bad)
    with pytest.raises(ValueError, match="JSON"):
        canonical_json(bad)


def test_json_cycles_are_rejected_but_shared_values_are_copied():
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="cycles"):
        EvidenceEdge(subject={"kind": "evaluation", "id": "run-a"}, evidence={"cycle": cyclic})
    shared = {"score": 0.5}
    edge = EvidenceEdge(subject={"kind": "evaluation", "id": "run-a"}, evidence={"a": shared, "b": shared})
    exported = edge.payload()
    exported["evidence"]["a"]["score"] = 1.0
    assert exported["evidence"]["b"]["score"] == 0.5
    assert edge.evidence["a"]["score"] == 0.5


@pytest.mark.parametrize("field,value", [
    ("subject", {"kind": "evaluation", "id": ["run-a"]}),
    ("evidence", []), ("runtime", "space"), ("authority", False),
    ("source_revision", []), ("reason", {"reason": "unknown"}),
    ("artifact_sha256", ""), ("parents", "edge-parent"),
    ("parents", [1]), ("invariant_ids", ["source-consistency", None]),
    ("verdict", ["OBSERVED"]),
])
def test_edge_fields_reject_wrong_types(field, value):
    values = {"subject": {"kind": "evaluation", "id": "run-a"}, field: value}
    with pytest.raises(ValueError):
        EvidenceEdge(**values)
    with pytest.raises(ValueError):
        EvidenceEdge.from_dict(values)


def test_primitives_import_without_fastapi():
    code = """
import importlib.abc
import sys
class NoFastAPI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'fastapi' or fullname.startswith('fastapi.'):
            raise ModuleNotFoundError('optional FastAPI is unavailable', name='fastapi')
sys.meta_path.insert(0, NoFastAPI())
from szl_evidence_graph import EvidenceEdge, graph_snapshot
edge = EvidenceEdge(subject={'kind': 'evaluation', 'id': 'standalone'})
assert graph_snapshot([edge])['edge_count'] == 1
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_serving_routes_keep_resolvable_response_annotations():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from szl_evidence_graph import register

    app = FastAPI()
    register(app)
    with TestClient(app) as client:
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        assert "/api/a11oy/v1/evidence/graph" in schema.json()["paths"]
        assert "/api/a11oy/v1/evidence/query" in schema.json()["paths"]
        assert client.get("/api/a11oy/v1/evidence/graph").status_code == 200
        assert client.get("/api/a11oy/v1/evidence/query?verdict=GREEN").status_code == 400
