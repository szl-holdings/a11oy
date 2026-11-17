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

    def test_cli_exposes_no_arbitrary_target_or_method_override(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                audit.main(["--report", "unused.json", "--url", "https://example.invalid", "--method", "POST"])
        self.assertEqual(caught.exception.code, 2)



GATEWAY_ZONE_ID = "1" * 32
GATEWAY_ACCOUNT_ID = "2" * 32
GATEWAY_RECORD_ID = "3" * 32


def gateway_page(items, *, page=1, total=None, page_size=100):
    count = len(items) if total is None else total
    return {
        "success": True, "result": items,
        "result_info": {
            "page": page, "per_page": page_size, "count": len(items),
            "total_count": count, "total_pages": max(1, (count + page_size - 1) // page_size),
        },
    }


def gateway_fixture():
    dns = f"/zones/{GATEWAY_ZONE_ID}/dns_records"
    tunnel = f"/accounts/{GATEWAY_ACCOUNT_ID}/cfd_tunnel/{audit.WINDOWS_TUNNEL}"
    payloads = {
        audit.ZONES: gateway_page([{
            "id": GATEWAY_ZONE_ID, "name": audit.ZONE_NAME, "status": "active",
            "account": {"id": GATEWAY_ACCOUNT_ID, "name": "reader@example.invalid"},
            "owner": {"email": "reader@example.invalid"},
        }], page_size=audit.ZONE_PAGE_SIZE),
        dns: gateway_page([{
            "id": GATEWAY_RECORD_ID, "zone_id": GATEWAY_ZONE_ID,
            "name": audit.GATEWAY_HOSTNAME, "type": "CNAME",
            "content": audit.GATEWAY_CNAME, "proxied": True, "ttl": 1,
            "comment": "fixture-dns-private-comment",
            "tags": ["fixture-dns-private-tag"],
        }]),
        tunnel: envelope({
            "id": audit.WINDOWS_TUNNEL, "account_tag": GATEWAY_ACCOUNT_ID,
            "status": "healthy", "config_src": "cloudflare",
            "name": "reader@example.invalid", "token": "fixture-tunnel-secret",
        }),
        tunnel + "/configurations": envelope({
            "account_id": GATEWAY_ACCOUNT_ID, "tunnel_id": audit.WINDOWS_TUNNEL,
            "version": 7, "source": "cloudflare",
            "config": {
                "client_secret": "fixture-config-secret",
                "ingress": [
                    {"hostname": audit.GATEWAY_HOSTNAME, "service": "http://localhost:4000"},
                    {"service": "http_status:404"},
                ],
            },
        }),
    }

    def callback(request):
        path = urllib.parse.urlsplit(request.full_url).path.removeprefix("/client/v4")
        if path not in payloads:
            raise AssertionError("Unexpected provider resource")
        body = payloads[path]
        return Response(body[0], body[1]) if isinstance(body, tuple) else Response(body)

    return payloads, Opener(callback), dns, tunnel


class GatewayProfileTests(unittest.TestCase):
    def run_gateway(self, payloads=None, opener=None):
        if opener is None:
            payloads, opener, _, _ = gateway_fixture()
        client = audit.Client(FIXTURE_TOKEN, opener, profile="windows-gateway")
        return audit.audit_gateway(client), opener

    def test_exact_binding_uses_resolved_account_and_four_gets(self):
        payloads, opener, dns, tunnel = gateway_fixture()
        result, _ = self.run_gateway(payloads, opener)
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["request_count"], 4)
        self.assertEqual(result["resolved_account_id"], GATEWAY_ACCOUNT_ID)
        self.assertNotEqual(GATEWAY_ACCOUNT_ID, audit.ACCOUNT)
        paths = []
        for request, timeout in opener.requests:
            url = urllib.parse.urlsplit(request.full_url)
            self.assertEqual((url.scheme, url.netloc), ("https", "api.cloudflare.com"))
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertEqual(request.get_header("Authorization"), "Bearer " + FIXTURE_TOKEN)
            self.assertEqual(timeout, audit.TIMEOUT)
            paths.append(url.path.removeprefix("/client/v4"))
        self.assertEqual(paths, [audit.ZONES, dns, tunnel, tunnel + "/configurations"])
        zone_query = urllib.parse.parse_qs(urllib.parse.urlsplit(opener.requests[0][0].full_url).query)
        self.assertEqual(zone_query, {
            "name": [audit.ZONE_NAME], "status": ["active"], "match": ["all"],
            "page": ["1"], "per_page": ["50"],
        })
        dns_query = urllib.parse.parse_qs(urllib.parse.urlsplit(opener.requests[1][0].full_url).query)
        self.assertEqual(dns_query, {
            "name.exact": [audit.GATEWAY_HOSTNAME], "match": ["all"],
            "page": ["1"], "per_page": ["100"],
        })
        self.assertEqual(result["binding"]["dns"], "MATCHED_CONFIGURATION_ONLY")
        self.assertEqual(result["binding"]["ingress"]["status"], "MATCHED_CONFIGURATION_ONLY")
        self.assertEqual(result["windows_connector_identity"], "NOT_ESTABLISHED")
        self.assertFalse(result["origin_probed"])
        self.assertFalse(result["provider_mutations"])
        self.assertEqual(result["security_verdict"], "NOT_EVALUATED")

    def test_empty_or_ambiguous_zone_stops_before_account_reads(self):
        for count in (0, 2):
            with self.subTest(count=count):
                payloads, opener, _, _ = gateway_fixture()
                prototype = payloads[audit.ZONES]["result"][0]
                rows = [{**prototype, "id": f"{n + 1:032x}"} for n in range(count)]
                payloads[audit.ZONES] = gateway_page(rows, page_size=audit.ZONE_PAGE_SIZE)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(len(opener.requests), 1)
                self.assertNotIn("resolved_account_id", result)

    def test_zone_wrong_name_status_or_id_does_not_expand_scope(self):
        changes = [
            {"name": "unrelated.invalid"}, {"status": "pending"}, {"status": True},
            {"id": APP}, {"id": "../dns_records"}, {"account": {"id": APP}},
            {"account": []}, {"account": {"id": "2" * 31}},
        ]
        for change in changes:
            with self.subTest(change=change):
                payloads, opener, _, _ = gateway_fixture()
                payloads[audit.ZONES]["result"][0].update(change)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(len(opener.requests), 1)
                self.assertNotIn("resolved_zone_id", result)

    def test_zone_pagination_missing_inconsistent_or_boolean_is_not_complete(self):
        infos = [
            {}, {"page": True, "total_count": 1},
            {"page": 1, "per_page": 100, "total_count": 1},
            {"page": 1, "total_count": 1, "total_pages": 2},
            {"page": 1, "total_count": True},
            {"page": 1, "count": 2, "total_count": 1},
            {"page": 1, "total_count": 10 ** 1000},
        ]
        for info in infos:
            with self.subTest(info=info):
                payloads, opener, _, _ = gateway_fixture()
                payloads[audit.ZONES]["result_info"] = info
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(len(opener.requests), 1)


    def test_strict_pagination_rejects_zero_page_rows_and_regressing_page_totals(self):
        for target in ("zone", "dns"):
            with self.subTest(target=target):
                payloads, opener, dns, _ = gateway_fixture()
                path = audit.ZONES if target == "zone" else dns
                info = payloads[path]["result_info"]
                info.pop("total_count")
                info["total_pages"] = 0
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(
                    result["observations"][target]["status"], "INCONSISTENT_PAGINATION"
                )
                if target == "zone":
                    self.assertEqual(len(opener.requests), 1)

        first = {"id": GATEWAY_ZONE_ID, "name": audit.ZONE_NAME, "status": "active",
                 "account": {"id": GATEWAY_ACCOUNT_ID}}
        second = {**first, "id": "4" * 32}
        pages = {}
        for page, row, total_pages in ((1, first, 2), (2, second, 1)):
            payload = gateway_page([row], page=page, page_size=audit.ZONE_PAGE_SIZE)
            payload["result_info"].pop("total_count")
            payload["result_info"]["total_pages"] = total_pages
            pages[page] = payload

        def callback(request):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            return Response(pages[int(query["page"][0])])

        client = audit.Client(FIXTURE_TOKEN, Opener(callback), profile="windows-gateway")
        result, _ = audit.collection(
            client, audit.ZONES, audit.gateway_zone_metadata,
            id_parser=audit.cloudflare_identifier, page_size=audit.ZONE_PAGE_SIZE,
            strict_pagination=True,
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"], "INCONSISTENT_PAGINATION")
        self.assertEqual(client.calls, 2)

    def test_empty_zero_page_is_complete_absence_without_establishing_binding(self):
        for target in ("zone", "dns"):
            with self.subTest(target=target):
                payloads, opener, dns, _ = gateway_fixture()
                path = audit.ZONES if target == "zone" else dns
                payloads[path]["result"] = []
                payloads[path]["result_info"].update(count=0, total_pages=0)
                payloads[path]["result_info"].pop("total_count")
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertTrue(result["observations"][target]["complete"])
                expected = "ACTIVE_ZONE_NOT_OBSERVED" if target == "zone" else "GATEWAY_DNS_ABSENT"
                self.assertIn(expected, result["issues"])

    def test_duplicate_zone_ids_are_not_unique_scope(self):
        payloads, opener, _, _ = gateway_fixture()
        row = payloads[audit.ZONES]["result"][0]
        payloads[audit.ZONES] = gateway_page([row, dict(row)], page_size=audit.ZONE_PAGE_SIZE)
        result, _ = self.run_gateway(payloads, opener)
        self.assertEqual(result["observations"]["zone"]["status"], "DUPLICATE_RESOURCE_ID")
        self.assertEqual(len(opener.requests), 1)

    def test_page_limit_stops_without_selecting_first_zone(self):
        def callback(request):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            page = int(query["page"][0])
            rows = [{
                "id": f"{page * 100 + n:032x}", "name": audit.ZONE_NAME,
                "status": "active", "account": {"id": GATEWAY_ACCOUNT_ID},
            } for n in range(50)]
            return Response(gateway_page(rows, page=page, total=151, page_size=50))
        opener = Opener(callback)
        result, _ = self.run_gateway(opener=opener)
        self.assertEqual(result["observations"]["zone"]["status"], "PAGE_LIMIT")
        self.assertEqual(len(opener.requests), 3)
        self.assertNotIn("resolved_account_id", result)

    def test_changing_pagination_totals_are_unresolved(self):
        def callback(request):
            page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)["page"][0])
            rows = [{
                "id": f"{page * 100 + n:032x}", "name": audit.ZONE_NAME,
                "status": "active", "account": {"id": GATEWAY_ACCOUNT_ID},
            } for n in range(50)]
            return Response(gateway_page(rows, page=page, total=101 if page == 1 else 102, page_size=50))
        result, opener = self.run_gateway(opener=Opener(callback))
        self.assertEqual(result["observations"]["zone"]["status"], "INCONSISTENT_PAGINATION")
        self.assertEqual(len(opener.requests), 2)

    def test_exact_dns_absence_mismatch_or_ambiguity_is_reported(self):
        for change in ("absent", "duplicate_name", "wrong_target", "wrong_name", "wrong_zone", "uuid_id", "address"):
            with self.subTest(change=change):
                payloads, opener, dns, _ = gateway_fixture()
                row = payloads[dns]["result"][0]
                if change == "absent":
                    payloads[dns] = gateway_page([])
                elif change == "duplicate_name":
                    payloads[dns] = gateway_page([row, {**row, "id": "4" * 32}])
                elif change == "wrong_target":
                    row["content"] = f"{APP}.cfargotunnel.com"
                elif change == "wrong_name":
                    row["name"] = "gpu.a-11-oy.com"
                elif change == "wrong_zone":
                    row["zone_id"] = "9" * 32
                elif change == "uuid_id":
                    row["id"] = APP
                else:
                    row.update(type="A", content="127.0.0.1")
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertNotEqual(result["binding"]["dns"], "MATCHED_CONFIGURATION_ONLY")
                self.assertEqual(len(opener.requests), 4)

    def test_dns_boolean_truthiness_and_partial_pages_never_match(self):
        for value in (False, "true", 1, None):
            with self.subTest(value=value):
                payloads, opener, dns, _ = gateway_fixture()
                payloads[dns]["result"][0]["proxied"] = value
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["binding"]["dns"], "GATEWAY_DNS_PROXY_UNVERIFIED")
                self.assertEqual(result["status"], "INCOMPLETE")
        payloads, opener, dns, _ = gateway_fixture()
        payloads[dns].pop("result_info")
        result, _ = self.run_gateway(payloads, opener)
        self.assertEqual(result["observations"]["dns"]["status"], "PAGINATION_UNVERIFIED")
        self.assertEqual(result["binding"]["dns"], "DNS_READ_INCOMPLETE")

    def test_dns_ids_and_types_use_separate_validators(self):
        self.assertIsNone(audit.identifier(GATEWAY_RECORD_ID))
        self.assertEqual(audit.cloudflare_identifier(GATEWAY_RECORD_ID), GATEWAY_RECORD_ID)
        self.assertIsNone(audit.cloudflare_identifier(APP))
        for value in (True, 123, [], {}):
            with self.subTest(value=value):
                payloads, opener, dns, _ = gateway_fixture()
                payloads[dns]["result"][0].update(type="A", content=value)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["observations"]["dns"]["status"], "DNS_RECORD_CONTENT_INVALID")

    def test_tunnel_exact_id_and_full_account_must_match_before_configuration(self):
        for change in (
            {"id": APP}, {"id": None}, {"account_tag": None},
            {"account_tag": "0" * 26 + GATEWAY_ACCOUNT_ID[-6:]},
        ):
            with self.subTest(change=change):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel]["result"].update(change)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(result["binding"]["tunnel"], "TUNNEL_IDENTITY_UNVERIFIED")
                self.assertEqual(result["observations"]["configuration"]["status"], "NOT_ATTEMPTED")
                self.assertEqual(len(opener.requests), 3)

    def test_configuration_returns_its_own_observed_identities(self):
        for change in (
            {"tunnel_id": APP}, {"account_id": "0" * 26 + GATEWAY_ACCOUNT_ID[-6:]},
            {"tunnel_id": None}, {"account_id": None},
        ):
            with self.subTest(change=change):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel + "/configurations"]["result"].update(change)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(result["binding"]["ingress"]["status"], "CONFIGURATION_IDENTITY_UNVERIFIED")
                self.assertNotEqual(
                    result["observations"]["configuration"]["item"].get("tunnel_id"),
                    audit.TUNNEL,
                )

    def test_local_or_unknown_config_source_never_proves_remote_ingress(self):
        for detail_source, config_source in (
            ("local", "local"), ("local", "cloudflare"), ("cloudflare", "local"),
            (None, "cloudflare"), ("cloudflare", []),
        ):
            with self.subTest(detail_source=detail_source, config_source=config_source):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel]["result"]["config_src"] = detail_source
                payloads[tunnel + "/configurations"]["result"]["source"] = config_source
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertNotEqual(result["binding"]["ingress"]["status"], "MATCHED_CONFIGURATION_ONLY")

    def test_malformed_provider_shapes_return_incomplete_without_tracebacks(self):
        for key, value in (("status", []), ("status", True), ("config_src", {})):
            with self.subTest(key=key, value=value):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel]["result"][key] = value
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
        for value in (None, {}, [None], [{"hostname": [], "service": "http://localhost:4000"}]):
            with self.subTest(ingress=value):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel + "/configurations"]["result"]["config"]["ingress"] = value
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")

    def test_ordered_ingress_cannot_skip_shadowing_or_path_specific_rule(self):
        first_rules = [
            {"service": "http_status:404"},
            {"hostname": "*.a-11-oy.com", "service": "http://localhost:4000"},
            {"hostname": audit.GATEWAY_HOSTNAME, "path": "/private", "service": "http://localhost:4000"},
            {"hostname": audit.GATEWAY_HOSTNAME, "path": [], "service": "http://localhost:4000"},
        ]
        for first in first_rules:
            with self.subTest(first=first):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel + "/configurations"]["result"]["config"]["ingress"].insert(0, first)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertNotEqual(result["binding"]["ingress"]["status"], "MATCHED_CONFIGURATION_ONLY")
                self.assertEqual(result["binding"]["ingress"]["rule_index"], 0)

    def test_unrelated_rule_and_explicit_ipv4_ipv6_preserve_observation_scope(self):
        for service in ("http://127.0.0.1:4000", "http://[::1]:4000/", "http://localhost:4000"):
            with self.subTest(service=service):
                payloads, opener, _, tunnel = gateway_fixture()
                ingress = payloads[tunnel + "/configurations"]["result"]["config"]["ingress"]
                ingress[0]["service"] = service
                ingress.insert(0, {"hostname": "unrelated.invalid", "service": "http://127.0.0.1:9000"})
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "OBSERVED")
                self.assertEqual(result["binding"]["ingress"]["rule_index"], 1)
                self.assertFalse(result["origin_probed"])
                self.assertEqual(result["windows_connector_identity"], "NOT_ESTABLISHED")

    def test_sanitized_credential_or_path_origin_cannot_become_a_positive_match(self):
        services = [
            "http://fixture-user:fixture-password@localhost:4000",
            "http://@localhost:4000", "http://localhost:4000/private",
            "http://localhost:4000/?token=fixture-query-secret",
            "http://localhost:4000/#fixture-fragment", "http://localhost:4000/?",
            "https://localhost:4000", "http://0.0.0.0:4000",
            "http://localhost:4001", "http://remote.invalid:4000",
        ]
        for service in services:
            with self.subTest(service=service):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel + "/configurations"]["result"]["config"]["ingress"][0]["service"] = service
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(result["binding"]["ingress"]["status"], "GATEWAY_ORIGIN_OUTSIDE_FIXED_SCOPE")
                serialized = json.dumps(result)
                for secret in ("fixture-user", "fixture-password", "fixture-query-secret", "fixture-fragment"):
                    self.assertNotIn(secret, serialized)


    def test_raw_origin_controls_and_whitespace_cannot_be_normalized_into_a_match(self):
        for service in (
            "http://local\nhost:4000", "http://local\rhost:4000",
            "http://local\thost:4000", "\x00http://localhost:4000",
            "\x1fhttp://localhost:4000", " http://localhost:4000",
            "http://localhost:4000\t", "http://localhost:4000 ",
            "http://localhost:4000\x7f", "\u00a0http://localhost:4000",
        ):
            with self.subTest(service=service):
                payloads, opener, _, tunnel = gateway_fixture()
                payloads[tunnel + "/configurations"]["result"]["config"]["ingress"][0]["service"] = service
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(
                    result["binding"]["ingress"]["status"], "GATEWAY_ORIGIN_OUTSIDE_FIXED_SCOPE"
                )

    def test_raw_hostnames_reject_multiple_dots_and_controls_but_allow_dns_canonical_case(self):
        for target in ("zone", "dns_name", "cname", "ingress"):
            for suffix in ("..", "...", "\t", "\r", "\n", "\x00", " "):
                with self.subTest(target=target, suffix=suffix):
                    payloads, opener, dns, tunnel = gateway_fixture()
                    row, field = {
                        "zone": (payloads[audit.ZONES]["result"][0], "name"),
                        "dns_name": (payloads[dns]["result"][0], "name"),
                        "cname": (payloads[dns]["result"][0], "content"),
                        "ingress": (
                            payloads[tunnel + "/configurations"]["result"]["config"]["ingress"][0],
                            "hostname",
                        ),
                    }[target]
                    row[field] += suffix
                    result, _ = self.run_gateway(payloads, opener)
                    self.assertEqual(result["status"], "INCOMPLETE")
                    if target == "zone":
                        self.assertEqual(len(opener.requests), 1)
        payloads, opener, dns, tunnel = gateway_fixture()
        payloads[audit.ZONES]["result"][0]["name"] = audit.ZONE_NAME.upper() + "."
        payloads[dns]["result"][0]["name"] = audit.GATEWAY_HOSTNAME.upper() + "."
        payloads[dns]["result"][0]["content"] = audit.GATEWAY_CNAME.upper() + "."
        payloads[tunnel + "/configurations"]["result"]["config"]["ingress"][0]["hostname"] = (
            audit.GATEWAY_HOSTNAME.upper() + "."
        )
        result, _ = self.run_gateway(payloads, opener)
        self.assertEqual(result["status"], "OBSERVED")

    def test_permission_denial_retains_other_exact_observations(self):
        for target, status in (("dns", 403), ("tunnel", 401), ("configuration", 403)):
            with self.subTest(target=target):
                payloads, opener, dns, tunnel = gateway_fixture()
                path = {"dns": dns, "tunnel": tunnel, "configuration": tunnel + "/configurations"}[target]
                payloads[path] = ({"success": False, "errors": [{"code": 10000, "message": FIXTURE_TOKEN}]}, status)
                result, _ = self.run_gateway(payloads, opener)
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(result["observations"][target]["status"], "PERMISSION_DENIED")
                self.assertTrue(result["observations"]["zone"]["complete"])
                self.assertNotIn(FIXTURE_TOKEN, json.dumps(result))

    def test_gateway_scope_requires_binding_and_rejects_other_targets(self):
        opener = Opener(lambda request: self.fail("Unexpected network call"))
        client = audit.Client(FIXTURE_TOKEN, opener, profile="windows-gateway")
        dns = f"/zones/{GATEWAY_ZONE_ID}/dns_records"
        with self.assertRaisesRegex(audit.AuditError, "SCOPE_REFUSED"):
            client.get(dns, 1)
        client.admit_gateway_zone(GATEWAY_ZONE_ID, GATEWAY_ACCOUNT_ID)
        paths = [
            audit.CONFIG, audit.TUNNELS, audit.APPS, audit.TOKENS, "/user/tokens/verify",
            client.gateway_tunnel_path + "/token",
            client.gateway_tunnel_path.replace(audit.WINDOWS_TUNNEL, APP),
            dns.replace(GATEWAY_ZONE_ID, "0" * 32),
            dns + "?name.exact=other.invalid", dns + "/../dns_records",
            client.gateway_tunnel_path + "/configurations?redirect=https://example.invalid",
            "https://example.invalid" + dns, "//example.invalid" + dns,
        ]
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(audit.AuditError, "SCOPE_REFUSED"):
                client.get(path, 1)
        with self.assertRaisesRegex(audit.AuditError, "SCOPE_REFUSED"):
            client.admit_gateway_zone(GATEWAY_ZONE_ID, "0" * 32)
        with self.assertRaisesRegex(audit.AuditError, "POLICY_SCOPE_LIMIT"):
            client.admit_policy_app(APP)
        self.assertEqual(opener.requests, [])

    def test_gateway_request_budget_is_eight_and_global_limit_still_applies(self):
        opener = Opener(lambda request: Response(envelope({})))
        client = audit.Client(FIXTURE_TOKEN, opener, profile="windows-gateway")
        for _ in range(8):
            client.get(audit.ZONES, 1)
        with self.assertRaisesRegex(audit.AuditError, "REQUEST_LIMIT"):
            client.get(audit.ZONES, 1)
        self.assertEqual(len(opener.requests), 8)
        with mock.patch.object(audit, "MAX_REQUESTS", 2):
            other = audit.Client(FIXTURE_TOKEN, opener, profile="windows-gateway")
            other.get(audit.ZONES, 1)
            other.get(audit.ZONES, 1)
            with self.assertRaisesRegex(audit.AuditError, "REQUEST_LIMIT"):
                other.get(audit.ZONES, 1)

    def test_gateway_body_redirect_and_deadline_bounds_remain_enforced(self):
        for response, expected in (
            (Response(b"fixture-redirect-secret", 302), "REDIRECT_REFUSED"),
            (Response(b"x" * 65), "RESPONSE_TOO_LARGE"),
        ):
            with self.subTest(expected=expected):
                opener = Opener(lambda request: response)
                with mock.patch.object(audit, "MAX_BYTES", 64):
                    result, _ = self.run_gateway(opener=opener)
                self.assertEqual(result["observations"]["zone"]["status"], expected)
                self.assertEqual(len(opener.requests), 1)
        clock = mock.Mock(side_effect=[0, 0, audit.DEADLINE_SECONDS + 1])
        opener = Opener(lambda request: Response(envelope({})))
        client = audit.Client(FIXTURE_TOKEN, opener, clock=clock, profile="windows-gateway")
        result = audit.audit_gateway(client)
        self.assertEqual(result["observations"]["zone"]["status"], "DEADLINE_EXCEEDED")
        self.assertEqual(len(opener.requests), 1)

    def test_public_report_omits_raw_provider_values_including_txt_content(self):
        payloads, opener, dns, _ = gateway_fixture()
        payloads[dns]["result"][0].update(type="TXT", content="fixture-txt-secret")
        result, _ = self.run_gateway(payloads, opener)
        serialized = json.dumps(result)
        for forbidden in (
            FIXTURE_TOKEN, "reader@example.invalid", "fixture-dns-private-comment",
            "fixture-dns-private-tag", "fixture-tunnel-secret", "fixture-config-secret",
            "fixture-txt-secret", "Authorization", "client_secret",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(result["observations"]["dns"]["items"][0]["content_omitted"])
        self.assertEqual(result["signature"], "UNSIGNED")

    def test_gateway_cli_success_failure_and_source_identity(self):
        for absent in (False, True):
            with self.subTest(absent=absent), tempfile.TemporaryDirectory() as directory:
                payloads, opener, dns, _ = gateway_fixture()
                if absent:
                    payloads[dns] = gateway_page([])
                client = audit.Client(FIXTURE_TOKEN, opener, profile="windows-gateway")
                path = Path(directory) / "gateway.json"
                env = {
                    "CLOUDFLARE_API_TOKEN": FIXTURE_TOKEN, "GITHUB_SHA": "a" * 40,
                    "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "2",
                }
                with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(audit, "Client", return_value=client):
                    with contextlib.redirect_stdout(io.StringIO()):
                        code = audit.main(["--profile", "windows-gateway", "--report", str(path)])
                result = json.loads(path.read_text())
                self.assertEqual(code, 2 if absent else 0)
                self.assertEqual(result["source_revision"], "a" * 40)
                self.assertEqual(result["run_id"], "12345")
                self.assertEqual(result["run_attempt"], 2)
                self.assertNotIn(FIXTURE_TOKEN, path.read_text())

    def test_gateway_cli_missing_credential_and_invalid_profile_never_open_network(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / "gateway.json"
            with mock.patch.object(audit, "Client") as client, contextlib.redirect_stdout(io.StringIO()):
                code = audit.main(["--profile", "windows-gateway", "--report", str(path)])
            client.assert_not_called()
            self.assertEqual(code, 2)
            result = json.loads(path.read_text())
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["request_count"], 0)
        with mock.patch.object(audit, "Client") as client, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                audit.main(["--profile", "arbitrary", "--report", "unused.json"])
            self.assertEqual(error.exception.code, 2)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
