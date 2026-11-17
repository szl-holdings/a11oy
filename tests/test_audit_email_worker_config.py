# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise malformed metadata, fixed transport, and secret-safe projections offline."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("email_audit", ROOT / "scripts/audit_email_worker_config.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
SHA = "1" * 40
ACCOUNT = "a" * 32
SENDER = "betterwithage@a-11-oy.com"
MARKER = "private-value-must-never-appear"


def settings():
    return {"success": True, "result": {"bindings": [
        {"name": "MAIL_FROM", "type": "plain_text", "text": SENDER},
        {"name": "SEND_EMAIL", "type": "send_email"},
        {"name": "SOURCE_REVISION", "type": "plain_text", "text": SHA},
    ]}}


def secret():
    return {"success": True, "result": {"name": "API_SECRET", "type": "secret_text", "text": MARKER}}


class Response(io.BytesIO):
    headers = {}


class Opener:
    def __init__(self, body=None, error=None):
        self.body = body or json.dumps(settings()).encode()
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if self.error:
            raise self.error
        return Response(self.body)


class AuditTests(unittest.TestCase):
    def test_success_is_metadata_only_and_does_not_export_values(self):
        before = settings()
        before["result"]["bindings"].append({"name": "PRIVATE_EXTRA", "type": "plain_text", "text": MARKER})
        result = audit.summarize(before, copy.deepcopy(before), secret(), SHA, SENDER)
        self.assertEqual(result["status"], "METADATA_PRESENT_RUNTIME_UNPROVED")
        self.assertFalse(result["runtime_readiness_proved"])
        self.assertFalse(result["api_secret_length_verified"])
        for value in (MARKER, SENDER, "PRIVATE_EXTRA"):
            self.assertNotIn(value, json.dumps(result))

    def test_missing_secret_is_distinct_from_failed_metadata(self):
        result = audit.summarize(settings(), settings(), audit.NOT_FOUND, SHA, SENDER)
        self.assertEqual(result["api_secret_metadata"], "NOT_FOUND")
        self.assertEqual(result["status"], "CONFIGURATION_METADATA_BLOCKED")
        with self.assertRaisesRegex(audit.AuditError, "SECRET_METADATA_INVALID"):
            audit.summarize(settings(), settings(), {"result": []}, SHA, SENDER)

    def test_secret_type_is_not_exported_and_does_not_prove_length(self):
        value = secret()
        value["result"]["type"] = MARKER
        result = audit.summarize(settings(), settings(), value, SHA, SENDER)
        self.assertEqual(result["api_secret_metadata"], "UNEXPECTED_TYPE")
        self.assertNotIn(MARKER, json.dumps(result))

    def test_contradictory_secret_presence_is_refused(self):
        value = settings()
        value["result"]["bindings"].append({"name": "API_SECRET", "type": "secret_text"})
        with self.assertRaisesRegex(audit.AuditError, "SECRET_METADATA_CONTRADICTION"):
            audit.summarize(value, value, audit.NOT_FOUND, SHA, SENDER)

    def test_changed_metadata_and_duplicate_bindings_are_refused(self):
        after = settings()
        after["result"]["bindings"][2]["text"] = "2" * 40
        with self.assertRaisesRegex(audit.AuditError, "WORKER_METADATA_CHANGED_DURING_AUDIT"):
            audit.summarize(settings(), after, secret(), SHA, SENDER)
        after = settings()
        after["result"]["bindings"].append(after["result"]["bindings"][0])
        with self.assertRaisesRegex(audit.AuditError, "DUPLICATE_BINDING"):
            audit.bindings(after)

    def test_arbitrary_revision_and_sender_values_are_not_exported(self):
        value = settings()
        value["result"]["bindings"][0]["text"] = MARKER
        value["result"]["bindings"][2]["text"] = MARKER
        result = audit.summarize(value, value, secret(), SHA, SENDER)
        self.assertIsNone(result["source_revision"])
        self.assertFalse(result["mail_from_matches_repository"])
        self.assertFalse(result["expected_revision_matches"])
        self.assertNotIn(MARKER, json.dumps(result))
        value["result"]["bindings"][2]["text"] = "f" * 40
        result = audit.summarize(value, value, secret(), SHA, SENDER)
        self.assertIsNone(result["source_revision"])
        self.assertNotIn("f" * 40, json.dumps(result))

    def test_complete_audit_uses_four_fixed_gets_and_repository_contract(self):
        class ScriptedOpener(Opener):
            def open(self, request, timeout):
                self.requests.append(request)
                if request.full_url.endswith("/accounts?page=1&per_page=5"):
                    payload = {"success": True, "result": [{"id": ACCOUNT}],
                               "result_info": {"per_page": 5, "count": 1, "page": 1, "total_count": 1}}
                elif request.full_url.endswith("/secrets/API_SECRET"):
                    payload = secret()
                else:
                    payload = settings()
                return Response(json.dumps(payload).encode())
        opener = ScriptedOpener()
        client = audit.MetadataClient(MARKER, opener)
        result = audit.audit(client, "", SHA, ROOT / "ops/email-sender-worker/wrangler.toml")
        self.assertEqual(client.requests, 4)
        self.assertEqual(result["status"], "METADATA_PRESENT_RUNTIME_UNPROVED")
        self.assertTrue(result["metadata_unchanged_between_reads"])
        self.assertNotIn(MARKER, json.dumps(result))

    def test_decoder_bounds_duplicates_nonfinite_and_error_content(self):
        cases = (b'x' * (audit.MAX_BODY + 1), b'{"success":true,"success":true}',
                 b'{"success":true,"result":NaN}', b'{"success":false,"errors":["private"]}', b'\xff')
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(audit.AuditError):
                audit.decode(raw)

    def test_only_fixed_get_targets_and_four_requests_are_available(self):
        opener = Opener()
        client = audit.MetadataClient(MARKER, opener)
        path = "/accounts/" + ACCOUNT + "/workers/scripts/szl-email-sender/settings"
        for _ in range(4):
            client.get(path)
        self.assertTrue(all(request.get_method() == "GET" and request.data is None for request in opener.requests))
        with self.assertRaisesRegex(audit.AuditError, "REQUEST_BUDGET_EXCEEDED"):
            client.get(path)
        with self.assertRaisesRegex(audit.AuditError, "API_TARGET_REFUSED"):
            audit.MetadataClient(MARKER, Opener()).get("https://example.org/collect")

    def test_redirect_and_http_errors_never_become_absent_secrets(self):
        with self.assertRaisesRegex(audit.AuditError, "API_REDIRECT_REFUSED"):
            audit.NoRedirect().redirect_request(None)
        path = "/accounts/" + ACCOUNT + "/workers/scripts/szl-email-sender/secrets/API_SECRET"
        for code in (401, 403, 429, 500):
            error = urllib.error.HTTPError("https://api.cloudflare.com/", code, MARKER, {}, None)
            with self.subTest(code=code), self.assertRaisesRegex(audit.AuditError, "API_HTTP_READ_FAILED"):
                audit.MetadataClient(MARKER, Opener(error=error)).get(path, allow_missing_secret=True)
        error = urllib.error.HTTPError("https://api.cloudflare.com/", 404, MARKER, {}, None)
        self.assertIs(audit.MetadataClient(MARKER, Opener(error=error)).get(path, allow_missing_secret=True), audit.NOT_FOUND)

    def test_ambiguous_or_boolean_account_pagination_is_refused(self):
        class Client:
            def get(self, _path):
                return {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"total_count": True}}
        with self.assertRaisesRegex(audit.AuditError, "SINGLE_ACCOUNT_REQUIRED"):
            audit.account_id(Client(), "")
        with self.assertRaisesRegex(audit.AuditError, "ACCOUNT_ID_INVALID"):
            audit.account_id(Client(), MARKER)

    def test_expected_revision_is_checked_before_network(self):
        class Client:
            def get(self, *_args, **_kwargs):
                self.fail("unexpected network")
        with self.assertRaisesRegex(audit.AuditError, "EXPECTED_REVISION_INVALID"):
            audit.audit(Client(), ACCOUNT, MARKER, ROOT / "ops/email-sender-worker/wrangler.toml")

    def test_unexpected_errors_have_content_free_cli_output(self):
        output = io.StringIO()
        with patch.object(audit, "MetadataClient", side_effect=RuntimeError(MARKER)), contextlib.redirect_stdout(output):
            self.assertEqual(audit.main(["--expect-revision", SHA]), 2)
        self.assertNotIn(MARKER, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["reason"], "BOUNDED_METADATA_AUDIT_FAILED")


if __name__ == "__main__":
    unittest.main()
