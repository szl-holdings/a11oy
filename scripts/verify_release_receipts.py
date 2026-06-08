#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""Re-verify governance + Khipu DSSE receipts published as GitHub RELEASE ASSETS.

Issue #241. `rekor-recheck.yml` (issue #195) continuously re-verifies the
governance receipts persisted on the `governance-receipts` ledger branch. This is
its release-asset counterpart: the deploy/release pipelines also upload the signed
governance + Khipu-ingest DSSE envelopes as assets on the GitHub release, and
downstream consumers fetch THOSE assets — so they need a way to re-verify them long
after the run, against the public Sigstore/Rekor trust root, with no org secret.

A receipt envelope uploaded to a release may have been signed by any of several
producing workflows (release.yml, slsa.yml, zarf-build-and-sign.yml,
dsse-receipts.yml). Each mints its own Fulcio certificate whose SAN is the calling
workflow's ref, so there is no single fixed identity to pin. Instead, for each real
envelope this tool reads the signer SAN from the embedded Fulcio certificate and
PINS it: the SAN must name one of the allowed receipt-producing workflows in this
repository (at a tag or branch ref). It then re-derives trust via
`szl_formulas.verify_dsse_real()` against that exact SAN — the same independent
verification (Fulcio cert chain + Rekor inclusion proof + DSSE signature) used by
`scripts/verify_dsse_real.py` at mint time.

HONESTY
  - Verification is performed entirely from the bundle embedded in each asset plus
    the public Sigstore trust root — no private key, no org secret.
  - A published release receipt is supposed to carry a GENUINE signature (the
    signing scripts REFUSE to ship a placeholder in CI). A PLACEHOLDER or any
    non-real envelope found among the assets is therefore reported as UNVERIFIABLE
    and FAILS the run — it is never silently passed.
  - An envelope whose signer SAN is not one of the allowed producing workflows in
    this repo is a LOUD failure (an unexpected signer), even if the bundle itself
    is internally consistent.
  - Any envelope that no longer verifies is a LOUD failure (non-zero exit).
  - This does NOT change the SLSA claim (still L1). It re-checks signatures only.

Exit codes:
  0  every real release receipt re-verified (or there were none to check)
  1  at least one published receipt FAILED to re-verify or is UNVERIFIABLE
  2  usage / environment error
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_SIGSTORE_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
_REAL_MODE = "SIGSTORE-KEYLESS"
_PLACEHOLDER_MODE = "PLACEHOLDER"

# Workflows that legitimately mint + publish governance / Khipu receipt assets.
# The signer SAN of every published release receipt must name one of these.
_DEFAULT_PRODUCER_WORKFLOWS = (
    "release.yml",
    "slsa.yml",
    "zarf-build-and-sign.yml",
    "dsse-receipts.yml",
)


def _default_repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "szl-holdings/a11oy")


def _leaf_cert_der(bundle_json: dict) -> bytes:
    """Return the DER bytes of the leaf signing certificate from a Sigstore bundle.

    Handles both bundle media-type shapes: the v0.3 single `certificate` field and
    the older `x509CertificateChain.certificates[]` list.
    """
    vm = (bundle_json or {}).get("verificationMaterial") or {}
    cert = vm.get("certificate")
    if isinstance(cert, dict) and cert.get("rawBytes"):
        return base64.b64decode(cert["rawBytes"])
    chain = (vm.get("x509CertificateChain") or {}).get("certificates") or []
    if chain and isinstance(chain[0], dict) and chain[0].get("rawBytes"):
        return base64.b64decode(chain[0]["rawBytes"])
    raise ValueError("bundle has no leaf certificate (verificationMaterial.certificate)")


def _signer_san(bundle_json: dict) -> str:
    """Extract the SAN URI (the GitHub Actions workflow identity) from the cert."""
    from cryptography import x509  # lazy: only needed for real envelopes

    der = _leaf_cert_der(bundle_json)
    cert = x509.load_der_x509_certificate(der)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    uris = san.get_values_for_type(x509.UniformResourceIdentifier)
    if not uris:
        raise ValueError("certificate SAN has no URI (not a workflow OIDC identity)")
    return uris[0]


def san_is_allowed_producer(
    san: str, *, repo: str, allowed_workflows: tuple[str, ...]
) -> bool:
    """True iff `san` names an allowed receipt-producing workflow in `repo`.

    A GitHub Actions Fulcio SAN looks like:
        https://github.com/<owner>/<repo>/.github/workflows/<wf>.yml@<ref>
    We pin the repository and the producing workflow (the part that establishes
    WHO signed). The ref must be a tag or branch ref of that repo.
    """
    prefix = f"https://github.com/{repo}/.github/workflows/"
    if not san.startswith(prefix):
        return False
    rest = san[len(prefix):]
    if "@" not in rest:
        return False
    workflow, ref = rest.split("@", 1)
    if workflow not in allowed_workflows:
        return False
    return ref.startswith("refs/tags/") or ref.startswith("refs/heads/")


def _verify_real(envelope: dict, *, identity: str, issuer: str) -> dict:
    from szl_formulas import verify_dsse_real  # lazy: avoids SDK import for --help

    return verify_dsse_real(envelope, identity=identity, issuer=issuer)


def verify_one(
    envelope: dict,
    *,
    repo: str,
    allowed_workflows: tuple[str, ...],
    issuer: str,
) -> dict:
    """Verify a single envelope dict. Returns a result entry (never raises)."""
    entry: dict = {}
    mode = envelope.get("_mode", "?")
    entry["mode"] = mode

    if mode != _REAL_MODE:
        # PLACEHOLDER or any non-real mode: a published release receipt must be
        # genuinely signed, so this is unverifiable — reported, never a soft pass.
        reason = (
            "placeholder signature (not authenticated)"
            if mode == _PLACEHOLDER_MODE
            else f"non-real mode '{mode}'"
        )
        entry.update(status="UNVERIFIABLE", reason=reason)
        return entry

    bundle = (envelope.get("_sigstore") or {}).get("bundle")
    if not bundle:
        entry.update(status="FAIL", reason="real mode but no _sigstore.bundle present")
        return entry

    try:
        san = _signer_san(bundle)
    except Exception as exc:  # noqa: BLE001 - an unreadable cert is a failure
        entry.update(status="FAIL", reason=f"could not read signer identity: {exc}")
        return entry

    entry["signer_identity"] = san
    if not san_is_allowed_producer(san, repo=repo, allowed_workflows=allowed_workflows):
        entry.update(
            status="FAIL",
            reason=(
                f"unexpected signer '{san}' — not an allowed receipt-producing "
                f"workflow in {repo}"
            ),
        )
        return entry

    sig = envelope.get("_sigstore") or {}
    entry["rekor_log_index"] = sig.get("rekor_log_index")
    try:
        result = _verify_real(envelope, identity=san, issuer=issuer)
    except Exception as exc:  # noqa: BLE001 - ANY verification failure must be loud
        entry.update(status="FAIL", reason=str(exc))
        return entry

    entry.update(
        status="PASS",
        payloadType=result.get("payloadType"),
        certificate_fpr_sha256=result.get("certificate_fpr_sha256"),
    )
    return entry


def verify_dir(
    receipts_dir: Path,
    *,
    repo: str,
    allowed_workflows: tuple[str, ...],
    issuer: str,
) -> dict:
    """Walk *.dsse.json under receipts_dir and verify each as a release asset."""
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
        entry.update(
            verify_one(
                envelope, repo=repo, allowed_workflows=allowed_workflows, issuer=issuer
            )
        )
        results.append(entry)

    summary = {
        "directory": str(receipts_dir),
        "repo": repo,
        "allowed_workflows": list(allowed_workflows),
        "checked": len(files),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "unverifiable": sum(1 for r in results if r["status"] == "UNVERIFIABLE"),
        "results": results,
    }
    return summary


def _print_summary(summary: dict) -> None:
    print(f"[release-verify] directory: {summary['directory']}")
    print(f"[release-verify] repo: {summary['repo']}")
    print(
        f"[release-verify] {summary['checked']} asset(s): "
        f"{summary['passed']} verified, {summary['failed']} FAILED, "
        f"{summary['unverifiable']} UNVERIFIABLE"
    )
    for r in summary["results"]:
        tag = {"PASS": "✔", "FAIL": "✗", "UNVERIFIABLE": "✗"}.get(r["status"], "?")
        line = f"  {tag} {r['status']:12} {r['file']}"
        if r.get("rekor_log_index") is not None:
            line += f"  rekor#{r['rekor_log_index']}"
        if r.get("signer_identity"):
            line += f"  signer={r['signer_identity']}"
        if r.get("reason"):
            line += f"  ({r['reason']})"
        print(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dir",
        required=True,
        help="directory of downloaded release *.dsse.json receipt assets",
    )
    ap.add_argument(
        "--repo",
        default=_default_repo(),
        help="owner/repo whose workflows are allowed signers (default: $GITHUB_REPOSITORY)",
    )
    ap.add_argument(
        "--allow-workflow",
        action="append",
        default=None,
        help=(
            "workflow file name permitted to sign published receipts "
            "(repeatable; default: the known receipt-producing workflows)"
        ),
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

    allowed = tuple(args.allow_workflow) if args.allow_workflow else _DEFAULT_PRODUCER_WORKFLOWS

    receipts_dir = Path(args.dir)
    summary = verify_dir(
        receipts_dir, repo=args.repo, allowed_workflows=allowed, issuer=args.issuer
    )
    _print_summary(summary)

    if args.summary_out:
        out = Path(args.summary_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[release-verify] wrote summary: {out}")

    if summary["checked"] == 0:
        print(
            "[release-verify] no published receipt assets found on this release — "
            "nothing to re-verify (not a failure)."
        )
        return 0
    bad = summary["failed"] + summary["unverifiable"]
    if bad > 0:
        print(
            f"[release-verify] FAILURE: {summary['failed']} failed + "
            f"{summary['unverifiable']} unverifiable published receipt(s).",
            file=sys.stderr,
        )
        return 1
    print("[release-verify] OK: all published release receipts still verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
