#!/usr/bin/env python3
"""verify_chain_offline.py — offline verifier for SZL DSSE receipt chains.

Verifies a published receipt bundle with NO network access:

  1. Every DSSE envelope signature is checked against a trusted local
     public key (ECDSA P-256 / SHA-256, the estate signing scheme —
     Sigstore cosign default).
  2. The hash chain is replayed: each beat's payload carries
     prev_beat_hash == prior beat_hash, where
     beat_hash = sha256(PAE(payloadType, payload)).
  3. The final beat_hash must equal the bundle's expected root.

Fails closed: any signature, link, digest, or canonical-encoding
mismatch aborts with CHAIN FAILED and a non-zero exit code.

Usage:
  python examples/verify_chain_offline.py \
      --bundle examples/offline-verify-sample/bundle.json \
      --pubkey examples/offline-verify-sample/pubkey.pem

Exit codes: 0 = CHAIN OK, 1 = verification failed, 2 = usage/IO error.
Only dependency: `cryptography` (already used by szl-receipt / szl_dsse.py).
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import sys
from pathlib import Path

from cryptography import x509  # noqa: F401  (imported for parity with szl_dsse)
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

LEGACY_KEYIDS = {"szlholdings-cosign"}
GENESIS_ZERO = "0" * 64


class ChainError(Exception):
    """Any verification failure. Fail closed."""


def pae(payload_type: bytes, body: bytes) -> bytes:
    """DSSE v1 pre-auth encoding: "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body."""
    return (
        b"DSSEv1 "
        + str(len(payload_type)).encode("ascii")
        + b" "
        + payload_type
        + b" "
        + str(len(body)).encode("ascii")
        + b" "
        + body
    )


def canonical_json(obj) -> bytes:
    """Canonical JSON: sorted keys, tight separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_pem(pem_bytes: bytes) -> bytes:
    """Normalize a PEM for fingerprinting: LF endings, single trailing newline."""
    text = pem_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return (text.strip() + "\n").encode("utf-8")


def key_fingerprint(pem_bytes: bytes) -> str:
    """Estate keyid convention: SHA-256 of the normalized public PEM."""
    return hashlib.sha256(normalize_pem(pem_bytes)).hexdigest()


def load_public_key(path: Path):
    pem = path.read_bytes()
    try:
        key = serialization.load_pem_public_key(pem)
    except ValueError as exc:
        raise ChainError(f"{path}: not a valid PEM public key ({exc})")
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(
        key.curve, ec.SECP256R1
    ):
        raise ChainError(f"{path}: trusted key is not ECDSA P-256 (secp256r1)")
    return key, pem


def verify_signature(envelope: dict, pubkey, pem: bytes, strict_keyid: bool) -> str:
    payload_type = envelope.get("payloadType")
    if not isinstance(payload_type, str) or not payload_type:
        raise ChainError("envelope missing payloadType")
    payload_b64 = envelope.get("payload")
    if not isinstance(payload_b64, str):
        raise ChainError("envelope missing payload")
    try:
        body = base64.b64decode(payload_b64, validate=True)
    except binascii.Error as exc:
        raise ChainError(f"payload is not valid base64 ({exc})")

    sigs = envelope.get("signatures") or []
    if not sigs:
        raise ChainError("envelope has no signatures")

    pae_bytes = pae(payload_type.encode("utf-8"), body)
    fpr = key_fingerprint(pem)
    keyid_note = ""
    verified = False
    last_err = "no signatures"
    for entry in sigs:
        sig_b64 = entry.get("sig")
        if not isinstance(sig_b64, str):
            continue
        try:
            sig = base64.b64decode(sig_b64, validate=True)
        except binascii.Error:
            last_err = "signature not valid base64"
            continue
        try:
            pubkey.verify(sig, pae_bytes, ec.ECDSA(hashes.SHA256()))
            verified = True
        except InvalidSignature:
            last_err = "ECDSA signature invalid"
            continue
        keyid = entry.get("keyid", "")
        if keyid == fpr:
            keyid_note = "keyid matches key fingerprint"
        elif keyid in LEGACY_KEYIDS:
            keyid_note = f"legacy keyid {keyid!r} accepted (signature is what matters)"
        elif strict_keyid:
            raise ChainError(
                f"keyid {keyid!r} does not match trusted key fingerprint {fpr[:16]}…"
            )
        else:
            keyid_note = f"WARNING: keyid {keyid!r} != fingerprint {fpr[:16]}…"
        break
    if not verified:
        raise ChainError(last_err)
    return payload_type, body, keyid_note


def verify_chain(bundle: dict, pubkey, pem: bytes, strict_keyid: bool,
                 strict_canonical: bool, quiet: bool) -> dict:
    payload_type = bundle.get("payloadType")
    beats = bundle.get("beats")
    if not payload_type or not isinstance(beats, list) or not beats:
        raise ChainError("bundle must declare payloadType and a non-empty beats[] array")
    expected_root = (bundle.get("expected_root") or "").lower().removeprefix("sha256:")
    if len(expected_root) != 64:
        raise ChainError("bundle expected_root must be a 64-char sha256 hex digest")
    genesis = (bundle.get("genesis") or GENESIS_ZERO).lower().removeprefix("sha256:")

    running = genesis
    n = len(beats)
    for i, env in enumerate(beats):
        pt, body, keyid_note = verify_signature(env, pubkey, pem, strict_keyid)
        if pt != payload_type:
            raise ChainError(
                f"beat {i}: payloadType {pt!r} != bundle payloadType {payload_type!r}"
            )
        try:
            payload_obj = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ChainError(f"beat {i}: payload is not UTF-8 JSON ({exc})")
        for field in ("seq", "prev_beat_hash", "receipt", "ts"):
            if field not in payload_obj:
                raise ChainError(f"beat {i}: payload missing field {field!r}")
        if payload_obj["seq"] != i:
            raise ChainError(f"beat {i}: seq {payload_obj['seq']} != position {i}")
        if strict_canonical and canonical_json(payload_obj) != body:
            raise ChainError(f"beat {i}: payload is not canonical JSON (reorder/whitespace)")
        prev = str(payload_obj["prev_beat_hash"]).lower().removeprefix("sha256:")
        if prev != running:
            raise ChainError(f"beat {i}: prev_beat_hash breaks chain link")
        beat_hash = hashlib.sha256(pae(pt.encode("utf-8"), body)).hexdigest()
        if not quiet:
            print(f"[beat {i:>3}/{n}] sig OK · link OK · hash {beat_hash[:16]}…"
                  + (f" ({keyid_note})" if i == 0 and keyid_note else ""))
        running = beat_hash

    if running != expected_root:
        raise ChainError(
            f"chain root {running[:16]}… != expected_root {expected_root[:16]}…"
        )
    return {"beats": n, "root": running, "fingerprint": key_fingerprint(pem)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline verifier for SZL DSSE receipt chains.")
    ap.add_argument("--bundle", required=True, type=Path, help="receipt bundle JSON")
    ap.add_argument("--pubkey", required=True, type=Path, help="trusted signer public key (PEM, P-256)")
    ap.add_argument("--strict-keyid", action="store_true",
                    help="require keyid == sha256(normalized PEM) (legacy keyids rejected)")
    ap.add_argument("--no-canonical-check", action="store_true",
                    help="skip canonical-JSON byte check on payloads")
    ap.add_argument("--quiet", action="store_true", help="suppress per-beat lines")
    ap.add_argument("--json", action="store_true", help="emit machine-readable verdict")
    args = ap.parse_args(argv)

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot load bundle {args.bundle}: {exc}", file=sys.stderr)
        return 2
    try:
        pubkey, pem = load_public_key(args.pubkey)
    except (OSError, ChainError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = verify_chain(bundle, pubkey, pem,
                              strict_keyid=args.strict_keyid,
                              strict_canonical=not args.no_canonical_check,
                              quiet=args.quiet or args.json)
    except ChainError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"CHAIN FAILED — {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": True, **result}))
    else:
        print(f"CHAIN OK — {result['beats']} beats verified, root sha256:{result['root']}")
        print(f"signer fingerprint (sha256 of normalized PEM): {result['fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
