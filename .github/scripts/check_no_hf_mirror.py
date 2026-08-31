#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guard: no stale `.hf-mirror/` snapshot directories may be committed.

`.hf-mirror/` directories were one-off frozen snapshots of an organ's HF Space
serve.py / retrieval.py, ingested during a bulk consolidation. They are not the
canonical source (that is `organs/<organ>/serve.py` etc.), nothing imports or
COPYs them, and leaving them in the tree invites drift between a dead snapshot
and the live code. This checker fails CI if any such directory returns.

Usage:
    check_no_hf_mirror.py [ROOT]   # ROOT defaults to the repo root (".")

Exit 0 = clean (no `.hf-mirror/` directories). Exit 1 = at least one found.
"""
import os
import sys

MIRROR_DIRNAME = ".hf-mirror"


def find_mirror_dirs(root: str) -> list[str]:
    hits: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        # never descend into VCS metadata
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if MIRROR_DIRNAME in dirnames:
            hits.append(os.path.join(dirpath, MIRROR_DIRNAME))
    return sorted(hits)


def main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "."
    hits = find_mirror_dirs(root)
    if hits:
        print("FAIL: stale `.hf-mirror/` snapshot directories are committed:")
        for h in hits:
            print(f"  - {os.path.relpath(h, root)}")
        print(
            "\nThese are dead HF-Space snapshots, not canonical source. "
            "Delete them; the live code lives at organs/<organ>/serve.py etc."
        )
        return 1
    print("OK: no `.hf-mirror/` snapshot directories committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
