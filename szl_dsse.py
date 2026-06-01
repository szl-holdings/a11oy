# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by Yachay (CTO) — Provenance Hardening: PLACEHOLDER -> REAL.
"""
szl_dsse — DSSE (in-toto/Dead-Simple-Signing-Envelope) signing + verification
for SZL Khipu receipts, backed by the SZLHOLDINGS **Cosign** keypair.

  Spec sources baked in:
    - DSSE protocol (secure-systems-lab/dsse) — PAE pre-authentication encoding:
        PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
        SIGNATURE       = Sign(PAE(UTF8(payloadType), SERIALIZED_BODY))
    - Sigstore Cosign (docs.sigstore.dev/cosign) — key-based blob signing:
        cosign sign-blob   --key cosign.key  <blob>   (ECDSA P-256 over SHA-256)
        cosign verify-blob --key cosign.pub  --signature <sig> <blob>

  KEY MODEL (honest):
    - The canonical signing key is the SZLHOLDINGS Cosign keypair generated with
      `cosign generate-key-pair` (imported from an OpenSSL P-256 EC key).
    - cosign.pub is published at szl-holdings/.github/cosign.pub (PUBLIC).
    - The PRIVATE key is delivered to each Space ONLY as a runtime secret
      env var `SZL_COSIGN_PRIVATE_PEM` (PKCS8 PEM). It is NEVER committed to a
      repo (HF or GitHub). If the secret is absent the module reports
      `signing_available=false` and emits a clearly-labelled UNSIGNED receipt —
      it NEVER fabricates a signature.
    - In-Space signing uses the Python `cryptography` lib over the DSSE PAE
      bytes. This is byte-for-byte verifiable by the `cosign` CLI (proven:
      cosign verify-blob accepts the cryptography-produced ECDSA-SHA256 sig,
      and Python verifies cosign-produced sigs — full round-trip equivalence).

  payloadType for Khipu receipts: "application/vnd.szl.khipu+json"
  keyid: "szlholdings-cosign"
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

KEYID = "szlholdings-cosign"
KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"
COSIGN_PUB_FINGERPRINT_ENV = "SZL_COSIGN_PUB_SHA256"  # optional pin

# The published public key (szl-holdings/.github/cosign.pub). Embedded so the
# /khipu/verify endpoint can verify WITHOUT a network call. This is PUBLIC data.
COSIGN_PUBLIC_PEM = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE7mrYWDnz8TvT7o4/65XGqYxo9OoV
vaB/grNuz+kVP1Xsaw0RokBKG0xT/XlV5Fz90AOwtgqC2yMBP0blK455gQ==
-----END PUBLIC KEY-----
"""

PUB_KEY_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"

# ---------------------------------------------------------------------------
# Canonical JSON  +  DSSE PAE
# ---------------------------------------------------------------------------

def canonical_json(obj: Any) -> bytes:
    """Deterministic canonical JSON: sorted keys, no extra whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1)."""
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


# ---------------------------------------------------------------------------
# Key loading (private = runtime secret; public = embedded)
# ---------------------------------------------------------------------------

def _load_private_key():
    """Load the Cosign EC private key from the SZL_COSIGN_PRIVATE_PEM secret.
    Returns None if absent/invalid — NEVER raises into the request path."""
    pem = os.environ.get("SZL_COSIGN_PRIVATE_PEM")
    if not pem:
        return None
    try:
        # Allow the secret to be provided base64-wrapped (HF UI friendliness)
        if "BEGIN" not in pem:
            pem = base64.b64decode(pem).decode("utf-8")
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        return load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception:
        return None


def _load_public_key():
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    return load_pem_public_key(COSIGN_PUBLIC_PEM.encode("utf-8"))


def signing_available() -> bool:
    return _load_private_key() is not None


def public_key_fingerprint() -> str:
    return hashlib.sha256(COSIGN_PUBLIC_PEM.strip().encode()).hexdigest()


# ---------------------------------------------------------------------------
# Sign / Verify
# ---------------------------------------------------------------------------

def sign_payload(payload_obj: Any, payload_type: str = KHIPU_PAYLOAD_TYPE) -> dict[str, Any]:
    """Produce a DSSE envelope over the canonical JSON of `payload_obj`.

    Returns the DSSE envelope dict:
      {payload(b64), payloadType, signatures:[{sig(b64), keyid}], ...meta}
    If no private key is present, returns an UNSIGNED envelope with an explicit
    honesty marker (NO fabricated signature)."""
    body = canonical_json(payload_obj)
    to_sign = pae(payload_type, body)
    env: dict[str, Any] = {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode("ascii"),
        "_dsse": "DSSEv1",
        "_pae_sha256": hashlib.sha256(to_sign).hexdigest(),
        "_signed_at": datetime.now(timezone.utc).isoformat(),
    }
    priv = _load_private_key()
    if priv is None:
        env["signatures"] = []
        env["honesty"] = ("UNSIGNED — SZL_COSIGN_PRIVATE_PEM secret not present in this "
                          "Space runtime; no signature fabricated.")
        env["signed"] = False
        return env
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": KEYID}]
    env["signed"] = True
    env["honesty"] = ("REAL — ECDSA-P256-SHA256 over DSSE PAE; verifiable by "
                      "`cosign verify-blob --key cosign.pub` and by the /khipu/verify endpoint.")
    env["verify_key_url"] = PUB_KEY_URL
    return env


def verify_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Verify a DSSE envelope's signature against the SZLHOLDINGS cosign.pub.

    Recomputes PAE over the embedded payload + payloadType and checks the
    ECDSA signature. Returns a structured verdict (never raises)."""
    out: dict[str, Any] = {"keyid_expected": KEYID, "pub_fingerprint_sha256": public_key_fingerprint(),
                           "verify_key_url": PUB_KEY_URL}
    try:
        payload_b64 = env.get("payload")
        payload_type = env.get("payloadType")
        sigs = env.get("signatures") or []
        if not payload_b64 or not payload_type:
            return {**out, "verified": False, "reason": "missing payload/payloadType"}
        if not sigs:
            return {**out, "verified": False, "reason": "no signatures (unsigned envelope)"}
        body = base64.b64decode(payload_b64)
        to_verify = pae(payload_type, body)
        out["pae_sha256"] = hashlib.sha256(to_verify).hexdigest()
        pub = _load_public_key()
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        results = []
        any_ok = False
        for s in sigs:
            sig_b64 = s.get("sig", "")
            keyid = s.get("keyid", "")
            try:
                sig = base64.b64decode(sig_b64)
                pub.verify(sig, to_verify, ec.ECDSA(hashes.SHA256()))
                results.append({"keyid": keyid, "verified": True})
                any_ok = True
            except InvalidSignature:
                results.append({"keyid": keyid, "verified": False, "reason": "signature mismatch"})
            except Exception as e:  # malformed sig
                results.append({"keyid": keyid, "verified": False, "reason": f"{type(e).__name__}"})
        # Optionally decode the payload back for the caller's convenience
        try:
            out["payload_decoded"] = json.loads(body)
        except Exception:
            pass
        return {**out, "verified": any_ok, "signatures": results,
                "payloadType": payload_type}
    except Exception as e:
        return {**out, "verified": False, "reason": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# Convenience: build a full signed Khipu receipt dict
# ---------------------------------------------------------------------------

def sign_khipu_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Return {receipt, dsse} where dsse is the DSSE envelope over the receipt."""
    env = sign_payload(receipt, KHIPU_PAYLOAD_TYPE)
    return {"receipt": receipt, "dsse": env}
