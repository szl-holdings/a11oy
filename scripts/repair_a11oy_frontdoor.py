#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed admission check for the reviewed A11oy front-door successor.

The former anchor-by-anchor repair program targeted the pre-v3 landing page. The
Living Command Fabric is now a separately reviewed successor and must not be
rewritten through stale literals. This operator therefore accepts only the
explicitly versioned successor and delegates its truth/mobile contract to the
independent checker. Anything else stops for review rather than guessing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_a11oy_frontdoor_truth import check as check_truth_contract


REVIEWED_SUCCESSOR_MARKERS = (
    'data-szl-shell-owner="homepage"',
    'data-szl-public-experience-v3="true"',
    'data-szl-living-command-fabric-v1="true"',
    '<title>a11oy — The Living Command Fabric</title>',
    '<meta name="description" content="One governed intelligence fabric',
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    text = args.path.read_text(encoding="utf-8")
    missing = [marker for marker in REVIEWED_SUCCESSOR_MARKERS if marker not in text]
    truth = check_truth_contract(args.path)

    if missing or truth.get("status") != "PASS":
        print(
            json.dumps(
                {
                    "status": "BLOCKED_DRIFT",
                    "target": str(args.path),
                    "missing_reviewed_successor_markers": missing,
                    "truth_contract": truth,
                    "notes": (
                        "The legacy literal rewriter is retired for the v3 homepage; "
                        "unrecognized pages require a reviewed migration rather than "
                        "an automatic best-effort rewrite."
                    ),
                },
                indent=2,
            )
        )
        return 2

    output = args.output
    if output is not None and output != args.path:
        output.write_text(text, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "target": str(args.path),
                "output": str(output or args.path),
                "state": "REVIEWED_SUCCESSOR",
                "changed": False,
                "truth_contract": truth,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
