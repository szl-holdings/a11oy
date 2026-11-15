# SPDX-License-Identifier: Apache-2.0
"""Read-only source/image identity witnesses stay explicit and fail closed."""

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_healthz_exposes_source_identity_and_unattested_image(monkeypatch):
    import serve

    source_sha = "a" * 40
    monkeypatch.setattr(
        serve.app.state,
        "szl_build_identity_reader",
        lambda: {
            "state": "OBSERVED",
            "revision": source_sha,
            "revision_source": "env:SZL_GIT_SHA",
        },
        raising=False,
    )
    monkeypatch.setattr(serve, "_healthz_dep_ping", lambda: None, raising=False)
    # Keep the health route's read-only dependency probes deterministic.
    async def dependency():
        return {"status": "ok", "backend_alive": True, "checked_at": 100.0}
    monkeypatch.setattr(serve, "_healthz_dep_ping", dependency)
    monkeypatch.setattr(serve, "_ledger_storage_signal", lambda: {"status": "available"})
    monkeypatch.setattr(serve, "_signer_availability_signal", lambda: {"status": "ABSENT"})
    monkeypatch.setattr(serve, "_frontier_liveness_signal", lambda: {
        "status": "unavailable", "operational_readiness": {
            "ready": False, "blocked_tiles": []}})
    monkeypatch.setattr(serve, "_sovereign_health_signal", lambda: {})
    monkeypatch.setattr(serve, "_brain_health_signal", lambda: {})
    monkeypatch.setattr(serve, "_preflight_signal", lambda: {"overall": "DEGRADED"})

    body = TestClient(serve.app).get("/api/a11oy/healthz").json()
    identity = body["runtime_identity"]
    assert identity["source_repository"] == "szl-holdings/a11oy"
    assert identity["source_revision"] == source_sha
    assert identity["source_revision_source"] == "env:SZL_GIT_SHA"
    assert identity["source_revision_state"] == "OBSERVED"
    assert identity["image_digest"] is None
    assert identity["image_identity_state"] == "UNAVAILABLE"
    assert identity["image_attestation"] is False
    assert identity["hardware_attestation"] is False
    assert identity["execution_authority"] is False


def test_provenance_board_exposes_source_identity_without_attestation():
    import szl_provenance

    app = FastAPI()
    source_sha = "b" * 40
    app.state.szl_build_identity_reader = lambda: {
        "state": "OBSERVED",
        "revision": source_sha,
        "revision_source": "env:SZL_GIT_SHA",
    }
    szl_provenance.register_provenance(app, "a11oy")

    body = TestClient(app).get("/api/a11oy/provenance").json()
    identity = body["runtime_identity"]
    assert identity["source_repository"] == "szl-holdings/a11oy"
    assert identity["source_revision"] == source_sha
    assert identity["source_revision_source"] == "env:SZL_GIT_SHA"
    assert identity["image_digest"] is None
    assert identity["image_attestation"] is False
    assert identity["execution_authority"] is False
