#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real tab-matrix route without starting unrelated runtime organs."""

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
PATH = "/api/a11oy/v1/readiness/tab-matrix?view=summary"
SOURCE = "a" * 40
ORIGIN = "https://szlholdings-a11oy.hf.space"


@pytest.fixture
def route_client(monkeypatch):
    # Compile the unchanged registration/import closure, rather than copying its
    # predicate into a test double or importing unrelated provider startup code.
    source_path = ROOT / "serve.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    registration = next(
        statement for statement in module.body
        if isinstance(statement, ast.Try) and any(
            isinstance(child, ast.AsyncFunctionDef)
            and child.name == "_a11oy_readiness_tab_matrix"
            for child in statement.body
        )
    )
    app = FastAPI()
    namespace = {"app": app, "__file__": str(source_path)}
    exec(compile(ast.Module(body=[registration], type_ignores=[]), str(source_path), "exec"), namespace)
    assert any(route.path == PATH.split("?")[0] for route in app.routes)
    monkeypatch.setenv("SZL_GIT_SHA", SOURCE)
    monkeypatch.setenv("SZL_READINESS_CANONICAL_ORIGIN", ORIGIN)
    return TestClient(app)


def verdict_summary(**counts):
    summary = dict(endpoints=5, ok=5, skippedStateChanging=0, lies=0,
                   unreachable=0, throttled=0, degraded=0,
                   blockingDegraded=0, p95_worst=1)
    summary.update(counts)
    return {
        "schema": "szl.readiness-verdict/v1", "harness": "a11oy-readiness probe",
        "doctrine": "v11", "base": ORIGIN, "sourceRevision": SOURCE,
        "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "summary": summary,
    }


@pytest.mark.parametrize("count", ("missing", 1, True, -1, 2, 1.5, "1", None))
def test_unprobed_required_or_unclassified_outcomes_remain_unavailable(
    route_client, monkeypatch, count,
):
    verdict = verdict_summary(ok=4, skippedStateChanging=1)
    if count != "missing":
        verdict["summary"]["requiredNotProbed"] = count
    monkeypatch.setenv("SZL_PROBE_VERDICT_JSON", json.dumps(verdict))
    response = route_client.get(PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["matrix_available"] is True
    assert body["probe_verdict_available"] is False
    assert body["available"] is False
    assert body["verdict_summary"] is None


@pytest.mark.parametrize("skipped", (0, 1))
def test_explicit_optional_skips_preserve_counts_without_claiming_a_probe(
    route_client, monkeypatch, skipped,
):
    verdict = verdict_summary(ok=5-skipped, skippedStateChanging=skipped,
                              requiredNotProbed=0)
    monkeypatch.setenv("SZL_PROBE_VERDICT_JSON", json.dumps(verdict))
    body = route_client.get(PATH).json()
    assert body["probe_verdict_available"] is True
    assert body["verdict_summary"]["endpoints"] == 5
    assert body["verdict_summary"]["ok"] == 5-skipped
    assert body["verdict_summary"]["skippedStateChanging"] == skipped
    assert body["verdict_summary"]["requiredNotProbed"] == 0


def test_legacy_complete_observations_normalize_zero_unprobed_count(route_client, monkeypatch):
    monkeypatch.setenv("SZL_PROBE_VERDICT_JSON", json.dumps(verdict_summary()))
    body = route_client.get(PATH).json()
    assert body["probe_verdict_available"] is True
    assert body["verdict_summary"]["requiredNotProbed"] == 0
