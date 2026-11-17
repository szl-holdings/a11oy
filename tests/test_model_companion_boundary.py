#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Shared-engine refusal tests; no strict companion or Access helper required."""

import builtins
import io
import json
import socket
import types
from email.message import Message
import urllib.request
import urllib.response

import pytest

import a11oy_code_engine as engine


ACCESS_NAMES = (
    "A11OY_MODEL_CF_ACCESS_ORIGIN", "A11OY_MODEL_CF_ACCESS_CLIENT_ID",
    "A11OY_MODEL_CF_ACCESS_CLIENT_SECRET")
MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ORIGIN = "https://model.example"
BEARER = "fixture-model-bearer"
SECRET = "fixture-model-secret"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in (*ACCESS_NAMES, "A11OY_MODEL_API_KEY", "A11OY_MODEL_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(engine, "_MODEL_BASE_URL", ORIGIN + "/v1")
    monkeypatch.setattr(engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.setattr(engine, "_HF_TOKEN", "fixture-hf-token")
    return monkeypatch


def unavailable_companion(monkeypatch, *, kind):
    original = builtins.__import__
    imports = []

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "szl_router_client":
            imports.append(name)
            if kind == "missing-entrypoint":
                return types.ModuleType(name)
            raise ModuleNotFoundError(SECRET, name=name)
        if name == "szl_model_access":
            raise AssertionError("Shared engine must not import the Access helper")
        return original(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded)
    return imports


@pytest.mark.parametrize("configuration", [
    {name: value} for name in ACCESS_NAMES for value in ("", SECRET)
] + [dict(zip(ACCESS_NAMES, (ORIGIN, "fixture-client-id", SECRET)))])
@pytest.mark.parametrize("kind", ["missing-module", "missing-entrypoint"])
def test_unavailable_companion_refuses_partial_and_complete_contracts(isolated, configuration, kind):
    for name, value in configuration.items():
        isolated.setenv(name, value)
    isolated.setenv("A11OY_MODEL_API_KEY", BEARER)
    unavailable_companion(isolated, kind=kind)
    network = []

    def refused_network(*args, **kwargs):
        network.append(True)
        raise AssertionError("A missing companion cannot dispatch")

    isolated.setattr(socket, "create_connection", refused_network)
    isolated.setattr(socket.socket, "connect", refused_network)
    isolated.setattr(urllib.request.OpenerDirector, "open", refused_network)
    assert engine._model_configured() is False
    with pytest.raises(ValueError, match="^MODEL_ACCESS_CLIENT_UNAVAILABLE$"):
        engine._model_auth_headers()
    with pytest.raises(ValueError, match="^MODEL_ACCESS_CLIENT_UNAVAILABLE$"):
        engine.strict_transport_preflight(MODEL)
    for budget in (None, object()):
        result = engine._hf_chat([{"role": "user", "content": "2 + 2"}],
            max_tokens=4, want_model=MODEL, execution_budget=budget)
        assert result["ok"] is False and result["attempts"] == 0
        assert result["error"] == "MODEL_ACCESS_CLIENT_UNAVAILABLE"
        assert SECRET not in json.dumps(result) and BEARER not in json.dumps(result)
    isolated.setattr(engine, "_resolve_harness", lambda *args: None)
    isolated.setattr(engine, "_retrieve_with_identity", lambda *args, **kwargs: ([], {}))
    for name in ("_local_chat", "_local_code", "_sandbox_exec"):
        isolated.setattr(engine, name, refused_network)
    for mode in ("chat", "code", "research"):
        result = engine.governed_turn(mode, "2 + 2", lambda _: {"signed": False},
            "fixture", want_model=MODEL, sandbox=True, allow_exec=True)
        assert result["decision"] == "DENY" and result["emitted"] is False
        assert result["answer"] is result["code"] is result["research"] is None
        assert result["inference"]["error"] == "MODEL_ACCESS_CLIENT_UNAVAILABLE"
        assert result["inference"]["attempts"] == 0
        assert result["backend"]["backend"] == "unavailable"
        assert result["executed"] is False
        assert SECRET not in json.dumps(result) and BEARER not in json.dumps(result)
    assert network == []


@pytest.mark.parametrize("base,bearer,expected", [
    (ORIGIN + "/v1", BEARER, "Bearer " + BEARER),
    ("http://model.example/v1", None, None),
    ("https://router.huggingface.co/v1", None, "Bearer fixture-hf-token"),
])
def test_all_absent_preserves_ordinary_clients_without_importing_companion(isolated, base, bearer, expected):
    isolated.setattr(engine, "_MODEL_BASE_URL", base)
    if bearer is not None:
        isolated.setenv("A11OY_MODEL_API_KEY", bearer)
    imports = unavailable_companion(isolated, kind="missing-module")
    requests = []

    class Provider(urllib.request.HTTPSHandler, urllib.request.HTTPHandler):
        handler_order = 100

        def https_open(self, request):
            requests.append(request)
            headers = Message()
            headers["Content-Type"] = "application/json"
            body = {"choices": [{"message": {"content": "4"}}]}
            response = urllib.response.addinfourl(
                io.BytesIO(json.dumps(body).encode()), headers, request.full_url, 200)
            response.msg = "fixture"
            return response

        http_open = https_open

    original = engine._model_opener

    def opener():
        value = original()
        value.add_handler(Provider())
        return value

    isolated.setattr(engine, "_model_opener", opener)
    assert engine._model_configured() is True
    assert engine._model_auth_headers() == ({} if expected is None else {"Authorization": expected})
    result = engine._hf_chat([{"role": "user", "content": "2 + 2"}],
                            max_tokens=4, want_model=MODEL)
    assert result["ok"] is True and result["attempts"] == 1
    assert len(requests) == 1 and requests[0].get_header("Authorization") == expected
    assert not any(name.lower().startswith("cf-access-") for name, _ in requests[0].header_items())
    assert imports == []


def test_all_absent_retains_existing_local_response_when_model_is_not_configured(isolated):
    isolated.setattr(engine, "_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    isolated.setattr(engine, "_HF_TOKEN", "")
    isolated.setattr(engine, "_resolve_harness", lambda *args: None)
    isolated.setattr(engine, "_retrieve_with_identity", lambda *args, **kwargs: ([], {}))
    imports = unavailable_companion(isolated, kind="missing-module")
    result = engine.governed_turn("chat", "2 + 2", lambda _: {"signed": False}, "fixture")
    assert result["decision"] == "ALLOW"
    assert result["inference"]["mode"] == "local-deterministic"
    assert result["inference"]["error"] is None and result["answer"]
    assert imports == []
