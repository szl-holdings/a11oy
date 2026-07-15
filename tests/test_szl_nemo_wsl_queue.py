# SPDX-License-Identifier: Apache-2.0
"""Focused offline tests for the durable SZL-Nemo WSL queue."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "model_release" / "szl-nemo" / "szl_nemo_wsl_queue.py"
SPEC = importlib.util.spec_from_file_location("szl_nemo_wsl_queue", QUEUE_PATH)
assert SPEC and SPEC.loader
queue = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = queue
SPEC.loader.exec_module(queue)
CONTRACT = json.loads(queue.CONTRACT_PATH.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _stage_result(stage, attempt_dir, receipt_path, receipt, exit_code=0):
    stdout = attempt_dir / f"{stage}.stdout.log"
    stderr = attempt_dir / f"{stage}.stderr.log"
    stdout.write_text("fixture\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    if receipt_path is not None and receipt is not None:
        _write(receipt_path, receipt)
    return queue.StageResult(stage, exit_code, stdout, stderr, receipt_path, receipt)


def _preflight(state="PASS"):
    checks = [{"id": "GPU_ADMISSION", "state": state}]
    return {
        "schema_version": "szl.nemo.preflight-receipt.v1",
        "state": "PASS" if state == "PASS" else "BLOCKED",
        "checks": checks,
    }


def _capacity():
    return {
        "schema_version": "szl.nemo.capacity-probe-receipt.v1",
        "state": queue.CAPACITY_PASS,
        "training_started": False,
        "effects": {
            "capacity_optimization_step_completed": True,
            "adapter_written": False,
        },
    }


def _config(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    return queue.QueueConfig(
        base_snapshot=base,
        output_root=tmp_path / "runs",
        state_root=tmp_path / "state",
        confirmation=CONTRACT["training"]["confirmation_phrase"],
        license_acknowledgement=CONTRACT["base"]["license_acknowledgement"],
        max_attempts=3,
        retry_seconds=30,
    )


def _passing_executor(calls):
    def execute(stage, command, attempt_dir, receipt_path, _config):
        calls.append((stage, list(command)))
        if stage == "preflight":
            return _stage_result(stage, attempt_dir, receipt_path, _preflight())
        if stage == "capacity":
            return _stage_result(stage, attempt_dir, receipt_path, _capacity())
        output = Path(command[command.index("--output-dir") + 1])
        receipts = output / "receipts"
        _write(receipts / "reload-evaluation-receipt.json", {"state": "PASS"})
        _write(receipts / "candidate-summary.dsse.json", {"promotion": "NOT_PROMOTED"})
        _write(receipts / "adapter-files.json", {"files": [{"path": "adapter/adapter_model.safetensors"}]})
        training = {
            "schema_version": "szl.nemo.training-receipt.v1",
            "state": queue.CANDIDATE_PASS,
            "promotion": "NOT_PROMOTED",
            "training_started_at_unix_ns": 1,
        }
        return _stage_result(stage, attempt_dir, receipt_path, training)
    return execute


def test_native_windows_is_non_retryable_before_queue_creation(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Windows")
    config = _config(tmp_path)
    with pytest.raises(queue.QueueRefused, match="native Windows"):
        queue.run_queue(config, executor=lambda *_args: pytest.fail("must not execute"))
    assert not config.state_root.exists()


def test_exact_acknowledgements_are_required_before_queue_creation(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    config = _config(tmp_path)
    bad = queue.QueueConfig(**{**config.__dict__, "confirmation": "WRONG"})
    with pytest.raises(queue.QueueRefused, match="exact training confirmation"):
        queue.run_queue(bad, executor=lambda *_args: pytest.fail("must not execute"))
    assert not config.state_root.exists()


def test_queue_runs_preflight_capacity_train_and_keeps_release_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    calls = []
    code, queue_dir = queue.run_queue(
        _config(tmp_path), executor=_passing_executor(calls), sleep=lambda _seconds: None,
        queue_id="fixture-passing",
    )

    assert code == 0
    assert [stage for stage, _command in calls] == ["preflight", "capacity", "training"]
    assert all("fetch-base" not in command and "setup_wsl_runtime.sh" not in command for _, command in calls)
    state = json.loads((queue_dir / "state.json").read_text(encoding="utf-8"))
    assert state["state"] == queue.CANDIDATE_PASS
    assert state["effects"] == {
        "training_started": True,
        "uploaded": False,
        "published": False,
        "deployed": False,
        "promoted": False,
    }
    events = [json.loads(line) for line in (queue_dir / "events.jsonl").read_text().splitlines()]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert all(event["effects"]["published"] is False for event in events)
    stage_receipt = (queue_dir / "attempts" / "001" / "queue-stage-training.json").read_text()
    assert CONTRACT["training"]["confirmation_phrase"] not in stage_receipt
    assert CONTRACT["base"]["license_acknowledgement"] not in stage_receipt
    assert "<ACKNOWLEDGEMENT_REDACTED>" in stage_receipt


def test_pure_gpu_refusal_is_bounded_and_retries_from_preflight(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    passing = _passing_executor([])
    calls = []

    def execute(stage, command, attempt_dir, receipt_path, config):
        calls.append(stage)
        if len(calls) == 1:
            return _stage_result(stage, attempt_dir, receipt_path, _preflight("BLOCKED"), 3)
        return passing(stage, command, attempt_dir, receipt_path, config)

    code, queue_dir = queue.run_queue(
        _config(tmp_path), executor=execute, sleep=lambda _seconds: None,
        queue_id="fixture-retry",
    )
    assert code == 0
    assert calls == ["preflight", "preflight", "capacity", "training"]
    assert (queue_dir / "attempts" / "001" / "attempt-receipt.json").is_file()
    assert (queue_dir / "attempts" / "002" / "attempt-receipt.json").is_file()


def test_gpu_refusal_exhausts_at_exact_bound_without_capacity_or_training(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    calls = []

    def execute(stage, _command, attempt_dir, receipt_path, _config):
        calls.append(stage)
        return _stage_result(stage, attempt_dir, receipt_path, _preflight("BLOCKED"), 3)

    config = _config(tmp_path)
    config = queue.QueueConfig(**{**config.__dict__, "max_attempts": 2})
    code, queue_dir = queue.run_queue(
        config, executor=execute, sleep=lambda _seconds: None,
        queue_id="fixture-exhausted",
    )
    assert code == 3
    assert calls == ["preflight", "preflight"]
    assert json.loads((queue_dir / "state.json").read_text())["state"] == "EXHAUSTED_NOT_TRAINED"


def test_non_gpu_preflight_refusal_is_never_retried(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    calls = []

    def execute(stage, _command, attempt_dir, receipt_path, _config):
        calls.append(stage)
        receipt = {
            "schema_version": "szl.nemo.preflight-receipt.v1",
            "state": "BLOCKED",
            "checks": [{"id": "LINUX_MAMBA_EXECUTION_LANE", "state": "BLOCKED"}],
        }
        return _stage_result(stage, attempt_dir, receipt_path, receipt, 3)

    code, queue_dir = queue.run_queue(
        _config(tmp_path), executor=execute, sleep=lambda _seconds: None,
        queue_id="fixture-runtime-refusal",
    )
    assert code == 4
    assert calls == ["preflight"]
    assert json.loads((queue_dir / "state.json").read_text())["state"] == "BLOCKED_OPERATOR_REVIEW"


def test_capacity_failure_is_terminal_and_never_invokes_training(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    calls = []

    def execute(stage, command, attempt_dir, receipt_path, _config):
        calls.append(stage)
        if stage == "preflight":
            return _stage_result(stage, attempt_dir, receipt_path, _preflight())
        failed = {
            "schema_version": "szl.nemo.capacity-probe-receipt.v1",
            "state": "FAILED_NOT_TRAINED_NOT_PROMOTED",
            "effects": {"capacity_optimization_step_started": True},
        }
        return _stage_result(stage, attempt_dir, receipt_path, failed, 3)

    code, queue_dir = queue.run_queue(
        _config(tmp_path), executor=execute, sleep=lambda _seconds: None,
        queue_id="fixture-capacity-fail",
    )
    assert code == 5
    assert calls == ["preflight", "capacity"]
    assert json.loads((queue_dir / "state.json").read_text())["state"] == "BLOCKED_OPERATOR_REVIEW"


def test_capacity_launcher_preflight_gpu_refusal_is_retryable(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    passing = _passing_executor([])
    calls = []
    capacity_calls = 0

    def execute(stage, command, attempt_dir, receipt_path, config):
        nonlocal capacity_calls
        calls.append(stage)
        if stage == "capacity":
            capacity_calls += 1
            if capacity_calls == 1:
                companion = attempt_dir / "capacity-preflight-receipt.json"
                _write(companion, _preflight("BLOCKED"))
                return _stage_result(stage, attempt_dir, receipt_path, None, 3)
        return passing(stage, command, attempt_dir, receipt_path, config)

    code, queue_dir = queue.run_queue(
        _config(tmp_path), executor=execute, sleep=lambda _seconds: None,
        queue_id="fixture-capacity-recheck",
    )
    assert code == 0
    assert calls == ["preflight", "capacity", "preflight", "capacity", "training"]
    stage = json.loads(
        (queue_dir / "attempts" / "001" / "queue-stage-capacity.json").read_text()
    )
    assert stage["runner_receipt"] is None
    assert stage["companion_receipts"][0]["path"].endswith("capacity-preflight-receipt.json")


def test_training_failure_is_never_retried(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    calls = []

    def execute(stage, command, attempt_dir, receipt_path, config):
        if stage != "training":
            return _passing_executor(calls)(stage, command, attempt_dir, receipt_path, config)
        calls.append((stage, list(command)))
        failed = {
            "schema_version": "szl.nemo.training-receipt.v1",
            "state": "FAILED_NOT_PROMOTED",
            "promotion": "NOT_PROMOTED",
            "training_started_at_unix_ns": 1,
        }
        return _stage_result(stage, attempt_dir, receipt_path, failed, 3)

    code, queue_dir = queue.run_queue(
        _config(tmp_path), executor=execute, sleep=lambda _seconds: None,
        queue_id="fixture-training-fail",
    )
    assert code == 6
    assert [stage for stage, _command in calls] == ["preflight", "capacity", "training"]
    assert json.loads((queue_dir / "state.json").read_text())["state"] == "TRAINING_TERMINAL_OPERATOR_REVIEW"


def test_contract_and_launcher_expose_the_governed_queue_boundary():
    contract = json.loads(queue.CONTRACT_PATH.read_text(encoding="utf-8"))
    launcher = queue.LAUNCHER_PATH.read_text(encoding="utf-8")
    assert contract["gpu_admission"]["thresholds_may_be_weakened"] is False
    assert contract["gpu_admission"]["processes_may_be_stopped_automatically"] is False
    assert contract["promotion"]["automatic"] is False
    assert "--preflight-receipt" in launcher
    assert "unshare --user --map-root-user --net" in launcher
    runner = (queue.HERE / "szl_nemo_finetune.py").read_text(encoding="utf-8")
    assert "with training_mutex(), fresh_hf_modules_cache()" in runner
    for key, value in queue.OFFLINE_ENVIRONMENT.items():
        assert f"{key}={value}" in launcher or f"{key}='{value}'" in launcher
