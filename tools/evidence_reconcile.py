#!/usr/bin/env python3
"""Reconcile retained A11oy evidence without contacting a provider.

This utility is deliberately stdlib-only and read-only. It verifies the
retained JSON files' own SHA-256 values, compares protected-main identity with
the retained manifest, and reports runtime/HF drift and authority status. It
does not discover credentials, make HTTP requests, create receipts, or grant
execution authority.

Each input is read once, so the reported SHA-256 is of the same bytes that were
parsed. An identity comparison is MATCH or MISMATCH only when both sides are
revisions in the form the identity sources emit: 40 or 64 lowercase hex
characters, both the same length and not all zeros. Anything else, including a
missing value, a placeholder such as "unknown" or "null", uppercase or padded
text, or an abbreviated revision, is UNKNOWN, so two placeholders are never
reported as equal. Optional pinned digests bind the inputs to bytes the caller
already trusts. This tool verifies no signature, so it never reports a binding
as authenticated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import string
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "szl.local.evidence-reconciliation/v1"
_HEX_DIGITS = frozenset(string.hexdigits)
_REVISION = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def required(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(path)


def read_once(path: Path) -> bytes:
    """Return the file's bytes from one open that refuses a swapped-in symlink."""
    required(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        return handle.read()


def load(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def revision(value: Any) -> str | None:
    """The value if it is a full lowercase hex revision, else None."""
    if isinstance(value, str) and _REVISION.fullmatch(value) and value.strip("0"):
        return value
    return None


def compare_identity(left: Any, right: Any) -> dict[str, Any]:
    """MATCH or MISMATCH only for two revisions of one length, else UNKNOWN."""
    left, right = revision(left), revision(right)
    if left is None or right is None or len(left) != len(right):
        status = "UNKNOWN"
    else:
        status = "MATCH" if left == right else "MISMATCH"
    return {"status": status, "equal": status == "MATCH"}


def checked_pins(pins: Mapping[str, Any], names: Any) -> dict[str, str]:
    if not isinstance(pins, Mapping) or set(pins) - set(names):
        raise ValueError("pinned digests must map known input names")
    for value in pins.values():
        if not isinstance(value, str) or len(value) != 64 or not set(value) <= _HEX_DIGITS:
            raise ValueError("pinned digest must be 64 hex characters")
    return {name: value.upper() for name, value in pins.items()}


def reconcile(
    summary_path: Path,
    manifest_path: Path,
    gap_path: Path,
    authority_path: Path,
    gpu_path: Path,
    pinned_digests: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    paths = {
        "summary": summary_path,
        "manifest": manifest_path,
        "preservation_gap": gap_path,
        "authority_review": authority_path,
        "gpu_preflight": gpu_path,
    }
    raw = {name: read_once(path) for name, path in paths.items()}
    pins = checked_pins(pinned_digests or {}, paths)

    summary = load(raw["summary"])
    manifest = load(raw["manifest"])
    gap = load(raw["preservation_gap"])
    authority = load(raw["authority_review"])
    gpu = load(raw["gpu_preflight"])

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

    files = {}
    for name, path in paths.items():
        actual = sha256(raw[name])
        pinned = pins.get(name)
        if pinned is None:
            digest_status = "NOT_PINNED"
        else:
            digest_status = "MATCHED" if pinned == actual else "MISMATCHED"
        files[name] = {"path": str(path), "sha256": actual,
                       "pinned_sha256": pinned, "digest_status": digest_status}

    protected_main = {
        "summary_sha": summary.get("canonical_main"),
        "manifest_sha": manifest_main.get("sha"),
        **compare_identity(summary.get("canonical_main"), manifest_main.get("sha")),
    }
    runtime_hf_binding = {
        "runtime_source_sha": runtime_identity.get("source_revision"),
        "latest_hf_sync_sha": latest_hf_sha,
        **compare_identity(runtime_identity.get("source_revision"), latest_hf_sha),
    }

    digest_states = {entry["digest_status"] for entry in files.values()}
    if "MISMATCHED" in digest_states:
        level = "PINNED_DIGEST_MISMATCH"
    elif "UNKNOWN" in (protected_main["status"], runtime_hf_binding["status"]):
        level = "UNKNOWN"
    elif digest_states == {"MATCHED"}:
        level = "PINNED_DIGESTS_MATCHED"
    else:
        level = "LOCAL_CONSISTENCY"

    result = {
        "schema": SCHEMA,
        "evidence_class": "MEASURED",
        "scope": "LOCAL_READ_ONLY_RECONCILIATION",
        "provider_calls": 0,
        "provider_writes": 0,
        "gpu_mutations": 0,
        "credentials_read": False,
        "files": files,
        "binding": {"level": level, "authenticated": False},
        "protected_main": protected_main,
        "runtime_hf_binding": runtime_hf_binding,
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
    parser.add_argument("--pinned-digests", type=Path,
                        help="JSON object mapping input names to trusted SHA-256 values")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        pins = load(read_once(args.pinned_digests)) if args.pinned_digests else None
        report = reconcile(
            args.summary,
            args.manifest,
            args.preservation_gap,
            args.authority_review,
            args.gpu_preflight,
            pinned_digests=pins,
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
