#!/usr/bin/env python3
"""Negative-fixture self-test for validate_hf_test_results_manifest.py.

The HF test-results validator keeps the staged Hugging Face dataset honest until
real sealed results exist: claim_status must stay staged-no-live-score, the
corpus must be unsealed with problem_count 0 and no problem text, runs must be
empty, the results/receipts dirs must stay empty, GitHub remains canonical
(publish_mode=mirror-not-canonical), and the public wording must forbid
"solved/beat the benchmark"/"AGI proven" while never itself using
"cracked/solved/leaderboard". Nothing proved those rules keep working — a future
edit could silently flip the staged manifest to "live" with nobody noticing.

This test feeds the REAL validator tampered manifests and asserts it FAILS on
each (exit 1), plus an honest fixture (the committed manifest) that PASSES
(exit 0) so the guard is real, not merely always-failing.

Pure stdlib (unittest), network-free, touches no live manifest. Run by file path
(the scripts dir is not an importable package):
    python3 scripts/test_validate_hf_test_results_manifest.py
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
_VALIDATOR = os.path.join(_HERE, "validate_hf_test_results_manifest.py")

_spec = importlib.util.spec_from_file_location("validate_hf_test_results_manifest", _VALIDATOR)
validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator)

_REAL = json.loads(Path(validator.MANIFEST_PATH).read_text(encoding="utf-8"))


def honest() -> dict:
    return copy.deepcopy(_REAL)


def run_validator(manifest: dict) -> int:
    """Redirect MANIFEST_PATH at a temp copy; BENCHMARK_MAP and the
    results/receipts dir checks stay pointed at the real repo."""
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


class HfTestResultsGuardSelfTest(unittest.TestCase):
    def test_honest_manifest_passes(self):
        """Sanity floor: the committed manifest must PASS so the guard is not
        merely always-failing."""
        self.assertEqual(run_validator(honest()), 0)

    def test_claim_status_promoted_fails(self):
        """The core anti-overclaim rule: the staged manifest cannot self-promote
        to a live score."""
        m = honest()
        m["claim_status"] = "live-verified"
        self.assertEqual(run_validator(m), 1)

    def test_corpus_sealed_fails(self):
        m = honest()
        m["corpus"]["sealed"] = True
        self.assertEqual(run_validator(m), 1)

    def test_corpus_problem_count_nonzero_fails(self):
        m = honest()
        m["corpus"]["problem_count"] = 42
        self.assertEqual(run_validator(m), 1)

    def test_nonempty_runs_fails(self):
        m = honest()
        m["runs"] = [{"runId": "fake", "score": 99}]
        self.assertEqual(run_validator(m), 1)

    def test_publish_mode_canonical_fails(self):
        m = honest()
        m["publication"]["publish_mode"] = "canonical"
        self.assertEqual(run_validator(m), 1)

    def test_disallowed_claim_dropped_fails(self):
        for phrase in ("solved the benchmark", "beat the benchmark", "agi proven", "hf is canonical"):
            with self.subTest(phrase=phrase):
                m = honest()
                m["disallowed_claims"] = [
                    c for c in m["disallowed_claims"] if c.lower() != phrase
                ]
                self.assertEqual(run_validator(m), 1)

    def test_overclaiming_allowed_wording_fails(self):
        for word in ("cracked", "solved", "leaderboard"):
            with self.subTest(word=word):
                m = honest()
                m["allowed_public_wording"] = list(m.get("allowed_public_wording", [])) + [
                    f"we {word} it"
                ]
                self.assertEqual(run_validator(m), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
