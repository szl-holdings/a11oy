#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Portable required checks. Missing OPA is a failing check, not a pass."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--opa", default="opa")
    parser.add_argument("--cedar", default="cedar")
    args = parser.parse_args()
    opa = shutil.which(args.opa)
    if not opa:
        parser.error(
            "OPA is required; install the checksum-pinned tool with tools/install_opa.py"
        )
    cedar = shutil.which(args.cedar)
    if not cedar:
        parser.error("Cedar CLI is required; install it with tools/install_cedar.py")
    opa, cedar = str(Path(opa).resolve()), str(Path(cedar).resolve())
    environment = dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1", ANATOMY_OPA=opa, CEDAR_BIN=cedar
    )
    commands = [
        [opa, "fmt", "--fail", "policy/rego"],
        [opa, "test", "policy/rego", "-v", "--timeout", "30s"],
        [sys.executable, "-B", "tools/check_cedar.py", "--cedar", cedar],
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
    ]
    for command in commands:
        subprocess.run(command, cwd=BASE, env=environment, check=True, timeout=180)
    for path in (BASE / "policy/cedar").rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    json.loads((BASE / "toolchain-lock.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="anatomy-verify-") as temp:
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(BASE / "tools/build_ledger.py"),
                "--root",
                temp,
                "--output",
                "ledger.json",
                "--opa",
                opa,
            ],
            check=True,
            env=environment,
            timeout=60,
        )
        ledger = json.loads((Path(temp) / "ledger.json").read_text(encoding="utf-8"))
        if ledger["recordCount"] != 0:
            raise SystemExit("empty evidence must remain empty")
    print("PASS: OPA, Cedar engine, Python/HTTP tests, JSON, and honest empty ledger")
    print(
        "Local verification does not establish production deployment or execution authority."
    )


if __name__ == "__main__":
    main()
