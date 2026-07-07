#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""
check_banned_tokens.py — robust Doctrine v7 §1 banned-token scanner.

Why this exists (the fragility it fixes)
-----------------------------------------
The banned-token gate used to live entirely inside .github/workflows/doctrine-grep.yml
as an inline bash loop. Two properties made it brittle enough to red-gate the whole
org on legitimate content:

  1. Allowlist matching was `grep -v "^${line}"` — an UNANCHORED, UNESCAPED regex
     PREFIX match, evaluated one allowlist line at a time against the file list.
       * A `.` in an allowlist path was a regex wildcard (over-matching).
       * A path was matched as a prefix of the *whole line*, so ORDERING of the
         allowlist and partial-path collisions could silently include or exclude
         the wrong files.
       * There was no notion of "this entry is a directory -> exempt everything
         under it" vs "this entry is an exact file". Directory entries only worked
         by accident of prefix-matching.
  2. There was NO self-test. Nothing proved the gate still (a) catches real
     marketing prose and (b) does NOT red-gate harvested third-party corpus text
     or line-wrapped content.

This module keeps the EXACT token semantics of the original gate (same ban-list,
same Tailwind `leading-*` suppression) so it never WEAKENS the gate — it only makes
the allowlist matching correct and adds a self-test (scripts/check_banned_tokens.test.sh).

Token policy (unchanged from doctrine-grep.yml)
-----------------------------------------------
  * BANNED tokens (case-insensitive), always flagged:
      revolutionary, unprecedented, world-class, seamless, industry-leading,
      cutting-edge, game-changing, breakthrough, best-in-class, immaculate,
      state-of-the-art, premier, Bo11y, Bolly, Jarvis, Wayne Slaughter
  * bare `leading` is flagged UNLESS the same line carries a Tailwind
      leading-{none,tight,snug,normal,relaxed,loose,N} utility class.

Allowlist (.doctrine-allowlist) — robust semantics
--------------------------------------------------
Each non-comment line is a repo-relative path. It is classified as:
  * DIRECTORY prefix if it ends with "/"  -> exempts that path and everything under it.
  * GLOB           if it contains * ? [ ] -> matched with fnmatch against each path.
  * EXACT FILE     otherwise              -> exempts exactly that one path (and, as a
                                            convenience, anything under it if it turns
                                            out to be a directory on disk).
Matching is done with os.path / fnmatch semantics on normalised POSIX paths — never
as an unescaped regex — so wraps / ordering / special characters cannot mis-classify.

Usage:
  python3 scripts/check_banned_tokens.py [--root .] [--allowlist .doctrine-allowlist]
                                         [--files-from FILE] [--report-out FILE]
Exit codes:
  0 — no banned-token hits (PASS)
  1 — one or more banned-token hits (Doctrine v7 §1 violation)
  2 — configuration / usage error
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

# --- Token policy (identical to the historical doctrine-grep.yml gate) --------
BANNED_NO_LEADING = re.compile(
    r"(revolutionary|unprecedented|world-class|seamless|industry-leading|"
    r"cutting-edge|game-changing|breakthrough|best-in-class|immaculate|"
    r"state-of-the-art|premier|Bo11y|Bolly|Jarvis|Wayne Slaughter)",
    re.IGNORECASE,
)
LEADING_RE = re.compile(r"\bleading\b", re.IGNORECASE)
TAILWIND_LEADING_RE = re.compile(
    r"leading-(none|tight|snug|normal|relaxed|loose|[0-9]+)", re.IGNORECASE
)


def norm(p: str) -> str:
    """Normalise to a POSIX repo-relative path (no leading ./, no trailing /)."""
    p = p.replace(os.sep, "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


class Allowlist:
    """Robust path allowlist parsed from .doctrine-allowlist."""

    def __init__(self, dirs, globs, files):
        self.dirs = dirs      # list of dir prefixes (no trailing slash)
        self.globs = globs    # list of fnmatch patterns
        self.files = files    # set of exact file paths

    @classmethod
    def load(cls, path: str) -> "Allowlist":
        dirs, globs, files = [], [], set()
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Strip inline comments only when clearly separated, to avoid
                    # eating '#' that is part of a path (paths with '#' are absent
                    # here, but be conservative: only split on ' #').
                    if " #" in line:
                        line = line.split(" #", 1)[0].strip()
                    if not line:
                        continue
                    ends_dir = raw.rstrip("\n").rstrip().endswith("/")
                    n = norm(line)
                    if not n:
                        continue
                    if any(ch in n for ch in "*?[]"):
                        globs.append(n)
                    elif ends_dir:
                        dirs.append(n)
                    else:
                        # Exact file OR (if it resolves to a dir on disk) a dir prefix.
                        files.add(n)
                        dirs.append(n)  # belt-and-suspenders: treat as prefix too
        return cls(dirs, globs, files)

    def is_allowed(self, rel: str) -> bool:
        rel = norm(rel)
        if rel in self.files:
            return True
        for d in self.dirs:
            if rel == d or rel.startswith(d + "/"):
                return True
        for g in self.globs:
            if fnmatch.fnmatch(rel, g):
                return True
        return False


def list_repo_files(root: str, files_from):
    if files_from:
        with open(files_from, "r", encoding="utf-8") as fh:
            return [norm(x) for x in fh.read().splitlines() if x.strip()]
    # Prefer git ls-files (tracked only); fall back to a walk.
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files"],
            check=True, capture_output=True, text=True,
        ).stdout
        return [norm(x) for x in out.splitlines() if x.strip()]
    except Exception:
        acc = []
        for dp, dirs, names in os.walk(root):
            if ".git" in dirs:
                dirs.remove(".git")
            for n in names:
                acc.append(norm(os.path.relpath(os.path.join(dp, n), root)))
        return acc


def scan_file(path: str):
    """Return list of (lineno, text) hits for one file."""
    hits = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                line = line.rstrip("\n")
                if BANNED_NO_LEADING.search(line):
                    hits.append((i, line))
                    continue
                if LEADING_RE.search(line) and not TAILWIND_LEADING_RE.search(line):
                    hits.append((i, line))
    except (IsADirectoryError, PermissionError):
        pass
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Robust Doctrine v7 §1 banned-token scanner")
    ap.add_argument("--root", default=".")
    ap.add_argument("--allowlist", default=".doctrine-allowlist")
    ap.add_argument("--files-from", default=None,
                    help="scan only paths listed in this file (e.g. a PR diff)")
    ap.add_argument("--report-out", default=None)
    args = ap.parse_args(argv)

    root = args.root
    allow = Allowlist.load(os.path.join(root, args.allowlist)
                           if not os.path.isabs(args.allowlist) else args.allowlist)
    files = list_repo_files(root, args.files_from)

    scanned = 0
    all_hits = {}  # rel -> [(lineno, text), ...]
    for rel in files:
        if allow.is_allowed(rel):
            continue
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue
        scanned += 1
        hits = scan_file(full)
        if hits:
            all_hits[rel] = hits

    total_hits = sum(len(v) for v in all_hits.values())
    print(f"Doctrine v7 §1 banned-token scan (robust): "
          f"{scanned} file(s) scanned, {total_hits} hit(s) in {len(all_hits)} file(s).")

    if args.report_out:
        with open(args.report_out, "w", encoding="utf-8") as fh:
            json.dump(
                {"scanned": scanned, "total_hits": total_hits,
                 "hits": {k: v for k, v in all_hits.items()}},
                fh, indent=2,
            )

    if total_hits:
        print("::error::Doctrine v7 §1 violation: "
              f"{total_hits} banned-token hit(s) found.")
        print("Each match below must be removed or — if it is a factual claim —")
        print("carry an adjacent citation. If the file legitimately enumerates or")
        print("verbatim-quotes third-party text (harvested corpus, KEV feed, arXiv")
        print("abstracts, ban-list docs), add its path to .doctrine-allowlist with a")
        print("reason (founder-authorized).")
        print("Hits (file:line:content):")
        for rel in sorted(all_hits):
            for ln, text in all_hits[rel]:
                snippet = text if len(text) <= 200 else text[:197] + "..."
                print(f"  {rel}:{ln}:{snippet}")
        return 1

    print("Doctrine v7 §1 — banned-token scan: PASS (0 hits).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
