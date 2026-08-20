#!/usr/bin/env python3
"""Pre-ship honesty guard for the a11oy PINN benchmark.

Runs the shared verifiable-ai honesty gate over the committed benchmark
artifacts and exits non-zero if any of them overclaims. Wire this into CI (and
locally before shipping) so results.json / results_gpu.json can never regress
into an overclaim.

Usage:
    python benchmarks/pinn/honesty_guard.py                 # default artifacts
    python benchmarks/pinn/honesty_guard.py path/to/x.json  # explicit
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The reusable honesty core lives alongside the repo as `verifiable-ai/`.
_CORE = HERE.parents[1] / "verifiable-ai"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

try:
    from verifiable_ai import honesty_gate
except ImportError as e:  # pragma: no cover - environment guard
    print(f"[honesty-guard] cannot import verifiable_ai from {_CORE}: {e}", file=sys.stderr)
    raise SystemExit(2)


def main(argv: list[str]) -> int:
    if argv:
        targets = argv
    else:
        # Default: guard the shipped flagship artifact. results_gpu.json is a local
        # raw GPU artifact that is not committed to main, so only include it when it
        # actually exists (avoids a spurious MISSING failure in CI on main).
        targets = [str(HERE / "results.json")]
        gpu = HERE / "results_gpu.json"
        if gpu.exists():
            targets.append(str(gpu))
    failed = False
    for path in targets:
        p = Path(path)
        if not p.exists():
            print(f"[honesty-guard] MISSING  {p}")
            failed = True
            continue
        res = honesty_gate(json.loads(p.read_text()))
        if res.ok:
            print(f"[honesty-guard] PASS     {p.name}  ({res.arms_checked} arms)")
        else:
            failed = True
            print(f"[honesty-guard] OVERCLAIM {p.name}")
            for v in res.violations:
                print(f"    - {v}")
    if failed:
        print("[honesty-guard] FAILED — artifact overclaims; refusing to ship.")
        return 1
    print("[honesty-guard] OK — all artifacts honest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
