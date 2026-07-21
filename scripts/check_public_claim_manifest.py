#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed CLI for an explicit EvidenceOS public-claim manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from szl_public_claim_manifest import (
    PublicClaimContractError,
    evaluate_public_claim_manifest,
    strict_json_loads,
)


MAX_MANIFEST_BYTES = 256 * 1024


def load_manifest(path: Path):
    if not path.is_file():
        raise PublicClaimContractError("manifest is missing")
    with path.open("rb") as handle:
        content = handle.read(MAX_MANIFEST_BYTES + 1)
    if len(content) > MAX_MANIFEST_BYTES:
        raise PublicClaimContractError(
            f"manifest exceeds the {MAX_MANIFEST_BYTES}-byte limit"
        )
    return strict_json_loads(content.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repository-root", default=".", type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        report = evaluate_public_claim_manifest(
            manifest,
            as_of=args.as_of,
            repository_root=args.repository_root,
        )
    except (OSError, UnicodeError, PublicClaimContractError) as exc:
        print(f"public-claim manifest: REFUSE ({exc})", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(
        "public-claim manifest: "
        f"{report['outcome']} claims={report['claim_count']} "
        f"current={report['freshness_counts']['CURRENT']} "
        f"digest={report['receipt']['content_sha256']}"
    )
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
