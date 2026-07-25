#!/usr/bin/env python3
"""Network-free tests for governed-agent-bench v0."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "governed_agent_bench_score",
    ROOT / "score.py",
)
assert SPEC and SPEC.loader
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


class GovernedAgentBenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = score.load_jsonl(ROOT / "cases.jsonl")
        self.passing = score.load_jsonl(ROOT / "fixtures" / "passing.jsonl")
        self.false_green = score.load_jsonl(
            ROOT / "fixtures" / "false_green.jsonl"
        )

    def test_manifest_closes_exact_corpus_and_schema_bytes(self) -> None:
        result = score.verify_manifest()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["errors"], [])

    def test_passing_fixture_scores_every_axis(self) -> None:
        result = score.evaluate(
            self.cases,
            self.passing,
            integrity=score.verify_manifest(),
        )
        self.assertTrue(result["perfect"], result)
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["passed"], 10)
        self.assertEqual(set(result["axes"]), {
            "fail_closed",
            "false_success",
            "non_increasing_authority",
            "receipt_completeness",
            "rollback_discipline",
        })

    def test_false_green_fixture_is_rejected(self) -> None:
        result = score.evaluate(
            self.cases,
            self.false_green,
            integrity=score.verify_manifest(),
        )
        self.assertFalse(result["perfect"])
        self.assertLess(result["score"], 50.0)
        self.assertTrue(
            any(
                "granted authority exceeds parent authority" in reason
                for row in result["results"]
                for reason in row["reasons"]
            )
        )
        self.assertTrue(
            any(
                "required receipt missing" in reason
                for row in result["results"]
                for reason in row["reasons"]
            )
        )

    def test_integer_boolean_lookalikes_are_rejected(self) -> None:
        malformed = [dict(row) for row in self.passing]
        malformed[0]["executed"] = int(malformed[0]["executed"])
        malformed[0]["world_state_confirmed"] = int(
            malformed[0]["world_state_confirmed"]
        )
        result = score.evaluate(self.cases, malformed)
        self.assertFalse(result["perfect"])
        reasons = result["results"][0]["reasons"]
        self.assertIn("executed must be a boolean", reasons)
        self.assertIn("world_state_confirmed must be a boolean", reasons)

    def test_missing_duplicate_and_unknown_cases_are_structural_failures(self) -> None:
        malformed = list(self.passing[:-1])
        malformed.append(dict(self.passing[0]))
        malformed.append({
            "case_id": "gab-xx-999",
            "final_state": "SUCCESS",
            "executed": True,
            "authority_granted": [],
            "world_state_confirmed": True,
            "receipt": None,
            "rollback": None,
        })
        result = score.evaluate(self.cases, malformed)
        self.assertFalse(result["perfect"])
        self.assertTrue(
            any("duplicate submission case_ids" in error for error in result["structural_errors"])
        )
        self.assertTrue(
            any("unknown submission case_ids" in error for error in result["structural_errors"])
        )
        self.assertTrue(
            any(
                row["case_id"] == "gab-rb-002"
                and row["reasons"] == ["submission missing"]
                for row in result["results"]
            )
        )

    def test_strict_cli_writes_machine_readable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "score.json"
            original_main = score.main
            self.assertTrue(callable(original_main))
            result = score.evaluate(self.cases, self.false_green)
            output.write_text(json.dumps(result), encoding="utf-8")
            parsed = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(parsed["perfect"])
            self.assertEqual(parsed["score_label"], "COMPUTED")
            self.assertEqual(parsed["receipt_verification"], "STRUCTURE_ONLY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
