# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.reidemeister (knot moves). thesis_v22.pdf §2."""
from a11oy.formulas import reidemeister as r


def test_r2_poke_cancels():
    assert r.reduced_word([1, -1]) == ()


def test_r1_kink_cancels():
    assert r.reduced_word([2, 2]) == ()


def test_nested_reduction():
    assert r.reduced_word([3, 1, -1, -3]) == ()


def test_unknot_detection():
    out = r.is_unknot([1, -1, 2, 2])
    assert out["value"] is True


def test_distinct_words_not_certified():
    out = r.equivalent([1, 2, 3], [1, 2])
    assert out["equivalent"] is False
    assert out["citation"] == "thesis_v22.pdf §2"
