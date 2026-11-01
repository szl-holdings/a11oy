#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Actual assembled FastAPI routes with SIMULATED lifecycle observations.

Run in a credential-clean, network-denied test process. No real backend is
qualified and no permission/retained receipt is manufactured by these tests.
"""

import asyncio
import builtins
import hashlib
from pathlib import Path
import socket
import sqlite3
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from szl_signing_state import SigningState


PATHS = ("/healthz", "/api/a11oy/v1/signing-status")


@pytest.fixture
def runtime(monkeypatch):
    import serve
    now = [100.0]
    owner = SigningState(clock=lambda: now[0])
    monkeypatch.setattr(serve.app.state, "szl_signing_state", owner)
    monkeypatch.setattr(serve, "_A11OY_SIGNING_STATE", owner)
    return SimpleNamespace(serve=serve, owner=owner, now=now, client=TestClient(serve.app))


def sample(runtime, **changes):
    facts = dict(boot_id="boot-simulated", observed_at="2026-10-22T00:00:00+00:00",
                 configured=True, key_source="persistent:SIMULATED",
                 backend_loaded=True, backend_state="LOADED_LOCAL",
                 verification_key_fingerprint="a" * 64, loaded_key_fingerprint="a" * 64,
                 expected_key_fingerprint="a" * 64)
    facts.update(changes)
    return runtime.owner.sample(**facts)


def views(runtime):
    bodies = []
    for path in PATHS:
        response = runtime.client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert "no-store" in response.headers["cache-control"]
        bodies.append(response.json())
    assert bodies[0]["scope"] == "PROCESS_LIVENESS"
    assert bodies[0]["capability_readiness_asserted"] is False
    assert bodies[0]["signer"]["status"] == "ABSENT"
    assert bodies[0]["signer"]["legacy_status_deprecated"] is True
    assert bodies[1]["non_repudiation"] is False
    assert bodies[1]["non_repudiation_state"] == "UNKNOWN"
    state = bodies[0]["signing_state"]
    assert state["evidence_class"] == "DECLARED"
    assert state == bodies[1]["signing_state"]
    assert bodies[1]["key_persistent"] is (
        state["key_material_available"] and state["key_source"].startswith("persistent:"))
    assert state["signing_ready"] is False
    assert state["execution_authorized"] is False
    return state


@pytest.mark.parametrize("changes,reason", [
    ({"configured": False, "backend_loaded": False, "backend_state": "ABSENT",
      "verification_key_fingerprint": None, "loaded_key_fingerprint": None,
      "expected_key_fingerprint": None}, "SIGNER_BACKEND_UNAVAILABLE"),
    ({"configured": False, "backend_loaded": False, "backend_state": "ABSENT",
      "loaded_key_fingerprint": None}, "KEY_AGREEMENT_UNKNOWN"),
    ({"backend_loaded": False, "backend_state": "UNAVAILABLE",
      "loaded_key_fingerprint": None}, "SIGNER_BACKEND_UNAVAILABLE"),
    ({"loaded_key_fingerprint": "b" * 64}, "KEY_AGREEMENT_MISMATCH"),
])
def test_missing_public_only_startup_failure_and_wrong_key(runtime, changes, reason):
    sample(runtime, **changes)
    state = views(runtime)
    assert state["key_material_available"] is False
    assert reason in state["blockers"]


def test_fresh_positive_metadata_never_establishes_permission(runtime):
    sample(runtime)
    state = views(runtime)
    assert state["key_material_available"] is True
    assert state["permission"]["state"] == "UNKNOWN"
    assert state["observed_capability"]["state"] == "UNKNOWN"
    assert runtime.serve._a11oy_signer_status()["signing_state"] == state


def test_stale_cache_cannot_keep_availability_alive(runtime, monkeypatch):
    observation = sample(runtime)
    state = views(runtime)
    monkeypatch.setitem(runtime.serve._SIGNER_HEALTH_CACHE, "checked_at", 10 ** 30)
    monkeypatch.setitem(runtime.serve._SIGNER_HEALTH_CACHE, "value",
                        {"status": "DSSE-LIVE", "signing_available": True})
    runtime.now[0] = 160
    expired = views(runtime)
    assert state["key_material_available"] is True
    assert expired["key_material_available"] is False
    assert expired["freshness"] == "STALE"
    assert runtime.serve._signer_availability_signal()["signing_available"] is False
    assert runtime.owner._observation is observation


def test_backend_loss_invalidates_availability_without_read_side_probe(runtime):
    sample(runtime)
    assert views(runtime)["key_material_available"] is True
    runtime.owner.invalidate()
    state = views(runtime)
    assert state["key_material_available"] is False
    assert state["backend"]["state"] == "UNAVAILABLE"
    assert state["generation"] == 2


def test_rotation_changes_key_and_generation_without_retaining_capability(runtime):
    sample(runtime)
    first = views(runtime)
    sample(runtime, verification_key_fingerprint="b" * 64,
           loaded_key_fingerprint="b" * 64, expected_key_fingerprint="b" * 64)
    second = views(runtime)
    assert second["generation"] == first["generation"] + 1
    assert second["public_key_fingerprint"] != first["public_key_fingerprint"]
    assert second["observed_capability"]["state"] == "UNKNOWN"


def test_replicas_are_distinguishable_despite_same_public_key(runtime):
    sample(runtime)
    first = views(runtime)
    sample(runtime, boot_id="boot-other-replica")
    second = views(runtime)
    assert first["public_key_fingerprint"] == second["public_key_fingerprint"]
    assert first["runtime_boot_id"] != second["runtime_boot_id"]
    assert second["generation"] != first["generation"]


@pytest.mark.parametrize("clock", [None, True, "100", float("nan"), float("inf"), 10 ** 400, 99])
def test_malformed_or_reversed_clock_cannot_make_endpoints_ready(runtime, clock):
    sample(runtime)
    runtime.now[0] = clock
    state = views(runtime)
    assert state["freshness"] == "UNKNOWN"
    assert state["key_material_available"] is False


def test_actual_rollup_consumes_same_record_without_weakening_frontier(runtime, monkeypatch):
    sample(runtime)
    async def dependency():
        return {"status": "ok", "backend_alive": True, "checked_at": 100}
    monkeypatch.setattr(runtime.serve, "_healthz_dep_ping", dependency)
    monkeypatch.setattr(runtime.serve, "_ledger_storage_signal", lambda: {"status": "available"})
    monkeypatch.setattr(runtime.serve, "_frontier_liveness_signal", lambda: {
        "status": "degraded", "operational_readiness": {
            "ready": False, "blocked_tiles": [{"name": "SIMULATED_UNOBSERVED_CAPABILITY"}]}})
    monkeypatch.setattr(runtime.serve, "_sovereign_health_signal", lambda: {})
    monkeypatch.setattr(runtime.serve, "_brain_health_signal", lambda: {})
    monkeypatch.setattr(runtime.serve, "_preflight_signal", lambda: {"overall": "DEGRADED"})
    response = runtime.client.get("/api/a11oy/healthz")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert body["rollup"]["signer"]["signing_state"] == views(runtime)
    assert body["operational_readiness"]["ready"] is False


def test_get_head_do_not_load_sign_probe_write_or_refresh(runtime, monkeypatch):
    import a11oy_signing_key
    import szl_dsse
    from cryptography.hazmat.primitives.asymmetric import ec
    observation = sample(runtime)
    forbidden = Mock(side_effect=AssertionError("status read attempted a side effect"))
    for module, name in (
        (a11oy_signing_key, "load_signing_key"), (szl_dsse, "_load_private_key"),
        (szl_dsse, "sign_payload"), (ec, "generate_private_key"),
        (runtime.serve, "_a11oy_sign_receipt"), (runtime.serve, "_refresh_a11oy_signing_state"),
        (runtime.serve.app.state, "szl_sign_receipt"),
        (SigningState, "sample"), (SigningState, "invalidate"),
        (sqlite3, "connect"), (socket, "create_connection"),
        (subprocess, "run"), (subprocess, "Popen"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    real_open = builtins.open
    def readonly_open(file, mode="r", *args, **kwargs):
        if any(flag in str(mode) for flag in ("w", "a", "+", "x")):
            return forbidden(file, mode)
        return real_open(file, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", readonly_open)
    for _ in range(2):
        views(runtime)
        for path in PATHS:
            response = runtime.client.head(path)
            assert response.status_code == 200
            assert response.content == b""
            assert "no-store" in response.headers["cache-control"]
    forbidden.assert_not_called()
    assert runtime.owner._observation is observation


def test_sampler_uses_captured_backend_not_a_later_loader_success(runtime, monkeypatch):
    import a11oy_signing_key
    loader = Mock(side_effect=AssertionError("must not reload"))
    monkeypatch.setattr(a11oy_signing_key, "load_signing_key", loader)
    monkeypatch.setattr(runtime.serve, "_A11OY_PRIV", None)
    monkeypatch.setattr(runtime.serve, "_A11OY_PUB_PEM", None)
    monkeypatch.setattr(runtime.serve, "_A11OY_KEYID", "unavailable")
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_SOURCE", "unavailable")
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_ERR", "SIMULATED_STARTUP_FAILURE")
    runtime.serve._refresh_a11oy_signing_state()
    assert views(runtime)["backend"]["state"] == "UNAVAILABLE"
    loader.assert_not_called()


def test_default_mount_startup_failure_does_not_claim_unconfigured(runtime, monkeypatch):
    # The loader can discover its default mount with no configuration env names.
    # A failed load returns unavailable/error but no source; the origin is UNKNOWN.
    monkeypatch.setattr(runtime.serve, "_A11OY_SIGNER_CONFIGURED", False)
    monkeypatch.setattr(runtime.serve, "_A11OY_PRIV", None)
    monkeypatch.setattr(runtime.serve, "_A11OY_PUB_PEM", None)
    monkeypatch.setattr(runtime.serve, "_A11OY_KEYID", "unavailable")
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_SOURCE", "unavailable")
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_ERR", "SIMULATED_DEFAULT_MOUNT_LOAD_FAILURE")
    runtime.serve._refresh_a11oy_signing_state()
    state = views(runtime)
    assert state["signer_configured"] is None
    assert state["configuration_state"] == "UNKNOWN"
    assert state["backend"]["state"] == "UNAVAILABLE"


def test_sampler_reuses_boot_and_preserves_stripped_pem_fingerprint(runtime, monkeypatch):
    pem = b"SIMULATED PUBLIC METADATA\n"
    fingerprint = hashlib.sha256(pem.strip()).hexdigest()
    key = Mock()
    key.public_key.return_value.public_bytes.return_value = pem
    monkeypatch.setattr(runtime.serve, "_A11OY_PRIV", key)
    monkeypatch.setattr(runtime.serve, "_A11OY_PUB_PEM", pem.decode("ascii"))
    monkeypatch.setattr(runtime.serve, "_A11OY_KEYID", fingerprint)
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_SOURCE", "ephemeral")
    monkeypatch.setattr(runtime.serve.app.state, "szl_series_a_service",
                        SimpleNamespace(runtime_boot_id="boot-owned-by-existing-service"),
                        raising=False)
    runtime.serve._refresh_a11oy_signing_state()
    state = views(runtime)
    assert state["runtime_boot_id"] == "boot-owned-by-existing-service"
    assert state["public_key_fingerprint"] == fingerprint
    assert state["fingerprint_algorithm"] == "SHA256_STRIPPED_ASCII_PEM"
    key.sign.assert_not_called()


def test_sampler_retained_public_only_is_known_but_cannot_sign(runtime, monkeypatch):
    pem = "SIMULATED RETAINED PUBLIC METADATA\n"
    fingerprint = hashlib.sha256(pem.strip().encode("ascii")).hexdigest()
    monkeypatch.setattr(runtime.serve, "_A11OY_PRIV", None)
    monkeypatch.setattr(runtime.serve, "_A11OY_PUB_PEM", pem)
    monkeypatch.setattr(runtime.serve, "_A11OY_KEYID", fingerprint)
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_SOURCE", "unavailable")
    monkeypatch.setattr(runtime.serve, "_A11OY_KEY_ERR", None)
    runtime.serve._refresh_a11oy_signing_state()
    state = views(runtime)
    assert state["verification_key_known"] is True
    assert state["verification_key_scope"] == "CAPTURED_SHARED_SIGNER_IDENTITY"
    assert state["historical_verification_keys_evaluated"] is False
    assert state["key_material_available"] is False
    assert state["backend"]["loaded"] is False


def test_sampler_missing_existing_boot_identity_remains_unknown(runtime, monkeypatch):
    monkeypatch.delattr(runtime.serve.app.state, "szl_series_a_service", raising=False)
    runtime.serve._refresh_a11oy_signing_state()
    state = views(runtime)
    assert state["runtime_boot_id"] is None
    assert "RUNTIME_BOOT_ID_UNKNOWN" in state["blockers"]
    assert state["signing_ready"] is False


def test_sampler_failure_and_lifecycle_shutdown_are_bounded(runtime, monkeypatch):
    sample(runtime)
    monkeypatch.setattr(runtime.serve, "_A11OY_SIGNING_STATE_TASK", None)
    failure = Mock(side_effect=RuntimeError("SIMULATED_BACKEND_LOSS"))
    monkeypatch.setattr(runtime.serve, "_refresh_a11oy_signing_state", failure)
    async def lifecycle():
        runtime.serve._start_a11oy_signing_state()
        task = runtime.serve._A11OY_SIGNING_STATE_TASK
        runtime.serve._start_a11oy_signing_state()
        assert runtime.serve._A11OY_SIGNING_STATE_TASK is task
        await runtime.serve._stop_a11oy_signing_state()
        assert task.cancelled()
        assert runtime.serve._A11OY_SIGNING_STATE_TASK is None
    asyncio.run(lifecycle())
    assert views(runtime)["key_material_available"] is False


def test_periodic_sampler_failure_invalidates_previous_observation(runtime, monkeypatch):
    sample(runtime)
    failure = Mock(side_effect=RuntimeError("SIMULATED_BACKEND_LOSS"))
    turns = []
    async def one_interval(delay):
        assert delay == 15
        if turns:
            raise asyncio.CancelledError()
        turns.append(delay)
    with monkeypatch.context() as patch:
        patch.setattr(runtime.serve, "_refresh_a11oy_signing_state", failure)
        patch.setattr(asyncio, "sleep", one_interval)
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(runtime.serve._a11oy_signing_state_loop())
    failure.assert_called_once()
    state = views(runtime)
    assert state["key_material_available"] is False
    assert state["backend"]["state"] == "UNAVAILABLE"
    assert state["observation_sequence"] == 2


def test_signer_module_is_shipped_by_canonical_copy_closure():
    root = Path(__file__).resolve().parents[1]
    lines = (root / "Dockerfile").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("COPY ") and "szl_signing_state.py" in line.split()
               for line in lines)
