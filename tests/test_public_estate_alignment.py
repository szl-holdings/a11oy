from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_public_estate_alignment.py"
SPEC = importlib.util.spec_from_file_location("public_estate_alignment", SCRIPT)
assert SPEC and SPEC.loader
alignment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alignment)


class PublicEstateAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = alignment.load_json(alignment.CONTRACT)
        self.manifest = alignment.load_json(alignment.HF_MANIFEST)
        self.evidence = alignment.validate(self.contract, self.manifest)

    def test_contract_has_one_fabric_five_bodies_and_six_engines(self) -> None:
        self.assertEqual(self.contract["fabric"]["id"], "a11oy")
        self.assertEqual(len(self.contract["publicDomainBodies"]), 5)
        self.assertEqual(len(self.contract["internalEngines"]), 6)
        self.assertEqual(
            [row["id"] for row in self.contract["publicDomainBodies"]],
            ["immune", "lyte", "terra", "counsel", "finance"],
        )

    def test_declared_hub_keep_set_equals_measured_public_inventory(self) -> None:
        expected = alignment.expected_spaces(self.contract)
        observed = alignment.measured_spaces(self.manifest)
        self.assertEqual(len(expected), 15)
        self.assertEqual(expected, observed)

    def test_truth_and_authority_cannot_be_promoted_by_rendering(self) -> None:
        formula = next(
            row
            for row in self.contract["internalEngines"]
            if row["id"] == "formula-kernel"
        )
        self.assertEqual(formula["lockedProvenCount"], 8)
        self.assertEqual(
            formula["lambdaStatus"], "CONJECTURE_1_OPEN_ADVISORY_ONLY"
        )
        self.assertEqual(self.contract["authority"]["publicEffectors"], [])
        self.assertFalse(self.contract["authority"]["productionAuthorization"])
        self.assertTrue(self.contract["authority"]["humanApprovalRequired"])

    def test_generated_fragments_are_current_and_single_source(self) -> None:
        generated = alignment.generated()
        self.assertEqual(set(generated), set(alignment.OUTPUTS.values()))
        for path, content in generated.items():
            self.assertTrue(path.exists(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), content.rstrip() + "\n")
            self.assertEqual(content.count("BEGIN SZL PUBLIC ESTATE"), 1)
            self.assertEqual(content.count("END SZL PUBLIC ESTATE"), 1)
            self.assertIn(self.evidence["alignmentSha256"], content)

    def test_product_front_door_names_canonical_origins(self) -> None:
        landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        for value in self.contract["canonical"].values():
            if value.startswith("https://"):
                host = value.removeprefix("https://").split("/", 1)[0]
                self.assertIn(host, landing)
        for body in self.contract["publicDomainBodies"]:
            self.assertIn(body["name"].split()[0], landing)

    def test_contract_json_is_deterministic_and_strict(self) -> None:
        source = alignment.CONTRACT.read_text(encoding="utf-8")
        decoded = json.loads(source)
        self.assertEqual(decoded, self.contract)
        self.assertTrue(source.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
