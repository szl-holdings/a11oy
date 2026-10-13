#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Publish bounded historical rehearsal status, never restore admission.

The full qualification report stays private. Only the source-owned historical
capture is eligible; a successful rehearsal says nothing about later writes.
This helper classifies a completed inspection and does not inspect databases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_PATH = ROOT / "docs/operations/evidence/gdw-capture-37223162231.json"
ANCHORS_PATH = ROOT / "docs/operations/evidence/gdw-recovery-historical-anchors.json"
SCHEMA = "szl.gdw-store-recovery-qualification/v1"
PUBLIC_SCHEMA = "szl.gdw-historical-qualification-public/v1"
MAX_INPUT_BYTES = 2 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
RUN_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
RUN_ATTEMPT = re.compile(r"[1-9][0-9]{0,5}\Z")
ANCHOR_REFERENCE_FIELDS = (
    "source_revision", "workflow_run_id", "workflow_attempt", "artifact_id",
    "artifact_archive_sha256", "capture_report_sha256",
)
FALSE_FLAGS = (
    "deployment_admitted", "restore_admitted", "provider_writes_performed",
    "originals_mutated", "secret_values_recorded", "private_bytes_in_public_artifacts",
    "later_acknowledged_writes_verified",
)
UNCHANGED_FLAGS = (
    "captured_originals_unchanged", "all_declared_stored_values_unchanged",
    "schema_unchanged", "receipt_bytes_unchanged", "database_generation_unchanged",
)


def _json(data: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def invalid_constant(_value: str) -> None:
        raise ValueError("non-finite number")

    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds bound")
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)


def _bounded_bytes(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                         | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_INPUT_BYTES:
            raise ValueError("input exceeds bound")
        data = handle.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds bound")
    return data


def _matches(value: Any, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _anchor_verified(label: str, observed: dict, anchor: dict) -> bool:
    if label == "gdw":
        return (
            observed.get("signature_verification") == "VERIFIED_PINNED_PUBLIC_KEY"
            and observed.get("pinned_key_der_sha256") == anchor["pinned_key_der_sha256"]
            and observed.get("chain_sha256") == anchor["chain_sha256"]
            and observed.get("audit_scope_unchanged") is True
            and observed.get("report_payload_bindings_verified") is True
            and _matches(observed.get("payload_sha256"), SHA64)
        )
    return (
        observed.get("signature_verification") == "NOT_PERFORMED"
        and observed.get("storage_created_at_unchanged") is True
        and type(observed.get("minimum_receipt_count")) is int
        and observed.get("minimum_receipt_count") == anchor["minimum_receipt_count"]
        and type(observed.get("receipt_count")) is int
        and anchor["minimum_receipt_count"] <= observed["receipt_count"] <= 1_000_000
    )


def _database_verified(label: str, database: Any, anchor: dict, capture: dict) -> bool:
    if type(database) is not dict:
        return False
    original = database.get("original_historical_anchor")
    candidate = database.get("candidate_historical_anchor")
    integrity = database.get("candidate_integrity")
    return (
        database.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
        and database.get("diagnostic_code") == "RESTORE_CONTRACT_REQUIRED"
        and database.get("historical_anchor_state") == "VERIFIED"
        and database.get("restore_admitted") is False
        and database.get("durable_storage_qualified") is False
        and all(database.get(key) is True for key in UNCHANGED_FLAGS)
        and database.get("database_generation_id") == anchor["database_generation_id"]
        == capture["database_generation_id"]
        and type(original) is dict and type(candidate) is dict
        and original.get("state") == "VERIFIED"
        and json.dumps(candidate, sort_keys=True, allow_nan=False)
        == json.dumps(original, sort_keys=True, allow_nan=False)
        and type(original.get("sequence")) is int
        and original.get("sequence") == anchor["sequence"]
        and original.get("receipt_sha256") == anchor["receipt_sha256"]
        and original.get("generation_unchanged") is True
        and _anchor_verified(label, original, anchor)
        and type(integrity) is dict and integrity.get("classification") == "OK"
        and integrity.get("integrity_check_complete") is True
        and type(integrity.get("unreferenced_page_count")) is int
        and integrity.get("unreferenced_page_count") == 0
        and _matches(integrity.get("result_sha256"), SHA64)
        and type(integrity.get("foreign_key_violation_count")) is int
        and integrity.get("foreign_key_violation_count") == 0
        and integrity.get("foreign_key_check_complete") is True
    )


def classify(report: Any, *, exit_code: int, expected_sha: str,
             run_id: str, run_attempt: str) -> tuple[dict[str, Any], bool]:
    """Fail closed and project constants and validated identifiers only."""
    source_valid = _matches(expected_sha, SHA40)
    run_valid = _matches(run_id, RUN_ID) and _matches(run_attempt, RUN_ATTEMPT)
    public = {
        "schema": PUBLIC_SCHEMA,
        "source_revision": expected_sha if source_valid else "UNVERIFIED",
        "run_id": run_id if run_valid else "UNVERIFIED",
        "run_attempt": run_attempt if run_valid else "UNVERIFIED",
        "evidence_class": "MEASURED",
        "scope": "HISTORICAL_CAPTURE_ONLY",
        "state": "BLOCKED",
        "historical_rehearsal_state": "NOT_VERIFIED",
        "diagnostic_code": "HISTORICAL_QUALIFICATION_REPORT_INVALID",
        "restore_admitted": False,
        "deployment_admitted": False,
        "later_acknowledged_writes_verified": False,
    }
    if type(report) is not dict or not source_valid or not run_valid:
        return public, False
    try:
        capture_bytes = _bounded_bytes(CAPTURE_PATH)
        capture = _json(capture_bytes)
        anchors = _json(_bounded_bytes(ANCHORS_PATH))
        reference = report.get("historical_anchor_reference")
        databases = report.get("databases")
        expected_reference = {key: anchors[key] for key in ANCHOR_REFERENCE_FIELDS}
        valid = (
            type(exit_code) is int and exit_code == 0
            and report.get("schema") == SCHEMA
            and report.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
            and report.get("inspector_source_revision") == expected_sha
            and report.get("diagnostic_code") == "RESTORE_CONTRACT_REQUIRED"
            and report.get("historical_anchor_state") == "VERIFIED"
            and report.get("captured_historical_anchor_state") == "VERIFIED"
            and all(report.get(key) is False for key in FALSE_FLAGS)
            and report.get("space_mutated", False) is False
            and capture["schema"] == "szl.hf-private-store-preservation/v1"
            and capture["space"] == "SZLHOLDINGS/a11oy"
            and capture["bucket"] == "SZLHOLDINGS/szl-evidence"
            and capture["preservation_state"] == "VERIFIED"
            and capture["restore_admitted"] is False and capture["deployment_admitted"] is False
            and anchors["schema"] == "szl.gdw-recovery-historical-anchors/v1"
            and anchors["source_repository"] == "szl-holdings/a11oy"
            and anchors["capture_report_sha256"] == hashlib.sha256(capture_bytes).hexdigest()
            and _matches(anchors["source_revision"], SHA40)
            and _matches(anchors["artifact_archive_sha256"], SHA64)
            and all(type(anchors[key]) is int and 0 < anchors[key] < 10**20
                    for key in ("workflow_run_id", "workflow_attempt", "artifact_id"))
            and type(reference) is dict and reference == expected_reference
            and all(type(reference[key]) is type(value) for key, value in expected_reference.items())
            and report.get("capture_id") == capture["capture_id"]
            and report.get("capture_source_revision") == capture["source_revision"]
            and report.get("preservation_manifest_sha256") == capture["private_manifest"]["sha256"]
            and type(databases) is dict and set(databases) == {"gdw", "series_a"}
            and all(_database_verified(label, databases[label], anchors[label], capture["databases"][label])
                    for label in ("gdw", "series_a"))
        )
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        valid = False
    if valid:
        public.update(historical_rehearsal_state="VERIFIED",
                      diagnostic_code="RESTORE_CONTRACT_REQUIRED")
    return public, bool(valid)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--qualification-exit-code", required=True)
    args = parser.parse_args()
    try:
        report = _json(_bounded_bytes(args.report))
        exit_code = int(args.qualification_exit_code)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        report, exit_code = None, -1
    public, verified = classify(report, exit_code=exit_code,
                                expected_sha=args.expected_source_sha,
                                run_id=args.run_id, run_attempt=args.run_attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(public, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(public, sort_keys=True))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
