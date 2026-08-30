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

console_start = " if 'id=\"szl-series-a-cards\"' not in s:\n"
console_end = " k=s.find('id=\"inv-mode-js\"')"
start = text.find(console_start)
end = text.find(console_end, start)
if start < 0 or end < 0:
    raise SystemExit("v1 console insertion block was not found exactly")
new_console = """ if 'id="szl-series-a-cards"' not in s:
  st=s.find('id="cc-stream"');ri=s.find('id="cc-radar"')
  if st<0:raise SystemExit("cc-stream fold unavailable")
  if ri>=0:
   point=s.rfind("<",0,ri)
   if point<=st:raise SystemExit("cc-radar ordering invalid")
   insertion=block()
  else:
   close=s.find("</section>",st)
   if close<0:raise SystemExit("cc-stream section close unavailable")
   point=close+len("</section>")
   insertion=block()+"\\n<section id=\"cc-radar\" class=\"panel card\" aria-label=\"Operational radar\"><h2>Operational radar</h2><div class=\"empty unknown\">UNKNOWN · no measured radar feed is available.</div></section>"
  s=s[:point]+"\\n"+insertion+"\\n"+s[point:]
"""
text = text[:start] + new_console + text[end:]

old_secondary = """ if "timed out" not in s.lower():s=ins(s,"</body>",'<p class="sr-only">Live checks terminate as ready, unavailable, or timed out.</p>\\n',p)
 wr(p,s)
"""
new_secondary = """ if "timed out" not in s.lower():s=ins(s,"</body>",'<p class="sr-only">Live checks terminate as ready, unavailable, or timed out.</p>\\n',p)
 if "loadKernelLocked" not in s:
  x=r\"\"\"<script>
async function loadKernelLocked(signal){
 const response=await fetch('/api/a11oy/v1/honest',{cache:'no-store',signal:signal});
 if(!response.ok)throw new Error('honest HTTP '+response.status);
 const value=await response.json();
 return value&&value.locked_formula_count===8?8:null;
}
</script>
\"\"\"
  s=ins(s,"</body>",x,p)
 wr(p,s)
"""
if old_secondary not in text:
    raise SystemExit("v1 secondary landing block was not found exactly")
text = text.replace(old_secondary, new_secondary, 1)

if " V.khipu=" not in text:
    marker = " V.investor={title:'Investor'"
    if marker not in text:
        raise SystemExit("v1 investor view marker was not found")
    text = text.replace(
        marker,
        " V.khipu={title:'Khipu',render:function(c){renderKhipuPanel(c)}};\\n" + marker,
        1,
    )

V1.write_text(text, encoding="utf-8")
try:
    runpy.run_path(str(V1), run_name="__main__")
finally:
    if SELF.exists():
        SELF.unlink()
