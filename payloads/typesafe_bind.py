#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""TypeSafe System One bind for a11oy. Contract only. No invented LIVE.

Missing TYPESAFE_API_KEY -> UNAVAILABLE. This file does not call Jev
unless honesty=LIVE and a key exists; default path is the contract receipt.
Jev never ALLOW-alone. Conjecture 1 stays OPEN.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from yuyay_jev import (  # noqa: E402
    DEFAULT_MODEL,
    ENDPOINT,
    YUYAY_AXES,
    fail,
    sha256_hex,
    canon,
)

PAYLOAD = "typesafe_bind"
PACK_ID = "yuyay13.doctrine.v1"


def contract() -> dict:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    body = {
        "ok": True,
        "payload": PAYLOAD,
        "endpoint": ENDPOINT,
        "model": DEFAULT_MODEL,
        "pack_id": PACK_ID,
        "axes": list(YUYAY_AXES),
        "dim": 13,
        "auth": "present" if key else "UNAVAILABLE",
        "honesty": "CONTRACT",
        "live": False,
        "conjecture_1": "OPEN",
        "proven_trust": False,
        "jev_allow_alone": False,
        "khipu_n": 4,
        "khipu_threshold": 3,
        "energy": "UNAVAILABLE",
        "signer": "UNSIGNED-honest",
        "note": "Code owns Lambda. TypeSafe Jev supplies typed judgments when the key is present. Missing key is UNAVAILABLE, not SOFTWARE.",
    }
    body["receipt_hash"] = sha256_hex(canon({k: v for k, v in body.items() if k != "receipt_hash"}))
    return body


def main() -> None:
    raw = sys.stdin.read()
    if raw.strip():
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            fail("stdin is not JSON")
    sys.stdout.write(json.dumps(contract(), sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"crash:{type(exc).__name__}")
