#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Actual status route never equates provider readiness with content admission."""
import importlib
import hashlib
import json

import pytest


@pytest.mark.parametrize("backend_ready", [False, True])
def test_status_requires_scoped_content_admission(monkeypatch, tmp_path, backend_ready):
    for key, name in (("A11OY_CODE_DB", "code.db"),
                      ("A11OY_CODE_SANDBOX", "sandbox"),
                      ("A11OY_REACT_DB", "react.sqlite3"),
                      ("A11OY_AGENT_REFLECT_DB", "reflect.db")):
        monkeypatch.setenv(key, str(tmp_path / name))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    orchestrator = importlib.import_module("a11oy_code_orchestrator")
    calls = []

    async def forbidden_model(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Status must not call a synthesis backend")

    monkeypatch.setattr(orchestrator, "inference_backend_ready", lambda: backend_ready)
    monkeypatch.setattr(orchestrator, "agent_model_complete", forbidden_model)
    monkeypatch.setattr(orchestrator._agent, "recent_reflections", lambda limit: [])
    app = FastAPI()
    orchestrator.attach(app)
    response = TestClient(app).get("/api/a11oy/code/agent/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["control_loop_available"] is True
    assert body["inference_backend_ready"] is backend_ready
    assert body["mode"] == "content_admission_unavailable"
    assert body["synthesis_admission"] == {
        "state": "UNAVAILABLE", "reason": "CONTENT_ADMISSION_UNAVAILABLE"}
    assert calls == []


@pytest.mark.parametrize("path,body", [
    ("/api/a11oy/code/agent/stream", {"task": "synthesis"}),
    ("/api/a11oy/code/chat/stream", {"message": "synthesis", "agentic": True}),
])
@pytest.mark.parametrize("failure_reason", [None, "SYNTHESIS_BACKEND_FAILED", "SYNTHESIS_RESPONSE_UNAVAILABLE"])
def test_actual_streamed_loop_halt_never_claims_a_served_model(monkeypatch, tmp_path, path, body, failure_reason):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    orchestrator = importlib.import_module("a11oy_code_orchestrator")
    loop = orchestrator._agent
    monkeypatch.setattr(loop, "REFLECT_DB", str(tmp_path / "reflect.db"))
    monkeypatch.setattr(loop, "_active_flux_tier_hint", lambda task: None)
    monkeypatch.setattr(loop, "_span", lambda name: loop._SpanShim(name))
    monkeypatch.setattr(orchestrator._opauth, "principal", lambda request: {
        "operator": True, "two_person_attested": False})
    monkeypatch.setattr(orchestrator, "_get_client", lambda: object())
    monkeypatch.setattr(orchestrator, "route", lambda *a, **kw: {
        "tier": "SIMULATED", "model": "uninvoked", "license_class": "GREEN", "reason": "unit route"})
    monkeypatch.setattr(orchestrator, "_serving_base", lambda: pytest.fail("Agentic status must not probe a model"))
    monkeypatch.setattr(orchestrator, "mem_get_conversation", lambda key: {"messages": []})
    monkeypatch.setattr(orchestrator, "mem_upsert_conversation", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "mem_add_message", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "khipu_emit", lambda *a, **kw: {"hash": None, "chain_verified": False})
    monkeypatch.setattr(orchestrator, "_agent_rag_query", lambda query: {
        "ok": True, "chunks": [{"path": f"PRIVATE_SOURCE_{index}",
            "sha256": hashlib.sha256(str(index).encode()).hexdigest()} for index in range(6)]})

    async def forbidden_model(*args, **kwargs):
        pytest.fail("Operator role did not grant source/provider admission")

    monkeypatch.setattr(orchestrator, "agent_model_complete", forbidden_model)
    if failure_reason:
        # Projection fixture for an already-failed attempt. The shared adapter
        # suite executes these failures against its real admitted local spy.
        async def failed_attempt(*args, **kwargs):
            return {"ok": False, "final_state": loop.S_HALT, "halt_reason": failure_reason,
                    "synthesis_admission": {"state": "DENIED", "reason": failure_reason}}
        monkeypatch.setattr(loop, "run_agent", failed_attempt)
    app = FastAPI()
    orchestrator.attach(app)
    response = TestClient(app).post(path, json=body)
    assert response.status_code == 200
    events = {}
    for part in response.text.split("\n\n"):
        lines = part.splitlines()
        if len(lines) >= 2 and lines[0].startswith("event: ") and lines[1].startswith("data: "):
            events[lines[0][7:]] = json.loads(lines[1][6:])
    done = events["done"]
    assert done["ok"] is False and done["final_state"] == loop.S_HALT
    expected_reason = failure_reason or "CONTENT_ADMISSION_UNAVAILABLE"
    assert done["halt_reason"] == expected_reason
    assert done["synthesis_admission"] == {
        "state": "DENIED" if failure_reason else "UNAVAILABLE", "reason": expected_reason}
    assert "PRIVATE_SOURCE" not in response.text
    if "route" in events:
        assert events["route"]["served_by"] == "NOT_INVOKED"  # no dispatch at route selection
        assert done["served_by"] == ("NOT_CONFIRMED" if failure_reason else "NOT_INVOKED")
        for event in (events["route"], done):
            assert event["served_locally"] is False and event["sovereign"] is False
            assert event["model"] is None and event["base_url"] is None
