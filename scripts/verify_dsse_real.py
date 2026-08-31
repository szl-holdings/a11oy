#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""Independently verify a Sigstore-keyless DSSE envelope produced by sign_governance_receipts.py.

Issue #203 (Tier B) — this is the verification half of the #203 evidence chain.
Re-derives trust from the embedded Sigstore bundle: validates the Fulcio
certificate chain, the Rekor inclusion proof, and the DSSE signature, and pins the
signer identity (the GitHub Actions workflow SAN) + OIDC issuer.

HONESTY
  - An envelope whose `_mode` is "PLACEHOLDER" is NOT a real signature and cannot
    be cryptographically verified — this tool reports that plainly and (unless
    --allow-placeholder is passed) exits non-zero.
  - Verification is performed entirely from the bundle in the file plus the public
    Sigstore trust root — no private key, no org secret.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from szl_formulas import verify_dsse_real  # noqa: E402

_SIGSTORE_OIDC_ISSUER = "https://token.actions.githubusercontent.com"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("envelope", help="path to the .dsse.json envelope to verify")
    ap.add_argument(
        "--identity", required=True,
        help=(
            "expected certificate SAN, e.g. https://github.com/szl-holdings/a11oy/"
            ".github/workflows/dsse-receipts.yml@refs/heads/main"
        ),
    )
    ap.add_argument(
        "--issuer", default=_SIGSTORE_OIDC_ISSUER,
        help="expected OIDC issuer (default: GitHub Actions)",
    )
    ap.add_argument(
        "--allow-placeholder", action="store_true",
        help="treat a PLACEHOLDER envelope as a soft pass (exit 0) instead of failing",
    )
    args = ap.parse_args(argv)

    env_path = Path(args.envelope)
    if not env_path.exists():
        print(f"[verify] ERROR: envelope not found: {env_path}", file=sys.stderr)
        return 1

    envelope = json.loads(env_path.read_text(encoding="utf-8"))
    mode = envelope.get("_mode", "?")
    print(f"[verify] file={env_path.name} mode={mode}")

    if mode != "SIGSTORE-KEYLESS":
        msg = (
            f"[verify] envelope is '{mode}', NOT a real Sigstore keyless signature; "
            "there is nothing to cryptographically verify."
        )
        if args.allow_placeholder:
            print(msg + " (--allow-placeholder: soft pass)")
            return 0
        print(msg, file=sys.stderr)
        return 2

    try:
        result = verify_dsse_real(
            envelope, identity=args.identity, issuer=args.issuer,
        )
    except Exception as exc:  # noqa: BLE001 - any verification failure must be loud
        print(f"[verify] VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 3

    print("[verify] VERIFIED ✔  (Fulcio cert chain + Rekor inclusion + DSSE signature)")
    print(f"[verify] payloadType={result['payloadType']} payload_len={result['payload_len']}")
    print(f"[verify] rekor_log_index={result['rekor_log_index']}")
    print(f"[verify] certificate_fpr_sha256={result['certificate_fpr_sha256']}")
    print(f"[verify] identity={args.identity}")
    print(f"[verify] issuer={args.issuer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
