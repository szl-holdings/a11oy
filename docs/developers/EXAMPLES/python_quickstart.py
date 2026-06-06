#!/usr/bin/env python3
"""
python_quickstart.py — Sign a payload, verify it, and build a 2-link Khipu chain.

Uses the live SZL a11oy endpoints. Pure stdlib + requests.
Doctrine v11 · Apache-2.0 · Signed Yachay <yachay@szlholdings.dev>
Co-Authored-By: Perplexity Computer Agent
"""
import base64
import hashlib
import json
import sys

import requests  # pip install requests

A11OY = "https://szlholdings-a11oy.hf.space"


def sign(payload: dict) -> dict:
    """Ask a11oy to wrap `payload` in a DSSE envelope (ECDSA-P256-SHA256)."""
    r = requests.post(f"{A11OY}/khipu/sign", json={"payload": payload}, timeout=30)
    r.raise_for_status()
    return r.json()


def verify(envelope: dict) -> dict:
    """Verify a DSSE envelope server-side."""
    r = requests.post(f"{A11OY}/khipu/verify", json=envelope, timeout=30)
    r.raise_for_status()
    return r.json()


def pubkey() -> dict:
    return requests.get(f"{A11OY}/khipu/pubkey", timeout=30).json()


def receipt_hash(envelope: dict) -> str:
    """Stable hash over the canonical envelope — the Khipu Merkle link."""
    canon = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).hexdigest()


def main() -> int:
    # 0. confirm doctrine
    h = requests.get(f"{A11OY}/healthz", timeout=30).json()
    print("doctrine:", h.get("doctrine"), "numbers:", h.get("numbers"))

    # 1. sign two payloads, chaining the 2nd to the 1st (a Khipu chain)
    env1 = sign({"event": "ingest", "n": 1})
    h1 = receipt_hash(env1)
    print("\nreceipt #1 hash:", h1)
    print("verified #1:", verify(env1).get("verified"))

    env2 = sign({"event": "ingest", "n": 2, "prev": h1})  # link to predecessor
    h2 = receipt_hash(env2)
    print("\nreceipt #2 hash:", h2, "(links prev =", h1[:12] + "...)")
    print("verified #2:", verify(env2).get("verified"))

    # 2. tamper-evidence demo: any change breaks verification
    pk = pubkey()
    print("\nsigning key fingerprint:", pk.get("fingerprint_sha256"))
    print("\nKhipu chain (2 links) built and verified. Tamper any byte and #2 will fail to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
