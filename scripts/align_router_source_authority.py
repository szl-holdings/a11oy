#!/usr/bin/env python3
"""Align A11oy router adapters with the canonical szl-router repository.

The script is deliberately exact-string based. It refuses to silently continue
when an expected legacy statement is absent, which prevents a broad or ambiguous
rewrite of unrelated product documentation.
"""
from __future__ import annotations

from pathlib import Path


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


class AlignmentError(RuntimeError):
    pass


def replace_exact(path: Path, old: str, new: str, *, required: bool = True) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if required:
            raise AlignmentError(f"expected legacy statement is absent in {path}")
        return False
    updated = text.replace(old, new)
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    changed: list[str] = []

    for candidate in (
        Path("szl_brain.py"),
        Path("organs/amaru/szl_brain.py"),
        Path("organs/sentra/szl_brain.py"),
    ):
        if candidate.exists() and replace_exact(
            candidate,
            LEGACY_PLATFORM,
            CANONICAL_ROUTER,
            required=(candidate == Path("szl_brain.py")),
        ):
            changed.append(str(candidate))

    registry = Path("szl_llm_registry.py")
    if not registry.exists():
        raise AlignmentError("szl_llm_registry.py is missing")
    replace_exact(
        registry,
        "szl_llm_registry — a11oy is THE LLM Hub for the SZL ecosystem.",
        (
            "szl_llm_registry — A11oy is the portfolio model registry and operator "
            "forum; szl-holdings/szl-router is the canonical routing-runtime source."
        ),
    )
    replace_exact(
        registry,
        "  1. a11oy holds ALL the LLMs — explicit, real, no mocked entries.",
        (
            "  1. A11oy catalogs approved model routes; szl-router owns runtime "
            "routing and provider fallback."
        ),
    )
    changed.append(str(registry))

    code = Path("a11oy_code.py")
    if not code.exists():
        raise AlignmentError("a11oy_code.py is missing")
    replace_exact(
        code,
        "a11oy.code — the 7-tier organ-mapped LLM router baked into the anatomy.",
        (
            "a11oy.code — the integrated 7-tier organ-mapped view of the canonical "
            "szl-holdings/szl-router runtime."
        ),
    )
    changed.append(str(code))

    source_page = Path("src/pages/A11oyCode.tsx")
    if source_page.exists():
        text = source_page.read_text(encoding="utf-8")
        marker = "// a11oy.code — 7-tier organ-mapped LLM router UI (Doctrine v11 §14)."
        replacement = (
            "// a11oy.code — integrated 7-tier view of the canonical "
            "szl-holdings/szl-router runtime (Doctrine v11 §14)."
        )
        if marker in text:
            source_page.write_text(
                text.replace(marker, replacement),
                encoding="utf-8",
                newline="\n",
            )
            changed.append(str(source_page))

    if LEGACY_PLATFORM in Path("szl_brain.py").read_text(encoding="utf-8"):
        raise AlignmentError("root A11oy router adapter still names the retired platform path")
    if "a11oy is THE LLM Hub" in registry.read_text(encoding="utf-8"):
        raise AlignmentError("A11oy registry still claims canonical runtime ownership")
    if not changed:
        raise AlignmentError("no source-authority files changed")

    print("aligned router source authority:")
    for path in changed:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
