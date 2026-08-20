"""Fail-closed GDW storage preparation and supervised outbox draining."""

import json
import os
import runpy
import sqlite3
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from gdw_proofs import (
    export_proof_payload,
    export_receipt_projection,
    sha256_json,
)
from gdw_workspace import GDWWorkspace


if __name__ == "__main__":
    # Let route modules import the same stateful module while this file is the
    # process entry point.
    sys.modules.setdefault("gdw_runtime", sys.modules[__name__])


ALLOWED_JOURNAL_MODES = {"DELETE", "WAL"}
ALLOWED_SYNCHRONOUS_MODES = {"FULL", "NORMAL"}
_STATE_LOCK = threading.RLock()
_STATE: dict[str, Any] = {
    "startup_state": "NOT_RUN",
    "evidence_label": "UNAVAILABLE",
    "drain": {
        "enabled": False,
        "running": False,
        "last_outcome": "NOT_RUN",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "last_report": None,
        "run_generation_id": None,
        "success_run_generation_id": None,
        "success_database_generation_id": None,
        "max_staleness_seconds": None,
    },
}


class GDWRuntimeError(RuntimeError):
    """Fail-closed GDW production-runtime configuration error."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enabled(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(
    value: Optional[str],
    *,
    default: int,
    minimum: int,
    maximum: int,
    name: str,
) -> int:
    try:
        parsed = int(value) if value not in (None, "") else default
    except (TypeError, ValueError) as exc:
        raise GDWRuntimeError(f"{name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise GDWRuntimeError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return parsed


def _path_within(path: Path, root: Path, *, name: str) -> Path:
    candidate = path.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GDWRuntimeError(
            f"{name} must be contained by required mount {root}"
        ) from exc
    return candidate


def _verify_writable_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    handle, probe = tempfile.mkstemp(prefix=".gdw-write-probe-", dir=path)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(b"ok")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        Path(probe).unlink(missing_ok=True)


def storage_contract(
    environ: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Resolve and validate the declared GDW storage contract without writes."""

    values = os.environ if environ is None else environ
    database = Path(
        values.get("GDW_DB_PATH", "output/gdw/gdw.sqlite3")
    ).resolve()
    proof_dir = Path(
        values.get("GDW_PROOF_DIR", "output/proofs")
    ).resolve()
    receipt_dir = Path(
        values.get("GDW_RECEIPT_PROJECTION_DIR", "output/gdw/receipts")
    ).resolve()
    required_mount_text = (values.get("GDW_REQUIRED_MOUNT") or "").strip()
    persistent_required = _enabled(
        values.get("GDW_REQUIRE_PERSISTENT_STORAGE")
    )
    journal_mode = (
        values.get("GDW_SQLITE_JOURNAL") or "WAL"
    ).strip().upper()
    synchronous = (
        values.get("GDW_SQLITE_SYNCHRONOUS") or "NORMAL"
    ).strip().upper()
    proof_export_mode = (
        values.get("GDW_PROOF_EXPORT_MODE") or "outbox"
    ).strip().lower()

    if journal_mode not in ALLOWED_JOURNAL_MODES:
        raise GDWRuntimeError(
            "GDW_SQLITE_JOURNAL must be one of "
            + ",".join(sorted(ALLOWED_JOURNAL_MODES))
        )
    if synchronous not in ALLOWED_SYNCHRONOUS_MODES:
        raise GDWRuntimeError(
            "GDW_SQLITE_SYNCHRONOUS must be one of "
            + ",".join(sorted(ALLOWED_SYNCHRONOUS_MODES))
        )
    if proof_export_mode != "outbox":
        raise GDWRuntimeError(
            "GDW_PROOF_EXPORT_MODE must be 'outbox'; synchronous export "
            "is not transaction-safe"
        )
    if persistent_required and not required_mount_text:
        raise GDWRuntimeError(
            "GDW_REQUIRED_MOUNT is required when persistent storage is required"
        )

    mount: Optional[Path] = None
    mount_verified = False
    if required_mount_text:
        mount = Path(required_mount_text).resolve()
        database = _path_within(database, mount, name="GDW_DB_PATH")
        proof_dir = _path_within(proof_dir, mount, name="GDW_PROOF_DIR")
        receipt_dir = _path_within(
            receipt_dir,
            mount,
            name="GDW_RECEIPT_PROJECTION_DIR",
        )
        mount_verified = os.path.ismount(str(mount))
        if not mount_verified:
            raise GDWRuntimeError(
                f"required GDW storage mount is not attached: {mount}"
            )
    if persistent_required and journal_mode != "DELETE":
        raise GDWRuntimeError(
            "persistent GDW storage requires GDW_SQLITE_JOURNAL=DELETE"
        )

    return {
        "persistence_required": persistent_required,
        "required_mount": str(mount) if mount else None,
        "mount_verified": mount_verified,
        "database_path": str(database),
        "proof_dir": str(proof_dir),
        "receipt_projection_dir": str(receipt_dir),
        "journal_mode_requested": journal_mode,
        "synchronous_requested": synchronous,
        "proof_export_mode": proof_export_mode,
    }


def prepare_runtime(
    environ: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Verify durable paths, initialise SQLite, and select the declared journal."""

    contract = storage_contract(environ)
    database = Path(contract["database_path"])
    proof_dir = Path(contract["proof_dir"])
    receipt_dir = Path(contract["receipt_projection_dir"])

    try:
        _verify_writable_directory(database.parent)
        _verify_writable_directory(proof_dir)
        _verify_writable_directory(receipt_dir)
        workspace = GDWWorkspace(
            str(database),
            namespace=(os.environ.get("GDW_NAMESPACE") or "a11oy"),
            owner_id=(
                os.environ.get("GDW_SERVICE_OWNER_ID") or "gdw-runtime"
            ),
            production=False,
        )
        connection = sqlite3.connect(str(database), timeout=30)
        try:
            selected = connection.execute(
                f"PRAGMA journal_mode={contract['journal_mode_requested']}"
            ).fetchone()[0]
            selected = str(selected).upper()
            if selected != contract["journal_mode_requested"]:
                raise GDWRuntimeError(
                    "SQLite journal mode mismatch: requested "
                    f"{contract['journal_mode_requested']}, observed {selected}"
                )
            connection.execute(
                f"PRAGMA synchronous={contract['synchronous_requested']}"
            )
            observed_synchronous = int(
                connection.execute("PRAGMA synchronous").fetchone()[0]
            )
            integrity = str(
                connection.execute("PRAGMA integrity_check").fetchone()[0]
            )
            if integrity != "ok":
                raise GDWRuntimeError(
                    f"GDW SQLite integrity check failed: {integrity}"
                )
        finally:
            connection.close()
        legacy_link_failures_requeued = (
            workspace.requeue_legacy_link_failures(now=_now())
        )
        observed = {
            **contract,
            "journal_mode_observed": selected,
            "synchronous_observed": observed_synchronous,
            "sqlite_integrity": integrity,
            "schema_version": workspace.schema_version(),
            "database_generation_id": workspace.database_generation_id,
            "workspace_path": str(workspace.path),
            "legacy_link_failures_requeued": (
                legacy_link_failures_requeued
            ),
        }
    except GDWRuntimeError:
        raise
    except Exception as exc:
        raise GDWRuntimeError(
            f"GDW persistent runtime preparation failed: {type(exc).__name__}"
        ) from exc

    with _STATE_LOCK:
        _STATE.update(
            {
                "startup_state": "READY",
                "evidence_label": "VERIFIED",
                "storage": observed,
                "prepared_at": _now(),
                "error": None,
            }
        )
    return observed


def _verify_effect_binding(
    workspace: GDWWorkspace,
    row: Mapping[str, Any],
) -> None:
    errors = workspace.effect_binding_errors_for_row(dict(row))
    if errors:
        raise ValueError("invalid effect binding: " + ",".join(errors))


def _verify_legacy_proof_binding(
    workspace: GDWWorkspace,
    row: Mapping[str, Any],
) -> None:
    payload = row["payload"]
    claimed_digest = str(payload.get("payload_sha256") or "")
    unsigned_payload = dict(payload)
    unsigned_payload.pop("payload_sha256", None)
    if row["proposal_id"] != payload.get("proposal_id"):
        raise ValueError("legacy proof proposal binding is invalid")
    if row["payload_sha256"] != claimed_digest:
        raise ValueError("legacy proof row digest is invalid")
    if claimed_digest != sha256_json(unsigned_payload):
        raise ValueError("legacy proof payload digest is invalid")
    for field, expected in (
        ("namespace", row["namespace"]),
        ("owner_id", row["owner_id"]),
    ):
        if field in payload and payload[field] != expected:
            raise ValueError(f"legacy proof {field} binding is invalid")
    if (
        "database_generation_id" in payload
        and payload["database_generation_id"]
        != workspace.database_generation_id
    ):
        raise ValueError("legacy proof database generation binding is invalid")


def _export_effect(
    workspace: GDWWorkspace,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    _verify_effect_binding(workspace, row)
    artifact_id = str(row["intent_sha256"])
    if row["kind"] == "proof_export":
        return export_proof_payload(
            row["payload"],
            artifact_id=artifact_id,
            owner_id=str(row["owner_id"]),
        )
    if row["kind"] == "receipt_projection":
        return export_receipt_projection(
            row["payload"],
            artifact_id,
            owner_id=str(row["owner_id"]),
        )
    raise ValueError(f"unsupported effect kind: {row['kind']}")


def drain_once(
    *,
    limit: int = 100,
    lease_seconds: int = 300,
    worker_id: Optional[str] = None,
    workspace: Optional[GDWWorkspace] = None,
) -> dict[str, Any]:
    """Run one bounded drain pass and leave failed rows retryable."""

    bounded = _bounded_int(
        str(limit), default=100, minimum=1, maximum=1000, name="limit"
    )
    lease = _bounded_int(
        str(lease_seconds),
        default=300,
        minimum=1,
        maximum=3600,
        name="lease_seconds",
    )
    store = workspace or GDWWorkspace(
        namespace=(os.environ.get("GDW_NAMESPACE") or "a11oy"),
        owner_id=(os.environ.get("GDW_SERVICE_OWNER_ID") or "gdw-runtime"),
    )
    owner = worker_id or f"gdw-drain-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    exported = 0
    failed = 0
    errors = []
    garbage_collected = {
        "sessions_tombstoned": 0,
        "requests_tombstoned": 0,
        "effects_compacted": 0,
        "proofs_compacted": 0,
        "tombstones_purged": 0,
    }
    identities = (
        [(store.namespace, store.owner_id)]
        if workspace is not None
        else store.lifecycle_identities()
    )

    for namespace, owner_id in identities:
        remaining = bounded - exported - failed
        if remaining <= 0:
            break
        for row in store.pending_proofs(
            remaining,
            namespace=namespace,
            owner_id=owner_id,
        ):
            try:
                _verify_legacy_proof_binding(store, row)
                artifact = export_proof_payload(
                    row["payload"],
                    artifact_id=row["payload_sha256"],
                    owner_id=owner_id,
                )
                artifact.update(
                    {
                        "migration_status": "LEGACY_PROOF_PRESERVED",
                        "source_payload_sha256": row["payload_sha256"],
                    }
                )
                store.mark_proof_exported(
                    row["proposal_id"],
                    artifact,
                    _now(),
                    expected_payload=row["payload"],
                    expected_payload_sha256=row["payload_sha256"],
                    namespace=namespace,
                    owner_id=owner_id,
                )
                exported += 1
            except Exception as exc:
                failed += 1
                errors.append(f"legacy:{type(exc).__name__}")
            if exported + failed >= bounded:
                break

        remaining = bounded - exported - failed
        if remaining <= 0:
            break
        rows = store.claim_effects(
            owner,
            limit=remaining,
            lease_seconds=lease,
            namespace=namespace,
            owner_id=owner_id,
        )
        for row in rows:
            try:
                store.assert_effect_claim(
                    row["idempotency_key"],
                    owner,
                    row["claim_generation"],
                    namespace=namespace,
                    owner_id=owner_id,
                )
                artifact = _export_effect(store, row)
                store.mark_effect_exported(
                    row["idempotency_key"],
                    owner,
                    row["claim_generation"],
                    artifact,
                    _now(),
                    namespace=namespace,
                    owner_id=owner_id,
                )
                exported += 1
            except Exception as exc:
                try:
                    store.release_effect(
                        row["idempotency_key"],
                        owner,
                        row["claim_generation"],
                        f"{type(exc).__name__}: {str(exc)[:240]}",
                        namespace=namespace,
                        owner_id=owner_id,
                    )
                except RuntimeError:
                    errors.append(f"{row['kind']}:CLAIM_LOST")
                failed += 1
                errors.append(f"{row['kind']}:{type(exc).__name__}")

        collected = store.collect_garbage(
            limit=bounded,
            namespace=namespace,
            owner_id=owner_id,
        )
        for key in garbage_collected:
            garbage_collected[key] += collected[key]

    integrity = store.integrity(global_scope=True)
    return {
        "attempted": exported + failed,
        "exported": exported,
        "failed": failed,
        "pending_effects": integrity["pending_effects"],
        "claimed_effects": integrity["claimed_effects"],
        "dead_letter_effects": integrity["dead_letter_effects"],
        "legacy_pending_proofs": integrity["pending_proofs"],
        "sqlite_integrity": integrity["sqlite_integrity"],
        "invalid_effect_bindings": integrity["invalid_effect_bindings"],
        "invalid_exported_artifacts": integrity[
            "invalid_exported_artifacts"
        ],
        "garbage_collected": garbage_collected,
        "errors": errors,
    }


def _set_drain_state(**values: Any) -> None:
    with _STATE_LOCK:
        drain = dict(_STATE["drain"])
        drain.update(values)
        _STATE["drain"] = drain


class OutboxSupervisor:
    """Single-process bounded outbox worker with retry backoff."""

    def __init__(
        self,
        *,
        enabled: bool,
        interval_seconds: int,
        retry_max_seconds: int,
        batch_size: int,
        lease_seconds: int,
    ) -> None:
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        self.retry_max_seconds = retry_max_seconds
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.worker_id = f"gdw-supervisor-{os.getpid()}-{uuid.uuid4().hex[:12]}"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def from_environment(cls) -> "OutboxSupervisor":
        return cls(
            enabled=_enabled(os.environ.get("GDW_OUTBOX_ENABLED")),
            interval_seconds=_bounded_int(
                os.environ.get("GDW_OUTBOX_INTERVAL_SECONDS"),
                default=5,
                minimum=1,
                maximum=3600,
                name="GDW_OUTBOX_INTERVAL_SECONDS",
            ),
            retry_max_seconds=_bounded_int(
                os.environ.get("GDW_OUTBOX_RETRY_MAX_SECONDS"),
                default=60,
                minimum=1,
                maximum=3600,
                name="GDW_OUTBOX_RETRY_MAX_SECONDS",
            ),
            batch_size=_bounded_int(
                os.environ.get("GDW_OUTBOX_BATCH_SIZE"),
                default=100,
                minimum=1,
                maximum=1000,
                name="GDW_OUTBOX_BATCH_SIZE",
            ),
            lease_seconds=_bounded_int(
                os.environ.get("GDW_OUTBOX_LEASE_SECONDS"),
                default=300,
                minimum=1,
                maximum=3600,
                name="GDW_OUTBOX_LEASE_SECONDS",
            ),
        )

    def start(self) -> None:
        _set_drain_state(enabled=self.enabled)
        if not self.enabled:
            _set_drain_state(last_outcome="DISABLED")
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="gdw-outbox-supervisor",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        run_generation_id = uuid.uuid4().hex
        with _STATE_LOCK:
            database_generation_id = str(
                (_STATE.get("storage") or {}).get("database_generation_id") or ""
            )
        _set_drain_state(
            running=True,
            worker_id=self.worker_id,
            last_outcome="STARTING",
            last_attempt_at=None,
            last_success_at=None,
            last_error=None,
            last_report=None,
            run_generation_id=run_generation_id,
            success_run_generation_id=None,
            success_database_generation_id=None,
            max_staleness_seconds=max(30, self.interval_seconds * 3),
        )
        delay = 0
        retry_delay = self.interval_seconds
        try:
            while not self._stop.wait(delay):
                attempted_at = _now()
                _set_drain_state(last_attempt_at=attempted_at)
                try:
                    report = drain_once(
                        limit=self.batch_size,
                        lease_seconds=self.lease_seconds,
                        worker_id=self.worker_id,
                    )
                    terminal_failure = (
                        report["dead_letter_effects"]
                        or report["sqlite_integrity"] != "ok"
                        or report["invalid_effect_bindings"]
                        or report["invalid_exported_artifacts"]
                    )
                    retryable_failure = (
                        report["failed"]
                        or report["legacy_pending_proofs"]
                    )
                    pending_work = report["pending_effects"]
                    if terminal_failure:
                        delay = self.retry_max_seconds
                        _set_drain_state(
                            last_outcome="FAILED",
                            last_error=(
                                "bounded drain pass reported terminal "
                                "integrity or dead-letter failures"
                            ),
                            last_report=report,
                        )
                    elif retryable_failure:
                        retry_delay = min(
                            self.retry_max_seconds,
                            max(self.interval_seconds, retry_delay * 2),
                        )
                        delay = retry_delay
                        _set_drain_state(
                            last_outcome="RETRY_SCHEDULED",
                            last_error=(
                                "bounded drain pass remains non-quiescent"
                            ),
                            last_report=report,
                        )
                    elif pending_work:
                        retry_delay = self.interval_seconds
                        delay = self.interval_seconds
                        _set_drain_state(
                            last_outcome="RETRY_SCHEDULED",
                            last_error=(
                                "bounded drain pass remains non-quiescent"
                            ),
                            last_report=report,
                        )
                    else:
                        retry_delay = self.interval_seconds
                        delay = self.interval_seconds
                        _set_drain_state(
                            last_outcome="SUCCEEDED",
                            last_success_at=_now(),
                            last_error=None,
                            last_report=report,
                            success_run_generation_id=run_generation_id,
                            success_database_generation_id=(
                                database_generation_id
                            ),
                        )
                except Exception as exc:
                    retry_delay = min(
                        self.retry_max_seconds,
                        max(self.interval_seconds, retry_delay * 2),
                    )
                    delay = retry_delay
                    _set_drain_state(
                        last_outcome="RETRY_SCHEDULED",
                        last_error=f"{type(exc).__name__}: {str(exc)[:240]}",
                    )
        finally:
            _set_drain_state(running=False)

    def stop(self, timeout_seconds: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(0.0, timeout_seconds))
        _set_drain_state(running=False)


def runtime_health() -> dict[str, Any]:
    """Return secret-free observed inputs for the GDW health route."""

    with _STATE_LOCK:
        return json.loads(json.dumps(_STATE))


def main() -> int:
    try:
        prepare_runtime()
    except Exception as exc:
        with _STATE_LOCK:
            _STATE.update(
                {
                    "startup_state": "BLOCKED",
                    "evidence_label": "VERIFIED",
                    "error": f"{type(exc).__name__}: {str(exc)[:240]}",
                }
            )
        raise

    supervisor = OutboxSupervisor.from_environment()
    supervisor.start()
    try:
        runpy.run_path(
            str(Path(__file__).with_name("serve.py")),
            run_name="__main__",
        )
    finally:
        supervisor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
