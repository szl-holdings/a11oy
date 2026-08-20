#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Negative-fixture self-test for check_no_hf_mirror.py.

Proves the guard FAILS (exit!=0) when a `.hf-mirror/` directory exists and
PASSES (exit 0) on a clean tree, so a future neutering of the checker is caught.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "check_no_hf_mirror.py")


def run(root: str) -> int:
    return subprocess.run(
        [sys.executable, CHECKER, root],
        capture_output=True,
        text=True,
    ).returncode


def main() -> int:
    failures = []

    # 1) clean tree -> PASS (exit 0)
    with tempfile.TemporaryDirectory() as clean:
        os.makedirs(os.path.join(clean, "organs", "amaru"))
        with open(os.path.join(clean, "organs", "amaru", "serve.py"), "w") as fh:
            fh.write("# canonical\n")
        rc = run(clean)
        if rc != 0:
            failures.append(f"clean tree expected exit 0, got {rc}")

    # 2) tree with a .hf-mirror snapshot -> FAIL (exit != 0)
    with tempfile.TemporaryDirectory() as dirty:
        mirror = os.path.join(dirty, "organs", "amaru", ".hf-mirror")
        os.makedirs(mirror)
        with open(os.path.join(mirror, "serve.py"), "w") as fh:
            fh.write("# stale snapshot\n")
        rc = run(dirty)
        if rc == 0:
            failures.append("tree with .hf-mirror expected nonzero exit, got 0")

    if failures:
        for f in failures:
            print("SELF-TEST FAIL:", f)
        return 1
    print("SELF-TEST OK: guard passes clean, fails on a committed .hf-mirror.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
