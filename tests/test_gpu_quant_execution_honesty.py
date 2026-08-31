"""Execution-honesty contracts for the classical finance quant engine."""

from __future__ import annotations

import szl_gpu_quant as quant


def _all_acceleration_dependencies_present() -> dict[str, bool]:
    return {
        "cupy": True,
        "cuml": True,
        "cudf": True,
        "gtda": True,
        "ripser_plusplus": True,
        "numpy": True,
    }


def test_dependency_readiness_never_claims_gpu_execution(monkeypatch) -> None:
    """Imports and reachability are not proof that a GPU kernel executed."""
    monkeypatch.setattr(quant, "_gpu_reachable", lambda state=None: True)
    monkeypatch.setattr(
        quant, "_gpu_libs_present", _all_acceleration_dependencies_present
    )

    backend = quant._compute_backend()

    assert backend["acceleration_dependencies_ready"] is True
    assert backend["acceleration_implementation_wired"] is False
    assert backend["execution_evidence"] is None
    assert backend["compute_path"] == "CPU_REFERENCE"
    assert backend["label"] == "SAMPLE"
    assert "GPU" not in backend["backend"]


def test_pipeline_receipt_carries_actual_cpu_reference_path(monkeypatch) -> None:
    monkeypatch.setattr(quant, "_gpu_reachable", lambda state=None: True)
    monkeypatch.setattr(
        quant, "_gpu_libs_present", _all_acceleration_dependencies_present
    )

    result = quant.run_pipeline()
    backend = result["compute_backend"]
    receipt = result["signed_receipt"]["receipt"]

    assert backend["compute_path"] == "CPU_REFERENCE"
    assert backend["label"] == "SAMPLE"
    assert receipt["compute_label"] == "SAMPLE"
    assert receipt["gpu_device"] == "CPU pure-Python reference"
    assert receipt["data_source"] == "SAMPLE_SYNTHETIC"
    assert receipt["label"] == quant.SAMPLE_LABEL


def test_no_live_or_backtest_claim_is_emitted() -> None:
    result = quant.run_pipeline(stress=True)
    receipt = result["signed_receipt"]["receipt"]

    assert result["label"] == "SAMPLE_SIGNAL | NOT_LIVE | NO_BACKTEST_VALIDATED"
    assert receipt["label"] == result["label"]
    assert "NO backtest run" in receipt["honesty"]
    assert receipt["data_source"] == "SAMPLE_SYNTHETIC"


def test_reachable_serve_tier_is_not_execution_measurement(monkeypatch) -> None:
    """A reachable sovereign endpoint is not a measured model execution."""
    monkeypatch.setattr(
        quant,
        "_sovereign_state",
        lambda: {
            "sovereign": True,
            "inference": "self-hosted-gpu",
            "mode": "test",
            "backend": "test-gpu",
        },
    )
    monkeypatch.setattr(quant, "_energy_fields", lambda: {})

    panel = quant.tiers_panel()
    local = [tier for tier in panel["tiers"] if tier["where"] == "gpu"]

    assert local
    assert all(tier["label"] == "LIVE_REACHABLE" for tier in local)
    assert all(tier["execution_evidence"] is None for tier in local)
