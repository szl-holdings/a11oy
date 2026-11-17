#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline request/response and workflow boundary tests for relay observations."""

import contextlib
import copy
import email.message
import importlib.util
import io
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "relay_observation", ROOT / "scripts/audit_cloudflare_alert_relay_telemetry.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

TOKEN = "test-only-not-a-real-token-0123456789"
PRIVATE = "TEST_ONLY_PRIVATE_PROVIDER_CONTENT"
ACCOUNT = "a" * 32
WINDOW, _ = audit.time_window(audit.DEFAULT_FROM, audit.DEFAULT_TO)
PREFIX = audit.API + f"/accounts/{ACCOUNT}/workers/observability/telemetry/"


def envelope(result, **extra):
    return {"success": True, "errors": [], "result": result, **extra}


def keys_response():
    return envelope([
        {"key": key, "type": kind, "lastSeenAt": WINDOW["from"]}
        for key, kind in audit.REQUIRED_KEYS.items()
    ])


def query_response(count=4, sample=1):
    values = (count, 2.5, 5, 18000.5, 20000, 19500)
    calculations = []
    for (alias, operator, _), value in zip(audit.CALCULATIONS, values):
        calculations.append({
            "alias": alias, "calculation": operator, "series": [],
            "aggregates": [{"value": value, "count": count, "sampleInterval": sample}],
        })
    return envelope({
        "run": {"dry": True, "status": "COMPLETED", "timeframe": dict(WINDOW)},
        "statistics": {"elapsed": 0.05, "rows_read": count, "bytes_read": 400},
        "calculations": calculations,
    })


def accounts_response(**info):
    return envelope(
        [{"id": ACCOUNT, "name": PRIVATE}],
        result_info={"page": 1, "count": 1, "total_count": 1, **info},
    )


class Response:
    def __init__(self, body, status=200, headers=None, url=None):
        self.raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.stream = io.BytesIO(self.raw)
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.status = status
        self.url = url
        self.reads = 0

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def read(self, size):
        self.reads += 1
        return self.stream.read(size)

    read1 = read

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if not isinstance(response, Response):
            response = Response(response)
        if response.url is None:
            response.url = request.full_url
        return response


class RedirectHTTPS(urllib.request.HTTPSHandler):
    """Run urllib's real redirect handling without a socket."""

    def __init__(self, status):
        super().__init__()
        self.status = status
        self.requests = []

    def https_open(self, request):
        self.requests.append(request)
        headers = email.message.Message()
        headers["Location"] = "https://example.invalid/" + PRIVATE
        headers["Content-Type"] = "application/json"
        response = urllib.response.addinfourl(
            io.BytesIO(PRIVATE.encode()), headers, request.full_url, code=self.status
        )
        response.msg = "test response"
        return response


class ObservationTests(unittest.TestCase):
    def observe(self, opener, **kwargs):
        return audit.observe(
            kwargs.pop("start", audit.DEFAULT_FROM),
            kwargs.pop("end", audit.DEFAULT_TO),
            kwargs.pop("token", TOKEN),
            kwargs.pop("configured_account", ACCOUNT),
            opener=opener, **kwargs,
        )

    def assert_unavailable(self, report, reason=None):
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertIn(report["stage"], audit.STAGES)
        self.assertEqual(report["delivery_status"], "UNVERIFIED")
        self.assertEqual(report["aggregates"], {})
        if reason:
            self.assertEqual(report["reason"], reason)

    def assert_private_absent(self, value):
        encoded = json.dumps(value)
        for secret in (TOKEN, PRIVATE, ACCOUNT, "example.invalid"):
            self.assertNotIn(secret, encoded)

    def test_actual_requests_are_fixed_and_credential_is_header_only(self):
        opener = Opener(keys_response(), query_response())
        report = self.observe(opener)
        self.assertEqual(report["status"], "OBSERVED")
        self.assertEqual(report["delivery_status"], "UNVERIFIED")
        self.assertEqual(report["request_count"], 2)
        self.assertEqual([r.full_url for r, _ in opener.requests],
                         [PREFIX + "keys", PREFIX + "query"])
        for request, timeout in opener.requests:
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
            self.assertNotIn(TOKEN, request.full_url)
            self.assertNotIn(TOKEN.encode(), request.data)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, audit.REQUEST_TIMEOUT)
        discovery = json.loads(opener.requests[0][0].data)
        query = json.loads(opener.requests[1][0].data)
        self.assertEqual((discovery["from"], discovery["to"]),
                         (1794869540000, 1794869660000))
        self.assertEqual(discovery["filters"], [audit.service_filter()])
        self.assertEqual(discovery["keyNeedle"]["value"], audit.KEY_PATTERN)
        self.assertIs(query["dry"], True)
        self.assertEqual(query["view"], "calculations")
        self.assertEqual(query["chartType"], "aggregate")
        self.assertIs(query["ignoreSeries"], True)
        self.assertEqual(query["timeframe"], WINDOW)
        self.assertEqual(query["limit"], 1)
        parameters = query["parameters"]
        self.assertNotIn("datasets", parameters)
        self.assertNotIn("groupBys", parameters)
        self.assertEqual(parameters["filterCombination"], "and")
        self.assertEqual(parameters["filters"][0], audit.service_filter())
        self.assertEqual({f["key"] for f in parameters["filters"][1:]},
                         {"$workers.cpuTimeMs", "$workers.wallTimeMs"})
        self.assertEqual({c["alias"] for c in parameters["calculations"]},
                         {c[0] for c in audit.CALCULATIONS})
        self.assert_private_absent(report)

    def test_account_discovery_requires_one_proven_unpaginated_account(self):
        opener = Opener(accounts_response(), keys_response(), query_response())
        report = self.observe(opener, configured_account="")
        self.assertEqual(report["status"], "OBSERVED")
        self.assertEqual(report["request_count"], 3)
        self.assertEqual(opener.requests[0][0].get_method(), "GET")
        self.assertEqual(opener.requests[0][0].full_url, audit.API + "/accounts")
        self.assertIsNone(opener.requests[0][0].data)
        self.assert_private_absent(report)

    def test_ambiguous_missing_or_paginated_account_never_queries(self):
        cases = [
            envelope([]), envelope([{"id": ACCOUNT}, {"id": "b" * 32}]),
            envelope([{"id": ACCOUNT}]), accounts_response(total_count=2),
            accounts_response(page=2), accounts_response(count=True),
            accounts_response(total_pages=2), accounts_response(cursors={"after": PRIVATE}),
            accounts_response(next=PRIVATE),
        ]
        for value in cases:
            with self.subTest(value=cases.index(value)):
                opener = Opener(value)
                self.assert_unavailable(self.observe(opener, configured_account=""))
                self.assertEqual(len(opener.requests), 1)

    def test_configured_account_is_validated_without_fallback(self):
        for configured in ("bad", ACCOUNT + "/query", "https://example.invalid", " " + ACCOUNT):
            with self.subTest(configured=configured):
                opener = Opener()
                self.assert_unavailable(
                    self.observe(opener, configured_account=configured), "INVALID_ACCOUNT"
                )
                self.assertEqual(opener.requests, [])

    def test_time_bounds_fail_before_any_http(self):
        pairs = [
            ("2026-11-16T22:52:20", audit.DEFAULT_TO),
            ("2026-11-16", audit.DEFAULT_TO),
            ("2026-13-16T22:52:20Z", audit.DEFAULT_TO),
            (audit.DEFAULT_TO, audit.DEFAULT_FROM),
            (audit.DEFAULT_FROM, audit.DEFAULT_FROM),
            (audit.DEFAULT_FROM, "2026-11-16T23:07:20.001Z"),
            (audit.DEFAULT_FROM + "\n" + PRIVATE, audit.DEFAULT_TO),
            ("2026-11-16T22:52:20.000001Z", "2026-11-16T22:52:20.000002Z"),
            ("1960-01-01T00:00:00Z", "1960-01-01T00:01:00Z"),
        ]
        for start, end in pairs:
            with self.subTest(start=start, end=end):
                opener = Opener()
                self.assert_unavailable(self.observe(opener, start=start, end=end), "INVALID_INPUT")
                self.assertEqual(opener.requests, [])

    def test_aware_offsets_and_exact_fifteen_minute_boundary(self):
        window, canonical = audit.time_window(
            "2026-11-16T17:52:20-05:00", "2026-11-16T18:07:20-05:00"
        )
        self.assertEqual(window["to"] - window["from"], audit.MAX_WINDOW_MS)
        self.assertEqual(canonical["from"], "2026-11-16T22:52:20.000Z")

    def test_invalid_credentials_never_reach_request_constructor(self):
        values = ("", "short", TOKEN + "\r\nX-Test: bad", TOKEN + " ", TOKEN + "\x7f",
                  TOKEN + "\u00e9", "a" * 513)
        for token in values:
            with self.subTest(index=values.index(token)):
                opener = Opener()
                with mock.patch.object(audit.urllib.request, "Request") as constructor:
                    self.assert_unavailable(self.observe(opener, token=token))
                    constructor.assert_not_called()
                self.assertEqual(opener.requests, [])

    def test_only_fixed_api_paths_and_methods_are_accepted(self):
        opener = Opener()
        client = audit.Client(TOKEN, opener=opener)
        for method, path, payload in [
            ("POST", "/accounts", {}),
            ("GET", f"/accounts/{ACCOUNT}/workers/scripts", None),
            ("DELETE", f"/accounts/{ACCOUNT}/workers/observability/telemetry/query", {}),
            ("POST", "https://example.invalid/" + PRIVATE, {}),
            ("POST", f"/accounts/{ACCOUNT}/workers/observability/telemetry/query?x=1", {}),
            ("POST", f"/accounts/{ACCOUNT}/workers/observability/telemetry/queries", {}),
        ]:
            with self.subTest(method=method, path=path):
                with self.assertRaises(audit.ObservationError) as error:
                    client.request(method, path, payload)
                self.assertEqual(error.exception.reason, "SCOPE_REFUSED")
        self.assertEqual(opener.requests, [])

    def test_environment_proxies_are_disabled(self):
        opener = Opener()
        with mock.patch.object(audit.urllib.request, "build_opener", return_value=opener) as build:
            audit.Client(TOKEN)
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], audit.NoRedirect)

    def test_real_urllib_redirect_handling_sends_exactly_one_request(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                transport = RedirectHTTPS(status)
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), audit.NoRedirect(), transport
                )
                report = self.observe(opener)
                self.assert_unavailable(report, "REDIRECT_REFUSED")
                self.assertEqual(report["http_status"], status)
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(transport.requests[0].full_url, PREFIX + "keys")
                self.assert_private_absent(report)

    def test_changed_final_url_is_refused_before_reading(self):
        response = Response(keys_response(), url="https://example.invalid/" + PRIVATE)
        opener = Opener(response)
        self.assert_unavailable(self.observe(opener), "REDIRECT_REFUSED")
        self.assertEqual(response.reads, 0)
        self.assertEqual(len(opener.requests), 1)

    def test_permission_refusals_are_distinct_and_error_body_is_not_read(self):
        for status in (401, 403):
            with self.subTest(status=status):
                body = io.BytesIO((TOKEN + PRIVATE).encode())
                error = urllib.error.HTTPError(PREFIX + "keys", status, PRIVATE, {}, body)
                opener = Opener(error)
                report = self.observe(opener)
                self.assertEqual(report["status"], "PERMISSION_BLOCKED")
                self.assertEqual(report["http_status"], status)
                self.assertEqual(report["delivery_status"], "UNVERIFIED")
                self.assertEqual(len(opener.requests), 1)
                self.assertTrue(body.closed)
                self.assert_private_absent(report)

    def test_permission_stage_distinguishes_account_keys_and_query_refusals(self):
        for stage, configured, prior in (
            ("ACCOUNT_DISCOVERY", "", []),
            ("KEY_DISCOVERY", ACCOUNT, []),
            ("AGGREGATE_QUERY", ACCOUNT, [keys_response()]),
        ):
            with self.subTest(stage=stage):
                error = urllib.error.HTTPError(
                    audit.API, 403, TOKEN + PRIVATE, {}, io.BytesIO(PRIVATE.encode())
                )
                opener = Opener(*prior, error)
                report = self.observe(opener, configured_account=configured)
                self.assertEqual(report["status"], "PERMISSION_BLOCKED")
                self.assertEqual(report["stage"], stage)
                self.assertEqual(report["reason"], "HTTP_REFUSED")
                self.assertEqual(report["http_status"], 403)
                self.assertEqual(report["delivery_status"], "UNVERIFIED")
                self.assertEqual(len(opener.requests), len(prior) + 1)
                self.assert_private_absent(report)

    def test_stage_cannot_contain_provider_or_caller_text(self):
        response = query_response()
        response["stage"] = TOKEN
        response["result"]["run"]["stage"] = PRIVATE
        report = self.observe(Opener(keys_response(), response))
        self.assertEqual(report["stage"], "RESPONSE_ADMISSION")
        self.assert_private_absent(report)
        report = self.observe(Opener(), start=PRIVATE)
        self.assertEqual(report["stage"], "INPUT")
        self.assert_private_absent(report)
        for value in (PRIVATE, TOKEN, [], {}, None, True):
            audit.set_stage(report, value)
            self.assertEqual(report["stage"], "UNKNOWN")

    def test_other_http_and_transport_failures_never_retry(self):
        errors = [
            urllib.error.HTTPError(PREFIX + "keys", code, PRIVATE, {}, io.BytesIO(TOKEN.encode()))
            for code in (400, 404, 429, 500, 503)
        ] + [RuntimeError(TOKEN + PRIVATE), urllib.error.URLError(TOKEN)]
        for error in errors:
            with self.subTest(kind=type(error).__name__):
                opener = Opener(error)
                report = self.observe(opener)
                self.assert_unavailable(report)
                self.assertEqual(len(opener.requests), 1)
                self.assert_private_absent(report)

    def test_non_json_oversized_or_malformed_response_is_unavailable(self):
        responses = [
            Response(b"<html>" + PRIVATE.encode(), headers={"Content-Type": "text/html"}),
            Response(b"{}", headers={"Content-Length": str(audit.MAX_BYTES + 1)}),
            Response(b"x" * (audit.MAX_BYTES + 1)),
            Response(b'{"success": true, "result": NaN}'),
            Response(b'{"success": true, "success": false, "result": []}'),
            Response(b'{"success":'),
            Response(b"\xff"),
        ]
        for response in responses:
            with self.subTest(index=responses.index(response)):
                opener = Opener(response)
                report = self.observe(opener)
                self.assert_unavailable(report)
                self.assertEqual(len(opener.requests), 1)
                self.assert_private_absent(report)
        self.assertEqual(responses[0].reads, 0)
        self.assertEqual(responses[1].reads, 0)

    def test_false_success_and_error_envelopes_are_not_observations(self):
        for value in (
            {"success": False, "errors": [{"message": TOKEN}], "result": []},
            {"success": 1, "errors": [], "result": []},
            envelope([], errors=[{"message": PRIVATE}]),
            [],
        ):
            opener = Opener(value)
            report = self.observe(opener)
            self.assert_unavailable(report, "PROVIDER_REJECTED")
            self.assertEqual(len(opener.requests), 1)
            self.assert_private_absent(report)

    def test_missing_mistyped_extra_or_duplicate_keys_stop_before_query(self):
        valid = keys_response()["result"]
        for rows in (
            [], valid[:-1], valid + [copy.deepcopy(valid[0])],
            valid + [{"key": PRIVATE, "type": "number"}],
            [{"key": key, "type": "string"} for key in audit.REQUIRED_KEYS],
            {"key": PRIVATE},
        ):
            opener = Opener(envelope(rows))
            self.assert_unavailable(self.observe(opener), "KEY_SCHEMA_UNSUPPORTED")
            self.assertEqual(len(opener.requests), 1)

    def test_started_or_unbound_query_never_becomes_observed(self):
        for field, value, reason in (
            ("status", "STARTED", "QUERY_NOT_COMPLETED"),
            ("status", "COMPLETED " + PRIVATE, "QUERY_NOT_COMPLETED"),
            ("dry", False, "QUERY_SCOPE_MISMATCH"),
            ("timeframe", {"from": 0, "to": 1}, "QUERY_SCOPE_MISMATCH"),
        ):
            response = query_response()
            response["result"]["run"][field] = value
            opener = Opener(keys_response(), response)
            self.assert_unavailable(self.observe(opener), reason)

    def test_empty_timing_results_are_unavailable_and_delivery_unverified(self):
        cases = [query_response(count=0), query_response()]
        cases[1]["result"]["calculations"] = []
        for response in cases:
            opener = Opener(keys_response(), response)
            self.assert_unavailable(self.observe(opener), "NO_MATCHING_TIMING_EVENTS")

    def test_malformed_aliases_or_groups_fail_closed(self):
        cases = []
        value = query_response()
        value["result"]["calculations"][0]["alias"] = PRIVATE
        cases.append(value)
        value = query_response()
        value["result"]["calculations"][1]["alias"] = "matching_timing_events"
        cases.append(value)
        value = query_response()
        value["result"]["calculations"].pop()
        cases.append(value)
        value = query_response()
        value["result"]["calculations"][0]["aggregates"][0]["groups"] = [
            {"key": "$metadata.service", "value": PRIVATE}
        ]
        cases.append(value)
        value = query_response()
        value["result"]["calculations"][1]["aggregates"] = []
        cases.append(value)
        for response in cases:
            opener = Opener(keys_response(), response)
            report = self.observe(opener)
            self.assert_unavailable(report, "CALCULATION_SCHEMA_UNSUPPORTED")
            self.assert_private_absent(report)

    def test_numbers_are_strict_finite_nonnegative_and_not_booleans(self):
        for field, value in (
            ("value", PRIVATE), ("value", True), ("value", -1),
            ("value", float("inf")), ("value", float("nan")),
            ("count", None), ("count", False), ("sampleInterval", 0.5),
        ):
            response = query_response()
            response["result"]["calculations"][2]["aggregates"][0][field] = value
            report = self.observe(Opener(keys_response(), response))
            self.assert_unavailable(report)
            self.assert_private_absent(report)

    def test_inconsistent_count_is_not_reported(self):
        response = query_response()
        response["result"]["calculations"][0]["aggregates"][0]["count"] = 7
        self.assert_unavailable(
            self.observe(Opener(keys_response(), response)), "CALCULATION_SCHEMA_UNSUPPORTED"
        )

    def test_sample_weights_are_preserved_without_exact_invocation_claims(self):
        for sample in (1, 2, 16.5):
            report = self.observe(Opener(keys_response(), query_response(count=33, sample=sample)))
            self.assertEqual(report["status"], "OBSERVED")
            self.assertEqual(report["count_basis"], "ESTIMATED_MATCHING_TIMING_EVENTS")
            self.assertEqual(report["delivery_status"], "UNVERIFIED")
            for row in report["aggregates"].values():
                self.assertEqual(row["count"], 33)
                self.assertEqual(row["sampleInterval"], sample)

    def test_raw_provider_fields_are_never_copied_into_report(self):
        response = query_response()
        response["messages"] = [{"message": TOKEN}]
        response["result"]["events"] = {"url": "https://example.invalid/" + PRIVATE}
        response["result"]["traces"] = [{"headers": {"Authorization": TOKEN}}]
        response["result"]["run"].update({"accountId": ACCOUNT, "userId": PRIVATE})
        response["result"]["calculations"][0]["debug"] = TOKEN
        report = self.observe(Opener(keys_response(), response))
        self.assertEqual(report["status"], "OBSERVED")
        self.assert_private_absent(report)
        self.assertEqual(set(report["aggregates"]), {entry[0] for entry in audit.CALCULATIONS})

    def test_request_budget_is_enforced(self):
        opener = Opener(accounts_response(), accounts_response(), accounts_response())
        client = audit.Client(TOKEN, opener=opener)
        for _ in range(3):
            client.request("GET", "/accounts")
        with self.assertRaises(audit.ObservationError) as error:
            client.request("GET", "/accounts")
        self.assertEqual(error.exception.reason, "REQUEST_LIMIT")
        self.assertEqual(len(opener.requests), 3)

    def test_elapsed_deadline_stops_before_request_or_during_body(self):
        clock = mock.Mock(side_effect=[0, audit.DEADLINE_SECONDS + 1])
        opener = Opener()
        report = self.observe(opener, clock=clock)
        self.assert_unavailable(report, "DEADLINE_EXCEEDED")
        self.assertEqual(opener.requests, [])
        clock = mock.Mock(side_effect=[0, 0, 0, audit.DEADLINE_SECONDS + 1])
        opener = Opener(keys_response())
        self.assert_unavailable(self.observe(opener, clock=clock), "DEADLINE_EXCEEDED")
        self.assertEqual(len(opener.requests), 1)

    def test_hard_deadline_returns_without_waiting_for_trickling_transport(self):
        release = threading.Event()
        captured = []

        def hung_read(start, end, token, configured, stop):
            captured.append(stop)
            release.wait(2)
            return query_response()

        started = time.monotonic()
        try:
            report = audit.bounded_observe(
                audit.DEFAULT_FROM, audit.DEFAULT_TO, TOKEN, ACCOUNT,
                timeout=0.02, operation=hung_read,
            )
            self.assertLess(time.monotonic() - started, 1)
            self.assert_unavailable(report, "DEADLINE_EXCEEDED")
            self.assertEqual(report["stage"], "UNKNOWN")
            self.assertIsNone(report["request_count"])
            self.assertTrue(captured[0].is_set())
        finally:
            release.set()

    def run_main(self, opener, args=None, extra_env=None):
        with tempfile.TemporaryDirectory() as temporary:
            report_path = Path(temporary) / audit.REPORT_FILE
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(audit, "REPORT_FILE", str(report_path)), \
                    mock.patch.object(audit.urllib.request, "build_opener", return_value=opener), \
                    mock.patch.dict(os.environ, {
                        "CLOUDFLARE_API_TOKEN": TOKEN,
                        "CLOUDFLARE_ACCOUNT_ID": ACCOUNT, **(extra_env or {}),
                    }, clear=True), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = audit.main(args or [])
            artifact = report_path.read_text()
            for output in (artifact, stdout.getvalue(), stderr.getvalue()):
                for secret in (TOKEN, PRIVATE, ACCOUNT, "example.invalid"):
                    self.assertNotIn(secret, output)
            self.assertEqual(stderr.getvalue(), "")
            return code, json.loads(artifact), stdout.getvalue()

    def test_cli_success_artifact_and_stdout_are_allowlisted(self):
        response = query_response(sample=4)
        response["result"]["events"] = {"headers": TOKEN, "topic": PRIVATE}
        code, report, stdout = self.run_main(Opener(keys_response(), response))
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "OBSERVED")
        self.assertEqual(json.loads(stdout)["delivery_status"], "UNVERIFIED")

    def test_cli_error_body_and_exception_canaries_never_escape(self):
        for error in (
            RuntimeError(TOKEN + PRIVATE),
            urllib.error.HTTPError(PREFIX + "keys", 403, TOKEN, {}, io.BytesIO(PRIVATE.encode())),
        ):
            code, report, _ = self.run_main(Opener(error))
            self.assertEqual(code, 2)
            self.assertNotEqual(report["status"], "OBSERVED")
            self.assertEqual(report["delivery_status"], "UNVERIFIED")

    def test_cli_invalid_arguments_are_not_echoed(self):
        opener = Opener()
        code, report, _ = self.run_main(opener, ["--unknown", TOKEN + PRIVATE])
        self.assertEqual(code, 2)
        self.assertEqual(report["reason"], "INVALID_INPUT")
        self.assertEqual(opener.requests, [])

    def test_cli_missing_token_fails_without_network(self):
        opener = Opener()
        code, report, _ = self.run_main(opener, extra_env={"CLOUDFLARE_API_TOKEN": ""})
        self.assertEqual(code, 2)
        self.assertEqual(report["reason"], "MISSING_CREDENTIAL")
        self.assertEqual(opener.requests, [])


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github/workflows/audit-alert-relay-telemetry.yml").read_text()
        cls.contract, cls.observe = cls.text.split("\n  observe:\n", 1)

    def test_production_secrets_are_only_in_manual_main_job(self):
        self.assertIn("if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'",
                      self.observe)
        self.assertIn("environment: production", self.observe)
        self.assertIn("needs: contract", self.observe)
        self.assertNotIn("secrets.", self.contract)
        self.assertNotIn("pull_request_target:", self.text)
        self.assertIn("permissions:\n  contents: read", self.text)

    def test_trusted_source_and_isolated_python_guards_remain(self):
        for fragment in (
            'test "$GITHUB_REF" = "refs/heads/main"',
            'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
            'test -z "$(git status --porcelain)"',
            'git merge-base --is-ancestor "$GITHUB_SHA" refs/remotes/origin/main',
            'git diff --exit-code "$GITHUB_SHA" refs/remotes/origin/main',
            "persist-credentials: false", "ref: __DOLLAR__{{ github.sha }}",
            "python -I -B scripts/audit_cloudflare_alert_relay_telemetry.py",
        ):
            self.assertIn(fragment.replace("__DOLLAR__", "$"), self.observe)
        self.assertIn("python -I -B tests/test_cloudflare_alert_relay_telemetry.py -v", self.contract)

    def test_dispatch_inputs_are_only_times_and_are_passed_via_environment(self):
        inputs = self.text.split("  workflow_dispatch:", 1)[1].split("\npermissions:", 1)[0]
        self.assertEqual(
            [line.strip().split(":")[0] for line in inputs.splitlines()
             if line.startswith("      ") and not line.startswith("        ")],
            ["from_utc", "to_utc"],
        )
        for name in ("from_utc", "to_utc"):
            self.assertIn("__DOLLAR__{{ inputs.".replace("__DOLLAR__", "$") + name + " }}", self.observe)
        self.assertIn('--from-utc "$TELEMETRY_FROM_UTC" --to-utc "$TELEMETRY_TO_UTC"', self.observe)
        observation_run = self.observe.split("          set +e", 1)[1].split("\n      - name:", 1)[0]
        self.assertNotIn("__DOLLAR__{{".replace("__DOLLAR__", "$"), observation_run)
        self.assertNotIn("wrangler", self.observe)
        self.assertNotIn("curl ", self.observe)

    def test_artifact_is_single_fixed_report_with_no_raw_response_upload(self):
        self.assertIn("AUDIT_REPORT: " + audit.REPORT_FILE, self.observe)
        self.assertIn("path: __DOLLAR__{{ env.AUDIT_REPORT }}".replace("__DOLLAR__", "$"), self.observe)
        self.assertIn("retention-days: 7", self.observe)
        self.assertIn("steps.observe.outputs.report_written == 'true'", self.observe)


if __name__ == "__main__":
    unittest.main()
