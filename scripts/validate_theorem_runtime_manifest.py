#!/usr/bin/env python3
"""Validate the A11oy theorem-to-runtime manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path.cwd()
MANIFEST = REPO_ROOT / "docs" / "theorem-runtime-manifest.json"
VALID_STATUSES = {
    "verified-runtime",
    "lean-backed-current-green",
    "lean-backed-needs-upstream-ci",
    "lean-backed-needs-runtime",
    "historical-roadmap",
    "roadmap",
    # staged-advisory: honest, NOT-proven status (SZL Doctrine v11). The gate
    # ships enforced:false/severity:warning while its Lean proof is pending, so
    # it must never be counted as proven. Honesty semantics enforced below.
    "staged-advisory",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args()
    path = Path(args.manifest)
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []

    seen = set()
    for entry in data.get("entries", []):
        entry_id = entry.get("id")
        if not entry_id:
            errors.append("entry missing id")
            continue
        if entry_id in seen:
            errors.append(f"duplicate entry id: {entry_id}")
        seen.add(entry_id)

        status = entry.get("claimStatus")
        if status not in VALID_STATUSES:
            errors.append(f"{entry_id}: invalid claimStatus {status}")

        for field in ["runtimeFile", "exportFile", "testFile"]:
            value = entry.get(field)
            if value and not (REPO_ROOT / value).exists():
                errors.append(f"{entry_id}: missing {field} path {value}")

        if status == "verified-runtime" and not entry.get("validationCommand"):
            errors.append(f"{entry_id}: verified-runtime requires validationCommand")

        if status == "staged-advisory":
            # Honesty guard (SZL Doctrine v11): staged-advisory entries are NOT
            # proven. They must self-identify as advisory and carry a caveat so
            # they can never be silently promoted into a proven claim.
            if entry.get("stagedAdvisory") is not True:
                errors.append(
                    f"{entry_id}: staged-advisory requires stagedAdvisory: true"
                )
            if not entry.get("caveat"):
                errors.append(
                    f"{entry_id}: staged-advisory requires a caveat"
                )
            if entry.get("leanStatus") in {"proven", "verified", "lean-proven"}:
                errors.append(
                    f"{entry_id}: staged-advisory cannot have leanStatus "
                    f"{entry.get('leanStatus')!r} (not yet proven)"
                )

    if errors:
        print("Theorem runtime manifest failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Theorem runtime manifest OK: {len(seen)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
