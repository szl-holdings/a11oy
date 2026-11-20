#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed state-store release admission without provider mutations."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from tests.test_hf_configuration_handover import (
    Clock, SOURCE, baseline as stable_baseline, sample,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "szl_fenced_release_admission", ROOT / ".github/scripts/admit_hf_fenced_runtime.py"
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def good():
    clock = Clock()
    return stable_baseline(clock), sample(clock, epoch=10, boot=1)["storage"], clock.wall()


def test_clean_fenced_private_head_and_public_stores_admit_existing_writer():
    baseline, storage, now = good()
    result = guard.assess(baseline, storage, expected_live_sha=SOURCE, now=now)
    assert result["status"] == "ADMITTED"
    assert result["scope"] == "CLEAN_FENCED_WRITER_ONLY"
    assert result["source_revision"] == SOURCE
    assert result["epoch"] == storage["epoch"]
    assert result["store_count"] == 7
    assert result["signature"] == "UNSIGNED"
    assert result["deployment_authority"] is False
    assert result["provider_writes"] == 0
    assert "token" not in json.dumps(result).lower()


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(mode="SNAPSHOT_ONLY_UNFENCED"),
    lambda s: s.update(mode_reason="STATE_DATASET_NOT_PRIVATE"),
    lambda s: s.update(mode_reason="STATE_DATASET_ABSENT"),
    lambda s: s.update(mode_reason=False),
    lambda s: s.update(role="RELEASED"),
    lambda s: s.update(unfenced=True),
    lambda s: s.update(writable=False),
    lambda s: s.update(alert=True),
    lambda s: s.update(active_errors={"gdw": "unresolved"}),
    lambda s: s.update(pending_publish=["uncommitted"]),
    lambda s: s.update(last_error={"code": "snapshot"}),
    lambda s: s.update(epoch=s["epoch"]+1),
    lambda s: s.update(claim="UNCLEAN_HANDOVER"),
    lambda s: s["lease"].update(sequence=1),
    lambda s: s["lease"].update(heartbeat_age_s=31),
    lambda s: s["lease"].update(heartbeat_age_s=float("nan")),
    lambda s: s["stores"].pop("series_a"),
    lambda s: s["stores"]["gdw"].update(health="BLOCKED"),
    lambda s: s["stores"]["gdw"].update(last_snapshot_age_s=901),
    lambda s: s["stores"]["gdw"].update(unsnapshotted_change_age_s=901),
    lambda s: s["stores"]["gdw"].update(origin="LEGACY_UNVERIFIED"),
    lambda s: s["stores"]["gdw"].update(snapshot_failures=1),
    lambda s: s["stores"]["gdw"].update(sha16="bad"),
    lambda s: s["stores"]["gdw"].update(integrity="none"),
])
def test_any_missing_storage_or_lease_witness_fails_closed(mutation):
    baseline, storage, now = good()
    mutation(storage)
    with pytest.raises(guard.AdmissionHold):
        guard.assess(baseline, storage, expected_live_sha=SOURCE, now=now)


@pytest.mark.parametrize("mutation", [
    lambda b: b.update(status="HOLD"),
    lambda b: b.update(signature="SIGNED"),
    lambda b: b.update(provider_writes=1),
    lambda b: b["observation"].update(claim="UNCLEAN_HANDOVER"),
    lambda b: b["observation"].update(state="RELEASED"),
    lambda b: b["observation"].update(source_revision="e"*40),
    lambda b: b["observation"].update(epoch=0),
    lambda b: b["observation"].update(head_sha256="NOT_A_HASH"),
])
def test_private_baseline_cannot_self_authorize(mutation):
    baseline, storage, now = good()
    mutation(baseline)
    with pytest.raises(guard.AdmissionHold):
        guard.assess(baseline, storage, expected_live_sha=SOURCE, now=now)


def test_stale_baseline_fails_even_though_baseline_schema_allows_older_capture():
    baseline, storage, now = good()
    with pytest.raises(guard.AdmissionHold, match="PRIVATE_BASELINE_STALE"):
        guard.assess(baseline, storage, expected_live_sha=SOURCE, now=now+91)


@pytest.mark.parametrize("source", ["", "a"*39, "f"*40, [], True, None])
def test_live_revision_is_independent_from_private_observation(source):
    baseline, storage, now = good()
    with pytest.raises(guard.AdmissionHold):
        guard.assess(baseline, storage, expected_live_sha=source, now=now)


def test_cli_staged_receipt_writes_only_after_verified_input(tmp_path, monkeypatch):
    baseline, storage, now = good()
    fixture = tmp_path / "private-head.json"
    receipt = tmp_path / "admission.json"
    output = tmp_path / "output"
    fixture.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(guard.time, "time", lambda: now)
    monkeypatch.setattr(guard, "read_public_status", lambda origin: copy.deepcopy(storage))
    monkeypatch.setattr(guard, "verify_v2_control_plane_setting", lambda: None)
    argv = [
        "--origin", guard.handover.ORIGIN, "--expected-live-sha", SOURCE,
        "--baseline", str(fixture), "--output", str(receipt),
        "--github-output", str(output),
    ]
    assert guard.main(argv) == 0
    assert output.read_text(encoding="utf-8") == "open=true\n"
    assert json.loads(receipt.read_text(encoding="utf-8"))["provider_writes"] == 0

    receipt.unlink()
    output.unlink()
    bad = copy.deepcopy(baseline)
    bad["observation"]["claim"] = "UNCLEAN_HANDOVER"
    fixture.write_text(json.dumps(bad), encoding="utf-8")
    assert guard.main(argv) == 2
    assert not output.exists() and not receipt.exists()


def test_wrong_canonical_origin_fails_without_egress(monkeypatch, tmp_path):
    baseline, _storage, now = good()
    fixture = tmp_path / "baseline.json"
    fixture.write_text(json.dumps(baseline))
    monkeypatch.setattr(guard.time, "time", lambda: now)
    monkeypatch.setattr(
        guard, "read_public_status",
        lambda _origin: pytest.fail("must fail before a network read"),
    )
    assert guard.main([
        "--origin", "https://example.com", "--expected-live-sha", SOURCE,
        "--baseline", str(fixture), "--output", str(tmp_path/"receipt"),
        "--github-output", str(tmp_path/"gh-out"),
    ]) == 2
    assert not (tmp_path/"gh-out").exists()


def test_operator_control_plane_must_have_v2_variable(monkeypatch):
    from types import SimpleNamespace

    class FakeApi:
        def __init__(self, value):
            self.value = value

        def get_space_variables(self, repo):
            assert repo == "SZLHOLDINGS/a11oy"
            return {"A11OY_STATE_STORE": SimpleNamespace(value=self.value)}

    for value in ("v1", "off", "", None):
        monkeypatch.setattr(guard.relock, "HfApi", lambda value=value: FakeApi(value))
        with pytest.raises(guard.AdmissionHold, match="V2_RUNTIME_VARIABLE_UNAVAILABLE"):
            guard.verify_v2_control_plane_setting()

    monkeypatch.setattr(guard.relock, "HfApi", lambda: FakeApi("v2"))
    assert guard.verify_v2_control_plane_setting() is None
