"""Fail-closed checks for the SZL-Forge family plan."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_release" / "szl-forge-family.json"


class SZLForgeFamilyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_family_has_five_distinct_weight_profiles(self) -> None:
        profiles = self.registry["profiles"]
        self.assertEqual(len(profiles), 5)
        self.assertEqual(len({item["model_id"] for item in profiles}), 5)
        self.assertTrue(all(item["weight_artifact_required"] is True for item in profiles))
        self.assertTrue(all(item["hf_target"].startswith("SZLHOLDINGS/") for item in profiles))

    def test_two_signed_profiles_remain_blocked_on_artifact_binding(self) -> None:
        states = {item["profile_id"]: item["state"] for item in self.registry["profiles"]}
        conflict = "SIGNED_RECEIPTS_VALID_ARTIFACT_BINDING_CONFLICT"
        self.assertEqual(states["ReceiptAgent-v1"], conflict)
        self.assertEqual(states["BrainNavigator-v1"], conflict)
        self.assertTrue(all(state.startswith("PLANNED_") for key, state in states.items()
                            if key not in {"ReceiptAgent-v1", "BrainNavigator-v1"}))

    def test_brain_and_external_inference_remain_fail_closed(self) -> None:
        brain = self.registry["brain_policy"]
        self.assertEqual(brain["raw_nodes_observed"], 9464)
        self.assertEqual(brain["raw_nodes_available_to_retrieval_and_evaluation"], 9464)
        self.assertEqual(brain["raw_nodes_admitted_to_gradients"], 0)
        self.assertEqual(brain["admission_engine"], "szl_brain_training_admission.py")
        self.assertEqual(
            brain["current_state"],
            "ROW_LEVEL_ADMISSION_ENGINE_IMPLEMENTED_CURRENT_RAW_ROWS_QUARANTINED",
        )
        council = self.registry["external_inference_council"]
        self.assertEqual(council["training_reuse_default"], "DENY_UNTIL_PROVIDER_TERMS_AND_ROW_PROVENANCE_PASS")
        self.assertFalse(council["private_data_to_third_party_allowed"])
        self.assertFalse(council["free_or_unlimited_capacity_assumed"])

    def test_holographic_is_an_interface_not_a_fake_model(self) -> None:
        self.assertEqual(self.registry["interface_surfaces"][0]["state"], "INTERFACE_NOT_MODEL")
        self.assertTrue(self.registry["naming_boundary"]["szl_1_reserved"])

    def test_yupaq_and_governed_organs_remain_outside_weights(self) -> None:
        yupaq = next(
            item for item in self.registry["interface_surfaces"]
            if item["surface_id"] == "SZL-Yupaq"
        )
        self.assertEqual(yupaq["state"], "BOUNDED_CORE_IMPLEMENTED_LIVE_VERIFICATION_PENDING")
        self.assertEqual(yupaq["runtime"], "szl_yupaq_compute.py")
        organs = self.registry["governed_organs"]
        self.assertIn("ouroboros", organs)
        self.assertIn("codex_workers", organs)
        self.assertIn("invariant", organs)
        self.assertIn("lambda", organs)
        self.assertIn("lean_mathlib", organs)

    def test_formula_accounting_refuses_unverified_200_claim(self) -> None:
        formulas = self.registry["formula_policy"]
        self.assertEqual(formulas["thesis_extracted_formula_count"], 100)
        self.assertEqual(formulas["namespace_crosswalk_records"], 146)
        self.assertEqual(formulas["holdout_rows"], 148)
        self.assertEqual(formulas["lean_declarations"], 269)
        self.assertEqual(formulas["requested_200_formula_claim"], "NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES")
        self.assertEqual(formulas["rows_admitted_to_gradients"], 0)

    def test_second_brain_release_and_admission_engine_ship_in_image(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("model_release/szl-khipu-second-brain.json", dockerfile)
        self.assertIn("COPY szl_brain_training_admission.py ./", dockerfile)


if __name__ == "__main__":
    unittest.main()
