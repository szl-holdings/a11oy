from __future__ import annotations

import importlib.util
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

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
        self.assertEqual(len(expected), 16)
        self.assertIn("SZLHOLDINGS/ayllu", self.contract["laboratorySurfaces"])
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
