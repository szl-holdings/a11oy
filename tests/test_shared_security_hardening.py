# SPDX-License-Identifier: Apache-2.0
"""Regressions for shared credential and receipt hardening."""
from __future__ import annotations

import base64
import hashlib
import json
import time

import szl_connectors.governance as governance
import szl_connectors.oauth as oauth
import szl_dsse
from szl_connectors.base import cred_fingerprint


def test_nested_secrets_are_refused_and_scrubbed(monkeypatch):
    monkeypatch.setattr(governance, "_now", lambda: "2026-01-01T00:00:00+00:00")
    monkeypatch.setattr(governance, "_dsse_sign", lambda body: {"body": body})
    allowed, _, receipt, _, detail = governance.gate_write(
        connector_id="test",
        connected=True,
        action={
            "method": "write",
            "payload": [{"client_secret": "raw-action-secret", "ok": True}],
        },
    )
    assert not allowed
    assert "raw secret" in detail
    assert "raw-action-secret" not in json.dumps(receipt)
    assert receipt["body"]["action"]["payload"] == [{"ok": True}]


def test_fingerprints_are_validated_and_receipt_hash_is_compatible(monkeypatch):
    monkeypatch.setattr(governance, "_now", lambda: "2026-01-01T00:00:00+00:00")
    monkeypatch.setattr(governance, "_dsse_sign", lambda body: {"body": body})
    fingerprint = cred_fingerprint("runtime-only-secret")
    receipt = governance.receipt_for_write(
        connector_id="test",
        action={"method": "write", "object": "record"},
        lambda_value=0.9,
        cred_fingerprints={"password": fingerprint, "token": "raw-secret"},
        result_summary={"nested": {"authorization": "Bearer secret", "ok": True}},
    )
    assert receipt["body"]["credential_fingerprints"] == {
        "password": fingerprint,
        "token": "invalid-fingerprint",
    }
    assert receipt["body"]["result"] == {"nested": {"ok": True}}
    unhashed = dict(receipt["body"])
    unhashed.pop("receipt_hash")
    expected = hashlib.sha256(
        json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert receipt["receipt_hash"] == f"sha256:{expected}"


def test_credentials_and_oauth_state_use_pbkdf2(monkeypatch):
    monkeypatch.setenv("SZL_FINGERPRINT_PEPPER", "test-pepper")
    fingerprint = cred_fingerprint("password123")
    assert fingerprint.startswith("pbkdf2-sha256:")
    assert fingerprint.removeprefix("pbkdf2-sha256:") != hashlib.sha256(
        b"password123"
    ).hexdigest()[:32]

    monkeypatch.setenv("SZL_OAUTH_STATE_SECRET", "state-secret")
    oauth._STATE_KEY_CACHE.clear()
    expected_key = hashlib.pbkdf2_hmac(
        "sha256",
        b"state-secret",
        oauth._STATE_KDF_SALT,
        oauth._STATE_KDF_ITERATIONS,
    )
    assert oauth._state_secret() == expected_key
    state = oauth.sign_state("salesforce", "nonce", ts=int(time.time()))
    assert oauth.verify_state(state, "salesforce")[0] is True


def test_dsse_content_address_remains_byte_compatible(monkeypatch):
    for name in szl_dsse.PRIVATE_KEY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    envelope = szl_dsse.sign_payload({"scope": "public", "unicode": "Perú"})
    body = base64.b64decode(envelope["payload"])
    expected = hashlib.sha256(
        szl_dsse.pae(envelope["payloadType"], body)
    ).hexdigest()
    assert envelope["_pae_sha256"] == expected
