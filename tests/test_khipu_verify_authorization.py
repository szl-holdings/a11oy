# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Verification that mints an audit receipt requires the operator.

Uses generated test-only P-256 keys and real DSSE signing/verification.
These local tests do not qualify any deployed signer or credential.
"""
import base64
import hashlib
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import a11oy_signing_key
import a11oy_state_store as state_store
import szl_dsse
import szl_operator_auth as auth
import szl_provenance
import szl_signing_state


OPERATOR = "synthetic-khipu-verifier-operator-not-a-real-credential"
VERIFY_PATH = "/api/a11oy/khipu/verify"


@pytest.fixture
def runtime(monkeypatch):
    # This authorization suite uses the supported unmanaged local mode. The
    # durable-storage suite separately exercises managed snapshot retention.
    monkeypatch.delenv("A11OY_STATE_STORE", raising=False)
    monkeypatch.setattr(state_store, "_ACTIVE", None)
    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode("ascii")
    # The first-priority generated key prevents any ambient key-file access.
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", private_pem)
    for name in set(szl_dsse.PRIVATE_KEY_ENV_VARS) | set(a11oy_signing_key._INLINE_KEY_NAMES):
        if name != "SZL_COSIGN_PRIVATE_PEM":
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(szl_dsse.TRUSTED_PUBLIC_PEMS_ENV, raising=False)
    monkeypatch.delenv(szl_dsse.COSIGN_PUB_FINGERPRINT_ENV, raising=False)
    monkeypatch.delenv("A11OY_WIRE_D_TARGETS", raising=False)
    monkeypatch.setattr(a11oy_signing_key, "_KEY_CACHE", {})
    monkeypatch.setattr(szl_dsse, "_RUNTIME_PUBLIC_KEYS", {})
    monkeypatch.setattr(szl_dsse, "_ACTIVE_RUNTIME_KEYID", None)
    monkeypatch.setenv(auth.OPERATOR_KEY_ENV, OPERATOR)
    monkeypatch.delenv(auth.SECOND_APPROVER_KEY_ENV, raising=False)
    envelope = szl_dsse.sign_payload({"schema": "test.receipt/v1", "nonce": "test-input"})
    app = FastAPI()
    szl_provenance.register_provenance(app, "a11oy")
    auth.install_gate(app)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, dag=app.state.szl_khipu_dag,
                              key=key, envelope=envelope)


def unreachable(*_args, **_kwargs):
    pytest.fail("refused request reached body parsing, verification, signing or append")


@pytest.mark.parametrize("authorization", [None, "Bearer wrong-credential", "Basic ignored"])
@pytest.mark.parametrize("path", [VERIFY_PATH, VERIFY_PATH + "/", "/api//a11oy/khipu/verify"])
def test_refused_verification_cannot_parse_sign_or_append(runtime, monkeypatch, authorization, path):
    monkeypatch.setattr(Request, "json", unreachable)
    monkeypatch.setattr(szl_dsse, "verify_envelope", unreachable)
    monkeypatch.setattr(szl_dsse, "sign_payload", unreachable)
    monkeypatch.setattr(runtime.dag, "append_signed", unreachable)
    headers = {"Authorization": authorization} if authorization else {}
    response = runtime.client.post(path, headers=headers, content="{malformed")
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"
    assert runtime.dag.recent(10) == []


def test_unconfigured_operator_cannot_mint_verification_receipt(runtime, monkeypatch):
    monkeypatch.delenv(auth.OPERATOR_KEY_ENV)
    monkeypatch.setattr(szl_dsse, "verify_envelope", unreachable)
    monkeypatch.setattr(runtime.dag, "append_signed", unreachable)
    response = runtime.client.post(VERIFY_PATH, json=runtime.envelope,
                                   headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 401
    assert response.json()["credential_configured"] is False
    assert runtime.dag.recent(10) == []


def independent_verify(key, envelope):
    kind = envelope["payloadType"].encode("utf-8")
    payload = base64.b64decode(envelope["payload"], validate=True)
    pae = (b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" "
           + str(len(payload)).encode() + b" " + payload)
    signature = base64.b64decode(envelope["signatures"][0]["sig"], validate=True)
    key.public_key().verify(signature, pae, ec.ECDSA(hashes.SHA256()))
    return json.loads(payload)


@pytest.mark.parametrize("wrapped", [False, True])
def test_operator_verifies_and_emits_real_signed_audit_receipt(runtime, wrapped):
    assert independent_verify(runtime.key, runtime.envelope)["nonce"] == "test-input"
    payload = {"dsse": runtime.envelope} if wrapped else runtime.envelope
    response = runtime.client.post(VERIFY_PATH, json=payload,
                                   headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 200
    verdict = response.json()
    assert verdict["verified"] is True
    assert verdict["verify_receipt_signed"] is True
    nodes = runtime.dag.recent(10)
    assert len(nodes) == 1
    assert nodes[0]["digest"] == verdict["verify_receipt_digest"]
    audit = independent_verify(runtime.key, nodes[0]["dsse"])
    assert audit["schema"] == "szl.khipu.verify_op/v1"
    assert audit["op"] == "khipu/verify"
    assert audit["verified"] is True
    # Public ledger reads remain available and do not produce more receipts.
    public = runtime.client.get("/api/a11oy/khipu/ledger")
    assert public.status_code == 200
    assert public.json()["count"] == 1
    assert len(runtime.dag.recent(10)) == 1


def test_operator_records_failed_verification_without_false_success(runtime):
    altered = dict(runtime.envelope)
    altered["payload"] = base64.b64encode(b'{"nonce":"changed"}').decode("ascii")
    response = runtime.client.post(VERIFY_PATH, json=altered,
                                   headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 200
    assert response.json()["verified"] is False
    assert response.json()["verify_receipt_signed"] is True
    nodes = runtime.dag.recent(10)
    assert len(nodes) == 1
    assert independent_verify(runtime.key, nodes[0]["dsse"])["verified"] is False


def test_non_mutating_verification_and_safe_methods_stay_public():
    # szl_warhacker_aliases.warhacker_verify returns only a verdict; it does not
    # emit_signed_receipt. Protecting that short path would break public replay.
    assert auth.protected_action("POST", "/khipu/verify") is None
    for method in ("GET", "HEAD", "OPTIONS"):
        assert auth.protected_action(method, VERIFY_PATH) is None


@pytest.mark.parametrize("recorded", [False, True])
@pytest.mark.parametrize("observation", ["absent", "fresh", "stale", "ephemeral", "mismatch"])
def test_ledger_projects_metadata_without_loading_signing_or_refreshing(runtime, monkeypatch,
                                                                       recorded, observation):
    if recorded:
        response = runtime.client.post(VERIFY_PATH, json=runtime.envelope,
                                       headers={"Authorization": "Bearer " + OPERATOR})
        assert response.status_code == 200
    expected_nodes = runtime.dag.recent(20)
    owner = None
    fingerprint = None
    if observation != "absent":
        now = [10.0]
        owner = szl_signing_state.SigningState(clock=lambda: now[0])
        public = runtime.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        fingerprint = hashlib.sha256(public.strip()).hexdigest()
        captured = owner.sample(
            boot_id="synthetic-test-boot", observed_at="2026-01-01T00:00:00Z",
            configured=observation != "ephemeral",
            key_source=("ephemeral" if observation == "ephemeral"
                        else "persistent:env:synthetic-test-key"),
            backend_loaded=True, backend_state="LOADED_LOCAL",
            verification_key_fingerprint=fingerprint,
            loaded_key_fingerprint="0" * 64 if observation == "mismatch" else fingerprint,
            expected_key_fingerprint=fingerprint)
        runtime.client.app.state.szl_signing_state = owner
        if observation == "stale":
            now[0] += 60.0
        monkeypatch.setattr(owner, "sample", unreachable)
        monkeypatch.setattr(owner, "invalidate", unreachable)
    monkeypatch.setattr(szl_dsse, "sign_payload", unreachable)
    monkeypatch.setattr(szl_dsse, "_load_private_key", unreachable)
    monkeypatch.setattr(szl_dsse, "signing_available", unreachable)
    monkeypatch.setattr(szl_dsse, "public_key_fingerprint", unreachable)
    monkeypatch.setattr(a11oy_signing_key, "load_signing_key", unreachable)
    monkeypatch.setattr(ec, "generate_private_key", unreachable)
    for _ in range(2):
        response = runtime.client.get("/api/a11oy/khipu/ledger")
        assert response.status_code == 200
        body = response.json()
        assert body["nodes"] == expected_nodes
        assert body["count"] == len(expected_nodes)
        assert body["khipu_root"] == (expected_nodes[-1]["digest"] if recorded else None)
        assert body["signing_available"] is (observation == "fresh")
        assert body["pub_fingerprint_sha256"] == fingerprint
        assert body["signing_state"]["freshness"] == {
            "absent": "UNKNOWN", "fresh": "FRESH", "stale": "STALE",
            "ephemeral": "FRESH", "mismatch": "FRESH"}[observation]
        assert body["signing_state"]["signing_ready"] is False
        assert body["signing_state"]["execution_authorized"] is False
        if owner is not None:
            assert owner._observation is captured
