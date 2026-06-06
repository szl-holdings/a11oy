"""Tests for the Byzantine mesh quorum (F1) + FLP/CAP partition guard (F2).

Edge cases exercised at n = 4, 5, 7, 10 per ADR-0001 acceptance criteria.
Receipt round-trip verified through pinn_dsse when a cosign key is present;
UNSIGNED marker asserted when the key is absent (no fabricated signatures).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Support both repo-root layout and src/mesh layout.
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest  # noqa: E402

from mesh.quorum import (  # noqa: E402
    MeshQuorum,
    max_byzantine_faults,
    quorum_size,
)

try:
    import pinn_dsse  # noqa: E402
except Exception:  # pragma: no cover
    pinn_dsse = None


def hb(name: str, alive: bool):
    return {"organ": name, "ts": 0.0, "alive": alive}


def all_alive(names):
    return [hb(n, True) for n in names]


# ---- pure math -------------------------------------------------------------

@pytest.mark.parametrize(
    "n,expected_f",
    [(1, 0), (3, 0), (4, 1), (5, 1), (6, 1), (7, 2), (10, 3)],
)
def test_max_byzantine_faults(n, expected_f):
    assert max_byzantine_faults(n) == expected_f


@pytest.mark.parametrize("f,expected", [(0, 1), (1, 3), (2, 5), (3, 7)])
def test_quorum_size(f, expected):
    assert quorum_size(f) == expected


# ---- n = 4 (boundary: 4 == 3f+1 for f=1, feasible) -------------------------

def test_n4_f1_boundary_feasible():
    q = MeshQuorum(4, f=1)
    assert q.bft_feasible is True
    assert q.required == 3  # 2f+1
    v = q.healthy(all_alive("abcd"), sign=False)
    assert v.healthy is True and v.live == 4

def test_n4_f1_two_alive_unhealthy():
    q = MeshQuorum(4, f=1)
    v = q.healthy([hb("a", True), hb("b", True), hb("c", False), hb("d", False)], sign=False)
    assert v.healthy is False and v.live == 2 and v.required == 3

def test_n4_f2_not_feasible():
    # 4 < 3*2+1 = 7 → structurally not BFT for f=2
    q = MeshQuorum(4, f=2)
    assert q.bft_feasible is False
    v = q.healthy(all_alive("abcd"), sign=False)
    assert v.healthy is False and "not BFT-feasible" in v.reason


# ---- n = 5 (f=1) -----------------------------------------------------------

def test_n5_f1_all_alive_healthy():
    q = MeshQuorum(5, f=1)
    assert q.required == 3
    v = q.healthy(all_alive("abcde"), sign=False)
    assert v.healthy is True and v.live == 5

def test_n5_f1_three_alive_healthy_boundary():
    q = MeshQuorum(5, f=1)
    v = q.healthy([hb("a", True), hb("b", True), hb("c", True), hb("d", False), hb("e", False)], sign=False)
    assert v.healthy is True and v.live == 3 and v.required == 3

def test_n5_f1_two_alive_unhealthy():
    q = MeshQuorum(5, f=1)
    v = q.healthy([hb("a", True), hb("b", True)] + [hb(x, False) for x in "cde"], sign=False)
    assert v.healthy is False and v.live == 2


# ---- n = 7 (f=2) -----------------------------------------------------------

def test_n7_auto_f_is_2():
    q = MeshQuorum(7)  # auto f = floor(6/3) = 2
    assert q.f == 2 and q.required == 5 and q.bft_feasible

def test_n7_f2_five_alive_healthy_boundary():
    q = MeshQuorum(7)
    alive = [hb(x, True) for x in "abcde"] + [hb(x, False) for x in "fg"]
    v = q.healthy(alive, sign=False)
    assert v.healthy is True and v.live == 5 and v.required == 5

def test_n7_f2_four_alive_unhealthy():
    q = MeshQuorum(7)
    alive = [hb(x, True) for x in "abcd"] + [hb(x, False) for x in "efg"]
    v = q.healthy(alive, sign=False)
    assert v.healthy is False and v.live == 4


# ---- n = 10 (f=3) ----------------------------------------------------------

def test_n10_auto_f_is_3():
    q = MeshQuorum(10)  # floor(9/3) = 3
    assert q.f == 3 and q.required == 7 and q.bft_feasible

def test_n10_f3_seven_alive_healthy_boundary():
    q = MeshQuorum(10)
    alive = [hb(str(i), True) for i in range(7)] + [hb(str(i), False) for i in range(7, 10)]
    v = q.healthy(alive, sign=False)
    assert v.healthy is True and v.live == 7 and v.required == 7

def test_n10_f3_six_alive_unhealthy():
    q = MeshQuorum(10)
    alive = [hb(str(i), True) for i in range(6)] + [hb(str(i), False) for i in range(6, 10)]
    v = q.healthy(alive, sign=False)
    assert v.healthy is False and v.live == 6


# ---- partition guard (FLP/CAP, CP choice) ----------------------------------

def test_partition_guard_disagreeing_views():
    q = MeshQuorum(7)
    assert q.partition_guard({"a", "b", "c"}, {"a", "b"}) is True

def test_partition_guard_agreeing_views():
    q = MeshQuorum(7)
    assert q.partition_guard({"a", "b", "c"}, {"c", "b", "a"}) is False

def test_partition_forces_unhealthy_even_with_full_quorum():
    q = MeshQuorum(7)
    v = q.healthy(all_alive("abcdefg"), view_a={"a", "b", "c"}, view_b={"a", "b"}, sign=False)
    assert v.healthy is False and v.partition is True and "partition" in v.reason

def test_partition_none_views_no_partition():
    q = MeshQuorum(7)
    v = q.healthy(all_alive("abcdefg"), sign=False)
    assert v.partition is False and v.healthy is True


# ---- DSSE receipt ----------------------------------------------------------

def test_receipt_present_and_typed():
    q = MeshQuorum(5, f=1)
    v = q.healthy(all_alive("abcde"))  # sign=True default
    assert v.receipt is not None
    assert v.receipt.get("payloadType", "").endswith("mesh-quorum-receipt+json")

@pytest.mark.skipif(pinn_dsse is None, reason="pinn_dsse not importable")
def test_receipt_unsigned_marker_when_no_key(monkeypatch):
    monkeypatch.delenv("SZL_COSIGN_PRIVATE_PEM", raising=False)
    q = MeshQuorum(5, f=1)
    v = q.healthy(all_alive("abcde"))
    # With no key, pinn_dsse returns signed=False and an honesty marker.
    assert v.receipt.get("signed") is False
    assert "UNSIGNED" in v.receipt.get("honesty", "")

@pytest.mark.skipif(
    pinn_dsse is None or not os.environ.get("SZL_COSIGN_PRIVATE_PEM"),
    reason="cosign key not present — signing path not exercised",
)
def test_receipt_roundtrip_verify_with_key():
    q = MeshQuorum(5, f=1)
    v = q.healthy(all_alive("abcde"))
    res = pinn_dsse.verify_envelope(v.receipt)
    assert res.get("verified") is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
