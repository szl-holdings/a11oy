#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Fixture tests for the AYLLU council offline verifier — tamper paths included.

Runs against a REAL committed decision fixture + the pinned council key.
Proves fail-closed behaviour: byte tampering the payload, the signature, the
declared digest, or the key must each flip PASS → FAIL.
"""
from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from verify_ayllu_council_receipt import verify  # noqa: E402

DECISIONS = sorted((REPO_ROOT / "ayllu" / "decisions").glob("2026-*.json"))
KEY = (REPO_ROOT / "ayllu" / "keys" / "council-runtime-2026-07-21.pub").read_bytes()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_fixtures_verify():
    assert DECISIONS, "no committed decision fixtures found"
    for p in DECISIONS:
        r = verify(_load(p), KEY)
        assert r["all_passed"], f"{p.name}: {r['checks']}"


def test_tampered_payload_fails():
    doc = copy.deepcopy(_load(DECISIONS[0]))
    raw = bytearray(base64.b64decode(doc["receipt"]["payload"]))
    raw[len(raw) // 2] ^= 0x01
    doc["receipt"]["payload"] = base64.b64encode(bytes(raw)).decode()
    r = verify(doc, KEY)
    assert not r["all_passed"]
    assert not r["checks"]["ecdsa_signature_verifies_over_pae"]


def test_tampered_signature_fails():
    doc = copy.deepcopy(_load(DECISIONS[0]))
    sig = bytearray(base64.b64decode(doc["receipt"]["signatures"][0]["sig"]))
    sig[-1] ^= 0x01
    doc["receipt"]["signatures"][0]["sig"] = base64.b64encode(bytes(sig)).decode()
    r = verify(doc, KEY)
    assert not r["all_passed"]
    assert not r["checks"]["ecdsa_signature_verifies_over_pae"]


def test_wrong_key_fails():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat)
    other = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    r = verify(_load(DECISIONS[0]), other)
    assert not r["all_passed"]
    assert not r["checks"]["ecdsa_signature_verifies_over_pae"]


def test_missing_signature_fails():
    doc = copy.deepcopy(_load(DECISIONS[0]))
    doc["receipt"]["signatures"] = []
    r = verify(doc, KEY)
    assert not r["all_passed"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[test] {fn.__name__}: PASS")
    print(f"[test] all {len(fns)} tests passed")
