from __future__ import annotations

"""Atomic reversible file executor confined to an explicit sandbox root."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .canonical import digest_bytes
from .capability import normalize_target
from .enums import ActionKind
from .errors import IntegrityError, PostconditionError, ValidationError
from .models import ActionRequest, ConditionSpec


@dataclass(frozen=True, slots=True)
class ConditionResult:
    condition: dict[str, Any]
    passed: bool
    observed: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "passed": self.passed,
            "observed": self.observed,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    action_digest: str
    target: str
    before_digest: str | None
    after_digest: str | None
    postcondition_results: tuple[ConditionResult, ...]
    postconditions_passed: bool
    rolled_back: bool
    rollback_digest: str | None
    mutation_applied: bool
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "szl.sandbox-execution-result/v1",
            "action_digest": self.action_digest,
            "target": self.target,
            "before_digest": self.before_digest,
            "after_digest": self.after_digest,
            "postcondition_results": [item.to_dict() for item in self.postcondition_results],
            "postconditions_passed": self.postconditions_passed,
            "rolled_back": self.rolled_back,
            "rollback_digest": self.rollback_digest,
            "mutation_applied": self.mutation_applied,
            "error": self.error,
            "assurance_scope": "LOCAL_SANDBOX_FILESYSTEM_ONLY",
        }


class SandboxExecutor:
    def __init__(self, root: str | Path, *, max_file_bytes: int = 10 * 1024 * 1024) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValidationError("sandbox root must be a real directory")
        self.root = self.root.resolve()
        self.max_file_bytes = max_file_bytes

    def _resolve(self, target: str, *, create_parents: bool = False) -> Path:
        normalized = normalize_target(target)
        candidate = self.root.joinpath(*normalized.split("/"))
        current = self.root
        parts = normalized.split("/")
        for part in parts[:-1]:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ValidationError("symbolic-link path components are forbidden")
            if create_parents and not current.exists():
                current.mkdir(mode=0o750)
        if candidate.exists() and candidate.is_symlink():
            raise ValidationError("symbolic-link targets are forbidden")
        resolved_parent = candidate.parent.resolve()
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as exc:
            raise ValidationError("target escapes sandbox root") from exc
        return candidate

    @staticmethod
    def _read(path: Path) -> bytes | None:
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValidationError("target must be a regular file")
        return path.read_bytes()

    @staticmethod
    def _digest(data: bytes | None) -> str | None:
        return None if data is None else digest_bytes(data)

    def _atomic_write(self, path: Path, data: bytes) -> None:
        if len(data) > self.max_file_bytes:
            raise ValidationError("target file exceeds configured sandbox limit")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise ValidationError("symbolic-link parent is forbidden")
        fd, temp_name = tempfile.mkstemp(prefix=".alloy-", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o640)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def evaluate_condition(self, condition: ConditionSpec) -> ConditionResult:
        path = self._resolve(condition.target)
        observed: Any
        passed = False
        reason = ""
        if condition.kind == "FILE_EXISTS":
            observed = path.is_file() and not path.is_symlink()
            passed = observed is bool(condition.expected)
            reason = "file presence compared"
        elif condition.kind == "FILE_ABSENT":
            observed = not path.exists()
            passed = observed is bool(condition.expected)
            reason = "file absence compared"
        elif condition.kind == "SHA256_EQUALS":
            data = self._read(path)
            observed = self._digest(data)
            passed = observed == condition.expected
            reason = "file digest compared"
        elif condition.kind == "TEXT_CONTAINS":
            data = self._read(path)
            if data is None:
                observed = None
            else:
                try:
                    observed = str(condition.expected) in data.decode("utf-8")
                except UnicodeDecodeError:
                    observed = False
            passed = observed is True
            reason = "UTF-8 text containment checked"
        elif condition.kind == "JSON_POINTER_EQUALS":
            if not isinstance(condition.expected, dict) or set(condition.expected) != {"pointer", "value"}:
                raise ValidationError("JSON_POINTER_EQUALS expected must contain pointer and value")
            data = self._read(path)
            if data is None:
                observed = None
            else:
                try:
                    current: Any = json.loads(data.decode("utf-8"))
                    pointer = condition.expected["pointer"]
                    if pointer == "":
                        observed = current
                    else:
                        if not isinstance(pointer, str) or not pointer.startswith("/"):
                            raise ValidationError("JSON pointer must be empty or start with /")
                        for token in pointer[1:].split("/"):
                            token = token.replace("~1", "/").replace("~0", "~")
                            current = current[int(token)] if isinstance(current, list) else current[token]
                        observed = current
                    passed = observed == condition.expected["value"]
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
                    observed = None
                    passed = False
            reason = "JSON pointer value compared"
        else:  # ConditionSpec already validates; keep fail-closed.
            raise ValidationError(f"unsupported condition kind: {condition.kind}")
        return ConditionResult(condition=condition.to_dict(), passed=passed, observed=observed, reason=reason)

    def check_conditions(self, conditions: Iterable[ConditionSpec]) -> tuple[ConditionResult, ...]:
        return tuple(self.evaluate_condition(item) for item in conditions)

    def execute(self, action: ActionRequest) -> ExecutionResult:
        path = self._resolve(action.target, create_parents=action.kind != ActionKind.FILE_DELETE)
        before = self._read(path)
        before_digest = self._digest(before)
        if action.expected_before_digest is not None and action.expected_before_digest != before_digest:
            raise IntegrityError("target preimage digest does not match action expectation")
        mutation_applied = False
        rolled_back = False
        rollback_digest = None
        after_digest = before_digest
        condition_results: tuple[ConditionResult, ...] = ()
        error: str | None = None
        try:
            if action.kind == ActionKind.FILE_WRITE:
                desired = (action.content or "").encode("utf-8")
                if desired != before:
                    self._atomic_write(path, desired)
                    mutation_applied = True
            elif action.kind == ActionKind.FILE_APPEND:
                desired = (before or b"") + (action.content or "").encode("utf-8")
                if desired != before:
                    self._atomic_write(path, desired)
                    mutation_applied = True
            elif action.kind == ActionKind.FILE_DELETE:
                if path.exists():
                    if not path.is_file() or path.is_symlink():
                        raise ValidationError("delete target must be a regular file")
                    path.unlink()
                    directory_fd = os.open(path.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                    mutation_applied = True
            else:
                raise ValidationError("unsupported action kind")
            after = self._read(path)
            after_digest = self._digest(after)
            condition_results = self.check_conditions(action.postconditions)
            if not all(item.passed for item in condition_results):
                raise PostconditionError("one or more required postconditions failed")
        except Exception as exc:
            # Persist a bounded reason code, not raw exception text that may
            # contain paths, provider payloads, or other sensitive context.
            error = type(exc).__name__
            if mutation_applied:
                try:
                    if before is None:
                        if path.exists():
                            path.unlink()
                    else:
                        self._atomic_write(path, before)
                    rolled_back = True
                    rollback_digest = self._digest(self._read(path))
                except Exception as rollback_exc:
                    error += f";ROLLBACK_FAILED:{type(rollback_exc).__name__}"
                    rolled_back = False
            if not isinstance(exc, PostconditionError):
                # Authorization/preimage and target safety errors should propagate before a mutation.
                if not mutation_applied:
                    raise
        return ExecutionResult(
            action_digest=action.digest,
            target=action.target,
            before_digest=before_digest,
            after_digest=after_digest,
            postcondition_results=condition_results,
            postconditions_passed=bool(condition_results) and all(item.passed for item in condition_results),
            rolled_back=rolled_back,
            rollback_digest=rollback_digest,
            mutation_applied=mutation_applied,
            error=error,
        )
