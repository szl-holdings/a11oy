#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Validate that paired engine cells share the same controlled environment."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for result in data["results"]:
        groups[(result["workload"], result["repetition"])].append(result)
    errors = []
    for key, cells in groups.items():
        if {cell["engine"] for cell in cells} != {"vllm", "sglang"}:
            errors.append(f"{key}: paired engines missing")
        controlled = {
            (cell["model_revision"], cell["tokenizer_revision"], cell["environment_digest"])
            for cell in cells
        }
        if len(controlled) != 1:
            errors.append(f"{key}: environment drift")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"fairness validation passed for {len(groups)} paired cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
