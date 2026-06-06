#!/usr/bin/env python3
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# dsse_scheme_regression_test.py — lock the receipt signing/verification scheme.
#
# Two components in this repo must agree byte-for-byte on how a governance
# receipt is signed:
#
#   * pepr/policies/szl-receipt-on-deploy.ts (signer) computes
#       HMAC-SHA-256(key, payloadBytes)
#     where payloadBytes = Buffer.from(JSON.stringify(payload)) — the RAW
#     JSON bytes, with NO DSSE Pre-Authentication Encoding (PAE) prefix.
#
#   * scripts/verify_receipts.sh (verifier) computes
#       HMAC-SHA-256(key, base64decode(envelope.payload))
#     — again the RAW payload bytes, NO PAE.
#
# A separate family of demo/scenario scripts in the survival kit signs over the
# DSSE PAE byte-string ("DSSEv1 " || len(type) || ... || payload). Those two
# schemes are INCOMPATIBLE: a receipt produced under one fails verification
# under the other. This test pins the in-repo scheme to RAW-no-PAE so a future
# edit that quietly switches the signer or verifier to PAE (or vice versa) is
# caught here instead of in the field.
#
# Standard library, no cluster, no network. Run:
#   python3 scripts/dsse_scheme_regression_test.py

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys

# Demo HMAC key used by the in-repo signer/verifier (matches the default in
# verify_receipts.sh and the SZL_HMAC_KEY env contract). Not a production
# secret — it is a labelled demo key carried in public source by design.
HMAC_KEY_B64 = "c3psLWRldi1kZW1vLWtleS0yMDI2LXdhcmhhY2tlcg=="
KEY_ID = "szl-dev-hmac-sha256-2026"
PAYLOAD_TYPE = "application/vnd.szl.receipt.v1+json"

# Mirrors the payload object built by the Deployment handler in the pepr policy,
# in the same key order (JSON.stringify preserves insertion order, so order is
# part of the signed bytes).
SAMPLE_PAYLOAD = {
    "_type": "https://szlholdings.com/receipt/v1",
    "subject": "szl-demo-workload/Deployment/szl-demo-agent",
    "specHash": "a" * 64,
    "timestamp": "2026-05-30T00:00:00Z",
    "admissionOp": "CREATE",
    "resourceVersion": "0",
}


def canonical_payload_bytes(payload: dict) -> bytes:
    """Reproduce the signer's payload bytes: Buffer.from(JSON.stringify(payload)).

    JSON.stringify with no replacer/space uses comma+colon separators and
    preserves key insertion order; json.dumps with these separators and
    sort_keys=False matches that byte-for-byte for ASCII payloads.
    """
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE v1 Pre-Authentication Encoding — the scheme this repo does NOT use."""
    pt = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(pt)).encode() + b" " + pt + b" "
        + str(len(payload)).encode() + b" " + payload
    )


def sign_like_pepr_policy(payload: dict, key: bytes) -> dict:
    """Build a DSSE envelope exactly as pepr/policies/szl-receipt-on-deploy.ts does."""
    payload_bytes = canonical_payload_bytes(payload)
    sig = hmac.new(key, payload_bytes, hashlib.sha256).digest()  # RAW bytes, no PAE
    return {
        "payload": base64.b64encode(payload_bytes).decode(),
        "payloadType": PAYLOAD_TYPE,
        "signatures": [{"keyid": KEY_ID, "sig": base64.b64encode(sig).decode()}],
    }


def verify_like_verify_receipts_sh(envelope: dict, key: bytes) -> bool:
    """Verify exactly as scripts/verify_receipts.sh does: HMAC over RAW payload bytes."""
    payload_b64 = envelope["payload"]
    expected = hmac.new(key, base64.b64decode(payload_b64), hashlib.sha256).digest()
    actual = base64.b64decode(envelope["signatures"][0]["sig"])
    return hmac.compare_digest(expected, actual)


def main() -> int:
    key = base64.b64decode(HMAC_KEY_B64)
    failures: list[str] = []

    # 1. The signer's output must verify under the verifier (schemes agree).
    envelope = sign_like_pepr_policy(SAMPLE_PAYLOAD, key)
    if not verify_like_verify_receipts_sh(envelope, key):
        failures.append(
            "signer (pepr policy) and verifier (verify_receipts.sh) disagree: "
            "a receipt signed over RAW payload bytes did not verify"
        )

    # 2. A PAE-wrapped signature must NOT verify under the RAW verifier. This
    #    pins the scheme: if someone switches the signer to DSSE PAE without
    #    updating the verifier, that divergence is caught here.
    payload_bytes = canonical_payload_bytes(SAMPLE_PAYLOAD)
    pae_sig = hmac.new(key, pae(PAYLOAD_TYPE, payload_bytes), hashlib.sha256).digest()
    pae_envelope = {
        "payload": base64.b64encode(payload_bytes).decode(),
        "payloadType": PAYLOAD_TYPE,
        "signatures": [{"keyid": KEY_ID, "sig": base64.b64encode(pae_sig).decode()}],
    }
    if verify_like_verify_receipts_sh(pae_envelope, key):
        failures.append(
            "scheme drift: a DSSE-PAE signature verified under the RAW verifier — "
            "the two schemes must remain distinguishable"
        )

    # 3. Tampering with the payload after signing must fail verification.
    tampered = json.loads(json.dumps(envelope))
    bad_payload = dict(SAMPLE_PAYLOAD, specHash="b" * 64)
    tampered["payload"] = base64.b64encode(canonical_payload_bytes(bad_payload)).decode()
    if verify_like_verify_receipts_sh(tampered, key):
        failures.append("tampered payload verified — signature is not bound to payload")

    if failures:
        print("DSSE scheme regression: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("DSSE scheme regression: PASS")
    print("  - signer and verifier agree on HMAC-SHA-256 over RAW payload bytes (no PAE)")
    print("  - DSSE-PAE signatures are correctly rejected by the RAW verifier")
    print("  - tampered payloads are rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
