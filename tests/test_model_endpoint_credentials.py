#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Credential routing tests with actual clients and local transport fixtures."""
import io
import json
from email.message import Message
import urllib.request
import urllib.response

import httpx
import pytest

import a11oy_code_engine as engine
try:
    from szl_router_client import ExecutionBudget
except ModuleNotFoundError as exc:
    if exc.name != "szl_router_client":
        raise
    ExecutionBudget = None  # The shared Killinchu engine has no strict caller.


MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
HF_KEY = "fixture-hf-token"
CUSTOM_KEY = "fixture-custom-token"
CLIENT = httpx.Client


def completion():
    return {"model": MODEL, "choices": [{"message": {"role": "assistant", "content": "4"},
                                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(engine, "_MODEL_BASE_URL", "https://gpu.example/v1")
    monkeypatch.setattr(engine, "_HF_TOKEN", HF_KEY)
    monkeypatch.setattr(engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.delenv("A11OY_MODEL_API_KEY", raising=False)
    return monkeypatch


def install_transport(monkeypatch, mode, *, status=200, exception=None):
    seen = []
    if mode == "strict":
        def provider(request):
            seen.append(request)
            if exception:
                raise exception
            return httpx.Response(status, json=completion(),
                                  headers={"Location": "https://redirect.invalid/stolen"})

        monkeypatch.setattr(httpx, "Client", lambda **kw: CLIENT(
            **kw, transport=httpx.MockTransport(provider)))
    else:
        # Exercise urllib's real redirect/error handling without opening a socket.
        class Provider(urllib.request.HTTPSHandler, urllib.request.HTTPHandler):
            handler_order = 100

            def https_open(self, request):
                seen.append(request)
                if exception:
                    raise exception
                headers = Message()
                headers["Content-Type"] = "application/json"
                if 300 <= status < 400:
                    headers["Location"] = "https://redirect.invalid/stolen"
                response = urllib.response.addinfourl(io.BytesIO(json.dumps(completion()).encode()),
                                                      headers, request.full_url, status)
                response.msg = "fixture"
                return response

            http_open = https_open

        original = engine._model_opener

        def opener():
            value = original()
            value.add_handler(Provider())
            return value

        monkeypatch.setattr(engine, "_model_opener", opener)
    return seen


def call(mode):
    options = {}
    if mode == "strict":
        if ExecutionBudget is None:
            pytest.skip("Strict execution-budget companion is absent in this repository")
        options["execution_budget"] = ExecutionBudget({"max_model_requests": 1,
            "max_output_tokens": 4, "max_elapsed_seconds": 10})
    return engine._hf_chat([{"role": "user", "content": "2 + 2"}],
                           max_tokens=4, want_model=MODEL, **options)


def authorization(request):
    if isinstance(request, httpx.Request):
        return request.headers.get("authorization")
    return request.get_header("Authorization")


@pytest.mark.parametrize("mode", ["strict", "legacy"])
@pytest.mark.parametrize("base", ["https://router.huggingface.co/v1", "https://ROUTER.HUGGINGFACE.CO:443/v1"])
def test_official_https_origin_keeps_hf_credential(configured, mode, base):
    configured.setattr(engine, "_MODEL_BASE_URL", base)
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    seen = install_transport(configured, mode)
    assert call(mode)["ok"] is True
    assert len(seen) == 1
    assert authorization(seen[0]) == "Bearer " + HF_KEY


@pytest.mark.parametrize("mode", ["strict", "legacy"])
@pytest.mark.parametrize("base", ["https://gpu.example/v1", "https://router.huggingface.co.example/v1",
                                   "https://prefix-router.huggingface.co/v1"])
def test_custom_and_lookalike_hosts_never_inherit_hf_credential(configured, mode, base):
    configured.setattr(engine, "_MODEL_BASE_URL", base)
    seen = install_transport(configured, mode)
    assert call(mode)["ok"] is True
    assert len(seen) == 1
    assert authorization(seen[0]) is None


@pytest.mark.parametrize("mode", ["strict", "legacy"])
def test_custom_endpoint_uses_only_its_explicit_credential(configured, mode):
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    seen = install_transport(configured, mode)
    assert call(mode)["ok"] is True
    assert len(seen) == 1
    assert authorization(seen[0]) == "Bearer " + CUSTOM_KEY


@pytest.mark.parametrize("mode", ["strict", "legacy"])
@pytest.mark.parametrize("base", ["http://router.huggingface.co/v1", "https://router.huggingface.co:8443/v1",
                                   "https://user@router.huggingface.co/v1", "https://gpu.example/v1?token=not-real",
                                   "https://gpu.example:bad/v1"])
def test_invalid_origin_refuses_before_dispatch(configured, mode, base):
    configured.setattr(engine, "_MODEL_BASE_URL", base)
    seen = install_transport(configured, mode)
    result = call(mode)
    assert result["ok"] is False
    assert result["attempts"] == 0
    assert seen == []
    assert HF_KEY not in json.dumps(result)


@pytest.mark.parametrize("mode", ["strict", "legacy"])
@pytest.mark.parametrize("key", ["", " ", "contains space", "header\r\ninjection", "quoted'key", "unicode-é", "x" * 4097])
def test_blank_or_malformed_custom_key_is_not_anonymous(configured, mode, key):
    configured.setenv("A11OY_MODEL_API_KEY", key)
    seen = install_transport(configured, mode)
    result = call(mode)
    assert result["ok"] is False
    assert result["attempts"] == 0
    assert seen == []
    assert CUSTOM_KEY not in json.dumps(result)


@pytest.mark.parametrize("mode", ["strict", "legacy"])
def test_official_endpoint_never_falls_back_to_custom_key(configured, mode):
    configured.setattr(engine, "_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    configured.setattr(engine, "_HF_TOKEN", "")
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    seen = install_transport(configured, mode)
    assert call(mode)["attempts"] == 0
    assert seen == []


def test_anonymous_legacy_http_remains_available_but_cannot_carry_a_key(configured):
    configured.setattr(engine, "_MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
    seen = install_transport(configured, "legacy")
    assert call("legacy")["ok"] is True
    assert authorization(seen[0]) is None
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    assert call("legacy")["attempts"] == 0
    assert len(seen) == 1


@pytest.mark.parametrize("mode", ["strict", "legacy"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_is_terminal_and_never_forwards_any_credential(configured, mode, status):
    configured.setattr(engine, "_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    seen = install_transport(configured, mode, status=status)
    result = call(mode)
    assert result["ok"] is False
    assert result["attempts"] == 1
    assert len(seen) == 1
    assert HF_KEY not in json.dumps(result)


@pytest.mark.parametrize("mode", ["strict", "legacy"])
def test_transport_error_text_cannot_echo_credentials(configured, mode):
    configured.setattr(engine, "_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    seen = install_transport(configured, mode, exception=RuntimeError(HF_KEY))
    result = call(mode)
    assert result["ok"] is False
    assert seen
    assert HF_KEY not in json.dumps(result)


@pytest.mark.parametrize("key", ["", "bad key"])
def test_invalid_custom_credentials_cannot_report_configured_hf_router(configured, key):
    configured.setenv("A11OY_MODEL_API_KEY", key)
    label = engine._backend_label()
    assert label["configured"] is False
    assert label["backend"] == "local-deterministic"
    assert "No admitted model endpoint" in label["honest"]


@pytest.mark.parametrize("key,auth_label", [(None, "no Authorization header"),
                                           (CUSTOM_KEY, "A11OY_MODEL_API_KEY")])
def test_custom_label_describes_only_its_selected_authentication(configured, key, auth_label):
    if key is not None:
        configured.setenv("A11OY_MODEL_API_KEY", key)
    configured.setattr(engine, "_GPU_LABEL", "declared-fixture-GPU")
    label = engine._backend_label()
    assert label["configured"] is True
    assert auth_label in label["honest"]
    assert "HF_TOKEN" not in label["honest"] and "HF token" not in label["honest"]
    assert "does not establish runtime availability" in label["honest"]
    assert label["offline"] is False
    assert label.get("sovereign") is not True
    assert CUSTOM_KEY not in json.dumps(label) and HF_KEY not in json.dumps(label)


def test_official_label_describes_hf_authentication(configured):
    configured.setattr(engine, "_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    label = engine._backend_label()
    assert label["configured"] is True
    assert "HF token" in label["honest"]
    assert "A11OY_MODEL_API_KEY" not in label["honest"]


BONSAI = "prism-ml/Ternary-Bonsai-2-27B-PQ2_0"


def test_bonsai_catalog_identifies_quantized_external_artifact_without_equivalence_claim():
    entry, = [item for item in engine._FALLBACK_ROSTER if item["id"] == BONSAI]
    assert engine._is_open_weight(entry)
    assert entry["provider"] == "Prism ML"
    assert entry["license"] == "Apache-2.0"
    assert entry["transport"] == "custom-https-only"
    assert entry["evaluation"] == entry["artifact_equivalence"] == "UNKNOWN"
    artifact = entry["upstream_artifact"]
    assert artifact["repo_id"] == "prism-ml/Ternary-Bonsai-2-27B-gguf"
    assert artifact["revision"] == "b072e1d3b35a0a630cece372c2127528e0994386"
    assert artifact["filename"] == "Ternary-Bonsai-2-27B-PQ2_0.gguf"
    assert artifact["size_bytes"] == 7206168928
    assert artifact["sha256"] == "3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1"
    assert artifact["base_model"] != BONSAI
    assert "SZLHOLDINGS" not in artifact["repo_id"]


@pytest.mark.skipif(ExecutionBudget is None, reason="Strict companion is absent in this repository")
def test_bonsai_strict_identity_requires_registered_alias_not_base_or_local_path():
    from szl_router_client import ExecutionBudgetError, strict_model_slug
    assert strict_model_slug(BONSAI) == BONSAI
    for model in ("./models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf",
                  "Ternary-Bonsai-2-27B-PQ2_0.gguf", "Qwen/Qwen3.8-27B",
                  "prism-ml/Ternary-Bonsai-2-27B-gguf"):
        with pytest.raises(ExecutionBudgetError):
            strict_model_slug(model)


@pytest.mark.skipif(ExecutionBudget is None, reason="Strict companion is absent in this repository")
@pytest.mark.parametrize("returned_model", [BONSAI,
    "./models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf", "Qwen/Qwen3.8-27B"])
def test_bonsai_strict_response_identity_is_not_repaired_by_provider_provenance(configured, returned_model):
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    seen = []

    def provider(request):
        seen.append(request)
        body = completion()
        body["model"] = returned_model
        # An asserted artifact digest never overrides the response identity check.
        body["provenance"] = {"sha256": "3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1"}
        return httpx.Response(200, json=body)

    configured.setattr(httpx, "Client", lambda **kw: CLIENT(**kw, transport=httpx.MockTransport(provider)))
    result = engine._hf_chat([{"role": "user", "content": "2 + 2"}], max_tokens=4,
        want_model=BONSAI, execution_budget=ExecutionBudget({"max_model_requests": 1,
            "max_output_tokens": 4, "max_elapsed_seconds": 10}))
    assert len(seen) == 1
    assert json.loads(seen[0].content)["model"] == BONSAI
    assert authorization(seen[0]) == "Bearer " + CUSTOM_KEY
    assert result["ok"] is (returned_model == BONSAI)
    if returned_model != BONSAI:
        assert result["error"] == "STRICT_MODEL_IDENTITY_MISMATCH"
    assert HF_KEY not in json.dumps(result)


@pytest.mark.parametrize("mode", ["strict", "legacy"])
@pytest.mark.parametrize("base", ["https://router.huggingface.co/v1",
    "https://ROUTER.HUGGINGFACE.CO:443/v1", "http://127.0.0.1:18080/v1"])
def test_bonsai_alias_requires_custom_https_before_any_dispatch(configured, mode, base):
    configured.setattr(engine, "_MODEL_BASE_URL", base)
    configured.setattr(__import__(__name__, fromlist=["MODEL"]), "MODEL", BONSAI)
    seen = install_transport(configured, mode)
    result = call(mode)
    assert result["ok"] is False
    assert result["attempts"] == 0
    assert seen == []


@pytest.mark.parametrize("mode", ["strict", "legacy"])
def test_bonsai_alias_dispatches_to_explicit_custom_https_only(configured, mode):
    configured.setattr(__import__(__name__, fromlist=["MODEL"]), "MODEL", BONSAI)
    configured.setenv("A11OY_MODEL_API_KEY", CUSTOM_KEY)
    seen = install_transport(configured, mode)
    result = call(mode)
    assert result["ok"] is True
    assert len(seen) == 1
    assert authorization(seen[0]) == "Bearer " + CUSTOM_KEY
