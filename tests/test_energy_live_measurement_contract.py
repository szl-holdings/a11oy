#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exporter reachability alone cannot establish an energy measurement."""

import json
import time

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import szl_energy_live as energy


@pytest.mark.parametrize("invalid", [None, True, False, -1, float("nan"), float("inf")])
def test_json_meter_rejects_invalid_readings(invalid):
    parsed = energy.parse_meter_metrics(json.dumps({
        "engines": [{"engine": "test", "gpus": [{
            "index": 0, "power_w": invalid, "joules": invalid,
        }]}],
        "totals": {"joules": invalid},
    }))
    assert parsed["gpus"][0]["watts"] is None
    assert parsed["gpus"][0]["joules"] is None
    assert parsed["total_watts"] is None
    assert parsed["total_joules"] is None
    json.dumps(parsed, allow_nan=False)


@pytest.mark.parametrize("body", [
    "# unrelated exporter\nprocess_uptime_seconds 12\n",
    'szl_gpu_power_watts{gpu="0"} -1\nszl_gpu_energy_joules{gpu="0"} -3\n',
    '{"engines":[],"totals":{}}',
])
def test_empty_or_invalid_exporter_does_not_fabricate_zero(body):
    parsed = energy.parse_meter_metrics(body)
    assert parsed["total_watts"] is None
    assert parsed["total_joules"] is None


def test_valid_zero_and_per_gpu_fallback_require_counter_provenance():
    sample_ts = time.time()
    parsed = energy.parse_meter_metrics(json.dumps({
        "engines": [{"engine": "test", "gpus": [{
            "index": 0, "power_w": 0, "joules": 0, "live": True,
            "sample_ts": sample_ts, "gpu_uuid": "GPU-zero",
            "counter_epoch": "epoch-zero", "joules_method": "NVML_COUNTER_DELTA",
        }, {"index": 1, "power_w": 12.5, "joules": 40.25, "live": True,
            "sample_ts": sample_ts, "gpu_uuid": "GPU-one",
            "counter_epoch": "epoch-one", "joules_method": "NVML_COUNTER_DELTA"}]}],
        "totals": {"joules": float("nan")},
    }))
    assert parsed["gpus"][0]["watts"] == 0.0
    assert parsed["gpus"][0]["joules"] == 0.0
    assert parsed["total_watts"] == 12.5
    assert parsed["total_joules"] == 40.25
    json.dumps(parsed, allow_nan=False)


def test_finite_values_cannot_overflow_into_nonfinite_aggregate():
    parsed = energy.parse_meter_metrics(json.dumps({
        "engines": [{"gpus": [
            {"index": 0, "power_w": 1e308, "joules": 1e308},
            {"index": 1, "power_w": 1e308, "joules": 1e308},
        ]}],
    }))
    assert parsed["total_watts"] is None
    assert parsed["total_joules"] is None
    json.dumps(parsed, allow_nan=False)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(energy, "govern_posture", lambda: {"nodes": []})
    monkeypatch.setattr(energy, "_fetch_grid_intensity", lambda: (400.0, "MODELED", "test"))
    app = Starlette()
    energy.register(app)
    with TestClient(app) as session:
        yield session


def test_http_200_power_only_exporter_does_not_claim_measured_joules(client, monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "status": "ok", "total_watts": 12.5,
        "total_joules": None, "gpus": [{"gpu": "0", "watts": 12.5, "joules": None}],
    })
    response = client.get("/api/a11oy/v1/energy/live")
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "UNAVAILABLE"
    assert body["joules_label"] == "UNAVAILABLE"
    assert body["total_joules"] is None
    assert body["watts_label"] == "MEASURED"
    assert body["total_watts"] == 12.5
    assert body["nodes"][0]["joules_label"] == "UNAVAILABLE"


@pytest.mark.parametrize("invalid", [True, -1, float("nan"), float("inf")])
def test_live_and_sci_routes_sanitize_invalid_energy(client, monkeypatch, invalid):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "status": "ok", "total_watts": invalid,
        "total_joules": invalid, "gpus": [{"gpu": "0", "watts": invalid, "joules": invalid}],
    })
    for path in ("live", "sci"):
        response = client.get(f"/api/a11oy/v1/energy/{path}")
        assert response.status_code == 200
        body = response.json()
        assert body["label"] == "UNAVAILABLE"
        if path == "live":
            assert body["total_joules"] is None
            assert body["total_watts"] is None
            assert body["nodes"][0]["joules"] is None
        else:
            assert body["energy_joules"] is None
            assert body["carbon_gco2eq"] is None
            assert body["sci_score_gco2_per_call"] is None


def test_offline_cached_reading_does_not_enter_sci_receipt(client, monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": False, "status": "offline", "total_joules": 40.25,
    })
    body = client.get("/api/a11oy/v1/energy/sci").json()
    assert body["energy_joules"] is None
    assert body["energy_label"] == "UNAVAILABLE"
    assert energy.build_sci_receipt_fields()["energy_joules"] is None


@pytest.mark.parametrize("joules", [0.0, 40.25])
def test_live_route_preserves_valid_numeric_measurements(client, monkeypatch, joules):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "status": "ok", "total_watts": 0.0,
        "total_joules": joules, "gpus": [{"gpu": "0", "watts": 0.0, "joules": joules}],
    })
    body = client.get("/api/a11oy/v1/energy/live").json()
    assert body["label"] == "MEASURED"
    assert body["joules_label"] == "MEASURED"
    assert body["total_joules"] == joules
    assert body["nodes"][0]["joules_label"] == "MEASURED"


def test_sci_zero_is_measured_cumulative_energy_not_per_call_carbon(client, monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "total_joules": 0.0,
    })
    monkeypatch.setattr(energy, "_fetch_grid_intensity", lambda: (400.0, "MEASURED", "test"))
    body = client.get("/api/a11oy/v1/energy/sci").json()
    assert body["energy_joules"] == 0.0
    assert body["energy_kwh"] == 0.0
    assert body["energy_label"] == "MEASURED"
    assert body["carbon_gco2eq"] is None
    assert body["cumulative_operational_carbon_gco2eq_est"] == 0.0
    assert body["cumulative_operational_carbon_label"] == "MODELED"
    assert body["label"] == "UNAVAILABLE"
    assert body["per_inference_attribution"] == "UNAVAILABLE"
    receipt = energy.build_sci_receipt_fields()
    assert receipt["energy_scope"] == "cumulative_exporter_reading"
    assert receipt["per_inference_attribution"] == "UNAVAILABLE"
    assert "cumulative" in receipt["sci_note"]


@pytest.mark.parametrize("invalid", [True, -1, float("nan"), float("inf")])
def test_sci_invalid_carbon_input_cannot_poison_json(client, monkeypatch, invalid):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "total_joules": 40.25,
    })
    monkeypatch.setattr(energy, "_fetch_grid_intensity", lambda: (invalid, "MEASURED", "test"))
    body = client.get("/api/a11oy/v1/energy/sci").json()
    assert body["energy_label"] == "MEASURED"
    assert body["grid_intensity_gco2_per_kwh"] is None
    assert body["grid_intensity_label"] == "UNAVAILABLE"
    assert body["carbon_gco2eq"] is None
    assert body["sci_score_gco2_per_call"] is None
    assert body["label"] == "UNAVAILABLE"
    monkeypatch.setattr(energy, "_fetch_grid_intensity", lambda: (400.0, "MEASURED", "test"))
    monkeypatch.setattr(energy, "_SCI_EMBODIED_GCO2_PER_CALL", invalid)
    body = client.get("/api/a11oy/v1/energy/sci").json()
    assert body["embodied_gco2eq_per_call"] is None
    assert body["embodied_label"] == "UNAVAILABLE"
    assert body["sci_score_gco2_per_call"] is None
    assert body["label"] == "UNAVAILABLE"
    assert energy.build_sci_receipt_fields()["embodied_label"] == "UNAVAILABLE"


def test_sci_overflow_is_unavailable_without_erasing_valid_energy(client, monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "total_joules": 1e308,
    })
    monkeypatch.setattr(energy, "_fetch_grid_intensity", lambda: (1e308, "MEASURED", "test"))
    body = client.get("/api/a11oy/v1/energy/sci").json()
    assert body["energy_label"] == "MEASURED"
    assert body["carbon_gco2eq"] is None
    assert body["sci_score_gco2_per_call"] is None
    assert body["label"] == "UNAVAILABLE"


@pytest.mark.parametrize("invalid", [True, -1, float("nan"), float("inf")])
def test_mesh_invalid_node_and_model_readings_do_not_claim_measurement(client, monkeypatch, invalid):
    import szl_surface_fidelity as fidelity

    monkeypatch.setattr(energy, "meter_snapshot", lambda: {"reachable": True})
    monkeypatch.setattr(energy, "govern_posture", lambda: {"nodes": [{
        "name": "test", "exporter": "test", "is_glm": True, "model": "test:local",
    }]})
    monkeypatch.setattr(energy, "_merged_engine_readings", lambda: {
        "test": {"watts": invalid, "joules": invalid},
    })
    monkeypatch.setattr(energy, "_merged_model_readings", lambda: {
        "test": {"label": "MEASURED", "joules_per_token": invalid},
    })
    monkeypatch.setattr(fidelity, "meter_gate", lambda: {"label": "MEASURED"})
    body = client.get("/api/a11oy/v1/energy/mesh").json()
    assert body["label"] == "STRUCTURAL-ONLY"
    assert body["nodes"][0]["watts"] is None
    assert body["nodes"][0]["joules"] is None
    assert body["nodes"][0]["joules_label"] == "UNAVAILABLE"
    assert body["nodes"][0]["joules_per_token"] is None
    assert body["nodes"][0]["joules_per_token_label"] == "UNAVAILABLE"
    assert body["total_joules"] is None
    assert body["any_node_reading_this_request"] is False
