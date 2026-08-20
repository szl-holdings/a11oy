#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
#
# Shared-module hash lock (IN-REPO drift guard).
#
# a11oy and killinchu deploy a small set of SHARED, BYTE-IDENTICAL source
# modules (the agent loop, the MCP client, the operator shell). The existing
# cross-repo `shared-file-drift-check.py` compares a11oy against the live
# killinchu checkout; THIS guard is the complementary IN-REPO ratchet: it pins a
# committed SHA-256 of each shared module in `.shared_module_hashes.json` and
# fails the build the moment one of them changes without the lock being
# regenerated. That makes any edit to a shared module a deliberate, reviewable
# act (regenerate the lock in the same PR) instead of a silent divergence.
#
# It does NOT modify the modules and computes nothing about their contents
# beyond a hash — additive, honest, no fabrication.
#
# Usage:
#   python3 .github/shared-module-hash-check.py            # verify (CI mode)
#   python3 .github/shared-module-hash-check.py --update   # regenerate the lock
#
# Exit 0 = in sync; exit 1 = drift (or missing file / missing lock).
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# The SHARED byte-identical modules pinned by this lock. Keep in sync with the
# COPY lists in the Dockerfile and the cross-repo shared-file-drift guard.
SHARED_MODULES = (
    "a11oy_agent_loop.py",
    "a11oy_mcp_client.py",
    "operator_shell_v4.py",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = REPO_ROOT / ".shared_module_hashes.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    missing = []
    for rel in SHARED_MODULES:
        p = REPO_ROOT / rel
        if not p.is_file():
            missing.append(rel)
            continue
        out[rel] = _sha256(p)
    if missing:
        print(f"ERROR: shared module(s) missing from the tree: {missing}", file=sys.stderr)
        sys.exit(1)
    return out


def _write_lock(hashes: dict[str, str]) -> None:
    doc = {
        "_comment": (
            "SHA-256 lock of SHARED byte-identical modules (a11oy <-> killinchu). "
            "Regenerate intentionally with: python3 .github/shared-module-hash-check.py --update"
        ),
        "algorithm": "sha256",
        "modules": dict(sorted(hashes.items())),
    }
    LOCK_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote lock for {len(hashes)} shared module(s) -> {LOCK_PATH.name}")


def _verify(current: dict[str, str]) -> int:
    if not LOCK_PATH.is_file():
        print(f"ERROR: lock file {LOCK_PATH.name} is missing. "
              f"Generate it with --update.", file=sys.stderr)
        return 1
    locked = json.loads(LOCK_PATH.read_text(encoding="utf-8")).get("modules", {})
    drift = []
    for rel, cur in current.items():
        exp = locked.get(rel)
        if exp is None:
            drift.append(f"{rel}: not in lock (add it with --update)")
        elif exp != cur:
            drift.append(f"{rel}: drifted\n    locked  = {exp}\n    current = {cur}")
    for rel in locked:
        if rel not in current:
            drift.append(f"{rel}: in lock but no longer a tracked shared module")
    if drift:
        print("SHARED MODULE DRIFT DETECTED:", file=sys.stderr)
        for d in drift:
            print(f"  - {d}", file=sys.stderr)
        print("\nThese modules are SHARED byte-identical with killinchu and must not "
              "drift silently.\nIf the change is intentional, regenerate the lock in "
              "this PR:\n  python3 .github/shared-module-hash-check.py --update\n"
              "and apply the matching edit to killinchu (cross-repo enforcement is a "
              "follow-up).", file=sys.stderr)
        return 1
    print(f"OK: {len(current)} shared module(s) match the committed lock.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Shared-module SHA-256 in-repo drift lock.")
    ap.add_argument("--update", action="store_true",
                    help="Regenerate .shared_module_hashes.json from the current tree.")
    args = ap.parse_args()
    current = _current_hashes()
    if args.update:
        _write_lock(current)
        return 0
    return _verify(current)


if __name__ == "__main__":
    sys.exit(main())
