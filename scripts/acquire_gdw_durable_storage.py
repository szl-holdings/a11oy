#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Canonical private storage acquisition; a selector never grants authority.

The locator is safe metadata that selects an exact immutable bootstrap. Every
consumer must read the private dataset HEAD, history and admission through the
reviewed provider boundary and verify their binding. Local JSON, a command-line
flag and an environment value cannot supply recovery or deployment authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any
import uuid

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gdw_durable_storage as storage


LOCATOR_SCHEMA = "szl.gdw-durable-acquisition/v1"
MAX_LOCATOR_BYTES = 16 * 1024
MAX_SECONDS = 900
ROOT = Path(__file__).resolve().parents[1]
CAPTURE_REFERENCE = "docs/operations/evidence/gdw-capture-37223162231.json"
HISTORICAL_REFERENCE = "docs/operations/evidence/gdw-recovery-historical-anchors.json"
_LOCATOR_FIELDS = frozenset({
    "schema", "state", "space", "dataset", "bucket", "source_revision",
    "source_manifest_sha256", "admission_sha256", "qualification_sha256",
    "dataset_revision", "operation_id", "resource_group_sha256", "generations",
    "legacy_guard_sha256",
})


class AcquisitionBlocked(RuntimeError):
    """Fixed diagnostic codes only; never provider errors or private records."""
    def __init__(self, code: str):
        self.code = code if type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) else "ACQUISITION_UNAVAILABLE"
        super().__init__(self.code)


def canonical(value: Any) -> bytes:
    try:
        return storage.canonical(value)
    except Exception:
        raise AcquisitionBlocked("ACQUISITION_JSON_INVALID") from None


def _digest(value: Any, length: int) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None and value != "0" * length


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AcquisitionBlocked("ACQUISITION_DUPLICATE_FIELD")
        result[key] = value
    return result


def parse_acquisition_locator(data: bytes) -> dict:
    """Parse an exact bounded selector, without I/O or an authority claim."""
    if type(data) is not bytes or not 1 <= len(data) <= MAX_LOCATOR_BYTES:
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_BOUND_EXCEEDED")
    try:
        value = json.loads(data, object_pairs_hook=_object,
                           parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except AcquisitionBlocked:
        raise
    except Exception:
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_INVALID") from None
    if type(value) is not dict or set(value) != _LOCATOR_FIELDS:
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_FIELDS_INVALID")
    if (value["schema"] != LOCATOR_SCHEMA or value["state"] != "BOOTSTRAP_ACKNOWLEDGED"
            or value["space"] != storage.SPACE or value["dataset"] != storage.DATASET
            or value["bucket"] != storage.BUCKET):
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_UNQUALIFIED")
    for name in ("source_revision", "dataset_revision"):
        if not _digest(value[name], 40):
            raise AcquisitionBlocked("ACQUISITION_LOCATOR_IDENTITY_INVALID")
    for name in ("source_manifest_sha256", "admission_sha256", "qualification_sha256",
                 "resource_group_sha256", "legacy_guard_sha256"):
        if not _digest(value[name], 64):
            raise AcquisitionBlocked("ACQUISITION_LOCATOR_IDENTITY_INVALID")
    if not _digest(value["operation_id"], 32):
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_IDENTITY_INVALID")
    generations = value["generations"]
    if (type(generations) is not dict or set(generations) != {"gdw", "series_a"}
            or not _digest(generations["gdw"], 32)
            or type(generations["series_a"]) is not str
            or not generations["series_a"].startswith("store_")
            or not _digest(generations["series_a"][6:], 32)):
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_GENERATIONS_INVALID")
    if canonical(value) != data:
        raise AcquisitionBlocked("ACQUISITION_LOCATOR_NONCANONICAL")
    return value


def locator_for_bootstrap(head: storage.Head, admission: dict) -> dict:
    """Render the selector only from a caller's already acknowledged bootstrap.

    This pure rendering function does not claim that its inputs were observed.
    The canonical coordinator calls it only after storage.bootstrap has verified
    the exact immutable HEAD, history and admission readback.
    """
    try:
        import gdw_durable_startup as startup
        startup.validate_bootstrap_binding(admission, head.value)
        if head.value["kind"] != "BOOTSTRAP":
            raise AcquisitionBlocked("ACKNOWLEDGED_BOOTSTRAP_REQUIRED")
        value = {
            "schema": LOCATOR_SCHEMA, "state": "BOOTSTRAP_ACKNOWLEDGED",
            "space": storage.SPACE, "dataset": storage.DATASET, "bucket": storage.BUCKET,
            "source_revision": admission["source"]["revision"],
            "source_manifest_sha256": admission["runtime"]["source_manifest_sha256"],
            "admission_sha256": head.value["qualification_sha256"],
            "qualification_sha256": admission["qualification"]["report_sha256"],
            "dataset_revision": head.revision, "operation_id": head.value["operation_id"],
            "resource_group_sha256": admission["provider"]["resource_group_observation_sha256"],
            "generations": {label: head.value["snapshots"][label]["generation"] for label in storage.LABELS},
            "legacy_guard_sha256": hashlib.sha256(canonical(admission["legacy_guard"])).hexdigest(),
        }
        return parse_acquisition_locator(canonical(value))
    except AcquisitionBlocked:
        raise
    except Exception:
        raise AcquisitionBlocked("BOOTSTRAP_LOCATOR_BINDING_FAILED") from None


def _require(value: bool, code: str) -> None:
    if value is not True:
        raise AcquisitionBlocked(code)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _budget(deadline: float) -> None:
    _require(time.monotonic() < deadline, "ACQUISITION_DEADLINE_EXHAUSTED")


def original_identities(report: dict) -> dict:
    import preserve_hf_gdw_store as preservation
    _require(type(report) is dict and report.get("schema") == preservation.SCHEMA
        and report.get("space") == storage.SPACE and report.get("bucket") == storage.BUCKET
        and report.get("preservation_state") == "VERIFIED"
        and report.get("initial_identities_stable") is True
        and report.get("captured_originals_unchanged_after_inspection") is True
        and report.get("originals_mutated") is False and report.get("space_mutated") is False
        and report.get("private_bytes_in_public_artifacts") is False
        and report.get("secret_values_recorded") is False, "PRESERVATION_NOT_VERIFIED")
    rows = report.get("files")
    _require(type(rows) is list and len(rows) == len(preservation.SOURCE_PATHS), "ORIGINAL_IDENTITY_SET_INVALID")
    values = {}
    for row in rows:
        _require(type(row) is dict and row.get("source_path") in preservation.SOURCE_PATHS
            and row["source_path"] not in values and type(row.get("present")) is bool,
            "ORIGINAL_IDENTITY_SET_INVALID")
        if row["present"]:
            _require(type(row.get("size")) is int and 0 <= row["size"] <= preservation.MAX_FILE_BYTES
                and _digest(row.get("sha256"), 64) and _digest(row.get("xet_hash"), 64),
                "ORIGINAL_IDENTITY_INVALID")
            values[row["source_path"]] = {key: row[key] for key in ("size", "sha256", "xet_hash", "present")}
        else:
            _require(row.get("sha256") is None and row.get("private_copy_path") is None,
                "ORIGINAL_ABSENCE_INVALID")
            values[row["source_path"]] = {"present": False}
    _require(all(values[path]["present"] for path in preservation.DATABASES.values()), "ORIGINAL_DATABASE_MISSING")
    return values


def validate_qualified_reports(preserved: dict, qualified: dict, reference: dict,
                               capture_bytes: bytes, source_revision: str) -> dict:
    """Select source-owned native facts; this pure check does not grant effects."""
    import qualify_gdw_store_recovery as recovery
    _require(_digest(source_revision, 40) and preserved.get("source_revision") == source_revision,
        "PRESERVATION_SOURCE_MISMATCH")
    _require(original_identities(preserved) == original_identities(reference),
        "LATER_ORIGINAL_IDENTITIES_CHANGED")
    _require(type(qualified) is dict and qualified.get("schema") == recovery.SCHEMA
        and qualified.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
        and qualified.get("inspector_source_revision") == source_revision
        and qualified.get("capture_id") == reference.get("capture_id")
        and qualified.get("capture_source_revision") == reference.get("source_revision")
        and qualified.get("preservation_manifest_sha256") == reference.get("private_manifest", {}).get("sha256")
        and qualified.get("historical_anchor_state") == "VERIFIED"
        and qualified.get("captured_historical_anchor_state") == "VERIFIED"
        and qualified.get("originals_mutated") is False and qualified.get("provider_writes_performed") is False
        and qualified.get("restore_admitted") is False and qualified.get("deployment_admitted") is False
        and qualified.get("private_bytes_in_public_artifacts") is False
        and qualified.get("secret_values_recorded") is False
        and qualified.get("later_acknowledged_writes_verified") is False,
        "QUALIFIED_CAPTURE_REQUIRED")
    anchor = qualified.get("historical_anchor_reference")
    _require(type(anchor) is dict and anchor.get("capture_report_sha256") == hashlib.sha256(capture_bytes).hexdigest(),
        "QUALIFICATION_CAPTURE_HASH_MISMATCH")
    databases = qualified.get("databases")
    _require(type(databases) is dict and set(databases) == set(storage.LABELS), "QUALIFIED_PAIR_REQUIRED")
    result = {}
    for label in storage.LABELS:
        item = databases[label]
        _require(type(item) is dict and item.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
            and all(item.get(key) is True for key in ("captured_originals_unchanged", "all_declared_stored_values_unchanged",
                "schema_unchanged", "receipt_bytes_unchanged", "database_generation_unchanged"))
            and item.get("historical_anchor_state") == "VERIFIED"
            and item.get("database_generation_id") == reference.get("databases", {}).get(label, {}).get("database_generation_id")
            and _digest(item.get("candidate_sha256"), 64)
            and type(item.get("candidate_bytes")) is int and 0 < item["candidate_bytes"] <= storage.MAX_SNAPSHOT_BYTES
            and item.get("candidate_method") in {"SQLITE_NATIVE_BACKUP", "SQLITE_VACUUM_INTO_DISPOSABLE_EVALUATION"},
            "QUALIFIED_CANDIDATE_REQUIRED")
        integrity = item.get("candidate_integrity")
        _require(type(integrity) is dict and integrity.get("classification") == "OK"
            and integrity.get("foreign_key_check_complete") is True and integrity.get("integrity_check_complete") is True
            and type(integrity.get("foreign_key_violation_count")) is int and integrity["foreign_key_violation_count"] == 0,
            "QUALIFIED_NATIVE_INTEGRITY_REQUIRED")
        logical = item.get("original_logical_state", {})
        receipts = item.get("original_receipts", {})
        _require(_digest(logical.get("logical_sha256"), 64) and _digest(logical.get("schema_sha256"), 64)
            and all(type(receipts.get(key)) is int and receipts[key] == 0
                    for key in ("digest_errors", "binding_errors", "chain_link_errors")),
            "QUALIFIED_NATIVE_RECEIPTS_REQUIRED")
        result[label] = {"sha256": item["candidate_sha256"], "size": item["candidate_bytes"],
            "method": item["candidate_method"], "integrity": "OK", "foreign_key_violations": 0,
            "generation": item["database_generation_id"], "logical_sha256": logical["logical_sha256"],
            "schema_sha256": logical["schema_sha256"], "receipts_sha256": hashlib.sha256(canonical(receipts)).hexdigest(),
            "anchor_sha256": hashlib.sha256(canonical(item.get("candidate_historical_anchor"))).hexdigest()}
    return result


def observe_originals(api, expected: dict, *, require_owned_source, deadline: float) -> dict:
    """Observe exact paths, all absences and source; never open original bytes."""
    import preserve_hf_gdw_store as preservation
    import gdw_durable_guard as guard
    _budget(deadline)
    require_owned_source()
    observation = preservation.observe_stopped(api)
    _require(observation["hf_revision"] == guard.SPACE_REVISION, "LEGACY_SOURCE_CHANGED")
    _raw, current = preservation.paths_info(api, tuple(expected))
    _require(set(current) == {name for name, row in expected.items() if row["present"]},
        "ORIGINAL_PRESENCE_CHANGED")
    for name, row in current.items():
        _require(all(row[key] == expected[name][key] for key in ("size", "xet_hash")), "ORIGINAL_IDENTITIES_CHANGED")
    _budget(deadline)
    return observation


def pause_qualified_source(api, expected: dict, *, require_owned_source, deadline: float) -> dict:
    """One exact canonical pause, with no replay after uncertain acknowledgement."""
    before = observe_originals(api, expected, require_owned_source=require_owned_source, deadline=deadline)
    _require(before["stage"] in {"PAUSED", "RUNTIME_ERROR"}, "LEGACY_STOP_STATE_UNQUALIFIED")
    attempted = before["stage"] != "PAUSED"
    if attempted:
        require_owned_source()
        _budget(deadline)
        try:
            reply = api.pause_space(repo_id=storage.SPACE)
            stage = storage._value(reply, "stage")
            stage = storage._value(stage, "value", stage)
            _require(stage == "PAUSED", "PAUSE_OUTCOME_UNCERTAIN")
        except BaseException:
            raise AcquisitionBlocked("PAUSE_OUTCOME_UNCERTAIN") from None
    first = observe_originals(api, expected, require_owned_source=require_owned_source, deadline=deadline)
    second = observe_originals(api, expected, require_owned_source=require_owned_source, deadline=deadline)
    _require(first["stage"] == second["stage"] == "PAUSED" and first["hf_revision"] == second["hf_revision"],
        "PAUSED_READBACK_REQUIRED")
    return {"state": "PAUSED_SOURCE_AND_ORIGINAL_IDENTITIES_VERIFIED", "pause_submitted": attempted,
        "space_revision": second["hf_revision"], "observed_at": _utc(),
        "observation_sha256": hashlib.sha256(canonical([before, first, second])).hexdigest()}


class _AdmittedAcquisitionHub:
    """Qualify every native object/metadata write against current source and pause."""
    def __init__(self, api, require_paused):
        self.api, self.require_paused = api, require_paused
        self.endpoint = storage.ENDPOINT

    def __getattr__(self, name):
        if name in {"bucket_info", "dataset_info", "get_bucket_paths_info", "download_bucket_files",
                    "get_paths_info", "hf_hub_download"}:
            return getattr(self.api, name)
        raise AcquisitionBlocked("ACQUISITION_OPERATION_UNADMITTED")

    def batch_bucket_files(self, **kwargs):
        _require(set(kwargs) == {"bucket_id", "add"} and kwargs["bucket_id"] == storage.BUCKET
            and type(kwargs["add"]) is list and len(kwargs["add"]) == 1, "ACQUISITION_BUCKET_SCOPE_INVALID")
        self.require_paused()
        return self.api.batch_bucket_files(**kwargs)

    def create_commit(self, repo_id=None, **kwargs):
        _require(repo_id == storage.DATASET and kwargs.get("repo_type") == "dataset"
            and _digest(kwargs.get("parent_commit"), 40), "ACQUISITION_FENCE_SCOPE_INVALID")
        self.require_paused()
        return self.api.create_commit(repo_id, **kwargs)


def acquire_pair(api, *, source_context: dict, qualification_context: dict,
                 qualification_artifact_id: int, qualification_archive_sha256: str,
                 preserved: dict, qualified: dict, qualification_bytes: bytes,
                 reference: dict, capture_bytes: bytes, anchors: dict, anchor_bytes: bytes,
                 manifest: dict, base_observation: dict, guard_probe: dict,
                 paused: dict, legacy_observation: dict, workspace: Path,
                 require_owned_source, deadline: float, operation_factory) -> dict:
    """Reproduce qualified candidates, publish privately and bootstrap exactly once.

    No runtime config/restart/restore is performed here. All private working
    bytes are caller-owned disposable copies. The only outputs are a metadata
    selector and the separately acknowledged private dataset admission.
    """
    import gdw_durable_startup as startup
    import gdw_durable_source as source
    import gdw_durable_guard as guard
    import gdw_durable_image as image
    import qualify_gdw_store_recovery as recovery
    from gdw_durable_artifacts import ArtifactCache

    source_revision = source_context["revision"]
    startup._workflow(source_context)
    startup._workflow(qualification_context)
    _require(qualification_context["revision"] == source_revision
        and qualification_context["run_id"] == source_context["run_id"]
        and qualification_context["run_attempt"] == source_context["run_attempt"], "QUALIFICATION_SOURCE_CONTEXT_MISMATCH")
    selected = validate_qualified_reports(preserved, qualified, reference, capture_bytes, source_revision)
    _require(hashlib.sha256(qualification_bytes).hexdigest() != "0" * 64
        and recovery._json(qualification_bytes) == qualified, "QUALIFICATION_REPORT_BYTES_MISMATCH")
    recovery.validate_historical_anchors(anchors, reference, hashlib.sha256(capture_bytes).hexdigest())
    source.validate_manifest(manifest, source_revision)
    dockerfile = next(item for item in manifest["installed_files"] if item["path"] == "Dockerfile")
    base_observation = image.validate_runtime_base_observation(base_observation, source_revision, dockerfile["sha256"])
    _require(base_observation["execution"]["run_id"] == source_context["run_id"]
        and base_observation["execution"]["run_attempt"] == source_context["run_attempt"], "BASE_PROBE_RUN_MISMATCH")
    _require(paused.get("state") == "PAUSED_SOURCE_AND_ORIGINAL_IDENTITIES_VERIFIED"
        and paused.get("space_revision") == guard.SPACE_REVISION, "PAUSED_SOURCE_PROOF_REQUIRED")
    legacy = {"schema": guard.SCHEMA, "state": "QUALIFIED_LEGACY_STARTUP_GUARD",
        "space_revision": guard.SPACE_REVISION, "image": guard.IMAGE,
        "command": ["python", "gdw_runtime.py"], "working_directory": "/app",
        "source_files_sha256": dict(guard.SOURCE_FILES),
        "observation": {"stage": "PAUSED", "observed_at": paused["observed_at"],
            "public_variables_sha256": legacy_observation["variables_sha256"],
            "secret_names_sha256": hashlib.sha256(canonical(legacy_observation["secret_names"])).hexdigest(),
            "startup_overrides_absent": True},
        "native_probe": {"state": guard_probe.get("state"), "scope": guard_probe.get("scope"),
            "python_version": guard_probe.get("python_version"), "case_count": len(guard_probe.get("cases", [])),
            "case_results_sha256": hashlib.sha256(canonical(guard_probe.get("cases"))).hexdigest(),
            "report_sha256": hashlib.sha256(canonical(guard_probe)).hexdigest(),
            "source_closure_sha256": guard_probe.get("source_closure_sha256"),
            "forbidden_effect_count": guard_probe.get("total_forbidden_effect_count"),
            "unguarded_control": guard_probe.get("unguarded_control")}}
    guard.validate_legacy_guard(legacy)
    guard.validate_legacy_guard_observation(legacy, legacy_observation)
    _require(guard_probe.get("source_files_sha256") == guard.SOURCE_FILES
        and [item.get("name") for item in guard_probe.get("cases", [])] == list(guard.CASES)
        and all(item.get("state") == "PREWRITE_REJECTION_VERIFIED"
                and type(item.get("forbidden_effect_count")) is int and item["forbidden_effect_count"] == 0
                for item in guard_probe["cases"]), "LEGACY_NATIVE_CASES_UNQUALIFIED")
    expected_originals = original_identities(reference)
    def require_paused():
        observed = observe_originals(api, expected_originals, require_owned_source=require_owned_source, deadline=deadline)
        _require(observed["stage"] == "PAUSED", "PAUSED_READBACK_REQUIRED")
    require_paused()
    workspace = storage._private_directory(workspace)
    reproduction = recovery.qualify_capture(recovery.ReadOnlyCaptureHub(api), reference, workspace / "qualification",
        require_owned_source, deadline, historical_anchors=anchors, capture_report_sha256=hashlib.sha256(capture_bytes).hexdigest())
    reproduction["inspector_source_revision"] = source_revision
    reproduced = validate_qualified_reports(preserved, reproduction, reference, capture_bytes, source_revision)
    _require(reproduced == selected, "CANDIDATE_REPRODUCTION_MISMATCH")
    paths = {label: workspace / "qualification" / "working" / label / "candidate.sqlite3" for label in storage.LABELS}
    # Check both closed native candidate identities before any publication.
    for label, path in paths.items():
        observed = storage.inspect_snapshot(label, path, workspace, deadline)
        _require(all(observed[key] == selected[label][key] for key in ("size", "sha256", "generation")),
            "CANDIDATE_NATIVE_IDENTITY_MISMATCH")
    require_paused()
    info = api.dataset_info(storage.DATASET, revision="main", expand=["sha", "private", "resourceGroup"])
    _require(storage._value(info, "id") == storage.DATASET and storage._value(info, "private") is True
        and _digest(storage._value(info, "sha"), 40), "PRIVATE_FENCE_UNAVAILABLE")
    group = hashlib.sha256(canonical(storage._value(info, "resource_group"))).hexdigest()
    staging = workspace / "objects"; staging.mkdir(mode=0o700)
    guarded_api = _AdmittedAcquisitionHub(api, require_paused)
    backend = storage.HFDatasetFenceBackend(guarded_api, staging, group, operation_factory)
    backend.empty_parent(deadline)  # An existing HEAD cannot trigger new snapshot publication.
    objects = storage.HFPrivateObjectStore(guarded_api, staging, workspace)
    identities = {}
    def publish_artifact(path, object_path, sha256, object_deadline):
        value = objects.publish_artifact(path, object_path, sha256, object_deadline)
        if object_path in identities:
            _require(identities[object_path] == value, "ARTIFACT_READBACK_IDENTITY_CHANGED")
        identities[object_path] = value
        return value
    artifact_directory = workspace / "artifacts"; artifact_directory.mkdir(mode=0o700)
    artifacts = ArtifactCache(artifact_directory, publish_artifact)
    started = time.monotonic()
    measured_deadline = min(deadline, started + 300)
    artifacts.prepare(paths["gdw"], measured_deadline)
    generations = {label: selected[label]["generation"] for label in storage.LABELS}
    snapshots = objects.publish_snapshots(paths, generations, measured_deadline)
    restored_directory = workspace / "roundtrip"; restored_directory.mkdir(mode=0o700)
    restored = {label: restored_directory / (label + ".sqlite3") for label in storage.LABELS}
    objects.restore_snapshots(snapshots, restored, measured_deadline)
    artifacts.prepare(restored["gdw"], measured_deadline)
    elapsed = max(1, int((time.monotonic() - started) * 1000))
    _budget(measured_deadline)
    artifact_rows = [identities[path] for path in sorted(identities)]
    artifact_digest = hashlib.sha256(canonical(artifact_rows)).hexdigest()
    capture_match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)-([0-9a-f]{40})-([0-9a-f]{32})", reference["capture_id"])
    _require(capture_match is not None, "CAPTURE_IDENTITY_INVALID")
    capture_run, capture_attempt = int(capture_match.group(1)), int(capture_match.group(2))
    runtime = {"sdk_version": storage.SDK_VERSION, "sqlite_version": base_observation["sqlite"]["python_version"],
        "source_manifest": manifest, "source_manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
        "base_observation": base_observation}
    qualification = {"schema": recovery.SCHEMA, "state": "LOGICAL_CONTINUITY_VERIFIED",
        "report_sha256": hashlib.sha256(qualification_bytes).hexdigest(), "source": qualification_context,
        "artifact_id": qualification_artifact_id, "artifact_archive_sha256": qualification_archive_sha256,
        "capture_report_sha256": hashlib.sha256(capture_bytes).hexdigest(), "historical_anchor_state": "VERIFIED",
        "historical_anchor_sha256": hashlib.sha256(anchor_bytes).hexdigest(),
        "all_declared_stored_values_unchanged": True, "receipt_bytes_unchanged": True,
        "database_generations_unchanged": True, "later_acknowledged_writes_state": "NOT_ESTABLISHED",
        "logical_fingerprint_sha256": {label: selected[label]["logical_sha256"] for label in storage.LABELS},
        "candidates": {label: {key: selected[label][key] for key in ("sha256", "size", "method", "integrity", "foreign_key_violations")}
            for label in storage.LABELS}}
    latency_receipt = {"scope": "CANONICAL_ACQUISITION_FULL_PAIR_AND_ARTIFACT_UPLOAD_READBACK_RESTORE",
        "runner": "GITHUB_ACTIONS_CANONICAL_MAIN", "run_id": source_context["run_id"],
        "run_attempt": source_context["run_attempt"], "sample_count": 1, "samples_ms": [elapsed],
        "snapshot_sha256": {label: snapshots[label]["sha256"] for label in storage.LABELS},
        "artifact_identities_sha256": artifact_digest, "runtime_self_check": "REQUIRED_BEFORE_INSTALL_ON_ACTUAL_HOST",
        "ack_deadline_ms": 60000, "throughput_claim": "NOT_CLAIMED"}
    latency_receipt["receipt_sha256"] = hashlib.sha256(canonical(latency_receipt)).hexdigest()
    admission = {"schema": startup.SCHEMA, "state": "QUALIFIED_CAPTURED_STATE_FOR_PRIVATE_DATASET_STORAGE",
        "created_at": _utc(), "space": storage.SPACE, "dataset": storage.DATASET, "bucket": storage.BUCKET,
        "source": source_context, "capture": {"capture_id": reference["capture_id"],
            "source_revision": reference["source_revision"], "run_id": capture_run, "run_attempt": capture_attempt,
            "report_sha256": hashlib.sha256(capture_bytes).hexdigest(),
            "manifest_sha256": reference["private_manifest"]["sha256"], "manifest_xet_hash": reference["private_manifest"]["xet_hash"]},
        "qualification": qualification, "legacy_guard": legacy,
        "legacy_quiescence": {"state": "ALL_LEGACY_WRITERS_VERIFIED_STOPPED_SPACE_PAUSED",
            "space_revision": guard.SPACE_REVISION, "observed_at": paused["observed_at"], "source_revision": source_revision,
            "writer_inventory_sha256": hashlib.sha256(canonical({"space": storage.SPACE,
                "canonical_workflow": startup.WORKFLOW, "source_files": guard.SOURCE_FILES})).hexdigest(),
            "observation_sha256": paused["observation_sha256"]},
        "provider": {"endpoint": storage.ENDPOINT, "dataset_private": True, "bucket_private": True,
            "resource_group_observation_sha256": group, "audience_equivalence": "NOT_ESTABLISHED"},
        "runtime": runtime, "snapshots": snapshots,
        "retained_artifacts": {"state": "ALL_RETAINED_OBJECTS_READBACK_VERIFIED", "count": len(artifact_rows),
            "total_bytes": sum(item["size"] for item in artifact_rows), "identities_sha256": artifact_digest,
            "native_bindings_state": "VERIFIED", "reconstruction": "RECONSTRUCTED_FROM_RETAINED_PAYLOAD"},
        "latency": latency_receipt}
    encoded = canonical(admission)
    startup.parse_admission(encoded)
    proposal = {"schema": storage.SCHEMA, "space": storage.SPACE, "dataset": storage.DATASET, "bucket": storage.BUCKET,
        "kind": "BOOTSTRAP", "epoch": 0, "sequence": 0, "writer_id": "0" * 32, "operation_id": uuid.uuid4().hex,
        "previous_manifest_sha256": None, "source_revision": source_revision,
        "qualification_sha256": hashlib.sha256(encoded).hexdigest(), "snapshots": snapshots}
    require_paused()
    head = storage.bootstrap(backend, proposal, encoded, deadline)
    require_paused()
    _budget(deadline)
    return locator_for_bootstrap(head, admission)


def _read(path: Path, bound: int = 1024 * 1024) -> bytes:
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= bound,
            "ACQUISITION_INPUT_BOUND")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(bound + 1)
        after = os.fstat(fd)
        _require(len(data) == before.st_size
            and storage._stat_identity(after) == storage._stat_identity(before)
            and after.st_gid == before.st_gid, "ACQUISITION_INPUT_CHANGED")
        return data
    finally:
        os.close(fd)


def _references():
    import qualify_gdw_store_recovery as recovery
    captured = _read(ROOT / CAPTURE_REFERENCE)
    historical = _read(ROOT / HISTORICAL_REFERENCE)
    reference, anchors = recovery._json(captured), recovery._json(historical)
    recovery.validate_historical_anchors(anchors, reference, hashlib.sha256(captured).hexdigest())
    return reference, captured, anchors, historical


def classify_prerequisites(preservation_path: Path, qualification_path: Path, source_revision: str) -> dict:
    """The manual 1.23 job's typed decision; it never admits restore/deploy."""
    from gdw_acquisition_evidence import strict
    reference, captured, _anchors, _historical = _references()
    preserved, qualified = strict(_read(preservation_path)), strict(_read(qualification_path))
    selected = validate_qualified_reports(preserved, qualified, reference, captured, source_revision)
    return {"schema": "szl.hf-qualified-recovery-prerequisite/v1", "state": "QUALIFIED_CANDIDATE_ONLY",
        "source_revision": source_revision, "mode": "managed-recovery", "restore_admitted": False,
        "deployment_admitted": False, "secret_values_recorded": False,
        "qualification_sha256": hashlib.sha256(_read(qualification_path)).hexdigest(),
        "generations": {label: selected[label]["generation"] for label in storage.LABELS}}


def _native_inputs(request: dict, evidence):
    import gdw_acquisition_evidence as native
    evidence.observe_run()
    evidence.require_active_acquisition()
    source_members = evidence.artifact(request["source_artifact_id"], request["source_artifact_sha256"],
        name=f"canonical-source-admission-{evidence.run_id}-{evidence.attempt}", job_name=native.SOURCE_JOB,
        members=frozenset({"canonical-source-admission.json"}))
    prerequisite_members = evidence.artifact(request["qualification_artifact_id"], request["qualification_artifact_sha256"],
        name=f"canonical-manual-prerequisites-{evidence.run_id}-{evidence.attempt}", job_name=native.QUALIFICATION_JOB,
        members=frozenset({"manual-prerequisites.json", "gdw-store-preservation.json", "gdw-store-recovery-qualification.json"}))
    receipt = source_members["canonical-source-admission.json"]
    source = evidence.source_context(receipt, native.ACQUISITION_JOB)
    qualification_source = evidence.source_context(receipt, native.QUALIFICATION_JOB)
    prerequisite = native.strict(prerequisite_members["manual-prerequisites.json"])
    qualified_bytes = prerequisite_members["gdw-store-recovery-qualification.json"]
    _require(prerequisite.get("schema") == "szl.hf-qualified-recovery-prerequisite/v1"
        and prerequisite.get("state") == "QUALIFIED_CANDIDATE_ONLY" and prerequisite.get("mode") == "managed-recovery"
        and prerequisite.get("source_revision") == evidence.source
        and prerequisite.get("qualification_sha256") == hashlib.sha256(qualified_bytes).hexdigest()
        and prerequisite.get("restore_admitted") is False and prerequisite.get("deployment_admitted") is False,
        "NATIVE_QUALIFIED_PREREQUISITE_REQUIRED")
    return source, qualification_source, native.strict(prerequisite_members["gdw-store-preservation.json"]), \
        native.strict(qualified_bytes), qualified_bytes


def _execute_native(request: dict, workspace: Path, deadline: float) -> dict:
    import gdw_acquisition_evidence as native
    import gdw_durable_guard as guard
    import probe_gdw_runtime_base as base
    import probe_gdw_legacy_startup as legacy_native
    from build_gdw_installed_source_manifest import build_manifest
    from configure_hf_gdw_runtime import managed_space_observation
    from huggingface_hub import CommitOperationAdd

    evidence = native.NativeEvidence(dict(os.environ), deadline)
    source, qualification_source, preserved, qualified, qualification_bytes = _native_inputs(request, evidence)
    reference, captured, anchors, historical = _references()
    validate_qualified_reports(preserved, qualified, reference, captured, evidence.source)
    publisher = Path(request["publisher_script"])
    _require(publisher.is_absolute() and publisher.name == "hf_deploy_from_dockerfile.py", "PINNED_PUBLISHER_REQUIRED")
    manifest = build_manifest(ROOT, evidence.source, publisher, deadline=deadline)
    # canonical_context verifies this exact checkout/Dockerfile/FROM/native job.
    dockerfile_digest, execution = base.canonical_context(evidence.source, deadline=deadline - 40)
    expected_base = base.observe_runtime_base(evidence.source, dockerfile_digest, execution,
        deadline=min(deadline - 40, time.monotonic() + 240), temporary_root=workspace)
    api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
    legacy = managed_space_observation(api)
    guard.validate_environment(legacy["variables"], legacy["secret_names"])
    _require(legacy["space_revision"] == guard.SPACE_REVISION
        and legacy["stage"] in {"RUNTIME_ERROR", "PAUSED"}, "LEGACY_SOURCE_STATE_UNQUALIFIED")
    native_guard = legacy_native.observe_legacy_guard(api, expected_base, legacy,
        deadline=min(deadline - 20, time.monotonic() + 150), temporary_root=workspace)
    original = original_identities(reference)
    paused = pause_qualified_source(api, original, require_owned_source=evidence.require_current_main, deadline=deadline)
    after = managed_space_observation(api)
    _require(after["stage"] == "PAUSED" and after["space_revision"] == legacy["space_revision"]
        and after["variables"] == legacy["variables"] and after["secret_names"] == legacy["secret_names"],
        "PAUSE_CONFIGURATION_IDENTITY_CHANGED")
    return acquire_pair(api, source_context=source, qualification_context=qualification_source,
        qualification_artifact_id=request["qualification_artifact_id"],
        qualification_archive_sha256=request["qualification_artifact_sha256"], preserved=preserved,
        qualified=qualified, qualification_bytes=qualification_bytes, reference=reference, capture_bytes=captured,
        anchors=anchors, anchor_bytes=historical, manifest=manifest, base_observation=expected_base,
        guard_probe=native_guard, paused=paused, legacy_observation=after, workspace=workspace,
        require_owned_source=evidence.require_current_main, deadline=deadline, operation_factory=CommitOperationAdd)


def _worker() -> int:
    import logging
    import tempfile
    import preserve_hf_gdw_store as preservation
    from gdw_acquisition_evidence import strict
    value = None
    try:
        request = strict(sys.stdin.buffer.read(MAX_LOCATOR_BYTES + 1), MAX_LOCATOR_BYTES)
        _require(set(request) == {"source_artifact_id", "source_artifact_sha256", "qualification_artifact_id",
            "qualification_artifact_sha256", "publisher_script", "deadline"}, "ACQUISITION_REQUEST_INVALID")
        for name in ("source_artifact_id", "qualification_artifact_id"):
            _require(type(request[name]) is int and request[name] > 0, "ACQUISITION_ARTIFACT_INVALID")
        for name in ("source_artifact_sha256", "qualification_artifact_sha256"):
            _require(_digest(request[name], 64), "ACQUISITION_ARTIFACT_INVALID")
        _require(type(request["deadline"]) in (int, float) and 0 < request["deadline"] - time.monotonic() <= MAX_SECONDS,
            "ACQUISITION_DEADLINE_INVALID")
        os.umask(0o077)
        logging.disable(logging.CRITICAL)
        os.environ.update(HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DISABLE_TELEMETRY="1",
            HF_HUB_DISABLE_IMPLICIT_TOKEN="1", PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory(prefix="gdw-canonical-private-", dir=Path.cwd()) as temporary:
            directory = Path(temporary)
            os.environ.update(HF_HOME=str(directory / "cache"), HF_HUB_CACHE=str(directory / "cache" / "hub"),
                HF_XET_CACHE=str(directory / "cache" / "xet"))
            with preservation._private_output():
                value = _execute_native(request, directory, request["deadline"])
        _budget(request["deadline"])
        sys.stdout.buffer.write(canonical(value))
        return 0
    except BaseException:
        # Include no exception text, provider response, input path, token, private
        # SQL value or arbitrary JSON in either public stream.
        sys.stdout.write('{"schema":"szl.gdw-durable-acquisition/v1","state":"HELD","diagnostic_code":"CANONICAL_ACQUISITION_UNAVAILABLE"}\n')
        return 2


def run_native(request: dict) -> dict:
    import tempfile
    import probe_gdw_runtime_base as base
    deadline = time.monotonic() + MAX_SECONDS
    request = dict(request, deadline=deadline - 5)
    # Existing native credentials are inherited only by this private worker.
    names = ("HF_TOKEN", "GH_TOKEN", "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_REPOSITORY_ID",
        "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "GITHUB_RUN_ID",
        "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_JOB")
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment.update(PATH="/usr/local/bin:/usr/bin:/bin", PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="gdw-acquisition-parent-") as temporary:
        raw = base._run([sys.executable, "-B", str(Path(__file__).resolve()), "--worker"],
            deadline=deadline, limit=MAX_LOCATOR_BYTES, env=environment, cwd=temporary, input_bytes=canonical(request))
    _budget(deadline)
    return parse_acquisition_locator(raw)


def _write_output(path: Path, value: dict) -> None:
    data = canonical(value)
    _require(len(data) <= MAX_LOCATOR_BYTES and path.is_absolute(), "ACQUISITION_OUTPUT_INVALID")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    finally:
        os.close(fd)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--classify-prerequisites", action="store_true")
    mode.add_argument("--acquire", action="store_true")
    mode.add_argument("--fetch-locator", action="store_true")
    parser.add_argument("--preservation", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--source-artifact-id", type=int)
    parser.add_argument("--source-artifact-sha256")
    parser.add_argument("--qualification-artifact-id", type=int)
    parser.add_argument("--qualification-artifact-sha256")
    parser.add_argument("--acquisition-artifact-id", type=int)
    parser.add_argument("--acquisition-artifact-sha256")
    parser.add_argument("--publisher-script")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.classify_prerequisites:
            _require(args.preservation is not None and args.qualification is not None, "PREREQUISITE_INPUT_REQUIRED")
            value = classify_prerequisites(args.preservation, args.qualification, os.environ.get("GITHUB_SHA", ""))
        elif args.acquire:
            value = run_native({"source_artifact_id": args.source_artifact_id,
                "source_artifact_sha256": args.source_artifact_sha256,
                "qualification_artifact_id": args.qualification_artifact_id,
                "qualification_artifact_sha256": args.qualification_artifact_sha256,
                "publisher_script": args.publisher_script})
        else:
            import gdw_acquisition_evidence as native
            evidence = native.NativeEvidence(dict(os.environ), time.monotonic() + 60)
            evidence.observe_run()
            members = evidence.artifact(args.acquisition_artifact_id, args.acquisition_artifact_sha256,
                name=f"canonical-durable-acquisition-{evidence.run_id}-{evidence.attempt}",
                job_name=native.ACQUISITION_JOB, members=frozenset({"gdw-durable-acquisition.json", "gdw-managed-configuration.json"}))
            value = parse_acquisition_locator(members["gdw-durable-acquisition.json"])
            _require(value["source_revision"] == evidence.source, "ACQUISITION_SOURCE_MISMATCH")
            evidence.require_current_main()
        _write_output(args.output, value)
        if args.classify_prerequisites and args.github_output is not None:
            with args.github_output.open("a", encoding="ascii") as stream:
                stream.write("mode=managed-recovery\n")
        print(json.dumps({"schema": value["schema"], "state": value["state"], "secret_values_recorded": False}))
        return 0
    except BaseException:
        value = {"schema": LOCATOR_SCHEMA, "state": "HELD", "diagnostic_code": "CANONICAL_ACQUISITION_UNAVAILABLE",
            "restore_admitted": False, "deployment_admitted": False, "secret_values_recorded": False}
        try:
            if not os.path.lexists(args.output): _write_output(args.output, value)
        except BaseException:
            pass
        print(json.dumps(value))
        return 2


if __name__ == "__main__":
    raise SystemExit(_worker() if sys.argv[1:] == ["--worker"] else main())
