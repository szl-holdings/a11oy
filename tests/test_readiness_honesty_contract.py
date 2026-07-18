# SPDX-License-Identifier: Apache-2.0
"""Fail-closed contract for the deployment-readiness response."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_static_matrix_cannot_be_reported_as_a_deployment_verdict() -> None:
    source = (ROOT / "serve.py").read_text(encoding="utf-8")
    block = source.split(
        '@app.get("/api/a11oy/v1/readiness/tab-matrix")', 1
    )[1].split(
        'print("[a11oy] Readiness tab-matrix registered', 1
    )[0]

    assert '"matrix_available": False' in block
    assert '"probe_verdict_available": False' in block
    assert "_verdict_available = verdict is not None" in block
    assert '"available": _verdict_available' in block
    assert '"matrix_available": True' in block
    assert '"probe_verdict_available": _verdict_available' in block
    assert "probe not yet run on this deploy" in block


def test_landing_reads_matrix_and_probe_availability_separately() -> None:
    landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")

    assert "if(!d.matrix_available)" in landing
    assert "Boolean(d.probe_verdict_available)" in landing
    assert 'checked ? "REACHABLE" : "SNAPSHOT"' in landing
    assert "static contract; deployment probe pending" in landing
    assert ".data-state.amber" in landing
    for state in ("CACHED", "STALE_CACHE", "SNAPSHOT", "MODELED", "OBSERVED", "AVAILABLE", "DEGRADED"):
        assert state in landing
