# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
# Doctrine v11 LOCKED 749/14/163 · Λ Conjecture 1 · SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap
"""
tests/test_dsse_real_signing.py — proves the DSSE signer flips from
`signatures: []` (honest UNSIGNED) to a REAL ECDSA-P256-SHA256 signature
the moment the SZL_COSIGN_PRIVATE_KEY_PEM secret is present, and that the
resulting signature verifies against the matching public key.

HONESTY / SAFETY
  - No real org private key is ever required, embedded, or baked into CI.
  - The "present-secret" test GENERATES its own ephemeral P-256 key at runtime,
    sets the env var to it, signs, and verifies against THAT key's public half.
  - The real-org-secret round-trip is `skipif`-guarded: it runs ONLY if a real
    SZL_COSIGN_PRIVATE_KEY_PEM / SZL_COSIGN_PRIVATE_PEM is already in the env
    (e.g. a developer's local shell). It is never satisfied by CI defaults.
"""
from __future__ import annotations

import base64
import importlib
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

cryptography = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

import szl_dsse

_PRIV_ENV = "SZL_COSIGN_PRIVATE_KEY_PEM"
_LEGACY_ENV = "SZL_COSIGN_PRIVATE_PEM"


def _gen_ephemeral_keypair():
    """Generate a fresh, test-only ECDSA P-256 keypair (plain PKCS#8 PEM)."""
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no ambient secret leaks between tests unless a test sets one."""
    yield


def test_unsigned_fallback_when_secret_absent(monkeypatch):
    """No secret -> signatures:[] + honesty:UNSIGNED, never fabricated."""
    monkeypatch.delenv(_PRIV_ENV, raising=False)
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    importlib.reload(szl_dsse)
    env = szl_dsse.sign_payload({"hello": "world"})
    assert env["signatures"] == []
    assert env["signed"] is False
    assert "UNSIGNED" in env["honesty"]
    assert szl_dsse.signing_available() is False


def test_real_signature_with_ephemeral_key_verifies(monkeypatch):
    """Secret present (ephemeral test key) -> REAL signature that verifies
    against the matching public key via raw cryptography AND via the module's
    own active-runtime verify path."""
    priv_pem, pub_pem = _gen_ephemeral_keypair()
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    monkeypatch.setenv(_PRIV_ENV, priv_pem)
    importlib.reload(szl_dsse)

    assert szl_dsse.signing_available() is True
    env = szl_dsse.sign_payload({"hello": "world", "n": 42})

    # Flipped from [] to a real signature
    assert env["signed"] is True
    assert len(env["signatures"]) == 1
    sig_entry = env["signatures"][0]
    assert sig_entry["keyid"] == szl_dsse.active_keyid()
    assert "REAL" in env["honesty"]

    # 1) Verify the signature against the test public key with raw cryptography,
    #    reconstructing the exact DSSE PAE bytes the signer used.
    body = base64.b64decode(env["payload"])
    msg = szl_dsse.pae(env["payloadType"], body)
    pub = serialization.load_pem_public_key(pub_pem.encode("utf-8"))
    sig = base64.b64decode(sig_entry["sig"])
    pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))  # raises InvalidSignature on failure

    # 2) Module verify path derives the active public key from the same runtime
    #    secret, so no unrelated embedded key can invalidate a fresh receipt.
    assert szl_dsse.active_public_key_pem() == pub_pem
    verdict = szl_dsse.verify_envelope(env)
    assert verdict["verified"] is True


def test_tampered_payload_fails_verification(monkeypatch):
    """A tampered payload must NOT verify (signature binds the payload)."""
    priv_pem, pub_pem = _gen_ephemeral_keypair()
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    monkeypatch.setenv(_PRIV_ENV, priv_pem)
    importlib.reload(szl_dsse)

    env = szl_dsse.sign_payload({"amount": 1})
    body = szl_dsse.canonical_json({"amount": 1000000})  # tamper
    msg = szl_dsse.pae(env["payloadType"], body)
    pub = serialization.load_pem_public_key(pub_pem.encode("utf-8"))
    sig = base64.b64decode(env["signatures"][0]["sig"])
    with pytest.raises(InvalidSignature):
        pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))


def test_valid_signature_with_wrong_keyid_fails_verification(monkeypatch):
    """The key identifier is part of the verifier policy, not decoration."""
    priv_pem, pub_pem = _gen_ephemeral_keypair()
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    monkeypatch.setenv(_PRIV_ENV, priv_pem)
    importlib.reload(szl_dsse)
    monkeypatch.setattr(szl_dsse, "COSIGN_PUBLIC_PEM", pub_pem, raising=True)

    env = szl_dsse.sign_payload({"claim": "keyid-bound"})
    env["signatures"][0]["keyid"] = "different-key"

    verdict = szl_dsse.verify_envelope(env)
    assert verdict["verified"] is False
    assert verdict["signatures"][0]["reason"] == "unexpected or unavailable keyid"


def test_legacy_env_var_still_works(monkeypatch):
    """Backward-compat: the legacy SZL_COSIGN_PRIVATE_PEM name still signs."""
    priv_pem, _pub_pem = _gen_ephemeral_keypair()
    monkeypatch.delenv(_PRIV_ENV, raising=False)
    monkeypatch.setenv(_LEGACY_ENV, priv_pem)
    importlib.reload(szl_dsse)
    env = szl_dsse.sign_payload({"compat": True})
    assert env["signed"] is True
    assert len(env["signatures"]) == 1


def test_non_p256_private_key_fails_closed(monkeypatch):
    """A configured key of the wrong algorithm never produces a signature."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    monkeypatch.setenv(_PRIV_ENV, private_pem)
    importlib.reload(szl_dsse)

    assert szl_dsse.signing_available() is False
    envelope = szl_dsse.sign_payload({"wrong": "algorithm"})
    assert envelope["signed"] is False
    assert envelope["signatures"] == []


def test_retained_public_key_verifies_after_rotation(monkeypatch):
    """A receipt selects its retained public key after the active key rotates."""
    old_private_pem, old_public_pem = _gen_ephemeral_keypair()
    new_private_pem, _new_public_pem = _gen_ephemeral_keypair()
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    monkeypatch.setenv(_PRIV_ENV, old_private_pem)
    monkeypatch.delenv(szl_dsse.VERIFY_KEY_BUNDLE_ENV, raising=False)
    importlib.reload(szl_dsse)

    old_envelope = szl_dsse.sign_payload({"rotation": "before"})
    old_keyid = old_envelope["signatures"][0]["keyid"]
    assert old_keyid == szl_dsse.active_keyid()

    monkeypatch.setenv(_PRIV_ENV, new_private_pem)
    monkeypatch.setenv(szl_dsse.VERIFY_KEY_BUNDLE_ENV, old_public_pem)
    importlib.reload(szl_dsse)

    assert szl_dsse.active_keyid() != old_keyid
    verdict = szl_dsse.verify_envelope(old_envelope)
    assert verdict["verified"] is True
    assert verdict["pub_fingerprint_sha256"] == old_keyid
    assert verdict["signatures"][0]["key_source"] == "operator-retained"

    # Legacy envelopes used one constant keyid. They remain verifiable by trying
    # the bounded retained ring rather than silently binding to the new signer.
    old_envelope["signatures"][0]["keyid"] = szl_dsse.LEGACY_KEYID
    legacy_verdict = szl_dsse.verify_envelope(old_envelope)
    assert legacy_verdict["verified"] is True
    assert legacy_verdict["pub_fingerprint_sha256"] == old_keyid


@pytest.mark.skipif(
    not (os.environ.get(_PRIV_ENV) or os.environ.get(_LEGACY_ENV)),
    reason="real cosign private key not present in env; skip real-key round-trip "
           "(the private key is never baked into CI)",
)
def test_real_org_key_roundtrip_if_present():
    """OPT-IN: if a real org private key is in the env, the produced signature
    must verify against the module's embedded (published) public key."""
    importlib.reload(szl_dsse)
    assert szl_dsse.signing_available() is True
    env = szl_dsse.sign_payload({"real": "org-key-roundtrip"})
    assert env["signed"] is True
    verdict = szl_dsse.verify_envelope(env)
    assert verdict["verified"] is True, verdict


@pytest.fixture(autouse=True)
def _restore_module():
    yield
    # Restore a clean module state for any downstream tests
    for _n in (*szl_dsse.PRIVATE_KEY_ENV_VARS,
               szl_dsse.VERIFY_KEY_BUNDLE_ENV,
               szl_dsse.VERIFY_KEY_PATHS_ENV):
        os.environ.pop(_n, None)
    importlib.reload(szl_dsse)
