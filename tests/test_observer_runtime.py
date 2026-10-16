#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real Series-A SQLite/snapshot/CAS orchestration, synthetic endpoint boundaries.

No live network or authority is used. Keys are generated only inside temporary
test fixtures. Fixed-adapter semantic tests are a separate integration layer.
"""

import asyncio
import base64
import hashlib
import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

import a11oy_state_store as ss
import observer_runtime as observer
from routers.series_a_control_plane import Service
from szl_dsse import pae
from tests.state_store_support import FakeClock, FakeHeadBackend, replica
from tools import execution_acceptance as acceptance


HEADERS = {"authorization": "Bearer producer-fixture-operator", "x-a11oy-tenant": "producer-fixture-tenant"}


def public(private):
    pem = private.public_key().public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo)
    return pem, hashlib.sha256(pem.strip()).hexdigest()


def envelope(payload, private, kind=acceptance.PLAN_TYPE):
    raw = acceptance.canonical(payload)
    return {"payloadType": kind, "payload": base64.b64encode(raw).decode(),
            "signatures": [{"keyid": public(private)[1], "sig": base64.b64encode(
                private.sign(pae(kind, raw), ec.ECDSA(hashes.SHA256()))).decode()}]}


def remote_rows(world):
    entry = world.backend.head()["snapshots"].get("series_a")
    if not entry:
        return []
    path = world.root / "remote-readback.sqlite3"
    path.write_bytes(world.objects.get_bytes(entry["path"], limit=entry["size"]))
    with sqlite3.connect(path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "execution_observations" not in tables:
            return []
        return db.execute("SELECT case_id,state FROM execution_observations ORDER BY case_id").fetchall()


class SyntheticAdapters:
    """Only the fixed native effect boundary is synthetic; HTTP+storage are real."""

    def __init__(self, app, world):
        self.app, self.world = app, world
        self.before_case = None

    def preflight(self, plan):
        assert set(case["id"] for case in plan["cases"]) == set(acceptance.CONTRACTS)

    async def capture(self, case, credentials):
        if self.before_case:
            await self.before_case(case)
        rows = remote_rows(self.world)
        assert len(rows) == 5, "All attempts must be present in immutable acknowledged bytes before any effect"
        assert dict(rows)[case["id"]] == "RESERVED"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=acceptance.ORIGIN) as client:
            response = await client.post(case["path"], headers=credentials, json=case["body"])
        return SimpleNamespace(response_status=response.status_code, response_bytes=response.content,
                               readback_bytes=acceptance.canonical(self.world.effects[-1]))


@pytest.fixture
def world(tmp_path, monkeypatch):
    clock, backend = FakeClock(), FakeHeadBackend()
    objects = ss.LocalDirObjectStore(tmp_path / "objects")
    writer = replica(tmp_path, "a", objects, backend, clock)
    writer.boot()
    writer.heartbeat_once()
    monkeypatch.setattr(ss, "_ACTIVE", writer)
    for name, value in {ss.ENABLE_ENV: ss.ENABLED_VALUE, "A11OY_SERIES_A_SQLITE_JOURNAL": "DELETE",
                        "A11OY_CODE_ADMIN_KEY": "producer-fixture-operator",
                        "A11OY_CODE_TENANT": "producer-fixture-tenant", "SZL_GIT_SHA": "a" * 40,
                        "SPACE_REPOSITORY_COMMIT": "b" * 40}.items():
        monkeypatch.setenv(name, value)
    runtime_private, approval_private = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    key_path = tmp_path / "fixture-runtime.pem"
    key_path.write_bytes(runtime_private.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    monkeypatch.setenv("A11OY_RECEIPT_KEY_PATH", str(key_path))
    for name in ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM", "A11OY_RECEIPT_KEY_PEM"):
        monkeypatch.delenv(name, raising=False)
    approval_public, approval_id = public(approval_private)
    runtime_public, runtime_id = public(runtime_private)
    authority_file = tmp_path / "fixture-public-pins.json"
    authority_file.write_text(json.dumps({"schema": "szl.execution-authority-pins/v1",
        "approval_public_pem": approval_public.decode(), "approval_key_id": approval_id,
        "runtime_public_pem": runtime_public.decode(), "runtime_key_id": runtime_id}))
    result = SimpleNamespace(root=tmp_path, clock=clock, backend=backend, objects=objects,
                             writer=writer, approval_private=approval_private, effects=[],
                             runtime_private=runtime_private, authority_file=authority_file)
    routes = []
    for case_id, path in acceptance.CONTRACTS.items():
        async def native(request, case_id=case_id):
            result.effects.append({"ok": True, "case_id": case_id, "evidence_class": "SYNTHETIC_ENDPOINT"})
            return JSONResponse(result.effects[-1])
        routes.append(Route(path, native, methods=["POST"]))
    result.app = Starlette(routes=routes)
    result.service = Service()
    result.subject = observer.Observer(result.service, result.app, authority_file=authority_file)
    result.subject.adapters = SyntheticAdapters(result.app, result)
    observer.register(result.app, result.subject)
    yield result
    writer._close_watchers()


def signed_plan(world, *, subject=None, mutate=None):
    subject = subject or world.subject
    challenge = subject.challenge(HEADERS)["challenge"]
    nonce = challenge["run_nonce"]
    limits = {"max_model_requests": 2, "max_output_tokens": 100, "max_elapsed_seconds": 5}
    bodies = {"policy-decide": {"request_id": nonce + ":policy-decide", "action": {"operation": "inspect-synthetic-record"}},
              "policy-compliance": {"framework": "NIST"}, "operator-ask": {"question": "Which formulas are locked?"},
              "eval-run": {"model_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct", "suite": "honesty_v1",
                           "execution_mode": "live", "execution_limits": limits},
              "agentloop-run": {"task": "What is two plus two?", "mode": "chat",
                  "model_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct", "eval_suite": "honesty_v1", "max_retries": 0,
                  "sandbox": False, "consult_brain": False, "allocate_energy": False, "execution_limits": limits}}
    plan = {"schema": "szl.execution-acceptance-plan/v1", **{key: challenge[key] for key in
            ("origin", "source_revision", "runtime_revision", "runtime_boot_id", "run_nonce",
             "issued_at", "expires_at", "operator_reference")}, "max_requests": 5, "retries": 0,
            "cases": [{"id": case_id, "method": "POST", "path": path, "body": bodies[case_id],
                       "expected_status": 200, "response_assertions": {"/ok": True},
                       "readback_assertions": {"/ok": True}} for case_id, path in acceptance.CONTRACTS.items()]}
    if mutate:
        mutate(plan)
    return nonce, envelope(plan, world.approval_private)


def run(world, nonce, plan):
    return asyncio.run(world.subject.run(plan, nonce, HEADERS))


def test_five_effects_require_real_reservation_snapshot_and_completion_ack(world):
    nonce, plan = signed_plan(world)
    raw = run(world, nonce, plan)
    result = acceptance.strict_json(raw)
    assert len(world.effects) == 5
    assert all(state == "COMPLETED" for _, state in remote_rows(world))
    context, _ = world.subject._identity(nonce)
    assert acceptance.validate(result["bundle"], context)["binding_checks_passed"] is True
    assert result["publication_eligible"] is False
    assert result["storage_acknowledgment"]["label"] == "series_a"
    before = world.backend.submits
    assert asyncio.run(world.subject.export(nonce, HEADERS)) == raw
    assert world.backend.submits == before, "GET export must not snapshot or advance HEAD"


def test_complete_plan_cannot_be_replayed(world):
    nonce, plan = signed_plan(world)
    run(world, nonce, plan)
    with pytest.raises(observer.ObserverBlocked, match="CONSUMED"):
        run(world, nonce, plan)
    assert len(world.effects) == 5


@pytest.mark.parametrize("missing", ["approval", "hf_revision", "operator", "tenant", "persistent_key", "active_manager"])
def test_missing_external_admission_disables_before_reservation(world, monkeypatch, missing):
    if missing == "approval":
        world.subject.pins = None
    elif missing == "hf_revision":
        monkeypatch.delenv("SPACE_REPOSITORY_COMMIT")
    elif missing == "operator":
        monkeypatch.delenv("A11OY_CODE_ADMIN_KEY")
    elif missing == "tenant":
        monkeypatch.delenv("A11OY_CODE_TENANT")
    elif missing == "persistent_key":
        world.service.signer.source = "ephemeral"
    else:
        monkeypatch.setattr(ss, "_ACTIVE", None)
    with pytest.raises((observer.ObserverBlocked, acceptance.EvidenceError)):
        world.subject.challenge(HEADERS)
    assert world.effects == [] and remote_rows(world) == []


@pytest.mark.parametrize("field,value", [("source_revision", "c" * 40), ("runtime_revision", "d" * 40),
                                         ("runtime_boot_id", "wrong-boot"), ("operator_reference", "owner")])
def test_signed_identity_substitution_does_not_admit_effect(world, field, value):
    nonce, plan = signed_plan(world, mutate=lambda body: body.update({field: value}))
    with pytest.raises((observer.ObserverBlocked, acceptance.EvidenceError)):
        run(world, nonce, plan)
    assert world.effects == [] and remote_rows(world) == []


def test_failed_reservation_publication_consumes_attempts_without_dispatch(world, monkeypatch):
    nonce, plan = signed_plan(world)
    def failed_submit(*args):
        raise ss.StorageBlocked("STATE_DATASET_UNREACHABLE")
    monkeypatch.setattr(world.backend, "submit", failed_submit)
    with pytest.raises(ss.StorageBlocked):
        run(world, nonce, plan)
    assert world.effects == []
    with pytest.raises(observer.ObserverBlocked, match="CONSUMED"):
        run(world, nonce, plan)


def test_uncertain_landed_reservation_is_independently_acknowledged(world):
    nonce, plan = signed_plan(world)
    world.backend.fail_next_submit = "uncertain_landed"
    assert acceptance.strict_json(run(world, nonce, plan))["bundle"]["observations"]
    assert len(world.effects) == 5


def test_cancelled_dispatch_burns_all_reserved_cases_and_never_exports(world):
    nonce, plan = signed_plan(world)
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def pause(case):
            entered.set()
            await release.wait()
        world.subject.adapters.before_case = pause
        task = asyncio.create_task(world.subject.run(plan, nonce, HEADERS))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(remote_rows(world)) == 5
        with pytest.raises(observer.ObserverBlocked, match="UNAVAILABLE"):
            await world.subject.export(nonce, HEADERS)
    asyncio.run(scenario())
    assert world.effects == []
    with pytest.raises(observer.ObserverBlocked, match="CONSUMED"):
        run(world, nonce, plan)


def test_source_change_after_ack_prevents_first_effect(world, monkeypatch):
    nonce, plan = signed_plan(world)
    original = world.subject._acknowledge
    def drift(manager, rows):
        result = original(manager, rows)
        monkeypatch.setenv("SZL_GIT_SHA", "e" * 40)
        return result
    monkeypatch.setattr(world.subject, "_acknowledge", drift)
    with pytest.raises(observer.ObserverBlocked):
        run(world, nonce, plan)
    assert world.effects == [] and len(remote_rows(world)) == 5


def test_restart_rejects_old_boot_plan_even_when_reservations_restore(world, monkeypatch):
    nonce, plan = signed_plan(world)
    run(world, nonce, plan)
    world.clock.advance(200)
    successor = replica(world.root, "b", world.objects, world.backend, world.clock)
    successor.boot()
    successor.heartbeat_once()
    monkeypatch.setattr(ss, "_ACTIVE", successor)
    service = Service()
    restarted = observer.Observer(service, world.app, authority_file=world.authority_file)
    restarted.adapters = SyntheticAdapters(world.app, world)
    with pytest.raises(observer.ObserverBlocked, match="CONSUMED_OR_UNKNOWN"):
        asyncio.run(restarted.run(plan, nonce, HEADERS))
    assert len(world.effects) == 5
    with sqlite3.connect(service.store.path) as db:
        assert db.execute("SELECT count(*) FROM execution_observations").fetchone()[0] == 5
    successor._close_watchers()


def test_http_routes_authenticate_before_parsing(world):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world.app), base_url=acceptance.ORIGIN) as client:
            response = await client.post(observer.PREFIX + "/run", content=b"{")
            assert response.json()["error"] == "OPERATOR_REQUIRED"
            response = await client.post(observer.PREFIX + "/challenge", headers=HEADERS)
            assert response.status_code == 200
            assert response.json()["execution_authorized"] is False
    asyncio.run(scenario())
    assert world.effects == [] and remote_rows(world) == []


def test_completed_context_is_resolved_only_from_retained_digest(world, monkeypatch):
    nonce, plan = signed_plan(world)
    exported = acceptance.strict_json(run(world, nonce, plan))
    digest = acceptance.digest(acceptance.canonical(exported["bundle"]))
    before = world.backend.submits
    context = world.subject.context_for_bundle_digest(digest)
    assert context.run_nonce == nonce
    assert world.backend.submits == before
    with pytest.raises(observer.ObserverBlocked, match="NOT_ADMITTED"):
        world.subject.context_for_bundle_digest("0" * 64)
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "e" * 40)
    with pytest.raises(observer.ObserverBlocked, match="IDENTITY_CHANGED"):
        world.subject.context_for_bundle_digest(digest)


def test_failed_completion_ack_burns_plan_and_withholds_export(world, monkeypatch):
    nonce, plan = signed_plan(world)
    original = world.backend.submit
    calls = []
    def fail_second(parent, body, operation_id):
        calls.append(operation_id)
        if len(calls) >= 2:
            raise ss.StorageBlocked("STATE_DATASET_UNREACHABLE")
        return original(parent, body, operation_id)
    monkeypatch.setattr(world.backend, "submit", fail_second)
    with pytest.raises(ss.StorageBlocked):
        run(world, nonce, plan)
    assert len(world.effects) == 1
    assert all(state == "RESERVED" for _, state in remote_rows(world))
    with pytest.raises(observer.ObserverBlocked, match="UNAVAILABLE"):
        asyncio.run(world.subject.export(nonce, HEADERS))
    with pytest.raises(observer.ObserverBlocked, match="CONSUMED"):
        run(world, nonce, plan)


def test_concurrent_replay_has_one_effect_per_case(world):
    nonce, plan = signed_plan(world)
    async def scenario():
        results = await asyncio.gather(world.subject.run(plan, nonce, HEADERS),
                                       world.subject.run(plan, nonce, HEADERS), return_exceptions=True)
        assert sum(isinstance(result, bytes) for result in results) == 1
        assert sum(isinstance(result, observer.ObserverBlocked) for result in results) == 1
    asyncio.run(scenario())
    assert len(world.effects) == 5


@pytest.mark.parametrize("change", ["expired", "operator", "tenant", "hf", "boot", "lease"])
def test_change_after_first_effect_prevents_next_effect_and_export(world, monkeypatch, change):
    nonce, plan = signed_plan(world)
    original = world.subject.adapters.capture
    async def change_after_capture(case, credentials):
        captured = await original(case, credentials)
        if change == "expired":
            future = world.subject._challenges[nonce].expires_at + timedelta(seconds=1)
            monkeypatch.setattr(observer, "utcnow", lambda: future)
        elif change == "operator":
            monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "rotated")
        elif change == "tenant":
            monkeypatch.setenv("A11OY_CODE_TENANT", "rotated")
        elif change == "hf":
            monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "e" * 40)
        elif change == "boot":
            world.service.runtime_boot_id = "new-boot"
        else:
            world.backend.unreachable = True
        return captured
    monkeypatch.setattr(world.subject.adapters, "capture", change_after_capture)
    with pytest.raises((observer.ObserverBlocked, ss.StorageBlocked)):
        run(world, nonce, plan)
    assert len(world.effects) == 1
    assert nonce not in world.subject._exports


def test_cancelled_snapshot_worker_keeps_inflight_fence_until_finished(world, monkeypatch):
    import threading
    nonce, plan = signed_plan(world)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = world.subject._acknowledge
    def pause_ack(manager, rows):
        entered.set()
        release.wait(timeout=10)
        try:
            return original(manager, rows)
        finally:
            finished.set()
    monkeypatch.setattr(world.subject, "_acknowledge", pause_ack)
    async def scenario():
        task = asyncio.create_task(world.subject.run(plan, nonce, HEADERS))
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert world.writer._inflight == 1, "Storage worker must retain its own write fence"
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
    try:
        asyncio.run(scenario())
    finally:
        release.set()
    assert world.writer._inflight == 0 and world.effects == []
    assert nonce not in world.subject._exports


def test_export_capacity_rejected_before_reservations_or_effects(world, monkeypatch):
    monkeypatch.setattr(observer, "MAX_EXPORTS", 1)
    first_nonce, first_plan = signed_plan(world)
    run(world, first_nonce, first_plan)
    nonce, plan = signed_plan(world)
    with pytest.raises(observer.ObserverBlocked, match="CAPACITY"):
        run(world, nonce, plan)
    assert len(world.effects) == 5 and len(remote_rows(world)) == 5


def test_invalid_pins_leave_concrete_registration_disabled(world, monkeypatch):
    app = Starlette()
    app.state.szl_series_a_service = world.service
    invalid_path = world.root / "invalid-pins.json"
    invalid_path.write_text('{"schema":"wrong"}')
    monkeypatch.setenv("A11OY_EXECUTION_AUTHORITY_FILE", str(invalid_path))
    result = observer.register_from_service(app)
    assert result["authority_configured"] is False
    assert result["configuration_error"] == "INVALID_AUTHORITY_CONFIGURATION"
    with pytest.raises(observer.ObserverBlocked, match="AUTHORITY_UNAVAILABLE"):
        app.state.szl_execution_observer.challenge(HEADERS)
    assert world.effects == [] and remote_rows(world) == []


def test_http_size_limit_stops_stream_before_parse(world):
    async def body():
        yield b" " * (acceptance.MAX_BYTES + 1)
        pytest.fail("The request stream should stop after the size bound")
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world.app), base_url=acceptance.ORIGIN) as client:
            response = await client.post(observer.PREFIX + "/run", headers=HEADERS, content=body())
            assert response.json()["error"] == "PLAN_TOO_LARGE"
    asyncio.run(scenario())
    assert world.effects == [] and remote_rows(world) == []


def test_authority_expiry_cancels_native_await_and_burns_plan(world, monkeypatch):
    nonce, plan = signed_plan(world)
    expires_at = world.subject._challenges[nonce].expires_at
    # Snapshot setup must not spend the native-await timeout under test.
    now = [expires_at - timedelta(seconds=0.1)]
    monkeypatch.setattr(observer, "utcnow", lambda: now[0])
    cancelled = []
    async def stall(case):
        now[0] = expires_at + timedelta(microseconds=1)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(case["id"])
            raise
    world.subject.adapters.before_case = stall
    with pytest.raises(observer.ObserverBlocked, match="AUTHORITY_EXPIRED"):
        run(world, nonce, plan)
    assert len(cancelled) == 1 and world.effects == []
    assert len(remote_rows(world)) == 5 and nonce not in world.subject._exports
    assert world.subject._challenges[nonce].state == "BURNED"
    with pytest.raises(observer.ObserverBlocked, match="CONSUMED"):
        run(world, nonce, plan)


def restart(world, monkeypatch):
    from native_readbacks import NativeReadbacks
    world.clock.advance(200)
    successor = replica(world.root, "archive-successor", world.objects, world.backend, world.clock)
    successor.boot()
    successor.heartbeat_once()
    monkeypatch.setattr(ss, "_ACTIVE", successor)
    service = Service()
    restored = observer.Observer(service, world.app, authority_file=world.authority_file)
    world.app.state.execution_native_readbacks = NativeReadbacks(service, *public(world.runtime_private))
    return successor, restored


def test_restart_restores_whole_bundle_but_missing_native_records_deny_archive(world, monkeypatch):
    nonce, plan = signed_plan(world)
    original = acceptance.strict_json(run(world, nonce, plan))
    successor, restored = restart(world, monkeypatch)
    try:
        before = world.backend.submits
        journal = restored._journal_at(restored.service.store.path, nonce)
        assert acceptance.strict_json(journal["bundle_json"].encode()) == original["bundle"]
        assert acceptance.strict_json(journal["plan_envelope_json"].encode()) == plan
        with pytest.raises(ValueError, match="NATIVE_COMPLETION_READBACK_REQUIRED"):
            restored.restore_completed_archives()
        assert world.backend.submits == before
        with pytest.raises(observer.ObserverBlocked, match="UNAVAILABLE"):
            asyncio.run(restored.export(nonce, HEADERS))
        digest = acceptance.digest(acceptance.canonical(original["bundle"]))
        with pytest.raises(observer.ObserverBlocked, match="NOT_ADMITTED"):
            restored.context_for_bundle_digest(digest)
        with pytest.raises(observer.ObserverBlocked, match="CONSUMED_OR_UNKNOWN"):
            asyncio.run(restored.run(plan, nonce, HEADERS))
        assert world.backend.submits == before and len(world.effects) == 5
    finally:
        successor._close_watchers()


def test_unacknowledged_complete_bundle_never_restores_as_export(world, monkeypatch):
    nonce, plan = signed_plan(world)
    original = world.subject._acknowledge
    def fail_final_ack(manager, rows):
        if world.subject._journal_at(world.service.store.path, nonce)["state"] == "COMPLETE":
            raise ss.StorageBlocked("STATE_FINAL_PUBLICATION_UNAVAILABLE")
        return original(manager, rows)
    monkeypatch.setattr(world.subject, "_acknowledge", fail_final_ack)
    with pytest.raises(ss.StorageBlocked):
        run(world, nonce, plan)
    assert len(world.effects) == 5
    assert world.subject._journal_at(world.service.store.path, nonce)["state"] == "COMPLETE"
    successor, restored = restart(world, monkeypatch)
    try:
        assert restored.restore_completed_archives()["restored"] == 0
        with pytest.raises(observer.ObserverBlocked, match="UNAVAILABLE"):
            asyncio.run(restored.export(nonce, HEADERS))
        assert restored._journal_at(restored.service.store.path, nonce)["state"] == "PLANNED"
    finally:
        successor._close_watchers()


def test_native_mount_reuses_registered_service_and_never_mints_authority(world, monkeypatch):
    from fastapi import FastAPI
    import routers.series_a_control_plane as series
    monkeypatch.setenv("A11OY_EXECUTION_AUTHORITY_FILE", str(world.authority_file))
    app = FastAPI()
    result = series.register(app)
    assert result["execution_observer"]["authority_configured"] is True
    assert app.state.szl_execution_observer.service is app.state.szl_series_a_service
    assert app.state.execution_native_readbacks.service is app.state.szl_series_a_service
    assert app.state.szl_execution_observer.service.signer.keyid == public(world.runtime_private)[1]
    paths = [route.path for route in app.routes]
    assert observer.PREFIX + "/run" in paths and observer.PREFIX + "/cancel/{nonce}" in paths
    assert world.effects == []
