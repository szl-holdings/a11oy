#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Console bundle-integrity guard (Doctrine v11).

Every emitted Vite chunk under a deploy `assets/` dir references sibling chunks by
hashed name (static `import`, re-export `export ... from`, dynamic `import(...)`, and
the `__vite__mapDeps` preload table). If the entry/layout chunk is re-hashed but the
importers are not, those references dangle -> the browser 404s the missing chunk and
every lazy /code SPA tab hangs on "loading...". This scanner fails (exit 1) when any
referenced chunk is absent from the folder, so an internally-inconsistent build can
never ship again.

stdlib only. Usage:
    check_bundle_integrity.py [ASSETS_DIR ...]
Default target: console/assets (relative to CWD / repo root).
"""

import os
import re
import sys

# Reference forms emitted by Vite, all resolving to a sibling asset file:
#   from"./index-XXXX.js"      import"./chunk.js"      import("./chunk.js")
#   export{...}from"./layout-XXXX.js"
#   __vite__mapDeps table entries: "assets/HomePage-XXXX.js", "assets/ui-XXXX.css"
# We capture the trailing basename and check it exists in the assets dir. Both .js
# and .css are checked: a dangling preloaded stylesheet is a real 404 too.
_REL_REF = re.compile(r"""["'](?:\.{1,2}/)+([A-Za-z0-9_.\-]+\.(?:js|css))["']""")
_ASSETS_REF = re.compile(r"""["'](?:\.{0,2}/)?assets/([A-Za-z0-9_.\-]+\.(?:js|css))["']""")


def scan_dir(assets_dir):
    """Return (ok, present_count, missing) for one assets dir.

    missing: dict {missing_basename: sorted list of referring files (basenames)}.
    """
    present = {
        f for f in os.listdir(assets_dir)
        if os.path.isfile(os.path.join(assets_dir, f))
    }
    missing = {}
    for fname in sorted(present):
        if not fname.endswith(".js"):
            continue
        path = os.path.join(assets_dir, fname)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        refs = set(_REL_REF.findall(text)) | set(_ASSETS_REF.findall(text))
        for ref in refs:
            if ref == fname:
                continue  # a chunk may reference its own name in a string
            if ref not in present:
                missing.setdefault(ref, []).append(fname)
    return (not missing), len(present), missing


def main(argv):
    targets = argv[1:] or ["console/assets"]
    overall_ok = True
    for target in targets:
        if not os.path.isdir(target):
            print(f"[bundle-integrity] MISSING DIR: {target}", file=sys.stderr)
            overall_ok = False
            continue
        ok, present_count, missing = scan_dir(target)
        if ok:
            print(f"[bundle-integrity] PASS: {target} — "
                  f"{present_count} assets, 0 dangling references.")
            continue
        overall_ok = False
        total_refs = sum(len(v) for v in missing.values())
        print(f"[bundle-integrity] FAIL: {target} — {present_count} assets, "
              f"{len(missing)} missing chunk name(s), {total_refs} dangling reference(s):",
              file=sys.stderr)
        for ref in sorted(missing):
            referrers = sorted(missing[ref])
            print(f"  - {ref}  <- imported by {len(referrers)} chunk(s), "
                  f"but NOT present in {target}", file=sys.stderr)
            for r in referrers[:5]:
                print(f"      · {r}", file=sys.stderr)
            if len(referrers) > 5:
                print(f"      · … and {len(referrers) - 5} more", file=sys.stderr)
    if not overall_ok:
        print("\n[bundle-integrity] Doctrine v11: internally-inconsistent bundle. "
              "Rebuild the console from source (web/ -> web/dist) and re-copy to "
              "console/; do NOT hand-edit chunk hashes.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
