#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_formula_registry_guard.py — Proof-Carrying Formula Registry verifier.

HONESTY DOCTRINE (non-negotiable). Every formula a11oy serves via
``a11oy_formula_endpoints.py`` carries a ``lean_theorem`` name + a ``citation``.
This module CONFIRMS, against the bundled canonical corpus, that:

  1. the served ``lean_theorem`` name actually EXISTS as a real declaration in the
     corpus's Lean theorem list (``corpus/**/*.lean`` + ``proofs/**/*.lean`` +
     ``proofs/lean-theorem-tree.json``; the HF live mirror at ``/tmp/szl_math_corpus``
     is added best-effort when present), and
  2. the served ``citation`` RESOLVES to a real corpus entry (a bundled ``*.lean``
     file, or the thesis corpus version-lineage).

A formula that is NOT backed by the corpus is CAUGHT and REPORTED with an honest
status — it is NEVER surfaced as if proven:

  * ``verified``     — non-experimental, its Lean theorem name exists in the corpus.
  * ``unbacked``     — non-experimental yet its claimed Lean theorem is ABSENT from the
                       corpus (an overclaim — this is exactly what the guard exists to catch).
  * ``experimental`` — declared experimental / live-data / scaffolding (allodial,
                       entanglement, sovereign, kl, pinsker, aftershock, holevo,
                       reidemeister): a real computation with an OPEN / proposed Lean
                       obligation, deliberately NOT claimed as proven.

Λ-uniqueness stays **Conjecture 1** (never a theorem) — nothing here elevates it.

Pure/offline (stdlib only). Importable without FastAPI; the HTTP surface lives in
``a11oy_formula_endpoints.py`` (``GET /api/a11oy/v1/formulas/verify``).

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from typing import Iterable, Iterator

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ---- Corpus roots (bundled, offline-first) ---------------------------------------
_DEFAULT_ROOTS = (
    os.path.join(_HERE, "corpus"),
    os.path.join(_HERE, "proofs"),
)
_HF_LIVE_ROOT = "/tmp/szl_math_corpus"  # HF mirror, added best-effort when present
_THEOREM_TREE = os.path.join(_HERE, "proofs", "lean-theorem-tree.json")

# Lean keywords that introduce a NAMED declaration (the corpus theorem list).
_DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*"
    r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+|local\s+|"
    r"partial\s+|unsafe\s+|opaque\s+)*"
    r"(?:theorem|lemma|def|abbrev|axiom|instance|structure|inductive|class)\s+"
    r"([A-Za-z_][A-Za-z0-9_'\.]*)",
    re.MULTILINE,
)

# A single Lean identifier at the start (allows dotted / primed names).
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'\.]*")

# A Lean file reference embedded in a citation string.
_LEAN_FILE_RE = re.compile(r"([A-Za-z0-9_./-]+\.lean)")

# Tiers / names that are honestly NOT claimed as proven.
_EXPERIMENTAL_TIERS = frozenset({"experimental", "live-data", "scaffolding"})
_EXPERIMENTAL_NAMES = frozenset({"allodial", "entanglement", "sovereign"})


# ---- Corpus loading --------------------------------------------------------------
def _iter_lean_files(roots: Iterable[str]) -> Iterator[str]:
    seen: set[str] = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                if fn.endswith(".lean"):
                    path = os.path.join(dirpath, fn)
                    if path not in seen:
                        seen.add(path)
                        yield path


def _names_from_lean_text(text: str) -> set[str]:
    return {m.group(1) for m in _DECL_RE.finditer(text)}


def _names_from_theorem_tree(path: str) -> set[str]:
    names: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return names
    for decl in data.get("declarations", []) or []:
        nm = decl.get("name") if isinstance(decl, dict) else None
        if isinstance(nm, str) and nm:
            names.add(nm)
    return names


def _thesis_docs(roots: Iterable[str]) -> list[str]:
    docs: list[str] = []
    for root in roots:
        tdir = os.path.join(root, "thesis")
        if os.path.isdir(tdir):
            for dirpath, _dirs, files in os.walk(tdir):
                for fn in files:
                    docs.append(fn)
    return sorted(set(docs))


def load_corpus(roots: Iterable[str] | None = None, include_live: bool = True) -> dict:
    """Build the corpus view: Lean theorem-name set, lean-file set, thesis docs."""
    root_list = list(roots) if roots is not None else list(_DEFAULT_ROOTS)
    if include_live and os.path.isdir(_HF_LIVE_ROOT):
        root_list.append(_HF_LIVE_ROOT)

    theorem_names: set[str] = set()
    lean_files: set[str] = set()
    for path in _iter_lean_files(root_list):
        lean_files.add(os.path.basename(path))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except Exception:
            continue
        for nm in _names_from_lean_text(text):
            theorem_names.add(nm)
            theorem_names.add(nm.split(".")[-1])  # last dotted component

    for nm in _names_from_theorem_tree(_THEOREM_TREE):
        theorem_names.add(nm)
        theorem_names.add(nm.split(".")[-1])

    thesis_docs = _thesis_docs(root_list)
    return {
        "theorem_names": theorem_names,
        "lean_files": lean_files,
        "thesis_docs": thesis_docs,
        "thesis_available": bool(thesis_docs),
        "roots": [r for r in root_list if os.path.isdir(r)],
    }


@lru_cache(maxsize=1)
def _default_corpus() -> dict:
    return load_corpus()


# ---- Parsing served claims -------------------------------------------------------
def parse_lean_theorem_names(lean_theorem: str | None) -> list[str]:
    """Extract the claimed Lean declaration name(s) from a served ``lean_theorem``.

    Served format: ``File.lean::name (annotation)``; multiple names are separated by
    `` / `` (space-slash-space). A string with NO ``::`` claims no theorem (e.g.
    scaffolding / live-data) and yields ``[]``.
    """
    if not lean_theorem or "::" not in lean_theorem:
        return []
    names: list[str] = []
    _, _, tail = lean_theorem.partition("::")
    for part in re.split(r"\s+/\s+", tail):
        part = part.strip()
        if not part:
            continue
        if "::" in part:  # a later "File.lean::name" fragment
            part = part.split("::", 1)[1].strip()
        m = _IDENT_RE.match(part)
        if not m:
            continue
        token = m.group(0)
        if token.endswith(".lean"):  # a bare file name is not a theorem
            continue
        names.append(token)
    return names


def theorem_exists(token: str, corpus: dict) -> bool:
    tn = corpus["theorem_names"]
    return token in tn or token.split(".")[-1] in tn


def citation_resolves(citation: str | None, corpus: dict) -> tuple[bool, str]:
    """Does the citation resolve to a real corpus entry?

    Returns ``(resolved, note)``. A citation resolves when it references a bundled
    ``*.lean`` file that exists in the corpus, or the thesis corpus (version lineage).
    Purely-external literature citations do NOT resolve to a corpus artifact.
    """
    if not citation:
        return False, "no citation"
    lean_refs = _LEAN_FILE_RE.findall(citation)
    for ref in lean_refs:
        base = os.path.basename(ref)
        if base in corpus["lean_files"]:
            return True, f"lean file '{base}' present in corpus"
    if lean_refs:
        missing = ", ".join(sorted({os.path.basename(r) for r in lean_refs}))
        return False, f"cited lean file(s) absent from corpus: {missing}"
    if "thesis" in citation.lower():
        if corpus["thesis_available"]:
            return True, "thesis corpus present (version lineage)"
        return False, "thesis corpus absent"
    return False, "external literature citation (no corpus artifact)"


# ---- Per-formula + registry verification -----------------------------------------
def verify_formula(entry: dict, corpus: dict | None = None) -> dict:
    """Verify ONE served formula entry against the corpus. Never claims proven."""
    if corpus is None:
        corpus = _default_corpus()
    name = entry.get("name", "?")
    tier = entry.get("tier")
    lean_theorem = entry.get("lean_theorem")
    citation = entry.get("citation")

    claimed = parse_lean_theorem_names(lean_theorem)
    matched = [t for t in claimed if theorem_exists(t, corpus)]
    lean_theorem_exists = bool(matched)
    citation_exists, citation_note = citation_resolves(citation, corpus)
    in_corpus = lean_theorem_exists or citation_exists

    is_experimental = (tier in _EXPERIMENTAL_TIERS) or (name in _EXPERIMENTAL_NAMES)
    if is_experimental:
        status = "experimental"
    elif lean_theorem_exists:
        status = "verified"
    else:
        status = "unbacked"

    return {
        "name": name,
        "tier": tier or ("experimental" if is_experimental else "locked"),
        "in_corpus": in_corpus,
        "lean_theorem": lean_theorem,
        "claimed_theorems": claimed,
        "matched_theorems": matched,
        "lean_theorem_exists": lean_theorem_exists,
        "citation": citation,
        "citation_exists": citation_exists,
        "citation_note": citation_note,
        "status": status,
    }


def _load_index() -> list[dict]:
    from a11oy_formula_endpoints import _INDEX  # canonical served list
    return list(_INDEX)


def verify_registry(index: list[dict] | None = None, corpus: dict | None = None) -> list[dict]:
    """Verify EVERY served formula. The proof-carrying registry report body."""
    if index is None:
        index = _load_index()
    if corpus is None:
        corpus = _default_corpus()
    return [verify_formula(e, corpus) for e in index]


def registry_report(index: list[dict] | None = None, corpus: dict | None = None) -> dict:
    """Full honest report for the ``/formulas/verify`` endpoint."""
    if corpus is None:
        corpus = _default_corpus()
    results = verify_registry(index, corpus)
    counts: dict[str, int] = {"verified": 0, "unbacked": 0, "experimental": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    unbacked = [r["name"] for r in results if r["status"] == "unbacked"]
    return {
        "formulas": results,
        "count": len(results),
        "counts": counts,
        "unbacked": unbacked,
        "honest": not unbacked,  # True ⇔ no non-experimental formula overclaims
        "doctrine": "v11",
        "lambda_status": "Conjecture 1 (never a theorem)",
        "corpus": {
            "lean_theorem_names": len(corpus["theorem_names"]),
            "lean_files": len(corpus["lean_files"]),
            "thesis_docs": len(corpus["thesis_docs"]),
            "roots": corpus["roots"],
        },
    }


__all__ = [
    "load_corpus",
    "parse_lean_theorem_names",
    "theorem_exists",
    "citation_resolves",
    "verify_formula",
    "verify_registry",
    "registry_report",
]


if __name__ == "__main__":  # pragma: no cover — manual honest audit
    report = registry_report()
    print(json.dumps(report, indent=2, default=str))
    if report["unbacked"]:
        print(f"\nUNBACKED OVERCLAIMS: {report['unbacked']}", file=sys.stderr)
        sys.exit(1)
    print("\nOK — no non-experimental formula overclaims a Lean theorem.")

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.
