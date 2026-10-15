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
