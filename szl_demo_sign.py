# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
"""
szl_demo_sign — DEMO-ONLY ECDSA-P256 signing for SZL Khipu receipts.

WHY THIS EXISTS (read before editing):
    The PRODUCTION cosign private key is founder-gated and is NEVER placed in the
    HF Space runtime (see szl_dsse.py). When it is absent, szl_dsse emits an honest
    UNSIGNED envelope and /verify shows "⚠ UNSIGNED". To let a buyer watch a REAL
    in-browser ECDSA-P256 verification SUCCEED — without ever exposing the
    production key — this module signs with a SEPARATE, clearly-labelled DEMO key.

HONESTY CONTRACT (doctrine, non-negotiable):
    - The demo key is a DISTINCT keypair from the production cosign key.
    - Every envelope it produces is stamped keyid="demo-signing-key" and carries a
      human-visible note: "signed with demo-signing-key — NOT the production
      founder-gated cosign key". A demo signature is NEVER labelled as production.
    - The DEMO PUBLIC key is committed here and served at /demo-cosign.pub. The
      DEMO PRIVATE key is loaded ONLY from the Space secret env var
      SZL_DEMO_SIGN_KEY (PKCS8 PEM, optionally base64-wrapped). It is never
      committed to git.
    - If the secret is absent or invalid this module is a no-op: it returns None and
      the caller keeps the honest DSSE_PLACEHOLDER / UNSIGNED behaviour. It NEVER
      fabricates a signature and NEVER raises into the infer path.

The envelope is byte-compatible with the /verify WebCrypto verifier: ECDSA-P256
over the DSSE PAE ("DSSEv1 " ...), exactly as szl_dsse produces for production.
"""
from __future__ import annotations

import base64
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# Reuse the EXACT PAE + canonical-JSON encoding the production path and the
# /verify JS already agree on, so a demo signature verifies through the same code.
import szl_dsse

DEMO_KEY_ID = "demo-signing-key"
DEMO_SIGN_KEY_ENV = "SZL_DEMO_SIGN_KEY"
DEMO_NOTE = ("signed with demo-signing-key — NOT the production founder-gated "
             "cosign key")

# Demo PUBLIC key (SubjectPublicKeyInfo / SPKI PEM). PUBLIC data — safe to commit.
# Served at /demo-cosign.pub so the /verify JS can fetch + import it. The matching
# PRIVATE key lives ONLY in the SZL_DEMO_SIGN_KEY Space secret (never committed).
DEMO_COSIGN_PUBLIC_PEM = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsy4Rh7qm/NtCPupIoCrs+YLJUwqg
3WyMBuzMeK+IqTY2X8DCRKTVFqdWktYF6IKBpA2ZiHU5Yl5STf4QqX97/A==
-----END PUBLIC KEY-----
"""


def _load_demo_private_key():
    """Load the demo EC private key from the SZL_DEMO_SIGN_KEY secret.

    Returns None (never raises) if the secret is absent or invalid — the caller
    then keeps the honest UNSIGNED / placeholder behaviour."""
    pem = os.environ.get(DEMO_SIGN_KEY_ENV)
    if not pem:
        return None
    try:
        if "BEGIN" not in pem:  # allow base64-wrapped secret (HF UI friendliness)
            pem = base64.b64decode(pem).decode("utf-8")
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        return load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as e:  # pragma: no cover - defensive
        print(f"[demo-sign] private key load failed (staying UNSIGNED): {e!r}",
              file=sys.stderr)
        return None


def demo_signing_available() -> bool:
    return _load_demo_private_key() is not None


def sign_payload_demo(payload_obj: Any,
                      payload_type: str = szl_dsse.KHIPU_PAYLOAD_TYPE
                      ) -> Optional[dict[str, Any]]:
    """Produce a DSSE envelope over `payload_obj` using the DEMO key.

    Returns the envelope dict (signed=True, keyid="demo-signing-key") or None if
    the demo secret is absent/invalid. NEVER fabricates a signature."""
    priv = _load_demo_private_key()
    if priv is None:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        body = szl_dsse.canonical_json(payload_obj)
        to_sign = szl_dsse.pae(payload_type, body)
        sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
        return {
            "payloadType": payload_type,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [{"sig": base64.b64encode(sig).decode("ascii"),
                            "keyid": DEMO_KEY_ID}],
            "signed": True,
            "_dsse": "DSSEv1",
            "_signed_at": datetime.now(timezone.utc).isoformat(),
            "key_id": DEMO_KEY_ID,
            "key_kind": "demo",
            "verify_key_url": "/demo-cosign.pub",
            "honesty": ("DEMO — real ECDSA-P256-SHA256 over the DSSE PAE, "
                        "verifiable in-browser against /demo-cosign.pub. " + DEMO_NOTE
                        + ". The production cosign key stays founder-gated and is "
                        "NEVER placed in this runtime."),
        }
    except Exception as e:  # pragma: no cover - defensive
        print(f"[demo-sign] sign failed (staying UNSIGNED): {e!r}", file=sys.stderr)
        return None


def demo_sign_receipt(receipt: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Demo-sign a Khipu receipt. Returns {receipt, dsse} or None.

    The returned receipt is stamped with key_id="demo-signing-key" and a
    human-visible signature_status so no surface can mistake it for a production
    signature. The dsse envelope is the cryptographic source of truth and is what
    /verify checks against /demo-cosign.pub. Returns None (caller keeps the honest
    placeholder) when the demo secret is absent."""
    env = sign_payload_demo(receipt, szl_dsse.KHIPU_PAYLOAD_TYPE)
    if env is None:
        return None
    out = dict(receipt)
    out["signature"] = env["signatures"][0]["sig"]
    out["key_id"] = DEMO_KEY_ID
    out["signature_status"] = ("DEMO-SIGNED [demo-signing-key] — " + DEMO_NOTE)
    return {"receipt": out, "dsse": env}
