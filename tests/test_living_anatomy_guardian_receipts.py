#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline fault injection for the guardian's actual inline workflow program."""

from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import sys
import textwrap
from types import ModuleType, SimpleNamespace
import unittest
import urllib.error
from unittest.mock import Mock, patch


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/hf-living-anatomy-guardian.yml"
SOURCE_SHA = "1" * 40
HF_SHA = "2" * 40
BRAIN_SHA = "3" * 40


class GuardianReceiptTest(unittest.TestCase):
    def run_guardian(self, *, private=False, stage="RUNNING", hardware="cpu-basic",
                     failure=None, timeout=False, missing_token=False, host=None,
                     unrouted_alias=False):
        source = WORKFLOW.read_text(encoding="utf-8")
        inline = source.split("python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
        program = compile(textwrap.dedent(inline), str(WORKFLOW), "exec")
        declared = "https://fixture-owner-anatomy.hf.space"
        resolved = declared if host is None else host
        info = SimpleNamespace(private=private, sha=HF_SHA, host=resolved)
        runtime = SimpleNamespace(stage=stage, hardware=hardware)
        api = Mock()
        api.space_info.return_value = info
        api.get_space_runtime.return_value = runtime

        def update_settings(**kwargs):
            info.private = kwargs["private"]

        def restart(**kwargs):
            if failure == "restart":
                raise RuntimeError("403 Forbidden: cpu-basic quota exhausted")
            runtime.stage = "RUNNING"

        api.update_repo_settings.side_effect = update_settings
        api.restart_space.side_effect = restart
        if failure == "visibility":
            api.update_repo_settings.side_effect = RuntimeError("visibility denied")
        if failure == "sleep":
            api.set_space_sleep_time.side_effect = RuntimeError("sleep policy denied")

        def urlopen(request, timeout):
            url = request.full_url
            if unrouted_alias and url.startswith(declared):
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, BytesIO(b"missing"))
            if url.startswith("https://evil.example"):
                raise AssertionError(f"refused host was fetched: {url}")
            if url.startswith("https://api.github.com/"):
                payload = {"sha": SOURCE_SHA}
            elif "/living-health" in url:
                payload = {"ready": failure != "readiness"}
            elif "/brain/health" in url:
                payload = {"ready": True, "chunk_count": 575,
                           "private_graph_nodes_loaded": 0, "content_access": "HANDLES_ONLY",
                           "source_revision": BRAIN_SHA}
            elif "/.well-known/szl-source.json" in url:
                payload = {"alignment_state": "SOURCE_BOUND_DEPLOYMENT",
                           "source": {"repository": "szl-holdings/anatomy", "commit": SOURCE_SHA},
                           "deployment": {"hf_revision": HF_SHA}}
            else:
                raise AssertionError(f"unexpected request: {url}")
            return BytesIO(json.dumps(payload).encode())

        module = ModuleType("huggingface_hub")
        module.HfApi = Mock(return_value=api)
        env = {"SPACE_ID": "fixture-owner/anatomy",
               "SPACE_ORIGIN": "https://fixture-owner-anatomy.hf.space",
               "SOURCE_REPOSITORY": "szl-holdings/anatomy"}
        if not missing_token:
            env["HF_TOKEN"] = "offline-test-token"
        written = []

        def write_receipt(path, data, **kwargs):
            self.assertEqual("living-anatomy-guardian-receipt.json", path.name)
            written.append(json.loads(data))
            return len(data)

        error = None
        with patch.dict(sys.modules, {"huggingface_hub": module}), \
                patch.dict(os.environ, env, clear=True), \
                patch("urllib.request.urlopen", side_effect=urlopen), \
                patch("time.monotonic", side_effect=[0, 901] if timeout else None, return_value=0), \
                patch("time.sleep"), \
                patch.object(Path, "write_text", new=write_receipt), \
                redirect_stdout(StringIO()):
            try:
                exec(program, {"__name__": "__main__"})
            except Exception as exc:
                error = exc
        self.assertEqual(1, len(written))
        return written[0], api, error

    def test_quota_failure_preserves_prior_visibility_change(self):
        receipt, api, error = self.run_guardian(private=True, stage="PAUSED", failure="restart")
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertIn("cpu-basic quota exhausted", receipt["error"])
        self.assertEqual(["visibility:private->public"], receipt["actions"])
        self.assertEqual("HF_FIXED_48H_INACTIVITY_CPU_BASIC", receipt["sleep_policy"])
        api.restart_space.assert_called_once_with(repo_id="fixture-owner/anatomy", factory_reboot=False)

    def test_failed_visibility_write_is_not_reported_completed(self):
        receipt, api, error = self.run_guardian(private=True, failure="visibility")
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertEqual([], receipt["actions"])
        api.restart_space.assert_not_called()
        api.set_space_sleep_time.assert_not_called()

    def test_completed_sleep_change_survives_later_restart_failure(self):
        receipt, api, error = self.run_guardian(stage="PAUSED", hardware="cpu-upgrade", failure="restart")
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertEqual(["sleep_time:-1"], receipt["actions"])
        self.assertEqual("NEVER_SLEEP_UPGRADED_HARDWARE", receipt["sleep_policy"])
        api.set_space_sleep_time.assert_called_once_with(repo_id="fixture-owner/anatomy", sleep_time=-1)

    def test_failed_sleep_write_is_not_reported_completed(self):
        receipt, api, error = self.run_guardian(hardware="cpu-upgrade", failure="sleep")
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertEqual([], receipt["actions"])
        self.assertNotIn("sleep_policy", receipt)
        api.restart_space.assert_not_called()

    def test_completed_restart_survives_readiness_failure(self):
        receipt, api, error = self.run_guardian(stage="BUILD_ERROR", failure="readiness")
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertEqual(["restart:BUILD_ERROR"], receipt["actions"])
        api.restart_space.assert_called_once_with(repo_id="fixture-owner/anatomy", factory_reboot=True)
        self.assertNotIn("live_contract", receipt)

    def test_completed_restart_survives_runtime_timeout(self):
        receipt, api, error = self.run_guardian(stage="PAUSED", timeout=True)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertEqual(["restart:PAUSED"], receipt["actions"])
        api.restart_space.assert_called_once()

    def test_missing_token_retains_empty_action_history(self):
        receipt, api, error = self.run_guardian(missing_token=True)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual("FAIL", receipt["status"])
        self.assertEqual([], receipt["actions"])
        self.assertEqual([], api.mock_calls)

    def test_success_keeps_exact_contract_and_completed_action_order(self):
        receipt, api, error = self.run_guardian(private=True, stage="PAUSED")
        self.assertIsNone(error)
        self.assertEqual("PASS", receipt["status"])
        self.assertEqual(["visibility:private->public", "restart:PAUSED"], receipt["actions"])
        self.assertEqual(SOURCE_SHA, receipt["live_contract"]["anatomy_source_revision"])
        self.assertEqual(575, receipt["live_contract"]["second_brain_public_chunks"])
        self.assertEqual("FORBIDDEN", receipt["hardware_mutation"])
        self.assertEqual("RUNNING", receipt["after"]["stage"])
        self.assertEqual("https://fixture-owner-anatomy.hf.space", receipt["origin"])
        api.set_space_sleep_time.assert_not_called()

    def test_unrouted_declared_alias_still_proves_canonical_host(self):
        canonical = "https://fixture-canonical-anatomy.hf.space"
        receipt, api, error = self.run_guardian(host=canonical, unrouted_alias=True)
        self.assertIsNone(error)
        self.assertEqual("PASS", receipt["status"])
        self.assertEqual(canonical, receipt["origin"])
        self.assertEqual("https://fixture-owner-anatomy.hf.space", receipt["declared_origin"])
        self.assertEqual(SOURCE_SHA, receipt["live_contract"]["anatomy_source_revision"])
        self.assertEqual(575, receipt["live_contract"]["second_brain_public_chunks"])
        api.restart_space.assert_not_called()

    def test_non_hf_space_host_fails_closed_before_mutation(self):
        receipt, api, error = self.run_guardian(host="https://evil.example/anatomy", stage="PAUSED")
        self.assertIsInstance(error, RuntimeError)
        self.assertIn("exact https hf.space origin", receipt["error"])
        self.assertEqual("FAIL", receipt["status"])
        self.assertNotIn("live_contract", receipt)
        self.assertEqual([], receipt["actions"])
        api.update_repo_settings.assert_not_called()
        api.restart_space.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
