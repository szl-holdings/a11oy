#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
#
# Shared-source drift guard (a11oy <-> killinchu).
#
# The a11oy and killinchu HF Docker Spaces vendor many byte-identical source
# modules (szl_dsse.py, szl_provenance.py, szl_be_hardening.py, a11oy_hf_assets.py,
# szl_live_wires.py, ...). When one repo updates such a file and the sibling is
# forgotten, the two demos silently diverge. The existing dockerfile-copy-check.py
# guard catches *missing* COPY sources; this guard catches *stale / divergent*
# shared sources.
#
# How the shared set is derived (no hand-maintained list of "what is shared"):
#   1. Parse the COPY/ADD source lists from BOTH Dockerfiles (same parser shape as
#      dockerfile-copy-check.py). Both Dockerfiles enumerate every source explicitly
#      (no `COPY . .`), so this is exact.
#   2. Expand directory sources to the files they contain (in each repo).
#   3. candidate set = a repo-relative path that is a COPY source in EITHER
#      Dockerfile AND exists as a file in BOTH repos.
#   4. Drop paths matching EXCLUDE_GLOBS (intentionally per-repo: app servers,
#      Dockerfiles, requirements, branded landing pages, build artifacts, ...).
#
# Decision (fail vs warn) uses a committed allow-list so the guard is a *ratchet*:
#   * A candidate that is byte-identical in both repos is ENFORCED — if a later
#     change diverges it (in either repo), the guard FAILS.
#   * A candidate that is *already* diverged is reported, but only FAILS the build
#     if it is NOT in the allow-list. The allow-list (.github/shared-file-drift-allow.txt)
#     seeds the currently-accepted divergences so the guard is green-on-arrival and
#     only blocks NEW drift. When an allow-listed file becomes identical again the
#     guard WARNS to remove the now-stale entry (tightening the ratchet over time).
#
# Usage:
#   shared-file-drift-check.py <selfRoot> <siblingRoot> \
#       [--self-name a11oy] [--sibling-name killinchu] [--warn-only]
#
# Exit code 0 = no un-allowed drift; 1 = un-allowed drift (build should fail);
# 2 = usage / missing-input error.

import fnmatch
import hashlib
import json
import os
import re
import shlex
import sys

# Files that legitimately differ between the two repos even though the path/name
# collides. These are app-specific or per-repo build inputs, NOT shared modules.
EXCLUDE_GLOBS = [
    "Dockerfile",
    "serve.py",            # each repo's own FastAPI entrypoint / route wiring
    "requirements.txt",    # per-repo dependency pins
    "cathedral.html",      # per-repo branded 3D landing hero
    "README.md",
    "STATUS.md",
    "CHANGELOG.md",
    "RELEASE.md",
    "CITATION.cff",
    "NOTICES.md",
    ".github/*",
    ".github/**",
    "docs/*",
    "docs/**",
    "deploy/*",
    "deploy/**",
    ".compliance/*",
    ".compliance/**",
    "live_snapshots/*",    # captured live data, refreshed per repo
    "web/*",               # per-repo console / operator HTML+JS
    "web/**",
]


# ----------------------------------------------------------------------------
# Dockerfile COPY/ADD source parsing (mirrors .github/dockerfile-copy-check.py).
# ----------------------------------------------------------------------------
def logical_lines(text):
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
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
    m = re.match(r"^\s*(COPY|ADD)\s+(.*)$", instruction, re.IGNORECASE)
    if not m:
        return []
    verb = m.group(1).upper()
    rest = m.group(2).strip()
    if rest.startswith("["):
        try:
            tokens = json.loads(rest)
        except Exception:
            return []
    else:
        try:
            tokens = shlex.split(rest)
        except Exception:
            tokens = rest.split()
    real = []
    for tok in tokens:
        if tok.startswith("--from="):
            return []  # multi-stage: sources live in another build stage
        if tok.startswith("--"):
            continue
        real.append(tok)
    if len(real) < 2:
        return []
    sources = real[:-1]
    local = []
    for src in sources:
        if verb == "ADD" and re.match(r"^[a-z][a-z0-9+.-]*://", src, re.IGNORECASE):
            continue
        local.append(src.rstrip("/") or src)
    return local


def copy_sources(root):
    """Set of COPY/ADD source paths declared in <root>/Dockerfile."""
    dockerfile = os.path.join(root, "Dockerfile")
    if not os.path.isfile(dockerfile):
        return set()
    with open(dockerfile, "r", encoding="utf-8") as fh:
        text = fh.read()
    out = set()
    for instr in logical_lines(text):
        if not re.match(r"^\s*(COPY|ADD)\b", instr, re.IGNORECASE):
            continue
        for src in parse_copy_sources(instr):
            out.add(src.lstrip("./"))
    return out


def expand_to_files(root, src):
    """Expand a COPY source (file, dir, or glob) to repo-relative file paths."""
    import glob as globmod

    path = os.path.join(root, src)
    files = []
    if any(ch in src for ch in "*?[]"):
        matches = globmod.glob(path, recursive=True)
    else:
        matches = [path]
    for m in matches:
        if os.path.isdir(m):
            for dirpath, _dirs, names in os.walk(m):
                for n in names:
                    full = os.path.join(dirpath, n)
                    files.append(os.path.relpath(full, root))
        elif os.path.isfile(m):
            files.append(os.path.relpath(m, root))
    return files


def shipped_files(root):
    """Every repo-relative file path that the Dockerfile COPY/ADDs into the image."""
    out = set()
    for src in copy_sources(root):
        for rel in expand_to_files(root, src):
            out.add(rel.replace(os.sep, "/"))
    return out


def is_excluded(rel):
    return any(fnmatch.fnmatch(rel, g) for g in EXCLUDE_GLOBS)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_allow(root):
    """Read .github/shared-file-drift-allow.txt (one path per line; # comments)."""
    p = os.path.join(root, ".github", "shared-file-drift-allow.txt")
    allow = set()
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    allow.add(line)
    return allow


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if len(args) < 2:
        print("usage: shared-file-drift-check.py <selfRoot> <siblingRoot> "
              "[--self-name N] [--sibling-name N] [--warn-only]")
        return 2
    self_root, sib_root = args[0], args[1]

    def flagval(name, default):
        for f in flags:
            if f.startswith(name + "="):
                return f.split("=", 1)[1]
        return default

    self_name = flagval("--self-name", os.path.basename(os.path.abspath(self_root)))
    sib_name = flagval("--sibling-name", os.path.basename(os.path.abspath(sib_root)))
    warn_only = "--warn-only" in flags

    if not os.path.isfile(os.path.join(self_root, "Dockerfile")):
        print(f"::error::no Dockerfile under self root {self_root}")
        return 2
    if not os.path.isfile(os.path.join(sib_root, "Dockerfile")):
        print(f"::error::no Dockerfile under sibling root {sib_root}")
        return 2

    self_ship = shipped_files(self_root)
    sib_ship = shipped_files(sib_root)
    shipped_union = self_ship | sib_ship

    # candidate = shipped by either AND present as a file in BOTH repos AND not excluded
    candidates = []
    for rel in sorted(shipped_union):
        if is_excluded(rel):
            continue
        a = os.path.join(self_root, rel)
        b = os.path.join(sib_root, rel)
        if os.path.isfile(a) and os.path.isfile(b):
            candidates.append(rel)

    allow = load_allow(self_root)

    identical, diverged = [], []
    for rel in candidates:
        ha = sha256_file(os.path.join(self_root, rel))
        hb = sha256_file(os.path.join(sib_root, rel))
        (identical if ha == hb else diverged).append(rel)

    diverged_set = set(diverged)
    blocking = [r for r in diverged if r not in allow]      # NEW / un-accepted drift
    accepted = [r for r in diverged if r in allow]          # known, allow-listed drift
    stale_allow = sorted(allow - diverged_set)              # allow entries now identical or gone

    print(f"Shared-file drift guard: {self_name} <-> {sib_name}")
    print(f"  Dockerfile-shipped files: {self_name}={len(self_ship)} "
          f"{sib_name}={len(sib_ship)}")
    print(f"  shared candidates (in both, shipped, not excluded): {len(candidates)}")
    print(f"  identical: {len(identical)}   diverged: {len(diverged)} "
          f"(accepted={len(accepted)}, blocking={len(blocking)})")
    print()

    if accepted:
        print("Accepted (allow-listed) divergences — reconcile when convenient:")
        for r in accepted:
            print(f"  ~ {r}")
        print()

    if stale_allow:
        print("::warning::allow-list entries that are NO LONGER diverged "
              "(remove them from .github/shared-file-drift-allow.txt to tighten the guard):")
        for r in stale_allow:
            print(f"::warning::  stale-allow: {r}")
        print()

    if blocking:
        print(f"::error::{len(blocking)} shared file(s) have diverged between "
              f"{self_name} and {sib_name} and are NOT allow-listed:")
        for r in blocking:
            print(f"::error::  drift: {r}  (sync the two repos, or add it to "
                  f".github/shared-file-drift-allow.txt with a reason)")
        if not warn_only:
            return 1

    print("OK: no un-allowed shared-file drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
