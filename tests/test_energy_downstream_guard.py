"""Fail-closed consumers for direct NVML counter-delta meter evidence."""

import math
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

import szl_energy_operator as operator
import szl_surface_fidelity as fidelity


def _gpu(*, uuid="GPU-one", epoch="epoch-one", joules=12.5, sample_ts=None,
         live=True, method="NVML_COUNTER_DELTA", watts=85.0):
    return {
        "gpu_uuid": uuid,
        "counter_epoch": epoch,
        "index": 0,
        "joules": joules,
        "sample_ts": time.time() if sample_ts is None else sample_ts,
        "live": live,
        "joules_method": method,
        "power_w": watts,
    }


def _meter(*gpus, engine_joules=999.0):
    return {"engines": [{"engine": "omen", "joules": engine_joules,
                         "gpus": list(gpus)}],
            "totals": {"joules": engine_joules}}


@pytest.mark.parametrize("gpu", [
    _gpu(live=False),
    _gpu(sample_ts=time.time() - 3600),
    _gpu(sample_ts=time.time() + 3600),
    _gpu(method="POWER_INTEGRAL_MODEL"),
    _gpu(method=None),
    _gpu(uuid=""),
    _gpu(epoch=""),
    _gpu(joules=math.nan),
])
def test_operator_rejects_unproven_or_stale_gpu_energy(gpu):
    assert operator._exporter_sample_for_node(_meter(gpu), "omen") is None


def test_operator_uses_actual_gpu_sample_and_never_engine_aggregate():
    sample_ts = time.time() - 2.0
    sample = operator._exporter_sample_for_node(
        _meter(_gpu(sample_ts=sample_ts, joules=12.5), engine_joules=999.0),
        "omen", now=sample_ts + 2.0)
    assert sample is not None
    assert sample["joules_measured_total"] == 12.5
    assert sample["exporter_last_seen_ts"] == sample_ts
    assert sample["gpu_uuids"] == ("GPU-one",)
    assert sample["gpu_segments"] == (("GPU-one", "epoch-one"),)


def test_operator_rejects_partial_or_duplicate_gpu_set():
    good = _gpu()
    assert operator._exporter_sample_for_node(
        _meter(good, _gpu(uuid="GPU-two", live=False)), "omen") is None
    assert operator._exporter_sample_for_node(
        _meter(good, _gpu(uuid="GPU-one")), "omen") is None


def test_job_counter_window_requires_same_segment_and_new_gpu_poll():
    base = time.time() - 4.0
    before = operator._exporter_sample_for_node(
        _meter(_gpu(joules=10.0, sample_ts=base)), "omen", now=base + 1)
    after = operator._exporter_sample_for_node(
        _meter(_gpu(joules=12.5, sample_ts=base + 2)),
        "omen", now=base + 3)
    bounds = {"job_start_ts": base + 0.5, "job_end_ts": base + 1.5}
    assert operator._counter_window_joules(before, after, **bounds) == 2.5
    same_poll = operator._exporter_sample_for_node(
        _meter(_gpu(joules=10.0, sample_ts=base)), "omen", now=base + 3)
    assert operator._counter_window_joules(before, same_poll, **bounds) is None
    restarted = operator._exporter_sample_for_node(
        _meter(_gpu(epoch="new-epoch", joules=12.5, sample_ts=base + 2)),
        "omen", now=base + 3)
    assert operator._counter_window_joules(before, restarted, **bounds) is None
    new_gpu = operator._exporter_sample_for_node(
        _meter(_gpu(uuid="GPU-two", joules=12.5, sample_ts=base + 2)),
        "omen", now=base + 3)
    assert operator._counter_window_joules(before, new_gpu, **bounds) is None
    assert operator._counter_window_joules(
        before, after, job_start_ts=base - 0.5,
        job_end_ts=base + 1.5) is None
    assert operator._counter_window_joules(
        before, after, job_start_ts=base + 0.5,
        job_end_ts=base + 2.5) is None


def test_each_job_gets_its_own_counter_baseline_without_billable_attribution(monkeypatch):
    starts = iter((10.0, 12.0))
    before_calls = []
    def before_meter():
        joules = next(starts)
        before_calls.append(joules)
        return _meter(_gpu(joules=joules, sample_ts=time.time() - 0.1))
    ends = iter((12.0, 14.0))
    def after_sample(exporter_node, job_end_ts):
        return operator._exporter_sample_for_node(
            _meter(_gpu(joules=next(ends), sample_ts=job_end_ts + 0.01)),
            exporter_node, now=job_end_ts + 0.02)
    monkeypatch.setattr(operator, "_fetch_joule_meter", before_meter)
    monkeypatch.setattr(operator, "_post_job_sample", after_sample)
    def generate(*args):
        time.sleep(0.01)
        return 1, "ok"
    monkeypatch.setattr(operator, "_ollama_generate", generate)
    monkeypatch.setattr(operator, "_govern_turn", lambda *args: {})
    node = operator.NodeCfg(name="omen", base_url="http://unused",
                            gen_model="model", embed_model="embed",
                            exporter_node="omen")
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
        op = operator.OperatorDaemon(nodes=[], state_path=f"{folder}/ledger.json")
        first = op._run_real_job(node, "generate")
        second = op._run_real_job(node, "generate")
        status = op.status()
    assert before_calls == [10.0, 12.0]
    assert [first["window_joules_measured"],
            second["window_joules_measured"]] == [2.0, 2.0], (first, second)
    assert first["joules_scope"] == "BOUNDED_METER_WINDOW"
    assert second["joules_scope"] == "BOUNDED_METER_WINDOW"
    assert first["joules_label"] == second["joules_label"] == operator.LABEL_SAMPLE
    assert first["joules_measured"] is second["joules_measured"] is None
    assert status["joules_measured_total"] == 0


def test_job_label_stays_sample_without_valid_job_window():
    after = operator._exporter_sample_for_node(_meter(_gpu()), "omen")
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
        op = operator.OperatorDaemon(nodes=[], state_path=f"{folder}/ledger.json")
        record = op._commit("omen", "model", "generate", 1, 0.1, after, None)
    assert record.joules_label == operator.LABEL_SAMPLE
    assert record.joules_measured is None
    assert record.joules_reason == "NO_VERIFIED_NVML_COUNTER_WINDOW"


def test_external_claimed_joules_cannot_become_measured():
    after = operator._exporter_sample_for_node(_meter(_gpu()), "omen")
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
        op = operator.OperatorDaemon(nodes=[], state_path=f"{folder}/ledger.json")
        record = op.submit_external_job("omen", "model", "generate", 1, 0.1,
                                        exporter_sample=after, joules_measured=999.0)
        status = op.status()
    assert record.joules_label == operator.LABEL_SAMPLE
    assert record.joules_measured is None
    assert record.joules_reason == "NO_VERIFIED_NVML_COUNTER_WINDOW"
    assert status["joules_measured_total"] == 0
    assert status["joules_measured_label"] == "UNAVAILABLE"
    assert status["joules_sample_total"] == 0


def test_legacy_operator_state_is_backed_up_and_not_reclassified():
    legacy = {"jobs_done": 4, "seq": 4, "tokens_total": 40,
              "joules_measured_total": 45.0, "measured_jobs": 4,
              "measured_tokens": 40, "measured_token_joules": 45.0,
              "by_node": {"omen": {"jobs": 4, "tokens": 40,
                                    "joules_measured": 45.0}}}
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
        path = Path(folder) / "ledger.json"
        original = json.dumps(legacy).encode("utf-8")
        path.write_bytes(original)
        op = operator.OperatorDaemon(nodes=[], state_path=str(path))
        status = op.status()
        assert status["joules_measured_total"] == 0
        assert status["joules_measured_label"] == "UNAVAILABLE"
        assert status["legacy_unverified_joules_claimed"] == 45.0
        assert all(node["joules_measured"] == 0
                   for node in status["by_node"].values())
        op._persist()
        backup = Path(str(path) + ".pre-v2-legacy.json")
        assert backup.read_bytes() == original
        migrated = json.loads(path.read_text(encoding="utf-8"))
        assert migrated["schema_version"] == 2
        assert migrated["legacy_unverified_snapshot"] == legacy
        again = operator.OperatorDaemon(nodes=[], state_path=str(path))
        again._persist()
        assert backup.read_bytes() == original
        assert again.status()["legacy_unverified_joules_claimed"] == 45.0
        assert again.status()["joules_measured_total"] == 0


@pytest.mark.parametrize("bad", [b"{not-json", b'{"schema_version":99}'])
def test_corrupt_or_unsupported_state_cannot_be_overwritten(bad):
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
        path = Path(folder) / "ledger.json"
        path.write_bytes(bad)
        op = operator.OperatorDaemon(nodes=[], state_path=str(path))
        assert op.status()["state_persistence_status"] == "BLOCKED"
        op._persist()
        assert path.read_bytes() == bad
        assert op.status()["state_persistence_status"] == "BLOCKED"


@pytest.mark.parametrize("gpu", [
    _gpu(live=False),
    _gpu(sample_ts=time.time() - 3600),
    _gpu(sample_ts=time.time() + 3600),
    _gpu(method="POWER_INTEGRAL_MODEL"),
    _gpu(method=None),
    _gpu(uuid=""),
    _gpu(epoch=""),
    _gpu(joules=math.inf),
])
def test_surface_never_promotes_unproven_or_stale_gpu(monkeypatch, gpu):
    monkeypatch.setenv(fidelity.METER_URLS_ENV, "https://meter.example.test/metrics")
    monkeypatch.setattr(fidelity, "_read_one_meter", lambda url, timeout: {
        "url": url, "ok": True, "http_status": 200, "latency_ms": 1,
        "doc": _meter(gpu), "error": None,
    })
    gate = fidelity.meter_gate()
    assert gate["label"] != "MEASURED"
    assert gate["joules_total"] is None
    assert gate["live_this_request"] is False


def test_surface_uses_per_gpu_counter_and_real_sample_time(monkeypatch):
    sample_ts = time.time() - 2.0
    monkeypatch.setenv(fidelity.METER_URLS_ENV, "https://meter.example.test/metrics")
    monkeypatch.setattr(fidelity, "_read_one_meter", lambda url, timeout: {
        "url": url, "ok": True, "http_status": 200, "latency_ms": 1,
        "doc": _meter(_gpu(joules=12.5, sample_ts=sample_ts),
                      _gpu(uuid="GPU-two", joules=3.0, sample_ts=sample_ts),
                      engine_joules=999.0), "error": None,
    })
    gate = fidelity.meter_gate()
    assert gate["label"] == "MEASURED"
    assert gate["joules_total"] == 15.5
    assert gate["engines"][0]["joules"] == 15.5
    assert gate["engines"][0]["reading_taken_at"] == datetime.fromtimestamp(
        sample_ts, timezone.utc).isoformat()


def test_surface_rejects_partial_gpu_set(monkeypatch):
    monkeypatch.setenv(fidelity.METER_URLS_ENV, "https://meter.example.test/metrics")
    monkeypatch.setattr(fidelity, "_read_one_meter", lambda url, timeout: {
        "url": url, "ok": True, "http_status": 200, "latency_ms": 1,
        "doc": _meter(_gpu(), _gpu(uuid="GPU-two", live=False)), "error": None,
    })
    gate = fidelity.meter_gate()
    assert gate["label"] != "MEASURED"
    assert gate["joules_total"] is None


def test_surface_aggregate_rejects_missing_configured_meter(monkeypatch):
    monkeypatch.setenv(fidelity.METER_URLS_ENV,
                       "https://one.example/metrics,https://two.example/metrics")
    def read(url, timeout):
        if "two" in url:
            return {"url": url, "ok": False, "http_status": None,
                    "latency_ms": 1, "doc": None, "error": "timeout"}
        return {"url": url, "ok": True, "http_status": 200,
                "latency_ms": 1, "doc": _meter(_gpu()), "error": None}
    monkeypatch.setattr(fidelity, "_read_one_meter", read)
    gate = fidelity.meter_gate()
    assert gate["label"] != "MEASURED"
    assert gate["joules_total"] is None
    assert gate["all_sources_qualified"] is False
    assert gate["incomplete_sources"] == ["https://two.example/metrics"]


def test_surface_aggregate_rejects_duplicate_engine(monkeypatch):
    monkeypatch.setenv(fidelity.METER_URLS_ENV,
                       "https://one.example/metrics,https://two.example/metrics")
    monkeypatch.setattr(fidelity, "_read_one_meter", lambda url, timeout: {
        "url": url, "ok": True, "http_status": 200, "latency_ms": 1,
        "doc": _meter(_gpu()), "error": None,
    })
    gate = fidelity.meter_gate()
    assert gate["label"] != "MEASURED"
    assert gate["joules_total"] is None
    assert gate["incomplete_sources"] == ["https://two.example/metrics"]


def test_surface_aggregate_rejects_same_gpu_in_different_engines(monkeypatch):
    monkeypatch.setenv(fidelity.METER_URLS_ENV,
                       "https://one.example/metrics,https://two.example/metrics")
    def read(url, timeout):
        doc = _meter(_gpu(uuid="GPU-shared"))
        doc["engines"][0]["engine"] = "one" if "one" in url else "two"
        return {"url": url, "ok": True, "http_status": 200,
                "latency_ms": 1, "doc": doc, "error": None}
    monkeypatch.setattr(fidelity, "_read_one_meter", read)
    gate = fidelity.meter_gate()
    assert gate["label"] != "MEASURED"
    assert gate["joules_total"] is None
    assert gate["incomplete_sources"] == ["https://two.example/metrics"]
