#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Build the pinned LutarPolicy package and retain positive and negative evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / "formal" / "LutarPolicy"
AUDIT = ROOT / "audit"
LOGS = AUDIT / "formal-logs"
RECEIPT = AUDIT / "formal-verification-receipt.json"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def formal_digest() -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in FORMAL.rglob("*")
        if path.is_file()
        and ".lake" not in path.parts
        and path.name not in {".gitignore"}
    )
    for path in paths:
        rel = path.relative_to(FORMAL).as_posix().encode("utf-8")
        body = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return f"sha256:{digest.hexdigest()}"


def run(
    name: str,
    args: list[str],
    *,
    expected_failure_markers: tuple[str, ...] = (),
) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=FORMAL,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    LOGS.mkdir(parents=True, exist_ok=True)
    stdout_path = LOGS / f"{name}.stdout.txt"
    stderr_path = LOGS / f"{name}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    output = f"{proc.stdout}\n{proc.stderr}"
    expected_failure = bool(expected_failure_markers)
    passed = (
        proc.returncode != 0
        and all(marker in output for marker in expected_failure_markers)
        if expected_failure
        else proc.returncode == 0
    )
    return {
        "name": name,
        "command": [Path(args[0]).name, *args[1:]],
        "expected": "nonzero exit" if expected_failure else "zero exit",
        "returncode": proc.returncode,
        "status": "PASS" if passed else "FAILED",
        "stdout": stdout_path.relative_to(ROOT).as_posix(),
        "stdout_sha256": digest_file(stdout_path),
        "stderr": stderr_path.relative_to(ROOT).as_posix(),
        "stderr_sha256": digest_file(stderr_path),
    }


def version(executable: str) -> str:
    return subprocess.check_output(
        [executable, "--version"],
        cwd=FORMAL,
        text=True,
        encoding="utf-8",
    ).strip()


def main() -> int:
    lake = shutil.which("lake")
    lean = shutil.which("lean")
    if not lake or not lean:
        print("BLOCKED: `lake` and `lean` must be available on PATH")
        return 2
    AUDIT.mkdir(parents=True, exist_ok=True)
    commands = [
        run("lake-update", [lake, "update"]),
        run("lake-build", [lake, "build"]),
        run(
            "theorems",
            [lake, "env", "lean", "LutarPolicy/Theorems.lean"],
        ),
        run(
            "mutation",
            [lake, "env", "lean", "LutarPolicy/Tests/Mutation.lean"],
        ),
        run(
            "critical-premise-removal",
            [
                lake,
                "env",
                "lean",
                "negative-fixtures/RemovedDefaultDenialPremise.lean",
            ],
            expected_failure_markers=(
                "error: tactic 'rfl' failed",
                "evaluate state request",
                "Decision.reject",
            ),
        ),
    ]
    theorem_source = (FORMAL / "LutarPolicy" / "Theorems.lean").read_text(
        encoding="utf-8"
    )
    claimed = sorted(
        set(re.findall(r"(?m)^theorem\s+(T[12]_[A-Za-z0-9_]+)", theorem_source))
    )
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    candidate_paths = ("formal/LutarPolicy", "scripts/verify_lutar_policy.py")
    paths_match_source_commit = (
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *candidate_paths],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
        and subprocess.run(
            ["git", "diff", "--cached", "--quiet", "HEAD", "--", *candidate_paths],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )
    all_passed = all(item["status"] == "PASS" for item in commands)
    all_passed = all_passed and paths_match_source_commit
    manifest = FORMAL / "lake-manifest.json"
    receipt = {
        "generated_at": now(),
        "claim_label": "IMPLEMENTED NOT DEPLOYED",
        "kernel_check": "PASS" if all_passed else "FAILED",
        "source_commit": source_commit,
        "paths_match_source_commit": paths_match_source_commit,
        "public_proved_count_change": 0,
        "public_proved_count_reason": (
            "Only T1/T2 are in scope and independent English-statement review is absent."
        ),
        "toolchain": {
            "lean": version(lean),
            "lake": version(lake),
            "lean_toolchain": (FORMAL / "lean-toolchain").read_text(
                encoding="utf-8"
            ).strip(),
            "mathlib_input": "git#v4.13.0",
            "lake_manifest_sha256": digest_file(manifest) if manifest.exists() else None,
        },
        "formal_artifact_digest": formal_digest(),
        "theorem_declarations": claimed,
        "non_vacuity": {
            "positive_witness": "non_vacuity_authorized_action_exists",
            "negative_witness": "negative_default_denial_witness",
            "receipt_negative_witness": "negative_receipt_witness",
            "assumption_mutation": "LutarPolicy/Tests/Mutation.lean",
            "critical_premise_removal": (
                "negative-fixtures/RemovedDefaultDenialPremise.lean"
            ),
        },
        "independent_statement_review": {
            "status": "AWAITING AUTHORIZATION",
            "reason": "A second human reviewer has not signed the English theorem statements.",
        },
        "commands": commands,
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    baseline_path = AUDIT / "lean-baseline.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline["lutar_policy"] = {
            "claim_label": receipt["claim_label"],
            "kernel_check": receipt["kernel_check"],
            "formal_artifact_digest": receipt["formal_artifact_digest"],
            "receipt": RECEIPT.relative_to(ROOT).as_posix(),
        }
        baseline["clean_build"] = {
            "status": "PASS" if all_passed else "FAILED",
            "receipt": RECEIPT.relative_to(ROOT).as_posix(),
        }
        baseline_path.write_text(
            json.dumps(baseline, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(receipt, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
