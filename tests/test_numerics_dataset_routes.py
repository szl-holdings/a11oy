# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_numerics_dataset as dataset


def _payload(case, run_id="route-run"):
    return {
        "schema": dataset.INGEST_SCHEMA,
        "run_id": run_id,
        "case_id": case["case_id"],
        "engine": "octave",
        "outcome": {"state": "RESULT", "values": case["construction_reference"]["values"]},
        "engine_evidence": {
            "version": "octave test",
            "version_evidence_sha256": "a" * 64,
            "executable_sha256": "b" * 64,
            "license_state": "OPERATOR_REVIEWED",
            "offline_license_state": "NOT_APPLICABLE",
        },
        "containment": {"network_state": "DENIED", "evidence_sha256": "c" * 64},
        "resources": {
            "wall_time_ns": 100,
            "child_user_cpu_ns": None,
            "child_system_cpu_ns": None,
            "peak_resident_bytes": None,
            "request_bytes": 100,
            "response_bytes": 100,
            "log_bytes": 0,
        },
        "reference": {"state": "SOURCE_UNAVAILABLE"},
        "observed_at_utc": "2026-07-12T12:00:00Z",
    }


def _client():
    app = FastAPI()
    dataset.register(app)
    return TestClient(app)


def test_status_list_case_and_result_read_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_LEDGER", str(tmp_path / "runs.ndjson"))
    client = _client()
    status = client.get("/api/a11oy/v1/numerics/dataset/status")
    assert status.status_code == 200
    assert status.json()["preregistration"]["case_count"] == 1328

    cases = client.get("/api/a11oy/v1/numerics/dataset/cases?limit=2")
    assert cases.status_code == 200
    assert len(cases.json()["items"]) == 2
    case_id = cases.json()["items"][0]["case_id"]
    detail = client.get(f"/api/a11oy/v1/numerics/dataset/cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["case_id"] == case_id
    assert detail.json()["primary_reference"]["state"] == "SOURCE_UNAVAILABLE"

    results = client.get("/api/a11oy/v1/numerics/dataset/results")
    assert results.status_code == 200
    assert results.json()["total"] == 0
    assert results.json()["ledger_semantics"] == "APPEND_ONLY_NEWEST_FIRST"

    curriculum = client.get("/api/a11oy/v1/numerics/dataset/curriculum/formulas")
    assert curriculum.status_code == 200
    assert curriculum.json()["counts"]["eligible"] == 23
    assert curriculum.json()["proof_uplift"] == curriculum.json()["trust_uplift"] == 0


def test_result_route_is_fail_closed_until_authenticated(tmp_path, monkeypatch):
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_LEDGER", str(tmp_path / "runs.ndjson"))
    monkeypatch.delenv("A11OY_NUMERICS_DATASET_INGEST_TOKEN_SHA256", raising=False)
    client = _client()
    case = dataset.get_case(dataset.list_cases(limit=1, operation="MATRIX_SOLVE")["items"][0]["case_id"])
    assert client.post("/api/a11oy/v1/numerics/dataset/results", json=_payload(case)).status_code == 503

    token = "local-test-token"
    monkeypatch.setenv("A11OY_NUMERICS_DATASET_INGEST_TOKEN_SHA256", hashlib.sha256(token.encode()).hexdigest())
    assert client.post(
        "/api/a11oy/v1/numerics/dataset/results",
        json=_payload(case),
        headers={"x-a11oy-numerics-ingest-key": "wrong"},
    ).status_code == 401
    accepted = client.post(
        "/api/a11oy/v1/numerics/dataset/results",
        json=_payload(case),
        headers={"x-a11oy-numerics-ingest-key": token},
    )
    assert accepted.status_code == 201
    assert accepted.json()["row_state"] == "RESULT"
    assert accepted.json()["evidence_origin"] == "AUTHENTICATED_APPEND_ONLY_INGESTION_NOT_LOCAL_ENGINE_EXECUTION"


def test_service_docker_and_frontend_are_wired_before_spa_catchalls():
    root = Path(__file__).resolve().parents[1]
    serve = (root / "serve.py").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    holographic = (root / "static" / "3d" / "holographic.html").read_text(encoding="utf-8")
    surface = (root / "static" / "3d" / "surfaces" / "numericsdataset.js").read_text(encoding="utf-8")
    assert serve.index("import szl_numerics_dataset") < serve.index('@app.api_route("/api/a11oy/{path:path}"')
    assert "COPY szl_numerics_dataset.py ./" in dockerfile
    assert "COPY numerics/ ./numerics/" in dockerfile
    assert 'id: "numericsdataset"' in holographic
    assert "/api/a11oy/v1/numerics/dataset/status" in surface
    assert "/api/a11oy/v1/numerics/dataset/curriculum/formulas" in surface
    assert "preregistered inputs" in surface
    assert "proof/trust uplift is always zero" in surface
