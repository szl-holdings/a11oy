"""Source-bound governed inference energy; all readings here are synthetic fixtures."""

import time
from types import SimpleNamespace

import szl_governed_api as api


OMEN = "https://meter.a-11-oy.com"
LAPTOP = "https://meter2.a-11-oy.com"


def _engine(name, meter, exporter):
    return {"name": name, "meter": meter, "exporter": exporter}


def _snapshot(omen_joules, laptop_joules, *, omen_reachable=True, omen_counter="epoch-1"):
    return {
        "duplicate_gpu_source": False,
        "engines": [
            {"engine": "anchor", "meter": OMEN, "reachable": omen_reachable,
             "fresh": omen_reachable, "live": omen_reachable,
             "counter_samples": {"omen": {"joules": omen_joules,
                                          "sample_ts_min": omen_joules,
                                          "sample_ts_max": omen_joules,
                                          "gpu_counters": {"GPU-omen": omen_joules},
                                          "counter_id": omen_counter}}},
            {"engine": "laptop", "meter": LAPTOP, "reachable": True,
             "fresh": True, "live": True,
             "counter_samples": {"betterwithage": {"joules": laptop_joules,
                                                    "sample_ts_min": laptop_joules,
                                                    "sample_ts_max": laptop_joules,
                                                    "gpu_counters": {"GPU-laptop": laptop_joules},
                                                    "counter_id": "epoch-2"}}},
        ],
    }


def _window_delta(served_by, before, after, *, call_start_ts=101.0, call_end_ts=104.0):
    return api._served_meter_delta(
        served_by, before, after,
        call_start_ts=call_start_ts, call_end_ts=call_end_ts)


def test_meter_rejects_aggregate_without_direct_counter_evidence(monkeypatch):
    now = time.time()
    monkeypatch.setattr(api, "_http_json", lambda *a, **kw: {
        "ts": now, "engines": [{"engine": "omen", "gpus": [
            {"live": True, "joules": 999.0, "power_w": 10.0}]}],
        "totals": {"joules": 999.0},
    })
    joules, evidence = api._meter_one(OMEN)
    assert joules is None
    assert evidence["counter_samples"] == {}
    assert evidence["fresh"] is False


def test_meter_uses_fresh_nvml_gpu_counter_not_exporter_total(monkeypatch):
    now = time.time()
    monkeypatch.setattr(api, "_http_json", lambda *a, **kw: {
        "ts": now, "engines": [{"engine": "omen", "gpus": [
            {"live": True, "gpu_uuid": "GPU-one", "counter_epoch": "epoch-1",
             "sample_ts": now, "joules_method": "NVML_COUNTER_DELTA",
             "joules": 12.5}]}], "totals": {"joules": 999.0},
    })
    joules, evidence = api._meter_one(OMEN)
    assert joules == 12.5
    assert evidence["counter_samples"]["omen"]["joules"] == 12.5
    assert evidence["fresh"] is True


def test_mesh_snapshot_reads_shared_meter_once(monkeypatch):
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("laptop", LAPTOP, "betterwithage"),
        _engine("glm", OMEN, None),
    ])
    calls = []

    def read_one(meter):
        calls.append(meter)
        joules = 100.0 if meter == OMEN else 50.0
        return joules, {"meter": meter, "reachable": True, "fresh": True,
                        "live": True, "gpu_ids": [meter]}

    monkeypatch.setattr(api, "_meter_one", read_one)
    total, evidence = api._meter_snapshot()
    assert total == 150.0
    assert calls == [OMEN, LAPTOP]
    assert evidence["unique_meter_count"] == 2
    assert len(evidence["engines"]) == 3


def test_served_energy_uses_only_serving_gpu_not_fleet_delta(monkeypatch):
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("laptop", LAPTOP, "betterwithage"),
    ])
    delta, _ = _window_delta(
        "anchor", _snapshot(100.0, 20.0), _snapshot(105.0, 90.0))
    assert delta == 5.0  # Device window excludes the unrelated laptop's 70 J.


def test_shared_or_missing_serving_source_fails_closed(monkeypatch):
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("glm", OMEN, None),
    ])
    delta, reason = _window_delta(
        "anchor", _snapshot(100.0, 20.0), _snapshot(105.0, 90.0))
    assert delta is None and "shared" in reason
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("laptop", LAPTOP, "betterwithage"),
    ])
    for before, after in [
        (_snapshot(100.0, 20.0, omen_reachable=False), _snapshot(105.0, 90.0)),
        (_snapshot(100.0, 20.0), _snapshot(105.0, 90.0, omen_counter="new-epoch")),
    ]:
        delta, _ = _window_delta("anchor", before, after)
        assert delta is None
    stale_after = _snapshot(105.0, 90.0)
    stale_after["engines"][0]["counter_samples"]["omen"]["sample_ts_min"] = 100.0
    delta, _ = _window_delta("anchor", _snapshot(100.0, 20.0), stale_after)
    assert delta is None
    mixed_before, mixed_after = _snapshot(100.0, 20.0), _snapshot(110.0, 90.0)
    mixed_before["engines"][0]["counter_samples"]["omen"]["gpu_counters"] = {
        "GPU-one": 50.0, "GPU-two": 50.0}
    mixed_after["engines"][0]["counter_samples"]["omen"]["gpu_counters"] = {
        "GPU-one": 49.0, "GPU-two": 61.0}
    delta, _ = _window_delta("anchor", mixed_before, mixed_after)
    assert delta is None  # One counter reset cannot be hidden by another GPU rising.


def test_gpu_samples_must_enclose_the_model_call(monkeypatch):
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("laptop", LAPTOP, "betterwithage"),
    ])
    before, after = _snapshot(100.0, 20.0), _snapshot(105.0, 90.0)
    for start, end in [(99.0, 104.0), (101.0, 106.0), (104.0, 101.0)]:
        delta, reason = _window_delta(
            "anchor", before, after, call_start_ts=start, call_end_ts=end)
        assert delta is None
        assert "enclose" in reason


def test_overlapping_turns_do_not_claim_exclusive_joules(monkeypatch):
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("laptop", LAPTOP, "betterwithage"),
    ])
    monkeypatch.setattr(api, "_avf", SimpleNamespace(
        governed_turn=lambda *a, **kw: {"decision": "allow", "receipt": None}))
    monkeypatch.setattr(api, "_pick_engine", lambda effort: api.MESH[0])
    monkeypatch.setattr(api, "_ollama_generate", lambda *a: ("fixture answer", {}))
    monkeypatch.setattr(api, "_with_pb_reference", lambda energy: energy)
    monkeypatch.setattr(api, "_conformal_blocks", lambda *a: None)
    # Two turns observe the same physical window. Its 5 J may include both
    # inferences or unrelated GPU work; neither turn owns that device delta.
    monkeypatch.setattr(api, "_meter_snapshot", iter([
        (None, _snapshot(100.0, 20.0)),
        (None, _snapshot(105.0, 90.0)),
        (None, _snapshot(100.0, 20.0)),
        (None, _snapshot(105.0, 90.0)),
    ]).__next__)
    monkeypatch.setattr(api, "time", SimpleNamespace(
        time=iter([101.0, 104.0, 101.0, 104.0]).__next__))
    for _ in range(2):
        energy = api.govern_infer("A public fixture prompt.")["energy"]
        assert energy["joules"] is None
        assert energy["label"] == "UNAVAILABLE"
        assert energy["evidence"]["device_window"] == {
            "joules": 5.0, "label": "MEASURED", "method": "NVML_COUNTER_DELTA",
            "scope": "SHARED_GPU_DEVICE_WINDOW", "billable": False,
        }


def test_governed_turn_keeps_ambiguous_energy_unavailable(monkeypatch):
    monkeypatch.setattr(api, "MESH", [
        _engine("anchor", OMEN, "omen"),
        _engine("glm", OMEN, None),
    ])
    monkeypatch.setattr(api, "_avf", SimpleNamespace(
        governed_turn=lambda *a, **kw: {"decision": "allow", "receipt": None}))
    monkeypatch.setattr(api, "_pick_engine", lambda effort: api.MESH[0])
    monkeypatch.setattr(api, "_ollama_generate", lambda *a: ("fixture answer", {}))
    monkeypatch.setattr(api, "_with_pb_reference", lambda energy: energy)
    monkeypatch.setattr(api, "_conformal_blocks", lambda *a: None)
    monkeypatch.setattr(api, "_meter_snapshot", iter([
        (120.0, _snapshot(100.0, 20.0)),
        (195.0, _snapshot(105.0, 90.0)),
    ]).__next__)
    result = api.govern_infer("A public fixture prompt.")
    assert result["answer"] == "fixture answer"
    assert result["energy"]["label"] == "UNAVAILABLE"
    assert result["energy"]["joules"] is None
