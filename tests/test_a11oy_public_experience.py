#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Behavioral contract for the bounded A11oy public experience."""

import asyncio
import ast
import base64
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

import a11oy_public_experience as experience


ORIGIN = "http://testserver"
IDEMPOTENCY_KEY = "5f362345-47ed-4fbd-8d3d-2e4916f4154f"
OTHER_IDEMPOTENCY_KEY = "858247d7-30e1-4079-982d-19b63e9e3df7"
POST_HEADERS = {
    "Origin": ORIGIN,
    "Sec-Fetch-Site": "same-origin",
    "Content-Type": "application/json",
}


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture()
def service() -> experience.PublicExperienceService:
    return experience.PublicExperienceService()


@pytest.fixture()
def client(service: experience.PublicExperienceService) -> TestClient:
    app = FastAPI()

    @app.get("/{full_path:path}")
    async def stale_catch_all(full_path: str) -> HTMLResponse:
        return HTMLResponse(f"SPA fallback: {full_path}")

    experience.register(app, service=service)
    return TestClient(app)


def create(client: TestClient, scenario_id: str, key: str | None = None):
    headers = dict(POST_HEADERS)
    if key:
        headers["Idempotency-Key"] = key
    return client.post(
        f"{experience.API_PREFIX}/sessions",
        headers=headers,
        json={"scenario_id": scenario_id},
    )


def approve(client: TestClient, session: dict, *, scope: str | None = None):
    capability = session["approval_capability"]
    return client.post(
        f"{experience.API_PREFIX}/sessions/{session['session_id']}/approve",
        headers=POST_HEADERS,
        json={
            "capability_token": capability["token"],
            "scope": scope or capability["scope"],
            "expected_sequence": capability["issued_sequence"],
        },
    )


def test_transition_table_is_complete_and_terminal_states_have_no_exit() -> None:
    assert set(experience.LEGAL_TRANSITIONS) == set(experience.ExperienceStage)
    for stage in experience.TERMINAL_STAGES:
        assert experience.LEGAL_TRANSITIONS[stage] == frozenset()
    assert experience.ExperienceStage.APPROVED in experience.LEGAL_TRANSITIONS[
        experience.ExperienceStage.APPROVAL_REQUIRED
    ]
    assert experience.ExperienceStage.RECEIPTED in experience.LEGAL_TRANSITIONS[
        experience.ExperienceStage.VERIFIED
    ]


def test_public_configs_are_exact_allowlists(service) -> None:
    assert set(service.scenarios) == set(experience.EXPECTED_SCENARIO_IDS)
    manifest = json.loads(
        (service.root / "governance" / "public-estate.v1.json").read_text(encoding="utf-8")
    )
    assert {asset.id for asset in service.estate_assets} == {
        asset["id"]
        for kind in ("platforms", "public_products")
        for asset in manifest[kind]
        if asset["public"] is True
    }
    assert all(asset.public and asset.active for asset in service.estate_assets)
    assert all(asset.data_state == "SNAPSHOT" for asset in service.estate_assets)
    assert all(asset.live_url.startswith("https://") for asset in service.estate_assets)


def test_deterministic_replay_excludes_random_session_identity(service) -> None:
    request = experience.CreateSessionRequest(scenario_id="screen-vessel")
    first, _ = service.create_session(request, idempotency_key=None, origin=ORIGIN)
    second, _ = service.create_session(request, idempotency_key=None, origin=ORIGIN)
    assert first.session_id != second.session_id
    assert first.replay == second.replay
    first_events, _ = service.event_snapshot(first.session_id, -1)
    second_events, _ = service.event_snapshot(second.session_id, -1)
    assert [event.stage for event in first_events] == [event.stage for event in second_events]
    assert [item.digest for item in first_events[2].evidence] == [
        item.digest for item in second_events[2].evidence
    ]


def test_idempotency_replays_same_session_and_rejects_conflict(service) -> None:
    request = experience.CreateSessionRequest(scenario_id="investigate-outage")
    first, created = service.create_session(
        request, idempotency_key=IDEMPOTENCY_KEY, origin=ORIGIN
    )
    replay, replay_created = service.create_session(
        request, idempotency_key=IDEMPOTENCY_KEY, origin=ORIGIN
    )
    assert created is True and replay_created is False
    assert replay.session_id == first.session_id
    assert replay.idempotent_replay is True
    assert replay.approval_capability is not None
    assert first.approval_capability is not None
    assert replay.approval_capability == first.approval_capability
    with pytest.raises(experience.ExperienceAPIError) as caught:
        service.create_session(
            experience.CreateSessionRequest(scenario_id="screen-vessel"),
            idempotency_key=IDEMPOTENCY_KEY,
            origin=ORIGIN,
        )
    assert (caught.value.status_code, caught.value.code) == (409, "IDEMPOTENCY_CONFLICT")
    independent, independent_created = service.create_session(
        request,
        idempotency_key=OTHER_IDEMPOTENCY_KEY,
        origin=ORIGIN,
    )
    assert independent_created is True
    assert independent.session_id != first.session_id


@pytest.mark.parametrize(
    "key",
    (
        "predictable-key",
        "5F362345-47ED-4FBD-8D3D-2E4916F4154F",
        "5f36234547ed4fbd8d3d2e4916f4154f",
        "5f362345-47ed-1fbd-8d3d-2e4916f4154f",
    ),
)
def test_http_rejects_noncanonical_or_non_v4_idempotency_keys(client, key) -> None:
    response = create(client, "investigate-outage", key)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_IDEMPOTENCY_KEY"


def test_consumed_capability_is_not_exposed_by_idempotent_replay(service) -> None:
    request = experience.CreateSessionRequest(scenario_id="investigate-outage")
    pending, _ = service.create_session(
        request,
        idempotency_key=IDEMPOTENCY_KEY,
        origin=ORIGIN,
    )
    capability = pending.approval_capability
    assert capability is not None
    completed = service.approve_session(
        pending.session_id,
        experience.ApproveSessionRequest(
            capability_token=capability.token,
            scope=capability.scope,
            expected_sequence=capability.issued_sequence,
        ),
    )
    assert completed.stage is experience.ExperienceStage.RECEIPTED
    replay, created = service.create_session(
        request,
        idempotency_key=IDEMPOTENCY_KEY,
        origin=ORIGIN,
    )
    assert created is False and replay.idempotent_replay is True
    assert replay.approval_capability is None


@pytest.mark.parametrize(
    ("scenario_id", "expected"),
    (
        ("screen-vessel", experience.ExperienceStage.POLICY_DENIED),
        ("review-contract", experience.ExperienceStage.RECOVERY_REQUIRED),
        ("route-inference", experience.ExperienceStage.UNAVAILABLE),
    ),
)
def test_negative_outcomes_are_receipted_without_external_effect(service, scenario_id, expected) -> None:
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id=scenario_id),
        idempotency_key=None,
        origin=ORIGIN,
    )
    assert view.stage is expected and view.terminal is True and view.receipt_id
    receipt = service.get_receipt(view.receipt_id)
    assert receipt.final_stage is expected
    assert receipt.effect_state == "SIMULATED_NO_EXTERNAL_EFFECT"
    assert receipt.data_state == "SIMULATION"
    assert receipt.namespace == "sim-experience"
    assert receipt.signer_state == "UNSIGNED"
    assert receipt.verification_state == "PARTIAL"
    assert receipt.envelope["signatures"] == []


def test_scoped_approval_is_bound_one_time_and_cross_session_safe(service) -> None:
    request = experience.CreateSessionRequest(scenario_id="investigate-outage")
    first, _ = service.create_session(request, idempotency_key=None, origin=ORIGIN)
    second, _ = service.create_session(request, idempotency_key=None, origin=ORIGIN)
    assert first.stage is experience.ExperienceStage.APPROVAL_REQUIRED
    assert first.approval_capability is not None
    cap = first.approval_capability
    bad = experience.ApproveSessionRequest(
        capability_token=cap.token,
        scope=cap.scope,
        expected_sequence=cap.issued_sequence,
    )
    with pytest.raises(experience.ExperienceAPIError) as cross:
        service.approve_session(second.session_id, bad)
    assert cross.value.code == "APPROVAL_CAPABILITY_MISMATCH"
    completed = service.approve_session(first.session_id, bad)
    assert completed.stage is experience.ExperienceStage.RECEIPTED
    assert completed.receipt_id and completed.approval.state == "APPROVED"
    with pytest.raises(experience.ExperienceAPIError) as replay:
        service.approve_session(first.session_id, bad)
    assert replay.value.code == "APPROVAL_NOT_AVAILABLE"


def test_verification_failure_scenario_still_emits_a_separated_receipt(service) -> None:
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="review-property"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    cap = view.approval_capability
    assert cap is not None
    completed = service.approve_session(
        view.session_id,
        experience.ApproveSessionRequest(
            capability_token=cap.token,
            scope=cap.scope,
            expected_sequence=cap.issued_sequence,
        ),
    )
    assert completed.stage is experience.ExperienceStage.VERIFICATION_FAILED
    receipt = service.get_receipt(completed.receipt_id)
    assert receipt.verification_result.state == "VERIFICATION_FAILED"
    assert receipt.chain_integrity == "INTACT"
    checked = service.verify_receipt(receipt.receipt_id)
    assert checked.ok is True
    assert checked.verification_state == "PARTIAL"
    assert checked.checks["signature"] == "UNSIGNED"
    assert checked.effect_state == "SIMULATED_NO_EXTERNAL_EFFECT"


def test_receipt_tamper_fails_without_mutating_stored_receipt(service) -> None:
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    stored = service.get_receipt(view.receipt_id)
    tampered = stored.model_copy(deep=True)
    tampered.scenario_id = "route-inference"
    result = service.verify_receipt(stored.receipt_id, tampered)
    assert result.ok is False
    assert result.checks["receipt_digest"] == "FAILED"
    assert service.get_receipt(stored.receipt_id) == stored


def test_session_and_capability_expiry_fail_closed() -> None:
    clock = Clock()
    service = experience.PublicExperienceService(
        now_fn=clock.now,
        session_ttl_seconds=60,
        capability_ttl_seconds=15,
    )
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="investigate-outage"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    cap = view.approval_capability
    clock.advance(16)
    with pytest.raises(experience.ExperienceAPIError) as expired_cap:
        service.approve_session(
            view.session_id,
            experience.ApproveSessionRequest(
                capability_token=cap.token,
                scope=cap.scope,
                expected_sequence=cap.issued_sequence,
            ),
        )
    assert expired_cap.value.code == "APPROVAL_CAPABILITY_EXPIRED"
    clock.advance(45)
    with pytest.raises(experience.ExperienceAPIError) as expired_session:
        service.get_session(view.session_id)
    assert expired_session.value.code == "SESSION_EXPIRED"


def test_http_contract_guards_origin_shape_body_and_route_precedence(client) -> None:
    health = client.get(f"{experience.API_PREFIX}/health")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store"
    assert health.headers["content-type"].startswith("application/json")
    assert health.json()["external_authority_state"] == "UNAVAILABLE"
    assert client.post(
        f"{experience.API_PREFIX}/sessions", json={"scenario_id": "screen-vessel"}
    ).status_code == 403
    assert client.post(
        f"{experience.API_PREFIX}/sessions",
        headers={**POST_HEADERS, "Origin": "https://attacker.invalid"},
        json={"scenario_id": "screen-vessel"},
    ).status_code == 403
    assert client.post(
        f"{experience.API_PREFIX}/sessions",
        headers={**POST_HEADERS, "Content-Type": "text/plain"},
        content=json.dumps({"scenario_id": "screen-vessel"}),
    ).status_code == 415
    assert create(client, "not-public").status_code == 404
    assert client.post(
        f"{experience.API_PREFIX}/sessions",
        headers=POST_HEADERS,
        json={"scenario_id": "screen-vessel", "tool": "shell"},
    ).status_code == 422


def test_http_sse_resume_approval_and_receipt_verify(client) -> None:
    created = create(client, "investigate-outage", IDEMPOTENCY_KEY)
    assert created.status_code == 201
    session = created.json()
    stream = client.get(session["events_url"])
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "event: experience" in stream.text and "event: end" in stream.text
    first_ids = [
        int(line.removeprefix("id: "))
        for line in stream.text.splitlines()
        if line.startswith("id: ")
    ]
    assert first_ids == list(range(len(first_ids)))
    approved = approve(client, session)
    assert approved.status_code == 200
    completed = approved.json()
    resumed = client.get(
        session["events_url"], headers={"Last-Event-ID": str(first_ids[-1])}
    )
    resumed_ids = [
        int(line.removeprefix("id: "))
        for line in resumed.text.splitlines()
        if line.startswith("id: ")
    ]
    assert resumed_ids and resumed_ids[0] == first_ids[-1] + 1
    receipt_id = completed["receipt_id"]
    before = client.get(f"{experience.API_PREFIX}/receipts/{receipt_id}").json()
    checked = client.post(
        f"{experience.API_PREFIX}/receipts/{receipt_id}/verify",
        headers=POST_HEADERS,
        json={},
    )
    assert checked.status_code == 200 and checked.json()["ok"] is True
    after = client.get(f"{experience.API_PREFIX}/receipts/{receipt_id}").json()
    assert after == before

    # A full receipt is larger than a creation/approval request because it
    # contains the lifecycle and its encoded statement.
    assert len(experience._canonical({"receipt": before})) > experience.MAX_REQUEST_BYTES
    supplied = client.post(
        f"{experience.API_PREFIX}/receipts/{receipt_id}/verify",
        headers=POST_HEADERS,
        json={"receipt": before},
    )
    assert supplied.status_code == 200 and supplied.json()["ok"] is True


def test_body_and_rate_caps_return_bounded_errors(service) -> None:
    app = FastAPI()
    service.rate_limits["create"] = 1
    experience.register(app, service=service)
    client = TestClient(app)
    oversized = "x" * (experience.MAX_REQUEST_BYTES + 1)
    too_large = client.post(
        f"{experience.API_PREFIX}/sessions",
        headers=POST_HEADERS,
        content=oversized,
    )
    assert too_large.status_code == 413
    first = create(client, "screen-vessel")
    assert first.status_code == 429  # the bounded rejected write consumed the bucket


def test_registration_is_idempotent_and_exact_routes_are_first(service) -> None:
    app = FastAPI()

    @app.get("/{full_path:path}")
    async def fallback(full_path: str) -> HTMLResponse:
        return HTMLResponse(full_path)

    first = experience.register(app, service=service)
    second = experience.register(app, service=service)
    assert first["state"] == "REGISTERED"
    assert second["state"] == "ALREADY_REGISTERED"
    paths = [getattr(route, "path", "") for route in app.router.routes]
    assert paths.index(f"{experience.API_PREFIX}/health") < paths.index("/{full_path:path}")
    assert set(experience.experience_routes()) <= set(paths)
    owned = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in experience.experience_routes()
    ]
    assert len(owned) == len(experience.experience_routes())
    assert all(
        getattr(
            getattr(route, "endpoint", None),
            "__a11oy_public_experience_owner__",
            None,
        )
        == experience.ROUTE_OWNER
        for route in owned
    )
    assert {
        route.path: frozenset(route.methods or set()) for route in owned
    } == experience._experience_route_contract()


def test_recomputed_unsigned_replacement_is_not_the_stored_receipt(service) -> None:
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    stored = service.get_receipt(view.receipt_id)
    forged_payload = stored.model_dump(mode="json", by_alias=True, exclude_none=False)
    forged_payload["scenario_id"] = "route-inference"
    digest_payload = service._receipt_digest_payload(forged_payload)
    forged_digest = experience._sha256(digest_payload)
    forged_payload["receipt_digest"] = forged_digest
    forged_payload["current_hash"] = forged_digest
    statement = {
        **experience._jsonable(digest_payload),
        "receipt_digest": forged_digest,
    }
    forged_payload["envelope"] = service._unsigned_envelope(statement)
    forged = experience.ExperienceReceipt.model_validate(forged_payload)

    checked = service.verify_receipt(stored.receipt_id, forged)
    assert forged.receipt_digest != stored.receipt_digest
    assert checked.ok is False
    assert checked.verification_state == "FAILED"
    assert checked.checks["receipt_digest"] == "VERIFIED"
    assert checked.checks["stored_receipt"] == "FAILED"


def test_signed_identity_and_payload_type_are_bound_to_signed_statement() -> None:
    identity = {
        "keyid": "test-key-1",
        "verify_key_url": "/api/a11oy/cosign.pub",
        "key_scope": "DEPLOYMENT_PERSISTENT",
        "key_lifetime": "UNTIL_SECRET_ROTATION",
        "key_source": "test",
        "key_fingerprint_sha256": "a" * 64,
    }

    def signer(statement, *, outer_scope="DEPLOYMENT_PERSISTENT", payload_type=None):
        signed = {**experience._jsonable(statement), "_signing_identity": identity}
        return {
            "payloadType": payload_type or experience.HOST_RECEIPT_PAYLOAD_TYPE,
            "payload": base64.b64encode(experience._canonical(signed)).decode("ascii"),
            "signatures": [{"sig": "test-signature", "keyid": identity["keyid"]}],
            "signed": True,
            "verify_key_url": identity["verify_key_url"],
            "key_scope": outer_scope,
            "key_lifetime": identity["key_lifetime"],
            "key_fingerprint_sha256": identity["key_fingerprint_sha256"],
        }

    service = experience.PublicExperienceService(
        sign_fn=signer,
        verify_fn=lambda envelope: {"signature_valid": True},
    )
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    stored = service.get_receipt(view.receipt_id)
    assert stored.signer_state == "VERIFIED_PERSISTENT"
    assert stored.verification_state == "VERIFIED"
    assert service.verify_receipt(stored.receipt_id).ok is True

    scope_tamper = stored.model_copy(deep=True)
    scope_tamper.envelope["key_scope"] = "PROCESS_BOOT_EPHEMERAL"
    scope_tamper.signer_state = "VERIFIED_EPHEMERAL"
    checked_scope = service.verify_receipt(stored.receipt_id, scope_tamper)
    assert checked_scope.ok is False
    assert checked_scope.checks["signed_identity"] == "FAILED"
    assert checked_scope.checks["stored_receipt"] == "FAILED"

    type_tamper = stored.model_copy(deep=True)
    type_tamper.envelope["payloadType"] = "text/plain"
    checked_type = service.verify_receipt(stored.receipt_id, type_tamper)
    assert checked_type.ok is False
    assert checked_type.checks["payload_type"] == "FAILED"

    unbound_service = experience.PublicExperienceService(
        sign_fn=lambda statement: signer(
            statement, outer_scope="PROCESS_BOOT_EPHEMERAL"
        ),
        verify_fn=lambda envelope: {"signature_valid": True},
    )
    unbound_view, _ = unbound_service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    unbound = unbound_service.get_receipt(unbound_view.receipt_id)
    assert unbound.signer_state == "UNAVAILABLE"
    assert unbound.verification_state == "PARTIAL"
    assert unbound.envelope["signatures"] == []


def test_receipt_capacity_preflight_is_atomic_and_ttl_recovers() -> None:
    clock = Clock()
    service = experience.PublicExperienceService(
        now_fn=clock.now,
        max_receipts=1,
        max_sessions=8,
        receipt_ttl_seconds=30,
    )
    full, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    pending, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="investigate-outage"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    cap = pending.approval_capability
    assert cap is not None
    before = service.get_session(pending.session_id)
    with pytest.raises(experience.ExperienceAPIError) as capacity:
        service.approve_session(
            pending.session_id,
            experience.ApproveSessionRequest(
                capability_token=cap.token,
                scope=cap.scope,
                expected_sequence=cap.issued_sequence,
            ),
        )
    assert capacity.value.code == "RECEIPT_CAPACITY_REACHED"
    after = service.get_session(pending.session_id)
    assert after == before
    assert after.stage is experience.ExperienceStage.APPROVAL_REQUIRED
    assert service.store.sessions[pending.session_id].approval_consumed is False
    health = service.health()
    assert health.status == "DEGRADED"
    assert health.storage.receipt_capacity_remaining == 0
    assert health.storage.retention_policy == "TTL_BOUNDED"

    clock.advance(31)
    with pytest.raises(experience.ExperienceAPIError) as expired:
        service.get_receipt(full.receipt_id)
    assert expired.value.code == "RECEIPT_EXPIRED"
    assert full.receipt_id in service.store.receipts  # GET remains a pure projection.
    assert service.health().status == "READY"
    completed = service.approve_session(
        pending.session_id,
        experience.ApproveSessionRequest(
            capability_token=cap.token,
            scope=cap.scope,
            expected_sequence=cap.issued_sequence,
        ),
    )
    assert completed.stage is experience.ExperienceStage.RECEIPTED
    assert full.receipt_id not in service.store.receipts


def test_approval_rolls_back_if_receipt_commit_raises(service, monkeypatch) -> None:
    pending, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="investigate-outage"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    cap = pending.approval_capability
    assert cap is not None
    original_issue = service._issue_receipt_locked

    def store_then_fail(record, receipt_id):
        original_issue(record, receipt_id)
        raise RuntimeError("injected post-store failure")

    monkeypatch.setattr(service, "_issue_receipt_locked", store_then_fail)
    request = experience.ApproveSessionRequest(
        capability_token=cap.token,
        scope=cap.scope,
        expected_sequence=cap.issued_sequence,
    )
    with pytest.raises(RuntimeError, match="injected post-store failure"):
        service.approve_session(pending.session_id, request)
    restored = service.get_session(pending.session_id)
    assert restored.stage is experience.ExperienceStage.APPROVAL_REQUIRED
    assert restored.approval.state == "REQUIRED"
    assert service.store.sessions[pending.session_id].approval_consumed is False
    assert service.store.receipts == {}
    assert service.store.receipt_expiries == {}

    monkeypatch.setattr(service, "_issue_receipt_locked", original_issue)
    completed = service.approve_session(pending.session_id, request)
    assert completed.stage is experience.ExperienceStage.RECEIPTED


def test_replay_digest_binds_behavior_approval_and_evidence(service) -> None:
    scenario = service.scenarios["investigate-outage"]
    original = service._replay_info(scenario).simulation_digest
    payload = scenario.model_dump(mode="json", exclude_none=False)
    variants = []

    changed_action = copy.deepcopy(payload)
    changed_action["action"] = "simulate.changed-action"
    variants.append(changed_action)

    changed_scope = copy.deepcopy(payload)
    changed_scope["approval_scope"] = "Approve a different simulation scope"
    variants.append(changed_scope)

    changed_evidence = copy.deepcopy(payload)
    changed_evidence["evidence"][0]["title"] = "Different synthetic evidence"
    changed_evidence["evidence"][0]["uri"] = "/evidence/different"
    variants.append(changed_evidence)

    for variant in variants:
        changed = experience.ScenarioDefinition.model_validate(variant)
        assert service._replay_info(changed).simulation_digest != original


def test_incremental_request_cap_stops_before_buffering_full_body() -> None:
    messages = [
        {
            "type": "http.request",
            "body": b"x" * (experience.MAX_REQUEST_BYTES // 2),
            "more_body": True,
        },
        {
            "type": "http.request",
            "body": b"y" * (experience.MAX_REQUEST_BYTES // 2 + 1),
            "more_body": True,
        },
        {
            "type": "http.request",
            "body": b"z" * experience.MAX_REQUEST_BYTES,
            "more_body": False,
        },
    ]
    calls = 0

    async def receive():
        nonlocal calls
        value = messages[calls]
        calls += 1
        return value

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": f"{experience.API_PREFIX}/sessions",
            "raw_path": f"{experience.API_PREFIX}/sessions".encode(),
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 443),
        },
        receive,
    )
    with pytest.raises(HTTPException) as too_large:
        asyncio.run(
            experience._bounded_model(request, experience.CreateSessionRequest)
        )
    assert too_large.value.status_code == 413
    assert calls == 2


def test_rate_limiter_bounds_identity_buckets_and_reclaims_stale_entries() -> None:
    limiter = experience.FixedWindowRateLimiter(window_seconds=10, max_buckets=2)
    limiter.check("a", 2, 0.0)
    limiter.check("b", 2, 0.0)
    with pytest.raises(experience.ExperienceAPIError) as bounded:
        limiter.check("c", 2, 0.0)
    assert bounded.value.code == "RATE_LIMITED"
    assert len(limiter._buckets) == 2

    limiter.check("c", 2, 11.0)
    assert set(limiter._buckets) == {"c"}


@pytest.mark.parametrize(
    "uri",
    (
        "//untrusted.invalid/evidence",
        "https://untrusted.invalid/evidence",
        "/\\untrusted.invalid/evidence",
        "/evidence/line\nbreak",
    ),
)
def test_nonlocal_evidence_uri_is_rejected(uri) -> None:
    with pytest.raises(ValueError, match="same-origin absolute path"):
        experience.EvidenceConfig(
            id="bad-uri",
            title="Bad URI",
            source_class="SIMULATION",
            uri=uri,
        )
    relative = experience.EvidenceConfig(
        id="good-relative",
        title="Relative URI",
        source_class="SIMULATION",
        uri="/evidence/local",
    )
    assert relative.uri == "/evidence/local"


def test_partial_or_foreign_route_registration_fails_closed(service) -> None:
    app = FastAPI()

    @app.get(f"{experience.API_PREFIX}/health")
    async def foreign_health():
        return {"status": "foreign"}

    with pytest.raises(RuntimeError, match="partial, duplicated, or owned"):
        experience.register(app, service=service)


def test_session_capacity_health_recovers_when_sessions_expire() -> None:
    clock = Clock()
    service = experience.PublicExperienceService(
        now_fn=clock.now, max_sessions=1, session_ttl_seconds=30
    )
    request = experience.CreateSessionRequest(scenario_id="investigate-outage")
    service.create_session(request, idempotency_key=None, origin=ORIGIN)
    assert service.health().status == "DEGRADED"
    assert service.health().storage.session_capacity_remaining == 0
    with pytest.raises(experience.ExperienceAPIError) as capacity:
        service.create_session(request, idempotency_key=None, origin=ORIGIN)
    assert capacity.value.code == "SESSION_CAPACITY_REACHED"
    clock.advance(31)
    assert service.health().status == "READY"
    assert service.health().storage.session_capacity_remaining == 1


def test_creation_rolls_back_receipt_and_idempotency_on_post_store_failure(service, monkeypatch) -> None:
    original_issue = service._issue_receipt_locked

    def store_then_fail(record, receipt_id):
        original_issue(record, receipt_id)
        raise RuntimeError("injected creation commit failure")

    monkeypatch.setattr(service, "_issue_receipt_locked", store_then_fail)
    request = experience.CreateSessionRequest(scenario_id="screen-vessel")
    with pytest.raises(RuntimeError, match="injected creation commit failure"):
        service.create_session(request, idempotency_key=IDEMPOTENCY_KEY, origin=ORIGIN)
    assert not service.store.sessions
    assert not service.store.receipts
    assert not service.store.receipt_expiries
    assert not service.store.idempotency
    monkeypatch.setattr(service, "_issue_receipt_locked", original_issue)
    retried, created = service.create_session(
        request, idempotency_key=IDEMPOTENCY_KEY, origin=ORIGIN
    )
    assert created is True and retried.receipt_id


@pytest.mark.parametrize(
    "verdict",
    (
        {"ok": True},
        {"valid": True},
        {"ok": True, "signature_valid": False},
        {"signature": {"valid": False, "verified": True}},
        {"checks": [
            {"check": "signature", "status": "PASS"},
            {"check": "signature", "status": "FAILED"},
        ]},
    ),
)
def test_signature_verdict_requires_unambiguous_signature_success(verdict) -> None:
    assert experience.PublicExperienceService._verifier_passed(verdict) is False


def test_malformed_envelope_is_failed_without_a_server_exception(service) -> None:
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    candidate = service.get_receipt(view.receipt_id)
    candidate.envelope["payloadType"] = []
    checked = service.verify_receipt(view.receipt_id, candidate)
    assert checked.ok is False and checked.checks["payload_type"] == "FAILED"


def test_noncanonical_json_is_rejected_before_model_processing(client) -> None:
    response = client.post(
        f"{experience.API_PREFIX}/sessions",
        headers=POST_HEADERS,
        content='{"scenario_id":"screen-vessel","unsupported":NaN}',
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_JSON"


@pytest.mark.parametrize(
    ("key_source", "expected_signer_state"),
    (("ephemeral", "VERIFIED_EPHEMERAL"), ("persistent:test-only", "VERIFIED_PERSISTENT")),
)
def test_receipts_use_canonical_host_signer_and_real_signature_verifier(
    key_source, expected_signer_state
) -> None:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    # Compile only the canonical pure signing functions, without booting the
    # application, reaching providers, or loading deployment secrets.
    host_path = Path(experience.__file__).with_name("serve.py")
    tree = ast.parse(host_path.read_text(encoding="utf-8"), filename=str(host_path))
    names = {"_a11oy_pae", "_a11oy_canonical", "_a11oy_sign_receipt", "_a11oy_loop_verify"}
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == names
    payload_assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_A11OY_PAYLOAD_TYPE" for target in node.targets)
    )
    payload_type = ast.literal_eval(payload_assignment.value)
    assert payload_type == experience.HOST_RECEIPT_PAYLOAD_TYPE
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    namespace = {
        "_A11OY_PRIV": private_key,
        "_A11OY_PUB_PEM": public_pem,
        "_A11OY_PAYLOAD_TYPE": payload_type,
        "_A11OY_KEYID": "canonical-local-test-key",
        "_A11OY_LEGACY_RAW_PEM_KEYID": "legacy-local-test-key",
        "_A11OY_KEY_SOURCE": key_source,
        "_A11OY_KEY_ERR": None,
        "_b64v2": base64,
        "_hashv2": hashlib,
        "_jsonv2": json,
        "_dtv2": datetime,
        "_tzv2": timezone,
        "_ecv2": ec,
        "_hashesv2": hashes,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(host_path), "exec"), namespace)
    service = experience.PublicExperienceService(
        sign_fn=namespace["_a11oy_sign_receipt"],
        verify_fn=namespace["_a11oy_loop_verify"],
    )
    view, _ = service.create_session(
        experience.CreateSessionRequest(scenario_id="screen-vessel"),
        idempotency_key=None,
        origin=ORIGIN,
    )
    receipt = service.get_receipt(view.receipt_id)
    assert receipt.signer_state == expected_signer_state
    assert receipt.verification_state == "VERIFIED"
    checked = service.verify_receipt(receipt.receipt_id)
    assert checked.ok is True
    assert checked.checks["signature"] == "VERIFIED"
    assert checked.checks["signed_identity"] == "VERIFIED"
