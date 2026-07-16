# SPDX-License-Identifier: Apache-2.0
"""Focused offline tests for the durable SZL-Nemo WSL queue."""

from __future__ import annotations

import importlib.util
import base64
import hashlib
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
DSSE_IDENTITY = {
    "path": CONTRACT["dsse"]["verifier_path"],
    "sha256": CONTRACT["dsse"]["verifier_sha256"],
    "key_id": CONTRACT["dsse"]["key_id"],
    "public_key_fingerprint_sha256": CONTRACT["dsse"][
        "public_key_fingerprint_sha256"
    ],
}


@pytest.fixture(autouse=True)
def _verify_fixture_signature(monkeypatch):
    def verify(envelope):
        return {
            "verified": True,
            "pae_sha256": envelope["_pae_sha256"],
            "payloadType": queue.PAYLOAD_TYPE,
            "keyid_expected": DSSE_IDENTITY["key_id"],
            "pub_fingerprint_sha256": DSSE_IDENTITY[
                "public_key_fingerprint_sha256"
            ],
            "signatures": [{"keyid": queue.DSSE_KEY_ID, "verified": True}],
        }

    monkeypatch.setattr(queue, "_verify_candidate_signature", verify)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_signed_candidate(path: Path, summary: dict) -> None:
    body = queue._canonical_json(summary).encode("utf-8")
    payload_type = queue.PAYLOAD_TYPE.encode("utf-8")
    pae = (
        b"DSSEv1 "
        + str(len(payload_type)).encode("ascii")
        + b" "
        + payload_type
        + b" "
        + str(len(body)).encode("ascii")
        + b" "
        + body
    )
    pae_sha = hashlib.sha256(pae).hexdigest()
    _write(
        path,
        {
            "envelope": {
                "payloadType": queue.PAYLOAD_TYPE,
                "payload": base64.b64encode(body).decode("ascii"),
                "_dsse": "DSSEv1",
                "_pae_sha256": pae_sha,
                "signatures": [
                    {
                        "keyid": queue.DSSE_KEY_ID,
                        "sig": base64.b64encode(b"fixture-signature").decode("ascii"),
                    }
                ],
                "signed": True,
            },
            "verification": {
                "verified": True,
                "pae_sha256": pae_sha,
                "payloadType": queue.PAYLOAD_TYPE,
                "keyid_expected": DSSE_IDENTITY["key_id"],
                "pub_fingerprint_sha256": DSSE_IDENTITY[
                    "public_key_fingerprint_sha256"
                ],
            },
            "promotion_eligible_signature": True,
        },
    )


def _read_candidate_summary(path: Path) -> dict:
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    return json.loads(base64.b64decode(wrapper["envelope"]["payload"]))


def _stage_result(stage, attempt_dir, receipt_path, receipt, exit_code=0):
    stdout = attempt_dir / f"{stage}.stdout.log"
    stderr = attempt_dir / f"{stage}.stderr.log"
    stdout.write_text("fixture\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    if receipt_path is not None and receipt is not None:
        _write(receipt_path, receipt)
    return queue.StageResult(stage, exit_code, stdout, stderr, receipt_path, receipt)


def _preflight(state="PASS"):
    policy = CONTRACT["gpu_admission"]
    sample = {
        "gpu_name": CONTRACT["runtime"]["required_device_name"],
        "memory_free_mib": policy["minimum_free_memory_mib"],
        "utilization_pct": policy["maximum_utilization_pct"],
        "temperature_c": policy["maximum_temperature_c"],
    }
    checks = [
        {
            "id": "GPU_ADMISSION",
            "state": state,
            "policy": policy,
            "samples": [dict(sample) for _ in range(policy["probe_samples"])],
        }
    ]
    return {
        "schema_version": "szl.nemo.preflight-receipt.v1",
        "state": "PASS" if state == "PASS" else "BLOCKED",
        "checks": checks,
    }


def _runtime_guard():
    device = CONTRACT["runtime"]["required_device_name"]
    thresholds = {
        "maximum_training_temperature_c": CONTRACT["gpu_admission"][
            "maximum_training_temperature_c"
        ],
        "maximum_wall_clock_seconds": CONTRACT["training"][
            "maximum_wall_clock_seconds"
        ],
        "watchdog_interval_seconds": CONTRACT["training"][
            "watchdog_interval_seconds"
        ],
    }

    def sample(stage, measured_at):
        return {
            "stage": stage,
            "measured_at_unix_ns": measured_at,
            "gpu_name": device,
            "memory_total_mib": 8192,
            "memory_used_mib": 4096,
            "memory_free_mib": 4096,
            "utilization_pct": 50,
            "temperature_c": 55,
        }

    return {
        "schema_version": "szl.nemo.runtime-guard.v1",
        "state": "PASS",
        "reason": None,
        "thresholds": thresholds,
        "timing": {
            "started_at_unix_ns": 10,
            "finalized_at_unix_ns": 20,
            "elapsed_monotonic_ms": 1,
        },
        "samples": [sample("initial", 11), sample("final", 19)],
        "cooperative_interrupt_only": True,
    }


def _capacity():
    return {
        "schema_version": "szl.nemo.capacity-probe-receipt.v1",
        "state": queue.CAPACITY_PASS,
        "training_started": False,
        "profile_id": CONTRACT["training"]["capacity_profile_id"],
        "contract_sha256": queue._sha256_file(queue.CONTRACT_PATH),
        "runner_sha256": queue._sha256_file(queue.HERE / "szl_nemo_finetune.py"),
        "effects": {
            "capacity_optimization_step_completed": True,
            "adapter_written": False,
            "uploaded": False,
            "published": False,
            "deployed": False,
            "promoted": False,
            "training_authorized": False,
            "queue_progression_allowed": True,
            "canonical_threshold_changed": False,
        },
        "probe": {
            "profile_id": CONTRACT["training"]["capacity_profile_id"],
            "optimizer": CONTRACT["training"]["optimizer"],
            "optimizer_class": "PagedAdamW8bit",
            "gradient_accumulation_micro_steps": CONTRACT["training"]["gradient_accumulation_steps"],
            "sequence_limit": CONTRACT["training"]["capacity_probe_sequence_length"],
            "sequence_tokens": CONTRACT["training"]["capacity_probe_sequence_length"],
            "device_map": {"": 0},
        },
        "runtime_guard": _runtime_guard(),
    }


def _passing_training_output(output: Path) -> dict:
    adapter = output / "adapter"
    adapter.mkdir(parents=True, exist_ok=True)
    (adapter / "adapter_model.safetensors").write_bytes(b"safetensors-fixture")
    (adapter / "adapter_config.json").write_text('{"peft_type":"LORA"}\n', encoding="utf-8")
    files = []
    for path in sorted(adapter.iterdir()):
        files.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": queue._sha256_file(path),
            }
        )
    receipts = output / "receipts"
    adapter_receipt = receipts / "adapter-files.json"
    _write(
        adapter_receipt,
        {"schema_version": "szl.nemo.adapter-files.v1", "files": files},
    )
    adapter_sha = queue._sha256_file(adapter_receipt)
    eval_rows = [
        json.loads(line)
        for line in queue.EVAL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reload_receipt = receipts / "reload-evaluation-receipt.json"
    _write(
        reload_receipt,
        {
            "schema_version": "szl.nemo.reload-evaluation-receipt.v1",
            "state": "PASS",
            "rows": len(eval_rows),
            "passes": len(eval_rows),
            "adapter_files_sha256": adapter_sha,
            "base_revision": CONTRACT["base"]["revision"],
            "eval_sha256": queue._sha256_file(queue.EVAL_PATH),
            "results": [
                {"record_id": row["record_id"], "state": "PASS"}
                for row in eval_rows
            ],
            "promotion": "NONE_AUTOMATIC",
        },
    )
    reload_sha = queue._sha256_file(reload_receipt)
    runtime_guard = _runtime_guard()
    source_control = {"commit": "a" * 40, "tree": "b" * 40, "clean": True}
    base_files = [{"path": "config.json", "bytes": 1, "sha256": "c" * 64}]
    curriculum_inputs = {"manifest_sha256": "d" * 64, "rows": 12}
    runtime_identity = {"python": "3.12", "torch": "2.10.0+cu128"}
    loaded_model_class = {
        "phase": "training",
        "class": "fixture.NemotronHForCausalLM",
        "source_sha256": "e" * 64,
    }
    reloaded_model_class = {
        "phase": "reload",
        "class": "fixture.NemotronHForCausalLM",
        "source_sha256": "e" * 64,
    }
    training = {
        "schema_version": "szl.nemo.training-receipt.v1",
        "state": queue.CANDIDATE_PASS,
        "promotion": "NOT_PROMOTED",
        "training_started_at_unix_ns": 1,
        "training_completed_at_unix_ns": 2,
        "completed_at_unix_ns": 3,
        "global_steps": CONTRACT["training"]["max_steps"],
        "training_loss": 0.25,
        "peak_vram_reserved_bytes": 1024,
        "contract_sha256": queue._sha256_file(queue.CONTRACT_PATH),
        "runner_sha256": queue._sha256_file(queue.HERE / "szl_nemo_finetune.py"),
        "curriculum_manifest_sha256": queue._sha256_file(
            queue.HERE / "generated" / "curriculum-manifest.json"
        ),
        "runtime_identity": runtime_identity,
        "dsse_verifier": DSSE_IDENTITY,
        "loaded_model_class": loaded_model_class,
        "reloaded_model_class": reloaded_model_class,
        "source_control": source_control,
        "source_control_after": source_control,
        "base_files_before": base_files,
        "base_files_after": base_files,
        "curriculum_inputs_before": curriculum_inputs,
        "curriculum_inputs_after": curriculum_inputs,
        "adapter_files_sha256": adapter_sha,
        "reload_evaluation_receipt_sha256": reload_sha,
        "organization_signature_verified": True,
        "runtime_guard": runtime_guard,
    }
    training_evidence = {
        "schema_version": "szl.nemo.training-evidence.v1",
        "contract_id": CONTRACT["contract_id"],
        "candidate_id": CONTRACT["candidate_id"],
        "base_revision": CONTRACT["base"]["revision"],
        "contract_sha256": training["contract_sha256"],
        "runner_sha256": training["runner_sha256"],
        "curriculum_manifest_sha256": training["curriculum_manifest_sha256"],
        "dsse_verifier": DSSE_IDENTITY,
        "runtime_identity": runtime_identity,
        "model_code": {
            "loaded_model_class": loaded_model_class,
            "reloaded_model_class": reloaded_model_class,
        },
        "runtime_guard": runtime_guard,
        "source_control": {"before": source_control, "after": source_control},
        "base_files": {"before": base_files, "after": base_files},
        "curriculum_inputs": {
            "before": curriculum_inputs,
            "after": curriculum_inputs,
        },
        "step_evidence": {
            "training_started_at_unix_ns": 1,
            "training_completed_at_unix_ns": 2,
            "expected_global_steps": CONTRACT["training"]["max_steps"],
            "observed_global_steps": CONTRACT["training"]["max_steps"],
            "training_loss": 0.25,
            "peak_vram_reserved_bytes": 1024,
        },
        "artifact_evidence": {
            "adapter_files_receipt_sha256": adapter_sha,
            "reload_evaluation_receipt_sha256": reload_sha,
            "held_out_eval_sha256": queue._sha256_file(queue.EVAL_PATH),
        },
        "promotion": "NOT_PROMOTED",
    }
    training_evidence_path = receipts / "training-evidence.json"
    _write(training_evidence_path, training_evidence)
    training_evidence_sha = queue._sha256_file(training_evidence_path)
    summary = {
        "schema_version": "szl.nemo.candidate-summary.v1",
        "contract_id": CONTRACT["contract_id"],
        "base_revision": CONTRACT["base"]["revision"],
        "adapter_files_receipt_sha256": adapter_sha,
        "reload_evaluation_receipt_sha256": reload_sha,
        "training_evidence_sha256": training_evidence_sha,
        "dsse_verifier": DSSE_IDENTITY,
        "evaluation_state": "PASS",
        "runtime_guard": runtime_guard,
        "promotion": "NOT_PROMOTED",
    }
    candidate = receipts / "candidate-summary.dsse.json"
    _write_signed_candidate(candidate, summary)
    training["training_evidence_sha256"] = training_evidence_sha
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate)
    return training


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
        training = _passing_training_output(output)
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
        "training_started": queue.TRAINING_START_PROVEN_TRUE,
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


def test_training_invocation_is_unknown_while_live_and_after_receiptless_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.platform, "system", lambda: "Linux")
    config = _config(tmp_path)
    queue_id = "fixture-training-crash"
    passing = _passing_executor([])
    live_effects = []

    def execute(stage, command, attempt_dir, receipt_path, observed_config):
        if stage != "training":
            return passing(stage, command, attempt_dir, receipt_path, observed_config)
        live_state = json.loads(
            (config.state_root / queue_id / "state.json").read_text(encoding="utf-8")
        )
        live_effects.append(live_state["effects"]["training_started"])
        return _stage_result(stage, attempt_dir, receipt_path, None, 137)

    code, queue_dir = queue.run_queue(
        config,
        executor=execute,
        sleep=lambda _seconds: None,
        queue_id=queue_id,
    )

    assert code == 6
    assert live_effects == [queue.TRAINING_START_UNKNOWN]
    final_state = json.loads((queue_dir / "state.json").read_text(encoding="utf-8"))
    assert final_state["effects"]["training_started"] == queue.TRAINING_START_UNKNOWN
    attempt = json.loads(
        (queue_dir / "attempts" / "001" / "attempt-receipt.json").read_text(encoding="utf-8")
    )
    assert attempt["training_started"] == queue.TRAINING_START_UNKNOWN


def test_capacity_refuses_a_tripped_runtime_guard(tmp_path):
    receipt = _capacity()
    receipt["runtime_guard"] = {"state": "TRIPPED", "reason": "thermal ceiling"}
    result = _stage_result("capacity", tmp_path, tmp_path / "capacity.json", receipt)
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"


def test_low_vram_calibration_can_never_satisfy_queue_capacity(tmp_path):
    receipt = {
        "schema_version": "szl.nemo.low-vram-calibration-receipt.v1",
        "state": "PASS_CALIBRATION_ONLY_NOT_TRAINED_NOT_QUALIFIED_NOT_PROMOTED",
        "effects": {
            "capacity_optimization_step_completed": True,
            "training_authorized": False,
        },
        "runtime_guard": {
            "state": "PASS",
            "samples": [{"stage": "initial"}, {"stage": "final"}],
        },
    }
    result = _stage_result("capacity", tmp_path, tmp_path / "calibration.json", receipt)
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"


def test_stale_capacity_receipt_cannot_authorize_training(tmp_path):
    stale = _capacity()
    stale.pop("profile_id")
    stale["probe"].pop("optimizer_class")
    result = _stage_result("capacity", tmp_path, tmp_path / "stale-capacity.json", stale)
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"


def test_short_sequence_capacity_receipt_cannot_authorize_training(tmp_path):
    short = _capacity()
    short["probe"]["sequence_tokens"] = 128
    result = _stage_result("capacity", tmp_path, tmp_path / "short-capacity.json", short)
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"


@pytest.mark.parametrize("identity_field", ["contract_sha256", "runner_sha256"])
def test_capacity_receipt_must_bind_current_contract_and_runner(tmp_path, identity_field):
    stale = _capacity()
    stale[identity_field] = "0" * 64
    result = _stage_result(
        "capacity", tmp_path, tmp_path / f"stale-{identity_field}.json", stale
    )
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"


def test_static_preflight_pass_without_canonical_gpu_samples_is_refused(tmp_path):
    static = {
        "schema_version": "szl.nemo.preflight-receipt.v1",
        "state": "PASS",
        "checks": [{"id": "PINNED_CONTRACT_ASSETS", "state": "PASS"}],
    }
    result = _stage_result("preflight", tmp_path, tmp_path / "static-preflight.json", static)
    assert queue.preflight_outcome(result) == "TERMINAL_REFUSAL"


def test_capacity_refuses_runtime_guard_without_initial_and_final_samples(tmp_path):
    receipt = _capacity()
    receipt["runtime_guard"]["samples"] = []
    result = _stage_result("capacity", tmp_path, tmp_path / "capacity.json", receipt)
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"


def test_capacity_and_preflight_malformed_nested_shapes_fail_closed(tmp_path):
    capacity = _capacity()
    capacity["effects"] = []
    result = _stage_result(
        "capacity", tmp_path, tmp_path / "capacity-malformed.json", capacity
    )
    assert queue.capacity_outcome(result) == "TERMINAL_REFUSAL"

    for checks in (None, {}, ["not-an-object"]):
        malformed = {"state": "BLOCKED", "checks": checks}
        assert queue._only_gpu_admission_blocked(malformed) is False


def test_training_refuses_a_tripped_runtime_guard(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    training["runtime_guard"] = {"state": "TRIPPED", "reason": "thermal ceiling"}
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_invalid_dsse_even_when_file_hash_is_rebound(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    candidate = output / "receipts" / "candidate-summary.dsse.json"
    _write(candidate, {"not": "a DSSE envelope"})
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate)
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_pinned_dsse_loader_rejects_replaced_source_and_key():
    replaced = json.loads(json.dumps(CONTRACT))
    replaced["dsse"]["verifier_sha256"] = "0" * 64
    with pytest.raises(queue.QueueRefused, match="source mismatch"):
        queue._load_pinned_dsse(replaced)

    wrong_key = json.loads(json.dumps(CONTRACT))
    wrong_key["dsse"]["public_key_fingerprint_sha256"] = "0" * 64
    with pytest.raises(queue.QueueRefused, match="key identity mismatch"):
        queue._load_pinned_dsse(wrong_key)


def test_training_refuses_unsigned_candidate_even_when_all_hashes_match(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    candidate = output / "receipts" / "candidate-summary.dsse.json"
    candidate_value = json.loads(candidate.read_text(encoding="utf-8"))
    candidate_value["envelope"]["signed"] = False
    candidate_value["envelope"]["signatures"] = []
    candidate_value["verification"] = {"verified": False, "reason": "unsigned"}
    candidate_value["promotion_eligible_signature"] = False
    _write(candidate, candidate_value)
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate)
    training["organization_signature_verified"] = False
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_fully_rebound_malformed_result_row_without_crashing(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    receipts = output / "receipts"
    reload_path = receipts / "reload-evaluation-receipt.json"
    reload_value = json.loads(reload_path.read_text(encoding="utf-8"))
    reload_value["results"][0] = "not-an-object"
    _write(reload_path, reload_value)
    reload_sha = queue._sha256_file(reload_path)
    evidence_path = receipts / "training-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["artifact_evidence"]["reload_evaluation_receipt_sha256"] = reload_sha
    _write(evidence_path, evidence)
    evidence_sha = queue._sha256_file(evidence_path)
    candidate_path = receipts / "candidate-summary.dsse.json"
    summary = _read_candidate_summary(candidate_path)
    summary["reload_evaluation_receipt_sha256"] = reload_sha
    summary["training_evidence_sha256"] = evidence_sha
    _write_signed_candidate(candidate_path, summary)
    training["reload_evaluation_receipt_sha256"] = reload_sha
    training["training_evidence_sha256"] = evidence_sha
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate_path)
    result = _stage_result(
        "training", tmp_path, receipts / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_rebound_false_step_evidence(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    receipts = output / "receipts"
    evidence_path = receipts / "training-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["step_evidence"]["observed_global_steps"] -= 1
    _write(evidence_path, evidence)
    evidence_sha = queue._sha256_file(evidence_path)
    candidate_path = receipts / "candidate-summary.dsse.json"
    summary = _read_candidate_summary(candidate_path)
    summary["training_evidence_sha256"] = evidence_sha
    _write_signed_candidate(candidate_path, summary)
    training["training_evidence_sha256"] = evidence_sha
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate_path)
    result = _stage_result(
        "training", tmp_path, receipts / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_candidate_runtime_guard_not_equal_to_receipts(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    candidate_path = output / "receipts" / "candidate-summary.dsse.json"
    summary = _read_candidate_summary(candidate_path)
    summary["runtime_guard"]["timing"]["elapsed_monotonic_ms"] += 1
    _write_signed_candidate(candidate_path, summary)
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate_path)
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_adapter_file_tamper(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    (output / "adapter" / "adapter_model.safetensors").write_bytes(b"tampered")
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_symlinked_adapter_root(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    adapter = output / "adapter"
    real_adapter = output / "real-adapter"
    adapter.rename(real_adapter)
    try:
        adapter.symlink_to(real_adapter, target_is_directory=True)
    except OSError:
        pytest.skip("host does not permit directory symlinks")
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_non_monotonic_timestamps(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    training["training_completed_at_unix_ns"] = 0
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_refuses_missing_signature_honesty_fields(tmp_path):
    output = tmp_path / "run"
    training = _passing_training_output(output)
    candidate = output / "receipts" / "candidate-summary.dsse.json"
    candidate_value = json.loads(candidate.read_text(encoding="utf-8"))
    del candidate_value["promotion_eligible_signature"]
    _write(candidate, candidate_value)
    training["candidate_summary_dsse_sha256"] = queue._sha256_file(candidate)
    result = _stage_result(
        "training", tmp_path, output / "receipts" / "training-receipt.json", training
    )
    assert queue.training_outcome(result, output) == "TERMINAL_REVIEW_REQUIRED"


def test_training_start_evidence_is_tri_state_and_never_bool_collapsed():
    assert queue._training_start_state(None) == queue.TRAINING_START_UNKNOWN
    assert queue._training_start_state({"schema_version": "wrong"}) == queue.TRAINING_START_UNKNOWN
    assert queue._training_start_state(
        {
            "schema_version": "szl.nemo.training-receipt.v1",
            "state": "RUNNING_NOT_PROMOTED",
        }
    ) == queue.TRAINING_START_PROVEN_FALSE
    for state in (
        "TRAINING_STARTED_NOT_PROMOTED",
        "FAILED_NOT_PROMOTED",
        "CANDIDATE_PASS_NOT_PROMOTED",
    ):
        assert queue._training_start_state(
            {
                "schema_version": "szl.nemo.training-receipt.v1",
                "state": state,
            }
        ) == queue.TRAINING_START_UNKNOWN
    assert queue._training_start_state(
        {
            "schema_version": "szl.nemo.training-receipt.v1",
            "training_started_at_unix_ns": 1,
        }
    ) == queue.TRAINING_START_PROVEN_TRUE
    assert queue._training_start_state(
        {
            "schema_version": "szl.nemo.training-receipt.v1",
            "training_started_at_unix_ns": True,
        }
    ) == queue.TRAINING_START_UNKNOWN
    assert queue._merge_training_start_state(
        queue.TRAINING_START_PROVEN_FALSE, queue.TRAINING_START_UNKNOWN
    ) == queue.TRAINING_START_UNKNOWN
    assert queue._merge_training_start_state(
        queue.TRAINING_START_UNKNOWN, queue.TRAINING_START_PROVEN_FALSE
    ) == queue.TRAINING_START_PROVEN_FALSE


def test_stage_command_invokes_measured_bash_not_launcher_directly(monkeypatch, tmp_path):
    bash = tmp_path / "bash"
    bash.write_bytes(b"fixture")
    monkeypatch.setattr(queue, "_resolve_bash", lambda: bash)
    command = queue._stage_command(
        "preflight", _config(tmp_path), preflight_receipt=tmp_path / "preflight.json"
    )
    assert command[:2] == [str(bash), str(queue.LAUNCHER_PATH)]


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
