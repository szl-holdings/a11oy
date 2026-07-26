#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Run declared release commands and retain payload determinism and SPA-gap evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
LOGS = AUDIT / "release-command-logs"
RECEIPT = AUDIT / "release-command-verification.json"


def digest_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def tree_digest(root: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    total = 0
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        body = path.read_bytes()
        total += len(body)
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return {
        "digest": f"sha256:{digest.hexdigest()}",
        "files": len(files),
        "bytes": total,
    }


def run(name: str, args: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    LOGS.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name)
    stdout_path = LOGS / f"{safe}.stdout.txt"
    stderr_path = LOGS / f"{safe}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "command": [Path(args[0]).name, *args[1:]],
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAILED",
        "stdout": stdout_path.relative_to(ROOT).as_posix(),
        "stdout_sha256": digest_file(stdout_path),
        "stderr": stderr_path.relative_to(ROOT).as_posix(),
        "stderr_sha256": digest_file(stderr_path),
    }


def main() -> int:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        print("BLOCKED: `pnpm` must be available on PATH")
        return 2
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    with tempfile.TemporaryDirectory(prefix="a11oy-clean-release-") as temp_name:
        checkout = Path(temp_name) / "source"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(checkout), source_commit],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        try:
            tracked_clean_before = (
                subprocess.run(
                    ["git", "status", "--porcelain", "--untracked-files=no"],
                    cwd=checkout,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                ).stdout.strip()
                == ""
            )
            install = run(
                "clean-checkout-install",
                [pnpm, "install", "--frozen-lockfile"],
                checkout,
            )
            commands = [
                install,
                run("doctrine", [pnpm, "run", "test:doctrine"], checkout),
                run(
                    "doctrine-typecheck",
                    [pnpm, "run", "typecheck:doctrine"],
                    checkout,
                ),
                run(
                    "doctrine-build",
                    [pnpm, "run", "build:doctrine"],
                    checkout,
                ),
            ]
            payload_first = run(
                "payload-first",
                [pnpm, "run", "payload:huggingface"],
                checkout,
            )
            payload_path = checkout / "dist" / "huggingface" / "a11oy"
            first_digest = (
                tree_digest(payload_path)
                if payload_first["status"] == "PASS"
                else None
            )
            payload_second = run(
                "payload-second",
                [pnpm, "run", "payload:huggingface"],
                checkout,
            )
            second_digest = (
                tree_digest(payload_path)
                if payload_second["status"] == "PASS"
                else None
            )
            commands.extend((payload_first, payload_second))
            web_build = run(
                "web-build",
                [pnpm, "--dir", "web", "run", "build"],
                checkout,
            )
            commands.append(web_build)
            tracked_clean_after = (
                subprocess.run(
                    ["git", "status", "--porcelain", "--untracked-files=no"],
                    cwd=checkout,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                ).stdout.strip()
                == ""
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(checkout)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            registered = subprocess.check_output(
                ["git", "worktree", "list", "--porcelain"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
            )
            if str(checkout).replace("\\", "/").lower() in registered.replace(
                "\\", "/"
            ).lower():
                raise RuntimeError("temporary clean worktree remained registered")
    web_gap_path = AUDIT / "web-workspace-dependency-gap.json"
    web_gap = (
        json.loads(web_gap_path.read_text(encoding="utf-8"))
        if web_gap_path.exists()
        else None
    )
    payload_deterministic = (
        first_digest is not None
        and second_digest is not None
        and first_digest["digest"] == second_digest["digest"]
    )
    required_passed = all(
        item["status"] == "PASS" for item in commands if item["name"] != "web-build"
    ) and payload_deterministic and tracked_clean_before and tracked_clean_after
    complete = required_passed and web_build["status"] == "PASS"
    receipt = {
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "claim_label": "IMPLEMENTED NOT DEPLOYED",
        "source_commit": source_commit,
        "execution_context": "detached clean Git worktree at source_commit",
        "tracked_clean_before": tracked_clean_before,
        "tracked_clean_after": tracked_clean_after,
        "status": "PASS" if complete else "FAILED",
        "declared_delivery_path": "PASS" if required_passed else "FAILED",
        "broader_web_build": web_build["status"],
        "payload_determinism": {
            "status": "PASS" if payload_deterministic else "FAILED",
            "first": first_digest,
            "second": second_digest,
        },
        "web_workspace_gap": web_gap,
        "commands": commands,
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
