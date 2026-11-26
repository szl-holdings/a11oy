# SPDX-License-Identifier: Apache-2.0
"""Adversarial, no-credential/no-task tests for the Windows host preflight."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import host_preflight as h

TIME = "2026-11-19T09:23:10+00:00"


def sample(*, ready=False):
    return {
        "schema": h.OBS_SCHEMA, "observed_utc": TIME,
        "mutable_actions": 0, "credential_bytes_read": False,
        "task": {
            "present": True, "enabled": ready,
            "state": "Running" if ready else "Disabled",
            "action_count": 1, "binary_exists": True,
            "binary_is_pythonw": True,
            "python_probe_attempted": True, "python_probe_passed": ready,
            "uses_isolated_flag": True,
            "uses_no_bytecode_flag": True, "targets_private_bootstrap": True,
            "native_retry_count": 0,
            "last_result": 0 if ready else 2147942402,
        },
        "runtime": {
            "dir_exists": ready, "bootstrap_exists": ready,
            "supervisor_exists": ready, "transport_exists": ready,
            "ssh_config_exists": ready, "source_files_count": 4 if ready else 0,
        },
        "ports": {
            "readback_available": True, "loopback_gateway_listening": ready,
            "loopback_tunnel_listening": ready,
            "foreign_4000_listening": True,
        },
    }


def codes(value):
    return set(h.assess(value)["reason_codes"])


class HostPreflightTests(unittest.TestCase):
    def test_current_host_blocks_instead_of_production_promotion(self):
        d = h.assess(sample())
        self.assertEqual(d["state"], "HOLD")
        for need in (
            "SCHEDULED_TASK_DISABLED", "SCHEDULED_TASK_NOT_RUNNING",
            "HISTORIC_TASK_FILE_NOT_FOUND", "PRIVATE_RUNTIME_DIRECTORY_MISSING",
            "PRIVATE_BOOTSTRAP_MISSING", "PRIVATE_SUPERVISOR_MISSING",
            "PRIVATE_TRANSPORT_CONFIG_MISSING", "PINNED_SOURCE_BUNDLE_INCOMPLETE",
            "GATEWAY_4001_NOT_OBSERVED", "OWNED_TUNNEL_19484_NOT_OBSERVED",
        ):
            self.assertIn(need, d["reason_codes"])

    def test_apparently_complete_host_only_structural(self):
        d = h.assess(sample(ready=True))
        self.assertEqual(d["state"], "STRUCTURAL_ONLY")
        self.assertEqual(d["reason_count"], 0)
        for field in ("production_authorized", "signer_verified",
                      "source_sha_independently_verified",
                      "fresh_signed_startup_receipt_verified",
                      "owned_child_pid_ancestry_verified",
                      "authenticated_model_inference_verified",
                      "task_started_by_this_tool",
                      "credentials_read", "external_effects_performed"):
            self.assertIs(d[field], False, field)

    def test_foreign_ollama_port_is_not_an_adoption_target(self):
        d = sample(ready=True)
        d["ports"]["foreign_4000_listening"] = False
        self.assertEqual(h.assess(d)["state"], "STRUCTURAL_ONLY")
        self.assertFalse(h.assess(d)["foreign_4000_listener_observed"])

    def test_disabled_task_with_all_files_still_blocks(self):
        d = sample(ready=True)
        d["task"]["enabled"] = False
        d["task"]["state"] = "Disabled"
        self.assertIn("SCHEDULED_TASK_DISABLED", codes(d))

    def test_missing_task_is_explicit(self):
        d = sample(ready=True)
        d["task"].update(present=False, enabled=False, state="UNAVAILABLE",
                         action_count=0, native_retry_count=None,
                         last_result=None)
        self.assertIn("SCHEDULED_TASK_MISSING", codes(d))

    def test_missing_binary_with_existing_source_is_hold(self):
        d = sample(ready=True)
        d["task"]["binary_exists"] = False
        self.assertIn("SCHEDULED_TASK_BINARY_MISSING", codes(d))

    def test_executable_exists_but_stdlib_fails(self):
        d = sample(ready=True)
        d["task"]["python_probe_passed"] = False
        self.assertIn("TASK_INTERPRETER_STDLIB_IMPORT_FAILED", codes(d))
        self.assertEqual(h.assess(d)["state"], "HOLD")

    def test_unapproved_interpreter_not_executed_and_not_assumed_ok(self):
        d = sample(ready=True)
        d["task"]["python_probe_attempted"] = False
        d["task"]["python_probe_passed"] = False
        self.assertIn("TASK_INTERPRETER_STDLIB_PROBE_UNAVAILABLE", codes(d))

    def test_unexpected_executable_denied(self):
        d = sample(ready=True)
        d["task"]["binary_is_pythonw"] = False
        self.assertIn("SCHEDULED_TASK_BINARY_NOT_PYTHONW", codes(d))

    def test_isolation_flags_required(self):
        for key in ("uses_isolated_flag", "uses_no_bytecode_flag"):
            d = sample(ready=True)
            d["task"][key] = False
            with self.subTest(key=key):
                self.assertIn("SCHEDULED_TASK_PYTHON_ISOLATION_MISSING", codes(d))

    def test_action_must_reference_private_bootstrap(self):
        d = sample(ready=True)
        d["task"]["targets_private_bootstrap"] = False
        self.assertIn("SCHEDULED_TASK_BOOTSTRAP_TARGET_DRIFT", codes(d))

    def test_more_than_one_action_does_not_pass(self):
        d = sample(ready=True)
        d["task"]["action_count"] = 2
        self.assertIn("SCHEDULED_TASK_ACTION_COUNT_INVALID", codes(d))

    def test_native_scheduler_retry_forbidden(self):
        d = sample(ready=True)
        d["task"]["native_retry_count"] = 1
        self.assertIn("SCHEDULED_TASK_NATIVE_RETRY_ENABLED", codes(d))

    def test_unknown_native_retry_is_not_assumed_zero(self):
        d = sample(ready=True)
        d["task"]["native_retry_count"] = None
        self.assertIn("SCHEDULED_TASK_NATIVE_RETRY_UNVERIFIED", codes(d))

    def test_incomplete_source_bundle_is_not_full_admission(self):
        d = sample(ready=True)
        d["runtime"]["source_files_count"] = 3
        self.assertIn("PINNED_SOURCE_BUNDLE_INCOMPLETE", codes(d))

    def test_missing_ssh_is_hold(self):
        d = sample(ready=True)
        d["runtime"]["ssh_config_exists"] = False
        self.assertIn("PRIVATE_SSH_CONFIG_MISSING", codes(d))

    def test_port_readback_unavailable_not_empty(self):
        d = sample(ready=True)
        d["ports"]["readback_available"] = False
        result = h.assess(d)
        self.assertIn("LISTENER_READBACK_UNAVAILABLE", result["reason_codes"])
        self.assertEqual(result["state"], "HOLD")

    def test_gateway_and_tunnel_are_independent(self):
        for key,code in (("loopback_gateway_listening","GATEWAY_4001_NOT_OBSERVED"),
                         ("loopback_tunnel_listening","OWNED_TUNNEL_19484_NOT_OBSERVED")):
            d = sample(ready=True)
            d["ports"][key] = False
            with self.subTest(key=key):
                self.assertIn(code, codes(d))

    def test_historic_file_not_found_not_hidden(self):
        d = sample(ready=True)
        d["task"]["last_result"] = 2147942402
        self.assertIn("HISTORIC_TASK_FILE_NOT_FOUND", codes(d))

    def test_credentials_recorded_claim_is_refused(self):
        d = sample(ready=True)
        d["credential_bytes_read"] = True
        with self.assertRaisesRegex(h.PreflightInputError,
                                     "OBSERVATION_EFFECT_CLAIM_INVALID"):
            h.assess(d)

    def test_adding_credentials_field_refused(self):
        d = sample(ready=True)
        d["db_password"] = "synthetic-test-not-a-secret"
        with self.assertRaisesRegex(h.PreflightInputError, "OBSERVATION_FIELDS_INVALID"):
            h.assess(d)

    def test_task_args_cannot_be_smuggled(self):
        d = sample(ready=True)
        d["task"]["command_line"] = "synthetic-test"
        with self.assertRaisesRegex(h.PreflightInputError, "OBSERVATION_FIELDS_INVALID"):
            h.assess(d)

    def test_bad_type_boolean_is_rejected(self):
        d = sample(ready=True)
        d["task"]["enabled"] = "true"
        with self.assertRaisesRegex(h.PreflightInputError, "OBSERVATION_TYPE_INVALID"):
            h.assess(d)

    def test_source_count_boolean_is_rejected(self):
        d = sample(ready=True)
        d["runtime"]["source_files_count"] = True
        with self.assertRaisesRegex(h.PreflightInputError, "OBSERVATION_TYPE_INVALID"):
            h.assess(d)

    def test_source_count_above_limit_refused(self):
        d = sample(ready=True)
        d["runtime"]["source_files_count"] = 999
        with self.assertRaisesRegex(h.PreflightInputError, "RUNTIME_SOURCE_COUNT_INVALID"):
            h.assess(d)

    def test_duplicate_json_keys_refused(self):
        with self.assertRaisesRegex(h.PreflightInputError, "DUPLICATE_JSON_KEY"):
            h.parse(b'{"schema":"a","schema":"b"}')

    def test_nonfinite_json_refused(self):
        with self.assertRaisesRegex(h.PreflightInputError, "NONFINITE_JSON_NUMBER"):
            h.parse(b'{"v":NaN}')

    def test_large_input_refused(self):
        with self.assertRaisesRegex(h.PreflightInputError, "OBSERVATION_SIZE_INVALID"):
            h.parse(b" " * 20000)

    def test_naive_timestamp_refused(self):
        d = sample(ready=True)
        d["observed_utc"] = "2026-11-19T09:23:10"
        with self.assertRaisesRegex(h.PreflightInputError, "OBSERVATION_TIME_INVALID"):
            h.assess(d)

    def test_windows_readback_uses_only_passive_task_and_port_commands(self):
        script = h.WINDOWS_READBACK
        for name in ("Get-ScheduledTask", "Get-ScheduledTaskInfo",
                     "Get-NetTCPConnection", "Test-Path"):
            self.assertIn(name, script)
        for forbidden in ("Start-ScheduledTask", "Stop-ScheduledTask",
                          "Set-ScheduledTask", "Restart-Service",
                          "Remove-Item", "Stop-Process", "Start-Process",
                          "Get-Content", "Get-ItemProperty", "ReadAllBytes",
                          "gateway-audit-p256", "gateway-bearer.key"):
            self.assertNotIn(forbidden, script)

    def test_isolation_flags_use_case_sensitive_powershell_matching(self):
        # PowerShell -match accepts -i as -I; only -cmatch preserves the
        # actual Python interpreter flag semantics.
        script = h.WINDOWS_READBACK
        for flag in ("I", "B"):
            with self.subTest(flag=flag):
                expression = rf"$argsText -cmatch '(?<!\S)-{flag}(?!\S)'"
                self.assertIn(expression, script)

    def test_collector_unavailable_cannot_claim_structural(self):
        with mock.patch.object(h.sys, "platform", "win32"), \
                mock.patch.object(h.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stdout = b""
            with self.assertRaisesRegex(h.PreflightInputError,
                                         "WINDOWS_READBACK_UNAVAILABLE"):
                h.collect_native()
            self.assertEqual(run.call_count, 1)

    def test_collector_decodes_only_fixed_json_no_shell_side_effect(self):
        data = json.dumps(sample(ready=True)).encode()
        with mock.patch.object(h.sys, "platform", "win32"), \
                mock.patch.object(h.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = data
            self.assertEqual(h.collect_native()["task"]["state"], "Running")
            args = run.call_args.args[0]
            self.assertEqual(args[:3],
                             ["powershell.exe", "-NoProfile", "-NonInteractive"])
            self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_cli_exclusive_output_and_nonauthority(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "gateway-observation.json"
            with mock.patch.object(h, "collect_native", return_value=sample()):
                self.assertEqual(h.main(["--output", str(target)]), 2)
                self.assertTrue(target.exists())
                receipt = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(receipt["state"], "HOLD")
                self.assertFalse(receipt["production_authorized"])
                self.assertEqual(h.main(["--output", str(target)]), 3)

    def test_cli_malformed_input_unavailable(self):
        with mock.patch.object(h, "collect_native",
                               side_effect=h.PreflightInputError("WINDOWS_READBACK_UNAVAILABLE")):
            self.assertEqual(h.main([]), 3)


if __name__ == "__main__":
    unittest.main()
