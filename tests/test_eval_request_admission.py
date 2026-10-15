#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real eval route without model, signing or forum effects."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_eval_arena as arena
import szl_operator_auth as auth


TOKEN = "eval-admission-test-only"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PATH = "/api/a11oy/v1/eval/run"
EXPLICIT = {"suite": "core_honest_v1", "model_id": "test-model", "execution_mode": "modeled"}


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, TOKEN)
    run = Mock(return_value={"status_code": 200, "honesty_label": "MODELED"})
    monkeypatch.setattr(arena, "run_eval", run)
    app = FastAPI()
    arena.register(app)
    with TestClient(app) as client:
        yield client, run


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer wrong"}, {"Authorization": "Bearer "},
    {"Authorization": f"Basic {TOKEN}"}, {auth.SECOND_APPROVER_HEADER: TOKEN},
])
def test_refuses_anonymous_and_wrong_identity_before_parsing(isolated, headers):
    client, run = isolated
    response = client.post(PATH, headers=headers, content="not-json")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["status"] == "BLOCKED"
    assert TOKEN not in response.text
    run.assert_not_called()


def test_missing_server_credential_denies_even_explicit_request(isolated, monkeypatch):
    client, run = isolated
    monkeypatch.delenv(auth.OPERATOR_KEY_ENV)
    assert client.post(PATH, headers=HEADERS, json=EXPLICIT).status_code == 401
    run.assert_not_called()


def test_identity_resolver_error_denies(isolated, monkeypatch):
    client, run = isolated
    monkeypatch.setattr(arena, "principal", Mock(side_effect=RuntimeError("unavailable")))
    assert client.post(PATH, headers=HEADERS, json=EXPLICIT).status_code == 401
    run.assert_not_called()


@pytest.mark.parametrize("body", ["", "{", "not-json", "null", "[]", '"text"', "0"])
def test_invalid_json_and_non_objects_never_evaluate(isolated, body):
    client, run = isolated
    response = client.post(PATH, headers=HEADERS, content=body)
    assert response.status_code == 400
    run.assert_not_called()


@pytest.mark.parametrize("body", [
    {}, {"operator": True, "two_person_attested": True},
    {"suite": "core_honest_v1", "model_id": "test-model"},
    {**EXPLICIT, "suite": None}, {**EXPLICIT, "suite": []},
    {**EXPLICIT, "suite": " "}, {**EXPLICIT, "suite_id": "different"},
    {**EXPLICIT, "model_id": None}, {**EXPLICIT, "model_id": {}},
    {**EXPLICIT, "model_id": True}, {**EXPLICIT, "model_id": ""},
    {**EXPLICIT, "execution_mode": None}, {**EXPLICIT, "execution_mode": []},
    {**EXPLICIT, "execution_mode": True}, {**EXPLICIT, "execution_mode": "LIVE"},
    {**EXPLICIT, "harness_profile_id": {}}, {**EXPLICIT, "harness_profile_id": " "},
])
def test_incomplete_or_coerced_request_cannot_select_defaults(isolated, body):
    client, run = isolated
    assert client.post(PATH, headers=HEADERS, json=body).status_code == 422
    run.assert_not_called()


@pytest.mark.parametrize("mode", ["modeled", "live"])
@pytest.mark.parametrize("suite_key", ["suite", "suite_id"])
def test_explicit_authenticated_selection_runs_once(isolated, mode, suite_key):
    client, run = isolated
    body = {suite_key: "core_honest_v1", "model_id": "test-model", "execution_mode": mode}
    response = client.post(PATH, headers=HEADERS, json=body)
    assert response.status_code == 200
    run.assert_called_once_with("core_honest_v1", "test-model", None,
                                execution_mode=mode, request_origin="http://testserver/")


def test_get_does_not_run_evaluation(isolated):
    client, run = isolated
    assert client.get(PATH, headers=HEADERS).status_code == 405
    assert client.get("/api/a11oy/v1/eval/suites").status_code == 200
    run.assert_not_called()


def test_central_middleware_blocks_before_downstream(monkeypatch):
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, TOKEN)
    reached = []

    async def downstream(scope, receive, send):
        reached.append(scope)
        raise AssertionError("anonymous request reached handler")

    client = TestClient(auth.OperatorGateMiddleware(downstream))
    try:
        for path in (PATH, PATH + "/", "/api//a11oy/v1/eval/run"):
            response = client.post(path, json=EXPLICIT)
            assert response.status_code == 401
            assert response.json()["status"] == "BLOCKED"
    finally:
        client.close()
    assert reached == []


def test_alternate_namespace_keeps_local_operator_guard(isolated):
    _, run = isolated
    app = FastAPI()
    arena.register(app, "alternate")
    with TestClient(app) as client:
        assert client.post("/api/alternate/v1/eval/run", json=EXPLICIT).status_code == 401
    run.assert_not_called()


@pytest.mark.parametrize("limits", [None, {}, [], True,
    {"max_model_requests": 1, "max_output_tokens": 1, "max_elapsed_seconds": True},
    {"max_model_requests": 1, "max_output_tokens": 1, "max_elapsed_seconds": 1, "retry": 0}])
def test_invalid_strict_limits_do_not_reach_eval(isolated, limits):
    client, run = isolated
    response = client.post(PATH, headers=HEADERS,
        json={**EXPLICIT, "execution_mode": "live", "execution_limits": limits})
    assert response.status_code == 422
    run.assert_not_called()


def test_strict_limits_do_not_silently_select_modeled_execution(isolated):
    client, run = isolated
    response = client.post(PATH, headers=HEADERS, json={**EXPLICIT,
        "execution_limits": {"max_model_requests": 1, "max_output_tokens": 1, "max_elapsed_seconds": 1}})
    assert response.status_code == 422
    run.assert_not_called()


@pytest.mark.parametrize("extra", [
    ',"model_id":"replacement"', ',"retry":0', ',"unused":NaN',
    ',"execution_limits":{"max_model_requests":1,"max_model_requests":2,"max_output_tokens":1,"max_elapsed_seconds":1}',
])
def test_strict_json_cannot_hide_ambiguous_or_extra_request_fields(isolated, extra):
    client, run = isolated
    body = ('{"suite":"core_honest_v1","model_id":"test-model","execution_mode":"live",'
            '"execution_limits":{"max_model_requests":1,"max_output_tokens":1,"max_elapsed_seconds":1}'
            + extra + '}')
    assert client.post(PATH, headers=HEADERS, content=body).status_code == 422
    run.assert_not_called()


@pytest.mark.parametrize("middleware", [False, True])
def test_strict_eval_cancel_stops_pending_worker_before_next_effect(monkeypatch, middleware):
    import asyncio
    import threading
    import httpx
    import a11oy_code_engine as engine
    import a11oy_vertical_feeds as vertical

    selected = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    suite_id = "eval-cancellation-fixture"
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, TOKEN)
    monkeypatch.setattr(engine, "_MODEL_BASE_URL", "https://eval-cancel.example/v1")
    monkeypatch.setattr(engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.setattr(engine, "_HF_TOKEN", "eval-cancel-fixture-provider")
    monkeypatch.setattr(vertical, "_HAS_KHIPU", False)
    monkeypatch.setattr(vertical, "_HAS_DSSE", False)
    monkeypatch.setitem(arena._SUITES, suite_id, {"title": "Cancellation fixture", "version": "1",
        "description": "Isolated provider fixture", "cases": [{"id": case_id,
            "input": "What is two plus two?", "expected": "4", "scorer": "exact",
            "category": "correctness"} for case_id in ("first", "second")]})
    signer, forum = Mock(), Mock()
    signer.return_value = ({"signed": False, "signatures": []}, {"mode": "UNSIGNED-LOCAL"})
    monkeypatch.setattr(arena, "_sign", signer)
    monkeypatch.setattr(arena, "_ingest_forum", forum)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls, completed = [], []
    original_client, original_run = httpx.Client, arena.run_eval
    def provider(request):
        calls.append(request)
        entered.set()
        assert release.wait(3)
        return httpx.Response(200, json={"model": selected, "choices": [{"finish_reason": "stop",
            "message": {"role": "assistant", "content": "4"}}], "usage": {"completion_tokens": 1}})
    monkeypatch.setattr(httpx, "Client", lambda **kw: original_client(
        **{**kw, "transport": httpx.MockTransport(provider)}))
    def observed_run(*args, **kwargs):
        try:
            result = original_run(*args, **kwargs)
            completed.append(result)
            return result
        finally:
            finished.set()
    monkeypatch.setattr(arena, "run_eval", observed_run)
    app = FastAPI()
    if middleware:
        @app.middleware("http")
        async def pass_through(request, call_next):
            return await call_next(request)
    arena.register(app)
    body = {"model_id": selected, "suite": suite_id, "execution_mode": "live",
            "execution_limits": {"max_model_requests": 2, "max_output_tokens": 100, "max_elapsed_seconds": 5}}
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            request = asyncio.create_task(client.post(PATH, headers=HEADERS, json=body))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                request.cancel()
                done, _ = await asyncio.wait({request}, timeout=0.5)
                cancelled_promptly = request in done
            finally:
                release.set()
            with pytest.raises(asyncio.CancelledError):
                await request
            assert await asyncio.to_thread(finished.wait, 2)
            assert cancelled_promptly, "Strict eval shielded request cancellation"
    asyncio.run(scenario())
    assert len(calls) == 1
    signer.assert_not_called()
    forum.assert_not_called()
    assert completed[0]["execution_budget"]["error"] == "EXECUTION_CANCELLED"
    assert completed[0]["execution_complete"] is False
