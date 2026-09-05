#!/usr/bin/env python3
"""Run the reviewed repair and normalize exact generated source bytes."""
from __future__ import annotations

import runpy
from pathlib import Path


try:
    runpy.run_path(
        ".github/scripts/repair_runtime_postmerge_once.py",
        run_name="__main__",
    )
except SystemExit as exc:
    if exc.code not in (None, 0):
        raise

# The v1 one-shot generator uses raw templates containing two literal escape
# layers before each docstring quote. Prefer the exact two-layer token; retain a
# one-layer fallback only for a partially normalized retry. Each full target is
# path-scoped and must occur exactly once. No broad source rewrite is allowed.
replacements = {
    Path("szl_immune.py"): (
        (
            r'    \\"\\"\\"Return the key that actually verified the receipt, including rotation.\\"\\"\\"',
            r'    \"\"\"Return the key that actually verified the receipt, including rotation.\"\"\"',
        ),
        '    """Return the key that actually verified the receipt, including rotation."""',
    ),
    Path("szl_agentic_loop.py"): (
        (
            r'    \\"\\"\\"Atomically append one run-of-runs record without lineage forks.\\"\\"\\"',
            r'    \"\"\"Atomically append one run-of-runs record without lineage forks.\"\"\"',
        ),
        '    """Atomically append one run-of-runs record without lineage forks."""',
    ),
    Path("tests/test_post_merge_1986_review_repairs.py"): (
        (
            r'\\"\\"\\"Adversarial regressions for the Codex findings left after PR #1986.\\"\\"\\"',
            r'\"\"\"Adversarial regressions for the Codex findings left after PR #1986.\"\"\"',
        ),
        '"""Adversarial regressions for the Codex findings left after PR #1986."""',
    ),
}

for path, (candidates, replacement) in replacements.items():
    text = path.read_text(encoding="utf-8")
    matched = None
    for candidate in candidates:
        count = text.count(candidate)
        if count > 1:
            raise SystemExit(
                f"{path}: generated quoting target repeated {count} times"
            )
        if count == 1:
            matched = candidate
            break
    if matched is None:
        raise SystemExit(f"{path}: generated quoting target was not found")
    text = text.replace(matched, replacement, 1)
    if any(candidate in text for candidate in candidates):
        raise SystemExit(f"{path}: escaped quoting target survived normalization")
    if text.count(replacement) != 1:
        raise SystemExit(f"{path}: normalized docstring identity is not unique")
    path.write_text(text, encoding="utf-8")

workcell = Path("audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md")
workcell.write_text(
    workcell.read_text(encoding="utf-8").rstrip() + "\n",
    encoding="utf-8",
)
