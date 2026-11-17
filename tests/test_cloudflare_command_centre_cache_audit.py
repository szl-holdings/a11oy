#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Network-free privacy, ownership and incomplete-observation contracts."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_cloudflare_command_centre_cache as audit

ZID = "a" * 32
AID = "b" * 32
RULE_ID = "c" * 32
TOKEN = "synthetic-cloudflare-token-never-real"
PRIVATE = "private-value-must-not-be-retained"
ZONE_PATH = "/zones?name=a-11-oy.com&status=active&per_page=50&page=1"
BASE = "/zones/" + ZID


def envelope(result, info=None):
    out = {"success": True, "result": result}
    if info is not None:
        out["result_info"] = info
    return out, None


class World:
    def __init__(self):
        source = (audit.ROOT / "cloudflare/a11oy-product-root-worker.mjs").read_bytes()
        self.worker = "szl-a11oy-product-edge-v4-" + hashlib.sha256(source).hexdigest()[:16]
        self.calls = []
        self.responses = {
            ZONE_PATH: envelope([{"id": ZID, "name": audit.ZONE, "status": "active",
                                  "account": {"id": AID, "name": PRIVATE}}],
                                {"page": 1, "total_pages": 1, "total_count": 1, "count": 1}),
            BASE + "/workers/routes": envelope([
                {"id": RULE_ID, "pattern": audit.ZONE + "/*", "script": self.worker},
                {"id": "d" * 32, "pattern": "www." + audit.ZONE + "/*", "script": self.worker},
            ]),
            BASE + "/rulesets?per_page=50": envelope([
                {"id": RULE_ID, "kind": "zone", "phase": audit.PHASES[0]},
                {"id": "d" * 32, "kind": "zone", "phase": audit.PHASES[2]},
            ], {"cursors": {"after": None}}),
            BASE + "/pagerules?status=active": envelope([]),
            BASE + "/settings/browser_cache_ttl": envelope({"id": "browser_cache_ttl", "value": 3600}),
            BASE + "/settings/cache_level": envelope({"id": "cache_level", "value": "aggressive"}),
            f"/accounts/{AID}/workers/scripts/{self.worker}/settings": envelope({
                "compatibility_date": "2026-09-03",
                "compatibility_flags": ["cache_option_enabled", PRIVATE],
                "cache": {"enabled": False},
                "bindings": [{"type": "secret_text", "name": PRIVATE, "text": TOKEN}],
            }),
        }
        for phase in audit.PHASES:
            self.responses[BASE + "/rulesets/phases/" + phase + "/entrypoint"] = envelope(
                {"id": RULE_ID, "phase": phase, "kind": "zone", "rules": []})
        self.responses[BASE + "/rulesets/phases/" + audit.PHASES[1] + "/entrypoint"] = (
            None, "HTTP_STATUS:404")

    def transport(self, url, **options):
        self.calls.append((url, options))
        assert url.startswith(audit.API + "/"), "unexpected host"
        key = url[len(audit.API):]
        assert key in self.responses, "unexpected endpoint"
        return copy.deepcopy(self.responses[key])

    def run(self):
        return audit.audit(TOKEN, transport=self.transport)


class CacheAuditContract(unittest.TestCase):
    def test_get_only_fixed_scope_bounded_transport_and_honest_observation(self):
        world = World()
        with patch("socket.create_connection", side_effect=AssertionError("real network")):
            report = world.run()
        self.assertEqual(report["state"], "OBSERVED")
        self.assertEqual(len(world.calls), 11)
        self.assertFalse(report["provider_write_capability"])
        self.assertEqual(report["effective_policy"], "NOT_EVALUATED")
        self.assertFalse(report["atomic_snapshot"])
        self.assertEqual(report["scope"]["assets"], list(audit.ASSETS))
        for url, options in world.calls:
            self.assertEqual(options["method"], "GET")
            self.assertIsNone(options["body"])
            self.assertEqual(options["max_redirects"], 0)
            self.assertFalse(options["allow_private"])
            self.assertEqual(options["success_status"], 200)
            self.assertEqual(options["max_response_bytes"], audit.MAX_RESPONSE_BYTES)
            self.assertGreater(options["timeout"], 0)
            self.assertLessEqual(options["timeout"], audit.REQUEST_TIMEOUT)
            self.assertEqual(set(options["headers"]), {"Authorization", "Accept"})
            self.assertNotIn("purge", url)
        self.assertEqual(report["observations"][audit.PHASES[1]]["state"], "ABSENT")
        self.assertEqual(report["observations"]["route_recheck"], {"state": "OBSERVED", "same_owner": True})

    def test_missing_credential_performs_no_request(self):
        with patch.object(audit, "http_json", side_effect=AssertionError("network")):
            report = audit.audit("")
        self.assertEqual(report["reason"], "CREDENTIAL_UNAVAILABLE")
        self.assertEqual(report["provider_get_requests"], 0)

    def test_forbidden_is_partial_not_absent_and_other_reads_survive(self):
        world = World()
        world.responses[BASE + "/rulesets/phases/" + audit.PHASES[0] + "/entrypoint"] = (
            {"secret": TOKEN}, "HTTP_STATUS:403")
        report = world.run()
        self.assertEqual(report["state"], "PARTIAL")
        self.assertEqual(report["observations"][audit.PHASES[0]], {"state": "FORBIDDEN"})
        self.assertEqual(report["observations"]["browser_cache_ttl"]["value"], 3600)
        self.assertNotIn(TOKEN, json.dumps(report))

    def test_404_with_denied_index_never_claims_absence(self):
        world = World()
        world.responses[BASE + "/rulesets?per_page=50"] = (None, "HTTP_STATUS:403")
        report = world.run()
        self.assertEqual(report["observations"][audit.PHASES[1]]["state"], "NOT_FOUND_UNCONFIRMED")
        self.assertEqual(report["state"], "PARTIAL")

    def test_cursor_continuation_or_missing_completion_never_claims_absence(self):
        cases = [
            {"cursors": {"after": PRIVATE}},
            None,
            {},
            {"cursors": PRIVATE},
            {"cursors": {"after": 42}},
        ]
        for info in cases:
            with self.subTest(info=info):
                world = World()
                world.responses[BASE + "/rulesets?per_page=50"] = envelope([], info)
                report = world.run()
                self.assertEqual(report["state"], "PARTIAL")
                self.assertEqual(report["observations"][audit.PHASES[1]]["state"], "NOT_FOUND_UNCONFIRMED")
                self.assertNotIn(PRIVATE, json.dumps(report))
                self.assertEqual(sum("/rulesets?" in url for url, _ in world.calls), 1)

    def test_discovery_without_complete_page_is_unavailable(self):
        for info in (None, {}, {"page": 1, "total_pages": 2, "total_count": 51}):
            with self.subTest(info=info):
                world = World()
                world.responses[ZONE_PATH] = envelope(
                    [{"id": ZID, "name": audit.ZONE, "status": "active", "account": {"id": AID}}], info)
                report = world.run()
                self.assertEqual(report["state"], "UNAVAILABLE")
                self.assertEqual(len(world.calls), 1)

    def test_foreign_zone_and_untrusted_identifiers_cannot_expand_scope(self):
        for field, value in (("name", "other.example"), ("id", "../other"), ("status", "pending")):
            with self.subTest(field=field):
                world = World()
                world.responses[ZONE_PATH][0]["result"][0][field] = value
                report = world.run()
                self.assertEqual(report["state"], "UNAVAILABLE")
                self.assertEqual(len(world.calls), 1)

    def test_foreign_worker_or_unexpected_route_refuses_worker_settings(self):
        for extra in (False, True):
            with self.subTest(extra=extra):
                world = World()
                rows = world.responses[BASE + "/workers/routes"][0]["result"]
                if extra:
                    rows.append({"pattern": audit.ZONE + "/command-centre/*", "script": PRIVATE})
                else:
                    rows[0]["script"] = PRIVATE
                report = world.run()
                self.assertEqual(report["observations"]["worker_settings"]["state"], "UNAVAILABLE")
                self.assertFalse(any("/accounts/" in url for url, _ in world.calls))
                self.assertNotIn(PRIVATE, json.dumps(report))

    def test_provider_secrets_expressions_bindings_and_arbitrary_headers_are_not_retained(self):
        world = World()
        private_expression = '(http.request.headers["x-private"][0] eq "' + PRIVATE + '") and (http.host eq "a-11-oy.com")'
        world.responses[BASE + "/rulesets/phases/" + audit.PHASES[0] + "/entrypoint"][0]["result"]["rules"] = [{
            "id": RULE_ID, "description": PRIVATE, "ref": TOKEN, "enabled": True,
            "action": "set_cache_settings", "expression": private_expression,
            "action_parameters": {
                "cache": True, "edge_ttl": {"mode": "override_origin", "default": 86400},
                "browser_ttl": {"mode": "override_origin", "default": 3600},
                "cache_key": {"custom_key": {"cookie": {"include": [PRIVATE]}, "header": {"contains": {PRIVATE: TOKEN}}}},
            },
        }]
        world.responses[BASE + "/rulesets/phases/" + audit.PHASES[2] + "/entrypoint"][0]["result"]["rules"] = [{
            "id": RULE_ID, "enabled": True, "action": "rewrite", "expression": private_expression,
            "action_parameters": {"headers": {
                "cache-control": {"operation": "set", "value": "max-age=3600, hidden=" + PRIVATE},
                "etag": {"operation": "set", "value": PRIVATE},
                "x-private-name": {"operation": "set", "value": TOKEN},
                "set-cookie": {"operation": "set", "value": PRIVATE},
            }},
        }]
        world.responses[BASE + "/pagerules?status=active"] = envelope([{
            "id": RULE_ID, "status": "active", "priority": 1,
            "targets": [{"target": "url", "constraint": {"operator": "matches", "value": "*?key=" + PRIVATE}}],
            "actions": [{"id": "edge_cache_ttl", "value": 14400},
                        {"id": "bypass_cache_on_cookie", "value": PRIVATE}],
        }])
        report = world.run()
        encoded = json.dumps(report)
        for secret in (TOKEN, PRIVATE, "x-private", "x-private-name", "set-cookie", private_expression):
            self.assertNotIn(secret, encoded)
        rule = report["observations"][audit.PHASES[0]]["rules_projected"][0]
        self.assertEqual(rule["id"], RULE_ID)
        self.assertEqual(rule["parameters"]["edge_ttl"]["default"], 86400)
        self.assertEqual(rule["expression"]["fixed_public_literals_seen"], [audit.ZONE])
        self.assertEqual(rule["expression"]["state"], "REDACTED_NOT_EVALUATED")
        headers = report["observations"][audit.PHASES[2]]["rules_projected"][0]["parameters"]["cache_response_headers"]
        self.assertEqual(headers["cache-control"]["value"]["directives"], {"max-age": 3600})
        self.assertEqual(report["observations"]["worker_settings"]["worker_cache"]["enabled"], False)

    def test_failed_and_oversized_transport_does_not_emit_provider_body(self):
        for error, state in (("HTTP_STATUS:401", "UNAUTHENTICATED"), ("HTTP_STATUS:429", "RATE_LIMITED"),
                             ("RESPONSE_TOO_LARGE", "TRUNCATED"), ("TIMEOUT", "TIMEOUT"),
                             ("REDIRECT_LIMIT_EXCEEDED", "UNAVAILABLE")):
            with self.subTest(error=error):
                world = World()
                world.responses[ZONE_PATH] = ({"token": TOKEN}, error)
                report = world.run()
                self.assertEqual(report["observations"]["zone"]["state"], state)
                self.assertNotIn(TOKEN, json.dumps(report))
                self.assertEqual(len(world.calls), 1)

    def test_budget_stops_calls_without_retry_or_sleep(self):
        world = World()
        client = audit.AuditClient(TOKEN, transport=world.transport, clock=lambda: 0)
        for _ in range(audit.MAX_REQUESTS + 2):
            last = client.read("zone")
        self.assertEqual(len(world.calls), audit.MAX_REQUESTS)
        self.assertEqual(last["reason"], "AUDIT_BUDGET_EXHAUSTED")
        world = World()
        ticks = iter((0, audit.AUDIT_TIMEOUT + 1))
        client = audit.AuditClient(TOKEN, transport=world.transport, clock=lambda: next(ticks))
        self.assertEqual(client.read("zone")["reason"], "AUDIT_BUDGET_EXHAUSTED")
        self.assertEqual(world.calls, [])

    def test_unsupported_endpoint_never_reaches_transport(self):
        world = World()
        client = audit.AuditClient(TOKEN, transport=world.transport)
        client.zone_id = ZID
        self.assertEqual(client.read("purge_cache")["reason"], "ENDPOINT_NOT_ALLOWED")
        self.assertEqual(world.calls, [])

    def test_oversized_collection_and_phase_mismatch_are_incomplete(self):
        result = audit.collection({"state": "OBSERVED", "result": [{}] * (audit.MAX_ROWS + 1)})
        self.assertEqual(result["state"], "TRUNCATED")
        result = audit.rules_summary({"phase": "unexpected", "rules": []}, audit.PHASES[0])
        self.assertEqual(result["state"], "MALFORMED")
        self.assertEqual(audit.expression_summary("x" * (audit.MAX_EXPRESSION_BYTES + 1))["state"], "INVALID_OR_OVERSIZED")

    def test_actions_unprotected_contexts_refuse_before_audit(self):
        for field, value in (("GITHUB_REF", "refs/heads/unreviewed"),
                             ("GITHUB_REPOSITORY", "foreign/repository"),
                             ("GITHUB_EVENT_NAME", "pull_request")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                environment = {
                    "GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/main",
                    "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": "szl-holdings/a11oy",
                    field: value,
                }
                with patch.dict(os.environ, environment), patch.object(
                    audit, "audit", side_effect=AssertionError("audit called")
                ), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(audit.main(["--report", str(Path(folder) / "report.json")]), 2)
                    self.assertEqual(list(Path(folder).iterdir()), [])

    def test_response_cache_directives_retain_ttls_and_never_qualifiers_or_tags(self):
        world = World()
        world.responses[BASE + "/rulesets/phases/" + audit.PHASES[1] + "/entrypoint"] = envelope({
            "id": RULE_ID, "phase": audit.PHASES[1], "rules": [
                {"id": RULE_ID, "enabled": True, "expression": "true", "action": "set_cache_control",
                 "action_parameters": {
                     "max-age": {"operation": "set", "value": 3600, "cloudflare_only": True},
                     "s-maxage": {"operation": "set", "value": 86400},
                     "no-store": {"operation": "remove"},
                     "private": {"operation": "set", "qualifiers": [PRIVATE, TOKEN]},
                 }},
                {"id": RULE_ID, "enabled": True, "expression": "true", "action": "set_cache_settings",
                 "action_parameters": {"strip_etags": True, "strip_set_cookie": False, "strip_last_modified": True}},
                {"id": RULE_ID, "enabled": True, "expression": "true", "action": "set_cache_tags",
                 "action_parameters": {"operation": "set", "values": [PRIVATE, TOKEN]}},
            ],
        })
        report = world.run()
        self.assertEqual(report["state"], "OBSERVED")
        rules = report["observations"][audit.PHASES[1]]["rules_projected"]
        directives = rules[0]["parameters"]["cache_control_directives"]
        self.assertEqual(directives["max-age"], {
            "state": "OBSERVED", "operation": "set", "value": 3600, "cloudflare_only": True})
        self.assertEqual(directives["s-maxage"]["value"], 86400)
        self.assertEqual(directives["no-store"]["operation"], "remove")
        self.assertEqual(directives["private"]["qualifier_count"], 2)
        self.assertEqual(directives["private"]["qualifiers"], "PRESENT_REDACTED")
        self.assertTrue(rules[1]["parameters"]["strip_etags"])
        self.assertFalse(rules[1]["parameters"]["strip_set_cookie"])
        self.assertEqual(rules[2]["parameters"]["cache_tags"], "PRESENT_REDACTED")
        for secret in (PRIVATE, TOKEN):
            self.assertNotIn(secret, json.dumps(report))

    def test_malformed_nested_rules_preserve_bounded_partial_observations(self):
        cases = [
            (audit.PHASES[0], "set_cache_settings", {"edge_ttl": {"mode": {}}}),
            (audit.PHASES[0], "set_cache_settings", {"edge_ttl": {"status_code_ttl": [{"status_code": 200}]}}),
            (audit.PHASES[0], "set_cache_settings", {"edge_ttl": {"status_code_ttl": [{"status_code": {}, "value": 3600}]}}),
            (audit.PHASES[0], "set_cache_settings", {"edge_ttl": {"status_code_ttl": [{"status_code_range": {"from": "bad"}, "value": 3600}]}}),
            (audit.PHASES[0], {}, {}),
            (audit.PHASES[0], "set_cache_settings", {"cache": {}}),
            (audit.PHASES[2], "rewrite", {"headers": {"cache-control": {"operation": {}}}}),
            (audit.PHASES[1], "set_cache_control", {"max-age": {"operation": {}}}),
            (audit.PHASES[1], "set_cache_control", {"max-age": {"operation": "set", "value": []}}),
            (audit.PHASES[1], "set_cache_control", {"private": {"operation": "set", "qualifiers": {PRIVATE: TOKEN}}}),
        ]
        for phase, action, parameters in cases:
            with self.subTest(phase=phase, action=action):
                world = World()
                world.responses[BASE + "/rulesets/phases/" + phase + "/entrypoint"] = envelope({
                    "phase": phase, "rules": [{
                        "id": RULE_ID, "enabled": True, "expression": "true",
                        "action": action, "action_parameters": parameters,
                    }],
                })
                report = world.run()
                self.assertEqual(report["state"], "PARTIAL")
                self.assertEqual(report["observations"][phase]["state"], "PARTIAL")
                self.assertEqual(report["observations"]["browser_cache_ttl"]["value"], 3600)
                self.assertEqual(len(world.calls), 11)
                self.assertNotIn(TOKEN, json.dumps(report))
                self.assertNotIn(PRIVATE, json.dumps(report))

    def test_malformed_page_rules_settings_and_route_metadata_do_not_drop_report(self):
        for actions, status in (([{"id": {}, "value": {}}], "active"),
                                ([{"id": "cache_level", "value": {}}], "active"),
                                ([{"id": "origin_cache_control", "value": []}], "active"),
                                ([{"id": "edge_cache_ttl", "value": 3600}], {})):
            with self.subTest(actions=actions, status=status):
                world = World()
                world.responses[BASE + "/pagerules?status=active"] = envelope([{
                    "id": RULE_ID, "status": status, "actions": actions, "targets": [],
                }])
                report = world.run()
                self.assertEqual(report["state"], "PARTIAL")
                self.assertEqual(report["observations"]["page_rules"]["state"], "PARTIAL")
                self.assertEqual(report["observations"]["browser_cache_ttl"]["value"], 3600)
        world = World()
        world.responses[BASE + "/settings/cache_level"] = envelope({"id": "cache_level", "value": {}})
        report = world.run()
        self.assertEqual(report["observations"]["cache_level"]["state"], "MALFORMED")
        self.assertEqual(report["observations"]["browser_cache_ttl"]["value"], 3600)
        world = World()
        world.responses[BASE + "/workers/routes"][0]["result"][0]["script"] = {}
        report = world.run()
        self.assertEqual(report["observations"]["worker_settings"]["state"], "UNAVAILABLE")
        self.assertEqual(report["observations"]["browser_cache_ttl"]["value"], 3600)

    def test_workflow_admits_only_manual_main_source_and_environment_token(self):
        source = (audit.ROOT / ".github/workflows/audit-command-centre-cache-policy.yml").read_text(encoding="utf-8")
        trigger = re.search(r"(?m)^on:\n((?:[ \t].*\n|\n)+)", source)
        self.assertIsNotNone(trigger)
        self.assertEqual(trigger.group(1).strip(), "workflow_dispatch:")
        permissions = re.search(r"(?m)^permissions:\n((?:[ \t].*\n|\n)+)", source)
        self.assertEqual(permissions.group(1).strip(), "contents: read")
        self.assertIn("group: cloudflare-product-edge-v4", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertEqual(source.count("persist-credentials: false"), 2)
        self.assertEqual(source.count("ref: " + "$" + "{{ github.sha }}"), 2)
        self.assertEqual(source.count("$" + "{{ secrets."), 1)
        self.assertIn("CLOUDFLARE_API_TOKEN: " + "$" + "{{ secrets.CLOUDFLARE_API_TOKEN }}", source)
        self.assertIn('test "$GITHUB_REPOSITORY" = "szl-holdings/a11oy"', source)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', source)
        self.assertIn('test "$GITHUB_EVENT_NAME" = "workflow_dispatch"', source)
        observe = source.split("\n  observe:", 1)[1]
        self.assertIn("needs: contract", observe)
        self.assertIn("environment: production", observe)
        self.assertIn("github.repository == 'szl-holdings/a11oy'", observe)
        self.assertIn("github.ref == 'refs/heads/main'", observe)
        self.assertIn("github.event_name == 'workflow_dispatch'", observe)
        self.assertIn("if: always()", observe)
        self.assertIn("if-no-files-found: error", observe)
        ci = (audit.ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("tests/test_cloudflare_command_centre_cache_audit.py", ci)

    def test_cli_preserves_partial_report_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "GITHUB_ACTIONS": "false", "CLOUDFLARE_API_TOKEN": "",
        }), contextlib.redirect_stdout(io.StringIO()):
            path = Path(folder) / "report.json"
            self.assertEqual(audit.main(["--report", str(path)]), 2)
            document = json.loads(path.read_text())
            self.assertEqual(document["reason"], "CREDENTIAL_UNAVAILABLE")
            before = path.read_bytes()
            self.assertEqual(audit.main(["--report", str(path)]), 2)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_last_boundary_refuses_bearer_in_report(self):
        report = {"state": "OBSERVED", "provider_get_requests": 0, "unexpected": TOKEN}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "GITHUB_ACTIONS": "false", "CLOUDFLARE_API_TOKEN": TOKEN,
        }), patch.object(audit, "audit", return_value=report), contextlib.redirect_stdout(io.StringIO()) as captured:
            path = Path(folder) / "report.json"
            self.assertEqual(audit.main(["--report", str(path)]), 2)
            self.assertFalse(path.exists())
            self.assertNotIn(TOKEN, captured.getvalue())


if __name__ == "__main__":
    unittest.main()
