#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v13
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
.github/scripts/register_invocation.py
========================================
CI REGISTER-INVOCATION GUARD — root-cause fix for the recurring DEAD-TAB
pattern in szl-holdings/a11oy where a module is COPY'd into the image and
DEFINES a top-level ``def register(app, ...)`` (the a11oy surface-wiring
contract), but serve.py NEVER imports+calls it — so the surface's live routes
are silently absent (404) even though the module ships, the Dockerfile COPY's
it, and its own unit test (which calls register() on a fresh app) stays GREEN.

This is the INVERSE of the existing COPY-completeness guard:

  * copy_completeness.py  checks:  imported  ⇒  COPY'd
                                   (module used by serve.py is in the image)
  * THIS guard           checks:  COPY'd-register  ⇒  called
                                   (module that DEFINES register() is actually
                                    imported AND register() is invoked in serve.py)

Both the 18 killinchu dead tabs AND the Counter-UAS dead tab
(szl_counter_uas_proxy.py — COPY'd, defines register(), never called in
serve.py → all 5 /api/a11oy/v1/counter-uas/* endpoints 404 live) died from
EXACTLY this inverse gap. The unit test calls register() on a throwaway app so
it is green while the live route is missing — which is precisely why a STATIC
serve.py check (not a unit test) is the only thing that catches this class.

WHAT THIS SCRIPT DOES
---------------------
1. Scans the repo root for every ``<module>.py`` that defines a TOP-LEVEL
   ``def register(`` function (the a11oy surface-registration contract). Uses
   ast.parse so decorators / async / multi-line signatures are all handled;
   only module-level (not nested / not class-method) ``register`` counts.

2. Parses each entrypoint (serve.py + the other serve entrypoints) with ast to
   determine, for every register-defining module, whether serve.py BOTH:
       (a) imports the module  (import X / import X as Y / from X import ...),
           AND
       (b) invokes ``<module>.register(`` (or ``<alias>.register(``, or the
           bare ``register(`` brought in via ``from X import register``).

3. Honors an explicit, DOCUMENTED allow-list (--allowlist, default
   .github/register-invocation-allowlist.txt) of modules that intentionally
   define register() but are NOT wired into serve.py (e.g. registered by a
   different entrypoint, a library helper, or a deliberately-dark surface).
   Each allow-list entry REQUIRES a reason on the same line so the exemption is
   auditable and never silent.

4. FAILS (exit 1) if any register-defining module is neither wired into an
   entrypoint NOR present in the allow-list.

5. PASSES (exit 0) and prints an auditable summary (wired / allow-listed /
   entrypoints scanned).

HONEST SCOPE / LIMITATIONS (printed on success so CI logs are auditable)
- Only detects the top-level ``def register(`` contract by name. A surface that
  wires itself under a differently-named function is not covered (by design —
  the whole repo uses ``register`` as the contract).
- Only checks root-level ``*.py`` modules (surfaces live at repo root); it does
  not descend into sub-packages.
- Treats an import + a ``.register(`` attribute call OR a bare ``register(``
  (from ``from X import register``) as "wired". It does not prove the call is
  reachable at runtime (a try/except-guarded call still counts as wired — which
  is correct: the guarded block is how every a11oy surface is registered).
- Dynamic invocation via getattr/importlib string names is not detected; such a
  module must be allow-listed with a reason.

USAGE
-----
  python3 .github/scripts/register_invocation.py \
      --root . \
      --entrypoints serve.py wayra_serve.py ayni_os_serve.py kipu_qillqaq_serve.py \
      --allowlist .github/register-invocation-allowlist.txt

  # Self-test: verify the guard CATCHES an unwired register() (no false negative)
  python3 .github/scripts/register_invocation.py --missing-test

EXIT CODES
  0 — every register-defining module is wired into an entrypoint OR allow-listed
  1 — one or more register-defining modules are unwired AND not allow-listed
  2 — usage / IO error

DOCTRINE NOTE
-------------
No-bandaid, root-cause fix for the dead-tab class. Rather than re-discovering an
unwired surface after it 404s in production (the Counter-UAS + 18-killinchu-tab
failures), this guard catches the omission in CI before it ever deploys.
Apache-2.0 — SZL Holdings 2026.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Sequence

REGISTER_FUNC = "register"


# ---------------------------------------------------------------------------
# STEP 1 — find every root module that DEFINES a top-level def register(
# ---------------------------------------------------------------------------

def module_defines_register(py_path: Path) -> bool:
    """True iff the file defines a MODULE-LEVEL ``def register(`` (sync or async)."""
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return False
    for node in tree.body:  # module-level only (not nested / not class methods)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == REGISTER_FUNC:
            return True
    return False


def find_register_modules(repo_root: Path, entrypoints: Sequence[str]) -> set[str]:
    """
    Return the set of root-level module NAMES (no .py) that define a top-level
    register(). Entrypoints themselves are excluded (they are the callers, not
    surfaces — an entrypoint that happens to define register() is not a wiring
    target of itself).
    """
    ep_stems = {Path(ep).stem for ep in entrypoints}
    modules: set[str] = set()
    for py in sorted(repo_root.glob("*.py")):
        name = py.stem
        if name in ep_stems:
            continue
        if module_defines_register(py):
            modules.add(name)
    return modules


# ---------------------------------------------------------------------------
# STEP 2 — determine which register-modules an entrypoint IMPORTS + CALLS
# ---------------------------------------------------------------------------

def wired_modules_in_entrypoint(source: str) -> set[str]:
    """
    Parse an entrypoint and return the set of module names that are BOTH
    imported AND have their register() invoked.

    A module ``m`` is considered wired if:
      * ``import m`` (optionally ``as alias``) OR ``from m import register``
        appears, AND
      * a call to ``<m>.register(...)`` OR ``<alias>.register(...)`` OR a bare
        ``register(...)`` (only credited to modules that did
        ``from m import register``) appears.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    # alias name -> real module name  (e.g. _szl_cuas -> szl_cuas_formulas)
    alias_to_module: dict[str, str] = {}
    # modules that did `from <mod> import register` (bare register() credits them)
    from_import_register: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                bound = alias.asname or mod
                alias_to_module[bound] = mod
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                mod = node.module.split(".")[0]
                for alias in node.names:
                    if alias.name == REGISTER_FUNC:
                        from_import_register.add(mod)

    # Collect every attribute call `<something>.register(` and bare `register(`
    called_attr_bases: set[str] = set()  # the `<something>` bound-name
    bare_register_called = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == REGISTER_FUNC:
                if isinstance(fn.value, ast.Name):
                    called_attr_bases.add(fn.value.id)
            elif isinstance(fn, ast.Name) and fn.id == REGISTER_FUNC:
                bare_register_called = True

    wired: set[str] = set()
    # attribute-call path: alias.register(...) → resolve alias to module
    for base in called_attr_bases:
        mod = alias_to_module.get(base)
        if mod:
            wired.add(mod)
    # bare register() path: only credit modules that `from m import register`
    if bare_register_called:
        wired |= from_import_register

    return wired


def collect_wired_across_entrypoints(
    entrypoints: Sequence[str], repo_root: Path
) -> set[str]:
    wired: set[str] = set()
    for ep in entrypoints:
        ep_path = Path(ep) if Path(ep).is_absolute() else repo_root / ep
        if not ep_path.exists():
            print(f"::warning::Entrypoint not found: {ep_path} — skipping")
            continue
        wired |= wired_modules_in_entrypoint(
            ep_path.read_text(encoding="utf-8", errors="replace")
        )
    return wired


# ---------------------------------------------------------------------------
# ALLOW-LIST (documented intentional exemptions — reason REQUIRED)
# ---------------------------------------------------------------------------

def load_allowlist(path: Path) -> dict[str, str]:
    """
    Parse the allow-list file. Format (one per line):
        module_name   # reason it is intentionally not wired in serve.py
    Blank lines and full-line `#` comments are ignored. A reason (text after
    `#`) is REQUIRED — an entry with no reason is rejected (exit 2) so no
    exemption is ever silent.
    Returns { module_name: reason }.
    """
    allow: dict[str, str] = {}
    if not path.exists():
        return allow
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" not in line:
            print(f"::error::Allow-list line {lineno} has NO reason (a reason after "
                  f"'#' is REQUIRED so every exemption is auditable): {raw!r}")
            raise SystemExit(2)
        mod, reason = line.split("#", 1)
        mod = mod.strip()
        reason = reason.strip()
        if not mod or not reason:
            print(f"::error::Allow-list line {lineno} is malformed "
                  f"(need 'module  # reason'): {raw!r}")
            raise SystemExit(2)
        allow[mod] = reason
    return allow


# ---------------------------------------------------------------------------
# SELF-TEST — verify the guard CATCHES an unwired register() (no false negative)
# ---------------------------------------------------------------------------

def run_missing_test(repo_root: Path) -> bool:
    print("\n[SELF-TEST] Verifying guard catches an UNWIRED register()...")
    dummy_name = "test_guard_dummy_register_module"
    dummy = repo_root / f"{dummy_name}.py"
    dummy.write_text(
        "def register(app, ns='a11oy'):\n"
        "    # synthetic surface — deliberately NOT wired into serve.py\n"
        "    return {'registered': []}\n"
    )
    try:
        register_mods = find_register_modules(repo_root, ["serve.py"])
        assert dummy_name in register_mods, "guard failed to DETECT the register() def"
        wired = collect_wired_across_entrypoints(["serve.py"], repo_root)
        # dummy is NOT imported/called anywhere and NOT allow-listed
        unwired = register_mods - wired
        if dummy_name in unwired:
            print(f"[SELF-TEST] PASS: guard correctly flagged unwired '{dummy_name}'")
            return True
        print(f"[SELF-TEST] FAIL: guard did NOT flag '{dummy_name}' — false negative!")
        return False
    finally:
        dummy.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CI register-invocation guard: every module defining a top-level "
                    "register() must be imported+called in an entrypoint OR allow-listed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--root", default=".", help="Repo root (default: .)")
    parser.add_argument(
        "--entrypoints", nargs="+",
        default=["serve.py"],
        help="Entrypoint file(s) that wire surfaces (default: serve.py).",
    )
    parser.add_argument(
        "--allowlist",
        default=".github/register-invocation-allowlist.txt",
        help="Path to the documented exemption allow-list "
             "(default: .github/register-invocation-allowlist.txt).",
    )
    parser.add_argument(
        "--missing-test", action="store_true",
        help="Run built-in self-test: verify guard catches an unwired register().",
    )
    args = parser.parse_args(argv)

    repo_root = Path(os.path.abspath(args.root))

    if args.missing_test:
        return 0 if run_missing_test(repo_root) else 1

    allow_path = (
        Path(args.allowlist) if os.path.isabs(args.allowlist)
        else repo_root / args.allowlist
    )
    allow = load_allowlist(allow_path)

    print(f"[register-invocation] Repo root  : {repo_root}")
    print(f"[register-invocation] Entrypoints: {args.entrypoints}")
    print(f"[register-invocation] Allow-list : {allow_path} ({len(allow)} entry/entries)")
    print()

    register_mods = find_register_modules(repo_root, args.entrypoints)
    wired = collect_wired_across_entrypoints(args.entrypoints, repo_root)

    print(f"[register-invocation] Modules defining top-level register() : {len(register_mods)}")
    print(f"[register-invocation] Of those, wired into an entrypoint    : {len(register_mods & wired)}")
    print()

    unwired = sorted(register_mods - wired)
    allowed_unwired = [m for m in unwired if m in allow]
    violating = [m for m in unwired if m not in allow]

    if allowed_unwired:
        print(f"ALLOW-LISTED ({len(allowed_unwired)} intentional exemption(s)):")
        for m in allowed_unwired:
            print(f"  [EXEMPT] {m}.py — {allow[m]}")
        print()

    # Warn about stale allow-list entries (module now wired, or gone) so the
    # allow-list never rots into a rubber stamp.
    stale = [m for m in allow if m not in unwired]
    if stale:
        for m in stale:
            if m not in register_mods:
                print(f"::warning::Allow-list entry '{m}' no longer defines register() "
                      f"(module renamed/removed?) — prune it from the allow-list.")
            else:
                print(f"::warning::Allow-list entry '{m}' is NOW wired into an entrypoint "
                      f"— prune it from the allow-list (exemption no longer needed).")
        print()

    if violating:
        print(f"::error::{len(violating)} module(s) define a top-level register() but are "
              f"NEVER imported+called in any entrypoint AND are NOT allow-listed "
              f"(this is the DEAD-TAB class: the surface ships + COPY's + its unit test "
              f"is green, but its live routes 404):")
        for m in violating:
            print(f"::error::  UNWIRED: {m}.py  "
                  f"(defines register(); not called in {args.entrypoints}; not allow-listed)")
        print()
        print("FIX (choose one):")
        print("  1. Wire it: add a guarded block to serve.py, e.g.:")
        for m in violating:
            print(f"       try:\n"
                  f"           import {m} as _{m}\n"
                  f"           _{m}.register(app, ns=\"a11oy\")\n"
                  f"       except Exception as _e:  # pragma: no cover\n"
                  f"           print(f\"[a11oy] {m} NOT registered: {{_e!r}}\", file=__import__('sys').stderr)")
        print(f"  2. If intentionally NOT wired, add it to {allow_path} with a reason:")
        for m in violating:
            print(f"       {m}   # <why this register() is intentionally not wired>")
        print()
        print("[register-invocation] RESULT: FAIL — wire the surface or allow-list it with a reason.")
        return 1

    print("[register-invocation] RESULT: PASS — every module defining a top-level "
          "register() is wired into an entrypoint or documented in the allow-list.")
    print()
    print("Honest scope note: detects the top-level `def register(` contract by name on "
          "root-level *.py, and credits a module as wired when an entrypoint both imports "
          "it and invokes <module>.register( (or a bare register() from `from m import "
          "register`). Dynamic getattr/importlib wiring must be allow-listed with a reason.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
