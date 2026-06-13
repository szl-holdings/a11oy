#!/usr/bin/env python3
"""
check_infra_pointer.py — keep a11oy's infra/ directory pointer-only.

Tasks #547 and #682 removed the full vendored copies of other szl-holdings
repos from infra/ and replaced each one with a small *pointer* README that links
to the canonical repo. The only directory under infra/ that is genuinely
a11oy-original (and therefore allowed to carry real files) is
infra/receipts-samples/.

This guard fails the build if any directory under infra/ other than the
explicitly allowlisted a11oy-original dirs contains anything more than a single
pointer README.md. That is exactly how the repos silently drifted before:
a full copy of an external repo crept back in under infra/.

It is stricter than (and complements) check_infra_vendoring.py: rather than
grandfathering large vendored copies, it requires every non-allowlisted infra
dir to be pointer-only.

Usage:
  python3 scripts/check_infra_pointer.py [--infra <dir>]

Exit codes:
  0 — clean
  1 — a non-allowlisted infra dir holds more than a pointer README.md
  2 — configuration / usage error
"""

from __future__ import annotations

import argparse
import os
import sys

# Directories under infra/ that are genuinely a11oy-ORIGINAL content (not a copy
# of another szl-holdings repo) and are therefore allowed to carry real files.
#
# This allowlist is EXPLICIT and intentional. To add a new a11oy-original infra
# directory, add its name here in the same PR that introduces it, and say in the
# PR why it is a11oy-original rather than a copy of an external repo. Do NOT add
# a directory here just to silence the guard for a vendored external repo — link
# to the canonical szl-holdings/<repo> and leave a pointer README instead.
ALLOWLISTED_ORIGINAL = {
    "receipts-samples",
}

# A pointer dir may hold at most this many tracked files. A pointer is a single
# README.md, so the default is 1. Override only with a documented reason.
POINTER_MAX_FILES = int(os.environ.get("INFRA_POINTER_MAX_FILES", "1"))

# The only file a pointer directory may contain (matched case-insensitively).
POINTER_FILENAME = "readme.md"

CANONICAL_HINT = (
    "Every directory under infra/ (except the allowlisted a11oy-original dirs) "
    "must be a single pointer README.md that links to the canonical repo at "
    "https://github.com/szl-holdings/<repo>. Do NOT vendor a full copy of an "
    "external szl-holdings repo under infra/ — that is exactly the drift "
    "Tasks #547 and #682 removed."
)


def list_files(path: str) -> list[str]:
    """Return relative paths of regular files under path, ignoring .git."""
    out: list[str] = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), path)
            out.append(rel)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--infra",
        default=os.environ.get("INFRA_DIR", "infra"),
        help="path to the infra/ directory to scan (default: infra)",
    )
    args = parser.parse_args()

    infra = args.infra
    if not os.path.isdir(infra):
        # No infra/ dir is a perfectly clean state.
        print(f"[OK] no '{infra}/' directory present — nothing to check.")
        return 0

    subdirs = sorted(
        name
        for name in os.listdir(infra)
        if os.path.isdir(os.path.join(infra, name)) and name != ".git"
    )

    violations: list[str] = []
    print(f"[INFO] scanning {infra}/ ({len(subdirs)} subdirectories)")

    for name in subdirs:
        path = os.path.join(infra, name)

        if name in ALLOWLISTED_ORIGINAL:
            nfiles = len(list_files(path))
            print(
                f"[OK]   infra/{name}/ is an allowlisted a11oy-original dir "
                f"({nfiles} file(s))."
            )
            continue

        files = list_files(path)
        nfiles = len(files)

        if nfiles == 0:
            # An empty placeholder dir is harmless (not a vendored copy).
            print(f"[OK]   infra/{name}/ is empty.")
            continue

        too_many = nfiles > POINTER_MAX_FILES
        non_pointer = [f for f in files if f.lower() != POINTER_FILENAME]

        if too_many or non_pointer:
            if too_many:
                reason = (
                    f"has {nfiles} files but must be a single pointer "
                    f"README.md (<= {POINTER_MAX_FILES})"
                )
            else:
                reason = (
                    f"contains a non-pointer file: {non_pointer[0]} "
                    f"(only README.md is allowed)"
                )
            violations.append(
                f"infra/{name}/ {reason}. It looks like an external repo was "
                f"vendored here instead of being reduced to a pointer README."
            )
        else:
            print(f"[OK]   infra/{name}/ is a pointer README ({nfiles} file).")

    if violations:
        print()
        print("=" * 70)
        print("INFRA POINTER GUARD FAILED")
        print("=" * 70)
        for v in violations:
            print(f"  \u2717 {v}")
        print()
        print(CANONICAL_HINT)
        print()
        print(
            "If a directory is genuinely a11oy-original content (not a copy of "
            "an external repo), add it to ALLOWLISTED_ORIGINAL in "
            "scripts/check_infra_pointer.py in the same PR, with a note on why."
        )
        return 1

    print()
    print("[OK] infra/ is clean — every dir is a pointer or allowlisted-original.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
