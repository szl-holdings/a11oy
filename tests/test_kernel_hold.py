# SPDX-License-Identifier: Apache-2.0
from szl_kernel_hold import inventory, kernel_status, refuse_mint_v1


def test_four_kernels_all_missing_v1():
    inv = inventory()
    assert inv["count"] == 4
    assert len(inv["missing_v1"]) == 4
    assert inv["all_done"] is False
    assert inv["agi_claim"] is False


def test_refuse_mint_without_load():
    out = refuse_mint_v1("szl-holdings/szl-maskmod")
    assert out["mint"] is False
    assert out["v1"] == "missing"
    assert out["honesty"] == "UNAVAILABLE"


def test_refuse_mint_even_after_claimed_load():
    out = refuse_mint_v1("szl-holdings/YARQA-ATTN", native_load=True, abi_verified=True)
    assert out["mint"] is False


def test_status_overdue_hold():
    s = kernel_status()
    assert s["estate_gate"] == "HOLD"
    assert s["overdue"] is True
    assert s["cutoff"] == "2026-09-13"
    assert s["missing_v1_count"] == 4
    assert s["agi_claim"] is False
