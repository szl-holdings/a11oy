#!/usr/bin/env python3
"""Guarded-import liveness guard — turn silent no-op dead imports into a red gate.

THE GAP THIS CLOSES
-------------------
serve.py (and its siblings) wire optional features behind
`try: import <mod> ; <mod>.register(app) ; except Exception: print(...)`.
The doctrine "a missing dep can NEVER take down the app" makes that pattern
correct for RESILIENCE — but it also makes a BROKEN OR NEVER-CREATED feature
INVISIBLE: if `<mod>.py` does not exist, the import raises, the `except` prints
one line to stderr, and the whole feature silently does not register. No test
fails. No CI gate is red. The live endpoint just 404s forever.

This actually shipped: `serve.py` carries
  try: import a11oy_code_v4  as _code_v4 ; _code_v4.register(app, ns="a11oy")
  try: import a11oy_about_security as _abt_sec ; _abt_sec.register(app, ...)
  try: import szl_thesis_about as _thesis   ; _thesis.register(app, "a11oy")
for modules that NEVER EXISTED in git history — while nav files link
`/about/thesis`. So a user clicks a live nav link into a silent dead end, and
nothing in CI ever knew.

WHAT THIS GUARD DOES
--------------------
AST-scan the repo for guarded imports (imports lexically INSIDE a `try:` block)
of a FIRST-PARTY module (top-level name `szl_*` / `a11oy_*`). If the target
module file does not exist anywhere in the repo AND is not on the explicit
`.guarded-import-allowlist` (intentionally-optional deps, each with a reason),
the guard FAILS. A dead reference must be either (a) implemented, (b) removed,
or (c) consciously allowlisted with a one-line justification — never left as a
silent no-op.

This is the guarded-import analogue of tests/test_demo_critical_routes.py (which
guards route REGISTRATION) — here we guard that the module the registration
depends on actually EXISTS.

Pure stdlib. Exit 0 = clean; 1 = at least one un-allowlisted dead guarded import.
"""
from __future__ import annotations

import ast
import os
import sys

ALLOWLIST_FILE = ".guarded-import-allowlist"
FIRST_PARTY_PREFIXES = ("szl_", "a11oy_")
SKIP_DIRS = {".git", ".lake", "node_modules", "dist", "build", "__pycache__",
             "organs"}  # organs/ are retired-codename snapshots, scanned in their own repos


def _repo_local_modules(root: str) -> set[str]:
    """Every importable first-party top-level module name present in the repo."""
    mods: set[str] = set()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn.endswith(".py"):
                mods.add(os.path.splitext(fn)[0])
        # package dirs (with __init__.py) are importable by their dir name
        if "__init__.py" in fns:
            mods.add(os.path.basename(dp))
    return mods


def _guarded_import_targets(path: str):
    """Yield (module_top, lineno) for every import lexically inside a try-block."""
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="ignore").read(), path)
    except Exception:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        # only the `body` of the try (the guarded part), not the handlers/else
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Import):
                    for a in sub.names:
                        yield a.name.split(".")[0], sub.lineno
                elif isinstance(sub, ast.ImportFrom) and sub.module and sub.level == 0:
                    yield sub.module.split(".")[0], sub.lineno


def load_allowlist(root: str) -> set[str]:
    p = os.path.join(root, ALLOWLIST_FILE)
    allow: set[str] = set()
    if not os.path.exists(p):
        return allow
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # format: "<module>  # reason"
        allow.add(line.split("#", 1)[0].strip())
    return allow


def scan(root: str):
    """Return sorted list of (path, lineno, module) dead guarded imports."""
    local = _repo_local_modules(root)
    allow = load_allowlist(root)
    dead = set()
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dp, fn)
            for mod, ln in _guarded_import_targets(path):
                if not mod.startswith(FIRST_PARTY_PREFIXES):
                    continue
                if mod in local or mod in allow:
                    continue
                dead.add((os.path.relpath(path, root), ln, mod))
    return sorted(dead)


def main(argv=None) -> int:
    root = (argv or sys.argv[1:] or ["."])[0]
    dead = scan(root)
    if dead:
        for path, ln, mod in dead:
            print(f"::error file={path},line={ln}::guarded import of "
                  f"first-party module '{mod}' that does NOT exist in the repo "
                  f"and is not allowlisted — silent no-op dead feature. "
                  f"Implement it, remove the import, or allowlist it in "
                  f"{ALLOWLIST_FILE} with a reason.")
        print(f"::error::{len(dead)} dead guarded import(s) found "
              f"(silent-no-op feature regressions).")
        return 1
    print("Guarded-import liveness OK — no silent no-op dead first-party imports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
