#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Registered completion routes refuse before parsing or effects.

Most cases use SIMULATED routing, completion, retrieval and receipt doubles.
Explicit real-router cases run pure deterministic math and the no-model stub;
their unsigned receipt emitter alone remains SIMULATED. No transport, model,
signature or runtime readiness is inferred from these local responses.
"""
import asyncio
import contextlib
import hashlib
import io
import json
import socket
import types
import urllib.request
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

import szl_operator_auth as opauth


ROUTES = (
    "/api/a11oy/v1/code/route",
    "/api/a11oy/v1/code/auto",
    "/api/a11oy/v1/code/complete",
)
OPERATOR = "completion-test-secret-not-real"
OPERATOR_HEADERS = {"Authorization": f"Bearer {OPERATOR}"}
TOKEN_NAMES = (
    "A11OY_GPU_TOKEN", "LOCAL_LLM_TOKEN", "VLLM_API_KEY", "HF_ROUTER_TOKEN",
    "HF_TOKEN", "HF_API_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN", "Token",
)


@pytest.fixture
def surface(monkeypatch, tmp_path):
    for name in TOKEN_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("SZL_SECOND_BRAIN_RAG", raising=False)
    monkeypatch.setenv(opauth.OPERATOR_KEY_ENV, OPERATOR)
    monkeypatch.setenv(opauth.SECOND_APPROVER_KEY_ENV, "")
    for name, filename in (
        ("A11OY_CODE_DB", "code.sqlite3"),
        ("A11OY_CODE_SANDBOX", "sandbox"),
        ("A11OY_REACT_DB", "react.sqlite3"),
    ):
        monkeypatch.setenv(name, str(tmp_path / filename))
    monkeypatch.setenv("A11OY_ENERGY_AUTOSTART", "0")
    monkeypatch.setenv("A11OY_ORG_RAG_AUTOSTART", "0")
    monkeypatch.setenv("A11OY_EVAL_AUTORUN_INTERVAL_SEC", "0")

    def no_transport(*_args, **_kwargs):
        raise AssertionError("external transport is forbidden in this suite")

    original_connect = socket.socket.connect

    def internal_connect(sock, address):
        # Windows asyncio creates its internal socketpair over loopback.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return no_transport()

    monkeypatch.setattr(urllib.request, "urlopen", no_transport)
    monkeypatch.setattr(socket.socket, "connect", internal_connect)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import serve

    original_router = serve._a11oy_code_router
    tier = {"tier": "SIMULATED", "model_id": "synthetic-model", "role": "test"}
    routed = {
        "tier_used": tier["tier"], "organ_routed": "code", "lambda_signal": None,
        "evidence_class": "SIMULATED",
    }
    route = Mock(return_value=routed)
    router = types.SimpleNamespace(
        route=route, _BY_TIER={tier["tier"]: tier}, TIERS=[tier],
        sha256=hashlib.sha256,
        tiers_payload=lambda: {"evidence_class": "SIMULATED", "tiers": [tier]},
    )
    original_complete = serve._ac_complete
    complete = Mock(return_value=(
        "SIMULATED completion", "deterministic", {"evidence_class": "SIMULATED"},
    ))
    retrieve = Mock(side_effect=no_transport)
    receipt = Mock(return_value={
        "digest": "a" * 64, "signed": False, "index": 0,
        "evidence_class": "SIMULATED",
    })
    parser = AsyncMock(wraps=serve._safe_json_body)
    monkeypatch.setattr(serve, "_a11oy_code_router", router)
    monkeypatch.setattr(serve, "_ac_complete", complete)
    monkeypatch.setattr(serve, "_ac_sb_retrieve", retrieve)
    monkeypatch.setattr(serve, "_safe_json_body", parser)
    monkeypatch.setattr(serve.app.state, "szl_emit_signed_receipt", receipt, raising=False)
    return types.SimpleNamespace(
        serve=serve, client=TestClient(serve.app), tier=tier, route=route,
        complete=complete, retrieve=retrieve, receipt=receipt, parser=parser,
        original_complete=original_complete, original_router=original_router,
    )


def _assert_no_effects(surface, *, parsed=False):
    if not parsed:
        surface.parser.assert_not_called()
    surface.route.assert_not_called()
    surface.complete.assert_not_called()
    surface.retrieve.assert_not_called()
    surface.receipt.assert_not_called()


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("headers", (
    {},
    {"Authorization": "Bearer wrong"},
    {"Authorization": "Bearer "},
    {"Authorization": f"Basic {OPERATOR}"},
    {opauth.SECOND_APPROVER_HEADER: "body-independent-test-approver"},
))
def test_unauthorized_registered_requests_refuse_before_parsing(surface, path, headers):
    response = surface.client.post(path, headers=headers, json={
        "query": "synthetic question", "operator": True,
        "two_person_attested": True, "authorization": OPERATOR,
    })
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    assert response.headers.get("www-authenticate") == "Bearer"
    _assert_no_effects(surface)


@pytest.mark.parametrize("path", ROUTES)
def test_unset_server_key_refuses_even_matching_presented_token(surface, monkeypatch, path):
    monkeypatch.setenv(opauth.OPERATOR_KEY_ENV, "")
    response = surface.client.post(path, headers=OPERATOR_HEADERS, content=b"{not-json")
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    assert response.json()["credential_configured"] is False
    _assert_no_effects(surface)


@pytest.mark.parametrize("path", ROUTES)
def test_principal_resolver_error_denies_before_parsing(surface, monkeypatch, path):
    resolver = Mock(side_effect=ValueError("synthetic principal resolver failure"))
    monkeypatch.setattr(opauth, "principal", resolver)
    response = surface.client.post(path, headers=OPERATOR_HEADERS, content=b"{not-json")
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    resolver.assert_called_once()
    _assert_no_effects(surface)


@pytest.mark.parametrize("path", ROUTES)
def test_operator_helper_failure_blocks_before_parsing(surface, monkeypatch, path):
    refusal = Mock(side_effect=ImportError("synthetic helper unavailable"))
    monkeypatch.setattr(opauth, "operator_refusal", refusal)
    response = surface.client.post(path, headers=OPERATOR_HEADERS, content=b"{not-json")
    assert response.status_code == 503
    assert response.json()["status"] == "BLOCKED"
    refusal.assert_called_once()
    _assert_no_effects(surface)


def test_direct_anonymous_request_cannot_read_poison_body(surface):
    request = types.SimpleNamespace(
        headers={}, state=types.SimpleNamespace(),
        json=AsyncMock(side_effect=AssertionError("body must not be read")),
    )
    response = asyncio.run(surface.serve._ac_route_impl(request, auto=False))
    assert response.status_code == 401
    request.json.assert_not_called()
    _assert_no_effects(surface)


@pytest.mark.parametrize("path", ROUTES)
def test_authorized_registered_route_keeps_simulated_completion_and_receipt(surface, path):
    query = "synthetic coding question"
    response = surface.client.post(path, headers=OPERATOR_HEADERS, json={"query": query})
    assert response.status_code == 200
    out = response.json()
    assert out["response"] == "SIMULATED completion"
    assert out["generation"]["evidence_class"] == "SIMULATED"
    assert out["receipt"]["emitted"] is True
    assert out["receipt"]["receipt_signed"] is False
    surface.parser.assert_awaited_once()
    surface.route.assert_called_once()
    assert surface.route.call_args.args == (query,)
    assert surface.route.call_args.kwargs["auto"] is path.endswith("/auto")
    surface.complete.assert_called_once_with(query, surface.tier, "code")
    surface.retrieve.assert_not_called()
    surface.receipt.assert_called_once()
    assert surface.receipt.call_args.args[0]["query_digest"] == hashlib.sha256(
        query.encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("query", (None, 42, True, 1.5, ["bad"], {"query": "bad"}))
def test_invalid_query_type_is_400_before_effects(surface, path, query):
    response = surface.client.post(path, headers=OPERATOR_HEADERS, json={"query": query})
    assert response.status_code == 400
    _assert_no_effects(surface, parsed=True)


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("query", ("a" * 8193, "\u00e9" * 4097, "\ud800"),
                         ids=("ascii-over-limit", "utf8-over-limit", "invalid-utf8"))
def test_oversize_or_invalid_utf8_query_is_400_before_effects(surface, path, query):
    body = json.dumps({"query": query}, ensure_ascii=True).encode("ascii")
    response = surface.client.post(
        path, headers={**OPERATOR_HEADERS, "Content-Type": "application/json"}, content=body,
    )
    assert response.status_code == 400
    _assert_no_effects(surface, parsed=True)


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("query", ("a" * 8192, "\u00e9" * 4096),
                         ids=("ascii-exact-limit", "utf8-exact-limit"))
def test_exact_utf8_byte_limit_is_accepted_without_truncation(surface, path, query):
    response = surface.client.post(path, headers=OPERATOR_HEADERS, json={"query": query})
    assert response.status_code == 200
    assert surface.route.call_args.args == (query,)
    assert surface.complete.call_args.args[0] == query
    surface.receipt.assert_called_once()
    surface.retrieve.assert_not_called()


@pytest.mark.parametrize("path", ROUTES)
def test_authorized_malformed_json_is_400_before_effects(surface, path):
    response = surface.client.post(path, headers=OPERATOR_HEADERS, content=b"{not-json")
    assert response.status_code == 400
    surface.parser.assert_awaited_once()
    _assert_no_effects(surface, parsed=True)


@pytest.mark.parametrize("path", (
    "/api/a11oy/v1/code/health", "/api/a11oy/v1/code/tiers",
))
def test_code_read_surfaces_stay_public_without_emission(surface, monkeypatch, path):
    monkeypatch.setenv(opauth.OPERATOR_KEY_ENV, "")
    response = surface.client.get(path)
    assert response.status_code == 200
    _assert_no_effects(surface)


def test_default_off_preserves_original_generation_messages(surface, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "synthetic-inference-token-not-real")
    chat = Mock(return_value={
        "ok": True, "text": "SIMULATED answer", "model": "synthetic-model",
        "display": "synthetic-model", "license": "SIMULATED", "attempts": 1,
    })
    monkeypatch.setattr(surface.serve, "_ac_hf_chat", chat)
    assert surface.serve._ac_second_brain_rag_enabled() is False
    text, mode, meta = surface.original_complete("synthetic query", surface.tier, "code")
    assert text == "SIMULATED answer" and mode == "generative"
    assert "second_brain_rag" not in meta
    assert chat.call_args.args[0] == [
        {"role": "system", "content": (
            "You are a11oy Code, a governed open-weight coding assistant. Answer the "
            "user's coding question directly and correctly. Be concise and include "
            "runnable code when relevant."
        )},
        {"role": "user", "content": "synthetic query"},
    ]
    surface.retrieve.assert_not_called()
    surface.receipt.assert_not_called()


@pytest.mark.parametrize("path", ROUTES)
def test_real_router_registered_completion_without_inference(surface, monkeypatch, path):
    monkeypatch.setattr(surface.serve, "_a11oy_code_router", surface.original_router)
    monkeypatch.setattr(surface.serve, "_ac_complete", surface.original_complete)
    assert surface.serve._ac_hf_token() == ""
    assert surface.serve._ac_second_brain_rag_enabled() is False
    response = surface.client.post(path, headers=OPERATOR_HEADERS, json={
        "query": "synthetic plain question", "axis_scores": [0.4] * 13,
    })
    assert response.status_code == 200
    out = response.json()
    assert out["tier_used"] in {tier["tier"] for tier in surface.original_router.TIERS}
    assert out["lambda_signal"] == pytest.approx(0.4)
    assert out["mode"] == "deterministic"
    assert out["generation"] == {"backend": "local-deterministic", "configured": False}
    assert out["response"].startswith("[DETERMINISTIC]")
    assert "PLACEHOLDER" in out["lambda_receipt"]["signature_status"]
    assert out["receipt"]["emitted"] is True
    assert out["receipt"]["receipt_signed"] is False
    surface.parser.assert_awaited_once()
    surface.receipt.assert_called_once()
    surface.route.assert_not_called()
    surface.complete.assert_not_called()
    surface.retrieve.assert_not_called()


def test_real_router_binds_flat_source_and_public_seven_tiers(surface, monkeypatch):
    expected = Path(surface.serve.__file__).with_name("a11oy_code.py").resolve()
    assert Path(surface.original_router.__file__).resolve() == expected
    monkeypatch.setattr(surface.serve, "_a11oy_code_router", surface.original_router)
    monkeypatch.setenv(opauth.OPERATOR_KEY_ENV, "")
    response = surface.client.get("/api/a11oy/v1/code/tiers")
    assert response.status_code == 200
    out = response.json()
    assert out["count"] == 7
    assert out["tiers"] == surface.original_router.TIERS
    assert len(out["organ_mapping"]) == 7
    _assert_no_effects(surface)
