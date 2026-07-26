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
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.join(_HERE, "validate_action_contract_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_action_contract_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.CONTRACT_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    """A copy of the real, committed contract — the sanity-floor fixture."""
    return copy.deepcopy(_REAL)


def promote_to_verified_runtime(manifest: dict) -> None:
    manifest["claimStatus"] = "verified-runtime"
    manifest["execution"].update(
        {
            "runtimeStatus": "live",
            "runtimeImplemented": True,
            "authenticatedExecution": True,
            "idempotencyEnforced": True,
            "durableReceiptLifecycle": True,
        }
    )


def mark_as_release_payload(manifest: dict) -> None:
    manifest["claimStatus"] = "release-payload"


def run_validator(
    manifest: dict, *, runtime_root: Path | None = None
) -> int:
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
                return validator.main(
                    runtime_root=runtime_root or validator.REPO_ROOT
                )
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

    def test_same_manifest_runtime_flags_cannot_promote_without_independent_evidence(self):
        m = honest()
        promote_to_verified_runtime(m)
        self.assertEqual(run_validator(m), 1)

    def test_release_payload_without_runtime_claims_remains_valid(self):
        m = honest()
        mark_as_release_payload(m)
        self.assertEqual(run_validator(m), 0)

    def test_release_payload_cannot_claim_live_runtime(self):
        m = honest()
        mark_as_release_payload(m)
        m["execution"]["runtimeStatus"] = "live"
        self.assertEqual(run_validator(m), 1)

    def test_release_payload_cannot_set_implementation_flags(self):
        for field in validator.RUNTIME_CLAIM_FIELDS:
            with self.subTest(field=field):
                m = honest()
                mark_as_release_payload(m)
                m["execution"][field] = True
                self.assertEqual(run_validator(m), 1)

    def test_release_payload_cannot_bypass_with_all_live_claims(self):
        m = honest()
        promote_to_verified_runtime(m)
        mark_as_release_payload(m)
        with mock.patch.object(
            validator,
            "validate_pinned_runtime_suite",
        ) as qualification:
            self.assertEqual(run_validator(m), 1)
        qualification.assert_not_called()

    def test_forged_external_junit_cannot_promote(self):
        m = honest()
        promote_to_verified_runtime(m)
        with tempfile.NamedTemporaryFile(suffix=".xml") as forged:
            forged.write(
                b"<testsuite><testcase "
                b"name='test_authenticated_operator_execution'/></testsuite>"
            )
            forged.flush()
            self.assertTrue(Path(forged.name).is_file())
            self.assertNotIn(
                "runtime_evidence_junit",
                inspect.signature(validator.main).parameters,
            )
            self.assertEqual(run_validator(m), 1)

    def test_verified_runtime_runs_protected_suite_against_candidate_root(self):
        m = honest()
        promote_to_verified_runtime(m)
        suite_bytes = validator.PINNED_RUNTIME_SUITE_PATH.read_bytes()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="qualification passed\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            candidate_root = Path(directory).resolve()
            with (
                mock.patch.object(
                    validator,
                    "protected_runtime_suite_bytes",
                    return_value=suite_bytes,
                ),
                mock.patch.object(
                    validator.subprocess,
                    "run",
                    return_value=completed,
                ) as run,
                mock.patch.dict(
                    validator.os.environ,
                    {"GITHUB_TOKEN": "must-not-propagate"},
                ),
            ):
                self.assertEqual(
                    run_validator(m, runtime_root=candidate_root),
                    0,
                )
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            [
                sys.executable,
                "-I",
                str(validator.PINNED_RUNTIME_SUITE_PATH),
                "--runtime-root",
                str(candidate_root),
            ],
        )
        self.assertEqual(kwargs["cwd"], candidate_root)
        self.assertEqual(
            kwargs["env"]["ACTION_CONTRACT_RUNTIME_ROOT"],
            str(candidate_root),
        )
        self.assertNotIn("GITHUB_TOKEN", kwargs["env"])
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
        self.assertFalse(kwargs["check"])
        self.assertEqual(
            kwargs["timeout"],
            validator.RUNTIME_SUITE_TIMEOUT_SECONDS,
        )
        self.assertTrue(kwargs["text"])

    def test_verified_runtime_rejects_suite_not_on_protected_base(self):
        m = honest()
        promote_to_verified_runtime(m)
        with (
            mock.patch.object(
                validator,
                "protected_runtime_suite_bytes",
                return_value=b"author-supplied replacement",
            ),
            mock.patch.object(validator.subprocess, "run") as run,
        ):
            self.assertEqual(run_validator(m), 1)
        run.assert_not_called()

    def test_verified_runtime_rejects_modified_suite_digest(self):
        m = honest()
        promote_to_verified_runtime(m)
        with (
            mock.patch.object(
                validator,
                "PINNED_RUNTIME_SUITE_SHA256",
                "0" * 64,
            ),
            mock.patch.object(
                validator,
                "protected_runtime_suite_bytes",
            ) as protected,
        ):
            self.assertEqual(run_validator(m), 1)
        protected.assert_not_called()

    def test_verified_runtime_rejects_failing_pinned_suite(self):
        m = honest()
        promote_to_verified_runtime(m)
        suite_bytes = validator.PINNED_RUNTIME_SUITE_PATH.read_bytes()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="BLOCKED: runtime remains ROADMAP\n",
        )
        with (
            mock.patch.object(
                validator,
                "protected_runtime_suite_bytes",
                return_value=suite_bytes,
            ),
            mock.patch.object(
                validator.subprocess,
                "run",
                return_value=completed,
            ),
        ):
            self.assertEqual(run_validator(m), 1)

    def test_nonexistent_evidence_command_fails(self):
        m = honest()
        m["evidence"]["testCommands"] = [
            "python3 scripts/does_not_exist.py",
        ]
        self.assertEqual(run_validator(m), 1)

    def test_unrelated_existing_python_script_cannot_replace_validators(self):
        m = honest()
        m["evidence"]["testCommands"] = [
            "python3 scripts/tamper_release_receipt.py",
        ]
        self.assertEqual(run_validator(m), 1)

    def test_shell_indirection_cannot_masquerade_as_evidence(self):
        m = honest()
        m["evidence"]["testCommands"] = [
            "npm run action-contract:audit",
        ]
        self.assertEqual(run_validator(m), 1)

    def test_runtime_boundary_cannot_be_dropped(self):
        m = honest()
        m["execution"]["evidenceBoundary"] = "manifest is runtime"
        self.assertEqual(run_validator(m), 1)

    def test_stale_doctrine_regime_fails(self):
        m = honest()
        m["intent"]["regime"] = "doctrine-v6"
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
