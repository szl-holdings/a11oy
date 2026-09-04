#!/usr/bin/env python3
"""Replace one generated pathlib basename use with the ledger's existing os import."""
from pathlib import Path

path = Path("szl_energy_ledger.py")
text = path.read_text(encoding="utf-8")
old = "        active_name = Path(self.path).name\n"
new = "        active_name = os.path.basename(self.path)\n"
if text.count(old) != 1:
    raise SystemExit(f"expected one generated Path basename use, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
