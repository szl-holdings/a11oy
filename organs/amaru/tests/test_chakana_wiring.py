# Copyright 2024 CHAKANA Project Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
chakana_wiring_test.py — Assertions for the v3 spine canonical wiring.

Directed-edge convention: (a, b) != (b, a).
AMARU is a directional cognitive pipeline; edges carry flow meaning.
Duplicate check therefore uses ordered pairs.
"""

import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))

from chakana_wiring import CHAKRAS, EDGES, maxwell_count, verify_rigid


def test_maxwell_rigid():
    """M must equal 0 (isostatic)."""
    assert verify_rigid() == True, (
        f"Maxwell count M = {maxwell_count()}, expected 0"
    )


def test_edge_count():
    """Exactly 21 edges required."""
    assert len(EDGES) == 21, (
        f"Expected 21 edges, got {len(EDGES)}"
    )


def test_all_chakras_connected():
    """Every chakra must appear in at least one edge endpoint."""
    endpoints = set()
    for (src, dst, _justification) in EDGES:
        endpoints.add(src)
        endpoints.add(dst)
    for chakra in CHAKRAS:
        assert chakra in endpoints, (
            f"Chakra '{chakra}' is isolated — appears in no edge"
        )


def test_no_duplicate_directed_edges():
    """
    No duplicate directed edges allowed.
    Directed convention: (A→B) and (B→A) are distinct and both legal,
    but (A→B) appearing twice is an error.
    """
    seen = set()
    for (src, dst, _justification) in EDGES:
        pair = (src, dst)
        assert pair not in seen, (
            f"Duplicate directed edge detected: {src} → {dst}"
        )
        seen.add(pair)


def test_no_self_loops():
    """No edge should point from a node to itself."""
    for (src, dst, _justification) in EDGES:
        assert src != dst, f"Self-loop detected on '{src}'"


def test_chakra_registry_count():
    """Exactly 9 chakras in the v3 spine."""
    assert len(CHAKRAS) == 9, (
        f"Expected 9 chakras, got {len(CHAKRAS)}"
    )


def test_edge_endpoints_are_known_chakras():
    """Every edge endpoint must be a registered chakra."""
    chakra_set = set(CHAKRAS)
    for (src, dst, _justification) in EDGES:
        assert src in chakra_set, f"Unknown source node '{src}'"
        assert dst in chakra_set, f"Unknown destination node '{dst}'"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_maxwell_rigid,
        test_edge_count,
        test_all_chakras_connected,
        test_no_duplicate_directed_edges,
        test_no_self_loops,
        test_chakra_registry_count,
        test_edge_endpoints_are_known_chakras,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{passed+failed} tests passed", end="")
    if failed == 0:
        print(" — ALL GREEN")
    else:
        print(f" — {failed} FAILURE(S)")
        sys.exit(1)
