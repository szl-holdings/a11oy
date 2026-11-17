#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fleet status reads consume retained observations; POSTs retain real crypto."""

import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import serve
from szl_signing_state import SigningState

PATHS = ("/khipu/sign", "/khipu/verify")


@pytest.fixture()
def runtime(monkeypatch):
    now = [100.0]
    owner = SigningState(clock=lambda: now[0])
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    fingerprint = hashlib.sha256(public.strip().encode("ascii")).hexdigest()
    monkeypatch.setattr(serve, "_A11OY_PRIV", key)
    monkeypatch.setattr(serve, "_A11OY_PUB_PEM", public)
    monkeypatch.setattr(serve, "_A11OY_KEYID", fingerprint)
    monkeypatch.setattr(serve, "_A11OY_KEY_SOURCE", "ephemeral")
    monkeypatch.setattr(serve, "_A11OY_KEY_ERR", None)
    monkeypatch.setattr(serve, "_A11OY_SIGNER_CONFIGURED", False)
    monkeypatch.setattr(serve, "_A11OY_SIGNING_STATE", owner)
    monkeypatch.setitem(serve.app.state._state, "szl_signing_state", owner)
    monkeypatch.setattr(
        serve.app.state, "szl_series_a_service",
        SimpleNamespace(runtime_boot_id="fleet-test-boot"), raising=False
    )
    return SimpleNamespace(
        owner=owner, now=now, key=key, public=public, fingerprint=fingerprint,
        client=TestClient(serve.app)
    )


def observe(runtime):
    serve._refresh_a11oy_signing_state()
    serve._observe_a11oy_signing_capability()
    assert runtime.owner.read()["signing_ready"] is True


@pytest.mark.parametrize("path", PATHS)
def test_no_observation_or_only_metadata_fails_closed(runtime, path):
    for phase in ("unobserved", "metadata-only"):
        if phase == "metadata-only":
            serve._refresh_a11oy_signing_state()
        response = runtime.client.get(path)
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "UNAVAILABLE"
        assert body["receipt_minted"] is False
        assert body["signing_state"]["signing_ready"] is False
        assert body["receipt_verification"] == "NOT_EVALUATED"


@pytest.mark.parametrize("method", ("GET", "HEAD"))
@pytest.mark.parametrize("path", PATHS)
def test_fresh_observed_capability_is_a_passive_read(runtime, monkeypatch, method, path):
    observe(runtime)
    observation = runtime.owner._observation
    evidence = runtime.owner._evidence
    forbidden = Mock(side_effect=AssertionError("fleet read attempted signing or refresh"))
    for name in (
        "_khipu_fleet_signer_ready", "_khipu_fleet_receipt",
        "_refresh_a11oy_signing_state", "_observe_a11oy_signing_capability",
        "_a11oy_sign_receipt",
    ):
        monkeypatch.setattr(serve, name, forbidden)
    monkeypatch.setattr(serve, "_A11OY_PRIV", SimpleNamespace(
        sign=forbidden, public_key=forbidden
    ))
    for _ in range(2):
        response = runtime.client.request(method, path)
        assert response.status_code == 200
        assert "no-store" in response.headers["cache-control"]
        if method == "HEAD":
            assert response.content == b""
        else:
            body = response.json()
            assert body["status"] == "READY"
            assert body["scope"] == "PROCESS_LOCAL_SIGNING_CAPABILITY"
            assert body["receipt_minted"] is False
            assert body["sign_on_read"] is False
            assert body["receipt_verification"] == "NOT_EVALUATED"
            assert not {"signature_b64", "payload_digest", "verified", "verdict"} & body.keys()
            assert body["signing_state"]["signing_ready"] is True
            assert body["signing_state"]["public_key_fingerprint"] == runtime.fingerprint
            assert body["signing_state"]["execution_authorized"] is False
    forbidden.assert_not_called()
    assert runtime.owner._observation is observation
    assert runtime.owner._evidence is evidence


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("loss", ("stale", "rotation", "invalidated", "boot"))
def test_stale_changed_or_lost_evidence_cannot_stay_ready(runtime, path, loss):
    observe(runtime)
    if loss == "stale":
        runtime.now[0] = 160.0
    elif loss == "invalidated":
        runtime.owner.invalidate()
    elif loss == "rotation":
        monkey = ec.generate_private_key(ec.SECP256R1())
        serve._A11OY_PRIV = monkey
        serve._refresh_a11oy_signing_state()
    else:
        serve.app.state.szl_series_a_service.runtime_boot_id = "different-boot"
        serve._refresh_a11oy_signing_state()
    response = runtime.client.get(path)
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["signing_state"]["signing_ready"] is False
    assert body["receipt_minted"] is False


def test_post_sign_still_requires_operator_identity(runtime, monkeypatch):
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "fleet-test-operator-only")
    forbidden = Mock(side_effect=AssertionError("anonymous request reached signer"))
    monkeypatch.setattr(serve, "_A11OY_PRIV", SimpleNamespace(sign=forbidden))
    response = runtime.client.post("/khipu/sign", json={"payload": {"test": True}})
    assert response.status_code == 401
    assert response.json()["status"] == "BLOCKED"
    forbidden.assert_not_called()


def test_authenticated_post_sign_keeps_existing_owner_and_real_crypto(runtime, monkeypatch):
    routes = [
        route for route in serve.app.routes
        if getattr(route, "path", None) == "/khipu/sign"
        and "POST" in getattr(route, "methods", set())
    ]
    assert routes[0].endpoint.__name__ == "warhacker_sign"
    dsse = serve._wh_aliases._dsse
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "fleet-test-operator-only")
    monkeypatch.setattr(dsse, "_load_private_key", lambda: runtime.key)
    monkeypatch.setattr(dsse, "_RUNTIME_PUBLIC_KEYS", {})
    monkeypatch.setattr(dsse, "_ACTIVE_RUNTIME_KEYID", None)
    response = runtime.client.post(
        "/khipu/sign",
        headers={"Authorization": "Bearer fleet-test-operator-only"},
        json={"payload": {"scope": "TEST_ONLY", "value": 1}},
    )
    assert response.status_code == 200
    envelope = response.json()["envelope"]
    assert envelope["signed"] is True
    payload = base64.b64decode(envelope["payload"], validate=True)
    signature = base64.b64decode(envelope["signatures"][0]["sig"], validate=True)
    runtime.key.public_key().verify(
        signature, serve._a11oy_pae(envelope["payloadType"], payload),
        ec.ECDSA(hashes.SHA256())
    )
    assert json.loads(payload)["payload"] == {"scope": "TEST_ONLY", "value": 1}


def test_post_verifier_rejects_tampering_without_signing(runtime, monkeypatch):
    payload = b'{"scope":"TEST_ONLY","value":1}'
    payload_type = "application/vnd.szl.khipu+json"
    signature = runtime.key.sign(
        serve._a11oy_pae(payload_type, payload), ec.ECDSA(hashes.SHA256())
    )
    envelope = {
        "payloadType": payload_type,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [{"keyid": runtime.fingerprint,
                        "sig": base64.b64encode(signature).decode("ascii")}],
    }
    forbidden = Mock(side_effect=AssertionError("verification attempted signing"))
    monkeypatch.setattr(serve, "_A11OY_PRIV", SimpleNamespace(sign=forbidden))
    response = runtime.client.post(
        "/khipu/verify", json={"envelope": envelope, "pubkey_pem": runtime.public}
    )
    assert response.status_code == 200
    assert response.json()["verified"] is True
    altered = json.loads(json.dumps(envelope))
    altered["payload"] = base64.b64encode(b'{"scope":"TEST_ONLY","value":2}').decode("ascii")
    response = runtime.client.post(
        "/khipu/verify", json={"envelope": altered, "pubkey_pem": runtime.public}
    )
    assert response.status_code == 200
    assert response.json()["verified"] is False
    forbidden.assert_not_called()
