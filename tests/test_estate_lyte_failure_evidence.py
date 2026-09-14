"""Offline contracts for retaining native Lyte failure evidence.

SPDX-License-Identifier: Apache-2.0
These inspect real workflow source. They do not prove a provider publication,
validate uploaded receipt contents, or authorize any dispatch.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HF_PATH = ROOT / ".github/workflows/hf-sync.yml"
ESTATE_PATH = ROOT / ".github/workflows/estate-release-train.yml"
UPLOAD = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
TITLE = "Preserve source-bound Lyte failure diagnostics"
CONDITION = "${{ always() && hashFiles('hf-lyte-enterprise-manifest.failed.json') != '' }}"
FILES = ("hf-lyte-enterprise-manifest.failed.json", "hf-lyte-enterprise-receipt.json")


def step(document, name):
    marker = "      - name: " + name + "\n"
    if document.count(marker) != 1:
        raise ValueError("expected exactly one named workflow step")
    tail = document.split(marker, 1)[1]
    lines = []
    for line in tail.splitlines():
        if line.strip() and len(line) - len(line.lstrip()) <= 6:
            break
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def validate_retention(document):
    """Keep this tiny artifact contract independent of the production checker."""
    observed = step(document, TITLE)
    expected = (
        "        if: " + CONDITION + "\n"
        "        uses: " + UPLOAD + " # v7.0.1\n"
        "        with:\n"
        "          name: hf-lyte-failure-${{ github.run_id }}-${{ github.run_attempt }}\n"
        "          path: |\n"
        "            " + FILES[0] + "\n"
        "            " + FILES[1] + "\n"
        "          if-no-files-found: error\n"
        "          retention-days: 90\n"
    )
    if observed != expected:
        raise ValueError("native diagnostics artifact contract changed")
    return observed


class LyteFailureEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hf = HF_PATH.read_text(encoding="utf-8")
        cls.estate = ESTATE_PATH.read_text(encoding="utf-8")

    def test_current_native_retention_contract(self):
        validate_retention(self.hf)

    def test_omitted_or_duplicated_step_is_rejected(self):
        marker = "      - name: " + TITLE + "\n"
        block = marker + step(self.hf, TITLE)
        for document in (self.hf.replace(block, "", 1), self.hf + "\n" + block):
            with self.subTest(length=len(document)), self.assertRaises(ValueError):
                validate_retention(document)

    def test_weakened_or_broadened_artifact_contract_is_rejected(self):
        changes = (
            ("if: " + CONDITION, "if: success()"),
            (UPLOAD, "actions/upload-artifact@main"),
            ("hf-lyte-failure-${{ github.run_id }}-${{ github.run_attempt }}", "hf-lyte-failure-latest"),
            ("            " + FILES[0] + "\n", ""),
            ("            " + FILES[1] + "\n", ""),
            ("            " + FILES[0], "            **/*.json"),
            ("            " + FILES[1], "            .env"),
            ("if-no-files-found: error", "if-no-files-found: ignore"),
            ("retention-days: 90", "retention-days: 1"),
        )
        original = step(self.hf, TITLE)
        for before, after in changes:
            with self.subTest(before=before):
                self.assertEqual(original.count(before), 1)
                changed = self.hf.replace(original, original.replace(before, after, 1), 1)
                with self.assertRaises(ValueError):
                    validate_retention(changed)

    def test_existing_aggregate_archive_scope_is_unchanged(self):
        aggregate = step(self.hf, "Upload immutable vertical publication receipt")
        self.assertIn("name: hf-vertical-flagships-${{ github.run_id }}-${{ github.run_attempt }}", aggregate)
        self.assertIn("path: hf-vertical-flagships-receipt.json\n", aggregate)
        self.assertIn("if-no-files-found: error", aggregate)
        self.assertIn("retention-days: 180", aggregate)
        for path in FILES:
            self.assertNotIn(path, aggregate)

    def test_explicit_publisher_failure_is_still_enforced(self):
        job = self.hf.split("  publish-vertical-flagships:\n", 1)[1].split("\n  readiness-verdict:\n", 1)[0]
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("|| true", job)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.publish_vertical_flagships", job)
        gate = step(self.hf, "Enforce complete explicitly requested vertical publication")
        self.assertIn("if: always()", gate)
        self.assertIn("VERTICAL_PUBLISH_OUTCOME: ${{ steps.vertical_publish.outcome }}", gate)
        self.assertIn("run: python scripts/estate_child_completion.py", gate)
        self.assertLess(self.hf.index("name: Enforce complete explicitly"), self.hf.index("name: " + TITLE))

    def test_native_offline_step_executes_new_contract(self):
        block = step(self.estate, "Prove the release-vector controller offline")
        self.assertIn("set -euo pipefail", block)
        self.assertEqual(block.count("python tests/test_estate_lyte_failure_evidence.py"), 1)
        self.assertIn("python tests/test_estate_repair_plan_authority.py", block)
        self.assertIn("python tests/test_estate_child_completion.py", block)
        self.assertNotIn("continue-on-error", block)
        self.assertNotIn("|| true", block)

    def test_native_pr_trigger_includes_contract_and_both_workflows(self):
        trigger = self.estate.split("  pull_request:\n", 1)[1].split("  workflow_run:\n", 1)[0]
        for path in ("tests/test_estate_lyte_failure_evidence.py", ".github/workflows/hf-sync.yml", ".github/workflows/estate-release-train.yml"):
            with self.subTest(path=path):
                self.assertEqual(trigger.count("      - " + path + "\n"), 1)

    def test_source_ownership_and_plan_gates_are_retained(self):
        self.assertIn("--expected-sha \"$GITHUB_SHA\"", self.hf)
        self.assertIn("--require-vertical", step(self.hf, "Require the approved plan for the actual vertical source"))
        self.assertIn("publish_vertical_flagships:", self.hf)
        self.assertIn("default: false", self.hf.split("publish_vertical_flagships:", 1)[1].split("vertical_plan_json:", 1)[0])
        self.assertIn("group: sync-relock-canonical-a11oy", self.hf)
        self.assertIn("cancel-in-progress: false", self.hf)


if __name__ == "__main__":
    unittest.main()
