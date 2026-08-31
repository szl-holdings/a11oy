"""Quantum-bio claim language must expose the boundary of VERIFIED."""

from __future__ import annotations

import json

import szl_quant_qbio_holo as rollup
import szl_quantum_bio as qbio


def test_summary_scopes_verified_to_computational_reproducibility() -> None:
    response = qbio._h_summary(None)
    payload = json.loads(response.body)

    assert payload["verification_scope"] == "COMPUTATIONAL_REPRODUCIBILITY_ONLY"
    assert "not experimental validation" in payload["verification_boundary"]
    for result in payload["results"]:
        if result["status"] == "VERIFIED":
            assert result["verification_scope"] == payload["verification_scope"]


def test_status_rollup_preserves_scope_on_verified_models() -> None:
    payload = rollup._qbio_status()

    assert payload["verification_scope"] == "COMPUTATIONAL_REPRODUCIBILITY_ONLY"
    assert "not experimental validation" in payload["verification_boundary"]
    for model in payload["models"]:
        if model["status"] == "VERIFIED":
            assert model["verification_scope"] == payload["verification_scope"]


def test_scope_disclaims_measurement_and_advantage() -> None:
    boundary = qbio.VERIFICATION_BOUNDARY.lower()
    assert "not an instrument measurement" in boundary
    assert "not evidence of quantum advantage" in boundary
