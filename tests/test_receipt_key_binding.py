"""The receipt verification-key identity must be inside the DSSE payload."""

from __future__ import annotations

import base64
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("cryptography")

import serve


def test_ephemeral_key_identity_is_signed_not_envelope_only() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.key.binding"})
    payload = json.loads(base64.b64decode(envelope["payload"]))
    identity = payload["_signing_identity"]
    assert identity["keyid"] == envelope["signatures"][0]["keyid"]
    assert identity["verify_key_url"] == "/api/a11oy/cosign.pub"
    assert identity["key_scope"] == "PROCESS_BOOT_EPHEMERAL"
    assert identity["key_fingerprint_sha256"] == envelope["key_fingerprint_sha256"]


def test_mutable_envelope_metadata_cannot_replace_signed_key_identity() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.key.substitution"})
    payload = json.loads(base64.b64decode(envelope["payload"]))
    envelope["verify_key_url"] = "https://attacker.invalid/key.pem"
    envelope["key_fingerprint_sha256"] = "0" * 64
    identity = payload["_signing_identity"]
    assert envelope["verify_key_url"] != identity["verify_key_url"]
    assert envelope["key_fingerprint_sha256"] != identity["key_fingerprint_sha256"]
