#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contract tests for snapshot identity, bounded selection and read-only witnesses."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_evidence_graph as ceg


@pytest.fixture(autouse=True)
def isolated_identity(monkeypatch):
    for key in (*ceg._SOURCE_KEYS, *ceg._RUNTIME_KEYS):
        monkeypatch.delenv(key, raising=False)


def edge(name, *, kind="route", parents=(), verdict="OBSERVED", evidence=None):
    return ceg.EvidenceEdge(
        subject={"kind": kind, "id": name}, source_revision="a" * 40,
        parents=parents, verdict=verdict, evidence=evidence or {},
    )


def assert_digest_matches_returned_edges(graph):
    assert graph["digest_scope"] == "RETURNED_EDGES"
    assert graph["digest_sha256"] == ceg.sha256_hex({
        "schema": ceg.GRAPH_SCHEMA, "edges": graph["edges"],
    })
    assert graph["edge_count"] == len(graph["edges"])
    assert sum(graph["verdict_counts"].values()) == len(graph["edges"])


def test_query_hash_counts_and_parent_resolution_describe_selected_edges():
    parent = edge("parent")
    child = edge("child", kind="child", parents=(parent.receipt_id,), verdict="DEGRADED")
    source = ceg.graph_snapshot([parent, child])
    before = ceg.canonical_json(source)
    selected = ceg.query_snapshot(source, subject_kind="child")
    assert_digest_matches_returned_edges(selected)
    assert selected["source_digest_sha256"] == source["digest_sha256"]
    assert selected["digest_sha256"] != source["digest_sha256"]
    assert selected["source_edge_count"] == 2
    assert selected["selected_edge_count"] == selected["matched_edge_count"] == 1
    assert selected["missing_parent_count"] == 0
    assert selected["omitted_parent_count"] == selected["dangling_parent_count"] == 1
    assert selected["verdict_counts"]["OBSERVED"] == 0
    assert selected["verdict_counts"]["DEGRADED"] == 1
    assert ceg.canonical_json(source) == before
    empty = ceg.query_snapshot(source, subject_kind="absent")
    assert_digest_matches_returned_edges(empty)
    assert empty["edge_count"] == 0
    assert empty["ledger_head"] is None


def test_query_preserves_incomplete_source_scope_and_bounds_after_matching():
    source = ceg.graph_snapshot([edge(str(i)) for i in range(5)], max_edges=3)
    selected = ceg.query_snapshot(source, max_edges=1)
    assert selected["source_bounded"] is True
    assert selected["source_total_input_edges"] == 5
    assert selected["matched_edge_count"] == 3
    assert selected["selected_edge_count"] == 1
    assert selected["bounded"] is True
    assert_digest_matches_returned_edges(selected)


def test_query_rejects_tampered_source_snapshot():
    source = ceg.graph_snapshot([edge("one")])
    source["edges"] = []
    with pytest.raises(ValueError, match="source snapshot digest"):
        ceg.query_snapshot(source)


def test_hash_sort_is_not_exposed_as_a_ledger_or_causal_head():
    parent = edge("parent")
    child = edge("child", parents=(parent.receipt_id, "edge-missing"))
    graph = ceg.graph_snapshot([child, parent])
    assert graph["ledger_head"] is None
    assert graph["receipt_head_semantics"] == "LEXICOGRAPHIC_LAST_RECEIPT_ID"
    assert graph["causal_heads"] == [child.receipt_id]
    assert graph["causal_heads_scope"] == "RETURNED_EDGES"
    assert graph["missing_parent_count"] == graph["dangling_parent_count"] == 1
    assert graph["omitted_parent_count"] == 0


def test_input_iterator_is_stopped_at_the_documented_hard_limit():
    consumed = []
    sample = edge("repeated")
    def unbounded():
        while True:
            consumed.append(1)
            yield sample
    with pytest.raises(ValueError, match="input exceeds"):
        ceg.graph_snapshot(unbounded())
    assert len(consumed) == ceg._MAX_INPUT_EDGES + 1


@pytest.mark.parametrize("limit", [True, False, 0, 257, 1.0, "1"])
def test_invalid_output_limits_are_rejected(limit):
    with pytest.raises(ValueError, match="max_edges"):
        ceg.graph_snapshot([], max_edges=limit)


@pytest.mark.parametrize("environ,reason", [
    ({"SZL_GIT_SHA": "main"}, "MALFORMED_EXPLICIT_RUNTIME_IDENTITY"),
    ({"SZL_GIT_SHA": "A" * 40}, "MALFORMED_EXPLICIT_RUNTIME_IDENTITY"),
    ({"SZL_GIT_SHA": "a" * 40, "GIT_COMMIT": "b" * 40}, "CONFLICTING_EXPLICIT_RUNTIME_IDENTITIES"),
    ({"HF_REVISION": "a" * 40, "A11OY_RUNTIME_REVISION": "b" * 40}, "CONFLICTING_EXPLICIT_RUNTIME_IDENTITIES"),
])
def test_ambiguous_or_malformed_identity_does_not_select_a_winner(environ, reason):
    result = ceg.environment_snapshot(environ=environ)
    assert result["state"] == "DEGRADED"
    assert result["reason"] == reason
    assert result["graph"]["edges"] == []


def test_matching_explicit_aliases_and_full_sha256_are_accepted():
    source = "a" * 64
    result = ceg.environment_snapshot(environ={"SZL_GIT_SHA": source, "GIT_COMMIT": source})
    assert result["state"] == "OBSERVED"
    assert result["graph"]["edges"][0]["source_revision"] == source


def test_http_reads_do_not_recapture_environment_or_change_evidence_identity(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    monkeypatch.setattr(ceg, "_utc_now", lambda: "2026-11-16T20:00:00Z")
    app = FastAPI()
    ceg.register(app)
    with TestClient(app) as client:
        first = client.get("/api/a11oy/v1/evidence/graph").json()
        monkeypatch.setenv("SZL_GIT_SHA", "b" * 40)
        monkeypatch.setattr(ceg, "_utc_now", lambda: "2026-11-16T21:00:00Z")
        second = client.get("/api/a11oy/v1/evidence/graph").json()
    assert first["graph"] == second["graph"]
    assert first["captured_at"] == second["captured_at"] == "2026-11-16T20:00:00Z"
    assert first["retrieved_at"] != second["retrieved_at"]
    runtime = next(e for e in second["graph"]["edges"] if e["subject"]["kind"] == "runtime")
    assert runtime["source_revision"] == "a" * 40
    assert second["state_meaning"] == "EVIDENCE_AVAILABILITY_ONLY"
    assert second["execution_authority"] is False
    assert second["provenance_witness"]["state"] == "UNAVAILABLE"
    assert "SOURCE_WITNESS_UNAVAILABLE" in second["blockers"]


def test_http_query_applies_limit_after_filtering_and_retains_source_digest(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    ceg.register(app)
    with TestClient(app) as client:
        source = client.get("/api/a11oy/v1/evidence/graph").json()["graph"]
        target = source["edges"][-1]
        result = client.get("/api/a11oy/v1/evidence/query", params={
            "subject_id": target["subject"]["id"], "limit": 1,
        }).json()
    selected = result["graph"]
    assert len(source["edges"]) > 1
    assert [e["receipt_id"] for e in selected["edges"]] == [target["receipt_id"]]
    assert selected["source_digest_sha256"] == source["digest_sha256"]
    assert set(result["edge_assessments"]) == {target["receipt_id"]}
    assert_digest_matches_returned_edges(selected)


def witness_report(**updates):
    return {
        "status": "REPORTED", "source_revision": "a" * 40, "hf_revision": "b" * 40,
        "runtime_boot_id": "boot-123", "local_bytes_evidence": "MEASURED",
        "marker_sha256": "c" * 64, "binding_sha256": "d" * 64,
        "method": "GITHUB_ATTESTED_SOURCE_COPY_SET", "scope": "FINAL_APP_SOURCE_COPY_FILES",
        "hardware_attestation": False, "image_attestation": False, "execution_authority": False,
        **updates,
    }


class CachedIdentity:
    def __init__(self, report):
        self.report = report
        self.boot_id = "boot-123"
        self.reads = 0

    def snapshot(self):
        self.reads += 1
        return self.report

    def admitted(self):
        raise AssertionError("GET must not initiate attestation or mutate admission")

    start = admitted
    verify_once = admitted


def app_with_witness(monkeypatch, report):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    identity = CachedIdentity(report)
    app.state.szl_execution_observer = SimpleNamespace(
        process_identity=identity, service=SimpleNamespace(runtime_boot_id="boot-123"),
    )
    ceg.register(app)
    return app, identity


def test_cached_witness_has_real_matching_parent_and_no_authority(monkeypatch):
    app, identity = app_with_witness(monkeypatch, witness_report())
    with TestClient(app) as client:
        first = client.get("/api/a11oy/v1/evidence/graph").json()
        second = client.get("/api/a11oy/v1/evidence/graph").json()
    assert identity.reads == 2
    assert first["graph"]["digest_sha256"] == second["graph"]["digest_sha256"]
    runtime = next(e for e in first["graph"]["edges"] if e["subject"]["kind"] == "runtime")
    witness = next(e for e in first["graph"]["edges"] if e["subject"]["kind"] == "runtime-source-witness")
    assert witness["parents"] == [runtime["receipt_id"]]
    assert witness["evidence"]["relationship"] == "same-source-observation"
    assert witness["evidence"]["claims_verified"] is False
    assert witness["authority"]["execution_authorized"] is False
    assert first["edge_assessments"][witness["receipt_id"]]["freshness"] == "UNKNOWN"
    assert first["provenance_witness"]["state"] == "OBSERVED"


@pytest.mark.parametrize("updates", [{"source_revision": "e" * 40}, {"hf_revision": "f" * 40}])
def test_conflicting_witness_does_not_claim_matching_lineage(monkeypatch, updates):
    monkeypatch.setenv("HF_REVISION", "b" * 40)
    app, _ = app_with_witness(monkeypatch, witness_report(**updates))
    with TestClient(app) as client:
        result = client.get("/api/a11oy/v1/evidence/graph").json()
    witness = next(e for e in result["graph"]["edges"] if e["subject"]["kind"] == "runtime-source-witness")
    assert witness["parents"] == []
    assert witness["verdict"] == result["state"] == "DEGRADED"
    assert result["reason"] == "SOURCE_WITNESS_IDENTITY_CONFLICT"


@pytest.mark.parametrize("report,reason", [
    (witness_report(status="BLOCKED", error="DO_NOT_EXPORT"), "SOURCE_WITNESS_BLOCKED"),
    (witness_report(marker_sha256=None, error="DO_NOT_EXPORT"), "SOURCE_WITNESS_INVALID"),
    (witness_report(runtime_boot_id="secret\nDO_NOT_EXPORT"), "SOURCE_WITNESS_INVALID"),
])
def test_invalid_witness_is_explicit_and_does_not_export_internal_errors(monkeypatch, report, reason):
    app, _ = app_with_witness(monkeypatch, report)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/evidence/graph")
    result = response.json()
    assert "DO_NOT_EXPORT" not in response.text
    assert result["provenance_witness"]["state"] == result["state"] == "DEGRADED"
    assert result["provenance_witness"]["reason"] == reason
    assert not any(e["subject"]["kind"] == "runtime-source-witness" for e in result["graph"]["edges"])


def test_cached_witness_read_failure_is_unavailable_without_exception_leak(monkeypatch):
    app, identity = app_with_witness(monkeypatch, witness_report())
    def broken():
        raise RuntimeError("private-path-DO_NOT_EXPORT")
    identity.snapshot = broken
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/evidence/graph")
    assert response.status_code == 200
    assert "DO_NOT_EXPORT" not in response.text
    assert response.json()["provenance_witness"]["reason"] == "SOURCE_WITNESS_READ_FAILED"


@pytest.mark.parametrize("evidence,expected", [
    ({}, "UNKNOWN"),
    ({"observed_at": "2026-11-16T19:00:00Z"}, "UNKNOWN"),
    ({"observed_at": "2026-11-16T19:00:00Z", "valid_until": "2026-11-16T21:00:00Z"}, "EXPIRED"),
    ({"observed_at": "2026-11-16T19:00:00Z", "valid_until": "2026-11-16T22:00:00Z"}, "WITHIN_DECLARED_WINDOW"),
    ({"observed_at": "2026-11-16T22:00:00Z"}, "INVALID"),
    ({"observed_at": "2026-11-16T19:00:00"}, "INVALID"),
    ({"valid_until": "2026-11-16T22:00:00Z"}, "INVALID"),
    ({"observed_at": "2026-11-16T19:00:00Z", "valid_until": "2026-11-16T18:00:00Z"}, "INVALID"),
    ({"observed_at": "0001-01-01T00:00:00+01:00"}, "INVALID"),
])
def test_freshness_needs_an_explicit_valid_time_window(evidence, expected):
    item = edge("clock", evidence=evidence).as_dict()
    result = ceg.edge_assessment(
        item, runtime_source="a" * 40, now=datetime(2026, 11, 16, 21, tzinfo=timezone.utc),
    )
    assert result["freshness"] == expected
    assert result["source_relation"] == "MATCHES_RUNTIME_OBSERVATION"
    assert item["verdict"] == "OBSERVED"


def test_historical_observation_cannot_become_live_source_evidence(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    ceg.register(app)
    with TestClient(app) as client:
        result = client.get("/api/a11oy/v1/evidence/query?subject_kind=training").json()
    receipt = result["graph"]["edges"][0]
    assessment = result["edge_assessments"][receipt["receipt_id"]]
    assert assessment["scope"] == "HISTORICAL_ARTIFACT"
    assert assessment["source_relation"] == "UNBOUND"
    assert assessment["freshness"] == "UNKNOWN"
    assert receipt["parents"] == []
    assert receipt["authority"]["execution_authorized"] is False


def test_query_retains_parent_omission_known_by_bounded_source():
    # Find a child that sorts before its parent, so the output cap omits parent.
    parent = edge("parent")
    child = next(
        item for i in range(1000)
        if (item := edge(f"child-{i}", parents=(parent.receipt_id,))).receipt_id < parent.receipt_id
    )
    source = ceg.graph_snapshot([parent, child], max_edges=1)
    assert source["edges"][0]["receipt_id"] == child.receipt_id
    selected = ceg.query_snapshot(source)
    assert selected["missing_parent_count"] == 0
    assert selected["omitted_parent_count"] == 1
    assert selected["omitted_parent_ids"] == [parent.receipt_id]
    assert selected["unresolved_parent_count"] == 0
    # A legacy bounded snapshot without provenance of omissions stays unknown.
    source.pop("missing_parent_ids")
    source.pop("omitted_parent_ids")
    legacy = ceg.query_snapshot(source)
    assert legacy["missing_parent_count"] == 0
    assert legacy["unresolved_parent_count"] == 1


@pytest.mark.parametrize("updates", [
    {"method": "UNRECOGNIZED_METHOD"}, {"scope": "OTHER_SCOPE"},
    {"hardware_attestation": True}, {"image_attestation": True},
    {"execution_authority": True}, {"runtime_boot_id": "other-boot"},
    {"error": "RUNTIME_MARKER_CHANGED"},
])
def test_witness_cannot_upgrade_an_unrecognized_or_incoherent_report(monkeypatch, updates):
    app, _ = app_with_witness(monkeypatch, witness_report(**updates))
    with TestClient(app) as client:
        result = client.get("/api/a11oy/v1/evidence/graph").json()
    assert result["provenance_witness"]["reason"] == "SOURCE_WITNESS_INVALID"
    assert result["state"] == "DEGRADED"
    assert not any(e["subject"]["kind"] == "runtime-source-witness" for e in result["graph"]["edges"])


def test_witness_boot_must_match_the_service_owner(monkeypatch):
    app, _ = app_with_witness(monkeypatch, witness_report())
    app.state.szl_execution_observer.service.runtime_boot_id = "different-owner"
    with TestClient(app) as client:
        result = client.get("/api/a11oy/v1/evidence/graph").json()
    assert result["provenance_witness"]["reason"] == "SOURCE_WITNESS_INVALID"


def test_nested_queries_preserve_known_omitted_and_missing_parent_ids():
    parent = edge("parent")
    child = edge("child", kind="child", parents=(parent.receipt_id, "edge-missing"))
    source = ceg.graph_snapshot([parent, child])
    original = ceg.canonical_json(source)
    selected = ceg.query_snapshot(source, subject_kind="child")
    selected_edges = selected["edges"]
    selected_digest = selected["digest_sha256"]

    for _ in range(3):
        selected = ceg.query_snapshot(selected, subject_kind="child")
        assert selected["bounded"] is False
        assert selected["omitted_parent_ids"] == [parent.receipt_id]
        assert selected["omitted_parent_count"] == 1
        assert selected["missing_parent_ids"] == ["edge-missing"]
        assert selected["missing_parent_count"] == 1
        assert selected["unresolved_parent_count"] == 0
        assert selected["dangling_parent_count"] == 2
        assert selected["edges"] == selected_edges
        assert selected["digest_sha256"] == selected_digest
        assert_digest_matches_returned_edges(selected)

    empty = ceg.query_snapshot(selected, subject_kind="absent")
    assert empty["omitted_parent_ids"] == empty["missing_parent_ids"] == []
    assert empty["unresolved_parent_count"] == empty["dangling_parent_count"] == 0
    assert ceg.canonical_json(source) == original


@pytest.mark.parametrize("legacy", [False, True])
def test_nested_queries_retain_bounded_source_parent_knowledge(legacy):
    parent = edge("parent")
    child = next(
        item for i in range(1000)
        if (item := edge(f"bounded-child-{i}", parents=(parent.receipt_id, "edge-missing"))).receipt_id
        < parent.receipt_id
    )
    source = ceg.graph_snapshot([parent, child], max_edges=1)
    assert source["edges"][0]["receipt_id"] == child.receipt_id
    if legacy:
        source.pop("missing_parent_ids")
        source.pop("omitted_parent_ids")
    original = ceg.canonical_json(source)
    selected = source

    for _ in range(3):
        selected = ceg.query_snapshot(selected)
        assert selected["bounded"] is False
        assert selected["omitted_parent_ids"] == ([] if legacy else [parent.receipt_id])
        assert selected["omitted_parent_count"] == (0 if legacy else 1)
        assert selected["missing_parent_ids"] == ([] if legacy else ["edge-missing"])
        assert selected["missing_parent_count"] == (0 if legacy else 1)
        assert selected["unresolved_parent_count"] == (2 if legacy else 0)
        assert selected["dangling_parent_count"] == 2
        assert selected["edges"] == source["edges"]
        assert selected["digest_sha256"] == source["digest_sha256"]
        assert_digest_matches_returned_edges(selected)

    assert ceg.canonical_json(source) == original


def test_legacy_complete_source_still_classifies_absent_parents():
    parent = edge("parent")
    child = edge("child", kind="child", parents=(parent.receipt_id, "edge-missing"))
    source = ceg.graph_snapshot([parent, child])
    source.pop("missing_parent_ids")
    source.pop("omitted_parent_ids")

    selected = ceg.query_snapshot(source, subject_kind="child")
    assert selected["omitted_parent_ids"] == [parent.receipt_id]
    assert selected["missing_parent_ids"] == ["edge-missing"]
    assert selected["unresolved_parent_count"] == 0
    assert_digest_matches_returned_edges(selected)
