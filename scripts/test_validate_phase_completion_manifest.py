#!/usr/bin/env python3
"""Negative-fixture self-test for validate_phase_completion_manifest.py.

The phase-completion validator keeps cross-repo completion honest: sibling-repo
phases stay access-pending, a11oyLocalStatus is complete-for-current-branch,
crossRepoStatus is access-pending-handoff-queued, the forbiddenClaims must
include "zero sorry" / "solved the benchmark" / "uds catalog accepted" / "hf is
canonical", each phase status is from the allowed set with existing artifacts,
and sibling-repo completion requires target write access + target CI green.
Nothing proved those rules keep working — a future edit could silently flip
crossRepoStatus to complete with nobody noticing.

This test feeds the REAL validator tampered manifests and asserts it FAILS on
each (exit 1), plus an honest fixture (the committed manifest) that PASSES
(exit 0) so the guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_phase_completion_manifest.py
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
_VALIDATOR = os.path.join(_HERE, "validate_phase_completion_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_phase_completion_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MANIFEST).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    """Redirect MANIFEST at a temp copy; the PHASE_COMPLETION_REPORT.md existence
    check stays pointed at the real repo."""
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.MANIFEST
        validator.MANIFEST = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.MANIFEST = orig
    finally:
        os.unlink(path)


class PhaseCompletionGuardSelfTest(unittest.TestCase):
    def test_honest_manifest_passes(self):
        """Sanity floor: the committed manifest must PASS so the guard is not
        merely always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_cross_repo_status_completed_fails(self):
        """The core anti-overclaim rule: cross-repo work cannot self-mark
        complete while access is still pending."""
        m = honest()
        m["crossRepoStatus"] = "complete"
        self.assertEqual(run_validator(m), 1)

    def test_a11oy_local_status_changed_fails(self):
        m = honest()
        m["a11oyLocalStatus"] = "all-green-everywhere"
        self.assertEqual(run_validator(m), 1)

    def test_canonical_rule_weakened_fails(self):
        m = honest()
        m["canonicalRule"] = "everything is done"
        self.assertEqual(run_validator(m), 1)

    def test_forbidden_claim_dropped_fails(self):
        for phrase in ("zero sorry", "solved the benchmark", "uds catalog accepted", "hf is canonical"):
            with self.subTest(phrase=phrase):
                m = honest()
                m["forbiddenClaims"] = [c for c in m["forbiddenClaims"] if c.lower() != phrase]
                self.assertEqual(run_validator(m), 1)

    def test_bad_phase_status_fails(self):
        m = honest()
        m["phases"][0]["status"] = "totally-shipped"
        self.assertEqual(run_validator(m), 1)

    def test_sibling_completion_requirements_dropped_fails(self):
        for phrase in ("target repo write-ready access", "target ci green"):
            with self.subTest(phrase=phrase):
                m = honest()
                m["completionRequiresForSiblingRepos"] = [
                    c for c in m["completionRequiresForSiblingRepos"] if phrase not in c.lower()
                ]
                self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
