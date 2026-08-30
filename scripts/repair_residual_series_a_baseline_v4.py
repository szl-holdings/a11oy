#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Correct the temporary v3 source patcher, execute it, and self-remove."""
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "repair_residual_series_a_baseline_v2.py"
SELF = Path(__file__).resolve()
text = TARGET.read_text(encoding="utf-8")
old = '''    if 'id="szl-series-a-cards"' not in source:
        anchor = '<div id="inv-overlay"'
        if anchor not in source:
            anchor = '<script id="inv-mode-js"'
        source = insert_before_once(source, anchor, series_a_console_block(), path)
'''
new = '''    if 'id="szl-series-a-cards"' not in source:
        body = re.search(r"<body\\b[^>]*>", source, re.IGNORECASE)
        if not body:
            raise SystemExit("console: body tag unavailable for first-fold repair")
        source = source[:body.end()] + series_a_console_block() + source[body.end():]
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one v3 insertion block, observed {text.count(old)}")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
try:
    runpy.run_path(str(TARGET), run_name="__main__")
finally:
    if SELF.exists():
        SELF.unlink()
