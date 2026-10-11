"""Source-bound governed inference energy; all readings here are synthetic fixtures."""

import importlib.util
import io
import json
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
import szl_meter_access as meter_auth
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
    monkeypatch.setattr(api, "_meter_json", lambda *a, **kw: {
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
    monkeypatch.setattr(api, "_meter_json", lambda *a, **kw: {
        "ts": now, "engines": [{"engine": "omen", "gpus": [
            {"live": True, "gpu_uuid": "GPU-one", "counter_epoch": "epoch-1",
             "sample_ts": now, "joules_method": "NVML_COUNTER_DELTA",
             "joules": 12.5}]}], "totals": {"joules": 999.0},
    })
    joules, evidence = api._meter_one(OMEN)
    assert joules == 12.5
    assert evidence["counter_samples"]["omen"]["joules"] == 12.5
    assert evidence["fresh"] is True


def test_canonical_exporter_root_json_matches_consumer_contract(monkeypatch):
    source = Path(api.__file__).resolve().parent / "box-scripts" / "omen_joule_exporter.py"
    spec = importlib.util.spec_from_file_location("a11oy_exporter_contract", source)
    assert spec is not None and spec.loader is not None
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    now = time.time()
    monkeypatch.setattr(exporter, "ENGINE_NAME", "betterwithage")
    monkeypatch.setattr(exporter, "PEER_EXPORTERS", [])
    monkeypatch.setattr(exporter, "_read_models", lambda: [])
    monkeypatch.setattr(exporter, "_last_sample", {0: {
        "name": "fixture GPU", "power_w": 10.0, "live": True,
        "ts": now - 1, "counter_uuid": "GPU-source-contract",
        "counter_epoch": "epoch-1", "counter_delta_valid": True,
    }})
    monkeypatch.setattr(exporter, "_cum_counter_joules", {0: 12.5})
    monkeypatch.setattr(exporter, "_cum_joules", {0: 999.0})
    payload = exporter._meter_json(now=now)
    gpu = payload["engines"][0]["gpus"][0]
    assert {"gpu_uuid", "counter_epoch", "sample_ts", "joules_method", "joules"} <= gpu.keys()
    assert payload["engines"][0]["engine"] == "betterwithage"
    assert payload["totals"]["joules"] == 12.5
    samples = api._counter_samples(payload, now)
    assert samples is not None
    assert samples["betterwithage"]["joules"] == 12.5


def test_meter_without_hmac_target_fails_before_read(monkeypatch):
    monkeypatch.delenv("SZL_METER_HMAC_TARGETS", raising=False)
    def no_network(*_args, **_kwargs):
        raise AssertionError("meter network attempted without exact HMAC target")
    monkeypatch.setattr(meter_auth.urllib.request, "build_opener", no_network)
    joules, evidence = api._meter_one(LAPTOP)
    assert joules is None
    assert evidence["reachable"] is False


def test_ollama_tags_get_needs_no_meter_hmac_target(monkeypatch):
    monkeypatch.delenv("SZL_METER_HMAC_TARGETS", raising=False)
    def no_meter_get(*_args, **_kwargs):
        raise AssertionError("Ollama liveness must not use meter authentication")
    monkeypatch.setattr(meter_auth, "open_meter_get", no_meter_get)
    captured = []
    class Opener:
        def open(self, request, *, timeout):
            captured.append((request, timeout))
            return io.BytesIO(b'{"models":[{"name":"local:latest"}]}')
    def build_opener(*handlers):
        assert any(isinstance(handler, api._NoRedirect) for handler in handlers)
        return Opener()
    monkeypatch.setattr(api.urllib.request, "build_opener", build_opener)
    assert api._engine_live({"ollama": "http://127.0.0.1:11434",
                             "model": "local:latest"}) is True
    request, timeout = captured[0]
    assert request.full_url == "http://127.0.0.1:11434/api/tags"
    assert request.get_method() == "GET" and timeout == 6
    assert not any("meter" in name.lower() or "cf-access" in name.lower()
                   for name, _ in request.header_items())


def test_generic_get_neither_redirects_nor_forwards_meter_headers(monkeypatch):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, dict(self.headers)))
            self.send_response(302 if self.path == "/redirect" else 200)
            self.send_header("Location", "/followed")
            self.end_headers()

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({
        base: {"client_id": "fixture", "key_hex": "ab" * 32}}))
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            api._http_json(base + "/redirect", timeout=2)
        assert error.value.code == 302
        assert [path for path, _ in seen] == ["/redirect"]
        headers = {name.lower() for name in seen[0][1]}
        assert not any("meter" in name or "cf-access" in name for name in headers)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.mark.parametrize("url", ["file:///tmp/tags", "http://user:pass@host/api/tags",
                                 "http://host/api/tags#fragment", "http://host/api/tags\nInjected"])
def test_generic_get_rejects_invalid_targets_before_network(monkeypatch, url):
    def no_network(*_args, **_kwargs):
        raise AssertionError("invalid target reached network")
    monkeypatch.setattr(api.urllib.request, "build_opener", no_network)
    with pytest.raises(ValueError):
        api._http_json(url)


def test_ollama_generate_post_transport_is_unchanged(monkeypatch):
    captured = []
    def no_get_opener(*_args, **_kwargs):
        raise AssertionError("generation POST used GET opener")
    def open_post(request, *, timeout):
        captured.append((request, timeout))
        return io.BytesIO(b'{"response":"fixture answer"}')
    monkeypatch.setattr(api.urllib.request, "build_opener", no_get_opener)
    monkeypatch.setattr(api.urllib.request, "urlopen", open_post)
    result = api._http_json("http://127.0.0.1:11434/api/generate",
                            {"model": "local", "prompt": "fixture"}, timeout=7)
    assert result == {"response": "fixture answer"}
    request, timeout = captured[0]
    assert request.get_method() == "POST" and timeout == 7
    assert json.loads(request.data) == {"model": "local", "prompt": "fixture"}


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
    # Two turns observe the same physical window. Its 10 J may include both
    # inferences or unrelated GPU work; neither turn owns that device delta.
    monkeypatch.setattr(api, "_meter_snapshot", iter([
        (None, _snapshot(100.0, 20.0)),
        (None, _snapshot(110.0, 90.0)),
        (None, _snapshot(100.0, 20.0)),
        (None, _snapshot(110.0, 90.0)),
    ]).__next__)
    monkeypatch.setattr(api, "time", SimpleNamespace(
        time=iter([101.0, 104.0, 105.0, 108.0]).__next__))
    for _ in range(2):
        energy = api.govern_infer("A public fixture prompt.")["energy"]
        assert energy["joules"] is None
        assert energy["label"] == "UNAVAILABLE"
        assert energy["evidence"]["device_window"] == {
            "joules": 10.0, "label": "MEASURED", "method": "NVML_COUNTER_DELTA",
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
