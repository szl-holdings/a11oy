# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Tests for the sentra verdict HTTP service.
#
# These tests exercise the FastAPI application via the httpx TestClient.
# They do NOT mock sentra_immune.sentra_inspect(); they call the real function
# so the test suite validates the full chain: HTTP layer → pydantic model →
# sentra_immune pure function → HTTP response.
#
# Minimum test coverage (per Wire B remediation specification):
#   1. healthz — GET /healthz returns 200 {"status": "ok"}
#   2. verdict allow — clean payload returns decision: "allow"
#   3. verdict deny  — payload with threat keyword returns decision: "deny"
#   4. inspect no short-circuit — inspect returns ALL signals fired, not just
#      the first; the decision still reflects the full immune evaluation
#
# Run:
#   cd /repo-root && pip install -r sidecar/requirements.txt
#   pytest sidecar/tests/test_verdict_service.py -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the package root is on sys.path so `from sidecar.main import app`
# and the nested `from sentra_immune import sentra_inspect` both resolve.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sidecar.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Test 1: GET /healthz — liveness probe
# ---------------------------------------------------------------------------


def test_healthz_returns_ok(client: TestClient) -> None:
    """GET /healthz must return HTTP 200 with {"status": "ok"}."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok"}


# ---------------------------------------------------------------------------
# Test 2: POST /v1/verdict — allow path (clean payload)
# ---------------------------------------------------------------------------


def test_verdict_allow_clean_payload(client: TestClient) -> None:
    """A clean action with no threat keywords must produce decision: "allow"."""
    body = {
        "request_id": "test-req-001",
        "agent": "test-agent",
        "action": {"operation": "read", "resource": "/api/data"},
        "context": {"env": "test"},
        "axes": [0.9, 0.85, 0.95],
    }
    resp = client.post("/v1/verdict", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "allow", f"Expected allow, got: {data}"
    assert "reason" in data
    assert isinstance(data["signals"], list)
    assert len(data["signals"]) == 0, f"Expected no signals, got: {data['signals']}"
    # lambda_value should be MIN of axes = 0.85
    assert abs(data["lambda_value"] - 0.85) < 1e-9


def test_verdict_allow_mesh_router_request_shape(client: TestClient) -> None:
    """Accepts the mesh-router SentraVerdictRequest shape (actionId, kind, payload)."""
    body = {
        "actionId": "mesh-req-abc",
        "kind": "egress",
        "payload": {"url": "https://api.example.com/safe-endpoint"},
    }
    resp = client.post("/v1/verdict", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "allow"
    assert "decision" in data
    assert "reason" in data


# ---------------------------------------------------------------------------
# Test 3: POST /v1/verdict — deny path (threat keyword present)
# ---------------------------------------------------------------------------


def test_verdict_deny_threat_keyword(client: TestClient) -> None:
    """An action containing a threat keyword must produce decision: "deny"."""
    body = {
        "request_id": "test-req-002",
        "agent": "adversarial-agent",
        "action": {"operation": "execute", "command": "DROP TABLE users; --"},
        "axes": [0.9, 0.8],
    }
    resp = client.post("/v1/verdict", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "deny", f"Expected deny, got: {data}"
    assert "reason" in data
    assert data["reason"] != ""
    # At least one signal should have fired
    assert len(data["signals"]) >= 1


def test_verdict_deny_script_injection(client: TestClient) -> None:
    """An XSS payload must be denied."""
    body = {
        "request_id": "test-req-003",
        "action": {"input": "<script>alert('xss')</script>"},
    }
    resp = client.post("/v1/verdict", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "deny"


# ---------------------------------------------------------------------------
# Test 4: POST /v1/inspect — returns all signals, no short-circuit
# ---------------------------------------------------------------------------


def test_inspect_returns_all_signals_no_short_circuit(client: TestClient) -> None:
    """POST /v1/inspect must return ALL signals fired, not just the first one.

    This confirms the non-short-circuit contract: even after the first threat
    signature is detected, the service continues checking remaining signatures
    and reports each one fired.
    """
    # Payload contains TWO distinct threat signatures: "DROP TABLE" and "eval("
    body = {
        "request_id": "test-req-004",
        "agent": "inspect-test",
        "action": {
            "query": "DROP TABLE sessions",
            "script": "eval(base64_decode('malicious'))",
        },
    }
    resp = client.post("/v1/inspect", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "deny"
    # Both threat signals must appear in the signals list
    signals_str = str(data["signals"])
    assert "DROP TABLE" in signals_str, f"Expected DROP TABLE signal, got: {data['signals']}"
    assert "eval(" in signals_str, f"Expected eval( signal, got: {data['signals']}"
    assert len(data["signals"]) >= 2, (
        f"Expected at least 2 signals (no short-circuit), got {len(data['signals'])}: {data['signals']}"
    )


def test_inspect_allow_clean_payload(client: TestClient) -> None:
    """POST /v1/inspect with a clean payload must also allow and return no signals."""
    body = {
        "request_id": "test-req-005",
        "action": {"cmd": "list_files", "path": "/home/user"},
    }
    resp = client.post("/v1/inspect", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "allow"
    assert data["signals"] == []


# ---------------------------------------------------------------------------
# Test 5: Response schema compatibility with mesh-router SentraVerdict
# ---------------------------------------------------------------------------


def test_verdict_response_is_superset_of_sentra_verdict_interface(
    client: TestClient,
) -> None:
    """The response must include at minimum the fields the mesh-router reads:
    decision (str) and reason (str). Extra fields are fine.
    """
    body = {"action": {"op": "ping"}}
    resp = client.post("/v1/verdict", json=body)
    assert resp.status_code == 200
    data = resp.json()
    # Required by mesh-router SentraVerdict interface
    assert "decision" in data
    assert data["decision"] in ("allow", "deny")
    assert "reason" in data
    assert isinstance(data["reason"], str)
    # Extended fields
    assert "signals" in data
    assert "lambda_value" in data
    assert isinstance(data["lambda_value"], float)
