#!/usr/bin/env python3
"""Negative-fixture self-test for validate_action_contract_manifest.py.

The action-contract validator enforces the A11oy clean-room and least-privilege
safety contract: copying is pattern-only, egress is default-deny with mandatory
denied capabilities (secret-export / private-repo-ingestion / self-approval),
receipts are hash-chained, and the UDS proof-point wording must forbid implied
endorsement. Nothing proved those guard rules keep working — a future edit could
silently loosen one (e.g. flip defaultDeny to false, or drop self-approval from
the deny list) with nobody noticing.

This test feeds the REAL validator tampered manifests and asserts it FAILS on
each (exit 1), plus an honest fixture (the committed manifest) that PASSES
(exit 0) so the guard is real, not merely always-failing. Mirrors the pattern in
test_validate_theorem_runtime_manifest.py.

Pure stdlib (unittest), network-free, touches no live manifest (each fixture is
written to a throwaway temp file inside the repo and the validator's path
constant is redirected at it). Run by file path (the scripts dir is not an
importable package):
    python3 scripts/test_validate_action_contract_manifest.py
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
_VALIDATOR = os.path.join(_HERE, "validate_action_contract_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_action_contract_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.CONTRACT_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    """A copy of the real, committed contract — the sanity-floor fixture."""
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    """Run the real validator against a tampered copy of the contract.

    The fixture is written to a temp file INSIDE the repo so the validator's
    success-path ``relative_to(REPO_ROOT)`` works; cross-referenced manifests
    (the public-pattern source) stay pointed at the real committed files.
    """
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.CONTRACT_PATH
        validator.CONTRACT_PATH = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.CONTRACT_PATH = orig
    finally:
        os.unlink(path)


class ActionContractGuardSelfTest(unittest.TestCase):
    def test_honest_contract_passes(self):
        """Sanity floor: the committed contract must PASS, so the guard is not
        merely always-failing (which would be a useless guard)."""
        self.assertEqual(run_validator(honest()), 0)

    def test_egress_default_deny_off_fails(self):
        m = honest()
        m["egressLimits"]["defaultDeny"] = False
        self.assertEqual(run_validator(m), 1)

    def test_missing_denied_capability_fails(self):
        for cap in ("secret-export", "private-repo-ingestion", "self-approval"):
            with self.subTest(capability=cap):
                m = honest()
                m["egressLimits"]["deniedCapabilities"] = [
                    c for c in m["egressLimits"]["deniedCapabilities"] if c != cap
                ]
                self.assertEqual(run_validator(m), 1)

    def test_copying_rule_not_pattern_only_fails(self):
        m = honest()
        m["cleanRoom"]["copyingRule"] = "copy-everything"
        self.assertEqual(run_validator(m), 1)

    def test_endorsement_boundary_dropped_fails(self):
        m = honest()
        m["cleanRoom"]["endorsementBoundary"] = "anything goes"
        self.assertEqual(run_validator(m), 1)

    def test_uds_forbidden_claims_emptied_fails(self):
        m = honest()
        m["udsProofPoint"]["forbiddenClaims"] = []
        self.assertEqual(run_validator(m), 1)

    def test_receipt_chain_not_hash_chain_fails(self):
        m = honest()
        m["receiptSinks"]["chainMode"] = "none"
        self.assertEqual(run_validator(m), 1)

    def test_receipt_retention_too_short_fails(self):
        m = honest()
        m["receiptSinks"]["retentionDays"] = 30
        self.assertEqual(run_validator(m), 1)

    def test_bad_claim_status_fails(self):
        m = honest()
        m["claimStatus"] = "production-ready"
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
