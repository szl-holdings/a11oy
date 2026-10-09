# SPDX-License-Identifier: Apache-2.0
"""Fail-closed contract for the deployment-readiness response."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def test_hf_sync_awaits_the_source_bound_readiness_contract_before_probe() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["readiness-verdict"]["steps"]
    command = next(
        step["run"] for step in steps
        if step.get("name") == "Probe the exact canonical deployment"
    )
    matrix = json.loads(
        (ROOT / "tools/readiness-harness/tabs.json").read_text(encoding="utf-8")
    )

    assert "--await-readiness" in command
    assert "--prime-readiness" not in command
    assert matrix["endpoints"]["/api/a11oy/v1/readiness"]["freshnessSLA"] == 300


@pytest.mark.parametrize(
    ("outcomes", "summary", "expected"),
    [
        ([{"path": "/required", "degraded": True, "unavailableSources": ["hpd"]}],
         {"degraded": 1, "blockingDegraded": 1},
         "DEGRADED: unavailable sources hpd"),
        ([{"path": "/optional", "degraded": True,
           "degradedBlocksReadiness": False, "unavailableSources": ["meter"]}],
         {"degraded": 1, "blockingDegraded": 0},
         "DEGRADED: unavailable sources meter"),
        ([{"path": "/limited", "throttled": True, "status": 429}],
         {"throttled": 1}, "throttled (429)"),
        ([{"path": "/source", "unreachable": True, "error": "timeout"}],
         {"unreachable": 1}, "unreachable (timeout)"),
        ([{"path": "/claim", "lie": True, "lies": ["unsupported status"]}],
         {"lies": 1}, "LIE: unsupported status"),
        ([{"path": "/observed", "lie": False}],
         {"ok": 1}, "No flagged outcomes in the recorded probe results."),
        ([], {}, "No endpoint results were recorded."),
    ],
)
def test_workflow_summary_preserves_negative_probe_outcomes(
    tmp_path, outcomes, summary, expected,
) -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/readiness-harness.yml").read_text(encoding="utf-8")
    )
    command = next(
        step["run"] for step in workflow["jobs"]["probe"]["steps"]
        if step.get("name") == "Verdict -> job summary"
    )
    harness = tmp_path / "harness"
    harness.mkdir()
    counts = dict(ok=0, lies=0, unreachable=0, throttled=0, degraded=0,
                  blockingDegraded=0, skippedStateChanging=0,
                  endpoints=len(outcomes))
    counts.update(summary)
    (harness / "readiness-verdict.json").write_text(json.dumps({
        "base": "https://example.invalid", "checkedAt": "2026-10-04T00:00:00Z",
        "sourceRevisionStatus": "UNAVAILABLE", "summary": counts, "results": outcomes,
    }), encoding="utf-8")
    report = tmp_path / "summary.md"
    subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", command], cwd=tmp_path,
        env={**os.environ, "HARNESS": "harness", "GITHUB_STEP_SUMMARY": str(report)},
        check=True, capture_output=True, text=True, timeout=10,
    )
    rendered = report.read_text(encoding="utf-8")
    assert expected in rendered
    assert "| blocking degraded | total degraded | skipped |" in rendered
    assert "All probed endpoints real" not in rendered
    assert "source revision: UNAVAILABLE" in rendered


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

    assert "d.matrix_available !== true" in landing
    assert "d.probe_verdict_available === false" in landing
    assert "d.probe_verdict_available !== true" in landing
    assert '"unreachable","throttled","degraded"' in landing
    assert "blockingDegraded" in landing
    assert "releaseBlockers" in landing
    assert "optionalDegraded" in landing
    assert 'displayDegraded ? "DEGRADED" : "OBSERVED"' in landing
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
            "ok": 5,
            "skippedStateChanging": 0,
            "lies": 0,
            "unreachable": 0,
            "throttled": 0,
            "degraded": 0,
            "blockingDegraded": 0,
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

    for failure in ("lies", "unreachable", "throttled"):
        verdict["summary"].update(ok=4, **{failure: 1})
        monkeypatch.setenv(
            "SZL_PROBE_VERDICT_JSON",
            json.dumps(verdict, separators=(",", ":")),
        )
        rejected = client.get(
            "/api/a11oy/v1/readiness/tab-matrix?view=summary"
        ).json()
        assert rejected["probe_verdict_available"] is False
        assert rejected["verdict_summary"] is None
        verdict["summary"].update(ok=5, **{failure: 0})

    verdict["summary"].update(ok=4, degraded=1, blockingDegraded=1)
    monkeypatch.setenv(
        "SZL_PROBE_VERDICT_JSON",
        json.dumps(verdict, separators=(",", ":")),
    )
    rejected = client.get(
        "/api/a11oy/v1/readiness/tab-matrix?view=summary"
    ).json()
    assert rejected["probe_verdict_available"] is False
    assert rejected["verdict_summary"] is None

    verdict["summary"].update(ok=4, degraded=1, blockingDegraded=0)
    monkeypatch.setenv(
        "SZL_PROBE_VERDICT_JSON",
        json.dumps(verdict, separators=(",", ":")),
    )
    optional = client.get(
        "/api/a11oy/v1/readiness/tab-matrix?view=summary"
    ).json()
    assert optional["probe_verdict_available"] is True
    assert optional["verdict_summary"]["degraded"] == 1
    assert optional["verdict_summary"]["blockingDegraded"] == 0

    verdict["summary"].update(ok=5, degraded=0, blockingDegraded=0)
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
