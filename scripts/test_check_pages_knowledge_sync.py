#!/usr/bin/env python3
"""Self-test for check_pages_knowledge_sync.py.

Proves the guard actually catches what it claims to: the SERVED pages/knowledge.json
OVERCLAIMING relative to the canonical knowledge.json (e.g. Conjecture 1 silently
marked "proven" in the console copy, the Conjecture-1 honesty ledger drifting out of
sync), AND the Doctrine-v11 honesty regressions in either copy (F23 promoted into the
locked set, the locked-count theorem dropped, a missing version, an un-qualified
Theorem U). Also proves a valid, consistent, honest pair passes. Stdlib unittest, no
network — guards the validator so a future edit can't silently neuter it.
"""
import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_pages_knowledge_sync import (  # noqa: E402
    main,
    validate_consistency,
    validate_honesty,
)


# Canonical (root) corpus: declares v11, keeps Λ-uniqueness (TH_L1) conjectured,
# lists F23 as a conjecture (not locked), pins a locked-count theorem.
ROOT = {
    "version": "6.0.0",
    "doctrine": "Doctrine v11 LOCKED",
    "theorems": [
        {"id": "TH_L1", "name": "Λ_uniqueness", "maturity": "conjectured"},
        {"id": "TH_L2", "name": "Λ_min_max_bounds", "maturity": "proven"},
        {"id": "TH_L5", "name": "khipu_quorum_safety", "maturity": "experimental"},
    ],
    "proof_summary": {
        "locked_proven": 8,
        "locked_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "locked_count_theorem": "locked_count_eight",
        "conjecture": ["F23"],
    },
}

# The console-served copy: a SUBSET of root's theorems (no TH_L5), its OWN version
# string, but it must NOT overclaim and must carry the same Conjecture-1 ledger.
PAGES = {
    "version": "1.0.0",
    "doctrine": "Doctrine v11 LOCKED",
    "theorems": [
        {"id": "TH_L1", "name": "Λ_uniqueness", "maturity": "conjectured"},
        {"id": "TH_L2", "name": "Λ_min_max_bounds", "maturity": "proven"},
    ],
    "proof_summary": {
        "locked_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
        "locked_count_theorem": "locked_count_eight",
        "conjecture": ["F23"],
    },
}


def _txt(obj):
    return json.dumps(obj, ensure_ascii=False)


def _write(d, name, obj_or_text):
    p = os.path.join(d, name)
    data = obj_or_text if isinstance(obj_or_text, str) else _txt(obj_or_text)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(data)
    return p


class HonestyTests(unittest.TestCase):
    def _errs(self, obj):
        text = _txt(obj)
        return validate_honesty(text, obj, "test")

    def test_good_corpora_have_no_errors(self):
        self.assertEqual(self._errs(ROOT), [])
        self.assertEqual(self._errs(PAGES), [])

    def test_lambda_uniqueness_marked_proven_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["theorems"][0]["maturity"] = "proven"
        errs = self._errs(bad)
        self.assertTrue(any("Λ-uniqueness" in e and "conjectured" in e for e in errs), errs)

    def test_f23_promoted_to_locked_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["proof_summary"]["locked_ids"].append("F23")
        errs = self._errs(bad)
        self.assertTrue(any("F23" in e and "locked_ids" in e for e in errs), errs)

    def test_f23_missing_from_conjecture_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["proof_summary"]["conjecture"] = []
        errs = self._errs(bad)
        self.assertTrue(any("conjecture must include 'F23'" in e for e in errs), errs)

    def test_missing_locked_count_theorem_fails(self):
        bad = copy.deepcopy(PAGES)
        del bad["proof_summary"]["locked_count_theorem"]
        errs = self._errs(bad)
        self.assertTrue(any("locked_count_theorem" in e for e in errs), errs)

    def test_missing_proof_summary_entirely_fails(self):
        # The real-world regression this guard exists for: the served copy drops the
        # honesty ledger entirely.
        bad = copy.deepcopy(PAGES)
        del bad["proof_summary"]
        errs = self._errs(bad)
        self.assertTrue(any("conjecture must include 'F23'" in e for e in errs), errs)
        self.assertTrue(any("locked_count_theorem" in e for e in errs), errs)

    def test_missing_version_fails(self):
        bad = copy.deepcopy(PAGES)
        del bad["version"]
        errs = self._errs(bad)
        self.assertTrue(any("version" in e for e in errs), errs)

    def test_missing_doctrine_v11_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["doctrine"] = "Doctrine vX"
        errs = self._errs(bad)
        self.assertTrue(any("v11" in e for e in errs), errs)

    def test_lambda_theorem_absent_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["theorems"] = [{"id": "TH_L2", "name": "other", "maturity": "proven"}]
        errs = self._errs(bad)
        self.assertTrue(any("TH_L1" in e for e in errs), errs)

    def test_theorem_u_without_conditional_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["note"] = "Theorem U holds and is fully proven."
        errs = self._errs(bad)
        self.assertTrue(any("Theorem U" in e for e in errs), errs)

    def test_theorem_u_with_conditional_ok(self):
        ok = copy.deepcopy(PAGES)
        ok["note"] = "Theorem U holds conditional on the declared axioms."
        self.assertEqual(self._errs(ok), [])

    def test_non_object_corpus_fails(self):
        errs = validate_honesty("[]", [], "test")
        self.assertTrue(any("not a valid JSON object" in e for e in errs), errs)


class ConsistencyTests(unittest.TestCase):
    def test_good_pair_is_consistent(self):
        self.assertEqual(validate_consistency(ROOT, PAGES), [])

    def test_pages_overclaims_theorem_maturity_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["theorems"][0]["maturity"] = "proven"  # TH_L1 conjectured in root
        errs = validate_consistency(ROOT, bad)
        self.assertTrue(any("TH_L1" in e and "disagrees" in e for e in errs), errs)

    def test_pages_subset_of_theorems_is_allowed(self):
        # pages legitimately omits TH_L5 — that is a lighter view, not an overclaim.
        self.assertEqual(validate_consistency(ROOT, PAGES), [])

    def test_pages_ledger_conjecture_drift_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["proof_summary"]["conjecture"] = ["F99"]
        errs = validate_consistency(ROOT, bad)
        self.assertTrue(any("conjecture" in e and "out of sync" in e for e in errs), errs)

    def test_pages_ledger_locked_count_drift_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["proof_summary"]["locked_count_theorem"] = "locked_count_nine"
        errs = validate_consistency(ROOT, bad)
        self.assertTrue(any("locked_count_theorem" in e for e in errs), errs)

    def test_pages_locked_ids_drift_fails(self):
        bad = copy.deepcopy(PAGES)
        bad["proof_summary"]["locked_ids"] = ["F1"]
        errs = validate_consistency(ROOT, bad)
        self.assertTrue(any("locked_ids" in e and "out of sync" in e for e in errs), errs)


class MainTests(unittest.TestCase):
    def test_consistent_and_honest_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r = _write(d, "knowledge.json", ROOT)
            p = _write(d, "pages.json", PAGES)
            rc = main(["--root", r, "--pages", p])
            self.assertEqual(rc, 0)

    def test_overclaim_in_pages_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = _write(d, "knowledge.json", ROOT)
            bad = copy.deepcopy(PAGES)
            bad["theorems"][0]["maturity"] = "proven"
            p = _write(d, "pages.json", bad)
            rc = main(["--root", r, "--pages", p])
            self.assertEqual(rc, 1)

    def test_dishonest_root_fails(self):
        with tempfile.TemporaryDirectory() as d:
            bad = copy.deepcopy(ROOT)
            bad["theorems"][0]["maturity"] = "proven"
            r = _write(d, "knowledge.json", bad)
            # keep pages honest-but-now-inconsistent; either way must fail
            p = _write(d, "pages.json", PAGES)
            rc = main(["--root", r, "--pages", p])
            self.assertEqual(rc, 1)

    def test_missing_input_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            r = _write(d, "knowledge.json", ROOT)
            rc = main(["--root", r, "--pages", os.path.join(d, "nope.json")])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
