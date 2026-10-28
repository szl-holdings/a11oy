#!/usr/bin/env python3
"""Reconcile retained A11oy evidence without contacting a provider.

This utility is deliberately stdlib-only and read-only. It verifies the
retained JSON files' own SHA-256 values, compares protected-main identity with
the retained manifest, and reports runtime/HF drift and authority status. It
does not discover credentials, make HTTP requests, create receipts, or grant
execution authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "szl.local.evidence-reconciliation/v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def required(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(path)


def reconcile(
    summary_path: Path,
    manifest_path: Path,
    gap_path: Path,
    authority_path: Path,
    gpu_path: Path,
) -> dict[str, Any]:
    paths = {
        "summary": summary_path,
        "manifest": manifest_path,
        "preservation_gap": gap_path,
        "authority_review": authority_path,
        "gpu_preflight": gpu_path,
    }
    for path in paths.values():
        required(path)

    summary = load(summary_path)
    manifest = load(manifest_path)
    gap = load(gap_path)
    authority = load(authority_path)
    gpu = load(gpu_path)

    manifest_main = manifest.get("github_main")
    if not isinstance(manifest_main, dict):
        raise ValueError("manifest.github_main object required")
    runtime_identity = summary.get("runtime_identity")
    if not isinstance(runtime_identity, dict):
        raise ValueError("summary.runtime_identity object required")
    hf_runs = manifest.get("latest_hf_sync")
    if not isinstance(hf_runs, list):
        raise ValueError("manifest.latest_hf_sync list required")
    latest_hf_sha = None
    if hf_runs and isinstance(hf_runs[0], dict):
        latest_hf_sha = hf_runs[0].get("headSha")

    result = {
        "schema": SCHEMA,
        "evidence_class": "MEASURED",
        "scope": "LOCAL_READ_ONLY_RECONCILIATION",
        "provider_calls": 0,
        "provider_writes": 0,
        "gpu_mutations": 0,
        "credentials_read": False,
        "files": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "protected_main": {
            "summary_sha": summary.get("canonical_main"),
            "manifest_sha": manifest_main.get("sha"),
            "equal": summary.get("canonical_main") == manifest_main.get("sha"),
        },
        "runtime_hf_binding": {
            "runtime_source_sha": runtime_identity.get("source_revision"),
            "latest_hf_sync_sha": latest_hf_sha,
            "equal": runtime_identity.get("source_revision") == latest_hf_sha,
        },
        "acceptance": {
            "tests_run": summary.get("acceptance_tests_run"),
            "disposition": summary.get("acceptance_disposition"),
            "live_status": authority.get("live_acceptance"),
        },
        "authority": {
            "execution_authorized": authority.get("execution_authorized"),
            "runtime_admission": authority.get("runtime_admission"),
            "storage_admission": authority.get("storage_admission"),
        },
        "preservation": {"blocker": gap.get("blocker")},
        "gpu": {
            "allocation_admitted": gpu.get("gpu_allocation_admitted"),
            "workload_launched": gpu.get("workload_launched"),
            "vm_mutations": gpu.get("vm_mutations"),
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preservation-gap", type=Path, required=True)
    parser.add_argument("--authority-review", type=Path, required=True)
    parser.add_argument("--gpu-preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = reconcile(
            args.summary,
            args.manifest,
            args.preservation_gap,
            args.authority_review,
            args.gpu_preflight,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        # Fixed diagnostic: do not echo local paths, parser details, or file
        # contents into a receipt or CI log.
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "BLOCKED",
                    "reason": "INPUT_UNAVAILABLE",
                    "provider_calls": 0,
                    "provider_writes": 0,
                    "credentials_read": False,
                },
                sort_keys=True,
            )
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
