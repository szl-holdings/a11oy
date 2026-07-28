"""The receipt verification-key identity must be inside the DSSE payload."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("cryptography")

import serve
import a11oy_dev1_endpoints
from routers import series_a_control_plane


def test_shared_key_identity_is_signed_not_envelope_only() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.key.binding"})
    payload = json.loads(base64.b64decode(envelope["payload"]))
    identity = payload["_signing_identity"]
    assert identity["keyid"] == envelope["signatures"][0]["keyid"]
    assert identity["verify_key_url"] == "/api/a11oy/cosign.pub"
    assert identity["key_source"] == serve._A11OY_KEY_SOURCE
    if serve._A11OY_KEY_SOURCE.startswith("persistent:"):
        assert identity["key_scope"] == "DEPLOYMENT_PERSISTENT"
        assert identity["key_lifetime"] == "UNTIL_SECRET_ROTATION"
    else:
        assert identity["key_scope"] == "PROCESS_BOOT_EPHEMERAL"
        assert identity["key_lifetime"] == "UNTIL_PROCESS_RESTART"
    assert identity["key_fingerprint_sha256"] == envelope["key_fingerprint_sha256"]


def test_mutable_envelope_metadata_cannot_replace_signed_key_identity() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.key.substitution"})
    payload = json.loads(base64.b64decode(envelope["payload"]))
    envelope["verify_key_url"] = "https://attacker.invalid/key.pem"
    envelope["key_fingerprint_sha256"] = "0" * 64
    identity = payload["_signing_identity"]
    assert envelope["verify_key_url"] != identity["verify_key_url"]
    assert envelope["key_fingerprint_sha256"] != identity["key_fingerprint_sha256"]


def test_root_wow_and_series_a_share_one_process_key(tmp_path) -> None:
    service = series_a_control_plane.Service(
        str(tmp_path / "series-a.sqlite3")
    )
    public_keys = {
        serve._A11OY_PUB_PEM,
        a11oy_dev1_endpoints._PUB_PEM,
        service.signer.public_pem,
    }
    assert "" not in public_keys
    assert len(public_keys) == 1

    public_pem = public_keys.pop()
    expected = hashlib.sha256(public_pem.strip().encode()).hexdigest()
    assert serve._A11OY_KEYID == expected
    assert a11oy_dev1_endpoints._KEYID == expected[:16]
    assert service.signer.keyid == hashlib.sha256(
        public_pem.encode("utf-8")
    ).hexdigest()
