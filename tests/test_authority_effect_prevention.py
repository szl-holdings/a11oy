#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline integration: separate the checks that stop a capture from a receipt
rejected after captures already happened.

The existing owner is ``ObserverRuntime.run`` together with
``StateStore.snapshot_confirmed``. This module drives that path through the
synthetic adapter harness in ``tests.test_observer_runtime``. It does not add
an authorizer.

Order inside ``run``, before ``adapters.capture``:

1. ``_caller`` admits the operator principal and tenant.
2. ``execution_acceptance.validate_plan`` checks the signed plan. A source,
   runtime, boot, or nonce mismatch raises ``PLAN_BINDING_MISMATCH``.
3. The plan operator reference must match the challenge binding. That mismatch
   raises ``OPERATOR_PLAN_BINDING_MISMATCH`` and is a different code.
4. Local rows are reserved, then ``_acknowledge`` calls
   ``StateStore.snapshot_confirmed`` on series_a.

``adapters.capture`` is the effect. A failed acknowledgement leaves those local
rows ``RESERVED``, publishes no series_a snapshot, and performs no capture.
The local rows are not a grant. A later ``execution_acceptance.validate`` can
reject a receipt only after capture. That rejection withholds
``execution_authorized`` and leaves the earlier effects in place. A
reference-executor result whose status is ``COMMITTED`` is not an input to
this path and cannot become that flag.

Reserved-row recovery after a failed acknowledgement:

``run`` burns the challenge before it reserves the five rows. If
``snapshot_confirmed`` then fails, no capture runs. The exception handler
adds that nonce to the cancelled set and drops any export. The five local
rows stay ``RESERVED``. They are not a grant, and the series_a snapshot
stays unpublished. The supported path is to leave that nonce consumed.
Do not reset, delete, or reuse it to make those rows available again.
A second ``run`` of the same nonce raises
``OBSERVATION_CHALLENGE_CONSUMED_OR_UNKNOWN``. ``export`` raises
``OBSERVATION_EXPORT_UNAVAILABLE``. Reserving the same nonce and case
raises ``OBSERVATION_ATTEMPT_ALREADY_CONSUMED``. A new challenge is a
different nonce, leaves the five rows ``RESERVED``, and reports
``execution_authorized`` false. Receipt rejection after capture is a
different outcome: those five effects have already occurred, and
``execution_authorized`` stays false.
"""

from __future__ import annotations

import sqlite3
import sys
import types
from pathlib import Path

try:
    import fcntl  # noqa: F401
except ModuleNotFoundError:
    fcntl = types.ModuleType("fcntl")
    fcntl.LOCK_EX = 2
    fcntl.LOCK_NB = 4
    fcntl.LOCK_UN = 8
    fcntl.flock = lambda *_args, **_kwargs: None
    sys.modules["fcntl"] = fcntl

import pytest

import a11oy_state_store as state_store
import tests.test_observer_runtime as integration
from tools import execution_acceptance as acceptance


@pytest.fixture
def world(tmp_path, monkeypatch):
    # The owner fixture is wrapped by pytest and cannot be called directly.
    yield from integration.world.__wrapped__(tmp_path, monkeypatch)


def _committed_reference():
    return {
        "schema": "szl.accountable-execution-result/v1",
        "status": "COMMITTED",
        "execution_authorized": True,
    }


def local_rows(world):
    path = Path(world.service.store.path)
    if not path.is_file():
        return []
    with sqlite3.connect(path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "execution_observations" not in tables:
            return []
        return db.execute(
            "SELECT case_id,state FROM execution_observations ORDER BY case_id"
        ).fetchall()


def test_missing_plan_prevents_effects(world):
    nonce, _plan = integration.signed_plan(world)
    with pytest.raises((acceptance.EvidenceError, integration.observer.ObserverBlocked)):
        integration.run(world, nonce, {})
    assert world.effects == []
    assert integration.remote_rows(world) == []


def test_expired_plan_prevents_effects(world):
    nonce, plan = integration.signed_plan(
        world, mutate=lambda body: body.update({"expires_at": "2000-01-01T00:00:00Z"}))
    with pytest.raises(acceptance.EvidenceError, match="PLAN_EXPIRED_OR_INVALID"):
        integration.run(world, nonce, plan)
    assert world.effects == []
    assert integration.remote_rows(world) == []


def test_source_mismatch_refuses_before_capture(world):
    nonce, plan = integration.signed_plan(
        world, mutate=lambda body: body.update({"source_revision": "c" * 40}))
    with pytest.raises(acceptance.EvidenceError, match="PLAN_BINDING_MISMATCH"):
        integration.run(world, nonce, plan)
    assert world.effects == []
    assert integration.remote_rows(world) == []
    assert local_rows(world) == []


def test_operator_mismatch_refuses_before_capture(world):
    nonce, plan = integration.signed_plan(
        world, mutate=lambda body: body.update({"operator_reference": "other-operator"}))
    with pytest.raises(integration.observer.ObserverBlocked, match="OPERATOR_PLAN_BINDING_MISMATCH"):
        integration.run(world, nonce, plan)
    assert world.effects == []
    assert integration.remote_rows(world) == []
    assert local_rows(world) == []


def test_failed_acknowledgement_leaves_local_reservations_unpublished(world, monkeypatch):
    nonce, plan = integration.signed_plan(world)

    def refuse(*_args, **_kwargs):
        raise state_store.StorageBlocked("ACK_REQUIRED")

    monkeypatch.setattr(world.writer, "snapshot_confirmed", refuse)
    with pytest.raises(state_store.StorageBlocked, match="ACK_REQUIRED"):
        integration.run(world, nonce, plan)
    assert world.effects == []
    assert integration.remote_rows(world) == []
    rows = local_rows(world)
    assert [state for _case_id, state in rows] == ["RESERVED"] * 5
    assert [case_id for case_id, _state in rows] == sorted(acceptance.CONTRACTS)


def _stored_attempt(world, nonce):
    path = Path(world.service.store.path)
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            """SELECT p.source_revision, p.runtime_boot_id, p.plan_sha256, p.started_at,
                      o.case_id, o.request_sha256
               FROM execution_observations o
               JOIN execution_observation_plans p ON p.run_nonce = o.run_nonce
               WHERE o.run_nonce=? ORDER BY o.case_id LIMIT 1""",
            (nonce,),
        ).fetchone()
    return dict(row)


def test_failed_acknowledgement_retry_is_idempotent(world, monkeypatch):
    nonce, plan = integration.signed_plan(world)

    def refuse(*_args, **_kwargs):
        raise state_store.StorageBlocked("ACK_REQUIRED")

    monkeypatch.setattr(world.writer, "snapshot_confirmed", refuse)
    with pytest.raises(state_store.StorageBlocked, match="ACK_REQUIRED"):
        integration.run(world, nonce, plan)
    with pytest.raises(integration.observer.ObserverBlocked, match="CONSUMED"):
        integration.run(world, nonce, plan)
    with pytest.raises(integration.observer.ObserverBlocked, match="UNAVAILABLE"):
        integration.asyncio.run(world.subject.export(nonce, integration.HEADERS))
    assert world.effects == []
    assert integration.remote_rows(world) == []
    assert len(local_rows(world)) == 5
    stored = _stored_attempt(world, nonce)
    with pytest.raises(ValueError, match="OBSERVATION_ATTEMPT_ALREADY_CONSUMED"):
        world.service.store.reserve_execution_observation(
            source_revision=stored["source_revision"],
            runtime_boot_id=stored["runtime_boot_id"],
            run_nonce=nonce,
            plan_sha256=stored["plan_sha256"],
            case_id=stored["case_id"],
            request_sha256=stored["request_sha256"],
            receipt_id="observation-" + ("ab" * 24),
            started_at=stored["started_at"],
        )
    assert [state for _case_id, state in local_rows(world)] == ["RESERVED"] * 5


def test_new_challenge_leaves_failed_reservations_unchanged(world, monkeypatch):
    nonce, plan = integration.signed_plan(world)

    def refuse(*_args, **_kwargs):
        raise state_store.StorageBlocked("ACK_REQUIRED")

    monkeypatch.setattr(world.writer, "snapshot_confirmed", refuse)
    with pytest.raises(state_store.StorageBlocked, match="ACK_REQUIRED"):
        integration.run(world, nonce, plan)
    issued = world.subject.challenge(integration.HEADERS)
    assert issued["execution_authorized"] is False
    assert issued["challenge"]["run_nonce"] != nonce
    assert world.effects == []
    assert integration.remote_rows(world) == []
    assert [state for _case_id, state in local_rows(world)] == ["RESERVED"] * 5


def test_replayed_plan_retains_the_captured_effects(world):
    nonce, plan = integration.signed_plan(world)
    raw = integration.run(world, nonce, plan)
    result = acceptance.strict_json(raw)
    assert result["execution_authorized"] is False
    assert len(world.effects) == 5
    with pytest.raises(integration.observer.ObserverBlocked, match="CONSUMED"):
        integration.run(world, nonce, plan)
    assert len(world.effects) == 5
    assert len(integration.remote_rows(world)) == 5
    context, _manager = world.subject._identity(nonce)
    reported = acceptance.validate(result["bundle"], context)
    assert reported["execution_authorized"] is False
    assert reported["status"] == "REPORTED"


def test_rejected_receipt_leaves_the_captured_effects(world):
    nonce, plan = integration.signed_plan(world)
    raw = integration.run(world, nonce, plan)
    result = acceptance.strict_json(raw)
    bundle = result["bundle"]
    bundle["observations"][1] = bundle["observations"][0]
    context, _manager = world.subject._identity(nonce)
    assert len(bundle["observations"]) == 5
    with pytest.raises(acceptance.EvidenceError):
        acceptance.validate(bundle, context)
    assert result["execution_authorized"] is False
    assert len(world.effects) == 5
    assert len(integration.remote_rows(world)) == 5


def test_reference_committed_result_is_not_an_execution_grant(world):
    nonce, _plan = integration.signed_plan(world)
    committed = _committed_reference()
    with pytest.raises((acceptance.EvidenceError, integration.observer.ObserverBlocked)):
        integration.run(world, nonce, committed)
    assert world.effects == []
    assert integration.remote_rows(world) == []

    fresh, plan = integration.signed_plan(world)
    raw = integration.run(world, fresh, plan)
    result = acceptance.strict_json(raw)
    assert result["execution_authorized"] is False
    context, _manager = world.subject._identity(fresh)
    with pytest.raises(acceptance.EvidenceError):
        acceptance.validate(committed, context)
    reported = acceptance.validate(result["bundle"], context)
    assert reported["execution_authorized"] is False
    assert "COMMITTED" not in reported["status"]
