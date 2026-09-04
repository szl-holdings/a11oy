#!/usr/bin/env python3
"""Correct the retained-anchor digest predicate to the ledger's sha256: format."""
from pathlib import Path

path = Path("szl_energy_ledger.py")
text = path.read_text(encoding="utf-8")
old = '                and len(first_prev) == 64\n'
new = '                and first_prev.startswith("sha256:")\n                and len(first_prev) == 71\n'
if text.count(old) != 1:
    raise SystemExit(f"expected one raw-digest predicate, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
