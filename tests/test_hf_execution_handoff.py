#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline negative tests. Fixture keys confer no production authority."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hf_execution_handoff", ROOT / ".github/scripts/admit_execution_handoff.py")
HANDOFF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HANDOFF)


class ExecutionHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pins = {"schema": "szl.execution-authority-pins/v1"}
        for role in ("approval", "runtime"):
            public = ec.generate_private_key(ec.SECP256R1()).public_key()
            pins[role + "_public_pem"] = public.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
            normalized = pins[role + "_public_pem"].encode().strip()
            pins[role + "_key_id"] = hashlib.sha256(normalized).hexdigest()
        cls.env = {
            "GITHUB_EVENT_NAME": "workflow_dispatch", "VERIFY_CURRENT_DEPLOYMENT": "true",
            "OPEN_DEPLOY_WINDOW": "false", "PUBLISH_VERTICAL_FLAGSHIPS": "false",
            "A11OY_EXECUTION_HF_REVISION": "b" * 40, "A11OY_EXECUTION_BOOT_ID": "fixture-boot",
            "A11OY_EXECUTION_RUN_NONCE": "c" * 64,
            "A11OY_EXECUTION_AUTHORITY_PINS_JSON": json.dumps(pins),
        }
        cls.pins = pins

    def context(self, **changes):
        return HANDOFF.independent_context("a" * 40, {**self.env, **changes})

    def test_verification_requires_manual_and_no_mutation_flags(self):
        self.assertTrue(HANDOFF.validate_invocation(self.env))
        for change in ({"GITHUB_EVENT_NAME": "push"}, {"OPEN_DEPLOY_WINDOW": "true"},
                       {"PUBLISH_VERTICAL_FLAGSHIPS": "true"}, {"VERTICAL_PLAN_JSON": "{}"},
                       {"VERIFY_CURRENT_DEPLOYMENT": "True"}):
            with self.subTest(change=change), self.assertRaises(HANDOFF.HandoffBlocked):
                HANDOFF.validate_invocation({**self.env, **change})
        self.assertFalse(HANDOFF.validate_invocation({"GITHUB_EVENT_NAME": "push"}))

    def test_each_independent_context_field_is_required_before_network(self):
        with mock.patch.object(HANDOFF, "admit") as network:
            for field in ("HF_REVISION", "BOOT_ID", "RUN_NONCE"):
                for missing in ("", " "):
                    with self.subTest(field=field, missing=missing):
                        with self.assertRaisesRegex(HANDOFF.HandoffBlocked, "EXECUTION_CONTEXT_REQUIRED"):
                            self.context(**{"A11OY_EXECUTION_" + field: missing})
            network.assert_not_called()

    def test_run_2164_missing_context_retains_names_without_values(self):
        names = HANDOFF.CONTEXT_VARIABLES
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, failure, github = (root / name for name in
                                       ("handoff.json", "handoff-failure.json", "outputs.txt"))
            summary = root / "summary.md"
            env = {**self.env, **{name: "" for name in names},
                   "A11OY_CODE_ADMIN_KEY": "private-credential-value"}
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(HANDOFF, "collector") as collector, \
                    redirect_stderr(stderr):
                result = HANDOFF.main([
                    "--source-sha", "a" * 40, "--output", str(output),
                    "--failure-output", str(failure), "--github-output", str(github),
                ])
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())
            self.assertFalse(github.exists())
            collector.assert_not_called()
            report = json.loads(failure.read_bytes())
            self.assertEqual(report, {
                "schema": "szl.execution-handoff-failure/v1",
                "source_revision": "a" * 40,
                "stage": "CONTEXT_CONFIGURATION",
                "error": "EXECUTION_CONTEXT_REQUIRED",
                "context_frozen": False,
                "execution_authorized": False,
                "export_collected": False,
                "provider_state_changed": False,
                "missing_variables": list(names),
            })
            self.assertEqual(json.loads(stderr.getvalue()), report)
            self.assertNotIn("private-credential-value", failure.read_text())

            with mock.patch.dict(os.environ, {
                "HANDOFF_OWNER_BEFORE_OUTCOME": "success",
                "HANDOFF_CONTEXT_OUTCOME": "failure",
                "HANDOFF_OWNER_AFTER_OUTCOME": "skipped",
            }, clear=True), redirect_stdout(io.StringIO()):
                result = HANDOFF.main([
                    "--record-workflow-failure", "--source-sha", "a" * 40,
                    "--failure-output", str(failure), "--summary-output", str(summary),
                ])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(failure.read_bytes()), report)
            summary_text = summary.read_text(encoding="utf-8")
            self.assertIn("independently admitted context is missing", summary_text)
            for name in names:
                self.assertIn(name, summary_text)
            self.assertIn("cannot select these values", summary_text)

    def test_run_2162_supersession_retains_distinct_failure_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failure, summary = root / "handoff-failure.json", root / "summary.md"
            env = {
                "HANDOFF_OWNER_BEFORE_OUTCOME": "failure",
                "HANDOFF_OWNER_BEFORE_STATUS": "SUPERSEDED_BY_NEWER_MAIN",
                "HANDOFF_CONTEXT_OUTCOME": "skipped",
                "HANDOFF_OWNER_AFTER_OUTCOME": "skipped",
            }
            with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()):
                result = HANDOFF.main([
                    "--record-workflow-failure", "--source-sha", "a" * 40,
                    "--failure-output", str(failure), "--summary-output", str(summary),
                ])
            self.assertEqual(result, 0)
            report = json.loads(failure.read_bytes())
            self.assertEqual(report["stage"], "SOURCE_OWNERSHIP_BEFORE")
            self.assertEqual(report["error"], "SUPERSEDED_BY_NEWER_MAIN")
            self.assertFalse(report["provider_state_changed"])
            summary_text = summary.read_text(encoding="utf-8")
            self.assertIn("SUPERSEDED_BY_NEWER_MAIN", summary_text)
            self.assertIn("newer protected main", summary_text)
            self.assertNotIn("complete the approved bounded execution", summary_text)

    def test_exact_context_and_independent_public_pins_are_required(self):
        changes = [
            {"A11OY_EXECUTION_HF_REVISION": "main"},
            {"A11OY_EXECUTION_RUN_NONCE": "c" * 64 + "\ninjected=true"},
            {"A11OY_EXECUTION_AUTHORITY_PINS_JSON": "{}"},
            {"A11OY_EXECUTION_AUTHORITY_PINS_JSON": "{}" * 9000},
            {"A11OY_EXECUTION_AUTHORITY_PINS_JSON": '{"schema":1,"schema":2}'},
            {"A11OY_EXECUTION_AUTHORITY_FILE": "untrusted.json"},
            {"A11OY_EXECUTION_AUTHORITY_FILE": ""},
        ]
        same_key = dict(self.pins, approval_public_pem=self.pins["runtime_public_pem"],
                        approval_key_id=self.pins["runtime_key_id"])
        changes.append({"A11OY_EXECUTION_AUTHORITY_PINS_JSON": json.dumps(same_key)})
        for change in changes:
            with self.subTest(field=next(iter(change))), self.assertRaises(ValueError):
                self.context(**change)
        with self.assertRaises(ValueError):
            HANDOFF.independent_context("main", self.env)

    def test_two_identity_bound_readbacks_must_match(self):
        context, pins = self.context()
        snapshot = {"storage_epoch": 1, "store_ids": ["fixture"]}
        with mock.patch.object(HANDOFF.collector(), "bracket", side_effect=[snapshot, snapshot]) as read:
            report = HANDOFF.admit(object(), context, pins)
        self.assertEqual(read.call_count, 2)
        self.assertFalse(report["execution_authorized"])
        self.assertFalse(report["export_collected"])
        self.assertFalse(report["provider_state_changed"])
        self.assertEqual(report["source_revision"], context.source_revision)
        with mock.patch.object(HANDOFF.collector(), "bracket", side_effect=[snapshot, {"storage_epoch": 2}]):
            with self.assertRaisesRegex(HANDOFF.HandoffBlocked, "SOURCE_RUNTIME_OR_STORAGE_CHANGED"):
                HANDOFF.admit(object(), context, pins)

    def test_invalid_context_retains_fixed_reason_without_values_or_network(self):
        cases = [
            ({"A11OY_EXECUTION_RUN_NONCE": "c" * 32}, "RUN_NONCE_REQUIRED"),
            ({"A11OY_EXECUTION_RUN_NONCE": "private-input-value"}, "RUN_NONCE_REQUIRED"),
            ({"A11OY_EXECUTION_HF_REVISION": "main"}, "EXACT_EXECUTION_REVISIONS_REQUIRED"),
            ({"A11OY_EXECUTION_BOOT_ID": " fixture-boot"}, "RUNTIME_BOOT_REQUIRED"),
        ]
        for pins, expected in (
            (dict(self.pins, approval_key_id=self.pins["runtime_key_id"]),
             "SEPARATE_APPROVAL_AUTHORITY_REQUIRED"),
            (dict(self.pins, approval_key_id="short"), "PUBLIC_KEY_PIN_REQUIRED"),
            (dict(self.pins, approval_public_pem="not a public key"), "INVALID_PUBLIC_KEY"),
            (dict(self.pins, approval_key_id="f" * 64), "PUBLIC_KEY_PIN_MISMATCH"),
        ):
            cases.append(({"A11OY_EXECUTION_AUTHORITY_PINS_JSON": json.dumps(pins)}, expected))
        for changes, expected in cases:
            with self.subTest(reason=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output, failure, github = (root / name for name in
                                           ("handoff.json", "failure.json", "outputs.txt"))
                stderr = io.StringIO()
                with mock.patch.dict(os.environ, {**self.env, **changes}, clear=True), \
                        mock.patch.object(HANDOFF, "admit") as network, redirect_stderr(stderr):
                    result = HANDOFF.main([
                        "--source-sha", "a" * 40, "--output", str(output),
                        "--failure-output", str(failure), "--github-output", str(github),
                    ])
                self.assertEqual(result, 2)
                network.assert_not_called()
                self.assertFalse(output.exists())
                self.assertFalse(github.exists())
                report = json.loads(failure.read_bytes())
                self.assertEqual(report["stage"], "CONTEXT_CONFIGURATION")
                self.assertEqual(report["error"], expected)
                self.assertFalse(report["context_frozen"])
                self.assertFalse(report["execution_authorized"])
                self.assertFalse(report["provider_state_changed"])
                self.assertEqual(json.loads(stderr.getvalue()), report)
                self.assertNotIn("private-input-value", failure.read_text())
                self.assertNotIn("PUBLIC KEY", failure.read_text())

    def test_frozen_outputs_ignore_later_environment_changes(self):
        context, pins = self.context()
        with mock.patch.dict(os.environ, {"A11OY_EXECUTION_HF_REVISION": "d" * 40}):
            outputs = dict(line.split("=", 1) for line in HANDOFF.frozen_outputs(context, pins).splitlines())
        self.assertEqual(outputs["hf_revision"], "b" * 40)
        self.assertEqual(outputs["run_nonce"], "c" * 64)
        self.assertEqual(json.loads(outputs["authority_pins"]), pins)
        self.assertEqual(len(outputs), 4)

    def test_context_reason_classifier_never_echoes_unknown_or_untyped_errors(self):
        gate = HANDOFF.collector().gate
        errors = (
            gate.CombinedEvidenceError("private-input-value"),
            gate.acceptance.EvidenceError("UNKNOWN_PROVIDER_CODE"),
            gate.CombinedEvidenceError("RUN_NONCE_REQUIRED\nprivate-input-value"),
            ValueError("RUN_NONCE_REQUIRED"),
        )
        for error in errors:
            with self.subTest(kind=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                failure, output, github = (root / name for name in
                                           ("failure.json", "handoff.json", "outputs.txt"))
                stderr = io.StringIO()
                with mock.patch.dict(os.environ, self.env, clear=True), \
                        mock.patch.object(gate, "_context", side_effect=error), \
                        mock.patch.object(HANDOFF, "admit") as network, redirect_stderr(stderr):
                    result = HANDOFF.main([
                        "--source-sha", "a" * 40, "--output", str(output),
                        "--failure-output", str(failure), "--github-output", str(github),
                    ])
                self.assertEqual(result, 2)
                network.assert_not_called()
                self.assertFalse(output.exists())
                self.assertFalse(github.exists())
                report = json.loads(failure.read_bytes())
                self.assertEqual(report["error"], "EXECUTION_HANDOFF_UNAVAILABLE")
                self.assertEqual(json.loads(stderr.getvalue()), report)
                self.assertNotIn("private-input-value", failure.read_text())
                self.assertNotIn("UNKNOWN_PROVIDER_CODE", failure.read_text())

    def test_failed_admission_emits_no_outputs_or_provider_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            failure = Path(directory) / "handoff-failure.json"
            github = Path(directory) / "outputs.txt"
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(HANDOFF, "admit", side_effect=RuntimeError("private-provider-data")), \
                    redirect_stderr(stderr):
                result = HANDOFF.main([
                    "--source-sha", "a" * 40, "--output", str(output),
                    "--failure-output", str(failure), "--github-output", str(github),
                ])
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())
            self.assertFalse(github.exists())
            self.assertNotIn("private-provider-data", stderr.getvalue())
            self.assertIn("EXECUTION_HANDOFF_UNAVAILABLE", stderr.getvalue())
            report = json.loads(failure.read_bytes())
            self.assertEqual(report["stage"], "RUNTIME_READBACK")
            self.assertEqual(report["error"], "EXECUTION_HANDOFF_UNAVAILABLE")
            self.assertNotIn("private-provider-data", failure.read_text())

            summary = Path(directory) / "summary.md"
            with mock.patch.dict(os.environ, {
                "HANDOFF_OWNER_BEFORE_OUTCOME": "success",
                "HANDOFF_CONTEXT_OUTCOME": "failure",
                "HANDOFF_OWNER_AFTER_OUTCOME": "skipped",
            }, clear=True), redirect_stdout(io.StringIO()):
                result = HANDOFF.main([
                    "--record-workflow-failure", "--source-sha", "a" * 40,
                    "--failure-output", str(failure), "--summary-output", str(summary),
                ])
            self.assertEqual(result, 0)
            self.assertIn("RUNTIME_READBACK", summary.read_text())
            self.assertIn("EXECUTION_HANDOFF_UNAVAILABLE", summary.read_text())

    def test_successful_cli_emits_only_validated_frozen_public_context(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            failure = Path(directory) / "handoff-failure.json"
            github = Path(directory) / "outputs.txt"
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(HANDOFF, "admit", return_value={"execution_authorized": False}) as read, \
                    redirect_stdout(io.StringIO()):
                result = HANDOFF.main([
                    "--source-sha", "a" * 40, "--output", str(output),
                    "--failure-output", str(failure), "--github-output", str(github),
                ])
            self.assertEqual(result, 0)
            self.assertEqual(read.call_count, 1)
            self.assertFalse(failure.exists())
            self.assertEqual(json.loads(output.read_bytes()), {"execution_authorized": False})
            values = dict(line.split("=", 1) for line in github.read_text().splitlines())
            self.assertEqual(values["hf_revision"], self.env["A11OY_EXECUTION_HF_REVISION"])
            self.assertEqual(values["run_nonce"], self.env["A11OY_EXECUTION_RUN_NONCE"])
            self.assertEqual(json.loads(values["authority_pins"]), self.pins)

    def test_existing_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            output.write_bytes(b"preserve")
            failure = Path(directory) / "handoff-failure.json"
            github = Path(directory) / "outputs.txt"
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(HANDOFF, "admit", return_value={"fixture": True}), \
                    redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                result = HANDOFF.main([
                    "--source-sha", "a" * 40, "--output", str(output),
                    "--failure-output", str(failure), "--github-output", str(github),
                ])
            self.assertEqual(result, 2)
            self.assertEqual(output.read_bytes(), b"preserve")
            self.assertFalse(github.exists())
            self.assertEqual(json.loads(failure.read_bytes())["stage"], "OUTPUT_PUBLICATION")

    def test_existing_failure_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, failure, github = (root / name for name in
                                       ("handoff.json", "handoff-failure.json", "outputs.txt"))
            failure.write_bytes(b"preserve-failure")
            with mock.patch.dict(os.environ, {**self.env, "A11OY_EXECUTION_BOOT_ID": ""}, clear=True), \
                    mock.patch.object(HANDOFF, "collector") as collector, \
                    redirect_stderr(io.StringIO()):
                result = HANDOFF.main([
                    "--source-sha", "a" * 40, "--output", str(output),
                    "--failure-output", str(failure), "--github-output", str(github),
                ])
            self.assertEqual(result, 2)
            self.assertEqual(failure.read_bytes(), b"preserve-failure")
            self.assertFalse(output.exists())
            self.assertFalse(github.exists())
            collector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
