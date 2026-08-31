"""Structured theorem-input export for asynchronous Lean checking."""

import ctypes
import errno
import hashlib
import json
import os
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts
    fcntl = None


_ARTIFACT_QUOTA_LOCK = threading.RLock()
_TRANSIENT_LINK_ERRNOS = {
    errno.ENOTSUP,
    getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
}
_UNSUPPORTED_DIRECTORY_FSYNC_ERRNOS = {
    errno.ENOSYS,
    errno.EINVAL,
    errno.ENOTSUP,
    getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
}
_LINK_MAX_ATTEMPTS = 61
_LINK_RETRY_SECONDS = 0.5
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_existing_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno == getattr(errno, "ELOOP", None):
            raise FileExistsError(
                "existing GDW artifact is not a regular file"
            ) from None
        raise
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise FileExistsError(
                "existing GDW artifact is not a regular file"
            )
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in _UNSUPPORTED_DIRECTORY_FSYNC_ERRNOS:
                raise
    finally:
        os.close(descriptor)


@contextmanager
def _owner_publication_lock(owner_root: Path) -> Iterator[None]:
    """Serialize publishers across processes on the durable POSIX mount."""

    if fcntl is None:
        yield
        return
    lock_path = owner_root / ".gdw-publication.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise FileExistsError(
                "GDW publication lock is not a regular file"
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _rename_noreplace(staging: str, destination: Path) -> None:
    """Atomically publish without replacing an existing destination."""

    if os.name != "posix":
        raise OSError(
            errno.ENOTSUP,
            "atomic no-replace rename requires a POSIX runtime",
        )
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except (AttributeError, OSError):
        raise OSError(
            errno.ENOTSUP,
            "atomic no-replace rename is unavailable",
        ) from None
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        _AT_FDCWD,
        os.fsencode(staging),
        _AT_FDCWD,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno() or errno.EIO
    if error_number == errno.EEXIST:
        raise FileExistsError(
            error_number,
            os.strerror(error_number),
            os.fspath(destination),
        )
    raise OSError(
        error_number,
        os.strerror(error_number),
        os.fspath(destination),
    )


def _publish_with_locked_rename(
    staging: str,
    destination: Path,
    encoded: bytes,
    owner_root: Path,
) -> tuple[bool, str]:
    """Atomically publish when the durable mount rejects hard links."""

    if fcntl is None:
        raise OSError(
            errno.ENOTSUP,
            "atomic rename fallback requires POSIX advisory locking",
        )
    if os.path.lexists(destination):
        if _read_existing_regular(destination) != encoded:
            raise FileExistsError(
                "refusing to overwrite a concurrently created "
                "non-identical GDW artifact"
            )
        return True, "REUSED"
    try:
        _rename_noreplace(staging, destination)
    except FileExistsError:
        if _read_existing_regular(destination) != encoded:
            raise FileExistsError(
                "refusing to overwrite a concurrently created "
                "non-identical GDW artifact"
            ) from None
        return True, "REUSED"
    _fsync_directory(owner_root)
    return False, "ATOMIC_RENAME_LOCKED"


def build_proof_payload(
    proposal_id: str,
    request_id: str,
    request_digest: str,
    namespace: str,
    owner_id: str,
    database_generation_id: str,
    step: int,
    before_hash: str,
    after_hash: str,
    decision: str,
    scheduler_mode: str,
    receipt_hash: str,
    dry_run: bool,
    governance: Dict[str, Any],
) -> Dict[str, Any]:
    mutates = decision == "ACCEPT" and not dry_run
    governance_digest = sha256_json(governance)
    payload = {
        "schema": "szl.gdw.proof-input/v1",
        "proposal_id": proposal_id,
        "request_id": request_id,
        "request_digest": request_digest,
        "namespace": namespace,
        "owner_id": owner_id,
        "database_generation_id": database_generation_id,
        "step_id": step,
        "state_before_hash": before_hash,
        "state_after_hash": after_hash,
        "decision": decision,
        "scheduler_mode": scheduler_mode,
        "delta_update_receipt_hash": receipt_hash,
        "governance": governance,
        "governance_evidence_sha256": governance_digest,
        "invariants": {
            "step_nonnegative": step >= 0,
            "accepted_write_has_receipt": (not mutates) or bool(receipt_hash),
            "accepted_write_has_governance_allow": (
                (not mutates) or governance.get("allowed") is True
            ),
            "non_mutating_preserves_state": mutates or before_hash == after_hash,
            "scheduler_mode_valid": scheduler_mode
            in {"kda_local", "laguna_hybrid", "mla_global"},
        },
        "formal_status": "NOT_RUN",
    }
    payload["payload_sha256"] = sha256_json(payload)
    return payload


def _export_json_artifact_unlocked(
    root: Path,
    filename: str,
    payload: Dict[str, Any],
    owner_id: str,
) -> Dict[str, Any]:
    if type(owner_id) is not str or not owner_id:
        raise ValueError("owner_id is required for artifact isolation")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    owner_scope = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:32]
    owner_candidate = root / owner_scope
    owner_candidate.mkdir(parents=True, exist_ok=True)
    owner_root = owner_candidate.resolve()
    if owner_root.parent != root or owner_root.name != owner_scope:
        raise ValueError("artifact owner scope escapes the configured root")
    destination = owner_root / filename
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    expected_sha256 = hashlib.sha256(encoded).hexdigest()
    with _owner_publication_lock(owner_root):
        if os.path.lexists(destination):
            if _read_existing_regular(destination) != encoded:
                raise FileExistsError(
                    "refusing to overwrite an existing non-identical "
                    "GDW artifact"
                )
            _fsync_directory(owner_root)
            return {
                "status": "EXPORTED",
                "path": str(destination),
                "sha256": expected_sha256,
                "reused": True,
                "immutable": True,
                "owner_scope": owner_scope,
                "publication_mode": "REUSED",
            }
        owner_limit = _bounded_artifact_limit(
            "GDW_OWNER_MAX_ARTIFACTS",
            default=10_000,
            maximum=100_000,
        )
        global_limit = _bounded_artifact_limit(
            "GDW_GLOBAL_MAX_ARTIFACTS",
            default=100_000,
            maximum=1_000_000,
        )
        if global_limit < owner_limit:
            raise ValueError(
                "GDW_GLOBAL_MAX_ARTIFACTS must be at least "
                "GDW_OWNER_MAX_ARTIFACTS"
            )
        if sum(1 for _ in owner_root.glob("*.json")) >= owner_limit:
            raise RuntimeError("per-owner artifact quota exceeded")
        if sum(1 for _ in root.glob("*/*.json")) >= global_limit:
            raise RuntimeError("global artifact quota exceeded")
        # A unique stage is owned only by this publisher. Process death can
        # leave that hidden file unreferenced, but no retry or replica may
        # delete an unknown concurrent stage or expose it as final JSON.
        handle, staging = tempfile.mkstemp(
            prefix=".gdw-artifact-",
            suffix=".tmp",
            dir=owner_root,
        )
        reused = False
        publication_mode = "HARD_LINK"
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(_LINK_MAX_ATTEMPTS):
                try:
                    os.link(staging, destination)
                except FileExistsError:
                    if _read_existing_regular(destination) != encoded:
                        raise FileExistsError(
                            "refusing to overwrite a concurrently created "
                            "non-identical GDW artifact"
                        )
                    reused = True
                    publication_mode = "REUSED"
                    break
                except OSError as exc:
                    if exc.errno not in _TRANSIENT_LINK_ERRNOS:
                        raise
                    if attempt + 1 >= _LINK_MAX_ATTEMPTS:
                        reused, publication_mode = (
                            _publish_with_locked_rename(
                                staging,
                                destination,
                                encoded,
                                owner_root,
                            )
                        )
                        break
                    publication_mode = "HARD_LINK_AFTER_FLUSH"
                    time.sleep(_LINK_RETRY_SECONDS)
                else:
                    break
            _fsync_directory(owner_root)
        finally:
            try:
                os.unlink(staging)
            except FileNotFoundError:
                pass
    return {
        "status": "EXPORTED",
        "path": str(destination),
        "sha256": expected_sha256,
        "reused": reused,
        "immutable": True,
        "owner_scope": owner_scope,
        "publication_mode": publication_mode,
    }


def _bounded_artifact_limit(name: str, *, default: int, maximum: int) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw not in (None, "") else default
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _export_json_artifact(
    root: Path,
    filename: str,
    payload: Dict[str, Any],
    owner_id: str,
) -> Dict[str, Any]:
    with _ARTIFACT_QUOTA_LOCK:
        return _export_json_artifact_unlocked(
            root,
            filename,
            payload,
            owner_id,
        )


def _validate_artifact_id(artifact_id: str) -> None:
    if (
        len(artifact_id) != 64
        or any(ch not in "0123456789abcdef" for ch in artifact_id)
    ):
        raise ValueError("artifact_id must be a lowercase SHA-256 digest")


def export_proof_payload(
    payload: Dict[str, Any],
    *,
    artifact_id: str | None = None,
    owner_id: str | None = None,
) -> Dict[str, Any]:
    root = Path(os.environ.get("GDW_PROOF_DIR", "output/proofs")).resolve()
    proposal_id = payload["proposal_id"]
    if not proposal_id or any(ch not in "0123456789abcdef" for ch in proposal_id):
        raise ValueError("proposal_id is not a canonical lowercase hexadecimal id")
    claimed_digest = payload.get("payload_sha256")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("payload_sha256", None)
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("proof payload_sha256 does not match canonical payload")
    resolved_artifact_id = artifact_id or claimed_digest
    _validate_artifact_id(resolved_artifact_id)
    artifact = _export_json_artifact(
        root,
        f"{resolved_artifact_id}.json",
        payload,
        owner_id or str(payload.get("owner_id") or ""),
    )
    artifact["artifact_identity"] = resolved_artifact_id
    artifact.update({"status": "INPUT_EXPORTED", "formal_status": "NOT_RUN"})
    return artifact


def export_receipt_projection(
    payload: Dict[str, Any],
    artifact_id: str,
    owner_id: str | None = None,
) -> Dict[str, Any]:
    root = Path(
        os.environ.get("GDW_RECEIPT_PROJECTION_DIR", "output/gdw/receipts")
    ).resolve()
    _validate_artifact_id(artifact_id)
    claimed_digest = payload.get("receipt_hash")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("receipt_hash", None)
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("receipt_hash does not match canonical receipt")
    artifact = _export_json_artifact(
        root,
        f"{artifact_id}.json",
        payload,
        owner_id or str(payload.get("owner_id") or ""),
    )
    artifact["artifact_identity"] = artifact_id
    artifact.update(
        {
            "status": "RECEIPT_PROJECTED",
            "receipt_status": "UNSIGNED_ATOMIC",
        }
    )
    return artifact
