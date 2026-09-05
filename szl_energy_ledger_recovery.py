#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cross-process serialization and forensic generation handling for SZL Energy.

The module is deliberately pure stdlib and Linux-first because the production
A11oy Space is Linux.  It never repairs a malformed chain in place.  It takes a
bounded advisory file lock, reads every retained byte strictly, and moves an
invalid generation into a digest-addressed quarantine directory before the
caller creates an explicit reset receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class LedgerLockTimeout(RuntimeError):
    """The cross-process writer lease could not be acquired in time."""


class LedgerLockUnavailable(RuntimeError):
    """The host cannot provide the required cross-process lock primitive."""


@dataclass(frozen=True)
class StrictRead:
    records: tuple[dict[str, Any], ...]
    files: tuple[dict[str, Any], ...]
    errors: tuple[dict[str, Any], ...]


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def retained_segment_paths(path: str, backup_count: int) -> list[Path]:
    """Return existing retained segments in oldest-to-newest record order."""

    base = Path(path)
    found: list[Path] = []
    for number in range(max(1, int(backup_count)), 0, -1):
        candidate = Path(f"{path}.{number}")
        if candidate.exists():
            found.append(candidate)
    if base.exists():
        found.append(base)
    return found


def strict_read(path: str, backup_count: int) -> StrictRead:
    """Read retained JSONL without skipping malformed, partial, or non-object rows."""

    records: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for segment in retained_segment_paths(path, backup_count):
        try:
            raw = segment.read_bytes()
        except OSError as exc:
            errors.append(
                {
                    "file": segment.name,
                    "line": None,
                    "reason": f"read:{type(exc).__name__}",
                }
            )
            continue
        files.append(
            {
                "path": str(segment),
                "name": segment.name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        if raw and not raw.endswith(b"\n"):
            errors.append(
                {
                    "file": segment.name,
                    "line": None,
                    "reason": "partial-final-line",
                }
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(
                {
                    "file": segment.name,
                    "line": None,
                    "reason": "invalid-utf8",
                }
            )
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(
                    {
                        "file": segment.name,
                        "line": line_number,
                        "reason": "invalid-json",
                        "column": exc.colno,
                    }
                )
                continue
            if not isinstance(value, dict):
                errors.append(
                    {
                        "file": segment.name,
                        "line": line_number,
                        "reason": "row-not-object",
                    }
                )
                continue
            records.append(value)
    return StrictRead(tuple(records), tuple(files), tuple(errors))


@contextmanager
def exclusive_writer_lock(path: str, timeout_s: float = 5.0) -> Iterator[dict[str, Any]]:
    """Take a bounded POSIX advisory lock on ``<ledger>.writer.lock``.

    Failure is explicit.  There is no process-local or best-effort fallback because
    that would recreate the rolling-restart fork this primitive exists to prevent.
    """

    if os.name != "posix":
        raise LedgerLockUnavailable("POSIX flock is required for the production ledger")
    try:
        import fcntl
    except Exception as exc:  # pragma: no cover - production is Linux
        raise LedgerLockUnavailable("fcntl is unavailable") from exc

    lock_path = Path(f"{path}.writer.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    started = time.monotonic()
    deadline = started + max(0.01, float(timeout_s))
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LedgerLockTimeout(
                        f"writer lock acquisition exceeded {float(timeout_s):.3f}s"
                    )
                time.sleep(0.01)
        yield {
            "path": str(lock_path),
            "wait_ms": round((time.monotonic() - started) * 1000.0, 3),
        }
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def quarantine_generation(
    path: str,
    backup_count: int,
    strict: StrictRead,
    prior_verdict: dict[str, Any],
    cause: str,
) -> dict[str, Any]:
    """Move every retained segment into a digest-bound forensic generation."""

    subject = {
        "schema": "szl.energy-ledger-quarantine-subject/v1",
        "cause": cause,
        "files": [
            {key: row[key] for key in ("name", "bytes", "sha256")}
            for row in strict.files
        ],
        "strict_errors": list(strict.errors),
        "prior_chain": prior_verdict,
    }
    aggregate = canonical_sha256(subject)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(f"{path}.quarantine")
    destination = root / f"{stamp}-{aggregate[:16]}"
    destination.mkdir(parents=True, exist_ok=False)

    moved: list[dict[str, Any]] = []
    for row in strict.files:
        source = Path(str(row["path"]))
        if not source.exists():
            raise RuntimeError(f"quarantine source disappeared: {source.name}")
        target = destination / source.name
        os.replace(source, target)
        moved.append(
            {
                "name": source.name,
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
        )

    manifest = {
        "schema": "szl.energy-ledger-quarantine/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "aggregate_sha256": aggregate,
        "cause": cause,
        "files": moved,
        "strict_errors": list(strict.errors),
        "prior_chain": prior_verdict,
        "record_count_recovered": len(strict.records),
    }
    manifest_path = destination / "manifest.json"
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_dir(destination)
    _fsync_dir(root)
    _fsync_dir(Path(path).parent)
    return {
        **manifest,
        "quarantine_directory": str(destination),
        "manifest_path": str(manifest_path),
    }
