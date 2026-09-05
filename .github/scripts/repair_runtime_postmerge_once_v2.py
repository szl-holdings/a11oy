#!/usr/bin/env python3
"""Run the reviewed repair and normalize generated source bytes."""
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

# The first one-shot generator deliberately uses raw templates. Normalize only
# the three generated docstring tokens that were over-escaped in those templates;
# do not perform a broad source rewrite.
replacements = {
    Path("szl_immune.py"): {
        r'    \"\"\"Return the key that actually verified the receipt, including rotation.\"\"\"':
            '    """Return the key that actually verified the receipt, including rotation."""',
    },
    Path("szl_agentic_loop.py"): {
        r'    \"\"\"Atomically append one run-of-runs record without lineage forks.\"\"\"':
            '    """Atomically append one run-of-runs record without lineage forks."""',
    },
    Path("tests/test_post_merge_1986_review_repairs.py"): {
        r'\"\"\"Adversarial regressions for the Codex findings left after PR #1986.\"\"\"':
            '"""Adversarial regressions for the Codex findings left after PR #1986."""',
    },
}
for path, mapping in replacements.items():
    text = path.read_text(encoding="utf-8")
    for old, new in mapping.items():
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f"{path}: expected one generated quoting target, found {count}"
            )
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

workcell = Path("audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md")
workcell.write_text(
    workcell.read_text(encoding="utf-8").rstrip() + "\n",
    encoding="utf-8",
)
