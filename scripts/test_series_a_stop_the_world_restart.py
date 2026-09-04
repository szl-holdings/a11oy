from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest


if "huggingface_hub" not in sys.modules:
    hub_stub = types.ModuleType("huggingface_hub")
    hub_stub.HfApi = object
    sys.modules["huggingface_hub"] = hub_stub

SCRIPT = pathlib.Path(__file__).with_name("prove_hf_series_a_restart.py")
SPEC = importlib.util.spec_from_file_location(
    "prove_hf_series_a_restart_stop_world",
    SCRIPT,
)
assert SPEC and SPEC.loader
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


def stage(value: str, *, nested: bool = False):
    runtime = SimpleNamespace(stage=SimpleNamespace(value=value))
    return SimpleNamespace(runtime=runtime) if nested else runtime


class SerialApi:
    def __init__(
        self,
        *,
        pause_response: str = "PAUSING",
        observed_stages: tuple[str, ...] = ("PAUSED",),
        restart_response: str = "RESTARTING",
    ) -> None:
        self.pause_response = pause_response
        self.observed_stages = list(observed_stages)
        self.restart_response = restart_response
        self.calls: list[tuple[str, dict]] = []

    def pause_space(self, **kwargs):
        self.calls.append(("pause", kwargs))
        return stage(self.pause_response)

    def get_space_runtime(self, **kwargs):
        self.calls.append(("runtime", kwargs))
        value = self.observed_stages.pop(0) if self.observed_stages else "PAUSED"
        return stage(value)

    def restart_space(self, **kwargs):
        self.calls.append(("restart", kwargs))
        return stage(self.restart_response, nested=True)


def test_stop_world_orders_pause_confirmation_before_restart(monkeypatch) -> None:
    api = SerialApi(observed_stages=("PAUSING", "PAUSED"))
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    evidence = {}

    result = proof.stop_the_world_restart(
        api,
        repo_id="SZLHOLDINGS/a11oy",
        deadline=proof.time.monotonic() + 30,
        attempts=3,
        retry_seconds=0,
        phase="durability",
        evidence=evidence,
    )

    assert [name for name, _ in api.calls] == [
        "pause",
        "runtime",
        "runtime",
        "restart",
    ]
    assert result["pause_confirmed"] is True
    assert result["writer_overlap_prevented"] is True
    assert result["confirmed_pause_stage"] == "PAUSED"
    assert result["restart_response_stage"] == "RESTARTING"
    assert evidence["durability_restart_control"] is result


def test_direct_paused_response_needs_no_runtime_poll(monkeypatch) -> None:
    api = SerialApi(pause_response="PAUSED")
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    result = proof.stop_the_world_restart(
        api,
        repo_id="SZLHOLDINGS/a11oy",
        deadline=proof.time.monotonic() + 30,
        attempts=2,
        retry_seconds=0,
        phase="activation",
    )

    assert [name for name, _ in api.calls] == ["pause", "restart"]
    assert result["pause_response_stage"] == "PAUSED"
    assert result["pause_observations"] == []


def test_restart_is_never_requested_before_paused_is_confirmed(monkeypatch) -> None:
    api = SerialApi(observed_stages=("RUNNING", "PAUSING"))
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        proof.RestartProofError,
        match="did not reach PAUSED before replacement request",
    ):
        proof.stop_the_world_restart(
            api,
            repo_id="SZLHOLDINGS/a11oy",
            deadline=proof.time.monotonic() + 30,
            attempts=2,
            retry_seconds=0,
            phase="durability",
        )

    assert [name for name, _ in api.calls] == ["pause", "runtime", "runtime"]
    assert all(name != "restart" for name, _ in api.calls)


class LostRestartApi(SerialApi):
    def __init__(self, recovery_stage: str) -> None:
        super().__init__(pause_response="PAUSED")
        self.recovery_stage = recovery_stage
        self.restart_attempts = 0

    def get_space_runtime(self, **kwargs):
        self.calls.append(("runtime", kwargs))
        return stage(self.recovery_stage)

    def restart_space(self, **kwargs):
        self.calls.append(("restart", kwargs))
        self.restart_attempts += 1
        if self.restart_attempts == 1:
            raise TimeoutError("provider response lost")
        return stage("RESTARTING", nested=True)


def test_lost_restart_response_retries_only_when_still_paused(monkeypatch) -> None:
    api = LostRestartApi("PAUSED")
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    result = proof.stop_the_world_restart(
        api,
        repo_id="SZLHOLDINGS/a11oy",
        deadline=proof.time.monotonic() + 30,
        attempts=2,
        retry_seconds=0,
        phase="activation",
    )

    assert [name for name, _ in api.calls] == [
        "pause",
        "restart",
        "runtime",
        "restart",
    ]
    assert result["restart_response_lost"] is True
    assert result["restart_retry_requested"] is True
    assert result["restart_response_stage"] == "RESTARTING"


def test_lost_restart_response_does_not_duplicate_an_accepted_restart(
    monkeypatch,
) -> None:
    api = LostRestartApi("STARTING")
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    result = proof.stop_the_world_restart(
        api,
        repo_id="SZLHOLDINGS/a11oy",
        deadline=proof.time.monotonic() + 30,
        attempts=2,
        retry_seconds=0,
        phase="activation",
    )

    assert [name for name, _ in api.calls] == ["pause", "restart", "runtime"]
    assert result["restart_response_lost"] is True
    assert result["restart_retry_requested"] is False
    assert result["restart_response_stage"] == "STARTING"
    assert api.restart_attempts == 1


def test_runtime_stage_supports_mapping_enum_and_nested_shapes() -> None:
    assert proof._runtime_stage({"stage": "paused"}) == "PAUSED"
    assert proof._runtime_stage({"runtime": {"stage": "running"}}) == "RUNNING"
    assert proof._runtime_stage(stage("restarting", nested=True)) == "RESTARTING"
