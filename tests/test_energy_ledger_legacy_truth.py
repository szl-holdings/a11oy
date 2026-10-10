"""Ledger compatibility: preserve history, never manufacture current billability."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import szl_energy_ledger as ledger
import szl_energy_live as live
import pytest
from joule_billing import JouleReading, build_receipt, d_idem


NOW = 1_000_000.0
TS = datetime.fromtimestamp(NOW - 5, tz=timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def _local_windows_lock(monkeypatch):
    """Exercise receipt semantics on Windows; POSIX flock is separately tested."""
    if ledger.os.name != "nt":
        return

    @contextmanager
    def _lock(path, timeout):
        yield {"test_lock": True}

    monkeypatch.setattr(ledger, "_exclusive_writer_lock", _lock)


def _job(**overrides):
    raw = {
        "node": "gpu-1",
        "joules_measured": 78369.586,
        "joules_label": "MEASURED",
        "tokens": 512,
        "wall_s": 8.0,
        "ts": TS,
        "model": "test-model",
        "nvml_age_s": 5.0,
    }
    raw.update(overrides)
    return ledger.JobRecord.from_dict(raw)


def test_new_measured_claim_is_nonbillable_even_with_stripe_key(monkeypatch, tmp_path):
    monkeypatch.setenv("STRIPE_API_KEY", "test-key-not-used")

    def _forbid_stripe(*args, **kwargs):
        raise AssertionError("Stripe must not be called without exclusive-job attribution")

    monkeypatch.setattr(ledger, "charge_stripe", _forbid_stripe, raising=False)
    led = ledger.EnergyLedger(path=str(tmp_path / "new.jsonl"))
    result = led.append_job(_job(), now=NOW)
    assert result["appended"] is True
    entry = result["entry"]
    assert entry["billable"] is False
    assert entry["reason"] == "ATTRIBUTION_UNVERIFIED"
    assert entry["charge"] == {"status": "blocked", "reason": "ATTRIBUTION_UNVERIFIED"}
    assert entry["receipt"]["decision"]["joules_measured"] == 0.0
    assert entry["receipt"]["decision"]["joules_label"] == "UNKNOWN"
    assert entry["receipt"]["decision"]["amount_cents"] == 0
    assert entry["receipt"]["decision"]["honesty"]["revenue"] == "ZERO"
    assert entry["job"]["joules_input"] == 78369.586
    assert entry["job"]["joules_input_label"] == "MEASURED"
    assert led.verify()["ok"] is True
    assert led.totals()["historical_reported_joules_input"] == 78369.586
    assert led.totals()["joules_measured_billable"] is None
    assert led.summary()["stripe_mode"] == "blocked-pending-attribution"


def test_source_job_digest_keeps_distinct_nonbillable_jobs_distinct(tmp_path):
    led = ledger.EnergyLedger(path=str(tmp_path / "idempotence.jsonl"))
    first = led.append_job(_job(), now=NOW)
    duplicate = led.append_job(_job(), now=NOW)
    second = led.append_job(_job(model="second-model"), now=NOW)
    assert first["appended"] is True
    assert duplicate["duplicate"] is True
    assert second["appended"] is True
    assert first["idempotency_key"] != second["idempotency_key"]
    assert led.verify()["ok"] is True
    assert led.verify()["length"] == 2


def test_replayed_source_job_dedupes_when_derived_age_changes(tmp_path):
    path = tmp_path / "replay.jsonl"
    job = _job(nvml_age_s=None, seq=7)
    led = ledger.EnergyLedger(path=str(path))
    first = led.append_job(job, now=NOW)
    assert first["appended"] is True
    original_bytes = path.read_bytes()

    replay = led.append_job(job, now=NOW + 30)
    assert replay["duplicate"] is True
    assert replay["idempotency_key"] == first["idempotency_key"]
    assert path.read_bytes() == original_bytes

    restarted = ledger.EnergyLedger(path=str(path))
    replay_after_restart = restarted.append_job(job, now=NOW + 60)
    assert replay_after_restart["duplicate"] is True
    assert replay_after_restart["idempotency_key"] == first["idempotency_key"]
    assert restarted.verify() == led.verify()
    assert path.read_bytes() == original_bytes


def _legacy_charged_entry():
    reading = JouleReading(
        node="legacy-gpu", joules=78369.586, label="MEASURED",
        nvml_age_s=5.0, grid_price_eur_mwh=0.0, ts=TS,
    )
    receipt = build_receipt(reading, 45)
    return {
        "seq": 0,
        "prev_digest": ledger.GENESIS_PREV,
        "receipt": receipt,
        "job": {"node": "legacy-gpu", "tokens": 512, "ts": TS},
        "billable": True,
        "reason": "ok",
        "charge": {"status": "charged", "amount_cents": 1, "payment_intent": "pi_legacy"},
        "idempotency_key": d_idem(receipt),
        "entry_digest": ledger._entry_digest(0, ledger.GENESIS_PREV, receipt["payload_digest"]),
    }


def test_legacy_charged_history_preserved_without_current_measured_promotion(
    monkeypatch, tmp_path
):
    path = tmp_path / "legacy.jsonl"
    entry = _legacy_charged_entry()
    path.write_text(json.dumps(entry, separators=(",", ":")) + "\n", encoding="utf-8")
    original_bytes = path.read_bytes()
    led = ledger.EnergyLedger(path=str(path))
    assert led.verify()["ok"] is True
    totals = led.totals()
    assert totals["joules_measured_billable"] is None
    assert totals["kwh_total"] is None
    assert totals["joules_measured_label"] == "UNAVAILABLE"
    assert totals["historical_reported_billable_joules"] == 78369.586
    assert totals["historical_reported_joules_input"] == 78369.586
    assert totals["historical_billable_receipts"] == 1
    assert totals["charged_cents"] is None
    assert totals["historical_reported_charged_cents"] == 1
    assert totals["historical_charge_label"] == "REPORTED"
    assert led.get_by_idem(entry["idempotency_key"]) == entry
    monkeypatch.setattr(ledger, "_LEDGER", led)
    projected = live._ledger_totals()
    assert projected["joules_measured_billable"] is None
    assert projected["joules_measured_label"] == "UNAVAILABLE"
    assert projected["historical_reported_charged_cents"] == 1
    assert path.read_bytes() == original_bytes


def test_harvest_html_does_not_zero_fill_unavailable_billable_energy():
    page = (Path(__file__).resolve().parents[1] / "web" / "energy-harvest.html").read_text(
        encoding="utf-8"
    )
    assert "billable energy unavailable" in page
    assert "'UNAVAILABLE'" in page
    assert "Object.prototype.hasOwnProperty.call(t,'joules_measured_billable')" in page
    assert "joules_measured_billable!=null?fmt(sl.joules_measured_billable,3):'0'" not in page
    assert "only the signed-ledger" not in page


def test_other_energy_views_do_not_promote_legacy_history_to_live_billing():
    root = Path(__file__).resolve().parents[1]
    ops = (root / "pages" / "energy-ops.html").read_text(encoding="utf-8")
    showcase = (root / "static" / "3d" / "energy_showcase" / "showcase.js").read_text(
        encoding="utf-8"
    )
    assert 'mode === "BLOCKED"' in ops
    assert 'mReal.textContent = "UNAVAILABLE"' in ops
    assert 'setChip(document.getElementById("m-real-chip"), "UNAVAILABLE")' in ops
    assert 'realCents > 0 ? "MEASURED"' not in ops
    assert 'totals.attribution_verified === true' in showcase
    assert 'host.setLabel(ok && len > 0 ? "REPORTED"' in showcase
    assert 'host.setLabel(ok && len > 0 ? "MEASURED"' not in showcase
