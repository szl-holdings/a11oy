# SPDX-License-Identifier: Apache-2.0
"""Adversarial contracts for the EnergyLedger rolling-restart repair."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import szl_energy_ledger as ledger_module
from szl_energy_ledger import EnergyLedger, JobRecord
from szl_energy_ledger_recovery import exclusive_writer_lock

NOW = 1_000_000.0
TS = datetime.fromtimestamp(NOW - 1.0, tz=timezone.utc).isoformat()


def job(index: int) -> JobRecord:
    return JobRecord(
        node=f"node-{index}",
        joules_measured=1000.0 + index,
        joules_label="measured",
        tokens=100 + index,
        wall_s=1.0,
        ts=TS,
        model=f"model-{index}",
        nvml_age_s=1.0,
    )


def _append_worker(path: str, index: int, queue) -> None:
    result = EnergyLedger(
        path=path,
        price_per_kwh_cents=45,
        writer_lock_timeout_s=10.0,
    ).append_job(job(index), now=NOW)
    queue.put({key: result.get(key) for key in ("appended", "duplicate", "error")})


def _hold_lock(path: str, ready, seconds: float) -> None:
    with exclusive_writer_lock(path, timeout_s=2.0):
        ready.set()
        time.sleep(seconds)


def test_stale_process_reloads_tail_before_deriving_sequence(tmp_path: Path) -> None:
    path = str(tmp_path / "energy.jsonl")
    first = EnergyLedger(path=path)
    stale = EnergyLedger(path=path)
    assert first.append_job(job(1), now=NOW)["appended"] is True
    assert stale.append_job(job(2), now=NOW)["appended"] is True
    final = EnergyLedger(path=path)
    assert final.verify()["ok"] is True
    assert [row["seq"] for row in final.entries()] == [0, 1]
    assert final.entries()[1]["prev_digest"] == final.entries()[0]["entry_digest"]


def test_concurrent_processes_produce_one_contiguous_chain(tmp_path: Path) -> None:
    path = str(tmp_path / "energy.jsonl")
    context = mp.get_context("spawn")
    queue = context.Queue()
    workers = [
        context.Process(target=_append_worker, args=(path, index, queue))
        for index in range(8)
    ]
    for process in workers:
        process.start()
    for process in workers:
        process.join(30)
        assert process.exitcode == 0
    outcomes = [queue.get(timeout=5) for _ in workers]
    assert all(item["appended"] is True for item in outcomes), outcomes
    final = EnergyLedger(path=path)
    verdict = final.verify()
    assert verdict["ok"] is True, verdict
    assert verdict["length"] == len(workers)
    assert [row["seq"] for row in final.entries()] == list(range(len(workers)))


def test_lock_timeout_fails_closed_without_record_or_charge(tmp_path: Path) -> None:
    path = str(tmp_path / "energy.jsonl")
    ledger = EnergyLedger(path=path, writer_lock_timeout_s=0.05)
    context = mp.get_context("spawn")
    ready = context.Event()
    holder = context.Process(target=_hold_lock, args=(path, ready, 0.5))
    holder.start()
    assert ready.wait(5)
    result = ledger.append_job(job(9), now=NOW)
    holder.join(10)
    assert result["appended"] is False
    assert result["error"] == "WRITER_LOCK_TIMEOUT"
    assert result["entry"] is None
    assert EnergyLedger(path=path).entries() == []


def test_partial_row_is_quarantined_and_bound_to_reset_receipt(tmp_path: Path) -> None:
    path = tmp_path / "energy.jsonl"
    path.write_bytes(b'{"partial":true')
    recovered = EnergyLedger(path=str(path))
    verdict = recovered.verify()
    assert verdict["ok"] is True, verdict
    assert verdict["length"] == 1
    decision = recovered.entries()[0]["receipt"]["decision"]
    assert decision["schema"] == "SZL.Energy.LedgerReset.v1"
    assert decision["reason"] == "INVALID_PRIOR_GENERATION_QUARANTINED"
    assert decision["prior_chain"]["ok"] is True
    assert decision["strict_errors"][0]["reason"] == "partial-final-line"
    quarantine_root = Path(f"{path}.quarantine")
    manifests = list(quarantine_root.glob("*/manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["aggregate_sha256"] == decision["prior_generation_sha256"]
    assert not path.read_bytes().startswith(b'{"partial"')


def test_forked_predecessor_is_preserved_as_forensic_generation(tmp_path: Path) -> None:
    path = tmp_path / "energy.jsonl"
    original = EnergyLedger(path=str(path))
    original.append_job(job(1), now=NOW)
    original.append_job(job(2), now=NOW)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[1]["prev_digest"] = "0" * 64
    rows[1]["entry_digest"] = ledger_module._entry_digest(
        rows[1]["seq"],
        rows[1]["prev_digest"],
        rows[1]["receipt"]["payload_digest"],
    )
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows)
        + "\n",
        encoding="utf-8",
    )

    recovered = EnergyLedger(path=str(path))
    assert recovered.verify()["ok"] is True
    assert len(recovered.entries()) == 1
    reset = recovered.entries()[0]["receipt"]["decision"]
    assert reset["prior_chain"]["ok"] is False
    assert "prev_digest" in reset["prior_chain"]["first_break"]["reason"]
    assert list(Path(f"{path}.quarantine").glob("*/energy.jsonl"))


def test_failed_durable_write_never_advances_memory(tmp_path: Path) -> None:
    ledger = EnergyLedger(path=str(tmp_path / "energy.jsonl"))

    class RefusingStore:
        backup_count = 4

        def iter_records(self):
            return iter(())

        def append(self, _entry):
            return SimpleNamespace(
                ok=False,
                status="unavailable",
                error="simulated full disk",
                bytes_written=0,
                rotated=False,
            )

        def status(self):
            return {"status": "unavailable", "bounded": True}

    ledger._store = RefusingStore()
    result = ledger.append_job(job(3), now=NOW)
    assert result["appended"] is False
    assert result["error"] == "STORAGE_UNAVAILABLE"
    assert ledger.entries() == []
    assert ledger.verify()["ok"] is True


def test_public_summary_is_bounded_and_cursor_pageable(tmp_path: Path) -> None:
    ledger = EnergyLedger(path=str(tmp_path / "energy.jsonl"))
    for index in range(55):
        assert ledger.append_job(job(index), now=NOW)["appended"] is True
    first = ledger.summary()
    assert first["ok"] is True
    assert len(first["receipts"]) == ledger_module.DEFAULT_LEDGER_PAGE_LIMIT == 50
    assert first["page"]["total_records"] == 55
    assert first["page"]["next_before_seq"] == 5
    assert len(json.dumps(first).encode("utf-8")) < 512_000

    second = ledger.summary(limit=50, before_seq=first["page"]["next_before_seq"])
    assert [row["seq"] for row in second["receipts"]] == list(range(5))
    assert second["page"]["complete"] is True


def test_sequence_field_is_part_of_chain_validity(tmp_path: Path) -> None:
    ledger = EnergyLedger(path=str(tmp_path / "energy.jsonl"))
    ledger.append_job(job(1), now=NOW)
    ledger._entries[0]["seq"] = 7
    ledger._entries[0]["entry_digest"] = ledger_module._entry_digest(
        7,
        ledger._entries[0]["prev_digest"],
        ledger._entries[0]["receipt"]["payload_digest"],
    )
    verdict = ledger.verify()
    assert verdict["ok"] is False
    assert verdict["first_break"]["reason"] == "seq is not contiguous and zero-based"
