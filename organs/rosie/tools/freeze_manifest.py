#!/usr/bin/env python3
"""tools/freeze_manifest.py — compute the frozen-baseline manifest for THIS Space.

Author: Yachay <yachay@szlholdings.dev>  ·  ADDITIVE  ·  Doctrine v11 LOCKED (749/14/163)
Signed-off-by: Yachay <yachay@szlholdings.dev>  ·  cosign keyid: szlholdings-cosign

Run this ONCE on the freeze commit (locally or in the Space repo) to fill the
`critical_file_hashes` in demo_freeze_baseline.manifest.json with real sha256
digests of the critical files that currently exist. The advisory startup check in
szl_demo_freeze.py then compares against these at runtime.

Usage:
    python tools/freeze_manifest.py            # update in place
    python tools/freeze_manifest.py --check    # exit 1 if current files drift
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

MANIFEST = "demo_freeze_baseline.manifest.json"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    check = "--check" in sys.argv
    mpath = Path(MANIFEST)
    if not mpath.is_file():
        print(f"❌ {MANIFEST} not found in cwd", file=sys.stderr)
        return 2
    m = json.loads(mpath.read_text())
    files = list(m.get("critical_file_hashes", {}).keys())
    current = {f: (sha256_file(Path(f)) if Path(f).is_file() else "MISSING") for f in files}

    if check:
        drift = {f: (m["critical_file_hashes"][f], current[f]) for f in files
                 if m["critical_file_hashes"][f] != current[f]}
        if drift:
            print("⚠️ DRIFT vs frozen baseline:")
            for f, (exp, act) in drift.items():
                print(f"  {f}: expected {exp} got {act}")
            return 1
        print(f"✅ all {len(files)} critical files match {m.get('freeze_tag')}")
        return 0

    m["critical_file_hashes"] = current
    mpath.write_text(json.dumps(m, indent=2))
    print(f"✅ wrote {len(files)} hashes into {MANIFEST} (freeze_tag={m.get('freeze_tag')})")
    for f, h in current.items():
        print(f"  {f}: {h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
