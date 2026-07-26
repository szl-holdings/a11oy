# SPDX-License-Identifier: Apache-2.0
"""Fail-closed contract for the deployment-readiness response."""
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def test_static_matrix_cannot_be_reported_as_a_deployment_verdict() -> None:
    source = (ROOT / "serve.py").read_text(encoding="utf-8")
    block = source.split(
        '@app.get("/api/a11oy/v1/readiness/tab-matrix")', 1
    )[1].split(
        'print("[a11oy] Readiness tab-matrix registered', 1
    )[0]

    assert '"matrix_available": False' in block
    assert '"probe_verdict_available": False' in block
    assert "_verdict_available = False" in block
    assert '_candidate_revision = verdict.get("sourceRevision")' in block
    assert "_candidate_revision == _current_revision" in block
    assert 'SZL_PROBE_VERDICT_JSON' in source
    assert 'SZL_READINESS_CANONICAL_ORIGIN' in block
    assert "_candidate_origin == _canonical_origin" in block
    assert '"available": _verdict_available' in block
    assert '"matrix_available": True' in block
    assert '"probe_verdict_available": _verdict_available' in block
    assert "canonical-origin-unbound for this deploy" in block


def test_landing_reads_matrix_and_probe_availability_separately() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "if(!d.matrix_available)" in landing
    assert "Boolean(d.probe_verdict_available)" in landing
    assert 'checked ? "REACHABLE" : "SNAPSHOT"' in landing
    assert "static contract; deployment probe pending" in landing
    assert ".data-state.amber" in landing
    for state in ("CACHED", "STALE_CACHE", "SNAPSHOT", "MODELED", "OBSERVED", "AVAILABLE", "DEGRADED"):
        assert state in landing


def test_runtime_variable_requires_exact_source_and_canonical_origin(
    monkeypatch,
) -> None:
    source_sha = "a" * 40
    origin = "https://szlholdings-a11oy.hf.space"
    verdict = {
        "schema": "szl.readiness-verdict/v1",
        "harness": "a11oy-readiness probe",
        "doctrine": "v11",
        "base": origin,
        "checkedAt": datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "sourceRevision": source_sha,
        "summary": {
            "endpoints": 5,
            "ok": 4,
            "skippedStateChanging": 0,
            "lies": 0,
            "unreachable": 0,
            "throttled": 1,
            "p95_worst": 1806,
        },
    }
    monkeypatch.setenv("SZL_GIT_SHA", source_sha)
    monkeypatch.setenv("SZL_READINESS_CANONICAL_ORIGIN", origin)
    monkeypatch.setenv(
        "SZL_PROBE_VERDICT_JSON",
        json.dumps(verdict, separators=(",", ":")),
    )

    import serve

    client = TestClient(serve.app)
    accepted = client.get(
        "/api/a11oy/v1/readiness/tab-matrix?view=summary"
    ).json()
    assert accepted["probe_verdict_available"] is True
    assert accepted["verdict_source_revision"] == source_sha
    assert accepted["verdict_base"] == origin

    verdict["base"] = "https://unrelated.example"
    monkeypatch.setenv(
        "SZL_PROBE_VERDICT_JSON",
        json.dumps(verdict, separators=(",", ":")),
    )
    rejected = client.get(
        "/api/a11oy/v1/readiness/tab-matrix?view=summary"
    ).json()
    assert rejected["probe_verdict_available"] is False
    assert rejected["verdict_summary"] is None
