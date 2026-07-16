#!/usr/bin/env python3
"""Durable, fail-closed WSL/Linux watcher for governed SZL-Nemo training.

The queue never provisions dependencies, fetches a model, changes an admission
threshold, terminates another process, or performs release operations.  It may
retry only a pure GPU-admission refusal or contention on the repository's
existing shared GPU lease.  Once training is invoked, every non-success result
is terminal and requires operator review.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONTRACT_PATH = HERE / "training-contract.json"
LAUNCHER_PATH = HERE / "run_wsl_governed.sh"
EVAL_PATH = HERE / "generated" / "eval.jsonl"
DSSE_PATH = REPO / "szl_dsse.py"
PAYLOAD_TYPE = "application/vnd.szl.nemo-training+json"
DSSE_KEY_ID = "szlholdings-cosign"
DEFAULT_STATE_ROOT = HERE / "queue-state" / "wsl"
CAPACITY_PASS = "PASS_CAPACITY_ONLY_NOT_TRAINED_NOT_PROMOTED"
CANDIDATE_PASS = "CANDIDATE_GENERATED_NOT_PROMOTED"
LEASE_BUSY_TEXT = "another governed SZL training process holds the shared GPU lease"
TRAINING_START_PROVEN_TRUE = "PROVEN_TRUE"
TRAINING_START_PROVEN_FALSE = "PROVEN_FALSE"
TRAINING_START_UNKNOWN = "UNKNOWN"
TRAINING_START_STATES = {
    TRAINING_START_PROVEN_TRUE,
    TRAINING_START_PROVEN_FALSE,
    TRAINING_START_UNKNOWN,
}
OFFLINE_ENVIRONMENT = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "WANDB_DISABLED": "true",
    "TOKENIZERS_PARALLELISM": "false",
    "NO_PROXY": "*",
}


class QueueRefused(RuntimeError):
    """A queue request or observed receipt failed a fixed policy gate."""


@dataclass(frozen=True)
class QueueConfig:
    base_snapshot: Path
    output_root: Path
    state_root: Path
    confirmation: str
    license_acknowledgement: str
    max_attempts: int
    retry_seconds: int
    python: Path | None = None


@dataclass(frozen=True)
class StageResult:
    stage: str
    exit_code: int
    stdout_path: Path
    stderr_path: Path
    receipt_path: Path | None
    receipt: dict[str, Any] | None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_dsse_identity(contract: dict[str, Any]) -> dict[str, str]:
    policy = contract.get("dsse")
    if not isinstance(policy, dict) or policy.get("ambient_module_allowed") is not False:
        raise QueueRefused("training contract lacks a fail-closed DSSE verifier policy")
    relative = policy.get("verifier_path")
    expected_sha = policy.get("verifier_sha256")
    key_id = policy.get("key_id")
    fingerprint = policy.get("public_key_fingerprint_sha256")
    if (
        relative != "szl_dsse.py"
        or not isinstance(expected_sha, str)
        or len(expected_sha) != 64
        or not isinstance(key_id, str)
        or not key_id
        or not isinstance(fingerprint, str)
        or len(fingerprint) != 64
    ):
        raise QueueRefused("pinned DSSE verifier identity is malformed")
    candidate = REPO / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise QueueRefused("pinned DSSE verifier is absent or symlinked")
    if candidate.resolve() != DSSE_PATH.resolve() or _sha256_file(candidate) != expected_sha:
        raise QueueRefused("pinned DSSE verifier source mismatch")
    return {
        "path": relative,
        "sha256": expected_sha,
        "key_id": key_id,
        "public_key_fingerprint_sha256": fingerprint,
    }


def _load_pinned_dsse(contract: dict[str, Any]) -> tuple[Any, dict[str, str]]:
    identity = _pinned_dsse_identity(contract)
    spec = importlib.util.spec_from_file_location(
        f"_szl_nemo_pinned_dsse_{uuid.uuid4().hex}", DSSE_PATH
    )
    if spec is None or spec.loader is None:
        raise QueueRefused("pinned DSSE verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        observed_fingerprint = module.public_key_fingerprint()
    except Exception as exc:
        raise QueueRefused("pinned DSSE verifier execution failed") from exc
    if (
        getattr(module, "KEYID", None) != identity["key_id"]
        or observed_fingerprint != identity["public_key_fingerprint_sha256"]
    ):
        raise QueueRefused("pinned DSSE verifier key identity mismatch")
    return module, identity


def _resolve_bash() -> Path:
    """Resolve the Linux Bash interpreter used to read the governed launcher.

    GitHub's web commit API stores regular files as 100644. Invoking Bash
    explicitly keeps a fresh Linux checkout operational without treating a
    Windows/DrvFS executable-bit accident as qualification evidence.
    """

    configured = os.environ.get("SZL_NEMO_BASH", "").strip()
    discovered = configured or shutil.which("bash")
    if not discovered:
        raise QueueRefused("Bash is unavailable; set SZL_NEMO_BASH to an executable Linux Bash")
    path = Path(discovered).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise QueueRefused("resolved Bash interpreter is absent or not executable")
    return path


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QueueRefused(f"receipt is not a JSON object: {path}")
    return value


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError("short write while persisting queue evidence")
        offset += written


def _write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        _write_new_json(temporary, value)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _append_jsonl(path: Path, value: Any) -> None:
    """Append one durable event while the queue's exclusive run lock is held."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (_canonical_json(value) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        _write_all(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


class QueueStore:
    """Single-writer journal plus atomic current-state projection."""

    def __init__(self, root: Path, queue_id: str, request: dict[str, Any]) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.queue_id = queue_id
        self.path = root / queue_id
        self.path.mkdir(mode=0o700)
        self.events_path = self.path / "events.jsonl"
        self.state_path = self.path / "state.json"
        self.sequence = 0
        self.effects = {
            "training_started": TRAINING_START_PROVEN_FALSE,
            "uploaded": False,
            "published": False,
            "deployed": False,
            "promoted": False,
        }
        _write_new_json(
            self.path / "runner.lock",
            {
                "schema_version": "szl.nemo.wsl-queue-lock.v1",
                "queue_id": queue_id,
                "pid": os.getpid(),
                "hostname": platform.node(),
                "automatic_stale_deletion": False,
                "stale_policy": "OPERATOR_REVIEW_REQUIRED",
            },
        )
        _write_new_json(self.path / "queue-request.json", request)

    def transition(
        self,
        state: str,
        reason: str,
        *,
        attempt: int | None = None,
        training_start_state: str | None = None,
    ) -> None:
        self.sequence += 1
        self.effects["training_started"] = _merge_training_start_state(
            self.effects["training_started"], training_start_state
        )
        event = {
            "schema_version": "szl.nemo.wsl-queue-event.v1",
            "sequence": self.sequence,
            "queue_id": self.queue_id,
            "state": state,
            "reason": reason,
            "attempt": attempt,
            "observed_at_unix_ns": time.time_ns(),
            "effects": dict(self.effects),
        }
        _append_jsonl(self.events_path, event)
        _atomic_json(
            self.state_path,
            {
                "schema_version": "szl.nemo.wsl-queue-state.v1",
                **event,
                "events_sha256": _sha256_file(self.events_path),
                "journal_is_append_only": True,
                "current_state_is_atomic_projection": True,
            },
        )

    def attempt_path(self, number: int) -> Path:
        path = self.path / "attempts" / f"{number:03d}"
        path.mkdir(parents=True)
        return path

    def write_stage(
        self,
        attempt: int,
        result: StageResult,
        command: Sequence[str],
        *,
        companion_receipts: Sequence[Path] = (),
    ) -> None:
        target = self.path / "attempts" / f"{attempt:03d}" / f"queue-stage-{result.stage}.json"
        _write_new_json(
            target,
            {
                "schema_version": "szl.nemo.wsl-queue-stage.v1",
                "queue_id": self.queue_id,
                "attempt": attempt,
                "stage": result.stage,
                "exit_code": result.exit_code,
                "command": _redact_command(command),
                "stdout": _file_identity(result.stdout_path),
                "stderr": _file_identity(result.stderr_path),
                "runner_receipt": _file_identity(result.receipt_path),
                "companion_receipts": [_file_identity(path) for path in companion_receipts],
                "completed_at_unix_ns": time.time_ns(),
            },
        )

    def write_attempt(self, number: int, value: dict[str, Any]) -> None:
        _write_new_json(self.path / "attempts" / f"{number:03d}" / "attempt-receipt.json", value)


def _file_identity(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _redact_command(command: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for value in command:
        if hide_next:
            redacted.append("<ACKNOWLEDGEMENT_REDACTED>")
            hide_next = False
            continue
        redacted.append(value)
        hide_next = value in {"--confirmation", "--license-acknowledgement"}
    return redacted


def _only_gpu_admission_blocked(receipt: dict[str, Any] | None) -> bool:
    if not receipt or receipt.get("state") != "BLOCKED":
        return False
    checks = receipt.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or not all(isinstance(check, dict) for check in checks)
    ):
        return False
    blocked = [
        check.get("id")
        for check in checks
        if check.get("state") == "BLOCKED"
    ]
    if blocked != ["GPU_ADMISSION"]:
        return False
    contract = _load_object(CONTRACT_PATH)
    blocked_check = next(check for check in checks if check.get("state") == "BLOCKED")
    return blocked_check.get("policy") == contract["gpu_admission"]


def _canonical_gpu_admission_pass(receipt: dict[str, Any]) -> bool:
    contract = _load_object(CONTRACT_PATH)
    policy = contract["gpu_admission"]
    checks = receipt.get("checks")
    if not isinstance(checks, list):
        return False
    matches = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("id") == "GPU_ADMISSION"
    ]
    if len(matches) != 1:
        return False
    check = matches[0]
    samples = check.get("samples")
    if (
        check.get("state") != "PASS"
        or check.get("policy") != policy
        or not isinstance(samples, list)
        or len(samples) != int(policy["probe_samples"])
    ):
        return False
    required_device = contract["runtime"]["required_device_name"]
    return all(
        isinstance(sample, dict)
        and sample.get("gpu_name") == required_device
        and type(sample.get("memory_free_mib")) is int
        and sample["memory_free_mib"] >= int(policy["minimum_free_memory_mib"])
        and type(sample.get("utilization_pct")) is int
        and sample["utilization_pct"] <= int(policy["maximum_utilization_pct"])
        and type(sample.get("temperature_c")) is int
        and sample["temperature_c"] <= int(policy["maximum_temperature_c"])
        for sample in samples
    )


def _lease_busy(result: StageResult) -> bool:
    try:
        return LEASE_BUSY_TEXT in result.stderr_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def preflight_outcome(result: StageResult) -> str:
    if (
        result.exit_code == 0
        and result.receipt
        and result.receipt.get("schema_version") == "szl.nemo.preflight-receipt.v1"
        and result.receipt.get("state") == "PASS"
        and _canonical_gpu_admission_pass(result.receipt)
    ):
        return "PASS"
    if _lease_busy(result) or (result.exit_code == 3 and _only_gpu_admission_blocked(result.receipt)):
        return "RETRYABLE_ADMISSION"
    return "TERMINAL_REFUSAL"


def capacity_outcome(result: StageResult, launcher_preflight: dict[str, Any] | None = None) -> str:
    receipt = result.receipt
    effects = receipt.get("effects") if isinstance(receipt, dict) else None
    probe = receipt.get("probe") if isinstance(receipt, dict) else None
    contract = _load_object(CONTRACT_PATH)
    training = contract["training"]
    if (
        result.exit_code == 0
        and receipt
        and receipt.get("schema_version") == "szl.nemo.capacity-probe-receipt.v1"
        and receipt.get("state") == CAPACITY_PASS
        and receipt.get("training_started") is False
        and receipt.get("profile_id") == training["capacity_profile_id"]
        and receipt.get("contract_sha256") == _sha256_file(CONTRACT_PATH)
        and receipt.get("runner_sha256") == _sha256_file(HERE / "szl_nemo_finetune.py")
        and isinstance(effects, dict)
        and effects.get("capacity_optimization_step_completed") is True
        and effects.get("adapter_written") is False
        and effects.get("uploaded") is False
        and effects.get("published") is False
        and effects.get("deployed") is False
        and effects.get("promoted") is False
        and effects.get("training_authorized") is False
        and effects.get("queue_progression_allowed") is True
        and effects.get("canonical_threshold_changed") is False
        and isinstance(probe, dict)
        and probe.get("profile_id") == training["capacity_profile_id"]
        and probe.get("optimizer") == training["optimizer"]
        and probe.get("optimizer_class") == "PagedAdamW8bit"
        and probe.get("gradient_accumulation_micro_steps") == training["gradient_accumulation_steps"]
        and probe.get("sequence_limit") == training["capacity_probe_sequence_length"]
        and type(probe.get("sequence_tokens")) is int
        and probe["sequence_tokens"] == training["max_sequence_length"]
        and probe["sequence_limit"] == training["max_sequence_length"]
        and probe.get("device_map") == {"": 0}
    ):
        try:
            _validate_runtime_guard(receipt.get("runtime_guard"), _load_object(CONTRACT_PATH))
        except (OSError, ValueError, json.JSONDecodeError, QueueRefused):
            return "TERMINAL_REFUSAL"
        return "PASS"
    nested = receipt.get("preflight") if receipt else launcher_preflight
    capacity_never_entered = receipt is None and launcher_preflight is not None
    capacity_reported_preflight_block = bool(
        receipt and receipt.get("state") == "BLOCKED_NOT_TRAINED_NOT_PROMOTED"
    )
    if _lease_busy(result) or (
        result.exit_code == 3
        and (capacity_never_entered or capacity_reported_preflight_block)
        and _only_gpu_admission_blocked(nested if isinstance(nested, dict) else None)
    ):
        return "RETRYABLE_ADMISSION"
    return "TERMINAL_REFUSAL"


def training_outcome(result: StageResult, output: Path) -> str:
    receipt = result.receipt
    reload_receipt = output / "receipts" / "reload-evaluation-receipt.json"
    candidate = output / "receipts" / "candidate-summary.dsse.json"
    adapter_files = output / "receipts" / "adapter-files.json"
    training_evidence = output / "receipts" / "training-evidence.json"
    started = receipt.get("training_started_at_unix_ns") if receipt else None
    trained = receipt.get("training_completed_at_unix_ns") if receipt else None
    completed = receipt.get("completed_at_unix_ns") if receipt else None
    if not (
        result.exit_code == 0
        and receipt
        and receipt.get("schema_version") == "szl.nemo.training-receipt.v1"
        and receipt.get("state") == CANDIDATE_PASS
        and receipt.get("promotion") == "NOT_PROMOTED"
        and type(started) is int
        and type(trained) is int
        and type(completed) is int
        and 0 < started <= trained <= completed
        and reload_receipt.is_file()
        and candidate.is_file()
        and adapter_files.is_file()
        and training_evidence.is_file()
    ):
        return "TERMINAL_REVIEW_REQUIRED"
    try:
        reload_value = _load_object(reload_receipt)
        adapter_value = _load_object(adapter_files)
        candidate_value = _load_object(candidate)
        training_evidence_value = _load_object(training_evidence)
        _verify_training_artifacts(
            output,
            receipt,
            adapter_files,
            adapter_value,
            reload_receipt,
            reload_value,
            candidate,
            candidate_value,
            training_evidence,
            training_evidence_value,
        )
    except (OSError, ValueError, json.JSONDecodeError, QueueRefused):
        return "TERMINAL_REVIEW_REQUIRED"
    return "PASS"


def _require_sha256(value: Any, expected: str, label: str) -> None:
    if not isinstance(value, str) or value != expected:
        raise QueueRefused(f"{label} SHA-256 binding mismatch")


def _training_start_state(receipt: dict[str, Any] | None) -> str:
    if not isinstance(receipt, dict):
        return TRAINING_START_UNKNOWN
    if receipt.get("schema_version") != "szl.nemo.training-receipt.v1":
        return TRAINING_START_UNKNOWN
    marker = receipt.get("training_started_at_unix_ns")
    if "training_started_at_unix_ns" not in receipt:
        return (
            TRAINING_START_PROVEN_FALSE
            if receipt.get("state") == "RUNNING_NOT_PROMOTED"
            else TRAINING_START_UNKNOWN
        )
    if type(marker) is int and marker > 0:
        return TRAINING_START_PROVEN_TRUE
    return TRAINING_START_UNKNOWN


def _merge_training_start_state(current: str, observed: str | None) -> str:
    if current not in TRAINING_START_STATES or (
        observed is not None and observed not in TRAINING_START_STATES
    ):
        raise QueueRefused("training-start evidence state is malformed")
    if observed is None:
        return current
    if TRAINING_START_PROVEN_TRUE in {current, observed}:
        return TRAINING_START_PROVEN_TRUE
    return observed


def _validate_runtime_guard(value: Any, contract: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise QueueRefused("runtime guard receipt is absent")
    expected_thresholds = {
        "maximum_training_temperature_c": contract["gpu_admission"][
            "maximum_training_temperature_c"
        ],
        "maximum_wall_clock_seconds": contract["training"][
            "maximum_wall_clock_seconds"
        ],
        "watchdog_interval_seconds": contract["training"][
            "watchdog_interval_seconds"
        ],
    }
    timing = value.get("timing")
    samples = value.get("samples")
    if (
        value.get("schema_version") != "szl.nemo.runtime-guard.v1"
        or value.get("state") != "PASS"
        or value.get("reason") is not None
        or value.get("cooperative_interrupt_only") is not True
        or value.get("thresholds") != expected_thresholds
        or not isinstance(timing, dict)
        or not isinstance(samples, list)
        or len(samples) < 2
        or not all(isinstance(sample, dict) for sample in samples)
    ):
        raise QueueRefused("runtime guard structure is incomplete")
    started = timing.get("started_at_unix_ns")
    finalized = timing.get("finalized_at_unix_ns")
    elapsed = timing.get("elapsed_monotonic_ms")
    if (
        type(started) is not int
        or type(finalized) is not int
        or type(elapsed) is not int
        or started <= 0
        or finalized < started
        or elapsed < 0
        or elapsed > expected_thresholds["maximum_wall_clock_seconds"] * 1000
    ):
        raise QueueRefused("runtime guard timing evidence is invalid")
    if samples[0].get("stage") != "initial" or samples[-1].get("stage") != "final":
        raise QueueRefused("runtime guard lacks ordered initial/final samples")
    previous_measured_at = 0
    required_device = contract["runtime"]["required_device_name"]
    maximum_temperature = expected_thresholds["maximum_training_temperature_c"]
    for sample in samples:
        measured_at = sample.get("measured_at_unix_ns")
        integer_fields = {
            field: sample.get(field)
            for field in (
                "memory_total_mib",
                "memory_used_mib",
                "memory_free_mib",
                "utilization_pct",
                "temperature_c",
            )
        }
        if (
            type(measured_at) is not int
            or measured_at <= 0
            or measured_at < previous_measured_at
            or not isinstance(sample.get("stage"), str)
            or not sample.get("stage")
            or sample.get("gpu_name") != required_device
            or any(type(item) is not int for item in integer_fields.values())
            or integer_fields["memory_total_mib"] <= 0
            or integer_fields["memory_used_mib"] < 0
            or integer_fields["memory_free_mib"] < 0
            or not 0 <= integer_fields["utilization_pct"] <= 100
            or integer_fields["temperature_c"] > maximum_temperature
        ):
            raise QueueRefused("runtime guard sample is outside the fixed evidence contract")
        previous_measured_at = measured_at
    if (
        samples[0]["measured_at_unix_ns"] < started
        or samples[-1]["measured_at_unix_ns"] > finalized
    ):
        raise QueueRefused("runtime guard samples fall outside the measured timing window")


def _expected_eval_ids() -> list[str]:
    ids: list[str] = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        record_id = row.get("record_id") if isinstance(row, dict) else None
        if not isinstance(record_id, str) or not record_id or record_id in ids:
            raise QueueRefused("held-out evaluation identity is malformed")
        ids.append(record_id)
    if not ids:
        raise QueueRefused("held-out evaluation identity is empty")
    return ids


def _verify_adapter_inventory(output: Path, value: dict[str, Any]) -> None:
    if value.get("schema_version") != "szl.nemo.adapter-files.v1":
        raise QueueRefused("adapter inventory schema mismatch")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise QueueRefused("adapter inventory is empty")
    adapter_root = output / "adapter"
    if adapter_root.is_symlink() or not adapter_root.is_dir():
        raise QueueRefused("adapter root is absent, not a directory, or a symlink")
    resolved_root = adapter_root.resolve(strict=True)
    if any(path.is_symlink() for path in adapter_root.rglob("*")):
        raise QueueRefused("adapter package contains a symlink")
    expected_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise QueueRefused("adapter inventory entry is malformed")
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            raise QueueRefused("adapter inventory path is malformed")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or relative.replace("\\", "/") != relative:
            raise QueueRefused("adapter inventory path escapes the adapter root")
        if relative in expected_paths:
            raise QueueRefused("adapter inventory contains duplicate paths")
        expected_paths.add(relative)
        path = adapter_root / candidate
        cursor = adapter_root
        for part in candidate.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise QueueRefused(f"adapter inventory traverses a symlink: {relative}")
        try:
            resolved_path = path.resolve(strict=True)
            resolved_path.relative_to(resolved_root)
        except (OSError, ValueError) as exc:
            raise QueueRefused(f"adapter inventory path escapes the adapter root: {relative}") from exc
        if not resolved_path.is_file():
            raise QueueRefused(f"adapter inventory file is absent or a symlink: {relative}")
        if item.get("bytes") != resolved_path.stat().st_size:
            raise QueueRefused(f"adapter inventory byte count mismatch: {relative}")
        _require_sha256(
            item.get("sha256"), _sha256_file(resolved_path), f"adapter file {relative}"
        )
    actual_paths = {
        str(path.relative_to(adapter_root)).replace("\\", "/")
        for path in adapter_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise QueueRefused("adapter inventory does not exactly cover the adapter directory")
    if "adapter_model.safetensors" not in expected_paths or "adapter_config.json" not in expected_paths:
        raise QueueRefused("adapter package lacks required safetensors/config files")
    if any(path.endswith(".bin") for path in expected_paths):
        raise QueueRefused("adapter package contains a pickle-compatible .bin payload")


def _verify_candidate_signature(envelope: dict[str, Any]) -> dict[str, Any]:
    contract = _load_object(CONTRACT_PATH)
    szl_dsse, _identity = _load_pinned_dsse(contract)
    return szl_dsse.verify_envelope(envelope)


def _decode_candidate_summary(value: dict[str, Any]) -> dict[str, Any]:
    expected_identity = _pinned_dsse_identity(_load_object(CONTRACT_PATH))
    envelope = value.get("envelope")
    verification = value.get("verification")
    if not isinstance(envelope, dict) or not isinstance(verification, dict):
        raise QueueRefused("candidate DSSE wrapper is malformed")
    if envelope.get("_dsse") != "DSSEv1" or envelope.get("payloadType") != PAYLOAD_TYPE:
        raise QueueRefused("candidate DSSE identity mismatch")
    payload = envelope.get("payload")
    if not isinstance(payload, str):
        raise QueueRefused("candidate DSSE payload is absent")
    try:
        body = base64.b64decode(payload, validate=True)
        summary = json.loads(body)
    except (ValueError, json.JSONDecodeError) as exc:
        raise QueueRefused("candidate DSSE payload is malformed") from exc
    if not isinstance(summary, dict):
        raise QueueRefused("candidate DSSE payload is not a JSON object")
    pae = (
        b"DSSEv1 "
        + str(len(PAYLOAD_TYPE.encode("utf-8"))).encode("ascii")
        + b" "
        + PAYLOAD_TYPE.encode("utf-8")
        + b" "
        + str(len(body)).encode("ascii")
        + b" "
        + body
    )
    _require_sha256(envelope.get("_pae_sha256"), _sha256_bytes(pae), "candidate DSSE PAE")
    signed = envelope.get("signed") is True
    signatures = envelope.get("signatures")
    promotion_eligible = value.get("promotion_eligible_signature") is True
    if (
        type(envelope.get("signed")) is not bool
        or type(value.get("promotion_eligible_signature")) is not bool
        or type(verification.get("verified")) is not bool
        or not isinstance(signatures, list)
    ):
        raise QueueRefused("candidate DSSE signatures are malformed")
    if not signed or not promotion_eligible or verification.get("verified") is not True:
        raise QueueRefused("queue PASS requires a signed, verified candidate DSSE")
    if len(signatures) != 1 or not isinstance(signatures[0], dict):
        raise QueueRefused("candidate DSSE must carry exactly one organization signature")
    signature = signatures[0]
    if signature.get("keyid") != DSSE_KEY_ID or not isinstance(signature.get("sig"), str):
        raise QueueRefused("candidate DSSE organization signature identity is invalid")
    try:
        decoded_signature = base64.b64decode(signature["sig"], validate=True)
    except ValueError as exc:
        raise QueueRefused("candidate DSSE signature encoding is invalid") from exc
    if not decoded_signature:
        raise QueueRefused("candidate DSSE signature is empty")
    observed = _verify_candidate_signature(envelope)
    observed_signatures = observed.get("signatures")
    if (
        observed.get("verified") is not True
        or observed.get("pae_sha256") != envelope.get("_pae_sha256")
        or verification.get("pae_sha256") != envelope.get("_pae_sha256")
        or verification.get("payloadType") != PAYLOAD_TYPE
        or observed.get("keyid_expected") != expected_identity["key_id"]
        or verification.get("keyid_expected") != expected_identity["key_id"]
        or observed.get("pub_fingerprint_sha256")
        != expected_identity["public_key_fingerprint_sha256"]
        or verification.get("pub_fingerprint_sha256")
        != expected_identity["public_key_fingerprint_sha256"]
        or not isinstance(observed_signatures, list)
        or not any(
            isinstance(item, dict)
            and item.get("keyid") == DSSE_KEY_ID
            and item.get("verified") is True
            for item in observed_signatures
        )
    ):
        raise QueueRefused("candidate DSSE signature did not verify against the pinned key")
    return summary


def _validate_training_evidence(
    value: dict[str, Any],
    training: dict[str, Any],
    contract: dict[str, Any],
    adapter_sha: str,
    reload_sha: str,
) -> None:
    runtime_guard = value.get("runtime_guard")
    runtime_identity = value.get("runtime_identity")
    model_code = value.get("model_code")
    source_control = value.get("source_control")
    base_files = value.get("base_files")
    curriculum_inputs = value.get("curriculum_inputs")
    step = value.get("step_evidence")
    artifacts = value.get("artifact_evidence")
    expected_dsse = _pinned_dsse_identity(contract)
    if (
        value.get("schema_version") != "szl.nemo.training-evidence.v1"
        or value.get("contract_id") != contract["contract_id"]
        or value.get("candidate_id") != contract["candidate_id"]
        or value.get("base_revision") != contract["base"]["revision"]
        or value.get("promotion") != "NOT_PROMOTED"
        or not isinstance(runtime_identity, dict)
        or not runtime_identity
        or not isinstance(model_code, dict)
        or not isinstance(source_control, dict)
        or not isinstance(base_files, dict)
        or not isinstance(curriculum_inputs, dict)
        or not isinstance(step, dict)
        or not isinstance(artifacts, dict)
    ):
        raise QueueRefused("immutable training evidence structure is incomplete")
    _validate_runtime_guard(runtime_guard, contract)
    if (
        value.get("dsse_verifier") != expected_dsse
        or training.get("dsse_verifier") != expected_dsse
    ):
        raise QueueRefused("training evidence DSSE verifier/key identity is unbound")
    _require_sha256(value.get("contract_sha256"), _sha256_file(CONTRACT_PATH), "evidence contract")
    _require_sha256(
        value.get("runner_sha256"),
        _sha256_file(HERE / "szl_nemo_finetune.py"),
        "evidence trainer",
    )
    _require_sha256(
        value.get("curriculum_manifest_sha256"),
        _sha256_file(HERE / "generated" / "curriculum-manifest.json"),
        "evidence curriculum manifest",
    )
    if (
        value.get("contract_sha256") != training.get("contract_sha256")
        or value.get("runner_sha256") != training.get("runner_sha256")
        or value.get("curriculum_manifest_sha256")
        != training.get("curriculum_manifest_sha256")
    ):
        raise QueueRefused("training evidence source hashes do not match the final receipt")
    if runtime_guard != training.get("runtime_guard"):
        raise QueueRefused("training evidence runtime guard does not match the final receipt")
    if (
        runtime_identity != training.get("runtime_identity")
        or model_code.get("loaded_model_class") != training.get("loaded_model_class")
        or model_code.get("reloaded_model_class") != training.get("reloaded_model_class")
        or not isinstance(model_code.get("loaded_model_class"), dict)
        or not isinstance(model_code.get("reloaded_model_class"), dict)
    ):
        raise QueueRefused("training evidence runtime/model identity is unbound")
    stable_sections = (
        (source_control, training.get("source_control"), training.get("source_control_after")),
        (base_files, training.get("base_files_before"), training.get("base_files_after")),
        (
            curriculum_inputs,
            training.get("curriculum_inputs_before"),
            training.get("curriculum_inputs_after"),
        ),
    )
    for section, before, after in stable_sections:
        if (
            not isinstance(before, (dict, list))
            or not before
            or not isinstance(after, type(before))
            or before != after
        ):
            raise QueueRefused("training inputs changed or lack complete before/after evidence")
        if section.get("before") != before or section.get("after") != after:
            raise QueueRefused("training evidence before/after binding mismatch")
    started = training.get("training_started_at_unix_ns")
    trained = training.get("training_completed_at_unix_ns")
    loss = training.get("training_loss")
    peak_vram = training.get("peak_vram_reserved_bytes")
    global_steps = training.get("global_steps")
    if (
        step.get("training_started_at_unix_ns") != started
        or step.get("training_completed_at_unix_ns") != trained
        or step.get("expected_global_steps") != contract["training"]["max_steps"]
        or step.get("observed_global_steps") != global_steps
        or global_steps != contract["training"]["max_steps"]
        or type(peak_vram) is not int
        or peak_vram < 0
        or step.get("peak_vram_reserved_bytes") != peak_vram
        or isinstance(loss, bool)
        or not isinstance(loss, (int, float))
        or not math.isfinite(float(loss))
        or step.get("training_loss") != loss
    ):
        raise QueueRefused("training step evidence is incomplete or inconsistent")
    if artifacts != {
        "adapter_files_receipt_sha256": adapter_sha,
        "reload_evaluation_receipt_sha256": reload_sha,
        "held_out_eval_sha256": _sha256_file(EVAL_PATH),
    }:
        raise QueueRefused("training artifact evidence is not bound to the evaluated candidate")


def _verify_training_artifacts(
    output: Path,
    training: dict[str, Any],
    adapter_path: Path,
    adapter_value: dict[str, Any],
    reload_path: Path,
    reload_value: dict[str, Any],
    candidate_path: Path,
    candidate_value: dict[str, Any],
    training_evidence_path: Path,
    training_evidence_value: dict[str, Any],
) -> None:
    for path in (adapter_path, reload_path, candidate_path, training_evidence_path):
        if path.is_symlink():
            raise QueueRefused("training receipt artifact must not be a symlink")
    adapter_sha = _sha256_file(adapter_path)
    reload_sha = _sha256_file(reload_path)
    candidate_sha = _sha256_file(candidate_path)
    training_evidence_sha = _sha256_file(training_evidence_path)
    _require_sha256(training.get("adapter_files_sha256"), adapter_sha, "training adapter inventory")
    _require_sha256(training.get("reload_evaluation_receipt_sha256"), reload_sha, "training reload evaluation")
    _require_sha256(training.get("candidate_summary_dsse_sha256"), candidate_sha, "training candidate summary")
    _require_sha256(
        training.get("training_evidence_sha256"),
        training_evidence_sha,
        "immutable training evidence",
    )
    _verify_adapter_inventory(output, adapter_value)

    contract = _load_object(CONTRACT_PATH)
    _validate_training_evidence(
        training_evidence_value, training, contract, adapter_sha, reload_sha
    )
    expected_ids = _expected_eval_ids()
    results = reload_value.get("results")
    if (
        reload_value.get("schema_version") != "szl.nemo.reload-evaluation-receipt.v1"
        or reload_value.get("state") != "PASS"
        or reload_value.get("promotion") != "NONE_AUTOMATIC"
        or reload_value.get("base_revision") != contract["base"]["revision"]
        or reload_value.get("eval_sha256") != _sha256_file(EVAL_PATH)
        or reload_value.get("adapter_files_sha256") != adapter_sha
        or reload_value.get("rows") != len(expected_ids)
        or reload_value.get("passes") != len(expected_ids)
        or not isinstance(results, list)
        or len(results) != len(expected_ids)
        or not all(isinstance(item, dict) for item in results)
    ):
        raise QueueRefused("reload evaluation binding is incomplete")
    observed_ids = [item.get("record_id") for item in results]
    if observed_ids != expected_ids or any(item.get("state") != "PASS" for item in results):
        raise QueueRefused("reload evaluation rows do not exactly match the held-out split")

    summary = _decode_candidate_summary(candidate_value)
    if (
        summary.get("schema_version") != "szl.nemo.candidate-summary.v1"
        or summary.get("contract_id") != contract["contract_id"]
        or summary.get("base_revision") != contract["base"]["revision"]
        or summary.get("adapter_files_receipt_sha256") != adapter_sha
        or summary.get("reload_evaluation_receipt_sha256") != reload_sha
        or summary.get("training_evidence_sha256") != training_evidence_sha
        or summary.get("dsse_verifier") != training.get("dsse_verifier")
        or summary.get("dsse_verifier") != training_evidence_value.get("dsse_verifier")
        or summary.get("evaluation_state") != "PASS"
        or summary.get("promotion") != "NOT_PROMOTED"
        or summary.get("runtime_guard") != training.get("runtime_guard")
        or summary.get("runtime_guard") != training_evidence_value.get("runtime_guard")
    ):
        raise QueueRefused("candidate summary does not bind the passing local candidate")
    if (
        type(training.get("organization_signature_verified")) is not bool
        or training.get("organization_signature_verified") is not True
        or training.get("organization_signature_verified")
        != candidate_value.get("promotion_eligible_signature")
    ):
        raise QueueRefused("training receipt signature status does not match the candidate DSSE")


def _stage_command(
    mode: str,
    config: QueueConfig,
    *,
    preflight_receipt: Path,
    capacity_receipt: Path | None = None,
    output: Path | None = None,
) -> list[str]:
    command = [
        str(_resolve_bash()),
        str(LAUNCHER_PATH),
        "--mode", mode,
        "--base-snapshot", str(config.base_snapshot),
        "--preflight-receipt", str(preflight_receipt),
    ]
    if mode == "capacity":
        if capacity_receipt is None:
            raise QueueRefused("capacity receipt path is required")
        command.extend(["--receipt", str(capacity_receipt)])
    if mode == "train":
        if output is None:
            raise QueueRefused("training output path is required")
        command.extend(["--output-dir", str(output)])
    if mode != "preflight":
        command.extend(
            [
                "--confirmation", config.confirmation,
                "--license-acknowledgement", config.license_acknowledgement,
            ]
        )
    return command


def _execute_stage(stage: str, command: Sequence[str], attempt_dir: Path, receipt: Path | None, config: QueueConfig) -> StageResult:
    stdout_path = attempt_dir / f"{stage}.stdout.log"
    stderr_path = attempt_dir / f"{stage}.stderr.log"
    environment = dict(os.environ)
    environment.update(OFFLINE_ENVIRONMENT)
    if config.python is not None:
        environment["SZL_NEMO_PYTHON"] = str(config.python)
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            completed = subprocess.run(
                list(command),
                cwd=REPO,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                check=False,
            )
            exit_code = completed.returncode
        except OSError as exc:
            stderr.write(f"LAUNCH_FAILED:{type(exc).__name__}:{exc}\n".encode("utf-8"))
            stderr.flush()
            os.fsync(stderr.fileno())
            exit_code = 127
    parsed = None
    if receipt is not None and receipt.is_file():
        try:
            parsed = _load_object(receipt)
        except (OSError, ValueError, json.JSONDecodeError, QueueRefused):
            parsed = None
    return StageResult(stage, exit_code, stdout_path, stderr_path, receipt, parsed)


StageExecutor = Callable[[str, Sequence[str], Path, Path | None, QueueConfig], StageResult]


def _validate_config(config: QueueConfig, contract: dict[str, Any]) -> None:
    if platform.system() != "Linux":
        raise QueueRefused("WSL2/Linux is required; native Windows is non-retryable")
    if config.confirmation != contract["training"]["confirmation_phrase"]:
        raise QueueRefused("exact training confirmation phrase is required")
    if config.license_acknowledgement != contract["base"]["license_acknowledgement"]:
        raise QueueRefused("exact NVIDIA license acknowledgement is required")
    if not 1 <= config.max_attempts <= 240:
        raise QueueRefused("max attempts must be between 1 and 240")
    if not 30 <= config.retry_seconds <= 3600:
        raise QueueRefused("retry seconds must be between 30 and 3600")
    if not config.base_snapshot.is_dir():
        raise QueueRefused("immutable base snapshot is absent")
    if not LAUNCHER_PATH.is_file():
        raise QueueRefused("governed Linux launcher is absent")
    _resolve_bash()
    if config.python is not None and not (config.python.is_file() and os.access(config.python, os.X_OK)):
        raise QueueRefused("pinned Python is absent or not executable")
    base = config.base_snapshot.resolve()
    output = config.output_root.resolve()
    state = config.state_root.resolve()
    for destination in (output, state):
        if destination == base or base in destination.parents or destination in base.parents:
            raise QueueRefused("immutable base and queue state/output paths must be disjoint")
    if output == state or output in state.parents or state in output.parents:
        raise QueueRefused("queue state and training output paths must be disjoint")


def _load_optional_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return _load_object(path)
    except (OSError, ValueError, json.JSONDecodeError, QueueRefused):
        return None


def run_queue(
    config: QueueConfig,
    *,
    executor: StageExecutor = _execute_stage,
    sleep: Callable[[float], None] = time.sleep,
    queue_id: str | None = None,
) -> tuple[int, Path]:
    contract = _load_object(CONTRACT_PATH)
    _validate_config(config, contract)
    bash_path = _resolve_bash()
    config.output_root.mkdir(parents=True, exist_ok=True)
    queue_id = queue_id or f"szl-nemo-wsl-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
    request = {
        "schema_version": "szl.nemo.wsl-queue-request.v1",
        "queue_id": queue_id,
        "contract_id": contract["contract_id"],
        "candidate_id": contract["candidate_id"],
        "base_snapshot": str(config.base_snapshot.resolve()),
        "output_root": str(config.output_root.resolve()),
        "max_attempts": config.max_attempts,
        "retry_seconds": config.retry_seconds,
        "confirmation_sha256": _sha256_bytes(config.confirmation.encode("utf-8")),
        "license_acknowledgement_sha256": _sha256_bytes(config.license_acknowledgement.encode("utf-8")),
        "orchestration_identity": {
            "contract_sha256": _sha256_file(CONTRACT_PATH),
            "launcher_sha256": _sha256_file(LAUNCHER_PATH),
            "trainer_sha256": _sha256_file(HERE / "szl_nemo_finetune.py"),
            "bash": {
                "path": str(bash_path),
                "sha256": _sha256_file(bash_path),
            },
            "shared_lease_implementation": "szl_nemo_finetune.training_mutex",
        },
        "policy": {
            "thresholds_may_be_weakened": False,
            "processes_may_be_stopped_automatically": False,
            "shared_gpu_lease_required": True,
            "retryable_states": ["PURE_GPU_ADMISSION_REFUSAL", "SHARED_GPU_LEASE_BUSY"],
            "retry_after_training_invoked": False,
            "network_fetch_allowed": False,
            "upload_allowed": False,
            "publish_allowed": False,
            "promotion_allowed": False,
        },
    }
    store = QueueStore(config.state_root, queue_id, request)
    store.transition("WAITING_FOR_ADMISSION", "Validated request; no model load or training has started.")

    for attempt in range(1, config.max_attempts + 1):
        attempt_dir = store.attempt_path(attempt)
        store.transition("PREFLIGHT", "Running pinned runtime and fixed GPU admission preflight.", attempt=attempt)
        preflight_receipt = attempt_dir / "preflight-receipt.json"
        preflight_command = _stage_command("preflight", config, preflight_receipt=preflight_receipt)
        preflight = executor("preflight", preflight_command, attempt_dir, preflight_receipt, config)
        store.write_stage(attempt, preflight, preflight_command)
        preflight_state = preflight_outcome(preflight)
        stage_states: dict[str, str] = {"preflight": preflight_state}

        if preflight_state == "RETRYABLE_ADMISSION":
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, TRAINING_START_PROVEN_FALSE))
            if attempt < config.max_attempts:
                store.transition("WAITING_FOR_ADMISSION", "Pure admission/lease refusal; fixed gates remain unchanged.", attempt=attempt)
                sleep(config.retry_seconds)
                continue
            store.transition("EXHAUSTED_NOT_TRAINED", "Maximum bounded attempts reached before capacity qualification.", attempt=attempt)
            return 3, store.path
        if preflight_state != "PASS":
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, TRAINING_START_PROVEN_FALSE))
            store.transition("BLOCKED_OPERATOR_REVIEW", "Preflight refusal was not safely retryable.", attempt=attempt)
            return 4, store.path

        store.transition("CAPACITY_PROBE", "Preflight passed; launching isolated one-step capacity proof.", attempt=attempt)
        capacity_receipt = attempt_dir / "capacity-receipt.json"
        capacity_preflight = attempt_dir / "capacity-preflight-receipt.json"
        capacity_command = _stage_command(
            "capacity", config, preflight_receipt=capacity_preflight, capacity_receipt=capacity_receipt
        )
        capacity = executor("capacity", capacity_command, attempt_dir, capacity_receipt, config)
        store.write_stage(
            attempt,
            capacity,
            capacity_command,
            companion_receipts=(capacity_preflight,),
        )
        capacity_state = capacity_outcome(capacity, _load_optional_object(capacity_preflight))
        stage_states["capacity"] = capacity_state
        if capacity_state == "RETRYABLE_ADMISSION":
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, TRAINING_START_PROVEN_FALSE))
            if attempt < config.max_attempts:
                store.transition("WAITING_FOR_ADMISSION", "Capacity was not entered; retrying only the fixed admission/lease boundary.", attempt=attempt)
                sleep(config.retry_seconds)
                continue
            store.transition("EXHAUSTED_NOT_TRAINED", "Maximum bounded attempts reached without a capacity pass.", attempt=attempt)
            return 3, store.path
        if capacity_state != "PASS":
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, TRAINING_START_PROVEN_FALSE))
            store.transition("BLOCKED_OPERATOR_REVIEW", "Capacity receipt did not prove the exact bounded step.", attempt=attempt)
            return 5, store.path

        output = config.output_root / f"{queue_id}-attempt-{attempt:03d}"
        store.transition(
            "TRAINING_INVOKED_NOT_PROMOTED",
            "Capacity passed; invoking one isolated governed training run. Automatic retry is now disabled.",
            attempt=attempt,
            training_start_state=TRAINING_START_UNKNOWN,
        )
        training_preflight = attempt_dir / "training-preflight-receipt.json"
        training_command = _stage_command("train", config, preflight_receipt=training_preflight, output=output)
        training_receipt = output / "receipts" / "training-receipt.json"
        training = executor("training", training_command, attempt_dir, training_receipt, config)
        store.write_stage(
            attempt,
            training,
            training_command,
            companion_receipts=(training_preflight,),
        )
        training_state = training_outcome(training, output)
        stage_states["training"] = training_state
        start_state = _training_start_state(training.receipt)
        store.write_attempt(
            attempt,
            _attempt_receipt(store.queue_id, attempt, stage_states, start_state, output),
        )
        if training_state == "PASS":
            store.transition(
                CANDIDATE_PASS,
                "Adapter, exact-base reload, and all held-out rows passed; upload/publish/promotion remain blocked.",
                attempt=attempt,
                training_start_state=TRAINING_START_PROVEN_TRUE,
            )
            return 0, store.path
        store.transition(
            "TRAINING_TERMINAL_OPERATOR_REVIEW",
            "Training was invoked and did not produce a fully passing candidate receipt; no automatic retry is permitted.",
            attempt=attempt,
            training_start_state=start_state,
        )
        return 6, store.path

    raise AssertionError("bounded attempt loop did not terminate")


def _attempt_receipt(
    queue_id: str,
    attempt: int,
    stages: dict[str, str],
    training_start_state: str,
    output: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "szl.nemo.wsl-queue-attempt.v1",
        "queue_id": queue_id,
        "attempt": attempt,
        "stages": stages,
        "training_started": training_start_state,
        "output": str(output) if output else None,
        "completed_at_unix_ns": time.time_ns(),
        "effects": {
            "uploaded": False,
            "published": False,
            "deployed": False,
            "promoted": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--base-snapshot", required=True, type=Path)
    run.add_argument("--output-root", required=True, type=Path)
    run.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    run.add_argument("--confirmation", required=True)
    run.add_argument("--license-acknowledgement", required=True)
    run.add_argument("--max-attempts", type=int, default=30)
    run.add_argument("--retry-seconds", type=int, default=120)
    run.add_argument("--python", type=Path)
    status = sub.add_parser("status")
    status.add_argument("--queue-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        state = _load_object(args.queue_dir / "state.json")
        print(json.dumps(state, indent=2))
        return 0
    config = QueueConfig(
        base_snapshot=args.base_snapshot.resolve(),
        output_root=args.output_root.resolve(),
        state_root=args.state_root.resolve(),
        confirmation=args.confirmation,
        license_acknowledgement=args.license_acknowledgement,
        max_attempts=args.max_attempts,
        retry_seconds=args.retry_seconds,
        python=args.python.resolve() if args.python else None,
    )
    try:
        exit_code, queue_dir = run_queue(config)
    except QueueRefused as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "training_started": TRAINING_START_PROVEN_FALSE}), file=sys.stderr)
        return 4
    print(json.dumps({"state": _load_object(queue_dir / "state.json")["state"], "queue_dir": str(queue_dir)}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
