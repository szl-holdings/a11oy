#!/usr/bin/env python3
"""Canonical Lean corpus counter for szl-holdings/lutar-lean.

Trust Tier 1 reproducibility script (TRUST.md TODO). Clones (or reads) the
lutar-lean repo at its current `main` HEAD and emits a single canonical JSON of
declaration / axiom / sorry counts so that public surfaces stop drifting.

The methods here are *fixed and documented* so any agent or reviewer gets the
same numbers from the same SHA. This file is the source of truth for the
"Live numbers" line, replacing hand-maintained figures.

Usage:
  python lean_numbers.py --repo-path /path/to/lutar-lean [--out lean_numbers.json]
  python lean_numbers.py --clone --out .github/data/lean_numbers.json

Counting methods (documented, stable):
  - declarations: lines in Lutar/ and Main.lean whose initial token is one of
    {theorem, lemma, def, abbrev, instance, structure, inductive, class},
    optionally preceded by the `noncomputable` and/or `private` modifier.
  - axioms_raw: lines whose initial token is `axiom` (after optional modifiers).
  - axioms_unique: distinct axiom names among those.
  - sorries_raw: total `\\bsorry\\b` token occurrences across all .lean files.
  - sorries_noncomment: occurrences excluding lines that are pure line-comments
    (leading `--`) — i.e. `sorry` that is live proof text.
  - sorries_putnam / sorries_baseline: split by whether the file is under Putnam/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

LUTAR_LEAN_URL = "https://github.com/szl-holdings/lutar-lean.git"

# Experimental scopes that are NOT part of the LOCKED Doctrine v11 baseline
# (749 declarations / 14 unique axioms / 163 sorries).
#
# These directories host additive, experimental work that is explicitly NOT
# folded into the v11 numbers cited verbatim across 32+ repos, the org README,
# every /healthz surface, and the published Ouroboros Thesis v20. The proofs in
# them are real and valuable; they are simply staged for a future planned
# Doctrine v12 release (see platform/docs/doctrine/v12-roadmap.md) rather than
# counted against the locked v11 baseline.
#
# Path fragments are matched os.sep-bounded against each .lean file path. To
# graduate a scope into the baseline, remove it here in the SAME PR that bumps
# .github/data/lean_numbers.json (an explicit, reviewable Doctrine release).
EXPERIMENTAL_SCOPES = (
    # PURIQ-OS agentic formula pack (Ouroboros Thesis v21) — 5 PROVED + 18 open.
    os.path.join("Lutar", "Puriq", "Formulas") + os.sep,
    # Bekenstein-bound scaffold (additive, Putnam) — 1 proved anchor + tracking sorry.
    os.path.join("Lutar", "Putnam", "BekensteinBound.lean"),
)


def _is_experimental(path: str) -> bool:
    """True if `path` lives in an experimental scope excluded from the v11 baseline.

    `path` is a repo-relative path (e.g. 'Lutar/Puriq/Formulas/X.lean'). A scope
    ending in os.sep is a directory prefix; otherwise it is an exact file.
    """
    norm = os.path.normpath(path)
    for scope in EXPERIMENTAL_SCOPES:
        if scope.endswith(os.sep):
            if (norm + os.sep).startswith(scope):
                return True
        elif norm == os.path.normpath(scope):
            return True
    return False

DECL_RE = re.compile(
    r"^(?:private\s+)?(?:noncomputable\s+)?(?:private\s+)?"
    r"(theorem|lemma|def|abbrev|instance|structure|inductive|class)\b"
)
AXIOM_RE = re.compile(r"^(?:private\s+)?axiom\s+([A-Za-z_][A-Za-z0-9_']*)")
SORRY_RE = re.compile(r"\bsorry\b")
COMMENT_LINE_RE = re.compile(r"^\s*--")


def iter_lean_files(root: str):
    base = os.path.join(root, "Lutar")
    for dirpath, _dirs, files in os.walk(base):
        for fn in files:
            if fn.endswith(".lean"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                # Skip experimental scopes — they do not roll into v11 numbers.
                if _is_experimental(rel):
                    continue
                yield full
    main = os.path.join(root, "Main.lean")
    if os.path.exists(main):
        yield main


def count(root: str) -> dict:
    declarations = 0
    axioms_raw = 0
    axiom_names: set[str] = set()
    sorries_raw = 0
    sorries_noncomment = 0
    sorries_putnam = 0
    sorries_baseline = 0

    for path in iter_lean_files(root):
        is_putnam = f"{os.sep}Putnam{os.sep}" in path
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if DECL_RE.match(line):
                    declarations += 1
                m = AXIOM_RE.match(line)
                if m:
                    axioms_raw += 1
                    axiom_names.add(m.group(1))
                hits = len(SORRY_RE.findall(line))
                if hits:
                    sorries_raw += hits
                    if not COMMENT_LINE_RE.match(line):
                        sorries_noncomment += hits
                    if is_putnam:
                        sorries_putnam += hits
                    else:
                        sorries_baseline += hits

    return {
        "declarations": declarations,
        "axioms_raw": axioms_raw,
        "axioms_unique": len(axiom_names),
        "axiom_names": sorted(axiom_names),
        "sorries_raw": sorries_raw,
        "sorries_noncomment": sorries_noncomment,
        "sorries_putnam": sorries_putnam,
        "sorries_baseline": sorries_baseline,
    }


def git_head_sha(root: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", root, "rev-parse", "HEAD"], text=True
        ).strip()
        return out
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Canonical lutar-lean corpus counter.")
    ap.add_argument("--repo-path", help="Path to an existing lutar-lean checkout.")
    ap.add_argument("--clone", action="store_true", help="Shallow-clone main first.")
    ap.add_argument("--ref", default="main", help="Branch/SHA to count (with --clone).")
    ap.add_argument("--out", help="Write JSON here (default: stdout).")
    args = ap.parse_args()

    tmp = None
    repo_path = args.repo_path
    if args.clone or not repo_path:
        tmp = tempfile.mkdtemp(prefix="lutar-lean-")
        subprocess.check_call(
            ["git", "clone", "--depth", "1", "--branch", args.ref, LUTAR_LEAN_URL, tmp]
        )
        repo_path = tmp

    if not os.path.isdir(os.path.join(repo_path, "Lutar")):
        print(f"error: {repo_path} has no Lutar/ directory", file=sys.stderr)
        return 2

    sha = git_head_sha(repo_path)
    numbers = count(repo_path)
    payload = {
        "schema": "szl.lean_numbers/v1",
        "repo": "szl-holdings/lutar-lean",
        "ref": args.ref,
        "sha": sha,
        "measured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "see .github/scripts/lean_numbers.py docstring (fixed grep-equivalent regexes)",
        "numbers": numbers,
    }

    out_json = json.dumps(payload, indent=2) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json)
        print(f"wrote {args.out} @ {sha}")
    else:
        sys.stdout.write(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
