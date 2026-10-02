"""Local contract evidence: actual temporary signing key, fake provider transport.

These tests prove Python boundaries and retained receipts, not xAI availability,
production deployment, conversation continuity or measured energy consumption.
"""

import base64
import hashlib
import json
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from routers import atelier_grok as atelier
from szl_durable_ledger import StoreResult


TOKEN = "local-atelier-credential"
PROVIDER_KEY = "local-fake-provider-key"
PROMPT = "Create a concise design brief for a blue ceramic cup."
ANSWER = "Use a blue glaze and a comfortable handle."
CIPHERTEXT = "local-encrypted-reasoning-must-disappear"


def credential(**overrides):
    return {"owner_id": "owner:local", "namespace": "a11oy", "key_id": "local-key-1",
            "token": TOKEN, "scopes": ["atelier:write"], "revoked": False, **overrides}


def registry(*credentials):
    return json.dumps({"version": 1, "credentials": list(credentials or [credential()])})


def provider_document(model="grok-4.7"):
    return {"id": "local-provider-response-1", "model": model, "status": "completed",
            "output": [
                {"type": "reasoning", "encrypted_content": CIPHERTEXT,
                 "summary": [{"type": "summary_text", "text": "private reasoning"}]},
                {"type": "message", "role": "user", "content": [
                    {"type": "output_text", "text": "not an assistant answer"}]},
                {"type": "message", "role": "assistant", "status": "completed", "content": [
                    {"type": "output_text", "text": ANSWER},
                    {"type": "encrypted_content", "text": CIPHERTEXT}]}],
            "usage": {"input_tokens": 12, "output_tokens": 10, "total_tokens": 22,
                      "untrusted_extra": "private reasoning"}}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    # Never consume an ambient organization key or credential in local tests.
    for name in ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM",
                 "A11OY_RECEIPT_KEY_PEM", "A11OY_RECEIPT_KEY_PATH", "A11OY_RECEIPT_KEY_DIR",
                 "A11OY_ATELIER_CREDENTIALS_JSON", "A11OY_ATELIER_NAMESPACE",
                 "A11OY_ATELIER_XAI_API_KEY", "XAI_API_KEY", "A11OY_ATELIER_LEDGER_PATH",
                 "A11OY_ATELIER_REQUIRED_MOUNT",
                 "SZL_GROK_MODEL", "A11OY_ATELIER_MODEL", "SZL_GIT_SHA"):
        monkeypatch.delenv(name, raising=False)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", pem)
    monkeypatch.setenv("A11OY_REQUIRE_PERSISTENT_SIGNING", "1")
    monkeypatch.setenv("A11OY_ATELIER_CREDENTIALS_JSON", registry())
    monkeypatch.setenv("A11OY_ATELIER_XAI_API_KEY", PROVIDER_KEY)
    ledger = tmp_path / "retained" / "atelier.jsonl"
    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SZL_GIT_SHA", "599d3a4783fe2816a7c5cf15a819453d5cb6c264")
    calls = []

    def fake_transport(url, **kwargs):
        body = json.loads(kwargs["body"])
        calls.append((url, kwargs, body))
        return provider_document(body["model"]), None

    monkeypatch.setattr(atelier.szl_provider_http, "http_json", fake_transport)
    app = FastAPI()

    @app.get("/{path:path}")
    async def catchall(path):
        return {"caught": path}

    atelier.register(app)
    with TestClient(app) as client:
        yield {"client": client, "app": app, "ledger": ledger, "calls": calls,
               "monkeypatch": monkeypatch}


def post(env, **body):
    return env["client"].post(f"{atelier.PREFIX}/turn", json={"prompt": PROMPT, **body},
                              headers={"Authorization": f"Bearer {TOKEN}"})


def records(env):
    return [json.loads(line) for line in env["ledger"].read_text().splitlines()]


def assert_signed(response, env, count=2):
    body = response.json()
    receipt = body["receipt"]
    envelope = body["dsse"]
    assert receipt["persisted"] is True
    assert receipt["signature_verified"] is True
    assert receipt["digest"] == atelier._digest(receipt["payload"])
    assert envelope["signed"] is True
    assert atelier.szl_dsse.verify_envelope(envelope)["verified"] is True
    assert json.loads(base64.b64decode(envelope["payload"])) == receipt["payload"]
    saved = records(env)
    assert len(saved) == count
    assert saved[-1]["digest"] == receipt["digest"]
    assert saved[-1]["dsse"] == envelope
    assert all(atelier.szl_dsse.verify_envelope(row["dsse"])["verified"] for row in saved)
    return saved


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh"])
def test_single_turn_signed_metadata_only_final_answer(configured, effort, monkeypatch):
    governed = atelier.a11oy_vertical_feeds.governed_turn
    decisions = []

    def observed(*args, **kwargs):
        decisions.append(kwargs)
        return governed(*args, **kwargs)

    monkeypatch.setattr(atelier.a11oy_vertical_feeds, "governed_turn", observed)
    response = post(configured, reasoning_effort=effort)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "COMPLETED"
    assert body["answer"] == ANSWER
    assert body["model"] == "grok-4.7"
    assert str(UUID(body["request_id"])) == body["request_id"]
    assert body["energy"] == {"label": "UNAVAILABLE", "joules": None}
    assert body["retry_safe"] is False
    assert response.headers["cache-control"] == "no-store"
    saved = assert_signed(response, configured)
    decision, outcome = [row["payload"] for row in saved]
    assert decision["phase"] == "DECISION" and decision["decision"] == "ALLOW"
    assert outcome["phase"] == "OUTCOME" and outcome["state"] == "COMPLETED"
    assert outcome["prior_hash"] == outcome["decision_receipt_hash"] == saved[0]["digest"]
    assert decision["sequence"] == 1 and outcome["sequence"] == 2
    assert decision["owner_id"] == "owner:local" and decision["namespace"] == "a11oy"
    assert decision["prompt_sha256"] == hashlib.sha256(PROMPT.encode()).hexdigest()
    assert outcome["answer_sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
    assert outcome["usage"] == {"input_tokens": 12, "output_tokens": 10, "total_tokens": 22}
    assert decisions[0]["emit_receipt"] is False
    assert decisions[0]["action_kind"] == "inference"
    assert len(configured["calls"]) == 1
    url, options, sent = configured["calls"][0]
    assert url == "https://api.x.ai/v1/responses"
    assert options["method"] == "POST" and options["timeout"] == 120.0
    assert options["max_redirects"] == 0 and options["allow_private"] is False
    assert options["headers"]["Authorization"] == f"Bearer {PROVIDER_KEY}"
    assert sent == {"model": "grok-4.7", "input": [{"role": "user", "content": PROMPT}],
                    "reasoning": {"effort": effort}, "store": False,
                    "max_output_tokens": 4096, "tools": []}
    retained = configured["ledger"].read_text()
    for private in (PROMPT, ANSWER, TOKEN, PROVIDER_KEY, CIPHERTEXT, "private reasoning"):
        assert private not in retained
    for private in (TOKEN, PROVIDER_KEY, CIPHERTEXT, "private reasoning", PROMPT):
        assert private not in response.text


@pytest.mark.parametrize("header", [None, "Bearer incorrect", "Basic local", "Bearer"])
def test_authentication_rejected_before_ledger_or_provider(configured, header):
    response = configured["client"].post(f"{atelier.PREFIX}/turn", json={"prompt": PROMPT},
                                       headers={} if header is None else {"Authorization": header})
    assert response.status_code == 401
    assert response.json() == {"state": "DENIED", "code": "AUTH_REQUIRED", "retry_safe": False}
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("change", [{"namespace": "other"}, {"revoked": True}, {"scopes": ["atelier:read"]}])
def test_forbidden_principal_never_calls_provider(configured, monkeypatch, change):
    monkeypatch.setenv("A11OY_ATELIER_CREDENTIALS_JSON", registry(credential(**change)))
    response = post(configured)
    assert response.status_code == 403 and response.json()["code"] == "AUTH_FORBIDDEN"
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("missing,code", [
    ("A11OY_ATELIER_CREDENTIALS_JSON", "CREDENTIALS_UNAVAILABLE"),
    ("A11OY_ATELIER_XAI_API_KEY", "PROVIDER_UNAVAILABLE"),
    ("SZL_COSIGN_PRIVATE_PEM", "SIGNER_UNAVAILABLE"),
    ("A11OY_ATELIER_LEDGER_PATH", "LEDGER_UNAVAILABLE")])
def test_missing_required_configuration_is_503_without_provider(configured, monkeypatch, missing, code):
    monkeypatch.delenv(missing)
    response = post(configured)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == code
    assert not configured["calls"] and not configured["ledger"].exists()


def test_unavailable_signer_and_invalid_signature_fail_closed(configured, monkeypatch):
    monkeypatch.setattr(atelier.szl_dsse, "signing_available", lambda: False)
    assert post(configured).json()["code"] == "SIGNER_UNAVAILABLE"
    assert not configured["calls"]
    monkeypatch.setattr(atelier.szl_dsse, "signing_available", lambda: True)
    monkeypatch.setattr(atelier.szl_dsse, "sign_payload", lambda *a, **k: {"signed": True})
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "SIGNATURE_UNAVAILABLE"
    assert not configured["calls"]


@pytest.mark.parametrize("declared", ["RESTRICTED", "SECRET"])
def test_sensitivity_floor_denial_is_signed_without_egress(configured, declared):
    response = post(configured, declared=declared)
    assert response.status_code == 403 and response.json()["code"] == "POLICY_DENIED"
    saved = assert_signed(response, configured, count=1)
    assert saved[0]["payload"]["decision"] == "DENY"
    assert saved[0]["payload"]["classification"] == declared
    assert not configured["calls"]
    assert PROMPT not in configured["ledger"].read_text()


@pytest.mark.parametrize("prompt", ["drop table old_records", "An SSN is 123-45-6789."])
def test_real_deterministic_doctrine_gate_denies_threat_or_pii(configured, prompt):
    response = post(configured, prompt=prompt)
    assert response.status_code == 403 and response.json()["code"] == "POLICY_DENIED"
    saved = assert_signed(response, configured, count=1)
    assert saved[0]["payload"]["policy_decision"] == "deny"
    assert not configured["calls"] and prompt not in configured["ledger"].read_text()


def test_only_exact_policy_allow_permits_egress(configured, monkeypatch):
    monkeypatch.setattr(atelier.a11oy_vertical_feeds, "governed_turn", lambda *a, **k: {"decision": "review"})
    response = post(configured)
    assert response.status_code == 403
    assert_signed(response, configured, count=1)
    assert not configured["calls"]


@pytest.mark.parametrize("body", [{"model": "untrusted-model"}, {"model": ""}])
def test_bad_model_zero_calls(configured, body):
    response = post(configured, **body)
    assert response.status_code == 400 and response.json()["code"] == "MODEL_NOT_ALLOWED"
    assert not configured["calls"] and not configured["ledger"].exists()


def test_model_precedence_and_legacy_compatibility(configured, monkeypatch):
    monkeypatch.setenv("A11OY_ATELIER_MODEL", "grok-4.6")
    assert post(configured).json()["model"] == "grok-4.6"
    monkeypatch.setenv("SZL_GROK_MODEL", "grok-4.7")
    assert post(configured).json()["model"] == "grok-4.7"
    assert post(configured, model="grok-4.6").json()["model"] == "grok-4.6"
    monkeypatch.setenv("SZL_GROK_MODEL", "invalid-model")
    assert post(configured).json()["code"] == "MODEL_NOT_ALLOWED"
    assert post(configured, model="grok-4.7").json()["model"] == "grok-4.7"
    assert len(configured["calls"]) == 4
    saved = records(configured)
    assert [row["payload"]["sequence"] for row in saved] == list(range(1, 9))
    assert all(saved[index]["payload"]["prior_hash"] == saved[index - 1]["digest"]
               for index in range(1, len(saved)))


def test_provider_key_fallback_is_server_only(configured, monkeypatch):
    monkeypatch.delenv("A11OY_ATELIER_XAI_API_KEY")
    monkeypatch.setenv("XAI_API_KEY", PROVIDER_KEY)
    response = post(configured)
    assert response.status_code == 200
    assert configured["calls"][0][1]["headers"]["Authorization"] == f"Bearer {PROVIDER_KEY}"
    assert PROVIDER_KEY not in response.text and PROVIDER_KEY not in configured["ledger"].read_text()


@pytest.mark.parametrize("change", [
    {"prompt": " "}, {"prompt": "x" * 32_769}, {"prompt": 123},
    {"reasoning_effort": "maximum"}, {"declared": "secret"},
    {"max_output_tokens": 4097}, {"max_output_tokens": True}, {"max_output_tokens": 0},
    {"tools": [{"name": "shell"}]}, {"history": [PROMPT]}, {"api_key": PROVIDER_KEY}])
def test_validation_rejects_extra_fields_without_echoing_input(configured, change):
    response = post(configured, **change)
    assert response.status_code == 422
    assert response.json() == {"state": "DENIED", "code": "INVALID_REQUEST", "retry_safe": False}
    assert not configured["calls"] and not configured["ledger"].exists()
    assert PROMPT not in response.text and PROVIDER_KEY not in response.text


@pytest.mark.parametrize("raw,status", [
    (b'{"prompt":"first","prompt":"second"}', 422),
    (b'{"prompt":', 422), (b'\xff', 422), (b'[]', 422),
    (b'{"prompt":"' + b'x' * atelier.MAX_BODY_BYTES + b'"}', 413)],
    ids=["duplicate-key", "incomplete-json", "invalid-utf8", "nonobject", "oversized-body"])
def test_raw_body_is_bounded_and_duplicate_keys_rejected(configured, raw, status):
    response = configured["client"].post(f"{atelier.PREFIX}/turn", content=raw,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    assert response.status_code == status
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("code,status", [("HTTP_STATUS:401", 401), ("HTTP_STATUS:402", 402),
    ("HTTP_STATUS:403", 403), ("HTTP_STATUS:429", 429), ("HTTP_STATUS:503", 502),
    ("TIMEOUT", 504), ("NETWORK_FAILURE", 502), ("raw private error", 502)])
def test_provider_failure_is_once_sanitized_and_retained(configured, monkeypatch, code, status):
    calls = []

    def failed(*args, **kwargs):
        calls.append(True)
        return None, code

    monkeypatch.setattr(atelier.szl_provider_http, "http_json", failed)
    response = post(configured)
    assert response.status_code == status, response.text
    assert response.json()["state"] == "UNAVAILABLE" and response.json()["retry_safe"] is False
    saved = assert_signed(response, configured)
    assert saved[-1]["payload"]["phase"] == "OUTCOME"
    assert saved[-1]["payload"]["state"] == "UNAVAILABLE"
    assert len(calls) == 1
    assert "raw private error" not in response.text


def test_transport_exception_never_echoed_or_retried(configured, monkeypatch):
    calls = []

    def failed(*args, **kwargs):
        calls.append(True)
        raise RuntimeError(f"private failure: {PROVIDER_KEY} {PROMPT}")

    monkeypatch.setattr(atelier.szl_provider_http, "http_json", failed)
    response = post(configured)
    assert response.status_code == 502 and response.json()["code"] == "PROVIDER_UNAVAILABLE"
    saved = assert_signed(response, configured)
    assert saved[-1]["payload"]["provider_outcome_uncertain"] is True
    assert len(calls) == 1
    assert PROVIDER_KEY not in response.text and PROMPT not in response.text


@pytest.mark.parametrize("change", [{"model": "wrong-model"}, {"status": "in_progress"},
    {"output": None}, {"output": []},
    {"output": [{"type": "reasoning", "encrypted_content": CIPHERTEXT}]},
    {"output": [{"type": "message", "role": "assistant", "content": None}]}])
def test_invalid_or_reasoning_only_response_cannot_be_answer(configured, monkeypatch, change):
    monkeypatch.setattr(atelier.szl_provider_http, "http_json",
                        lambda *a, **k: ({**provider_document(), **change}, None))
    response = post(configured)
    assert response.status_code == 502 and response.json()["code"] == "PROVIDER_INVALID_RESPONSE"
    assert "answer" not in response.json() and CIPHERTEXT not in response.text
    assert_signed(response, configured)


@pytest.mark.parametrize("path_kind", ["relative", "directory"])
def test_invalid_ledger_path_prevents_provider(configured, monkeypatch, tmp_path, path_kind):
    path = "relative.jsonl" if path_kind == "relative" else str(tmp_path)
    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", path)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_UNAVAILABLE"
    assert not configured["calls"]


def test_required_mount_is_checked_before_provider_and_without_get_side_effects(configured, monkeypatch, tmp_path):
    mount = tmp_path / "mounted"
    mount.mkdir()
    ledger = mount / "atelier" / "receipts.jsonl"
    monkeypatch.setenv("A11OY_ATELIER_REQUIRED_MOUNT", str(mount))
    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", str(ledger))
    monkeypatch.setattr(atelier.os.path, "ismount", lambda candidate: candidate == str(mount))
    health = configured["client"].get(f"{atelier.PREFIX}/health")
    assert health.status_code == 200 and health.json()["configured"]["ledger"] is True
    assert not ledger.exists() and not configured["calls"]
    assert post(configured).status_code == 200
    assert ledger.exists() and len(configured["calls"]) == 1

    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", str(tmp_path / "outside.jsonl"))
    outside = post(configured)
    assert outside.status_code == 503 and outside.json()["code"] == "LEDGER_UNAVAILABLE"
    assert len(configured["calls"]) == 1
    assert not (tmp_path / "outside.jsonl").exists()

    monkeypatch.setenv("A11OY_ATELIER_LEDGER_PATH", str(ledger))
    monkeypatch.setattr(atelier.os.path, "ismount", lambda _candidate: False)
    unmounted = post(configured)
    assert unmounted.status_code == 503 and unmounted.json()["code"] == "LEDGER_UNAVAILABLE"
    assert len(configured["calls"]) == 1


def test_storage_preflight_failure_prevents_provider(configured, monkeypatch):
    monkeypatch.setattr(atelier.DurableStore, "status", lambda self: {"status": "UNAVAILABLE"})
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_UNAVAILABLE"
    assert not configured["calls"]


def test_decision_append_failure_prevents_provider(configured, monkeypatch):
    monkeypatch.setattr(atelier.DurableStore, "append",
                        lambda *a, **k: StoreResult(False, "UNAVAILABLE", error="local injected failure"))
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_WRITE_FAILED"
    assert not configured["calls"]


def test_outcome_append_failure_withholds_answer_and_does_not_retry(configured, monkeypatch):
    append = atelier.DurableStore.append
    appends = []

    def append_once(self, record):
        appends.append(record)
        if len(appends) == 2:
            return StoreResult(False, "UNAVAILABLE", error="local injected failure")
        return append(self, record)

    monkeypatch.setattr(atelier.DurableStore, "append", append_once)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_WRITE_FAILED"
    assert "answer" not in response.json() and response.json()["retry_safe"] is False
    assert len(configured["calls"]) == 1 and len(records(configured)) == 1


def test_retained_receipt_tampering_prevents_next_provider_call(configured):
    assert post(configured).status_code == 200
    saved = records(configured)
    saved[0]["payload"]["decision"] = "DENY"
    configured["ledger"].write_text("\n".join(json.dumps(row) for row in saved) + "\n")
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_INTEGRITY_UNAVAILABLE"
    assert len(configured["calls"]) == 1


def test_stable_owner_chain_survives_credential_rotation(configured, monkeypatch):
    assert post(configured).status_code == 200
    monkeypatch.setenv("A11OY_ATELIER_CREDENTIALS_JSON", registry(credential(key_id="local-key-2")))
    response = post(configured)
    assert response.status_code == 200
    saved = assert_signed(response, configured, count=4)
    assert saved[2]["payload"]["prior_hash"] == saved[1]["digest"]
    assert saved[2]["payload"]["owner_id"] == saved[0]["payload"]["owner_id"]
    assert saved[2]["payload"]["key_id"] != saved[0]["payload"]["key_id"]


def test_health_read_only_configuration_not_inference_proof(configured, monkeypatch):
    def must_not_write(*args, **kwargs):
        raise AssertionError("a read attempted a write")

    monkeypatch.setattr(atelier.szl_dsse, "sign_payload", must_not_write)
    monkeypatch.setattr(atelier.DurableStore, "__init__", must_not_write)
    response = configured["client"].get(f"{atelier.PREFIX}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True and body["inference_verified"] is False
    assert body["configured"] == {"credentials": True, "provider": True, "signer": True, "ledger": True}
    assert body["source_revision"] == "599d3a4783fe2816a7c5cf15a819453d5cb6c264"
    assert body["continuity"] == "SINGLE_TURN_NO_SERVER_TEXT_HISTORY"
    assert body["energy"] == {"label": "UNAVAILABLE", "joules": None}
    head = configured["client"].head(f"{atelier.PREFIX}/health")
    assert head.status_code == 200 and head.content == b""
    assert not configured["calls"] and not configured["ledger"].parent.exists()
    assert TOKEN not in response.text and PROVIDER_KEY not in response.text


def test_health_invalid_namespace_or_model_is_truthful(configured, monkeypatch):
    monkeypatch.setenv("A11OY_ATELIER_NAMESPACE", "Invalid Namespace")
    monkeypatch.setenv("SZL_GROK_MODEL", "grok-unknown")
    body = configured["client"].get(f"{atelier.PREFIX}/health").json()
    assert body["ready"] is False and body["model"] is None
    assert "CREDENTIALS_UNAVAILABLE" in body["blockers"] and "MODEL_NOT_ALLOWED" in body["blockers"]
    assert not configured["calls"] and not configured["ledger"].exists()


@pytest.mark.parametrize("change", [{"namespace": "other"}, {"revoked": True},
                                      {"scopes": ["atelier:read"]}])
def test_health_requires_active_namespace_write_credential(configured, monkeypatch, change):
    monkeypatch.setenv("A11OY_ATELIER_CREDENTIALS_JSON", registry(credential(**change)))
    body = configured["client"].get(f"{atelier.PREFIX}/health").json()
    assert body["ready"] is False and body["configured"]["credentials"] is False
    assert "CREDENTIALS_UNAVAILABLE" in body["blockers"]


def test_concurrent_turn_is_rejected_without_wait_or_provider(configured):
    assert atelier._TURN_LOCK.acquire(blocking=False)
    try:
        response = post(configured)
    finally:
        atelier._TURN_LOCK.release()
    assert response.status_code == 409 and response.json()["code"] == "ATELIER_BUSY"
    assert not configured["calls"] and not configured["ledger"].exists()


def test_unreadable_retained_segment_prevents_provider(configured, monkeypatch):
    assert post(configured).status_code == 200
    path_class = type(configured["ledger"])
    original = path_class.open

    def injected(self, *args, **kwargs):
        if self == configured["ledger"] and args and args[0] == "r":
            raise PermissionError("local injected read failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(path_class, "open", injected)
    response = post(configured)
    assert response.status_code == 503 and response.json()["code"] == "LEDGER_INTEGRITY_UNAVAILABLE"
    assert len(configured["calls"]) == 1


def test_registration_precedes_catchall_and_is_idempotent(configured):
    paths = [getattr(route, "path", None) for route in configured["app"].router.routes]
    assert paths.index(f"{atelier.PREFIX}/health") < paths.index("/{path:path}")
    assert paths.index(f"{atelier.PREFIX}/turn") < paths.index("/{path:path}")
    before = len(paths)
    assert atelier.register(configured["app"])["state"] == "ALREADY_REGISTERED"
    assert len(configured["app"].router.routes) == before
    app = FastAPI()

    @app.get(f"{atelier.PREFIX}/health")
    def collision():
        return {}

    with pytest.raises(RuntimeError, match="ATELIER_ROUTE_COLLISION"):
        atelier.register(app)
