#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""hf-sync.yml must never again gate deploy on an exact identity (stdlib only).

Incident 2026-10-04..06: the Space crash-looped for about 41 hours on "GDW
SQLite integrity check failed: Page 362/363 never used" (SQLite on the bucket
FUSE mount) while hf-sync failed 47+ consecutive main pushes. Every fix commit
had to re-pin its own parent SHA, a diagnostic run id, an artifact id/digest
and an exact 72/224 namespace, so each later merge livelocked deploy again.

This guard forbids, outside action ``uses:`` pins:
  * any 40-hex commit literal and any 9+ digit run/artifact id literal,
  * ``run_attempt == 1`` (a transient failure must not burn the commit),
  * any reference to the retired incident jobs,
and requires the deploy job's needs chain to reach source-admission through
preflight only, with no pause/restart proof or variable write after deploy.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"
DRILL = ROOT / ".github" / "workflows" / "restart-drill.yml"

RETIRED_JOBS = (
    "recovery-reconciliation",
    "manual-prerequisites",
    "durable-acquisition",
    "resume-paused-space",
    "publish-finance-projection",
)
POST_DEPLOY_JOBS = (
    "runtime-config",
    "readiness-verdict",
    "relock",
    "post-deployment-parity",
    "terminal-source-authorization",
)
POST_DEPLOY_FORBIDDEN = (
    "restart_space",
    "restart-space",
    "pause_space",
    "add_space_variable",
    "prove_hf_series_a_restart.py",
    "prove_hf_gdw_runtime.py",
)
HEX40 = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")
LONG_ID = re.compile(r"(?<![0-9A-Za-z_])\d{9,}(?![0-9A-Za-z_])")
# The verdict gate may run post-deploy only in its no-write validation mode.
VERDICT_PUBLISH = re.compile(r"publish_readiness_verdict\.py(?!\s+--validate-only\b)")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*\S+@[0-9a-f]{40}(?:\s+#.*)?$")


def exact_identity_violations(text: str) -> list[str]:
    """Return every exact SHA/run/artifact literal outside a ``uses:`` pin."""
    violations = []
    for number, line in enumerate(text.splitlines(), start=1):
        if USES_LINE.match(line):
            continue
        for pattern, label in ((HEX40, "40-hex literal"), (LONG_ID, "run/artifact id literal")):
            for match in pattern.finditer(line):
                violations.append(f"line {number}: {label} {match.group()!r}")
    return violations


def job_blocks(text: str) -> dict[str, str]:
    """Split the top-level jobs map into raw job bodies (two-space job keys)."""
    body = text.split("\njobs:\n", 1)[1]
    starts = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", body))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        if match.group(1) in blocks:
            raise AssertionError("duplicate job: " + match.group(1))
        blocks[match.group(1)] = body[match.start():end]
    return blocks


def job_needs(block: str) -> list[str]:
    match = re.search(r"(?m)^    needs:\s*(.+?)\s*$", block)
    if match is None:
        return []
    value = match.group(1)
    if value.startswith("["):
        return [item.strip() for item in value.strip("[]").split(",") if item.strip()]
    return [value]


def ancestors(blocks: dict[str, str], name: str) -> set[str]:
    pending, seen = list(job_needs(blocks[name])), set()
    while pending:
        parent = pending.pop()
        if parent in seen:
            continue
        if parent not in blocks:
            raise AssertionError(f"{name} needs a missing job: {parent}")
        seen.add(parent)
        pending.extend(job_needs(blocks[parent]))
    return seen


def contract_violations(text: str) -> list[str]:
    violations = exact_identity_violations(text)
    if "run_attempt == 1" in text:
        violations.append("first-attempt gate run_attempt == 1")
    for name in RETIRED_JOBS:
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", text):
            violations.append("retired job reference: " + name)
    blocks = job_blocks(text)
    for required in ("source-admission", "preflight", "deploy"):
        if required not in blocks:
            violations.append("missing job: " + required)
    if not violations:
        if job_needs(blocks["deploy"]) != ["source-admission", "preflight"]:
            violations.append("deploy must need exactly source-admission and preflight")
        if job_needs(blocks["preflight"]) != ["source-admission"]:
            violations.append("preflight must need exactly source-admission")
        if ancestors(blocks, "deploy") != {"source-admission", "preflight"}:
            violations.append("deploy ancestry must be source-admission -> preflight")
        for name in POST_DEPLOY_JOBS:
            if name not in blocks:
                violations.append("missing post-deploy job: " + name)
                continue
            if "deploy" not in ancestors(blocks, name):
                violations.append("post-deploy job does not follow deploy: " + name)
            for token in POST_DEPLOY_FORBIDDEN:
                if token in blocks[name]:
                    violations.append(f"post-deploy restart or variable write in {name}: {token}")
            if VERDICT_PUBLISH.search(blocks[name]):
                violations.append(f"post-deploy verdict variable write in {name}")
    if re.search(r"(?m)^\s*exit 3\s*$", text):
        violations.append("superseded run exits red (exit 3)")
    return violations


class HfSyncNoExactPinsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_actual_workflow_has_no_exact_identity_gate(self) -> None:
        self.assertEqual(contract_violations(self.text), [])

    def test_only_uses_lines_carry_commit_pins(self) -> None:
        pinned = [line for line in self.text.splitlines() if HEX40.search(line)]
        self.assertTrue(pinned)
        for line in pinned:
            self.assertRegex(line, USES_LINE)
        self.assertIn(
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@fc71ae973a0f31b8e9ee793fc8545a354448d451",
            self.text,
        )

    def test_deploy_reaches_admission_without_recovery_jobs(self) -> None:
        blocks = job_blocks(self.text)
        self.assertEqual(ancestors(blocks, "deploy"), {"source-admission", "preflight"})
        self.assertFalse(set(RETIRED_JOBS) & set(blocks))
        for name in POST_DEPLOY_JOBS:
            with self.subTest(job=name):
                self.assertIn("deploy", ancestors(blocks, name))
                self.assertIn("source-admission", ancestors(blocks, name))

    def test_restart_proofs_live_only_in_the_manual_drill(self) -> None:
        for script in ("prove_hf_series_a_restart.py", "prove_hf_gdw_runtime.py"):
            self.assertNotIn(script, self.text)
        drill = DRILL.read_text(encoding="utf-8")
        trigger = drill.split("\non:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(trigger.strip(), "workflow_dispatch: {}")
        for script in ("prove_hf_series_a_restart.py", "prove_hf_gdw_runtime.py"):
            self.assertEqual(drill.count(script), 1)
        self.assertEqual(exact_identity_violations(drill), [])
        self.assertNotIn("run_attempt == 1", drill)

    def test_negative_fixtures_are_detected(self) -> None:
        # The guard must reject each historical livelock shape, so it cannot
        # rot into an always-pass check.
        sha = "f4a1a45f" + "0" * 32
        anchor = '          python3 -B scripts/hf_exact_main_ownership.py \\\n'
        self.assertIn(anchor, self.text)
        preflight_if = "    if: ${{ needs.source-admission.result == 'success' && needs.source-admission.outputs.publish == 'true' }}\n"
        self.assertIn(preflight_if, self.text)
        cases = {
            "40-hex literal": self.text.replace(anchor, f"          test \"$PARENT\" = {sha}\n" + anchor, 1),
            "run/artifact id literal": self.text.replace(anchor, "          echo diagnostic-run=37406817882\n" + anchor, 1),
            "40-hex literal in a ref": self.text.replace(
                "          ref: ${{ github.sha }}\n", f"          ref: {sha}\n", 1),
            "run_attempt": self.text.replace(
                preflight_if,
                "    if: ${{ github.run_attempt == 1 && needs.source-admission.result == 'success' && needs.source-admission.outputs.publish == 'true' }}\n", 1),
            "retired job": self.text.replace(
                "    needs: [source-admission, preflight]\n",
                "    needs: [source-admission, preflight, manual-prerequisites]\n", 1),
            "deploy ancestry": self.text.replace(
                "    needs: [source-admission, preflight]\n", "    needs: preflight\n", 1),
            "post-deploy restart": self.text.replace(
                "            --retry-seconds 10\n",
                "            --retry-seconds 10\n          python -B scripts/prove_hf_series_a_restart.py --source-sha \"$GITHUB_SHA\"\n", 1),
            "verdict variable write": self.text.replace(
                "          --validate-only\n", "          --repo-id \"$CANONICAL_SPACE\"\n", 1),
            "exit 3": self.text.replace(
                "            exit 0\n          fi\n          echo 'Canonical A11oy is source-bound",
                "            exit 3\n          fi\n          echo 'Canonical A11oy is source-bound", 1),
        }
        for label, changed in cases.items():
            with self.subTest(case=label):
                self.assertNotEqual(changed, self.text)
                self.assertTrue(contract_violations(changed))

    def test_uses_pins_and_short_numbers_are_allowed(self) -> None:
        sample = (
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
            "    uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@fc71ae973a0f31b8e9ee793fc8545a354448d451\n"
            "      wait-running: 1200\n"
            "          retention-days: 90\n"
        )
        self.assertEqual(exact_identity_violations(sample), [])
        self.assertTrue(exact_identity_violations(
            "      # pinned diagnostic 3d3c42e5aac5ba805825da76410c181273ba90b1\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
