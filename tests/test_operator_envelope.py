"""Governed envelope regressions for the canonical a11oy Operator API.

The real application is exercised in-process.  Operator responses must retain
their underlying data while carrying an explicit evidence envelope.
"""

import warnings

import pytest

warnings.filterwarnings("ignore")

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(serve.app)


def _assert_envelope(body):
    assert isinstance(body, dict), f"expected a JSON object, got {type(body).__name__}"
    assert body.get("status") in ("REAL", "DEMO", "DEGRADED")
    assert isinstance(body.get("citations"), list)
    assert isinstance(body.get("fetchedAt"), str) and body["fetchedAt"]


@pytest.mark.parametrize("path", [
    "/api/a11oy/v1/operator/recommend",
    "/api/a11oy/v1/operator/ledger",
    "/api/a11oy/v2/operator/command-log",
])
def test_operator_get_surface_is_live_and_governed(client, path):
    response = client.get(path)
    assert response.status_code == 200, f"GET {path} regressed to {response.status_code}"
    _assert_envelope(response.json())


@pytest.mark.parametrize("path,payload", [
    ("/api/a11oy/v1/operator/ask", {"question": "which services are live?"}),
    ("/api/a11oy/v1/operator/act", {"action": "acknowledge", "target": "test", "note": "regression"}),
])
def test_operator_post_surface_is_live_and_governed(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 200, f"POST {path} regressed to {response.status_code}"
    _assert_envelope(response.json())


def test_operator_recommendation_payload_survives_envelope(client):
    body = client.get("/api/a11oy/v1/operator/recommend").json()
    _assert_envelope(body)
    assert isinstance(body.get("recommendations"), list)
    assert isinstance(body.get("counts"), dict)


def test_operator_ledgers_keep_receipt_records(client):
    ledger = client.get("/api/a11oy/v1/operator/ledger").json()
    command_log = client.get("/api/a11oy/v2/operator/command-log").json()
    _assert_envelope(ledger)
    _assert_envelope(command_log)
    assert isinstance(ledger.get("receipts"), list)
    assert isinstance(command_log.get("receipts"), list)
