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
   determine direct registration, and follows literal repository-local calls
   through called top-level parent/wrapper functions. Direct registration BOTH:
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
- Only credits a top-level ``def register(`` contract. A differently named
  wrapper is followed only when statically called and its call chain reaches
  that contract; importing or defining a wrapper grants no credit.
- Only checks root-level ``*.py`` modules (surfaces live at repo root); it does
  not descend into sub-packages.
- Treats an import + a ``.register(`` attribute call OR a bare ``register(``
  (from ``from X import register``) as "wired". It does not prove the call is
  reachable at runtime (a try/except-guarded call still counts as wired — which
  is correct: the guarded block is how every a11oy surface is registered).
- Indirect traversal reads repository-local ASTs only, never imports modules,
  skips uncalled nested definitions, and is bounded to 2048 call targets.
- Dynamic invocation via getattr/importlib string names is not detected; such a
  module still needs an existing documented exemption or explicit wiring.

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
import tempfile
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


def indirect_register_calls(repo_root: Path, entrypoints: Sequence[str]) -> set[str]:
    """Follow literal repo-local calls without importing application modules.

    Only module bodies and called top-level functions contribute edges. A
    definition, import, dynamic lookup or uncalled nested handler is not a call.
    Existing direct detection is retained separately for compatibility.
    """
    root = repo_root.resolve()
    trees: dict[str, ast.Module | None] = {}
    pending: list[tuple[str, str | None]] = []
    visited: set[tuple[str, str | None]] = set()
    wired: set[str] = set()

    def scoped_nodes(nodes):
        for node in nodes:
            yield node
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef, ast.Lambda)):
                yield from scoped_nodes(ast.iter_child_nodes(node))

    def module_path(name):
        if not name or not all(part.isidentifier() for part in name.split(".")):
            return None
        base = root.joinpath(*name.split("."))
        for path in (base.with_suffix(".py"), base / "__init__.py"):
            resolved = path.resolve()
            if resolved.is_relative_to(root) and resolved.is_file():
                return resolved
        return None

    def tree_for(name):
        if name not in trees:
            path = module_path(name)
            try:
                trees[name] = (ast.parse(path.read_text(encoding="utf-8", errors="replace"))
                               if path is not None else None)
            except (OSError, SyntaxError, ValueError):
                trees[name] = None
        return trees[name]

    def bindings(nodes, inherited, module_scope=False):
        result = dict(inherited)
        shadowed = set()
        for node in scoped_nodes(nodes):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    target = (alias.name if alias.asname else bound, None)
                    result[bound] = target if bound not in result or result[bound] == target else None
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound = alias.asname or alias.name
                    child = node.module + "." + alias.name
                    target = ((child, None) if module_path(child) is not None
                              else (node.module, alias.name))
                    result[bound] = target if bound not in result or result[bound] == target else None
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                shadowed.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                result.pop(node.name, None)
                if not module_scope or isinstance(node, ast.ClassDef):
                    shadowed.add(node.name)
        for name in shadowed:
            result.pop(name, None)
        return result, shadowed

    for entrypoint in entrypoints:
        path = (root / entrypoint).resolve()
        if path.is_relative_to(root) and path.suffix == ".py":
            pending.append((".".join(path.relative_to(root).with_suffix("").parts), None))

    while pending:
        target = pending.pop()
        if target in visited:
            continue
        if len(visited) >= 2048:
            print("::warning::Indirect registration call budget exhausted; no indirect credit granted.")
            return set()
        visited.add(target)
        module, symbol = target
        tree = tree_for(module)
        if tree is None:
            continue
        functions = {node.name: node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        function = functions.get(symbol) if symbol is not None else None
        if symbol is not None and function is None:
            continue
        global_bindings, global_shadowed = bindings(tree.body, {}, module_scope=True)
        if symbol is not None and (symbol in global_shadowed or symbol in global_bindings):
            continue
        if symbol == REGISTER_FUNC:
            wired.add(module)
        body = tree.body if function is None else function.body
        aliases, shadowed = (bindings(body, global_bindings) if function is not None
                             else (global_bindings, set(global_shadowed)))
        if function is not None:
            shadowed.update(arg.arg for arg in (function.args.posonlyargs + function.args.args
                                                + function.args.kwonlyargs))
            shadowed.update(arg.arg for arg in (function.args.vararg, function.args.kwarg)
                            if arg is not None)
        for node in scoped_nodes(body):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            attributes = []
            while isinstance(callee, ast.Attribute):
                attributes.append(callee.attr)
                callee = callee.value
            if not isinstance(callee, ast.Name) or callee.id in shadowed:
                continue
            alias = aliases.get(callee.id)
            if attributes and alias is not None and alias[1] is None:
                parts = list(reversed(attributes))
                pending.append((".".join([alias[0]] + parts[:-1]), parts[-1]))
            elif not attributes and alias is not None and alias[1] is not None:
                pending.append(alias)
            elif (not attributes and callee.id in functions
                  and callee.id not in global_shadowed):
                pending.append((module, callee.id))
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
    return wired | indirect_register_calls(repo_root, entrypoints)


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

def run_indirect_tests() -> bool:
    """SAMPLE source fixtures; nothing in the fixture modules is executed."""
    sources = {
        "serve.py": "from routers import frontier as surface\nsurface.register(object())\n",
        "routers/frontier.py": (
            "def register(app):\n"
            "    from routers import service as parent\n"
            "    return parent.register(app)\n"
        ),
        "routers/service.py": (
            "def register(app):\n"
            "    from child import register_from_service as mount\n"
            "    return mount(app)\n"
        ),
        "child.py": (
            "def register(app, owner):\n    return {}\n"
            "def register_from_service(app):\n    return register(app, object())\n"
        ),
    }
    cases = [
        ("intact delegated chain", {}, True),
        ("direct module registration retained", {"serve.py": (
            "import child as surface\nsurface.register(object(), object())\n"
        )}, True),
        ("direct bare registration retained", {"serve.py": (
            "from child import register\nregister(object(), object())\n"
        )}, True),
        ("aliased registration wrapper", {"serve.py": (
            "from routers.service import register as setup\nsetup(object())\n"
        )}, True),
        ("missing parent call", {"routers/frontier.py": "def register(app):\n    return {}\n"}, False),
        ("missing terminal call", {"child.py": (
            "def register(app, owner):\n    return {}\n"
            "def register_from_service(app):\n    return {}\n"
        )}, False),
        ("imported but uncalled wrapper", {"routers/service.py": (
            "def register(app):\n"
            "    from child import register_from_service as mount\n"
            "    return {}\n"
        )}, False),
        ("uncalled entrypoint function", {"serve.py": (
            "from routers import frontier as surface\n"
            "def unused():\n    surface.register(object())\n"
        )}, False),
        ("uncalled nested terminal function", {"child.py": (
            "def register(app, owner):\n    return {}\n"
            "def register_from_service(app):\n"
            "    def unused():\n        register(app, object())\n"
            "    return {}\n"
        )}, False),
        ("dynamic lookup", {"routers/service.py": (
            "def register(app):\n    import child\n"
            "    return getattr(child, 'register_from_service')(app)\n"
        )}, False),
        ("helper cycle", {"routers/service.py": (
            "def register(app):\n    return repeat(app)\n"
            "def repeat(app):\n    return register(app)\n"
        )}, False),
        ("shadowed imported function", {"routers/service.py": (
            "from child import register_from_service as mount\n"
            "def register(app, mount=None):\n    return mount(app)\n"
        )}, False),
        ("rebound terminal definition", {"child.py": (
            "def register(app, owner):\n    return {}\n"
            "register = object()\n"
            "def register_from_service(app):\n    return register(app, object())\n"
        )}, False),
    ]
    with tempfile.TemporaryDirectory(prefix="szl-register-guard-") as temporary:
        root = Path(temporary)
        (root / "routers").mkdir()
        for description, changes, expected in cases:
            for path, source in {**sources, **changes}.items():
                (root / path).write_text(source, encoding="utf-8")
            actual = "child" in collect_wired_across_entrypoints(["serve.py"], root)
            if actual != expected:
                print(f"[SELF-TEST] FAIL: {description}: expected={expected}, actual={actual}")
                return False
            print(f"[SELF-TEST] PASS: {description}")
    return True


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
            return run_indirect_tests()
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
    print("Honest scope note: detects the top-level `def register(` contract on root-level "
          "*.py. Preserves direct entrypoint detection and follows bounded, statically "
          "called repository-local parent/wrapper functions without importing them. "
          "Unknown/dynamic targets grant no indirect credit; static wiring does not "
          "prove successful runtime initialization.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
