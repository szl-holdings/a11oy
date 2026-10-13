"""Brain energy views must not promote historical ledger values to measurements."""

import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

import szl_be_hardening
import szl_brain_command
import szl_brain_hub
import szl_fabric_surface


class _Ledger:
    def __init__(self, totals):
        self._totals = totals

    def totals(self):
        return self._totals

    def persistence_info(self):
        return {"label": "EPHEMERAL", "survives_redeploy": False}

    def storage_health(self):
        return {"status": "ok"}


def _install_ledger(monkeypatch, totals):
    ledger = _Ledger(totals)
    monkeypatch.setitem(
        sys.modules, "szl_energy_ledger", SimpleNamespace(get_ledger=lambda: ledger)
    )


@pytest.mark.parametrize(
    "totals",
    [
        {"jobs": 1, "joules_measured_billable": 12.5, "joules_total": 12.5,
         "kwh_total": 0.000003, "would_charge_cents": 2, "charged_cents": 1},
        {"jobs": 1, "joules_measured_label": "UNAVAILABLE",
         "joules_measured_reason": "NO_VERIFIED_EXCLUSIVE_JOB_ATTRIBUTION",
         "joules_measured_billable": None, "joules_total": None,
         "kwh_total": None, "would_charge_cents": None, "charged_cents": None},
        {"jobs": 1, "joules_measured_label": "MEASURED",
         "joules_measured_billable": float("inf"), "joules_total": float("inf")},
        {"jobs": 1, "joules_measured_label": "MEASURED",
         "joules_measured_billable": 12.5, "joules_total": 12.5},
    ],
)
def test_unverified_ledger_values_stay_unavailable(monkeypatch, totals):
    _install_ledger(monkeypatch, totals)
    for summary in (szl_brain_hub.energy_summary(), szl_brain_command._energy_summary()):
        assert summary["label"] == "UNAVAILABLE"
        assert summary["joules_measured_billable"] is None
        assert summary["kwh_total"] is None
        assert summary["would_charge_cents"] is None
        assert summary["charged_cents"] is None


def test_complete_future_attribution_contract_can_surface_measured_pool(monkeypatch):
    _install_ledger(monkeypatch, {
        "jobs": 1, "joules_measured_label": "MEASURED",
        "attribution_verified": True,
        "attribution_method": "NVML_TOTAL_ENERGY_COUNTER_EXCLUSIVE_JOB_DELTA_V1",
        "attribution_version": 1,
        "joules_measured_billable": 12.5, "joules_total": 12.5,
        "kwh_total": 0.000003, "would_charge_cents": 2, "charged_cents": 0,
    })
    for summary in (szl_brain_hub.energy_summary(), szl_brain_command._energy_summary()):
        assert summary["label"] == "MEASURED"
        assert summary["joules_measured_billable"] == 12.5


def test_equal_share_from_measured_pool_is_still_modeled(monkeypatch):
    monkeypatch.setattr(szl_brain_hub, "_known_surface", lambda *_: True)
    pulse = {
        "ns": "a11oy", "knowledge": {"label": "MODELED"},
        "energy": {"label": "MEASURED", "joules_measured_billable": 12.5},
        "lit": {"surfaces_lit": 2},
    }
    budget = szl_brain_hub.allocate_budget(pulse, "example")["energy_budget"]
    assert budget["label"] == "MODELED"
    assert budget["joules_allocated"] == 6.25


@pytest.mark.parametrize(
    "energy",
    [
        {"joules_measured_total": 12.5},
        {"joules_measured_total": 12.5, "joules_measured_label": "MEASURED"},
        {"joules_measured_total": float("inf"), "joules_measured_label": "MEASURED"},
        {"joules_measured_total": None, "joules_measured_label": "MEASURED"},
    ],
)
def test_fabric_does_not_default_missing_meter_evidence_to_measured(monkeypatch, energy):
    payloads = {
        szl_fabric_surface._COMPUTE_POOL_PATH: {"nodes": [], "counts": {}},
        szl_fabric_surface._ENERGY_OP_PATH: energy,
        szl_fabric_surface._ENERGY_PROV_PATH: {"verify": {"ok": True}},
    }
    monkeypatch.setattr(
        szl_fabric_surface, "_self_get", lambda path, **_kwargs: payloads[path]
    )
    fabric = szl_fabric_surface._fabric_summary()
    assert fabric["status"] == "DEGRADED"
    assert fabric["summary"]["joules_measured_label"] == "UNAVAILABLE"
    assert fabric["summary"]["joules_measured_total"] is None


@pytest.mark.parametrize(
    "operator_status",
    [
        {"joules_measured_total": 12.5, "measured_jobs": 1},
        {"joules_measured_total": 12.5, "joules_measured_label": "MEASURED",
         "measured_jobs": 1},
    ],
)
def test_forge_ledger_requires_attribution_not_just_a_counter(
    monkeypatch, tmp_path, operator_status
):
    monkeypatch.setitem(
        sys.modules, "szl_energy_operator",
        SimpleNamespace(_OPERATOR=SimpleNamespace(status=lambda: operator_status)),
    )
    app = FastAPI()
    szl_be_hardening.harden(
        app, "a11oy", khipu_path=str(tmp_path / "brain-energy-khipu.jsonl")
    )
    route = next(r for r in app.routes if r.path == "/api/a11oy/v1/forge/ledger")
    # The handler has no await points; step its coroutine directly so this
    # contract test does not need a Windows socket-backed event loop.
    with pytest.raises(StopIteration) as done:
        route.endpoint().send(None)
    body = done.value.value
    assert body["energy_ledger"]["joules_measured_label"] == "UNAVAILABLE"
    assert body["energy_ledger"]["joules_measured_total"] is None
    assert body["energy_ledger"]["measured_jobs"] is None
