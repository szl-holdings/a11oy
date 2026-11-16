#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline boundaries for an observed public hold with no keeper/authority grant."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import render_public_estate_alignment as alignment
from scripts.hf_keep_policy import (
    KeepPolicyError,
    load_inventory_pending_public_holds,
    load_keep_ids,
)


HELD = "SZLHOLDINGS/szl-constellation"
DISPOSITION = "HELD_PUBLIC_PENDING_OWNER_DECISION"
SECTION = (
    "inventory_pending_public_holds:\n"
    "  - id: SZLHOLDINGS/szl-constellation\n"
    "    state: OWNER_VISIBILITY_DECISION_PENDING\n"
    "    source: static/shared/public-estate-contract.v1.json#/foldExecution/2026-11-15-batch2/held\n"
)


class PendingPublicHoldTests(unittest.TestCase):
    def setUp(self):
        self.contract = alignment.load_json(alignment.CONTRACT)
        self.manifest = alignment.load_json(alignment.HF_MANIFEST)
        self.policy = alignment.KEEP_POLICY.read_text(encoding="utf-8")
        self.evidence = alignment.validate(self.contract, self.manifest)

    def parse(self, policy):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keep.yaml"
            path.write_text(policy, encoding="utf-8")
            return load_inventory_pending_public_holds(path)

    def row(self, contract, repo_id=HELD):
        return next(
            row for row in contract["inventoryOnlyHuggingFaceRepositories"]
            if row["id"] == repo_id
        )

    def test_only_existing_pending_decision_is_represented(self):
        self.assertEqual(self.parse(self.policy), [HELD])
        self.assertEqual(alignment.pending_public_hold_spaces(self.contract), [HELD])
        self.assertEqual(self.row(self.contract), {
            "id": HELD, "classification": "INVENTORY_ONLY",
            "governedKeep": False, "disposition": DISPOSITION,
            "policySource": "docs/series-a/hf-space-keep-list.yaml",
        })
        self.assertEqual(load_keep_ids(alignment.KEEP_POLICY), [
            "SZLHOLDINGS/a11oy", "SZLHOLDINGS/anatomy", "SZLHOLDINGS/counsel",
            "SZLHOLDINGS/curation-atlas", "SZLHOLDINGS/david-leads",
            "SZLHOLDINGS/finance", "SZLHOLDINGS/killinchu", "SZLHOLDINGS/lyte",
            "SZLHOLDINGS/szl-foundation-confirmation", "SZLHOLDINGS/terra",
        ])
        self.assertNotIn(HELD, alignment.topology_spaces(self.contract))
        self.assertEqual(self.evidence["huggingFaceInventoryHeldPublic"], [HELD])
        self.assertFalse(self.contract["authority"]["productionAuthorization"])
        self.assertEqual(self.contract["authority"]["publicEffectors"], [])
        self.assertTrue(self.contract["authority"]["humanApprovalRequired"])

    def test_missing_duplicate_malformed_or_unsupported_policy_is_rejected(self):
        self.assertIn(SECTION, self.policy)
        alternatives = [
            "",
            SECTION + SECTION,
            SECTION.replace(HELD, "SZLHOLDINGS/immune"),
            SECTION.replace("OWNER_VISIBILITY_DECISION_PENDING", "APPROVED"),
            SECTION.replace("2026-11-15-batch2", "2026-11-14"),
            SECTION + "  - id: SZLHOLDINGS/other\n",
            SECTION + "    state: OWNER_VISIBILITY_DECISION_PENDING\n",
            SECTION.replace("inventory_pending_public_holds:", "  inventory_pending_public_holds:"),
            SECTION.replace("inventory_pending_public_holds:", "inventory_pending_public_holds :"),
            SECTION.replace("inventory_pending_public_holds:", "inventory_pending_public_holds: []"),
            SECTION + "    keeper: true\n",
            SECTION.replace("  - id: ", "  - id : "),
            SECTION.replace("    state:", "      state:"),
        ]
        for alternative in alternatives:
            with self.subTest(alternative=alternative):
                with self.assertRaises(KeepPolicyError):
                    self.parse(self.policy.replace(SECTION, alternative))
        with self.assertRaises(KeepPolicyError):
            self.parse(self.policy.replace(SECTION, "# " + SECTION.replace("\n", "\n# ")))

    def test_quoted_duplicate_keys_are_not_alternative_policy_authority(self):
        for key in ('"inventory_pending_public_holds"', "'inventory_pending_public_holds'"):
            with self.subTest(key=key):
                with self.assertRaises(KeepPolicyError):
                    self.parse(self.policy + "\n" + key + ": []\n")

    def test_malformed_inventory_ids_use_the_controlled_error_path(self):
        for identity in (None, [], {}, 3):
            with self.subTest(identity=identity):
                changed = copy.deepcopy(self.contract)
                changed["inventoryOnlyHuggingFaceRepositories"][0]["id"] = identity
                with self.assertRaises(alignment.ContractError):
                    alignment.validate(changed, self.manifest)

    def test_comments_cannot_supply_a_pending_hold(self):
        comment = "# Held public: szl-constellation (owner-gated visibility decision pending).\n"
        with self.assertRaises(KeepPolicyError):
            self.parse(self.policy.replace(SECTION, comment))
        self.assertEqual(self.parse(self.policy + "# grant HOLD to all repositories\n"), [HELD])

    def test_unreadable_pending_policy_fails_closed(self):
        with patch.object(Path, "read_text", side_effect=OSError("missing")):
            with self.assertRaises(KeepPolicyError):
                load_inventory_pending_public_holds(alignment.KEEP_POLICY)

    def test_pending_id_cannot_be_relabelled_fold_keep_or_org_card(self):
        for value in ("FOLD", "KEEP", "ORG_CARD", "HOLD", "HELD_PUBLIC"):
            with self.subTest(value=value):
                changed = copy.deepcopy(self.contract)
                self.row(changed)["disposition"] = value
                with self.assertRaisesRegex(alignment.ContractError, "must retain its held disposition"):
                    alignment.validate(changed, self.manifest)

    def test_other_ids_and_readme_cannot_use_the_pending_disposition(self):
        for repo_id in ("SZLHOLDINGS/ayllu", "SZLHOLDINGS/README"):
            with self.subTest(repo_id=repo_id):
                changed = copy.deepcopy(self.contract)
                self.row(changed, repo_id)["disposition"] = DISPOSITION
                with self.assertRaises(alignment.ContractError):
                    alignment.validate(changed, self.manifest)

    def test_held_row_requires_inventory_only_false_keep_and_canonical_policy(self):
        for field, value in (
            ("classification", "LABORATORY"), ("governedKeep", True),
            ("policySource", "elsewhere.yaml"),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.contract)
                self.row(changed)[field] = value
                with self.assertRaises(alignment.ContractError):
                    alignment.validate(changed, self.manifest)

    def test_held_row_is_mandatory_even_if_promoted_to_topology(self):
        for promote in (False, True):
            with self.subTest(promote=promote):
                changed = copy.deepcopy(self.contract)
                changed["inventoryOnlyHuggingFaceRepositories"].remove(self.row(changed))
                if promote:
                    changed["laboratorySurfaces"].append(HELD)
                with self.assertRaisesRegex(alignment.ContractError, "requires its inventory-only row"):
                    alignment.validate(changed, self.manifest)

    def test_pending_hold_cannot_overlap_topology_or_keep(self):
        changed = copy.deepcopy(self.contract)
        changed["laboratorySurfaces"].append(HELD)
        with self.assertRaisesRegex(alignment.ContractError, "cannot become topology or a governed keeper"):
            alignment.validate(changed, self.manifest)
        keepers = alignment.governed_keep_spaces()
        with patch.object(alignment, "governed_keep_spaces", return_value=keepers + [HELD]):
            with self.assertRaisesRegex(alignment.ContractError, "cannot become topology or a governed keeper"):
                alignment.validate(self.contract, self.manifest)

    def test_duplicate_held_rows_are_rejected(self):
        changed = copy.deepcopy(self.contract)
        changed["inventoryOnlyHuggingFaceRepositories"].append(copy.deepcopy(self.row(changed)))
        with self.assertRaises(alignment.ContractError):
            alignment.validate(changed, self.manifest)

    def test_historical_hold_binding_cannot_use_a_cleared_or_fabricated_hold(self):
        changes = [None, [], {}, {"2026-11-14": {"held": [HELD]}}]
        for executions in changes:
            with self.subTest(executions=executions):
                changed = copy.deepcopy(self.contract)
                changed["foldExecution"] = executions
                with self.assertRaises(alignment.ContractError):
                    alignment.validate(changed, self.manifest)
        for field, value in (
            ("held", ["SZLHOLDINGS/immune"]), ("held", [HELD, "SZLHOLDINGS/other"]),
            ("heldReason", "visibility approved"), ("heldReason", None),
        ):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.contract)
                changed["foldExecution"]["2026-11-15-batch2"][field] = value
                with self.assertRaises(alignment.ContractError):
                    alignment.validate(changed, self.manifest)

    def test_a_hold_does_not_ignore_absent_or_unknown_public_membership(self):
        absent = copy.deepcopy(self.manifest)
        absent["inventory"]["spaces"] = [x for x in absent["inventory"]["spaces"] if x["id"] != HELD]
        absent["counts"]["spaces"] -= 1
        with self.assertRaisesRegex(alignment.ContractError, "missing=.*szl-constellation"):
            alignment.validate(self.contract, absent)
        unknown = copy.deepcopy(self.manifest)
        unknown["inventory"]["spaces"].append({"id": "SZLHOLDINGS/unreviewed", "repoType": "space"})
        unknown["counts"]["spaces"] += 1
        with self.assertRaisesRegex(alignment.ContractError, "undeclared=.*unreviewed"):
            alignment.validate(self.contract, unknown)

    def test_all_fragments_distinguish_pending_hold_fold_and_org_card(self):
        for render in (alignment.render_github, alignment.render_huggingface, alignment.render_proof):
            with self.subTest(render=render.__name__):
                content = render(self.contract, self.evidence)
                folded = content.split("Inventory-only / FOLD", 1)[1].split("Canonical keep policy:", 1)[0]
                held = content.split("Inventory-only / HELD_PUBLIC_PENDING_OWNER_DECISION", 1)[1].split(" Reserved organization card", 1)[0]
                self.assertNotIn(HELD, folded)
                self.assertIn(HELD, held)
                self.assertIn("visibility decision pending", held)
                self.assertNotIn("SZLHOLDINGS/README", folded + held)
                self.assertNotIn("SZLHOLDINGS/immune`", content)
                self.assertIn("SZLHOLDINGS/sentra", folded)
                self.assertIn("grants no runtime qualification or visibility-write authority", content)


if __name__ == "__main__":
    unittest.main()
