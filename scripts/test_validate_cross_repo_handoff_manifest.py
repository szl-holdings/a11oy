#!/usr/bin/env python3
"""Negative-fixture self-test for validate_cross_repo_handoff_manifest.py.

The cross-repo handoff validator enforces the "not complete until target repo
evidence exists" doctrine: it forbids completion claims like "production-ready"
/ "endorsed", binds every handoff's patchSha256 to the actual patch bytes,
restricts accessState / handoffState / claimStatus to allowed sets, and requires
a complete handoff to cite a target PR + target CI green. Nothing proved those
rules keep working — a future edit could silently let a handoff be marked
complete (or its patch swapped) with nobody noticing.

This test feeds the REAL validator tampered manifests and asserts it FAILS on
each (exit 1), plus an honest fixture that PASSES (exit 0) so the guard is real,
not merely always-failing.

Note: the committed manifest may reference a patch file that is not present in a
given checkout (an unrelated, separately-tracked drift). To keep the sanity
floor robust, the honest fixture is the committed manifest reduced to only the
handoffs whose patch file exists in this checkout — the validator's own
path-existence rule defines that set.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_cross_repo_handoff_manifest.py
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
_VALIDATOR = os.path.join(_HERE, "validate_cross_repo_handoff_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_cross_repo_handoff_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MANIFEST).read_text(encoding="utf-8"))


def honest() -> dict:
    """Committed manifest reduced to handoffs whose patch file exists here, so the
    sanity floor doesn't depend on separately-tracked patch files."""
    data = copy.deepcopy(_REAL)
    data["handoffs"] = [
        h for h in data.get("handoffs", [])
        if (validator.REPO_ROOT / str(h.get("patchPath", ""))).exists()
    ]
    return data


def run_validator(manifest: dict) -> int:
    """Redirect MANIFEST at a temp copy; the access checklist stays real so the
    targetRepo membership cross-check resolves."""
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


class CrossRepoHandoffGuardSelfTest(unittest.TestCase):
    def setUp(self):
        if not honest().get("handoffs"):
            self.skipTest("no handoff with an existing patch file in this checkout")

    def test_honest_manifest_passes(self):
        """Sanity floor: an honest manifest must PASS so the guard is not merely
        always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_forbidden_completion_claim_dropped_fails(self):
        for phrase in ("production-ready", "endorsed", "all green"):
            with self.subTest(phrase=phrase):
                m = honest()
                m["forbiddenClaims"] = [c for c in m["forbiddenClaims"] if c.lower() != phrase]
                self.assertEqual(run_validator(m), 1)

    def test_canonical_rule_weakened_fails(self):
        m = honest()
        m["canonicalRule"] = "handoffs are done when we say so"
        self.assertEqual(run_validator(m), 1)

    def test_patch_sha_mismatch_fails(self):
        """The anti-swap rule: patchSha256 must match the real patch bytes."""
        m = honest()
        m["handoffs"][0]["patchSha256"] = "0" * 64
        self.assertEqual(run_validator(m), 1)

    def test_bad_access_state_fails(self):
        m = honest()
        m["handoffs"][0]["accessState"] = "fully-open"
        self.assertEqual(run_validator(m), 1)

    def test_complete_without_target_evidence_fails(self):
        """A handoff cannot be 'complete' without citing target PR + target CI."""
        m = honest()
        m["handoffs"][0]["handoffState"] = "complete"
        m["handoffs"][0]["completionRequires"] = ["local validation only"]
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
