# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1.
"""test_durable_ledger.py — guards the DURABLE, BOUNDED, ROTATING receipt/energy store
that fixes the "database or disk is full" class (waveI_gapsB Gap 3).

The two properties the fix MUST hold, proven here with NO mocks (real files, real
fsync, real OSError on a degraded path):

  1. BOUNDS SIZE — hammering the store far past its cap keeps the on-disk footprint
     at or under the hard bound max_bytes * (backup_count + 1); rotation fires and the
     oldest segment is evicted (retention), so the disk can never fill.
  2. DEGRADES HONESTLY — when the storage is unwritable (full / read-only / missing),
     append() returns ok=False / status="unavailable" with the real error and NOTHING
     is fabricated as written; status() reports UNAVAILABLE. We NEVER claim a write we
     could not make.

Also proven: the real EnergyLedger routes through the bounded store, its hash chain
still verifies across rotated segments, and its storage_health() surfaces the honest
OK/PRESSURE/UNAVAILABLE signal used by /healthz.

Run:  pytest -q tests/test_durable_ledger.py     (stdlib + our modules only; no fastapi)
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import szl_durable_ledger as D
from szl_durable_ledger import DurableStore, OK, PRESSURE, UNAVAILABLE

import szl_energy_ledger as L
from szl_energy_ledger import EnergyLedger, JobRecord, GENESIS_PREV


# ===========================================================================
# 1. BOUNDS SIZE — the whole point: the footprint is capped, disk cannot fill.
# ===========================================================================
def test_footprint_bounded_under_hard_cap(tmp_path):
    path = os.path.join(tmp_path, "ledger.jsonl")
    # fsync=False here: durability is proven elsewhere; this test isolates the SIZE
    # BOUND and would otherwise spend all its time fsync'ing thousands of rotations.
    store = DurableStore(path, max_bytes=1024, backup_count=3, min_free_bytes=0,
                         fsync=False)
    hard_cap = store.max_total_bytes()
    assert hard_cap == 1024 * (3 + 1)

    # Write WAY more than the cap would ever hold if unbounded.
    for i in range(1500):
        r = store.append({"seq": i, "payload": "z" * 80})
        assert r.ok is True, r

    total = store.total_bytes()
    # The invariant that fixes "disk full": footprint stays at/under the hard cap.
    assert total <= hard_cap, (total, hard_cap)
    # And it actually rotated + evicted (i.e. the bound is real, not just a small write).
    assert store._counters.rotations > 0
    assert store._counters.dropped_segments > 0


def test_rotation_keeps_only_backup_count_segments(tmp_path):
    path = os.path.join(tmp_path, "ledger.jsonl")
    store = DurableStore(path, max_bytes=256, backup_count=2, min_free_bytes=0,
                         fsync=False)
    for i in range(800):
        assert store.append({"seq": i, "payload": "q" * 32}).ok

    # At most backup_count + 1 segments exist on disk (active + .1 + .2). No .3+.
    existing = [n for n in range(0, 8) if os.path.exists(store._segment_path(n))]
    assert existing and max(existing) <= store.backup_count, existing
    assert not os.path.exists(store._segment_path(store.backup_count + 1))


def test_retained_records_read_in_order_after_rotation(tmp_path):
    path = os.path.join(tmp_path, "ledger.jsonl")
    store = DurableStore(path, max_bytes=256, backup_count=2, min_free_bytes=0,
                         fsync=False)
    for i in range(500):
        assert store.append({"seq": i}).ok

    seqs = [rec["seq"] for rec in store.iter_records()]
    # Oldest→newest ordering across segments, newest present, oldest evicted (honest).
    assert seqs == sorted(seqs)
    assert seqs[-1] == 499
    assert seqs[0] > 0  # earliest records were evicted by retention, not fabricated


def test_zero_config_cannot_disable_the_bound(tmp_path):
    # A pathological max_bytes=0 / backup_count=0 must NOT re-create the unbounded bug.
    path = os.path.join(tmp_path, "ledger.jsonl")
    store = DurableStore(path, max_bytes=0, backup_count=0, min_free_bytes=0,
                         fsync=False)
    assert store.max_bytes >= 1024      # floored to a safe minimum
    assert store.backup_count >= 1      # rotation stays enabled
    for i in range(2000):
        assert store.append({"seq": i, "payload": "w" * 40}).ok
    assert store.total_bytes() <= store.max_total_bytes()


# ===========================================================================
# 2. DEGRADES HONESTLY — UNAVAILABLE, never a fabricated success.
# ===========================================================================
def test_unwritable_path_degrades_honestly(tmp_path):
    # Point the store UNDER a regular file so the parent "dir" can never be created /
    # opened — a real OSError, the same class as a full or read-only disk.
    afile = os.path.join(tmp_path, "afile")
    with open(afile, "w") as f:
        f.write("x")
    store = DurableStore(os.path.join(afile, "ledger.jsonl"), max_bytes=512)

    r = store.append({"seq": 0})
    assert r.ok is False
    assert r.status == UNAVAILABLE
    assert r.error  # the real OSError reason, surfaced (not swallowed)

    s = store.status()
    assert s["status"] == UNAVAILABLE
    assert s["writable"] is False
    # Nothing was fabricated as persisted.
    assert store._counters.appended == 0
    assert store._counters.write_failures >= 1
    assert not os.path.exists(store.path)


def test_status_reports_real_bound_and_never_green(tmp_path):
    path = os.path.join(tmp_path, "ledger.jsonl")
    store = DurableStore(path, max_bytes=2048, backup_count=2, min_free_bytes=0)
    store.append({"seq": 0})
    s = store.status()
    assert s["bounded"] is True
    assert s["max_total_bytes"] == 2048 * 3
    # Honest label vocabulary only — never "green".
    assert s["status"] in (OK, PRESSURE, UNAVAILABLE)
    assert s["status"] != "green"


def test_pressure_flagged_near_cap(tmp_path):
    path = os.path.join(tmp_path, "ledger.jsonl")
    # pressure at 50% of a small cap; write enough to cross it without rotating away.
    store = DurableStore(path, max_bytes=4096, backup_count=3,
                         pressure_ratio=0.5, min_free_bytes=0)
    saw_pressure = False
    for i in range(40):
        r = store.append({"seq": i, "payload": "p" * 60})
        assert r.ok
        if r.status == PRESSURE:
            saw_pressure = True
    assert saw_pressure, "active segment near the cap must report PRESSURE"


# ===========================================================================
# 3. Applied to the real a11oy energy/receipt ledger path.
# ===========================================================================
NOW = 1_000_000.0
FRESH_TS = datetime.fromtimestamp(NOW - 5.0, tz=timezone.utc).isoformat()


def _measured_job(i: int) -> JobRecord:
    return JobRecord(node=f"n{i}", joules_measured=78369.586 + i, joules_label="measured",
                     tokens=512, wall_s=8.0, ts=FRESH_TS, model="qwen2.5-coder:7b",
                     nvml_age_s=12.0, grid_price_eur_mwh=-2.90)


def test_energy_ledger_uses_bounded_store(tmp_path):
    path = os.path.join(tmp_path, "energy.jsonl")
    led = EnergyLedger(path=path, price_per_kwh_cents=45)
    # The durable store must be wired in (this is the fix being applied to the path).
    assert led._store is not None, "EnergyLedger must route through the durable store"
    sh = led.storage_health()
    assert sh["bounded"] is True
    assert sh["backend"] == "durable-rotating-jsonl"
    assert sh["status"] in (OK, PRESSURE)


def test_energy_ledger_footprint_bounded_and_chain_verifies(tmp_path, monkeypatch):
    # Force a tiny cap on the ledger's store so a modest run rotates + evicts.
    path = os.path.join(tmp_path, "energy.jsonl")
    led = EnergyLedger(path=path, price_per_kwh_cents=45)
    # Shrink the live store's bound in place (real store, no mock).
    led._store.max_bytes = 2048
    led._store.backup_count = 2
    led._store.fsync = False

    for i in range(200):
        out = led.append_job(_measured_job(i), now=NOW)
        assert out["appended"] is True

    total = led._store.total_bytes()
    assert total <= led._store.max_total_bytes(), (total, led._store.max_total_bytes())
    assert led._store._counters.rotations > 0

    # A fresh ledger over the same rotated segments reloads the RETAINED chain. Because
    # the oldest segment was EVICTED (retention, not archival — the honest, documented
    # limit), the retained head no longer roots at genesis, so verify() flags exactly
    # that at index 0. The important, provable property is that the retained subchain is
    # INTERNALLY CONSISTENT: every retained entry's prev_digest links to its predecessor
    # and every receipt still re-hashes to its digest. We assert that here so truncation
    # is honest + auditable, never a silently corrupted chain.
    led2 = EnergyLedger(path=path, price_per_kwh_cents=45)
    entries = led2.entries()
    assert len(entries) > 0
    # Receipts all re-hash (no tamper).
    assert led2.verify()["receipts_intact"] is True
    # Internal links: each entry (after the retained head) chains to the prior one.
    for prev_e, e in zip(entries, entries[1:]):
        assert e["prev_digest"] == prev_e["entry_digest"], (prev_e["seq"], e["seq"])
    # And the only break verify() reports is the genesis-root check at the retained head
    # (i.e. the chain was truncated by retention, honestly — not corrupted mid-stream).
    v = led2.verify()
    if not v["ok"]:
        assert v["first_break"]["index"] == 0, v
        assert "prev_digest" in v["first_break"]["reason"], v


def test_energy_ledger_honest_when_storage_degraded(tmp_path):
    afile = os.path.join(tmp_path, "afile")
    with open(afile, "w") as f:
        f.write("x")
    led = EnergyLedger(path=os.path.join(afile, "energy.jsonl"), price_per_kwh_cents=45)
    assert led._store is not None
    # Appending still returns a receipt result (never crashes the emit loop) ...
    out = led.append_job(_measured_job(0), now=NOW)
    assert "entry" in out
    # ... but the storage signal is HONEST that the write did not persist.
    sh = led.storage_health()
    assert sh["status"] == UNAVAILABLE
    assert sh.get("writable") is False
    assert led._last_store_status == UNAVAILABLE


def test_module_level_storage_health_accessor(tmp_path, monkeypatch):
    # ledger_storage_health() (used by serve.py /healthz) never raises and returns an
    # honest status dict.
    path = os.path.join(tmp_path, "energy.jsonl")
    led = EnergyLedger(path=path)
    monkeypatch.setattr(L, "_LEDGER", led)
    sig = L.ledger_storage_health()
    assert sig["status"] in (OK, PRESSURE, UNAVAILABLE)
    assert sig["status"] != "green"


# Also runnable as a plain script (mirrors the repo's self-test convention).
if __name__ == "__main__":
    import sys
    import pytest as _pytest
    sys.exit(_pytest.main([__file__, "-q"]))
