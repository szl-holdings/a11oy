#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Honesty sentence for a measured signer. The frozen route-contract file stays pinned."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from szl_signing_state import SigningState


@pytest.fixture
def runtime():
    import serve
    now = [100.0]
    owner = SigningState(clock=lambda: now[0])
    previous = serve.app.state.szl_signing_state
    previous_module = serve._A11OY_SIGNING_STATE
    serve.app.state.szl_signing_state = owner
    serve._A11OY_SIGNING_STATE = owner
    try:
        yield SimpleNamespace(serve=serve, owner=owner, now=now, client=TestClient(serve.app))
    finally:
        serve.app.state.szl_signing_state = previous
        serve._A11OY_SIGNING_STATE = previous_module


def _sample(runtime):
    return runtime.owner.sample(
        boot_id="boot-simulated", observed_at="2026-10-22T00:00:00+00:00",
        configured=True, key_source="persistent:SIMULATED",
        backend_loaded=True, backend_state="LOADED_LOCAL",
        verification_key_fingerprint="a" * 64, loaded_key_fingerprint="a" * 64,
        expected_key_fingerprint="a" * 64)


def _record(runtime):
    runtime.owner.record_capability_evidence(
        boot_id="boot-simulated", observed_at="2026-10-22T00:00:01+00:00",
        payload_digest="b" * 64, signature_b64="c2ln", key_fingerprint="a" * 64,
        verified=True)


def test_status_honesty_stays_declared_until_evidence_and_never_authorizes(runtime):
    _sample(runtime)
    declared = runtime.serve._signing_status_honesty(runtime.owner.read())
    assert declared.startswith("DECLARED ")
    _record(runtime)
    text = runtime.serve._signing_status_honesty(runtime.owner.read())
    assert text.startswith("MEASURED ")
    assert "not observed signing capability" not in text
    assert "execution authorization" in text
    assert "UNKNOWN" in text
    state = runtime.owner.read()
    assert state["execution_authorized"] is False
    assert state["non_repudiation"] == "UNKNOWN"


def test_measured_route_honesty_matches_evidence_and_stays_unauthorized(runtime):
    _sample(runtime)
    _record(runtime)
    response = runtime.client.get("/api/a11oy/v1/signing-status")
    assert response.status_code == 200
    body = response.json()
    state = body["signing_state"]
    assert state["signing_ready"] is True
    assert state["evidence_class"] == "MEASURED"
    assert state["blockers"] == []
    assert state["execution_authorized"] is False
    assert state["non_repudiation"] == "UNKNOWN"
    assert body["non_repudiation"] is False
    assert body["non_repudiation_state"] == "UNKNOWN"
    assert body["honesty"].startswith("MEASURED ")
    assert "not observed signing capability" not in body["honesty"]
