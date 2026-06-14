#!/usr/bin/env python3
"""Negative-fixture self-test for validate_public_pattern_manifest.py.

The public-pattern validator is the clean-room guardrail: private ingestion is
forbidden (privateIngestionAllowed=false), the copyingRule must state pattern-
only / no upstream code / no private material, the endorsementBoundary must
reject implied endorsement, source queues must use public http(s) URLs with
public/authorized audit scope, and every pattern must carry a license caveat and
describe original SZL/A11oy transformation. Nothing proved those rules keep
working — a future edit could silently allow private ingestion with nobody
noticing.

This test feeds the REAL validator tampered manifests and asserts it FAILS on
each (exit 1), plus an honest fixture (the committed manifest) that PASSES
(exit 0) so the guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_public_pattern_manifest.py
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
_VALIDATOR = os.path.join(_HERE, "validate_public_pattern_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_public_pattern_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MANIFEST_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.MANIFEST_PATH
        validator.MANIFEST_PATH = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.MANIFEST_PATH = orig
    finally:
        os.unlink(path)


class PublicPatternGuardSelfTest(unittest.TestCase):
    def test_honest_manifest_passes(self):
        """Sanity floor: the committed manifest must PASS so the guard is not
        merely always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_private_ingestion_allowed_fails(self):
        """The core clean-room rule: private ingestion must never be allowed."""
        m = honest()
        m["privateIngestionAllowed"] = True
        self.assertEqual(run_validator(m), 1)

    def test_copying_rule_weakened_fails(self):
        for required in ("pattern-only", "no upstream code", "private material"):
            with self.subTest(required=required):
                m = honest()
                m["copyingRule"] = m["copyingRule"].lower().replace(required, "")
                self.assertEqual(run_validator(m), 1)

    def test_endorsement_boundary_dropped_fails(self):
        m = honest()
        m["endorsementBoundary"] = "anything goes"
        self.assertEqual(run_validator(m), 1)

    def test_non_public_queue_url_fails(self):
        m = honest()
        m["sourceQueues"][0]["publicUrl"] = "file:///etc/secret"
        self.assertEqual(run_validator(m), 1)

    def test_bad_pattern_claim_status_fails(self):
        m = honest()
        m["patterns"][0]["claimStatus"] = "totally-verified"
        self.assertEqual(run_validator(m), 1)

    def test_pattern_missing_szl_transform_fails(self):
        m = honest()
        m["patterns"][0]["a11oyTransform"] = "a generic reimplementation"
        self.assertEqual(run_validator(m), 1)

    def test_pattern_license_caveat_dropped_fails(self):
        m = honest()
        m["patterns"][0]["licenseCaveat"] = "use freely"
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
