# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent.
"""
szl_warhacker_aliases — ADDITIVE top-level alias routes for Warhacker readiness.

Why this module exists
-----------------------
The flagship Spaces serve their real health + DSSE signing endpoints under the
`/api/<space>/...` prefix (e.g. `/api/a11oy/healthz`, `/api/a11oy/khipu/sign`).
The Warhacker demo surface + investor verification scripts hit the *short*,
top-level paths:

    GET  /healthz
    GET  /api/<space>/v3/doctrine
    GET  /khipu/pubkey
    POST /khipu/sign
    POST /khipu/verify
    GET  /wires/D

This module registers those short paths so they resolve LOCALLY and win over the
SPA history catch-all (`/{full_path:path}`). It is purely ADDITIVE: it adds new
routes and never deletes or overwrites an existing one. It MUST be registered
BEFORE the SPA catch-all (caller responsibility).

Doctrine v11 numbers are returned VERBATIM:
    749 declarations · 14 unique axioms · 163 sorries
    (putnam 51 · baseline 112)  Λ = Conjecture 1 (NOT a theorem)  SLSA = L1 honest.

Signing is delegated to the already-shipped, already-LIVE szl_dsse module — the
same real ECDSA-P256 cosign keypair used by szl_provenance. No new key material,
no fabrication. If szl_dsse is unavailable the endpoints return an honest 503.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

try:
    import szl_dsse as _dsse  # the LIVE signing module (Wire D)
except Exception:  # pragma: no cover
    _dsse = None

DOCTRINE_VERSION = "v11"
DOCTRINE_LOCKED_AT = "c7c0ba17"
YUYAY_V3_REPLAY_HASH = "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5"
SIBLINGS = ["a11oy", "amaru", "sentra", "rosie", "killinchu"]

# Canonical Doctrine v11 numbers — VERBATIM, never to drift.
NUMBERS = {
    "declarations": 749,
    "axioms": 14,
    "sorries": 163,
    "putnam_sorries": 51,
    "baseline_sorries": 112,
}


def _doctrine_payload(space: str, build_sha: str) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": space,
        "version": "3.0.0",
        "doctrine": DOCTRINE_VERSION,
        "doctrine_locked_at": DOCTRINE_LOCKED_AT,
        "numbers": dict(NUMBERS),
        "yuyay_axes": 13,
        "yuyay_v3_replay_hash": YUYAY_V3_REPLAY_HASH,
        "slsa": "L1 (honest; L2 in roadmap via Wire D)",
        "lambda_status": "Conjecture 1 (NOT a theorem)",
        "build_sha": build_sha,
        "sibling_organs": list(SIBLINGS),
    }


def register(app, space: str, build_sha: str = "unknown") -> dict[str, Any]:
    """Register top-level Warhacker alias routes. ADDITIVE. Returns a status dict.

    Caller MUST invoke this BEFORE the SPA catch-all is defined so these explicit
    routes win the FastAPI ordered route match.
    """
    registered: list[str] = []

    # ---- /healthz : Doctrine v11 health JSON (short alias) ------------------
    @app.get("/healthz")
    async def warhacker_healthz() -> JSONResponse:  # noqa: ANN202
        return JSONResponse(_doctrine_payload(space, build_sha))

    registered.append("/healthz")

    # ---- /api/<space>/v3/doctrine : canonical doctrine endpoint -------------
    @app.get(f"/api/{space}/v3/doctrine")
    async def warhacker_doctrine() -> JSONResponse:  # noqa: ANN202
        return JSONResponse(_doctrine_payload(space, build_sha))

    registered.append(f"/api/{space}/v3/doctrine")

    # ---- /khipu/pubkey : PEM public key + fingerprint -----------------------
    @app.get("/khipu/pubkey")
    async def warhacker_pubkey():  # noqa: ANN202
        if _dsse is None:
            return JSONResponse(
                {"error": "szl_dsse unavailable", "unblock": "ensure szl_dsse.py is vendored in this Space"},
                status_code=503,
            )
        pem = _dsse.COSIGN_PUBLIC_PEM.strip()
        return JSONResponse({
            "pem": pem,
            "fingerprint_sha256": _dsse.public_key_fingerprint(),
            "keyid": getattr(_dsse, "KEYID", "szlholdings-cosign"),
            "curve": "secp256r1 (P-256)",
            "verify_key_url": getattr(_dsse, "PUB_KEY_URL", ""),
            "signing_available": _dsse.signing_available(),
        })

    registered.append("/khipu/pubkey")

    # also serve the raw PEM at /khipu/pubkey.pem for cosign verify-blob users
    @app.get("/khipu/pubkey.pem")
    async def warhacker_pubkey_pem():  # noqa: ANN202
        if _dsse is None:
            return PlainTextResponse("szl_dsse unavailable", status_code=503)
        return PlainTextResponse(_dsse.COSIGN_PUBLIC_PEM.strip() + "\n", media_type="application/x-pem-file")

    registered.append("/khipu/pubkey.pem")

    # ---- POST /khipu/sign : real DSSE envelope over arbitrary payload -------
    @app.post("/khipu/sign")
    async def warhacker_sign(request: Request) -> JSONResponse:  # noqa: ANN202
        if _dsse is None:
            return JSONResponse(
                {"error": "szl_dsse unavailable", "unblock": "vendor szl_dsse.py + set SZL_COSIGN_PRIVATE_PEM secret"},
                status_code=503,
            )
        try:
            body = await request.json()
        except Exception:
            body = {}
        payload = body.get("payload", body)
        receipt = {
            "space": space,
            "doctrine": DOCTRINE_VERSION,
            "doctrine_numbers": dict(NUMBERS),
            "payload": payload,
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }
        env = _dsse.sign_payload(receipt, getattr(_dsse, "KHIPU_PAYLOAD_TYPE", "application/vnd.szl.khipu+json"))
        return JSONResponse({
            "space": space,
            "envelope": env,
            "dsse": env,  # alias for clients expecting either key
            "verify_at": "/khipu/verify",
            "pubkey_at": "/khipu/pubkey",
        })

    registered.append("/khipu/sign")

    # ---- POST /khipu/verify : real verify against cosign.pub ----------------
    @app.post("/khipu/verify")
    async def warhacker_verify(request: Request) -> JSONResponse:  # noqa: ANN202
        if _dsse is None:
            return JSONResponse({"error": "szl_dsse unavailable"}, status_code=503)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"verified": False, "reason": "invalid JSON body"}, status_code=400)
        env = body.get("envelope") or body.get("dsse") or body
        # Optional external pubkey (for cross-Space trust-chain demos)
        ext_pem = body.get("pubkey_pem") or body.get("pem")
        verdict = _verify_with_optional_key(env, ext_pem)
        # surface a clean keyid_match + verified for the smoke scripts
        out = {
            "verified": bool(verdict.get("verified")),
            "keyid_match": _keyid_match(env, verdict),
            "pae_digest": verdict.get("pae_sha256"),
            "detail": verdict,
        }
        return JSONResponse(out)

    registered.append("/khipu/verify")

    # ---- GET /wires/D : signing availability + honest SLSA ------------------
    @app.get("/wires/D")
    async def warhacker_wire_d() -> JSONResponse:  # noqa: ANN202
        available = bool(_dsse and _dsse.signing_available())
        return JSONResponse({
            "wire": "D",
            "space": space,
            "signing_available": available,
            "slsa": "L1 (honest; L2 in roadmap via Wire D)",
            "lambda_status": "Conjecture 1 (NOT a theorem)",
            "doctrine": DOCTRINE_VERSION,
            "pubkey_at": "/khipu/pubkey",
            "sign_at": "/khipu/sign",
            "verify_at": "/khipu/verify",
            "honesty": (
                "DSSE signing is REAL (ECDSA-P256-SHA256 over DSSE PAE, "
                "cosign-verifiable). SLSA tier is L1 by honest self-assessment; "
                "L2 attestation in CI is roadmap, not yet claimed."
            ),
        })

    registered.append("/wires/D")

    return {"module": "szl_warhacker_aliases", "space": space, "registered": registered,
            "signing_available": bool(_dsse and _dsse.signing_available())}


def _verify_with_optional_key(env: dict[str, Any], ext_pem: str | None) -> dict[str, Any]:
    """Verify an envelope. If ext_pem is given, verify against THAT key (cross-Space)."""
    if not ext_pem:
        return _dsse.verify_envelope(env)
    # Cross-Space: verify the signature against an externally-supplied pubkey.
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        pub = load_pem_public_key(ext_pem.encode("utf-8"))
        payload_b64 = env.get("payload")
        payload_type = env.get("payloadType")
        sigs = env.get("signatures") or []
        body = base64.b64decode(payload_b64)
        to_verify = _dsse.pae(payload_type, body)
        digest = hashlib.sha256(to_verify).hexdigest()
        ok = False
        for s in sigs:
            try:
                pub.verify(base64.b64decode(s.get("sig", "")), to_verify, ec.ECDSA(hashes.SHA256()))
                ok = True
            except InvalidSignature:
                pass
        return {"verified": ok, "pae_sha256": digest, "cross_space": True,
                "ext_pubkey_fingerprint": hashlib.sha256(ext_pem.strip().encode()).hexdigest()}
    except Exception as e:
        print(f"[warhacker-aliases] cross-space verify error: {e!r}", file=sys.stderr)
        return {"verified": False, "reason": "verification failed", "cross_space": True}


def _keyid_match(env: dict[str, Any], verdict: dict[str, Any]) -> bool:
    try:
        sigs = env.get("signatures") or []
        expected = getattr(_dsse, "KEYID", "szlholdings-cosign")
        return any(s.get("keyid") == expected for s in sigs)
    except Exception:
        return False
