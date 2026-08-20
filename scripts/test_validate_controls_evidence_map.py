#!/usr/bin/env python3
"""Negative-fixture self-test for validate_controls_evidence_map.py.

The controls-evidence-map validator enforces the clean-room and honest-exposure
contract for A11oy controls: no copied external control catalog, controlIds match
A11OY-CE-###, claimStatus is from the allowed set, a verified-runtime control
must carry a runtime-available receipt hook, and HF/UDS exposure may NOT be
advertised as canonical / source-of-truth / catalog-accepted / endorsed. Nothing
proved those rules keep working — a future edit could silently let a control
claim endorsement with nobody noticing.

This test feeds the REAL validator tampered maps and asserts it FAILS on each
(exit 1), plus an honest fixture (the committed map) that PASSES (exit 0) so the
guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_controls_evidence_map.py
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
_VALIDATOR = os.path.join(_HERE, "validate_controls_evidence_map.py")

_spec = importlib.util.spec_from_file_location("validate_controls_evidence_map", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MAP_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.MAP_PATH
        validator.MAP_PATH = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.MAP_PATH = orig
    finally:
        os.unlink(path)


class ControlsEvidenceGuardSelfTest(unittest.TestCase):
    def test_honest_map_passes(self):
        """Sanity floor: the committed map must PASS so the guard is not merely
        always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_clean_room_rule_dropped_fails(self):
        m = honest()
        m["cleanRoomRule"] = "we reuse whatever catalog we like"
        self.assertEqual(run_validator(m), 1)

    def test_hf_exposure_canonical_fails(self):
        for bad in ("canonical", "source-of-truth"):
            with self.subTest(hfExposure=bad):
                m = honest()
                m["controls"][0]["hfExposure"] = bad
                self.assertEqual(run_validator(m), 1)

    def test_uds_exposure_endorsed_fails(self):
        for bad in ("catalog-grade", "catalog-accepted", "endorsed"):
            with self.subTest(udsExposure=bad):
                m = honest()
                m["controls"][0]["udsExposure"] = bad
                self.assertEqual(run_validator(m), 1)

    def test_bad_control_id_format_fails(self):
        m = honest()
        m["controls"][0]["controlId"] = "CONTROL-1"
        self.assertEqual(run_validator(m), 1)

    def test_bad_claim_status_fails(self):
        m = honest()
        m["controls"][0]["claimStatus"] = "totally-verified"
        self.assertEqual(run_validator(m), 1)

    def test_verified_runtime_without_runtime_receipt_fails(self):
        """A verified-runtime control that downgrades its receipt hook to roadmap
        is overclaiming and must be rejected."""
        m = honest()
        idx = next(
            (i for i, c in enumerate(m["controls"]) if c.get("claimStatus") == "verified-runtime"),
            None,
        )
        if idx is None:
            self.skipTest("no verified-runtime control in committed map")
        m["controls"][idx]["receiptHook"]["status"] = "roadmap"
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
