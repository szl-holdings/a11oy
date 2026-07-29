from fastapi.testclient import TestClient
from szl_gdw.api import HONEST_LIMITATIONS, create_app
from szl_gdw.models import WorkspaceState, to_primitive


def test_capability_get_is_honest_and_receipt_free():
    client = TestClient(create_app())
    response = client.get("/v1/szl-gdw/capability")
    assert response.status_code == 200
    body = response.json()
    assert body["capability_label"] == "MODELED"
    assert body["loss_evidence"] == "UNAVAILABLE"
    assert body["receipt_on_read"] is False
    assert body["limitations"] == HONEST_LIMITATIONS


def test_step_api_returns_kernel_receipt(tmp_path):
    client = TestClient(create_app(receipt_path=tmp_path / "receipts.jsonl"))
    response = client.post(
        "/v1/szl-gdw/step",
        json={
            "state": to_primitive(WorkspaceState("session", delta_memory=(0.0, 0.0))),
            "request": "govern this",
            "allowed_experts": ["expert-a"],
            "risk_budget": 0.5,
            "created_at": "2026-07-29T00:00:00+00:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["step"] == 1
    assert body["audit"]["receipt"]["decision"] == "ACCEPT"
    assert body["limitations"] == HONEST_LIMITATIONS


def test_step_api_fails_closed_on_missing_allowlist():
    client = TestClient(create_app())
    response = client.post(
        "/v1/szl-gdw/step",
        json={
            "state": to_primitive(WorkspaceState("session")),
            "request": "govern this",
            "risk_budget": 0.5,
            "created_at": "2026-07-29T00:00:00+00:00",
        },
    )
    assert response.status_code == 200
    assert response.json()["audit"]["receipt"]["decision"] == "REJECT"
