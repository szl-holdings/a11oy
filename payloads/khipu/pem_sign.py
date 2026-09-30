#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Optional PEM signer for Khipu organ verdicts.

Fail-closed. Stdlib-first. Never fabricates a signature.
Jev never signs. Organs sign only when a PEM is present AND a real
ECDSA-P256 signer is importable (khipu_consensus preferred).

Env (owner machine only):
  SZL_SENTRA_COSIGN_PEM
  SZL_AMARU_COSIGN_PEM
  SZL_A11OY_COSIGN_PEM
  SZL_KILLINCHU_COSIGN_PEM

Missing PEM -> signer=UNSIGNED-honest, signed=False.
Present PEM but no signer module -> signer=UNSIGNED-honest, signed=False,
reason=PEM-present-signer-UNAVAILABLE. Do not paint LIVE.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from khipu_organs import ORGAN_PEMS, WITNESS_KEYIDS

PAYLOAD_TYPE = "application/vnd.szl.khipu.organ-verdict+json"


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def action_hash(intent: str, lambda_: float, decision: str) -> str:
    body = {"intent": intent, "lambda": round(float(lambda_), 12), "decision": decision}
    return hashlib.sha256(_canon(body)).hexdigest()


def _try_khipu_sign(organ: str, digest: str, verdict: str, pem: str) -> dict[str, Any] | None:
    try:
        from khipu_consensus import sign_verdict  # type: ignore
    except Exception:
        return None
    try:
        signed = sign_verdict(organ, digest, verdict, pem)
    except Exception as exc:  # noqa: BLE001
        return {
            "signed": False,
            "signer": "UNSIGNED-honest",
            "reason": f"khipu_consensus.sign_verdict failed:{type(exc).__name__}",
        }
    return {
        "signed": True,
        "signer": WITNESS_KEYIDS[organ],
        "signature": signed,
        "reason": "khipu_consensus.sign_verdict",
    }


def _try_ecdsa_sign(organ: str, digest: str, pem: str) -> dict[str, Any] | None:
    try:
        import ecdsa  # type: ignore
        from ecdsa import NIST256p, SigningKey
    except Exception:
        return None
    try:
        key = SigningKey.from_pem(pem)
        if key.curve != NIST256p:
            return {
                "signed": False,
                "signer": "UNSIGNED-honest",
                "reason": "PEM is not ECDSA-P256",
            }
        sig = key.sign_digest(
            bytes.fromhex(digest),
            sigencode=ecdsa.util.sigencode_der,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "signed": False,
            "signer": "UNSIGNED-honest",
            "reason": f"ecdsa-sign-failed:{type(exc).__name__}",
        }
    return {
        "signed": True,
        "signer": WITNESS_KEYIDS[organ],
        "signature": sig.hex(),
        "encoding": "ecdsa-p256-sha256-der",
        "reason": "stdlib-adjacent ecdsa. Signing is analog until khipu_consensus verifies.",
        "honesty": "SOFTWARE",
    }


def sign_organ(organ: str, *, intent: str, lambda_: float, verdict: str) -> dict[str, Any]:
    if organ not in WITNESS_KEYIDS:
        return {
            "organ": organ,
            "signed": False,
            "signer": "UNSIGNED-honest",
            "reason": "unknown organ",
            "jev_allow_alone": False,
        }
    digest = action_hash(intent, lambda_, verdict)
    env_name = ORGAN_PEMS[organ]
    pem = os.environ.get(env_name, "").strip()
    base = {
        "organ": organ,
        "keyid": WITNESS_KEYIDS[organ],
        "pem_env": env_name,
        "action_hash": digest,
        "verdict": verdict,
        "payload_type": PAYLOAD_TYPE,
        "jev_allow_alone": False,
    }
    if not pem:
        return {
            **base,
            "signed": False,
            "signer": "UNSIGNED-honest",
            "reason": "PEM absent",
        }
    signed = _try_khipu_sign(organ, digest, verdict, pem)
    if signed is None:
        signed = _try_ecdsa_sign(organ, digest, pem)
    if signed is None:
        return {
            **base,
            "signed": False,
            "signer": "UNSIGNED-honest",
            "reason": "PEM-present-signer-UNAVAILABLE",
        }
    return {**base, **signed}


def sign_votes(votes: list[dict[str, Any]], *, intent: str, lambda_: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in votes:
        organ = str(v.get("organ") or "")
        verdict = str(v.get("verdict") or "block")
        sig = sign_organ(organ, intent=intent, lambda_=lambda_, verdict=verdict)
        out.append({**v, "cosign": sig, "signer": sig.get("signer") or v.get("signer")})
    return out
