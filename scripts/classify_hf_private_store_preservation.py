#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish only a bounded status after a private stopped-store capture.

The full preservation report stays in runner temp and is never an artifact.
VERIFIED means a private byte capture succeeded; restore/deploy remain BLOCKED.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "szl.hf-private-store-preservation/v1"
PUBLIC_SCHEMA = "szl.hf-private-store-preservation-public/v1"
PREFIX = "a11oy/incident-preservation/v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
RUN_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
RUN_ATTEMPT = re.compile(r"[1-9][0-9]{0,5}\Z")
NONCE = re.compile(r"[0-9a-f]{32}\Z")


def classify(report: Any, *, exit_code: int, expected_sha: str,
             run_id: str, run_attempt: str) -> tuple[dict[str, Any], bool]:
    """Fail closed and discard all private fields, including provider text."""
    source_valid = isinstance(expected_sha, str) and SHA40.fullmatch(expected_sha) is not None
    run_valid = (isinstance(run_id, str) and RUN_ID.fullmatch(run_id) is not None
                 and isinstance(run_attempt, str) and RUN_ATTEMPT.fullmatch(run_attempt) is not None)
    public = {
        "schema": PUBLIC_SCHEMA,
        "source_revision": expected_sha if source_valid else "UNVERIFIED",
        "run_id": run_id if run_valid else "UNVERIFIED",
        "run_attempt": run_attempt if run_valid else "UNVERIFIED",
        "state": "BLOCKED",
        "preservation_state": "NOT_VERIFIED",
        "diagnostic_code": "PRESERVATION_REPORT_INVALID",
        "deployment_admitted": False,
        "restore_admitted": False,
    }
    if not isinstance(report, dict) or not source_valid or not run_valid:
        return public, False
    capture_id = report.get("capture_id")
    manifest = report.get("private_manifest")
    observations = report.get("observations")
    valid = (
        exit_code == 2
        and report.get("schema") == SCHEMA
        and report.get("space") == "SZLHOLDINGS/a11oy"
        and report.get("bucket") == "SZLHOLDINGS/szl-evidence"
        and report.get("source_revision") == expected_sha
        and report.get("state") == "BLOCKED"
        and report.get("preservation_state") == "VERIFIED"
        and report.get("diagnostic_code") == "STORAGE_RECOVERY_REQUIRED"
        and report.get("storage_contract") == "BUCKET_MOUNTED_SQLITE_UNQUALIFIED"
        and report.get("deployment_admitted") is False
        and report.get("restore_admitted") is False
        and report.get("originals_mutated") is False
        and report.get("space_mutated") is False
        and report.get("secret_values_recorded") is False
        and report.get("private_bytes_in_public_artifacts") is False
        and report.get("initial_identities_stable") is True
        and report.get("captured_originals_unchanged_after_inspection") is True
        and isinstance(capture_id, str)
        and capture_id.startswith(f"{run_id}-{run_attempt}-{expected_sha}-")
        and NONCE.fullmatch(capture_id[len(f"{run_id}-{run_attempt}-{expected_sha}-"):]) is not None
        and report.get("private_capture_prefix") == f"{PREFIX}/{capture_id}"
        and isinstance(manifest, dict)
        and manifest.get("path") == f"{PREFIX}/{capture_id}/preservation-manifest.json"
        and isinstance(manifest.get("sha256"), str)
        and SHA64.fullmatch(manifest["sha256"]) is not None
        and isinstance(observations, list)
        and len(observations) >= 2
        and all(isinstance(value, dict) and value.get("stage") in {"PAUSED", "RUNTIME_ERROR"}
                for value in observations)
    )
    if valid:
        public.update(preservation_state="VERIFIED", diagnostic_code="STORAGE_RECOVERY_REQUIRED",
                      private_manifest_sha256=manifest["sha256"])
    return public, bool(valid)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--preservation-exit-code", required=True)
    args = parser.parse_args()
    try:
        if args.report.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("report exceeds bound")
        report = json.loads(args.report.read_text(encoding="utf-8"))
        exit_code = int(args.preservation_exit_code)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
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
