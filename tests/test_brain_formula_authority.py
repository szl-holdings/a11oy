# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Regressions for the formal-authority/numerical-case Brain boundary."""

import copy

import pytest

import a11oy_brain_graph as brain
import szl_formula_registry as registry
import szl_puriq_formulas as puriq


@pytest.fixture(autouse=True)
def bounded_graph_sources(monkeypatch):
    """Keep unrelated surface/harvest inputs small; formula sources stay real."""
    monkeypatch.setattr(brain._frontier, "build_surfaces_manifest", lambda ns: {
        "surfaces": [{"id": "khipu", "title": "Khipu evidence", "label": "MODELED"}],
    })
    monkeypatch.setattr(brain, "_harvest_files", lambda: [])
    monkeypatch.setattr(brain, "_iter_harvest_records", lambda: iter(()))
    monkeypatch.setattr(brain, "_CACHE", {})


def test_numeric_nodes_keep_historical_ids_without_formal_proof_claims():
    graph = brain.build_brain_graph()
    demos = {n["id"]: n for n in graph["nodes"] if n["kind"] == "formula"}
    assert set(demos) == {f"formula:F{i}" for i in range(1, 24)}
    assert demos["formula:F1"]["title"] == "Euler-Khipu DAG Identity"
    for node in demos.values():
        assert node["formula_namespace"] == "puriq.numeric-demo.v1"
        assert node["record_id"] == f"puriq.numeric-demo.v1:{node['formula_id']}"
        assert node["formal_binding"] == "UNKNOWN_NOT_ASSERTED"
        assert node["proof_status"] == node["lean_status"] == "UNVERIFIED"
        assert node["lean_name"] is None
        assert node["locked"] is False
        assert node["can_authorize_action"] is False
        assert node["conjecture"] is None


def test_formal_nodes_use_exact_registry_names_scope_and_source():
    graph = brain.build_brain_graph()
    snapshot = puriq.formal_registry_snapshot()
    formal = {n["formula_id"]: n for n in graph["nodes"] if n["kind"] == "formal_formula"}
    assert set(formal) == set(registry.EXPECTED_COVERED_IDS)
    assert formal["F1"]["title"] == "Replay-Hash Determinism"
    assert formal["F11"]["title"] == "Ayni Reciprocity Conservation"
    assert formal["F12"]["title"] == "Kuramoto Additive Fragment"
    for fid, node in formal.items():
        source = snapshot["formulas"][fid]
        assert node["id"] == f"formal-formula:{fid}"
        assert node["formula_namespace"] == "lutar-lean.formal-f-id.v2"
        assert node["scope"] == source["scope"]
        assert node["caveat"] == source["caveat"]
        assert node["theorem_refs"] == source["theorem_refs"]
        assert node["source_url"] == source["source_url"]
        assert node["source_pin"] == source["source"]
        assert registry.FORMAL_COMMIT in node["source_url"]
        assert node["registry_digest"] == snapshot["registry_digest"]
        assert node["signature_status"] == "UNSIGNED"
        assert node["kernel_mapping"] == "UNKNOWN_NOT_ASSERTED"
        assert node["can_authorize_action"] is False
        assert node["applicability_required"] is True
        assert node["runtime_applicability"] == "NOT_ESTABLISHED"
        assert node["execution_authority"] is False
    assert {fid for fid, node in formal.items() if node["locked"]} == set(registry.EXPECTED_LOCKED_IDS)
    assert formal["F23"]["maturity"] == "CONJECTURE_1_ADVISORY"
    assert formal["F23"]["locked"] is False
    assert graph["doctrine"]["locked_count"] == graph["summary"]["locked_flagged"] == 8


def test_matching_identifiers_do_not_create_semantic_mapping_edges():
    graph = brain.build_brain_graph()
    formal_ids = {n["id"] for n in graph["nodes"] if n["kind"] == "formal_formula"}
    formal_links = [link for link in graph["links"]
                    if link["source"] in formal_ids or link["target"] in formal_ids]
    assert len(formal_links) == len(formal_ids) == 9
    assert all(link["rel"] == "formal-formula-endpoint" for link in formal_links)
    assert all(link["target"] == "endpoint:/api/a11oy/v1/puriq/formulas" for link in formal_links)


def test_registry_failure_does_not_fall_back_to_legacy_locked_labels(monkeypatch):
    def unavailable(**kwargs):
        raise ValueError("formula authority digest mismatch")

    monkeypatch.setattr(registry, "load_registry", unavailable)
    graph = brain.build_brain_graph()
    assert len([n for n in graph["nodes"] if n["kind"] == "formula"]) == 23
    assert not any(n["kind"] == "formal_formula" for n in graph["nodes"])
    assert not any(n.get("locked") for n in graph["nodes"])
    assert graph["doctrine"]["formula_authority_state"] == "UNAVAILABLE"
    assert graph["doctrine"]["locked_count"] is None
    assert graph["doctrine"]["locked_ids"] is None
    assert graph["sources"]["formal_formulas"]["state"] == "UNAVAILABLE"
    assert graph["sources"]["formal_formulas"]["locked_proven_count"] is None


def test_harvest_cannot_supply_formal_authority_or_mapping_edges(monkeypatch):
    records = [
        ("node", {"id": "formal-formula:F999", "kind": "formal_formula", "label": "Claimed proof"}),
        ("node", {"id": "paper:untrusted", "kind": "formal_formula", "label": "Claimed proof"}),
        ("edge", {"src": "formula:F1", "dst": "formal-formula:F1", "rel": "proves"}),
    ]
    monkeypatch.setattr(brain, "_iter_harvest_records", lambda: iter(records))
    graph = brain.build_brain_graph()
    assert not any(n["id"] in {"formal-formula:F999", "paper:untrusted"} for n in graph["nodes"])
    assert not any(link["rel"] == "proves" for link in graph["links"])
    assert graph["sources"]["harvest"]["reserved_formula_nodes_rejected"] == 2
    assert graph["sources"]["harvest"]["unproved_formal_links_rejected"] == 1


def test_cached_graph_drops_formal_claims_when_registry_becomes_unavailable(monkeypatch):
    assert brain.get_brain_graph()["summary"]["locked_flagged"] == 8

    def unavailable(**kwargs):
        raise ValueError("formula authority digest mismatch")

    monkeypatch.setattr(registry, "load_registry", unavailable)
    graph = brain.get_brain_graph()
    assert graph["sources"]["formal_formulas"]["state"] == "UNAVAILABLE"
    assert graph["doctrine"]["locked_count"] is None
    assert not any(n["kind"] == "formal_formula" for n in graph["nodes"])


def test_public_graph_routes_share_the_same_formula_projection():
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")
    app = fastapi.FastAPI()
    brain.register(app)
    with testclient.TestClient(app) as client:
        response = client.get("/api/a11oy/v1/brain/graph")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        full = response.json()
        formal = client.get("/api/a11oy/v1/brain/graph?kind=formal_formula").json()
        demos = client.get("/api/a11oy/v1/brain/graph?kind=formula").json()
    assert formal["node_count"] == 9
    assert demos["node_count"] == 23
    assert full["node_count"] == len(full["nodes"])
    assert full["link_count"] == len(full["links"])
    assert formal["sources"]["formal_formulas"]["registry_digest"] == puriq.formal_registry_snapshot()["registry_digest"]
    assert not any(node["locked"] for node in demos["nodes"])


def test_graph_projection_does_not_evaluate_or_rewrite_numerical_sources(monkeypatch):
    before = copy.deepcopy(puriq.FORMULA_META)

    def forbidden(*args, **kwargs):
        raise AssertionError("read-only graph must not evaluate numerical cases")

    for name in ("live_snapshot", "_receipt_chain"):
        if hasattr(puriq, name):
            monkeypatch.setattr(puriq, name, forbidden)
    brain.build_brain_graph()
    assert puriq.FORMULA_META == before
