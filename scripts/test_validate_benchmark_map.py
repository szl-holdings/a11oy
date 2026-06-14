#!/usr/bin/env python3
"""Negative-fixture self-test for validate_benchmark_map.py.

The benchmark-map validator is a doctrine-safe overclaim guard: competition-math
entries must score raw_points, must disallow "solved/beat the benchmark" and
"AGI proven" claims, must NOT phrase the allowed claim as "solved/cracked",
must require hash-chained receipts, and may only mirror (publishMode=
mirror-not-canonical). Nothing proved those rules keep working — a future edit
could silently let a benchmark be advertised as "solved" with nobody noticing.

This test feeds the REAL validator tampered maps and asserts it FAILS on each
(exit 1), plus an honest fixture (the committed map) that PASSES (exit 0) so the
guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_benchmark_map.py
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
_VALIDATOR = os.path.join(_HERE, "validate_benchmark_map.py")

_spec = importlib.util.spec_from_file_location("validate_benchmark_map", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.BENCHMARK_MAP).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def mathcomp_index() -> int:
    """The index of a competition-math ("mathcomp") entry, whose honesty rules
    are the strictest part of the guard."""
    for i, e in enumerate(_REAL.get("entries", [])):
        if "mathcomp" in str(e.get("id", "")).lower():
            return i
    raise unittest.SkipTest("no mathcomp benchmark entry in committed map")


def run_validator(manifest: dict) -> int:
    """Redirect BENCHMARK_MAP at a temp copy; THEOREM_MANIFEST stays real so the
    formula-route theoremRuntimeManifestId cross-check resolves."""
    fd, path = tempfile.mkstemp(suffix=".json", dir=str(validator.REPO_ROOT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        orig = validator.BENCHMARK_MAP
        validator.BENCHMARK_MAP = Path(path)
        try:
            with redirect_stdout(io.StringIO()):
                return validator.main()
        finally:
            validator.BENCHMARK_MAP = orig
    finally:
        os.unlink(path)


class BenchmarkMapGuardSelfTest(unittest.TestCase):
    def test_honest_map_passes(self):
        """Sanity floor: the committed map must PASS so the guard is not merely
        always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_publish_mode_canonical_fails(self):
        m = honest()
        m["publication"]["publishMode"] = "canonical"
        self.assertEqual(run_validator(m), 1)

    def test_mathcomp_not_raw_points_fails(self):
        i = mathcomp_index()
        m = honest()
        m["entries"][i]["scoring"]["scoreType"] = "normalized"
        self.assertEqual(run_validator(m), 1)

    def test_mathcomp_disallowed_claim_dropped_fails(self):
        i = mathcomp_index()
        for phrase in ("solved the benchmark", "beat the benchmark", "AGI proven"):
            with self.subTest(phrase=phrase):
                m = honest()
                m["entries"][i]["honesty"]["disallowedClaims"] = [
                    c for c in m["entries"][i]["honesty"]["disallowedClaims"] if c != phrase
                ]
                self.assertEqual(run_validator(m), 1)

    def test_mathcomp_overclaiming_allowed_claim_fails(self):
        i = mathcomp_index()
        for word in ("solved", "cracked"):
            with self.subTest(word=word):
                m = honest()
                m["entries"][i]["honesty"]["allowedClaim"] = f"We {word} the benchmark"
                self.assertEqual(run_validator(m), 1)

    def test_receipts_not_required_fails(self):
        m = honest()
        m["entries"][0]["receipts"]["required"] = False
        self.assertEqual(run_validator(m), 1)

    def test_receipts_chain_not_hash_chain_fails(self):
        m = honest()
        m["entries"][0]["receipts"]["chain"] = "none"
        self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
