"""Focused exact-main semantic merge checks; no external requests or billing writes."""

import json
import secrets
import sys
from types import SimpleNamespace

import httpx

import szl_energy_live as energy


def _gpu(**changes):
    row = {
        "index": 0,
        "name": "test GPU",
        "live": True,
        "power_w": 12.5,
        "joules": 40.25,
        "sample_ts": 100.0,
        "joules_method": "NVML_COUNTER_DELTA",
        "gpu_uuid": "GPU-1",
        "counter_epoch": "epoch-1",
    }
    row.update(changes)
    return row


def test_counter_provenance_is_required_for_measured_joules():
    valid = energy.parse_meter_metrics(json.dumps({
        "engines": [{"engine": "test", "gpus": [_gpu()]}],
        "totals": {"joules": 9999},
    }), now=101.0)
    assert valid["total_joules"] == 40.25
    invalid = energy.parse_meter_metrics(json.dumps({
        "engines": [{"engine": "test", "gpus": [_gpu(joules_method="POWER_INTEGRAL")]}],
        "totals": {"joules": 9999},
    }), now=101.0)
    assert invalid["total_joules"] is None


def test_stale_or_duplicate_gpu_cannot_launder_aggregate():
    stale = energy.parse_meter_metrics(json.dumps({
        "engines": [{"engine": "test", "gpus": [_gpu(sample_ts=80.0)]}],
        "totals": {"joules": 40.25},
    }), now=101.0)
    assert stale["total_joules"] is None
    duplicate = energy.parse_meter_metrics(json.dumps({
        "engines": [{"engine": "a", "gpus": [_gpu()]},
                    {"engine": "b", "gpus": [_gpu(index=1)]}],
    }), now=101.0)
    assert duplicate["total_joules"] is None
    assert all(row["joules"] is None for row in duplicate["gpus"])


def test_merged_engine_totals_cannot_bypass_gpu_provenance(monkeypatch):
    now = energy.time.time()
    meter = {"engines": [
        {"engine": "good", "gpus": [_gpu(sample_ts=now)], "joules": 9999},
        {"engine": "spoof", "gpus": [_gpu(sample_ts=now, gpu_uuid="GPU-2",
                                          joules_method="POWER_INTEGRAL")], "joules": 9999},
    ]}
    monkeypatch.setitem(sys.modules, "szl_energy_operator", SimpleNamespace(
        _fetch_joule_meter=lambda: meter,
    ))
    readings = energy._merged_engine_readings()
    assert readings["good"]["joules"] == 40.25
    assert readings["spoof"]["joules"] is None
    meter["engines"][1]["gpus"][0]["gpu_uuid"] = "GPU-1"
    duplicate = energy._merged_engine_readings()
    assert duplicate["good"]["joules"] is None
    assert duplicate["spoof"]["joules"] is None


def test_prometheus_malformed_gpu_line_cannot_make_partial_set_measured():
    labels = ('gpu="0",name="test",live="true",sample_ts="100",'
              'joules_method="NVML_COUNTER_DELTA",gpu_uuid="GPU-0",counter_epoch="epoch-1"')
    parsed = energy.parse_meter_metrics(
        f'szl_gpu_power_watts{{{labels}}} 12.5\n'
        f'szl_gpu_energy_joules{{{labels}}} 10\n'
        'szl_gpu_power_watts{gpu="1"} +Inf\n'
        'szl_gpu_energy_joules{gpu="1"} +Inf\n', now=101.0,
    )
    assert parsed["total_joules"] is None
    assert all(row["joules"] is None for row in parsed["gpus"])


def test_prometheus_duplicate_uuid_cannot_double_count_one_gpu():
    parts = []
    for index in (0, 1):
        labels = (f'gpu="{index}",name="test-{index}",live="true",sample_ts="100",'
                  'joules_method="NVML_COUNTER_DELTA",gpu_uuid="GPU-shared",counter_epoch="epoch-1"')
        parts.extend((f'szl_gpu_power_watts{{{labels}}} 12.5',
                      f'szl_gpu_energy_joules{{{labels}}} 10'))
    parsed = energy.parse_meter_metrics("\n".join(parts), now=101.0)
    assert parsed["total_joules"] is None
    assert all(row["joules"] is None for row in parsed["gpus"])


def test_meter_access_scoped_and_no_redirect(monkeypatch):
    monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({
        origin: {"client_id": "synthetic-test", "key_hex": secrets.token_hex(32)}
        for origin in ("https://meter2.a-11-oy.com", "https://meter.a-11-oy.com")
    }))
    monkeypatch.setenv("A11OY_METER2_CF_ACCESS_CLIENT_ID", "test-id")
    monkeypatch.setenv("A11OY_METER2_CF_ACCESS_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(energy, "METER_URL", "https://meter2.a-11-oy.com")
    calls = []

    class Client:
        def __init__(self, **kwargs):
            calls.append({"options": kwargs})

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get(self, url, headers):
            calls[-1].update(url=url, headers=headers)
            return SimpleNamespace(status_code=302, text="")

    monkeypatch.setattr(httpx, "Client", Client)
    result = energy._fetch_meter()
    assert result["reachable"] is False and result["status"] == "http-302"
    assert calls[0]["options"]["follow_redirects"] is False
    assert calls[0]["headers"]["CF-Access-Client-Id"] == "test-id"
    assert calls[0]["headers"]["CF-Access-Client-Secret"] == "test-secret"
    assert calls[0]["url"] == "https://meter2.a-11-oy.com/metrics"
    assert calls[0]["headers"]["X-SZL-Meter-Client"] == "synthetic-test"
    monkeypatch.setattr(energy, "METER_URL", "https://meter.a-11-oy.com")
    energy._fetch_meter()
    assert calls[1]["options"]["follow_redirects"] is False
    assert "CF-Access-Client-Id" not in calls[1]["headers"]
    assert "CF-Access-Client-Secret" not in calls[1]["headers"]


def test_structural_gate_nulls_fleet_totals(monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {"reachable": False})
    monkeypatch.setattr(energy, "govern_posture", lambda: {"nodes": [
        {"name": "test", "exporter": "test", "live": True},
    ]})
    monkeypatch.setattr(energy, "_merged_engine_readings", lambda: {
        "test": {"watts": 12.5, "joules": 40.25},
    })
    monkeypatch.setattr(energy, "_merged_model_readings", lambda: {})
    monkeypatch.setitem(sys.modules, "szl_surface_fidelity", SimpleNamespace(
        meter_gate=lambda: {"label": "STRUCTURAL-ONLY"},
    ))
    mesh = energy.build_mesh()
    assert mesh["label"] == "STRUCTURAL-ONLY"
    assert mesh["nodes"][0]["joules"] == 40.25
    assert mesh["total_joules"] is None
    assert mesh["total_watts"] is None


def test_mesh_fleet_total_uses_gate_evidence_not_mismatched_node_or_snapshot(monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "total_joules": 9999, "total_watts": 9999, "gpus": [],
    })
    monkeypatch.setattr(energy, "govern_posture", lambda: {"nodes": [
        {"name": "test", "exporter": "test", "live": True},
    ]})
    monkeypatch.setattr(energy, "_merged_engine_readings", lambda: {
        "test": {"watts": 7, "joules": 70},
    })
    monkeypatch.setattr(energy, "_merged_model_readings", lambda: {})
    gate = {
        "label": "MEASURED", "all_sources_qualified": True,
        "read_at": "2026-10-07T00:00:00+00:00",
        "urls_configured": ["https://meter.example"],
        "reads": [{"url": "https://meter.example", "ok": True}],
        "engines": [{"engine": "test", "meter_url": "https://meter.example", "gpu_evidence": [
            _gpu(sample_ts=energy.time.time(), joules=40.25, power_w=12.5),
        ]}],
        "engine_count": 1, "joules_total": 9999, "watts_total": 9999,
    }
    monkeypatch.setitem(sys.modules, "szl_surface_fidelity", SimpleNamespace(
        meter_gate=lambda: gate,
    ))
    mesh = energy.build_mesh()
    assert mesh["label"] == "MEASURED"
    assert mesh["nodes"][0]["joules"] == 70
    assert mesh["nodes"][0]["sample_basis"] == "MERGED_METER_INDEPENDENT_SCRAPE"
    assert mesh["nodes"][0]["fleet_sample_parity"] == "UNKNOWN"
    assert mesh["total_joules"] == 40.25
    assert mesh["total_watts"] == 12.5
    assert mesh["totals_from_node_readings"] is False
    assert mesh["totals_from_meter_gate"] is True
    assert mesh["fleet_sample_basis"] == "METER_GATE_PER_REQUEST_GPU_EVIDENCE"
    assert mesh["fleet_sample_read_at"] == "2026-10-07T00:00:00+00:00"
    assert mesh["node_fleet_sample_parity"] == "UNKNOWN"
    gate["engines"][0]["meter_url"] = "https://different.example"
    wrong_source = energy.build_mesh()
    assert wrong_source["label"] == "STRUCTURAL-ONLY"
    assert wrong_source["total_joules"] is None
    gate["engines"][0]["meter_url"] = "https://meter.example"
    gate["engines"][0].pop("gpu_evidence")
    old_gate = energy.build_mesh()
    assert old_gate["label"] == "STRUCTURAL-ONLY"
    assert old_gate["total_joules"] is None


def test_unverified_model_number_cannot_bypass_normalized_map(monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {"reachable": False})
    monkeypatch.setattr(energy, "govern_posture", lambda: {"nodes": [
        {"name": "model", "is_glm": True, "model": "glm-test:latest"},
    ]})
    monkeypatch.setattr(energy, "_merged_engine_readings", lambda: {})
    monkeypatch.setattr(energy, "_merged_model_readings", lambda: {
        "glm-test": {"label": "MEASURED", "joules_per_token": 0.42,
                     "energy_joules": 84.0, "source": "unverified"},
    })
    monkeypatch.setitem(sys.modules, "szl_surface_fidelity", SimpleNamespace(
        meter_gate=lambda: {"label": "STRUCTURAL-ONLY"},
    ))
    node = energy.build_mesh()["nodes"][0]
    assert node["joules_per_token"] is None
    assert node["energy_joules"] is None
    assert node["joules_per_token_label"] == "UNAVAILABLE"


def test_cumulative_counter_never_yields_per_call_sci(monkeypatch):
    monkeypatch.setattr(energy, "meter_snapshot", lambda: {
        "reachable": True, "total_joules": 40.25,
    })
    monkeypatch.setattr(energy, "_fetch_grid_intensity", lambda: (400.0, "MODELED", "test"))
    sci = energy.build_sci()
    assert sci["energy_label"] == "MEASURED"
    assert sci["energy_joules"] == 40.25
    assert sci["carbon_gco2eq"] is None
    assert sci["cumulative_operational_carbon_gco2eq_est"] is not None
    assert sci["cumulative_operational_carbon_label"] == "MODELED"
    assert sci["sci_score_gco2_per_call"] is None
    assert sci["per_inference_attribution"] == "UNAVAILABLE"
    receipt = energy.build_sci_receipt_fields()
    assert receipt["carbon_gco2eq"] is None
    assert receipt["sci_score_gco2_per_call"] is None


def test_historical_ledger_not_relabelled_measured(monkeypatch):
    ledger = SimpleNamespace(
        totals=lambda: {
            "jobs": 2,
            "joules_measured_billable": None,
            "joules_measured_label": "UNAVAILABLE",
            "joules_measured_reason": "legacy receipts lack exclusive-job attribution",
            "historical_reported_billable_joules": 123.0,
            "historical_receipt_label": "REPORTED",
        },
        verify=lambda: {"ok": True, "length": 2},
    )
    monkeypatch.setitem(sys.modules, "szl_energy_ledger", SimpleNamespace(get_ledger=lambda: ledger))
    projection = energy._ledger_totals()
    assert projection["chain_ok"] is True
    assert projection["joules_measured_billable"] is None
    assert projection["joules_measured_label"] == "UNAVAILABLE"
    assert projection["historical_reported_billable_joules"] == 123.0
    assert projection["historical_receipt_label"] == "REPORTED"


def test_old_ledger_numeric_billable_field_is_only_historical(monkeypatch):
    ledger = SimpleNamespace(
        totals=lambda: {"jobs": 1, "joules_measured_billable": 123.0, "kwh_total": 0.000034},
        verify=lambda: {"ok": True, "length": 1},
    )
    monkeypatch.setitem(sys.modules, "szl_energy_ledger", SimpleNamespace(get_ledger=lambda: ledger))
    projection = energy._ledger_totals()
    assert projection["joules_measured_billable"] is None
    assert projection["joules_measured_label"] == "UNAVAILABLE"
    assert projection["kwh_total"] is None
    assert projection["historical_reported_billable_joules"] == 123.0
