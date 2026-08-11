#!/usr/bin/env python3
# Offline receipt verifier for signed governance receipts.
# Expected usage:
#   python receipt_verify.py receipt.json
#   python receipt_verify.py receipt.json --secret-file key.txt

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "receipt_id",
    "agent_id",
    "policy_id",
    "tool_id",
    "data_scope",
    "human_approval_id",
    "output_digest",
    "timestamp_utc",
    "signature",
}


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def signature_for(payload: dict, secret: str) -> str:
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    data = canonical(unsigned)
    mac = hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


def verify(payload: dict, secret: str) -> bool:
    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    sig = payload.get("signature")
    expected = signature_for(payload, secret)
    if not hmac.compare_digest(sig, expected):
        raise ValueError("signature mismatch")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt")
    parser.add_argument("--secret", default="demo-local-secret")
    parser.add_argument("--secret-file", default=None)
    args = parser.parse_args()

    secret = args.secret
    if args.secret_file:
        secret = Path(args.secret_file).read_text(encoding="utf-8").strip()

    try:
        raw = Path(args.receipt).read_text(encoding="utf-8")
        payload = json.loads(raw)
        verify(payload, secret)
        print(f"receipt_ok: {payload.get('receipt_id')}")
        return 0
    except Exception as err:
        print(f"receipt_bad: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
