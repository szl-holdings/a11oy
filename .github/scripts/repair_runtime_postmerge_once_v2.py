#!/usr/bin/env python3
"""Run the reviewed repair and normalize the generated Markdown EOF."""
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

workcell = Path("audit/POST_MERGE_1986_REVIEW_REPAIR_2026-09-05.md")
workcell.write_text(
    workcell.read_text(encoding="utf-8").rstrip() + "\n",
    encoding="utf-8",
)
