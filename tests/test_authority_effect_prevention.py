#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline integration: bad evidence does not admit an A11oy effect.

The existing owner is ``ObserverRuntime.run`` together with
``StateStore.snapshot_confirmed``. This module drives that path through the
synthetic adapter harness in ``tests.test_observer_runtime``. It does not add
an authorizer.

Order inside ``run``, before ``adapters.capture``:

1. ``_caller`` admits the operator principal and tenant.
2. ``execution_acceptance.validate_plan`` checks the signed plan.
3. The plan operator reference must match the challenge binding.
4. ``_acknowledge`` calls ``StateStore.snapshot_confirmed`` on series_a.

``adapters.capture`` is the effect. A later ``execution_acceptance.validate``
checks the observation receipts and still returns ``execution_authorized``
false. A reference-executor result whose status is ``COMMITTED`` is not an
input to this path and cannot become that flag.
"""

from __future__ import annotations

import sys
import types

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


def test_mismatched_source_and_operator_prevent_effects(world):
    nonce, plan = integration.signed_plan(
        world, mutate=lambda body: body.update({
            "source_revision": "c" * 40,
            "operator_reference": "other-operator",
        }))
    with pytest.raises((acceptance.EvidenceError, integration.observer.ObserverBlocked)):
        integration.run(world, nonce, plan)
    assert world.effects == []
    assert integration.remote_rows(world) == []


def test_missing_v2_acknowledgement_prevents_effects(world, monkeypatch):
    nonce, plan = integration.signed_plan(world)

    def refuse(*_args, **_kwargs):
        raise state_store.StorageBlocked("ACK_REQUIRED")

    monkeypatch.setattr(world.writer, "snapshot_confirmed", refuse)
    with pytest.raises(state_store.StorageBlocked, match="ACK_REQUIRED"):
        integration.run(world, nonce, plan)
    assert world.effects == []


def test_replayed_plan_adds_no_effect(world):
    nonce, plan = integration.signed_plan(world)
    raw = integration.run(world, nonce, plan)
    result = acceptance.strict_json(raw)
    assert result["execution_authorized"] is False
    assert len(world.effects) == 5
    with pytest.raises(integration.observer.ObserverBlocked, match="CONSUMED"):
        integration.run(world, nonce, plan)
    assert len(world.effects) == 5
    context, _manager = world.subject._identity(nonce)
    reported = acceptance.validate(result["bundle"], context)
    assert reported["execution_authorized"] is False
    assert reported["status"] == "REPORTED"


def test_replayed_receipt_does_not_grant_execution(world):
    nonce, plan = integration.signed_plan(world)
    raw = integration.run(world, nonce, plan)
    result = acceptance.strict_json(raw)
    bundle = result["bundle"]
    bundle["observations"][1] = bundle["observations"][0]
    context, _manager = world.subject._identity(nonce)
    with pytest.raises(acceptance.EvidenceError):
        acceptance.validate(bundle, context)
    assert result["execution_authorized"] is False
    assert len(world.effects) == 5


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
