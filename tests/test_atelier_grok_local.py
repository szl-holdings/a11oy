"""Offline contract evidence for Atelier's explicit no-provider-key local lane.

The fake Ollama transport verifies the governed route and signed receipt chain;
these tests do not establish that a model is installed or reachable on a host.
"""

import base64
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from routers import atelier_grok as atelier


TOKEN = "local-atelier-operator-token"
PROMPT = "Write a short description of a blue ceramic cup."
ANSWER = "A blue ceramic cup with a comfortable handle."
MODEL = "qwen3:4b-instruct"
DIGEST = "a" * 64
URL = "http://127.0.0.1:11434/api/chat"
THINKING = "private-local-reasoning-must-disappear"


def ollama_document(**changes):
    document = {"model": MODEL, "message": {"role": "assistant", "content": ANSWER,
                                             "thinking": THINKING},
                "done": True, "done_reason": "stop", "prompt_eval_count": 12,
                "eval_count": 10}
    document.update(changes)
    return document


def tags_document(digest=DIGEST):
    return {"models": [{"name": MODEL, "digest": digest}]}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    for name in ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM",
                 "A11OY_RECEIPT_KEY_PEM", "A11OY_RECEIPT_KEY_PATH", "A11OY_RECEIPT_KEY_DIR",
                 "A11OY_ATELIER_CREDENTIALS_JSON", "A11OY_ATELIER_NAMESPACE",
                 "A11OY_ATELIER_XAI_API_KEY", "XAI_API_KEY", "A11OY_ATELIER_LEDGER_PATH",
                 "A11OY_ATELIER_REQUIRED_MOUNT", "A11OY_ATELIER_LOCAL_URL",
                 "A11OY_ATELIER_LOCAL_MODEL", "A11OY_ATELIER_LOCAL_MODEL_DIGEST",
                 "SZL_GROK_MODEL", "A11OY_ATELIER_MODEL",
                 "SZL_GIT_SHA"):
        monkeypatch.delenv(name, raising=False)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", pem)
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_SIGNING", "1")
    monkeypatch.setenv("A11OY_ATELIER_CREDENTIALS_JSON", json.dumps({
        "version": 1, "credentials": [{
            "owner_id": "owner:local", "namespace": "a11oy", "key_id": "local-key-1",
            "token": TOKEN, "scopes": ["atelier:write"], "revoked": False,
        }],
    }))
    monkeypatch.setenv("A11OY_ATELIER_LOCAL_URL", URL)
    monkeypatch.setenv("A11OY_ATELIER_LOCAL_MODEL", MODEL)
    monkeypatch.setenv("A11OY_ATELIER_LOCAL_MODEL_DIGEST", DIGEST)
    ledger = tmp_path / "retained" / "atelier.jsonl"
    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SZL_GIT_SHA", "599d3a4783fe2816a7c5cf15a819453d5cb6c264")
    calls = []
    probes = []

    def fake_transport(url, **kwargs):
        if kwargs["method"] == "GET":
            probes.append((url, kwargs))
            return tags_document(), None
        calls.append((url, kwargs, json.loads(kwargs["body"])))
        return ollama_document(), None

    monkeypatch.setattr(atelier.szl_provider_http, "http_json", fake_transport)
    app = FastAPI()

    @app.get("/{path:path}")
    async def catchall(path):
        return {"caught": path}

    atelier.register(app)
    with TestClient(app) as client:
        yield {"client": client, "app": app, "calls": calls, "probes": probes,
               "ledger": ledger,
               "monkeypatch": monkeypatch}


def post(env, **body):
    return env["client"].post(f"{atelier.PREFIX}/local/turn",
                              json={"prompt": PROMPT, **body},
                              headers={"Authorization": f"Bearer {TOKEN}"})


def records(env):
    return [json.loads(line) for line in env["ledger"].read_text().splitlines()]


def assert_signed(response, env, count=2):
    response_body = response.json()
    receipt, envelope = response_body["receipt"], response_body["dsse"]
    saved = records(env)
    assert len(saved) == count
    assert receipt["persisted"] is True and receipt["signature_verified"] is True
    assert saved[-1]["digest"] == receipt["digest"]
    assert envelope["signed"] is True
    assert atelier.szl_dsse.verify_envelope(envelope)["verified"] is True
    assert json.loads(base64.b64decode(envelope["payload"])) == receipt["payload"]
    assert all(atelier.szl_dsse.verify_envelope(row["dsse"])["verified"] for row in saved)
    return saved


def test_local_turn_is_single_bounded_no_key_call_with_signed_metadata(configured):
    response = post(configured, max_output_tokens=512)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "COMPLETED" and body["answer"] == ANSWER
    assert body["provider"] == "local_ollama" and body["mode"] == "NO_KEY_LOCAL"
    assert body["model"] == MODEL and body["retry_safe"] is False
    assert body["energy"] == {"label": "UNAVAILABLE", "joules": None}
    assert response.headers["cache-control"] == "no-store"
    saved = assert_signed(response, configured)
    decision, outcome = [row["payload"] for row in saved]
    assert decision["phase"] == "DECISION" and decision["decision"] == "ALLOW"
    assert outcome["phase"] == "OUTCOME" and outcome["state"] == "COMPLETED"
    assert outcome["prior_hash"] == outcome["decision_receipt_hash"] == saved[0]["digest"]
    assert [decision["sequence"], outcome["sequence"]] == [1, 2]
    assert decision["prompt_sha256"] == hashlib.sha256(PROMPT.encode()).hexdigest()
    assert outcome["answer_sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
    assert outcome["usage"] == {"prompt_eval_count": 12, "eval_count": 10}
    assert decision["provider"] == outcome["provider"] == "local_ollama"
    assert decision["mode"] == outcome["mode"] == "NO_KEY_LOCAL"
    assert decision["model_digest_expected"] == outcome["model_digest_expected"] == DIGEST
    assert "model_digest_observed_before_call" not in decision
    assert outcome["model_digest_observed_before_call"] == DIGEST
    assert "reasoning_effort" not in decision
    assert len(configured["probes"]) == 1
    tags_url, tags_options = configured["probes"][0]
    assert tags_url == "http://127.0.0.1:11434/api/tags"
    assert tags_options["method"] == "GET" and tags_options["timeout"] == 10.0
    assert tags_options["allow_private"] is True and tags_options["max_redirects"] == 0
    assert len(configured["calls"]) == 1
    url, options, sent = configured["calls"][0]
    assert url == URL
    assert options["method"] == "POST" and options["timeout"] == 120.0
    assert options["max_response_bytes"] == 1_048_576
    assert options["allow_private"] is True and options["max_redirects"] == 0
    assert "Authorization" not in options["headers"]
    assert sent == {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
                    "stream": False, "truncate": False,
                    "options": {"num_predict": 512}}
    retained = configured["ledger"].read_text()
    for secret in (PROMPT, ANSWER, TOKEN, URL, THINKING):
        assert secret not in retained
    for secret in (PROMPT, TOKEN, URL, THINKING):
        assert secret not in response.text


@pytest.mark.parametrize("header", [None, "Bearer incorrect", "Basic local", "Bearer"])
def test_authentication_precedes_local_body_ledger_and_transport(configured, header):
    headers = {} if header is None else {"Authorization": header}
    response = configured["client"].post(f"{atelier.PREFIX}/local/turn",
                                         json={"prompt": PROMPT}, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    assert not configured["ledger"].exists() and not configured["calls"]
    assert not configured["probes"]


@pytest.mark.parametrize("declared", ["RESTRICTED", "SECRET"])
def test_sensitive_prompt_is_signed_deny_without_local_egress(configured, declared):
    response = post(configured, declared=declared)
    assert response.status_code == 403 and response.json()["code"] == "POLICY_DENIED"
    saved = assert_signed(response, configured, count=1)
    assert saved[0]["payload"]["decision"] == "DENY"
    assert not configured["calls"]


def test_deterministic_policy_denial_before_local_egress(configured):
    response = post(configured, prompt="An SSN is 123-45-6789.")
    assert response.status_code == 403 and response.json()["code"] == "POLICY_DENIED"
    assert len(records(configured)) == 1 and not configured["calls"]


def test_only_exact_policy_allow_permits_local_egress(configured):
    configured["monkeypatch"].setattr(
        atelier.a11oy_vertical_feeds, "governed_turn",
        lambda *args, **kwargs: {"decision": "allow_with_warning"})
    response = post(configured)
    assert response.status_code == 403 and response.json()["code"] == "POLICY_DENIED"
    assert len(records(configured)) == 1 and not configured["calls"]


@pytest.mark.parametrize("missing,code", [
    ("A11OY_ATELIER_CREDENTIALS_JSON", "CREDENTIALS_UNAVAILABLE"),
    ("A11OY_ATELIER_LOCAL_URL", "LOCAL_ENDPOINT_UNAVAILABLE"),
    ("A11OY_ATELIER_LOCAL_MODEL", "LOCAL_MODEL_UNAVAILABLE"),
    ("A11OY_ATELIER_LOCAL_MODEL_DIGEST", "LOCAL_MODEL_DIGEST_UNAVAILABLE"),
    ("A11OY_ATELIER_LEDGER_PATH", "LEDGER_UNAVAILABLE"),
])
def test_required_configuration_fails_before_transport(configured, missing, code):
    configured["monkeypatch"].delenv(missing)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == code
    assert not configured["calls"]


def test_signer_unavailable_prevents_local_call(configured):
    configured["monkeypatch"].setattr(atelier.szl_dsse, "signing_available", lambda: False)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "SIGNER_UNAVAILABLE"
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("url", [
    "http://localhost:11434/api/chat", "http://0.0.0.0:11434/api/chat",
    "http://169.254.169.254:11434/api/chat", "http://100.64.0.1:11434/api/chat",
    "https://127.0.0.1:11434/api/chat", "http://127.0.0.1/api/chat",
    "http://127.0.0.1:11434/api/generate", "http://127.0.0.1:11434/api/chat?x=1",
    "http://127.0.0.1:11434/api/chat#fragment", "http://user@127.0.0.1:11434/api/chat",
])
def test_local_endpoint_requires_literal_loopback_chat_url(configured, url):
    configured["monkeypatch"].setenv("A11OY_ATELIER_LOCAL_URL", url)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LOCAL_ENDPOINT_UNAVAILABLE"
    assert not configured["calls"]


@pytest.mark.parametrize("model", ["", "grok-4.7", "custom-grok:latest", "bad model", "bad?model"])
def test_local_model_must_be_exact_configured_non_grok_tag(configured, model):
    configured["monkeypatch"].setenv("A11OY_ATELIER_LOCAL_MODEL", model)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LOCAL_MODEL_UNAVAILABLE"
    assert not configured["calls"]


@pytest.mark.parametrize("digest", ["", "A" * 64, "a" * 63, "sha256:" + "a" * 64, "z" * 64])
def test_local_model_digest_requires_exact_lowercase_sha256(configured, digest):
    configured["monkeypatch"].setenv("A11OY_ATELIER_LOCAL_MODEL_DIGEST", digest)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_MODEL_DIGEST_UNAVAILABLE"
    assert not configured["calls"] and not configured["probes"]


@pytest.mark.parametrize("extra", [
    {"model": MODEL}, {"url": URL}, {"reasoning_effort": "high"},
    {"tools": []}, {"max_output_tokens": True}, {"history": [PROMPT]},
])
def test_request_rejects_client_backend_selection_and_extra_fields(configured, extra):
    response = post(configured, **extra)
    assert response.status_code == 422 and response.json()["code"] == "INVALID_REQUEST"
    assert not configured["ledger"].exists() and not configured["calls"]


def test_duplicate_json_keys_and_oversized_body_are_rejected(configured):
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    duplicate = configured["client"].post(f"{atelier.PREFIX}/local/turn",
                                          content=b'{"prompt":"one","prompt":"two"}',
                                          headers=headers)
    assert duplicate.status_code == 422
    huge = configured["client"].post(f"{atelier.PREFIX}/local/turn",
                                     content=b" " * (atelier.MAX_BODY_BYTES + 1),
                                     headers=headers)
    assert huge.status_code == 413
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("document", [
    ollama_document(model="other:tag"), ollama_document(done=False),
    ollama_document(done_reason="length"),
    ollama_document(message={"role": "assistant", "content": ""}),
    ollama_document(message={"role": "assistant", "content": ANSWER,
                             "tool_calls": [{"function": {"name": "shell"}}]}),
    ollama_document(message={"role": "user", "content": ANSWER}),
])
def test_invalid_or_nonfinal_local_response_withholds_answer(configured, document):
    calls = configured["calls"]

    def fake(url, **kwargs):
        if kwargs["method"] == "GET":
            return tags_document(), None
        calls.append((url, kwargs))
        return document, None

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", fake)
    response = post(configured)
    assert response.status_code == 502 and response.json()["code"] == "LOCAL_INVALID_RESPONSE"
    assert "answer" not in response.json() and THINKING not in response.text
    assert len(calls) == 1
    saved = assert_signed(response, configured)
    assert saved[1]["payload"]["state"] == "UNAVAILABLE"


def test_timeout_is_one_uncertain_call_with_signed_outcome(configured):
    calls = configured["calls"]

    def timeout(url, **kwargs):
        if kwargs["method"] == "GET":
            return tags_document(), None
        calls.append((url, kwargs))
        return None, "TIMEOUT"

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", timeout)
    response = post(configured)
    assert response.status_code == 504 and response.json()["code"] == "LOCAL_TIMEOUT"
    assert response.json()["retry_safe"] is False and "answer" not in response.json()
    assert len(calls) == 1
    saved = assert_signed(response, configured)
    assert saved[1]["payload"]["provider_outcome_uncertain"] is True


def test_over_context_error_withholds_answer_without_silent_prompt_truncation(configured):
    long_prompt = "Describe the blue cup. " * 1_300
    assert len(long_prompt) < 32_768
    configured["monkeypatch"].setattr(
        atelier.szl_governance_gateway, "classify",
        lambda *args, **kwargs: {"class": "PUBLIC"})
    configured["monkeypatch"].setattr(
        atelier.a11oy_vertical_feeds, "governed_turn",
        lambda *args, **kwargs: {"decision": "allow"})
    calls = configured["calls"]

    def context_exceeded(url, **kwargs):
        if kwargs["method"] == "GET":
            return tags_document(), None
        calls.append((url, kwargs))
        sent = json.loads(kwargs["body"])
        assert sent["messages"] == [{"role": "user", "content": long_prompt}]
        assert sent["truncate"] is False
        return None, "HTTP_STATUS:400"

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", context_exceeded)
    response = post(configured, prompt=long_prompt, max_output_tokens=1)
    assert response.status_code == 502 and response.json()["code"] == "LOCAL_UNAVAILABLE"
    assert "answer" not in response.json() and len(calls) == 1
    decision, outcome = [row["payload"] for row in assert_signed(response, configured)]
    assert decision["prompt_sha256"] == hashlib.sha256(long_prompt.encode()).hexdigest()
    assert outcome["state"] == "UNAVAILABLE" and outcome["provider_outcome_uncertain"] is True


def test_outcome_write_failure_withholds_local_answer(configured):
    original = atelier._append

    def fail_outcome(store, principal, metadata):
        if metadata["phase"] == "OUTCOME":
            raise atelier.AtelierFailure("LEDGER_WRITE_FAILED")
        return original(store, principal, metadata)

    configured["monkeypatch"].setattr(atelier, "_append", fail_outcome)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_WRITE_FAILED"
    assert "answer" not in response.json()
    assert len(configured["calls"]) == 1 and len(records(configured)) == 1


def test_digest_mismatch_is_signed_and_blocks_inference(configured):
    probes = configured["probes"]

    def changed_tag(url, **kwargs):
        probes.append((url, kwargs))
        assert kwargs["method"] == "GET"
        return tags_document("b" * 64), None

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", changed_tag)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_MODEL_DIGEST_MISMATCH"
    assert len(probes) == 1 and not configured["calls"]
    decision, outcome = [row["payload"] for row in assert_signed(response, configured)]
    assert decision["model_digest_expected"] == DIGEST
    assert outcome["model_digest_expected"] == DIGEST
    assert outcome["model_digest_observed_before_call"] == "b" * 64
    assert outcome["state"] == "UNAVAILABLE"
    assert outcome["provider_outcome_uncertain"] is False


@pytest.mark.parametrize("result", [(None, "TIMEOUT"), ({"models": []}, None),
                                      ({"models": [
                                          {"name": MODEL, "digest": DIGEST},
                                          {"name": MODEL, "digest": DIGEST}]}, None)])
def test_digest_probe_failure_is_signed_and_blocks_inference(configured, result):
    probes = configured["probes"]

    def unavailable(url, **kwargs):
        probes.append((url, kwargs))
        assert kwargs["method"] == "GET"
        return result

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", unavailable)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_MODEL_DIGEST_UNAVAILABLE"
    assert len(probes) == 1 and not configured["calls"]
    assert probes[0][1]["timeout"] == 10.0
    decision, outcome = [row["payload"] for row in assert_signed(response, configured)]
    assert decision["model_digest_expected"] == DIGEST
    assert "model_digest_observed_before_call" not in outcome
    assert outcome["provider_outcome_uncertain"] is False


def test_digest_probe_exception_fails_closed_without_inference(configured):
    probes = configured["probes"]

    def timed_out(url, **kwargs):
        probes.append((url, kwargs))
        raise TimeoutError("local tags took too long")

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", timed_out)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_MODEL_DIGEST_UNAVAILABLE"
    assert response.json()["retry_safe"] is False
    assert len(probes) == 1 and probes[0][1]["timeout"] == 10.0
    assert not configured["calls"]
    decision, outcome = [row["payload"] for row in assert_signed(response, configured)]
    assert decision["phase"] == "DECISION"
    assert outcome["state"] == "UNAVAILABLE"
    assert outcome["provider_outcome_uncertain"] is False


def test_model_digest_is_reobserved_before_each_local_turn(configured):
    assert post(configured).status_code == 200
    assert post(configured).status_code == 200
    assert len(configured["probes"]) == len(configured["calls"]) == 2
    saved = records(configured)
    assert [row["payload"]["sequence"] for row in saved] == [1, 2, 3, 4]
    assert all(row["payload"]["model_digest_expected"] == DIGEST for row in saved)


def test_tampered_retained_receipt_blocks_next_local_call(configured):
    assert post(configured).status_code == 200
    saved = records(configured)
    saved[0]["payload"]["model"] = "tampered"
    configured["ledger"].write_text("\n".join(json.dumps(row) for row in saved) + "\n")
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LEDGER_INTEGRITY_UNAVAILABLE"
    assert len(configured["calls"]) == 1


def test_local_health_is_read_only_and_does_not_claim_inference(configured):
    response = configured["client"].get(f"{atelier.PREFIX}/local/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True and body["blockers"] == []
    assert body["model"] == MODEL and body["provider"] == "local_ollama"
    assert body["mode"] == "NO_KEY_LOCAL" and body["inference_verified"] is False
    assert body["configured"] == {"credentials": True, "endpoint": True,
                                  "model": True, "model_digest": True,
                                  "signer": True, "ledger": True}
    assert URL not in response.text and TOKEN not in response.text
    assert not configured["calls"] and not configured["ledger"].exists()
    head = configured["client"].head(f"{atelier.PREFIX}/local/health")
    assert head.status_code == 200 and head.content == b""


def test_local_routes_precede_catchall_and_register_once(configured):
    paths = [getattr(route, "path", None) for route in configured["app"].router.routes]
    assert paths.index(f"{atelier.PREFIX}/local/health") < paths.index("/{path:path}")
    assert paths.index(f"{atelier.PREFIX}/local/turn") < paths.index("/{path:path}")
    assert atelier.register(configured["app"])["state"] == "ALREADY_REGISTERED"
    assert len(configured["app"].router.routes) == len(paths)
