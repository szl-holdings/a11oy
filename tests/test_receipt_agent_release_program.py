"""Dependency-light guardrails for the proposed ReceiptAgent release program."""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "model_release" / "receipt-agent"


def load_json(name: str) -> dict[str, Any]:
    return json.loads((PROGRAM / name).read_text(encoding="utf-8"))


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    raise AssertionError(f"unsupported schema type in test validator: {expected}")


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the strict JSON-Schema subset used by this artifact family.

    This is intentionally small and standard-library-only. It is not a general
    JSON Schema implementation; it keeps this focused release-program check
    runnable in the repository's minimal Python environment.
    """

    if "type" in schema:
        expected = schema["type"]
        expected_types = expected if isinstance(expected, list) else [expected]
        assert any(_type_matches(instance, item) for item in expected_types), (
            f"{path}: expected type {expected_types}, got {type(instance).__name__}"
        )

    if "const" in schema:
        assert instance == schema["const"], f"{path}: expected const {schema['const']!r}"
    if "enum" in schema:
        assert instance in schema["enum"], f"{path}: {instance!r} not in enum"

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        assert not missing, f"{path}: missing required keys {missing}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(instance) - set(properties))
            assert not extras, f"{path}: unexpected properties {extras}"
        for key, subschema in properties.items():
            if key in instance:
                validate(instance[key], subschema, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema:
            assert len(instance) >= schema["minItems"], f"{path}: too few items"
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in instance]
            assert len(encoded) == len(set(encoded)), f"{path}: duplicate items"
        if "items" in schema:
            for index, item in enumerate(instance):
                validate(item, schema["items"], f"{path}[{index}]")

    if isinstance(instance, str):
        if "minLength" in schema:
            assert len(instance) >= schema["minLength"], f"{path}: string too short"
        if "pattern" in schema:
            assert re.search(schema["pattern"], instance), (
                f"{path}: {instance!r} does not match {schema['pattern']!r}"
            )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema:
            assert instance >= schema["minimum"], f"{path}: below minimum"
        if "maximum" in schema:
            assert instance <= schema["maximum"], f"{path}: above maximum"

    for subschema in schema.get("allOf", []):
        conditional = subschema.get("if")
        if conditional is None:
            validate(instance, subschema, path)
            continue
        try:
            validate(instance, conditional, path)
        except AssertionError:
            if "else" in subschema:
                validate(instance, subschema["else"], path)
        else:
            if "then" in subschema:
                validate(instance, subschema["then"], path)


class ReceiptAgentReleaseProgramTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = load_json("release-manifest.json")
        self.admission = load_json("admission-manifest.json")
        self.evaluation = load_json("evaluation-manifest.json")
        self.output_schema = load_json("receipt-agent-output.schema.json")
        self.example = load_json("example-unavailable.json")

    def test_all_machine_readable_artifacts_match_their_schemas(self) -> None:
        pairs = (
            ("release-manifest.json", "release-manifest.schema.json"),
            ("admission-manifest.json", "admission-manifest.schema.json"),
            ("evaluation-manifest.json", "evaluation-manifest.schema.json"),
            ("example-unavailable.json", "receipt-agent-output.schema.json"),
        )
        for instance_name, schema_name in pairs:
            with self.subTest(instance=instance_name):
                schema = load_json(schema_name)
                self.assertEqual(
                    schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
                )
                self.assertTrue(schema["$id"].startswith("https://a-11-oy.com/schemas/"))
                validate(load_json(instance_name), schema)

    def test_exact_existing_adapter_identity_is_preserved(self) -> None:
        adapter = self.release["existing_adapter"]
        self.assertEqual(
            adapter["base_repository"], "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit"
        )
        self.assertEqual(
            adapter["base_revision"], "d2f2dd02b071701d5100a04a7a49d6fb0bd305b7"
        )
        self.assertEqual(
            adapter["adapter_sha256"],
            "682e2f0ea480d47c284b9de12c2e3d2d5170934c065e82fc375e3f069b4730ac",
        )
        self.assertEqual(adapter["dataset_rows"], 167)
        self.assertEqual(adapter["dataset_review"], "BLOCKED_NOT_COMPLETE")
        self.assertEqual(adapter["evaluation_state"], "INCOMPLETE")

    def test_current_corpus_and_orpo_boundaries_are_fail_closed(self) -> None:
        boundary = self.release["current_data_boundary"]
        self.assertEqual(boundary["brain_raw_nodes"], 9464)
        self.assertEqual(boundary["brain_raw_nodes_training_quarantined"], 9464)
        self.assertEqual(boundary["brain_raw_rows_admitted_to_train"], 0)
        self.assertEqual(boundary["formula_crosswalk_rows"], 148)
        self.assertEqual(boundary["formula_holdout_rows"], 148)
        self.assertEqual(boundary["formula_train_rows"], 0)
        self.assertEqual((boundary["orpo_checks_passed"], boundary["orpo_checks_total"]), (0, 12))
        self.assertEqual(boundary["orpo_state"], "QUARANTINED")

    def test_program_does_not_claim_a_release_or_external_mutation(self) -> None:
        self.assertEqual(self.release["release_state"], "NOT_PROMOTED")
        self.assertEqual(self.release["quality_claim"], "NOT_ESTABLISHED")
        self.assertIn("NOT_YET_ESTABLISHED", self.release["artifact_relation"])
        self.assertTrue(all(value is False for value in self.release["external_mutations"].values()))
        self.assertEqual(self.release["identity_and_attestation"]["current_state"], "UNATTESTED")
        self.assertEqual(self.release["licensing"]["license_gate"], "BLOCKED")

    def test_hugging_face_family_is_planned_and_nonexistent(self) -> None:
        family = self.release["hf_artifact_family"]
        self.assertEqual(len(family), 5)
        self.assertEqual(
            {item["artifact_type"] for item in family},
            {"MODEL_ADAPTER", "EVALUATION_DATASET", "SCHEMA_DATASET", "SPACE", "COLLECTION"},
        )
        self.assertTrue(all(item["state"] == "PLANNED_NOT_CREATED" for item in family))
        self.assertTrue(all(item["target_id"].startswith("SZLHOLDINGS/") for item in family))

    def test_all_promotion_gates_are_unique_and_currently_blocked(self) -> None:
        gates = self.admission["gates"]
        ids = [gate["gate_id"] for gate in gates]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.admission["promotion_decision"], "BLOCKED")
        self.assertTrue(all(gate["required_for_promotion"] for gate in gates))
        self.assertTrue(all(gate["evidence"] for gate in gates))
        self.assertTrue(any(gate["state"] == "FAIL" for gate in gates))
        self.assertTrue(any(gate["state"] == "BLOCKED" for gate in gates))
        self.assertTrue(any(gate["state"] == "NOT_EVALUATED" for gate in gates))
        by_id = {gate["gate_id"]: gate for gate in gates}
        self.assertIn("9,464 of 9,464", by_id["RA-G04"]["observed"])
        self.assertIn("148 holdout", by_id["RA-G05"]["observed"])
        self.assertIn("0 of 12", by_id["RA-G06"]["observed"])

    def test_three_way_evaluation_is_preregistered_but_not_run(self) -> None:
        self.assertEqual(
            set(self.evaluation["comparators"]),
            {"base", "existing_sft", "proposed_receipt_agent"},
        )
        suite_ids = [suite["suite_id"] for suite in self.evaluation["suites"]]
        self.assertEqual(len(suite_ids), len(set(suite_ids)))
        self.assertGreaterEqual(len(suite_ids), 10)
        for suite in self.evaluation["suites"]:
            self.assertEqual(suite["dataset_state"], "NOT_PREREGISTERED")
            for result in suite["results"].values():
                self.assertEqual(result, {"state": "NOT_RUN", "value": None, "receipt": None})
        budget = self.evaluation["catastrophic_error_budget"]
        self.assertEqual(budget["allowed"], 0)
        self.assertIsNone(budget["observed"])
        self.assertEqual(budget["state"], "NOT_EVALUATED")

    def test_unavailable_example_contains_no_fake_answer_or_receipt(self) -> None:
        validate(self.example, self.output_schema)
        self.assertEqual(self.example["status"], "UNAVAILABLE")
        self.assertIsNone(self.example["answer"])
        self.assertEqual(self.example["evidence"], [])
        self.assertEqual(self.example["formulae"], [])
        self.assertEqual(self.example["tool_proposal"]["state"], "NONE")
        self.assertIsNone(self.example["tool_proposal"]["execution_receipt_id"])
        self.assertEqual(self.example["receipt_binding"]["state"], "NOT_AVAILABLE")
        self.assertIsNone(self.example["receipt_binding"]["receipt_id"])

    def test_unavailable_or_abstained_response_cannot_carry_answer_text(self) -> None:
        invalid = copy.deepcopy(self.example)
        invalid["answer"] = "fabricated answer"
        with self.assertRaises(AssertionError):
            validate(invalid, self.output_schema)

    def test_answered_response_requires_admitted_evidence_calibration_and_signature(self) -> None:
        invalid = copy.deepcopy(self.example)
        invalid["status"] = "ANSWERED"
        invalid["answer"] = "A candidate answer."
        invalid["abstention"] = {"required": False, "code": "NONE", "detail": "Evidence gate passed."}
        with self.assertRaises(AssertionError):
            validate(invalid, self.output_schema)

        valid = copy.deepcopy(invalid)
        valid["model_identity"]["adapter_sha256"] = "a" * 64
        valid["evidence"] = [
            {
                "evidence_id": "artifact:example-1",
                "content_sha256": "b" * 64,
                "support_role": "SUPPORTS",
                "admission_state": "ADMITTED_REFERENCE",
                "source_uri": "https://example.invalid/evidence/1",
            }
        ]
        valid["uncertainty"] = {
            "confidence": 0.8,
            "calibration_state": "CALIBRATED",
            "basis": "Frozen held-out calibration receipt.",
        }
        valid["receipt_binding"] = {
            "state": "SIGNED",
            "request_sha256": "c" * 64,
            "evidence_set_sha256": "d" * 64,
            "policy_snapshot_sha256": "e" * 64,
            "receipt_id": "receipt:example-signed-1",
        }
        validate(valid, self.output_schema)

        quarantined = copy.deepcopy(valid)
        quarantined["evidence"][0]["admission_state"] = "QUARANTINED"
        with self.assertRaises(AssertionError):
            validate(quarantined, self.output_schema)

    def test_formula_proof_transfer_requires_kernel_status_and_receipt(self) -> None:
        invalid = copy.deepcopy(self.example)
        invalid["formulae"] = [
            {
                "formula_id": "F1",
                "namespace": "puriq-runtime-registry",
                "status": "OPEN",
                "proof_transfer_allowed": True,
                "formula_receipt_sha256": None,
            }
        ]
        with self.assertRaises(AssertionError):
            validate(invalid, self.output_schema)

    def test_model_card_is_detailed_without_claiming_a_release(self) -> None:
        card = (PROGRAM / "MODEL_CARD_DRAFT.md").read_text(encoding="utf-8")
        required_markers = (
            "MODEL PROGRAM - NOT A WEIGHT RELEASE",
            "9,464 raw nodes",
            "148 rows",
            "0 approved for reuse",
            "szl.receipt-agent-output.v1",
            "The catastrophic-error budget is **zero**",
            "PLANNED_NOT_CREATED",
            "model program specification, not a released model",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, card)
        self.assertNotIn("trained on all 200 formulas", card.lower())
        self.assertNotIn("quality: established", card.lower())


if __name__ == "__main__":
    unittest.main()
