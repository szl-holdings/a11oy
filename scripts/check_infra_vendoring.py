#!/usr/bin/env python3
"""
check_infra_vendoring.py — guard against re-vendoring external szl-holdings
repos under infra/.

Task #547 reduced the vendored deployment repos (infra/uds-deployment,
infra/uds-mesh, infra/uds-bundles) to small *pointer* READMEs because the full
vendored copies were drifting from canonical and re-introducing stale guidance.
This guard stops that from silently coming back:

  1. The three pointer dirs MUST stay pointer-only (a README that links to the
     canonical repo, not a full mirror of it).
  2. No brand-new full-repo copy may be vendored under infra/ — link to the
     canonical szl-holdings/<repo> instead of copying its tree in.

It is intentionally additive: it does not fire on the existing legitimate
pointer READMEs, nor on the vendored copies that already existed when the guard
was added (allowlisted below and FROZEN — do not grow the allowlist; vendor
nothing new).

Usage:
  python3 scripts/check_infra_vendoring.py [--infra <dir>]

Exit codes:
  0 — clean
  1 — a re-vendored pointer dir or a new vendored repo copy was detected
  2 — configuration / usage error
"""

from __future__ import annotations

import argparse
import os
import sys

# Dirs that Task #547 reduced to pointers. They must contain only a small
# pointer README, never a re-vendored full repo tree.
POINTER_DIRS = {"uds-deployment", "uds-mesh", "uds-bundles"}

# A pointer dir may hold at most this many tracked files (README.md plus an
# optional note). Anything more means someone re-vendored the repo.
POINTER_MAX_FILES = int(os.environ.get("INFRA_POINTER_MAX_FILES", "2"))

# Vendored copies that already existed when this guard was introduced. They are
# FROZEN: do NOT add new entries here. The whole point of the guard is to stop
# the set of vendored copies from growing — link to the canonical repo instead.
ALLOWLISTED_VENDORED = {
    "build-env",
    "fleet-overlay",
    "hatun-mcp",
    "khipu-consensus",
    "lake",
    "lambda-bounty",
    "receipts-samples",
    "szl-mesh",
    "vsp-otel",
    "vsp_otel",
}

# A non-pointer, non-allowlisted dir holding more than this many files looks
# like a freshly vendored external repo rather than a pointer.
MAX_FILES = int(os.environ.get("INFRA_VENDOR_MAX_FILES", "10"))

# Tell-tale signs that a directory is a whole repo copy rather than a pointer,
# even if it slips under the file-count threshold.
REPO_ROOT_MARKERS = (
    os.path.join(".github", "workflows"),
    "uds-bundle.yaml",
    "lakefile.lean",
    "lean-toolchain",
)

CANONICAL_HINT = (
    "Do NOT vendor a full copy of an external szl-holdings repo under infra/. "
    "Link to the canonical repo (https://github.com/szl-holdings/<repo>) and, "
    "if a placeholder is needed, leave only a small pointer README — exactly as "
    "Task #547 did for uds-deployment / uds-mesh / uds-bundles."
)


def count_files(path: str) -> int:
    """Count regular files under path, ignoring any nested .git metadata."""
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git"]
        total += len(files)
    return total


def has_repo_marker(path: str) -> str | None:
    for marker in REPO_ROOT_MARKERS:
        if os.path.exists(os.path.join(path, marker)):
            return marker
    return None


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
        nfiles = count_files(path)

        if name in POINTER_DIRS:
            if nfiles > POINTER_MAX_FILES:
                violations.append(
                    f"infra/{name}/ has {nfiles} files but must stay a POINTER "
                    f"(<= {POINTER_MAX_FILES}). It looks like the canonical repo "
                    f"was re-vendored here. Task #547 deliberately reduced this "
                    f"to a pointer README — keep it that way."
                )
            else:
                print(f"[OK]   infra/{name}/ is a pointer ({nfiles} file(s)).")
            continue

        if name in ALLOWLISTED_VENDORED:
            print(
                f"[OK]   infra/{name}/ is an allowlisted (frozen) vendored copy "
                f"({nfiles} files)."
            )
            continue

        # Brand-new directory: must not be a full vendored repo copy.
        marker = has_repo_marker(path)
        if nfiles > MAX_FILES or marker is not None:
            reason = (
                f"{nfiles} files (> {MAX_FILES})"
                if nfiles > MAX_FILES
                else f"contains repo-root marker '{marker}'"
            )
            violations.append(
                f"infra/{name}/ looks like a newly vendored external repo "
                f"({reason})."
            )
        else:
            print(
                f"[OK]   infra/{name}/ is small ({nfiles} files) — treated as a "
                f"pointer/new placeholder."
            )

    if violations:
        print()
        print("=" * 70)
        print("INFRA VENDORING GUARD FAILED")
        print("=" * 70)
        for v in violations:
            print(f"  ✗ {v}")
        print()
        print(CANONICAL_HINT)
        print()
        print(
            "If a directory is a legitimate, intentional exception, discuss it "
            "first — do not silently add it to ALLOWLISTED_VENDORED in "
            "scripts/check_infra_vendoring.py."
        )
        return 1

    print()
    print("[OK] infra/ is clean — no re-vendored pointers, no new repo copies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
