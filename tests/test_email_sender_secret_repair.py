# SPDX-License-Identifier: Apache-2.0
# (c) 2026 SZL Holdings
"""Offline contract tests. No provider calls, real secrets, or mail recipients."""
from __future__ import annotations

import base64
import contextlib
import copy
import email.message
import fnmatch
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "email_secret_repair_under_test", ROOT / "scripts/repair_email_sender_secret.py"
)
m = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = m
SPEC.loader.exec_module(m)

CONTROL = "a" * 40
REVISION = "b" * 40
ACCOUNT = "c" * 32
CF_TOKEN = "fake-cloudflare-private-canary"
GH_TOKEN = "fake-github-private-canary"
CANDIDATE = "x" * 63 + "_"
DEPLOYMENT = "11111111-1111-4111-8111-111111111111"
VERSION = "22222222-2222-4222-8222-222222222222"
OTHER_VERSION = "33333333-3333-4333-8333-333333333333"


def envelope(value):
    return {"success": True, "errors": [], "messages": [], "result": value}


def response(value, status=200):
    return m.Response(status, {"content-type": "application/json; charset=utf-8"},
                      json.dumps(value).encode())


class Clock:
    def __init__(self):
        self.value = 1.0

    def __call__(self):
        return self.value


class Provider:
    """A closed in-memory endpoint fixture, including uncertain write effects."""

    def __init__(self):
        self.config, self.files = m.repository_contract(ROOT)
        self.lock = threading.Lock()
        self.events = []
        self.counts = {}
        self.overrides = {}
        self.before_ready = False
        self.after_ready = True
        self.put_seen = False

    def __call__(self, method, url, headers, body, timeout):
        with self.lock:
            self.events.append((method, url, dict(headers), body, timeout))
            if url.startswith(m.GH_API):
                if url.endswith("/git/ref/heads/main"):
                    kind, value = "main", {
                        "ref": "refs/heads/main",
                        "object": {"type": "commit", "sha": CONTROL},
                    }
                else:
                    kind = "source"
                    name = url.split("/contents/", 1)[1].split("?ref=", 1)[0]
                    raw = self.files[name]
                    value = {
                        "type": "file", "path": name, "encoding": "base64",
                        "size": len(raw), "content": base64.b64encode(raw).decode(),
                        "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                    }
            elif url == m.CF_API + "/accounts?page=1&per_page=5":
                kind, value = "accounts", [{"id": ACCOUNT}]
            elif url.endswith("/workers/subdomain"):
                kind, value = "subdomain", {"subdomain": m.SUBDOMAIN}
            elif url.endswith("/settings"):
                kind, value = "settings", {
                    "compatibility_date": self.config["compatibility_date"],
                    "bindings": [
                        {"name": "API_SECRET", "type": "secret_text"},
                        {"name": "MAIL_FROM", "type": "plain_text",
                         "text": self.config["vars"]["MAIL_FROM"]},
                        {"name": "SOURCE_REVISION", "type": "plain_text", "text": REVISION},
                        {"name": "SEND_EMAIL", "type": "send_email"},
                    ],
                }
            elif url.endswith("/secrets/API_SECRET"):
                kind, value = "secret", {"name": "API_SECRET", "type": "secret_text"}
            elif url.endswith("/deployments?page=1&per_page=1"):
                kind, value = "deployment", {"deployments": [{
                    "id": DEPLOYMENT, "strategy": "percentage",
                    "versions": [{"version_id": VERSION, "percentage": 100}],
                }]}
            elif url.endswith("/versions?page=1&per_page=1"):
                kind, value = "versions", {"items": [{"id": VERSION}]}
            elif method == "PUT" and url.endswith("/secrets"):
                kind, value = "put", {"name": "API_SECRET", "type": "secret_text",
                                      "text": CANDIDATE}
                self.put_seen = True
            elif url == m.ORIGIN + m.REVISION_PATH:
                kind = "readiness"
                ready = self.after_ready if self.put_seen else self.before_ready
                value = {
                    "worker": m.WORKER, "source_revision": REVISION, "ready": ready,
                    "readiness_checks": {
                        key: ready if key == "secret_requirement_met" else True for key in m.CHECKS
                    },
                }
            elif url == m.ORIGIN + "/send" and method == "POST":
                kind, value = "probe", {"error": "unsupported_media_type"}
            else:
                raise AssertionError("Unrecognized fixture request")
            self.counts[kind] = self.counts.get(kind, 0) + 1
            ordinal = self.counts[kind]
            if kind in self.overrides:
                value = self.overrides[kind](ordinal, copy.deepcopy(value))
            if isinstance(value, BaseException):
                raise value
            if type(value) is m.Response:
                return value
            if url.startswith(m.CF_API):
                return response(envelope(value))
            return response(value, 415 if kind == "probe" else 200)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "evidence"
        self.clock = Clock()
        self.provider = Provider()
        self.no_network = patch.object(socket, "create_connection",
                                       side_effect=AssertionError("Real network prohibited"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def run_repair(self, *, execute=True, evidence_type=m.Evidence, run_attempt=1,
                   configured_account=ACCOUNT):
        self.client = m.Client(CF_TOKEN, GH_TOKEN, CANDIDATE,
                               transport=self.provider, clock=self.clock)
        self.output = io.StringIO()
        with contextlib.redirect_stdout(self.output):
            evidence = evidence_type(self.directory, CONTROL, REVISION, VERSION)
            try:
                report = m.repair(
                    self.client, evidence, root=ROOT, control_source=CONTROL, revision=REVISION, expected_version_id=VERSION,
                    configured_account=configured_account, execute=execute, run_attempt=run_attempt,
                )
            finally:
                evidence.close()
        self.report = report
        return report

    def assert_no_write(self, report):
        self.assertFalse(report["mutation_attempted"])
        self.assertFalse(report["mutation_acknowledged"])
        self.assertEqual(self.provider.counts.get("put", 0), 0)

    def test_one_write_then_readiness_then_bodyless_auth_probe(self):
        report = self.run_repair()
        self.assertEqual(report["status"], "VERIFIED")
        for key in ("mutation_attempted", "mutation_acknowledged", "readiness_verified",
                    "candidate_authentication_verified"):
            self.assertTrue(report[key])
        self.assertFalse(report["email_delivery_proved"])
        self.assertFalse(report["automatic_retry"])
        self.assertEqual(report["prior_deployment_id"], DEPLOYMENT)
        self.assertEqual(report["prior_version_id"], VERSION)
        methods = [x[0] for x in self.provider.events]
        position = methods.index("PUT")
        self.assertEqual(methods[position:], ["PUT", "GET", "POST"])
        method, url, headers, body, _ = self.provider.events[-1]
        self.assertEqual(url, m.ORIGIN + "/send")
        self.assertEqual(body, b"")
        self.assertEqual(headers["Content-Type"], "application/octet-stream")
        put = self.provider.events[position]
        self.assertEqual(json.loads(put[3]), {
            "name": "API_SECRET", "type": "secret_text", "text": CANDIDATE,
        })
        self.assertLessEqual(len(self.provider.events), m.MAX_REQUESTS)
        journal = [json.loads(x) for x in (self.directory / "receipt.jsonl").read_text().splitlines()]
        self.assertEqual([x["event"] for x in journal],
                         ["PRECONDITIONS", "PUT_INTENT", "PUT_ACKNOWLEDGED", "OUTCOME"])

    def test_credentials_are_separated_and_reports_are_value_free(self):
        self.run_repair()
        for method, url, headers, _, _ in self.provider.events:
            expected = ("Bearer " + CF_TOKEN if url.startswith(m.CF_API)
                        else "Bearer " + GH_TOKEN if url.startswith(m.GH_API)
                        else "Bearer " + CANDIDATE if method == "POST" else None)
            self.assertEqual(headers.get("Authorization"), expected)
        emitted = self.output.getvalue()
        emitted += "".join(p.read_text() for p in self.directory.iterdir())
        for forbidden in (CF_TOKEN, GH_TOKEN, CANDIDATE, ACCOUNT,
                          self.provider.config["vars"]["MAIL_FROM"]):
            self.assertNotIn(forbidden, emitted)

    def test_read_only_admission_does_not_auth_probe_or_put(self):
        report = self.run_repair(execute=False)
        self.assertEqual(report["status"], "READY_FOR_EXECUTION")
        self.assert_no_write(report)
        self.assertNotIn("probe", self.provider.counts)

    def test_already_ready_requires_same_credential_proof_without_put(self):
        self.provider.before_ready = True
        report = self.run_repair()
        self.assertEqual(report["status"], "ALREADY_REPAIRED")
        self.assertTrue(report["candidate_authentication_verified"])
        self.assert_no_write(report)
        self.assertEqual(self.provider.counts["probe"], 1)

    def test_already_ready_different_credential_is_refused_without_replacement(self):
        self.provider.before_ready = True
        self.provider.overrides["probe"] = lambda _n, _v: response({"error": "unauthorized"}, 401)
        report = self.run_repair()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["diagnostic_code"], "CANDIDATE_AUTHENTICATION_UNPROVED")
        self.assert_no_write(report)

    def test_initial_contract_errors_block_before_write(self):
        cases = {
            "host": ("subdomain", lambda _n, _v: {"subdomain": "another-account"}),
            "secret-missing": ("secret", lambda _n, _v: {}),
            "secret-wrong-type": ("secret", lambda _n, _v: {"name": "API_SECRET", "type": "plain_text"}),
            "secret-value-present": ("secret", lambda _n, _v: {"name": "API_SECRET", "type": "secret_text", "text": "unknown"}),
            "missing-binding": ("settings", lambda _n, v: {**v, "bindings": v["bindings"][1:]}),
            "extra-binding": ("settings", lambda _n, v: {**v, "bindings": v["bindings"] + [{"name": "EXTRA", "type": "secret_text"}]}),
            "duplicate-binding": ("settings", lambda _n, v: {**v, "bindings": [v["bindings"][0]] * 4}),
            "binding-type": ("settings", lambda _n, v: {**v, "bindings": [{**x, "type": "plain_text"} if x["name"] == "API_SECRET" else x for x in v["bindings"]]}),
            "binding-revision": ("settings", lambda _n, v: {**v, "bindings": [{**x, "text": CONTROL} if x["name"] == "SOURCE_REVISION" else x for x in v["bindings"]]}),
            "compatibility": ("settings", lambda _n, v: {**v, "compatibility_date": "2000-01-01"}),
            "public-revision": ("readiness", lambda _n, v: {**v, "source_revision": CONTROL}),
            "other-predicate": ("readiness", lambda _n, v: {**v, "readiness_checks": {**v["readiness_checks"], "sender_valid": False}}),
            "boolean-coercion": ("readiness", lambda _n, v: {**v, "readiness_checks": {**v["readiness_checks"], "sender_valid": 1}}),
            "empty-deployment": ("deployment", lambda _n, _v: {"deployments": []}),
            "split-deployment": ("deployment", lambda _n, v: {"deployments": [{**v["deployments"][0], "versions": [{"version_id": VERSION, "percentage": 50}, {"version_id": OTHER_VERSION, "percentage": 50}]}]}),
            "boolean-percentage": ("deployment", lambda _n, v: {"deployments": [{**v["deployments"][0], "versions": [{"version_id": VERSION, "percentage": True}]}]}),
            "latest-not-active": ("versions", lambda _n, _v: {"items": [{"id": OTHER_VERSION}]}),
            "latest-missing": ("versions", lambda _n, _v: {"items": []}),
            "canonical-version-changed": ("deployment", lambda _n, v: {"deployments": [{**v["deployments"][0], "versions": [{"version_id": OTHER_VERSION, "percentage": 100}]}]}),
            "invalid-id": ("deployment", lambda _n, v: {"deployments": [{**v["deployments"][0], "id": "untrusted-provider-value"}]}),
            "source-bytes": ("source", lambda _n, v: {**v, "content": base64.b64encode(b"changed").decode()}),
            "source-hash": ("source", lambda _n, v: {**v, "sha": "d" * 40}),
        }
        for name, (kind, override) in cases.items():
            with self.subTest(case=name):
                self.directory = Path(self.tmp.name) / name
                self.provider = Provider()
                self.provider.overrides[kind] = override
                report = self.run_repair()
                self.assertEqual(report["status"], "BLOCKED")
                self.assert_no_write(report)

    def test_each_changed_final_identity_blocks_before_write(self):
        cases = {
            "settings": lambda n, v: v if n == 1 else {**v, "logpush": True},
            "subdomain": lambda n, v: v if n == 1 else {"subdomain": "another-account"},
            "deployment": lambda n, v: v if n == 1 else {"deployments": [{**v["deployments"][0], "id": OTHER_VERSION}]},
            "readiness": lambda n, v: v if n == 1 else {**v, "ready": True, "readiness_checks": {key: True for key in m.CHECKS}},
            "versions": lambda n, v: v if n == 1 else {"items": [{"id": OTHER_VERSION}]},
            "main": lambda n, v: v if n == 1 else {**v, "object": {"type": "commit", "sha": REVISION}},
        }
        for kind, override in cases.items():
            with self.subTest(case=kind):
                self.directory = Path(self.tmp.name) / kind
                self.provider = Provider()
                self.provider.overrides[kind] = override
                report = self.run_repair()
                self.assert_no_write(report)
                self.assertNotIn("probe", self.provider.counts)

    def test_slow_final_main_cannot_renew_dispatch_deadline(self):
        def slow_main(n, value):
            if n == 2:
                self.clock.value += m.DISPATCH_SECONDS + 0.01
            return value
        self.provider.overrides["main"] = slow_main
        report = self.run_repair()
        self.assertEqual(report["diagnostic_code"], "DISPATCH_WINDOW_EXPIRED")
        self.assert_no_write(report)

    def test_intent_fsync_is_inside_the_original_dispatch_deadline(self):
        clock = self.clock
        class SlowIntent(m.Evidence):
            def emit(self, event, **fields):
                super().emit(event, **fields)
                if event == "PUT_INTENT":
                    clock.value += m.DISPATCH_SECONDS + 0.01
        report = self.run_repair(evidence_type=SlowIntent)
        self.assertEqual(report["diagnostic_code"], "DISPATCH_WINDOW_EXPIRED")
        self.assert_no_write(report)

    def test_failed_intent_write_prevents_submission(self):
        class FailedIntent(m.Evidence):
            def emit(self, event, **fields):
                if event == "PUT_INTENT":
                    raise OSError(CANDIDATE)
                return super().emit(event, **fields)
        report = self.run_repair(evidence_type=FailedIntent)
        self.assertEqual(report["status"], "BLOCKED")
        self.assert_no_write(report)
        self.assertNotIn(CANDIDATE, self.output.getvalue())

    def test_uncertain_write_stops_without_any_readback_or_retry(self):
        outcomes = [
            RuntimeError(CANDIDATE),
            response({"success": False, "errors": [{"message": CANDIDATE}], "result": None}, 500),
            m.Response(200, {"content-type": "application/json"}, b"not json"),
            response(envelope({"name": "OTHER", "type": "secret_text"})),
            m.Response(302, {"content-type": "application/json"}, b"{}"),
        ]
        for i, outcome in enumerate(outcomes):
            with self.subTest(case=i):
                self.directory = Path(self.tmp.name) / str(i)
                self.provider = Provider()
                self.provider.overrides["put"] = lambda _n, _v, outcome=outcome: outcome
                report = self.run_repair()
                self.assertEqual(report["status"], "WRITE_OUTCOME_UNCERTAIN")
                self.assertTrue(report["mutation_attempted"])
                self.assertFalse(report["mutation_acknowledged"])
                self.assertEqual(self.provider.events[-1][0], "PUT")
                self.assertEqual(self.provider.counts["put"], 1)
                self.assertNotIn(CANDIDATE, self.output.getvalue())

    def test_acknowledged_readiness_failure_does_not_probe_or_retry(self):
        self.provider.after_ready = False
        report = self.run_repair()
        self.assertEqual(report["status"], "ACKNOWLEDGED_NOT_VERIFIED")
        self.assertTrue(report["mutation_attempted"])
        self.assertTrue(report["mutation_acknowledged"])
        self.assertFalse(report["readiness_verified"])
        self.assertNotIn("probe", self.provider.counts)
        self.assertEqual(self.provider.counts["put"], 1)

    def test_acknowledged_wrong_revision_does_not_auth_probe(self):
        self.provider.overrides["readiness"] = (
            lambda n, v: v if n <= 2 else {**v, "source_revision": CONTROL}
        )
        report = self.run_repair()
        self.assertEqual(report["status"], "ACKNOWLEDGED_NOT_VERIFIED")
        self.assertEqual(report["diagnostic_code"], "DEPLOYED_REVISION_CHANGED")
        self.assertNotIn("probe", self.provider.counts)

    def test_auth_proof_requires_exact_status_body_and_json_type(self):
        invalid = [
            response({"error": "unauthorized"}, 401),
            response({"error": "unsupported_media_type"}, 200),
            response({"error": "edge-generated"}, 415),
            response({"error": "unsupported_media_type", "extra": True}, 415),
            m.Response(415, {"content-type": "text/html"}, b"<h1>Unsupported Media Type</h1>"),
        ]
        for i, item in enumerate(invalid):
            with self.subTest(case=i):
                self.directory = Path(self.tmp.name) / str(i)
                self.provider = Provider()
                self.provider.overrides["probe"] = lambda _n, _v, item=item: item
                report = self.run_repair()
                self.assertEqual(report["status"], "ACKNOWLEDGED_NOT_VERIFIED")
                self.assertFalse(report["candidate_authentication_verified"])
                self.assertEqual(self.provider.counts["put"], 1)

    def test_final_evidence_failure_preserves_attempt_and_acknowledgement(self):
        class FailedFinal(m.Evidence):
            def finish(self, report):
                raise OSError(CANDIDATE)
        report = self.run_repair(evidence_type=FailedFinal)
        self.assertEqual(report["status"], "ACKNOWLEDGED_NOT_VERIFIED")
        self.assertEqual(report["diagnostic_code"], "EVIDENCE_WRITE_FAILED")
        self.assertTrue(report["mutation_attempted"])
        self.assertTrue(report["mutation_acknowledged"])
        self.assertNotIn(CANDIDATE, self.output.getvalue())

    def test_exclusive_evidence_and_rerun_guard(self):
        self.directory.mkdir()
        with self.assertRaises(FileExistsError):
            m.Evidence(self.directory, CONTROL, REVISION, VERSION)
        self.directory = Path(self.tmp.name) / "rerun"
        report = self.run_repair(run_attempt=2)
        self.assertEqual(report["diagnostic_code"], "RERUN_MUTATION_REFUSED")
        self.assert_no_write(report)
        self.assertEqual(self.provider.events, [])

    def test_account_fallback_is_exactly_one_bounded_account(self):
        report = self.run_repair(configured_account="")
        self.assertEqual(report["status"], "VERIFIED")
        self.assertEqual(self.provider.counts["accounts"], 1)
        self.directory = Path(self.tmp.name) / "ambiguous"
        self.provider = Provider()
        self.provider.overrides["accounts"] = lambda _n, _v: [{"id": ACCOUNT}, {"id": "d" * 32}]
        self.assert_no_write(self.run_repair(configured_account=""))


    def test_envelope_failure_reports_fixed_route_phase_and_no_provider_values(self):
        cases = [
            ("accounts", 1, "ACCOUNT_DISCOVERY", "INITIAL"),
            ("settings", 1, "WORKER_SETTINGS", "INITIAL"),
            ("secret", 1, "SECRET_METADATA", "INITIAL"),
            ("subdomain", 1, "ACCOUNT_SUBDOMAIN", "INITIAL"),
            ("deployment", 1, "ACTIVE_DEPLOYMENT", "INITIAL"),
            ("versions", 2, "LATEST_VERSION", "FINAL"),
            ("put", 1, "SECRET_UPDATE", "UPDATE_ACK"),
        ]
        for kind, ordinal, route, phase in cases:
            with self.subTest(route=route, phase=phase):
                self.directory = Path(self.tmp.name) / kind
                self.provider = Provider()
                def malformed(n, value, ordinal=ordinal):
                    if n != ordinal:
                        return value
                    return response({
                        "success": True, "result": value, "errors": None,
                        "messages": [{"message": CANDIDATE}], "untrusted_key": CF_TOKEN,
                    })
                self.provider.overrides[kind] = malformed
                report = self.run_repair(configured_account="" if kind == "accounts" else ACCOUNT)
                self.assertEqual(report["diagnostic_code"], "CLOUDFLARE_RESPONSE_INVALID")
                self.assertEqual(report["cloudflare_envelope"], {
                    "route": route, "phase": phase, "envelope_is_object": True,
                    "errors_shape": "NULL", "messages_shape": "NONEMPTY_LIST",
                    "errors_count": None, "result_present": True,
                })
                if kind == "put":
                    self.assertEqual(report["status"], "WRITE_OUTCOME_UNCERTAIN")
                    self.assertTrue(report["mutation_attempted"])
                    self.assertFalse(report["mutation_acknowledged"])
                    self.assertEqual(self.provider.events[-1][0], "PUT")
                else:
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assert_no_write(report)
                self.assertNotIn("probe", self.provider.counts)
                emitted = self.output.getvalue()
                emitted += "".join(path.read_text() for path in self.directory.iterdir())
                for forbidden in (CANDIDATE, CF_TOKEN, GH_TOKEN, ACCOUNT, "untrusted_key"):
                    self.assertNotIn(forbidden, emitted)


    def test_observed_latest_null_envelope_passes_initial_and_final_reads(self):
        for execute in (False, True):
            with self.subTest(execute=execute):
                self.directory = Path(self.tmp.name) / str(execute)
                self.provider = Provider()
                self.provider.overrides["versions"] = lambda _n, value: response({
                    "success": True, "errors": None, "messages": None, "result": value,
                })
                report = self.run_repair(execute=execute)
                self.assertEqual(report["status"], "VERIFIED" if execute else "READY_FOR_EXECUTION")
                self.assertEqual(self.provider.counts["versions"], 2)
                self.assertEqual(self.provider.counts["main"], 2)
                self.assertEqual(report["prior_version_id"], VERSION)
                self.assertEqual(self.provider.counts.get("put", 0), int(execute))
                if not execute:
                    self.assert_no_write(report)
                    self.assertNotIn("probe", self.provider.counts)

    def test_latest_null_envelope_does_not_bypass_version_result_validation(self):
        results = [
            None, {}, {"items": []}, {"items": [{"id": "invalid"}]},
            {"items": [{"id": OTHER_VERSION}]},
            {"items": [{"id": VERSION}, {"id": OTHER_VERSION}]},
        ]
        for i, value in enumerate(results):
            with self.subTest(case=i):
                self.directory = Path(self.tmp.name) / str(i)
                self.provider = Provider()
                self.provider.overrides["versions"] = lambda _n, _v, value=value: response({
                    "success": True, "errors": None, "messages": None, "result": value,
                })
                report = self.run_repair()
                self.assertEqual(report["status"], "BLOCKED")
                self.assert_no_write(report)
                self.assertNotIn("probe", self.provider.counts)

    def test_null_pair_on_other_read_or_update_ack_keeps_prior_refusal(self):
        for kind in ("settings", "put"):
            with self.subTest(route=kind):
                self.directory = Path(self.tmp.name) / kind
                self.provider = Provider()
                self.provider.overrides[kind] = lambda _n, value: response({
                    "success": True, "errors": None, "messages": None, "result": value,
                })
                report = self.run_repair()
                self.assertEqual(report["diagnostic_code"], "CLOUDFLARE_RESPONSE_INVALID")
                self.assertEqual(report["cloudflare_envelope"]["errors_shape"], "NULL")
                self.assertEqual(report["cloudflare_envelope"]["messages_shape"], "NULL")
                self.assertNotIn("probe", self.provider.counts)
                if kind == "put":
                    self.assertEqual(report["status"], "WRITE_OUTCOME_UNCERTAIN")
                    self.assertTrue(report["mutation_attempted"])
                    self.assertFalse(report["mutation_acknowledged"])
                    self.assertEqual(self.provider.events[-1][0], "PUT")
                else:
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assert_no_write(report)


class BoundaryTests(unittest.TestCase):

    def test_latest_null_compatibility_requires_exact_route_phase_presence_and_types(self):
        payload = {"success": True, "errors": None, "messages": None, "result": {"items": []}}
        routes = (
            "ACCOUNT_DISCOVERY", "ACCOUNT_SUBDOMAIN", "WORKER_SETTINGS", "SECRET_METADATA",
            "ACTIVE_DEPLOYMENT", "LATEST_VERSION", "SECRET_UPDATE",
        )
        for route in routes:
            for phase in ("INITIAL", "FINAL", "UPDATE_ACK"):
                with self.subTest(route=route, phase=phase):
                    if route == "LATEST_VERSION" and phase in {"INITIAL", "FINAL"}:
                        self.assertEqual(m.api_result(payload, route=route, phase=phase), payload["result"])
                    else:
                        with self.assertRaises(m.RepairError):
                            m.api_result(payload, route=route, phase=phase)
        variants = [
            {key: value for key, value in payload.items() if key != "errors"},
            {key: value for key, value in payload.items() if key != "messages"},
            {key: value for key, value in payload.items() if key not in {"errors", "messages"}},
            {key: value for key, value in payload.items() if key != "result"},
            {**payload, "errors": []}, {**payload, "messages": []},
            {**payload, "errors": ["untrusted"]}, {**payload, "errors": "untrusted"},
            {**payload, "errors": {}}, {**payload, "messages": "untrusted"},
            {**payload, "messages": {}}, {**payload, "success": False},
            {**payload, "success": 1},
        ]
        for i, variant in enumerate(variants):
            for phase in ("INITIAL", "FINAL"):
                with self.subTest(case=i, phase=phase), self.assertRaises(m.RepairError):
                    m.api_result(variant, route="LATEST_VERSION", phase=phase)

    def test_envelope_diagnostics_preserve_original_admission_decisions(self):
        cases = [
            ("empty", {"success": True, "errors": [], "messages": [], "result": {}}, "EMPTY_LIST", "EMPTY_LIST", True),
            ("errors-absent", {"success": True, "messages": [], "result": {}}, "ABSENT", "EMPTY_LIST", True),
            ("errors-null", {"success": True, "errors": None, "result": {}}, "NULL", "ABSENT", True),
            ("errors-other", {"success": True, "errors": CANDIDATE, "result": {}}, "OTHER", "ABSENT", True),
            ("errors-nonempty", {"success": True, "errors": [{"message": CANDIDATE}, CF_TOKEN], "result": {}}, "NONEMPTY_LIST", "ABSENT", True),
            ("messages-absent", {"success": True, "errors": [], "result": {}}, "EMPTY_LIST", "ABSENT", True),
            ("messages-null", {"success": True, "errors": [], "messages": None, "result": {}}, "EMPTY_LIST", "NULL", True),
            ("messages-other", {"success": True, "errors": [], "messages": CF_TOKEN, "result": {}}, "EMPTY_LIST", "OTHER", True),
            ("messages-nonempty", {"success": True, "errors": [], "messages": [CANDIDATE], "result": {}}, "EMPTY_LIST", "NONEMPTY_LIST", True),
            ("result-absent", {"success": True, "errors": [], "messages": []}, "EMPTY_LIST", "EMPTY_LIST", False),
            ("result-null", {"success": True, "errors": [], "messages": [], "result": None}, "EMPTY_LIST", "EMPTY_LIST", True),
            ("success-false", {"success": False, "errors": [], "result": {}}, "EMPTY_LIST", "ABSENT", True),
            ("success-number", {"success": 1, "errors": [], "result": {}}, "EMPTY_LIST", "ABSENT", True),
            ("not-object", [], "ABSENT", "ABSENT", False),
        ]
        for label, payload, errors_shape, messages_shape, result_present in cases:
            with self.subTest(case=label):
                original_accepts = (
                    type(payload) is dict and payload.get("success") is True
                    and payload.get("errors") == [] and type(payload.get("messages", [])) is list
                    and "result" in payload
                )
                if original_accepts:
                    self.assertEqual(
                        m.api_result(payload, route="WORKER_SETTINGS", phase="INITIAL"),
                        payload["result"],
                    )
                else:
                    with self.assertRaises(m.RepairError) as raised:
                        m.api_result(payload, route="WORKER_SETTINGS", phase="INITIAL")
                    facts = raised.exception.cloudflare_envelope
                    self.assertEqual(facts, {
                        "route": "WORKER_SETTINGS", "phase": "INITIAL",
                        "envelope_is_object": type(payload) is dict,
                        "errors_shape": errors_shape, "messages_shape": messages_shape,
                        "errors_count": len(payload["errors"]) if type(payload) is dict
                        and type(payload.get("errors")) is list else None,
                        "result_present": result_present,
                    })
                    encoded = json.dumps(facts)
                    self.assertNotIn(CANDIDATE, encoded)
                    self.assertNotIn(CF_TOKEN, encoded)

    def test_envelope_diagnostics_refuse_untrusted_context(self):
        for route, phase in ((CANDIDATE, "INITIAL"), ("WORKER_SETTINGS", CANDIDATE)):
            with self.subTest(field="route" if route == CANDIDATE else "phase"):
                with self.assertRaises(m.RepairError) as raised:
                    m.api_result(envelope({}), route=route, phase=phase)
                self.assertEqual(raised.exception.code, "DIAGNOSTIC_CONTEXT_INVALID")
                self.assertIsNone(raised.exception.cloudflare_envelope)
                self.assertNotIn(CANDIDATE, str(raised.exception))

    def test_json_rejects_duplicate_nonfinite_oversized_and_invalid_utf8(self):
        invalid = [
            b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'{"a":Infinity}',
            b'{"a":123456789012345678901}', b'\xff', b'', b'[' * 2000,
            b'{"a":"' + b"x" * m.MAX_BODY + b'"}',
        ]
        for i, raw in enumerate(invalid):
            with self.subTest(case=i), self.assertRaises(m.RepairError):
                m.decode(raw)

    def test_candidate_shape_is_exact_and_never_trimmed(self):
        for candidate in ("x" * 63, "x" * 65, " " + CANDIDATE, CANDIDATE + "\n",
                          "x" * 63 + "/", None):
            with self.subTest(length=None if candidate is None else len(candidate)):
                with self.assertRaises(m.RepairError):
                    m.Client(CF_TOKEN, GH_TOKEN, candidate, transport=lambda *_: None)

    def test_fixed_surface_rejects_targets_payloads_and_invalid_deadlines(self):
        fake = Provider()
        client = m.Client(CF_TOKEN, GH_TOKEN, CANDIDATE, transport=fake)
        calls = [
            ("cf", "DELETE", "/accounts/" + ACCOUNT + "/workers/scripts/szl-email-sender"),
            ("cf", "GET", "/accounts/" + ACCOUNT + "/workers/scripts/other/settings"),
            ("worker", "GET", "https://elsewhere.invalid/"),
            ("worker", "POST", "/"),
            ("github", "GET", "/repos/another/repository/git/ref/heads/main"),
        ]
        for args in calls:
            with self.subTest(case=args[:2]), self.assertRaises(m.RepairError):
                client._call(*args)
        with self.assertRaises(m.RepairError):
            client._call("worker", "POST", "/send", body=b'{"to":"forbidden"}')
        for deadline in (float("nan"), float("inf"), True, "later", 0):
            with self.subTest(deadline=str(deadline)), self.assertRaises(m.RepairError):
                client._call("worker", "GET", m.REVISION_PATH, deadline=deadline)
        self.assertEqual(fake.events, [])

    def test_client_refuses_second_put_and_preserves_first_attempt(self):
        fake, clock = Provider(), Clock()
        client = m.Client(CF_TOKEN, GH_TOKEN, CANDIDATE, transport=fake, clock=clock)
        target = "/accounts/" + ACCOUNT + "/workers/scripts/" + m.WORKER
        client.put(target, clock.value + 5)
        with self.assertRaises(m.RepairError):
            client.put(target, clock.value + 5)
        self.assertTrue(client.attempted)
        self.assertTrue(client.acknowledged)
        self.assertEqual(fake.counts["put"], 1)

    def test_request_budget_is_enforced(self):
        fake = Provider()
        client = m.Client(CF_TOKEN, GH_TOKEN, CANDIDATE, transport=fake)
        client.requests = m.MAX_REQUESTS
        with self.assertRaises(m.RepairError):
            client.readiness(REVISION)
        self.assertEqual(fake.events, [])

    def test_transport_disables_proxies_redirects_and_retries(self):
        class RawResponse:
            code = 200
            def __init__(self):
                self.headers = email.message.Message()
                self.headers["Content-Type"] = "application/json"
                self.read_sizes = []
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self, size):
                self.read_sizes.append(size)
                return b"{}"
        raw = RawResponse()
        with patch.object(m.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = raw
            result = m.Transport()("GET", m.ORIGIN + m.REVISION_PATH, {}, None, 2)
            self.assertEqual(result.status, 200)
            self.assertEqual(raw.read_sizes, [m.MAX_BODY + 1])
            handlers = build.call_args.args
            self.assertIsInstance(handlers[0], m.urllib.request.ProxyHandler)
            self.assertEqual(handlers[0].proxies, {})
            self.assertIsInstance(handlers[1], m.NoRedirect)
            self.assertEqual(build.return_value.open.call_count, 1)
            with self.assertRaises(m.RepairError):
                handlers[1].redirect_request(None, None, None, None, None, None)
        with patch.object(m.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = RuntimeError(CANDIDATE)
            with self.assertRaisesRegex(m.RepairError, "^TRANSPORT_UNAVAILABLE$"):
                m.Transport()("GET", m.ORIGIN + m.REVISION_PATH, {}, None, 2)
            self.assertEqual(build.return_value.open.call_count, 1)

    def test_cli_requires_manual_protected_context_and_sanitizes_argument_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["--control-source", CONTROL, "--expect-revision", REVISION,
                    "--expected-version-id", VERSION, "--output-directory", str(Path(directory) / "proof")]
            with patch.dict(os.environ, {}, clear=True), patch.object(m, "Client") as client:
                capture = io.StringIO()
                with contextlib.redirect_stdout(capture):
                    self.assertEqual(m.main(args), 2)
                client.assert_not_called()
                self.assertIn("PROTECTED_MANUAL_CONTEXT_REQUIRED", capture.getvalue())
            with patch.dict(os.environ, {}, clear=True):
                capture = io.StringIO()
                with contextlib.redirect_stdout(capture):
                    self.assertEqual(m.main(["--unknown-" + CANDIDATE]), 2)
                self.assertNotIn(CANDIDATE, capture.getvalue())

    def test_workflow_is_manual_main_environment_serialized_and_path_isolated(self):
        path = ".github/workflows/email-sender-secret-repair.yml"
        text = (ROOT / path).read_text()
        self.assertIn("  workflow_dispatch:", text)
        self.assertNotIn("  push:", text)
        self.assertNotIn("  pull_request:", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("environment: cloudflare-production", text)
        self.assertIn("group: deploy-szl-email-sender", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("secrets.EMAIL_SENDER_API_SECRET_V2", text)
        self.assertIn("test_email_sender_secret_repair.py", text)
        changed = (
            path, "scripts/repair_email_sender_secret.py",
            "tests/test_email_sender_secret_repair.py", "docs/ops/email-sender-secret-repair.md",
        )
        for existing in ("email-sender-worker.yml", "alert-relay-worker.yml"):
            original = (ROOT / ".github/workflows" / existing).read_text()
            patterns = [
                line.strip()[3:-1] for line in original.splitlines()
                if line.strip().startswith("- '") and line.strip().endswith("'")
            ]
            for name in changed:
                self.assertFalse(any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns),
                                 "Repair path unexpectedly triggers an existing deploy workflow")


if __name__ == "__main__":
    unittest.main()
