# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.bls_aggregate (BLS12-381). thesis_v22.pdf §2.

If py_ecc is present, exercise a real aggregate verify; otherwise assert the HONEST
error path (no fabricated 'verified').
"""
from a11oy.formulas import bls_aggregate


def test_honest_or_real():
    v = bls_aggregate.BLSAggregate()
    if not v.available:
        out = v.verify_same_message([b"pk"], b"msg", b"sig")
        assert out["ok"] is False
        assert "honest_error" in out
        return
    # real path
    sk1 = v.keygen(b"\x01" * 32); sk2 = v.keygen(b"\x02" * 32)
    msg = b"khipu-root"
    s1 = v.sign(sk1["sk"], msg)["signature"]
    s2 = v.sign(sk2["sk"], msg)["signature"]
    agg = v.aggregate([s1, s2])["aggregate_signature"]
    out = v.verify_same_message([sk1["pk"], sk2["pk"]], msg, agg)
    assert out["verified"] is True
    assert out["pairings_used"] == 2
    assert out["pairings_naive"] == 4
    assert out["citation"] == "thesis_v22.pdf §2"
