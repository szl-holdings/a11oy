#!/usr/bin/env python3
"""Fail CI if the live Lean corpus numbers drift from the committed baseline.

Reads the committed baseline at .github/data/lean_numbers.json and compares the
core counts (declarations, axioms_raw, axioms_unique, sorries_raw) against a
freshly-computed measurement. Any difference fails the build with a clear diff.

Rationale (Doctrine v7 §2 + §3): declaration/axiom/sorry counts are public
claims. They must not drift silently. To intentionally change them, a committer
updates .github/data/lean_numbers.json in the same PR (an explicit, reviewable
"baseline-update" commit) — then this check passes again.

Usage:
  python check_numbers_drift.py --baseline .github/data/lean_numbers.json \
      --measured /tmp/measured.json
"""
from __future__ import annotations

import argparse
import json
import sys

# Counts that constitute a public claim and must not drift silently.
GUARDED_KEYS = ("declarations", "axioms_raw", "axioms_unique", "sorries_raw")


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(description="Numbers drift gate.")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--measured", required=True)
    args = ap.parse_args()

    base = load(args.baseline)["numbers"]
    meas = load(args.measured)["numbers"]

    diffs = []
    for key in GUARDED_KEYS:
        b = base.get(key)
        m = meas.get(key)
        if b != m:
            diffs.append((key, b, m))

    # Axiom-name set is also guarded (Doctrine v7 §3: no new axioms).
    base_axioms = set(base.get("axiom_names", []))
    meas_axioms = set(meas.get("axiom_names", []))
    added = sorted(meas_axioms - base_axioms)
    removed = sorted(base_axioms - meas_axioms)

    if not diffs and not added and not removed:
        print("OK: live Lean numbers match the committed baseline.")
        for key in GUARDED_KEYS:
            print(f"  {key}: {base.get(key)}")
        return 0

    print("DRIFT DETECTED — live Lean numbers differ from committed baseline.")
    print("(.github/data/lean_numbers.json). To accept, update that file in this PR.\n")
    for key, b, m in diffs:
        print(f"  {key}: baseline={b}  measured={m}")
    if added:
        print(f"  NEW AXIOMS (Doctrine v7 §3 — needs founder approval): {added}")
    if removed:
        print(f"  REMOVED AXIOMS: {removed}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
