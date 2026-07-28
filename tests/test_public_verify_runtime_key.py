"""The public verifier must use the exact runtime key served by A11oy."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_dsse
import szl_public_verify


def _runtime_fixture():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    keyid = hashlib.sha256(public_pem.strip().encode("ascii")).hexdigest()
    payload_type = "application/vnd.szl.receipt+json"
    body = json.dumps(
        {"event": "test.runtime.verifier"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    pae = szl_dsse.pae(payload_type, body)
    signature = private_key.sign(pae, ec.ECDSA(hashes.SHA256()))
    envelope = {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{
            "keyid": keyid,
            "sig": base64.b64encode(signature).decode("ascii"),
        }],
    }

    def verify(candidate):
        entry = (candidate.get("signatures") or [{}])[0]
        if entry.get("keyid") != keyid:
            return {
                "signature_valid": False,
                "keyid_expected": keyid,
                "detail": "unexpected keyid for a11oy shared public key",
            }
        try:
            candidate_body = base64.b64decode(candidate["payload"])
            candidate_pae = szl_dsse.pae(
                candidate["payloadType"],
                candidate_body,
            )
            private_key.public_key().verify(
                base64.b64decode(entry["sig"]),
                candidate_pae,
                ec.ECDSA(hashes.SHA256()),
            )
        except Exception:
            return {
                "signature_valid": False,
                "keyid_expected": keyid,
                "detail": "signature check failed",
            }
        return {
            "signature_valid": True,
            "keyid_expected": keyid,
            "detail": "verified against runtime key",
        }

    return envelope, keyid, verify


def test_fingerprint_keyid_uses_runtime_verifier_before_static_key(
    monkeypatch,
) -> None:
    envelope, keyid, runtime_verify = _runtime_fixture()
    monkeypatch.setattr(
        szl_dsse,
        "verify_envelope",
        lambda _env: {
            "verified": False,
            "keyid_expected": "static-key",
            "reason": "unexpected keyid",
        },
    )

    result = szl_public_verify._check_signature(
        envelope,
        runtime_verify_fn=runtime_verify,
    )

    assert result["status"] == szl_public_verify.VERIFIED
    assert result["keyid_expected"] == keyid
    assert result["verify_key_url"] == "/cosign.pub"


def test_runtime_verifier_keeps_keyid_bound(monkeypatch) -> None:
    envelope, keyid, runtime_verify = _runtime_fixture()
    envelope["signatures"][0]["keyid"] = "0" * 64
    monkeypatch.setattr(
        szl_dsse,
        "verify_envelope",
        lambda _env: {
            "verified": False,
            "keyid_expected": "static-key",
            "reason": "unexpected keyid",
            "signatures": [{
                "keyid": "0" * 64,
                "verified": False,
                "reason": "unexpected keyid",
            }],
        },
    )

    result = szl_public_verify._check_signature(
        envelope,
        runtime_verify_fn=runtime_verify,
    )

    assert result["status"] == szl_public_verify.MISMATCH
    assert result["runtime_detail"] == (
        "unexpected keyid for a11oy shared public key"
    )
    assert keyid != envelope["signatures"][0]["keyid"]


@pytest.mark.parametrize("payload_type", [None, "", "   "])
def test_public_verifier_rejects_missing_payload_type(
    monkeypatch,
    payload_type,
) -> None:
    envelope, _, _ = _runtime_fixture()
    if payload_type is None:
        envelope.pop("payloadType")
    else:
        envelope["payloadType"] = payload_type
    runtime_called = False

    def fail_open_runtime_verifier(_candidate):
        nonlocal runtime_called
        runtime_called = True
        return {"signature_valid": True}

    monkeypatch.setattr(
        szl_dsse,
        "verify_envelope",
        lambda _env: {"verified": True},
    )

    result = szl_public_verify._check_signature(
        envelope,
        runtime_verify_fn=fail_open_runtime_verifier,
    )

    assert result["status"] == szl_public_verify.MISMATCH
    assert result["detail"] == (
        "DSSE envelope payloadType must be a non-empty string"
    )
    assert runtime_called is False


def test_historical_key_falls_back_to_static_verifier(monkeypatch) -> None:
    envelope, _, runtime_verify = _runtime_fixture()
    monkeypatch.setattr(
        szl_dsse,
        "verify_envelope",
        lambda _env: {
            "verified": True,
            "keyid_expected": "historical-key",
            "reason": None,
            "signatures": [{
                "keyid": "historical-key",
                "verified": True,
            }],
        },
    )

    envelope["signatures"][0]["keyid"] = "historical-key"
    result = szl_public_verify._check_signature(
        envelope,
        runtime_verify_fn=runtime_verify,
    )

    assert result["status"] == szl_public_verify.VERIFIED
    assert result["keyid_expected"] == "historical-key"
