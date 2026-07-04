#!/usr/bin/env python3
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Self-test for szl_corpus_publish's verify-before-publish gate (Incident #325).

Proves the root-cause fix: a receipt CANNOT be published unless it verifies under
the DOCUMENTED trusted keyset at publish time. A receipt signed with an untrusted
/ transient key (the class that produced the #325 orphans) is REJECTED; a receipt
signed with a trusted key is accepted; and the gate reads the real multi-key
trust set from .github/hf-corpus-guards.json.

Requires `cryptography` (present in CI); self-skips the real-crypto asserts
otherwise. Run by file path:  python3 scripts/test_szl_corpus_publish_gate.py
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_corpus_publish as pub  # noqa: E402

FAILURES = []


def check(name, cond):
    if cond:
        print("  ok  - %s" % name)
    else:
        print("  FAIL- %s" % name)
        FAILURES.append(name)


def _dsse_env(private_key, payload=b'{"receipt":"demo"}',
              ptype="application/vnd.szl.khipu+json"):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    pae = b"DSSEv1 %d %s %d %s" % (
        len(ptype.encode()), ptype.encode(), len(payload), payload)
    sig = private_key.sign(pae, ec.ECDSA(hashes.SHA256()))
    return {"payloadType": ptype,
            "payload": base64.b64encode(payload).decode(),
            "signatures": [{"sig": base64.b64encode(sig).decode(),
                            "keyid": "test"}],
            "signed": True,
            "honesty": "REAL — test envelope"}


def real_gate_path():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except Exception:
        print("  skip- real publish-gate path (cryptography not installed)")
        return

    def pem_of(k):
        return k.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    trusted_key = ec.generate_private_key(ec.SECP256R1())
    untrusted_key = ec.generate_private_key(ec.SECP256R1())  # e.g. ephemeral pod
    trusted_pem = pem_of(trusted_key)

    orig = pub._corpus_trusted_pub_pems
    pub._corpus_trusted_pub_pems = lambda: [trusted_pem]
    try:
        env_ok = _dsse_env(trusted_key)
        env_bad = _dsse_env(untrusted_key)

        # low-level verifier
        check("trusted-key envelope verifies against the keyset",
              pub._ecdsa_envelope_verifies(env_ok, [trusted_pem]) is True)
        check("untrusted-key envelope does NOT verify against the keyset",
              pub._ecdsa_envelope_verifies(env_bad, [trusted_pem]) is False)

        # gate
        check("GATE: trusted-key receipt is publishable",
              pub._publishable_against_corpus_key(env_ok, "ecdsa-p256-dsse-pae")
              is True)
        check("GATE: untrusted/transient-key receipt is REJECTED at publish",
              pub._publishable_against_corpus_key(env_bad, "ecdsa-p256-dsse-pae")
              is False)

        # end-to-end producer hook: an untrusted-key receipt is never published
        res = pub.on_new_receipt(env_bad)
        check("on_new_receipt skips untrusted-key receipt (published=0)",
              res.get("published", 0) == 0
              and res.get("skipped") == "signature-not-verifiable-against-corpus-key")

        # backfill also refuses the untrusted-key receipt
        # (bucket may be unavailable in the sandbox; the refusal is what matters)
        bf = pub.backfill_receipts([env_bad], flush=False)
        check("backfill refuses untrusted-key receipt (0 queued or bucket-unavailable)",
              (bf.get("queued", 0) == 0))
    finally:
        pub._corpus_trusted_pub_pems = orig


def config_trust_set_path():
    """The gate reads the real documented multi-key trust set from the config."""
    pems = pub._corpus_trusted_pub_pems()
    check("config exposes >= 2 trusted keys (historical + current org)",
          len(pems) >= 2)
    fps = {hashlib.sha256(p.strip().encode()).hexdigest() for p in pems}
    check("historical CI key present in trust set",
          "421a1422ebb2516aaf08358e5c4b75aed4f5e1ecd76ac9e2a2e7a9879c067e1e" in fps)
    check("current org key present in trust set",
          "d3028f8aecd0841f684e1c7fd7b06de7a211dc6fc09c34163003798b391bcf71" in fps)
    check("ephemeral orphan key is NOT trusted",
          "76199818b3b626f4854385ecb868e288696a2981dced3cec600c948eb9ac65a7"
          not in fps)


def main():
    config_trust_set_path()
    real_gate_path()
    print()
    if FAILURES:
        print("PUBLISH-GATE SELF-TEST FAILED: %d" % len(FAILURES))
        return 1
    print("PUBLISH-GATE SELF-TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
