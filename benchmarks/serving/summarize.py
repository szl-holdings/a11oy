#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Summarize evidence without hiding failed or blocked matrix cells."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    counts = Counter(cell["status"] for cell in data["results"])
    summary = {
        "_license": "SPDX-License-Identifier: Apache-2.0; (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173",
        "label": "MEASURED" if counts and set(counts) == {"MEASURED"} else "BLOCKED",
        "cell_counts": dict(sorted(counts.items())),
        "winner": None,
        "routing_change_authorized": False,
        "reason": "No routing decision is made unless every paired cell is measured and the comparison gate is separately approved.",
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
