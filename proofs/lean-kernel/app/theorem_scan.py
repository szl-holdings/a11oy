#!/usr/bin/env python3
"""Scan the lutar-lean corpus for theorems/lemmas and classify each as
PROVEN / AXIOM / SORRY with file:line. Honest by construction:

- AXIOM: a line whose initial token (after optional private modifier) is `axiom`.
- SORRY: a theorem/lemma/def whose proof body contains a non-comment `sorry`
  token before the next top-level declaration.
- PROVEN: a theorem/lemma with no `sorry` in its body and not an axiom.

This is a static classifier (no kernel run). When the kernel build is GREEN,
PROVEN means the elaborator accepted the proof; SORRY entries are the open
obligations the kernel admits via the `sorry` axiom; AXIOM entries are explicit
postulates. The classification is conservative: any ambiguity is reported as the
weaker status (SORRY > AXIOM > PROVEN in honesty ordering is not assumed; we just
flag the literal tokens present).
"""
from __future__ import annotations
import json, os, re, sys

DECL_RE = re.compile(
    r"^(?P<indent>\s*)(?:@\[[^\]]*\]\s*)?(?:private\s+)?(?:noncomputable\s+)?(?:private\s+)?"
    r"(?P<kind>theorem|lemma|def|abbrev|instance)\s+(?P<name>[A-Za-z_][A-Za-z0-9_'.]*)"
)
AXIOM_RE = re.compile(r"^\s*(?:private\s+)?axiom\s+(?P<name>[A-Za-z_][A-Za-z0-9_'.]*)")
SORRY_RE = re.compile(r"\bsorry\b")
COMMENT_LINE_RE = re.compile(r"^\s*--")


def iter_lean_files(root: str):
    for base in ("Lutar", "TH8"):
        d = os.path.join(root, base)
        if os.path.isdir(d):
            for dp, _dirs, files in os.walk(d):
                for fn in files:
                    if fn.endswith(".lean"):
                        yield os.path.join(dp, fn)
    for top in ("Main.lean", "MainRef.lean", "Lutar.lean", "RefVectors.lean"):
        p = os.path.join(root, top)
        if os.path.exists(p):
            yield p


def scan(root: str) -> list[dict]:
    out = []
    for path in sorted(iter_lean_files(root)):
        rel = os.path.relpath(path, root)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        # First pass: axioms
        for i, line in enumerate(lines):
            m = AXIOM_RE.match(line)
            if m:
                out.append({"name": m.group("name"), "kind": "axiom",
                            "status": "AXIOM", "file": rel, "line": i + 1})
        # Second pass: decls + body sorry detection
        decl_idxs = [i for i, ln in enumerate(lines) if DECL_RE.match(ln)]
        for j, i in enumerate(decl_idxs):
            m = DECL_RE.match(lines[i])
            name = m.group("name")
            kind = m.group("kind")
            end = decl_idxs[j + 1] if j + 1 < len(decl_idxs) else len(lines)
            body = lines[i:end]
            has_sorry = any(SORRY_RE.search(ln) and not COMMENT_LINE_RE.match(ln)
                            for ln in body)
            # only count theorem/lemma as "theorems"; def/abbrev/instance noted too
            status = "SORRY" if has_sorry else "PROVEN"
            out.append({"name": name, "kind": kind, "status": status,
                        "file": rel, "line": i + 1})
    return out


def summarize(items: list[dict]) -> dict:
    theorems = [x for x in items if x["kind"] in ("theorem", "lemma")]
    return {
        "total_declarations": len(items),
        "theorems_and_lemmas": len(theorems),
        "proven": sum(1 for x in theorems if x["status"] == "PROVEN"),
        "sorry": sum(1 for x in items if x["status"] == "SORRY"),
        "axiom": sum(1 for x in items if x["status"] == "AXIOM"),
    }


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    items = scan(root)
    print(json.dumps({"summary": summarize(items), "items": items}, indent=2))
