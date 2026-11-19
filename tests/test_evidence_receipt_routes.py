#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real read-only route with a reviewed receipt release artifact."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from szl_evidence_graph import canonical_json, register
from szl_evidence_receipts import build_bundle, decode_bundle, import_receipt

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "evidence_graph_receipts.json"
IDENTITY_KEYS = (
    "A11OY_SOURCE_REVISION", "GIT_COMMIT", "SOURCE_REVISION", "SZL_GIT_SHA",
    "A11OY_RUNTIME_REVISION", "HF_REVISION",
)


@pytest.fixture(autouse=True)
def isolated_identity(monkeypatch):
    for key in IDENTITY_KEYS:
        monkeypatch.delenv(key, raising=False)


def fixture_bundle(path):
    raw = b'{"schema":"fixture/v1","status":"OK","prompt":"DO_NOT_EXPORT"}'
    edge = import_receipt(
        raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_uri="https://huggingface.co/datasets/example/receipts/resolve/"
        + "b" * 40 + "/result.json",
        kind="evaluation",
        observed_at="2026-11-16T20:00:00Z",
    )
    path.write_text(canonical_json(build_bundle([edge])), encoding="utf-8")
    return edge


def test_release_catalog_only_contains_explicit_public_receipt_observations(monkeypatch):
    expected = {
        "191f3f6b15394561dd584c69ad789b9d4d9de174c6f8d488ee5dd1892d889f46",
        "ff11fd7996d15df46e7944b728dd150b45a64271735aa0e8a622a41f06787a5e",
    }
    edges = decode_bundle(CATALOG.read_bytes())
    assert {edge.artifact_sha256 for edge in edges} == expected
    assert {edge.subject["kind"] for edge in edges} == {"training", "evaluation"}
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    register(app)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/evidence/graph")
        assert response.status_code == 200
        result = response.json()
        assert result["state"] == "OBSERVED"
        assert result["receipt_bundle"]["edge_count"] == 2
        assert result["receipt_bundle"]["signature_status"] == "UNSIGNED"
        assert result["graph"]["edge_count"] == 3
        observed = [e for e in result["graph"]["edges"] if e["subject"]["kind"] != "runtime"]
        assert {e["artifact_sha256"] for e in observed} == expected
        for edge in observed:
            assert edge["verdict"] == "OBSERVED"
            assert edge["source_revision"] is None
            assert edge["runtime"] == {}
            assert edge["parents"] == []
            assert edge["authority"]["execution_authorized"] is False
            assert edge["evidence"]["claims_verified"] is False


def test_receipts_are_loaded_once_and_get_neither_reads_nor_rewrites_catalog(tmp_path, monkeypatch):
    path = tmp_path / "receipts.json"
    edge = fixture_bundle(path)
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    register(app, receipt_bundle_path=path)
    path.unlink()
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get("/api/a11oy/v1/evidence/query?subject_kind=evaluation")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            result = response.json()
            assert result["graph"]["selected_edge_count"] == 1
            assert result["graph"]["edges"][0]["receipt_id"] == edge.receipt_id
            assert "DO_NOT_EXPORT" not in response.text
    assert not path.exists()


@pytest.mark.parametrize("contents, reason", [
    (None, "RECEIPT_BUNDLE_UNREADABLE"),
    (b'{"schema":"wrong"}', "RECEIPT_BUNDLE_INVALID"),
    (b'{"edges":[],"edges":[1]}', "RECEIPT_BUNDLE_INVALID"),
])
def test_invalid_catalog_does_not_hide_runtime_or_leak_paths(tmp_path, monkeypatch, contents, reason):
    path = tmp_path / "sensitive-local-name.json"
    if contents is not None:
        path.write_bytes(contents)
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    register(app, receipt_bundle_path=path)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/evidence/graph")
        result = response.json()
        assert result["state"] == "DEGRADED"
        assert result["runtime_identity_state"] == "OBSERVED"
        assert result["receipt_bundle"]["state"] == "UNAVAILABLE"
        assert result["receipt_bundle"]["reason"] == reason
        assert result["graph"]["edge_count"] == 1
        assert result["graph"]["edges"][0]["subject"]["kind"] == "runtime"
        assert str(path) not in response.text
        assert "sensitive-local-name" not in response.text


def test_historical_receipts_cannot_fill_missing_runtime_identity(tmp_path):
    path = tmp_path / "receipts.json"
    fixture_bundle(path)
    app = FastAPI()
    register(app, receipt_bundle_path=path)
    with TestClient(app) as client:
        result = client.get("/api/a11oy/v1/evidence/graph").json()
        assert result["state"] == "UNAVAILABLE"
        assert result["runtime_identity_state"] == "UNAVAILABLE"
        assert result["reason"] == "NO_EXPLICIT_RUNTIME_IDENTITY_CONFIGURED"
        assert result["receipt_bundle"]["state"] == "OBSERVED"
        assert result["graph"]["edge_count"] == 1
        assert result["graph"]["edges"][0]["source_revision"] is None


def test_query_bounds_and_openapi_work_with_the_release_catalog(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    register(app)
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 200
        full = client.get("/api/a11oy/v1/evidence/graph?limit=1").json()
        assert full["graph"]["edge_count"] == 1
        assert full["graph"]["bounded"] is True
        selected = client.get(
            "/api/a11oy/v1/evidence/query?subject_kind=training&verdict=OBSERVED"
        ).json()
        assert selected["graph"]["selected_edge_count"] == 1
        assert selected["graph"]["edges"][0]["subject"]["kind"] == "training"
        assert client.get("/api/a11oy/v1/evidence/graph?limit=0").status_code == 422
        assert client.get("/api/a11oy/v1/evidence/graph?limit=257").status_code == 422
        assert client.get("/api/a11oy/v1/evidence/query?verdict=READY").status_code == 400


def test_receipt_catalog_packaging_uses_existing_root_copy():
    from scripts.build_gdw_installed_source_manifest import _instructions
    import shlex
    _, instructions = _instructions((ROOT / "Dockerfile").read_bytes())
    rows = [
        line for kind, _, line in instructions
        if kind == "COPY" and "evidence_graph_receipts.json" in line
    ]
    assert len(rows) == 1
    values = shlex.split(rows[0])
    assert "szl_evidence_graph.py" in values
    assert "szl_evidence_receipts.py" in values
    assert values[-1] == "./"


@pytest.mark.parametrize("observed_at", [
    "0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00",
])
def test_timestamp_overflow_degrades_catalog_without_aborting_registration(tmp_path, monkeypatch, observed_at):
    path = tmp_path / "receipts.json"
    fixture_bundle(path)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    bundle["edges"][0]["evidence"]["observed_at"] = observed_at
    unsigned = {key: bundle[key] for key in ("schema", "signature_status", "edges")}
    bundle["digest_sha256"] = hashlib.sha256(canonical_json(unsigned).encode()).hexdigest()
    path.write_text(canonical_json(bundle), encoding="utf-8")
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    register(app, receipt_bundle_path=path)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/evidence/graph")
        assert response.status_code == 200
        result = response.json()
        assert result["state"] == "DEGRADED"
        assert result["runtime_identity_state"] == "OBSERVED"
        assert result["receipt_bundle"]["state"] == "UNAVAILABLE"
        assert result["receipt_bundle"]["reason"] == "RECEIPT_BUNDLE_INVALID"


def test_static_lineage_route_is_read_only_and_never_admits_execution(tmp_path):
    path = tmp_path / "receipts.json"
    fixture_bundle(path)
    app = FastAPI()
    register(app, receipt_bundle_path=path)
    path.unlink()
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        assert "/api/a11oy/v1/evidence/openlineage" in schema["paths"]
        for _ in range(2):
            result = client.get("/api/a11oy/v1/evidence/openlineage")
            assert result.status_code == 200
            assert result.headers["cache-control"] == "no-store"
            event = result.json()
            assert event["schemaURL"].endswith("#/$defs/JobEvent")
            assert "run" not in event and "eventType" not in event
            assert event["job"]["name"] == "observed_graph_snapshot_projection"
            assert len(event["inputs"]) == 1
            assert len(event["outputs"]) == 1
            assert "DO_NOT_EXPORT" not in result.text
    assert not path.exists()


def test_static_lineage_rejects_absent_or_invalid_catalog(tmp_path, monkeypatch):
    path = tmp_path / "missing.json"
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    register(app, receipt_bundle_path=path)
    with TestClient(app) as client:
        result = client.get("/api/a11oy/v1/evidence/openlineage")
        assert result.status_code == 503
        assert result.json() == {
            "state": "UNAVAILABLE", "reason": "RECEIPT_BUNDLE_UNAVAILABLE",
        }
        assert result.headers["cache-control"] == "no-store"
