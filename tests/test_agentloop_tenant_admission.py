"""The agent-loop route must refuse unscoped writes before parsing or running."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette

import szl_agent_loop_governed as agentloop


PATH = "/api/a11oy/v1/agentloop/run"
OPERATOR = "fixture-agentloop-operator"
TENANT = "fixture-agentloop-tenant"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", OPERATOR)
    monkeypatch.setenv("A11OY_CODE_TENANT", TENANT)
    app = Starlette()
    agentloop.register(app, ns="a11oy", sign_fn=lambda _: {"signed": False})
    return TestClient(app)


def _headers(tenant=TENANT):
    return {"Authorization": f"Bearer {OPERATOR}", "X-A11oy-Tenant": tenant}


@pytest.mark.parametrize("headers,status", [
    ({}, 401),
    ({"X-A11oy-Tenant": TENANT}, 401),
    ({"Authorization": f"Bearer {OPERATOR}"}, 403),
    (_headers("other-tenant"), 403),
    (_headers(TENANT + "-extra"), 403),
])
def test_unadmitted_request_never_parses_or_runs(client, headers, status):
    with patch.object(agentloop, "run_loop", side_effect=AssertionError("ran before admission")) as run:
        response = client.post(PATH, headers=headers, content=b"{")
    assert response.status_code == status
    assert response.json()["status"] == "BLOCKED"
    assert OPERATOR not in response.text and TENANT not in response.text
    run.assert_not_called()


def test_body_claim_cannot_replace_tenant_header(client):
    with patch.object(agentloop, "run_loop", side_effect=AssertionError("ran before admission")) as run:
        response = client.post(PATH, headers={"Authorization": f"Bearer {OPERATOR}"},
                               json={"task": "fixture", "tenant": TENANT})
    assert response.status_code == 403
    run.assert_not_called()


def test_missing_tenant_configuration_fails_closed(client, monkeypatch):
    monkeypatch.delenv("A11OY_CODE_TENANT")
    with patch.object(agentloop, "run_loop", side_effect=AssertionError("ran before admission")) as run:
        response = client.post(PATH, headers=_headers(), content=b"{")
    assert response.status_code == 503
    assert response.json()["tenant_configured"] is False
    run.assert_not_called()


@pytest.mark.parametrize("failure", ["missing_module", "missing_helper", "raised_helper"])
def test_unavailable_tenant_admission_fails_closed(client, monkeypatch, failure):
    if failure == "missing_module":
        monkeypatch.setattr(agentloop, "_RUNLOOP_OK", False)
    elif failure == "missing_helper":
        monkeypatch.delattr(agentloop._runloop, "_tenant_refusal")
    else:
        def unavailable(_request):
            raise RuntimeError("fixture unavailable")
        monkeypatch.setattr(agentloop._runloop, "_tenant_refusal", unavailable)
    with patch.object(agentloop, "run_loop", side_effect=AssertionError("ran before admission")) as run:
        response = client.post(PATH, headers=_headers(), content=b"{")
    assert response.status_code == 503
    assert response.json() == {"ok": False, "status": "BLOCKED",
                               "error": "tenant admission unavailable"}
    run.assert_not_called()


def test_admitted_operator_reaches_governed_loop_without_exec_permission(client):
    observed = {"ok": True, "status_code": 200, "evidenceClass": "SIMULATED"}
    with patch.object(agentloop, "run_loop", return_value=observed) as run:
        response = client.post(PATH, headers=_headers(), json={"task": "synthetic fixture",
                                                        "mode": "chat", "consult_brain": False,
                                                        "allocate_energy": False})
    assert response.status_code == 200
    assert response.json() == observed
    assert run.call_count == 1
    assert run.call_args.args[0] == "synthetic fixture"
    assert run.call_args.kwargs["allow_exec"] is False
