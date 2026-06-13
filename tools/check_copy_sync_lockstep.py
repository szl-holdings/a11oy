#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# Dockerfile COPY  <->  serve.py imports  <->  hf-sync mirror  LOCKSTEP guard.
#
# PERMANENT CI guard (no bandaid). Stops the recurring failure that broke the SZL
# estate three times on 2026-06-13: a module/asset is added to the GitHub repo and
# referenced (an `import` in serve.py, or a Dockerfile `COPY`), but it is NOT in
# BOTH the Dockerfile COPY set AND the hf-sync mirror set — so the HF Space either
# BUILD_ERRORs (COPY of a file the Space never received) or silently serves a stub
# (a try/except-guarded import falls back because the module was never in the image).
#
# Three failure modes, three checks (any failure exits non-zero with a clear,
# file-named message saying WHICH set the file is missing from):
#
#   CHECK 1 — COPY source exists.
#       Every local source path in a Dockerfile COPY/ADD line must exist in the
#       repo. A missing source BUILD_ERRORs the HF Docker build at that line.
#       (Reproduces the a11oy/formula-404 incident: allodial.py etc. referenced
#        but not present in the COPY context.)
#
#   CHECK 2 — serve.py local imports are COPY'd.
#       Every LOCAL .py module that serve.py imports (and, transitively, every
#       local module those import — a bounded local-only scan) must be in the
#       Dockerfile COPY set, or the guarded import in the image falls back to a
#       stub at runtime. (Reproduces joules #349: szl_joules_truth.py imported,
#        never COPY'd -> silent stub -> merged-but-not-live.)
#
#   CHECK 3 — explicitly-COPY'd non-.py served assets are mirrored to HF.
#       Every NON-.py asset brought in by an EXPLICIT PER-FILE Dockerfile COPY
#       (e.g. `COPY static/cathedral_app.js ...`, `COPY cathedral_genius.html ...`)
#       must be in the hf-sync mirror set (APP_FILES / on.push.paths / front-door
#       globs). A per-file COPY is the signal a dev hand-added ONE served file; if it
#       is not also mirrored, the GitHub-built image has it but the HF Space never
#       receives it => GitHub<->HF drift / BUILD_ERROR. This is EXACTLY the a11oy
#       cathedral_app.js / cathedral_genius.html incident.
#       Assets brought in by a DIRECTORY or GLOB COPY (e.g. `COPY static/ ./static/`,
#       `COPY console/ ./static/`) are the bulk vendored/built SPA tree that already
#       lives baked on the Space and is intentionally NOT re-mirrored by hf-sync (its
#       own comments document that re-syncing those LFS/vendor blobs reintroduces
#       pre-receive failures); those are treated as image-only and not flagged.
#       A committed allowlist (.github/copy-sync-lockstep.json -> "image_only_assets")
#       declares any remaining per-file assets intentionally baked-only (large/LFS
#       vendor blobs). This is an explicit, reviewed escape hatch, NOT a silent skip —
#       every exemption is named in-repo.
#
# stdlib ONLY (ast for imports, no third-party deps) so it runs anywhere with no
# install step, exactly like the sibling .github/dockerfile-copy-check.py.
#
# Exit 0 = all three checks pass. Exit 1 = at least one violation (printed with
# ::error:: GitHub-Actions annotations). Exit 2 = the guard could not run
# (missing Dockerfile/serve.py) — treated as a hard failure too.

import ast
import fnmatch
import glob as globmod
import json
import os
import re
import shlex
import sys

REPO_PY_EXT = ".py"


# --------------------------------------------------------------------------- #
# Dockerfile parsing (mirrors .github/dockerfile-copy-check.py handling).
# --------------------------------------------------------------------------- #
def logical_lines(text):
    """Yield Dockerfile logical instructions, joining backslash continuations."""
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
    """
    Return (sources, skip_reason) for a COPY/ADD instruction.
    skip_reason is set (sources empty) for intentionally-ignored instructions
    (multi-stage --from, remote URL ADD, unparseable).
    """
    m = re.match(r"^\s*(COPY|ADD)\s+(.*)$", instruction, re.IGNORECASE)
    if not m:
        return [], None
    verb = m.group(1).upper()
    rest = m.group(2).strip()

    if rest.startswith("["):
        try:
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
            continue  # --chown=, --chmod=, --link, ...
        real.append(tok)

    if len(real) < 2:
        return [], "no-source-or-dest"

    sources = real[:-1]  # last token is the destination
    local_sources = []
    for src in sources:
        if verb == "ADD" and re.match(r"^[a-z][a-z0-9+.-]*://", src, re.IGNORECASE):
            continue
        local_sources.append(src)
    return local_sources, None


def collect_copy_sources(dockerfile_text):
    """Return (sources, skipped) — list of local COPY/ADD source path strings."""
    sources = []
    skipped = []
    for instr in logical_lines(dockerfile_text):
        if not re.match(r"^\s*(COPY|ADD)\b", instr, re.IGNORECASE):
            continue
        srcs, skip = parse_copy_sources(instr)
        if skip:
            skipped.append((instr.strip(), skip))
            continue
        for s in srcs:
            sources.append((s, instr.strip()))
    return sources, skipped


def expand_source_to_files(root, src):
    """
    Expand a single COPY source into the set of repo-relative file paths it
    actually brings into the image. Handles plain files, globs, and directories
    (recursively). Returns (files, exists_bool).
    """
    path = src if os.path.isabs(src) else os.path.join(root, src)
    matched = []
    if any(ch in src for ch in "*?[]"):
        hits = globmod.glob(path, recursive=True)
        for h in hits:
            if os.path.isfile(h):
                matched.append(os.path.relpath(h, root))
            elif os.path.isdir(h):
                for dp, _dn, fns in os.walk(h):
                    for fn in fns:
                        matched.append(os.path.relpath(os.path.join(dp, fn), root))
        return matched, bool(hits)
    if not os.path.exists(path):
        return [], False
    if os.path.isdir(path):
        for dp, _dn, fns in os.walk(path):
            for fn in fns:
                matched.append(os.path.relpath(os.path.join(dp, fn), root))
        return matched, True
    matched.append(os.path.relpath(path, root))
    return matched, True


# --------------------------------------------------------------------------- #
# serve.py import analysis (ast — bounded local-module transitive scan).
# --------------------------------------------------------------------------- #
def local_module_files(root):
    """
    Map of importable local top-level module name -> repo-relative file path.
    Includes top-level <name>.py and packages (<name>/__init__.py).
    """
    mods = {}
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if os.path.isfile(full) and entry.endswith(REPO_PY_EXT):
            mods[entry[:-3]] = entry
        elif os.path.isdir(full) and os.path.isfile(os.path.join(full, "__init__.py")):
            mods[entry] = os.path.join(entry, "__init__.py")
    return mods


def imported_top_names(py_path):
    """Top-level module names imported by a .py file (ast; absolute imports only)."""
    with open(py_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=py_path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # Skip relative imports (level>0); they resolve within a package.
            if node.level and node.level > 0:
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def transitive_local_imports(root, entry_files, local_mods):
    """
    Starting from entry_files, follow imports that resolve to LOCAL modules and
    return the set of local module NAMES reachable (bounded; local-only).
    """
    seen_files = set()
    reached = set()
    stack = list(entry_files)
    while stack:
        f = stack.pop()
        full = os.path.join(root, f)
        if f in seen_files or not os.path.isfile(full):
            continue
        seen_files.add(f)
        try:
            names = imported_top_names(full)
        except SyntaxError as e:
            print(f"::warning::could not ast-parse {f} for import scan: {e}")
            continue
        for n in names:
            if n in local_mods:
                reached.add(n)
                stack.append(local_mods[n])
    return reached


# --------------------------------------------------------------------------- #
# hf-sync mirror-set parsing.
# --------------------------------------------------------------------------- #
def parse_hf_sync_mirror(hf_sync_text):
    """
    Extract the hf-sync mirror set from a hf-sync.yml: the union of
      * env.APP_FILES (space-separated literal list), if present
      * on.push.paths literal entries
    Returns (explicit_paths:set, glob_patterns:list).
    Path entries ending in /** or containing wildcards are returned as globs.
    """
    explicit = set()
    globs = []

    # env.APP_FILES: "a.py b.py ..."
    m = re.search(r"APP_FILES:\s*\"([^\"]*)\"", hf_sync_text)
    if m:
        for tok in m.group(1).split():
            explicit.add(tok)

    # on.push.paths: a YAML list of quoted strings under a `paths:` key. Parse
    # the literal "- "..."" entries (stdlib-only, no yaml dependency).
    in_paths = False
    paths_indent = None
    for raw in hf_sync_text.splitlines():
        if re.match(r"^\s*paths:\s*$", raw):
            in_paths = True
            paths_indent = len(raw) - len(raw.lstrip())
            continue
        if in_paths:
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip())
            if stripped.startswith("- "):
                val = stripped[2:].strip().strip('"').strip("'")
                if val:
                    if any(ch in val for ch in "*?[]") or val.endswith("/**"):
                        globs.append(val)
                    else:
                        explicit.add(val)
            elif stripped and indent <= (paths_indent or 0):
                in_paths = False
    return explicit, globs


# Front-door globs that hf-sync.yml mirrors via the inline create_commit step
# (a11oy: pages/*.{html,js}, console/*.{html,js}). These live in the workflow's
# python heredoc, not on.push.paths, so they are recognised here too. Kept in
# lockstep with hf-sync.yml's `patterns` list.
A11OY_FRONTDOOR_GLOBS = [
    "pages/*.html", "pages/*.js", "console/*.html", "console/*.js",
]


def gha_path_matches(asset, explicit, globs):
    """True if a repo-relative asset path is covered by the mirror set."""
    if asset in explicit:
        return True
    for pat in globs:
        # Translate a GitHub-Actions path filter to an fnmatch-style test.
        if pat.endswith("/**"):
            prefix = pat[:-3].rstrip("/")
            if asset == prefix or asset.startswith(prefix + "/"):
                return True
        else:
            if fnmatch.fnmatch(asset, pat):
                return True
    return False


# --------------------------------------------------------------------------- #
# Main.
# --------------------------------------------------------------------------- #
def load_config(root):
    cfg_path = os.path.join(root, ".github", "copy-sync-lockstep.json")
    if os.path.isfile(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as fh:
            return json.load(fh), cfg_path
    return {}, cfg_path


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    root = os.path.abspath(root)
    dockerfile = os.path.join(root, "Dockerfile")
    serve = os.path.join(root, "serve.py")
    hf_sync = os.path.join(root, ".github", "workflows", "hf-sync.yml")

    if not os.path.isfile(dockerfile):
        print(f"::error::Dockerfile not found at {dockerfile}")
        return 2
    if not os.path.isfile(serve):
        print(f"::error::serve.py not found at {serve}")
        return 2

    cfg, cfg_path = load_config(root)
    image_only = set(cfg.get("image_only_assets", []))
    extra_mirror = set(cfg.get("extra_mirror_paths", []))
    # Non-.py asset extensions that hf-sync is responsible for mirroring.
    mirror_exts = tuple(cfg.get("mirror_asset_exts",
                                [".html", ".js", ".css"]))

    with open(dockerfile, "r", encoding="utf-8") as fh:
        df_text = fh.read()

    copy_sources, skipped = collect_copy_sources(df_text)
    local_mods = local_module_files(root)

    failures = []

    # ---------------- CHECK 1: every COPY source exists ------------------- #
    copied_files = set()       # all repo-relative files brought into the image
    copied_py_modules = set()  # top-level python module names COPY'd into image
    # Non-.py assets brought in by an EXPLICIT per-file COPY (single file source,
    # no wildcard, source resolves to a file not a directory) — the per-file signal
    # CHECK 3 cares about. Directory/glob-COPY'd trees are bulk image-only content.
    perfile_assets = set()
    check1_missing = []
    for src, instr in copy_sources:
        files, exists = expand_source_to_files(root, src)
        if not exists:
            check1_missing.append((src, instr))
            continue
        is_wildcard = any(ch in src for ch in "*?[]")
        src_path = src if os.path.isabs(src) else os.path.join(root, src)
        is_dir = os.path.isdir(src_path)
        per_file = (not is_wildcard) and (not is_dir)
        for f in files:
            copied_files.add(f)
            base = os.path.basename(f)
            if base.endswith(REPO_PY_EXT) and os.path.dirname(f) == "":
                copied_py_modules.add(base[:-3])
            if per_file and not base.endswith(REPO_PY_EXT):
                perfile_assets.add(f)

    for src, instr in check1_missing:
        failures.append(
            f"[CHECK 1: COPY source missing] '{src}' is COPY'd by the Dockerfile "
            f"but does not exist in the repo — the HF Docker build BUILD_ERRORs at "
            f"this line. Add the file or remove the COPY.  <- {instr}"
        )

    # ---------------- CHECK 2: serve.py local imports are COPY'd ---------- #
    reached = transitive_local_imports(root, ["serve.py"], local_mods)
    # serve.py itself must be in the COPY set as well.
    reached_with_serve = set(reached) | {"serve"}
    check2_missing = []
    for modname in sorted(reached_with_serve):
        if modname not in copied_py_modules:
            # Only top-level single-file modules are tracked here; package
            # imports (dir/__init__.py) are covered by CHECK 1 dir-COPY checks.
            relfile = local_mods.get(modname, modname + ".py")
            if relfile.endswith("__init__.py"):
                continue
            check2_missing.append((modname, relfile))
    for modname, relfile in check2_missing:
        failures.append(
            f"[CHECK 2: imported module not COPY'd] serve.py imports local module "
            f"'{modname}' ({relfile}) but it is NOT in the Dockerfile COPY set — in "
            f"the HF image the guarded import falls back to a STUB (merged-but-not-live). "
            f"Add '{relfile}' to a Dockerfile COPY line."
        )

    # ---------------- CHECK 3: non-.py COPY assets are mirrored ----------- #
    mirror_explicit = set()
    mirror_globs = []
    hf_sync_present = os.path.isfile(hf_sync)
    if hf_sync_present:
        with open(hf_sync, "r", encoding="utf-8") as fh:
            hf_text = fh.read()
        mirror_explicit, mirror_globs = parse_hf_sync_mirror(hf_text)
        # a11oy mirrors front-door pages/console globs inside the heredoc step.
        if "pages/*.html" in hf_text or "console/*.html" in hf_text:
            mirror_globs = list(mirror_globs) + A11OY_FRONTDOOR_GLOBS
    mirror_explicit |= extra_mirror

    check3_missing = []
    for f in sorted(perfile_assets):
        base = os.path.basename(f)
        if not base.endswith(mirror_exts):
            continue  # only the served text asset types hf-sync owns
        if f in image_only:
            continue  # explicitly declared image-only (baked, not mirrored)
        if hf_sync_present and gha_path_matches(f, mirror_explicit, mirror_globs):
            continue
        check3_missing.append(f)
    for f in check3_missing:
        failures.append(
            f"[CHECK 3: asset not mirrored to HF] '{f}' is a non-.py asset COPY'd "
            f"into the image but is NOT in the hf-sync mirror set (APP_FILES / "
            f"on.push.paths / front-door globs) — GitHub-built image has it, the HF "
            f"Space never receives it => GitHub<->HF drift. Add '{f}' to hf-sync.yml's "
            f"mirror set, or list it under \"image_only_assets\" in "
            f".github/copy-sync-lockstep.json if it is intentionally baked-only."
        )

    # ----------------------------- report -------------------------------- #
    print(f"repo root: {root}")
    print(f"Dockerfile COPY sources parsed: {len(copy_sources)} "
          f"(skipped {len(skipped)} multi-stage/remote/unparseable)")
    print(f"files brought into image by COPY: {len(copied_files)}")
    print(f"top-level .py modules COPY'd: {len(copied_py_modules)}")
    print(f"non-.py assets COPY'd PER-FILE (CHECK 3 scope): {len(perfile_assets)}")
    print(f"local modules reachable from serve.py imports: {len(reached_with_serve)}")
    if hf_sync_present:
        print(f"hf-sync mirror set: {len(mirror_explicit)} explicit + "
              f"{len(mirror_globs)} glob(s)")
    else:
        print("hf-sync.yml not present — CHECK 3 mirror set is empty "
              "(only image_only/extra config honoured)")
    if os.path.isfile(cfg_path):
        print(f"config: {os.path.relpath(cfg_path, root)} "
              f"(image_only={len(image_only)}, extra_mirror={len(extra_mirror)})")

    if failures:
        print()
        print(f"::error::copy-sync lockstep guard FAILED with {len(failures)} "
              f"violation(s):")
        for msg in failures:
            print(f"::error::  {msg}")
        return 1

    print("\nOK: COPY <-> serve.py imports <-> hf-sync mirror are in lockstep.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
