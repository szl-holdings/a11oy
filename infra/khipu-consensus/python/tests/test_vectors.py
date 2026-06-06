# SPDX-License-Identifier: Apache-2.0
"""Validate the Python reference verifier against the deterministic test vectors."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ))
from khipu_consensus import tally  # noqa: E402

HERE = os.path.dirname(__file__)
VEC = os.path.normpath(os.path.join(HERE, "..", "..", "testdata", "vectors.json"))


def test_vectors():
    v = json.load(open(VEC))
    pubkeys = v["pubkeys"]
    failures = []
    for case in v["cases"]:
        result = tally(v["action_hash"], case["signatures"], pubkeys,
                       threshold=v["threshold"], n=v["n"])
        exp = case["expect"]
        ok = result.decision == exp["decision"] and result.consensus_count == exp["consensus_count"]
        print(f"[{'PASS' if ok else 'FAIL'}] {case['name']}: {result.khipu_consensus} -> {result.decision}")
        if not ok:
            failures.append(case["name"])
    assert not failures, f"failed cases: {failures}"


if __name__ == "__main__":
    test_vectors()
    print("ALL PYTHON VECTOR TESTS PASSED")
