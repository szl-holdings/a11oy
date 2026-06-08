#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Produce a deliberately-tampered copy of a genuine release-asset DSSE receipt.

Negative-proof helper for scripts/verify_release_receipts.py (issue #241 / #310).
Given a REAL `*.dsse.json` release receipt, emit a corrupted copy that the
release-receipt verifier MUST reject (non-zero exit). Strategies:

  payload-byteflip   flip one byte of the SIGNED payload inside
                     _sigstore.bundle.dsseEnvelope.payload (and mirror the
                     top-level payload). Defeats the DSSE signature → the real
                     Sigstore verify_dsse() raises → FAIL.
  signature-byteflip flip one byte of _sigstore.bundle.dsseEnvelope
                     .signatures[0].sig → signature no longer matches → FAIL.
  mode-placeholder   set _mode to PLACEHOLDER → a published receipt must be
                     genuinely signed → UNVERIFIABLE (no SDK needed to catch).

All strategies leave the file structurally valid JSON so the verifier reaches
its real checks rather than failing on a parse error.
"""
from __future__ import annotations
import argparse, base64, json, sys
from pathlib import Path

_REAL_MODE = "SIGSTORE-KEYLESS"
_PLACEHOLDER_MODE = "PLACEHOLDER"


def _flip_b64_byte(b64: str) -> str:
    raw = bytearray(base64.b64decode(b64))
    if not raw:
        raise ValueError("nothing to flip (empty)")
    raw[0] ^= 0x01  # flip the lowest bit of the first byte
    return base64.b64encode(bytes(raw)).decode("ascii")


def tamper(env: dict, strategy: str) -> dict:
    env = json.loads(json.dumps(env))  # deep copy
    if strategy == "mode-placeholder":
        env["_mode"] = _PLACEHOLDER_MODE
        return env
    bundle = (env.get("_sigstore") or {}).get("bundle") or {}
    dsse = bundle.get("dsseEnvelope") or {}
    if strategy == "payload-byteflip":
        if "payload" not in dsse:
            raise ValueError("no bundle.dsseEnvelope.payload to tamper")
        dsse["payload"] = _flip_b64_byte(dsse["payload"])
        if "payload" in env:  # keep the mirror consistent so the change is real
            env["payload"] = dsse["payload"]
        return env
    if strategy == "signature-byteflip":
        sigs = dsse.get("signatures") or []
        if not sigs or "sig" not in sigs[0]:
            raise ValueError("no bundle.dsseEnvelope.signatures[0].sig to tamper")
        sigs[0]["sig"] = _flip_b64_byte(sigs[0]["sig"])
        return env
    raise SystemExit(f"unknown strategy: {strategy}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="genuine *.dsse.json receipt")
    ap.add_argument("output", help="path to write the tampered copy")
    ap.add_argument("--strategy", default="payload-byteflip",
        choices=["payload-byteflip", "signature-byteflip", "mode-placeholder"])
    a = ap.parse_args(argv)
    env = json.loads(Path(a.input).read_text(encoding="utf-8"))
    if env.get("_mode") != _REAL_MODE:
        print(f"WARNING: input _mode is {env.get('_mode')!r}, not {_REAL_MODE}",
              file=sys.stderr)
    out = tamper(env, a.strategy)
    Path(a.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[tamper] {a.strategy}: wrote {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
