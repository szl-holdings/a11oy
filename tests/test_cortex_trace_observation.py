#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the real route/middleware boundary with deterministic inference data."""
import copy
import json
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_governed_cortex as cortex
import vsp_otel.middleware as otel


REVISION = "a" * 40
TRACE = "00-" + "1" * 32 + "-" + "2" * 16 + "-00"


@pytest.fixture
def proposal(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", REVISION)
    body = {
        "source_revision": REVISION,
        "model": {"sha256": cortex.MODEL_SHA256},
        "output_sha256": "b" * 64,
        "decision": "REVIEW_PROPOSAL_ONLY",
        "executed": False,
        "tool_execution": False,
        "authority_state": "NO_ACTION_AUTHORITY",
    }
    return {
        "state": "PROPOSAL",
        "output": "private-output-marker",
        "source_revision": REVISION,
        "model": {"sha256": cortex.MODEL_SHA256},
        "executed": False,
        "tool_execution": False,
        "authority_state": "NO_ACTION_AUTHORITY",
        "nemo": [
            {"stage": stage, "decision": "ALLOW"}
            for stage in ("PRE_GENERATION", "TEXT_R1_R5", "POST_GENERATION")
        ],
        "receipt": {
            "payload": body,
            "receipt_sha256": cortex.canonical_sha256(body),
            "signature": {"status": "UNSIGNED_RUNTIME"},
            "persistence": "EPHEMERAL_PROCESS_MEMORY_ONLY",
        },
    }


def client_for(proposal, *, middleware=True):
    app = FastAPI()
    if middleware:
        otel.install(app, service_name="trace-contract-test", endpoint=None)
    cortex.register(app)
    return TestClient(app)


def test_route_observes_actual_server_span_without_changing_receipt(proposal):
    before = cortex.canonical_bytes(proposal["receipt"])
    with mock.patch.object(cortex, "infer_payload", side_effect=lambda request: copy.deepcopy(proposal)):
        with client_for(proposal) as client:
            response = client.post(
                "/api/v2/governed-infer",
                json={"prompt": "private-request-marker"},
                headers={"traceparent": TRACE},
            )
            repeated = client.post("/api/v2/governed-infer", json={"prompt": "private-request-marker"})
    assert response.status_code == repeated.status_code == 200
    body = response.json()
    event = body["trace_observation"]
    current = otel.parse_traceparent(response.headers["traceparent"])
    assert event["state"] == "OBSERVED"
    assert event["trace_id"] == "1" * 32 == current["trace_id"]
    assert event["span_id"] == current["parent_id"] != "2" * 16
    assert event["trace_flags"] == "00"
    assert repeated.json()["trace_observation"]["trace_id"] != event["trace_id"]
    assert cortex.canonical_bytes(body["receipt"]) == before
    assert body["authority_state"] == "NO_ACTION_AUTHORITY"
    assert body["executed"] is body["tool_execution"] is False
    assert "private-" not in json.dumps(event, allow_nan=False)
    assert event["collector_delivery"] == "UNVERIFIED"


@pytest.mark.parametrize("fault", ["missing_context", "constructor_error", "receipt_drift"])
def test_diagnostic_failure_preserves_success_and_hides_exception(proposal, fault):
    if fault == "receipt_drift":
        proposal["receipt"]["receipt_sha256"] = "c" * 64
    with mock.patch.object(cortex, "infer_payload", return_value=copy.deepcopy(proposal)):
        with mock.patch.object(cortex.trace_ir, "receipt_observation", wraps=cortex.trace_ir.receipt_observation) as observe:
            if fault == "constructor_error":
                observe.side_effect = RuntimeError("private-error-marker")
            with client_for(proposal, middleware=fault != "missing_context") as client:
                response = client.post("/api/v2/governed-infer", json={"prompt": "status"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "PROPOSAL"
    assert body["trace_observation"]["state"] == "UNAVAILABLE"
    assert "private-error-marker" not in json.dumps(body["trace_observation"], allow_nan=False)
    assert body["receipt"] == proposal["receipt"]


@pytest.mark.parametrize("mutation", ["missing_witness", "duplicate_witness", "blocked_witness", "authority", "model", "source", "signature"])
def test_inconsistent_metadata_cannot_claim_observed(proposal, mutation):
    if mutation == "missing_witness":
        proposal["nemo"].pop()
    elif mutation == "duplicate_witness":
        proposal["nemo"][2] = proposal["nemo"][0]
    elif mutation == "blocked_witness":
        proposal["nemo"][1]["decision"] = "BLOCK"
    elif mutation == "authority":
        proposal["executed"] = True
    elif mutation == "model":
        proposal["model"]["sha256"] = "c" * 64
    elif mutation == "source":
        proposal["source_revision"] = "c" * 40
    elif mutation == "signature":
        proposal["receipt"]["signature"]["status"] = "SIGNED"
    result = cortex._receipt_trace_observation(proposal, TRACE)
    assert result["state"] == "UNAVAILABLE"
    assert result["diagnostic"]["decision"] == "HOLD"
    assert "private-" not in json.dumps(result, allow_nan=False)


def test_existing_nemo_denial_never_observes_success(proposal):
    with (
        mock.patch.object(cortex, "infer_payload", side_effect=cortex.CortexBoundaryError("nemo_text_witness_blocked", 422)),
        mock.patch.object(cortex, "_receipt_trace_observation") as observe,
        client_for(proposal) as client,
    ):
        response = client.post("/api/v2/governed-infer", json={"prompt": "status"})
    assert response.status_code == 422
    assert "trace_observation" not in response.json()
    observe.assert_not_called()


def test_discovery_reads_do_not_create_observations(proposal):
    with mock.patch.object(cortex, "_receipt_trace_observation") as observe, client_for(proposal) as client:
        response = client.get("/api/v2/governed-contract")
        last = client.get("/api/v2/anatomy/last")
    assert response.status_code == last.status_code == 200
    assert response.json()["trace_observation"]["authority"] == "NONE"
    assert "observation_sha256" not in response.text
    observe.assert_not_called()


def test_receipt_authority_drift_cannot_hide_behind_response_flags(proposal):
    proposal["receipt"]["payload"]["executed"] = True
    proposal["receipt"]["receipt_sha256"] = cortex.canonical_sha256(proposal["receipt"]["payload"])
    result = cortex._receipt_trace_observation(proposal, TRACE)
    assert result["state"] == "UNAVAILABLE"
    assert result["diagnostic"]["decision"] == "HOLD"
