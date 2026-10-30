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

    def test_frozen_outputs_ignore_later_environment_changes(self):
        context, pins = self.context()
        with mock.patch.dict(os.environ, {"A11OY_EXECUTION_HF_REVISION": "d" * 40}):
            outputs = dict(line.split("=", 1) for line in HANDOFF.frozen_outputs(context, pins).splitlines())
        self.assertEqual(outputs["hf_revision"], "b" * 40)
        self.assertEqual(outputs["run_nonce"], "c" * 64)
        self.assertEqual(json.loads(outputs["authority_pins"]), pins)
        self.assertEqual(len(outputs), 4)

    def test_failed_admission_emits_no_outputs_or_provider_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            github = Path(directory) / "outputs.txt"
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(HANDOFF, "admit", side_effect=RuntimeError("private-provider-data")), \
                    redirect_stderr(stderr):
                result = HANDOFF.main(["--source-sha", "a" * 40, "--output", str(output),
                                       "--github-output", str(github)])
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())
            self.assertFalse(github.exists())
            self.assertNotIn("private-provider-data", stderr.getvalue())
            self.assertIn("EXECUTION_HANDOFF_UNAVAILABLE", stderr.getvalue())

    def test_successful_cli_emits_only_validated_frozen_public_context(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            github = Path(directory) / "outputs.txt"
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(HANDOFF, "admit", return_value={"execution_authorized": False}) as read, \
                    redirect_stdout(io.StringIO()):
                result = HANDOFF.main(["--source-sha", "a" * 40, "--output", str(output),
                                       "--github-output", str(github)])
            self.assertEqual(result, 0)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(json.loads(output.read_bytes()), {"execution_authorized": False})
            values = dict(line.split("=", 1) for line in github.read_text().splitlines())
            self.assertEqual(values["hf_revision"], self.env["A11OY_EXECUTION_HF_REVISION"])
            self.assertEqual(values["run_nonce"], self.env["A11OY_EXECUTION_RUN_NONCE"])
            self.assertEqual(json.loads(values["authority_pins"]), self.pins)

    def test_existing_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            output.write_bytes(b"preserve")
            github = Path(directory) / "outputs.txt"
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(HANDOFF, "admit", return_value={"fixture": True}), \
                    redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                result = HANDOFF.main(["--source-sha", "a" * 40, "--output", str(output),
                                       "--github-output", str(github)])
            self.assertEqual(result, 2)
            self.assertEqual(output.read_bytes(), b"preserve")
            self.assertFalse(github.exists())


if __name__ == "__main__":
    unittest.main()
