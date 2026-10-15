# SPDX-License-Identifier: Apache-2.0
"""Native owner uses actual registered SQLite and immutable snapshot readback."""
import asyncio
import base64
import sqlite3

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

import native_readbacks as owner
import observer_runtime as runtime
from observer_adapters import NATIVE_TYPE
from szl_dsse import pae
from tools import execution_acceptance as a
from tests.test_observer_runtime import world, signed_plan, public, HEADERS


def receipt(world, kind="eval-run"):
    body = {"schema": "szl.eval_arena.receipt/v1" if kind == "eval-run" else "szl.agentloop.receipt/v1",
            "fixture": "Native evidence — not a live model run"}
    if kind == "agentloop-run":
        from tests.test_observer_adapters import actual_host_signer
        sign = actual_host_signer(world.runtime_private, *public(world.runtime_private))
        return {"body": body, "dsse": sign(body), "signing": {"state": "SIGNED"}}
    raw = a.canonical(body)
    encoded = pae(NATIVE_TYPE, raw)
    return {"body": body, "dsse": {"payloadType": NATIVE_TYPE, "payload": base64.b64encode(raw).decode(),
            "signatures": [{"keyid": public(world.runtime_private)[1], "sig": base64.b64encode(
                world.runtime_private.sign(encoded, ec.ECDSA(hashes.SHA256()))).decode()}],
            "signed": True, "_pae_sha256": a.digest(encoded)}, "signing": {"state": "SIGNED"}}


def native_owner(world):
    pem, key_id = public(world.runtime_private)
    return owner.NativeReadbacks(world.service, pem, key_id)


def reserve(world, nonce, case_id):
    context, _ = world.subject._identity(nonce)
    return world.service.store.reserve_execution_observation(source_revision=context.source_revision,
        runtime_boot_id=context.runtime_boot_id, run_nonce=nonce, plan_sha256="c" * 64,
        case_id=case_id, request_sha256="d" * 64, receipt_id="native-test-" + case_id,
        started_at=runtime.stamp(runtime.utcnow()))


def test_native_callback_without_reserved_context_has_no_effect(world):
    subject = native_owner(world)
    assert subject.record_eval(receipt(world)) is None
    with sqlite3.connect(world.service.store.path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='execution_native_receipts'").fetchone()


def test_exact_signed_native_bytes_survive_real_snapshot(world):
    subject = native_owner(world)
    nonce, _ = signed_plan(world)
    row = reserve(world, nonce, "eval-run")
    world.writer.snapshot_confirmed("series_a", lambda path:
        runtime.Store.execution_observation_matches(path, row))
    value = receipt(world)
    with subject.case_scope(nonce, "eval-run"):
        result = subject.record_eval(value)
    digest = result["payload_sha256"]
    raw = subject.read_eval(digest)
    assert a.strict_json(raw)["receipt"] == value
    assert result["durability_acknowledged"] is False
    before = world.backend.submits
    assert subject.read_eval(digest) == raw
    assert world.backend.submits == before
    row = world.service.store.complete_execution_observation(row["receipt_id"],
        {"readback_b64": base64.b64encode(raw).decode()})
    predicate = subject.snapshot_predicate([row])
    ack = world.writer.snapshot_confirmed("series_a", predicate)
    path = world.root / "native-ack.sqlite3"
    path.write_bytes(world.objects.get_bytes(ack["entry"]["path"], limit=ack["entry"]["size"]))
    assert predicate(path)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM execution_native_receipts")
    assert not predicate(path)


def test_nested_eval_and_agent_receipt_require_both_native_rows(world):
    subject = native_owner(world)
    nonce, _ = signed_plan(world)
    row = reserve(world, nonce, "agentloop-run")
    with subject.case_scope(nonce, "agentloop-run"):
        ev = subject.record_eval(receipt(world))
        agent = subject.record_agentloop(receipt(world, "agentloop-run"))
    rb = {"record": a.strict_json(subject.read_agentloop(agent["payload_sha256"])),
          "eval_record": a.strict_json(subject.read_eval(ev["payload_sha256"]))}
    row = world.service.store.complete_execution_observation(row["receipt_id"],
        {"readback_b64": base64.b64encode(a.canonical(rb)).decode()})
    assert subject.snapshot_predicate([row])(world.service.store.path)
    with sqlite3.connect(world.service.store.path) as db:
        db.execute("DELETE FROM execution_native_links WHERE native_kind='eval-run'")
    with pytest.raises(owner.NativeReadbackBlocked, match="COMPLETION_READBACK"):
        subject.snapshot_predicate([row])


@pytest.mark.parametrize("fault", ["signature", "body", "scope", "duplicate", "boot", "absent"])
def test_native_recording_refuses_forgery_scope_replay_and_wrong_process(world, fault):
    subject = native_owner(world)
    nonce, _ = signed_plan(world)
    row = reserve(world, nonce, "eval-run")
    value = receipt(world)
    if fault == "signature":
        value["dsse"]["signatures"][0]["sig"] = base64.b64encode(b"wrong").decode()
    elif fault == "body":
        value["body"]["fixture"] = "substituted"
    elif fault == "boot":
        world.service.runtime_boot_id = "other"
    elif fault == "absent":
        nonce = "f" * 64
    with subject.case_scope(nonce, "policy-decide" if fault == "scope" else "eval-run"):
        if fault == "duplicate":
            subject.record_eval(value)
        with pytest.raises(ValueError):
            subject.record_eval(value)
    assert world.writer._inflight == 0


def test_cancel_endpoint_burns_pending_and_inflight_nonce(world):
    import httpx
    nonce, plan = signed_plan(world)
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def pause(case):
            entered.set()
            await release.wait()
        world.subject.adapters.before_case = pause
        task = asyncio.create_task(world.subject.run(plan, nonce, HEADERS))
        await entered.wait()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world.app), base_url=a.ORIGIN) as client:
            denied = await client.post(runtime.PREFIX + "/cancel/" + nonce)
            assert denied.json()["error"] == "OPERATOR_REQUIRED"
            response = await client.post(runtime.PREFIX + "/cancel/" + nonce, headers=HEADERS)
            assert response.json()["remote_cancellation_confirmed"] is False
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(runtime.ObserverBlocked, match="CONSUMED"):
            await world.subject.run(plan, nonce, HEADERS)
    asyncio.run(scenario())
    assert world.effects == [] and nonce not in world.subject._exports
