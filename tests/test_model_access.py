#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Protected model requests use one origin and cannot become another protocol."""

import json
import socket

import httpx
import pytest

import a11oy_code_engine as engine
import szl_boot_preflight as preflight
import szl_llm_registry as registry
import szl_model_access as access
import szl_provider_http as provider_http


MODEL = "prism-ml/Ternary-Bonsai-2-27B-PQ2_0"
ORIGIN = "https://gpu.example"
CLIENT_ID = "fixture-model-client.access"
CLIENT_SECRET = "fixture-model-access-secret"
BEARER = "fixture-model-bearer"
HTTPX_CLIENT = httpx.Client
ACCESS_NAMES = (access.ACCESS_ORIGIN_ENV, access.ACCESS_ID_ENV, access.ACCESS_SECRET_ENV)


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in (*ACCESS_NAMES, "A11OY_MODEL_API_KEY", "A11OY_BRAIN_URL",
                 "A11OY_MODEL_BASE_URL", "A11OY_SOVEREIGN_GATEWAY_URL",
                 "SZL_LOCAL_LLM_URL", "A11OY_MODEL_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(engine, "_MODEL_BASE_URL", ORIGIN + "/v1")
    monkeypatch.setattr(engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.setattr(engine, "_HF_TOKEN", "fixture-hf-credential")
    return monkeypatch


def configure(monkeypatch):
    for name, value in ((access.ACCESS_ORIGIN_ENV, ORIGIN),
                        (access.ACCESS_ID_ENV, CLIENT_ID),
                        (access.ACCESS_SECRET_ENV, CLIENT_SECRET),
                        ("A11OY_MODEL_API_KEY", BEARER),
                        ("A11OY_BRAIN_URL", ORIGIN + "/v1")):
        monkeypatch.setenv(name, value)


def model_transport(monkeypatch, *, status=200, location="https://other.example/v1/chat/completions"):
    requests = []

    def send(request):
        requests.append(request)
        payload = json.loads(request.content)
        body = {"model": payload["model"],
                "choices": [{"message": {"role": "assistant", "content": "4"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}}
        return httpx.Response(status, json=body, headers={"Location": location})

    monkeypatch.setattr(httpx, "Client", lambda **kw: HTTPX_CLIENT(
        **kw, transport=httpx.MockTransport(send)))
    return requests


def complete(model=MODEL):
    return engine._hf_chat([{"role": "user", "content": "2 + 2"}],
                           max_tokens=4, want_model=model)


@pytest.mark.parametrize("secret", [CLIENT_SECRET, "a" * 64, "cfast_" + "A" * 48])
def test_access_pair_and_bearer_share_one_bounded_request(isolated, secret):
    configure(isolated)
    isolated.setenv(access.ACCESS_SECRET_ENV, secret)
    requests = model_transport(isolated)
    result = complete()
    assert result["ok"] is True and result["attempts"] == 1
    assert len(requests) == 1 and str(requests[0].url) == ORIGIN + "/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer " + BEARER
    assert requests[0].headers["CF-Access-Client-Id"] == CLIENT_ID
    assert requests[0].headers["CF-Access-Client-Secret"] == secret
    payload = json.loads(requests[0].content)
    assert payload["model"] == MODEL and payload["stream"] is False
    assert payload["max_tokens"] == 4
    assert result["execution_limits"]["limits"] == {
        "max_model_requests": 1, "max_output_tokens": 4, "max_elapsed_seconds": 30}
    assert secret not in json.dumps(result) and BEARER not in json.dumps(result)


@pytest.mark.parametrize("name", ACCESS_NAMES)
@pytest.mark.parametrize("value", [None, "", " value ", "bad\r\nheader", "é"])
def test_partial_or_malformed_access_configuration_never_dispatches(isolated, name, value):
    configure(isolated)
    if value is None:
        isolated.delenv(name)
    else:
        isolated.setenv(name, value)
    requests = model_transport(isolated)
    result = complete()
    assert result["ok"] is False and result["attempts"] == 0
    assert requests == []
    assert CLIENT_SECRET not in json.dumps(result) and BEARER not in json.dumps(result)


@pytest.mark.parametrize("destination", [
    "https://other.example/v1", "https://gpu.example.evil.test/v1",
    "https://prefix-gpu.example/v1", "http://gpu.example/v1",
    "https://gpu.example:444/v1", "https://gpu.example:0443/v1",
    "https://user:password@gpu.example/v1", "https://gpu.example./v1",
    "https://gpu.example/v1?redirect=1", "https://gpu.example/v1#fragment",
    "https://127.0.0.1/v1", "https://router.huggingface.co/v1",
])
def test_access_configuration_cannot_send_credentials_to_another_destination(isolated, destination):
    configure(isolated)
    isolated.setattr(engine, "_MODEL_BASE_URL", destination)
    requests = model_transport(isolated)
    result = complete()
    assert result["ok"] is False and result["attempts"] == 0
    assert requests == []


@pytest.mark.parametrize("host", ["127.1", "0177.0.0.1", "0x7f.0.0.1", "2130706433"])
def test_numeric_ip_spellings_cannot_be_configured_as_access_origins(isolated, host):
    configure(isolated)
    origin = "https://" + host
    isolated.setenv(access.ACCESS_ORIGIN_ENV, origin)
    isolated.setenv("A11OY_BRAIN_URL", origin + "/v1")
    isolated.setattr(engine, "_MODEL_BASE_URL", origin + "/v1")
    requests = model_transport(isolated)
    catalog = catalog_transport(isolated)
    assert complete()["attempts"] == 0
    assert registry.sovereign_probe()["live"] is False
    assert requests == catalog == []


@pytest.mark.parametrize("origin", [ORIGIN + "/v1", ORIGIN + "?x=1",
                                     ORIGIN + "#x", "https://*.example",
                                     "https://user:password@gpu.example"])
def test_access_origin_is_an_origin_without_credentials_or_a_path(isolated, origin):
    configure(isolated)
    isolated.setenv(access.ACCESS_ORIGIN_ENV, origin)
    requests = model_transport(isolated)
    assert complete()["attempts"] == 0
    assert requests == []


@pytest.mark.parametrize("destination", ["https://GPU.EXAMPLE:443/v1", ORIGIN + "/v1"])
def test_equivalent_https_authorities_are_accepted(isolated, destination):
    configure(isolated)
    isolated.setattr(engine, "_MODEL_BASE_URL", destination)
    requests = model_transport(isolated)
    assert complete()["ok"] is True
    assert len(requests) == 1


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 401, 403, 429, 500])
def test_protected_failure_never_retries_or_forwards_credentials(isolated, status):
    configure(isolated)
    requests = model_transport(isolated, status=status)
    result = complete()
    assert result["ok"] is False and result["attempts"] == 1
    assert len(requests) == 1 and requests[0].url.host == "gpu.example"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_protected_same_origin_redirect_is_also_terminal(isolated, status):
    configure(isolated)
    requests = model_transport(isolated, status=status, location=ORIGIN + "/another-path")
    assert complete()["ok"] is False and len(requests) == 1


def test_official_router_cannot_receive_stale_model_access_credentials(isolated):
    configure(isolated)
    isolated.setattr(engine, "_MODEL_BASE_URL", "https://router.huggingface.co/v1")
    requests = model_transport(isolated)
    result = complete("Qwen/Qwen2.5-Coder-1.5B-Instruct")
    assert result["ok"] is False and result["attempts"] == 0 and requests == []


def test_access_requires_a_selected_model_and_uses_strict_client_for_other_catalog_models(isolated):
    configure(isolated)
    requests = model_transport(isolated)
    assert complete(model=None)["attempts"] == 0
    assert requests == []
    isolated.setenv("A11OY_MODEL_ID", "Qwen/Qwen2.5-Coder-1.5B-Instruct")
    assert complete(model=None)["ok"] is True
    assert len(requests) == 1
    assert json.loads(requests[0].content)["stream"] is False


def test_all_absent_access_ignores_unrelated_meter_credentials(isolated):
    isolated.setenv("A11OY_METER2_CF_ACCESS_CLIENT_ID", "fixture-meter-id")
    isolated.setenv("A11OY_METER2_CF_ACCESS_CLIENT_SECRET", "fixture-meter-secret")
    isolated.setenv("A11OY_MODEL_API_KEY", BEARER)
    assert access.model_access_configured() is False
    assert engine._model_auth_headers() == {"Authorization": "Bearer " + BEARER}


def catalog_transport(monkeypatch, *, status=200):
    requests = []

    class Response:
        def __init__(self):
            self.status = status

        def getheader(self, name):
            return "https://other.example/v1/models" if name == "Location" else None

        def read(self, _limit):
            return json.dumps({"data": [{"id": MODEL}]}).encode()

    class Connection:
        sock = None

        def close(self):
            pass

    def request(target, **kwargs):
        requests.append((target, kwargs))
        return Response(), Connection(), None

    monkeypatch.setattr(provider_http, "_resolve_bounded", lambda *_: (
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))], None))
    monkeypatch.setattr(provider_http, "_request_once", request)
    return requests


def test_catalog_uses_code_bearer_and_access_without_generation_or_receipts(isolated):
    configure(isolated)
    isolated.setenv("A11OY_SOVEREIGN_GATEWAY_KEY", "fixture-other-gateway-secret")
    isolated.setenv("A11OY_GPU_TOKEN", "fixture-energy-secret")
    import szl_dsse

    def no_signature(*_args, **_kwargs):
        raise AssertionError("catalog observation must not sign")

    isolated.setattr(szl_dsse, "sign_payload", no_signature)
    requests = catalog_transport(isolated)
    observed = registry.sovereign_probe()
    assert observed["live"] is True and observed["models"] == [MODEL]
    assert len(requests) == 1
    target, sent = requests[0]
    assert target.url == ORIGIN + "/v1/models"
    assert sent["method"] == "GET" and sent["body"] is None
    assert sent["headers"]["Authorization"] == "Bearer " + BEARER
    assert sent["headers"]["CF-Access-Client-Id"] == CLIENT_ID
    assert sent["headers"]["CF-Access-Client-Secret"] == CLIENT_SECRET
    for credential in (BEARER, CLIENT_ID, CLIENT_SECRET, "fixture-other-gateway-secret",
                       "fixture-energy-secret", "fixture-hf-credential"):
        assert credential not in json.dumps(observed)
    assert registry.sovereign_generate("do not run", model=MODEL)["generated"] is False
    assert len(requests) == 1


def test_public_catalog_health_preserves_unqualified_state_and_withholds_credentials(isolated):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    configure(isolated)
    isolated.setenv("SZL_LOCAL_LLM_MODEL", MODEL)
    isolated.delenv("SZL_SOVEREIGN_NODES", raising=False)
    isolated.setattr(registry, "_inference_receipt_state", lambda _model: {
        "inference_receipted": False, "successful_receipt_count": 0,
        "total_receipt_count": 0, "chain_ok": True, "latest_receipt_hash": None})
    requests = catalog_transport(isolated)
    app = FastAPI()
    registry.register(app)
    response = TestClient(app).get("/api/a11oy/v1/llm/sovereign/health")
    assert response.status_code == 200 and len(requests) == 1
    body = response.json()
    assert body["label"] == "UNKNOWN" and body["operational"] is False
    for value in (CLIENT_SECRET, CLIENT_ID, BEARER, ORIGIN, MODEL):
        assert value not in response.text


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 401, 403, 404, 429, 500])
def test_protected_catalog_refusal_is_terminal(isolated, status):
    configure(isolated)
    requests = catalog_transport(isolated, status=status)
    observed = registry.sovereign_probe()
    assert observed["live"] is False
    assert len(requests) == 1 and requests[0][0].hostname == "gpu.example"
    assert len(observed["probed"]) == 1


@pytest.mark.parametrize("case", ["partial", "different_base", "unselected_code_endpoint"])
def test_protected_catalog_bad_configuration_fails_before_transport(isolated, case):
    configure(isolated)
    if case == "partial":
        isolated.delenv(access.ACCESS_SECRET_ENV)
    if case == "unselected_code_endpoint":
        isolated.delenv("A11OY_BRAIN_URL")
        isolated.setenv("SZL_LOCAL_LLM_URL", ORIGIN + "/v1")
    requests = catalog_transport(isolated)
    kwargs = {"base": "https://other.example/v1"} if case == "different_base" else {}
    observed = registry.sovereign_probe(**kwargs)
    assert observed["live"] is False and requests == []


@pytest.mark.parametrize("base", [
    "https://user:private-url-value@gpu.example/v1",
    ORIGIN + "/v1?token=private-url-value",
    ORIGIN + "/v1#private-url-value",
])
def test_protected_refusals_do_not_echo_an_unvalidated_url(isolated, base):
    configure(isolated)
    isolated.setenv("A11OY_BRAIN_URL", base)
    requests = catalog_transport(isolated)
    observation = registry.sovereign_probe()
    generation = registry.sovereign_generate("do not run", model=MODEL)
    assert requests == []
    assert observation["base_url"] is None and generation["base_url"] is None
    assert "private-url-value" not in json.dumps([observation, generation])


def test_absent_access_keeps_legacy_registry_authentication(isolated):
    isolated.setenv("A11OY_BRAIN_URL", ORIGIN + "/v1")
    isolated.setenv("A11OY_SOVEREIGN_GATEWAY_KEY", "fixture-legacy-gateway-key")
    requests = catalog_transport(isolated)
    observed = registry.sovereign_probe()
    assert observed["live"] is True and len(requests) == 2
    assert all(row[1]["headers"]["Authorization"] == "Bearer fixture-legacy-gateway-key"
               for row in requests)
    assert all(not any(name.lower().startswith("cf-access-") for name in row[1]["headers"])
               for row in requests)


def test_preflight_declares_secrets_without_values_and_refuses_partial_configuration():
    specs = {spec.name: spec for spec in preflight._REGISTRY}
    assert specs[access.ACCESS_ORIGIN_ENV].kind == preflight.VARIABLE
    assert all(specs[name].kind == preflight.SECRET for name in ACCESS_NAMES[1:])
    legacy = {spec.name: "fixture-legacy-provider" for spec in preflight._REGISTRY
              if spec.subsystem == "brain" and spec.kind == preflight.SECRET
              and spec.name not in ACCESS_NAMES}
    assert preflight._subsystem_label(legacy, "brain")["label"] == preflight.LIVE
    partial = {**legacy, access.ACCESS_ID_ENV: CLIENT_ID}
    result = preflight._subsystem_label(partial, "brain")
    assert result["label"] == preflight.DEGRADED
    assert result["configuration_error"] == "MODEL_ACCESS_CONFIGURATION_INCOMPLETE"
    assert CLIENT_ID not in json.dumps(result)
