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
import hashlib
import json
import os
import platform
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
DEFAULT_STATE_ROOT = HERE / "queue-state" / "wsl"
CAPACITY_PASS = "PASS_CAPACITY_ONLY_NOT_TRAINED_NOT_PROMOTED"
CANDIDATE_PASS = "CANDIDATE_GENERATED_NOT_PROMOTED"
LEASE_BUSY_TEXT = "another governed SZL training process holds the shared GPU lease"
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
            "training_started": False,
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
        training_started: bool = False,
    ) -> None:
        self.sequence += 1
        self.effects["training_started"] = self.effects["training_started"] or training_started
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
    blocked = [
        check.get("id")
        for check in receipt.get("checks", [])
        if isinstance(check, dict) and check.get("state") == "BLOCKED"
    ]
    return blocked == ["GPU_ADMISSION"]


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
    ):
        return "PASS"
    if _lease_busy(result) or (result.exit_code == 3 and _only_gpu_admission_blocked(result.receipt)):
        return "RETRYABLE_ADMISSION"
    return "TERMINAL_REFUSAL"


def capacity_outcome(result: StageResult, launcher_preflight: dict[str, Any] | None = None) -> str:
    receipt = result.receipt
    if (
        result.exit_code == 0
        and receipt
        and receipt.get("schema_version") == "szl.nemo.capacity-probe-receipt.v1"
        and receipt.get("state") == CAPACITY_PASS
        and receipt.get("training_started") is False
        and receipt.get("effects", {}).get("capacity_optimization_step_completed") is True
        and receipt.get("effects", {}).get("adapter_written") is False
    ):
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
    if not (
        result.exit_code == 0
        and receipt
        and receipt.get("schema_version") == "szl.nemo.training-receipt.v1"
        and receipt.get("state") == CANDIDATE_PASS
        and receipt.get("promotion") == "NOT_PROMOTED"
        and reload_receipt.is_file()
        and candidate.is_file()
        and adapter_files.is_file()
    ):
        return "TERMINAL_REVIEW_REQUIRED"
    try:
        reload_value = _load_object(reload_receipt)
    except (OSError, ValueError, json.JSONDecodeError, QueueRefused):
        return "TERMINAL_REVIEW_REQUIRED"
    return "PASS" if reload_value.get("state") == "PASS" else "TERMINAL_REVIEW_REQUIRED"


def _stage_command(
    mode: str,
    config: QueueConfig,
    *,
    preflight_receipt: Path,
    capacity_receipt: Path | None = None,
    output: Path | None = None,
) -> list[str]:
    command = [
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
    if not LAUNCHER_PATH.is_file() or not os.access(LAUNCHER_PATH, os.X_OK):
        raise QueueRefused("governed Linux launcher is absent or not executable")
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
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, False))
            if attempt < config.max_attempts:
                store.transition("WAITING_FOR_ADMISSION", "Pure admission/lease refusal; fixed gates remain unchanged.", attempt=attempt)
                sleep(config.retry_seconds)
                continue
            store.transition("EXHAUSTED_NOT_TRAINED", "Maximum bounded attempts reached before capacity qualification.", attempt=attempt)
            return 3, store.path
        if preflight_state != "PASS":
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, False))
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
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, False))
            if attempt < config.max_attempts:
                store.transition("WAITING_FOR_ADMISSION", "Capacity was not entered; retrying only the fixed admission/lease boundary.", attempt=attempt)
                sleep(config.retry_seconds)
                continue
            store.transition("EXHAUSTED_NOT_TRAINED", "Maximum bounded attempts reached without a capacity pass.", attempt=attempt)
            return 3, store.path
        if capacity_state != "PASS":
            store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, False))
            store.transition("BLOCKED_OPERATOR_REVIEW", "Capacity receipt did not prove the exact bounded step.", attempt=attempt)
            return 5, store.path

        output = config.output_root / f"{queue_id}-attempt-{attempt:03d}"
        store.transition("TRAINING_INVOKED_NOT_PROMOTED", "Capacity passed; invoking one isolated governed training run. Automatic retry is now disabled.", attempt=attempt)
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
        started = bool(training.receipt and training.receipt.get("training_started_at_unix_ns"))
        store.write_attempt(attempt, _attempt_receipt(store.queue_id, attempt, stage_states, started, output))
        if training_state == "PASS":
            store.transition(
                CANDIDATE_PASS,
                "Adapter, exact-base reload, and all held-out rows passed; upload/publish/promotion remain blocked.",
                attempt=attempt,
                training_started=True,
            )
            return 0, store.path
        store.transition(
            "TRAINING_TERMINAL_OPERATOR_REVIEW",
            "Training was invoked and did not produce a fully passing candidate receipt; no automatic retry is permitted.",
            attempt=attempt,
            training_started=started,
        )
        return 6, store.path

    raise AssertionError("bounded attempt loop did not terminate")


def _attempt_receipt(
    queue_id: str,
    attempt: int,
    stages: dict[str, str],
    training_started: bool,
    output: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "szl.nemo.wsl-queue-attempt.v1",
        "queue_id": queue_id,
        "attempt": attempt,
        "stages": stages,
        "training_started": training_started,
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
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "training_started": False}), file=sys.stderr)
        return 4
    print(json.dumps({"state": _load_object(queue_dir / "state.json")["state"], "queue_dir": str(queue_dir)}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
