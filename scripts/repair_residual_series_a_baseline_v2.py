#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Correct and execute the isolated residual baseline repair.
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "scripts" / "repair_residual_series_a_baseline.py"
SELF = Path(__file__).resolve()

text = V1.read_text(encoding="utf-8")

old_pattern = r'r"<(?:section|div)\b[^>]*\bid='
new_pattern = r'r"<[A-Za-z][A-Za-z0-9:_-]*\b[^>]*\bid='
if old_pattern not in text:
    raise SystemExit("v1 radar tag pattern was not found exactly")
text = text.replace(old_pattern, new_pattern, 1)

old_secondary = ''' if "timed out" not in s.lower():s=ins(s,"</body>",'<p class="sr-only">Live checks terminate as ready, unavailable, or timed out.</p>\\n',p)
 wr(p,s)
'''
new_secondary = ''' if "timed out" not in s.lower():s=ins(s,"</body>",'<p class="sr-only">Live checks terminate as ready, unavailable, or timed out.</p>\\n',p)
 if "loadKernelLocked" not in s:
  x=r"""<script>
async function loadKernelLocked(signal){
 const response=await fetch('/api/a11oy/v1/honest',{cache:'no-store',signal:signal});
 if(!response.ok)throw new Error('honest HTTP '+response.status);
 const value=await response.json();
 return value&&value.locked_formula_count===8?8:null;
}
</script>
"""
  s=ins(s,"</body>",x,p)
 wr(p,s)
'''
if old_secondary not in text:
    raise SystemExit("v1 secondary landing block was not found exactly")
text = text.replace(old_secondary, new_secondary, 1)

V1.write_text(text, encoding="utf-8")
try:
    runpy.run_path(str(V1), run_name="__main__")
finally:
    if SELF.exists():
        SELF.unlink()
