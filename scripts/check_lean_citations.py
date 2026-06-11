#!/usr/bin/env python3
# =============================================================================
# check_lean_citations.py — catch broken / phantom Lean proof citations before
# they ship.
#
# WHY
#   Task #562 fixed a "phantom" proof citation in the a11oy policy gates: a gate
#   cited a Lean proof file (Lutar/Gate/BekensteinEntropyMeasure.lean) that never
#   existed in szl-holdings/lutar-lean, presenting an unproven claim as
#   machine-checked. Nothing stopped another phantom from being introduced. This
#   guard verifies that every citation which CLAIMS a real, machine-checked Lean
#   proof points at a file that actually exists in lutar-lean.
#
# WHAT IT PARSES
#   1. gates_manifest.json                  -> lean_file / lean_commit_sha / lean_status
#   2. docs/theorem-runtime-manifest.json   -> leanFile / leanStatus
#   3. packages/policy/src/gates/*_gate.ts  -> LEAN_FILE / LEAN_COMMIT constants
#      (the authoritative lean_status for a gate .ts is resolved from
#       gates_manifest.json by matching the gate filename; the .ts comment's
#       free-text "Lean status:" line is intentionally NOT trusted because it has
#       been observed to disagree with the manifest, e.g. anatomyReduction.)
#
# POLICY (honest disclosure preserved)
#   * gates_manifest.json + gate .ts carry an authoritative, COMMIT-PINNED
#     real-proof claim (lean_status == "real"). These have hard-fail authority:
#       - file present at the pinned commit ............... PASS
#       - file absent at the pinned commit but present at
#         the lutar-lean default branch .................. PASS + ::warning::
#                                                           (stale pin — repin)
#       - file present at NEITHER (exists nowhere) ........ FAIL  (phantom)
#   * Entries honestly marked phantom / conjectured / staged-advisory /
#     *-tracked-sorries / axiom-advisory / measured-* / mixed-* etc. are
#     REPORTED but never fail the build — honest disclosure is the whole point.
#   * docs/theorem-runtime-manifest.json is REPORTED but never hard-fails: that
#     manifest's own canonicalRule states "Lean proof status is scoped separately
#     from runtime test status", it carries NO commit pins, and its leanFile
#     pointers are aspirational/runtime-wiring references, not pinned proof
#     claims. Missing ones surface as warnings so drift is still visible.
#
# OFFLINE / TEST MODE
#   Set LEAN_CITATION_FIXTURE=<path-to-json> to resolve existence from a local
#   JSON map instead of the network (used by the negative-fixture self-test).
#   The map keys are "<ref>:<path>" and values are booleans. Unknown keys are
#   treated as "does not exist". This keeps the self-test fully offline.
#
# Exit codes: 0 = ok (warnings allowed), 1 = phantom real citation found,
#             2 = usage / parse error.
# =============================================================================
import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

LUTAR_REPO = "szl-holdings/lutar-lean"
DEFAULT_REF = "main"
RAW = "https://raw.githubusercontent.com/" + LUTAR_REPO + "/{ref}/{path}"

# Statuses that ASSERT a real, machine-checked Lean proof file. Only these have
# hard-fail authority. Everything else is honest non-proof disclosure.
REAL_PROOF_STATUSES = {"real"}

# Statuses we recognise as honest non-proof disclosures (reported, never fail).
KNOWN_HONEST_STATUSES = {
    "phantom", "conjectured", "conjecture-open", "staged-advisory",
    "axiom-advisory", "measured-empirical", "measured-conjectured",
    "theorem-with-tracked-sorries", "mixed-green-red", "lean-backed", "theorem",
    "unknown", "none",
}

_existence_cache = {}
_fixture = None


def _load_fixture():
    global _fixture
    if _fixture is not None:
        return _fixture
    path = os.environ.get("LEAN_CITATION_FIXTURE")
    if not path:
        _fixture = {}
        return _fixture
    with open(path, "r", encoding="utf-8") as fh:
        _fixture = json.load(fh)
    return _fixture


def lean_file_exists(path, ref):
    """Return True if `path` exists in lutar-lean at `ref` (default branch if ref is None)."""
    ref = ref or DEFAULT_REF
    key = "{}:{}".format(ref, path)
    if key in _existence_cache:
        return _existence_cache[key]

    fixture = _load_fixture()
    if os.environ.get("LEAN_CITATION_FIXTURE"):
        result = bool(fixture.get(key, False))
        _existence_cache[key] = result
        return result

    url = RAW.format(ref=ref, path=path)
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=25) as resp:
            result = resp.status == 200
    except urllib.error.HTTPError:
        result = False
    except Exception as exc:  # network hiccup — surface, do not silently pass
        print("::warning::existence check errored for {}@{}: {}".format(path, ref, exc))
        result = False
    _existence_cache[key] = result
    return result


def is_lutar_lean_path(p):
    """A citation we can verify must look like a concrete lutar-lean .lean file."""
    if not p:
        return False
    if " " in p or "*" in p:  # globs / prose like "Lutar/DPI/* and ..."
        return False
    return p.startswith("Lutar/") and p.endswith(".lean")


def norm_status(s):
    if not s:
        return "none"
    return str(s).strip().split()[0].lower()


class Result:
    def __init__(self):
        self.fails = []
        self.warns = []
        self.checked = 0
        self.report_only = 0


def verify_pinned(result, source, ident, lean_file, commit, status):
    """Verify an authoritative, commit-pinned real-proof claim."""
    s = norm_status(status)
    if s not in REAL_PROOF_STATUSES:
        result.report_only += 1
        return
    if not is_lutar_lean_path(lean_file):
        result.warns.append(
            "{} :: {} :: real-proof status but unverifiable reference {!r} "
            "(not a concrete Lutar/*.lean path) — skipped".format(source, ident, lean_file))
        return
    result.checked += 1
    if lean_file_exists(lean_file, commit):
        return
    # not at pinned commit; is it anywhere?
    if lean_file_exists(lean_file, DEFAULT_REF):
        result.warns.append(
            "{} :: {} :: STALE PIN — {} is absent at pinned commit {} but present "
            "on {} default branch; repin lean_commit_sha".format(
                source, ident, lean_file, (commit or "(none)")[:12], LUTAR_REPO))
    else:
        result.fails.append(
            "{} :: {} :: PHANTOM CITATION — {} (status={}) does not exist in {} "
            "at pinned commit {} NOR on the default branch. Either point at a real "
            "Lean file or mark the entry honestly (phantom / staged-advisory / "
            "conjectured).".format(
                source, ident, lean_file, status, LUTAR_REPO, (commit or "(none)")[:12]))


def check_gates_manifest(root, result):
    path = os.path.join(root, "gates_manifest.json")
    if not os.path.exists(path):
        return
    data = json.load(open(path, "r", encoding="utf-8"))
    for e in data:
        verify_pinned(result, "gates_manifest.json", e.get("name", "?"),
                      e.get("lean_file"), e.get("lean_commit_sha"), e.get("lean_status"))


def check_gate_ts(root, result):
    gates_glob = os.path.join(root, "packages", "policy", "src", "gates", "*_gate.ts")
    # authoritative status for a gate .ts comes from gates_manifest.json by filename
    gm_path = os.path.join(root, "gates_manifest.json")
    by_file = {}
    if os.path.exists(gm_path):
        for e in json.load(open(gm_path, "r", encoding="utf-8")):
            if e.get("file"):
                by_file[e["file"]] = e
    lean_file_re = re.compile(r'const\s+LEAN_FILE\s*=\s*"([^"]+)"')
    lean_commit_re = re.compile(r'const\s+LEAN_COMMIT\s*=\s*"([^"]+)"')
    for fp in sorted(glob.glob(gates_glob)):
        txt = open(fp, "r", encoding="utf-8").read()
        m = lean_file_re.search(txt)
        if not m:
            continue
        base = os.path.basename(fp)
        lean_file = m.group(1)
        cm = lean_commit_re.search(txt)
        commit = cm.group(1) if cm else None
        entry = by_file.get(base)
        if entry is None:
            result.warns.append(
                "gate .ts :: {} :: declares LEAN_FILE but has no gates_manifest.json "
                "entry — cannot resolve honest status; add it to the manifest".format(base))
            # fall back to verifying existence anywhere so a phantom is still caught
            if is_lutar_lean_path(lean_file) and not lean_file_exists(lean_file, DEFAULT_REF) \
                    and not lean_file_exists(lean_file, commit):
                result.fails.append(
                    "gate .ts :: {} :: PHANTOM CITATION — {} does not exist in {} "
                    "(no manifest entry to mark it honestly).".format(base, lean_file, LUTAR_REPO))
            continue
        verify_pinned(result, "gate .ts", base, lean_file, commit, entry.get("lean_status"))


def check_theorem_runtime_manifest(root, result):
    """Report-only: this manifest scopes Lean status separately and is unpinned."""
    path = os.path.join(root, "docs", "theorem-runtime-manifest.json")
    if not os.path.exists(path):
        return
    data = json.load(open(path, "r", encoding="utf-8"))
    entries = data.get("entries", [])
    resolved = 0
    missing = []
    skipped = 0
    for e in entries:
        lf = e.get("leanFile")
        if not is_lutar_lean_path(lf):
            skipped += 1
            continue
        result.report_only += 1
        if lean_file_exists(lf, DEFAULT_REF):
            resolved += 1
        else:
            missing.append("{} -> {} (leanStatus={})".format(
                e.get("id", "?"), lf, e.get("leanStatus")))
    print("  theorem-runtime-manifest.json: {} leanFile refs resolve on {} default "
          "branch, {} missing, {} non-lean/aspirational skipped".format(
              resolved, LUTAR_REPO, len(missing), skipped))
    print("    (report-only: this manifest scopes Lean proof status separately from "
          "runtime status per its canonicalRule and carries no commit pins.)")
    for m in missing:
        result.warns.append("theorem-runtime-manifest.json :: {} :: leanFile absent on "
                            "default branch (informational)".format(m))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a11oy Lean proof citations exist in lutar-lean.")
    ap.add_argument("--root", default=".", help="a11oy repo root (default: .)")
    args = ap.parse_args(argv)

    root = args.root
    if not os.path.exists(os.path.join(root, "gates_manifest.json")) and \
       not glob.glob(os.path.join(root, "packages", "policy", "src", "gates", "*_gate.ts")):
        print("::error::no gates_manifest.json or policy gates found under {!r} — wrong root?".format(root))
        return 2

    print("Lean citation guard — verifying real-proof citations against {}".format(LUTAR_REPO))
    result = Result()
    check_gates_manifest(root, result)
    check_gate_ts(root, result)
    check_theorem_runtime_manifest(root, result)

    print("\nVerified {} commit-pinned real-proof citation(s); {} honest non-proof "
          "reference(s) reported.".format(result.checked, result.report_only))

    for w in result.warns:
        print("::warning::" + w)

    if result.fails:
        print("\n=== BROKEN PROOF CITATIONS ({}) ===".format(len(result.fails)))
        for f in result.fails:
            print("::error::" + f)
        print("\nFAILED: at least one citation claims a real Lean proof but the file "
              "does not exist. Fix the path/commit or mark the entry honestly.")
        return 1

    print("\nOK: every real-proof citation resolves to a real Lean file in {}.".format(LUTAR_REPO))
    if result.warns:
        print("({} warning(s) above — stale pins / informational, not blocking.)".format(len(result.warns)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
