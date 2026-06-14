# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_energy_ledger.py — guards the metering + signed-receipt hash-chained ledger.

Doctrine v11 (the whole point): a JouleCharge receipt is billable ONLY when joules_label
== MEASURED and the NVML sample is fresh (<30s); SAMPLE/ESTIMATE/stale are REFUSED.
Every receipt re-hashes to its digest; the chain is hash-linked (prev_digest) and tamper
breaks it; DRY-RUN bills with no STRIPE key; the same job never double-appends a charge.

Run: python test_energy_ledger.py   (also collectable by pytest)
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import szl_energy_ledger as L
from szl_energy_ledger import EnergyLedger, JobRecord, GENESIS_PREV
from joule_billing import sha256_canon

NOW = 1_000_000.0
FRESH_TS = datetime.fromtimestamp(NOW - 5.0, tz=timezone.utc).isoformat()
STALE_TS = datetime.fromtimestamp(NOW - 120.0, tz=timezone.utc).isoformat()


def _fresh_measured_job(node="betterwithage", joules=78369.586, tokens=512, model="qwen2.5-coder:7b"):
    return JobRecord(node=node, joules_measured=joules, joules_label="measured",
                     tokens=tokens, wall_s=8.0, ts=FRESH_TS, model=model,
                     nvml_age_s=12.0, grid_price_eur_mwh=-2.90)


def _ledger():
    tmp = tempfile.mktemp(suffix=".jsonl")
    return EnergyLedger(path=tmp, price_per_kwh_cents=45), tmp


def _cleanup(tmp):
    try:
        os.remove(tmp)
    except OSError:
        pass


def test_receipt_rehashes_to_its_digest():
    led, tmp = _ledger()
    try:
        r = led.append_job(_fresh_measured_job(), now=NOW)
        rec = r["entry"]["receipt"]
        assert sha256_canon(rec["decision"]) == rec["payload_digest"]
    finally:
        _cleanup(tmp)


def test_chain_verifies_end_to_end():
    led, tmp = _ledger()
    try:
        led.append_job(_fresh_measured_job(), now=NOW)
        led.append_job(_fresh_measured_job(joules=12345.0, model="bge-large"), now=NOW)
        v = led.verify()
        assert v["ok"] is True
        assert v["length"] == 2
        assert v["first_break"] is None
        assert v["links_intact"] and v["receipts_intact"]
        # genesis prev is 64 zeros; each link chains to prior entry_digest
        es = led.entries()
        assert es[0]["prev_digest"] == GENESIS_PREV
        assert es[1]["prev_digest"] == es[0]["entry_digest"]
    finally:
        _cleanup(tmp)


def test_tamper_one_entry_breaks_chain():
    led, tmp = _ledger()
    try:
        led.append_job(_fresh_measured_job(), now=NOW)
        led.append_job(_fresh_measured_job(joules=12345.0, model="bge-large"), now=NOW)
        assert led.verify()["ok"] is True
        # mutate a billed field on entry 0 -> receipt no longer re-hashes -> chain breaks
        led._entries[0]["receipt"]["decision"]["amount_cents"] = 999999
        v = led.verify()
        assert v["ok"] is False
        assert v["first_break"]["index"] == 0
        assert v["receipts_intact"] is False
    finally:
        _cleanup(tmp)


def test_reorder_breaks_chain_links():
    led, tmp = _ledger()
    try:
        led.append_job(_fresh_measured_job(), now=NOW)
        led.append_job(_fresh_measured_job(joules=22222.0, model="bge-large"), now=NOW)
        led._entries[0], led._entries[1] = led._entries[1], led._entries[0]
        v = led.verify()
        assert v["ok"] is False
        assert v["links_intact"] is False
    finally:
        _cleanup(tmp)


def test_sample_joules_blocked_from_billing():
    led, tmp = _ledger()
    try:
        r = led.append_job(JobRecord(
            node="chaski", joules_measured=5000.0, joules_label="sample",
            tokens=128, wall_s=2.0, ts=FRESH_TS, model="mistral", nvml_age_s=3.0), now=NOW)
        assert r["appended"] is True
        assert r["entry"]["billable"] is False
        assert r["entry"]["charge"]["status"] == "blocked"
    finally:
        _cleanup(tmp)


def test_estimate_joules_blocked_from_billing():
    led, tmp = _ledger()
    try:
        r = led.append_job(JobRecord(
            node="chaski", joules_measured=4000.0, joules_label="estimate",
            tokens=64, wall_s=1.0, ts=FRESH_TS, model="deepseek-r1:14b", nvml_age_s=3.0), now=NOW)
        assert r["entry"]["billable"] is False
        assert r["entry"]["charge"]["status"] == "blocked"
    finally:
        _cleanup(tmp)


def test_stale_measured_joules_blocked_from_billing():
    led, tmp = _ledger()
    try:
        # MEASURED label but NVML sample derived ~120s old (>30s) -> stale -> refused
        r = led.append_job(JobRecord(
            node="betterwithage", joules_measured=9000.0, joules_label="measured",
            tokens=256, wall_s=4.0, ts=STALE_TS, model="llama3.1:8b", nvml_age_s=None), now=NOW)
        assert r["entry"]["billable"] is False
        assert "stale" in r["entry"]["reason"].lower()
        assert r["entry"]["charge"]["status"] == "blocked"
    finally:
        _cleanup(tmp)


def test_dry_run_path_clean():
    # No STRIPE_API_KEY -> billable job dry-runs with would_charge_cents, no money moves.
    old = os.environ.pop("STRIPE_API_KEY", None)
    led, tmp = _ledger()
    try:
        r = led.append_job(_fresh_measured_job(), now=NOW)
        charge = r["entry"]["charge"]
        assert charge["status"] == "dry-run"
        assert charge["would_charge_cents"] >= 1
        assert "payment_intent" not in charge
        assert led.summary()["stripe_mode"] == "dry-run"
    finally:
        if old is not None:
            os.environ["STRIPE_API_KEY"] = old
        _cleanup(tmp)


def test_idempotency_same_job_never_double_appends():
    led, tmp = _ledger()
    try:
        r1 = led.append_job(_fresh_measured_job(), now=NOW)
        assert r1["appended"] is True
        r2 = led.append_job(_fresh_measured_job(), now=NOW)  # identical job
        assert r2["appended"] is False
        assert r2["duplicate"] is True
        assert r2["idempotency_key"] == r1["idempotency_key"]
        assert led.verify()["length"] == 1
    finally:
        _cleanup(tmp)


def test_idempotency_survives_restart():
    led, tmp = _ledger()
    try:
        led.append_job(_fresh_measured_job(), now=NOW)
        # fresh ledger over the same file reloads the chain + idem set
        led2 = EnergyLedger(path=tmp, price_per_kwh_cents=45)
        assert led2.verify()["length"] == 1
        r = led2.append_job(_fresh_measured_job(), now=NOW)
        assert r["appended"] is False and r["duplicate"] is True
        assert led2.verify()["length"] == 1
    finally:
        _cleanup(tmp)


def test_totals_correct():
    led, tmp = _ledger()
    try:
        led.append_job(_fresh_measured_job(), now=NOW)                       # billable dry-run
        led.append_job(JobRecord(node="chaski", joules_measured=5000.0,
                                 joules_label="sample", tokens=128, wall_s=2.0,
                                 ts=FRESH_TS, model="mistral", nvml_age_s=3.0), now=NOW)  # blocked
        led.append_job(JobRecord(node="betterwithage", joules_measured=9000.0,
                                 joules_label="measured", tokens=256, wall_s=4.0,
                                 ts=STALE_TS, model="llama3.1:8b"), now=NOW)              # stale->blocked
        t = led.totals()
        assert t["jobs"] == 3
        assert t["dry_run_count"] == 1
        assert t["blocked_count"] == 2
        assert t["would_charge_cents"] >= 1
        assert t["charged_cents"] == 0
        assert t["tokens_total"] == 512 + 128 + 256
        # only the billable MEASURED joules count toward billable joules
        assert abs(t["joules_measured_billable"] - 78369.586) < 1e-6
    finally:
        _cleanup(tmp)


def test_get_receipt_by_idem_and_rehash():
    led, tmp = _ledger()
    try:
        r = led.append_job(_fresh_measured_job(), now=NOW)
        idem = r["idempotency_key"]
        L._LEDGER = led  # point the module singleton at our temp ledger
        resp = L.handle_receipt(idem)
        assert resp["ok"] is True
        assert resp["rehash"]["matches"] is True
        missing = L.handle_receipt("joule-doesnotexist")
        assert missing["ok"] is False
    finally:
        L._LEDGER = None
        _cleanup(tmp)


def test_ledger_summary_shape():
    led, tmp = _ledger()
    try:
        led.append_job(_fresh_measured_job(), now=NOW)
        L._LEDGER = led
        s = L.handle_ledger()
        assert s["ok"] is True
        assert isinstance(s["receipts"], list) and len(s["receipts"]) == 1
        assert s["chain"]["ok"] is True
        assert s["totals"]["jobs"] == 1
        assert "doctrine" in s
    finally:
        L._LEDGER = None
        _cleanup(tmp)


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\nok:true checks:{passed}")
    sys.exit(0)
