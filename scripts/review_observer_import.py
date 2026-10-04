#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline import review: bounded stdin, stdout report, no network or file writes.

From the repository root:
  python -m scripts.review_observer_import < imported-series.json
  python -m scripts.review_observer_import --html < imported-series.json

Exit 0 means a descriptive rank was computed, not operational qualification.
Exit 2 means HOLD. The clock is always current UTC, never an input option.
"""

import argparse
from datetime import datetime, timezone
import json
import sys

from szl_observer_contract import MAX_REQUEST_BYTES, evaluate_import, render_import


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", action="store_true", help="emit a script-free, read-only report")
    arguments = parser.parse_args()
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    now = datetime.now(timezone.utc)
    report = evaluate_import(raw, clock=lambda: now)
    if arguments.html:
        # Both projections use one independently captured clock. Neither reads a
        # caller-supplied report or a caller-supplied freshness timestamp.
        output = render_import(raw, clock=lambda: now)
        # Windows redirected stdout can default to cp1252. Match the document's
        # UTF-8 declaration explicitly, without mutating a caller's locale.
        sys.stdout.buffer.write((output + "\n").encode("utf-8"))
        return 0 if report["result"]["status"] == "RANKED" else 2
    print(json.dumps(report, allow_nan=False, ensure_ascii=True, separators=(",", ":")))
    return 0 if report["result"]["status"] == "RANKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
