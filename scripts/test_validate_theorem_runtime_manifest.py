#!/usr/bin/env python3
"""Negative-fixture self-test for validate_theorem_runtime_manifest.py.

The theorem-runtime manifest validator accepts the honest "staged-advisory"
claimStatus (SZL Doctrine v11) and enforces an HONESTY GUARD: a staged-advisory
entry is NOT proven, so it must self-identify as advisory (stagedAdvisory: true),
carry a caveat, and must NOT claim a proven Lean status. Nothing proved that
guard keeps working — a future edit could silently loosen it and let a
not-yet-proven claim be promoted to "proven" with nobody noticing.

This test feeds the REAL validator tampered manifests and asserts it FAILS on
each (exit 1), and that a correct honest staged-advisory manifest PASSES (exit 0)
so the guard is real, not merely strict. Mirrors the box-script alarm CI guard
pattern: a negative-fixture self-test that gates the real guard.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_theorem_runtime_manifest.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.join(_HERE, "validate_theorem_runtime_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_theorem_runtime_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)


def run_validator(manifest: dict) -> int:
    """Write manifest to a temp file, run the real validator, return its exit code."""
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        argv = sys.argv
        sys.argv = ["validate_theorem_runtime_manifest.py", "--manifest", path]
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            sys.argv = argv
    finally:
        os.unlink(path)


def staged_entry(**overrides) -> dict:
    """A minimal, honest staged-advisory entry. Overrides tamper with it.

    No runtimeFile/exportFile/testFile so the validator's path-existence check is
    not exercised — these fixtures isolate the honesty guard.
    """
    entry = {
        "id": "STAGED-SELFTEST",
        "claimStatus": "staged-advisory",
        "stagedAdvisory": True,
        "caveat": "STAGED-ADVISORY. Lean proof pending; gate enforced:false.",
        "leanStatus": "conjectured",
    }
    entry.update(overrides)
    return entry


def manifest_with(entry: dict) -> dict:
    return {"schemaVersion": 2, "entries": [entry]}


class HonestyGuardSelfTest(unittest.TestCase):
    def test_honest_staged_advisory_passes(self):
        """Sanity floor: a correct honest entry must PASS, so the guard is not
        merely always-failing (which would be a useless guard)."""
        self.assertEqual(run_validator(manifest_with(staged_entry())), 0)

    def test_staged_advisory_false_fails(self):
        """A staged claim that hides it is staged must be rejected."""
        self.assertEqual(
            run_validator(manifest_with(staged_entry(stagedAdvisory=False))), 1
        )

    def test_staged_advisory_missing_flag_fails(self):
        entry = staged_entry()
        del entry["stagedAdvisory"]
        self.assertEqual(run_validator(manifest_with(entry)), 1)

    def test_missing_caveat_fails(self):
        entry = staged_entry()
        del entry["caveat"]
        self.assertEqual(run_validator(manifest_with(entry)), 1)

    def test_empty_caveat_fails(self):
        self.assertEqual(run_validator(manifest_with(staged_entry(caveat=""))), 1)

    def test_proven_lean_status_fails(self):
        """The core anti-overclaim rule: a not-yet-proven staged entry must never
        carry a proven Lean status."""
        for bad in ("proven", "verified", "lean-proven"):
            with self.subTest(leanStatus=bad):
                self.assertEqual(
                    run_validator(manifest_with(staged_entry(leanStatus=bad))), 1
                )

    def test_all_violations_at_once_fails(self):
        entry = staged_entry(stagedAdvisory=False, leanStatus="proven")
        del entry["caveat"]
        self.assertEqual(run_validator(manifest_with(entry)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
