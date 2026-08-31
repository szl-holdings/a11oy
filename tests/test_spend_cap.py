# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""Network-free tests for szl_spend_cap: the hard cumulative cap + kill-switch."""
import szl_spend_cap as sc


def _fresh(cap):
    return sc.SpendLedger(cap_usd=cap)


def test_allow_under_cap():
    led = _fresh(10.0)
    r = led.allow(3.0)
    assert r["allow"] is True
    assert r["remaining_usd"] == 10.0


def test_trips_at_cap_projection():
    led = _fresh(1.0)
    led.record(0.6, "unit")
    assert led.allow(0.5)["allow"] is False  # 0.6 + 0.5 > 1.0
    assert led.allow(0.3)["allow"] is True   # 0.6 + 0.3 <= 1.0


def test_hard_trip_when_spent_meets_cap():
    led = _fresh(1.0)
    led.record(1.0, "unit")
    assert led.tripped() is True
    assert led.allow(0.0)["allow"] is False


def test_kill_file_forces_trip(tmp_path, monkeypatch):
    kf = tmp_path / ".spend-KILL"
    kf.write_text("stop")
    monkeypatch.setenv("SZL_SPEND_KILL_FILE", str(kf))
    led = _fresh(1000.0)
    assert led.kill_engaged() is True
    assert led.allow(0.01)["allow"] is False


def test_ledger_chain_tamper_evident():
    led = _fresh(100.0)
    led.record(1.0, "a")
    led.record(2.0, "b")
    v = led.verify()
    assert v["intact"] is True and v["entries"] == 2
    led._entries[0]["amount_usd"] = 999.0  # tamper
    assert led.verify()["intact"] is False


def test_set_cap_updates_state():
    led = _fresh(5.0)
    led.record(4.0, "x")
    s = led.set_cap(10.0)
    assert s["cap_usd"] == 10.0
    assert s["remaining_usd"] == 6.0


def test_selftest_smoke():
    r = sc._selftest()
    assert r["a1_ok"] and r["a2_deny"] and r["chain_intact"]
