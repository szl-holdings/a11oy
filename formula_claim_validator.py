#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail closed when active formula claims drift from the canonical registry.

This guard deliberately excludes immutable receipts, archived snapshots, and the
vendored Lean source history.  It covers the live API projections and the public
surfaces that explain the formula maturity contract.  The registry remains the
only authority; this module does not introduce another formula list.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import szl_formula_registry as registry


ROOT = Path(__file__).resolve().parent
ACTIVE_CLAIM_PATHS = (
    "AGENTS.md",
    ".claude/rules/doctrine.md",
    "README.md",
    "STATUS.md",
    "a11oy_formula_tiers.py",
    "a11oy_constitution.py",
    "a11oy_brain_graph.py",
    "a11oy_landing.html",
    "pages/wires.html",
    "pages/pricing.html",
    "pages/landing.html",
    "web/living-anatomy.html",
    "web/proof.html",
    "docs/developers/API_REFERENCE.md",
    "training/build_seed.py",
    "training/build_formula_corpus.py",
    "training/build_brain_corpus.py",
    "training/szl_seed.jsonl",
    "training/szl_formula_corpus.jsonl",
    "training/szl_brain_corpus.jsonl",
    "training/szl_seed_full.jsonl",
    "szl3d_holographic.py",
    "static/3d/holographic.html",
)


def _old_locked_label() -> str:
    return "locked-" + str(8)


def _old_locked_theorem() -> str:
    return "locked_count_" + "eight"


def _old_locked_ids_compact() -> str:
    return "F1F4F7F11F12F18F19F22"


def claim_errors(paths: Iterable[str] = ACTIVE_CLAIM_PATHS, *, root: Path = ROOT) -> list[str]:
    """Return active-surface drift without treating honest denials as claims."""
    errors: list[str] = []
    old_label = _old_locked_label().lower()
    old_theorem = _old_locked_theorem().lower()
    old_ids = _old_locked_ids_compact()
    numeric_overclaim = re.compile(r"\b(?:8|189|200)\s+(?:locked[- ]?)?proven\b", re.I)
    assignment_overclaim = re.compile(
        r"\blocked(?:_flagged|_proven|_count|\s+count)?\s*[:=]\s*8\b", re.I
    )
    negation = re.compile(r"\b(?:not|never|does\s+not|cannot|rejects?|forbids?)\b", re.I)

    for relative in paths:
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: active claim surface missing")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            compact = re.sub(r"[^A-Za-z0-9]", "", line)
            stale = old_label in lowered or old_theorem in lowered or old_ids in compact
            numeric = (numeric_overclaim.search(line) is not None
                       or assignment_overclaim.search(line) is not None)
            if (stale or numeric) and not negation.search(line):
                errors.append(f"{relative}:{line_no}: stale formula claim: {line.strip()}")
    return errors


def projection_errors() -> list[str]:
    """Verify live Python projections derive their locked state from the registry."""
    import a11oy_brain_graph
    import a11oy_constitution
    import a11oy_formula_tiers

    errors: list[str] = []
    expected_ids = tuple(registry.LOCKED_PROVEN_IDS)
    expected_count = registry.LOCKED_PROVEN_COUNT

    if a11oy_formula_tiers.TIERS["locked_count"] != expected_count:
        errors.append("formula-tiers locked_count drift")
    if tuple(a11oy_formula_tiers.TIERS["locked_ids"]) != expected_ids:
        errors.append("formula-tiers locked_ids drift")
    if a11oy_formula_tiers.TIERS["signature_status"] != "UNSIGNED":
        errors.append("formula-tiers must preserve UNSIGNED registry status")
    experimental = tuple(row["id"] for row in a11oy_formula_tiers.EXPERIMENTAL)
    if experimental != registry.EXPECTED_EXPERIMENTAL_IDS:
        errors.append("formula-tiers experimental crosswalk drift")
    if tuple(a11oy_constitution.LOCKED_PROVEN) != expected_ids:
        errors.append("constitution locked set drift")

    graph = a11oy_brain_graph.build_brain_graph("a11oy")
    if graph["doctrine"]["locked_count"] != expected_count:
        errors.append("brain graph locked_count drift")
    if tuple(graph["doctrine"]["locked_ids"]) != expected_ids:
        errors.append("brain graph locked_ids drift")
    if graph["summary"]["locked_flagged"] != expected_count:
        errors.append("brain graph locked flags drift")
    return errors


def validate() -> None:
    errors = claim_errors() + projection_errors()
    if errors:
        raise ValueError("formula claim validation failed:\n" + "\n".join(errors))


if __name__ == "__main__":
    validate()
    print(
        "formula claims: OK — "
        f"{registry.LOCKED_PROVEN_COUNT} locked {list(registry.LOCKED_PROVEN_IDS)}; "
        f"experimental {list(registry.EXPECTED_EXPERIMENTAL_IDS)}; "
        f"signature {registry.FORMULA_REGISTRY_SIGNATURE_STATUS}"
    )
