#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Regression tests for shared-peer identity and payload resolution."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "resolve-shared-peer-ref.py"
WORKFLOW = HERE / "workflows" / "shared-file-drift.yml"
PEER_REPOSITORY = "szl-holdings/killinchu"
CURRENT_REPOSITORY = "szl-holdings/a11oy"
PEER_PR = 234
CURRENT_PR = 1227
PEER_HEAD = "1231821569182b5f1e7eecce5dd531e9f98ccf63"
PEER_MAIN = "9fb553e483cd887f57799cf264424227d68db155"
PAYLOAD = "ab" * 32
LEGACY_MARKER = f"Shared-source-peer: {PEER_REPOSITORY}#{PEER_PR}@{PEER_HEAD}"
CONTENT_MARKERS = (
    f"Shared-source-peer: {PEER_REPOSITORY}#{PEER_PR}\n"
    f"Shared-source-payload: sha256:{PAYLOAD}"
)
RECIPROCAL_MARKERS = (
    f"Shared-source-peer: {CURRENT_REPOSITORY}#{CURRENT_PR}\n"
    f"Shared-source-payload: sha256:{PAYLOAD}"
)


class ResolverTests(unittest.TestCase):
    def run_event(self, event_name: str, body: str | None = None) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event_path = root / "event.json"
            output_path = root / "output.txt"
            event_path.write_text(json.dumps({"pull_request": {"body": body}}), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--event-name",
                    event_name,
                    "--event-path",
                    str(event_path),
                    "--output",
                    str(output_path),
                    "--expected-repository",
                    PEER_REPOSITORY,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return result, self.read_outputs(output_path)

    def run_peer(self, peer: dict, **overrides: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            peer_path = root / "peer.json"
            output_path = root / "output.txt"
            peer_path.write_text(json.dumps(peer), encoding="utf-8")
            values = {
                "current_repository": CURRENT_REPOSITORY,
                "current_pull_request": str(CURRENT_PR),
                "expected_payload_sha256": PAYLOAD,
                "peer_main_ref": PEER_MAIN,
            }
            values.update(overrides)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--peer-pr-path",
                    str(peer_path),
                    "--output",
                    str(output_path),
                    "--expected-repository",
                    PEER_REPOSITORY,
                    "--current-repository",
                    values["current_repository"],
                    "--current-pull-request",
                    values["current_pull_request"],
                    "--expected-payload-sha256",
                    values["expected_payload_sha256"],
                    "--peer-main-ref",
                    values["peer_main_ref"],
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return result, self.read_outputs(output_path)

    @staticmethod
    def read_outputs(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                values[key] = value
        return values

    @staticmethod
    def peer_payload(**updates: object) -> dict:
        peer = {
            "number": PEER_PR,
            "state": "open",
            "merged": False,
            "merged_at": None,
            "body": RECIPROCAL_MARKERS,
            "base": {"ref": "main", "repo": {"full_name": PEER_REPOSITORY}},
            "head": {"sha": PEER_HEAD, "repo": {"full_name": PEER_REPOSITORY}},
        }
        peer.update(updates)
        return peer

    def test_non_pr_always_uses_main(self) -> None:
        result, values = self.run_event("push", CONTENT_MARKERS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["ref"], "main")
        self.assertEqual(values["source"], "sibling-main")

    def test_pr_without_marker_uses_main(self) -> None:
        result, values = self.run_event("pull_request", "ordinary pull request")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["ref"], "main")

    def test_legacy_exact_head_marker_remains_supported(self) -> None:
        result, values = self.run_event("pull_request", LEGACY_MARKER)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["source"], "legacy-pinned-peer-pr")
        self.assertEqual(values["ref"], PEER_HEAD)

    def test_content_marker_binds_stable_peer_and_payload(self) -> None:
        result, values = self.run_event("pull_request", CONTENT_MARKERS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["source"], "content-bound-peer-pr")
        self.assertEqual(values["ref"], "")
        self.assertEqual(values["payload_sha256"], PAYLOAD)

    def test_duplicate_or_incomplete_markers_fail_closed(self) -> None:
        cases = [
            CONTENT_MARKERS + "\n" + f"Shared-source-peer: {PEER_REPOSITORY}#999",
            f"Shared-source-peer: {PEER_REPOSITORY}#{PEER_PR}",
            f"Shared-source-payload: sha256:{PAYLOAD}",
            LEGACY_MARKER + "\n" + f"Shared-source-payload: sha256:{PAYLOAD}",
        ]
        for body in cases:
            with self.subTest(body=body):
                result, values = self.run_event("pull_request", body)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(values, {})

    def test_malformed_repository_or_digest_fails_closed(self) -> None:
        cases = [
            CONTENT_MARKERS.replace(PEER_REPOSITORY, "attacker/killinchu"),
            CONTENT_MARKERS.replace(PAYLOAD, PAYLOAD.upper()),
            f"Shared-source-peer: {PEER_REPOSITORY}#{PEER_PR}@branch-name",
        ]
        for body in cases:
            with self.subTest(body=body):
                result, values = self.run_event("pull_request", body)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(values, {})

    def test_open_peer_resolves_exact_current_head(self) -> None:
        result, values = self.run_peer(self.peer_payload())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["source"], "content-bound-peer-pr")
        self.assertEqual(values["ref"], PEER_HEAD)

    def test_merged_peer_resolves_exact_current_main_for_second_half(self) -> None:
        result, values = self.run_peer(
            self.peer_payload(state="closed", merged=True, merged_at="2026-08-01T22:00:00Z")
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(values["source"], "content-bound-peer-main")
        self.assertEqual(values["ref"], PEER_MAIN)

    def test_peer_fork_wrong_base_and_unmerged_close_fail(self) -> None:
        cases = [
            self.peer_payload(head={"sha": PEER_HEAD, "repo": {"full_name": "attacker/killinchu"}}),
            self.peer_payload(base={"ref": "dev", "repo": {"full_name": PEER_REPOSITORY}}),
            self.peer_payload(state="closed", merged=False, merged_at=None),
        ]
        for peer in cases:
            with self.subTest(peer=peer):
                result, values = self.run_peer(peer)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(values, {})

    def test_peer_requires_exact_reciprocal_identity_and_digest(self) -> None:
        cases = [
            self.peer_payload(body=RECIPROCAL_MARKERS.replace(f"#{CURRENT_PR}", "#999")),
            self.peer_payload(body=RECIPROCAL_MARKERS.replace(PAYLOAD, "34" * 32)),
            self.peer_payload(body="ordinary pull request"),
        ]
        for peer in cases:
            with self.subTest(peer=peer):
                result, values = self.run_peer(peer)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(values, {})


class WorkflowTests(unittest.TestCase):
    def test_edited_pull_request_rechecks_peer_markers(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("types: [opened, synchronize, reopened, edited]", workflow)

    def test_workflow_keeps_least_privilege_and_expected_peer(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("--expected-repository=szl-holdings/killinchu", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_both_peer_modes_are_verified_before_checkout(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        legacy = workflow.index("- name: Verify legacy exact-head peer")
        content = workflow.index("- name: Resolve content-bound peer")
        checkout = workflow.index("- name: Checkout killinchu (verified sibling)")
        self.assertLess(legacy, checkout)
        self.assertLess(content, checkout)

    def test_content_payload_is_validated_before_full_drift_check(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        payload = workflow.index("- name: Validate content-addressed shared payload")
        drift = workflow.index("- name: Compare shared source files")
        self.assertLess(payload, drift)
        self.assertIn("--expected-manifest-sha256", workflow)

    def test_checkout_uses_only_resolved_exact_ref(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ref: ${{ steps.content_peer.outputs.ref || steps.peer.outputs.ref }}", workflow)
        self.assertNotIn("ref: ${{ steps.peer.outputs.pull_request }}", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
