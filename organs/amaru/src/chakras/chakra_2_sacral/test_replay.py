"""
chakra_2_sacral test_replay.py — pinned 5× byte-identical replay test.

Doctrine fix: previous REPLAY_5X.txt described the procedure but did not
commit the harness. External auditors could not reproduce because:
  (a) the test-data fixture (pirwa/codex stores) was not pinned in code, and
  (b) `top_k_features` returns a Python list whose underlying dict iteration
      order is implementation-defined for ties.

This file pins both. The canonical replay hash printed at the bottom is
the value any auditor should reproduce by running `python test_replay.py`
under Python 3.10+ on x86_64 with `numpy>=1.24`.

License: Apache-2.0
"""
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from kernel import yachay


def build_fixtures(test_data_seed: int = 0):
    """Pinned test data — pirwa: 20 features × 16-dim, codex: 25 priors × 16-dim.

    Insertion order is fixed (f00..f19 then p00..p24) so dict iteration
    order is deterministic in CPython 3.7+.
    """
    rng = np.random.default_rng(test_data_seed)
    pirwa_store = {f"f{i:02d}": rng.standard_normal(16) for i in range(20)}
    codex_store = {f"p{i:02d}": rng.standard_normal(16) for i in range(25)}
    return pirwa_store, codex_store


def canonical_serialize(result) -> bytes:
    """Serialize yachay() output to a stable byte string.

    `result` is (top_k_features: list[str], codex_priors: list[str]).
    Both are already ordered by score (desc), so they serialize stably.
    `sort_keys=True` is a no-op for lists but kept for any future dict outputs.
    """
    payload = {"top_k_features": list(result[0]),
               "codex_priors": list(result[1])}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    pirwa, codex = build_fixtures(test_data_seed=0)
    hashes = []
    for i in range(5):
        result = yachay(query=None, codex_store=codex, pirwa_store=pirwa, k=3, seed=42)
        digest = hashlib.sha256(canonical_serialize(result)).hexdigest()
        hashes.append(digest)
        print(f"Run {i+1}: {digest}")
    all_equal = len(set(hashes)) == 1
    print(f"\nByte-identical across 5 runs: {all_equal}")
    print(f"Canonical hash: {hashes[0]}")
    return 0 if all_equal else 1


if __name__ == "__main__":
    sys.exit(main())
