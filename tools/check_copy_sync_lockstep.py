#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
#
# Dockerfile COPY  <->  serve.py imports  <->  hf-sync deploy  LOCKSTEP guard.
#
# PERMANENT CI guard (no bandaid). Stops the recurring failure that broke the SZL
# estate three times on 2026-06-13: a module/asset is added to the GitHub repo and
# referenced (an `import` in serve.py, or a Dockerfile `COPY`), but it is NOT in
# BOTH the Dockerfile COPY set AND the hf-sync deployment contract — so the Space either
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
#   CHECK 3 — explicitly-COPY'd non-.py served assets are deployed to HF.
#       Every NON-.py asset brought in by an EXPLICIT PER-FILE Dockerfile COPY
#       (e.g. `COPY static/cathedral_app.js ...`, `COPY cathedral_genius.html ...`)
#       must be covered by the active deployment contract. The current contract
#       calls a commit-pinned reusable deployer with `dockerfile-path: Dockerfile`;
#       that controller derives the Space file set from COPY sources. Legacy callers
#       may instead enumerate APP_FILES / on.push.paths / front-door globs. A
#       per-file COPY that neither contract covers recreates GitHub<->HF drift.
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
import posixpath
import re
import shlex
import sys

REPO_PY_EXT = ".py"


def normalize_repo_path(path):
    """Return one stable POSIX-form repository-relative path.

    Docker and GitHub Actions paths are slash-delimited even when this guard
    runs on Windows. Normalize at comparison boundaries so host path separators
    cannot create false drift failures.
    """
    value = str(path).replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return posixpath.normpath(value)


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
                matched.append(normalize_repo_path(os.path.relpath(h, root)))
            elif os.path.isdir(h):
                for dp, _dn, fns in os.walk(h):
                    for fn in fns:
                        matched.append(normalize_repo_path(
                            os.path.relpath(os.path.join(dp, fn), root)
                        ))
        return matched, bool(hits)
    if not os.path.exists(path):
        return [], False
    if os.path.isdir(path):
        for dp, _dn, fns in os.walk(path):
            for fn in fns:
                matched.append(normalize_repo_path(
                    os.path.relpath(os.path.join(dp, fn), root)
                ))
        return matched, True
    matched.append(normalize_repo_path(os.path.relpath(path, root)))
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
            mods[entry] = normalize_repo_path(os.path.join(entry, "__init__.py"))
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
# hf-sync deployment-contract parsing.
# --------------------------------------------------------------------------- #
def workflow_job_blocks(workflow_text):
    """Yield ``(job_id, block_lines, job_indent)`` from a workflow's jobs map."""
    lines = workflow_text.splitlines()
    parsed = []
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entry = yaml_mapping_entry(stripped)
        if entry:
            parsed.append((index, len(raw) - len(raw.lstrip()), entry))
    if not parsed:
        return []
    top_indent = min(indent for _index, indent, _entry in parsed)
    jobs_entries = [
        item
        for item in parsed
        if item[1] == top_indent and item[2][0] == "jobs"
    ]
    if len(jobs_entries) != 1 or jobs_entries[0][2][1]:
        return []
    jobs_index, jobs_indent, _entry = jobs_entries[0]

    blocks = []
    current_id = None
    current_lines = []
    job_indent = None

    for raw in lines[jobs_index + 1:]:
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if stripped and not stripped.startswith("#") and indent <= jobs_indent:
            break
        entry = yaml_mapping_entry(stripped) if stripped else None
        if entry and indent > jobs_indent:
            if job_indent is None:
                job_indent = indent
            if indent == job_indent:
                job_id, value = entry
                if job_id == "<<" or value:
                    # Inline jobs and merges are deliberately unsupported:
                    # accepting a partial parse could prove an inert snippet.
                    return []
                if current_id is not None:
                    blocks.append((current_id, current_lines, job_indent))
                current_id = job_id
                current_lines = [raw]
                continue
        if current_id is not None:
            current_lines.append(raw)
    if current_id is not None:
        blocks.append((current_id, current_lines, job_indent))
    return blocks


def strip_yaml_comment(value):
    """Strip a YAML comment marker only outside quotes and after whitespace."""
    quote = None
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = None
        elif quote == "'":
            if char == "'":
                if index + 1 < len(value) and value[index + 1] == "'":
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        index += 1
    return value.strip()


def yaml_mapping_entry(stripped):
    """Return a simple YAML mapping key/value pair, including quoted keys."""
    match = re.match(
        r"^(?:\"(?P<double>[^\"]+)\"|'(?P<single>[^']+)'|"
        r"(?P<bare><<|[A-Za-z_][A-Za-z0-9_-]*))\s*:\s*(?P<value>.*)$",
        stripped,
    )
    if not match:
        return None
    key = match.group("double") or match.group("single") or match.group("bare")
    value = strip_yaml_comment(match.group("value"))
    return key, value


def yaml_scalar_value(value):
    """Parse the YAML string-scalar spellings supported by this guard."""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return False, None
        return isinstance(parsed, str), parsed
    if value.startswith("'"):
        if not value.endswith("'") or len(value) < 2:
            return False, None
        return True, value[1:-1].replace("''", "'")
    if "'" in value or '"' in value:
        return False, None
    return True, value


def yaml_scalar_matches(value, expected):
    """Compare a plain or quoted scalar, failing closed on invalid quoting."""
    valid, parsed = yaml_scalar_value(value)
    return valid and parsed == expected


def yaml_sequence_items(lines, entry_index, property_indent, value):
    """Return an ordered inline or indented YAML sequence."""
    if value:
        if value.startswith("[") and value.endswith("]"):
            content = value[1:-1]
            items = []
            item_start = 0
            quote = None
            escaped = False
            index = 0
            while index < len(content):
                char = content[index]
                if quote == '"':
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        quote = None
                elif quote == "'":
                    if char == "'":
                        if index + 1 < len(content) and content[index + 1] == "'":
                            index += 1
                        else:
                            quote = None
                elif char in {"'", '"'}:
                    quote = char
                elif char == ",":
                    items.append(content[item_start:index])
                    item_start = index + 1
                index += 1
            if quote is not None or escaped:
                return None
            items.append(content[item_start:])
        else:
            items = [value]
        normalized = []
        for item in items:
            item = item.strip()
            if not item:
                continue
            valid, item = yaml_scalar_value(item)
            if not valid:
                return None
            normalized.append(item)
        return normalized

    items = []
    for raw in lines[entry_index + 1:]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= property_indent:
            break
        item = re.match(r"^-\s*(.*?)\s*$", stripped)
        if item:
            value = strip_yaml_comment(item.group(1)).strip()
            valid, value = yaml_scalar_value(value)
            if not valid:
                return None
            items.append(value)
    return items


def github_branch_pattern_matches_main(pattern):
    """Match ``main`` with GitHub Actions filter-pattern semantics."""
    tokens = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            if index + 1 >= len(pattern):
                return None
            tokens.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                tokens.append(".*")
                index += 2
            else:
                tokens.append("[^/]*")
                index += 1
            continue
        if char in {"?", "+"}:
            if not tokens:
                return None
            tokens[-1] = "(?:%s)%s" % (tokens[-1], char)
            index += 1
            continue
        if char == "[":
            close = pattern.find("]", index + 1)
            if close < 0:
                return None
            members = pattern[index + 1:close]
            if not members or not re.fullmatch(r"[A-Za-z0-9-]+", members):
                return None
            try:
                re.compile("[" + members + "]")
            except re.error:
                return None
            tokens.append("[" + members + "]")
            index = close + 1
            continue
        tokens.append(re.escape(char))
        index += 1
    try:
        return re.fullmatch("".join(tokens), "main") is not None
    except re.error:
        return None


def ordered_branch_patterns_include_main(patterns):
    """Evaluate ordered GitHub positive/negative branch patterns for main."""
    included = False
    for pattern in patterns:
        negative = pattern.startswith("!")
        candidate = pattern[1:] if negative else pattern
        matches = github_branch_pattern_matches_main(candidate)
        if matches is None:
            return False
        if matches:
            included = not negative
    return included


def workflow_has_unfiltered_main_push(workflow_text):
    """Require a top-level push trigger that includes main without path filters."""
    lines = workflow_text.splitlines()
    parsed = []
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entry = yaml_mapping_entry(stripped)
        if entry:
            parsed.append((index, len(raw) - len(raw.lstrip()), entry))
    if not parsed:
        return False
    top_indent = min(indent for _index, indent, _entry in parsed)
    on_entries = [
        (index, indent, entry)
        for index, indent, entry in parsed
        if indent == top_indent and entry[0] == "on"
    ]
    if len(on_entries) != 1 or on_entries[0][2][1]:
        return False

    on_index, on_indent, _entry = on_entries[0]
    on_block = []
    for index, raw in enumerate(lines[on_index + 1:], start=on_index + 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= on_indent:
            break
        entry = yaml_mapping_entry(stripped)
        if entry:
            on_block.append((index, indent, entry))
    if not on_block:
        return False
    event_indent = min(indent for _index, indent, _entry in on_block)
    push_entries = [
        item
        for item in on_block
        if item[1] == event_indent and item[2][0] == "push"
    ]
    if len(push_entries) != 1 or push_entries[0][2][1]:
        return False

    push_index, push_indent, _entry = push_entries[0]
    push_block = []
    for index, raw in enumerate(lines[push_index + 1:], start=push_index + 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= push_indent:
            break
        entry = yaml_mapping_entry(stripped)
        if entry:
            push_block.append((index, indent, entry))
    if not push_block:
        return True

    property_indent = min(indent for _index, indent, _entry in push_block)
    properties = [
        item for item in push_block if item[1] == property_indent
    ]
    property_keys = {entry[0] for _index, _indent, entry in properties}
    if property_keys & {"<<", "paths", "paths-ignore", "branches-ignore"}:
        return False
    branch_entries = [
        item for item in properties if item[2][0] == "branches"
    ]
    if not branch_entries:
        return not (property_keys & {"tags", "tags-ignore"})
    if len(branch_entries) != 1:
        return False
    branch_index, _indent, (_key, value) = branch_entries[0]
    branch_patterns = yaml_sequence_items(
        lines,
        branch_index,
        property_indent,
        value,
    )
    return branch_patterns is not None and ordered_branch_patterns_include_main(
        branch_patterns
    )


SOURCE_DERIVED_CONTROLLER_REVISIONS = frozenset({
    # Reviewed reusable-hf-deploy controller that expands Dockerfile COPY
    # sources into the HF payload. A generic 40-hex pin proves immutability,
    # not this capability; additions require an explicit guard review.
    "e3ec47ad2e99a535839afe0f30fefbd8973d52da",
})


def job_has_source_derived_deploy_contract(block_lines, job_indent):
    """Require an unconditional reviewed Dockerfile-derived deploy job."""
    property_indents = []
    for raw in block_lines[1:]:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            indent = len(raw) - len(raw.lstrip())
            if indent > job_indent:
                property_indents.append(indent)
    if not property_indents:
        return False
    property_indent = min(property_indents)

    pinned_controller = False
    controller_seen = False
    with_index = None
    for index, raw in enumerate(block_lines[1:], start=1):
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if indent != property_indent:
            continue
        entry = yaml_mapping_entry(stripped)
        if entry and entry[0] in {"if", "<<", "needs"}:
            # A skipped reusable job can leave the workflow green without
            # publishing protected-main source changes. Dependencies can be
            # skipped, and YAML merges can inherit either gate. Fail closed
            # rather than proving arbitrary dependency/expression semantics.
            return False
        if entry and entry[0] == "uses":
            if controller_seen:
                return False
            controller_seen = True
            controller = re.fullmatch(
                r"szl-holdings/\.github/\.github/workflows/"
                r"reusable-hf-deploy\.yml@(?P<revision>[0-9a-fA-F]{40})",
                entry[1],
            )
            pinned_controller = bool(
                controller
                and controller.group("revision").lower()
                in SOURCE_DERIVED_CONTROLLER_REVISIONS
            )
        if entry and entry[0] == "with":
            if entry[1] or with_index is not None:
                return False
            with_index = index
    if not controller_seen or not pinned_controller or with_index is None:
        return False

    expected_inputs = {
        "hf-repo": "SZLHOLDINGS/a11oy",
        "ref": "${{ github.sha }}",
        "dockerfile-path": "Dockerfile",
    }
    matched_inputs = {}
    with_indent = None
    for raw in block_lines[with_index + 1:]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= property_indent:
            break
        if with_indent is None:
            with_indent = indent
        if indent != with_indent:
            continue
        entry = yaml_mapping_entry(stripped)
        if not entry or entry[0] == "<<":
            return False
        key, value = entry
        if key in expected_inputs:
            if key in matched_inputs:
                return False
            matched_inputs[key] = yaml_scalar_matches(value, expected_inputs[key])
    return (
        set(matched_inputs) == set(expected_inputs)
        and all(matched_inputs.values())
    )


def has_source_derived_deploy_contract(hf_sync_text):
    """Return True only for the pinned reusable Dockerfile-derived deploy lane.

    The shared controller expands Dockerfile COPY sources and publishes that
    exact set. Requiring a reviewed capability-bearing controller revision,
    canonical destination, exact source SHA, and Dockerfile input in the same
    unconditional job prevents a generic pin, stale ref, wrong destination,
    comment, step, unrelated workflow, or skipped deploy job from satisfying
    CHECK 3.
    """
    return workflow_has_unfiltered_main_push(hf_sync_text) and any(
        job_has_source_derived_deploy_contract(block_lines, job_indent)
        for _job_id, block_lines, job_indent in workflow_job_blocks(hf_sync_text)
    )


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
            explicit.add(normalize_repo_path(tok))

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
                    val = normalize_repo_path(val)
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
    asset = normalize_repo_path(asset)
    explicit = {normalize_repo_path(path) for path in explicit}
    if asset in explicit:
        return True
    for raw_pattern in globs:
        pat = normalize_repo_path(raw_pattern)
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
    image_only = {
        normalize_repo_path(path) for path in cfg.get("image_only_assets", [])
    }
    extra_mirror = {
        normalize_repo_path(path) for path in cfg.get("extra_mirror_paths", [])
    }
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
            base = posixpath.basename(f)
            if base.endswith(REPO_PY_EXT) and posixpath.dirname(f) == "":
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

    # ---------------- CHECK 3: non-.py COPY assets are deployed ----------- #
    mirror_explicit = set()
    mirror_globs = []
    source_derived_deploy = False
    hf_sync_present = os.path.isfile(hf_sync)
    if hf_sync_present:
        with open(hf_sync, "r", encoding="utf-8") as fh:
            hf_text = fh.read()
        source_derived_deploy = has_source_derived_deploy_contract(hf_text)
        mirror_explicit, mirror_globs = parse_hf_sync_mirror(hf_text)
        # a11oy mirrors front-door pages/console globs inside the heredoc step.
        if "pages/*.html" in hf_text or "console/*.html" in hf_text:
            mirror_globs = list(mirror_globs) + A11OY_FRONTDOOR_GLOBS
    mirror_explicit |= extra_mirror

    check3_missing = []
    for f in sorted(perfile_assets):
        base = posixpath.basename(f)
        if not base.endswith(mirror_exts):
            continue  # only the served text asset types hf-sync owns
        if source_derived_deploy:
            continue  # reusable deployer publishes the exact Dockerfile source set
        if f in image_only:
            continue  # explicitly declared image-only (baked, not mirrored)
        if hf_sync_present and gha_path_matches(f, mirror_explicit, mirror_globs):
            continue
        check3_missing.append(f)
    for f in check3_missing:
        failures.append(
            f"[CHECK 3: asset not deployed to HF] '{f}' is a non-.py asset COPY'd "
            f"into the image but is NOT covered by hf-sync's source-derived deploy "
            f"contract or legacy mirror set (APP_FILES / on.push.paths / front-door "
            f"globs) — GitHub-built image has it, the HF Space never receives it "
            f"=> GitHub<->HF drift. Add '{f}' to the legacy mirror set, use the "
            f"pinned Dockerfile-derived deploy controller, or list it under "
            f"\"image_only_assets\" in "
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
        if source_derived_deploy:
            print("hf-sync deployment contract: pinned Dockerfile-derived reusable deploy")
        else:
            print(f"hf-sync legacy mirror set: {len(mirror_explicit)} explicit + "
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
