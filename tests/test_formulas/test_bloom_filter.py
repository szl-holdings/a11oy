# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.bloom_filter (Bloom 1970, FN-free). thesis_v22.pdf §2."""
from a11oy.formulas import bloom_filter


def test_no_false_negatives():
    bf = bloom_filter.BloomFilter(expected_n=1000, target_fp=1e-3)
    keys = [f"receipt-{i}" for i in range(500)]
    for k in keys:
        bf.add(k)
    for k in keys:
        assert bf.definitely_absent(k) is False  # FN-free guarantee


def test_absent_is_safe_to_bypass():
    bf = bloom_filter.BloomFilter(expected_n=1000, target_fp=1e-4)
    bf.add("seen")
    assert bf.definitely_absent("never-inserted-xyz") is True


def test_rotation_preserves_membership():
    bf = bloom_filter.BloomFilter(expected_n=100, target_fp=1e-3)
    bf.add("old")
    bf.rotate()
    bf.add("new")
    # both still readable across the two live generations
    assert bf.definitely_absent("old") is False
    assert bf.definitely_absent("new") is False


def test_stats_schema():
    bf = bloom_filter.BloomFilter(expected_n=100, target_fp=1e-3)
    bf.add("x")
    s = bf.stats()
    assert s["citation"] == "thesis_v22.pdf §2"
    assert "query_after_insert" in s["lean_theorem"]
