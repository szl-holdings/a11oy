from __future__ import annotations

import copy
import hashlib
import importlib.util
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from scripts.hf_keep_policy import load_keep_ids

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_public_estate_alignment.py"
SPEC = importlib.util.spec_from_file_location("public_estate_alignment", SCRIPT)
assert SPEC and SPEC.loader
alignment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(alignment)


class BrandingText(HTMLParser):
    """Read heading/link text, never identifiers, attributes, scripts or CSS."""
    def __init__(self) -> None:
        super().__init__()
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3", "h4", "a", "script", "style"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            del self.stack[self.stack.index(tag):]

    def handle_data(self, data):
        if self.stack and not any(tag in self.stack for tag in ("script", "style")):
            self.text.append(data.strip())


class PublicEstateAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = alignment.load_json(alignment.CONTRACT)
        self.manifest = alignment.load_json(alignment.HF_MANIFEST)
        self.evidence = alignment.validate(self.contract, self.manifest)

    def test_contract_has_one_fabric_six_bodies_and_six_engines(self) -> None:
        self.assertEqual(self.contract["fabric"]["id"], "a11oy")
        self.assertEqual(len(self.contract["publicDomainBodies"]), 6)
        self.assertEqual(len(self.contract["internalEngines"]), 6)
        self.assertEqual(
            [row["id"] for row in self.contract["publicDomainBodies"]],
            ["killinchu", "sentra", "lyte", "finance", "terra", "counsel"],
        )

    def test_owner_directive_role_boundaries_are_materialized(self) -> None:
        body_ids = {row["id"] for row in self.contract["publicDomainBodies"]}
        self.assertIn("sentra", body_ids)
        self.assertIn("killinchu", body_ids)
        self.assertNotIn("immune", body_ids)
        immune = next(
            row
            for row in self.contract["supportingSystems"]
            if row["id"] == "immune"
        )
        self.assertEqual(immune["classification"], "ENGINE_LIBRARY_UNDER_SENTRA")
        ayllu = next(
            row
            for row in self.contract["supportingSystems"]
            if row["id"] == "ayllu"
        )
        self.assertEqual(
            ayllu["classification"], "NON_PRODUCT_SUPPORT_SURFACE"
        )
        self.assertNotIn("ayllu", body_ids)
        historical = {
            row["id"]: row["state"] for row in self.contract["historicalBindings"]
        }
        self.assertEqual(historical, {"vessels": "FOLDED_INTO_KILLINCHU"})

    def test_declared_hub_classifications_equal_measured_public_inventory(self) -> None:
        topology = alignment.topology_spaces(self.contract)
        inventory_only = alignment.inventory_only_spaces(self.contract)
        observed = alignment.measured_spaces(self.manifest)
        self.assertEqual(len(topology), 16)
        self.assertEqual(inventory_only, ["SZLHOLDINGS/yarqa"])
        self.assertEqual(
            sorted(topology + inventory_only, key=str.casefold),
            observed,
        )

    def test_killinchu_is_public_body_and_governed_keeper(self) -> None:
        killinchu = next(
            row for row in self.contract["publicDomainBodies"]
            if row["id"] == "killinchu"
        )
        self.assertEqual(killinchu["githubRepository"], "szl-holdings/killinchu")
        self.assertEqual(killinchu["huggingFaceRepositories"], ["SZLHOLDINGS/killinchu"])
        self.assertEqual(killinchu["truth"], "SOURCE_OWNED_RUNTIME")
        self.assertIn("SZLHOLDINGS/killinchu", alignment.governed_keep_spaces())

    def test_immune_spaces_are_supporting_engine_surfaces_under_sentra(self) -> None:
        immune = next(
            row
            for row in self.contract["supportingSystems"]
            if row["id"] == "immune"
        )
        self.assertEqual(immune["classification"], "ENGINE_LIBRARY_UNDER_SENTRA")
        self.assertEqual(
            immune["huggingFaceRepositories"],
            ["SZLHOLDINGS/immune", "SZLHOLDINGS/immune-lattice"],
        )
        topology = alignment.topology_spaces(self.contract)
        governed = alignment.governed_keep_spaces()
        for space in immune["huggingFaceRepositories"]:
            with self.subTest(space=space):
                self.assertIn(space, topology)
                self.assertNotIn(space, governed)
                self.assertNotIn(
                    space, alignment.inventory_only_spaces(self.contract)
                )

    def test_ayllu_is_non_product_support_not_a_governed_keeper(self) -> None:
        ayllu = next(
            row
            for row in self.contract["supportingSystems"]
            if row["id"] == "ayllu"
        )
        self.assertEqual(ayllu["classification"], "NON_PRODUCT_SUPPORT_SURFACE")
        self.assertEqual(ayllu["huggingFaceRepositories"], ["SZLHOLDINGS/ayllu"])
        self.assertNotIn(
            "ayllu", {row["id"] for row in self.contract["publicDomainBodies"]}
        )
        self.assertIn("SZLHOLDINGS/ayllu", alignment.topology_spaces(self.contract))
        governed = alignment.governed_keep_spaces()
        organization_keepers = [
            item for item in governed if item.startswith("SZLHOLDINGS/")
        ]
        self.assertEqual(len(organization_keepers), 8)
        self.assertNotIn("SZLHOLDINGS/ayllu", governed)
        self.assertIn("SZLHOLDINGS/sentra", governed)
        self.assertEqual(governed, load_keep_ids(alignment.KEEP_POLICY))
        self.assertEqual(
            self.evidence["governedKeepPolicySource"],
            "docs/series-a/hf-space-keep-list.yaml",
        )
        self.assertEqual(
            self.evidence["keepPolicySha256"],
            hashlib.sha256(alignment.KEEP_POLICY.read_bytes()).hexdigest(),
        )

    def test_yarqa_is_observed_without_promoting_keep_or_topology(self) -> None:
        rows = self.contract["inventoryOnlyHuggingFaceRepositories"]
        yarqa = next(row for row in rows if row["id"] == "SZLHOLDINGS/yarqa")
        self.assertEqual(yarqa, {
            "id": "SZLHOLDINGS/yarqa", "classification": "INVENTORY_ONLY",
            "governedKeep": False, "disposition": "FOLD",
            "policySource": "docs/series-a/hf-space-keep-list.yaml",
        })
        self.assertNotIn(yarqa["id"], alignment.governed_keep_spaces())
        self.assertNotIn(yarqa["id"], alignment.topology_spaces(self.contract))
        removed = copy.deepcopy(self.contract)
        removed["inventoryOnlyHuggingFaceRepositories"] = [row for row in rows if row["id"] != yarqa["id"]]
        with self.assertRaisesRegex(
            alignment.ContractError, "Yarqa must remain the sole inventory-only Space"
        ):
            alignment.validate(removed, self.manifest)
        promoted = copy.deepcopy(self.contract)
        promoted_yarqa = next(
            row for row in promoted["inventoryOnlyHuggingFaceRepositories"]
            if row["id"] == "SZLHOLDINGS/yarqa"
        )
        promoted_yarqa["governedKeep"] = True
        with self.assertRaisesRegex(alignment.ContractError, "cannot be a governed keeper"):
            alignment.validate(promoted, self.manifest)

    def test_inventory_only_classification_is_strict_and_disjoint(self) -> None:
        for field, value, message in (
            ("classification", "LABORATORY", "classification drifted"),
            ("governedKeep", True, "cannot be a governed keeper"),
            ("disposition", "KEEP", "must retain its FOLD disposition"),
            ("policySource", "elsewhere.yaml", "must cite the canonical keep policy"),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.contract)
                changed["inventoryOnlyHuggingFaceRepositories"][0][field] = value
                with self.assertRaisesRegex(alignment.ContractError, message):
                    alignment.validate(changed, self.manifest)

        overlap = copy.deepcopy(self.contract)
        overlap["laboratorySurfaces"].append("SZLHOLDINGS/yarqa")
        with self.assertRaisesRegex(alignment.ContractError, "cannot be topology bindings"):
            alignment.validate(overlap, self.manifest)

    def test_quoted_keeper_ids_are_normalized_before_overlap_checks(self) -> None:
        policy = alignment.KEEP_POLICY.read_text(encoding="utf-8").replace(
            "  - id: SZLHOLDINGS/a11oy",
            '  - id: "SZLHOLDINGS/yarqa"',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.yaml"
            path.write_text(policy, encoding="utf-8")
            keepers = alignment.governed_keep_spaces(path)

        self.assertIn("SZLHOLDINGS/yarqa", keepers)
        self.assertNotIn('"SZLHOLDINGS/yarqa"', keepers)
        self.assertTrue(
            set(alignment.inventory_only_spaces(self.contract)) & set(keepers)
        )

    def test_keeper_id_parser_rejects_non_repository_scalars(self) -> None:
        policy = alignment.KEEP_POLICY.read_text(encoding="utf-8").replace(
            "  - id: SZLHOLDINGS/a11oy",
            "  - id: [SZLHOLDINGS/a11oy]",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.yaml"
            path.write_text(policy, encoding="utf-8")
            with self.assertRaisesRegex(alignment.ContractError, "invalid keeper id"):
                alignment.governed_keep_spaces(path)

    def test_keeper_parser_rejects_unrecognized_sequence_syntax(self) -> None:
        original = alignment.KEEP_POLICY.read_text(encoding="utf-8")
        for replacement in (
            "  - {id: SZLHOLDINGS/ayllu}",
            "  - id : SZLHOLDINGS/ayllu",
        ):
            with self.subTest(replacement=replacement):
                policy = original.replace("  - id: SZLHOLDINGS/a11oy", replacement)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "keep.yaml"
                    path.write_text(policy, encoding="utf-8")
                    with self.assertRaisesRegex(
                        alignment.ContractError,
                        "unrecognized keeper item",
                    ):
                        alignment.governed_keep_spaces(path)

    def test_keeper_parser_ignores_top_level_comments_without_truncation(self) -> None:
        expected = alignment.governed_keep_spaces()
        policy = alignment.KEEP_POLICY.read_text(encoding="utf-8").replace(
            "  - id: SZLHOLDINGS/terra",
            "# The comment must not terminate the governed keep section.\n"
            "  - id: SZLHOLDINGS/terra",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.yaml"
            path.write_text(policy, encoding="utf-8")
            keepers = alignment.governed_keep_spaces(path)

        self.assertEqual(keepers, expected)

    def test_keeper_parser_rejects_unexpected_top_level_syntax(self) -> None:
        policy = alignment.KEEP_POLICY.read_text(encoding="utf-8").replace(
            "  - id: SZLHOLDINGS/terra",
            "unexpected scalar\n  - id: SZLHOLDINGS/terra",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.yaml"
            path.write_text(policy, encoding="utf-8")
            with self.assertRaisesRegex(
                alignment.ContractError,
                "unexpected top-level syntax",
            ):
                alignment.governed_keep_spaces(path)

    def test_operator_and_validator_share_the_bounded_keep_parser(self) -> None:
        operator = (ROOT / "scripts" / "hf_consolidate_fleet.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("governed = load_keep_ids(path)", operator)
        self.assertNotIn("re.finditer", operator)
        governed = load_keep_ids(alignment.KEEP_POLICY)
        self.assertIn("SZLHOLDINGS/sentra", governed)
        self.assertNotIn("SZLHOLDINGS/ayllu", governed)

    def test_unknown_inventory_space_still_fails_closed(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["inventory"]["spaces"].append(
            {"id": "SZLHOLDINGS/undeclared", "repoType": "space"}
        )
        manifest["counts"]["spaces"] += 1
        with self.assertRaisesRegex(
            alignment.ContractError,
            r"undeclared=\['SZLHOLDINGS/undeclared'\]",
        ):
            alignment.validate(self.contract, manifest)

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
            self.assertIn("inventory is observational", content)
            self.assertIn("Inventory-only / FOLD", content)
            self.assertIn("16 topology-bound Spaces", content)
            self.assertIn("`SZLHOLDINGS/yarqa`", content)
            self.assertIn("Sentra Assurance Command", content)

    def test_product_front_door_names_canonical_origins(self) -> None:
        landing = (ROOT / "a11oy_landing.html").read_text(encoding="utf-8")
        branding = BrandingText()
        branding.feed(landing)
        words = " ".join(branding.text).casefold().split()
        for value in self.contract["canonical"].values():
            if value.startswith("https://"):
                host = value.removeprefix("https://").split("/", 1)[0]
                self.assertIn(host, landing)
        for body in self.contract["publicDomainBodies"]:
            name = body["name"].split()[0]
            self.assertIn(name.casefold(), words, f"Missing heading/link body name: {name}")

    def test_identifiers_and_source_code_are_not_visible_branding(self) -> None:
        branding = BrandingText()
        branding.feed('<style>.lyte{}</style><script>const name="Lyte"</script>'
                      '<!-- Lyte --><a href="/lyte" id="body-lyte">Open</a>')
        self.assertEqual(branding.text, ["Open"])
        branding.feed('<h3>LYTE</h3>')
        self.assertIn("LYTE", branding.text)

    def test_receipt_binds_mapping_truth_and_authority(self) -> None:
        for section, field in (("publicDomainBodies", "githubRepository"),
                               ("publicDomainBodies", "truth"),
                               ("internalEngines", "authority")):
            changed = copy.deepcopy(self.contract)
            changed[section][0][field] += "_CHANGED"
            evidence = alignment.validate(changed, self.manifest)
            self.assertNotEqual(evidence["alignmentSha256"], self.evidence["alignmentSha256"])

    def test_contract_json_is_deterministic_and_strict(self) -> None:
        source = alignment.CONTRACT.read_text(encoding="utf-8")
        decoded = json.loads(source)
        self.assertEqual(decoded, self.contract)
        self.assertTrue(source.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
