#!/usr/bin/env python3
"""make_sample_chain.py — regenerate the offline-verify sample bundle.

Builds a 3-beat DSSE-signed, hash-chained receipt bundle using an EPHEMERAL
ECDSA P-256 key, and writes:

  examples/offline-verify-sample/pubkey.pem   (trusted verifier key)
  examples/offline-verify-sample/bundle.json  (payloadType, genesis, beats, expected_root)

The private key is discarded. This sample exists so a fresh clone can run
verify_chain_offline.py and see CHAIN OK in under 5 minutes.
"""

import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

PAYLOAD_TYPE = "application/vnd.szl.heart.beat+json"
GENESIS = "0" * 64
OUT = Path(__file__).resolve().parent / "offline-verify-sample"


def pae(payload_type: bytes, body: bytes) -> bytes:
    return (b"DSSEv1 " + str(len(payload_type)).encode() + b" " + payload_type
            + b" " + str(len(body)).encode() + b" " + body)


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    keyid = hashlib.sha256(pub_pem.decode().strip().encode() + b"\n").hexdigest()

    beats, prev = [], GENESIS
    for i in range(3):
        body = canonical_json({
            "seq": i,
            "prev_beat_hash": prev,
            "receipt": {"action": f"governed-action-{i}", "verdict": "ALLOW",
                        "gate": "yuyay-13", "demo": True},
            "ts": f"2026-09-02T00:00:0{i}Z",
        })
        sig = key.sign(pae(PAYLOAD_TYPE.encode(), body), ec.ECDSA(hashes.SHA256()))
        beats.append({
            "payloadType": PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode(),
            "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode()}],
        })
        prev = hashlib.sha256(pae(PAYLOAD_TYPE.encode(), body)).hexdigest()

    bundle = {
        "bundle_id": "szl-offline-verify-sample-v1",
        "payloadType": PAYLOAD_TYPE,
        "genesis": GENESIS,
        "beats": beats,
        "expected_root": prev,
        "note": "Ephemeral demo key. Real bundles are signed by estate organ keys "
                "published at github.com/szl-holdings/.github/tree/main/cosign-keys.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pubkey.pem").write_bytes(pub_pem)
    (OUT / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    print(f"wrote {OUT}/bundle.json ({len(beats)} beats, root {prev[:16]}…) and pubkey.pem")


if __name__ == "__main__":
    main()
