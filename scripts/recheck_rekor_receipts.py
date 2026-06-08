#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""Continuously re-verify previously-published governance receipts against Rekor.

Issue #195 — long-term audit value.

`scripts/verify_dsse_real.py` verifies a *freshly-signed* envelope inside the
same CI job that minted it. That proves signing works at mint-time, but says
nothing about whether the receipts published weeks or months ago still verify
against the public Sigstore trust root + Rekor transparency log today.

This script is the ongoing monitor: it walks every published DSSE envelope under
a directory (default: attestations/governance/), and for each REAL
(`_mode: SIGSTORE-KEYLESS`) envelope it re-runs the same independent
verification used at mint-time (`szl_formulas.verify_dsse_real`) — Fulcio cert
chain + Rekor inclusion proof + DSSE signature, pinned to the signer identity
(the GitHub Actions workflow SAN) and OIDC issuer.

HONESTY
  - Verification is performed entirely from the bundle embedded in each file plus
    the public Sigstore trust root — no private key, no org secret.
  - PLACEHOLDER envelopes are NOT real signatures; they are reported and skipped
    (they are not failures, they were never claimed to be verifiable).
  - Any envelope that no longer verifies is a LOUD failure (non-zero exit), so a
    scheduled workflow turns red and an alert is raised.
  - This does NOT change the SLSA claim (still L1). It re-checks signatures only.

Exit codes:
  0  every real receipt re-verified (or there were none to check)
  1  at least one real receipt FAILED to re-verify
  2  usage / environment error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_SIGSTORE_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
_REAL_MODE = "SIGSTORE-KEYLESS"
_PLACEHOLDER_MODE = "PLACEHOLDER"


def _default_identity() -> str:
    """The signer identity used by dsse-receipts.yml on the default branch.

    Published governance receipts are minted by `.github/workflows/dsse-receipts.yml`
    on `refs/heads/main`, so that workflow SAN is the expected certificate identity.
    Derived from $GITHUB_REPOSITORY when available so a fork verifies against its
    own signer.
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "szl-holdings/a11oy")
    return (
        f"https://github.com/{repo}/.github/workflows/dsse-receipts.yml"
        "@refs/heads/main"
    )


def _verify_one(envelope: dict, *, identity: str, issuer: str) -> dict:
    """Re-verify a single envelope. Import is lazy so PLACEHOLDER-only runs and
    --help don't require the sigstore SDK to be installed."""
    from szl_formulas import verify_dsse_real  # noqa: WPS433 (lazy by design)

    return verify_dsse_real(envelope, identity=identity, issuer=issuer)


def recheck_dir(
    receipts_dir: Path,
    *,
    identity: str,
    issuer: str,
) -> dict:
    """Walk *.dsse.json under receipts_dir and re-verify each real receipt.

    Returns a JSON-serialisable summary. Each envelope may carry its own
    `_signer_identity` / `_signer_issuer` (written at publish time); when present
    those take precedence over the CLI defaults so receipts signed from a
    different ref/workflow still verify against the identity that actually
    produced them.
    """
    results: list[dict] = []
    files = sorted(receipts_dir.glob("*.dsse.json")) if receipts_dir.exists() else []

    for path in files:
        entry: dict = {"file": path.name}
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - unreadable receipt is a failure
            entry.update(status="FAIL", reason=f"unreadable envelope: {exc}")
            results.append(entry)
            continue

        mode = envelope.get("_mode", "?")
        entry["mode"] = mode

        if mode == _PLACEHOLDER_MODE:
            entry.update(status="SKIP", reason="placeholder (not a real signature)")
            results.append(entry)
            continue
        if mode != _REAL_MODE:
            entry.update(status="SKIP", reason=f"unknown mode '{mode}' — nothing to verify")
            results.append(entry)
            continue

        want_identity = envelope.get("_signer_identity") or identity
        want_issuer = envelope.get("_signer_issuer") or issuer
        entry["identity"] = want_identity
        sig = envelope.get("_sigstore") or {}
        entry["rekor_log_index"] = sig.get("rekor_log_index")

        try:
            result = _verify_one(envelope, identity=want_identity, issuer=want_issuer)
        except Exception as exc:  # noqa: BLE001 - ANY failure must be loud
            entry.update(status="FAIL", reason=str(exc))
            results.append(entry)
            continue

        entry.update(
            status="PASS",
            payloadType=result.get("payloadType"),
            certificate_fpr_sha256=result.get("certificate_fpr_sha256"),
        )
        results.append(entry)

    summary = {
        "directory": str(receipts_dir),
        "checked": len(files),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "skipped": sum(1 for r in results if r["status"] == "SKIP"),
        "results": results,
    }
    return summary


def _print_summary(summary: dict) -> None:
    print(f"[recheck] directory: {summary['directory']}")
    print(
        f"[recheck] {summary['checked']} envelope(s): "
        f"{summary['passed']} verified, {summary['failed']} FAILED, "
        f"{summary['skipped']} skipped"
    )
    for r in summary["results"]:
        tag = {"PASS": "✔", "FAIL": "✗", "SKIP": "·"}.get(r["status"], "?")
        line = f"  {tag} {r['status']:4} {r['file']}"
        if r.get("rekor_log_index") is not None:
            line += f"  rekor#{r['rekor_log_index']}"
        if r.get("reason"):
            line += f"  ({r['reason']})"
        print(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dir",
        default=str(REPO_ROOT / "attestations" / "governance"),
        help="directory of published *.dsse.json receipts to re-verify",
    )
    ap.add_argument(
        "--identity",
        default=_default_identity(),
        help="expected certificate SAN (the dsse-receipts.yml workflow on main)",
    )
    ap.add_argument(
        "--issuer",
        default=_SIGSTORE_OIDC_ISSUER,
        help="expected OIDC issuer (default: GitHub Actions)",
    )
    ap.add_argument(
        "--summary-out",
        default=None,
        help="optional path to write the JSON summary to (for status surfacing)",
    )
    args = ap.parse_args(argv)

    receipts_dir = Path(args.dir)
    summary = recheck_dir(receipts_dir, identity=args.identity, issuer=args.issuer)
    _print_summary(summary)

    if args.summary_out:
        out = Path(args.summary_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[recheck] wrote summary: {out}")

    if summary["checked"] == 0:
        print(
            "[recheck] no published receipts found yet — nothing to re-verify "
            "(not a failure)."
        )
        return 0
    if summary["failed"] > 0:
        print(
            f"[recheck] FAILURE: {summary['failed']} published receipt(s) no "
            "longer verify against Rekor.",
            file=sys.stderr,
        )
        return 1
    print("[recheck] OK: all published real receipts still verify against Rekor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
