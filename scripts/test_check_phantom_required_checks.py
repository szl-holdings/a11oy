#!/usr/bin/env python3
# =============================================================================
# Self-test for check_phantom_required_checks.py — proves the guard actually
# catches the task #313 phantom (`check` required but never emitted on PRs) and
# does NOT false-flag the healthy state. Stdlib unittest, no network. Guards the
# guard so a future edit can't silently neuter it.
#
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_phantom_required_checks import (  # noqa: E402
    extract_required_from_rules,
    extract_required_from_classic,
    extract_reported_from_pr,
    find_phantoms,
)

# Effective rules union as returned by /repos/<repo>/rules/branches/main.
RULES = [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {"context": "docs / Markdown lint"},
                {"context": "secrets / TruffleHog Secret Scan"},
                # The task #313 phantom: required, but no workflow emits a bare
                # `check` context on pull_request runs.
                {"context": "check"},
            ]
        },
    },
]

CLASSIC = {"contexts": ["legacy-context"], "checks": [{"context": "docs / Markdown lint", "app_id": 1}]}


def _pr_payload(contexts):
    """Build a single-PR GraphQL payload from (name, isRequired) tuples."""
    nodes = [{"__typename": "CheckRun", "name": n, "isRequired": r} for n, r in contexts]
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "commits": {
                        "nodes": [{"commit": {"statusCheckRollup": {"contexts": {"nodes": nodes}}}}]
                    }
                }
            }
        }
    }


class ExtractRequiredTests(unittest.TestCase):
    def test_rules_union_includes_phantom(self):
        req = extract_required_from_rules(RULES)
        self.assertEqual(req, {"docs / Markdown lint", "secrets / TruffleHog Secret Scan", "check"})

    def test_rules_string_form(self):
        self.assertEqual(
            extract_required_from_rules(
                [{"type": "required_status_checks", "parameters": {"required_status_checks": ["a", "b"]}}]
            ),
            {"a", "b"},
        )

    def test_rules_ignores_non_list(self):
        self.assertEqual(extract_required_from_rules(None), set())
        self.assertEqual(extract_required_from_rules({}), set())

    def test_classic_contexts_and_checks(self):
        self.assertEqual(extract_required_from_classic(CLASSIC), {"legacy-context", "docs / Markdown lint"})

    def test_classic_none_tolerated(self):
        self.assertEqual(extract_required_from_classic(None), set())


class ExtractReportedTests(unittest.TestCase):
    def test_reads_reported_and_required_observed(self):
        payload = _pr_payload([("docs / Markdown lint", True), ("Trivy", False)])
        reported, req_obs, had = extract_reported_from_pr(payload)
        self.assertTrue(had)
        self.assertEqual(reported, {"docs / Markdown lint", "Trivy"})
        self.assertEqual(req_obs, {"docs / Markdown lint"})

    def test_no_rollup(self):
        payload = {"data": {"repository": {"pullRequest": {"commits": {"nodes": [{"commit": {"statusCheckRollup": None}}]}}}}}
        reported, req_obs, had = extract_reported_from_pr(payload)
        self.assertFalse(had)
        self.assertEqual(reported, set())

    def test_missing_pr(self):
        reported, req_obs, had = extract_reported_from_pr({"data": {"repository": {"pullRequest": None}}})
        self.assertFalse(had)


class FindPhantomTests(unittest.TestCase):
    def test_catches_phantom_check(self):
        # End-to-end on the fixtures: `check` is required but only `check / doctrine`
        # (a DIFFERENT context) and the docs/secrets contexts ever report.
        required = extract_required_from_rules(RULES)
        reported = set()
        for ctxs in (
            [("docs / Markdown lint", True), ("check / doctrine", False), ("Trivy", False)],
            [("secrets / TruffleHog Secret Scan", True), ("docs / Markdown lint", True)],
        ):
            r, _o, _h = extract_reported_from_pr(_pr_payload(ctxs))
            reported |= r
        self.assertEqual(find_phantoms(required, reported), ["check"])

    def test_healthy_state_no_phantom(self):
        required = {"docs / Markdown lint", "secrets / TruffleHog Secret Scan"}
        reported = {"docs / Markdown lint", "secrets / TruffleHog Secret Scan", "Trivy", "CodeQL"}
        self.assertEqual(find_phantoms(required, reported), [])

    def test_check_doctrine_is_not_check(self):
        # Regression: a bare `check` requirement is NOT satisfied by `check / doctrine`.
        self.assertEqual(find_phantoms({"check"}, {"check / doctrine"}), ["check"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
