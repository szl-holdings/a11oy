#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Lean health diagnostics share cached state, never a request-time signer probe."""
from pathlib import Path

import pytest

from tests import test_signing_state_routes as contract
from tests.test_signing_state_routes import runtime  # noqa: F401 -- shared fixture


PATHS = ("/api/health", "/api/a11oy/v1/health")


def views(runtime):
    expected = runtime.owner.read()
    for path in PATHS:
        response = runtime.client.get(path)
        assert response.status_code == 200
        assert "no-store" in response.headers["cache-control"]
        body = response.json()
        assert body["scope"] == "PROCESS_LIVENESS"
        assert body["capability_readiness_asserted"] is False
        assert body["operational_readiness_endpoint"] == "/api/a11oy/healthz"
        assert body["signing_state"] == expected
        signer = body["signer"]
        assert signer["status"] == "ABSENT"
        assert signer["signing_available"] is False
        assert signer["scope"] == "NOT_EVALUATED_BY_THIS_ROUTE"
        assert signer["availability_evaluated"] is False
        assert signer["legacy_status_deprecated"] is True
        assert signer["legacy_status_semantics"] == "LIVENESS_SENTINEL_NOT_A_SIGNER_OBSERVATION"
        assert signer["replacement"] == "signing_state"
    assert expected["signing_ready"] is False
    assert expected["execution_authorized"] is False
    return expected


@pytest.mark.parametrize("changes,available", [
    ({}, True),
    ({"configured": False, "backend_loaded": False, "backend_state": "ABSENT",
      "loaded_key_fingerprint": None}, False),
    ({"backend_loaded": False, "backend_state": "UNAVAILABLE",
      "loaded_key_fingerprint": None}, False),
    ({"loaded_key_fingerprint": "b" * 64}, False),
])
def test_lean_health_reports_same_configured_or_unavailable_state(runtime, changes, available):
    contract.sample(runtime, **changes)
    state = views(runtime)
    assert state["key_material_available"] is available
    assert state["permission"]["state"] == "UNKNOWN"
    assert state["observed_capability"]["state"] == "UNKNOWN"


def test_stale_state_does_not_report_key_availability(runtime):
    contract.sample(runtime)
    runtime.now[0] = 160
    state = views(runtime)
    assert state["freshness"] == "STALE"
    assert state["key_material_available"] is False


def test_missing_owner_is_unavailable(runtime, monkeypatch):
    monkeypatch.delattr(runtime.serve.app.state, "szl_signing_state")
    for path in PATHS:
        body = runtime.client.get(path).json()
        assert body["signing_state"]["key_material_available"] is False
        assert body["signing_state"]["signing_ready"] is False


def test_lean_get_head_obey_original_process_wide_no_effects_guard(runtime, monkeypatch):
    # Reuse the pinned guard unchanged; only its inspected routes/views differ.
    monkeypatch.setattr(contract, "PATHS", PATHS)
    monkeypatch.setattr(contract, "views", views)
    contract.test_get_head_do_not_load_sign_probe_write_or_refresh(runtime, monkeypatch)


def test_lean_suite_has_a_mandatory_separate_ci_process():
    import yaml
    workflow = yaml.safe_load((Path(__file__).resolve().parents[1]
                               / ".github/workflows/tests.yml").read_text())
    steps = workflow["jobs"]["python-demo-critical-routes"]["steps"]
    step, = [row for row in steps
             if row.get("name") == "Verify lean health signing diagnostics in isolation"]
    assert "if" not in step and "continue-on-error" not in step
    assert step["env"] == {"SZL_EVIDENCE_WARM_DELAY": "3600"}
    assert step["run"] == (
        "python -B -m pytest -q -p no:cacheprovider tests/test_lean_health_signing_state.py")
