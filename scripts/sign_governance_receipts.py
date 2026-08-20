#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""Sign the a11oy governance decision log as a GENUINE Sigstore keyless DSSE envelope.

Issue #203 (Tier B). Reads a governance log (default: governed_loop_E4.json),
canonicalises it, and produces a DSSE envelope signed with a real Sigstore keyless
signature — a GitHub OIDC token is exchanged at Fulcio for an ephemeral ECDSA-P256
certificate and the signature is recorded in the Rekor transparency log.

HONESTY
  - This is REAL signing only inside CI (a context with an ambient OIDC token, i.e.
    GitHub Actions with `permissions: id-token: write`). Outside CI there is no
    identity to mint a certificate from, so by default we DECLINE rather than
    fabricate a signature (exit 2). Pass --allow-placeholder to instead emit the
    honest dsse_envelope() placeholder (clearly marked `_mode: PLACEHOLDER`).
  - This does NOT change the SLSA claim. SLSA wording stays L1; this only upgrades
    the receipt SIGNATURE from placeholder to real.

Output: attestations/governance/<payload_sha256>.dsse.json
"""
from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from szl_formulas import (  # noqa: E402
    DsseSigningUnavailable,
    dsse_envelope_real,
    real_signing_available,
    sign_dsse_or_placeholder,
)

_PAYLOAD_TYPE = "application/vnd.szl.governance-log+json"


def _canonical_payload(log_path: Path) -> bytes:
    """Deterministic bytes for the governance log (sorted keys, compact)."""
    data = json.loads(log_path.read_text(encoding="utf-8"))
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--log", default=str(REPO_ROOT / "governed_loop_E4.json"),
        help="path to the governance decision log to sign",
    )
    ap.add_argument(
        "--out-dir", default=str(REPO_ROOT / "attestations" / "governance"),
        help="directory to write the signed DSSE envelope into",
    )
    ap.add_argument(
        "--subject", default="szl-governance-decision-log",
        help="DSSE statement subject name",
    )
    ap.add_argument(
        "--allow-placeholder", action="store_true",
        help="emit the honest placeholder instead of failing when real signing is unavailable",
    )
    args = ap.parse_args(argv)

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"[sign] ERROR: governance log not found: {log_path}", file=sys.stderr)
        return 1

    payload = _canonical_payload(log_path)
    digest = sha256(payload).hexdigest()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{digest}.dsse.json"

    available = real_signing_available()
    print(f"[sign] log={log_path.name} sha256={digest}")
    print(f"[sign] real Sigstore keyless signing available: {available}")

    if args.allow_placeholder:
        envelope = sign_dsse_or_placeholder(
            payload, _PAYLOAD_TYPE, subject_name=args.subject,
        )
    else:
        try:
            envelope = dsse_envelope_real(
                payload, _PAYLOAD_TYPE, subject_name=args.subject,
            )
        except DsseSigningUnavailable as exc:
            print(
                f"[sign] REFUSING to fabricate a signature: {exc}\n"
                "[sign] run inside GitHub Actions with `id-token: write`, or pass "
                "--allow-placeholder for the honest placeholder.",
                file=sys.stderr,
            )
            return 2

    out_path.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")
    mode = envelope.get("_mode", "?")
    print(f"[sign] mode={mode}")
    print(f"[sign] wrote {out_path}")
    if mode == "SIGSTORE-KEYLESS":
        sig = envelope.get("_sigstore", {})
        print(f"[sign] rekor_log_index={sig.get('rekor_log_index')}")
        print(f"[sign] certificate_fpr_sha256={sig.get('certificate_fpr_sha256')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
