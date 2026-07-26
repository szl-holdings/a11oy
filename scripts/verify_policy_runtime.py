#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Run and retain the TypeScript authorization-boundary conformance evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
LOGS = AUDIT / "policy-runtime-logs"
RECEIPT = AUDIT / "policy-runtime-verification.json"
SCRIPTS = (
    "test:policy-contract",
    "test:policy-negative",
    "test:policy-mutation",
    "test:policy-differential",
)
IMPLEMENTATION_PATHS = (
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "packages/policy/src/verified/authorization_boundary.ts",
    "packages/policy/src/verified/__tests__/authorization_boundary.test.ts",
    "packages/policy/src/index.ts",
    "packages/policy/package.json",
    "schemas/action-request.schema.json",
    "schemas/authorization-receipt.schema.json",
    "schemas/deployment-identity.schema.json",
    "scripts/verify_policy_runtime.py",
)


def digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def run(name: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    LOGS.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name)
    stdout_path = LOGS / f"{safe_name}.stdout.txt"
    stderr_path = LOGS / f"{safe_name}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    parsed = None
    for line in reversed(proc.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("status"):
            parsed = value
            break
    return {
        "name": name,
        "command": [Path(args[0]).name, *args[1:]],
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAILED",
        "result": parsed,
        "stdout": stdout_path.relative_to(ROOT).as_posix(),
        "stdout_sha256": digest(stdout_path),
        "stderr": stderr_path.relative_to(ROOT).as_posix(),
        "stderr_sha256": digest(stderr_path),
    }


def main() -> int:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        print("BLOCKED: `pnpm` must be available on PATH")
        return 2
    commands = [run(name, [pnpm, "run", name]) for name in SCRIPTS]
    commands.append(
        run(
            "policy-typecheck",
            [pnpm, "--dir", "packages/policy", "run", "typecheck"],
        )
    )
    assertions = sum(
        int(item["result"].get("assertions", 0))
        for item in commands
        if isinstance(item["result"], dict)
    )
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    implementation_sources = {
        path: digest(ROOT / path) for path in IMPLEMENTATION_PATHS
    }
    implementation_bundle_digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                implementation_sources,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    implementation_paths_match_source_commit = (
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *IMPLEMENTATION_PATHS],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
        and subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--quiet",
                "HEAD",
                "--",
                *IMPLEMENTATION_PATHS,
            ],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )
    passed = all(item["status"] == "PASS" for item in commands)
    passed = passed and implementation_paths_match_source_commit
    formal_receipt_path = AUDIT / "formal-verification-receipt.json"
    formal = (
        json.loads(formal_receipt_path.read_text(encoding="utf-8"))
        if formal_receipt_path.exists()
        else {}
    )
    receipt = {
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "claim_label": "IMPLEMENTED NOT DEPLOYED",
        "status": "PASS" if passed else "FAILED",
        "assertions": assertions,
        "implementation_source_commit": source_commit,
        "implementation_paths_match_source_commit": (
            implementation_paths_match_source_commit
        ),
        "implementation_bundle_digest": implementation_bundle_digest,
        "implementation_sources": implementation_sources,
        "runtime_binding": {
            "mechanism": "TypeScript implementation with finite-domain differential checks",
            "formal_artifact_digest": formal.get("formal_artifact_digest"),
            "label": "MODELED",
            "reason": (
                "The TypeScript-to-Lean refinement has not been independently reviewed "
                "or exhaustively established over an encoded finite domain."
            ),
        },
        "schemas": {
            name: digest(ROOT / "schemas" / name)
            for name in (
                "action-request.schema.json",
                "authorization-receipt.schema.json",
                "deployment-identity.schema.json",
            )
        },
        "commands": commands,
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
