"""Offline contract tests for Atelier's public, unsigned CPU-lab provider lane.

The fake transport proves route behavior, not live model quality or availability.
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


TOKEN = "cpu-lab-test-operator-token"
PROMPT = "Describe a blue ceramic cup."
ANSWER = "A small blue ceramic cup."


def json_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def identity_document(**changes):
    identity = {
        "status": "READY",
        "space": {"id": atelier.CPU_LAB_SPACE,
                  "release_id": atelier.CPU_LAB_RELEASE_ID,
                  "release_manifest_sha256": atelier.CPU_LAB_RELEASE_MANIFEST_SHA256,
                  "source_integrity": True},
        "model": {"repo": atelier.CPU_LAB_MODEL_REPO,
                  "revision": atelier.CPU_LAB_MODEL_REVISION,
                  "file": atelier.CPU_LAB_MODEL_FILE,
                  "sha256_expected": atelier.CPU_LAB_MODEL_SHA256,
                  "sha256_loaded": atelier.CPU_LAB_MODEL_SHA256},
        "runtime": {"max_input_chars": atelier.CPU_LAB_MAX_INPUT_CHARS,
                    "max_formatted_prompt_tokens": 800,
                    "max_new_tokens": atelier.CPU_LAB_MAX_OUTPUT_TOKENS,
                    "max_request_body_bytes": atelier.CPU_LAB_MAX_BODY_BYTES,
                    "openai_compatible_subset": {
                        "chat_completions": "POST /v1/chat/completions",
                        "model_id": atelier.CPU_LAB_MODEL, "streaming": False}},
    }
    identity.update(changes)
    return identity


@pytest.fixture
def protected_release_identity():
    # Forge 85f1067 release.json matches HF commit 614d904 byte-for-byte.
    identity = identity_document()
    identity["space"]["release_id"] = (
        "brain13-1d3960c-controller-9f227f6-atlas-d7b08cde")
    identity["space"]["release_manifest_sha256"] = (
        "d1170d8265c523352f800d3c68dbb701b8220bca3db5403a8de94258f5a5613c")
    return identity


@pytest.mark.parametrize("changed_field", [
    None, "release_id", "release_manifest_sha256",
])
def test_protected_cpu_release_binding_stays_exact(
        monkeypatch, protected_release_identity, changed_field):
    identity = protected_release_identity
    if changed_field:
        identity["space"][changed_field] = "unapproved-release"
    monkeypatch.setattr(
        atelier.szl_provider_http, "http_json", lambda *args, **kwargs: (identity, None))
    if changed_field:
        with pytest.raises(atelier.AtelierFailure) as failure:
            atelier._cpu_lab_identity()
        assert failure.value.code == "CPU_LAB_IDENTITY_MISMATCH"
    else:
        observed = atelier._cpu_lab_identity()
        assert observed["release_id_observed_before_call"] == identity["space"]["release_id"]
        assert observed["release_manifest_observed_before_call"] == (
            identity["space"]["release_manifest_sha256"])


def completion_document(request_body, answer=ANSWER):
    messages = request_body["messages"]
    max_tokens = request_body["max_completion_tokens"]
    canonical_request = {
        "schema": "szl.openai-chat-request/v1", "model": atelier.CPU_LAB_MODEL,
        "messages": messages, "max_completion_tokens": max_tokens,
        "temperature": 0.0, "top_p": 1.0, "n": 1,
        "stream": False, "tools": None,
    }
    usage = {"prompt_tokens": 18, "completion_tokens": 7, "total_tokens": 25}
    model = {"repo": atelier.CPU_LAB_MODEL_REPO,
             "revision": atelier.CPU_LAB_MODEL_REVISION,
             "file": atelier.CPU_LAB_MODEL_FILE,
             "sha256": atelier.CPU_LAB_MODEL_SHA256}
    record = {
        "schema": "szl.unsigned-execution-record/v1",
        "request_id": "chatcmpl-szl-test1", "created_unix": 1790992800,
        "canonical_request_sha256": json_hash(canonical_request),
        "output_sha256": hashlib.sha256(answer.encode()).hexdigest(),
        "model": {"id": atelier.CPU_LAB_MODEL, **model},
        "source": {"space_id": atelier.CPU_LAB_SPACE,
                   "release_id": atelier.CPU_LAB_RELEASE_ID,
                   "release_manifest_sha256": atelier.CPU_LAB_RELEASE_MANIFEST_SHA256},
        "usage": usage,
        "elapsed_ms": 200,
        "termination": {"reason": "stop", "time_budget_reached": False},
        "signature_status": "UNSIGNED", "signature": None,
        "authenticity_not_established": True,
        "persistence": {"application_record_storage": "NOT_PERSISTED"},
    }
    record["record_sha256"] = json_hash(record)
    return {
        "id": record["request_id"], "object": "chat.completion",
        "created": record["created_unix"], "model": atelier.CPU_LAB_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer,
                                              "private_reasoning": "never forward this"},
                     "finish_reason": "stop"}],
        "usage": usage,
        "szl_provenance": {
            "schema": "szl.openai-compat-provenance/v1", "model": model,
            "runtime": {"space": atelier.CPU_LAB_SPACE,
                        "release_id": atelier.CPU_LAB_RELEASE_ID,
                        "service_level": "BEST_EFFORT_NO_SLA"},
            "receipts": {"covers_this_output": False},
            "output": {"signature_status": "UNSIGNED", "signature": None,
                       "termination_reason": "stop"},
            "execution_record": record,
        },
    }


@pytest.fixture
def configured(monkeypatch, tmp_path):
    for name in ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM",
                 "A11OY_RECEIPT_KEY_PEM", "A11OY_RECEIPT_KEY_PATH", "A11OY_RECEIPT_KEY_DIR",
                 "A11OY_ATELIER_CREDENTIALS_JSON", "A11OY_ATELIER_NAMESPACE",
                 "A11OY_ATELIER_XAI_API_KEY", "XAI_API_KEY", "A11OY_ATELIER_LEDGER_PATH",
                 "A11OY_ATELIER_REQUIRED_MOUNT", "A11OY_ATELIER_LOCAL_URL",
                 "A11OY_ATELIER_LOCAL_MODEL", "A11OY_ATELIER_LOCAL_MODEL_DIGEST",
                 "SZL_GIT_SHA"):
        monkeypatch.delenv(name, raising=False)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", pem)
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_SIGNING", "1")
    monkeypatch.setenv("A11OY_ATELIER_CREDENTIALS_JSON", json.dumps({
        "version": 1, "credentials": [{
            "owner_id": "owner:cpu-lab", "namespace": "a11oy", "key_id": "cpu-lab-key-1",
            "token": TOKEN, "scopes": ["atelier:write"], "revoked": False,
        }],
    }))
    ledger = tmp_path / "retained" / "atelier.jsonl"
    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SZL_GIT_SHA", "4e3941c1a922f1d6877e292b3cc3803a9d443e87")
    calls = []

    def fake_transport(url, **kwargs):
        calls.append((url, kwargs))
        if kwargs["method"] == "GET":
            return identity_document(), None
        return completion_document(json.loads(kwargs["body"])), None

    monkeypatch.setattr(atelier.szl_provider_http, "http_json", fake_transport)
    app = FastAPI()

    @app.get("/{path:path}")
    async def catchall(path):
        return {"caught": path}

    atelier.register(app)
    with TestClient(app) as client:
        yield {"client": client, "app": app, "calls": calls,
               "ledger": ledger, "monkeypatch": monkeypatch,
               "fake_transport": fake_transport}


def post(env, **body):
    return env["client"].post(f"{atelier.PREFIX}/cpu-lab/turn",
                              json={"prompt": PROMPT, "declared": "PUBLIC",
                                    "public_share_acknowledged": True, **body},
                              headers={"Authorization": f"Bearer {TOKEN}"})


def records(env):
    return [json.loads(line) for line in env["ledger"].read_text().splitlines()]


def assert_signed(response, env, count=2):
    saved = records(env)
    assert len(saved) == count
    body = response.json()
    receipt, envelope = body["receipt"], body["dsse"]
    assert receipt["persisted"] is True and receipt["signature_verified"] is True
    assert saved[-1]["digest"] == receipt["digest"]
    assert envelope["signed"] is True
    assert atelier.szl_dsse.verify_envelope(envelope)["verified"] is True
    assert json.loads(base64.b64decode(envelope["payload"])) == receipt["payload"]
    assert all(atelier.szl_dsse.verify_envelope(row["dsse"])["verified"] for row in saved)
    return [row["payload"] for row in saved]


def test_success_is_exactly_one_identity_get_one_post_and_signed_public_metadata(configured):
    response = post(configured, max_output_tokens=24)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "COMPLETED" and body["answer"] == ANSWER
    assert body["model"] == atelier.CPU_LAB_MODEL
    assert body["provider"] == "szl_cpu_lab"
    assert body["mode"] == "NO_PROVIDER_KEY_PUBLIC_CPU_LAB"
    assert body["provider_output_signature_status"] == "UNSIGNED"
    assert body["energy"] == {"label": "UNAVAILABLE", "joules": None}
    assert body["retry_safe"] is False and response.headers["cache-control"] == "no-store"
    decision, outcome = assert_signed(response, configured)
    assert decision["phase"] == "DECISION" and decision["decision"] == "ALLOW"
    assert outcome["phase"] == "OUTCOME" and outcome["state"] == "COMPLETED"
    assert outcome["decision_receipt_hash"] == outcome["prior_hash"]
    assert decision["model_digest_expected"] == atelier.CPU_LAB_MODEL_SHA256
    assert outcome["model_digest_observed_before_call"] == atelier.CPU_LAB_MODEL_SHA256
    assert decision["release_id_expected"] == atelier.CPU_LAB_RELEASE_ID
    assert outcome["release_id_observed_before_call"] == atelier.CPU_LAB_RELEASE_ID
    assert decision["public_share_acknowledged"] is True
    assert decision["prompt_sha256"] == hashlib.sha256(PROMPT.encode()).hexdigest()
    assert outcome["answer_sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
    assert outcome["provider_output_signature_status"] == "UNSIGNED"
    assert outcome["provider_unsigned_execution_record_sha256"]
    assert outcome["usage"] == {"prompt_tokens": 18, "completion_tokens": 7,
                                "total_tokens": 25}
    assert PROMPT not in configured["ledger"].read_text()
    assert ANSWER not in configured["ledger"].read_text()
    assert "never forward this" not in response.text
    assert len(configured["calls"]) == 2
    identity_url, identity_options = configured["calls"][0]
    chat_url, chat_options = configured["calls"][1]
    assert identity_url == atelier.CPU_LAB_IDENTITY_URL
    assert identity_options == {"method": "GET", "timeout": 4.0,
                                "max_response_bytes": 16_384,
                                "max_redirects": 0, "allow_private": False}
    assert chat_url == atelier.CPU_LAB_CHAT_URL
    assert chat_options["method"] == "POST" and chat_options["timeout"] == 60.0
    assert chat_options["max_redirects"] == 0 and chat_options["allow_private"] is False
    assert "Authorization" not in chat_options["headers"]
    sent = json.loads(chat_options["body"])
    assert sent == {"model": atelier.CPU_LAB_MODEL,
                    "messages": [{"role": "user", "content": PROMPT}],
                    "max_completion_tokens": 24, "temperature": 0.0,
                    "top_p": 1.0, "n": 1, "stream": False}
    assert decision["outbound_request_sha256"] == hashlib.sha256(
        chat_options["body"]).hexdigest()


@pytest.mark.parametrize("header", [None, "Bearer incorrect", "Basic test", "Bearer"])
def test_authentication_precedes_body_ledger_and_egress(configured, header):
    response = configured["client"].post(
        f"{atelier.PREFIX}/cpu-lab/turn", content=b"not-json",
        headers={"Authorization": header} if header else {})
    assert response.status_code == 401
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("body", [
    {"model": "grok-4.7"}, {"url": "https://example.com"},
    {"reasoning_effort": "high"}, {"declared": "INTERNAL"},
    {"public_share_acknowledged": False}, {"public_share_acknowledged": 1},
    {"max_output_tokens": 33}, {"max_output_tokens": True},
    {"prompt": " prefixed"}, {"prompt": "trailing "},
    {"prompt": "<|im_start|>test"}, {"prompt": "a\x00b"},
    {"prompt": "x" * 1201},
])
def test_request_rejects_nonpublic_extra_or_modified_prompt(configured, body):
    response = post(configured, **body)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert not configured["calls"] and not configured["ledger"].exists()


def test_public_share_acknowledgment_is_required_on_each_turn(configured):
    response = configured["client"].post(
        f"{atelier.PREFIX}/cpu-lab/turn",
        json={"prompt": PROMPT, "declared": "PUBLIC"},
        headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("prompt", [
    "Synthetic xai-" + "A" * 24,
    "Synthetic hf_" + "B" * 24,
    "Synthetic sk-" + "C" * 24,
    "-----BEGIN PRIVATE KEY-----\nnot-a-real-key",
    "Authorization: Bearer synthetic-value",
])
def test_known_secret_shapes_are_rejected_before_receipt_or_egress(configured, prompt):
    response = post(configured, prompt=prompt)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert prompt not in response.text
    assert not configured["calls"] and not configured["ledger"].exists()


def test_duplicate_keys_and_oversized_body_are_rejected(configured):
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    duplicate = configured["client"].post(f"{atelier.PREFIX}/cpu-lab/turn",
                                           content=b'{"prompt":"a","prompt":"b"}',
                                           headers=headers)
    assert duplicate.status_code == 422
    huge = configured["client"].post(f"{atelier.PREFIX}/cpu-lab/turn",
                                      content=b"x" * (atelier.CPU_LAB_MAX_BODY_BYTES + 1),
                                      headers=headers)
    assert huge.status_code == 413
    assert not configured["calls"] and not configured["ledger"].exists()


def test_classification_and_policy_must_both_allow_public_egress(configured):
    configured["monkeypatch"].setattr(
        atelier.szl_governance_gateway, "classify",
        lambda *args, **kwargs: {"class": "INTERNAL"})
    configured["monkeypatch"].setattr(
        atelier.a11oy_vertical_feeds, "governed_turn",
        lambda *args, **kwargs: {"decision": "allow"})
    response = post(configured)
    assert response.status_code == 403
    decision = assert_signed(response, configured, count=1)[0]
    assert decision["decision"] == "DENY" and decision["classification"] == "INTERNAL"
    assert not configured["calls"]


def test_policy_non_allow_does_not_egress(configured):
    configured["monkeypatch"].setattr(
        atelier.a11oy_vertical_feeds, "governed_turn",
        lambda *args, **kwargs: {"decision": "allow_with_warning"})
    response = post(configured)
    assert response.status_code == 403
    assert assert_signed(response, configured, count=1)[0]["decision"] == "DENY"
    assert not configured["calls"]


@pytest.mark.parametrize("missing,code", [
    ("A11OY_ATELIER_CREDENTIALS_JSON", "CREDENTIALS_UNAVAILABLE"),
    ("SZL_COSIGN_PRIVATE_PEM", "SIGNER_UNAVAILABLE"),
    ("A11OY_ATELIER_LEDGER_PATH", "LEDGER_UNAVAILABLE"),
])
def test_required_configuration_fails_before_egress(configured, missing, code):
    configured["monkeypatch"].delenv(missing)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == code
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("identity,code", [
    (None, "CPU_LAB_IDENTITY_UNAVAILABLE"),
    (identity_document(status="STARTING"), "CPU_LAB_IDENTITY_MISMATCH"),
    (identity_document(model={"sha256_loaded": "b" * 64}),
     "CPU_LAB_IDENTITY_MISMATCH"),
])
def test_preflight_failure_is_signed_and_never_posts(configured, identity, code):
    def fake(url, **kwargs):
        configured["calls"].append((url, kwargs))
        assert kwargs["method"] == "GET"
        return (None, "TIMEOUT") if identity is None else (identity, None)

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", fake)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == code
    decision, outcome = assert_signed(response, configured)
    assert decision["phase"] == "DECISION" and decision["decision"] == "ALLOW"
    assert outcome["phase"] == "OUTCOME" and outcome["state"] == "UNAVAILABLE"
    assert outcome["provider_outcome_uncertain"] is False
    assert len(configured["calls"]) == 1


@pytest.mark.parametrize("change", [
    lambda d: d.update(model="other-model"),
    lambda d: d["choices"][0].update(finish_reason="length"),
    lambda d: d.update(choices=[]),
    lambda d: d["szl_provenance"]["model"].update(sha256="b" * 64),
    lambda d: d["szl_provenance"]["output"].update(signature_status="SIGNED"),
    lambda d: d["szl_provenance"]["execution_record"].update(record_sha256="b" * 64),
    lambda d: d["szl_provenance"]["execution_record"].update(
        canonical_request_sha256="b" * 64),
    lambda d: d["szl_provenance"]["execution_record"].update(
        output_sha256="b" * 64),
    lambda d: d["usage"].update(completion_tokens=33),
])
def test_bad_or_partial_lab_response_is_signed_unavailable(configured, change):
    def fake(url, **kwargs):
        configured["calls"].append((url, kwargs))
        if kwargs["method"] == "GET":
            return identity_document(), None
        document = completion_document(json.loads(kwargs["body"]))
        change(document)
        return document, None

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", fake)
    response = post(configured)
    assert response.status_code == 502
    assert response.json()["code"] == "CPU_LAB_INVALID_RESPONSE"
    assert "answer" not in response.json()
    decision, outcome = assert_signed(response, configured)
    assert decision["phase"] == "DECISION"
    assert outcome["state"] == "UNAVAILABLE" and outcome["provider_outcome_uncertain"] is True
    assert len(configured["calls"]) == 2


@pytest.mark.parametrize("transport_code,expected,status", [
    ("TIMEOUT", "CPU_LAB_TIMEOUT", 504),
    ("HTTP_STATUS:429", "CPU_LAB_UNAVAILABLE", 502),
    ("HTTP_STATUS:422", "CPU_LAB_UNAVAILABLE", 502),
])
def test_single_post_failure_is_signed_uncertain(configured, transport_code, expected, status):
    def fake(url, **kwargs):
        configured["calls"].append((url, kwargs))
        return (identity_document(), None) if kwargs["method"] == "GET" else (
            None, transport_code)

    configured["monkeypatch"].setattr(atelier.szl_provider_http, "http_json", fake)
    response = post(configured)
    assert response.status_code == status
    assert response.json()["code"] == expected and "answer" not in response.json()
    _, outcome = assert_signed(response, configured)
    assert outcome["provider_outcome_uncertain"] is True
    assert len(configured["calls"]) == 2


def test_outcome_write_failure_withholds_answer(configured):
    original = atelier._append

    def fail_outcome(store, principal, metadata):
        if metadata.get("phase") == "OUTCOME":
            raise atelier.AtelierFailure("LEDGER_WRITE_FAILED")
        return original(store, principal, metadata)

    configured["monkeypatch"].setattr(atelier, "_append", fail_outcome)
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LEDGER_WRITE_FAILED"
    assert "answer" not in response.json() and ANSWER not in response.text
    assert len(records(configured)) == 1
    assert len(configured["calls"]) == 2


def test_retained_chain_tamper_blocks_later_provider_call(configured):
    assert post(configured).status_code == 200
    saved = records(configured)
    saved[0]["payload"]["decision"] = "DENY"
    configured["ledger"].write_text("\n".join(json.dumps(row) for row in saved) + "\n")
    configured["calls"].clear()
    response = post(configured)
    assert response.status_code == 503
    assert response.json()["code"] == "LEDGER_INTEGRITY_UNAVAILABLE"
    assert not configured["calls"]


def test_health_is_read_only_and_does_not_claim_inference(configured):
    def forbidden_transport(*args, **kwargs):
        raise AssertionError("health must not contact the provider")

    configured["monkeypatch"].setattr(
        atelier.szl_provider_http, "http_json", forbidden_transport)
    for _ in range(3):
        response = configured["client"].get(f"{atelier.PREFIX}/cpu-lab/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True and body["blockers"] == []
        assert body["ready_scope"] == "LOCAL_PREREQUISITES_ONLY"
        assert body["mode"] == "NO_PROVIDER_KEY_PUBLIC_CPU_LAB"
        assert body["model"] == atelier.CPU_LAB_MODEL
        assert body["provider"] == "szl_cpu_lab"
        assert body["provider_identity_verified"] is False
        assert body["inference_verified"] is False
        assert body["configured"]["ledger_path_configured"] is True
        assert body["ledger_durability_verified"] is False
        assert body["output_signature_status"] == "UNSIGNED"
        head = configured["client"].head(f"{atelier.PREFIX}/cpu-lab/health")
        assert head.status_code == 200 and head.text == ""
    assert not configured["calls"]
    assert not configured["ledger"].exists()


def test_health_reports_ledger_path_configuration_without_durability_claim(configured):
    configured["monkeypatch"].delenv("A11OY_ATELIER_LEDGER_PATH")
    response = configured["client"].get(f"{atelier.PREFIX}/cpu-lab/health")
    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["model"] is None
    assert response.json()["blockers"] == ["LEDGER_UNAVAILABLE"]
    assert response.json()["configured"]["ledger_path_configured"] is False
    assert response.json()["ledger_durability_verified"] is False
    assert response.json()["provider_identity_verified"] is False
    assert response.json()["inference_verified"] is False
    assert not configured["calls"]
    assert not configured["ledger"].exists()


def test_cpu_lab_routes_precede_catchall_and_register_once(configured):
    paths = [route.path for route in configured["app"].router.routes]
    assert paths.index(f"{atelier.PREFIX}/cpu-lab/health") < paths.index("/{path:path}")
    assert paths.index(f"{atelier.PREFIX}/cpu-lab/turn") < paths.index("/{path:path}")
    assert atelier.register(configured["app"])["state"] == "ALREADY_REGISTERED"
