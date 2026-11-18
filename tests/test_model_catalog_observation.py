# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic catalog regressions: no credentials, provider requests, or inference."""

import json
from types import SimpleNamespace

import pytest

import a11oy_code_orchestrator as orchestrator
import szl_provider_http as provider_http
from ayllu.model_binding import second_brain_binding


BASE = "https://provider.invalid/v1"
REAL_HTTP_JSON = provider_http.http_json


@pytest.fixture
def provider(monkeypatch):
    state = {
        "base": BASE,
        "authorization": "Bearer synthetic-catalog-header",
        "payload": {"data": [{"id": "khipu:latest"}]},
        "error": None,
        "calls": [],
        "header_calls": [],
    }
    monkeypatch.setattr(orchestrator, "_sovereign_base_url", lambda: state["base"])
    monkeypatch.setattr(
        orchestrator, "forge_profile_model_map",
        lambda: dict(orchestrator._FORGE_PROFILE_DEFAULTS))

    def headers(*, is_local=False):
        state["header_calls"].append(is_local)
        assert is_local is True
        return {
            "Authorization": state["authorization"],
            "Content-Type": "application/json",
        }

    def forbidden_hf_token():
        raise AssertionError("local metadata must not resolve HF credentials")

    def http_json(url, **kwargs):
        state["calls"].append((url, kwargs))
        if url.endswith("/models"):
            return state["payload"], state["error"]
        if url.endswith("/api/show"):
            return {"details": {"format": "gguf"}, "template": "synthetic"}, None
        if url.endswith("/api/tags"):
            return {"models": [{"name": "khipu:latest", "digest": "a" * 64}]}, None
        raise AssertionError("unexpected synthetic metadata target")

    monkeypatch.setattr(orchestrator, "_inference_headers", headers)
    monkeypatch.setattr(orchestrator, "_resolve_hf_token", forbidden_hf_token)
    monkeypatch.setattr(provider_http, "http_json", http_json)
    return state


def test_authorized_catalog_uses_completion_headers_and_preserves_unbound(provider):
    assert orchestrator._serving_base() == (BASE, True)
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    status = orchestrator.forge_profile_runtime_status()
    assert attestation["available"] is True
    assert attestation["state"] == "TAG_ATTESTED_ARTIFACT_UNBOUND"
    assert attestation["artifact_binding"] == "UNBOUND"
    assert attestation["served_model"] == "khipu:latest"
    assert attestation["model_details"] == {
        "format": "gguf", "family": None, "parameter_size": None,
        "quantization_level": None,
    }
    assert status["profiles"]["BrainNavigator-v1"]["available"] is True
    assert status["catalog_scope"] == "CONFIGURED_LOCAL_PROVIDER"
    assert status["base_url"] == BASE
    for _url, request in provider["calls"]:
        assert request["headers"] == {
            "Authorization": provider["authorization"],
            "Content-Type": "application/json",
        }
        assert request["max_redirects"] == 0
        assert request["allow_private"] is True
        assert request["max_response_bytes"] == 4 * 1024 * 1024
    assert all(provider["header_calls"])
    assert provider["authorization"] not in json.dumps([attestation, status])


@pytest.mark.parametrize("error,expected", [
    ("HTTP_STATUS:401", "MODEL_CATALOG_UNAUTHORIZED"),
    ("HTTP_STATUS:403", "MODEL_CATALOG_UNAUTHORIZED"),
    ("INVALID_JSON", "MODEL_CATALOG_MALFORMED"),
    ("TIMEOUT", "MODEL_CATALOG_UNAVAILABLE"),
    ("NETWORK_FAILURE", "MODEL_CATALOG_UNAVAILABLE"),
    ("HTTP_STATUS:503", "MODEL_CATALOG_UNAVAILABLE"),
    ("unknown raw diagnostic content", "MODEL_CATALOG_UNAVAILABLE"),
])
def test_catalog_failure_is_unknown_inventory_and_keeps_remote_authority(
    provider, error, expected,
):
    provider["payload"] = None
    provider["error"] = error
    assert orchestrator._serving_base() == (orchestrator.HF_ROUTER_BASE, False)
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    status = orchestrator.forge_profile_runtime_status()
    for observation in (attestation, status):
        assert observation["catalog_state"] == expected
        assert observation["catalog_scope"] == "CONFIGURED_LOCAL_PROVIDER"
        assert observation["local_endpoint"] is False
        assert observation["base_url"] == orchestrator.HF_ROUTER_BASE
        assert observation["served_model_count"] is None
        assert "served_models_sha256" not in observation
        assert error not in json.dumps(observation)
        assert provider["authorization"] not in json.dumps(observation)
    assert attestation["state"] == expected
    assert attestation["available"] is False
    assert status["profiles"]["BrainNavigator-v1"]["state"] == expected
    assert status["profiles"]["BrainNavigator-v1"]["served_model"] is None
    assert all(url.endswith("/models") for url, _request in provider["calls"])


@pytest.mark.parametrize("payload", [
    None, [], {}, {"data": None}, {"data": {}}, {"data": "provider text"},
    {"data": [{"id": 3}]}, {"data": [{}]}, {"data": [""]},
    {"data": [{"id": "khipu:latest"}, None]},
    {"data": None, "models": ["khipu:latest"]},
])
def test_malformed_catalog_never_becomes_a_valid_partial_inventory(provider, payload):
    provider["payload"] = payload
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    assert attestation["state"] == "MODEL_CATALOG_MALFORMED"
    assert attestation["served_model_count"] is None
    assert attestation["available"] is False
    assert "served_models_sha256" not in attestation


@pytest.mark.parametrize("payload", [
    {"data": []}, {"models": []},
    {"data": [], "models": ["khipu:latest"]},
    {"data": [{"id": "Khipu:latest"}]},
    {"data": [{"id": " khipu:latest"}]},
    {"models": ["khipu:latest "]},
])
def test_valid_catalog_requires_the_exact_tag_including_case_and_whitespace(provider, payload):
    provider["payload"] = payload
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    assert attestation["catalog_state"] == "MODEL_CATALOG_OBSERVED"
    assert attestation["state"] == "MODEL_TAG_MISSING"
    assert attestation["available"] is False
    assert isinstance(attestation["served_model_count"], int)
    assert len(attestation["served_models_sha256"]) == 64


def test_unexpected_provider_exception_does_not_escape_public_diagnostics(provider, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("synthetic private exception https://private.invalid Authorization")

    monkeypatch.setattr(provider_http, "http_json", unavailable)
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    assert attestation["state"] == "MODEL_CATALOG_UNAVAILABLE"
    serialized = json.dumps(attestation)
    assert "synthetic private exception" not in serialized
    assert "private.invalid" not in serialized
    assert "Authorization" not in serialized


def test_catalog_auth_is_resolved_per_observation_without_stale_failure(provider):
    provider["error"] = "HTTP_STATUS:401"
    assert orchestrator._local_endpoint_reachable(BASE) is False
    provider["authorization"] = "Bearer synthetic-rotated-header"
    provider["error"] = None
    assert orchestrator._local_endpoint_reachable(BASE) is True
    assert [request["headers"]["Authorization"] for _url, request in provider["calls"]] == [
        "Bearer synthetic-catalog-header", "Bearer synthetic-rotated-header",
    ]


@pytest.mark.parametrize("configured", [
    "", "https://router.huggingface.co/v1",
    "https://ROUTER.HUGGINGFACE.CO/v1",
    "https://ROUTER.HUGGINGFACE.CO./v1",
    "https://provider.invalid/router.huggingface.co/v1",
])
def test_excluded_configured_base_never_receives_local_or_hf_credentials(provider, configured):
    provider["base"] = configured
    status = orchestrator.forge_profile_runtime_status()
    assert orchestrator._serving_base() == (orchestrator.HF_ROUTER_BASE, False)
    assert status["local_endpoint"] is False
    assert status["catalog_state"] == "LOCAL_ENDPOINT_UNAVAILABLE"
    assert status["base_url"] == orchestrator.HF_ROUTER_BASE
    assert provider["calls"] == []
    assert provider["header_calls"] == []


def test_metadata_credentials_are_never_resolved_for_a_different_base(provider):
    state, models = orchestrator._local_model_catalog_observation(
        "https://other-provider.invalid/v1")
    assert (state, models) == ("LOCAL_ENDPOINT_UNAVAILABLE", None)
    assert provider["calls"] == []
    assert provider["header_calls"] == []


@pytest.mark.parametrize("base", [
    "https://provider.invalid/proxy/v1",
    "https://provider.invalid/v1?tenant=synthetic",
])
def test_scoped_provider_catalog_does_not_authorize_origin_root_metadata(provider, base):
    provider["base"] = base
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    assert attestation["available"] is True
    assert attestation["artifact_binding"] == "UNBOUND"
    assert attestation["show_state"] == "UNAVAILABLE"
    assert [url for url, _request in provider["calls"]] == [base + "/models"]


def test_authenticated_catalog_refuses_redirect_without_contacting_destination(provider, monkeypatch):
    validated = []
    requested = []
    closed = []

    def validate(url, **_kwargs):
        validated.append(url)
        assert url == BASE + "/models"
        return SimpleNamespace(origin=("https", "provider.invalid", 443)), None

    def request_once(_target, **kwargs):
        requested.append(kwargs)
        response = SimpleNamespace(
            status=302, getheader=lambda _name: "https://other-provider.invalid/models",
            close=lambda: None)
        connection = SimpleNamespace(close=lambda: closed.append(True))
        # The real _request_once hands over every connection with its deadline
        # guard attached; without one, http_json never reaches the redirect check.
        connection._szl_deadline_guard = provider_http._SocketDeadline(
            None, kwargs["deadline"])
        return response, connection, None

    reasons = []

    def observed_http_json(*args, **kwargs):
        result = REAL_HTTP_JSON(*args, **kwargs)
        reasons.append(result[1])
        return result

    monkeypatch.setattr(provider_http, "http_json", observed_http_json)
    monkeypatch.setattr(provider_http, "_validate_target", validate)
    monkeypatch.setattr(provider_http, "_request_once", request_once)
    attestation = orchestrator.attest_local_model("BrainNavigator-v1")
    assert attestation["state"] == "MODEL_CATALOG_UNAVAILABLE"
    assert reasons == ["REDIRECT_LIMIT_EXCEEDED"]
    assert validated == [BASE + "/models"]
    assert len(requested) == len(closed) == 1
    assert requested[0]["headers"]["Authorization"] == provider["authorization"]


def test_generic_document_call_remains_unauthenticated_with_existing_redirect_default(provider):
    orchestrator._endpoint_json(BASE + "/models", allow_private=True)
    _url, request = provider["calls"][0]
    assert request["headers"] is None
    assert request["max_redirects"] == 2
    assert provider["header_calls"] == []


@pytest.mark.parametrize("profile_state,expected", [
    ("MODEL_TAG_MISSING", "UNAVAILABLE_MODEL_TAG_MISSING"),
    ("MODEL_CATALOG_UNAUTHORIZED", "UNAVAILABLE_MODEL_CATALOG_UNAUTHORIZED"),
    ("MODEL_CATALOG_MALFORMED", "UNAVAILABLE_MODEL_CATALOG_MALFORMED"),
    ("MODEL_CATALOG_UNAVAILABLE", "UNAVAILABLE_MODEL_CATALOG_UNAVAILABLE"),
    ("LOCAL_ENDPOINT_UNAVAILABLE", "UNAVAILABLE_LOCAL_MODEL_ENDPOINT"),
    ("untrusted provider text", "UNAVAILABLE_MODEL_CATALOG_UNAVAILABLE"),
])
@pytest.mark.parametrize("index_ready", [True, False])
def test_second_brain_preserves_catalog_reason_and_independent_index_gate(
    profile_state, expected, index_ready,
):
    result = second_brain_binding(
        backend_status={"forge_profiles": {"profiles": {"BrainNavigator-v1": {
            "available": False, "state": profile_state,
        }}}},
        rag_status={"built": index_ready},
    )
    assert result["state"] == (expected if index_ready else "UNAVAILABLE_MODEL_AND_INDEX")
    assert result["ready_for_grounded_navigation"] is False
    assert result["profile"]["artifact_binding"] == "UNBOUND"
    assert result["promotion_state"] == "BLOCKED_ARTIFACT_AND_EVAL_GATES"
    assert result["memory"]["built"] is index_ready
    assert "untrusted provider text" not in json.dumps(result)


@pytest.mark.parametrize("available", ["false", "true", 1, {}, ["true"]])
def test_second_brain_requires_literal_true_availability(available):
    result = second_brain_binding(
        backend_status={"forge_profiles": {"profiles": {"BrainNavigator-v1": {
            "available": available,
        }}}},
        rag_status={"built": True},
    )
    assert result["profile"]["exact_tag_observed"] is False
    assert result["ready_for_grounded_navigation"] is False
    assert result["state"] == "UNAVAILABLE_MODEL_CATALOG_UNAVAILABLE"
    assert result["promotion_state"] == "BLOCKED_ARTIFACT_AND_EVAL_GATES"
