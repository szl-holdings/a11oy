#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Independent OFFLINE verifier for committed AYLLU council decision receipts.

Trusts NOTHING from the running server: given a committed decision file
(`ayllu/decisions/*.json`) and the pinned council public key
(`ayllu/keys/council-runtime-2026-07-21.pub`), it re-derives everything:

  1. DSSE PAE  = b"DSSEv1 SP len(type) SP type SP len(body) SP body"
  2. ECDSA-P256-SHA256 signature over the PAE vs the pinned public key
  3. payload_digest reproduces from canonical JSON (sorted keys, compact
     separators) of the payload `body`
  4. receipt_id equals the Khipu chain receipt id inside the body

HONESTY: the envelope keyid label is "szlholdings-cosign" but the pinned key
does NOT match the published org cosign.pub (szl-holdings/.github). The pin's
provenance (ECDSA public-key recovery from two independent live signatures,
2026-07-21) is stated in ayllu/keys/README.md. PASS here means "signed by the
pinned runtime key and unaltered" — nothing more.

Usage:
  python scripts/verify_ayllu_council_receipt.py \
      ayllu/decisions/<file>.json --key ayllu/keys/council-runtime-2026-07-21.pub
Exit 0 = all checks pass; non-zero = at least one check failed (fail-closed).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    t = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(body), body)


def verify(doc: dict, pem: bytes) -> dict:
    checks: dict[str, bool] = {}
    env = doc.get("receipt") or {}
    try:
        payload_bytes = base64.b64decode(env.get("payload") or "", validate=True)
        payload = json.loads(payload_bytes)
        checks["payload_decodes"] = True
    except Exception:
        payload_bytes, payload = b"", {}
        checks["payload_decodes"] = False
    sig_ok = False
    try:
        pub = load_pem_public_key(pem)
        sig = base64.b64decode((env.get("signatures") or [{}])[0].get("sig") or "",
                               validate=True)
        pub.verify(sig, pae(env.get("payloadType") or "", payload_bytes),
                   ec.ECDSA(hashes.SHA256()))
        sig_ok = True
    except Exception:
        sig_ok = False
    checks["ecdsa_signature_verifies_over_pae"] = sig_ok
    body = payload.get("body") if isinstance(payload, dict) else None
    checks["payload_digest_reproduces"] = (
        isinstance(body, dict)
        and payload.get("payload_digest")
        == hashlib.sha256(canonical(body)).hexdigest()
    )
    chain = (body or {}).get("chain") or {}
    checks["receipt_id_matches_chain"] = (
        payload.get("receipt_id") is not None
        and payload.get("receipt_id") == chain.get("receipt_id")
    )
    return {
        "all_passed": all(checks.values()),
        "checks": checks,
        "derived": {
            "council_id": (body or {}).get("council_id"),
            "receipt_id": payload.get("receipt_id") if isinstance(payload, dict) else None,
            "participants": (body or {}).get("participants"),
            "decision_state": (body or {}).get("decision_state"),
            "prompt_sha256": (body or {}).get("prompt_sha256"),
            "keyid_label": (env.get("signatures") or [{}])[0].get("keyid"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("decision", help="path to a committed ayllu/decisions/*.json file")
    ap.add_argument("--key", required=True,
                    help="path to the pinned council public key PEM")
    args = ap.parse_args(argv)
    doc = json.loads(Path(args.decision).read_text(encoding="utf-8"))
    pem = Path(args.key).read_bytes()
    result = verify(doc, pem)
    for name, passed in result["checks"].items():
        print(f"[verify] {name}: {'PASS' if passed else 'FAIL'}")
    for k, v in result["derived"].items():
        print(f"[derived] {k} = {v}")
    print(f"[verify] pinned key fingerprint sha256 = "
          f"{hashlib.sha256(pem).hexdigest()}")
    if result["all_passed"]:
        print("[verify] VERIFIED ✔ — signed by the pinned runtime key, unaltered "
              "(NOT proof of decision quality or authority)")
        return 0
    print("[verify] FAILED — at least one check did not pass (fail-closed)",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
