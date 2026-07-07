#!/usr/bin/env python3
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# check_surface_registry_sync.py — PERMANENT CI guard (Doctrine v11).
#
# Why this exists
# ---------------
# The a11oy flagship keeps the holographic-surface list in TWO places:
#   1. szl3d_holographic.py         -> SURFACES = [ {"id": "...", ...}, ... ]
#      (served by /api/a11oy/v1/holographic/info — the manifest the 3D UI loads)
#   2. static/3d/holographic.html   -> const SURFACES = [ { id: "...", ... }, ... ]
#      (parsed by a11oy_frontier_page.py to serve /api/a11oy/v1/frontier/surfaces
#       — the count the public flagship AND the fleet health watchdog read)
#
# On 2026-07-06 these silently diverged: szl3d_holographic.py was updated to add
# the wave-15 surfaces (giving 63) while holographic.html was NOT, so
# /frontier/surfaces kept reporting 59 and the fleet watchdog under-reported the
# live surface count for hours before it was caught by hand.
#
# This guard makes that class of drift impossible: it extracts the ordered list
# of surface ids from BOTH files and FAILS the job if the two sets differ (or the
# ordering differs), naming exactly which ids are missing from which file.
#
# Pure stdlib (re only). Org policy: github-owned actions, SHA-pinned in the yml.

import re
import sys
from pathlib import Path

PY_FILE = "szl3d_holographic.py"
HTML_FILE = "static/3d/holographic.html"

# Surface ids may contain letters, digits, underscores and hyphens (e.g. "counter-uas").
# Match {"id": "foo", ...} (python dict form) — double-quoted key and value.
_PY_ID = re.compile(r'\{\s*"id"\s*:\s*"([A-Za-z0-9_-]+)"')
# Match { id: "foo", ... } (JS object literal form) — bare key, double-quoted value.
_HTML_ID = re.compile(r'\{\s*id\s*:\s*"([A-Za-z0-9_-]+)"')


def _extract(path: Path, pattern: re.Pattern) -> list:
    if not path.exists():
        print(f"FAIL: expected surface-registry file not found: {path}", file=sys.stderr)
        sys.exit(2)
    text = path.read_text(encoding="utf-8")
    return pattern.findall(text)


def main(root: str = ".") -> int:
    base = Path(root)
    py_ids = _extract(base / PY_FILE, _PY_ID)
    html_ids = _extract(base / HTML_FILE, _HTML_ID)

    py_set, html_set = set(py_ids), set(html_ids)
    ok = True

    if len(py_ids) != len(py_set):
        dupes = sorted({i for i in py_ids if py_ids.count(i) > 1})
        print(f"FAIL: duplicate ids in {PY_FILE}: {dupes}", file=sys.stderr)
        ok = False
    if len(html_ids) != len(html_set):
        dupes = sorted({i for i in html_ids if html_ids.count(i) > 1})
        print(f"FAIL: duplicate ids in {HTML_FILE}: {dupes}", file=sys.stderr)
        ok = False

    missing_in_html = sorted(py_set - html_set)
    missing_in_py = sorted(html_set - py_set)
    if missing_in_html:
        print(f"FAIL: ids in {PY_FILE} but MISSING from {HTML_FILE}: {missing_in_html}", file=sys.stderr)
        ok = False
    if missing_in_py:
        print(f"FAIL: ids in {HTML_FILE} but MISSING from {PY_FILE}: {missing_in_py}", file=sys.stderr)
        ok = False

    # Ordering must match too (the UI relies on a stable surface order).
    if ok and py_ids != html_ids:
        for i, (a, b) in enumerate(zip(py_ids, html_ids)):
            if a != b:
                print(f"FAIL: surface order diverges at index {i}: "
                      f"{PY_FILE}='{a}' vs {HTML_FILE}='{b}'", file=sys.stderr)
                break
        ok = False

    if not ok:
        print(f"\nsurface-registry-sync: DRIFT DETECTED "
              f"({len(py_ids)} in {PY_FILE}, {len(html_ids)} in {HTML_FILE}).", file=sys.stderr)
        return 1

    print(f"surface-registry-sync: OK — both registries list the same {len(py_ids)} "
          f"surfaces in the same order.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
