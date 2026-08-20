#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Guard: assert release-receipt-verify actually PUBLISHED a usable summary.

The public status board's release-receipt provenance row reads its counts from
the `release-receipt-verify-summary` artifact (`.release-verify-summary.json`)
produced by `release-receipt-verify.yml`. That summary is a dot-prefixed (hidden)
file, and `actions/upload-artifact@v4` excludes hidden files by default — so the
upload once silently produced an artifact with `total_count 0` on an otherwise
green run, starving the status row of counts. It was fixed with
`include-hidden-files: true`, but nothing guarded against that regressing.

This validator is the content half of that guard. Given the DOWNLOADED summary
artifact (a directory, or an explicit file), it FAILS unless the artifact is
non-empty and the summary JSON parses with the expected integer keys
``checked`` / ``passed`` / ``failed`` / ``unverifiable``.

It is deliberately INDEPENDENT of whether the release currently carries receipt
assets: the verifier writes a soft-pass summary (``checked == 0``) either way, so
a valid summary with zero checks is a PASS — the artifact must simply exist and
be well-formed every run.

Exit codes:
  0  the summary artifact is present, non-empty and well-formed
  1  the summary artifact is missing, empty or malformed (the regression)
  2  usage / environment error
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# The four counts the status-page release-receipt row depends on. Every summary
# release-receipt-verify writes — including a soft-pass (checked=0) — carries them.
REQUIRED_INT_KEYS = ("checked", "passed", "failed", "unverifiable")


def _find_summaries(directory: Path) -> list[Path]:
    """Return every *.json file under ``directory`` (dotfiles included).

    The real artifact holds one dot-prefixed `.release-verify-summary.json`, but
    we glob defensively so a future rename inside the artifact is still audited.
    """
    return sorted(
        p for p in directory.rglob("*") if p.is_file() and p.name.endswith(".json")
    )


def validate_summary_file(path: Path) -> list[str]:
    """Validate one summary JSON file. Returns a list of problems ([] == valid)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - an unreadable summary is a failure
        return [f"could not read {path}: {exc}"]
    if not raw.strip():
        return [f"{path.name} is empty"]
    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - non-parsing summary is a failure
        return [f"{path.name} is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.name} top-level JSON is not an object"]

    problems: list[str] = []
    for key in REQUIRED_INT_KEYS:
        if key not in data:
            problems.append(f"missing required key '{key}'")
        elif isinstance(data[key], bool) or not isinstance(data[key], int):
            problems.append(
                f"key '{key}' is not an integer (got {type(data[key]).__name__})"
            )
    if "results" in data and not isinstance(data["results"], list):
        problems.append("key 'results' is present but is not a list")
    return problems


def check_dir(directory: Path) -> int:
    """Audit a downloaded artifact directory. Returns a process exit code."""
    if not directory.exists():
        print(
            f"::error::artifact directory '{directory}' does not exist — the "
            "release-receipt-verify-summary artifact was not produced (total_count 0)."
        )
        return 1
    summaries = _find_summaries(directory)
    if not summaries:
        print(
            f"::error::no JSON summary found under '{directory}' — the "
            "release-receipt-verify-summary artifact is empty or lost its summary "
            "file (most likely the dot-prefixed summary was excluded by "
            "upload-artifact, or the path/name changed)."
        )
        return 1

    ok = True
    for path in summaries:
        problems = validate_summary_file(path)
        if problems:
            ok = False
            for problem in problems:
                print(f"::error::{path.name}: {problem}")
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            print(
                f"[summary-guard] OK: {path.name} "
                f"checked={data['checked']} passed={data['passed']} "
                f"failed={data['failed']} unverifiable={data['unverifiable']}"
            )
    return 0 if ok else 1


def _selftest() -> int:
    """Prove the validator passes good summaries and rejects broken ones."""
    failures: list[str] = []
    good_full = {
        "directory": "release-receipts",
        "repo": "szl-holdings/a11oy",
        "allowed_workflows": [],
        "checked": 3,
        "passed": 3,
        "failed": 0,
        "unverifiable": 0,
        "results": [{"file": "a.dsse.json", "status": "PASS"}],
    }
    good_soft = {"checked": 0, "passed": 0, "failed": 0, "unverifiable": 0, "results": []}

    def write(dirpath: Path, name: str, content: str) -> None:
        (dirpath / name).write_text(content, encoding="utf-8")

    cases: list[tuple[str, object, int]] = [
        ("good-full", lambda d: write(d, ".release-verify-summary.json", json.dumps(good_full)), 0),
        ("good-soft-pass(checked=0)", lambda d: write(d, ".release-verify-summary.json", json.dumps(good_soft)), 0),
        ("missing-artifact(empty-dir)", lambda d: None, 1),
        ("empty-file", lambda d: write(d, ".release-verify-summary.json", ""), 1),
        ("not-json", lambda d: write(d, ".release-verify-summary.json", "not json {"), 1),
        ("missing-key", lambda d: write(d, ".release-verify-summary.json", json.dumps({"checked": 1, "passed": 1, "failed": 0})), 1),
        ("wrong-type", lambda d: write(d, ".release-verify-summary.json", json.dumps({**good_soft, "failed": "0"})), 1),
        ("bool-not-int", lambda d: write(d, ".release-verify-summary.json", json.dumps({**good_soft, "failed": True})), 1),
    ]

    for name, setup, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dirpath = Path(tmp)
            setup(dirpath)  # type: ignore[operator]
            rc = check_dir(dirpath)
            if rc != expected:
                failures.append(f"{name}: expected rc={expected}, got rc={rc}")

    # A directory path that does not exist at all.
    rc = check_dir(Path(tempfile.gettempdir()) / "release-receipt-summary-does-not-exist-404")
    if rc != 1:
        failures.append(f"nonexistent-dir: expected rc=1, got rc={rc}")

    if failures:
        print("::error::self-test FAILED — the summary validator is not trustworthy:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        "[summary-guard] self-test passed: validator accepts well-formed summaries "
        "(including soft-pass checked=0) and rejects missing / empty / malformed artifacts."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", help="directory holding the downloaded summary artifact")
    ap.add_argument("--summary", help="explicit path to the summary JSON file")
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="run built-in positive/negative fixtures and exit (no real artifact needed)",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.summary:
        path = Path(args.summary)
        if not path.exists():
            print(f"::error::summary file '{path}' does not exist (artifact not produced).")
            return 1
        problems = validate_summary_file(path)
        if problems:
            for problem in problems:
                print(f"::error::{path.name}: {problem}")
            return 1
        print(f"[summary-guard] OK: {path.name} is non-empty and well-formed.")
        return 0
    if args.dir:
        return check_dir(Path(args.dir))
    ap.error("one of --dir, --summary or --selftest is required")
    return 2  # unreachable; argparse.error exits 2


if __name__ == "__main__":
    raise SystemExit(main())
