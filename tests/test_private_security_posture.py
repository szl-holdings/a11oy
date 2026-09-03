#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".github" / "scripts" / "private_security_posture.py"
SPEC = importlib.util.spec_from_file_location("private_security_posture", MODULE_PATH)
assert SPEC and SPEC.loader
posture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = posture
SPEC.loader.exec_module(posture)


class FakeClient:
    def __init__(self, pages=None, requests=None):
        self.pages = pages or {}
        self.requests = requests or {}
        self.calls = []

    def paged_arrays(self, path, *, max_pages=100):
        self.calls.append(("PAGED", path, max_pages))
        value = self.pages.get(path)
        if isinstance(value, Exception):
            raise value
        for page in value or [[]]:
            yield page

    def request(self, method, path, payload=None, *, expected=(200,)):
        self.calls.append((method, path, payload, tuple(expected)))
        value = self.requests.get((method, path))
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise AssertionError(f"unexpected request: {method} {path}")
        if isinstance(value, tuple) and len(value) == 3:
            return value
        return value, {}, 200


class FamilyCollectionTests(unittest.TestCase):
    def test_dependabot_aggregates_only_allowed_severity_counts(self):
        endpoint = "/repos/szl-holdings/a11oy/dependabot/alerts?state=open"
        client = FakeClient(
            pages={
                endpoint: [
                    [
                        {
                            "number": 1,
                            "security_advisory": {
                                "severity": "critical",
                                "description": "must never persist",
                            },
                            "dependency": {"package": {"name": "private-name"}},
                        },
                        {
                            "number": 2,
                            "security_advisory": {"severity": "high"},
                        },
                    ],
                    [{"number": 3, "security_advisory": {"severity": "moderate"}}],
                ]
            }
        )
        result = posture.collect_family(client, "szl-holdings/a11oy", posture.FAMILIES[0])
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["open_count"], 3)
        self.assertEqual(result["severity"]["critical"], 1)
        self.assertEqual(result["severity"]["high"], 1)
        self.assertEqual(result["severity"]["unknown"], 1)
        self.assertEqual(result["pages_observed"], 2)
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("must never persist", serialized)
        self.assertNotIn("private-name", serialized)

    def test_code_scanning_normalizes_supported_severity_only(self):
        endpoint = "/repos/szl-holdings/a11oy/code-scanning/alerts?state=open"
        client = FakeClient(
            pages={
                endpoint: [[
                    {"rule": {"security_severity_level": "error"}},
                    {"rule": {"severity": "warning"}},
                    {"rule": {"security_severity_level": "none"}},
                ]]
            }
        )
        result = posture.collect_family(client, "szl-holdings/a11oy", posture.FAMILIES[1])
        self.assertEqual(result["severity"]["high"], 1)
        self.assertEqual(result["severity"]["warning"], 1)
        self.assertEqual(result["severity"]["unknown"], 1)

    def test_secret_scanning_counts_alerts_without_persisting_types(self):
        endpoint = "/repos/szl-holdings/a11oy/secret-scanning/alerts?state=open"
        client = FakeClient(
            pages={endpoint: [[
                {"secret_type": "github_pat", "locations_url": "sensitive"},
                {"secret_type": "generic", "locations_url": "sensitive"},
            ]]}
        )
        result = posture.collect_family(client, "szl-holdings/a11oy", posture.FAMILIES[2])
        self.assertEqual(result["open_count"], 2)
        self.assertEqual(result["severity"]["unknown"], 2)
        self.assertNotIn("secret_type", json.dumps(result))
        self.assertNotIn("locations", json.dumps(result))

    def test_each_unavailable_family_fails_closed_independently(self):
        endpoint = "/repos/szl-holdings/a11oy/code-scanning/alerts?state=open"
        client = FakeClient(pages={endpoint: posture.PostureError("HTTP_403", status=403)})
        result = posture.collect_family(client, "szl-holdings/a11oy", posture.FAMILIES[1])
        self.assertEqual(
            result,
            {
                "status": "UNAVAILABLE",
                "reason": "HTTP_403",
                "http_status": 403,
                "open_count": None,
                "severity": None,
                "pages_observed": 0,
            },
        )


class ReceiptBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.families = {
            "dependabot": {
                "status": "OBSERVED",
                "reason": None,
                "http_status": 200,
                "open_count": 2,
                "severity": {
                    "critical": 1,
                    "high": 1,
                    "medium": 0,
                    "low": 0,
                    "warning": 0,
                    "note": 0,
                    "unknown": 0,
                },
                "pages_observed": 1,
            },
            "code_scanning": {
                "status": "UNAVAILABLE",
                "reason": "HTTP_403",
                "http_status": 403,
                "open_count": None,
                "severity": None,
                "pages_observed": 0,
            },
            "secret_scanning": {
                "status": "OBSERVED",
                "reason": None,
                "http_status": 200,
                "open_count": 0,
                "severity": {name: 0 for name in posture.SEVERITIES},
                "pages_observed": 1,
            },
        }

    def build(self, observed_at="2026-09-03T00:00:00Z"):
        return posture.build_receipt(
            repository="szl-holdings/a11oy",
            revision=self.sha,
            default_branch="main",
            families=self.families,
            features={"status": "OBSERVED", "reason": None, "features": {"advanced_security": "enabled"}},
            governance={
                "default_branch": "main",
                "branch_protection": {"status": "OBSERVED", "required_check_count": 3, "required_reviews": 0},
                "rulesets": {"status": "OBSERVED", "count": 1, "identity_digest": "b" * 64},
            },
            workflows={
                "status": "OBSERVED",
                "reason": None,
                "latest_success": [
                    {
                        "name": "CodeQL",
                        "run_id": 7,
                        "conclusion": "success",
                        "head_sha": self.sha,
                        "created_at": "2026-09-02T00:00:00Z",
                    }
                ],
            },
            observed_at=observed_at,
        )

    def test_receipt_is_aggregate_secret_safe_and_attention_is_fail_closed(self):
        receipt = self.build()
        self.assertEqual(receipt["schema"], posture.SCHEMA)
        self.assertTrue(receipt["attention"]["required"])
        self.assertEqual(receipt["attention"]["open_total"], 2)
        self.assertEqual(receipt["attention"]["high_critical_total"], 2)
        self.assertEqual(receipt["attention"]["unavailable_families"], ["code_scanning"])
        self.assertEqual(posture.public_receipt_errors(receipt), [])
        self.assertFalse(receipt["privacy"]["raw_alerts_persisted"])
        self.assertFalse(receipt["privacy"]["automatic_dismissal"])

    def test_digest_is_deterministic_across_observation_times(self):
        first = self.build("2026-09-03T00:00:00Z")
        second = self.build("2026-09-03T01:00:00Z")
        self.assertEqual(first["summary_digest"], second["summary_digest"])
        self.assertNotEqual(first["observed_at"], second["observed_at"])

    def test_public_boundary_rejects_private_keys_and_credentials(self):
        for value in (
            {"path": "src/private.py"},
            {"nested": {"secret_type": "generic"}},
            {"message": "github_pat_abcdefghijklmnopqrstuvwxyz123456"},
            {"security_advisory": {"severity": "high"}},
        ):
            with self.subTest(value=value):
                self.assertTrue(posture.public_receipt_errors(value))

    def test_issue_body_contains_aggregate_counts_only(self):
        body = posture.render_issue(self.build())
        self.assertIn(posture.ISSUE_MARKER, body)
        self.assertIn("`dependabot` | OBSERVED | 2 | 1 | 1", body)
        self.assertIn("`code_scanning` | UNAVAILABLE", body)
        for forbidden in (
            "security_advisory",
            "secret_type",
            "locations_url",
            "manifest_path",
            "src/private.py",
        ):
            self.assertNotIn(forbidden, body)

    def test_report_writer_emits_canonical_public_receipt(self):
        receipt = self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            posture.write_report(str(path), receipt)
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, receipt)
        self.assertEqual(posture.public_receipt_errors(loaded), [])


class FeatureAndGovernanceTests(unittest.TestCase):
    def test_repository_features_are_status_only(self):
        client = FakeClient(
            requests={
                ("GET", "/repos/szl-holdings/a11oy"): {
                    "security_and_analysis": {
                        "advanced_security": {"status": "enabled"},
                        "secret_scanning": {"status": "enabled"},
                    }
                }
            }
        )
        result = posture.collect_repository_features(client, "szl-holdings/a11oy")
        self.assertEqual(
            result,
            {
                "status": "OBSERVED",
                "reason": None,
                "features": {"advanced_security": "enabled", "secret_scanning": "enabled"},
            },
        )

    def test_governance_persists_ruleset_identity_digest_not_rules(self):
        client = FakeClient(
            requests={
                ("GET", "/repos/szl-holdings/a11oy/branches/main/protection"): {
                    "required_status_checks": {"contexts": ["ci", "CodeQL"]},
                    "required_pull_request_reviews": {"required_approving_review_count": 0},
                },
                ("GET", "/repos/szl-holdings/a11oy/rulesets?includes_parents=true"): [
                    {
                        "id": 42,
                        "name": "protected-main",
                        "enforcement": "active",
                        "target": "branch",
                        "source_type": "Organization",
                        "rules": [{"type": "required_status_checks", "parameters": {"private": "detail"}}],
                    }
                ],
            }
        )
        result = posture.collect_governance(client, "szl-holdings/a11oy", "main")
        self.assertEqual(result["branch_protection"]["required_check_count"], 2)
        self.assertEqual(result["rulesets"]["count"], 1)
        self.assertRegex(result["rulesets"]["identity_digest"], r"^[0-9a-f]{64}$")
        serialized = json.dumps(result)
        self.assertNotIn("private", serialized)
        self.assertNotIn("required_status_checks\"", serialized)

    def test_workflow_evidence_is_bounded_and_source_identified(self):
        client = FakeClient(
            requests={
                ("GET", "/repos/szl-holdings/a11oy/actions/runs?status=success&per_page=100"): {
                    "workflow_runs": [
                        {"name": "Build", "id": 1, "head_sha": "b" * 40, "conclusion": "success"},
                        {
                            "name": "CodeQL",
                            "id": 2,
                            "head_sha": "a" * 40,
                            "conclusion": "success",
                            "created_at": "2026-09-02T00:00:00Z",
                        },
                        {
                            "name": "CodeQL",
                            "id": 3,
                            "head_sha": "c" * 40,
                            "conclusion": "success",
                            "created_at": "2026-09-01T00:00:00Z",
                        },
                    ]
                }
            }
        )
        result = posture.collect_workflow_evidence(client, "szl-holdings/a11oy")
        self.assertEqual(len(result["latest_success"]), 1)
        self.assertEqual(result["latest_success"][0]["run_id"], 2)
        self.assertEqual(result["latest_success"][0]["head_sha"], "a" * 40)


class IncidentSynchronizationTests(unittest.TestCase):
    def test_no_issue_is_created_when_every_family_is_observed_and_zero(self):
        client = FakeClient(pages={"/repos/szl-holdings/a11oy/issues?state=all": [[]]})
        receipt = {
            "attention": {"required": False},
            "families": {},
            "source_revision": "a" * 40,
            "observed_at": "2026-09-03T00:00:00Z",
            "summary_digest": "b" * 64,
        }
        self.assertEqual(posture.synchronize_issue(client, "szl-holdings/a11oy", receipt), "NOT_REQUIRED")
        self.assertFalse(any(call[0] == "POST" for call in client.calls))

    def test_attention_creates_one_deduplicated_issue(self):
        path = "/repos/szl-holdings/a11oy/issues?state=all"
        client = FakeClient(
            pages={path: [[]]},
            requests={
                ("POST", "/repos/szl-holdings/a11oy/issues"): ({"number": 7}, {}, 201)
            },
        )
        receipt = {
            "attention": {"required": True, "unavailable_families": []},
            "families": {
                "code_scanning": {
                    "status": "OBSERVED",
                    "open_count": 1,
                    "severity": {"critical": 0, "high": 1},
                }
            },
            "source_revision": "a" * 40,
            "observed_at": "2026-09-03T00:00:00Z",
            "summary_digest": "b" * 64,
        }
        self.assertEqual(posture.synchronize_issue(client, "szl-holdings/a11oy", receipt), "CREATED")
        post = [call for call in client.calls if call[0] == "POST"]
        self.assertEqual(len(post), 1)
        payload = post[0][2]
        self.assertEqual(payload["title"], posture.ISSUE_TITLE)
        self.assertEqual(payload["labels"], ["security", "automated"])
        self.assertNotIn("rule", json.dumps(payload))


class SourceAndWorkflowContractTests(unittest.TestCase):
    def test_source_contains_no_alert_dismissal_or_security_setting_mutation(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "dismiss_reason",
            "dismissed_reason",
            "resolution=",
            '"state": "dismissed"',
            "update_repo_settings",
            "enable_advanced_security",
            "disable_advanced_security",
            "delete_secret",
            "create_or_update_environment_secret",
        ):
            self.assertNotIn(forbidden, source)

    def test_workflow_is_least_privilege_source_bound_and_non_required(self):
        workflow_path = ROOT / ".github" / "workflows" / "private-security-posture.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        for required in (
            "security-events: read",
            "issues: write",
            "contents: read",
            "actions: read",
            "secrets.SZL_GITHUB_TOKEN",
            "github.token",
            "--revision \"$GITHUB_SHA\"",
            "--apply",
            "retention-days: 90",
            "private-security-posture.json",
        ):
            self.assertIn(required, workflow)
        for forbidden in (
            "contents: write",
            "pull-requests: write",
            "administration: write",
            "secrets: write",
            "packages: write",
            "actions: write",
            "branches-ignore",
        ):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
