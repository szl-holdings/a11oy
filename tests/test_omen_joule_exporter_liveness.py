"""A stale sampled-power integral must never become a measured joule claim."""

import importlib.util
import json
from pathlib import Path

import pytest


_PATH = Path(__file__).resolve().parents[1] / "box-scripts" / "omen_joule_exporter.py"
_SPEC = importlib.util.spec_from_file_location("omen_joule_exporter_liveness_test", _PATH)
exporter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(exporter)
_REAL_READ_MODELS = exporter._read_models


def _row(power_w, gpu_uuid="GPU-123"):
    return (0, gpu_uuid, "GPU", power_w)


@pytest.fixture(autouse=True)
def isolated_exporter_state(monkeypatch):
    monkeypatch.setattr(exporter, "_cum_joules", {})
    monkeypatch.setattr(exporter, "_cum_counter_joules", {})
    monkeypatch.setattr(exporter, "_last_sample", {})
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", [])
    monkeypatch.setattr(exporter, "_read_models", lambda: [])


def test_missing_gpu_in_new_poll_clears_live_flag_and_emitted_readings():
    exporter._record_sample([_row(12.5)], now=100.0, dt=2.0)
    assert exporter._last_sample[0]["live"] is True
    exporter._record_sample([], now=102.0, dt=2.0)
    assert exporter._last_sample[0]["live"] is False
    engine, total = exporter._local_engine(now=102.0)
    assert total is None
    assert engine["joules"] is None
    assert engine["gpus"][0]["power_w"] is None
    assert engine["gpus"][0]["joules"] is None
    assert engine["gpus"][0]["live"] is False
    assert engine["gpus"][0]["sample_ts"] == 100.0


@pytest.mark.parametrize("sample_ts", [100.0, 200.0, float("nan")])
def test_stalled_future_or_invalid_sample_cannot_claim_live(sample_ts):
    exporter._cum_joules[0] = 40.25
    exporter._last_sample[0] = {
        "name": "GPU", "power_w": 12.5, "live": True, "ts": sample_ts,
    }
    engine, total = exporter._local_engine(now=100.0 + exporter.MAX_SAMPLE_AGE_S + 1.0)
    assert total is None
    assert engine["joules"] is None
    assert engine["gpus"][0]["power_w"] is None
    assert engine["gpus"][0]["joules"] is None
    assert engine["gpus"][0]["live"] is False


def test_fresh_zero_power_is_observed_but_integrated_joules_are_modeled():
    exporter._record_sample([_row(0.0)], now=100.0, dt=2.0)
    engine, total = exporter._local_engine(now=101.0)
    gpu = engine["gpus"][0]
    assert gpu["live"] is True
    assert gpu["power_w"] == 0.0
    assert gpu["sample_ts"] == 100.0
    assert gpu["joules"] is None
    assert gpu["estimated_joules"] == 0.0
    assert gpu["estimated_joules_label"] == "MODELED"
    assert total is None


def test_old_peer_without_observation_timestamp_cannot_supply_measured_total(monkeypatch):
    old_peer = {"engine": "old", "joules": 100.0, "gpus": [
        {"index": 0, "power_w": 12.5, "joules": 100.0, "live": True},
    ]}
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", ["https://peer.example"])
    monkeypatch.setattr(exporter, "_fetch_peer_engines", lambda: ([old_peer], True))
    payload = exporter._meter_json(now=101.0)
    assert payload["totals"]["joules"] is None
    peer = payload["engines"][1]
    assert peer["joules"] is None
    assert peer["gpus"][0]["live"] is False
    assert peer["gpus"][0]["joules"] is None


def test_response_timestamp_is_not_sample_timestamp():
    exporter._record_sample([_row(12.5)], now=100.0, dt=2.0)
    payload = exporter._meter_json(now=101.0)
    assert payload["ts"] == 101.0
    assert payload["engines"][0]["gpus"][0]["sample_ts"] == 100.0
    assert payload["totals"]["joules"] is None
    assert payload["totals"]["estimated_joules_label"] == "MODELED"


def _counter(mj, uuid="GPU-123", ts=104.0):
    return {0: {"mj": mj, "uuid": uuid, "ts": ts}}


def test_two_monotone_nvml_counter_polls_enable_measured_joules_and_zero_delta():
    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    first, _ = exporter._local_engine(now=101.0)
    assert first["gpus"][0]["joules"] is None  # baseline is not a delta
    exporter._record_sample([_row(12.5)], now=102.0, dt=2,
                            counters_mj=_counter(1000, ts=102.0))
    second, total = exporter._local_engine(now=103.0)
    gpu = second["gpus"][0]
    assert total == gpu["joules"] == 0.0
    assert gpu["joules_method"] == "NVML_COUNTER_DELTA"
    assert gpu["gpu_uuid"] == "GPU-123"
    assert gpu["counter_epoch"]
    epoch = gpu["counter_epoch"]
    exporter._record_sample([_row(12.5)], now=104.0, dt=2,
                            counters_mj=_counter(1425))
    third, total = exporter._local_engine(now=105.0)
    assert total == third["gpus"][0]["joules"] == 0.425
    assert third["gpus"][0]["counter_epoch"] == epoch


@pytest.mark.parametrize("second", [None, _counter(500), _counter(1200, uuid="GPU-other")])
def test_missing_reset_or_different_device_counter_breaks_epoch(second):
    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    exporter._record_sample([_row(12.5)], now=102.0, dt=2,
                            counters_mj=_counter(1100, ts=102.0))
    prior, _ = exporter._local_engine(now=103.0)
    epoch = prior["gpus"][0]["counter_epoch"]
    exporter._record_sample([_row(12.5)], now=104.0, dt=2,
                            counters_mj=second)
    current, total = exporter._local_engine(now=105.0)
    assert total is None
    assert current["gpus"][0]["joules"] is None
    assert exporter._last_sample[0]["counter_epoch"] != epoch


def test_stalled_sampler_does_not_reemit_old_counter_delta_as_live():
    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    exporter._record_sample([_row(12.5)], now=102.0, dt=2,
                            counters_mj=_counter(1100, ts=102.0))
    stale_now = 102.0 + exporter.MAX_SAMPLE_AGE_S + 1
    payload = exporter._meter_json(now=stale_now)
    assert payload["engines"][0]["gpus"][0]["live"] is False
    assert payload["totals"]["joules"] is None


def test_old_peer_fake_aggregate_and_unqualified_gpu_are_scrubbed(monkeypatch):
    peer = {"engine": "old", "joules": 100, "gpus": [
        {"index": 0, "live": True, "sample_ts": 100.0, "power_w": 1,
         "joules": 100, "joules_method": "NVML_COUNTER_DELTA"},
    ]}
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", ["https://peer.example"])
    monkeypatch.setattr(exporter, "_fetch_peer_engines", lambda: ([peer], True))
    payload = exporter._meter_json(now=101.0)
    assert payload["engines"][1]["joules"] is None
    assert payload["totals"]["joules"] is None


def test_nvidia_smi_and_nvml_uuid_mismatch_blocks_counter_delta():
    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    exporter._record_sample([_row(12.5, gpu_uuid="GPU-other")], now=102.0, dt=2,
                            counters_mj=_counter(1100, ts=102.0))
    engine, total = exporter._local_engine(now=103.0)
    assert total is None
    assert engine["gpus"][0]["joules"] is None


def test_missing_configured_peer_nulls_aggregate_even_with_local_counter(monkeypatch):
    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    exporter._record_sample([_row(12.5)], now=102.0, dt=2,
                            counters_mj=_counter(1100, ts=102.0))
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", ["https://unreachable.example"])
    monkeypatch.setattr(exporter, "_fetch_peer_engines", lambda: ([], False))
    payload = exporter._meter_json(now=103.0)
    assert payload["engines"][0]["gpus"][0]["joules"] == 0.1
    assert payload["totals"]["joules"] is None


def test_exporter_counter_payload_is_accepted_by_live_consumer():
    import szl_energy_live as energy

    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    exporter._record_sample([_row(12.5)], now=102.0, dt=2,
                            counters_mj=_counter(1100, ts=102.0))
    payload = exporter._meter_json(now=103.0)
    parsed = energy.parse_meter_metrics(json.dumps(payload), now=103.0)
    assert parsed["total_joules"] == 0.1
    assert parsed["total_watts"] == 12.5


def test_duplicate_gpu_uuid_from_different_peer_name_nulls_exporter_total(monkeypatch):
    exporter._record_sample([_row(12.5)], now=100.0, dt=0,
                            counters_mj=_counter(1000, ts=100.0))
    exporter._record_sample([_row(12.5)], now=102.0, dt=2,
                            counters_mj=_counter(1100, ts=102.0))
    peer = {"engine": "other-name", "gpus": [{
        "index": 0, "gpu_uuid": "GPU-123", "counter_epoch": "peer-epoch",
        "sample_ts": 102.0, "live": True, "power_w": 12.5,
        "joules": 100, "joules_method": "NVML_COUNTER_DELTA",
    }]}
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", ["https://peer.example"])
    monkeypatch.setattr(exporter, "_fetch_peer_engines", lambda: ([peer], True))
    payload = exporter._meter_json(now=103.0)
    assert payload["engines"][0]["joules"] == 0.1
    assert payload["engines"][1]["joules"] == 100
    assert payload["totals"]["joules"] is None


def test_nvml_reader_unsupported_counter_returns_no_measurement(monkeypatch):
    import sys
    from types import SimpleNamespace

    def unsupported(_handle):
        raise RuntimeError("NVML_ERROR_NOT_SUPPORTED")

    fake = SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlShutdown=lambda: None,
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda idx: idx,
        nvmlDeviceGetTotalEnergyConsumption=unsupported,
        nvmlDeviceGetUUID=lambda _handle: b"GPU-123",
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    assert exporter._read_gpu_energy_counters() == {}


def test_nvml_reader_captures_uuid_counter_and_observation_time(monkeypatch):
    import sys
    from types import SimpleNamespace

    fake = SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlShutdown=lambda: None,
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda idx: idx,
        nvmlDeviceGetTotalEnergyConsumption=lambda _handle: 1100,
        nvmlDeviceGetUUID=lambda _handle: b"GPU-123",
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    read = exporter._read_gpu_energy_counters()
    assert read[0]["mj"] == 1100.0
    assert read[0]["uuid"] == "GPU-123"
    assert isinstance(read[0]["ts"], float)


def test_forged_fresh_model_file_cannot_promote_measured_claim(monkeypatch):
    from unittest.mock import mock_open

    raw = {"model": "glm-test", "label": "MEASURED", "joules_per_token": 1.25,
           "energy_joules": 100, "source": "self-asserted"}
    monkeypatch.setattr(exporter, "_read_models", _REAL_READ_MODELS)
    monkeypatch.setattr(exporter, "OLLAMA_ENERGY_JSON", "synthetic-model-energy.json")
    monkeypatch.setattr(exporter.os.path, "getmtime", lambda _path: exporter.time.time())
    monkeypatch.setattr(exporter, "open", mock_open(read_data=json.dumps(raw)), raising=False)
    projected = exporter._read_models()[0]
    assert projected["label"] == "UNKNOWN"
    assert projected["joules_per_token"] is None
    assert projected["energy_joules"] is None
    assert projected["provenance_status"] == "EXTERNAL_PROBE_PROVENANCE_UNVERIFIED"
    assert raw["label"] == "MEASURED"  # input left unchanged


@pytest.mark.parametrize("remote, expected", [
    ("127.0.0.1", True),
    ("::1", True),
    ("100.100.100.100", True),
    ("fd7a:115c:a1e0::1", True),
    ("100.63.255.255", False),
    ("203.0.113.9", False),
    ("not-an-ip", False),
])
def test_current_main_source_ip_allowlist_is_preserved(remote, expected):
    assert exporter._client_allowed(remote) is expected


def test_denied_http_client_gets_403_before_meter_read(monkeypatch):
    def no_meter_read():
        raise AssertionError("denied source must not trigger meter read")

    monkeypatch.setattr(exporter, "_meter_json", no_meter_read)
    handler = exporter.Handler.__new__(exporter.Handler)
    handler.client_address = ("203.0.113.9", 12345)
    status = []
    handler.send_error = lambda code: status.append(code)
    handler.do_GET()
    assert status == [403]


def test_allowed_http_client_keeps_json_route_and_headers(monkeypatch):
    import io

    monkeypatch.setattr(exporter, "_meter_json", lambda: {"engines": [], "totals": {"joules": None}})
    handler = exporter.Handler.__new__(exporter.Handler)
    handler.client_address = ("127.0.0.1", 12345)
    handler.wfile = io.BytesIO()
    statuses = []
    headers = []
    handler.send_response = lambda code: statuses.append(code)
    handler.send_header = lambda name, value: headers.append((name, value))
    handler.end_headers = lambda: None
    handler.do_GET()
    assert statuses == [200]
    assert ("Content-Type", "application/json") in headers
    assert ("Access-Control-Allow-Origin", "*") in headers
    assert json.loads(handler.wfile.getvalue())["totals"]["joules"] is None
