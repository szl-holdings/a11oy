#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline regressions for observed false positives; no production requests."""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import szl_runtime_observation as runtime

NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
TARGET = runtime.Target("https://runtime.example.invalid", "fixture/runtime", "a" * 40, "b" * 64)


def bodies(now=NOW):
    earlier = runtime._iso(now - timedelta(seconds=2))
    signer = {
        "schema": "szl.signing-state/v1", "runtime_boot_id": "boot_fixture",
        "signing_ready": True, "freshness": "FRESH", "observed_at": earlier,
        "age_seconds": 2, "max_age_seconds": 60,
        "public_key_fingerprint": TARGET.signer_fingerprint,
        "loaded_key_fingerprint": TARGET.signer_fingerprint,
        "expected_key_fingerprint": TARGET.signer_fingerprint,
        "key_agreement": "MATCH", "key_source": "persistent:fixture",
        "blockers": [], "execution_authorized": False, "source_binding": "UNKNOWN",
        "observed_capability": {"evidence": {
            "verified": True, "observed_at": earlier, "payload_digest": "d" * 64}},
    }
    health = {"status": "ok", "signing_state": signer}
    healthz = {
        "status": "ok",
        "runtime_identity": {"source_repository": TARGET.repository,
                             "source_revision": TARGET.source_revision,
                             "source_revision_state": "OBSERVED",
                             "image_attestation": False, "hardware_attestation": False},
        "operational_readiness": {
            "ready": True, "status": "READY", "service_blockers": [],
            "frontier": {"state": "READY", "ready": True, "ready_tiles": ["fixture"],
                         "blocked_tiles": []}},
        "mcp_inventory": {"label": "CACHED", "reason": None, "count": 1,
                          "source": "/api/a11oy/v1/mcp/tools",
                          "scope": "ADVERTISED_MANIFEST_ONLY",
                          "capability_readiness_asserted": False,
                          "checked_at": earlier, "age_s": 2, "max_age_s": 30},
    }
    values = {
        "healthz_baseline": healthz, "healthz_final": healthz,
        "health_baseline": health, "health_final": health,
        "livez": {"status": "PROCESS_ALIVE", "production_ready": False,
                  "receipt_minted": False},
        "build_info": {"status": "OBSERVED", "build": {
            "state": "OBSERVED", "revision": TARGET.source_revision,
            "revision_source": "env:SZL_GIT_SHA", "version_source": "UNKNOWN",
            "working_tree_source": "UNKNOWN"}},
        "storage": {"schema": "szl.a11oy-storage-status/v2", "mode": "FENCED",
                    "role": "WRITER", "writable": True, "unfenced": False, "alert": False,
                    "epoch": 1, "lease": {"state": "ACTIVE", "sequence": 1, "heartbeat_age_s": 2},
                    "active_errors": {}, "last_error_history": {"old": "recovered"},
                    "stores": {name: {"health": "OK", "blocked_code": None}
                               for name in runtime.STORES}},
        "brain": {"schema": "szl.brain-capabilities.v1", "generated_at": runtime._iso(now),
                  "overall_status": "OPERATIONAL",
                  "summary": {"capabilities_total": 1,
                              "status_counts": {state: int(state == "OPERATIONAL")
                                                for state in runtime.CAPABILITY_STATES}},
                  "capabilities": [{"id": "fixture", "status": "OPERATIONAL", "blockers": []}]},
        "source": {"schema": "szl.deployment-source/v1", "observed_at": earlier,
                   "source": {"repository": TARGET.repository, "commit": TARGET.source_revision,
                              "state": "ENV_DECLARATION"},
                   "verification_state": "STRUCTURAL_ONLY", "attestation_state": "UNSIGNED_STRUCTURAL",
                   "alignment_state": "UNKNOWN"},
    }
    return copy.deepcopy(values)


def record(route, body, now=NOW):
    name, path = route
    raw = runtime.canonical(body)
    return {"name": name, "path": path, "url": TARGET.base_url + path,
            "captured_at": runtime._iso(now), "http_status": 200,
            "content_type": "application/json", "body_b64": base64.b64encode(raw).decode(),
            "body_sha256": hashlib.sha256(raw).hexdigest(), "truncated": False, "error": None}


def fixture(now=NOW, active=False):
    values = bodies(now)
    snapshot = {"schema": runtime.SNAPSHOT_SCHEMA, "scope": runtime.SCOPE,
                "expected_target": asdict(TARGET), "started_at": runtime._iso(now),
                "completed_at": runtime._iso(now),
                "observations": [record(route, values[route[0]], now) for route in runtime.ROUTES],
                "active_probe": None}
    if active:
        snapshot["active_probe"] = [
            record(runtime.ACTIVE_ROUTES[0], {"tools": [{"name": "fixture"}]}, now),
            record(runtime.ACTIVE_ROUTES[1], values["healthz_final"], now)]
    return snapshot


def mutate(snapshot, name, transform):
    row = next(row for row in snapshot["observations"] if row["name"] == name)
    body = json.loads(base64.b64decode(row["body_b64"]))
    transform(body)
    raw = runtime.canonical(body)
    row["body_b64"] = base64.b64encode(raw).decode()
    row["body_sha256"] = hashlib.sha256(raw).hexdigest()


class EvaluatorTests(unittest.TestCase):
    def evaluate(self, snapshot, now=NOW):
        return runtime.evaluate(snapshot, TARGET, now=now)

    def assert_blocked(self, snapshot, code=None, now=NOW):
        result = self.evaluate(snapshot, now)
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertNotEqual(result["verdict"], "OBSERVATIONS_PASS")
        if code:
            self.assertTrue(any(code in item["code"] for item in result["findings"]), result)
        return result

    def test_valid_observation_has_no_release_authority(self):
        result = self.evaluate(fixture())
        self.assertEqual(result["verdict"], "OBSERVATIONS_PASS", result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["boundaries"], runtime.BOUNDARIES)
        self.assertEqual(result["boundaries"]["release_approval"], "NOT_EVALUATED")
        self.assertEqual(len(result["observations"]), len(runtime.ROUTES))
        self.assertEqual(result["snapshot_canonical_sha256"], runtime.digest(fixture()))

    def test_missing_registries_and_status_only_receipts_are_not_inputs(self):
        for value in (None, {}, [], {"entries": []}, {"gaps": []},
                      {"status": "PASS", "expires_at": "2000-01-01T00:00:00Z"},
                      {"schema": "szl.release-readiness.v1", "verdict": "READY"}):
            with self.subTest(value=value):
                result = self.assert_blocked(value)
                self.assertEqual(result["exit_code"], 2)

    def test_expected_fingerprint_is_never_an_observation(self):
        snapshot = fixture()
        def expected_only(body):
            signer = body["signing_state"]
            del signer["public_key_fingerprint"]
            del signer["loaded_key_fingerprint"]
        mutate(snapshot, "health_baseline", expected_only)
        self.assert_blocked(snapshot, "PUBLIC_KEY_FINGERPRINT_NOT_OBSERVED")

    def test_conflicting_observed_fingerprint_blocks(self):
        snapshot = fixture()
        mutate(snapshot, "health_baseline",
               lambda body: body["signing_state"].update(loaded_key_fingerprint="c" * 64))
        self.assert_blocked(snapshot, "LOADED_KEY_FINGERPRINT_MISMATCH")

    def test_json_truthiness_cannot_supply_boolean_evidence(self):
        for value in ("false", "true", 1, 0, [], {}):
            with self.subTest(value=value):
                snapshot = fixture()
                mutate(snapshot, "health_baseline",
                       lambda body: body["signing_state"].update(signing_ready=value))
                self.assertEqual(self.assert_blocked(snapshot, "BOOLEAN_REQUIRED")["exit_code"], 2)

    def test_ready_label_cannot_override_false_or_blocked_tiles(self):
        snapshot = fixture()
        def contradictory(body):
            body["operational_readiness"]["ready"] = False
            body["operational_readiness"]["frontier"]["blocked_tiles"] = [
                {"name": "fixture", "ready": False, "reasons": ["missing_evidence"]}]
        mutate(snapshot, "healthz_baseline", contradictory)
        self.assert_blocked(snapshot, "OPERATIONAL_READINESS_NOT_ESTABLISHED")

    def test_all_required_runtime_observations_must_exist(self):
        for name in ("storage", "brain", "build_info", "source", "health_final"):
            with self.subTest(name=name):
                snapshot = fixture()
                snapshot["observations"] = [r for r in snapshot["observations"] if r["name"] != name]
                self.assertEqual(self.assert_blocked(snapshot, "REQUIRED_OBSERVATIONS_MISSING")["exit_code"], 2)

    def test_liveness_is_exact_status_not_substring(self):
        snapshot = fixture()
        mutate(snapshot, "livez",
               lambda body: body.update(status="ERROR", detail="PROCESS_ALIVE unavailable"))
        self.assert_blocked(snapshot, "PROCESS_NOT_ALIVE")

    def test_expired_or_future_snapshot_cannot_pass(self):
        self.assert_blocked(fixture(), "OBSERVATION_EXPIRED_OR_FUTURE",
                            now=NOW + timedelta(seconds=121))
        self.assert_blocked(fixture(), "OBSERVATION_EXPIRED_OR_FUTURE",
                            now=NOW - timedelta(seconds=6))

    def test_expired_signer_self_report_cannot_pass(self):
        snapshot = fixture()
        mutate(snapshot, "health_baseline",
               lambda body: body["signing_state"].update(
                   observed_at=runtime._iso(NOW - timedelta(seconds=61)), age_seconds=61))
        self.assert_blocked(snapshot, "CACHED_OBSERVATION_EXPIRED_OR_FUTURE")

    def test_stale_mcp_remains_blocked_after_active_refresh_without_reason(self):
        snapshot = fixture(active=True)
        mutate(snapshot, "healthz_baseline",
               lambda body: body["mcp_inventory"].update(
                   age_s=9999, checked_at=runtime._iso(NOW - timedelta(seconds=9999)), reason=None))
        result = self.assert_blocked(snapshot, "CACHED_OBSERVATION_EXPIRED_OR_FUTURE")
        self.assertTrue(result["active_probe"]["performed"])
        self.assertFalse(result["active_probe"]["baseline_replaced"])
        self.assertEqual(result["active_probe"]["findings"], [])

    def test_missing_mcp_evidence_is_not_a_fresh_empty_inventory(self):
        snapshot = fixture()
        mutate(snapshot, "healthz_baseline",
               lambda body: body["mcp_inventory"].update(
                   count=None, age_s=None, checked_at=None, label="UNAVAILABLE"))
        self.assert_blocked(snapshot, "MCP_OBSERVATION_MISSING")

    def test_declared_source_contract_does_not_require_invented_fields(self):
        snapshot = fixture()
        self.assertEqual(self.evaluate(snapshot)["exit_code"], 0)
        source = bodies()["source"]
        self.assertNotIn("receipt_minted", source)
        self.assertNotIn("publication_eligible", source)

    def test_wrong_source_or_target_blocks(self):
        for name in ("healthz_baseline", "build_info", "source"):
            snapshot = fixture()
            def change(body):
                if name.startswith("healthz"):
                    body["runtime_identity"]["source_revision"] = "c" * 40
                elif name == "build_info":
                    body["build"]["revision"] = "c" * 40
                else:
                    body["source"]["commit"] = "c" * 40
            mutate(snapshot, name, change)
            self.assert_blocked(snapshot, "MISMATCH")
        snapshot = fixture()
        snapshot["expected_target"]["source_revision"] = "c" * 40
        self.assertEqual(self.assert_blocked(snapshot, "TARGET_MISMATCH")["exit_code"], 2)

    def test_byte_hash_and_origin_are_bound(self):
        snapshot = fixture()
        snapshot["observations"][0]["body_sha256"] = "0" * 64
        self.assertEqual(self.assert_blocked(snapshot, "SHA256_MISMATCH")["exit_code"], 2)
        snapshot = fixture()
        snapshot["observations"][0]["url"] = "https://wrong.example.invalid/api/a11oy/healthz"
        self.assertEqual(self.assert_blocked(snapshot, "URL_TARGET_MISMATCH")["exit_code"], 2)

    def test_reboot_during_collection_blocks(self):
        snapshot = fixture()
        mutate(snapshot, "health_final",
               lambda body: body["signing_state"].update(runtime_boot_id="boot_other"))
        self.assert_blocked(snapshot, "RUNTIME_BOOT_CHANGED")

    def test_partial_brain_and_contradictory_counts_do_not_pass(self):
        snapshot = fixture()
        def partial(body):
            body["overall_status"] = "PARTIALLY OPERATIONAL"
            body["capabilities"][0]["status"] = "PARTIALLY OPERATIONAL"
            body["summary"]["status_counts"]["OPERATIONAL"] = 0
            body["summary"]["status_counts"]["PARTIALLY OPERATIONAL"] = 1
        mutate(snapshot, "brain", partial)
        self.assert_blocked(snapshot, "BRAIN_NOT_OPERATIONAL")
        snapshot = fixture()
        mutate(snapshot, "brain", lambda body: body["summary"].update(capabilities_total=0))
        self.assertEqual(self.assert_blocked(snapshot, "SUMMARY_DISAGREEMENT")["exit_code"], 2)

    def test_storage_alert_active_error_and_missing_store_block(self):
        changes = [
            lambda body: body.update(alert=True),
            lambda body: body.update(active_errors={"publish": {"code": "FAILED"}}),
            lambda body: body["stores"].pop("gdw"),
            lambda body: body.update(writable="true"),
        ]
        for change in changes:
            snapshot = fixture()
            mutate(snapshot, "storage", change)
            self.assert_blocked(snapshot)

    def test_strict_json_and_nonobject_endpoint_rejected(self):
        for raw in (b'{"status":"PROCESS_ALIVE","status":"ERROR"}',
                    b'{"value":NaN}', b'{"value":1e9999}', b'[]', b'null'):
            with self.subTest(raw=raw):
                snapshot = fixture()
                row = snapshot["observations"][2]
                row["body_b64"] = base64.b64encode(raw).decode()
                row["body_sha256"] = hashlib.sha256(raw).hexdigest()
                self.assertEqual(self.assert_blocked(snapshot)["exit_code"], 2)

    def test_nested_malformed_shapes_and_huge_numbers_return_error(self):
        cases = [
            ("brain", lambda body: body["capabilities"][0].update(status=[])),
            ("health_baseline", lambda body: body.update(signing_state=[])),
            ("health_final", lambda body: body.update(signing_state=None)),
            ("healthz_baseline", lambda body: body["mcp_inventory"].update(age_s=10 ** 1000)),
            ("health_baseline", lambda body: body["signing_state"].update(max_age_seconds=10 ** 1000)),
            ("healthz_baseline", lambda body: body.update(operational_readiness=[])),
        ]
        for name, change in cases:
            with self.subTest(name=name):
                snapshot = fixture()
                mutate(snapshot, name, change)
                self.assertEqual(self.assert_blocked(snapshot)["exit_code"], 2)

    def test_fresh_envelope_cannot_rejuvenate_old_selftest_or_brain_data(self):
        old = runtime._iso(NOW - timedelta(seconds=121))
        snapshot = fixture()
        mutate(snapshot, "brain", lambda body: body.update(generated_at=old))
        self.assert_blocked(snapshot, "BRAIN_OBSERVATION_EXPIRED_OR_FUTURE")
        snapshot = fixture()
        mutate(snapshot, "health_baseline", lambda body:
               body["signing_state"]["observed_capability"]["evidence"].update(observed_at=old))
        self.assert_blocked(snapshot, "SIGNER_SELFTEST_EXPIRED_OR_FUTURE")

    def test_html_truncation_http_failure_and_bad_boolean_rejected(self):
        for changes in ({"content_type": "text/html"}, {"truncated": True},
                        {"http_status": 503}, {"http_status": True}, {"truncated": "false"}):
            snapshot = fixture()
            snapshot["observations"][2].update(changes)
            self.assert_blocked(snapshot)


class FakeResponse(io.BytesIO):
    def __init__(self, url, body, status=200):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = {"Content-Type": "application/json"}

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, error=None, large=False):
        self.calls = []
        self.error, self.large = error, large

    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout))
        if self.error:
            raise self.error
        index = len(self.calls) - 1
        route = (runtime.ROUTES + runtime.ACTIVE_ROUTES)[index]
        values = bodies()
        body = values.get(route[0], values["healthz_final"])
        raw = b"x" * (runtime.MAX_BODY_BYTES + 1) if self.large else runtime.canonical(body)
        return FakeResponse(request.full_url, raw)


class CollectorTests(unittest.TestCase):
    def test_passive_baseline_precedes_optional_active_probe(self):
        opener = FakeOpener()
        snapshot = runtime.collect(TARGET, active_probe=True, opener=opener, clock=lambda: NOW)
        expected = [TARGET.base_url + path for _, path in runtime.ROUTES + runtime.ACTIVE_ROUTES]
        self.assertEqual([call[0] for call in opener.calls], expected)
        self.assertTrue(all(method == "GET" and timeout == 10 for _, method, timeout in opener.calls))
        self.assertEqual(runtime.evaluate(snapshot, TARGET, now=NOW)["exit_code"], 0)
        self.assertEqual(snapshot["active_probe"][0]["name"], "mcp_active")

    def test_network_error_is_retained_and_denied(self):
        opener = FakeOpener(error=URLError("fixture network failure"))
        snapshot = runtime.collect(TARGET, opener=opener, clock=lambda: NOW)
        self.assertTrue(all(row["error"] == "URLError" for row in snapshot["observations"]))
        report = runtime.evaluate(snapshot, TARGET, now=NOW)
        self.assertEqual(report["exit_code"], 2)
        self.assertTrue(all(item["code"] == "COLLECTION_FAILED" for item in report["findings"]))

    def test_bounded_read_marks_truncation(self):
        snapshot = runtime.collect(TARGET, opener=FakeOpener(large=True), clock=lambda: NOW)
        self.assertTrue(snapshot["observations"][0]["truncated"])
        self.assertEqual(len(base64.b64decode(snapshot["observations"][0]["body_b64"])),
                         runtime.MAX_BODY_BYTES)
        self.assertEqual(runtime.evaluate(snapshot, TARGET, now=NOW)["exit_code"], 2)

    def test_redirects_are_not_followed(self):
        handler = runtime._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://other.invalid"))


class CliTests(unittest.TestCase):
    def command(self, path):
        return [sys.executable, str(ROOT / "scripts" / "szl_runtime_observation.py"),
                "evaluate", "--base-url", TARGET.base_url, "--repository", TARGET.repository,
                "--source-revision", TARGET.source_revision,
                "--signer-fingerprint", TARGET.signer_fingerprint, "--snapshot", str(path)]

    def test_exit_codes_match_pass_block_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            now = datetime.now(timezone.utc)
            for value, code, verdict in ((fixture(now), 0, "OBSERVATIONS_PASS"),
                                         (fixture(now - timedelta(seconds=121)), 1, "BLOCKED"),
                                         ({}, 2, "ERROR")):
                with self.subTest(code=code):
                    path.write_bytes(runtime.canonical(value))
                    result = subprocess.run(self.command(path), capture_output=True, text=True)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    report = json.loads(result.stdout)
                    self.assertEqual(report["exit_code"], code)
                    self.assertEqual(report["verdict"], verdict)
                    self.assertEqual(report["snapshot_file_sha256"],
                                     hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_malformed_and_duplicate_key_files_exit_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            for data in (None, b'{"missing":', b'{"schema":"one","schema":"two"}'):
                with self.subTest(data=data):
                    if data is not None:
                        path.write_bytes(data)
                    result = subprocess.run(self.command(path), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout)["verdict"], "ERROR")

    def test_missing_target_argument_is_nonzero(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "szl_runtime_observation.py"),
                                 "evaluate"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
