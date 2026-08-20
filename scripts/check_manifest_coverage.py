#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
#
# check_manifest_coverage.py — PERMANENT CI guard (Doctrine v11): a registered frontier
# surface must ship an honesty manifest the Honesty Wall can read.
#
# Why this exists
# ---------------
# The Honesty Wall (szl_honestywall.py) aggregates each registered surface's OWN honesty
# invariants. For every surface in the registry (szl3d_holographic.SURFACES) it asks the
# Frontier Index whether any registered a11oy GET route under /api/{ns}/v1 has a path
# SEGMENT equal (normalized) to the surface id. If none does, the wall can read nothing
# about that surface and honestly reports NO-MANIFEST — it is skipped, not verified.
#
# So every surface added without an id-matching manifest route silently shrinks the share
# of the estate the wall can actually check. #890 (szl_surface_manifests.py) closed a batch
# of that gap by shipping a truthful UNAVAILABLE manifest per client-only surface. Nothing
# stopped the gap from reopening on the next surface. This guard is that stop:
#
#   * it reports the honest per-surface NATIVE-OK / NO-MANIFEST split;
#   * it FAILS if coverage drops below the level recorded when the guard shipped, so an
#     existing manifest cannot be deleted; and
#   * RATCHET: it FAILS if a surface ADDED in this PR has no manifest at all. Only ever
#     tightens — the pre-existing NO-MANIFEST surfaces are not retroactively failed.
#
# STATIC ANALYSIS, and honest about it
# ------------------------------------
# The wall's real answer is an in-process probe of the booted app. Reproducing that here
# would mean importing serve.py and the whole dependency tree inside a governance guard,
# so this checker instead STATICALLY approximates the same question with the stdlib only:
# it parses the registry with `ast`, then treats a surface as manifest-bearing when a
# route-registering Python module declares an /api/{ns}/v1 path whose id segment matches
# the surface, or registers one manifest route per id from a list of surface ids (the
# #890 batch pattern).
#
# The static view therefore OVER-approximates: a module can declare an id-matching API
# path that is not mounted at request time (an unmounted router, a path only named in a
# docstring of a module that does register routes), and this checker counts it. That
# direction is deliberate — a governance guard must not red-gate a PR on a path it cannot
# see — but it means the counts printed here are a STATIC-ONLY estimate and NOT a
# measurement of the live wall. The authoritative live split is whatever
# GET /api/a11oy/v1/govern/honestywall/status reports at run time. Cross-checked once by
# hand against that live read on main @ 23de209 (78 NATIVE-OK / 49 NO-MANIFEST of 127
# surfaces): the static pass saw every surface the live wall could read, plus 2 it could
# not. No count here is labelled MEASURED.
#
# Doctrine: pure observability. Adds nothing to the locked-8
# {F1,F4,F7,F11,F12,F18,F19,F22}; Λ stays Conjecture 1 (advisory, never a theorem);
# touches no surface logic and no other gate. Pure stdlib (ast, re, subprocess, pathlib).
#
# Usage:
#   python3 scripts/check_manifest_coverage.py [--root .] [--base-ref origin/main]
#                                              [--base-ids-from FILE] [--selftest]
# Exit codes:
#   0 — coverage at or above the recorded level and no new surface without a manifest
#   1 — coverage regressed, or a surface added in this PR ships no manifest
#   2 — configuration / usage error (registry unreadable)

import argparse
import ast
import re
import subprocess
import sys
import warnings
from pathlib import Path

REGISTRY_FILE = "szl3d_holographic.py"
REGISTRY_NAME = "SURFACES"

# Honest per-surface labels — the same vocabulary the wall uses for these two states, so a
# reader can line this output up against GET /govern/honestywall/status without a mapping.
NATIVE_OK = "NATIVE-OK"
NO_MANIFEST = "NO-MANIFEST"

# Coverage floor: the number of registered surfaces this checker saw a manifest for on main
# @ 23de209 (post-#890). A drop below it means an existing manifest route was removed.
# Raise it only when real coverage rises; never lower it to make a diff pass.
BASELINE_COVERED = 80

# The wall probes the a11oy namespace. A module that registers under a parameter (ns=...,
# "<ns>") is registered as a11oy by serve.py, so parameterized namespaces count; another
# estate's hardcoded namespace does not.
NAMESPACE = "a11oy"
_API_PATH = re.compile(
    r"/api/(?P<ns>\{[A-Za-z0-9_.]+\}|<[A-Za-z0-9_]+>|[A-Za-z0-9_-]+)/v1(?P<tail>/[A-Za-z0-9_{}<>./-]*)?"
)

# Attribute calls that wire an HTTP route in this estate, plus the Starlette Route object
# and the router-list splice used by the front-insert modules.
_ROUTE_ATTRS = {"get", "post", "add_api_route", "add_route", "api_route", "route", "include_router"}
_ROUTE_LIST_ATTRS = {"insert", "append", "extend"}

_MAX_TEMPLATE = 4096


def _norm(token):
    """Normalize an id / path segment exactly as the wall does: lowercase, drop non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", (token or "").lower())


# ---------------------------------------------------------------------------
# Registry — the single source of truth for what a "registered surface" is.
# ---------------------------------------------------------------------------

def registry_ids(text):
    """Ordered surface ids from a szl3d_holographic.py source text (SURFACES literal)."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if not any(isinstance(t, ast.Name) and t.id == REGISTRY_NAME for t in targets):
            continue
        try:
            surfaces = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(surfaces, list):
            return [s["id"] for s in surfaces
                    if isinstance(s, dict) and isinstance(s.get("id"), str) and s["id"]]
    return []


# ---------------------------------------------------------------------------
# Static manifest evidence.
# ---------------------------------------------------------------------------

def _resolve(node, env):
    """Best-effort single-string value of a str expression. Unresolved interpolations are
    kept as `{name}` so a path template stays recognizable as a template."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                inner = _resolve(value.value, env)
                if inner is None:
                    name = value.value.id if isinstance(value.value, ast.Name) else ""
                    inner = "{%s}" % name
                parts.append(inner)
            else:
                parts.append("{}")
        out = "".join(parts)
        return out if len(out) <= _MAX_TEMPLATE else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _resolve(node.left, env), _resolve(node.right, env)
        if left is not None and right is not None and len(left) + len(right) <= _MAX_TEMPLATE:
            return left + right
    return None


def _registers_routes(tree):
    """Does this module wire HTTP routes at all? Only such modules are treated as evidence,
    so a path named in a doc or a data file never counts on its own."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr in _ROUTE_ATTRS and node.args:
                    return True
                if func.attr in _ROUTE_LIST_ATTRS and "route" in _norm(
                        getattr(func.value, "attr", "") or getattr(func.value, "id", "")):
                    return True
            if isinstance(func, ast.Name) and func.id in ("Route", "APIRoute"):
                return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "register":
            args = node.args.args
            if args and args[0].arg == "app":
                return True
    return False


def _path_segments(template):
    """Normalized id-bearing segments of an /api/{ns}/v1 path template, or []."""
    segments = []
    for match in _API_PATH.finditer(template):
        namespace = match.group("ns")
        parameterized = namespace.startswith("{") or namespace.startswith("<")
        if not parameterized and namespace != NAMESPACE:
            continue  # another estate's namespace — the a11oy wall never reads it
        for segment in (match.group("tail") or "").split("/"):
            if segment and "{" not in segment and "<" not in segment and "." not in segment:
                segments.append(_norm(segment))
    return segments


def _string_lists(tree):
    """Every `NAME = ["a", "b", ...]` list of plain strings in the module."""
    out = {}
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else []
        if not targets or not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        values = [e.value for e in node.value.elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if not values or len(values) != len(node.value.elts):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                out[target.id] = values
    return out


def _batch_manifest_ids(tree, env, lists):
    """Ids covered by the #890 batch pattern: one manifest route registered per id, from a
    loop over a list of surface ids, at a path whose LAST segment is the loop variable."""
    covered = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)) or not isinstance(node.target, ast.Name):
            continue
        if isinstance(node.iter, ast.Name):
            ids = lists.get(node.iter.id)
        elif isinstance(node.iter, (ast.List, ast.Tuple)):
            ids = [e.value for e in node.iter.elts
                   if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        else:
            ids = None
        if not ids:
            continue
        placeholder = "{%s}" % node.target.id
        for inner in ast.walk(node):
            template = _resolve(inner, env) if isinstance(inner, ast.JoinedStr) else None
            if not template or not template.rstrip("/").endswith(placeholder):
                continue
            if _API_PATH.search(template):
                covered.update(ids)
                break
    return covered


def _module_env(tree):
    """Flat name -> resolved string map for path bases (module and function scope alike).
    Scopes are intentionally not isolated: a base only ever widens what a template resolves
    to, which keeps the checker permissive rather than red-gating a path it mis-scoped."""
    env = {"ns": NAMESPACE}
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if not targets or getattr(node, "value", None) is None:
            continue
        value = _resolve(node.value, env)
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                env[target.id] = value
    return env


def scan_module(text):
    """(id-bearing path segments, batch-manifest ids) declared by one Python module."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a module's own escape warnings are not this gate's business
            tree = ast.parse(text)
    except SyntaxError:
        return set(), set()
    if not _registers_routes(tree):
        return set(), set()
    env = _module_env(tree)
    segments = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.JoinedStr)):
            template = _resolve(node, env)
            if template:
                segments.update(_path_segments(template))
    return segments, _batch_manifest_ids(tree, env, _string_lists(tree))


def manifest_evidence(root):
    """Union of the static manifest evidence over every Python module in the tree."""
    segments, batch = set(), set()
    for path in sorted(Path(root).rglob("*.py")):
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        module_segments, module_batch = scan_module(text)
        segments |= module_segments
        batch |= module_batch
    return segments, batch


def classify(ids, segments, batch):
    """Per-surface honest status: NATIVE-OK when the wall would have a manifest to read."""
    covered_by_batch = {_norm(i) for i in batch}
    return {sid: (NATIVE_OK if _norm(sid) in segments or _norm(sid) in covered_by_batch
                  else NO_MANIFEST)
            for sid in ids}


# ---------------------------------------------------------------------------
# Ratchet — which surfaces are NEW in this PR.
# ---------------------------------------------------------------------------

def base_registry_ids(root, base_ref, ids_file):
    """(ids, note) for the registry as of the PR base. ids is None when it cannot be read —
    the ratchet is then skipped honestly rather than guessed at."""
    if ids_file:
        try:
            lines = Path(ids_file).read_text(encoding="utf-8").split()
        except OSError as exc:
            return None, f"base id list unreadable ({exc})"
        return [line.strip() for line in lines if line.strip()], f"base ids from {ids_file}"
    if not base_ref:
        return None, "no base ref given"
    try:
        text = subprocess.run(
            ["git", "show", f"{base_ref}:{REGISTRY_FILE}"],
            cwd=str(root), check=True, capture_output=True, text=True, timeout=60,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        return None, f"cannot read {REGISTRY_FILE} at {base_ref} ({detail.strip()[:120]})"
    try:
        return registry_ids(text), f"base ids from {base_ref}"
    except SyntaxError as exc:
        return None, f"{REGISTRY_FILE} at {base_ref} does not parse ({exc})"


# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------

def run(root, base_ref, ids_file):
    registry_path = Path(root) / REGISTRY_FILE
    try:
        ids = registry_ids(registry_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        print(f"CONFIG ERROR: cannot read the surface registry {registry_path}: {exc}",
              file=sys.stderr)
        return 2
    if not ids:
        print(f"CONFIG ERROR: no {REGISTRY_NAME} entries found in {registry_path}",
              file=sys.stderr)
        return 2

    segments, batch = manifest_evidence(root)
    status = classify(ids, segments, batch)
    covered = sorted(s for s in ids if status[s] == NATIVE_OK)
    uncovered = sorted(s for s in ids if status[s] == NO_MANIFEST)

    print("manifest-coverage guard — can the Honesty Wall read each registered surface?")
    print(f"  registered surfaces      : {len(ids)}")
    print(f"  {NATIVE_OK} (static evidence) : {len(covered)}")
    print(f"  {NO_MANIFEST} (static)        : {len(uncovered)}")
    print("  counts are a STATIC-ONLY estimate of the wall's in-process probe, not a")
    print("  measurement; GET /api/a11oy/v1/govern/honestywall/status is the live authority.")
    if uncovered:
        print(f"  surfaces the wall cannot verify: {', '.join(uncovered)}")

    ok = True

    if len(covered) < BASELINE_COVERED:
        print(f"\nFAIL: manifest coverage regressed — {len(covered)} surfaces have a "
              f"wall-readable manifest, below the recorded floor of {BASELINE_COVERED}. "
              f"An existing manifest route was removed or renamed.", file=sys.stderr)
        ok = False

    base_ids, note = base_registry_ids(root, base_ref, ids_file)
    if base_ids is None:
        print(f"\nratchet SKIPPED ({note}); the coverage floor still applies.")
    else:
        new_ids = [s for s in ids if s not in set(base_ids)]
        print(f"\nratchet ({note}): {len(new_ids)} surface(s) added in this diff"
              + (f" — {', '.join(new_ids)}" if new_ids else ""))
        missing = [s for s in new_ids if status[s] == NO_MANIFEST]
        if missing:
            print(f"\nFAIL: surface(s) added without an honesty manifest the wall can read: "
                  f"{', '.join(missing)}.\n"
                  f"      The wall matches an a11oy GET route under /api/{{ns}}/v1 whose path "
                  f"SEGMENT equals the surface id. Give each new surface such a route — a "
                  f"native manifest if it has a backend, or the honest UNAVAILABLE manifest "
                  f"in szl_surface_manifests.py (add the id to CLIENT_ONLY_SURFACES) if it is "
                  f"a client-only surface. Never upgrade the label to claim a backend that "
                  f"does not exist.", file=sys.stderr)
            ok = False

    if not ok:
        return 1
    print(f"\nmanifest-coverage: OK — {len(covered)}/{len(ids)} surfaces carry a manifest the "
          f"wall can read (floor {BASELINE_COVERED}); no new surface ships without one.")
    return 0


# ---------------------------------------------------------------------------
# Negative control — the checker must reject a planted gap before it is trusted.
# ---------------------------------------------------------------------------

_FIXTURE_REGISTRY = '''
SURFACES = [
    {"id": "withnative", "cat": "proof", "title": "Has A Native Route"},
    {"id": "withbatch", "cat": "more", "title": "Covered By The Batch Manifests"},
    {"id": "nomanifest", "cat": "more", "title": "Ships No Manifest"},
]
'''

_FIXTURE_MODULE = '''
CLIENT_ONLY = ["withbatch"]

def register(app, ns="a11oy"):
    base = f"/api/{ns}/v1/govern/manifest"

    @app.get(f"/api/{ns}/v1/withnative/status")
    def _status():
        return {}

    for sid in CLIENT_ONLY:
        app.add_api_route(f"{base}/{sid}", _status, methods=["GET"])
'''

_FIXTURE_DOC_ONLY = '''
"""A module that documents /api/a11oy/v1/nomanifest/status but wires no route."""
NOTE = "/api/a11oy/v1/nomanifest/status"
'''

_FIXTURE_OTHER_NS = '''
def register(app, ns="killinchu"):
    @app.get("/api/killinchu/v1/nomanifest/estimate")
    def _estimate():
        return {}
'''


def selftest():
    ids = registry_ids(_FIXTURE_REGISTRY)
    assert ids == ["withnative", "withbatch", "nomanifest"], ids
    print("[1] registry ids parsed from the SURFACES literal  OK")

    segments, batch = set(), set()
    for source in (_FIXTURE_MODULE, _FIXTURE_DOC_ONLY, _FIXTURE_OTHER_NS):
        module_segments, module_batch = scan_module(source)
        segments |= module_segments
        batch |= module_batch
    status = classify(ids, segments, batch)
    assert status["withnative"] == NATIVE_OK, status
    assert status["withbatch"] == NATIVE_OK, status
    print("[2] id-matching GET route and batch-manifest loop both read as NATIVE-OK  OK")

    assert status["nomanifest"] == NO_MANIFEST, status
    print("[3] negative control: a surface named only in a doc, and one whose only route is "
          "in another namespace, stay NO-MANIFEST  OK")

    assert scan_module("def helper():\n    return '/api/a11oy/v1/withnative/status'\n") == (
        set(), set()), "a module that wires no route must not count as evidence"
    print("[4] a module that registers no route is not evidence  OK")

    assert _path_segments("/api/a11oy/v1/brain/query") == ["brain", "query"], \
        "a two-segment path must not read as the joined id 'brainquery'"
    assert _path_segments("/api/{ns}/v1/govern/honestywall/status") == [
        "govern", "honestywall", "status"], "parameterized namespace must count"
    print("[5] segment equality (never substring) matches the wall's own rule  OK")

    print("\nok:true checks:5")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repo root to scan (default: .)")
    parser.add_argument("--base-ref", default="origin/main",
                        help="git ref of the PR base, for the new-surface ratchet")
    parser.add_argument("--base-ids-from",
                        help="file of base-revision surface ids, one per line (skips git)")
    parser.add_argument("--selftest", action="store_true",
                        help="run the negative control instead of scanning the repo")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    return run(args.root, args.base_ref, args.base_ids_from)


if __name__ == "__main__":
    sys.exit(main())
