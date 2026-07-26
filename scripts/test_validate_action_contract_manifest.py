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
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
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


def write_runtime_evidence(contract_path: Path, destination: Path) -> None:
    suite = ET.Element("testsuite", name="action-contract-runtime")
    properties = ET.SubElement(suite, "properties")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    values = {
        "evidence_schema": validator.RUNTIME_EVIDENCE_SCHEMA,
        "contract_id": contract["contractId"],
        "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "source_commit": validator.current_source_commit(),
    }
    for name, value in values.items():
        ET.SubElement(properties, "property", name=name, value=value)
    for name in sorted(validator.REQUIRED_RUNTIME_TESTS):
        ET.SubElement(suite, "testcase", name=name)
    ET.ElementTree(suite).write(destination, encoding="utf-8", xml_declaration=True)


def run_validator(
    manifest: dict,
    *,
    runtime_evidence: bool = False,
    mutate_evidence=None,
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
        evidence_path = None
        try:
            if runtime_evidence:
                evidence_fd, evidence_name = tempfile.mkstemp(suffix=".xml")
                os.close(evidence_fd)
                evidence_path = Path(evidence_name)
                write_runtime_evidence(validator.CONTRACT_PATH, evidence_path)
                if mutate_evidence is not None:
                    mutate_evidence(evidence_path)
            with redirect_stdout(io.StringIO()):
                return validator.main(evidence_path)
        finally:
            validator.CONTRACT_PATH = orig
            if evidence_path is not None:
                evidence_path.unlink(missing_ok=True)
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

    def test_verified_runtime_accepts_external_commit_bound_all_green_evidence(self):
        m = honest()
        promote_to_verified_runtime(m)
        self.assertEqual(run_validator(m, runtime_evidence=True), 0)

    def test_verified_runtime_rejects_incomplete_external_evidence(self):
        def remove_authentication_case(path: Path) -> None:
            tree = ET.parse(path)
            root = tree.getroot()
            for node in root.findall(".//testcase"):
                if node.get("name") == "test_authenticated_operator_execution":
                    root.remove(node)
            tree.write(path, encoding="utf-8", xml_declaration=True)

        m = honest()
        promote_to_verified_runtime(m)
        self.assertEqual(
            run_validator(
                m,
                runtime_evidence=True,
                mutate_evidence=remove_authentication_case,
            ),
            1,
        )

    def test_verified_runtime_rejects_evidence_bound_to_another_commit(self):
        def replace_source_commit(path: Path) -> None:
            tree = ET.parse(path)
            root = tree.getroot()
            for node in root.findall(".//property"):
                if node.get("name") == "source_commit":
                    node.set("value", "0" * 40)
            tree.write(path, encoding="utf-8", xml_declaration=True)

        m = honest()
        promote_to_verified_runtime(m)
        self.assertEqual(
            run_validator(
                m,
                runtime_evidence=True,
                mutate_evidence=replace_source_commit,
            ),
            1,
        )

    def test_verified_runtime_rejects_report_committed_inside_repository(self):
        m = honest()
        promote_to_verified_runtime(m)
        report = validator.REPO_ROOT / ".action-runtime-evidence-test.xml"
        try:
            write_runtime_evidence(validator.CONTRACT_PATH, report)
            self.assertEqual(validator.validate_runtime_evidence(report, m), [
                "verified-runtime evidence must be generated outside the repository; "
                "a committed same-change report is not independent"
            ])
        finally:
            report.unlink(missing_ok=True)

    def test_nonexistent_evidence_command_fails(self):
        m = honest()
        m["evidence"]["testCommands"] = [
            "python3 scripts/does_not_exist.py",
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
