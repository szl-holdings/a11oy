#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""UNSIGNED-honest relock receipt for the CURRENT product tip SHA.

The historical 95-probe (bda66daa / run 34424414138) does not cover a later
tip. Lyte three-plane MATCH at dd17d9f is observational equality, not a
signed relock. This script never mints DSSE as product signer and never
stamps LIVE/RUNNING/PASS.

Identity is /api/a11oy/v1/honest git_sha. Doctrine v11 LOCKED kernel pin
c7c0ba17 is the doctrine lock, NOT the Space deploy SHA.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN = frozenset({"LIVE", "RUNNING", "PASS"})
DOCTRINE_KERNEL_PIN = "c7c0ba17"
HISTORICAL_95_PROBE_SHA = "bda66daa67aaa2c7bd9a94bb43537f22bc6c89d7"
HISTORICAL_95_PROBE_RUN = "34424414138"
LYTE_OBSERVATIONAL_SHA = "dd17d9f524b76c8f0e260d7ec1e084cc079dfc43"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def build_relock_receipt(
    git_sha: str,
    *,
    observed_at: str | None = None,
    origin_source_json: str = "undeclared",
) -> dict[str, Any]:
    sha = str(git_sha or "").strip().lower()
    if _SHA40.fullmatch(sha) is None:
        raise ValueError(f"git_sha is not a 40-hex SHA: {git_sha!r}")
    if sha == HISTORICAL_95_PROBE_SHA:
        raise ValueError(
            "refusing to reuse the historical 95-probe SHA as a current-tip relock"
        )
    first_paint = "OBSERVED"
    status = "UNSIGNED-honest"
    if first_paint in FORBIDDEN or status in FORBIDDEN:
        raise RuntimeError("refusing LIVE/RUNNING/PASS on relock receipt")
    return {
        "schema": "szl.current-tip-relock/v1",
        "kind": "UNSIGNED-honest observational relock",
        "git_sha": sha,
        "identity": "/api/a11oy/v1/honest git_sha",
        "origin": "https://a-11-oy.com",
        "repository": "szl-holdings/a11oy",
        "observed_at": observed_at or _now_iso(),
        "doctrine": "v11",
        "doctrine_lock": {
            "doctrine": "v11",
            "state": "LOCKED",
            "commit": DOCTRINE_KERNEL_PIN,
            "note": (
                "Doctrine v11 LOCKED kernel pin. This is the doctrine lock, "
                "NOT the Space deploy SHA."
            ),
        },
        "signer": "ABSENT",
        "signer_honesty": "UNSIGNED-honest",
        "certified": False,
        "proven_trust": False,
        "publication_eligible": False,
        "first_paint": first_paint,
        "status": status,
        "receipt_minted": False,
        "dsse": None,
        "signed_relock": False,
        "origin_source_json": origin_source_json,
        "historical_95_probe": {
            "git_sha": HISTORICAL_95_PROBE_SHA,
            "run": HISTORICAL_95_PROBE_RUN,
            "covers_current_tip": False,
            "note": (
                "95 passed endpoint probes plus five intentionally unexecuted "
                "state-changing probes at bda66daa / run 34424414138. Historical "
                "evidence only. Does not cover the current tip. Five unexecuted "
                "probes are not passes."
            ),
        },
        "lyte_three_plane": {
            "sha": LYTE_OBSERVATIONAL_SHA,
            "kind": "observational equality",
            "signed_relock": False,
            "note": (
                "Lyte three-plane MATCH at dd17d9f is observational equality, "
                "not a signed relock."
            ),
        },
        "limits": [
            "This receipt is UNSIGNED-honest. No persistent product-signer key verifies it.",
            "Do not stamp LIVE, RUNNING, or PASS.",
            "Do not mint DSSE as product signer.",
            "Do not reuse the 95-probe receipt for a later tip.",
            "Lyte three-plane MATCH is not a signed relock of a11oy.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit an UNSIGNED-honest relock receipt for the current tip SHA."
    )
    parser.add_argument("--git-sha", required=True, help="Current tip SHA (40-hex)")
    parser.add_argument(
        "--out",
        type=Path,
        help="Write JSON to this path (stdout if omitted)",
    )
    parser.add_argument(
        "--origin-source-json",
        default="undeclared",
        help="Origin GET /.well-known/source.json observation (default: undeclared)",
    )
    args = parser.parse_args(argv)
    try:
        receipt = build_relock_receipt(
            args.git_sha,
            origin_source_json=args.origin_source_json,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
