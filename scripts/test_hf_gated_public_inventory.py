#!/usr/bin/env python3
"""Offline public-inventory access-boundary regressions; no credentials or network."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("gated_inventory_audit", HERE / "audit_huggingface_ecosystem.py")
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
NOW = datetime(2026, 9, 5, 1, 0, tzinfo=timezone.utc)


def fixture(gated="auto"):
    return {"id": "SZLHOLDINGS/test-gated-model", "sha": "a" * 40,
            "lastModified": "2026-09-04T00:00:00Z", "private": False,
            "gated": gated, "tags": ["license:apache-2.0"],
            "cardData": {"license": "apache-2.0", "tags": ["receipt"]}}


def manifest(item):
    return {"inventory": {"models": [item], "datasets": [], "spaces": []}}


class GatedPublicInventoryTests(unittest.TestCase):
    def summarize(self, value=None):
        with patch.object(audit, "fetch_card_markdown", side_effect=AssertionError("protected download attempted")):
            return audit.item_summary(value or fixture(), "model")

    def test_all_supported_gate_modes_avoid_protected_file_requests(self):
        for mode, expected in (("auto", "auto"), ("manual", "manual"), (True, "enabled")):
            with self.subTest(mode=mode):
                result = self.summarize(fixture(mode))
                self.assertIsNone(result["cardSemanticSha256"])
                self.assertTrue(result["gated"])
                evidence = result["cardObservation"]
                self.assertEqual(evidence["state"], "ACCESS_RESTRICTED")
                self.assertEqual(evidence["scope"], "PUBLIC_METADATA_ONLY")
                self.assertEqual(evidence["gateMode"], expected)
                audit.validate_generated_revision_evidence(manifest(result), observed_at=NOW)

    def test_public_card_keeps_exact_revision_markdown_digest(self):
        value = fixture(False)
        with patch.object(audit, "fetch_card_markdown", return_value="# Real public card\n") as fetch:
            result = audit.item_summary(value, "model")
        fetch.assert_called_once_with(value["id"], "model", "a" * 40)
        self.assertEqual(result["cardSemanticSha256"], audit.card_semantic_sha256("# Real public card\n"))
        self.assertNotIn("cardObservation", result)

    def test_unexpected_ungated_auth_failure_remains_blocking(self):
        error = urllib.error.HTTPError("https://huggingface.co/test", 401, "Unauthorized", {}, None)
        with patch.object(audit, "fetch_card_markdown", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError):
                audit.item_summary(fixture(False), "model")

    def test_missing_public_metadata_is_null_not_an_empty_readme(self):
        value = fixture()
        value.pop("cardData")
        result = self.summarize(value)
        self.assertIsNone(result["cardObservation"]["metadata"])
        self.assertIsNone(result["cardSemanticSha256"])
        self.assertNotEqual(result["cardObservation"]["metadataSha256"], audit.card_semantic_sha256(""))

    def test_metadata_is_copied_and_committed_not_mutable_provider_alias(self):
        value = fixture()
        result = self.summarize(value)
        value["cardData"]["tags"].append("unreviewed")
        self.assertEqual(result["cardObservation"]["metadata"]["tags"], ["receipt"])
        audit.validate_generated_revision_evidence(manifest(result), observed_at=NOW)

    def test_forged_restricted_evidence_cannot_pass_validation(self):
        valid = self.summarize()
        changes = [
            lambda v: v.update(cardSemanticSha256="c" * 64),
            lambda v: v.update(gated=False),
            lambda v: v.pop("cardObservation"),
            lambda v: v["cardObservation"].update(state="LIVE"),
            lambda v: v["cardObservation"].update(scope="README_BYTES"),
            lambda v: v["cardObservation"].update(gateMode="unknown"),
            lambda v: v["cardObservation"].update(metadataSha256="0" * 64),
            lambda v: v["cardObservation"].update(metadata={"different": True}),
            lambda v: v["cardObservation"].update(extra="unreviewed"),
        ]
        for index, mutate in enumerate(changes):
            invalid = copy.deepcopy(valid)
            mutate(invalid)
            with self.subTest(case=index), self.assertRaises(ValueError):
                audit.validate_generated_revision_evidence(manifest(invalid), observed_at=NOW)

    def test_unknown_gate_states_and_invalid_metadata_fail_closed(self):
        for gate in ("false", "unexpected", 1, [], {}):
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                self.summarize(fixture(gate))
        for metadata in ([], "not an object", {"number": float("nan")}, {"text": "x" * 262145}):
            value = fixture()
            value["cardData"] = metadata
            with self.subTest(metadata_type=type(metadata).__name__), self.assertRaises(ValueError):
                self.summarize(value)

    def test_restricted_revision_advance_requires_review_without_historical_download(self):
        stored = self.summarize()
        newer = copy.deepcopy(stored)
        newer.update(sha="b" * 40, lastModified="2026-09-05T00:00:00Z")
        with patch.object(audit, "fetch_revision", side_effect=AssertionError("historical request attempted")):
            with self.assertRaisesRegex(ValueError, "restricted revision changed"):
                audit.validate_snapshot_revisions(manifest(stored), manifest(newer), observed_at=NOW, now=NOW)
        self.assertNotEqual(audit.semantic_manifest(manifest(stored)), audit.semantic_manifest(manifest(newer)))

    def test_same_restricted_revision_remains_public_metadata_only(self):
        stored = self.summarize()
        with patch.object(audit, "fetch_revision", side_effect=AssertionError("request attempted")):
            audit.validate_snapshot_revisions(manifest(stored), manifest(stored), observed_at=NOW, now=NOW)

    def test_public_semantic_revision_behavior_is_preserved(self):
        value = fixture(False)
        with patch.object(audit, "fetch_card_markdown", return_value="# Card"):
            first = audit.item_summary(value, "model")
        newer = {**first, "sha": "b" * 40, "lastModified": "2026-09-05T00:00:00Z"}
        self.assertEqual(audit.semantic_manifest(manifest(first)), audit.semantic_manifest(manifest(newer)))

    def test_gate_and_metadata_changes_are_not_semantically_ignored(self):
        first = self.summarize()
        for changed in (fixture("manual"), {**fixture(), "cardData": {"license": "other"}}):
            with self.subTest(changed=changed):
                second = self.summarize(changed)
                self.assertNotEqual(audit.semantic_manifest(manifest(first)), audit.semantic_manifest(manifest(second)))

    def test_gate_policy_transition_and_future_timestamps_still_fail(self):
        stored = self.summarize()
        with patch.object(audit, "fetch_card_markdown", return_value="# Card"):
            ungated = audit.item_summary(fixture(False), "model")
        with self.assertRaisesRegex(ValueError, "gate policy changed"):
            audit.validate_snapshot_revisions(manifest(stored), manifest(ungated), observed_at=NOW, now=NOW)
        future = {**stored, "lastModified": "2026-09-06T00:00:00Z"}
        with self.assertRaises(ValueError):
            audit.validate_generated_revision_evidence(manifest(future), observed_at=NOW)

    def test_full_check_accepts_only_unchanged_restricted_metadata(self):
        current = fixture()
        with patch.object(audit, "api_items", side_effect=lambda kind: [current] if kind == "models" else []):
            with patch.object(audit, "fetch_card_markdown", side_effect=AssertionError("protected request")):
                snapshot = audit.build_manifest(observed_at=NOW.isoformat())
                self.assertEqual(snapshot["schemaVersion"], 2)
                self.assertFalse(snapshot["inventoryScope"]["authenticated"])
                self.assertIn("ACCESS_RESTRICTED", snapshot["inventoryScope"]["cardEvidenceBoundary"])
                with tempfile.TemporaryDirectory() as folder:
                    target = Path(folder) / "manifest.json"
                    target.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
                    with patch.object(sys, "argv", ["audit", "--check", "--output", str(target)]), redirect_stdout(io.StringIO()):
                        self.assertEqual(audit.main(), 0)
                        current["cardData"] = {"license": "other"}
                        self.assertEqual(audit.main(), 1)

    def test_schema_has_restricted_conditional_without_global_null_exemption(self):
        schema = json.loads((HERE.parent / "docs/huggingface-ecosystem-manifest.schema.json").read_text())
        self.assertEqual(schema["properties"]["schemaVersion"], {"const": 2})
        rule = schema["$defs"]["items"]["items"]["allOf"][0]
        self.assertEqual(rule["if"]["properties"]["gated"], {"const": True})
        self.assertIn("cardObservation", rule["then"]["required"])
        self.assertEqual(rule["else"]["properties"]["cardSemanticSha256"], {"type": "string"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
