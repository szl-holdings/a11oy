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
import szl_dsse
from routers import series_a_control_plane
from cryptography.hazmat.primitives import serialization
from starlette.testclient import TestClient
from fastapi import FastAPI
import szl_governed_api


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
    assert szl_dsse.verify_envelope(envelope)["verified"] is True


def test_mutable_envelope_metadata_cannot_replace_signed_key_identity() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.key.substitution"})
    payload = json.loads(base64.b64decode(envelope["payload"]))
    envelope["verify_key_url"] = "https://attacker.invalid/key.pem"
    envelope["key_fingerprint_sha256"] = "0" * 64
    identity = payload["_signing_identity"]
    assert envelope["verify_key_url"] != identity["verify_key_url"]
    assert envelope["key_fingerprint_sha256"] != identity["key_fingerprint_sha256"]


def test_runtime_verifier_rejects_keyid_substitution() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.runtime.keyid.binding"})
    envelope["signatures"][0]["keyid"] = "0" * 64
    verdict = serve._a11oy_loop_verify(envelope)
    assert verdict["signature_valid"] is False
    assert verdict["keyid_expected"] == serve._A11OY_KEYID
    assert verdict["detail"] == "unexpected keyid for a11oy shared public key"


def test_runtime_verifier_retains_legacy_inimage_keyid() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.runtime.legacy.keyid"})
    envelope["signatures"][0]["keyid"] = "a11oy-inimage-ecdsa-p256"
    verdict = serve._a11oy_loop_verify(envelope)
    assert verdict["signature_valid"] is True
    assert verdict["keyid_expected"] == serve._A11OY_KEYID
    assert verdict["keyid_verified"] == "a11oy-inimage-ecdsa-p256"


def test_runtime_verifier_retains_legacy_raw_pem_keyid() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.runtime.legacy.pem.keyid"})
    envelope["signatures"][0]["keyid"] = serve._A11OY_LEGACY_RAW_PEM_KEYID

    verdict = serve._a11oy_loop_verify(envelope)

    assert verdict["signature_valid"] is True
    assert verdict["keyid_expected"] == serve._A11OY_KEYID
    assert verdict["keyid_verified"] == serve._A11OY_LEGACY_RAW_PEM_KEYID


@pytest.mark.parametrize("payload_type", [None, "", "   "])
def test_runtime_verifier_rejects_missing_payload_type(payload_type) -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.runtime.payload-type"})
    if payload_type is None:
        envelope.pop("payloadType")
    else:
        envelope["payloadType"] = payload_type

    verdict = serve._a11oy_loop_verify(envelope)

    assert verdict["signature_valid"] is False
    assert verdict["detail"] == (
        "DSSE envelope payloadType must be a non-empty string"
    )


def test_public_verifier_accepts_shared_runtime_signature() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.public.runtime.verify"})
    response = TestClient(serve.app).post(
        "/api/a11oy/v1/verify/receipt",
        json={"envelope": envelope},
    )
    assert response.status_code == 200
    signature = next(
        check
        for check in response.json()["checks"]
        if check["check"] == "signature"
    )
    assert signature["status"] == "VERIFIED"
    assert signature["keyid_expected"] == serve._A11OY_KEYID
    assert signature["verify_key_url"] == "/cosign.pub"


def test_public_verifier_rejects_tampered_runtime_payload() -> None:
    envelope = serve._a11oy_sign_receipt({"event": "test.public.runtime.tamper"})
    payload = bytearray(base64.b64decode(envelope["payload"]))
    payload[-1] ^= 1
    envelope["payload"] = base64.b64encode(payload).decode("ascii")
    response = TestClient(serve.app).post(
        "/api/a11oy/v1/verify/receipt",
        json={"envelope": envelope},
    )
    assert response.status_code == 200
    signature = next(
        check
        for check in response.json()["checks"]
        if check["check"] == "signature"
    )
    assert response.json()["verdict"] == "FAIL"
    assert signature["status"] == "MISMATCH"


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
    assert szl_dsse.active_public_key_pem() == public_pem
    assert serve._A11OY_KEYID == expected
    assert a11oy_dev1_endpoints._KEYID == expected[:16]
    assert service.signer.keyid == expected


def test_public_verifier_accepts_series_a_runtime_signature(tmp_path) -> None:
    service = series_a_control_plane.Service(
        str(tmp_path / "series-a.sqlite3")
    )
    envelope = service.signer.sign(
        {
            "schema": series_a_control_plane.SCHEMA_RECEIPT,
            "kind": "test.series-a.runtime.verify",
        }
    )

    response = TestClient(serve.app).post(
        "/api/a11oy/v1/verify/receipt",
        json={"envelope": envelope},
    )
    assert response.status_code == 200
    signature = next(
        check
        for check in response.json()["checks"]
        if check["check"] == "signature"
    )
    assert response.json()["verdict"] == "PARTIAL"
    assert signature["status"] == "VERIFIED"
    assert signature["keyid_expected"] == serve._A11OY_KEYID
    assert signature["verify_key_url"] == "/cosign.pub"


def test_every_live_public_key_alias_serves_the_shared_signer() -> None:
    client = TestClient(serve.app)
    fingerprints = set()
    for path in (
        "/cosign.pub",
        "/.well-known/cosign.pub",
        "/api/a11oy/cosign.pub",
        "/api/a11oy/v1/series-a/public-key",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert response.headers["cache-control"] == "no-store"
        public_key = serialization.load_pem_public_key(response.content)
        der = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        fingerprints.add(hashlib.sha256(der).hexdigest())
    assert len(fingerprints) == 1


def test_empty_injected_key_fails_closed_on_both_public_aliases() -> None:
    isolated = FastAPI()
    szl_governed_api.register(isolated, public_pem="")
    client = TestClient(isolated)
    for path in ("/cosign.pub", "/.well-known/cosign.pub"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert "unavailable" in response.text
