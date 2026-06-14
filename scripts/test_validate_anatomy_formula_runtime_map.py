#!/usr/bin/env python3
"""Negative-fixture self-test for validate_anatomy_formula_runtime_map.py.

The anatomy/formula/runtime map validator enforces the autonomous-learning
doctrine: the canonical hub is a11oy, promotion REQUIRES a human
(promotionModel=human_promotion_required), and the agent's forbiddenModes must
include self_approve / self_promote / deploy / publish. It also rejects
unsupported claimStatus values. Nothing proved those guard rules keep working —
a future edit could silently let the doctrine flip to self-promotion with nobody
noticing.

This test feeds the REAL validator tampered maps and asserts it FAILS on each
(exit 1), plus an honest fixture (the committed map) that PASSES (exit 0) so the
guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_anatomy_formula_runtime_map.py
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
_VALIDATOR = os.path.join(_HERE, "validate_anatomy_formula_runtime_map.py")

_spec = importlib.util.spec_from_file_location("validate_anatomy_formula_runtime_map", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MAP_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    """Redirect MAP_PATH at a temp copy; THEOREM_MANIFEST_PATH stays real so the
    theoremRuntimeManifestId cross-check resolves against the committed manifest."""
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


class AnatomyMapGuardSelfTest(unittest.TestCase):
    def test_honest_map_passes(self):
        """Sanity floor: the committed map must PASS so the guard is not merely
        always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_promotion_model_not_human_fails(self):
        """The core anti-self-promotion rule: promotion must require a human."""
        m = honest()
        m["autonomousLearningDoctrine"]["promotionModel"] = "autonomous"
        self.assertEqual(run_validator(m), 1)

    def test_missing_forbidden_mode_fails(self):
        for mode in ("self_approve", "self_promote", "deploy", "publish"):
            with self.subTest(mode=mode):
                m = honest()
                m["autonomousLearningDoctrine"]["forbiddenModes"] = [
                    x for x in m["autonomousLearningDoctrine"]["forbiddenModes"] if x != mode
                ]
                self.assertEqual(run_validator(m), 1)

    def test_canonical_hub_changed_fails(self):
        m = honest()
        m["canonicalHub"] = "huggingface"
        self.assertEqual(run_validator(m), 1)

    def test_bad_organ_claim_status_fails(self):
        m = honest()
        m["organs"][0]["claimStatus"] = "totally-proven"
        self.assertEqual(run_validator(m), 1)

    def test_missing_required_repo_fails(self):
        m = honest()
        # Drop the canonical a11oy organ -> required-repo check must fire.
        m["organs"] = [o for o in m["organs"] if o.get("repo") != "a11oy"]
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
