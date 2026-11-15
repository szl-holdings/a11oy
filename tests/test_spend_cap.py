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


def test_record_refuses_once_the_existing_cap_is_reached():
    led = _fresh(1.0)
    assert led.record(0.6, "unit")["recorded"] is True
    refused = led.record(0.5, "unit")
    assert refused["allow"] is False and refused["recorded"] is False
    assert refused["reason"] == "cap exceeded"
    assert led.state()["spent_usd"] == 0.6
    assert led.state()["entries"] == 1


def test_concurrent_records_cannot_pass_the_cap():
    import threading
    led = _fresh(1.0)
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait()
        results.append(led.record(0.6, "unit"))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(1 for item in results if item["recorded"]) == 1
    assert led.state()["spent_usd"] == 0.6


def test_invalid_amounts_do_not_change_the_total():
    led = _fresh(1.0)
    for value in (float("nan"), float("inf"), True, -1, 4e-7, "nope"):
        refused = led.record(value, "unit")
        assert refused["allow"] is False and refused["recorded"] is False
        assert refused["reason"] == "invalid amount"
    assert led.allow(float("nan"))["allow"] is False
    assert led.state()["spent_usd"] == 0.0
    assert led.state()["entries"] == 0


def test_admit_retry_is_bound_to_amount_and_payload():
    led = _fresh(10.0)
    first = led.admit(0.01, "op", "d")
    replay = led.admit(0.01, "op", "d")
    amount_clash = led.admit(100, "op", "d")
    digest_clash = led.admit(0.01, "op", "other")
    assert first["recorded"] is True
    assert replay["recorded"] is False and replay["reason"] == "duplicate"
    assert amount_clash["allow"] is False and amount_clash["reason"] == "operation reuse conflict"
    assert digest_clash["reason"] == "operation reuse conflict"
    assert led.state()["entries"] == 1
    assert led.state()["spent_usd"] == 0.01


def test_admission_memory_stays_protective_when_full():
    led = sc.SpendLedger(cap_usd=10.0, max_admissions=1)
    assert led.admit(0.2, "kept", "d")["recorded"] is True
    refused = led.admit(0.2, "new", "d")
    replay = led.admit(0.2, "kept", "d")
    assert refused["reason"] == "admission memory full"
    assert replay["reason"] == "duplicate" and replay["recorded"] is False
    assert led.state()["entries"] == 1


def test_trimmed_tail_verifies_retained_history_only():
    led = sc.SpendLedger(cap_usd=10.0, max_tail=2)
    led.record(0.1, "a")
    led.record(0.2, "b")
    led.record(0.3, "c")
    checked = led.verify()
    assert checked["intact"] is True
    assert checked["entries"] == 2
    assert checked["retained_only"] is True
    assert led.state()["spent_usd"] == 0.6
    led._entries[-1]["amount_usd"] = 9.0
    assert led.verify()["intact"] is False


def test_omitted_cap_keeps_the_current_decimal_value():
    led = _fresh(5)
    kept = led.set_cap(led.cap_usd)
    assert kept.get("cap_rejected") is not True
    assert kept["cap_usd"] == 5.0
    assert led.set_cap(5)["cap_usd"] == 5.0
    assert led.set_cap(4)["cap_usd"] == 4.0


def test_invalid_constructor_cap_does_not_grant_the_default(monkeypatch):
    monkeypatch.delenv("SZL_SPEND_CAP_USD", raising=False)
    assert sc.SpendLedger().state()["cap_usd"] == 25.0
    assert sc.SpendLedger(cap_usd=1).state()["cap_usd"] == 1.0
    for value in (float("nan"), float("inf"), float("-inf"), True, -1, "nope"):
        try:
            sc.SpendLedger(cap_usd=value)
        except sc.SpendCapError:
            continue
        raise AssertionError(f"invalid cap was accepted: {value!r}")
    monkeypatch.setenv("SZL_SPEND_CAP_USD", "nan")
    try:
        sc.SpendLedger()
    except sc.SpendCapError:
        return
    raise AssertionError("invalid env cap substituted a budget")


def test_admit_retries_once_and_rejects_a_different_payload():
    led = _fresh(1.0)
    first = led.admit(0.4, "op-1", "digest-a")
    second = led.admit(0.4, "op-1", "digest-a")
    clash = led.admit(0.4, "op-1", "digest-b")
    assert first["recorded"] is True and first["reason"] == "admitted"
    assert second["recorded"] is False and second["reason"] == "duplicate"
    assert clash["allow"] is False and clash["reason"] == "operation reuse conflict"
    assert led.state()["entries"] == 1
    assert led.state()["spent_usd"] == 0.4
