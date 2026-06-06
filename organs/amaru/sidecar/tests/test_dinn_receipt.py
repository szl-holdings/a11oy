"""Tests for the DINN reasoner + DSSE-signed receipt endpoints (ADDITIVE).

Yachay 2026-06-01, PINN/DINN finish. These cover the wiring fixes:
  - DINN monitor reports canonical Doctrine v11 numbers (not stale v9)
  - /chakra/dinn/v1/healthz reports the cosign keyid + signing availability
  - /chakra/dinn/receipt emits final_state_hash + ledger_digest + stop_reason
  - the DSSE signed path round-trips (real ECDSA-P256) when a key is present
  - honest UNSIGNED fallback when no key is present (no fabricated signature)
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from amaru.app import app
from amaru import dinn_dsse

client = TestClient(app)


def test_dinn_monitor_reports_v11():
    m = client.get("/chakra/dinn").json()
    assert m["doctrine_version"].startswith("v11")
    assert "749" in m["doctrine_version"]
    assert "163" in m["doctrine_version"]
    assert m["lambda_status"] == "Conjecture 1 (NOT a theorem)"
    # Canonical v11 SLSA claim (matches /api/amaru/v1/honest and the whole mesh):
    # L1 honest (cosign-signed; public Sigstore/Rekor). L2 attestation roadmap (Wire D) — not yet earned. NEVER L3.
    assert m["slsa"].startswith("L1 honest")
    assert "L3 not claimed" in m["slsa"]


def test_dinn_healthz():
    h = client.get("/chakra/dinn/v1/healthz").json()
    assert h["status"] == "ok"
    assert h["keyid"] == "szlholdings-cosign"
    assert h["doctrine_version"] == "v11"
    assert isinstance(h["signing_available"], bool)


def test_dinn_receipt_shape():
    r = client.get("/chakra/dinn/receipt?envelope=pytest-env").json()
    assert "final_state_hash" in r and len(r["final_state_hash"]) == 64
    assert "ledger_digest" in r and len(r["ledger_digest"]) == 64
    assert r["stop_reason"] in ("convergence", "max_iter")
    assert "dsse_receipt" in r
    env = r["dsse_receipt"]
    assert env["payloadType"] == "application/vnd.szl.dinn-receipt+json"
    assert "_pae_sha256" in env
    # honest disclaimer must be present and not claim a proof
    assert "sorry" in env["honesty"].lower() or "unsigned" in env["honesty"].lower()


def test_dinn_receipt_unsigned_when_no_key(monkeypatch):
    monkeypatch.delenv("SZL_COSIGN_PRIVATE_PEM", raising=False)
    env = dinn_dsse.sign_payload({"kind": "dinn-receipt", "residual_loss": 0.01})
    assert env["signed"] is False
    assert env["signatures"] == []
    assert "UNSIGNED" in env["honesty"]


def test_dinn_receipt_signed_round_trip(monkeypatch):
    # Generate a real P-256 key to exercise the signed path + verification.
    # The signer honestly degrades to UNSIGNED when `cryptography` is absent
    # (see dinn_dsse.signing_available); skip the SIGNED-path assertions then.
    import pytest as _pytest
    _pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setenv("SZL_COSIGN_PRIVATE_PEM", priv_pem)
    monkeypatch.setattr(dinn_dsse, "COSIGN_PUBLIC_PEM", pub_pem)

    env = dinn_dsse.sign_payload({"kind": "dinn-receipt", "residual_loss": 0.01})
    assert env["signed"] is True
    assert env["signatures"][0]["keyid"] == "szlholdings-cosign"
    verdict = dinn_dsse.verify_envelope(env)
    assert verdict["verified"] is True
    assert verdict["keyid_match"] is True
