# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. / SZL Holdings
"""Fail-closed external-claim registry and benchmark-receipt verifier.

Taxonomy: provenance/.  This module performs no benchmark, network, GPU, model,
or signing work.  It reads at most one digest-addressed local DSSE envelope per
claim, verifies the already-written receipt, and keeps the claim ROADMAP on any
missing, malformed, stale, mismatched, unsigned, or unapproved evidence.
"""

import copy
import hashlib
import json
import math
import os
import re
import stat
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import szl_dsse

CLAIM_SCHEMA_VERSION = "szl.quant.claim/v1"
RUN_SCHEMA_VERSION = "szl.quant.benchmark-run/v1"
RUN_PAYLOAD_TYPE = "application/vnd.szl.quant.benchmark-run.v1+json"
RECEIPT_DIR_ENV = "SZL_QUANT_CLAIM_RECEIPT_DIR"
MAX_RECEIPT_BYTES = 1_048_576
MAX_RECEIPT_AGE_SECONDS = 7 * 24 * 60 * 60
_DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
_CLAIM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
_PROTOCOL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
_HARDWARE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")

_CLAIM_KEYS = {
    "schema_version", "claim_id", "claim", "external_report", "protocol",
    "required_hardware_class", "measurement_receipt_id", "blocked_by",
    "szl_label", "szl_measured", "measurement_gate",
}
_REPORT_KEYS = {"value", "units", "scope", "source"}
_SOURCE_KEYS = {"organization", "title", "url", "kind"}
_PROTOCOL_KEYS = {"id", "metric", "unit", "description", "requires_energy"}
_GATE_KEYS = {"promoted", "reason", "receipt_id"}
_RUN_KEYS = {
    "schema_version", "run_id", "claim_id", "protocol", "subject", "baseline",
    "dataset", "hardware", "software", "execution", "raw_trials", "measurement",
    "correctness", "energy", "freshness", "review", "artifacts",
}


def _exact_keys(value: Any, expected: set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % path)
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError("%s keys invalid; missing=%s extra=%s" % (path, missing, extra))


def _nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % path)
    return value


def _digest(value: Any, path: str) -> str:
    text = _nonempty_string(value, path)
    if _DIGEST_RE.fullmatch(text) is None:
        raise ValueError("%s must be sha256:<64 lowercase hex>" % path)
    return text


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a number" % path)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("%s must be finite" % path)
    return number


def _utc(value: Any, path: str) -> datetime:
    text = _nonempty_string(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("%s must be ISO-8601" % path) from exc
    if parsed.tzinfo is None:
        raise ValueError("%s must include a timezone" % path)
    return parsed.astimezone(timezone.utc)


def validate_claim(claim: Any) -> dict[str, Any]:
    _exact_keys(claim, _CLAIM_KEYS, "claim")
    if claim["schema_version"] != CLAIM_SCHEMA_VERSION:
        raise ValueError("claim.schema_version unsupported")
    if _CLAIM_ID_RE.fullmatch(_nonempty_string(claim["claim_id"], "claim.claim_id")) is None:
        raise ValueError("claim.claim_id invalid")
    _nonempty_string(claim["claim"], "claim.claim")
    _exact_keys(claim["external_report"], _REPORT_KEYS, "claim.external_report")
    report = claim["external_report"]
    _nonempty_string(report["value"], "claim.external_report.value")
    _nonempty_string(report["units"], "claim.external_report.units")
    _nonempty_string(report["scope"], "claim.external_report.scope")
    _exact_keys(report["source"], _SOURCE_KEYS, "claim.external_report.source")
    source = report["source"]
    for key in ("organization", "title", "url", "kind"):
        _nonempty_string(source[key], "claim.external_report.source.%s" % key)
    if not source["url"].startswith("https://"):
        raise ValueError("claim external source URL must use https")
    if source["kind"] not in {
        "OFFICIAL_VENDOR_REPORT", "OFFICIAL_RESEARCH", "OFFICIAL_DOCS", "OFFICIAL_MODEL_CARD", "ACADEMIC_PAPER"
    }:
        raise ValueError("claim external source kind invalid")
    _exact_keys(claim["protocol"], _PROTOCOL_KEYS, "claim.protocol")
    protocol = claim["protocol"]
    if _PROTOCOL_ID_RE.fullmatch(_nonempty_string(protocol["id"], "claim.protocol.id")) is None:
        raise ValueError("claim.protocol.id invalid")
    for key in ("metric", "unit", "description"):
        _nonempty_string(protocol[key], "claim.protocol.%s" % key)
    if not isinstance(protocol["requires_energy"], bool):
        raise ValueError("claim.protocol.requires_energy must be boolean")
    if _HARDWARE_RE.fullmatch(_nonempty_string(claim["required_hardware_class"], "claim.required_hardware_class")) is None:
        raise ValueError("claim.required_hardware_class invalid")
    receipt_id = claim["measurement_receipt_id"]
    if receipt_id is not None:
        _digest(receipt_id, "claim.measurement_receipt_id")
    blockers = claim["blocked_by"]
    if not isinstance(blockers, list) or not blockers or len(blockers) != len(set(blockers)):
        raise ValueError("claim.blocked_by must be a non-empty unique list")
    for index, blocker in enumerate(blockers):
        _nonempty_string(blocker, "claim.blocked_by[%d]" % index)
    if claim["szl_label"] not in {"ROADMAP", "MEASURED", "UNVERIFIED", "CONFLICT"}:
        raise ValueError("claim.szl_label invalid")
    _exact_keys(claim["measurement_gate"], _GATE_KEYS, "claim.measurement_gate")
    gate = claim["measurement_gate"]
    if not isinstance(gate["promoted"], bool):
        raise ValueError("claim.measurement_gate.promoted must be boolean")
    _nonempty_string(gate["reason"], "claim.measurement_gate.reason")
    if gate["receipt_id"] is not None:
        _digest(gate["receipt_id"], "claim.measurement_gate.receipt_id")
    if gate["receipt_id"] != receipt_id:
        raise ValueError("claim measurement gate and receipt IDs differ")
    if claim["szl_label"] == "MEASURED":
        if gate["promoted"] is not True:
            raise ValueError("MEASURED claim must have a promoted gate")
        measured = claim["szl_measured"]
        _exact_keys(
            measured,
            {"metric", "value", "unit", "estimator", "confidence_interval", "summary_tolerance"},
            "claim.szl_measured",
        )
        for key in ("metric", "unit", "estimator"):
            _nonempty_string(measured[key], "claim.szl_measured.%s" % key)
        if measured["metric"] != protocol["metric"] or measured["unit"] != protocol["unit"]:
            raise ValueError("claim measured semantics differ from protocol")
        if measured["estimator"] not in {"mean", "median"}:
            raise ValueError("claim measured estimator unsupported")
        _finite_number(measured["value"], "claim.szl_measured.value")
        if _finite_number(measured["summary_tolerance"], "claim.szl_measured.summary_tolerance") < 0:
            raise ValueError("claim.szl_measured.summary_tolerance must be non-negative")
        interval = measured["confidence_interval"]
        if interval is not None:
            if not isinstance(interval, list) or len(interval) != 2:
                raise ValueError("claim.szl_measured.confidence_interval invalid")
            lower = _finite_number(interval[0], "claim.szl_measured.confidence_interval[0]")
            upper = _finite_number(interval[1], "claim.szl_measured.confidence_interval[1]")
            if lower > upper:
                raise ValueError("claim.szl_measured confidence interval reversed")
        if receipt_id is None:
            raise ValueError("MEASURED claim must bind a receipt ID")
    else:
        if gate["promoted"] is not False:
            raise ValueError("non-MEASURED claim cannot have a promoted gate")
        if claim["szl_measured"] is not None:
            raise ValueError("non-MEASURED claim cannot contain szl_measured")
    return claim


def _validate_subject(value: Any, path: str) -> None:
    _exact_keys(value, {"artifact_id", "revision", "sha256", "license"}, path)
    for key in ("artifact_id", "revision", "license"):
        _nonempty_string(value[key], "%s.%s" % (path, key))
    _digest(value["sha256"], "%s.sha256" % path)


def validate_benchmark_run(run: Any, now: datetime | None = None) -> dict[str, Any]:
    _exact_keys(run, _RUN_KEYS, "benchmark_run")
    if run["schema_version"] != RUN_SCHEMA_VERSION:
        raise ValueError("benchmark_run.schema_version unsupported")
    _nonempty_string(run["run_id"], "benchmark_run.run_id")
    if _CLAIM_ID_RE.fullmatch(_nonempty_string(run["claim_id"], "benchmark_run.claim_id")) is None:
        raise ValueError("benchmark_run.claim_id invalid")
    _exact_keys(run["protocol"], {"id", "version", "sha256", "preregistered_at", "manifest"}, "benchmark_run.protocol")
    _nonempty_string(run["protocol"]["id"], "benchmark_run.protocol.id")
    _nonempty_string(run["protocol"]["version"], "benchmark_run.protocol.version")
    protocol_digest = _digest(run["protocol"]["sha256"], "benchmark_run.protocol.sha256")
    preregistered = _utc(run["protocol"]["preregistered_at"], "benchmark_run.protocol.preregistered_at")
    protocol_manifest = run["protocol"]["manifest"]
    _exact_keys(
        protocol_manifest,
        {
            "id", "version", "metric", "unit", "preregistered_at", "minimum_trials",
            "hardware_class", "requires_energy", "dataset_manifest_sha256",
        },
        "benchmark_run.protocol.manifest",
    )
    for key in ("id", "version", "metric", "unit", "hardware_class"):
        _nonempty_string(protocol_manifest[key], "benchmark_run.protocol.manifest.%s" % key)
    manifest_preregistered = _utc(
        protocol_manifest["preregistered_at"],
        "benchmark_run.protocol.manifest.preregistered_at",
    )
    if not isinstance(protocol_manifest["minimum_trials"], int) or isinstance(protocol_manifest["minimum_trials"], bool) or protocol_manifest["minimum_trials"] < 3:
        raise ValueError("PROTOCOL_MINIMUM_TRIALS_INVALID")
    if not isinstance(protocol_manifest["requires_energy"], bool):
        raise ValueError("PROTOCOL_ENERGY_REQUIREMENT_INVALID")
    _digest(protocol_manifest["dataset_manifest_sha256"], "benchmark_run.protocol.manifest.dataset_manifest_sha256")
    canonical_protocol = json.dumps(protocol_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    actual_protocol_digest = "sha256:" + hashlib.sha256(canonical_protocol).hexdigest()
    if actual_protocol_digest != protocol_digest:
        raise ValueError("PROTOCOL_MANIFEST_DIGEST_MISMATCH")
    if (protocol_manifest["id"] != run["protocol"]["id"]
            or protocol_manifest["version"] != run["protocol"]["version"]
            or manifest_preregistered != preregistered):
        raise ValueError("PROTOCOL_MANIFEST_BINDING_MISMATCH")
    _validate_subject(run["subject"], "benchmark_run.subject")
    _validate_subject(run["baseline"], "benchmark_run.baseline")
    _exact_keys(run["dataset"], {"manifest_sha256", "split", "seeds", "rights_admitted"}, "benchmark_run.dataset")
    _digest(run["dataset"]["manifest_sha256"], "benchmark_run.dataset.manifest_sha256")
    _nonempty_string(run["dataset"]["split"], "benchmark_run.dataset.split")
    if run["dataset"]["rights_admitted"] is not True:
        raise ValueError("benchmark_run.dataset.rights_admitted must be true")
    if not isinstance(run["dataset"]["seeds"], list) or not run["dataset"]["seeds"] or not all(isinstance(seed, int) and not isinstance(seed, bool) for seed in run["dataset"]["seeds"]):
        raise ValueError("benchmark_run.dataset.seeds must be a non-empty integer list")
    if protocol_manifest["dataset_manifest_sha256"] != run["dataset"]["manifest_sha256"]:
        raise ValueError("PROTOCOL_DATASET_BINDING_MISMATCH")
    _exact_keys(run["hardware"], {"class", "devices", "driver", "cuda"}, "benchmark_run.hardware")
    _nonempty_string(run["hardware"]["class"], "benchmark_run.hardware.class")
    for key in ("driver", "cuda"):
        _nonempty_string(run["hardware"][key], "benchmark_run.hardware.%s" % key)
    devices = run["hardware"]["devices"]
    if not isinstance(devices, list) or not devices:
        raise ValueError("benchmark_run.hardware.devices must be non-empty")
    for index, device in enumerate(devices):
        path = "benchmark_run.hardware.devices[%d]" % index
        _exact_keys(device, {"kind", "model", "count"}, path)
        if device["kind"] not in {"CPU", "GPU", "REMOTE_ACCELERATOR"}:
            raise ValueError("%s.kind invalid" % path)
        _nonempty_string(device["model"], "%s.model" % path)
        if not isinstance(device["count"], int) or isinstance(device["count"], bool) or device["count"] < 1:
            raise ValueError("%s.count invalid" % path)
    _exact_keys(run["software"], {"git_commit", "container_digest", "lock_sha256"}, "benchmark_run.software")
    if _HEX40_RE.fullmatch(_nonempty_string(run["software"]["git_commit"], "benchmark_run.software.git_commit")) is None:
        raise ValueError("benchmark_run.software.git_commit invalid")
    _digest(run["software"]["container_digest"], "benchmark_run.software.container_digest")
    _digest(run["software"]["lock_sha256"], "benchmark_run.software.lock_sha256")
    _exact_keys(run["execution"], {"started_at", "completed_at", "warmup_trials", "measured_trials", "config"}, "benchmark_run.execution")
    started = _utc(run["execution"]["started_at"], "benchmark_run.execution.started_at")
    completed = _utc(run["execution"]["completed_at"], "benchmark_run.execution.completed_at")
    if preregistered > started:
        raise ValueError("PREREGISTRATION_AFTER_START")
    if completed < started:
        raise ValueError("EXECUTION_TIME_REVERSED")
    for key, minimum in (("warmup_trials", 0), ("measured_trials", 3)):
        value = run["execution"][key]
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise ValueError("benchmark_run.execution.%s invalid" % key)
    if not isinstance(run["execution"]["config"], dict):
        raise ValueError("benchmark_run.execution.config must be an object")
    if protocol_manifest["minimum_trials"] > run["execution"]["measured_trials"]:
        raise ValueError("PROTOCOL_MINIMUM_TRIALS_NOT_MET")
    trials = run["raw_trials"]
    if not isinstance(trials, list) or len(trials) != run["execution"]["measured_trials"]:
        raise ValueError("RAW_TRIAL_COUNT_MISMATCH")
    trial_ids: list[int] = []
    for index, trial in enumerate(trials):
        path = "benchmark_run.raw_trials[%d]" % index
        _exact_keys(trial, {"trial", "value", "unit"}, path)
        if not isinstance(trial["trial"], int) or isinstance(trial["trial"], bool) or trial["trial"] < 1:
            raise ValueError("%s.trial invalid" % path)
        trial_ids.append(trial["trial"])
        _finite_number(trial["value"], "%s.value" % path)
        _nonempty_string(trial["unit"], "%s.unit" % path)
    if len(trial_ids) != len(set(trial_ids)):
        raise ValueError("DUPLICATE_TRIAL_ID")
    _exact_keys(run["measurement"], {"metric", "value", "unit", "estimator", "confidence_interval", "summary_tolerance"}, "benchmark_run.measurement")
    for key in ("metric", "unit", "estimator"):
        _nonempty_string(run["measurement"][key], "benchmark_run.measurement.%s" % key)
    measured_value = _finite_number(run["measurement"]["value"], "benchmark_run.measurement.value")
    tolerance = _finite_number(run["measurement"]["summary_tolerance"], "benchmark_run.measurement.summary_tolerance")
    if tolerance < 0:
        raise ValueError("SUMMARY_TOLERANCE_NEGATIVE")
    if any(trial["unit"] != run["measurement"]["unit"] for trial in trials):
        raise ValueError("benchmark_run raw-trial and measurement units differ")
    values = [float(trial["value"]) for trial in trials]
    if run["measurement"]["estimator"] == "mean":
        recomputed = statistics.fmean(values)
    elif run["measurement"]["estimator"] == "median":
        recomputed = float(statistics.median(values))
    else:
        raise ValueError("UNSUPPORTED_ESTIMATOR")
    if abs(measured_value - recomputed) > tolerance:
        raise ValueError("SUMMARY_RECOMPUTE_MISMATCH")
    if protocol_manifest["metric"] != run["measurement"]["metric"] or protocol_manifest["unit"] != run["measurement"]["unit"]:
        raise ValueError("PROTOCOL_MEASUREMENT_BINDING_MISMATCH")
    if protocol_manifest["hardware_class"] != run["hardware"]["class"]:
        raise ValueError("PROTOCOL_HARDWARE_BINDING_MISMATCH")
    interval = run["measurement"]["confidence_interval"]
    if interval is not None:
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("benchmark_run.measurement.confidence_interval invalid")
        lower = _finite_number(interval[0], "benchmark_run.measurement.confidence_interval[0]")
        upper = _finite_number(interval[1], "benchmark_run.measurement.confidence_interval[1]")
        if lower > upper:
            raise ValueError("benchmark_run.measurement confidence interval reversed")
        if not lower <= measured_value <= upper:
            raise ValueError("SUMMARY_OUTSIDE_CONFIDENCE_INTERVAL")
    _exact_keys(run["correctness"], {"passed", "checks"}, "benchmark_run.correctness")
    if run["correctness"]["passed"] is not True:
        raise ValueError("benchmark_run.correctness.passed must be true")
    checks = run["correctness"]["checks"]
    if not isinstance(checks, list) or not checks:
        raise ValueError("benchmark_run.correctness.checks must be non-empty")
    for index, check in enumerate(checks):
        path = "benchmark_run.correctness.checks[%d]" % index
        _exact_keys(check, {"name", "passed", "tolerance"}, path)
        _nonempty_string(check["name"], "%s.name" % path)
        _nonempty_string(check["tolerance"], "%s.tolerance" % path)
        if check["passed"] is not True:
            raise ValueError("%s.passed must be true" % path)
    energy = run["energy"]
    if not isinstance(energy, dict):
        raise ValueError("benchmark_run.energy must be an object")
    if energy.get("status") == "NOT_OBSERVABLE":
        _exact_keys(energy, {"status", "blocker"}, "benchmark_run.energy")
        _nonempty_string(energy["blocker"], "benchmark_run.energy.blocker")
    elif energy.get("status") == "MEASURED_DELTA":
        _exact_keys(
            energy,
            {
                "status", "exporter_id", "sampled_at_start", "sampled_at_end",
                "joules_before", "joules_after", "work_units_before", "work_units_after",
                "work_unit", "fresh",
            },
            "benchmark_run.energy",
        )
        _nonempty_string(energy["exporter_id"], "benchmark_run.energy.exporter_id")
        _nonempty_string(energy["work_unit"], "benchmark_run.energy.work_unit")
        energy_start = _utc(energy["sampled_at_start"], "benchmark_run.energy.sampled_at_start")
        energy_end = _utc(energy["sampled_at_end"], "benchmark_run.energy.sampled_at_end")
        if not started <= energy_start <= energy_end <= completed:
            raise ValueError("ENERGY_WINDOW_NOT_MATCHED")
        joules_before = _finite_number(energy["joules_before"], "benchmark_run.energy.joules_before")
        joules_after = _finite_number(energy["joules_after"], "benchmark_run.energy.joules_after")
        work_before = _finite_number(energy["work_units_before"], "benchmark_run.energy.work_units_before")
        work_after = _finite_number(energy["work_units_after"], "benchmark_run.energy.work_units_after")
        if min(joules_before, joules_after, work_before, work_after) < 0:
            raise ValueError("ENERGY_COUNTER_NEGATIVE")
        if joules_after < joules_before or work_after <= work_before:
            raise ValueError("ENERGY_DELTA_INVALID")
        if energy["fresh"] is not True:
            raise ValueError("ENERGY_NOT_FRESH")
    else:
        raise ValueError("ENERGY_STATUS_INVALID")
    _exact_keys(run["freshness"], {"fresh_until"}, "benchmark_run.freshness")
    fresh_until = _utc(run["freshness"]["fresh_until"], "benchmark_run.freshness.fresh_until")
    _exact_keys(run["review"], {"status", "reviewer", "reviewed_at"}, "benchmark_run.review")
    if run["review"]["status"] != "APPROVED":
        raise ValueError("benchmark_run.review.status must be APPROVED")
    _nonempty_string(run["review"]["reviewer"], "benchmark_run.review.reviewer")
    reviewed = _utc(run["review"]["reviewed_at"], "benchmark_run.review.reviewed_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("VALIDATION_NOW_MISSING_TIMEZONE")
    current = current.astimezone(timezone.utc)
    if not preregistered <= started <= completed <= reviewed <= current:
        raise ValueError("RECEIPT_TIMELINE_INVALID")
    if (current - completed).total_seconds() > MAX_RECEIPT_AGE_SECONDS:
        raise ValueError("RECEIPT_TOO_OLD")
    if fresh_until < reviewed or (fresh_until - completed).total_seconds() > MAX_RECEIPT_AGE_SECONDS:
        raise ValueError("FRESHNESS_WINDOW_INVALID")
    _exact_keys(run["artifacts"], {"result_sha256", "result_bundle"}, "benchmark_run.artifacts")
    expected_result_digest = _digest(run["artifacts"]["result_sha256"], "benchmark_run.artifacts.result_sha256")
    bundle = run["artifacts"]["result_bundle"]
    _exact_keys(bundle, {"raw_trials", "measurement", "correctness", "energy"}, "benchmark_run.artifacts.result_bundle")
    if (bundle["raw_trials"] != run["raw_trials"] or bundle["measurement"] != run["measurement"]
            or bundle["correctness"] != run["correctness"] or bundle["energy"] != run["energy"]):
        raise ValueError("RESULT_BUNDLE_CONTENT_MISMATCH")
    canonical_bundle = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    actual_result_digest = "sha256:" + hashlib.sha256(canonical_bundle).hexdigest()
    if actual_result_digest != expected_result_digest:
        raise ValueError("RESULT_BUNDLE_DIGEST_MISMATCH")
    return run


class DigestReceiptLoader:
    """Bounded local loader.  It never lists, writes, signs, or fetches receipts."""

    def __init__(self, root: str | os.PathLike[str] | None = None, max_bytes: int = MAX_RECEIPT_BYTES):
        configured = root if root is not None else os.environ.get(RECEIPT_DIR_ENV)
        self.root: Path | None = None
        self._root_stat: os.stat_result | None = None
        if configured:
            raw_root = Path(configured).expanduser().absolute()
            try:
                root_lstat = os.lstat(raw_root)
                reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                is_reparse = bool(getattr(root_lstat, "st_file_attributes", 0) & reparse_flag)
                if stat.S_ISLNK(root_lstat.st_mode) or is_reparse or not stat.S_ISDIR(root_lstat.st_mode):
                    self.root = raw_root
                else:
                    self.root = raw_root.resolve(strict=True)
                    self._root_stat = os.stat(self.root)
            except OSError:
                self.root = raw_root
        self.max_bytes = max(1, min(int(max_bytes), MAX_RECEIPT_BYTES))

    def load(self, receipt_id: str) -> dict[str, Any]:
        match = _DIGEST_RE.fullmatch(receipt_id or "")
        if match is None:
            return {"ok": False, "reason": "INVALID_RECEIPT_ID"}
        if self.root is None:
            return {"ok": False, "reason": "RECEIPT_STORE_NOT_CONFIGURED"}
        path = self.root / (match.group(1) + ".json")
        try:
            if self._root_stat is None or not os.path.samestat(self._root_stat, os.stat(self.root)):
                return {"ok": False, "reason": "RECEIPT_STORE_IDENTITY_CHANGED"}
            before = os.lstat(path)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            is_reparse = bool(getattr(before, "st_file_attributes", 0) & reparse_flag)
            if stat.S_ISLNK(before.st_mode) or is_reparse:
                return {"ok": False, "reason": "RECEIPT_SYMLINK_REJECTED"}
            if not stat.S_ISREG(before.st_mode):
                return {"ok": False, "reason": "RECEIPT_NOT_FILE"}
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags)
            try:
                opened = os.fstat(fd)
                if not os.path.samestat(before, opened):
                    return {"ok": False, "reason": "RECEIPT_IDENTITY_CHANGED"}
                with os.fdopen(fd, "rb", closefd=False) as handle:
                    raw = handle.read(self.max_bytes + 1)
                after_fd = os.fstat(fd)
                after_path = os.lstat(path)
                if not (os.path.samestat(opened, after_fd) and os.path.samestat(opened, after_path)):
                    return {"ok": False, "reason": "RECEIPT_IDENTITY_CHANGED"}
                if opened.st_size != after_fd.st_size or opened.st_mtime_ns != after_fd.st_mtime_ns:
                    return {"ok": False, "reason": "RECEIPT_CHANGED_DURING_READ"}
                if not os.path.samestat(self._root_stat, os.stat(self.root)):
                    return {"ok": False, "reason": "RECEIPT_STORE_IDENTITY_CHANGED"}
            finally:
                os.close(fd)
            size = len(raw)
            if size < 2 or size > self.max_bytes or size != opened.st_size:
                return {"ok": False, "reason": "RECEIPT_SIZE_INVALID"}
            actual = hashlib.sha256(raw).hexdigest()
            if actual != match.group(1):
                return {"ok": False, "reason": "RECEIPT_DIGEST_MISMATCH"}
            envelope = json.loads(raw.decode("utf-8"))
            if not isinstance(envelope, dict):
                return {"ok": False, "reason": "RECEIPT_NOT_OBJECT"}
            return {"ok": True, "envelope": envelope, "path": str(path), "size": size}
        except FileNotFoundError:
            return {"ok": False, "reason": "RECEIPT_ABSENT"}
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"ok": False, "reason": "RECEIPT_READ_INVALID"}


def _gate(claim: dict[str, Any], reason: str) -> dict[str, Any]:
    result = copy.deepcopy(claim)
    result["szl_label"] = "ROADMAP"
    result["szl_measured"] = None
    result["measurement_gate"] = {
        "promoted": False,
        "reason": reason,
        "receipt_id": result.get("measurement_receipt_id"),
    }
    validate_claim(result)
    return result


def resolve_claim(claim: dict[str, Any], loader: DigestReceiptLoader | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Resolve one claim without effects. Any failed obligation remains ROADMAP."""
    validate_claim(claim)
    receipt_id = claim.get("measurement_receipt_id")
    if receipt_id is None:
        return _gate(claim, "NO_PERSISTED_BENCHMARK_RECEIPT")
    loaded = (loader or DigestReceiptLoader()).load(receipt_id)
    if not loaded.get("ok"):
        return _gate(claim, str(loaded.get("reason", "RECEIPT_LOAD_FAILED")))
    envelope = loaded["envelope"]
    verdict = szl_dsse.verify_envelope(envelope)
    if not verdict.get("verified"):
        return _gate(claim, "DSSE_%s" % str(verdict.get("reason", "VERIFICATION_FAILED")).upper().replace(" ", "_"))
    if verdict.get("payloadType") != RUN_PAYLOAD_TYPE:
        return _gate(claim, "WRONG_PAYLOAD_TYPE")
    payload = verdict.get("payload_decoded")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return _gate(claim, "VALIDATION_NOW_MISSING_TIMEZONE")
    current = current.astimezone(timezone.utc)
    try:
        validate_benchmark_run(payload, now=current)
    except ValueError as exc:
        code = str(exc)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,95}", code) is None:
            code = "BENCHMARK_SCHEMA_INVALID"
        return _gate(claim, code)
    if payload["claim_id"] != claim["claim_id"]:
        return _gate(claim, "WRONG_CLAIM_ID")
    if payload["protocol"]["id"] != claim["protocol"]["id"]:
        return _gate(claim, "WRONG_PROTOCOL")
    protocol_manifest = payload["protocol"]["manifest"]
    if (protocol_manifest["metric"] != claim["protocol"]["metric"]
            or protocol_manifest["unit"] != claim["protocol"]["unit"]
            or protocol_manifest["requires_energy"] != claim["protocol"]["requires_energy"]):
        return _gate(claim, "WRONG_PROTOCOL_SEMANTICS")
    if payload["hardware"]["class"] != claim["required_hardware_class"]:
        return _gate(claim, "WRONG_HARDWARE_CLASS")
    measurement = payload["measurement"]
    if measurement["metric"] != claim["protocol"]["metric"] or measurement["unit"] != claim["protocol"]["unit"]:
        return _gate(claim, "WRONG_MEASUREMENT_SEMANTICS")
    if claim["protocol"]["requires_energy"] and payload["energy"]["status"] != "MEASURED_DELTA":
        return _gate(claim, "ENERGY_NOT_OBSERVABLE")
    if _utc(payload["freshness"]["fresh_until"], "fresh_until") < current:
        return _gate(claim, "STALE_RECEIPT")
    result = copy.deepcopy(claim)
    result["szl_label"] = "MEASURED"
    result["szl_measured"] = copy.deepcopy(measurement)
    result["measurement_gate"] = {"promoted": True, "reason": "VERIFIED", "receipt_id": receipt_id}
    validate_claim(result)
    return result


def _claim(
    claim_id: str,
    claim: str,
    value: str,
    units: str,
    scope: str,
    organization: str,
    source_title: str,
    source_url: str,
    source_kind: str,
    protocol_id: str,
    metric: str,
    unit: str,
    protocol_description: str,
    hardware_class: str,
    blockers: list[str],
    requires_energy: bool = False,
) -> dict[str, Any]:
    record = {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "claim_id": claim_id,
        "claim": claim,
        "external_report": {
            "value": value,
            "units": units,
            "scope": scope,
            "source": {
                "organization": organization,
                "title": source_title,
                "url": source_url,
                "kind": source_kind,
            },
        },
        "protocol": {
            "id": protocol_id,
            "metric": metric,
            "unit": unit,
            "description": protocol_description,
            "requires_energy": requires_energy,
        },
        "required_hardware_class": hardware_class,
        "measurement_receipt_id": None,
        "blocked_by": blockers,
        "szl_label": "ROADMAP",
        "szl_measured": None,
        "measurement_gate": {"promoted": False, "reason": "NO_PERSISTED_BENCHMARK_RECEIPT", "receipt_id": None},
    }
    return validate_claim(record)


def claim_registry() -> list[dict[str, Any]]:
    """Primary-source-scoped claims. Reported values are not SZL measurements."""
    nvidia_blog = "https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-powers-faster-more-efficient-reasoning-for-long-running-agents/"
    return [
        _claim(
            "nemotron-ultra-throughput", "Nemotron 3 Ultra throughput", "up to 5x", "reported throughput ratio",
            "Vendor-reported system result for specified model/endpoints and workloads; not a generic model-only speedup.",
            "NVIDIA", "NVIDIA Nemotron 3 Ultra Powers Faster, More Efficient Reasoning for Long-Running Agents",
            nvidia_blog, "OFFICIAL_VENDOR_REPORT", "nemotron-throughput-v1", "system_throughput_ratio", "ratio",
            "Pinned model, serving stack, workload, comparator, concurrency, latency, throughput, failure, and energy trials.",
            "NVIDIA_NEMOTRON_ULTRA_QUALIFIED", ["qualified Ultra runtime unavailable", "no preregistered paired benchmark", "no signed benchmark receipt"],
        ),
        _claim(
            "nemotron-ultra-cost-to-task", "Nemotron 3 Ultra cost to task completion", "up to 30% lower", "reported cost-to-task",
            "Vendor-reported cost-to-task result; it is not a reasoning-accuracy uplift.",
            "NVIDIA", "NVIDIA Nemotron 3 Ultra Powers Faster, More Efficient Reasoning for Long-Running Agents",
            nvidia_blog, "OFFICIAL_VENDOR_REPORT", "nemotron-cost-to-task-v1", "cost_to_task_reduction", "percent_lower",
            "Pinned task suite, scorer, token accounting, price schedule, failures, and paired uncertainty.",
            "NVIDIA_NEMOTRON_ULTRA_QUALIFIED", ["qualified Ultra runtime unavailable", "task and pricing protocol not preregistered", "no signed benchmark receipt"],
        ),
        _claim(
            "nemotron-ultra-pinchbench", "Nemotron 3 Ultra PinchBench score", "91%", "reported PinchBench score",
            "Vendor-reported score on PinchBench; not generic benchmark accuracy.",
            "NVIDIA", "NVIDIA Nemotron 3 Ultra Powers Faster, More Efficient Reasoning for Long-Running Agents",
            nvidia_blog, "OFFICIAL_VENDOR_REPORT", "pinchbench-v1", "pinchbench_score", "percent",
            "Pinned PinchBench release, split, evaluator, prompts, seeds, retries, raw outcomes, and confidence interval.",
            "NVIDIA_NEMOTRON_ULTRA_QUALIFIED", ["qualified Ultra runtime unavailable", "PinchBench protocol not pinned", "no signed benchmark receipt"],
        ),
        _claim(
            "nemotron-ultra-ruler-1m", "Nemotron 3 Ultra RULER at 1M context", "95%", "reported RULER score",
            "Vendor-reported RULER score at 1M context; 1M is an extended configuration, not the native NIM default.",
            "NVIDIA", "NVIDIA Nemotron 3 Ultra Powers Faster, More Efficient Reasoning for Long-Running Agents",
            nvidia_blog, "OFFICIAL_VENDOR_REPORT", "ruler-1m-v1", "ruler_1m_score", "percent",
            "Official RULER tasks at native and extended context with pinned server flags, raw task scores, OOMs, latency, and KV-cache evidence.",
            "NVIDIA_NEMOTRON_ULTRA_QUALIFIED", ["qualified Ultra runtime unavailable", "1M extended-context configuration not qualified", "no signed benchmark receipt"],
        ),
        _claim(
            "cuml-pca-speedup", "cuML PCA wall-clock speedup", "typically 2x-10x", "reported acceleration range",
            "Official cuML accelerator benchmark guidance; workload-specific and not an S&P 500 or genomic PCA guarantee.",
            "RAPIDS", "cuml.accel Benchmarks", "https://docs.rapids.ai/api/cuml/stable/cuml-accel/benchmarks/",
            "OFFICIAL_DOCS", "cuml-pca-parity-v1", "pca_wall_clock_speedup", "ratio",
            "Preregistered matrix strata; distinct CPU/GPU paths; synchronized repeated timing; transfer-inclusive and compute-only results; numerical parity.",
            "CUDA_GPU", ["distinct cuML execution path not implemented", "matrix protocol and tolerances not preregistered", "no signed benchmark receipt"],
        ),
        _claim(
            "ripserpp-speedup", "Ripser++ persistence wall-clock speedup", "up to 30x", "author-reported speedup vs original Ripser",
            "Paper-reported result on specified datasets and hardware; not an NVIDIA-issued claim.",
            "Ripser++ authors", "Ripser++: A High-Performance GPU-Accelerated Vietoris-Rips Persistence Barcode Algorithm",
            "https://arxiv.org/abs/2003.07989", "ACADEMIC_PAPER", "ripserpp-parity-v1", "persistence_wall_clock_speedup", "ratio",
            "Pinned Ripser/Ripser++ revisions and identical inputs/options; repeated timings; memory; persistence-barcode parity under declared tolerance.",
            "CUDA_GPU", ["Ripser++ execution path not implemented", "current cycle-rank proxy is not a barcode oracle", "no signed benchmark receipt"],
        ),
    ]


def resolved_claims(loader: DigestReceiptLoader | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    return [resolve_claim(claim, loader=loader, now=now) for claim in claim_registry()]


def canonical_envelope_bytes(envelope: dict[str, Any]) -> bytes:
    """Canonical artifact representation used by the digest-addressed local store."""
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def envelope_receipt_id(envelope: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_envelope_bytes(envelope)).hexdigest()
