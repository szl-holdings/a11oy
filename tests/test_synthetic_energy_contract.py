"""Local-only schema handshake. This is not hosted measurement or release proof."""

import importlib.util
import json
import time
from contextlib import contextmanager
from pathlib import Path

import szl_energy_ledger as ledger
import szl_energy_live as live
import szl_energy_operator as operator
import szl_surface_fidelity as fidelity

ROOT = Path(__file__).resolve().parents[1]


spec = importlib.util.spec_from_file_location(
    "candidate_omen_exporter", ROOT / "box-scripts" / "omen_joule_exporter.py"
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def test_synthetic_counter_to_gate_to_operator_to_nonbillable_ledger(monkeypatch, tmp_path):
    """No hardware, network, model inference, payment, or provider writes."""
    t0 = time.time() - 2.0
    t1 = t0 + 1.0
    row = [(0, "GPU-synthetic", "Synthetic GPU", 100.0)]
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", [])
    monkeypatch.setattr(exporter, "_read_models", lambda: [])
    exporter._last_sample.clear()
    exporter._cum_joules.clear()
    exporter._cum_counter_joules.clear()
    exporter._record_sample(
        row, now=t0, dt=1.0,
        counters_mj={0: {"mj": 10_000.0, "uuid": "GPU-synthetic", "ts": t0}},
    )
    exporter._record_sample(
        row, now=t1, dt=1.0,
        counters_mj={0: {"mj": 12_500.0, "uuid": "GPU-synthetic", "ts": t1}},
    )
    doc = exporter._meter_json(now=t1)
    gpu = doc["engines"][0]["gpus"][0]
    assert gpu["joules"] == 2.5
    assert gpu["joules_method"] == "NVML_COUNTER_DELTA"
    assert gpu["gpu_uuid"] == "GPU-synthetic"
    assert gpu["sample_ts"] == t1
    parsed = live.parse_meter_metrics(json.dumps(doc), now=t1)
    assert parsed["total_joules"] == 2.5

    monkeypatch.setenv(fidelity.METER_URLS_ENV, "https://synthetic.invalid/metrics")
    monkeypatch.setattr(fidelity, "_read_one_meter", lambda url, timeout: {
        "url": url, "ok": True, "http_status": 200,
        "latency_ms": 0, "doc": doc, "error": None,
    })
    gate = fidelity.meter_gate()
    assert gate["label"] == "MEASURED"
    assert gate["joules_total"] == 2.5

    sample = operator._exporter_sample_for_node(doc, exporter.ENGINE_NAME)
    assert sample["joules_measured_total"] == 2.5
    op = operator.OperatorDaemon(nodes=[], state_path=str(tmp_path / "operator.json"))
    record = op._commit("omen", "synthetic-model", "generate", 1, 0.1,
                        sample, None)
    assert record.joules_label == "SAMPLE"
    assert record.joules_measured is None
    assert record.window_joules_measured is None

    @contextmanager
    def local_test_lock(path, timeout):
        yield {"synthetic_only": True}

    if ledger.os.name == "nt":
        monkeypatch.setattr(ledger, "_exclusive_writer_lock", local_test_lock)
    monkeypatch.setattr(ledger, "charge_stripe", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("no payment effect permitted")), raising=False)
    receipts = ledger.EnergyLedger(path=str(tmp_path / "ledger.jsonl"))
    append = receipts.append_job(ledger.JobRecord.from_dict(record.to_dict()))
    assert append["appended"] is True
    assert append["entry"]["billable"] is False
    assert receipts.verify()["ok"] is True
    assert receipts.totals()["joules_measured_billable"] is None


def test_synthetic_duplicate_peer_device_nulls_fleet_total(monkeypatch):
    """Two engine names cannot count the same GPU twice as a fleet."""
    now = time.time()
    exporter._last_sample.clear()
    exporter._cum_counter_joules.clear()
    exporter._cum_joules.clear()
    exporter._record_sample(
        [(0, "GPU-duplicate", "Synthetic GPU", 50.0)],
        now=now - 2, dt=1.0,
        counters_mj={0: {"mj": 1000.0, "uuid": "GPU-duplicate", "ts": now - 2}},
    )
    exporter._record_sample(
        [(0, "GPU-duplicate", "Synthetic GPU", 50.0)],
        now=now - 1, dt=1.0,
        counters_mj={0: {"mj": 1500.0, "uuid": "GPU-duplicate", "ts": now - 1}},
    )
    peer = {"engine": "peer", "gpus": [{
        "index": 0, "name": "same device", "power_w": 50.0,
        "live": True, "sample_ts": now - 1,
        "gpu_uuid": "GPU-duplicate", "counter_epoch": "another-epoch",
        "joules_method": "NVML_COUNTER_DELTA", "joules": 0.5,
    }]}
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", ["https://synthetic.invalid"])
    monkeypatch.setattr(exporter, "_fetch_peer_engines", lambda: ([peer], True))
    monkeypatch.setattr(exporter, "_read_models", lambda: [])
    doc = exporter._meter_json(now=now)
    assert doc["totals"]["joules"] is None
    assert live.parse_meter_metrics(json.dumps(doc), now=now)["total_joules"] is None
    monkeypatch.setenv(fidelity.METER_URLS_ENV, "https://synthetic.invalid/metrics")
    monkeypatch.setattr(fidelity, "_read_one_meter", lambda url, timeout: {
        "url": url, "ok": True, "http_status": 200,
        "latency_ms": 0, "doc": doc, "error": None,
    })
    gate = fidelity.meter_gate()
    assert gate["label"] != "MEASURED"
    assert gate["joules_total"] is None
