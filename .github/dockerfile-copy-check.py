#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
#
# Dockerfile COPY-source guard.
#
# Parses a Dockerfile's COPY/ADD instructions and verifies that every local
# source path actually exists in the build context (the repo). This catches the
# silent drift where someone adds a `COPY foo.py ...` line but forgets to commit
# `foo.py`, so a fresh `git clone` + `docker build` dies at the first missing
# COPY (the exact failure mode that broke szl-holdings/a11oy + killinchu before
# task #205).
#
# Handling:
#   * per-file and directory COPY/ADD (shell form and JSON-array form)
#   * line continuations (trailing backslash)
#   * flag tokens (--chown=, --chmod=, --link)
#   * wildcards / globs (must match at least one path)
#   * SKIPS `COPY --from=...` (multi-stage / external-image copies — those
#     sources live in another build stage, not the repo)
#   * SKIPS remote ADD sources (http://, https://)
#
# Exit code 0 = all sources present; 1 = one or more missing (build would break).

import glob
import os
import re
import shlex
import sys


def logical_lines(text):
    """Yield Dockerfile logical instructions, joining backslash continuations."""
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        # Skip blank lines and full-line comments (only when not mid-continuation).
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        buf += line
        yield buf
        buf = ""
    if buf:
        yield buf


def parse_copy_sources(instruction):
    """
    Return (sources, skip_reason).
    sources is the list of local source paths for a COPY/ADD instruction.
    skip_reason is set (and sources empty) when the whole instruction is
    intentionally ignored (multi-stage --from, remote URL, unparseable).
    """
    m = re.match(r"^\s*(COPY|ADD)\s+(.*)$", instruction, re.IGNORECASE)
    if not m:
        return [], None
    verb = m.group(1).upper()
    rest = m.group(2).strip()

    # JSON-array (exec) form: COPY ["src", "dest"]
    if rest.startswith("["):
        try:
            import json

            tokens = json.loads(rest)
        except Exception:
            return [], "unparseable-json-array"
    else:
        try:
            tokens = shlex.split(rest)
        except Exception:
            tokens = rest.split()

    # Strip flags; bail out entirely on --from (sources are in another stage).
    real = []
    for tok in tokens:
        if tok.startswith("--from="):
            return [], "multi-stage --from"
        if tok.startswith("--"):
            continue  # --chown=, --chmod=, --link, etc.
        real.append(tok)

    if len(real) < 2:
        return [], "no-source-or-dest"

    sources = real[:-1]  # last token is the destination

    # Drop remote ADD sources (downloaded at build time, not from the repo).
    local_sources = []
    for src in sources:
        if verb == "ADD" and re.match(r"^[a-z][a-z0-9+.-]*://", src, re.IGNORECASE):
            continue
        local_sources.append(src)
    return local_sources, None


def main():
    dockerfile = sys.argv[1] if len(sys.argv) > 1 else "Dockerfile"
    root = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(dockerfile)) or "."

    if not os.path.isfile(dockerfile):
        print(f"::error::Dockerfile not found: {dockerfile}")
        return 2

    with open(dockerfile, "r", encoding="utf-8") as fh:
        text = fh.read()

    checked = 0
    missing = []
    skipped = []
    for instr in logical_lines(text):
        if not re.match(r"^\s*(COPY|ADD)\b", instr, re.IGNORECASE):
            continue
        sources, skip = parse_copy_sources(instr)
        if skip:
            skipped.append((instr.strip(), skip))
            continue
        for src in sources:
            checked += 1
            # Resolve relative to the build context root.
            path = src if os.path.isabs(src) else os.path.join(root, src)
            if any(ch in src for ch in "*?[]"):
                if not glob.glob(path):
                    missing.append((src, instr.strip()))
            elif not os.path.exists(path):
                missing.append((src, instr.strip()))

    print(f"Dockerfile: {dockerfile}")
    print(f"Build-context root: {root}")
    print(f"Checked {checked} local COPY/ADD source(s); skipped {len(skipped)}.")
    for instr, why in skipped:
        print(f"  skip ({why}): {instr}")

    if missing:
        print()
        print(f"::error::{len(missing)} COPY/ADD source(s) missing from the repo "
              f"(a fresh clone + docker build would fail):")
        for src, instr in missing:
            print(f"::error::  missing '{src}'  <-  {instr}")
        return 1

    print("OK: every COPY/ADD source exists in the repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
