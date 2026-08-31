#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Prepare a local evidence bundle; public publication requires authorization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    raw = args.results.read_bytes()
    receipt = {
        "_license": "SPDX-License-Identifier: Apache-2.0; (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173",
        "label": "PREPARED IN A PR",
        "publication_authorized": False,
        "artifact": str(args.results.as_posix()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
