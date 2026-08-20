#!/usr/bin/env python3
"""Extract each surface's exported `endpoints` array by resolving the EP-const
string literals declared in the file. Best-effort static parse (no JS engine)."""
import re, json, sys
from pathlib import Path

SURF_DIR = Path(__file__).resolve().parent.parent / "static" / "3d" / "surfaces"

# const NAME = "literal";  (also handles `template` with no ${})
CONST_RE = re.compile(r"""(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(["'`])([^"'`]*)\2""")
# export default { ... endpoints: [ ... ] ... }
EXPORT_RE = re.compile(r"endpoints\s*:\s*\[([^\]]*)\]")

def resolve(fp: Path):
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    consts = {}
    for m in CONST_RE.finditer(txt):
        name, _q, val = m.group(1), m.group(2), m.group(3)
        consts[name] = val
    m = EXPORT_RE.search(txt)
    eps = []
    if m:
        inner = m.group(1)
        # split by comma at top level
        for tok in inner.split(","):
            tok = tok.strip()
            if not tok:
                continue
            if tok.startswith(("\"", "'", "`")):
                eps.append(tok.strip("\"'`"))
            elif tok in consts:
                eps.append(consts[tok])
            else:
                # maybe const with query params; keep name for manual review
                eps.append(f"<UNRESOLVED:{tok}>")
    # strip query strings for endpoint hitting but keep original too
    out = []
    for e in eps:
        out.append(e)
    return out

def main():
    result = {}
    for fp in sorted(SURF_DIR.glob("*.js")):
        sid = fp.stem
        if sid in ("_showcase",):
            continue
        result[sid] = resolve(fp)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
