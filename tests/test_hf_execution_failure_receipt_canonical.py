#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline negative controls for canonical A11oy handoff failure receipts."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("a11oy_failure_receipt", ROOT / ".github/scripts/admit_execution_handoff.py")
HANDOFF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HANDOFF)

class FailureReceiptCanonicalTests(unittest.TestCase):
    def setUp(self):
        self.report = HANDOFF.failure_report("a" * 40, "HF_IDENTITY_MISMATCH", "RUNTIME_READBACK")
        self.canonical = HANDOFF.canonical_failure(self.report)

    def parse(self, raw):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "failure.json"
            path.write_bytes(raw)
            return HANDOFF.read_failure(path)

    def assert_blocked(self, raw):
        with self.assertRaisesRegex(HANDOFF.HandoffBlocked, "FAILURE_REPORT_INVALID"):
            self.parse(raw)

    def test_owned_canonical_receipts_still_read(self):
        self.assertEqual(self.parse(self.canonical), self.report)
        context = HANDOFF.failure_report(
            "a" * 40, "EXECUTION_CONTEXT_REQUIRED", "CONTEXT_CONFIGURATION",
            missing_variables=("A11OY_EXECUTION_BOOT_ID",))
        self.assertEqual(self.parse(HANDOFF.canonical_failure(context)), context)

    def test_duplicate_member_cannot_hide_contradictory_authority(self):
        tampered = self.canonical.replace(
            b'"execution_authorized":false',
            b'"execution_authorized":true,"execution_authorized":false')
        self.assertNotEqual(tampered, self.canonical)
        self.assert_blocked(tampered)

    def test_nonfinite_extra_field_is_rejected(self):
        self.assert_blocked(self.canonical.replace(b"}\n", b',"unexpected":NaN}\n'))

    def test_unknown_canonical_field_is_rejected(self):
        self.assert_blocked(self.canonical.replace(b"}\n", b',"unexpected":"text"}\n'))

    def test_noncanonical_bytes_are_rejected(self):
        self.assert_blocked(b" " + self.canonical)

    def test_unpinned_source_revision_is_rejected(self):
        self.assert_blocked(self.canonical.replace(b"a" * 40, b"main"))

if __name__ == "__main__":
    unittest.main()
