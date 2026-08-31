#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Create, restore, and byte-compare a temporary archive of the current source commit."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_PATHS = [
    "docs/FORMAL_SCOPE_AND_LIMITATIONS.md",
    "docs/SERIES_A_DILIGENCE.md",
    "docs/THREAT_MODEL.md",
    "docs/architecture.md",
    "formal/LutarPolicy",
    "package.json",
    "packages/policy",
    "packages/receipt-substrate",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "proofs/lutar-lean",
    "schemas",
    "scripts/audit_web_workspace_dependencies.py",
    "scripts/build_operation_verified_throughput_reports.py",
    "scripts/operation_verified_throughput_inventory.py",
    "scripts/verify_lutar_policy.py",
    "scripts/verify_policy_runtime.py",
    "scripts/verify_release_commands.py",
    "scripts/verify_source_restore.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if os.path.commonpath((root, target)) != str(root):
            raise RuntimeError(f"unsafe archive member: {member.name}")
    archive.extractall(destination, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "audit" / "source-restore-evidence.json",
    )
    args = parser.parse_args()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    with tempfile.TemporaryDirectory(prefix="a11oy-source-restore-") as temp_name:
        temp = Path(temp_name)
        archive_path = temp / "source.tar"
        restored = temp / "restored"
        restored.mkdir()
        subprocess.run(
            [
                "git",
                "archive",
                "--format=tar",
                f"--output={archive_path}",
                commit,
                "--",
                *CRITICAL_PATHS,
            ],
            cwd=ROOT,
            check=True,
        )
        with tarfile.open(archive_path, "r") as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            expected = {}
            for member in members:
                handle = archive.extractfile(member)
                if handle is None:
                    raise RuntimeError(f"cannot read archive member: {member.name}")
                expected[member.name] = hashlib.sha256(handle.read()).hexdigest()
        with tarfile.open(archive_path, "r") as archive:
            safe_extract(archive, restored)
        actual = {
            path.relative_to(restored).as_posix(): sha256(path)
            for path in restored.rglob("*")
            if path.is_file()
        }
        mismatches = sorted(
            name
            for name in set(expected) | set(actual)
            if expected.get(name) != actual.get(name)
        )
        evidence = {
            "generated_at": generated_at,
            "label": "MEASURED" if not mismatches else "FAILED",
            "scope": "governed release critical-path source restore only; not a production data or infrastructure backup",
            "included_paths": CRITICAL_PATHS,
            "source_commit": commit,
            "archive_sha256": sha256(archive_path),
            "regular_files": len(expected),
            "restored_regular_files": len(actual),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "temporary_archive_retained": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
