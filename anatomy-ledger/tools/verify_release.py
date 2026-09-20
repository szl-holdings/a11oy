#!/usr/bin/env python3
"""Verify a released Anatomy artifact with gh attestation verify.

Exit non-zero on failure. Never convert a failed verification into REVIEW
or ALLOW. The written JSON is the only source of verified=true for ingest.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys

UTC = dt.timezone.utc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--output",
        default="anatomy-ledger/evidence/verified/github-verification.json",
    )
    args = parser.parse_args()

    artifact = pathlib.Path(args.artifact).resolve()
    if not artifact.exists():
        print(f"Artifact does not exist: {artifact}", file=sys.stderr)
        return 2
    if shutil.which("gh") is None:
        print("gh CLI is unavailable; cannot verify attestations", file=sys.stderr)
        return 2

    result = subprocess.run(
        [
            "gh",
            "attestation",
            "verify",
            str(artifact),
            "--repo",
            args.repo,
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout or "attestation verify failed", file=sys.stderr)
        return result.returncode or 1

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"gh attestation verify returned non-JSON: {exc}", file=sys.stderr)
        return 1

    verification = {
        "verified": True,
        "verifier": "gh attestation verify",
        "repository": args.repo,
        "artifact": str(artifact),
        "verifiedAt": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "result": payload,
        "disclosure": (
            "verified=true is set only because gh attestation verify exited 0. "
            "Do not copy this flag onto unsigned envelopes."
        ),
    }
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
