#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: source-bound admission before restoring or starting either store.

The record is written by the separately admitted canonical acquisition path.
Schema validation alone is not evidence that an acquisition happened. Runtime
loads only the digest-bound record at an immutable private dataset HEAD; neither
an environment flag nor a caller-supplied local document can grant admission.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any
import uuid

import gdw_durable_source as installed_source
import gdw_durable_guard as legacy_guard
import gdw_durable_image as runtime_image

SCHEMA = "szl.gdw-durable-storage-admission/v1"
MAX_ADMISSION_BYTES = 512 * 1024
MAX_ACK_SECONDS = 60
SPACE = "SZLHOLDINGS/a11oy"
DATASET = BUCKET = "SZLHOLDINGS/szl-evidence"
REPOSITORY = "szl-holdings/a11oy"
WORKFLOW = ".github/workflows/hf-sync.yml"
OBJECT_PREFIX = "a11oy/durable-store/v1/objects"
LOCAL_PARENT = Path("/tmp/a11oy-durable-v1")
RUNTIME_SOURCE_ROOT = Path("/app")
_LABELS = ("gdw", "series_a")
_LOCK = threading.Lock()
_PARENT_LOCK_FD = None
_STARTED = False


class AdmissionBlocked(RuntimeError):
    """Only fixed non-private codes leave this boundary."""


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("ascii") + b"\n"
    except Exception:
        raise AdmissionBlocked("ADMISSION_JSON_INVALID") from None


def _shape(value: Any, fields: set[str]) -> dict:
    if type(value) is not dict or set(value) != fields:
        raise AdmissionBlocked("ADMISSION_FIELDS_INVALID")
    return value


def _fixed(value: Any, expected: Any) -> None:
    if type(value) is not type(expected) or value != expected:
        raise AdmissionBlocked("ADMISSION_FACT_UNQUALIFIED")


def _number(value: Any, minimum: int = 1, maximum: int = 2**63 - 1) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise AdmissionBlocked("ADMISSION_NUMBER_INVALID")


def _hex(value: Any, length: int = 64, *, zero: bool = False) -> None:
    if (type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is None
            or (not zero and value == "0" * length)):
        raise AdmissionBlocked("ADMISSION_IDENTITY_INVALID")


def _timestamp(value: Any) -> datetime:
    if type(value) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        raise AdmissionBlocked("ADMISSION_TIMESTAMP_INVALID")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise AdmissionBlocked("ADMISSION_TIMESTAMP_INVALID") from None


def _workflow(value: Any) -> None:
    _shape(value, {"repository", "ref", "revision", "workflow_path", "run_id", "run_attempt",
                   "job_id", "event_name", "source_admission_state", "source_admission_sha256"})
    _fixed(value["repository"], REPOSITORY)
    _fixed(value["ref"], "refs/heads/main")
    _fixed(value["workflow_path"], WORKFLOW)
    _fixed(value["source_admission_state"], "VERIFIED")
    if type(value["event_name"]) is not str or value["event_name"] not in {"push", "workflow_dispatch"}:
        raise AdmissionBlocked("ADMISSION_WORKFLOW_UNQUALIFIED")
    _hex(value["revision"], 40)
    _hex(value["source_admission_sha256"])
    for key in ("run_id", "run_attempt", "job_id"):
        _number(value[key])


def _snapshots(value: Any) -> None:
    _shape(value, set(_LABELS))
    for label in _LABELS:
        fields = {"path", "size", "sha256", "xet_hash", "generation",
                  "receipt_count", "receipt_sequence", "receipt_head_sha256"}
        if label == "series_a":
            fields.add("receipt_rows_sha256")
        item = _shape(value[label], fields)
        for key in ("sha256", "xet_hash"):
            _hex(item[key])
        _number(item["size"], maximum=256 * 1024 * 1024)
        _number(item["receipt_count"], 0, 1_000_000)
        _number(item["receipt_sequence"], 0)
        generation = item["generation"]
        if label == "series_a":
            if type(generation) is not str or not generation.startswith("store_"):
                raise AdmissionBlocked("ADMISSION_GENERATION_INVALID")
            _hex(generation[6:], 32)
            if item["receipt_sequence"] < item["receipt_count"]:
                raise AdmissionBlocked("ADMISSION_RECEIPT_CHAIN_INVALID")
        else:
            _hex(generation, 32)
            _fixed(item["receipt_sequence"], 0)
        empty = label == "series_a" and item["receipt_count"] == item["receipt_sequence"] == 0
        _hex(item["receipt_head_sha256"], zero=empty)
        if empty:
            _fixed(item["receipt_head_sha256"], "0" * 64)
        if label == "series_a":
            _hex(item["receipt_rows_sha256"])
            if empty:
                _fixed(item["receipt_rows_sha256"], hashlib.sha256(b"szl.series-a-receipt-rows/v1\n").hexdigest())
        pattern = re.escape(OBJECT_PREFIX) + r"/[0-9a-f]{32}/" + label + "-" + item["sha256"] + r"\.sqlite3"
        if type(item["path"]) is not str or re.fullmatch(pattern, item["path"]) is None:
            raise AdmissionBlocked("ADMISSION_SNAPSHOT_PATH_INVALID")


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionBlocked("ADMISSION_DUPLICATE_KEY")
        result[key] = value
    return result


def parse_admission(data: bytes) -> dict:
    """Pure, bounded, canonical metadata allowlist; no provider or filesystem I/O."""
    if type(data) is not bytes or not 1 <= len(data) <= MAX_ADMISSION_BYTES:
        raise AdmissionBlocked("ADMISSION_BOUND_INVALID")
    try:
        value = json.loads(data, object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except AdmissionBlocked:
        raise
    except Exception:
        raise AdmissionBlocked("ADMISSION_JSON_INVALID") from None
    _shape(value, {"schema", "state", "created_at", "space", "dataset", "bucket", "source",
                   "capture", "qualification", "legacy_quiescence", "legacy_guard", "provider", "runtime",
                   "snapshots", "retained_artifacts", "latency"})
    _fixed(value["schema"], SCHEMA)
    _fixed(value["state"], "QUALIFIED_CAPTURED_STATE_FOR_PRIVATE_DATASET_STORAGE")
    for key, expected in (("space", SPACE), ("dataset", DATASET), ("bucket", BUCKET)):
        _fixed(value[key], expected)
    created = _timestamp(value["created_at"])
    _workflow(value["source"])
    capture = _shape(value["capture"], {"capture_id", "source_revision", "run_id", "run_attempt",
                                        "report_sha256", "manifest_sha256", "manifest_xet_hash"})
    for key in ("run_id", "run_attempt"):
        _number(capture[key])
    _hex(capture["source_revision"], 40)
    for key in ("report_sha256", "manifest_sha256", "manifest_xet_hash"):
        _hex(capture[key])
    expected = f"{capture['run_id']}-{capture['run_attempt']}-{capture['source_revision']}-[0-9a-f]{{32}}"
    if type(capture["capture_id"]) is not str or re.fullmatch(expected, capture["capture_id"]) is None:
        raise AdmissionBlocked("ADMISSION_CAPTURE_BINDING_INVALID")
    qualification = _shape(value["qualification"], {"schema", "state", "report_sha256", "source",
        "artifact_id", "artifact_archive_sha256", "capture_report_sha256", "historical_anchor_state",
        "historical_anchor_sha256", "all_declared_stored_values_unchanged", "receipt_bytes_unchanged",
        "database_generations_unchanged", "later_acknowledged_writes_state", "logical_fingerprint_sha256", "candidates"})
    _fixed(qualification["schema"], "szl.gdw-store-recovery-qualification/v1")
    _fixed(qualification["state"], "LOGICAL_CONTINUITY_VERIFIED")
    _workflow(qualification["source"])
    _fixed(qualification["capture_report_sha256"], capture["report_sha256"])
    _fixed(qualification["historical_anchor_state"], "VERIFIED")
    # Qualifying a captured state does not establish an unobserved later history.
    _fixed(qualification["later_acknowledged_writes_state"], "NOT_ESTABLISHED")
    for key in ("all_declared_stored_values_unchanged", "receipt_bytes_unchanged", "database_generations_unchanged"):
        _fixed(qualification[key], True)
    for key in ("report_sha256", "artifact_archive_sha256", "historical_anchor_sha256"):
        _hex(qualification[key])
    _number(qualification["artifact_id"])
    _shape(qualification["logical_fingerprint_sha256"], set(_LABELS))
    for digest in qualification["logical_fingerprint_sha256"].values():
        _hex(digest)
    stopped = _shape(value["legacy_quiescence"], {"state", "space_revision", "observed_at", "source_revision",
                                                 "writer_inventory_sha256", "observation_sha256"})
    _fixed(stopped["state"], "ALL_LEGACY_WRITERS_VERIFIED_STOPPED_SPACE_PAUSED")
    _hex(stopped["space_revision"], 40)
    _fixed(stopped["source_revision"], value["source"]["revision"])
    for key in ("writer_inventory_sha256", "observation_sha256"):
        _hex(stopped[key])
    if _timestamp(stopped["observed_at"]) > created:
        raise AdmissionBlocked("ADMISSION_OBSERVATION_ORDER_INVALID")
    try:
        guarded = legacy_guard.validate_legacy_guard(value["legacy_guard"])
        _fixed(guarded["space_revision"], stopped["space_revision"])
        if _timestamp(guarded["observation"]["observed_at"]) > created:
            raise AdmissionBlocked("ADMISSION_OBSERVATION_ORDER_INVALID")
    except legacy_guard.GuardBlocked:
        raise AdmissionBlocked("ADMISSION_LEGACY_GUARD_UNQUALIFIED") from None
    provider = _shape(value["provider"], {"endpoint", "dataset_private", "bucket_private",
                                         "resource_group_observation_sha256", "audience_equivalence"})
    _fixed(provider["endpoint"], "https://huggingface.co")
    _fixed(provider["dataset_private"], True)
    _fixed(provider["bucket_private"], True)
    _fixed(provider["audience_equivalence"], "NOT_ESTABLISHED")
    _hex(provider["resource_group_observation_sha256"])
    runtime = _shape(value["runtime"], {"sdk_version", "sqlite_version", "source_manifest", "source_manifest_sha256",
                                        "base_observation"})
    _fixed(runtime["sdk_version"], "1.31.0")
    if type(runtime["sqlite_version"]) is not str or re.fullmatch(r"3\.\d{1,3}\.\d{1,3}", runtime["sqlite_version"]) is None:
        raise AdmissionBlocked("ADMISSION_SQLITE_VERSION_INVALID")
    _hex(runtime["source_manifest_sha256"])
    try:
        manifest = installed_source.validate_manifest(runtime["source_manifest"], value["source"]["revision"])
        _fixed(runtime["source_manifest_sha256"], hashlib.sha256(canonical(manifest)).hexdigest())
    except installed_source.SourceBlocked:
        raise AdmissionBlocked("ADMISSION_INSTALLED_SOURCE_INVALID") from None
    try:
        expected_base = runtime_image.validate_runtime_base_observation(
            runtime["base_observation"], value["source"]["revision"], manifest["dockerfile"]["sha256"])
    except runtime_image.RuntimeBaseBlocked:
        raise AdmissionBlocked("ADMISSION_RUNTIME_BASE_UNQUALIFIED") from None
    for key in ("run_id", "run_attempt"):
        _fixed(expected_base["execution"][key], value["source"][key])
    _fixed(runtime["sqlite_version"], expected_base["sqlite"]["python_version"])
    _fixed(guarded["native_probe"]["python_version"],
           ".".join(str(part) for part in expected_base["interpreter"]["version"]))
    _snapshots(value["snapshots"])
    _shape(qualification["candidates"], set(_LABELS))
    for label in _LABELS:
        candidate = _shape(qualification["candidates"][label], {"sha256", "size", "method", "integrity", "foreign_key_violations"})
        _fixed(candidate["sha256"], value["snapshots"][label]["sha256"])
        _fixed(candidate["size"], value["snapshots"][label]["size"])
        _fixed(candidate["integrity"], "OK")
        _fixed(candidate["foreign_key_violations"], 0)
        if type(candidate["method"]) is not str or candidate["method"] not in {
                "SQLITE_NATIVE_BACKUP", "SQLITE_VACUUM_INTO_DISPOSABLE_EVALUATION"}:
            raise AdmissionBlocked("ADMISSION_CANDIDATE_METHOD_UNQUALIFIED")
    artifacts = _shape(value["retained_artifacts"], {"state", "count", "total_bytes", "identities_sha256",
                                                    "native_bindings_state", "reconstruction"})
    _fixed(artifacts["state"], "ALL_RETAINED_OBJECTS_READBACK_VERIFIED")
    _fixed(artifacts["native_bindings_state"], "VERIFIED")
    _fixed(artifacts["reconstruction"], "RECONSTRUCTED_FROM_RETAINED_PAYLOAD")
    _number(artifacts["count"], 0, 1_000_000)
    _number(artifacts["total_bytes"], 0, 2**40)
    if (artifacts["count"] == 0) != (artifacts["total_bytes"] == 0):
        raise AdmissionBlocked("ADMISSION_ARTIFACT_SUMMARY_INVALID")
    _hex(artifacts["identities_sha256"])
    if artifacts["count"] == 0:
        _fixed(artifacts["identities_sha256"], hashlib.sha256(canonical([])).hexdigest())
    latency = _shape(value["latency"], {"scope", "runner", "run_id", "run_attempt", "sample_count", "samples_ms",
        "snapshot_sha256", "artifact_identities_sha256", "receipt_sha256", "runtime_self_check", "ack_deadline_ms", "throughput_claim"})
    _fixed(latency["scope"], "CANONICAL_ACQUISITION_FULL_PAIR_AND_ARTIFACT_UPLOAD_READBACK_RESTORE")
    _fixed(latency["runner"], "GITHUB_ACTIONS_CANONICAL_MAIN")
    _fixed(latency["run_id"], value["source"]["run_id"])
    _fixed(latency["run_attempt"], value["source"]["run_attempt"])
    _number(latency["sample_count"], 1, 20)
    if type(latency["samples_ms"]) is not list or len(latency["samples_ms"]) != latency["sample_count"]:
        raise AdmissionBlocked("ADMISSION_LATENCY_UNMEASURED")
    for elapsed in latency["samples_ms"]:
        _number(elapsed, 1, 300_000)
    _shape(latency["snapshot_sha256"], set(_LABELS))
    for label in _LABELS:
        _fixed(latency["snapshot_sha256"][label], value["snapshots"][label]["sha256"])
    _fixed(latency["artifact_identities_sha256"], artifacts["identities_sha256"])
    _hex(latency["receipt_sha256"])
    _fixed(latency["runtime_self_check"], "REQUIRED_BEFORE_INSTALL_ON_ACTUAL_HOST")
    _fixed(latency["ack_deadline_ms"], MAX_ACK_SECONDS * 1000)
    _fixed(latency["throughput_claim"], "NOT_CLAIMED")
    if canonical(value) != data:
        raise AdmissionBlocked("ADMISSION_NOT_CANONICAL")
    return json.loads(data)


def validate_bootstrap_binding(admission: dict, manifest: dict) -> None:
    """Pure cross-contract check, called before the first provider HEAD write."""
    accepted = parse_admission(canonical(admission))
    if type(manifest) is not dict:
        raise AdmissionBlocked("ADMISSION_BOOTSTRAP_SHAPE_INVALID")
    _snapshots(manifest.get("snapshots"))
    _fixed(manifest.get("kind"), "BOOTSTRAP")
    _fixed(manifest.get("epoch"), 0)
    _fixed(manifest.get("sequence"), 0)
    _fixed(manifest.get("source_revision"), accepted["source"]["revision"])
    _fixed(manifest.get("qualification_sha256"), hashlib.sha256(canonical(accepted)).hexdigest())
    _fixed(manifest.get("snapshots"), accepted["snapshots"])
    for key in ("space", "dataset", "bucket"):
        _fixed(manifest.get(key), accepted[key])


def verify_runtime(admission: dict, source_root: Path, source_revision: str, sdk_version: str) -> None:
    """Compare exact first-cutover source content and the separately named versions."""
    _hex(source_revision, 40)
    # First cutover has no reviewed unrelated-revision compatibility contract.
    _fixed(source_revision, admission["source"]["revision"])
    _fixed(sdk_version, admission["runtime"]["sdk_version"])
    _fixed(sqlite3.sqlite_version, admission["runtime"]["sqlite_version"])
    if not sys.dont_write_bytecode:
        raise AdmissionBlocked("RUNTIME_BYTECODE_WRITING_ENABLED")
    if _timestamp(admission["created_at"]) > datetime.now(timezone.utc):
        raise AdmissionBlocked("ADMISSION_FROM_FUTURE")
    try:
        result = installed_source.verify_installed_source(
            admission["runtime"]["source_manifest"], source_root, source_revision,
            runtime_install_root=installed_source.RUNTIME_INSTALL_ROOT)
        _fixed(result["manifest_sha256"], admission["runtime"]["source_manifest_sha256"])
        installed_source.install_import_policy(admission["runtime"]["source_manifest"], source_root)
    except installed_source.SourceBlocked:
        raise AdmissionBlocked("RUNTIME_INSTALLED_SOURCE_UNQUALIFIED") from None


def verify_installed_credentials(source_root: Path) -> None:
    """Native installed key/registry preflight, separate from source equality.

    No HTTP probe, signature request, key creation or credential output. The
    existing key loader runs in strict mode and the existing verifier compares
    its public half to both independent pins, retaining its documented limits.
    """
    try:
        import importlib.util
        from a11oy_signing_key import load_signing_key
        from gdw_auth import load_credential_registry
        key, public, source, _error = load_signing_key(
            dict(os.environ, A11OY_REQUIRE_PERSISTENT_SIGNING="1"))
        if key is None or not source.startswith("persistent:") or not public:
            raise AdmissionBlocked("INSTALLED_SIGNING_AUTHORITY_UNAVAILABLE")
        registry = load_credential_registry(os.environ.get("GDW_CREDENTIALS_JSON"))
        if registry.credential_count < 1:
            raise AdmissionBlocked("INSTALLED_GDW_AUTHORITY_UNAVAILABLE")
        path = source_root / "scripts/verify_installed_authority.py"
        spec = importlib.util.spec_from_file_location("_gdw_installed_authority", path)
        if spec is None or spec.loader is None:
            raise AdmissionBlocked("INSTALLED_AUTHORITY_VERIFIER_UNAVAILABLE")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)

        def public_get(url):
            if url != verifier.CANONICAL_ORIGIN + verifier.PUBLIC_KEY_ROUTE:
                raise AdmissionBlocked("UNEXPECTED_AUTHORITY_READ")
            return 200, {}, public.encode("ascii")

        report = verifier.verify_signing_authority(
            verifier.CANONICAL_ORIGIN, get=public_get,
            pinned_pem_path=source_root / verifier.PINNED_SIGNING_PUBLIC_KEY_PATH,
            static_source_path=source_root / verifier.STATIC_FALLBACK_SOURCE)
        if report.get("state") != verifier.VERIFIED_PINNED_RUNTIME_KEY:
            raise AdmissionBlocked("INSTALLED_SIGNING_AUTHORITY_UNAVAILABLE")
    except AdmissionBlocked:
        raise
    except Exception:
        raise AdmissionBlocked("INSTALLED_AUTHORITY_UNAVAILABLE") from None


class _BoundArtifacts:
    """Bind initial retained-artifact summary before the first epoch claim."""
    def __init__(self, directory: Path, publisher, expected: dict | None):
        from gdw_durable_artifacts import ArtifactCache
        self.directory = directory
        self.expected = expected
        self.records = {}

        def publish(*args):
            value = publisher(*args)
            record = _shape(value, {"path", "size", "sha256", "xet_hash"})
            old = self.records.get(record["path"])
            if old is not None and old != record:
                raise AdmissionBlocked("STARTUP_ARTIFACT_IDENTITY_CHANGED")
            self.records[record["path"]] = dict(record)
            return value

        self.cache = ArtifactCache(directory, publish)

    def prepare(self, path: Path, deadline: float):
        self.records.clear()
        report = self.cache.prepare(path, deadline)
        if self.expected is not None:
            records = sorted(self.records.values(), key=lambda item: item["path"])
            observed = {"count": len(records), "total_bytes": sum(item["size"] for item in records),
                        "identities_sha256": hashlib.sha256(canonical(records)).hexdigest()}
            for key, value in observed.items():
                _fixed(value, self.expected[key])
            # Later commits may legitimately append/compact artifacts. Each is
            # still independently verified by the native cache/provider path.
            self.expected = None
        return report

    def local_root(self, path):
        return self.cache.local_root(path)

    def resolve(self, path):
        return self.cache.resolve(path)


def _release_parent_lock() -> None:
    global _PARENT_LOCK_FD
    if _PARENT_LOCK_FD is not None:
        descriptor, _PARENT_LOCK_FD = _PARENT_LOCK_FD, None
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _new_private_run() -> Path:
    global _PARENT_LOCK_FD
    import gdw_durable_runtime as durable
    LOCAL_PARENT.mkdir(mode=0o700, exist_ok=True)
    durable._private_directory(LOCAL_PARENT)
    descriptor = os.open(LOCAL_PARENT / "startup.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o600):
            raise AdmissionBlocked("STARTUP_LOCK_UNSAFE")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(descriptor)
        raise AdmissionBlocked("STARTUP_LOCK_UNAVAILABLE") from None
    _PARENT_LOCK_FD = descriptor
    directory = LOCAL_PARENT / ("run-" + uuid.uuid4().hex)
    directory.mkdir(mode=0o700)
    return durable._private_directory(directory)


def activate() -> dict:
    """Canonical entry only: restore, claim, measure, then install before serve.

    This function never bootstraps a missing HEAD and never reads an admission
    document from the environment or a local working copy. Only the separately
    admitted acquisition path may create the first immutable record.
    """
    global _STARTED
    import gdw_durable_runtime as durable
    with _LOCK:
        if _STARTED or durable._GATE is not None:
            raise AdmissionBlocked("STARTUP_ALREADY_ATTEMPTED")
        _STARTED = True
        gate = None
        try:
            _fixed(os.environ.get("GDW_DURABLE_STORAGE"), durable.MODE)
            for name in ("GDW_REQUIRED_MOUNT", "A11OY_SERIES_A_REQUIRE_MOUNT"):
                if os.environ.get(name, "").strip():
                    raise AdmissionBlocked("LEGACY_MOUNT_CONFIGURATION_REJECTED")
            for name, expected in (("GDW_SQLITE_JOURNAL", "DELETE"), ("GDW_SQLITE_SYNCHRONOUS", "FULL"),
                                   ("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE")):
                _fixed(os.environ.get(name), expected)
            _fixed(os.environ.get("GDW_PROOF_EXPORT_MODE"), legacy_guard.EXPORT_GUARD)
            from gdw_durable_artifacts import LOGICAL_ROOTS
            logical_variables = {"GDW_PROOF_DIR": LOGICAL_ROOTS["proof_export"],
                                 "GDW_RECEIPT_PROJECTION_DIR": LOGICAL_ROOTS["receipt_projection"]}
            for name, path in logical_variables.items():
                if name in os.environ:
                    _fixed(os.environ[name], str(path))
            actual_source = os.environ.get("SZL_GIT_SHA", "")
            _hex(actual_source, 40)
            directory = _new_private_run()
            import huggingface_hub
            import gdw_durable_storage as storage
            head, encoded, resource_group = storage.load_admitted_head(directory, time.monotonic() + MAX_ACK_SECONDS)
            admission = parse_admission(encoded)
            _fixed(head.value["qualification_sha256"], hashlib.sha256(encoded).hexdigest())
            _fixed(resource_group, admission["provider"]["resource_group_observation_sha256"])
            _fixed(head.value["source_revision"], admission["source"]["revision"])
            source_root = RUNTIME_SOURCE_ROOT
            verify_runtime(admission, source_root, actual_source, huggingface_hub.__version__)
            verify_installed_credentials(source_root)
            bootstrap = head.value["kind"] == "BOOTSTRAP"
            if bootstrap:
                validate_bootstrap_binding(admission, head.value)
            generations = {label: admission["snapshots"][label]["generation"] for label in _LABELS}
            for label in _LABELS:
                _fixed(head.value["snapshots"][label]["generation"], generations[label])
            writer = storage.Writer(storage.WorkerFenceBackend(directory, resource_group), actual_source)
            objects = storage.WorkerSnapshotStore(directory, generations, resource_group, head=lambda: writer.head)
            paths = objects.restore(head, time.monotonic() + MAX_ACK_SECONDS)
            # Native anchor inspection also rejects a self-consistent longer
            # Series-A replacement chain that dropped the original terminal.
            for label in _LABELS:
                storage.inspect_snapshot(label, paths[label], directory, time.monotonic() + MAX_ACK_SECONDS,
                                         previous=admission["snapshots"][label])
            verify_runtime(admission, source_root, actual_source, huggingface_hub.__version__)
            artifact_directory = directory / "artifacts"
            artifact_directory.mkdir(mode=0o700)
            artifacts = _BoundArtifacts(artifact_directory, objects.publish_artifact,
                                        admission["retained_artifacts"] if bootstrap else None)
            gate = durable.LocalGate(writer, paths, directory, objects.publish,
                                     timeout_seconds=MAX_ACK_SECONDS, restored_head=head, artifacts=artifacts)
            # A GitHub acquisition timing cannot qualify this host. Measure the
            # entire unchanged-state acknowledgement here before any reader or
            # supervisor can observe the gate. No SQLite row or receipt changes.
            started = time.monotonic()
            with gate.lock:
                gate.acknowledge()
            elapsed = time.monotonic() - started
            if elapsed > MAX_ACK_SECONDS:
                gate.poisoned = True
                raise AdmissionBlocked("ACTUAL_HOST_ACK_DEADLINE_EXHAUSTED")
            verify_runtime(admission, source_root, actual_source, huggingface_hub.__version__)
            gate.bind_admission_context(
                admission_sha256=head.value["qualification_sha256"],
                qualification_sha256=admission["qualification"]["report_sha256"],
                source_revision=actual_source, generations=generations,
                actual_host_full_state_ack_ms=max(1, int(elapsed * 1000)))
            os.environ["GDW_DB_PATH"] = str(paths["gdw"])
            os.environ["A11OY_SERIES_A_DB"] = str(paths["series_a"])
            for name, path in logical_variables.items():
                os.environ[name] = str(path)
            durable.install(gate)
            # This process-local compatibility value is set only after verified
            # installation. The provider's persistent old-source guard remains
            # durable-private-dataset-v1 across configuration and deployments.
            os.environ["GDW_PROOF_EXPORT_MODE"] = "outbox"
            return {"state": "RESTORED_AND_ACKNOWLEDGED", "source_revision": actual_source,
                    "admission_sha256": head.value["qualification_sha256"],
                    "qualification_sha256": admission["qualification"]["report_sha256"],
                    "actual_host_full_state_ack_ms": max(1, int(elapsed * 1000)),
                    "throughput_claim": "NOT_CLAIMED"}
        except BaseException:
            if gate is not None:
                gate.close()
            _release_parent_lock()
            installed_source.clear_import_policy()
            raise AdmissionBlocked("QUALIFIED_STORAGE_STARTUP_UNAVAILABLE") from None


def close() -> None:
    """Release local resources only after service/supervisor shutdown."""
    import gdw_durable_runtime as durable
    with _LOCK:
        if durable._GATE is not None:
            durable._GATE.close()
        _release_parent_lock()
        installed_source.clear_import_policy()
