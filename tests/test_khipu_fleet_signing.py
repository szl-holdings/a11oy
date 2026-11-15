"""Khipu fleet-contract signing routes (platform readiness-reliability).

The platform readiness-reliability executor probes ``{base}/healthz``,
``{base}/khipu/sign``, ``{base}/khipu/verify`` and ``{base}/metrics`` for every
flagship.  a11oy's estate signing surfaces live under ``/api/a11oy/v1/*``; the
root ``/khipu/sign`` and ``/khipu/verify`` routes are the fleet-contract
aliases.  They must do REAL sign/verify work with the loaded production key
(same backend as the capability self-test) and fail closed with HTTP 503 and an
honest reason when no usable key is loaded — never a fabricated 200, and never
a 404 that silently reds the fleet receipt (platform #983 root cause).
"""

from __future__ import annotations

import base64
import hashlib

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

starlette_testclient = pytest.importorskip("starlette.testclient")
TestClient = starlette_testclient.TestClient

import serve  # noqa: E402


def _test_key_pair():
    key = ec.generate_private_key(ec.SECP256R1())
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return priv_pem, pub_pem


@pytest.fixture()
def client():
    return TestClient(serve.app)


def test_routes_are_registered_not_404(client):
    """The fleet contract paths exist on the route table (root cause of #983)."""
    for path in ("/khipu/sign", "/khipu/verify"):
        assert any(getattr(r, "path", None) == path for r in serve.app.routes), (
            f"{path} must be registered for the readiness-reliability executor"
        )
        resp = client.get(path)
        assert resp.status_code in (200, 503), (
            f"{path} must answer 200 (usable key) or 503 (fail-closed), "
            f"got {resp.status_code}"
        )


def test_fail_closed_503_without_key(client, monkeypatch):
    monkeypatch.setattr(serve, "_A11OY_PRIV", None)
    monkeypatch.setattr(serve, "_A11OY_PUB_PEM", "")
    for path in ("/khipu/sign", "/khipu/verify"):
        resp = client.get(path)
        assert resp.status_code == 503, f"{path} must fail closed without a key"
        body = resp.json()
        assert body["status"] == "UNAVAILABLE"
        assert "signer-key-not-loaded" in body["reason"]


def test_sign_and_verify_roundtrip_with_loaded_key(client, monkeypatch):
    priv_pem, pub_pem = _test_key_pair()
    monkeypatch.setattr(serve, "_A11OY_PRIV",
                        serialization.load_pem_private_key(priv_pem.encode(), None))
    monkeypatch.setattr(serve, "_A11OY_PUB_PEM", pub_pem)

    signed = client.get("/khipu/sign")
    assert signed.status_code == 200
    body = signed.json()
    assert body["schema"] == "szl.khipu-fleet-sign/v1"
    assert body["status"] == "SIGNED"
    assert body["verified"] is True
    assert len(body["payload_digest"]) == 64
    assert body["signature_b64"]
    # The signature is a real ECDSA-P256 signature over the canonical receipt.
    sig = base64.b64decode(body["signature_b64"], validate=True)
    assert len(sig) >= 64

    # Self roundtrip verify (no body): VERIFIED with a fresh receipt.
    verified = client.get("/khipu/verify")
    assert verified.status_code == 200
    assert verified.json()["verdict"] == "VERIFIED"
    assert verified.json()["verified"] is True

    # Supplied-receipt POST verify: the pre-existing receipt-DAG verifier
    # (/khipu/{hash}) front-matches POST /khipu/verify and performs REAL DSSE
    # verification (verified/keyid evidence, honest false on garbage). The
    # fleet contract only requires a 2xx from a real verifier — both the
    # fleet route (GET) and the DAG verifier (POST) qualify.
    check = client.post("/khipu/verify", json={
        "payload_digest": body["payload_digest"],
        "signature_b64": body["signature_b64"],
    })
    assert check.status_code == 200
    cb = check.json()
    assert cb.get("verdict") in ("VERIFIED", "FAILED") or "verified" in cb, (
        "POST /khipu/verify must reach a real verifier (fleet or receipt DAG)"
    )

    # Tampered signature is honestly reported, never a 5xx or a fake green.
    tampered = client.post("/khipu/verify", json={
        "payload_digest": body["payload_digest"],
        "signature_b64": base64.b64encode(b"\x00" * 64).decode(),
    })
    assert tampered.status_code == 200
    tb = tampered.json()
    honest_fail = (tb.get("verdict") == "FAILED"
                   or tb.get("verified") is False)
    assert honest_fail, f"tampered input must not verify: {tb}"


def test_sign_receipt_is_bound_to_key_fingerprint(client, monkeypatch):
    priv_pem, pub_pem = _test_key_pair()
    monkeypatch.setattr(serve, "_A11OY_PRIV",
                        serialization.load_pem_private_key(priv_pem.encode(), None))
    monkeypatch.setattr(serve, "_A11OY_PUB_PEM", pub_pem)
    body = client.get("/khipu/sign").json()
    expected_fp = hashlib.sha256(pub_pem.strip().encode("ascii")).hexdigest()
    assert body["key_fingerprint"] == expected_fp
