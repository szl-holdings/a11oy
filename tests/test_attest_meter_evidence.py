#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Attest only fresh, unique NVML counters; transport success is insufficient."""

import copy
import io
import json
import socket
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import szl_attest as attest
import szl_meter_access as access


METER = "https://meter.example.test/metrics"


def _meter(*, name="device-one", uuid="GPU-private-one", epoch="private-epoch-one",
           joules=12.5, sample_ts=None):
    return {
        "engines": [{
            "engine": name, "joules": joules, "joules_method": "NVML_COUNTER_DELTA",
            "estimated_joules": 9876.0, "estimated_joules_label": "MODELED",
            "gpus": [{
                "index": 0, "name": "test GPU", "joules": joules, "power_w": 10.25,
                "joules_method": "NVML_COUNTER_DELTA", "gpu_uuid": uuid,
                "counter_epoch": epoch, "live": True,
                "sample_ts": time.time() if sample_ts is None else sample_ts,
                "estimated_joules": 9876.0, "estimated_joules_label": "MODELED",
            }],
        }],
        "totals": {"joules": joules, "joules_method": "NVML_COUNTER_DELTA",
                   "estimated_joules": 9876.0, "estimated_joules_label": "MODELED"},
        "ts": time.time(),
        "models": [{"name": "unverified-model", "energy_joules": None,
                    "label": "UNAVAILABLE", "stale": True}],
    }


@pytest.fixture(autouse=True)
def configured_meter(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, METER)
    monkeypatch.delenv("SZL_METER_HMAC_TARGETS", raising=False)


def _read(payload):
    return attest.energy_measured(opener=lambda _url, _timeout: payload)


def test_nested_exporter_counter_is_counted_once_with_honest_scope_and_private_ids():
    payload = _meter()
    payload["joules"] = 99999.0
    payload["totals"]["joules"] = 99999.0
    payload["engines"][0]["joules"] = 99999.0
    readings, disclosure = _read(payload)

    assert disclosure["label"] == "MEASURED"
    assert disclosure["all_sources_qualified"] is True
    assert len(readings) == 1
    assert readings[0]["joules"] == 12.5
    assert readings[0]["measurement_scope"] == "METER_CUMULATIVE_COUNTER_SNAPSHOT"
    assert readings[0]["action_attribution"] == "UNATTRIBUTED"
    assert readings[0]["sample_ts"] == payload["engines"][0]["gpus"][0]["sample_ts"]
    gpu = readings[0]["gpu_evidence"][0]
    assert gpu["joules_method"] == "NVML_COUNTER_DELTA"
    assert len(gpu["source_sha256"]) == len(gpu["counter_segment_sha256"]) == 64
    public = json.dumps(readings, allow_nan=False)
    for private in ("GPU-private-one", "private-epoch-one", "device-one", "unverified-model"):
        assert private not in public
    assert "estimated_joules" not in public


def test_zero_hardware_counter_remains_a_valid_zero():
    readings, disclosure = _read(_meter(joules=0.0))
    assert disclosure["label"] == "MEASURED"
    assert readings[0]["joules"] == 0.0


def test_distinct_gpu_counters_sum_without_adding_engine_or_meter_totals():
    payload = _meter(joules=3.25)
    second = _meter(name="device-two", uuid="GPU-private-two", epoch="epoch-two", joules=4.0)
    payload["engines"].extend(second["engines"])
    payload["totals"]["joules"] = 7.25
    readings, _ = _read(payload)
    assert readings[0]["joules"] == 7.25
    assert len(readings[0]["gpu_evidence"]) == 2


@pytest.mark.parametrize("field,value", [
    ("joules", -1), ("joules", True), ("joules", "12.5"),
    ("joules", float("nan")), ("joules", float("inf")),
    ("power_w", float("inf")), ("power_w", -2),
    ("joules_method", "POWER_INTEGRAL_MODEL"), ("joules_method", None),
    ("gpu_uuid", ""), ("counter_epoch", ""), ("live", False),
    ("sample_ts", 0), ("sample_ts", float("nan")),
])
def test_unqualified_gpu_never_enters_signed_energy_strand(field, value):
    payload = _meter()
    payload["engines"][0]["gpus"][0][field] = value
    readings, disclosure = _read(payload)
    assert readings == []
    assert disclosure["label"] == "STRUCTURAL-ONLY"
    assert disclosure["errors"]


@pytest.mark.parametrize("age", [-3600, 3600])
def test_fresh_response_time_cannot_refresh_stale_or_future_gpu_sample(age):
    payload = _meter(sample_ts=time.time() - age)
    readings, disclosure = _read(payload)
    assert readings == []
    assert disclosure["label"] == "STRUCTURAL-ONLY"


@pytest.mark.parametrize("scope,key,value", [
    ("root", "label", "MODELED"), ("root", "modeled", True),
    ("root", "synthetic", True), ("root", "measured", False),
    ("root", "method", "POWER_INTEGRAL"),
    ("engine", "joules_method", "POWER_INTEGRAL_MODEL"),
    ("totals", "joules_method", None), ("totals", "joules", None),
    ("totals", "joules", -5), ("totals", "joules", float("nan")),
])
def test_contradictory_aggregate_flags_cannot_borrow_valid_gpu_evidence(scope, key, value):
    payload = _meter()
    target = payload if scope == "root" else payload["engines"][0] if scope == "engine" else payload["totals"]
    target[key] = value
    readings, disclosure = _read(payload)
    assert readings == []
    assert disclosure["all_sources_qualified"] is False


@pytest.mark.parametrize("payload", [
    {"joules": 10.0},
    {"engines": [], "totals": {"joules": 10.0}},
    {"estimated_joules": 10.0, "label": "MODELED"},
])
def test_aggregate_or_modeled_only_payload_is_not_a_counter_snapshot(payload):
    readings, _ = _read(payload)
    assert readings == []


def test_partial_gpu_set_and_duplicate_device_are_rejected():
    for changes in ({"gpu_uuid": "GPU-second", "live": False}, {}):
        payload = _meter()
        extra = copy.deepcopy(payload["engines"][0]["gpus"][0])
        extra.update(changes)
        payload["engines"][0]["gpus"].append(extra)
        assert _read(payload)[0] == []


def test_duplicate_engine_identity_is_rejected_even_for_distinct_gpus():
    payload = _meter()
    payload["engines"].extend(_meter(name="DEVICE-ONE", uuid="GPU-second")["engines"])
    assert _read(payload)[0] == []


@pytest.mark.parametrize("same_engine", [True, False])
def test_meter_aliases_cannot_double_count_engine_or_device(monkeypatch, same_engine):
    monkeypatch.setenv(attest.JOULE_METER_ENV, METER + ",https://alias.example.test/")

    def read(url, _timeout):
        return _meter(name="device-one" if url == METER or same_engine else "different-engine")

    readings, disclosure = attest.energy_measured(opener=read)
    assert len(readings) == 1
    assert sum(reading["joules"] for reading in readings) == 12.5
    assert disclosure["all_sources_qualified"] is False
    assert any("duplicate counter source" in error for error in disclosure["errors"])


def test_distinct_devices_with_same_friendly_engine_name_are_accepted(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, METER + ",https://second.example.test/")

    def read(url, _timeout):
        return _meter(name="local", uuid="GPU-first" if url == METER else "GPU-second")

    readings, disclosure = attest.energy_measured(opener=read)
    assert len(readings) == 2
    assert sum(reading["joules"] for reading in readings) == 25.0
    assert disclosure["all_sources_qualified"] is True


def test_repeated_configured_target_is_not_requested_twice(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, METER + "," + METER)
    calls = []
    readings, disclosure = attest.energy_measured(opener=lambda url, timeout: (calls.append(url) or _meter()))
    assert calls == [METER]
    assert len(readings) == 1
    assert disclosure["all_sources_qualified"] is False


class _Response(io.BytesIO):
    status = 200

    def __init__(self, body=b""):
        super().__init__(body)
        self._test_socket = socket.socket()
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=self._test_socket))

    def close(self):
        self._test_socket.close()
        super().close()


def test_production_transport_retains_authenticated_helper_and_identified_user_agent(monkeypatch):
    from szl_energy_measured import _METER_PROBE_UA
    calls = []

    def open_meter(url, *, timeout, headers):
        calls.append((url, timeout, headers))
        return _Response(json.dumps(_meter()).encode())

    monkeypatch.setattr(access, "open_meter_get", open_meter)
    readings, _ = attest.energy_measured()
    assert len(readings) == 1
    assert calls == [(METER, 1.5, {"User-Agent": _METER_PROBE_UA})]
    assert "szl-energy-measured" in _METER_PROBE_UA


@pytest.mark.parametrize("key", ["engines", "totals"])
def test_ambiguous_duplicate_json_fields_are_rejected(monkeypatch, key):
    payload = _meter()
    body = json.dumps(payload)[:-1] + "," + json.dumps(key) + ":" + json.dumps(payload[key]) + "}"
    monkeypatch.setattr(access, "open_meter_get", lambda *_args, **_kwargs: _Response(body.encode()))
    readings, disclosure = attest.energy_measured()
    assert readings == []
    assert any("duplicate meter JSON field" in error for error in disclosure["errors"])


def test_oversized_meter_body_is_rejected_before_json_parsing(monkeypatch):
    response = _Response(b" " * ((1 << 20) + 10))
    consumed = []
    original = response.read1

    def read(size):
        value = original(size)
        consumed.append(len(value))
        return value

    response.read1 = read
    monkeypatch.setattr(access, "open_meter_get", lambda *_args, **_kwargs: response)
    readings, disclosure = attest.energy_measured()
    assert readings == []
    assert sum(consumed) == (1 << 20) + 1
    assert any("exceeds 1 MiB" in error for error in disclosure["errors"])


def test_continuously_streaming_body_has_a_read_deadline(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(attest, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    class StreamingResponse(_Response):
        def read1(self, _size):
            clock[0] += 0.4
            return b" "

    monkeypatch.setattr(access, "open_meter_get", lambda *_args, **_kwargs: StreamingResponse())
    readings, disclosure = attest.energy_measured()
    assert readings == []
    assert clock[0] < 2
    assert any("read budget exceeded" in error for error in disclosure["errors"])


def test_invalid_credential_bearing_url_is_not_echoed_in_errors(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, "https://private-user:private-key@meter.example.test/")
    readings, disclosure = attest.energy_measured()
    assert readings == []
    assert disclosure["errors"][0].startswith("meter[1]:")
    assert "private-user" not in json.dumps(disclosure)
    assert "private-key" not in json.dumps(disclosure)


def test_configured_query_parameters_are_not_disclosed_in_public_evidence(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, METER + "?private-query=private-value")
    readings, disclosure = _read(_meter())
    assert readings[0]["meter"] == "meter[1]"
    assert "meter_source_sha256" not in readings[0]
    assert "private-query" not in json.dumps((readings, disclosure))
    assert "private-value" not in json.dumps((readings, disclosure))


def test_private_address_is_not_disclosed_in_reading_labels(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, "http://127.0.0.1:9876/metrics")
    readings, disclosure = _read(_meter())
    assert readings[0]["meter"] == "meter[1]"
    assert "127.0.0.1" not in json.dumps((readings, disclosure))


def test_response_without_enforceable_socket_deadline_fails_closed(monkeypatch):
    class OpaqueResponse(io.BytesIO):
        status = 200

    monkeypatch.setattr(access, "open_meter_get", lambda *_args, **_kwargs:
                        OpaqueResponse(json.dumps(_meter()).encode()))
    readings, disclosure = attest.energy_measured()
    assert readings == []
    assert any("bounded meter response socket required" in error for error in disclosure["errors"])


@pytest.mark.parametrize("mode", ["complete", "trickle-body", "trickle-chunk-header"])
def test_real_authenticated_loopback_response_body_deadline(monkeypatch, mode):
    import secrets
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    authenticated = []
    stop = threading.Event()
    verifier = None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            accepted = verifier.accepts(self.command, self.path, self.headers)
            authenticated.append(accepted)
            self.send_response(200 if accepted else 401)
            body = json.dumps(_meter()).encode()
            if accepted and mode == "trickle-chunk-header":
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", str(len(body)) if accepted and mode == "complete"
                                 else "1000000" if accepted else "0")
            self.end_headers()
            if not accepted:
                return
            try:
                if mode == "complete":
                    self.wfile.write(body)
                    self.wfile.flush()
                    return
                while not stop.wait(0.03):
                    self.wfile.write(b"f" if mode == "trickle-chunk-header" else b" ")
                    self.wfile.flush()
            except OSError:
                pass

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        origin = f"http://127.0.0.1:{server.server_port}"
        key = secrets.token_hex(32)
        verifier = access.MeterRequestVerifier(origin, json.dumps({"attest-test": key}))
        monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({
            origin: {"client_id": "attest-test", "key_hex": key},
        }))
        monkeypatch.setenv(attest.JOULE_METER_ENV, origin + "/metrics")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            readings, disclosure = attest.energy_measured()
            elapsed = time.monotonic() - started
        finally:
            stop.set()
            server.shutdown()
            thread.join(timeout=2)
    assert authenticated == [True]
    assert elapsed < 2.5
    if mode == "complete":
        assert len(readings) == 1 and readings[0]["joules"] == 12.5
        assert disclosure["label"] == "MEASURED"
    else:
        assert readings == []
        assert disclosure["label"] == "STRUCTURAL-ONLY"
    assert "127.0.0.1" not in json.dumps(disclosure)


def test_missing_hmac_configuration_blocks_before_network(monkeypatch):
    calls = []
    monkeypatch.setattr(access.urllib.request, "build_opener", lambda *_args: calls.append(True))
    readings, disclosure = attest.energy_measured()
    assert readings == []
    assert calls == []
    assert any("MeterAuthConfigurationError" in error for error in disclosure["errors"])


def test_readings_that_expire_while_other_meters_respond_are_not_returned(monkeypatch):
    monkeypatch.setenv(attest.JOULE_METER_ENV, METER + ",https://second.example.test/")
    clock = [1000.0]
    monkeypatch.setattr(attest, "datetime", SimpleNamespace(
        now=lambda _tz: datetime.fromtimestamp(clock[0], timezone.utc),
    ))

    def read(url, _timeout):
        if url != METER:
            clock[0] += 20
            return _meter(name="second", uuid="GPU-second", sample_ts=clock[0])
        return _meter(sample_ts=clock[0])

    readings, disclosure = attest.energy_measured(opener=read)
    assert len(readings) == 1
    assert readings[0]["meter"] == "meter[2]"
    assert any("expired during meter reads" in error for error in disclosure["errors"])


@pytest.mark.parametrize("path", ["manifest", "verify"])
def test_slow_attestation_build_does_not_block_async_heartbeat(monkeypatch, path):
    import asyncio
    import threading
    import httpx
    from fastapi import FastAPI

    entered, release = threading.Event(), threading.Event()
    build_threads = []

    def slow_build(**_kwargs):
        build_threads.append(threading.get_ident())
        entered.set()
        if not release.wait(3):
            raise RuntimeError("test build was not released")
        return {"ok": True}

    monkeypatch.setattr(attest, "build_manifest", slow_build)
    monkeypatch.setattr(attest, "build_statement", slow_build)
    monkeypatch.setattr(attest, "verify", lambda *_args, **_kwargs: {"ok": True})
    app = FastAPI()
    attest.register(app)

    @app.get("/heartbeat")
    async def heartbeat():
        return {"ok": True}

    async def exercise():
        loop_thread = threading.get_ident()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            request = asyncio.create_task(client.get("/api/a11oy/v1/attest/" + path))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                assert len(build_threads) == 1 and build_threads[0] != loop_thread
                response = await asyncio.wait_for(client.get("/heartbeat"), timeout=0.5)
                assert response.status_code == 200
                assert not request.done()
            finally:
                release.set()
            assert (await request).status_code == 200

    asyncio.run(exercise())
