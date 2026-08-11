#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Round-5 release gate for operational/audit alignment.

The gate emits one machine-readable report under `audit/release-gate.json` and
forces fail-closed behavior for:

- round-5 bootstrap probe generation and verification
- lexicon lock enforcement
- frontdoor truth and idempotence checks
- Hugging Face ecosystem audit checks
- GitHub Enterprise access audit (no `write-ready` debt for write-required targets)
"""

from __future__ import annotations

import argparse
import sys
import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audit"
REPORT_PATH = AUDIT_DIR / "release-gate.json"
GITHUB_AUDIT_PATH = AUDIT_DIR / "github-access-audit.json"
LEXICON_REPORT_PATH = AUDIT_DIR / "frontier-lexicon-gate.json"
CHECKLIST_PATH = ROOT / "docs" / "github-enterprise-access-checklist.json"
PYTHON = [sys.executable, "-I", "-B"]


@dataclass
class CommandResult:
    name: str
    command: list[str]
    status: str
    return_code: int | None
    duration_ms: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_path: str
    stderr_path: str


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_command(name: str, command: list[str], *, require: bool = True) -> tuple[CommandResult, str]:
    start = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        check=False,
        capture_output=True,
    )
    duration = int((time.perf_counter() - start) * 1000)
    safe_name = name.replace("/", "-").replace(" ", "_")
    log_dir = AUDIT_DIR / "release-gate-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{safe_name}.stdout.txt"
    stderr_path = log_dir / f"{safe_name}.stderr.txt"
    stdout_path.write_text(process.stdout or "", encoding="utf-8")
    stderr_path.write_text(process.stderr or "", encoding="utf-8")
    status = "PASS" if process.returncode == 0 else ("SKIP" if not require else "FAIL")
    result = CommandResult(
        name=name,
        command=command,
        status=status,
        return_code=process.returncode,
        duration_ms=duration,
        stdout_sha256=_sha256_text(process.stdout or ""),
        stderr_sha256=_sha256_text(process.stderr or ""),
        stdout_path=str(stdout_path.relative_to(ROOT)),
        stderr_path=str(stderr_path.relative_to(ROOT)),
    )
    return result, stdout_path.read_text(encoding="utf-8")


def _evaluate_github_audit(path: Path) -> tuple[str, list[str]]:
    if not path.is_file():
        return "FAIL", [f"github audit file missing: {path}"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    notes: list[str] = []
    repos = raw.get("repos", [])
    if not isinstance(repos, list) or not repos:
        return "FAIL", ["github audit has no repos"]

    errors: list[str] = []
    for repo in repos:
        name = repo.get("repo") or "<unknown>"
        minimum = str(repo.get("minimumPermission", "write")).lower()
        status = str(repo.get("status", "")).lower()
        if minimum == "write" and status != "write-ready":
            errors.append(f"{name}: status={status}, minimum={minimum}")
        if status == "unavailable":
            errors.append(f"{name}: unavailable")
    if raw.get("auth", {}).get("authenticated") is not True:
        errors.append("gh authentication is not active")
    if errors:
        return "FAIL", errors
    return "PASS", notes


def _validate_frontier_artifacts() -> tuple[str, list[str]]:
    checks = [
        "audit/frontier-convergence-manifest.json",
        "audit/frontier-claims-ledger.json",
        "audit/frontier-contradictions-ledger.json",
        "audit/frontier-command-probes.json",
        "evidence/conformance/eu-ai-act-article-12.yaml",
        "audit/frontier-lexicon-gate.json",
    ]
    status = "PASS"
    notes: list[str] = []
    for rel in checks:
        path = ROOT / rel
        if not path.exists():
            status = "FAIL"
            notes.append(f"missing artifact: {rel}")
    return status, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Round-5 release gate")
    parser.add_argument("--run", action="store_true", help="execute checks and emit report")
    parser.add_argument("--verify", action="store_true", help="verify previously emitted report")
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORT_PATH,
        help="path to write/read the gate report",
    )
    args = parser.parse_args()

    if not args.run and not args.verify:
        args.run = True

    command_plan = [
        ("szl-convergence-bootstrap", PYTHON + ["tools/szl_convergence_bootstrap.py", "--run"]),
        (
            "round5-lexicon-gate",
            PYTHON
            + [
                "tools/lexicon_gate.py",
                "--check",
                "--report",
                str(LEXICON_REPORT_PATH),
            ],
        ),
        ("frontdoor-truth", PYTHON + ["scripts/check_a11oy_frontdoor_truth.py", "a11oy_landing.html"]),
        (
            "frontdoor-repair-check",
            PYTHON + ["scripts/repair_a11oy_frontdoor.py", "a11oy_landing.html", "--check"],
        ),
        ("hf-ecosystem-check", PYTHON + ["scripts/audit_huggingface_ecosystem.py", "--check"]),
        (
            "github-access-check",
            PYTHON + ["scripts/audit_github_access_permissions.py", "--checklist", str(CHECKLIST_PATH), "--output", str(GITHUB_AUDIT_PATH), "--validate"],
        ),
        ("szl-convergence-verify", PYTHON + ["tools/szl_convergence_bootstrap.py", "--verify"]),
    ]

    if args.run:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        command_results: list[dict[str, Any]] = []
        command_status: list[str] = []
        for name, command in command_plan:
            result, _ = _run_command(name, command)
            command_results.append(asdict(result))
            if result.status == "FAIL":
                command_status.append(result.status)

        github_status, github_notes = _evaluate_github_audit(GITHUB_AUDIT_PATH)
        frontier_status, frontier_notes = _validate_frontier_artifacts()

        passed = (
            not command_status
            and github_status == "PASS"
            and frontier_status == "PASS"
        )
        report = {
            "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "schemaVersion": 1,
            "status": "PASS" if passed else "FAIL",
            "commands": command_results,
            "githubAccess": {
                "status": github_status,
                "notes": github_notes,
            },
            "frontierArtifacts": {
                "status": frontier_status,
                "notes": frontier_notes,
            },
            "requiredArtifacts": {
                "frontierBootstrap": [
                    "audit/frontier-convergence-manifest.json",
                    "audit/frontier-claims-ledger.json",
                    "audit/frontier-contradictions-ledger.json",
                    "audit/frontier-command-probes.json",
                    "evidence/conformance/eu-ai-act-article-12.yaml",
                ],
                "frontierGate": [
                    "audit/frontier-lexicon-gate.json",
                    "audit/release-gate.json",
                ],
            },
        }
        command_count = len([item for item in command_results if item["status"] in {"PASS", "FAIL"}])
        report["commandCount"] = command_count
        report["commandFailures"] = [item["name"] for item in command_results if item["status"] == "FAIL"]
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if passed else 1

    if args.verify:
        if not args.report.is_file():
            print(f"release-gate report missing: {args.report}")
            return 1
        report = json.loads(args.report.read_text(encoding="utf-8"))
        missing = []
        if report.get("status") != "PASS":
            missing.append("status != PASS")
        if report.get("githubAccess", {}).get("status") != "PASS":
            missing.append("githubAccess.status != PASS")
        if report.get("frontierArtifacts", {}).get("status") != "PASS":
            missing.append("frontierArtifacts.status != PASS")
        if missing:
            print("release-gate verify failed:")
            for note in missing:
                print(f"- {note}")
            return 1
        print("release-gate verify: PASS")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
