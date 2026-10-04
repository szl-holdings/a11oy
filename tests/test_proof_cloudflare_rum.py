#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Network-free controls for fixed-target RUM admission and one field mutation."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "proof_cloudflare_rum.py"
SPEC = importlib.util.spec_from_file_location("proof_cloudflare_rum", SOURCE)
rum = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rum)
ZONE = "1" * 32
ACCOUNT = "2" * 32
SITE = "3" * 32
PUBLIC_FIXTURE = "4" * 32
SHA = "5" * 40


def site():
    return {"site_tag": SITE, "site_token": PUBLIC_FIXTURE, "auto_install": True,
            "created": "2026-01-01T00:00:00Z", "snippet": "public fixture only",
            "rules": [{"host": "a11oy.net", "paths": ["*"], "inclusive": True}],
            "ruleset": {"id": "6" * 32, "enabled": True,
                        "zone_name": "a11oy.net", "zone_tag": ZONE}}


class FakeClient:
    def __init__(self):
        self.events = []
        self.calls = []
        self.properties = [site()]
        self.current = site()
        self.reads = 0
        self.change_on_second_read = False
        self.deny_method = None
        self.extra_mutation = False
        self.change_on_readback = False
        self.account_id = ACCOUNT
        self.incomplete_list = False
        self.zone = {"id": ZONE, "name": "a11oy.net", "status": "active",
                     "account": {"id": ACCOUNT}}

    def request(self, method, path, payload=None):
        self.calls.append({"method": method, "path": path, "payload": copy.deepcopy(payload)})
        self.events.append({"method": method, "path_sha256": rum.digest(path)})
        if method == self.deny_method:
            self.events[-1]["status"] = 403
            raise rum.Refused("Provider HTTP 403; inspect numeric codes in the receipt")
        if path.startswith("/zones?"):
            return {"result": [copy.deepcopy(self.zone)]}
        if path == f"/zones/{ZONE}":
            return {"result": copy.deepcopy(self.zone)}
        if path == f"/accounts/{ACCOUNT}":
            return {"result": {"id": self.account_id}}
        if "/site_info/list?" in path:
            return {"result": copy.deepcopy(self.properties),
                    "result_info": {"page": 1, "total_pages": 1, "per_page": 50,
                        "count": len(self.properties),
                        "total_count": len(self.properties) + int(self.incomplete_list)}}
        if method == "GET":
            self.reads += 1
            if self.change_on_second_read and self.reads == 2:
                self.current["rules"][0]["inclusive"] = False
            if self.change_on_readback and self.reads == 3:
                self.current["rules"][0]["paths"] = ["/different"]
            return {"result": copy.deepcopy(self.current)}
        if method == "PUT":
            self.current["auto_install"] = payload["auto_install"]
            if self.extra_mutation:
                self.current["ruleset"]["enabled"] = False
            return {"result": copy.deepcopy(self.current)}
        raise AssertionError("Unexpected fixture request")


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.beacon = patch.object(rum, "BEACON_SHA256", hashlib.sha256(PUBLIC_FIXTURE.encode()).hexdigest())
        self.beacon.start()
        self.addCleanup(self.beacon.stop)
        self.client = FakeClient()

    def run_controller(self, mode="audit", expected=""):
        return rum.operate(self.client, mode, expected, self.out, SHA)

    def assert_no_put(self):
        self.assertEqual([], [event for event in self.client.events if event["method"] == "PUT"])

    def test_default_audit_preserves_settings_without_put_or_mutation_envelope(self):
        report = self.run_controller()
        self.assertEqual("AUDITED_READ_ONLY", report["state"])
        self.assertEqual("NOT_ATTEMPTED", report["mutation_outcome"])
        self.assertEqual(rum.digest(site()), report["before_settings_sha256"])
        self.assertEqual(site(), self.client.current)
        self.assert_no_put()
        self.assertTrue((self.out / "before-settings.json").is_file())
        self.assertFalse((self.out / "mutation-unsigned-dsse.json").exists())
        encoded = (self.out / "receipt.json").read_text()
        self.assertNotIn(PUBLIC_FIXTURE, encoded)
        self.assertNotIn(ACCOUNT, encoded)

    def test_wrong_zone_is_refused(self):
        self.client.zone["name"] = "a-11-oy.com"
        self.assertEqual("FAILED", self.run_controller()["state"])
        self.assert_no_put()

    def test_wrong_account_is_refused(self):
        self.client.account_id = "7" * 32
        self.assertEqual("FAILED", self.run_controller()["state"])
        self.assert_no_put()

    def test_wrong_site_domain_is_refused(self):
        self.client.properties[0]["ruleset"]["zone_name"] = "unrelated.example"
        self.assertEqual("FAILED", self.run_controller()["state"])
        self.assert_no_put()

    def test_wrong_beacon_is_refused(self):
        self.client.properties[0]["site_token"] = "7" * 32
        self.assertEqual("FAILED", self.run_controller()["state"])
        self.assert_no_put()

    def test_ambiguous_target_is_refused(self):
        other = site()
        other["site_tag"] = "8" * 32
        self.client.properties.append(other)
        self.assertEqual("FAILED", self.run_controller()["state"])
        self.assert_no_put()

    def test_incomplete_list_cannot_hide_another_target(self):
        self.client.incomplete_list = True
        report = self.run_controller()
        self.assertEqual("FAILED", report["state"])
        self.assertIn("complete list", report["error"])
        self.assert_no_put()

    def test_property_get_identity_must_match_selected_site(self):
        self.client.current["site_tag"] = "8" * 32
        self.assertEqual("FAILED", self.run_controller()["state"])
        self.assert_no_put()

    def test_changed_settings_since_prior_audit_prevent_put(self):
        report = self.run_controller("apply", "0" * 64)
        self.assertEqual("FAILED", report["state"])
        self.assert_no_put()

    def test_changed_settings_between_apply_reads_prevent_put(self):
        self.client.change_on_second_read = True
        report = self.run_controller("apply", rum.digest(site()))
        self.assertEqual("FAILED", report["state"])
        self.assert_no_put()

    def test_read_provider_denial_stays_failed_without_put(self):
        self.client.deny_method = "GET"
        report = self.run_controller()
        self.assertEqual("FAILED", report["state"])
        self.assertIn("403", report["error"])
        self.assert_no_put()

    def test_write_provider_denial_has_one_attempt_and_unsigned_failure_receipt(self):
        self.client.deny_method = "PUT"
        report = self.run_controller("apply", rum.digest(site()))
        self.assertEqual("FAILED", report["state"])
        self.assertEqual(1, report["put_attempts"])
        self.assertEqual("PROVIDER_REJECTED_WRITE_HTTP_4XX", report["mutation_outcome"])
        self.assertEqual(1, sum(event["method"] == "PUT" for event in self.client.events))
        envelope = json.loads((self.out / "mutation-unsigned-dsse.json").read_text())
        self.assertEqual("UNSIGNED", envelope["signature_status"])
        self.assertEqual([], envelope["signatures"])
        payload = base64.b64decode(envelope["payload"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), envelope["payload_sha256"])
        self.assertEqual("FAILED", json.loads(payload)["state"])
        decoded = json.loads(payload)
        previous = rum.digest({"source_revision": SHA, "domain": rum.DOMAIN,
                               "before_settings_sha256": rum.digest(site())})
        for link in decoded["provider_event_chain"]:
            self.assertEqual(previous, link["previous_event_sha256"])
            previous = rum.digest({"previous_event_sha256": previous, "event": link["event"]})
            self.assertEqual(previous, link["event_sha256"])
        self.assertEqual(previous, decoded["previous_event_sha256"])

    def test_apply_changes_one_field_once_and_reads_back_preservation(self):
        report = self.run_controller("apply", rum.digest(site()))
        self.assertEqual("APPLIED_SETTINGS_READBACK_VERIFIED", report["state"])
        self.assertEqual("VERIFIED_ONLY_AUTO_INSTALL_DISABLED", report["mutation_outcome"])
        puts = [event for event in self.client.calls if event["method"] == "PUT"]
        self.assertEqual(1, len(puts))
        self.assertEqual({"auto_install": False}, puts[0]["payload"])
        self.assertEqual(f"/accounts/{ACCOUNT}/rum/site_info/{SITE}", puts[0]["path"])
        expected = site()
        expected["auto_install"] = False
        self.assertEqual(expected, self.client.current)
        self.assertEqual(rum.digest(expected), report["after_settings_sha256"])
        self.assertTrue((self.out / "pre-write-admission.json").is_file())

    def test_other_setting_change_is_failed_after_single_attempt(self):
        self.client.extra_mutation = True
        report = self.run_controller("apply", rum.digest(site()))
        self.assertEqual("FAILED", report["state"])
        self.assertEqual(1, report["put_attempts"])
        self.assertNotIn("only_auto_install_changed", report)

    def test_independent_readback_detects_a_different_property_state(self):
        self.client.change_on_readback = True
        report = self.run_controller("apply", rum.digest(site()))
        self.assertEqual("FAILED", report["state"])
        self.assertIn("Readback", report["error"])
        self.assertEqual("PROVIDER_SUCCESS_RESPONSE_OBSERVED; FINAL_STATE_UNVERIFIED", report["mutation_outcome"])
        self.assertEqual(1, report["put_attempts"])

    def test_provider_reflection_of_auth_material_cannot_enter_snapshot(self):
        self.client.bearer = "NON_SECRET_TEST_FIXTURE"
        self.client.current["created"] = self.client.bearer
        report = self.run_controller()
        self.assertEqual("FAILED", report["state"])
        self.assertFalse((self.out / "before-settings.json").exists())
        self.assertNotIn(self.client.bearer, (self.out / "receipt.json").read_text())
        self.assert_no_put()

    def test_missing_exact_source_revision_refuses_before_network(self):
        with self.assertRaisesRegex(rum.Refused, "source revision"):
            rum.operate(self.client, "audit", "", self.out, "UNAVAILABLE")
        self.assertEqual([], self.client.events)

    def test_already_disabled_does_not_write(self):
        self.client.current["auto_install"] = False
        self.client.properties[0]["auto_install"] = False
        report = self.run_controller("apply", rum.digest(self.client.current))
        self.assertEqual("ALREADY_DISABLED_READ_ONLY", report["state"])
        self.assert_no_put()

    def test_apply_missing_prior_hash_refuses_before_network(self):
        with self.assertRaises(rum.Refused):
            self.run_controller("apply")
        self.assertEqual([], self.client.events)


class TransportTests(unittest.TestCase):
    def test_http403_records_codes_without_provider_text_or_credentials(self):
        client = rum.Client("NON_SECRET_TEST_FIXTURE")
        error = urllib.error.HTTPError(rum.API + "/zones", 403, "Forbidden", {},
            io.BytesIO(b'{"success":false,"errors":[{"code":9109,"message":"NON_SECRET_TEST_FIXTURE"}]}'))
        with patch.object(client.opener, "open", side_effect=error):
            with self.assertRaisesRegex(rum.Refused, "HTTP 403") as caught:
                client.request("GET", "/zones")
        self.assertNotIn("NON_SECRET_TEST_FIXTURE", str(caught.exception))
        self.assertEqual([9109], client.events[0]["provider_error_codes"])
        self.assertEqual(1, len(client.events))

    def test_redirect_handler_never_creates_a_followup_request(self):
        self.assertIsNone(rum.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://other.invalid"))

    def test_duplicate_keys_and_nonfinite_json_refused(self):
        for raw in (b'{"success":true,"success":false}', b'{"value":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(rum.Refused):
                rum.strict_json(raw)

    def test_response_byte_limit_and_total_budget_fail_closed(self):
        client = rum.Client("NON_SECRET_TEST_FIXTURE")
        with self.assertRaisesRegex(rum.Refused, "byte limit"):
            client.read_bounded(io.BytesIO(b"x" * (rum.MAX_BYTES + 1)))
        client.deadline = 0
        with self.assertRaisesRegex(rum.Refused, "deadline"):
            client.read_bounded(io.BytesIO(b"{}"))

    def test_unrecognized_field_values_are_hashed_in_public_projection(self):
        value = site()
        value["unexpected_metadata"] = {"private_value": "DO_NOT_EMIT_TEST_FIXTURE"}
        projected = rum.safe_settings(value)
        self.assertNotIn("DO_NOT_EMIT_TEST_FIXTURE", json.dumps(projected))
        self.assertIn("undocumented_fields_sha256", projected)


if __name__ == "__main__":
    unittest.main()
