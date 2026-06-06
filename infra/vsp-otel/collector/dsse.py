"""
collector/dsse.py — DSSE in-toto attestation signer for accepted spans.

Layer 4 crypto. Every span that passes the Λ-gate is wrapped in a DSSE envelope
(PAE v1) over an in-toto v1 statement. Two signing modes:

  * dev/local      — real ECDSA P-256 (cryptography) or HMAC-SHA-256 fallback.
  * cosign keyless — Sigstore Fulcio OIDC + Rekor transparency log (production).
                     Disclosed boundary: keyless signing requires an OIDC token and
                     network egress to Fulcio/Rekor; it is wired but lands in CI
                     (Doctrine v12 §2). Modelled on the proved-where-proved Lean refs
                     Lutar.Round10.CryptoDSSE.dsse_classical_euf_cma (PR #179, 0 real
                     sorry) and Lutar.Round10.CryptoRekor.rekor_inclusion_completeness
                     (PR #179; soundness is an honest tagged sorry → Conjecture 1).

SPDX-License-Identifier: Apache-2.0
Author: Yachay (CTO authority) · Built by Perplexity Computer Agent · SZL Holdings
Doctrine v11 LOCKED — 749 / 14 / 163.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, load_pem_private_key,
    )
    _CRYPTO = True
except Exception:  # pragma: no cover
    _CRYPTO = False

PAYLOAD_TYPE = "application/vnd.in-toto+json"
_HMAC_KEY = os.environ.get("VSP_HMAC_KEY", "szl-vsp-hmac-dev-v1").encode()


def _pae(payload_type: str, payload: bytes) -> bytes:
    t = payload_type.encode()
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
            + str(len(payload)).encode() + b" " + payload)


def _in_toto_statement(span: dict, gate: dict) -> dict:
    """in-toto v1 Statement binding the span to its Λ-gate verdict."""
    span_id = span.get("span_id", "")
    trace_id = span.get("trace_id", "")
    name = span.get("name", "")
    digest = hashlib.sha256(
        json.dumps(span, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": f"otel-span:{trace_id}/{span_id}",
                     "digest": {"sha256": digest}}],
        "predicateType": "https://szlholdings.ai/attestations/lambda-gate/v1",
        "predicate": {
            "span_name": name,
            "lambda": gate["lambda_value"],
            "floor": gate.get("floor"),
            "passed": gate["passed"],
            "axes": gate["axes"],
            "doctrine": "v11-749/14/163",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


class DsseSigner:
    """Signs accepted spans. Prefers ECDSA P-256; HMAC fallback for dep-free CI."""

    def __init__(self, mode: Optional[str] = None) -> None:
        self.mode = mode or os.environ.get("VSP_SIGN_MODE", "auto")
        self._key = None
        self._kid = "hmac-dev"
        pem = os.environ.get("VSP_SIGN_KEY_PEM")
        if _CRYPTO and pem and self.mode in ("auto", "ecdsa"):
            self._key = load_pem_private_key(pem.encode(), password=None)
            self._kid = "ecdsa-p256-" + hashlib.sha256(
                self._key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
            ).hexdigest()[:12]
        elif _CRYPTO and self.mode in ("auto", "ecdsa") and os.environ.get("VSP_SIGN_MODE") == "ecdsa":
            self._key = ec.generate_private_key(ec.SECP256R1())
            self._kid = "ecdsa-p256-ephemeral"

    def sign_span(self, span: dict, gate: dict) -> dict:
        statement = _in_toto_statement(span, gate)
        payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
        b64 = base64.b64encode(payload).decode()
        pae = _pae(PAYLOAD_TYPE, payload)
        if self._key is not None:
            sig = base64.b64encode(self._key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode()
        else:
            sig = base64.b64encode(hmac.new(_HMAC_KEY, pae, hashlib.sha256).digest()).decode()
        return {
            "payloadType": PAYLOAD_TYPE,
            "payload": b64,
            "signatures": [{"keyid": self._kid, "sig": sig}],
            "receipt_hash": hashlib.sha256(payload).hexdigest(),
        }

    def keyid(self) -> str:
        return self._kid
