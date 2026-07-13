from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "model_release" / "szl-forge" / "szl_forge_training.py"
SPEC = importlib.util.spec_from_file_location("szl_forge_training", MODULE_PATH)
assert SPEC and SPEC.loader
forge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forge)


class SZLForgeTrainingPathTests(unittest.TestCase):
    def test_project_authored_curriculum_is_deterministic_and_split_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            first = forge.build_curriculum(tmp_path / "first")
            second = forge.build_curriculum(tmp_path / "second")

            self.assertEqual(first["state"], "ADMITTED_PROJECT_AUTHORED_ONLY")
            self.assertEqual(first["train"]["rows"], 30)
            self.assertEqual(first["eval"]["rows"], 8)
            self.assertEqual(first["train"]["sha256"], second["train"]["sha256"])
            self.assertEqual(first["eval"]["sha256"], second["eval"]["sha256"])

            train_rows = list(forge.iter_jsonl(Path(first["train"]["path"])))
            eval_rows = list(forge.iter_jsonl(Path(first["eval"]["path"])))
            self.assertTrue(all(row["training_eligible"] is True and row["split"] == "TRAIN" for row in train_rows))
            self.assertTrue(all(row["training_eligible"] is False and row["split"] == "EVAL" for row in eval_rows))
            self.assertTrue({row["prompt_sha256"] for row in train_rows}.isdisjoint(
                {row["prompt_sha256"] for row in eval_rows}
            ))

    def test_curriculum_rejects_tampering_and_forbidden_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            manifest = forge.build_curriculum(tmp_path / "generated")
            train_path = Path(manifest["train"]["path"])
            rows = list(forge.iter_jsonl(train_path))
            rows[0]["forbidden_source_refs"] = ["model_release/m1/brain-ingest-ledger.jsonl"]
            train_path.write_text("".join(forge.canonical_json(row) + "\n" for row in rows), encoding="utf-8")
            manifest["train"]["sha256"] = forge.sha256_file(train_path)
            forge.atomic_json(tmp_path / "generated" / "curriculum-manifest.json", manifest)

            with self.assertRaisesRegex(forge.GateRefused, "forbidden material"):
                forge.validate_curriculum(tmp_path / "generated" / "curriculum-manifest.json")

    def test_gpu_policy_refuses_any_single_bad_sample_without_weakening(self) -> None:
        contract = forge.load_json(forge.CONTRACT_PATH)
        samples = iter(
            [
                {"memory_free_mib": 7000, "utilization_pct": 1, "temperature_c": 45},
                {"memory_free_mib": 6655, "utilization_pct": 1, "temperature_c": 45},
            ]
        )
        with self.assertRaisesRegex(forge.GateRefused, "thresholds"):
            forge.sample_gpu(
                contract["gpu_admission"], 3, 30, query=lambda: next(samples), sleeper=lambda _: None
            )

    def test_training_confirmation_refuses_before_preflight_or_ml_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            with self.assertRaisesRegex(forge.GateRefused, "confirmation"):
                forge.run_training(tmp_path / "missing-base", tmp_path / "output", "wrong")
            self.assertFalse((tmp_path / "output").exists())

    def test_draft_validator_enforces_fail_closed_shape(self) -> None:
        scenario = forge.load_json(forge.SOURCE_PATH)["train_scenarios"][0]
        valid = forge._draft_for(scenario)
        self.assertEqual(forge.validate_draft(valid), [])

        invalid = json.loads(json.dumps(valid))
        invalid["evidence_ids"] = []
        self.assertIn("answer proposal requires evidence identifiers", forge.validate_draft(invalid))

        invalid = forge._draft_for({"kind": "ABSTAIN", "code": "POLICY_DENIED"})
        invalid["answer"] = "executed"
        self.assertTrue(any("null answer" in error for error in forge.validate_draft(invalid)))


if __name__ == "__main__":
    unittest.main()
