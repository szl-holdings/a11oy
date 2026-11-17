#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only readiness explanations stay bound to the manifest decision.

All producer observations here are SIMULATED fixtures, not runtime attestations.
"""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_frontier_manifest as manifest


def capability(name, *, satisfied=True, reasons=None, **extra):
    return {
        "name": name,
        "category": "test",
        "status": "OK",
        "label": manifest.MEASURED,
        "ok": True,
        "provenance": {"endpoint": "/api/test/evidence"},
        "operational_evidence": {
            "predicate": "SIMULATED fixture reports its bounded condition",
            "satisfied": satisfied,
            "reasons": reasons or [],
        },
        **extra,
    }


def install(monkeypatch, sources):
    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (lambda tile=tile: tile, tile["name"], "test", tile["provenance"])
        for tile in sources
    ])
    monkeypatch.setattr(manifest, "_concept_tile_inference_provenance",
                        lambda: capability("composite fixture"))


def test_explanation_and_summary_share_one_decision_without_mutating_sources(monkeypatch):
    source = capability("reachable but stopped", satisfied=False,
                        reasons=["operator_stopped", "no_measured_jobs"])
    original = deepcopy(source)
    install(monkeypatch, [source])
    calls = []
    evaluate = manifest._tile_operational_readiness

    def counted(tile):
        calls.append(tile["name"])
        return evaluate(tile)

    monkeypatch.setattr(manifest, "_tile_operational_readiness", counted)
    result = manifest._build_manifest()
    card = result["capabilities"][0]
    explanation = card["operational_readiness"]
    blocked = result["summary"]["operational_readiness"]["blocked_tiles"][0]

    assert calls == ["reachable but stopped", "composite fixture"]
    assert source == original
    assert explanation["schema"] == "szl.frontier.capability-readiness.v1"
    assert explanation["source_reachable"] is True
    assert explanation["ready"] is False
    assert explanation["state"] == "NOT_READY"
    assert explanation["predicate"] == source["operational_evidence"]["predicate"]
    assert explanation["reasons"] == blocked["reasons"] == [
        "operator_stopped", "no_measured_jobs"]
    assert card["provenance"] == source["provenance"]
    assert result["summary"]["source_reachability"]["all_sources_reachable"] is True
    assert result["summary"]["operational_readiness"]["ready"] is False


def test_positive_card_has_same_bounded_scope_as_ready_rollup(monkeypatch):
    install(monkeypatch, [capability("observed fixture")])

    result = manifest._build_manifest()

    assert result["summary"]["operational_readiness"]["ready"] is True
    for tile in result["capabilities"]:
        explanation = tile["operational_readiness"]
        assert explanation["state"] == "READY"
        assert explanation["ready"] is True
        assert explanation["reasons"] == []
        assert explanation["predicate"] == tile["operational_evidence"]["predicate"]


def test_failed_producer_keeps_source_and_readiness_failures_visible(monkeypatch):
    install(monkeypatch, [])

    def unavailable():
        raise RuntimeError("SIMULATED source outage")

    monkeypatch.setattr(manifest, "_TILE_SPECS", [
        (unavailable, "failed source", "test", {"endpoint": "/api/test/evidence"})
    ])

    result = manifest._build_manifest()
    card = result["capabilities"][0]
    explanation = card["operational_readiness"]

    assert card["name"] == "failed source"
    assert card["label"] == manifest.UNAVAILABLE
    assert explanation["source_reachable"] is False
    assert explanation["ready"] is False
    assert explanation["state"] == "NOT_READY"
    assert explanation["predicate"] is None
    assert "source_unavailable" in explanation["reasons"]
    assert "explicit_operational_evidence_missing" in explanation["reasons"]
    assert explanation["reasons"] == result["summary"]["operational_readiness"][
        "blocked_tiles"][0]["reasons"]


@pytest.mark.parametrize("evidence", [
    None, "OK", {"satisfied": True}, {"predicate": "   ", "satisfied": True},
])
def test_missing_predicate_never_acquires_a_ready_explanation(monkeypatch, evidence):
    install(monkeypatch, [capability("invalid fixture", operational_evidence=evidence)])

    result = manifest._build_manifest()
    explanation = result["capabilities"][0]["operational_readiness"]

    assert explanation["source_reachable"] is True
    assert explanation["predicate"] is None
    assert explanation["state"] == "NOT_READY"
    assert explanation["ready"] is False
    assert explanation["reasons"]


def test_http_manifest_exposes_signature_blocker_on_repeated_reads(monkeypatch):
    source = capability("signer available", signature_required=True,
                        signature_verified=False)
    install(monkeypatch, [source])
    before = deepcopy(source)
    # Use the normal route/JSON serialization with deterministic source fixtures.
    # The tested projection must not invoke any signing function or source write.
    monkeypatch.setattr(manifest, "build_manifest", lambda app=None: manifest._build_manifest(app))
    app = FastAPI()
    manifest.register(app)

    with TestClient(app) as client:
        responses = [client.get("/api/a11oy/v1/frontier/manifest") for _ in range(2)]

    for response in responses:
        assert response.status_code == 200
        result = response.json()
        explanation = result["capabilities"][0]["operational_readiness"]
        assert explanation["source_reachable"] is True
        assert explanation["ready"] is False
        assert explanation["reasons"] == ["cryptographic_signature_not_verified"]
        assert result["summary"]["operational_readiness"]["ready"] is False
    assert source == before


@pytest.mark.parametrize("field", [
    "nodes_reachable", "reachable_nodes", "chain_length", "length",
])
def test_corrupt_count_blocks_one_tile_without_hiding_other_sources(monkeypatch, field):
    broken = capability("corrupt counter", **{field: "not-observed"})
    install(monkeypatch, [broken, capability("available sibling")])

    result = manifest._build_manifest()
    first, sibling = result["capabilities"][:2]

    assert result["ok"] is True
    assert first["operational_readiness"]["ready"] is False
    assert first["operational_readiness"]["reasons"] == [f"invalid_count_{field}"]
    assert sibling["operational_readiness"]["ready"] is True
    assert result["summary"]["operational_readiness"]["ready_tiles"] == [
        "available sibling", "composite fixture"]


@pytest.mark.parametrize("value", [True, 1.5, {}])
def test_non_counts_cannot_be_promoted_to_positive_evidence(monkeypatch, value):
    install(monkeypatch, [capability("invalid chain count", chain_length=value)])

    result = manifest._build_manifest()
    explanation = result["capabilities"][0]["operational_readiness"]

    assert explanation["state"] == "NOT_READY"
    assert explanation["reasons"] == ["invalid_count_chain_length"]


@pytest.mark.parametrize("value", [float("inf"), float("nan")])
def test_non_json_source_measurement_cannot_break_the_http_manifest(monkeypatch, value):
    install(monkeypatch, [
        capability("non-finite measurement", joules_measured_total=value),
        capability("available sibling"),
    ])
    monkeypatch.setattr(manifest, "build_manifest", lambda app=None: manifest._build_manifest(app))
    app = FastAPI()
    manifest.register(app)

    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/frontier/manifest")

    assert response.status_code == 200
    result = response.json()
    failed, sibling = result["capabilities"][:2]
    assert failed["label"] == manifest.UNAVAILABLE
    assert failed["operational_readiness"]["source_reachable"] is False
    assert "source_unavailable" in failed["operational_readiness"]["reasons"]
    assert sibling["operational_readiness"]["ready"] is True
    assert result["summary"]["operational_readiness"]["ready"] is False
