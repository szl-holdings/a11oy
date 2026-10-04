"""Simulated provider refusals, one-rule preservation, and receipt truth."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch
import urllib.error

from scripts import proof_cloudflare_headers as headers

ZONE, ACCOUNT, RULESET, RULE, OTHER = [str(i) * 32 for i in range(1, 6)]
SOURCE = "6" * 40


def owned_rule():
    rule = copy.deepcopy(headers.load_policy()["rule"])
    rule.update({"id": RULE, "version": "1", "last_updated": "2026-10-01T00:00:00Z"})
    return rule


def unrelated_rule():
    return {"id": OTHER, "version": "2", "ref": "other-rule", "action": "rewrite",
            "expression": '(http.host eq "other.a11oy.net")', "enabled": True,
            "action_parameters": {"headers": {"x-unrelated": {"operation": "set", "value": "retain"}}}}


def ruleset(rules=None):
    return {"id": RULESET, "version": "1", "kind": "zone", "phase": headers.PHASE,
            "name": "Existing entrypoint", "description": "Preserve me",
            "rules": copy.deepcopy([unrelated_rule()] if rules is None else rules)}


class FakeClient:
    def __init__(self):
        self.events, self.calls = [], []
        self.current = ruleset()
        self.zone = {"id": ZONE, "name": "a11oy.net", "status": "active", "account": {"id": ACCOUNT}}
        self.zones = [self.zone]
        self.account = ACCOUNT
        self.reads = 0
        self.change_on_second_read = False
        self.change_on_readback = False
        self.change_zone = False
        self.denied_method = None
        self.transport_method = None
        self.extra_mutation = False
        self.reorder = False
        self.missing_phase = False

    def request(self, method, path, payload=None):
        self.calls.append({"method": method, "path": path, "payload": copy.deepcopy(payload)})
        event = {"method": method, "path_sha256": headers.digest(path), "status": 200}
        self.events.append(event)
        if method == self.denied_method:
            event["status"] = 403
            raise headers.Refused("Provider HTTP 403; inspect numeric codes in receipt")
        if method == self.transport_method:
            raise headers.Refused("Provider transport failed; mutation outcome may be unknown")
        if path.startswith("/zones?"):
            return {"result": copy.deepcopy(self.zones)}
        if path == f"/accounts/{ACCOUNT}":
            return {"result": {"id": self.account}}
        if path == f"/zones/{ZONE}":
            zone = copy.deepcopy(self.zone)
            if self.change_zone:
                zone["account"]["id"] = "7" * 32
            return {"result": zone}
        if method == "GET":
            if self.missing_phase:
                event["status"] = 404
                raise headers.Refused("Provider HTTP 404; inspect numeric codes in receipt")
            self.reads += 1
            if self.change_on_second_read and self.reads == 2:
                self.current["description"] = "Concurrent change"
            if self.change_on_readback and self.reads == 3:
                self.current["rules"][0]["enabled"] = False
            return {"result": copy.deepcopy(self.current)}
        target = copy.deepcopy(payload)
        target.update({"id": RULE, "version": "2"})
        if method == "POST":
            self.current["rules"].append(target)
        elif method == "PATCH":
            for i, rule in enumerate(self.current["rules"]):
                if rule["id"] == RULE:
                    self.current["rules"][i] = target
                    break
        else:
            raise AssertionError("Unexpected fixture method")
        self.current["version"] = "2"
        if self.extra_mutation:
            self.current["rules"][0]["expression"] = "true"
        if self.reorder:
            self.current["rules"].reverse()
        return {"result": copy.deepcopy(self.current)}


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.policy = headers.load_policy()
        self.client = FakeClient()

    def run_controller(self, mode="audit", expected=""):
        return headers.operate(self.client, mode, expected, self.out, SOURCE, self.policy)

    def writes(self):
        return [call for call in self.client.calls if call["method"] in {"POST", "PATCH", "PUT", "DELETE"}]

    def assert_blocked_read_only(self, **kwargs):
        report = self.run_controller(**kwargs)
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(0, report["write_attempts"])
        self.assertEqual([], self.writes())
        return report

    def test_default_audit_has_no_provider_write_or_mutation_envelope(self):
        before = copy.deepcopy(self.client.current)
        report = self.run_controller()
        self.assertEqual("AUDITED_READ_ONLY", report["state"])
        self.assertEqual(before, self.client.current)
        self.assertEqual(headers.digest(before), report["before_settings_sha256"])
        self.assertEqual([], self.writes())
        self.assertFalse((self.out / "mutation-unsigned-dsse.json").exists())
        self.assertEqual("UNKNOWN", report["provider_atomic_compare_and_swap"])
        self.assertEqual("UNKNOWN", report["proof_current_protected_head"])

    def test_wrong_product_zone_is_refused(self):
        self.client.zone["name"] = "a-11-oy.com"
        self.assert_blocked_read_only()

    def test_ambiguous_active_zone_is_refused(self):
        self.client.zones.append(copy.deepcopy(self.client.zone))
        self.assert_blocked_read_only()

    def test_account_detail_must_match_zone(self):
        self.client.account = "7" * 32
        self.assert_blocked_read_only()

    def test_missing_existing_phase_blocks_without_creation(self):
        self.client.missing_phase = True
        self.assert_blocked_read_only()

    def test_other_phase_or_kind_is_refused(self):
        for key, value in [("phase", "http_request_firewall_custom"), ("kind", "root")]:
            with self.subTest(key=key):
                self.client = FakeClient()
                self.client.current[key] = value
                with tempfile.TemporaryDirectory() as temp:
                    report = headers.operate(self.client, "audit", "", Path(temp), SOURCE, self.policy)
                self.assertEqual("BLOCKED", report["state"])
                self.assertEqual([], self.writes())

    def test_another_writer_of_protected_header_blocks_even_if_disabled(self):
        rule = unrelated_rule()
        rule["enabled"] = False
        rule["action_parameters"]["headers"] = {"Content-Security-Policy": {"operation": "set", "value": "unsafe"}}
        self.client.current = ruleset([rule])
        self.assert_blocked_read_only()

    def test_mixed_managed_rule_cannot_be_taken_over(self):
        rule = owned_rule()
        rule["action_parameters"]["headers"]["x-unrelated"] = {"operation": "set", "value": "retain"}
        self.client.current = ruleset([rule])
        self.assert_blocked_read_only()

    def test_managed_ref_with_product_expression_cannot_be_taken_over(self):
        rule = owned_rule()
        rule["expression"] = '(http.host eq "a-11-oy.com")'
        self.client.current = ruleset([rule])
        self.assert_blocked_read_only()

    def test_managed_ref_duplicates_or_duplicate_ids_block(self):
        rule = owned_rule()
        other = copy.deepcopy(rule)
        other["id"] = "7" * 32
        self.client.current = ruleset([rule, other])
        self.assert_blocked_read_only()

    def test_expected_audit_hash_is_required_before_requests(self):
        with self.assertRaises(headers.Refused):
            self.run_controller("apply")
        self.assertEqual([], self.client.calls)

    def test_exact_source_is_required_before_requests(self):
        with self.assertRaises(headers.Refused):
            headers.operate(self.client, "audit", "", self.out, "UNKNOWN", self.policy)
        self.assertEqual([], self.client.calls)

    def test_prior_audit_hash_drift_prevents_write(self):
        self.assert_blocked_read_only(mode="apply", expected="0" * 64)

    def test_immediate_ruleset_drift_prevents_write(self):
        self.client.change_on_second_read = True
        self.assert_blocked_read_only(mode="apply", expected=headers.digest(self.client.current))

    def test_immediate_account_binding_drift_prevents_write(self):
        self.client.change_zone = True
        self.assert_blocked_read_only(mode="apply", expected=headers.digest(self.client.current))

    def test_audited_exact_rule_never_duplicate_applies(self):
        self.client.current = ruleset([unrelated_rule(), owned_rule()])
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("ALREADY_EXACT_READ_ONLY", report["state"])
        self.assertEqual([], self.writes())
        self.assertFalse((self.out / "mutation-unsigned-dsse.json").exists())

    def test_append_changes_one_rule_preserves_other_rules_and_reads_back(self):
        before = copy.deepcopy(self.client.current)
        report = self.run_controller("apply", headers.digest(before))
        self.assertEqual("APPLIED_SETTINGS_READBACK_VERIFIED", report["state"])
        self.assertEqual(1, report["write_attempts"])
        writes = self.writes()
        self.assertEqual(1, len(writes))
        self.assertEqual("POST", writes[0]["method"])
        self.assertEqual(f"/zones/{ZONE}/rulesets/{RULESET}/rules", writes[0]["path"])
        self.assertEqual(self.policy["rule"], writes[0]["payload"])
        self.assertEqual(before["rules"], self.client.current["rules"][:-1])
        self.assertEqual(3, self.client.reads)
        self.assertTrue(report["other_rules_preserved"])
        self.assertEqual("NOT_CHECKED", report["public_eight_header_acceptance"])

    def test_update_preserves_rule_identity_position_and_siblings(self):
        rule = owned_rule()
        rule["enabled"] = False
        self.client.current = ruleset([rule, unrelated_rule()])
        sibling = copy.deepcopy(self.client.current["rules"][1])
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("APPLIED_SETTINGS_READBACK_VERIFIED", report["state"])
        self.assertEqual("PATCH", self.writes()[0]["method"])
        self.assertEqual(f"/zones/{ZONE}/rulesets/{RULESET}/rules/{RULE}", self.writes()[0]["path"])
        self.assertEqual(RULE, self.client.current["rules"][0]["id"])
        self.assertEqual(sibling, self.client.current["rules"][1])

    def test_write_denial_records_one_attempt_and_no_retry(self):
        self.client.denied_method = "POST"
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(1, report["write_attempts"])
        self.assertEqual("PROVIDER_REJECTED_WRITE_HTTP_4XX", report["mutation_outcome"])
        self.assertEqual(1, len(self.writes()))

    def test_missing_permission_blocks_read_without_any_write(self):
        self.client.denied_method = "GET"
        self.assert_blocked_read_only()

    def test_ambiguous_transport_after_submission_retains_unknown_attempt(self):
        self.client.transport_method = "POST"
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(1, report["write_attempts"])
        self.assertEqual("UNKNOWN_AFTER_SUBMISSION_ATTEMPT", report["mutation_outcome"])
        self.assertEqual(1, len(self.writes()))

    def test_changed_sibling_is_blocked_after_one_write_without_rollback(self):
        self.client.extra_mutation = True
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(1, report["write_attempts"])
        self.assertNotIn("other_rules_preserved", report)
        self.assertEqual(1, len(self.writes()))

    def test_unexpected_reordering_is_blocked(self):
        self.client.reorder = True
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(1, len(self.writes()))

    def test_independent_get_detects_provider_response_then_drift(self):
        self.client.change_on_readback = True
        report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual("PROVIDER_RESPONSE_OBSERVED_FINAL_STATE_UNVERIFIED", report["mutation_outcome"])
        self.assertEqual(1, len(self.writes()))

    def test_write_envelope_is_unsigned_chained_and_digest_valid(self):
        self.run_controller("apply", headers.digest(self.client.current))
        envelope = json.loads((self.out / "mutation-unsigned-dsse.json").read_text())
        self.assertEqual([], envelope["signatures"])
        self.assertEqual("UNSIGNED", envelope["signature_status"])
        raw = base64.b64decode(envelope["payload"], validate=True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), envelope["payload_sha256"])
        payload = json.loads(raw)
        previous = headers.digest({"source_revision": SOURCE, "domain": headers.DOMAIN,
                                   "before_settings_sha256": payload["before_settings_sha256"]})
        for link in payload["provider_event_chain"]:
            self.assertEqual(previous, link["previous_event_sha256"])
            previous = headers.digest({"previous_event_sha256": previous, "event": link["event"]})
            self.assertEqual(previous, link["event_sha256"])
        self.assertEqual(previous, payload["previous_event_sha256"])

    def test_prewrite_durability_failure_prevents_provider_mutation(self):
        original = headers.write_new
        def fail(path, value):
            if path.name == "pre-write-admission.json":
                raise OSError("NON_SECRET_TEST_FIXTURE")
            return original(path, value)
        with patch.object(headers, "write_new", side_effect=fail):
            report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(0, report["write_attempts"])
        self.assertEqual([], self.writes())
        self.assertNotIn("NON_SECRET_TEST_FIXTURE", (self.out / "receipt.json").read_text())

    def test_postwrite_envelope_failure_never_resets_attempt_truth(self):
        original = headers.write_new
        def fail(path, value):
            if path.name == "mutation-unsigned-dsse.json":
                raise OSError("NON_SECRET_TEST_FIXTURE")
            return original(path, value)
        with patch.object(headers, "write_new", side_effect=fail):
            report = self.run_controller("apply", headers.digest(self.client.current))
        stored = json.loads((self.out / "receipt.json").read_text())
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(1, len(self.writes()))
        self.assertEqual(1, stored["write_attempts"])
        self.assertNotEqual("NOT_ATTEMPTED", stored["mutation_outcome"])
        self.assertNotIn("NON_SECRET_TEST_FIXTURE", json.dumps(stored))

    def test_postwrite_receipt_failure_returns_attempt_history(self):
        original = headers.write_new
        def fail(path, value):
            if path.name == "receipt.json":
                raise OSError("NON_SECRET_TEST_FIXTURE")
            return original(path, value)
        with patch.object(headers, "write_new", side_effect=fail):
            report = self.run_controller("apply", headers.digest(self.client.current))
        self.assertEqual("BLOCKED", report["state"])
        self.assertEqual(1, report["write_attempts"])
        envelope = json.loads((self.out / "mutation-unsigned-dsse.json").read_text())
        self.assertEqual(1, json.loads(base64.b64decode(envelope["payload"]))["write_attempts"])

    def test_audit_public_projection_hashes_unrelated_secrets(self):
        self.client.current["rules"][0]["unexpected"] = "NON_SECRET_TEST_FIXTURE"
        self.run_controller()
        self.assertNotIn("NON_SECRET_TEST_FIXTURE", (self.out / "receipt.json").read_text())

    def test_policy_cannot_be_rebound_to_product_or_modified_headers(self):
        for mutate in [lambda p: p.update(domain="a-11-oy.com"),
                       lambda p: p["rule"].update(expression='(http.host eq "a-11-oy.com")'),
                       lambda p: p["rule"]["action_parameters"]["headers"]["content-security-policy"].update(value="unsafe"),
                       lambda p: p.update(source_revision="7" * 40)]:
            with self.subTest(mutate=mutate):
                policy = copy.deepcopy(self.policy)
                mutate(policy)
                with self.assertRaises(headers.Refused):
                    headers.operate(self.client, "audit", "", self.out, SOURCE, policy)
        self.assertEqual([], self.client.calls)


class TransportTests(unittest.TestCase):
    def test_malformed_bearer_refuses_before_transport_without_exposing_value(self):
        for suffix in ["\nINJECTED", "\rINJECTED", "\tINJECTED", " INJECTED", "\x7f", "\u0100"]:
            with self.subTest(suffix=suffix):
                with patch.object(headers.common.urllib.request, "build_opener") as opener:
                    with self.assertRaises(headers.Refused) as caught:
                        headers.Client("NON_SECRET_TEST_FIXTURE" + suffix)
                opener.assert_not_called()
                self.assertNotIn("NON_SECRET_TEST_FIXTURE", str(caught.exception))

    def test_header_validator_valueerror_sanitizes_message_and_traceback(self):
        client = headers.Client("NON_SECRET_TEST_FIXTURE")
        with patch.object(client.opener, "open", side_effect=ValueError("NON_SECRET_TEST_FIXTURE")):
            try:
                client.request("GET", "/zones?name=a11oy.net&status=active&per_page=50")
            except headers.Refused:
                rendered = traceback.format_exc()
            else:
                self.fail("Header validation error was not refused")
        self.assertNotIn("NON_SECRET_TEST_FIXTURE", rendered)
        self.assertEqual(1, len(client.events))
        self.assertIsNone(client.events[0]["status"])

    def test_cli_malformed_bearer_has_redacted_blocked_receipt_and_zero_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "new-output"
            env = {"GITHUB_REPOSITORY": "szl-holdings/a11oy", "GITHUB_REF": "refs/heads/main",
                   "GITHUB_SHA": SOURCE, "CLOUDFLARE_API_TOKEN": "NON_SECRET_TEST_FIXTURE\nINJECTED"}
            stdout = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch("sys.argv", ["controller", "--output-directory", str(out)]), \
                 patch("sys.stdout", stdout), patch.object(headers.common.urllib.request, "build_opener") as opener:
                code = headers.main()
            opener.assert_not_called()
            stored = (out / "receipt.json").read_text()
            report = json.loads(stored)
            self.assertEqual(1, code)
            self.assertEqual("BLOCKED", report["state"])
            self.assertEqual(0, report["write_attempts"])
            self.assertNotIn("NON_SECRET_TEST_FIXTURE", stored + stdout.getvalue())

    def test_no_dns_rum_product_or_entrypoint_mutation_paths(self):
        for method, path in [("PUT", f"/zones/{ZONE}/rulesets/{RULESET}"),
            ("POST", f"/zones/{ZONE}/rulesets"), ("DELETE", f"/zones/{ZONE}/rulesets/{RULESET}"),
            ("GET", "/zones?name=a-11-oy.com&status=active&per_page=50"),
            ("PUT", f"/accounts/{ACCOUNT}/rum/site_info/{RULE}"),
            ("PATCH", f"/zones/{ZONE}/dns_records/{RULE}")]:
            with self.subTest(path=path):
                self.assertFalse(headers.allowed_request(method, path))

    def test_http_denial_records_numeric_code_without_provider_message(self):
        client = headers.Client("NON_SECRET_TEST_FIXTURE")
        error = urllib.error.HTTPError(headers.common.API + "/zones", 403, "Forbidden", {},
            io.BytesIO(b'{"success":false,"errors":[{"code":9109,"message":"NON_SECRET_TEST_FIXTURE"}]}'))
        with patch.object(client.opener, "open", side_effect=error):
            with self.assertRaisesRegex(headers.Refused, "HTTP 403") as caught:
                client.request("GET", "/zones?name=a11oy.net&status=active&per_page=50")
        self.assertEqual([9109], client.events[0]["provider_error_codes"])
        self.assertNotIn("NON_SECRET_TEST_FIXTURE", str(caught.exception))
        self.assertEqual(1, len(client.events))

    def test_redirect_handler_and_response_bounds_remain_fail_closed(self):
        self.assertIsNone(headers.common.NoRedirect().redirect_request(None,None,302,"Found",{},"https://other.invalid"))
        client = headers.Client("NON_SECRET_TEST_FIXTURE")
        with self.assertRaises(headers.Refused):
            client.read_bounded(io.BytesIO(b"x" * (headers.common.MAX_BYTES + 1)))
        client.deadline = 0
        with self.assertRaises(headers.Refused):
            client.request("GET", "/zones?name=a11oy.net&status=active&per_page=50")

    def test_duplicate_keys_and_nonfinite_policy_refuse(self):
        for raw in [b'{"rule":{},"rule":{}}', b'{"value":NaN}']:
            with self.subTest(raw=raw), self.assertRaises(headers.Refused):
                headers.common.strict_json(raw)


if __name__ == "__main__":
    unittest.main()
