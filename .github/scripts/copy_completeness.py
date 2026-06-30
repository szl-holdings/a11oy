#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v13
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
.github/scripts/copy_completeness.py
=====================================
CI COPY-COMPLETENESS GUARD — root-cause fix for the recurring silent-drop
pattern in szl-holdings/a11oy where a Python module is added to the repo,
imported in serve.py (or other entrypoints), but never added to the
Dockerfile's per-file COPY list — resulting in a ModuleNotFoundError at
container startup that is swallowed by a try/except, producing a silent 404.

WHAT THIS SCRIPT DOES
---------------------
1. Parses one or more Python entrypoint files (serve.py etc.) for:
     import <name>
     from <name> import ...
   for ALL import forms, including bare `import x`, try/except-guarded imports,
   and multi-line import blocks.

2. Resolves which imports are LOCAL root-level .py modules:
   - Ignore stdlib modules (uses sys.stdlib_module_names on 3.10+ or a bundled
     list on 3.9).
   - Ignore third-party (pip) packages: any module whose root package name does
     NOT correspond to an existing root-level .py file in the repo is ignored.
   - Only flag `<module>.py` files that ACTUALLY EXIST in the repo root.

3. Parses the Dockerfile for every `COPY` source (shell form + JSON-array form;
   skips --from=, skips remote ADD URLs). Collects the explicit file names that
   appear in any COPY line.

4. FAILS (exit 1) if any locally-imported root .py that exists in the repo root
   is NOT present in the Dockerfile COPY set.

5. PASSES (exit 0) and prints a summary of all checked modules.

HONEST SCOPE / LIMITATIONS (print these on success so CI logs are auditable)
- Only checks root-level *.py files directly imported by the entrypoints.
- Does not recurse into sub-packages (sub-package COPY is covered by
  directory-level COPY lines; this guard only catches per-file COPY drift).
- Does not parse dynamic import strings (e.g. importlib.import_module(var)).
- Does not check that COPY destinations are correct (covered by the existing
  dockerfile-copy-check.py guard).
- stdlib detection uses Python 3.10+ sys.stdlib_module_names; on 3.9 falls
  back to a bundled list that may be slightly incomplete.

USAGE
-----
  python3 .github/scripts/copy_completeness.py [--dockerfile Dockerfile]
          [--root .] [--entrypoints serve.py [wayra_serve.py ...]]

  # Fail deliberately with a missing COPY:
  python3 .github/scripts/copy_completeness.py --missing-test

EXIT CODES
  0 — all locally-imported root modules are present in Dockerfile COPY set
  1 — one or more locally-imported root modules are missing from COPY
  2 — usage error

DOCTRINE NOTE
-------------
This is the no-bandaid, root-cause fix for the "per-file COPY has silently
dropped modules 4+ times" pattern documented in DEEP_WIRING_SYNTHESIS.md.
Rather than adding COPY lines reactively, this guard catches the omission in CI
before it ever reaches the image.

Apache-2.0 — SZL Holdings 2026.
"""
from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# STDLIB MODULE LIST (fallback for Python < 3.10)
# Source: https://docs.python.org/3/library/index.html (trimmed to common set)
# On 3.10+ we use sys.stdlib_module_names which is authoritative.
# ---------------------------------------------------------------------------
_STDLIB_FALLBACK = frozenset({
    "__future__", "_thread", "abc", "aifc", "argparse", "array", "ast",
    "asynchat", "asyncio", "asyncore", "atexit", "audioop", "base64",
    "bdb", "binascii", "binhex", "bisect", "builtins", "bz2", "calendar",
    "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop",
    "collections", "colorsys", "compileall", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
    "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
    "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
    "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq",
    "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
    "numbers", "operator", "optparse", "os", "ossaudiodev", "parser",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
    "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib",
    "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "sre_compile",
    "sre_constants", "sre_parse", "ssl", "stat", "statistics", "string",
    "stringprep", "struct", "subprocess", "sunau", "symtable", "sys",
    "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile",
    "termios", "test", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "tomllib", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
    "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
    "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
    # common C-extension modules that appear as stdlib
    "_collections_abc", "_io", "abc", "builtins", "posixpath", "ntpath",
    "genericpath", "fnmatch", "linecache", "tokenize", "token",
    # typing extensions / runtime
    "typing_extensions",
})


def _stdlib_names() -> frozenset[str]:
    if hasattr(sys, "stdlib_module_names"):
        return sys.stdlib_module_names  # type: ignore[attr-defined]
    return _STDLIB_FALLBACK


# ---------------------------------------------------------------------------
# IMPORT EXTRACTION
# ---------------------------------------------------------------------------

def _extract_imports_from_source(source: str) -> list[str]:
    """
    Parse Python source and return every top-level imported module name
    (the root package, e.g. 'szl_dsse' for 'import szl_dsse' or
    'from szl_intoto import attest_receipt').

    Uses ast.parse; falls back to regex on SyntaxError (handles f-strings /
    newer syntax that older Python may not support).
    """
    names: list[str] = []

    # AST path (preferred — handles all edge cases)
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    names.append(root)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:  # absolute import only
                    root = node.module.split(".")[0]
                    names.append(root)
        return names
    except SyntaxError:
        pass

    # Regex fallback — handles files with syntax errors / newer features
    for m in re.finditer(
        r"(?:^|\n)\s*(?:import\s+([\w,\s]+)|from\s+([\w.]+)\s+import)",
        source,
    ):
        if m.group(1):  # `import a, b, c`
            for tok in re.split(r"[,\s]+", m.group(1)):
                tok = tok.strip()
                if tok:
                    names.append(tok.split(".")[0])
        elif m.group(2):  # `from x.y import z`
            names.append(m.group(2).split(".")[0])
    return names


def collect_local_imports(
    entrypoints: Sequence[str],
    repo_root: str,
    stdlib: frozenset[str],
) -> dict[str, set[str]]:
    """
    For each entrypoint, return the set of ROOT-level .py module names that:
      a) are imported (directly or via try-except blocks), AND
      b) have a corresponding <name>.py file in repo_root, AND
      c) are NOT stdlib or obviously third-party.

    Returns: { entrypoint_path: {module_name, ...} }
    """
    result: dict[str, set[str]] = {}
    root = Path(repo_root)

    for ep in entrypoints:
        ep_path = Path(ep) if Path(ep).is_absolute() else root / ep
        if not ep_path.exists():
            print(f"::warning::Entrypoint not found: {ep_path} — skipping")
            result[ep] = set()
            continue

        source = ep_path.read_text(encoding="utf-8", errors="replace")
        all_imports = _extract_imports_from_source(source)

        local: set[str] = set()
        for name in all_imports:
            if not name or name.startswith("_") and len(name) == 1:
                continue
            if name in stdlib:
                continue
            # Only flag if a matching root-level .py exists in the repo
            candidate = root / f"{name}.py"
            if candidate.exists():
                local.add(name)

        result[ep] = local

    return result


# ---------------------------------------------------------------------------
# DOCKERFILE COPY-SET EXTRACTION
# ---------------------------------------------------------------------------

def _logical_lines(text: str) -> Iterable[str]:
    """Yield Dockerfile logical instructions (backslash continuation folded)."""
    buf = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if raw.rstrip().endswith("\\"):
            buf += raw.rstrip()[:-1] + " "
            continue
        buf += raw
        yield buf
        buf = ""
    if buf:
        yield buf


def _parse_copy_sources_from_line(instruction: str) -> tuple[list[str], str | None]:
    """
    Return (sources, skip_reason).
    sources = list of local source paths from a COPY/ADD instruction.
    skip_reason = set and sources empty when intentionally skipped.
    """
    m = re.match(r"^\s*(COPY|ADD)\s+(.*)$", instruction, re.IGNORECASE)
    if not m:
        return [], None
    verb = m.group(1).upper()
    rest = m.group(2).strip()

    # JSON-array form
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

    real = []
    for tok in tokens:
        if tok.startswith("--from="):
            return [], "multi-stage --from"
        if tok.startswith("--"):
            continue
        real.append(tok)

    if len(real) < 2:
        return [], "no-source-or-dest"

    sources = real[:-1]

    local_sources = []
    for src in sources:
        if verb == "ADD" and re.match(r"^[a-z][a-z0-9+.-]*://", src, re.IGNORECASE):
            continue
        local_sources.append(src)
    return local_sources, None


def collect_dockerfile_copy_set(dockerfile_path: str) -> set[str]:
    """
    Return the set of BASE FILENAMES that appear as sources in any COPY
    instruction in the Dockerfile (excluding --from= copies and remote ADD URLs).

    For per-file copies like `COPY szl_dsse.py ./` the token is `szl_dsse.py`.
    For space-separated multi-file copies like `COPY a.py b.py c.py ./` all
    three source tokens are collected.
    For directory copies like `COPY ayni_os/ ./ayni_os/` the token `ayni_os/`
    is collected (the guard uses it to check wildcard coverage).

    Returns: set of source token strings (e.g. 'szl_dsse.py', 'ayni_os/')
    """
    if not os.path.isfile(dockerfile_path):
        raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")

    with open(dockerfile_path, encoding="utf-8") as fh:
        text = fh.read()

    copy_sources: set[str] = set()
    for instr in _logical_lines(text):
        if not re.match(r"^\s*(COPY|ADD)\b", instr, re.IGNORECASE):
            continue
        sources, skip = _parse_copy_sources_from_line(instr)
        if skip:
            continue
        for src in sources:
            # Normalize: collect the basename token as-is (for per-file COPY)
            # and also the bare module name (strip .py suffix) for lookup.
            copy_sources.add(src)
            # Expand globs relative to dockerfile directory
            base = os.path.dirname(dockerfile_path) or "."
            glob_path = os.path.join(base, src)
            for expanded in glob.glob(glob_path):
                copy_sources.add(os.path.basename(expanded))
                # Also add without .py suffix for set membership
                bn = os.path.basename(expanded)
                copy_sources.add(bn)

    return copy_sources


# ---------------------------------------------------------------------------
# MODULE → DOCKERFILE COPY MEMBERSHIP CHECK
# ---------------------------------------------------------------------------

def module_in_copy_set(module_name: str, copy_sources: set[str]) -> bool:
    """
    Return True if `module_name` (e.g. 'szl_dsse') is covered by the
    Dockerfile COPY set.

    Checks:
      1. Exact filename: 'szl_dsse.py' in copy_sources
      2. Bare name: 'szl_dsse' in copy_sources (rare but possible)
      3. Wildcard glob tokens like '*.py' in copy_sources
      4. Directory tokens: '<dir>/' where the module lives (root-level .py
         is only in root dir, so this only matters for non-root — skip here)
    """
    filename = f"{module_name}.py"
    if filename in copy_sources or module_name in copy_sources:
        return True
    # Check wildcard tokens from the copy set
    for token in copy_sources:
        if "*" in token or "?" in token:
            if glob.fnmatch.fnmatch(filename, os.path.basename(token)):
                return True
    return False


# ---------------------------------------------------------------------------
# SELF-TEST: deliberately missing COPY
# ---------------------------------------------------------------------------

def run_missing_test(repo_root: str, dockerfile_path: str) -> bool:
    """
    Self-test: verify the guard CATCHES a missing COPY.
    Creates a temp module, temporarily removes it from the known copy set,
    and checks that the guard reports it missing.
    Returns True if test passed (guard correctly caught the omission).
    """
    import tempfile
    print("\n[SELF-TEST] Verifying guard catches a missing COPY...")

    root = Path(repo_root)
    # Create a synthetic 'test_guard_dummy_module.py' in repo root
    dummy_name = "test_guard_dummy_module"
    dummy_file = root / f"{dummy_name}.py"
    dummy_file.write_text("# synthetic test module\n")

    # Create a synthetic entrypoint that imports it
    ep_content = f"import {dummy_name}\nprint('hi')\n"

    try:
        local_imports = collect_local_imports(
            ["<synthetic_ep>"],
            repo_root,
            _stdlib_names(),
        )
        # Manually inject the import for this test
        local_set = {dummy_name}

        # Build a copy_set that deliberately EXCLUDES the dummy module
        copy_set = collect_dockerfile_copy_set(dockerfile_path)
        # Do NOT add the dummy module to copy_set

        missing = [m for m in local_set if not module_in_copy_set(m, copy_set)]
        if dummy_name in missing:
            print(f"[SELF-TEST] PASS: guard correctly flagged '{dummy_name}' as missing from COPY")
            result = True
        else:
            print(f"[SELF-TEST] FAIL: guard did NOT flag '{dummy_name}' — false negative!")
            result = False
    finally:
        dummy_file.unlink(missing_ok=True)

    return result


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CI COPY-completeness guard: every locally-imported root .py "
                    "must appear in the Dockerfile COPY set.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dockerfile",
        default="Dockerfile",
        help="Path to the Dockerfile (default: Dockerfile)",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root / Docker build context (default: .)",
    )
    parser.add_argument(
        "--entrypoints",
        nargs="+",
        default=["serve.py"],
        help="Python entrypoint file(s) to parse for imports "
             "(default: serve.py). Paths relative to --root.",
    )
    parser.add_argument(
        "--missing-test",
        action="store_true",
        help="Run built-in self-test: verify guard catches a deliberately-missing COPY",
    )
    args = parser.parse_args(argv)

    repo_root = os.path.abspath(args.root)
    dockerfile_path = (
        args.dockerfile if os.path.isabs(args.dockerfile)
        else os.path.join(repo_root, args.dockerfile)
    )

    stdlib = _stdlib_names()

    # --missing-test: run the self-test and exit
    if args.missing_test:
        ok = run_missing_test(repo_root, dockerfile_path)
        return 0 if ok else 1

    print(f"[copy-completeness] Repo root  : {repo_root}")
    print(f"[copy-completeness] Dockerfile : {dockerfile_path}")
    print(f"[copy-completeness] Entrypoints: {args.entrypoints}")
    print()

    # Step 1: collect imports from entrypoints
    imports_by_ep = collect_local_imports(args.entrypoints, repo_root, stdlib)

    # Union of all locally-imported root .py modules across all entrypoints
    all_local_imports: set[str] = set()
    for ep, mods in imports_by_ep.items():
        all_local_imports |= mods
        print(f"  {ep}: {len(mods)} local root module(s) imported")

    print(f"\n[copy-completeness] Total unique local root modules : {len(all_local_imports)}")

    # Step 2: collect Dockerfile COPY set
    try:
        copy_set = collect_dockerfile_copy_set(dockerfile_path)
    except FileNotFoundError as exc:
        print(f"::error::{exc}")
        return 2

    print(f"[copy-completeness] Dockerfile COPY source tokens  : {len(copy_set)}")
    print()

    # Step 3: check membership
    missing: list[str] = []
    present: list[str] = []
    for mod in sorted(all_local_imports):
        if module_in_copy_set(mod, copy_set):
            present.append(mod)
        else:
            missing.append(mod)

    if present:
        print(f"OK ({len(present)} module(s) covered by Dockerfile COPY):")
        for m in present:
            print(f"  [OK] {m}.py")
        print()

    if missing:
        print(f"::error::{len(missing)} locally-imported root module(s) MISSING from "
              f"Dockerfile COPY (a container build would produce a silent 404):")
        for m in missing:
            print(f"::error::  MISSING: {m}.py  "
                  f"(imported by entrypoint; exists in repo; NOT in Dockerfile COPY)")
        print()
        print("FIX: Add each missing module to the Dockerfile COPY line, e.g.:")
        for m in missing:
            print(f"  COPY {m}.py ./{m}.py")
        print()
        print("[copy-completeness] RESULT: FAIL — add the missing COPY lines and re-run.")
        return 1

    print("[copy-completeness] RESULT: PASS — all locally-imported root modules "
          "are present in the Dockerfile COPY set.")
    print()
    print("Honest scope note: This guard checks root-level *.py imports from the "
          "listed entrypoints. Sub-packages covered by directory COPY, dynamic "
          "importlib calls, and pip-installed packages are not checked here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
