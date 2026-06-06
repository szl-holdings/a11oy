"""Inline DSSE signer for DINN receipts (Yachay 2026-06-01, PINN/DINN finish).

This mirrors the canonical root module ``szl_dsse.py`` byte-for-byte in its
signing contract so DINN receipts verify with the SAME key the rest of the mesh
uses:

    keyid:        szlholdings-cosign
    algorithm:    ECDSA P-256 over SHA-256 of the DSSE PAE preimage (DSSEv1)
    private key:  env SZL_COSIGN_PRIVATE_PEM (PKCS8 PEM; NEVER committed)
    public key:   szl-holdings/.github/cosign.pub (cosign verify-blob compatible)

It is inlined inside the sidecar package (rather than importing the root module)
so the 7-chakra sidecar stays dependency-light and self-contained. When the
``cryptography`` package or the secret is absent, this returns an UNSIGNED
envelope with an explicit honesty marker — NO signature is ever fabricated.

Honesty: a DINN's Lean obligation ships as a ``sorry`` placeholder; none is
claimed proven. The DSSE signature attests the *receipt bytes*, not the physics.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

KEYID = "szlholdings-cosign"
DINN_PAYLOAD_TYPE = "application/vnd.szl.dinn-receipt+json"
PUB_KEY_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"

# Published public key (szl-holdings/.github/cosign.pub) — PUBLIC, embedded so
# verification needs no network call. Identical to szl_dsse.COSIGN_PUBLIC_PEM.
COSIGN_PUBLIC_PEM = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE7mrYWDnz8TvT7o4/65XGqYxo9OoV
vaB/grNuz+kVP1Xsaw0RokBKG0xT/XlV5Fz90AOwtgqC2yMBP0blK455gQ==
-----END PUBLIC KEY-----
"""


def canonical_json(obj: Any) -> bytes:
    """Deterministic canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1)."""
    t = payload_type.encode("utf-8")
    return (
        b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
        + str(len(body)).encode() + b" " + body
    )


def _load_private_key():
    """Load the cosign EC private key from SZL_COSIGN_PRIVATE_PEM. None if absent."""
    pem = os.environ.get("SZL_COSIGN_PRIVATE_PEM")
    if not pem:
        return None
    try:
        if "BEGIN" not in pem:
            pem = base64.b64decode(pem).decode("utf-8")
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        return load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception:
        return None


def signing_available() -> bool:
    return _load_private_key() is not None


def public_key_fingerprint() -> str:
    return hashlib.sha256(COSIGN_PUBLIC_PEM.strip().encode()).hexdigest()


def sign_payload(payload_obj: Any, payload_type: str = DINN_PAYLOAD_TYPE) -> dict[str, Any]:
    """Produce a DSSE envelope over the canonical JSON of ``payload_obj``.

    Returns the DSSE envelope. If no private key is present, returns an UNSIGNED
    envelope with an explicit honesty marker (no fabricated signature).
    """
    body = canonical_json(payload_obj)
    to_sign = pae(payload_type, body)
    env: dict[str, Any] = {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode("ascii"),
        "_dsse": "DSSEv1",
        "_pae_sha256": hashlib.sha256(to_sign).hexdigest(),
        "_signed_at": datetime.now(timezone.utc).isoformat(),
        "verify_key_url": PUB_KEY_URL,
    }
    priv = _load_private_key()
    if priv is None:
        env["signatures"] = []
        env["signed"] = False
        env["honesty"] = (
            "UNSIGNED — SZL_COSIGN_PRIVATE_PEM secret not present in this Space "
            "runtime; no signature fabricated. Receipt bytes + PAE hash are still "
            "integrity-bound and verifiable once the key is provided."
        )
        return env
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": KEYID}]
    env["signed"] = True
    env["honesty"] = (
        "REAL — ECDSA-P256-SHA256 over DSSE PAE; verifiable by "
        "`cosign verify-blob --key cosign.pub` and the /api/amaru/khipu/verify endpoint."
    )
    return env


def verify_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Verify a DSSE envelope against the embedded cosign public key."""
    out: dict[str, Any] = {
        "keyid_expected": KEYID,
        "pub_fingerprint_sha256": public_key_fingerprint(),
        "verify_key_url": PUB_KEY_URL,
    }
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
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        pub = load_pem_public_key(COSIGN_PUBLIC_PEM.encode("utf-8"))
        any_ok = False
        for s in sigs:
            try:
                pub.verify(base64.b64decode(s.get("sig", "")), to_verify, ec.ECDSA(hashes.SHA256()))
                any_ok = any_ok or (s.get("keyid") == KEYID)
            except InvalidSignature:
                pass
        return {**out, "verified": any_ok, "keyid_match": any_ok}
    except Exception as e:  # pragma: no cover - defensive
        return {**out, "verified": False, "reason": f"{type(e).__name__}: {e}"}
