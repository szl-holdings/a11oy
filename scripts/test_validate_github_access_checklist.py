#!/usr/bin/env python3
"""Negative-fixture self-test for validate_github_access_checklist.py.

The GitHub access-checklist validator enforces least-privilege honesty: seats
alone do NOT grant write access, the only known-writable repo is szl-holdings/
a11oy, the read-only checks must be genuinely read-only gh commands (no pr
create / merge / api -X POST etc.), every target repo needs write as its minimum
permission, and the doctrine boundaries must forbid committing tokens / claiming
all-Lean-green / claiming Defense Unicorns endorsement. Nothing proved those
rules keep working — a future edit could silently slip a write command into the
"read-only" list with nobody noticing.

This test feeds the REAL validator tampered checklists and asserts it FAILS on
each (exit 1), plus an honest fixture (the committed checklist) that PASSES
(exit 0) so the guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_github_access_checklist.py
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.join(_HERE, "validate_github_access_checklist.py")

_spec = importlib.util.spec_from_file_location("validate_github_access_checklist", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.CHECKLIST).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.CHECKLIST
        validator.CHECKLIST = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.CHECKLIST = orig
    finally:
        os.unlink(path)


class GithubAccessGuardSelfTest(unittest.TestCase):
    def test_honest_checklist_passes(self):
        """Sanity floor: the committed checklist must PASS so the guard is not
        merely always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_seats_grant_write_fails(self):
        m = honest()
        m["seatsAloneGrantWriteAccess"] = True
        self.assertEqual(run_validator(m), 1)

    def test_write_command_in_readonly_checks_fails(self):
        """The core safety rule: a write-like gh command must never hide in the
        read-only checks list."""
        for cmd in (
            "gh pr create --title x",
            "gh pr merge 1",
            "gh api -X POST /repos/x",
            "gh issue create --title x",
        ):
            with self.subTest(command=cmd):
                m = honest()
                m["readOnlyChecks"] = list(m["readOnlyChecks"]) + [cmd]
                self.assertEqual(run_validator(m), 1)

    def test_non_gh_readonly_check_fails(self):
        m = honest()
        m["readOnlyChecks"] = list(m["readOnlyChecks"]) + ["curl https://example.com"]
        self.assertEqual(run_validator(m), 1)

    def test_target_repo_read_permission_fails(self):
        m = honest()
        m["targetRepos"][0]["minimumPermission"] = "read"
        self.assertEqual(run_validator(m), 1)

    def test_doctrine_boundary_dropped_fails(self):
        for phrase in (
            "do not commit tokens",
            "do not claim all lean green",
            "do not claim defense unicorns endorsement",
        ):
            with self.subTest(phrase=phrase):
                m = honest()
                m["doctrineBoundaries"] = [
                    b for b in m["doctrineBoundaries"] if phrase not in b.lower()
                ]
                self.assertEqual(run_validator(m), 1)

    def test_writable_repo_changed_fails(self):
        m = honest()
        m["currentKnownWritableRepo"] = "szl-holdings/everything"
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
