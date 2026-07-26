#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Reject malformed benchmark output while retaining explicit failed cells."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED = {"MEASURED", "FAILED", "BLOCKED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    if not data.get("results"):
        raise SystemExit("result set is empty")
    for index, cell in enumerate(data["results"]):
        if cell.get("status") not in ALLOWED:
            raise SystemExit(f"cell {index}: invalid status")
        if cell["status"] != "MEASURED" and not cell.get("failure"):
            raise SystemExit(f"cell {index}: failed or blocked cell lacks reason")
        if cell["status"] == "MEASURED" and cell.get("failure") is not None:
            raise SystemExit(f"cell {index}: measured cell has a failure")
    print(f"output validation passed for {len(data['results'])} retained cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
