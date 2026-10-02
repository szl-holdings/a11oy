#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only check of A11oy's declared router source ownership.

The original one-shot header migration is complete. This check rejects missing,
ambiguous, or retired declarations without rewriting a working tree. It verifies
declared ownership only; the governed consumer contract independently verifies
the integration with pinned szl-router source.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


LEGACY_PLATFORM = (
    "Python port of the canonical TypeScript source-of-truth at\n"
    "szl-holdings/platform/packages/llm-router/ (llm_router.ts)."
)
CANONICAL_ROUTER = (
    "Integrated A11oy adapter for the canonical routing source at\n"
    "szl-holdings/szl-router. A11oy owns the portfolio registry and operator\n"
    "interface; routing-runtime changes originate in the router repository and\n"
    "enter A11oy only through an explicit source-bound integration."
)

# Exact declarations keep this guard scoped to the completed migration.
REQUIREMENTS = {
    "szl_brain.py": ((CANONICAL_ROUTER,), (LEGACY_PLATFORM, "szl-holdings/platform/packages/llm-router/")),
    "organs/amaru/szl_brain.py": ((CANONICAL_ROUTER,), (LEGACY_PLATFORM, "szl-holdings/platform/packages/llm-router/")),
    "organs/sentra/szl_brain.py": ((CANONICAL_ROUTER,), (LEGACY_PLATFORM, "szl-holdings/platform/packages/llm-router/")),
    "szl_llm_registry.py": (
        (
            "szl_llm_registry — A11oy is the portfolio model registry and operator forum; szl-holdings/szl-router is the canonical routing-runtime source.",
            "  1. A11oy catalogs approved model routes; szl-router owns runtime routing and provider fallback.",
        ),
        (
            "szl_llm_registry — a11oy is THE LLM Hub for the SZL ecosystem.",
            "  1. a11oy holds ALL the LLMs — explicit, real, no mocked entries.",
        ),
    ),
    "a11oy_code.py": (
        ("a11oy.code — the integrated 7-tier organ-mapped view of the canonical szl-holdings/szl-router runtime.",),
        ("a11oy.code — the 7-tier organ-mapped LLM router baked into the anatomy.",),
    ),
    "src/pages/A11oyCode.tsx": (
        ("// a11oy.code — integrated 7-tier view of the canonical szl-holdings/szl-router runtime (Doctrine v11 §14).",),
        ("// a11oy.code — 7-tier organ-mapped LLM router UI (Doctrine v11 §14).",),
    ),
}


class AlignmentError(RuntimeError):
    pass


def check_alignment(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    failures: list[str] = []
    for relative, (required, retired) in REQUIREMENTS.items():
        candidate = root / relative
        try:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(root) or not candidate.is_file():
                raise AlignmentError("target is not a regular file within the source tree")
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError, AlignmentError) as exc:
            failures.append(f"{relative}: unavailable source ({type(exc).__name__})")
            continue
        for declaration in required:
            count = text.count(declaration)
            if count != 1:
                failures.append(f"{relative}: expected one canonical declaration, found {count}")
        if any(declaration in text for declaration in retired):
            failures.append(f"{relative}: retired source declaration remains")
    if failures:
        raise AlignmentError("\n".join(failures))
    return tuple(REQUIREMENTS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writes (also the default)")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="A11oy source tree (default: current directory)")
    args = parser.parse_args(argv)
    try:
        paths = check_alignment(args.root)
    except AlignmentError as exc:
        print(f"Router source authority is not aligned:\n{exc}", file=sys.stderr)
        return 1
    print("Declared router source authority is aligned:")
    for path in paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
