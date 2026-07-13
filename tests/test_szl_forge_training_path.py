from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
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

            train_rows = list(forge.iter_jsonl(tmp_path / "first" / first["train"]["path"]))
            eval_rows = list(forge.iter_jsonl(tmp_path / "first" / first["eval"]["path"]))
            self.assertTrue(all(row["training_eligible"] is True and row["split"] == "TRAIN" for row in train_rows))
            self.assertTrue(all(row["training_eligible"] is False and row["split"] == "EVAL" for row in eval_rows))
            self.assertTrue({row["prompt_sha256"] for row in train_rows}.isdisjoint(
                {row["prompt_sha256"] for row in eval_rows}
            ))

    def test_curriculum_rejects_tampering_and_forbidden_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            manifest = forge.build_curriculum(tmp_path / "generated")
            train_path = tmp_path / "generated" / manifest["train"]["path"]
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

    def test_dependency_light_validator_rejects_every_previously_accepted_bad_shape(self) -> None:
        bad = {
            "schema_version": forge.DRAFT_SCHEMA,
            "status": "ANSWER_PROPOSED",
            "answer": "x",
            "evidence_ids": ["BAD SPACE"],
            "formula_refs": "not-a-list",
            "uncertainty": {"band": "IMPOSSIBLE", "basis": ""},
            "abstention": {"required": False, "code": "BOGUS", "detail": ""},
            "tool_proposal": {"state": "NONE", "tool_id": "destructive.tool", "arguments": {"x": 1}},
        }
        self.assertGreaterEqual(len(forge.validate_draft(bad)), 6)

        contradictory = forge._draft_for({"kind": "ABSTAIN", "code": "POLICY_DENIED"})
        contradictory["tool_proposal"] = {"state": "PROPOSED", "tool_id": None, "arguments": None}
        self.assertTrue(any("tool" in error for error in forge.validate_draft(contradictory)))

    def test_curriculum_recomputes_row_hashes_and_refuses_stale_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "generated"
            manifest = forge.build_curriculum(output)
            train_path = output / manifest["train"]["path"]
            rows = list(forge.iter_jsonl(train_path))
            rows[0]["messages"][1]["content"] = "third-party trace injection"
            train_path.write_text("".join(forge.canonical_json(row) + "\n" for row in rows), encoding="utf-8")
            manifest["train"]["sha256"] = forge.sha256_file(train_path)
            forge.atomic_json(output / "curriculum-manifest.json", manifest)
            with self.assertRaisesRegex(forge.GateRefused, "prompt hash mismatch"):
                forge.validate_curriculum(output / "curriculum-manifest.json")

    def test_curriculum_rejects_absolute_and_traversal_paths(self) -> None:
        for bad_path, message in (("../outside.jsonl", "escapes"), (str(Path.cwd().resolve() / "outside.jsonl"), "absolute")):
            with self.subTest(bad_path=bad_path), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "generated"
                manifest = forge.build_curriculum(output)
                manifest["train"]["path"] = bad_path
                forge.atomic_json(output / "curriculum-manifest.json", manifest)
                with self.assertRaisesRegex(forge.GateRefused, message):
                    forge.validate_curriculum(output / "curriculum-manifest.json")

    def test_contract_pins_curriculum_source_and_schema_hashes(self) -> None:
        contract = forge.load_json(forge.CONTRACT_PATH)
        contract["curriculum"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(forge.GateRefused, "source digest mismatch"):
            forge._verify_contract_assets(contract)

    def test_training_mutex_refuses_a_second_local_training_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "training.lock"
            with forge.training_mutex(lock_path):
                with self.assertRaisesRegex(forge.GateRefused, "exclusive lease"):
                    with forge.training_mutex(lock_path):
                        self.fail("second training lease should not be acquired")

    def test_python_network_control_denies_and_restores_socket_functions(self) -> None:
        original_socket = socket.socket
        with forge.deny_python_network() as receipt:
            self.assertEqual(receipt["state"], "PYTHON_SOCKET_DENIED")
            with self.assertRaises(forge.PythonNetworkDenied):
                socket.getaddrinfo("example.invalid", 443)
        self.assertIs(socket.socket, original_socket)

    def test_runtime_identity_is_measured_and_fail_closed(self) -> None:
        contract = forge.load_json(forge.CONTRACT_PATH)
        versions = {**contract["runtime"]["package_exact"], **{
            package: "1.0.0" for package in contract["runtime"]["package_required_measured"]
        }}
        cuda = SimpleNamespace(
            get_device_capability=lambda: (12, 0),
            get_device_name=lambda: contract["runtime"]["required_device_name"],
        )
        torch_ok = SimpleNamespace(__version__="2.10.0+cu130", version=SimpleNamespace(cuda="13.0"), cuda=cuda)
        receipt = forge.verify_runtime_identity(torch_ok, contract, versions.__getitem__, (3, 12, 10))
        self.assertEqual(receipt["state"], "PASS")
        torch_bad = SimpleNamespace(__version__="2.9.0+cu128", version=SimpleNamespace(cuda="12.8"), cuda=cuda)
        with self.assertRaisesRegex(forge.GateRefused, "torch"):
            forge.verify_runtime_identity(torch_bad, contract, versions.__getitem__, (3, 12, 10))

    def test_reload_semantics_do_not_accept_one_valid_canned_abstention(self) -> None:
        source = forge.load_json(forge.SOURCE_PATH)
        expected = forge._draft_for(source["eval_scenarios"][0])
        canned = forge._draft_for({"kind": "ABSTAIN", "code": "POLICY_DENIED"})
        result = forge.evaluate_draft_completion(forge.canonical_json(canned), expected)
        self.assertTrue(result["draft_schema_valid"])
        self.assertFalse(result["exact_expected_match"])

    def test_final_integrity_receipt_fails_closed_on_identity_change(self) -> None:
        original = forge._collect_input_identity
        try:
            forge._collect_input_identity = lambda _base: {"identity_sha256": "b" * 64}
            with tempfile.TemporaryDirectory() as directory:
                receipt_dir = Path(directory)
                with self.assertRaisesRegex(forge.GateRefused, "changed after admission"):
                    forge._finalize_input_integrity(Path(directory), {"identity_sha256": "a" * 64}, receipt_dir)
                receipt = forge.load_json(receipt_dir / "final-input-integrity-receipt.json")
                self.assertEqual(receipt["state"], "FAIL")
        finally:
            forge._collect_input_identity = original

    def test_runtime_guard_trips_on_hot_sample(self) -> None:
        contract = forge.load_json(forge.CONTRACT_PATH)
        hot = {"temperature_c": contract["gpu_admission"]["maximum_training_temperature_c"] + 1}
        guard = forge.RuntimeGuard(contract, query=lambda: hot)
        guard._watch()
        with self.assertRaisesRegex(forge.GateRefused, "thermal"):
            guard.check("unit-test")

    def test_private_input_snapshot_copies_and_hashes_the_base(self) -> None:
        manifest = forge.validate_curriculum()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base"
            base.mkdir()
            source_file = base / "model.safetensors"
            source_file.write_bytes(b"pinned-model-bytes")
            identity = {
                "identity_sha256": "a" * 64,
                "train": manifest["train"],
                "eval": manifest["eval"],
                "base_files": [{
                    "path": source_file.name,
                    "bytes": source_file.stat().st_size,
                    "sha256": forge.sha256_file(source_file),
                }],
            }
            output = root / "run"
            receipts = output / "receipts"
            receipts.mkdir(parents=True)
            contract = {"training": {"minimum_output_free_bytes": 0}}
            staged_base, staged_train, staged_eval = forge._stage_inputs(
                base, output, receipts, identity, contract,
            )
            staged_file = staged_base / source_file.name
            self.assertEqual(staged_file.read_bytes(), b"pinned-model-bytes")
            self.assertEqual(forge.sha256_file(staged_train), manifest["train"]["sha256"])
            self.assertEqual(forge.sha256_file(staged_eval), manifest["eval"]["sha256"])
            source_file.write_bytes(b"later-cache-mutation")
            self.assertEqual(staged_file.read_bytes(), b"pinned-model-bytes")
            receipt = forge.load_json(receipts / "input-snapshot-receipt.json")
            self.assertEqual(receipt["state"], "PASS")
            self.assertEqual(receipt["base_snapshot_strategy"], "PRIVATE_HASH_VERIFIED_COPY")

    def test_persistent_training_gate_uses_non_retryable_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exit_code = forge.main([
                "train",
                "--base-snapshot", str(root / "missing-base"),
                "--output-dir", str(root / "output"),
                "--confirmation", "wrong",
            ])
            self.assertEqual(exit_code, 5)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
