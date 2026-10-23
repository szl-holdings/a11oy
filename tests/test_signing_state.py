#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""SIMULATED lifecycle metadata; never a real signing qualification."""

from dataclasses import FrozenInstanceError, replace

import pytest

from szl_signing_state import SigningState, project


def sample(owner, **changes):
    facts = dict(boot_id="boot-simulated", observed_at="2026-10-22T00:00:00+00:00",
                 configured=True, key_source="persistent:SIMULATED",
                 backend_loaded=True, backend_state="LOADED_LOCAL",
                 verification_key_fingerprint="a" * 64, loaded_key_fingerprint="a" * 64,
                 expected_key_fingerprint="a" * 64)
    facts.update(changes)
    return owner.sample(**facts)


def test_positive_local_metadata_is_neither_permission_nor_capability():
    owner = SigningState(clock=lambda: 100)
    observation = sample(owner)
    state = owner.read()
    assert state["key_material_available"] is True
    assert state["backend"]["reachability"] == "NOT_APPLICABLE_LOCAL"
    assert state["permission"]["state"] == state["observed_capability"]["state"] == "UNKNOWN"
    assert state["signing_ready"] is state["execution_authorized"] is False
    assert state["non_repudiation"] == state["source_binding"] == "UNKNOWN"
    with pytest.raises(FrozenInstanceError):
        observation.generation = 500
    state["blockers"].clear()
    assert owner.read()["blockers"]


@pytest.mark.parametrize("clock", [None, True, False, "100", float("nan"),
                                   float("inf"), -1, 10 ** 400, 99])
def test_malformed_or_backward_read_clock_is_fail_closed(clock):
    owner = SigningState(clock=lambda: 100)
    observation = sample(owner)
    state = project(observation, clock)
    assert state["freshness"] == "UNKNOWN"
    assert state["key_material_available"] is False
    assert state["age_seconds"] is None


@pytest.mark.parametrize("field,value", [
    ("observed_mono", float("nan")), ("observed_mono", 10 ** 400),
    ("max_age_seconds", True), ("max_age_seconds", 0), ("max_age_seconds", 10 ** 400),
])
def test_malformed_observation_clock_never_becomes_fresh(field, value):
    owner = SigningState(clock=lambda: 100)
    invalid = replace(sample(owner), **{field: value})
    assert project(invalid, 100)["key_material_available"] is False


def test_cached_derived_json_cannot_become_observation():
    owner = SigningState(clock=lambda: 100)
    sample(owner)
    forged = {**owner.read(), "blockers": [], "signing_ready": True}
    assert project(forged, 100)["key_material_available"] is False
    assert project(forged, 100)["signing_ready"] is False


def test_exact_expiry_and_read_does_not_renew_observation():
    now = [100.0]
    owner = SigningState(clock=lambda: now[0])
    observation = sample(owner)
    now[0] = 159.999
    assert owner.read()["key_material_available"] is True
    now[0] = 160
    state = owner.read()
    assert state["freshness"] == "STALE"
    assert state["key_material_available"] is False
    assert owner._observation is observation


def test_sampler_failure_invalidates_without_renewal():
    now = [100]
    owner = SigningState(clock=lambda: now[0])
    sample(owner)
    now[0] = 101
    owner.invalidate()
    state = owner.read()
    assert state["backend"]["state"] == "UNAVAILABLE"
    assert state["key_material_available"] is False
    assert state["age_seconds"] == 1
    assert state["generation"] == 2


def test_generation_changes_for_loss_rotation_and_replica_not_refresh():
    owner = SigningState(clock=lambda: 100)
    assert sample(owner).generation == 1
    assert sample(owner).generation == 1
    assert owner.read()["observation_sequence"] == 2
    assert sample(owner, backend_loaded=False, backend_state="ABSENT").generation == 2
    assert sample(owner, loaded_key_fingerprint="b" * 64).generation == 3
    assert sample(owner, boot_id="different-boot").generation == 4


@pytest.mark.parametrize("ttl", [True, 0, -1, float("nan"), float("inf"), 10 ** 400])
def test_ttl_requires_positive_finite_number(ttl):
    with pytest.raises(ValueError):
        SigningState(max_age_seconds=ttl)


def test_observer_rejects_contradictory_facts():
    owner = SigningState(clock=lambda: 100)
    for changes in ({"backend_loaded": 1}, {"backend_state": "ABSENT"},
                    {"configured": "true"}, {"verification_key_fingerprint": "short"},
                    {"boot_id": ""}):
        with pytest.raises(ValueError):
            sample(owner, **changes)
    assert owner.read()["key_material_available"] is False
