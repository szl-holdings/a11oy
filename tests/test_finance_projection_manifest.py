#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""SIMULATED transports and providers; no Hub state or runtime qualification.

Also runnable with stdlib unittest when the local host lacks pytest. CI collects
this exact suite with the established Finance contracts. Model/API execution is
not needed to test the source-projection evidence boundary.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "1" * 40
HUB = "2" * 40
RUN = 77


def load(name):
    spec = importlib.util.spec_from_file_location("projection_test_" + name,
        ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    hub = ModuleType("huggingface_hub")
    hub.HfApi = type("HfApi", (), {})
    with patch.dict(sys.modules, {"huggingface_hub": hub}):
        spec.loader.exec_module(module)
    return module


class ProjectionContractTests(unittest.TestCase):
    def setUp(self):
        self.renderer = load("hf_publish_vertical_flagships_v4_impl")
        self.gate = self.renderer._projection_module
        self.files = self.renderer.render_finance_payloads(SOURCE, RUN)
        self.expected = {self.gate.MANIFEST_PATH:
            self.gate.manifest_bytes(self.files, SOURCE, RUN), **self.files}
        self.calls = []

    def request(self, revision, path, limit):
        self.assertEqual(revision, HUB)
        self.assertEqual(limit, self.gate.MAX_BYTES[path])
        self.calls.append(path)
        return 200, self.expected[path]

    def witness(self, request=None):
        return self.gate.observe_projection(self.files, SOURCE, RUN, HUB,
            request=request or self.request)

    def test_exact_eight_files_including_configuration_without_self_hash(self):
        manifest = json.loads(self.expected[self.gate.MANIFEST_PATH])
        self.assertEqual({row["path"] for row in manifest["files"]}, set(self.files))
        self.assertEqual(manifest["self_hash_excluded"], self.gate.MANIFEST_PATH)
        self.assertFalse(manifest["legacy_manifest"]["retained_bytes_verified"])
        self.assertFalse(manifest["legacy_manifest"]["current_projection_attestation"])
        self.assertEqual(manifest["legacy_manifest"]["qualification"], "UNKNOWN")
        self.assertEqual(manifest["file_table_sha256"], hashlib.sha256(
            self.gate.canonical(manifest["files"])).hexdigest())
        witness = self.witness()
        self.assertEqual(self.calls, list(self.expected))
        self.assertTrue(self.gate.witness_matches(witness, self.files, SOURCE, RUN, HUB))
        for field in ("signature_verified", "runtime_inclusion_verified",
                      "authority_established", "execution_enabled", "credentials_sent"):
            self.assertIs(witness[field], False)
        self.assertEqual(witness["provider_mutations"], 0)

    def test_every_file_byte_is_required_at_one_immutable_revision(self):
        for path in self.expected:
            with self.subTest(path=path):
                def wrong(revision, name, limit):
                    status, raw = self.request(revision, name, limit)
                    return status, raw + b" " if name == path else raw
                witness = self.witness(wrong)
                self.assertFalse(witness["complete"])
                self.assertEqual(witness["failure_code"], "PROJECTION_BYTES_MISMATCH")

    def test_witness_complete_flag_cannot_replace_full_bound_evidence(self):
        good = self.witness()
        defects = {
            "source": lambda w: w.update(source_revision="3" * 40),
            "hub": lambda w: w.update(hf_revision="3" * 40),
            "run": lambda w: w.update(workflow_run_id=RUN + 1),
            "bool-run": lambda w: w.update(workflow_run_id=True),
            "manifest-hash": lambda w: w.update(manifest_sha256="0" * 64),
            "table-hash": lambda w: w.update(file_table_sha256="0" * 64),
            "missing-file": lambda w: w["files"].pop(),
            "duplicate-file": lambda w: w["files"].__setitem__(1, w["files"][0]),
            "path": lambda w: w["files"][0].update(path="unowned.txt"),
            "bytes": lambda w: w["files"][0].update(bytes=0),
            "bool-bytes": lambda w: w["files"][0].update(bytes=True),
            "file-hash": lambda w: w["files"][0].update(sha256="0" * 64),
            "status": lambda w: w["files"][0].update(http_status=201),
            "accepted": lambda w: w["files"][0].update(accepted=False),
            "execution": lambda w: w.update(execution_enabled=True),
            "raw-error": lambda w: w.update(failure_code="arbitrary secret"),
        }
        for defect, mutate in defects.items():
            with self.subTest(defect=defect):
                wrong = deepcopy(good)
                mutate(wrong)
                self.assertFalse(self.gate.witness_matches(wrong, self.files, SOURCE, RUN, HUB))
        self.assertFalse(self.gate.witness_matches({"complete": True}, self.files, SOURCE, RUN, HUB))

    def test_invalid_source_config_or_payload_has_zero_requests(self):
        configurations = [
            b'{"source_revision":"duplicate","source_revision":"again"}',
            b'{"value":NaN}', b'{"value":1e9999}', b'[]', b'\xff',
        ]
        for raw in configurations:
            with self.subTest(raw=raw):
                files = {**self.files, "config.json": raw}
                witness = self.gate.observe_projection(files, SOURCE, RUN, HUB, request=self.request)
                self.assertFalse(witness["complete"])
                self.assertEqual(self.calls, [])
        for field, value in (("source_revision", "3" * 40), ("workflow_run_id", True),
                             ("hf_repository", "SZLHOLDINGS/other"), ("slug", "other"),
                             ("artifact_set_sha256", "0" * 64), ("landing_sha256", "0" * 64)):
            with self.subTest(field=field):
                config = json.loads(self.files["config.json"])
                config[field] = value
                files = {**self.files, "config.json": json.dumps(config).encode()}
                witness = self.gate.observe_projection(files, SOURCE, RUN, HUB, request=self.request)
                self.assertFalse(witness["complete"])
                self.assertEqual(self.calls, [])
        for revision, run, hub in (("0" * 40, RUN, HUB), (SOURCE, True, HUB),
                                  (SOURCE, 0, HUB), (SOURCE, RUN, "main")):
            with self.subTest(revision=revision, run=run, hub=hub):
                self.assertFalse(self.gate.observe_projection(self.files, revision, run, hub,
                    request=self.request)["complete"])
                self.assertEqual(self.calls, [])

    def test_late_authority_denial_remains_terminal_not_a_timeout(self):
        for status in (401, 403):
            clock = [0]
            calls = []
            def late(revision, path, limit):
                calls.append(path)
                clock[0] = 41
                return status, b"arbitrary secret body"
            with self.subTest(status=status), patch.object(self.gate.time, "monotonic", lambda: clock[0]):
                witness = self.witness(late)
            self.assertEqual(witness["failure_code"], "AUTHORITY_UNAVAILABLE")
            self.assertIs(witness["terminal_authority_failure"], True)
            self.assertEqual(calls, [self.gate.MANIFEST_PATH])
            self.assertNotIn("secret", json.dumps(witness))

    def test_request_and_final_digest_completion_deadlines_are_enforced(self):
        clock = [0]
        def late_response(revision, path, limit):
            clock[0] = 40
            return 200, self.expected[path]
        with patch.object(self.gate.time, "monotonic", lambda: clock[0]):
            self.assertEqual(self.witness(late_response)["failure_code"], "RESPONSE_DEADLINE")
        clock[0] = 0
        original_hash = self.gate.hashlib.sha256
        # Preflight also hashes README, so arm delay only once requests start.
        started = [False]
        def delay_after_request(raw=b""):
            if started[0] and raw == self.files["README.md"]:
                clock[0] = 41
            return original_hash(raw)
        with patch.object(self.gate.time, "monotonic", lambda: clock[0]), \
             patch.object(self.gate.hashlib, "sha256", delay_after_request):
            def request(revision, path, limit):
                started[0] = True
                return self.request(revision, path, limit)
            witness = self.witness(request)
        self.assertFalse(witness["complete"])
        self.assertEqual(witness["failure_code"], "RESPONSE_DEADLINE")

    def test_transport_faults_redirects_boolean_status_and_oversize_fail_closed(self):
        replies = [(302, b"secret redirect"), (True, b"secret"),
                   (200, b"x" * (self.gate.MAX_BYTES[self.gate.MANIFEST_PATH] + 1)),
                   (200, "not bytes")]
        for reply in replies:
            with self.subTest(reply_type=type(reply[1])):
                witness = self.witness(lambda *args: reply)
                self.assertFalse(witness["complete"])
                self.assertNotIn("secret", json.dumps(witness))
        def fault(*args):
            raise OSError("arbitrary secret transport error")
        self.assertEqual(self.witness(fault)["failure_code"], "TRANSPORT_UNAVAILABLE")
        self.assertNotIn("secret", json.dumps(self.witness(fault)))

    def test_fixed_reader_has_no_auth_redirect_or_fallback_and_checks_eof_deadline(self):
        gate, clock, calls = self.gate, [0], []
        state = {"status": 200, "headers": {}, "late_eof": False}
        class Response:
            def __init__(self): self.status = state["status"]
            def getheader(self, key): return state["headers"].get(key)
            def read1(self, limit):
                calls.append(("body", limit))
                if state["late_eof"]: clock[0] = 4
                return b""
        class Connection:
            def __init__(self, host, **kwargs):
                calls.append(("connection", host, kwargs["timeout"]))
                self.sock = SimpleNamespace(settimeout=lambda value: calls.append(("timeout", value)))
            def set_debuglevel(self, value): self.debug = value
            def request(self, method, target, headers): calls.append(("request", method, target, headers))
            def getresponse(self): return Response()
            def close(self): calls.append(("close",))
        with patch.object(gate.http.client, "HTTPSConnection", Connection), \
             patch.object(gate.time, "monotonic", lambda: clock[0]):
            self.assertEqual(gate.read_public(HUB, "config.json", gate.MAX_BYTES["config.json"]), (200, b""))
            request = next(row for row in calls if row[0] == "request")
            self.assertEqual(request[1:3], ("GET", f"/api/resolve-cache/spaces/SZLHOLDINGS/finance/{HUB}/config.json"))
            self.assertFalse(any(key.lower() == "authorization" for key in request[3]))
            for path in ("../app.py", "https://evil.invalid", "szl-artifact-manifest.json"):
                with self.assertRaises(gate.ProjectionError): gate.read_public(HUB, path, 64000)
            count = len(calls)
            state["status"] = 302
            self.assertEqual(gate.read_public(HUB, "config.json", gate.MAX_BYTES["config.json"]), (302, b""))
            self.assertFalse(any(row[0] == "body" for row in calls[count:]))
            state["status"] = 200
            state["headers"] = {"Content-Encoding": "gzip"}
            with self.assertRaisesRegex(gate.ProjectionError, "ENCODED_RESPONSE_DENIED"):
                gate.read_public(HUB, "config.json", gate.MAX_BYTES["config.json"])
            state["headers"] = {"Content-Length": "64001"}
            with self.assertRaisesRegex(gate.ProjectionError, "RESPONSE_TOO_LARGE"):
                gate.read_public(HUB, "config.json", gate.MAX_BYTES["config.json"])
            state["headers"] = {}
            state["late_eof"] = True
            with self.assertRaisesRegex(gate.ProjectionError, "RESPONSE_DEADLINE"):
                gate.read_public(HUB, "config.json", gate.MAX_BYTES["config.json"])

    def test_transient_witness_retries_but_authority_denial_is_invocation_terminal(self):
        renderer = self.renderer
        renderer._finance_payloads.update(self.files)
        row = {"source_revision": SOURCE, "workflow_run_id": RUN,
               "build_info": {"hf_revision": HUB}}
        negative = {"complete": False, "failure_code": "TRANSPORT_UNAVAILABLE"}
        good = self.witness()
        with patch.object(renderer._projection_module, "observe_projection", side_effect=[negative, good]) as observe:
            self.assertEqual(renderer._observe_finance_projection(row), negative)
            self.assertEqual(renderer._observe_finance_projection(row), good)
            self.assertEqual(renderer._observe_finance_projection(row), good)
            self.assertEqual(observe.call_count, 2)
        renderer._finance_witnesses.clear()
        denied = {"complete": False, "terminal_authority_failure": True,
                  "failure_code": "AUTHORITY_UNAVAILABLE"}
        with patch.object(renderer._projection_module, "observe_projection", return_value=denied) as observe:
            self.assertEqual(renderer._observe_finance_projection(row), denied)
            row["build_info"]["hf_revision"] = "3" * 40
            self.assertEqual(renderer._observe_finance_projection(row), denied)
            self.assertEqual(observe.call_count, 1)

    def test_pure_preflight_refusal_precedes_provider_or_credential_access(self):
        renderer = self.renderer
        renderer.FLAGSHIPS = tuple(row for row in renderer.FLAGSHIPS if row["slug"] == "finance")
        with patch.dict("os.environ", {"GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": str(RUN)}), \
             patch.object(renderer._BASE, "token_from_env", side_effect=AssertionError("credentials forbidden")), \
             patch.object(renderer._BASE, "HfApi", side_effect=AssertionError("provider forbidden")), \
             patch.object(renderer, "render_finance_payloads", side_effect=ValueError("invalid projection")):
            with self.assertRaisesRegex(ValueError, "invalid projection"):
                renderer.main()
        self.assertFalse(renderer._finance_upload_active)

    def test_upload_cannot_mutate_unknown_path_or_change_preflight_identity_bytes(self):
        renderer, calls = self.renderer, []
        renderer._finance_upload_active = True
        renderer._finance_source_identity = (SOURCE, RUN)
        renderer._finance_expected_payloads.update(self.files)
        api = SimpleNamespace(upload_file=lambda **kwargs: calls.append(kwargs))
        with patch.dict("os.environ", {"GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": str(RUN)}):
            for path, content in (("szl-artifact-manifest.json", "legacy"), ("app.py", "tampered")):
                with self.assertRaises(RuntimeError): renderer.upload_text(api, "SZLHOLDINGS/finance", path, content)
            renderer._finance_payloads["app.py"] = self.files["app.py"]
            with self.assertRaisesRegex(RuntimeError, "duplicate"):
                renderer.upload_text(api, "SZLHOLDINGS/finance", "app.py", self.files["app.py"].decode())
        with patch.dict("os.environ", {"GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": str(RUN + 1)}):
            with self.assertRaisesRegex(RuntimeError, "preflight"):
                renderer.upload_text(api, "SZLHOLDINGS/finance", "README.md", self.files["README.md"].decode())
        self.assertEqual(calls, [])

    def test_eight_actual_writer_payloads_match_pure_materializer_bytes(self):
        renderer, observed, actions = self.renderer, {}, []
        expected = load("materialize_finance_runtime").payloads(renderer, SOURCE, RUN)
        class RecordingApi:
            def repo_exists(self, **kwargs):
                self_repo = kwargs["repo_id"]
                if self_repo != "SZLHOLDINGS/finance": raise AssertionError(self_repo)
                return True
            def auth_check(self, **kwargs):
                if kwargs != {"repo_id": "SZLHOLDINGS/finance", "repo_type": "space", "write": True}:
                    raise AssertionError("unscoped fixture authorization")
            def upload_file(self, **kwargs):
                if kwargs["repo_id"] != "SZLHOLDINGS/finance": raise AssertionError("sibling mutation")
                if kwargs["path_in_repo"] in observed: raise AssertionError("duplicate upload")
                observed[kwargs["path_in_repo"]] = kwargs["path_or_fileobj"]
                actions.append(kwargs["path_in_repo"])
            def restart_space(self, repo_id):
                if repo_id != "SZLHOLDINGS/finance": raise AssertionError("sibling restart")
        renderer.FLAGSHIPS = tuple(row for row in renderer.FLAGSHIPS if row["slug"] == "finance")
        before = os.getcwd()
        try:
            with tempfile.TemporaryDirectory(prefix="szl-finance-projection-test-") as output, \
                 patch.dict("os.environ", {"GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": str(RUN)}), \
                 patch.object(renderer._BASE, "token_from_env", return_value=("INERT_TEST_TOKEN", "SIMULATED")), \
                 patch.object(renderer._BASE, "HfApi", return_value=RecordingApi()), \
                 patch.object(renderer._BASE, "load_terra_forge_bundle", return_value=("UNUSED_TEST_FIXTURE", {})), \
                 patch.object(renderer._BASE, "observe_flagship", return_value=None), \
                 patch.object(renderer._BASE, "observation_passes", return_value=True), \
                 patch("builtins.print"):
                try:
                    os.chdir(output)
                    self.assertEqual(renderer.main(), 0)
                finally:
                    # Windows cannot remove a temporary current directory.
                    os.chdir(before)
        finally:
            os.chdir(before)
        self.assertEqual(observed, expected)
        self.assertEqual(len(actions), 8)
        self.assertEqual(actions[-1], self.gate.MANIFEST_PATH)
        self.assertNotIn(self.gate.LEGACY_MANIFEST_PATH, observed)
        self.assertFalse(renderer._finance_upload_active)

    def test_current_card_presentation_remains_present_with_finance_evidence_only(self):
        renderer = self.renderer
        for item in renderer.FLAGSHIPS:
            card = renderer.readme(item)
            if item["slug"] in ("terra", "sentra", "counsel", "finance"):
                self.assertIn("<!-- szl:card-presentation:v1 -->", card)
                self.assertIn("<!-- szl:preserved-source-body:start -->", card)
                self.assertIn("<!-- szl:preserved-source-body:end -->", card)
            self.assertEqual("## Current projection evidence" in card, item["slug"] == "finance")


if __name__ == "__main__":
    unittest.main()
