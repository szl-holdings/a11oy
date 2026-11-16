#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Network-free scope, disclosure, and completeness regressions."""

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.parse
import uuid
from pathlib import Path
from unittest import mock

from scripts import audit_cloudflare_massed_ingress as audit

FIXTURE_TOKEN = "fixture-not-a-live-cloudflare-credential"
APP = "00000000-0000-0000-0000-000000000001"
SERVICE = "00000000-0000-0000-0000-000000000002"
POLICY = "00000000-0000-0000-0000-000000000003"
AUDIENCE = "a" * 64


class Response(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.status = status

    def getcode(self):
        return self.status


class Opener:
    def __init__(self, callback):
        self.callback = callback
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.callback(request)


def envelope(result, page=1, total=None):
    value = {"success": True, "result": result}
    if isinstance(result, list):
        value["result_info"] = {
            "page": page, "per_page": audit.PAGE_SIZE,
            "total_count": len(result) if total is None else total,
        }
    return value


def fixture(extra_apps=0):
    payloads = {
        audit.TUNNELS: envelope([{
            "id": audit.TUNNEL, "name": "reader@example.invalid", "status": "healthy",
            "config_src": "cloudflare", "token": "fixture-connector-secret",
        }]),
        audit.CONFIG: envelope({
            "version": 7, "source": "cloudflare",
            "config": {
                "originRequest": {"access": {
                    "required": True, "teamName": "fixture-team", "audTag": [AUDIENCE],
                }},
                "ingress": [{
                    "hostname": "massed.example.invalid", "path": "/fixture-private-path",
                    "service": "https://fixture-user:fixture-password@127.0.0.1:8091/"
                               "fixture-path-secret?client_secret=fixture-query-secret#fixture-fragment",
                    "originRequest": {"httpHostHeader": "reader@example.invalid",
                                      "noTLSVerify": False},
                }, {"service": "http_status:404"}],
                "client_secret": "fixture-config-secret",
            },
        }),
        audit.ORGANIZATION: envelope({
            "auth_domain": "fixture-team.cloudflareaccess.com",
            "name": "reader@example.invalid", "private_key": "fixture-organization-secret",
        }),
        audit.APPS: envelope([{
            "id": APP, "name": "Massed reader@example.invalid",
            "domain": "massed.example.invalid/private", "type": "self_hosted", "aud": AUDIENCE,
            "client_secret": "fixture-app-secret", "client_id": "fixture-client-id",
            "destinations": [{"type": "public", "uri": "*.example.invalid/private"}],
        }]),
        audit.TOKENS: envelope([{
            "id": SERVICE, "name": "reader@example.invalid",
            "client_id": "fixture-client-id", "client_secret": "fixture-service-secret",
            "created_at": "2026-01-01T00:00:00Z", "expires_at": "2027-01-01T00:00:00Z",
        }]),
        f"{audit.APPS}/{APP}/policies": envelope([{
            "id": POLICY, "name": "reader@example.invalid", "decision": "non_identity",
            "precedence": 1, "include": [
                {"service_token": {"token_id": SERVICE, "secret": "fixture-selector-secret"}},
                {"email": {"email": "reader@example.invalid"}},
                {"reader@example.invalid": {"token": "fixture-unrecognized-secret"}},
            ],
            "exclude": [], "require": [{"group": {"id": APP}}],
            "approval_groups": [{"email_addresses": ["reader@example.invalid"]}],
        }]),
    }
    for index in range(extra_apps):
        app_id = str(uuid.UUID(int=100 + index))
        payloads[audit.APPS]["result"].append(
            {"id": app_id, "name": "massed", "domain": f"extra{index}.example.invalid"}
        )
        payloads[f"{audit.APPS}/{app_id}/policies"] = envelope([])
    payloads[audit.APPS]["result_info"]["total_count"] = len(payloads[audit.APPS]["result"])

    def callback(request):
        path = urllib.parse.urlsplit(request.full_url).path.removeprefix("/client/v4")
        return Response(payloads[path])

    return payloads, Opener(callback)


class TransportTests(unittest.TestCase):
    def test_get_only_exact_scope_and_header_placement(self):
        _, opener = fixture()
        client = audit.Client(FIXTURE_TOKEN, opener)
        result = audit.audit(client)
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(len(opener.requests), 6)
        for request, timeout in opener.requests:
            parsed = urllib.parse.urlsplit(request.full_url)
            self.assertEqual((parsed.scheme, parsed.netloc), ("https", "api.cloudflare.com"))
            self.assertTrue(parsed.path.startswith("/client/v4" + audit.PREFIX + "/"))
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertEqual(timeout, audit.TIMEOUT)
            self.assertEqual(request.get_header("Authorization"), "Bearer " + FIXTURE_TOKEN)
            self.assertNotIn(FIXTURE_TOKEN, request.full_url)

    def test_unapproved_paths_never_reach_transport(self):
        opener = Opener(lambda request: self.fail("Unapproved network request"))
        client = audit.Client(FIXTURE_TOKEN, opener)
        paths = [
            "https://example.invalid/" + audit.ACCOUNT,
            "//example.invalid/path", "/user/tokens/verify",
            audit.TUNNELS + "/" + audit.TUNNEL + "/token",
            audit.TOKENS + "/" + SERVICE,
            audit.PREFIX + "/access/service_tokens/" + SERVICE + "/rotate",
            "/accounts/" + "0" * 32 + "/access/apps",
            audit.CONFIG + "?redirect=https://example.invalid",
            audit.CONFIG + "/../token", audit.CONFIG + "%2f..%2ftoken",
        ]
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(audit.AuditError, "SCOPE_REFUSED"):
                client.get(path)
        self.assertEqual(opener.requests, [])
        self.assertEqual(client.calls, 0)

    def test_policy_reads_require_discovered_admitted_id(self):
        opener = Opener(lambda request: Response(envelope([])))
        client = audit.Client(FIXTURE_TOKEN, opener)
        with self.assertRaisesRegex(audit.AuditError, "SCOPE_REFUSED"):
            client.get(f"{audit.APPS}/{APP}/policies", 1)
        with self.assertRaisesRegex(audit.AuditError, "POLICY_SCOPE_LIMIT"):
            client.admit_policy_app("../service_tokens")
        client.admit_policy_app(APP)
        client.get(f"{audit.APPS}/{APP}/policies", 1)
        self.assertEqual(len(opener.requests), 1)

    def test_redirects_are_refused_without_following_or_disclosing_target(self):
        opener = Opener(lambda request: Response(b"fixture-redirect-secret", 302))
        client = audit.Client(FIXTURE_TOKEN, opener)
        with self.assertRaisesRegex(audit.AuditError, "REDIRECT_REFUSED") as caught:
            client.get(audit.CONFIG)
        self.assertNotIn("fixture-redirect-secret", json.dumps(caught.exception.public()))
        self.assertEqual(len(opener.requests), 1)
        with self.assertRaisesRegex(audit.AuditError, "REDIRECT_REFUSED"):
            audit.NoRedirect().redirect_request(
                None, None, 307, "fixture-error-secret", {}, "https://example.invalid"
            )

    def test_default_transport_does_not_inherit_environment_proxies(self):
        with mock.patch("urllib.request.build_opener") as builder:
            audit.Client(FIXTURE_TOKEN)
        handlers = builder.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], audit.NoRedirect)

    def test_error_response_exposes_only_numeric_codes(self):
        opener = Opener(lambda request: Response({
            "success": False, "errors": [
                {"code": 10000, "message": FIXTURE_TOKEN, "secret": "fixture-error-secret"},
                {"code": "reader@example.invalid"},
            ],
        }, 403))
        with self.assertRaises(audit.AuditError) as caught:
            audit.Client(FIXTURE_TOKEN, opener).get(audit.CONFIG)
        self.assertEqual(caught.exception.public(), {
            "status": "PERMISSION_DENIED", "complete": False,
            "http_status": 403, "error_codes": [10000],
        })

    def test_invalid_json_does_not_echo_body(self):
        opener = Opener(lambda request: Response(b"reader@example.invalid fixture-html-secret"))
        with self.assertRaises(audit.AuditError) as caught:
            audit.Client(FIXTURE_TOKEN, opener).get(audit.CONFIG)
        self.assertEqual(caught.exception.code, "INVALID_JSON")
        self.assertNotIn("fixture-html-secret", str(caught.exception))

    def test_response_limit_is_enforced(self):
        opener = Opener(lambda request: Response(b"x" * 65))
        with mock.patch.object(audit, "MAX_BYTES", 64):
            with self.assertRaisesRegex(audit.AuditError, "RESPONSE_TOO_LARGE"):
                audit.Client(FIXTURE_TOKEN, opener).get(audit.CONFIG)

    def test_request_budget_and_deadline_stop_new_requests(self):
        opener = Opener(lambda request: Response(envelope({})))
        client = audit.Client(FIXTURE_TOKEN, opener)
        with mock.patch.object(audit, "MAX_REQUESTS", 2):
            client.get(audit.CONFIG)
            client.get(audit.CONFIG)
            with self.assertRaisesRegex(audit.AuditError, "REQUEST_LIMIT"):
                client.get(audit.CONFIG)
        self.assertEqual(len(opener.requests), 2)
        clock = mock.Mock(side_effect=[0, audit.DEADLINE_SECONDS + 1])
        expired = audit.Client(FIXTURE_TOKEN, opener, clock=clock)
        with self.assertRaisesRegex(audit.AuditError, "DEADLINE_EXCEEDED"):
            expired.get(audit.CONFIG)
        self.assertEqual(expired.calls, 0)

    def test_deadline_also_applies_while_reading_body(self):
        clock = mock.Mock(side_effect=[0, 0, audit.DEADLINE_SECONDS + 1])
        opener = Opener(lambda request: Response(envelope({})))
        with self.assertRaisesRegex(audit.AuditError, "DEADLINE_EXCEEDED"):
            audit.Client(FIXTURE_TOKEN, opener, clock=clock).get(audit.CONFIG)


class CoverageTests(unittest.TestCase):
    def test_page_limit_is_explicit_and_bounded(self):
        def callback(request):
            page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)["page"][0])
            items = [{"id": str(uuid.UUID(int=page * 1000 + n))} for n in range(100)]
            return Response(envelope(items, page=page, total=301))
        opener = Opener(callback)
        result, _ = audit.collection(audit.Client(FIXTURE_TOKEN, opener), audit.APPS, audit.application_metadata)
        self.assertEqual((result["status"], result["complete"]), ("PAGE_LIMIT", False))
        self.assertEqual(len(opener.requests), audit.MAX_PAGES)

    def test_missing_pagination_cannot_claim_complete(self):
        opener = Opener(lambda request: Response({"success": True, "result": [{"id": APP}]}))
        result, _ = audit.collection(audit.Client(FIXTURE_TOKEN, opener), audit.APPS, audit.application_metadata)
        self.assertEqual(result["status"], "PAGINATION_UNVERIFIED")
        self.assertFalse(result["complete"])

    def test_inconsistent_totals_and_duplicate_ids_fail_closed(self):
        body = envelope([{"id": APP}], total=2)
        body["result_info"]["total_pages"] = 1
        opener = Opener(lambda request: Response(body))
        result, _ = audit.collection(audit.Client(FIXTURE_TOKEN, opener), audit.APPS, audit.application_metadata)
        self.assertEqual(result["status"], "INCOMPLETE_PAGINATION")
        opener = Opener(lambda request: Response(envelope([{"id": APP}, {"id": APP}])))
        result, _ = audit.collection(audit.Client(FIXTURE_TOKEN, opener), audit.APPS, audit.application_metadata)
        self.assertEqual(result["status"], "DUPLICATE_RESOURCE_ID")

    def test_permission_gap_is_incomplete_without_losing_other_observations(self):
        payloads, opener = fixture()
        payloads[audit.APPS] = {"success": False, "errors": [{"code": 10000}]}
        result = audit.audit(audit.Client(FIXTURE_TOKEN, opener))
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["observations"]["applications"]["status"], "API_ERROR")
        self.assertTrue(result["observations"]["target_configuration"]["complete"])

    def test_relevant_policy_limit_is_not_silently_complete(self):
        _, opener = fixture(extra_apps=audit.MAX_POLICY_APPS)
        result = audit.audit(audit.Client(FIXTURE_TOKEN, opener))
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("RELEVANT_APPLICATION_LIMIT", result["issues"])
        self.assertEqual(len(result["application_policies"]), audit.MAX_POLICY_APPS)
        self.assertLessEqual(result["request_count"], audit.MAX_REQUESTS)

    def test_unrelated_app_does_not_expand_policy_scope(self):
        payloads, opener = fixture()
        payloads[audit.APPS] = envelope([{"id": APP, "name": "Unrelated", "domain": "elsewhere.invalid"}])
        result = audit.audit(audit.Client(FIXTURE_TOKEN, opener))
        self.assertEqual(result["application_policies"], [])
        self.assertEqual(len(opener.requests), 5)


class DisclosureTests(unittest.TestCase):
    def test_artifact_allowlist_omits_secrets_emails_and_url_credentials(self):
        _, opener = fixture()
        result = audit.audit(audit.Client(FIXTURE_TOKEN, opener))
        serialized = json.dumps(result)
        for forbidden in [
            FIXTURE_TOKEN, "reader@example.invalid", "fixture-client-id",
            "fixture-user", "fixture-password", "fixture-path-secret",
            "fixture-query-secret", "fixture-fragment", "fixture-private-path",
            "fixture-connector-secret", "fixture-config-secret", "fixture-app-secret",
            "fixture-service-secret", "fixture-selector-secret", "fixture-unrecognized-secret",
            "fixture-organization-secret", "Authorization", "client_secret", "private_key",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)
        target = result["observations"]["target_configuration"]["item"]
        self.assertEqual(target["ingress"][0]["origin"]["endpoint"], "https://127.0.0.1:8091")
        self.assertTrue(target["ingress"][0]["origin"]["path_present"])
        self.assertEqual(target["default_access"]["audiences"], [AUDIENCE])
        policy = result["application_policies"][0]["items"][0]
        self.assertEqual(policy["selectors"]["include"]["service_token_ids"], [SERVICE])
        self.assertIn("email", policy["selectors"]["include"]["types"])
        self.assertIn("unrecognized", policy["selectors"]["include"]["types"])
        self.assertEqual(result["security_verdict"], "NOT_EVALUATED")
        self.assertEqual(result["signature"], "UNSIGNED")

    def test_origin_projection_strips_path_userinfo_query_fragment_and_ipv6_is_valid(self):
        self.assertEqual(
            audit.origin("http://user:fixture-password@[::1]:8091/private?token=x#fragment"),
            {"endpoint": "http://[::1]:8091", "path_present": True},
        )
        self.assertIsNone(audit.origin("unix:/private/fixture-secret.sock")["endpoint"])
        self.assertIsNone(audit.origin("https://reader@example.invalid:bad/")["endpoint"])
        self.assertIsNone(audit.domain_host("reader@example.invalid"))

    def test_missing_credential_writes_honest_blocked_report_without_network(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {}, clear=True):
            report = Path(directory) / "audit.json"
            with mock.patch.object(audit, "Client") as client, contextlib.redirect_stdout(io.StringIO()):
                code = audit.main(["--report", str(report)])
            client.assert_not_called()
            result = json.loads(report.read_text())
            self.assertEqual((code, result["status"]), (2, "BLOCKED"))
            self.assertEqual(result["issues"], ["CREDENTIAL_UNAVAILABLE"])

    def test_unexpected_exception_message_is_never_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "audit.json"
            console = io.StringIO()
            with mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": FIXTURE_TOKEN}):
                with mock.patch.object(audit, "audit", side_effect=RuntimeError(FIXTURE_TOKEN)):
                    with contextlib.redirect_stdout(console):
                        code = audit.main(["--report", str(report)])
            self.assertEqual(code, 2)
            self.assertNotIn(FIXTURE_TOKEN, console.getvalue() + report.read_text())
            self.assertIn("INTERNAL_ERROR", report.read_text())

    def test_cli_exposes_no_scope_or_method_override(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                audit.main(["--report", "unused.json", "--url", "https://example.invalid", "--method", "POST"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
